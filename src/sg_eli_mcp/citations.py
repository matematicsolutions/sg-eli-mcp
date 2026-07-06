"""SSO (Singapore) parsing + citation helpers.

SSO renders each act as one large HTML page: numbered sections are wrapped in
``<div class="prov1">``, with the section number in a child element carrying
``id="pr{N}-"`` (e.g. ``id="pr1-"`` for section 1) and the section body in a sibling
``prov1Txt`` cell. There is no ELI, no AKN - this is real, occasionally messy HTML, parsed
with the tolerant tree builder in ``html_tree.py``.

Citation contract:
- ``eli_uri``: Singapore has no ELI. This is the durable SSO act URL
  (``https://sso.agc.gov.sg/Act/{act_code}``), keyed on SSO's own short act code - never
  invented. See ``models.ELI_NOTE``.
- ``human_readable_citation``: the act title as SSO itself renders it in the page title.
- ``source_url``: the same SSO act URL (SSO has no separate machine endpoint).
"""

from __future__ import annotations

from typing import Any

from . import html_tree

BASE_URL = "https://sso.agc.gov.sg"
_TITLE_SUFFIX = " - Singapore Statutes Online"


def act_url(act_code: str) -> str:
    return f"{BASE_URL}/Act/{act_code}"


def parse_browse_page(html_text: str) -> list[dict[str, Any]]:
    """Parse one ``/Browse/Act/Current/All`` page into ``[{act_code, title}, ...]``.

    Uses the ``add-to-collection`` links, which carry both the act code (in ``href``) and
    the title (in ``data-legistitle``) directly as attributes - no innerHTML text extraction
    needed, and no dependency on the disallowed ``/search`` endpoint.
    """
    root = html_tree.parse(html_text)
    links = html_tree.find_all_by_exact_class(root, "add-to-collection")
    seen: dict[str, str] = {}
    for link in links:
        attr = link.get("attr") or {}
        href = attr.get("href", "")
        if not href.startswith("/Act/"):
            continue
        act_code = href[len("/Act/") :]
        title = attr.get("data-legistitle") or attr.get("data-legisTitle")
        if act_code and act_code not in seen and title:
            seen[act_code] = title
    return [{"act_code": code, "title": title} for code, title in seen.items()]


def _page_title(root: dict[str, Any]) -> str | None:
    for node in _iter_tags(root, "title"):
        text = html_tree.text_of(node).strip()
        if text.endswith(_TITLE_SUFFIX):
            return text[: -len(_TITLE_SUFFIX)].strip()
        if text:
            return text
    return None


def _iter_tags(node: Any, tag: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if node.get("tag") == tag:
            out.append(node)
        for child in node.get("children") or []:
            out.extend(_iter_tags(child, tag))
    elif isinstance(node, list):
        for child in node:
            out.extend(_iter_tags(child, tag))
    return out


def build_act_summary(act_code: str, html_text: str) -> dict[str, Any]:
    """Build metadata + the citation contract from a fetched ``/Act/{act_code}`` page."""
    root = html_tree.parse(html_text)
    title = _page_title(root)
    return {
        "act_code": act_code,
        "title": title,
        "human_readable_citation": title,
        "eli_uri": act_url(act_code),
        "source_url": act_url(act_code),
    }


def extract_provision(html_text: str, provision_num: str) -> dict[str, Any] | None:
    """Find one numbered section (``id="pr{provision_num}-"``) inside its ``prov1`` container.

    Returns ``{"caption": ..., "text": ...}`` or ``None`` if no section has that number.
    """
    root = html_tree.parse(html_text)
    target_id = f"pr{provision_num}-"
    for container in html_tree.find_all_by_exact_class(root, "prov1"):
        header = html_tree.find_by_id(container, target_id)
        if header is not None:
            caption = html_tree.text_of(header).strip()
            body = html_tree.text_of(container).strip()
            return {"caption": caption or None, "text": body or None}
    return None
