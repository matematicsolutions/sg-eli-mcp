# Constitution of sg-eli-mcp

Version: 0.1.0
Date: 2026-07-06
Licence: Apache-2.0

`sg-eli-mcp` is an MCP server for Singapore Statutes Online (SSO, `sso.agc.gov.sg`). It
browses, fetches, and cites Singapore Acts as parsed HTML. Subsidiary legislation and case
law are out of scope for this MVP.

The 4 principles below are inherited from the `eu-legal-mcp` line Constitution (Article IV),
adapted for a jurisdiction without ELI and without a public search API.

---

## Art. 1. Public data only

SSO is the official, public source of Singapore legislation, published by the
Attorney-General's Chambers. The server is read-only against SSO and sends nothing beyond the
requested act code, page index, or section number. It never calls `/search`, which SSO's
`robots.txt` disallows.

## Art. 2. Mandatory audit log

Every tool call MUST append one JSON line to `~/.matematic/audit/sg-eli-mcp.jsonl`
(ts / tool / input_hash SHA-256 / output_count_or_size / duration_ms / status). Inability to
write = the tool returns an error, it does not silently skip.

## Art. 3. Vendor neutrality

No tool hardcodes an LLM provider, assumes a model, or adds commercial telemetry. The server
talks only to `sso.agc.gov.sg` and the local filesystem. Authentication: none; own backoff +
cache.

## Art. 4. A durable identifier and a human-readable citation are mandatory

Every response MUST carry three fields:
- `eli_uri`: Singapore has no ELI. This is the durable SSO act URL
  (`https://sso.agc.gov.sg/Act/{act_code}`), keyed on SSO's own short act code - never
  invented. `eli_note` on every response says so explicitly.
- `human_readable_citation`: the Act title as SSO itself renders it (e.g. "Companies Act 1967").
- `source_url`: the same SSO act URL (SSO has no separate machine-readable endpoint).

---

## Open points

1. **No keyword search** - `robots.txt` disallows `/search`. Discovery is limited to browsing
   the paginated current-Acts listing; a future revision could add a title-substring filter
   over that listing without ever calling the disallowed endpoint.
2. **Subsidiary legislation, Bills, and case law** - not covered. SSO also serves subsidiary
   legislation and the Supreme Court publishes judgments separately; both are out of scope.
3. **Provision numbering edge cases** - sections with lettered sub-parts (e.g. 7A) are
   addressed via SSO's own `id="pr{N}-"` fragment identifiers; not all edge cases have been
   probed against the live site.

## Ewolucja konstytucji

Changes to art. 1-4 follow SEMVER + an entry in `CHANGELOG.md` + a `pyproject.toml` bump.

First version: 2026-07-06. Author: Wieslaw Mazur / MateMatic.
