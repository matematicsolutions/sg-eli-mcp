"""Pydantic v2 models for Singapore's SSO (Singapore Statutes Online) + sg-eli-mcp."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

DATASET_NOTE = (
    "Singapore Statutes Online (SSO, sso.agc.gov.sg) is the Attorney-General's Chambers' "
    "official portal for Singapore legislation. Singapore has no ELI scheme; eli_uri carries "
    "the durable SSO act URL (see eli_note). Discover with sg_list_acts (browse, paginated - "
    "SSO's robots.txt disallows /search, so this connector never queries it), then fetch a "
    "specific provision or the full text by act_code."
)

ELI_NOTE = (
    "Singapore has not deployed ELI. eli_uri is the durable SSO act URL "
    "(https://sso.agc.gov.sg/Act/{act_code}), keyed on SSO's own short act code - never invented."
)


class _Tolerant(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ActSummary(_Tolerant):
    """One act as listed by ``sg_list_acts``."""

    act_code: str | None = None
    title: str | None = None

    # Citation contract (Art. IV CONSTITUTION).
    eli_uri: str | None = None
    eli_note: str = ELI_NOTE
    human_readable_citation: str | None = None
    source_url: str | None = None


class ActListResult(_Tolerant):
    """Result of ``sg_list_acts``."""

    page_index: int
    page_size: int
    items: list[ActSummary] = Field(default_factory=list)
    dataset_note: str = DATASET_NOTE


class ProvisionText(_Tolerant):
    """Result of ``sg_get_provision`` - the text of one numbered section of an act."""

    act_code: str
    provision_num: str
    caption: str | None = None
    text: str | None = None

    eli_uri: str | None = None
    eli_note: str = ELI_NOTE
    human_readable_citation: str | None = None
    source_url: str | None = None
    dataset_note: str = DATASET_NOTE


class ActText(_Tolerant):
    """Result of ``sg_get_full_text`` - the full text of an act, possibly truncated."""

    act_code: str
    title: str | None = None
    eli_uri: str | None = None
    eli_note: str = ELI_NOTE
    human_readable_citation: str | None = None
    source_url: str | None = None
    content: str | None = None
    byte_size: int | None = None
    truncated: bool = False
    dataset_note: str = DATASET_NOTE
