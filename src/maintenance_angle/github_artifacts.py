"""Read-only GitHub Actions artifact and run client for the monitor index."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

from .artifact import ArtifactError, is_unexpired
from .monitor_policy import (
    STATE_SCHEMA_V1, STATE_SCHEMA_V2, confirm_final_state,
    normalize_state, update_outcome,
)


class GitHubError(RuntimeError):
    pass


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _ArtifactRedirectHandler(HTTPRedirectHandler):
    """Allow the single HTTPS API-to-blob redirect used for artifact ZIPs."""

    def __init__(self):
        super().__init__()
        self.redirect_count = 0
        self.rejected = False

    @staticmethod
    def _is_allowed_storage_url(source_url: str, target_url: str) -> bool:
        try:
            source = urlsplit(source_url)
            target = urlsplit(target_url)
            source_port = source.port
            target_port = target.port
        except ValueError:
            return False

        host = (target.hostname or "").lower()
        is_github_artifact_storage = re.fullmatch(
            r"productionresultssa[0-9]+\.blob\.core\.windows\.net", host
        ) is not None
        return (
            source.scheme == "https"
            and source.hostname == "api.github.com"
            and source.username is None
            and source.password is None
            and source_port in (None, 443)
            and target.scheme == "https"
            and target.username is None
            and target.password is None
            and target_port in (None, 443)
            and is_github_artifact_storage
            and not target.fragment
        )

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        try:
            target_url = urljoin(req.full_url, newurl)
        except (TypeError, ValueError):
            self.rejected = True
            return None
        if (self.redirect_count != 1 or code != 302 or
                not self._is_allowed_storage_url(req.full_url, target_url)):
            self.rejected = True
            return None

        # Whitelist only the ZIP accept header. In particular, never copy
        # Authorization, cookies, or GitHub-specific headers to storage.
        return Request(target_url, headers={"Accept": "application/zip"},
                       origin_req_host=req.origin_req_host, unverifiable=True)


class GitHubActionsArtifacts:
    def __init__(self, repository: str, token: str | None = None):
        parts = repository.split("/")
        if len(parts) != 2 or any(not p or p in {".", ".."} for p in parts):
            raise GitHubError("repository must be OWNER/NAME")
        self.repository = repository
        self.token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    def _github_api_request(self, path: str) -> Request:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return Request(f"https://api.github.com/repos/{self.repository}/{path}", headers=headers)

    def _request(self, path: str) -> bytes:
        request = self._github_api_request(path)
        opener = build_opener(_NoRedirectHandler())
        try:
            with opener.open(request, timeout=30) as response:
                if response.status != 200:
                    raise GitHubError(f"GitHub Actions API request failed (HTTP {response.status})")
                return response.read()
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise GitHubError(f"GitHub Actions API request failed (HTTP {status})") from None
        except (URLError, TimeoutError, OSError):
            raise GitHubError("GitHub Actions API request failed (network)") from None

    def _pages(self, path: str, key: str, *, branch: str | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 1
        while True:
            query = f"per_page=100&page={page}"
            if branch:
                query += f"&branch={quote(branch, safe='')}"
            separator = "&" if "?" in path else "?"
            payload = json.loads(self._request(f"{path}{separator}{query}"))
            if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
                raise GitHubError("GitHub Actions API returned an unexpected response")
            batch = payload[key]
            results.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < 100:
                return results
            page += 1
            if page > 50:
                raise GitHubError("GitHub Actions API pagination limit exceeded")

    def artifacts(self) -> list[dict[str, Any]]:
        return self._pages("actions/artifacts", "artifacts")

    def workflow_runs(self, workflow_file: str) -> list[dict[str, Any]]:
        safe = quote(workflow_file, safe="")
        return self._pages(f"actions/workflows/{safe}/runs", "workflow_runs", branch="main")

    def download_artifact(self, artifact_id: int) -> bytes:
        if not isinstance(artifact_id, int) or artifact_id <= 0:
            raise GitHubError("invalid artifact ID")
        request = self._github_api_request(f"actions/artifacts/{artifact_id}/zip")
        redirects = _ArtifactRedirectHandler()
        opener = build_opener(redirects)
        try:
            with opener.open(request, timeout=30) as response:
                if response.status != 200:
                    raise GitHubError(f"GitHub artifact download failed (HTTP {response.status})")
                return response.read()
        except HTTPError as exc:
            status = exc.code
            exc.close()
            if redirects.rejected:
                raise GitHubError("GitHub artifact download redirect rejected") from None
            raise GitHubError(f"GitHub artifact download failed (HTTP {status})") from None
        except (URLError, TimeoutError, OSError):
            raise GitHubError("GitHub artifact download failed (network)") from None

    def read_json_artifact(self, artifact: dict[str, Any], filename: str) -> dict[str, Any]:
        if artifact.get("expired") is True or not is_unexpired(artifact.get("expires_at", "")):
            raise GitHubError("artifact has expired")
        data = self.download_artifact(int(artifact.get("id", 0)))
        try:
            with tempfile.TemporaryDirectory(prefix="angle-state-") as folder:
                archive = Path(folder) / "state.zip"
                archive.write_bytes(data)
                with zipfile.ZipFile(archive) as source:
                    names = source.namelist()
                    if names.count(filename) != 1 or any(name.startswith("/") or ".." in Path(name).parts for name in names):
                        raise GitHubError("state artifact archive has an unsafe layout")
                    value = json.loads(source.read(filename))
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError, KeyError) as exc:
            raise GitHubError("state artifact could not be read") from exc
        if not isinstance(value, dict):
            raise GitHubError("state artifact JSON is not an object")
        return value

    def load_latest_state(self, workflow_file: str) -> dict[str, Any] | None:
        artifacts = self.artifacts()
        completed = [r for r in self.workflow_runs(workflow_file) if r.get("status") == "completed"]
        completed.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
        if not completed and not any(self._is_state_artifact(a) for a in artifacts):
            # This is the first monitor run even if PR review or publication
            # happened long after the workflow file was introduced.
            return None
        for run in completed:
            run_id = str(run.get("id", ""))
            related = [a for a in artifacts
                       if self._is_state_artifact(a)
                       and str(a.get("workflow_run", {}).get("id", "")) == run_id
                       and a.get("workflow_run", {}).get("head_branch") == "main"]
            finals = [a for a in related if a.get("name") == "stable-monitor-state"]
            checkpoints = [a for a in related if a.get("name") == f"stable-monitor-checkpoint-{run_id}"]
            resolved_checkpoints = [a for a in related
                                    if a.get("name") == f"stable-monitor-resolved-checkpoint-{run_id}"]
            if finals:
                state = self._read_state_artifact(finals, "stable-monitor-state.json")
                try:
                    return confirm_final_state(state)
                except ValueError as exc:
                    raise GitHubError("final monitor state is malformed") from exc
            if resolved_checkpoints:
                state = self._read_state_artifact(resolved_checkpoints, "stable-monitor-state.json")
                return self._mark_interrupted_checkpoint(state, run_id)
            if checkpoints:
                state = self._read_state_artifact(checkpoints, "stable-monitor-state.json")
                return self._mark_interrupted_checkpoint(state, run_id)
            # A run without its required pre-build checkpoint could not have
            # started source resolution or a build. It is safe to consult the
            # preceding persisted state.
        raise GitHubError("state-lost: monitor has completed runs but no valid state or pre-build checkpoint")

    @staticmethod
    def _is_state_artifact(artifact: dict[str, Any]) -> bool:
        name = artifact.get("name")
        return name == "stable-monitor-state" or (
            isinstance(name, str) and name.startswith(("stable-monitor-checkpoint-",
                                                       "stable-monitor-resolved-checkpoint-"))
        )

    def _read_state_artifact(self, candidates: list[dict[str, Any]], filename: str) -> dict[str, Any]:
        candidates.sort(key=lambda a: str(a.get("created_at", "")), reverse=True)
        artifact = candidates[0]
        if artifact.get("expired") is True or not is_unexpired(artifact.get("expires_at", "")):
            raise GitHubError("state-lost: latest available state artifact has expired")
        state = self.read_json_artifact(artifact, filename)
        if state.get("schema") not in {STATE_SCHEMA_V1, STATE_SCHEMA_V2}:
            raise GitHubError("unsupported monitor state schema")
        try:
            return normalize_state(state)
        except ValueError as exc:
            raise GitHubError("monitor state is malformed") from exc

    @staticmethod
    def _mark_interrupted_checkpoint(state: dict[str, Any], run_id: str) -> dict[str, Any]:
        try:
            state = normalize_state(state)
        except ValueError as exc:
            raise GitHubError("checkpoint monitor state is malformed") from exc
        records = state["records"]
        for record in records:
            if not isinstance(record, dict) or str(record.get("run_id", "")) != run_id:
                continue
            if record.get("status") in {"STABLE_RELEASE_DETECTED", "REACQUIRE_REQUESTED", "RETRY_REQUESTED"}:
                if record.get("input_resolution_status") == "resolved":
                    failure_stage = "run-interrupted-after-input-resolution"
                elif record.get("source_resolution_status") == "resolved":
                    failure_stage = "run-interrupted-after-source-resolution"
                else:
                    failure_stage = "run-interrupted-before-source-resolution"
                record.update({"status": "CI_BUILD_INTERRUPTED",
                               "reason": failure_stage,
                               "failure_stage": failure_stage})
                update_outcome(state, record)
        return state

    def find_artifact(self, name: str) -> dict[str, Any] | None:
        matches = [a for a in self.artifacts() if a.get("name") == name]
        matches.sort(key=lambda a: str(a.get("created_at", "")), reverse=True)
        return matches[0] if matches else None


def usable_artifact(artifact: dict[str, Any] | None) -> bool:
    return bool(artifact and artifact.get("expired") is not True and
                is_unexpired(artifact.get("expires_at", "")))
