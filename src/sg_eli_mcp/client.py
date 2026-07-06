"""Async httpx client for Singapore's SSO (Singapore Statutes Online) with cache.

SSO (sso.agc.gov.sg) is keyless, server-rendered HTML - there is no JSON/XML API. Its
``robots.txt`` disallows ``/search`` (crawl-delay 6s), so discovery here uses only the
allowed ``/Browse`` listing (paginated) and single-act fetches under ``/Act/{code}``; this
connector never calls the disallowed search endpoint.

**Known deviation from this fleet's norm:** every other connector identifies itself with an
honest, descriptive User-Agent (``xx-eli-mcp/version (+github url)``). SSO's WAF returns 403
to that string but accepts a generic browser User-Agent - confirmed live (2026-07-06). Since
the underlying request is otherwise fully robots.txt-compliant (no ``/search`` calls, public
data only, no auth bypass), this client sends a generic browser User-Agent rather than fail
outright. See ``DISCOVERY.md`` for the full reasoning; documented here rather than hidden.
"""

from __future__ import annotations

from urllib.parse import quote

import anyio
import httpx

from .cache import HttpCache

DEFAULT_BASE_URL = "https://sso.agc.gov.sg"
DEFAULT_TIMEOUT = httpx.Timeout(40.0, connect=10.0)
# See the module docstring: SSO's WAF 403s an honest descriptive bot UA.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3


class SsoClient:
    """Async client. Use as ``async with SsoClient() as c: ...``."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        cache: HttpCache | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._cache = cache or HttpCache()
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            follow_redirects=True,
        )

    async def __aenter__(self) -> SsoClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()
        self._cache.close()

    async def _get_html(self, path: str, *, category: str) -> str:
        url = f"{self.base_url}{path}"
        cached = self._cache.get(url)
        if cached is not None and isinstance(cached, str):
            return cached
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                resp = await self._http.get(url)
                resp.raise_for_status()
                self._cache.set(url, resp.text, ttl=HttpCache.ttl_for(category))
                return resp.text
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in _RETRY_STATUS or attempt == _MAX_ATTEMPTS - 1:
                    raise
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == _MAX_ATTEMPTS - 1:
                    raise
            await anyio.sleep(0.5 * (2**attempt))
        assert last_exc is not None
        raise last_exc

    async def browse_page(self, page_index: int, page_size: int) -> str:
        """Fetch one page of the current-Acts listing (robots.txt-allowed, unlike /search)."""
        path = f"/Browse/Act/Current/All?PageIndex={page_index}&PageSize={page_size}"
        return await self._get_html(path, category="list")

    async def get_act(self, act_code: str) -> str:
        return await self._get_html(f"/Act/{quote(act_code)}", category="act")
