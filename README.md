# aeat

<!--
README OUT OF DATE — needs a dedicated overhaul pass.

The codebase has drifted significantly past what this README describes.
Notably absent / stale:
  * Cl@ve Móvil auth (now the sanctioned live path; README still says
    "no Cl@ve / DNIe yet").
  * aeat.adapters.inbound.sanitizer subpackage (PDF sanitiser pipeline that produces the
    fixture corpus, shipped as part of #239).
  * aeat.application.filing.reconciliation (FilingDraft ↔ Justificante comparator
    with MATCH / DIVERGENT / NOT_YET_FOUND triad, shipped in #239).
  * aeat.adapters.outbound.aeat.sede.walk_declarations_register (Consultar declaraciones
    presentadas walker; the canonical filings register, shipped #239).
  * aeat.application.filing.testing.synthesize_filing_draft (test-fixture FilingDraft
    factory used by reconcile dry-runs).
  * The expanded justificante fixture corpus (40 sanitised PDFs across
    M100 2021-2023, M130 2021-2024, M303 2021-2024, M111 2024,
    M190 2024, M390 2021-2023).

Do not treat this README as the source of truth for shipped features.
Until it is rewritten, consult `.vault/audit/`, the per-subpackage
docstrings under the layered `src/aeat/{domain,adapters,application,entrypoints,core}/`
tree, and `docs/coverage/` for what is actually implemented.

Tracking: needs a separate PR with dedicated attention before the
next operator-facing release.
-->

> **Status: pre-alpha.** Local gates are authoritative — `just lint &&
> just typecheck && just test && just hooks` is the source of truth.
> GitHub Actions is permanently disabled on this repository; there is
> no CI badge by design.

Spanish tax authority (AEAT) automation for autónomos: fetch live
filing status, build typed filing drafts, and export/verify filing
files from the CLI. The project does not submit filings to AEAT.

## What it does

- **Authenticates against AEAT** with a real PKCS#12 client certificate
  (FNMT-RCM and other accepted CAs) or Cl@ve Movil where configured.
- **Reads your filing status** directly from *Mis expedientes* and
  *Mis notificaciones* via a controlled headless browser session.
- **Builds typed filing drafts** for the supported modelos by joining
  validated registry definitions, the manual práctico, and the live
  normative corpus.
- **Exports and verifies filing files** for operator to upload manually in
  AEAT's official portal. There is no live-submit or dry-run-submit CLI
  path.
- **Self-heals local state** by reconciling AEAT's view with the
  on-disk store after every sync, so the next run always starts from
  ground truth.

## What it does not do

- It is **not a tax adviser** and **not a substitute** for AEAT's
  official tools or for professional tax advice.
- It will **never submit a filing to AEAT**. Live submission is not
  hidden behind a confirmation flag; the code path is absent.
- It does **not yet** support DNIe.
- It is **not multi-tenant** — one workstation, one autónomo, one
  certificate at a time.
- It does **not** automate around captchas or other anti-bot defences;
  it pauses and alerts the operator instead.

## Quick start

```sh
git clone https://github.com/wgergely/aeat
cd aeat
just bootstrap
aeat setup

# Build the local transaction catalogue from a bank export or NDJSON.
uv run aeat financial txs build path/to/statement.csv
# or: uv run aeat financial txs build path/to/statement.xlsx
# or: uv run aeat financial txs build path/to/statement.ofx
# or: uv run aeat financial txs build path/to/transactions.ndjson
# add --replace to overwrite an existing catalogue

# Inspect what is stored and discover categories.
uv run aeat financial txs list
uv run aeat categories list
uv run aeat categories show <category-slug>

# Classify one transaction and record the reason.
uv run aeat financial txs classify <transaction_id> --as BUSINESS --category <category-slug> --reason "..."

# Review the full classification history for that transaction.
uv run aeat review history <transaction_id>
```

Use `aeat categories list` to discover valid category slugs before classifying.
`aeat review history` prints the chain oldest-first with the current
classification appended at the end.

## Architecture

The on-main package has hard-cut over to the ADR layout. The package
root is only a package marker plus version/logging bootstrap; it does
not keep compatibility re-export modules such as `aeat.auth`,
`aeat.errors`, `aeat.formulas`, or `aeat.submission`.

Primary subpackages under `src/aeat/`:

| Subpackage             | Responsibility                                                            |
| :--------------------- | :------------------------------------------------------------------------ |
| `aeat.domain.modelos`  | Current AEAT modelo identifiers shared by registry-backed modules.        |
| `aeat.domain.portals`  | URL + form metadata for every AEAT portal the project touches.            |
| `aeat.adapters.outbound.aeat.auth` | AEAT certificate and Cl@ve Movil authentication providers.     |
| `aeat.adapters.outbound.aeat.browser` | Controlled headless Playwright session against AEAT.          |
| `aeat.domain.calculations.registry` | Validated registry snapshots backed by `registry/aeat`.       |
| `aeat.entrypoints.cli.registry` | Registry inspection through `aeat app registry`.                  |
| `aeat.domain.normatives` | Live normative corpus (BOE references, vigencia windows).               |
| `aeat.domain.manuals`  | Manual práctico ingestion and structured extraction.                      |
| `aeat.domain.deadlines` | Deadline engine — what's due, when, with what tolerance.                 |
| `aeat.application.filing` | Filing draft orchestration from validated registry snapshots.         |
| `aeat.domain.submission` | Read-only preflight contracts and local filing records.                 |
| `aeat.adapters.outbound.aeat.sede` | *Mis expedientes* and notification readers.                  |
| `aeat.domain.sync` | Divergence taxonomy, wire records, validation, and classification.        |
| `aeat.application.sync` | Self-healing sync orchestration and divergence persistence.              |
| `aeat.adapters.persistence.storage` | Local on-disk store for filings, receipts, and audit trail.   |
| `aeat.core.i18n`       | Quadlingual (es / en / ca / hu) message catalogue with nested-dict shape. |
| `aeat.adapters.outbound.llm` | Bounded LLM client for manual práctico extraction and explanations. |
| `aeat.application.filing.testing` | Shared fixtures and synthetic filing factories for tests.       |
| `aeat.entrypoints.cli` | Typer-based CLI surface (`aeat ...`).                                     |
| `aeat.application.workflow` | Orchestration engine that drives a filing through the pipeline.      |
| `aeat.application.setup` | Interactive first-run setup wizard.                                     |

A data-flow diagram with one paragraph per arrow lives in
[`docs/architecture.md`](docs/architecture.md). The contributor
walkthrough lives in [`docs/getting-started.md`](docs/getting-started.md).
The operator runbook for `aeat security` (master-key rotation,
corpus integrity verification, KDF migration) lives in
[`docs/security-runbook.md`](docs/security-runbook.md).

## Roadmap

Milestones:

- `0.0.1-scaffolding` — repo, tooling, base module structure, dev loop.
- `0.0.2-foundations` — auth, browser, schema, storage, i18n, models.
- `0.1.0-pre-alpha` — **current** — full AEAT loop demoable end-to-end.
- `0.2.0-alpha` — first external contributors, expanded modelo coverage.
- `0.3.0-beta` — packaging, distribution, documentation site.
- `1.0.0` — production-ready for a single autónomo.

## Contributing

- **Conventional commits are mandatory** on every commit on every
  branch. Format: `<type>(<scope>): <subject>`. Valid types: `feat`,
  `fix`, `perf`, `revert`, `docs`, `refactor`, `chore`, `test`,
  `build`, `ci`, `style`. The type drives the CHANGELOG section when
  `just release` runs — see [`RELEASING.md`](RELEASING.md).
- **One branch per issue.** Branch naming is `<type>/<issue>-<subject>`
  where type ∈ {`feature`, `bug`, `chore`}. Each branch lives in its
  own git worktree.
- **Vault-driven pipeline.** Significant work flows through the
  vaultspec pipeline: research → ADR → plan → execute → code review.
  Artefacts live under `.vault/`.
- **Local gates are authoritative.** GitHub Actions is permanently
  disabled on this repository. Before every commit and before every
  PR:

  ```sh
  just lint           # ruff
  just typecheck      # ty
  just test           # pytest, default skip-live
  just hooks          # prek run --all-files
  ```

`uv run aeat --help` (and `--help` on any sub-command) prints the
authoritative version.

## Live smoke tests

Live tests hit real external services and are gated behind
`AEAT_LIVE_TESTS_ENABLED=true` in `env/.env`. Tests with unmet
preconditions skip cleanly with a clear message — they never silently
pass.

```sh
# default: skip live tests
just test

# opt in
just test-live
```

## Development

```sh
just lint           # ruff
just fmt            # ruff format
just typecheck      # ty
just test           # pytest, default skip-live
just test-live      # pytest -m "unit or live_read"
just hooks          # prek run --all-files
```

The full just recipe list is `just --list`.

Live tests are opt-in via `AEAT_LIVE_TESTS_ENABLED=1` and hit real
AEAT endpoints; never enable them on shared infrastructure.

The full rules for the agent-driven workflow live in
[`CLAUDE.md`](CLAUDE.md).

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Disclaimer

Tax automation is legally significant. **This project is not a
substitute for professional tax advice and is not affiliated with the
Agencia Estatal de Administración Tributaria (AEAT).** Every
live AEAT submission is permanently forbidden in this codebase; operator
uploads any exported filing through AEAT's official tools himself. Use
at your own risk. The authors accept no liability for filings produced
or actions taken with this software. If in doubt, consult a qualified
tax professional and use AEAT's official tools.
