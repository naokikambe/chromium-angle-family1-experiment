#!/usr/bin/env python3
"""Run one bounded autoninja target in a supervised process group."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


PROGRESS_RE = re.compile(rb"\[(\d+)/(\d+)\]")
PROGRESS_SAMPLE_SECONDS = 60
LOG_TAIL_LINES = 100
LOG_SCAN_BYTES = 1024 * 1024
TERM_GRACE_SECONDS = 10
KILL_WAIT_SECONDS = 5
_termination_signal: int | None = None


def _record_signal(signum: int, _frame: object) -> None:
    global _termination_signal
    _termination_signal = signum


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_process_group(pgid: int, signum: int) -> None:
    try:
        os.killpg(pgid, signum)
    except ProcessLookupError:
        pass


def _stop_process_group(process: subprocess.Popen[bytes]) -> bool:
    """Terminate every process started by autoninja, escalating if needed."""
    pgid = process.pid
    if not _process_group_exists(pgid):
        process.poll()
        return True

    print("small_target_process_group_signal=SIGTERM", flush=True)
    _signal_process_group(pgid, signal.SIGTERM)
    deadline = time.monotonic() + TERM_GRACE_SECONDS
    while time.monotonic() < deadline:
        process.poll()
        if not _process_group_exists(pgid):
            return True
        time.sleep(0.1)

    if _process_group_exists(pgid):
        print("small_target_process_group_signal=SIGKILL", flush=True)
        _signal_process_group(pgid, signal.SIGKILL)

    deadline = time.monotonic() + KILL_WAIT_SECONDS
    while time.monotonic() < deadline:
        process.poll()
        if not _process_group_exists(pgid):
            return True
        time.sleep(0.1)
    return not _process_group_exists(pgid)


def _read_latest_progress(build_log: Path) -> tuple[str, str]:
    try:
        size = build_log.stat().st_size
        with build_log.open("rb") as stream:
            stream.seek(max(0, size - LOG_SCAN_BYTES))
            contents = stream.read()
    except OSError:
        return "unknown", "unknown"

    matches = PROGRESS_RE.findall(contents)
    if not matches:
        return "unknown", "unknown"
    completed, total = matches[-1]
    return completed.decode("ascii"), total.decode("ascii")


def _sample_progress(
    build_log: Path, progress_log: Path, started: float, *, final: bool = False
) -> None:
    elapsed = max(0, int(time.monotonic() - started))
    completed, total = _read_latest_progress(build_log)
    if completed.isdigit() and total.isdigit() and elapsed > 0:
        completed_count = int(completed)
        total_count = int(total)
        remaining = max(0, total_count - completed_count)
        rate = f"{completed_count / elapsed:.4f}"
        estimate = (
            str(int(remaining / (completed_count / elapsed)))
            if completed_count > 0
            else "unknown"
        )
    else:
        remaining = "unknown"
        rate = "unknown"
        estimate = "unknown"

    sample = (
        f"sample_utc={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} "
        f"elapsed_seconds={elapsed} tasks_completed={completed} tasks_total={total} "
        f"tasks_remaining={remaining} completed_per_second={rate} "
        f"estimated_remaining_seconds={estimate}"
    )
    with progress_log.open("a", encoding="utf-8") as stream:
        stream.write(sample + "\n")
    suffix = " final=true" if final else ""
    print(f"small_target_progress {sample}{suffix}", flush=True)


def _print_build_log_tail(build_log: Path) -> None:
    print(f"small_target_build_log_tail_begin lines={LOG_TAIL_LINES}", flush=True)
    try:
        with build_log.open("r", encoding="utf-8", errors="replace") as stream:
            lines = stream.readlines()[-LOG_TAIL_LINES:]
    except OSError as error:
        print(f"small_target_build_log_unavailable={error}", flush=True)
        lines = []
    for line in lines:
        print(line.rstrip("\r\n"), flush=True)
    print("small_target_build_log_tail_end", flush=True)


def _positive_seconds(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer number of seconds") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least one second")
    return parsed


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--build-log", required=True, type=Path)
    parser.add_argument("--progress-log", required=True, type=Path)
    parser.add_argument("--timeout-marker", required=True, type=Path)
    parser.add_argument("--budget-seconds", required=True, type=_positive_seconds)
    return parser.parse_args()


def _main() -> int:
    args = _arguments()
    if not args.cwd.is_dir():
        print(f"build working directory does not exist: {args.cwd}", file=sys.stderr)
        return 2

    signal.signal(signal.SIGINT, _record_signal)
    signal.signal(signal.SIGTERM, _record_signal)

    command = ["autoninja", "-C", "out/Phase5Preflight", args.target]
    started = time.monotonic()
    deadline = started + args.budget_seconds
    next_sample = started
    process: subprocess.Popen[bytes] | None = None
    cleanup_ok = True

    try:
        with args.build_log.open("wb") as build_stream:
            process = subprocess.Popen(
                command,
                cwd=args.cwd,
                stdout=build_stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        print(f"small_target_process_group={process.pid}", flush=True)
        _sample_progress(args.build_log, args.progress_log, started)
        next_sample = started + PROGRESS_SAMPLE_SECONDS

        while True:
            return_code = process.poll()
            now = time.monotonic()

            if _termination_signal is not None:
                signum = _termination_signal
                print(f"small_target_supervisor_signal={signum}", flush=True)
                cleanup_ok = _stop_process_group(process)
                _sample_progress(args.build_log, args.progress_log, started, final=True)
                _print_build_log_tail(args.build_log)
                return 128 + signum if cleanup_ok else 125

            if return_code is not None:
                break

            if now >= deadline:
                args.timeout_marker.touch()
                print(
                    f"small_target_watchdog=timeout budget_seconds={args.budget_seconds}",
                    flush=True,
                )
                cleanup_ok = _stop_process_group(process)
                _sample_progress(args.build_log, args.progress_log, started, final=True)
                _print_build_log_tail(args.build_log)
                if not cleanup_ok:
                    print("small_target_process_group_cleanup=failed", flush=True)
                return 124

            if now >= next_sample:
                _sample_progress(args.build_log, args.progress_log, started)
                next_sample = now + PROGRESS_SAMPLE_SECONDS

            time.sleep(min(1, max(0, deadline - now)))

        return_code = process.wait()
        cleanup_ok = _stop_process_group(process)
        _sample_progress(args.build_log, args.progress_log, started, final=True)
        print(f"small_target_build_exit={return_code}", flush=True)
        if return_code != 0 or not cleanup_ok:
            _print_build_log_tail(args.build_log)
        if not cleanup_ok:
            print("small_target_process_group_cleanup=failed", flush=True)
            return 125
        return return_code if return_code >= 0 else 128 + abs(return_code)
    finally:
        if process is not None and _process_group_exists(process.pid):
            cleanup_ok = _stop_process_group(process) and cleanup_ok
        if process is not None:
            process.poll()
        if not cleanup_ok:
            print("small_target_process_group_cleanup=failed", file=sys.stderr, flush=True)


if __name__ == "__main__":
    raise SystemExit(_main())
