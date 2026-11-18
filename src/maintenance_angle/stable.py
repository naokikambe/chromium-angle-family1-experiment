"""Select fully rolled out Mac Chrome Stable releases from VersionHistory."""
from __future__ import annotations

import json
import re
from typing import Any

VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class ReleaseError(ValueError):
    pass


def version_key(value: str) -> tuple[int, int, int, int]:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ReleaseError("Chrome version must contain four numeric components")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def select_candidate(payload: Any, baseline: str) -> dict[str, Any] | None:
    """Return the newest currently served 100% Mac Stable above baseline.

    VersionHistory's API is already scoped to ``mac`` and ``stable`` by the
    caller. The end-time and rollout checks are repeated here so a malformed or
    unexpectedly broad API response fails closed.
    """
    baseline_key = version_key(baseline)
    if not isinstance(payload, dict) or not isinstance(payload.get("releases"), list):
        raise ReleaseError("VersionHistory response has no releases list")
    candidates: list[tuple[tuple[int, int, int, int], dict[str, Any]]] = []
    for release in payload["releases"]:
        if not isinstance(release, dict):
            continue
        version = release.get("version")
        if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
            continue
        serving = release.get("serving")
        if not isinstance(serving, dict) or not serving.get("startTime") or serving.get("endTime"):
            continue
        fraction = release.get("fraction")
        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
            raise ReleaseError("release fraction must be numeric")
        if not 0.0 <= float(fraction) <= 1.0:
            raise ReleaseError("release fraction is outside 0..1")
        key = version_key(version)
        if key <= baseline_key or float(fraction) != 1.0:
            continue
        candidates.append((key, {
            "chrome_version": version,
            "release_name": release.get("name"),
            "fraction": float(fraction),
            "serving_start": serving["startTime"],
            "status": "stable-fully-rolled-out",
        }))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def select_from_json(data: str, baseline: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ReleaseError("VersionHistory response is not valid JSON") from exc
    return select_candidate(payload, baseline)
