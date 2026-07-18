# sg-eli-mcp

<!-- mcp-name: io.github.matematicsolutions/sg-eli-mcp -->

An MCP server for **Singapore Statutes Online** (SSO, `sso.agc.gov.sg`), the Attorney-General's
Chambers' official portal for Singapore legislation. It browses, fetches, and cites Acts, with
a verifiable citation on every response.

Part of the MateMatic `eu-legal-mcp` production line, extended into Asia alongside `jp-eli-mcp`.
Same citation contract (a stable identifier + a human-readable citation + a source URL),
adapted for a jurisdiction with no ELI and no public search API.

> **Scope.** SSO's `robots.txt` disallows `/search`; discovery here is by browsing the current
> Acts listing (`sg_list_acts`, paginated), not by title or keyword query. Fetch a specific
> section (`sg_get_provision`) or the full text (`sg_get_full_text`, truncated for very large
> Acts). Every response carries a `dataset_note`.
>
> **Licence.** SSO legislation is official public information published by the Singapore
> government. This connector relays it with attribution and a `source_url`, respects
> `robots.txt` (no `/search` calls), and does not cache more aggressively than a normal browser
> visit would.

## The tools

| Tool | What it does |
|---|---|
| `sg_list_acts` | Browse the current Acts, paginated (no keyword search - see Scope above). |
| `sg_get_provision` | The text of one numbered section of an Act, by `act_code` and section number. |
| `sg_get_full_text` | The full text of an Act (truncated at ~300,000 characters). |

Every response carries the contract: `eli_uri` (Singapore has no ELI - this is the durable SSO
act URL, e.g. `https://sso.agc.gov.sg/Act/CoA1967`, see `eli_note`), `human_readable_citation`
(the Act title as SSO itself renders it, e.g. `Companies Act 1967`), and `source_url`.

## Install

Not yet on PyPI - install from source until the first release ships:

```bash
git clone https://github.com/matematicsolutions/sg-eli-mcp
cd sg-eli-mcp
pip install -e .
```

Once released, this will be `uvx sg-eli-mcp`.

Configuration via env:

- `SG_ELI_BASE_URL` - default `https://sso.agc.gov.sg`
- `SG_ELI_CACHE_DIR` - default `~/.matematic/cache/sg-eli`
- `SG_ELI_AUDIT_DIR` - default `~/.matematic/audit`

No API key. SSO is keyless.

### Configure (Claude Code / any MCP client)

```json
{
  "mcpServers": {
    "sg-eli-mcp": { "command": "sg-eli-mcp" }
  }
}
```

### Windows 11 ze Smart App Control

Smart App Control blokuje niepodpisane pliki wykonywalne, a `uvx.exe`, `pip.exe`
i generowany przy instalacji `sg-eli-mcp.exe` podpisane nie sa. `python.exe`
z python.org jest podpisany przez Python Software Foundation, wiec uruchomienie
przez modul omija blokade:

```bash
python -m pip install sg-eli-mcp
python -m sg_eli_mcp
```

```json
{ "mcpServers": { "sg-eli-mcp": { "command": "python", "args": ["-m", "sg_eli_mcp"] } } }
```

Nie wylaczaj Smart App Control, zeby to obejsc - wylaczenia nie da sie cofnac
bez ponownej instalacji systemu.

## Governance

- **Public data only** - read-only against SSO; no client data leaves the machine.
- **Robots-compliant** - never calls `/search` (disallowed by SSO's `robots.txt`); discovery
  uses only the allowed `/Browse` listing.
- **Audit log** - every tool call appends one JSON line to `~/.matematic/audit/sg-eli-mcp.jsonl`.
- **Vendor-neutral** - talks only to `sso.agc.gov.sg`; no LLM provider, no telemetry.
- **Verifiable citations** - every response is independently checkable via `source_url`.

See `CONSTITUTION.md` and `DISCOVERY.md`.

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_instructions_drift.py -v   # offline
pytest tests/test_smoke.py -v                # hits live SSO
```

## Licence

Apache-2.0. © Matematic Solutions / Wieslaw Mazur.
