---
tags:
  - "#adr"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
title: Self-Healing Live-to-Local Sync Runner
related:
  - "[[2026-04-12-self-healing-sync-research]]"
  - "[[2026-04-12-playwright-anti-bot-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
---

# architecture decision record: self-healing sync

## context

Issue wgergely/aeat#11 introduces the live-to-local
cross-validation runner. It must FETCH state from AEAT via a
Playwright session, VALIDATE incoming payloads through strict
pydantic schemas, DIFF the validated shape against the local
corpus/schema/catalogues, CLASSIFY any divergence, and then
either HEAL (bounded) or ESCALATE to a human. It must stay
read-only against AEAT.

Multiple dependent subpackages are in-flight on sibling branches
(#6, #7, #8, #9, #10, #17, #21, #25). Hard imports from any of
them would break this branch. The base module structure is
already locked by #12.

## decision

1. **Single subpackage: `src/aeat/application/sync/`.** All public exports
   go through `aeat.application.sync.__init__`. Internal modules are
   `_`-prefixed. Callers never import from internal modules.

2. **Pydantic v2 strict everywhere.** Every boundary-crossing
   type — wire payloads, divergence records, classification
   results, healing plans, run results — is a strict frozen
   pydantic v2 model. Closed enumerations are `enum.StrEnum`.
   `DivergencePayload` is a `Field(discriminator="kind")`
   discriminated union. No bare `dict[str, Any]` anywhere public
   or persisted.

3. **Cross-module dependencies are Protocol contracts, not
   imports.** For every in-flight subpackage the runner declares
   a local `Protocol` (or pydantic stub type) describing the
   slice of surface we consume. On rebase after the dependency
   merges, the Protocol is swapped for the real import in a
   single focused commit. Protocols live under
   `src/aeat/application/sync/_protocols.py`:

   - `CertificateBackend` (stub for #8 `LoadedCertificate` +
     `preload_into_browser_context`)
   - `CorpusLoader` (stub for #17)
   - `SchemaLoader` + `ModeloSchema` (stub for #9)
   - `ManualRulesLoader` + `Rule` (stub for #25)
   - `LLMClient` + `LLMRequest` (stub for #21)
   - `DivergenceRecordRepository` (stub for #10)
   - `ModeloIdentifier` + `PortalIdentifier` — typed string IDs
     with validators, matching the planned #6/#7 enum surfaces.

   `aeat.adapters.outbound.aeat.browser.BrowserSession` and `aeat.core.i18n.Translatable /
   Language` are imported directly; those branches have merged.

4. **Semantic diffing, not structural.** `DivergenceClassifier`
   compares live pydantic payloads against the local pydantic
   shape field-by-field with per-field comparators that emit
   typed `DivergencePayload` union members. Structural
   dict-diffs are rejected — they destroy the semantic
   information classification depends on.

5. **Bounded auto-heal policy (the correctness core of the
   feature):** auto-heal requires **both** conditions:

   - `classification == DivergenceClassification.ADDITIVE`
   - `divergence_payload.kind in AEAT_SYNC_AUTO_HEAL_ALLOWLIST`

   All other records — including every `BREAKING` and every
   `SUSPICIOUS` record — are persisted with
   `resolution_state = PENDING` and the runner refuses to apply
   them, even when invoked with `auto_heal=True`. This is the
   single invariant the test suite must protect rigorously.

   Starting allowlist (operator-configurable, kept intentionally
   small):

   - `casilla_added_with_default`
   - `label_translation_added`
   - `vigencia_extended`

   Everything else — `casilla_removed`, `casilla_type_changed`,
   `formula_changed`, `label_es_changed`, `portal_url_changed`,
   `unknown_shape` — is non-allowlisted by construction.

6. **Read-only against AEAT.** The runner never submits forms,
   never mutates AEAT server state, never retries on AEAT-side
   errors beyond transient navigation failures. The "healing"
   is always local: a local-schema migration record, not a
   write to AEAT.

7. **Strategies are pluggable.** `HealingStrategy` is an ABC
   keyed on `DivergenceClassification`. Default strategies:

   - `AdditiveAllowlistStrategy` — auto-applies allowlisted
     additive divergences via local-schema migration records.
   - `EscalateStrategy` — emits a PENDING divergence record and
     refuses to act. Used for every non-ADDITIVE classification
     and every non-allowlisted additive kind.
   - `BenignRecordStrategy` — records BENIGN divergences for
     audit with no action.

8. **Persistence is abstracted.** `DivergenceRecordRepository`
   is a Protocol. Two implementations ship:

   - `JsonFileDivergenceRepository` — one JSON file per
     divergence under `AEAT_SYNC_DIVERGENCE_FILE_DIR`. Default
     until #10 lands.
   - `StorageDivergenceRepository` — stub pointing at #10's
     planned persistence layer, selected when
     `AEAT_SYNC_DIVERGENCE_SINK=STORAGE`. Marked rebase-swap.

9. **Errors inherit from `aeat.core.errors.AeatError`.** Concrete
   subclasses: `SyncError`, `WireValidationError`,
   `DivergenceClassificationError`, `HealingError`,
   `DivergenceRepositoryError`.

10. **CLI surface.** Subcommands are wired through the existing
    typer-based CLI under `src/aeat/entrypoints/cli/sync/`:

    - `aeat sync run [--modelo ID] [--period P] [--auto-heal]`
    - `aeat sync list-divergences [--state S] [--since DATE]`
    - `aeat sync show-divergence <record-id>`
    - `aeat sync resolve-divergence <record-id> --action
      approve|reject [--notes TEXT]`

11. **Additive settings only.** New env vars added to
    `aeat.core.config.Settings` and documented in `env/.env.example`:

    - `AEAT_SYNC_CONCURRENCY` (default 4)
    - `AEAT_SYNC_AUTO_HEAL_ALLOWLIST` (CSV, default
      `casilla_added_with_default,label_translation_added,vigencia_extended`)
    - `AEAT_SYNC_DIVERGENCE_SINK` (`FILE` | `STORAGE`, default
      `FILE`)
    - `AEAT_SYNC_DIVERGENCE_FILE_DIR` (default
      `var/divergences/`)
    - `AEAT_SYNC_RETRY_MAX` (default 3)
    - `AEAT_SYNC_RETRY_BACKOFF_S` (default 5.0)

12. **Testing.** Unit tests colocate with the modules. They use
    real Protocol-conforming test doubles, not `unittest.mock` /
    `pytest-mock`. Live tests (`@pytest.mark.live`) are opt-in
    via `AEAT_LIVE_TESTS_ENABLED=1` and run a single end-to-end
    fetch → validate → diff → record against a low-risk AEAT
    endpoint. They require a real cert from #8; skipped by
    default.

## consequences

### positive

- Strict pydantic everywhere gives deterministic validation
  errors at the boundary and prevents silent coercion.
- Bounded auto-heal is explicit in code (two checks: enum +
  allowlist) and enforced by tests.
- Protocol-based dependency injection keeps the branch
  compilable standalone and lets the parallel branches land in
  any order.
- Semantic diffing scales: adding a new divergence kind is a new
  `DivergencePayload` union member + a classifier rule, no
  refactor.
- CLI gives humans a way to triage divergence records without a
  UI.

### negative / trade-offs

- Semantic diffing is more work than structural diffing and
  requires per-field comparators. Acceptable because
  classification is the whole point.
- Protocol stubs must be kept in sync with the in-flight
  branches' real surfaces on rebase. Mitigation: one commit per
  rebase-swap, referenced from this ADR.
- The starting allowlist is deliberately small; operators will
  likely want to extend it. That expansion must go through code
  review, not env-var editing alone.

## non-goals (explicit)

- Filing modelos or any other write against AEAT.
- Multi-user / multi-tenant orchestration.
- A UI beyond the CLI listing.
- Remediating AEAT-side server errors.
- Notifications beyond structured logs + divergence records.
- Hard imports from `aeat.corpus`, `aeat.domain.schema`, `aeat.domain.manuals`,
  `aeat.adapters.outbound.llm`, `aeat.adapters.persistence.storage`, `aeat.adapters.outbound.aeat.auth.certificate`,
  `aeat.domain.modelos`, `aeat.domain.portals` (all Protocol-stubbed).

## suspicious-divergence runbook

When a `SUSPICIOUS` record lands:

1. The runner logs a WARN-level entry and persists the record
   with `resolution_state=PENDING`.
2. An operator runs `aeat sync show-divergence <record-id>` and
   inspects the live payload + local shape side by side.
3. If legitimate: `aeat sync resolve-divergence <id> --action
   approve --notes <reason>`. The operator then updates the
   local corpus / schema / manual manually — the runner does
   NOT apply the change automatically.
4. If hostile (possible AEAT tampering / MITM / bot trap):
   `aeat sync resolve-divergence <id> --action reject --notes
   <reason>`. The operator investigates the browser session
   provenance before re-running.

## acceptance criteria

- Vault research + ADR + plan + exec records landed.
- `src/aeat/application/sync/` exposes `LiveSyncRunner`, `WireValidator`,
  `DivergenceClassifier`, `HealingDispatcher`, every wire
  schema, every divergence record type, every healing strategy.
  Pydantic v2 strict everywhere.
- CLI subcommands wired.
- Settings + env example updated; `tests/test_config.py` green.
- Unit tests cover wire validation, classification for every
  divergence kind, every healing strategy, the bounded
  auto-heal invariant (rigorously), and pydantic round-trips.
  No mocks.
- One opt-in live test, skipped by default.
- `just lint && just typecheck && just test && just hooks` all
  green on Windows.
