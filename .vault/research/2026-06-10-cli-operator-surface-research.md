---
tags:
  - '#research'
  - '#cli-operator-surface'
date: '2026-06-10'
related:
  - '[[2026-06-10-cli-operator-surface-audit]]'
  - '[[2026-06-10-cli-operator-crud-matrix-audit]]'
  - '[[2026-06-10-aeat-cli-userdocs-hardening-audit]]'
  - '[[2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr]]'
  - '[[2026-05-14-ledger-transaction-lifecycle-adr]]'
  - '[[2026-06-02-ledger-operator-hardening-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-01-registry-period-code-union-cli-boundary-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-profile-output-language-adr]]'
  - '[[2026-06-03-modelo-036-census-sync-adr]]'
---

# `cli-operator-surface` research: `operator surface weaknesses and prior-decision reconciliation`

The `aeat-cli-userdocs-hardening` campaign wrote operator how-to guides against
the live CLI and surfaced operator-surface design weaknesses documentation could
only describe, never repair. This research synthesises the two operator-surface
audits (`2026-06-10-cli-operator-surface-audit`, findings F1-F8;
`2026-06-10-cli-operator-crud-matrix-audit`, CRUD matrix and journeys) into the
decision-shaped evidence base that the operator-surface ADR consumes, and binds
each weakness to the prior decision that created it. Every current-behaviour
claim below was re-verified against `HEAD` during this pass.

## Findings

### F1 -- profile switch verb leaks the storage layer (HIGH)

`aeat config profile switch` and `use` are retired (`_RETIRED_VERBS` in
`src/aeat/entrypoints/cli/tests/test_config_profile_surface_inventory.py`); the
surviving switch door is `aeat config unlock NAME` (`config/_custody.py`), which
names session unsealing, not the operator's intent. Prior decision:
`2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr` reasoned
about `use` versus `set active` and never anticipated unlock vocabulary becoming
the only door. Reconciliation: restore an intent-named verb over session-unlock
semantics.

### F2 -- ledger lifecycle is a one-way trapdoor (HIGH)

`_transition_manual_transaction_lifecycle` (`ledger/_actions_lifecycle.py`) is
state-generic but no public action or CLI verb targets `ACTIVE`; only
`archive` / `stash` / `remove` exist. Prior decision:
`2026-05-14-ledger-transaction-lifecycle-adr` Decision 4 classed `archive` /
`stash` as "Tier 1 -- reversible state transitions" and Decision 2 named the
inverse `activate`; the inverse was never built. The CRUD audit (F-01, journey
e) rates this the single highest-leverage gap: an accidental bulk stash recovers
only through `ledger reset`. Reconciliation: honour the reversibility promise
with a `restore`-to-`ACTIVE` verb carrying the operator-hardening
`--yes` / `--reason` / audit guarantees.

### F3 -- `update` breaks row identity (MEDIUM)

The `transaction_id` derivation in `domain/transactions/_models.py` keys on
provider id and verbatim narrative and changes on edit, killing a written-down
`history <old-id>` handle. Prior decision:
`2026-06-04-modelo-addressing-ux-adr` already ruled internal content-addressed
IDs authoritative-but-not-operator-facing for modelo work; it never reached the
ledger surface. Reconciliation: extend that principle to ledger rows via
edit-lineage resolution.

### F4 -- two period grammars (MEDIUM)

Modelo surfaces accept `0A / 1T-4T / 01-12`; ledger surfaces accept
`2026Q1 / 2026-03 / 2026` (`_PERIOD_RE` / `_canonical_period` in
`entrypoints/cli/_common.py`), with no conversion. Prior decision:
`2026-06-01-registry-period-code-union-cli-boundary-adr` is the incumbent
authority for the AEAT shape but scoped itself to modelo periods; the ledger
calendar grammar has no governing ADR. Reconciliation: AEAT tokens canonical,
ledger calendar shapes accepted-and-converted, supplying the missing governing
decision.

### F5 -- help-text drift is systemic (HIGH)

Five distinct hand-maintained strings disagreed with the CLI in one campaign (a
hint to a non-existent `verification-report list`; an "unambiguous prefix"
evidence-id help while the lookup matches by exact equality in
`ledger/_evidence.py`; a `doclink --source` option typed as the full
`AttachmentSource` enum while the handler accepts three; a `work verify --select
latest-verified` advertised though verify refuses any state but `BORRADOR`; a
"profile registry" string for a calculation-registry probe). No ADR governs the
self-referential strings. Reconciliation: a conformance gate mirroring
`test_documented_command_conformance.py`.

### F6 -- localization half-wired (MEDIUM)

The root `--language` flag is `is_eager=True` in
`entrypoints/cli/__init__.py` and resolves after import-time `tr(...)` rendering,
so it does not localize help text; only `AEAT_OUTPUT_LANGUAGE` (read before
import) does. Prior decision:
`2026-05-13-cli-workflow-redesign-profile-output-language-adr` set the
output-language precedence but never decided the eager-flag help-rendering timing
contract. Reconciliation: make the flag work, warn, or be removed from surfaces
it cannot affect.

### F7 -- write-only records (MEDIUM)

`aeat app modelo m036` registers exactly `alta / modificacion / baja`
(`entrypoints/cli/_modelo_m036_cli.py`); the application layer exposes only
`record_m036_declaration` (`application/modelo/_m036_lifecycle.py`) with no
list / view -- the `list_declarations` verb the census-sync landing plan named
never shipped. The CRUD matrix names the same write-only shape on reconciliation
results, the IVA wallet seed, and the local filing record. Prior decision:
`2026-06-03-modelo-036-census-sync-adr` specified the write path without a
read-back guarantee. Reconciliation: read-back as a baseline guarantee.

### F8 -- internals leak into a readiness question (LOW)

`aeat config profile preflight` declares `revision_id: str = typer.Option(...)`
(no default) in `entrypoints/cli/_config/__init__.py`, forcing the operator to
fetch an internal revision id to answer "am I ready to file?". Shares F3's root
principle from `2026-06-04-modelo-addressing-ux-adr`, never extended to the
readiness surface. Reconciliation: default to the active revision; keep
`--revision-id` as an explicit override.

### New gap -- gestor cross-profile bulk (CRUD F-04, MEDIUM)

Every mutating verb is single-active-profile; the only cross-profile surface is
`overview calendar --all-profiles`. No prior ADR; not in the cited backlog.
Recommendation: defer to a dedicated gestor-mode feature ADR rather than fold a
product-scope question into the verb-and-lifecycle decision set.

## Synthesis

Five weaknesses (F2, F3, F6, F7, F8) are a prior accepted principle not carried
to a surface it should have reached; two (F1, F4) are a verb or grammar that
drifted from or never received a governing decision; one (F5) is a missing
enforcement gate for which a template already exists. The reconciliation shape is
therefore amend-or-extend for the five-plus-two and net-new-gate for F5, with the
gestor bulk gap deferred. This evidence base feeds the operator-surface ADR.
