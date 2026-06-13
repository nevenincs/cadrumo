---
tags:
  - '#audit'
  - '#aeat-cli-hardening'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-aeat-cli-hardening-plan]]"
  - "[[2026-05-08-aeat-cli-gap-discovery-audit]]"
---



# `aeat-cli-hardening` audit: `W1 live CLI inventory`

## Registered Root

Live command help exposes only two root command groups:

| Command | Help summary |
|---|---|
| `aeat setup` | Local profile and authentication preparation. |
| `aeat app` | Fiscal workspace for ledgers, invoices, declarations, and registry. |

The root has a single global `--format` option. It has no `--version`, `-V`,
`version`, `doctor`, `init`, `config`, `topic`, or `help <topic>` surface.

## Registered Tree

| Command group | Registered children |
|---|---|
| `aeat setup` | `init`, `status`, `auth`, `profile` |
| `aeat setup auth` | `providers`, `configure`, `login`, `status`, `reset`, `whoami`, `logout` |
| `aeat setup profile` | `use`, `show`, `list-keys`, `get`, `set`, `unset`, `validate`, `list` |
| `aeat app` | `overview`, `ledger`, `invoice`, `declaration`, `registry` |
| `aeat app overview` | `status` |
| `aeat app ledger` | `import`, `review`, `edit` |
| `aeat app invoice` | `import`, `review`, `edit`, `match` |
| `aeat app declaration` | `calculate`, `review`, `status`, `edit`, `approve`, `validate`, `preview`, `export`, `verify` |
| `aeat app registry` | `inspect`, `verify`, `audit-oracles`, `list-filed-data`, `capture-filed-data`, `capture-source-filed-data`, `verify-filed-state`, `workbooks`, `parity` |
| `aeat app registry workbooks` | `verify` |
| `aeat app registry parity` | `run`, `replay` |

## On-Disk CLI Modules Not Registered At Root

The root app imports only setup, overview, ledger, invoice, declaration, and
registry modules. The following Typer app modules exist on disk but are not
reachable from live root help:

| Module family | Initial classification |
|---|---|
| `attachments` | Hidden user-data/evidence surface; needs root placement decision. |
| `categories` | Hidden tax-category catalogue surface; needs data/config placement decision. |
| `normatives` | Hidden reference/advanced surface. |
| `browser` | Hidden diagnostics/live-adjacent surface. |
| `data ledgers inventory` | Hidden data/ledger inventory surface. |
| `deadlines` | Hidden obligations/calendar surface overlapping overview calendar. |
| `filing` | Hidden filing/draft surface overlapping app declaration. |
| `financial` | Hidden legacy/parallel financial surface overlapping app ledger/invoice/profile. |
| `llm` | Hidden advanced/provider surface. |
| `sanitize` | Hidden sanitizer/import safety surface. |

These remain covered by `DISCOVERED-001` until each is classified as public
target, advanced target, backend-only, or removal.

## New Findings

`DISCOVERED-004`: `aeat app registry audit-oracles` is registered but was not
listed in the pasted audit. It is an English, technical diagnostic under the
user-facing registry namespace.

`DISCOVERED-005`: the shared structured CLI error boundary exists but is not
applied to the root app. Root commands still rely on Typer/Click or local
`BadParameter` behavior unless a sub-app decorates itself.

`DISCOVERED-006`: `aeat setup status` computes profile readiness, auth
readiness, and next action inside the CLI handler. That violates the
transport-only invariant and blocks safe expansion of UX-006 and UX-009.

`DISCOVERED-007`: `_aggregate_filing_inputs` in CLI common helpers is a
placeholder returning an empty dictionary. That keeps declaration calculation
dependent on missing bindings and must move to backend aggregation/preflight.

## Test Coverage Inventory

Existing CLI tests use real `CliRunner` invocation for the live root surface and
some hidden sub-apps. Several tests isolate persistence through temporary secure
storage. That is useful behavior coverage, but the inventory found risks:

- root command tests currently assert the narrow `setup`/`app` tree and will
  need replacement as config/doctor/topic/modelo surfaces land;
- some CLI tests use monkeypatch for environment isolation, which is acceptable
  only where it selects real backend storage and not where it fakes behavior;
- hidden module tests prove sub-app behavior but do not prove root reachability;
- no current test asserts that root error-boundary decoration is active;
- no current test proves CLI status delegates readiness/next-action decisions to
  backend services.

## Verification Commands

- `uv run --no-sync aeat --help`
- `uv run --no-sync aeat setup --help`
- `uv run --no-sync aeat setup auth --help`
- `uv run --no-sync aeat setup profile --help`
- `uv run --no-sync aeat app --help`
- `uv run --no-sync aeat app overview --help`
- `uv run --no-sync aeat app ledger --help`
- `uv run --no-sync aeat app invoice --help`
- `uv run --no-sync aeat app declaration --help`
- `uv run --no-sync aeat app registry --help`
- Python Typer introspection over the root app command tree.
