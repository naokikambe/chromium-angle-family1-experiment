#!/usr/bin/env python3
"""Capture one narrowly scoped Chromium OSCrypt histogram through browser CDP."""
from __future__ import annotations

from datetime import datetime, timezone

HISTOGRAM = "OSCrypt.Mac.FindGenericPasswordResult"
SOURCE_REVISION = "82303c21a18acdc256c6264cd2ed0e1588df99d4"


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def capture(cdp, launch_pid, profile):
    record = {"schema": "phase5-oscrypt-keychain-histogram-v1", "histogram": HISTOGRAM,
              "source_revision": SOURCE_REVISION, "observed_at": timestamp(),
              "launch_pid": launch_pid, "profile": str(profile),
              "browser_pid": None, "status": "unavailable", "found": None,
              "bucket_counts": None, "sample_count": None, "sample_sum": None,
              "error": None}
    try:
        if isinstance(launch_pid, bool) or not isinstance(launch_pid, int) or launch_pid <= 0:
            raise ValueError("invalid launch PID")
        processes = cdp.call("SystemInfo.getProcessInfo").get("processInfo")
        if not isinstance(processes, list):
            raise ValueError("process list unavailable")
        browser = [p for p in processes if isinstance(p, dict) and p.get("type") == "browser"]
        if len(browser) != 1 or type(browser[0].get("id")) is not int:
            raise ValueError("browser process identity unavailable")
        record["browser_pid"] = browser[0]["id"]
        if record["browser_pid"] != launch_pid:
            raise ValueError("browser process does not match launch PID")
        response = cdp.call("Browser.getHistograms", {"query": HISTOGRAM, "delta": False})
        histograms = response.get("histograms")
        if not isinstance(histograms, list):
            raise ValueError("histogram response malformed")
        matches = [h for h in histograms if isinstance(h, dict) and h.get("name") == HISTOGRAM]
        if len(matches) != 1:
            raise ValueError("exact histogram missing or duplicated")
        histogram = matches[0]
        total_count, sample_sum = histogram.get("count"), histogram.get("sum")
        if type(total_count) is not int or total_count <= 0:
            raise ValueError("invalid histogram total count")
        if type(sample_sum) is not int:
            raise ValueError("invalid histogram sample sum")
        buckets = histogram.get("buckets")
        if not isinstance(buckets, list) or not buckets:
            raise ValueError("histogram buckets missing")
        clean, previous_high, found_counts, other_counts, bucket_total, bucket_sum = [], None, 0, 0, 0, 0
        for bucket in buckets:
            if not isinstance(bucket, dict):
                raise ValueError("malformed histogram bucket")
            low, high, count = bucket.get("low"), bucket.get("high"), bucket.get("count")
            if any(type(n) is not int for n in (low, high, count)) or count <= 0 or low >= high:
                raise ValueError("invalid histogram bounds or count")
            if previous_high is not None and low != previous_high:
                raise ValueError("overlapping or unordered histogram buckets")
            if (low, high) not in ((0, 1), (1, 2), (2, 3)):
                raise ValueError("unsupported enum bucket bounds")
            previous_high = high
            clean.append({"low": low, "high": high, "count": count})
            bucket_total += count
            bucket_sum += low * count
            if low <= 0 and high > 0:
                if low != 0 or high != 1:
                    raise ValueError("bucket straddles the PasswordFound enum value")
                found_counts += count
            else:
                other_counts += count
        if bucket_total != total_count or bucket_sum != sample_sum:
            raise ValueError("histogram totals do not match buckets")
        if found_counts and other_counts:
            raise ValueError("contradictory found and other enum buckets")
        if found_counts and sample_sum != 0:
            raise ValueError("PasswordFound bucket contradicts histogram sum")
        if other_counts and len(clean) > 1:
            raise ValueError("multiple enum outcomes are contradictory")
        record.update({"bucket_counts": clean, "sample_count": total_count,
                       "sample_sum": sample_sum, "found": bool(found_counts),
                       "status": "verified_found" if found_counts else "verified_other"})
    except Exception as exc:
        detail = str(exc) if isinstance(exc, ValueError) else "CDP request failed"
        record["error"] = f"{type(exc).__name__}: {detail}"
    return record
