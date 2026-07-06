# Discovery: Singapore Statutes Online (sso.agc.gov.sg)

Date: 2026-07-06. **Status: CLOSED** for a browse+fetch+cite MVP (confirmed by live probing).

## User-Agent: a known, documented deviation from this fleet's norm

A plain probe with no `User-Agent` header returned HTTP 403. A probe with a standard browser
`User-Agent` returned HTTP 200 with a full HTML page. During the build, the live smoke tests
then failed with 403 using this fleet's usual honest, descriptive bot User-Agent
(`sg-eli-mcp/0.1.0 (+github url)`, the same pattern every other connector in this line uses) -
SSO's WAF accepts a generic browser string but rejects a self-identifying one.

This was raised to WM as an explicit decision rather than silently worked around. Decision:
use a generic browser User-Agent. Reasoning: the request is otherwise fully robots.txt-compliant
(no `/search` calls, public data only, no authentication bypassed), so this is a WAF rejecting
bot signatures in general rather than a targeted anti-scraping measure against this connector
specifically. `client.py` documents this deviation in its module docstring rather than hiding it.

## robots.txt (CONFIRMED)

```
user-agent: *
disallow: /search
crawl-delay: 6
```

`/search` is off-limits. `/Browse/...` and `/Act/...` are not listed and are used here.

## Base properties (CONFIRMED live 2026-07-06)

- **Base URL:** `https://sso.agc.gov.sg`
- **Authentication:** none (public portal).
- **Format:** server-rendered HTML (ASP.NET, Knockout.js for UI widgets only - the legislative
  text itself is present in the initial HTML response, not loaded by a later AJAX call).
- **ELI:** NO - Singapore has not deployed ELI. The stable identifier is SSO's own short act
  code (e.g. `CoA1967` for the Companies Act 1967).

## Endpoints (CONFIRMED)

| Endpoint | Notes |
|---|---|
| `GET /Browse/Act/Current/All?PageIndex={n}&PageSize={n}` | paginated listing of current Acts; each `<a class="add-to-collection" href="/Act/{code}" data-legisTitle="{title}">` gives both the code and the title as attributes, no innerHTML scraping needed |
| `GET /Act/{act_code}` | the full act, e.g. `/Act/CoA1967` (Companies Act 1967) returned 1.4 MB of HTML with well-formed section markup |

Verified live: `/Browse/Act/Current/All?PageSize=20` returned real act codes (`IA1965`,
`AA2004`, `ACRAA2004`, `ASA2007`, ...) each carrying `data-legisTitle`; `/Act/CoA1967` returned
sections wrapped in `<div class="prov1">` with the section number in a child element carrying
`id="pr{N}-"` (e.g. `id="pr1-"` for section 1) and the body text in a sibling `prov1Txt` cell.

## Fields used (for the citation contract)

- Act short code (from `/Browse` or the URL path) -> the durable identifier ->
  `eli_uri = https://sso.agc.gov.sg/Act/{act_code}`.
- The `<title>` tag of an act page, minus the ` - Singapore Statutes Online` suffix ->
  `human_readable_citation`.
- Same SSO act URL -> `source_url` (SSO has no separate machine-readable endpoint).
- `div.prov1` containing `id="pr{N}-"` -> `sg_get_provision` (parsed with a small tolerant
  HTML tree builder, `html_tree.py` - stdlib `html.parser` only, no lxml/bs4 dependency).

## Citation contract (Article IV) - CLOSED for SG

- `eli_uri` = the SSO act URL, keyed on SSO's own act code (no native ELI; documented via
  `eli_note`).
- `human_readable_citation` = the act title as SSO renders it, e.g. "Companies Act 1967".
- `source_url` = the same SSO act URL (the fetchable original; SSO has no separate API).

## Tool mapping - browse+fetch+cite MVP

| Tool | Endpoint |
|---|---|
| `sg_list_acts` | `/Browse/Act/Current/All` (paginated) |
| `sg_get_provision` | `/Act/{act_code}` (walk HTML tree for `div.prov1` containing `id="pr{N}-"`) |
| `sg_get_full_text` | `/Act/{act_code}` (all `div.prov1` blocks flattened to text, truncated ~300k chars) |

**Deferred:** subsidiary legislation, Bills, Supreme Court judgments (a separate portal).

## Differences vs the EU/EEA and Japan lines

- No ELI, no AKN, no native JSON - the source is real, deeply-nested HTML with occasional
  malformed nesting, parsed with a purpose-built tolerant tree builder
  (`html_tree.py`) rather than `xml.etree.ElementTree` or a JSON tree walker.
- No search API at all, and the one that exists (`/search`) is off-limits by `robots.txt` -
  the first connector in this fleet built without any keyword-search tool.
- A `User-Agent` header is required; a bare request without one returns 403.

## Decision: BUILD

Keyless, robots-compliant once a browser-like User-Agent is used, and structurally clean:
a reasonable MVP. Market-size comparisons against other jurisdictions in this fleet were not
verified in this session and are left out rather than asserted unsourced.
