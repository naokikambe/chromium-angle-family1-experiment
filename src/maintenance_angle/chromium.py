"""Parse public Chromium tag contents and resolve the DEPS ANGLE pin."""
from __future__ import annotations

import re

from .stable import VERSION_RE

REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_FIELDS = {"MAJOR", "MINOR", "BUILD", "PATCH"}


class SourceError(ValueError):
    pass


def parse_chrome_version(version_file: str) -> str:
    found: dict[str, str] = {}
    for line in version_file.splitlines():
        match = re.fullmatch(r"\s*(MAJOR|MINOR|BUILD|PATCH)\s*=\s*([0-9]+)\s*", line)
        if match:
            key, value = match.groups()
            if key in found:
                raise SourceError(f"duplicate Chrome version field: {key}")
            found[key] = value
    if set(found) != VERSION_FIELDS:
        raise SourceError("chrome/VERSION must provide MAJOR, MINOR, BUILD, and PATCH")
    version = ".".join(found[key] for key in ("MAJOR", "MINOR", "BUILD", "PATCH"))
    if not VERSION_RE.fullmatch(version):
        raise SourceError("chrome/VERSION is malformed")
    return version


def parse_angle_revision(deps_file: str) -> str:
    matches = re.findall(r"['\"]angle_revision['\"]\s*:\s*['\"]([0-9a-f]{40})['\"]", deps_file)
    if len(matches) != 1 or not REVISION_RE.fullmatch(matches[0]):
        raise SourceError("DEPS must contain exactly one full angle_revision pin")
    return matches[0]
