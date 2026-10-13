#!/usr/bin/env python3
"""Scan the staged Git snapshot and commit identities for privacy hazards."""

from __future__ import annotations

import argparse
import ipaddress
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_RANGES = tuple(
    ipaddress.ip_network(value)
    for value in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
)
IPV6_DOC_RANGE = ipaddress.ip_network("2001:db8::/32")
SAFE_EXAMPLE_EMAIL_DOMAINS = ("example.com", "invalid", "localhost")
# Public Chromium/Google code-signing fixture only; owner identities are never
# allowlisted. Keep this exception tied to the exact labeled team field.
PUBLIC_FIXTURE_TEAM_IDS = {"EQHXZ8M8AV"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    category: str


def git(root: Path, *args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("git operation failed")
    return result.stdout


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return lowered in {"<placeholder>", "<name>", "<user>", "<username>", "example", "synthetic-user"}


def source_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    # Construct the MAC pattern without embedding an address-shaped literal in
    # this scanner's own source.
    octet = r"[A-Fa-f0-9]{2}"
    mac = re.compile(rf"(?<![A-Fa-f0-9])(?:{octet}[:-]){{5}}{octet}(?![A-Fa-f0-9])")
    return (
        ("home-path", re.compile(r"(?<![A-Za-z0-9_])/(?:Users|home)/([^/\s:]+)")),
        ("email", re.compile(r"(?i)(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9.-])")),
        ("ipv4", re.compile(r"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])")),
        ("ipv6", re.compile(r"(?<![A-Za-z0-9_:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![A-Za-z0-9_:])")),
        ("mac-address", mac),
        ("certificate-identity", re.compile(r"(?i)Apple (?:Development|Distribution):\s*[^\n()]{2,100}\([A-Z0-9]{10}\)")),
        ("team-identifier", re.compile(r"(?i)\b(team(?:[ _]+(?:identifier|id))?|teamidentifier)([\"']?)\s*([:=])\s*([\"']?)([A-Z0-9]{10})(?![A-Z0-9])\4")),
        ("certificate-fingerprint", re.compile(r"(?i)\b(?:certificate|cert)[ _]+(?:sha-?256|fingerprint)[\"']?\s*[:=]\s*[\"']?[A-F0-9: -]{32,}?[\"']?(?=[,}\s]|$)")),
        ("device-identifier", re.compile(r"(?i)\b(?:serial(?:[ _]+number)?|udid|device[ _]+id)[\"']?\s*[:=]\s*[\"']?[^\s,;\"'}]{4,}[\"']?")),
        ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
        ("credential-token", re.compile(r"(?i)\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b")),
    )


PATTERNS = source_patterns()
EVIDENCE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic",
    ".mov", ".mp4", ".m4v", ".webm", ".mkv", ".avi", ".wav", ".m4a",
    ".log", ".trace", ".crash", ".ips", ".pcap", ".netlog", ".har", ".sqlite", ".db",
    ".keychain", ".keychain-db", ".p12", ".pfx",
}
EVIDENCE_COMPONENTS = {
    "profile", "profiles", "cookies", "login data", "keychain", "keychain-db",
    "sysdiagnose", "device-receipt", "device-receipts", "screenshot", "screenshots",
    "recording", "recordings", "capture", "captures", "gpu-info", "securityd",
}
EVIDENCE_FILENAMES = {
    "typescript", "cookies", "login data", "history", "local state", "preferences",
    "web data", "signing-receipt.json", "signing_receipt.json", "receipt.json",
}
PLACEHOLDER_COMPONENTS = {"<placeholder>", "synthetic-profile", "synthetic-cookie"}


def is_github_noreply(address: str) -> bool:
    return re.fullmatch(r"(?:[0-9]+\+)?[A-Za-z0-9-]+@users\.noreply\.github\.com", address, re.I) is not None


def is_public_account_alias(name: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9-]{1,39}", name) is not None


def scan_line(path: str, line_number: int, line: str, deny_values: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for category, pattern in PATTERNS:
        for match in pattern.finditer(line):
            value = match.group(0)
            if (category == "team-identifier" and match.group(1).casefold() == "teamidentifier"
                    and match.group(2) == "" and match.group(3) == "=" and match.group(4) == ""
                    and match.group(5) in PUBLIC_FIXTURE_TEAM_IDS):
                continue
            if category == "home-path" and is_placeholder(match.group(1)):
                continue
            if category == "email":
                domain = value.rsplit("@", 1)[1].lower()
                if is_github_noreply(value) or any(domain == suffix or domain.endswith("." + suffix)
                                                   for suffix in SAFE_EXAMPLE_EMAIL_DOMAINS):
                    continue
            if category in {"ipv4", "ipv6"}:
                try:
                    address = ipaddress.ip_address(value)
                except ValueError:
                    continue
                if (address.is_loopback or address.is_unspecified
                        or (address.version == 4 and any(address in net for net in DOC_RANGES))
                        or (address.version == 6 and address in IPV6_DOC_RANGE)):
                    continue
            findings.append(Finding(path, line_number, category))
    folded = line.casefold()
    for value in deny_values:
        if value and value.casefold() in folded:
            findings.append(Finding(path, line_number, "owner-deny-value"))
            break
    return findings


def scan_path(path: str) -> list[Finding]:
    name = Path(path).name.casefold()
    parts = {part.casefold() for part in Path(path).parts}
    findings: list[Finding] = []
    if Path(name).suffix.casefold() in EVIDENCE_SUFFIXES:
        findings.append(Finding(path, 0, "evidence-file-type"))
    if name in EVIDENCE_FILENAMES or name.startswith("typescript."):
        findings.append(Finding(path, 0, "evidence-file-name"))
    if any(part in EVIDENCE_COMPONENTS for part in parts) and not any(
        placeholder in parts for placeholder in PLACEHOLDER_COMPONENTS
    ):
        findings.append(Finding(path, 0, "evidence-file-name"))
    return findings


def staged_blobs(root: Path) -> list[tuple[str, bytes]]:
    records = git(root, "ls-files", "--stage", "-z").split(b"\0")
    blobs: list[tuple[str, bytes]] = []
    for record in records:
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, oid, stage = header.decode("ascii").split()
        path = raw_path.decode("utf-8", "surrogateescape")
        if stage != "0":
            raise RuntimeError("unmerged index entries must be resolved before scanning")
        if mode not in {"100644", "100755", "120000"}:
            blobs.append((path, b"\x00"))
            continue
        blobs.append((path, git(root, "cat-file", "blob", oid)))
    return blobs


def tree_blobs(root: Path, ref: str) -> list[tuple[str, bytes]]:
    records = git(root, "ls-tree", "-r", "-z", "--full-tree", ref).split(b"\0")
    blobs: list[tuple[str, bytes]] = []
    for record in records:
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, object_type, oid = header.decode("ascii").split()
        path = raw_path.decode("utf-8", "surrogateescape")
        if object_type != "blob" or mode not in {"100644", "100755", "120000"}:
            blobs.append((path, b"\x00"))
            continue
        blobs.append((path, git(root, "cat-file", "blob", oid)))
    return blobs


def identity_findings(root: Path, tree: str | None) -> list[Finding]:
    if tree:
        output = git(root, "log", "-1", "--format=%an%x00%ae%x00%cn%x00%ce", tree).decode("utf-8", "replace")
        fields = output.strip("\n\0").split("\0")
        identities = [(fields[index], fields[index + 1]) for index in range(0, len(fields) - 1, 2)]
        label = "commit"
    else:
        identities = []
        for variable in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
            raw = git(root, "var", variable).decode("utf-8", "replace").strip()
            match = re.search(r"^(.*?) <([^<>]+)>", raw)
            identities.append((match.group(1), match.group(2)) if match else ("", ""))
        label = "configured"
    result: list[Finding] = []
    for index, (name, address) in enumerate(identities):
        role = "author" if index == 0 else "committer"
        if not is_public_account_alias(name):
            result.append(Finding(f"<{label}-metadata>", 0, f"{role}-name"))
        if not is_github_noreply(address):
            result.append(Finding(f"<{label}-metadata>", 0, f"{role}-email"))
    return result


def inspect(root: Path, tree: str | None, deny_values: list[str]) -> list[Finding]:
    findings = identity_findings(root, tree)
    blobs = tree_blobs(root, tree) if tree else staged_blobs(root)
    findings.extend(scan_blobs(blobs, deny_values))
    return findings


def scan_blobs(blobs: list[tuple[str, bytes]], deny_values: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for path, content in blobs:
        findings.extend(scan_path(path))
        if b"\x00" in content:
            findings.append(Finding(path, 0, "binary-content"))
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(Finding(path, 0, "non-text-content"))
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            findings.extend(scan_line(path, line_number, line, deny_values))
    return findings


def pre_push_findings(root: Path, input_bytes: bytes, deny_values: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    zero = "0" * 40
    for raw_line in input_bytes.splitlines():
        if not raw_line.strip():
            continue
        fields = raw_line.decode("utf-8", "replace").split()
        if len(fields) != 4:
            raise RuntimeError("invalid pre-push input")
        _local_ref, local_sha, _remote_ref, remote_sha = fields
        if not re.fullmatch(r"[0-9a-fA-F]{40}", local_sha) or not re.fullmatch(r"[0-9a-fA-F]{40}", remote_sha):
            raise RuntimeError("invalid pre-push revision")
        if local_sha == zero:
            continue
        args = ["rev-list", local_sha]
        if remote_sha != zero:
            args.extend(["--not", remote_sha])
        commits = git(root, *args).decode("ascii", "replace").splitlines()
        for commit in commits:
            findings = identity_findings(root, commit)
            if findings:
                return findings
            findings = scan_blobs(tree_blobs(root, commit), deny_values)
            if findings:
                return findings
            message = git(root, "log", "-1", "--format=%B", commit)
            findings = scan_blobs([("<commit-message>", message)], deny_values)
            if findings:
                return findings
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--tree", help="scan a committed Git tree/ref instead of the index")
    parser.add_argument("--pre-push", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--commit-message", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--deny-value", action="append", default=[], help="additional owner-supplied value to detect")
    args = parser.parse_args(argv)
    if sum((bool(args.pre_push), bool(args.tree), bool(args.commit_message))) > 1:
        parser.error("choose only one scan mode")
    try:
        if args.pre_push:
            findings = pre_push_findings(args.repo.resolve(), sys.stdin.buffer.read(), args.deny_value)
        elif args.commit_message:
            findings = scan_blobs([("<commit-message>", args.commit_message.read_bytes())], args.deny_value)
        else:
            findings = inspect(args.repo.resolve(), args.tree, args.deny_value)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"privacy scan could not complete: {type(exc).__name__}", file=sys.stderr)
        return 2
    if findings:
        for finding in sorted(set(findings), key=lambda item: (item.path, item.line, item.category)):
            location = f":{finding.line}" if finding.line else ""
            print(f"{finding.path}{location}: {finding.category}")
        print(f"privacy scan failed: {len(set(findings))} finding(s)", file=sys.stderr)
        return 1
    print("publication privacy scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
