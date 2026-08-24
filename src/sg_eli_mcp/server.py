"""FastMCP entry point - Singapore SSO (Singapore Statutes Online) tools.

Run:

    python -m sg_eli_mcp.server

Configuration via env:

- ``SG_ELI_CACHE_DIR`` (default ``~/.matematic/cache/sg-eli``)
- ``SG_ELI_AUDIT_DIR`` (default ``~/.matematic/audit``)
- ``SG_ELI_BASE_URL`` (default ``https://sso.agc.gov.sg``)
"""

from __future__ import annotations

import os

import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import html_tree
from .audit import AuditLogger, hash_input, timer
from .citations import build_act_summary, extract_provision, parse_browse_page
from . import runtime
from .client import DEFAULT_BASE_URL, SsoClient
from .models import ActListResult, ActSummary, ActText, ProvisionText
from .coverage import Coverage, build_coverage

_MAX_FULL_TEXT_CHARS = 300_000

INSTRUCTIONS = """\
This MCP server exposes Singapore Statutes Online (SSO, sso.agc.gov.sg), the Attorney-General's Chambers' official portal for Singapore legislation. Singapore has no ELI scheme; every response carries a stable `eli_uri` (the durable SSO act URL, keyed on SSO's own short act code), a `human_readable_citation` (the act title as SSO renders it) and a `source_url`. See `eli_note` on every response for the honest explanation.

## Call order

1. `sg_list_acts` - browse the current Acts (paginated with `page_index`, `page_size`). Returns `act_code` for each act (e.g. `CoA1967` for the Companies Act 1967). SSO's `robots.txt` disallows `/search`, so this tool paginates the allowed `/Browse` listing instead of a keyword search - there is no free-text search tool.
2. `sg_get_provision` - the text of one numbered section of an act, by `act_code` and `provision_num` (the plain section number, e.g. `"1"`).
3. `sg_get_full_text` - the full text of an act by `act_code`. Large acts are truncated at roughly 300,000 characters; prefer `sg_get_provision` for a specific section.

## Hard constraints

- **Do not answer past the edge of this corpus** - when a search comes back empty, or the question touches material this connector does not carry, call `sg_coverage` and relay what it says is missing. Absence here is not absence in the law.
- **No native ELI** - Singapore has not deployed ELI. `eli_uri` is the SSO act URL (`https://sso.agc.gov.sg/Act/{act_code}`), never invented; see `eli_note`.
- **No keyword search** - `/search` is disallowed by SSO's `robots.txt`; discovery is by browsing (`sg_list_acts`), not by title or keyword query.
- **Every response has `human_readable_citation` + `source_url`** - cite both to the user.
- **No modification of official text** - returned verbatim from SSO.
- **Audit log JSONL** - every tool call appends to `~/.matematic/audit/sg-eli-mcp.jsonl`.

## Error iteration

Tools return a structured error with a `[code]` prefix:
- `invalid_arg` - a parameter is missing, empty, or out of range.
- `not_found` - no act matches that `act_code`, or no section matches that `provision_num`.
- `upstream_error` - an SSO error (HTTP, timeout, malformed HTML). Retry once before surfacing.

## Response style

- Cite acts as `human_readable_citation` with the SSO URL: "Companies Act 1967, https://sso.agc.gov.sg/Act/CoA1967".
- NEVER invent an `act_code`, `eli_uri` or section number - take each from the tool output.
"""


class ToolError(Exception):
    """Structured error for sg-eli MCP tools - visible to the LLM with a [code] prefix."""

    VALID_CODES = frozenset({"invalid_arg", "not_found", "upstream_error"})

    def __init__(self, code: str, message: str):
        if code not in self.VALID_CODES:
            raise ValueError(f"Unknown ToolError code: {code}. Valid: {sorted(self.VALID_CODES)}")
        self.code = code
        super().__init__(f"[{code}] {message}")


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,
)

mcp: FastMCP = FastMCP(name="sg-eli-mcp", instructions=INSTRUCTIONS)


def _base_url() -> str:
    return os.environ.get("SG_ELI_BASE_URL", runtime.base_url("eli", DEFAULT_BASE_URL)).rstrip("/")


def _audit() -> AuditLogger:
    return AuditLogger()


def _map_upstream(exc: Exception) -> Exception:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return ToolError("not_found", "No act found on SSO for that act_code.")
    if isinstance(exc, (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException)):
        return ToolError("upstream_error", f"SSO error: {type(exc).__name__}: {exc}")
    return exc


