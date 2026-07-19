# Changelog

All notable changes to this project are documented here. This file is
maintained by [release-please](https://github.com/googleapis/release-please)
driven locally via `just release` — see [`RELEASING.md`](RELEASING.md) and
[`.vault/adr/2026-04-12-release-please-adr.md`](.vault/adr/2026-04-12-release-please-adr.md).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-07-19

First public release cohort of **Cadrumo** — the product's first distribution
under its product name (renamed from the internal `aeat` working name) — built
once into one immutable, hash-bound cross-platform cohort and promoted without
rebuild to every channel, so PyPI, the GitHub release, Scoop, Homebrew, and
Claude all serve identical bytes. No `v0.2.0` distribution was ever published;
the `v0.2.0` tag predates the work below.

### Added

- **Distribution channels:** Cadrumo installs from PyPI
  (`cadrumo`, `cadrumo-data-manuals`, `cadrumo-data-official` via Trusted
  Publishing), the GitHub release, a Scoop bucket, a Homebrew tap, the Claude
  plugin marketplace, and a Claude Desktop MCPB bundle. Every artefact is
  digest-verified against the one tested cohort; each channel's installed
  behaviour is proven by a grounded tax-work oracle before release.
- **Warm MCP serving:** local read and mutate MCP tools run in-process against
  a warm runtime — steady-state latency is roughly 0.09 s for reads, 0.28 s for
  simple writes, and 1.7 s for the heaviest Modelo 200 calculation — replacing
  the previous per-call subprocess spawn.
- **Bilingual client-display copy:** the Claude plugin, marketplace, and MCPB
  product descriptions carry English and Spanish summaries.

### Changed

- **Product identity:** the agent harness (personas, skills, operator rules) is
  namespaced under the `cadrumo-` prefix, and the MCP server, tools, and
  resource URIs use the `cadrumo` / `cadrumo://` identity. The Python package
  imports as `cadrumo`, the human CLI executable is `aeat`, and the MCP server
  executable is `cadrumo-mcp`.
- **Config safety:** state-destroying config operations (`config reset`,
  `config repair`) now require explicit human confirmation on the MCP surface.
- **User documentation:** the installation surfaces address end users
  installing a released package; developer-checkout setup moved to
  `CONTRIBUTING.md`. The documented MCP command is `cadrumo-mcp`.

### Fixed

- **MCP robustness:** the MCP server now starts and answers the protocol on a
  machine carrying retired prior-product state instead of crashing before its
  first response; the `execute` meta-tool no longer blocks the event loop
  (removing multi-second and Cowork-client hangs); a wedged warm call degrades
  to the supervised subprocess transport with a visible warning.
- **Packaging:** `click` is now a declared direct dependency; `typer>=0.26`
  stopped pulling it in, so a clean wheel install crashed on import
  (`ModuleNotFoundError: click`). Caught by the split-install packaging
  smoke; `uv.lock` reconciled to the committed `pyproject.toml`.
- **Publish lane:** one GitHub environment per distribution
  (`pypi`, `pypi-data-manuals`, `pypi-data-official`) so all three pending
  Trusted Publishers can register from the one publish workflow.
- **`just doctor`** invoked a nonexistent `cadrumo` console script; the
  human CLI is `aeat`.

## [0.2.0] - 2026-07-04

Prepared per issue #382. No `v0.1.0` git tag exists on the remote, so this
section is a hand-curated summary of the work landed on `main` since the
0.1.0 baseline (2026-04-12) rather than a `release-please`-generated
per-commit log; `just release` should still be run by the operator at cut
time to let release-please walk the full commit history and reconcile this
summary against its own changelog delta. The interval spans thousands of
commits — dominated by a large registry/calculation-grounding hardening
campaign and a hexagonal-architecture restructure (#476) — so entries below
are grouped by domain rather than enumerated per commit. No breaking changes
to released data: the project remains pre-beta with zero released versions,
so there is no upgrade path to document (see `no-legacy-compatibility`).

### Highlights

- **Modelo calculation coverage:** extended registry-grounded calc-verify
  roundtrips across Modelos 100 (RENTA, full-form), 111, 115, 123, 130, 131,
  180, 190, 200, 303, 347, 349, 390, 720, and others, each grounded in BOE /
  AEAT workbooks and cross-checked against the legal-citation registry.
- **CLI surface:** typed `--json` output contract with a shared envelope
  spine, `ErrorCode` registry, exit-code table, and a uniform `Notice`
  diagnostics channel replacing ad hoc advisory fields.
- **Agent harness:** an operator-facing agent-skills and agent-harness
  surface (`aeat.agent`) with per-modelo applicability skills, conformance
  gates tying harness documents to the live CLI surface.
- **Ledger hardening:** absolute-magnitude transaction amounts with
  direction as the sole flow authority, idempotent-guarded single-subject
  mutations, evidence-bundled ledger-derived calculation revisions, and a
  rebuildable transaction-to-revision participation index.
- **Secure persistence:** encrypted secure-object storage foundation for
  sensitive financial data (invoices, bank statements, evidence bytes),
  content-addressed attachment storage, and profile-bucket scoping.
- **Registry authority:** consolidated the modelo registry into a single
  deterministic TOML-authoring → loader/compiler → validated-authority →
  snapshot pipeline, with binding/resolver taxonomy hardening (source kinds,
  aggregation ops, provenance parity with casilla observations).
- **Architecture restructure (#476):** relocated the codebase onto a
  hexagonal layout (`core` / `domain` / `application` / `adapters` /
  `entrypoints`), removed compatibility shims and dead code, and enforced
  import-linter boundary contracts.
- **Documentation:** generated CLI reference and API-doc scaffolding tied to
  the live Typer tree, a Terminology Handbook glossary, and locale-catalogue
  CLI tooling for `en`/`es`/`ca`/`hu`.

### Notes

- Live AEAT submission remains permanently forbidden; this release only
  extends build / validate / verify / export capability outside the
  application (see `aeat-safety-legal-gates`).
- Version bump applied at cut time: `pyproject.toml [project].version`,
  `src/aeat/__init__.py __version__`, and `.release-please-manifest.json`
  now read `0.2.0` (per the `2026-04-12-release-please-adr` human-gated cut).

## [0.1.1] - 2026-07-04

### Fixed

- `corpus-sources` extra now resolves: the published 0.1.0 metadata pinned the
  never-published single `aeat-data` companion; 0.1.1 pins the two sub-cap
  companions (`aeat-data-manuals`, `aeat-data-official`) that actually ship.

Run `just release` to preview the next release. Run `just release-apply`
to land the version bump and CHANGELOG entries on `main` (human-gated,
no push).

## [0.1.0] - 2026-04-12

Initial scaffolding release. Backfilled from conventional-commit history
on `main` through 2026-04-12. Merge commits and non-conventional messages
are omitted.

### Features

- **auth:** PKCS#12 client certificate authentication for AEAT (#8, #58)
- **testing:** synthetic filing-history fixtures + loader (#14, #56)
- **inbox:** AEAT notifications inbox (#46, #55)
- **normatives:** typed BOE-linked Spanish tax normatives catalogue (#45, #53)
- **status:** AEAT live status reader (#43)
- **google-fixtures:** Google Workspace test fixture surface (#13, #29)
- **submission:** dry-run-default filing submission engine (#42, #49)
- **filing:** typed `FilingDraft` + `Modelo130Builder` PoC + CLI (#39)
- **deadlines:** filing-deadline computation engine (#38, #47)
- **manuals:** Manual práctico schema, loader, CLI skeleton, raw-PDF manifests (#25, #35)
- **sync:** self-healing live-to-local sync runner (#11, #37)
- **storage:** scaffold SQLite + SQLAlchemy + Alembic storage layer (#10, #28)
- **browser:** Playwright anti-bot evasion (#16, #26)

### Bug Fixes

- **status:** apply code-review and round-2 findings (#43)
- address review feedback: NFC normalization, type safety, fallback config

### Documentation

- **audit:** PR #28 storage retrospective + reviewer hardening (#32, #40)

### Miscellaneous Chores

- **ci:** add GitHub Actions workflow for Ubuntu/Windows parity (#31, #34) — later superseded when GitHub Actions was permanently disabled on the repo
- **dev-scaffolding:** full `gsuite-bootstrap` pipeline + CLI + doctor (#4, #18)
- base module structure scaffolding (#19)
