"""Read the official Chrome VersionHistory Mac Stable endpoint."""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .stable import ReleaseError

ENDPOINT = "https://versionhistory.googleapis.com/v1/chrome/platforms/mac/channels/stable/versions/all/releases"


def fetch_releases() -> dict:
    token = None
    pages = []
    seen_tokens = set()
    while True:
        query = {"filter": "endtime=none", "pageSize": "100"}
        if token:
            if token in seen_tokens:
                raise ReleaseError("VersionHistory pagination repeated a page token")
            seen_tokens.add(token)
            query["pageToken"] = token
        request = Request(ENDPOINT + "?" + urlencode(query), headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=20) as response:
                page = json.load(response)
        except Exception as exc:
            raise ReleaseError("VersionHistory request failed") from exc
        if not isinstance(page, dict) or not isinstance(page.get("releases"), list):
            raise ReleaseError("VersionHistory returned an unexpected response")
        pages.extend(page["releases"])
        token = page.get("nextPageToken")
        if not token:
            break
    return {"releases": pages}
