"""Smoke tests - require internet, hit the live SSO site.

Run manually:

    pytest tests/test_smoke.py -v
"""

from __future__ import annotations

import pytest

from sg_eli_mcp.server import sg_get_full_text, sg_get_provision, sg_list_acts

# Companies Act 1967.
ACT_CODE = "CoA1967"


@pytest.mark.asyncio
async def test_smoke_list_acts() -> None:
    result = await sg_list_acts(page_index=1, page_size=20)
    assert len(result.items) > 0, "expected at least one act on page 1"
    for item in result.items:
        assert item.act_code is not None
        assert item.eli_uri is not None and "sso.agc.gov.sg/Act" in item.eli_uri
        assert item.human_readable_citation is not None


@pytest.mark.asyncio
async def test_smoke_get_provision() -> None:
    provision = await sg_get_provision(ACT_CODE, "1")
    assert provision.text is not None and len(provision.text) > 0
    assert provision.eli_uri == f"https://sso.agc.gov.sg/Act/{ACT_CODE}"
    assert provision.human_readable_citation is not None and "Companies Act" in (
        provision.human_readable_citation
    )


@pytest.mark.asyncio
async def test_smoke_get_full_text() -> None:
    text = await sg_get_full_text(ACT_CODE)
    assert text.content is not None and len(text.content) > 0
    assert text.eli_uri is not None
    assert text.byte_size and text.byte_size > 0
