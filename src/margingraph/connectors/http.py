"""A tiny JSON-over-HTTPS client on the standard library (no extra deps).

Retries 429 and 5xx with Retry-After or exponential backoff. The transport is
injectable so tests can mock HTTP without a network.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable


@dataclass
class Response:
    status: int
    headers: dict[str, str]  # lower-cased names
    data: object


# transport(method, url, headers, timeout) -> (status, headers, body bytes)
Transport = Callable[[str, str, dict, float], tuple[int, dict, bytes]]


def urllib_transport(method: str, url: str, headers: dict, timeout: float) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers.items()), e.read()


class HttpError(RuntimeError):
    pass


class HttpClient:
    def __init__(
        self,
        headers: dict | None = None,
        timeout: float = 30.0,
        max_retries: int = 5,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.headers = {"Accept": "application/json", "User-Agent": "margingraph-connector/0.1", **(headers or {})}
        self.timeout = timeout
        self.max_retries = max_retries
        self.transport = transport or urllib_transport
        self.sleep = sleep
        self.requests = 0

    def get(self, url: str, params: dict | None = None) -> Response:
        if params:
            q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url = f"{url}{'&' if '?' in url else '?'}{q}"
        for attempt in range(self.max_retries + 1):
            self.requests += 1
            status, headers, body = self.transport("GET", url, self.headers, self.timeout)
            headers = {k.lower(): v for k, v in headers.items()}
            if status == 429 or status >= 500:
                if attempt == self.max_retries:
                    break
                wait = headers.get("retry-after")
                try:
                    delay = float(wait) if wait else 2.0**attempt
                except ValueError:
                    delay = 2.0**attempt
                self.sleep(min(delay, 60.0))
                continue
            if status >= 400:
                raise HttpError(f"GET {_redact(url)} -> {status}: {body[:300]!r}")
            return Response(status, headers, json.loads(body or b"null"))
        raise HttpError(f"GET {_redact(url)} -> {status} after {self.max_retries} retries")


def next_link(link_header: str | None) -> str | None:
    """The rel="next" URL of an RFC 8288 Link header (Shopify pagination)."""
    if not link_header:
        return None
    for part in link_header.split(","):
        m = re.match(r'\s*<([^>]+)>\s*;\s*rel="?next"?', part)
        if m:
            return m.group(1)
    return None


def _redact(url: str) -> str:
    return re.sub(r"(consumer_(key|secret)=)[^&]+", r"\1***", url)
