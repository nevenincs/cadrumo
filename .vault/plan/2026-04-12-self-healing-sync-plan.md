---
tags:
  - "#plan"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
title: Self-Healing Sync Implementation Plan
related:
  - "[[2026-04-12-self-healing-sync-adr]]"
  - "[[2026-04-12-self-healing-sync-research]]"
---

# plan: self-healing sync (issue #11)

Phase: `phase-1` (single phase — one branch,
`feature/11-self-healing-sync`).

## explicit plan review

Reviewed against the ADR and issue #11 on 2026-04-12.

- Scope matches issue #11 exactly (fetch / validate / diff /
  classify / heal-or-escalate / audit / CLI).
- Pydantic mandate respected: every boundary type is a strict
  frozen v2 model; enums are `StrEnum`.
- Protocol stubs cover every in-flight subpackage (#6, #7, #8,
  #9, #10, #17, #21, #25); only #16 browser and #20 i18n are
  imported directly.
- Bounded auto-heal invariant is codified in two checks
  (classification + allowlist) and tested rigorously.
- Read-only against AEAT; no form submission or server-side
  mutation.
- CLI extends the existing typer surface under `src/aeat/entrypoints/cli/`.
- Settings are additive and alignment-tested.

**Outcome: APPROVED. Proceed to execution.**

## file layout

```
src/aeat/application/sync/
├── __init__.py                 # public re-exports only
├── _protocols.py               # Protocol stubs for in-flight deps
├── _errors.py                  # SyncError + subclasses
├── _wire.py                    # WirePayload pydantic models
├── _divergence.py              # DivergencePayload union + record
├── _classifier.py              # DivergenceClassifier
├── _strategies/
│   ├── __init__.py
│   ├── _base.py                # HealingStrategy ABC
│   ├── _additive_allowlist.py
│   ├── _escalate.py
│   └── _benign.py
├── _dispatcher.py              # HealingDispatcher + HealingPlan
├── _runner.py                  # LiveSyncRunner + SyncRunResult
├── _validator.py               # WireValidator
├── _repository.py              # DivergenceRecordRepository Protocol
│                               #   + JsonFileDivergenceRepository
│                               #   + stub StorageDivergenceRepository
├── test_wire.py
├── test_classifier.py
├── test_strategies.py
├── test_dispatcher.py
├── test_runner.py
├── test_repository.py
├── test_bounded_policy.py      # the invariant
└── test_live_sync.py           # @pytest.mark.live, skipped by default

src/aeat/entrypoints/cli/sync/
├── __init__.py
├── run.py                      # aeat sync run
├── list.py                     # aeat sync list-divergences
├── show.py                     # aeat sync show-divergence
├── resolve.py                  # aeat sync resolve-divergence
└── test_cli.py
```

## step 1 — errors, protocols, wire schemas

- Add `_errors.py`: `SyncError(AeatError)`, `WireValidationError`,
  `DivergenceClassificationError`, `HealingError`,
  `DivergenceRepositoryError`.
- Add `_protocols.py`: define `CertificateBackend`, `CorpusLoader`,
  `SchemaLoader`, `ModeloSchema`, `ManualRulesLoader`, `Rule`,
  `LLMClient`, `LLMRequest`, `DivergenceRecordRepository`, and
  typed `ModeloIdentifier` / `PortalIdentifier` string validators.
  Every Protocol is `@runtime_checkable` and carries a Google-style
  docstring pointing at the owning issue (#8 / #17 / #9 / #25 /
  #21 / #10 / #6 / #7) for rebase-swap.
- Add `_wire.py`: `WirePayloadBase` (frozen strict pydantic v2),
  and concrete subclasses:
  - `WireModeloDefinition` — modelo id, vigencia range, tuple of
    `WireCasilla(id, label: Translatable, type_, default,
    formula)`
  - `WireFilingHistory` — tuple of `WireFilingEntry(modelo, period,
    submitted_at, status)`
  - `WirePortalManifest` — tuple of `WirePortalLink(url: AnyHttpUrl,
    label: Translatable, modelo: str | None)`
- Acceptance: `test_wire.py` — each schema round-trips via
  `model_dump_json` / `model_validate_json`, rejects malformed
  payloads with `ValidationError` wrapped as `WireValidationError`.

## step 2 — divergence + classifier

- Add `_divergence.py`:
  - `DivergenceClassification(StrEnum)` — ADDITIVE, BREAKING,
    BENIGN, SUSPICIOUS.
  - `DivergenceKind(StrEnum)` — enumerates every concrete
    divergence shape (casilla_added_with_default,
    casilla_removed, casilla_type_changed, formula_changed,
    label_translation_added, label_es_changed,
    vigencia_extended, portal_url_changed, filing_status_changed,
    unknown_shape, ...).
  - `DivergencePayload` discriminated union
    (`Field(discriminator="kind")`) of frozen pydantic v2 models,
    one per kind.
  - `ResolutionState(StrEnum)` — PENDING, AUTO_HEALED,
    HUMAN_APPROVED, REJECTED.
  - `DivergenceRecord` — frozen pydantic v2 with fields per ADR.
- Add `_classifier.py`: `DivergenceClassifier` with semantic
  per-field comparators that emit `DivergencePayload` union
  members. The classifier also assigns a
  `DivergenceClassification` per emitted kind via a static table
  (immutable `MappingProxyType`), so classification and kind are
  decoupled but deterministic.
- Acceptance: `test_classifier.py` — one parametrised case per
  `DivergenceKind` covering ADDITIVE / BREAKING / BENIGN /
  SUSPICIOUS buckets, plus a "no divergence" baseline.

## step 3 — strategies + dispatcher

- Add `_strategies/_base.py`: `HealingStrategy(ABC)` with
  `can_handle(record) -> bool` and `async apply(record, *,
  auto_heal: bool) -> StrategyOutcome` where `StrategyOutcome` is
  a frozen pydantic v2 model `(action: StrategyAction, record:
  DivergenceRecord, notes: str | None)` with
  `StrategyAction(StrEnum)` in `{AUTO_HEALED, ESCALATED,
  RECORDED}`.
- Add `_strategies/_additive_allowlist.py`: auto-applies iff
  `classification == ADDITIVE and payload.kind in allowlist`;
  otherwise delegates to escalate.
- Add `_strategies/_escalate.py`: always returns `ESCALATED` with
  `resolution_state=PENDING`.
- Add `_strategies/_benign.py`: records BENIGN with no action.
- Add `_dispatcher.py`: `HealingDispatcher` composes strategies
  in order; `HealingPlan` frozen pydantic v2 model groups
  `(auto_heal: tuple[DivergenceRecord, ...], escalate:
  tuple[DivergenceRecord, ...], benign:
  tuple[DivergenceRecord, ...])`.
- Acceptance:
  - `test_strategies.py` exercises each strategy on synthetic
    divergence records.
  - `test_bounded_policy.py` — parametrises every BREAKING and
    every SUSPICIOUS kind and asserts the dispatcher escalates
    with `auto_heal=True`. This is the critical invariant test.

## step 4 — repository + validator

- Add `_repository.py`:
  - `DivergenceRecordRepository` Protocol (save, load, list,
    update_resolution).
  - `JsonFileDivergenceRepository` implementation — one JSON
    file per record, UTF-8, pretty-printed, atomic writes via
    `os.replace`.
  - `StorageDivergenceRepository` stub raising
    `NotImplementedError("pending storage subpackage from #10")`
    on construction when selected — we do not break the import
    surface, we just refuse to run until #10 rebases in.
- Add `_validator.py`: `WireValidator.validate(raw: bytes | str,
  schema: type[WirePayloadBase]) -> WirePayloadBase` — wraps
  `model_validate_json` into `WireValidationError` on failure.
- Acceptance: `test_repository.py` — round-trip a synthetic
  record through a tmp_path JSON sink; list returns what was
  saved; update mutates resolution state.

## step 5 — runner

- Add `_runner.py`:
  - `SyncRunResult` frozen pydantic v2 model per ADR.
  - `LiveSyncRunner` composing: `BrowserSession`,
    `CertificateBackend`, `CorpusLoader`, `SchemaLoader`,
    `ManualRulesLoader`, `LLMClient`, `WireValidator`,
    `DivergenceClassifier`, `HealingDispatcher`,
    `DivergenceRecordRepository`, and a tuple of
    `HealingStrategy`.
  - `async run(*, modelo=None, period=None, auto_heal=False) ->
    SyncRunResult` orchestrates: preload cert into browser,
    fetch payloads, validate, classify, dispatch, persist,
    emit audit log entries, return result.
- Retries use `AEAT_SYNC_RETRY_MAX` + `AEAT_SYNC_RETRY_BACKOFF_S`
  with exponential backoff on transient navigation failures.
- Acceptance: `test_runner.py` builds a real Protocol-conforming
  test-double harness (concrete classes, no mocks) and asserts a
  happy-path run, a validation-failure path, and a bounded-
  policy path.

## step 6 — settings + env

- Extend `src/aeat/config.py` with the six `AEAT_SYNC_*` fields.
- `AEAT_SYNC_DIVERGENCE_SINK` is a `StrEnum` field.
- `AEAT_SYNC_AUTO_HEAL_ALLOWLIST` is stored as CSV string; the
  runner parses it into a `frozenset[DivergenceKind]` once at
  startup.
- Update `env/.env.example` with the new vars + comments.
- Acceptance: `tests/test_config.py` alignment test green.

## step 7 — cli

- Add `src/aeat/entrypoints/cli/sync/` with four typer subcommands per ADR.
- Wire into the existing cli app under `src/aeat/entrypoints/cli/__init__.py`
  (or whichever module owns the root typer group — read and
  respect the existing convention).
- Acceptance: `test_cli.py` invokes each subcommand via
  `typer.testing.CliRunner` against a tmp repository.

## step 8 — live opt-in test

- Add `test_live_sync.py` marked `@pytest.mark.live`, skipped
  unless `AEAT_LIVE_TESTS_ENABLED=1`. Uses a real cert backend
  and a low-risk AEAT endpoint (e.g. the sede landing page)
  to assert one full fetch → validate → classify cycle.
- Document the opt-in in the ADR (tests/README is owned by
  f/15).

## step 9 — verify

- `just lint && just typecheck && just test && just hooks` —
  all green on Windows.
- Code review via `vaultspec-code-review` covering: pydantic
  strictness, Protocol discipline, bounded policy invariant,
  public API discipline, cross-module import hygiene, error
  hierarchy, logging, tests without mocks.

## rollback

Every step is a focused commit referencing #11. Rolling back
one step is `git revert <sha>`; the branch is isolated from
sibling branches by Protocol stubs, so rollback cannot cascade.
