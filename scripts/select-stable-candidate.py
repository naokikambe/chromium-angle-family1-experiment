#!/usr/bin/env python3
"""Find the newest fully rolled out Mac Chrome Stable version."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.maintenance_angle.stable import ReleaseError, select_candidate  # noqa: E402
from src.maintenance_angle.versionhistory import fetch_releases  # noqa: E402

BASELINE = "156.0.8078.48"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default=BASELINE)
    parser.add_argument("--fixture", type=Path, help="synthetic VersionHistory JSON for offline use")
    parser.add_argument("--output", type=Path, help="write the selected candidate record to this path")
    args = parser.parse_args()
    try:
        payload = json.loads(args.fixture.read_text(encoding="utf-8")) if args.fixture else fetch_releases()
        candidate = select_candidate(payload, args.baseline)
    except (OSError, json.JSONDecodeError, TimeoutError, ReleaseError) as exc:
        print(f"stable release inspection failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    result = candidate or {"status": "no-new-fully-rolled-out-stable", "baseline": args.baseline}
    rendered = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
