"""Drift test - INSTRUCTIONS consistent with registered tools and error codes.

Cherry-picked from dograh-hq/dograh v1.31.0 (BSD-2) via mcp-eu-compliance v0.2.0.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sg_eli_mcp.server import INSTRUCTIONS, ToolError, mcp

SRC = (Path(__file__).parent.parent / "src" / "sg_eli_mcp" / "server.py").read_text(
    encoding="utf-8"
)


def _registered_tool_names() -> set[str]:
    if hasattr(mcp, "_tool_manager"):
        tools_dict = getattr(mcp._tool_manager, "_tools", {})
        if tools_dict:
            return set(tools_dict.keys())
    return set(re.findall(r"@mcp\.tool\([^)]*\)\s+async def (\w+)", SRC))


def _referenced_tool_names_in_instructions() -> set[str]:
    skip = {"isError", "true", "false", "json"}
    out: set[str] = set()
    for m in re.finditer(r"`([a-z][a-z0-9_]{3,})`", INSTRUCTIONS):
        token = m.group(1)
        if token in skip:
            continue
        if "_" in token:
            out.add(token)
    return out


def test_instructions_only_reference_registered_tools():
    registered = _registered_tool_names()
    referenced = _referenced_tool_names_in_instructions()
    referenced_tools = {r for r in referenced if r.startswith("sg_")}
    orphan = referenced_tools - registered
    assert not orphan, (
        f"INSTRUCTIONS reference tools not in mcp: {orphan}. Registered: {sorted(registered)}."
    )


def test_error_codes_documented_in_instructions():
    undocumented = set()
    for code in ToolError.VALID_CODES:
        if not re.search(r"\b" + re.escape(code) + r"\b", INSTRUCTIONS):
            undocumented.add(code)
    assert not undocumented, (
        f"ErrorCode in VALID_CODES not documented in INSTRUCTIONS: {undocumented}."
    )


def test_raised_error_codes_in_valid_codes():
    raised = set(re.findall(r'ToolError\(\s*"(\w+)"\s*,', SRC))
    invalid = raised - ToolError.VALID_CODES
    assert not invalid, (
        f"ToolError uses codes not in VALID_CODES: {invalid}. "
        f"VALID_CODES: {sorted(ToolError.VALID_CODES)}"
    )


def test_tool_error_format():
    err = ToolError("invalid_arg", "bad")
    assert str(err).startswith("[invalid_arg] ")


def test_tool_error_rejects_unknown_code():
    with pytest.raises(ValueError, match="Unknown ToolError code"):
        ToolError("nonexistent_code", "x")