# ---------------------------------------------------------------------------
# sg_list_acts
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def sg_list_acts(page_index: int = 1, page_size: int = 20) -> ActListResult:
    """Browse Singapore's current Acts (paginated - SSO has no keyword search API).

    Args:
        page_index: 1-based page number (default 1).
        page_size: results per page, 1-100 (default 20).

    Returns:
        ``ActListResult`` with ``items: list[ActSummary]``, each carrying the citation contract.
    """
    audit = _audit()
    if page_index < 1:
        raise ToolError("invalid_arg", f"page_index={page_index} must be >= 1.")
    if not 1 <= page_size <= 100:
        raise ToolError("invalid_arg", f"page_size={page_size} must be in 1..100.")
    input_hash = hash_input({"page_index": page_index, "page_size": page_size})

    with timer() as t:
        try:
            async with SsoClient(base_url=_base_url()) as client:
                html = await client.browse_page(page_index, page_size)
        except Exception as exc:
            audit.log(tool="sg_list_acts", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    rows = parse_browse_page(html)
    items = [
        ActSummary.model_validate(
            {
                "act_code": row["act_code"],
                "title": row["title"],
                "human_readable_citation": row["title"],
                "eli_uri": f"https://sso.agc.gov.sg/Act/{row['act_code']}",
                "source_url": f"https://sso.agc.gov.sg/Act/{row['act_code']}",
            }
        )
        for row in rows
    ]
    result = ActListResult(page_index=page_index, page_size=page_size, items=items)
    audit.log(tool="sg_list_acts", input_hash=input_hash, output_count_or_size=len(items),
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# sg_get_provision
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def sg_get_provision(act_code: str, provision_num: str) -> ProvisionText:
    """Fetch the text of one numbered section of an act.

    Args:
        act_code: SSO's short act code, e.g. ``"CoA1967"`` (Companies Act 1967).
        provision_num: the plain section number, e.g. ``"1"``.

    Returns:
        ``ProvisionText`` with ``eli_uri``, ``human_readable_citation``, ``source_url`` and ``text``.
    """
    audit = _audit()
    if not act_code.strip():
        raise ToolError("invalid_arg", "act_code must not be empty.")
    if not provision_num.strip():
        raise ToolError("invalid_arg", "provision_num must not be empty.")
    input_hash = hash_input({"act_code": act_code, "provision_num": provision_num})

    with timer() as t:
        try:
            async with SsoClient(base_url=_base_url()) as client:
                html = await client.get_act(act_code)
        except Exception as exc:
            audit.log(tool="sg_get_provision", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    provision = extract_provision(html, provision_num)
    if provision is None:
        raise ToolError(
            "not_found", f"No section {provision_num!r} in act_code={act_code!r}."
        )
    meta = build_act_summary(act_code, html)
    result = ProvisionText(
        act_code=act_code,
        provision_num=provision_num,
        caption=provision.get("caption"),
        text=provision.get("text"),
        eli_uri=meta.get("eli_uri"),
        human_readable_citation=meta.get("human_readable_citation"),
        source_url=meta.get("source_url"),
    )
    audit.log(tool="sg_get_provision", input_hash=input_hash,
              output_count_or_size=len(provision.get("text") or ""),
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# sg_get_full_text
@mcp.tool(annotations=READ_ONLY)
async def sg_coverage() -> Coverage:
    """Declare what this connector covers, how it is sourced, and what it does NOT cover.

    Call this before telling a user that the law "does not contain" something, and whenever
    a search comes back empty: the absence may be a gap in this connector rather than in the
    law. Every gap carries a fallback saying where to look instead.

    Returns:
        ``Coverage`` with families, an as-of note, and a non-empty list of known gaps.
    """
    return build_coverage()


# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def sg_get_full_text(act_code: str) -> ActText:
    """Fetch the full text of an act. Large acts are truncated.

    Args:
        act_code: SSO's short act code, e.g. ``"CoA1967"`` (Companies Act 1967).

    Returns:
        ``ActText`` with ``eli_uri``, ``human_readable_citation``, ``source_url``, ``content``
        and ``truncated`` (True if the text was cut at ~300,000 characters - use
        ``sg_get_provision`` for a specific section instead).
    """
    audit = _audit()
    if not act_code.strip():
        raise ToolError("invalid_arg", "act_code must not be empty.")
    input_hash = hash_input({"act_code": act_code})

    with timer() as t:
        try:
            async with SsoClient(base_url=_base_url()) as client:
                html = await client.get_act(act_code)
        except Exception as exc:
            audit.log(tool="sg_get_full_text", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    root = html_tree.parse(html)
    main_containers = html_tree.find_all_by_exact_class(root, "prov1")
    full_text = "\n".join(html_tree.text_of(c).strip() for c in main_containers).strip()
    if not full_text:
        raise ToolError("not_found", f"No act found for act_code={act_code!r}.")
    truncated = len(full_text) > _MAX_FULL_TEXT_CHARS
    content = full_text[:_MAX_FULL_TEXT_CHARS] if truncated else full_text

    meta = build_act_summary(act_code, html)
    result = ActText(
        act_code=act_code,
        title=meta.get("title"),
        eli_uri=meta.get("eli_uri"),
        human_readable_citation=meta.get("human_readable_citation"),
        source_url=meta.get("source_url"),
        content=content,
        byte_size=len(content.encode("utf-8")),
        truncated=truncated,
    )
    audit.log(tool="sg_get_full_text", input_hash=input_hash, output_count_or_size=result.byte_size or 0,
              duration_ms=t.duration_ms, status="ok")
    return result


def main() -> None:
    """Run the MCP server over stdio (default for Claude Code)."""
    mcp.run()


if __name__ == "__main__":
    main()
