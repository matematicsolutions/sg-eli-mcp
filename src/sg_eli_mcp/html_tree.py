"""Minimal, tolerant HTML -> tree parser (stdlib only, no lxml/bs4 dependency).

Singapore's SSO serves real, deeply-nested, occasionally-malformed HTML (unlike the AKN/XML
or native-JSON sources elsewhere in this fleet), so there is no ready-made namespace to parse.
This module builds the same ``{"tag": ..., "attr": {...}, "children": [...]}`` shape used by
``jp_eli_mcp.citations`` out of ``html.parser.HTMLParser``, tolerating unclosed tags (a real
HTML5 parser this is not - it is deliberately permissive: an unmatched end tag is ignored
rather than raising, and unclosed start tags stay open until an ancestor closes).
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

_VOID_ELEMENTS = frozenset(
    {"br", "img", "hr", "input", "meta", "link", "area", "base", "col", "embed", "source"}
)


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root: dict[str, Any] = {"tag": "#root", "attr": {}, "children": []}
        self._stack: list[dict[str, Any]] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node: dict[str, Any] = {
            "tag": tag,
            "attr": {k: (v or "") for k, v in attrs},
            "children": [],
        }
        self._stack[-1]["children"].append(node)
        if tag not in _VOID_ELEMENTS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._stack[-1]["children"].append(
            {"tag": tag, "attr": {k: (v or "") for k, v in attrs}, "children": []}
        )

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i]["tag"] == tag:
                del self._stack[i:]
                return
        # unmatched close tag - ignore rather than raise (tolerant parsing)

    def handle_data(self, data: str) -> None:
        if data:
            self._stack[-1]["children"].append(data)


def parse(html_text: str) -> dict[str, Any]:
    """Parse an HTML document into a ``{"tag", "attr", "children"}`` tree rooted at ``#root``."""
    builder = _TreeBuilder()
    builder.feed(html_text)
    return builder.root


def find_by_id(node: Any, element_id: str) -> dict[str, Any] | None:
    """Depth-first search for the first element whose ``id`` attribute matches exactly."""
    if isinstance(node, dict):
        if (node.get("attr") or {}).get("id") == element_id:
            return node
        for child in node.get("children") or []:
            found = find_by_id(child, element_id)
            if found is not None:
                return found
    elif isinstance(node, list):
        for child in node:
            found = find_by_id(child, element_id)
            if found is not None:
                return found
    return None


def find_all_by_exact_class(
    node: Any, class_name: str, out: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Collect every element with an exact ``class`` token match (not a prefix - ``prov1``
    must not match ``prov1Hdr``)."""
    if out is None:
        out = []
    if isinstance(node, dict):
        classes = (node.get("attr") or {}).get("class", "").split()
        if class_name in classes:
            out.append(node)
        for child in node.get("children") or []:
            find_all_by_exact_class(child, class_name, out)
    elif isinstance(node, list):
        for child in node:
            find_all_by_exact_class(child, class_name, out)
    return out


def find_all_by_attr(
    node: Any, attr_name: str, attr_value: str, out: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Collect every element with an exact attribute value match."""
    if out is None:
        out = []
    if isinstance(node, dict):
        if (node.get("attr") or {}).get(attr_name) == attr_value:
            out.append(node)
        for child in node.get("children") or []:
            find_all_by_attr(child, attr_name, attr_value, out)
    elif isinstance(node, list):
        for child in node:
            find_all_by_attr(child, attr_name, attr_value, out)
    return out


def text_of(node: Any) -> str:
    """Flatten all text nodes under ``node`` into one whitespace-joined string."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(text_of(c) for c in node)
    if isinstance(node, dict):
        if node.get("tag") in {"script", "style"}:
            return ""
        return "".join(text_of(c) for c in node.get("children") or [])
    return ""
