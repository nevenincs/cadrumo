---
tags:
  - '#audit'
  - '#centralized-module-drift'
date: '2026-05-27'
modified: '2026-05-27'
related: []
---

# `centralized-module-drift` audit: `Centralized module drift swarm audit`

## Scope

Eight-axis parallel swarm audit (sonnet + haiku) over the ~1530 `.py`
files under `src/aeat/`. Each axis was scoped to a single drift family
and instructed to return concrete `file:line` findings with remediation,
not commentary. Production code only; tests, fixtures, scripts, and
`_data/` excluded except where typecheck escape hatches surfaced in
test files.

Axes audited:

- **A1** centralized exceptions (`aeat.core.errors`) — sonnet
- **A2** centralized logging (`aeat.core.logging.get_logger`) — sonnet
- **A3** centralized locale (`aeat.core.i18n.tr` / `Translatable`) — sonnet
- **A4** pydantic v2 boundary models — haiku
- **A5** duplication and redefinition — haiku
- **A6** stubs and dead code — haiku
- **A7** hardcoded values and global-enum bypass — sonnet
- **A8** typecheck escape hatches (`cast`, `# type: ignore`, `Any`) — haiku

Anchors used: `src/aeat/core/errors/__init__.py`, `src/aeat/core/logging.py`,
`src/aeat/core/i18n/__init__.py`, `src/aeat/core/external_constants.py`,
project rules `aeat-architecture-boundaries`, `aeat-calculation-grounding`,
`aeat-source-hygiene`, `aeat-quality-gates`.

## Severity ranking

| Axis | Findings | Severity | Hotspot |
| --- | --- | --- | --- |
| A1 exceptions | 25 | **HIGH** | wizard setup-answers, namespace registry, workflow engine `except Exception`, two unregistered `Exception` subclasses |
| A7 hardcoded / enum-bypass | 15 | **HIGH** | `input_kind` Literal comparisons (27 sites), `AggregationSourceKind` inlined as strings (53 sites), review-status enum bypass |
| A3 locale | 25 | **HIGH** | `ModeloVerificationFinding.message/next_action` constructed with bare English f-strings; sede adapter errors raised without `translated_message` |
| A2 logging | 14 | **MEDIUM** | raw `logging.getLogger` bypasses `SecretScrubbingFilter`; `print()` in auth adapter; observability sink installed without scrubbing filter |
| A5 duplication | 9 | **MEDIUM** | `_storage_path` ×7, `_now` / `_utcnow` ×6, `_ensure_utc` with **conflicting semantics** across 4 sites, `_round_to_cents` ×3 |
| A4 pydantic boundaries | 10 | **MEDIUM** | oracle replay payloads return `dict[str, Any]` from `decode_replay_json_payload`; Google / Playwright dicts are legitimately documented |
| A8 typecheck escapes | 20 | **LOW** | no bare `# type: ignore` / `# noqa`; 21 `cast()` calls (11 in tests); existing `__iter__` override pyright-ignores are documented |
| A6 stubs / dead code | 1 | **LOW** | only one real finding (empty `TYPE_CHECKING: pass` block); other suspects are legitimate ABC contracts or compat bridges |

## Findings

### A1 centralized exceptions

Standing review gate G1/G2 violations. Domain code raises stdlib
`ValueError` / `TypeError` / `RuntimeError` outside pydantic validator
contexts, so the raises escape `ERROR_REGISTRY`, skip
`build_error_envelope`, and surface as untyped tracebacks with no
`ErrorCode` and no i18n.

Highest blast-radius items:

- **A1.1** `TaxationComparisonError` directly subclasses `Exception` and
  is never registered. Location: `src/aeat/application/modelo/_taxation_comparison.py:220`.
- **A1.2** `_BinaryXlsConversionError` directly subclasses `Exception`
  inside the parity harness. Location: `src/aeat/domain/calculations/registry/_workbook_parity.py:63`.
- **A1.3** Export boundary raises `ValueError` for unsupported format —
  bypasses envelope. Location: `src/aeat/application/export/_tabular.py:74` plus
  six further `ValueError` raises in the same file.
- **A1.4** Three Playwright adapters (`_renta_web_open.py:158`,
  `_nif_iva_check.py:300`, `_groi_check.py:279`) raise raw `TypeError`
  at the browser boundary.
- **A1.5** Wizard `_setup_answers.py` has 15+ coercion raises of
  `TypeError` / `ValueError` outside pydantic validators.
- **A1.6** Storage namespace registry: 12 boot-time `ValueError` raises
  in `src/aeat/adapters/persistence/storage/_namespace_registry.py`.
- **A1.7** Aggregation service: 9 configuration `ValueError` raises in
  `src/aeat/application/aggregation/_service.py`.
- **A1.8** Workflow engine `_engine.py` has seven `except Exception`
  clauses that route through `_record_unhandled` without constructing
  an `AeatError` envelope — observability loses `ErrorCode`.
- **A1.9** `entrypoints/cli/_modelo.py:564` swallows every exception
  during autocomplete (`except Exception: return ()`), masking real
  `AeatError` failures.
- **A1.10** `entrypoints/cli/_ledger.py:1831` reclassifies any
  exception as "no active profile" — destroys structured context.

Remediation pattern: add per-leaf `_errors.py` subclasses of
`CoreError` / `CoreValidationError`; replace stdlib raises; narrow the
`except Exception` catches in CLI and workflow engine to `AeatError`
subtypes.

### A2 centralized logging

`get_logger` from `aeat.core.logging` installs `SecretScrubbingFilter`
and the run-context record factory. Direct `logging.getLogger(...)`
bypasses both — taxpayer NIF / credential data passing through those
loggers is never masked, and run-id / step-id stamping is lost.

Highest-impact items:

- **A2.1** `src/aeat/entrypoints/cli/_stdio.py:122` —
  `_LOGGER = logging.getLogger(__name__)` at module level.
- **A2.2** `src/aeat/core/errors/_registry.py:247` — inline
  `_logging.getLogger(__name__).debug(...)` inside the error-registry
  resolution failure path.
- **A2.3** `src/aeat/core/observability/_sink.py:117` — the sink's own
  failure path bypasses scrubbing.
- **A2.4** `src/aeat/core/observability/_context.py:243` — root logger
  `addHandler(sink)` without first attaching `SecretScrubbingFilter`.
- **A2.5** `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py:289`
  emits authentication waiting messages via `print(line, file=stream)`,
  fully bypassing the logging stack.
- **A2.6** `src/aeat/application/wizard/_prompter.py:187` uses
  `sys.stdout.write(...)` directly in the application layer.
- **A2.7** Duplicated third-party-logger silencing for `pdfminer` in
  both `_pdfplumber.py:52` and `_record_design.py:675` — should be
  centralized in `configure_logging()`'s dictConfig.

Remediation pattern: replace every production `logging.getLogger` with
`get_logger`; add `pdfminer` and `pikepdf._core` to dictConfig
`loggers`; expose `attach_run_sink(sink)` helper in `aeat.core.logging`
that installs the scrub filter before attaching.

### A3 centralized locale

Standing gate G3 violations. Three distinct patterns produce
operator-visible English strings:

- **A3-pattern A** `ModeloVerificationFinding.message` and `next_action`
  fields in `src/aeat/application/modelo/_actions.py` are constructed
  with hard-coded English f-strings (cross-casilla invariant, registry
  snapshot unresolved, DT12 reducción advisory, IVA wallet next-action,
  missing required casilla). Rendered verbatim in `aeat app modelo work
  verify` text and JSON. Lines: 1281, 2440, 2441, 2679, 2764, 2794,
  2806.
- **A3-pattern B** `SedeNavigationError` / `SedeParseError` raised with
  positional English `message` and no `translated_message`. Five sites:
  `_auth_state.py:18,21`, `_walker.py:73`, `_declarations.py:342,912`,
  `_notifications.py:443`, `_iva_compensation_wallet.py:589,612`.
- **A3-pattern C** CLI emit sites bypass `tr()` entirely:
  `_common.py:139-140,263`, `_ledger.py:279`, `_modelo.py:364,369-379,3020,3058`,
  `_commands.py:906-910`, `diagnostics/profile.py:112,149,166`.

Remediation pattern: scaffold catalog keys via
`python -m aeat.locales scaffold`; thread `tr()` at every emit site;
populate `translated_message=` on every `SedeError` raise.

### A4 pydantic boundary models

Production boundary leaks are concentrated in oracle replay:

- **A4.1** `decode_replay_json_payload` at
  `src/aeat/domain/calculations/registry/_live_parity.py:593` returns
  `dict[str, Any]`. Three callers (`_aeat_nif_iva_oracle.py:122-134`,
  `_groi_oracle.py:148-165`, `_renta_web_open_oracle.py:127-140`)
  manually unpack the dict instead of model-validating.
- **A4.2** LLM cache entry path
  `src/aeat/adapters/outbound/llm/_cache.py:93-96` consumes payload
  without an explicit `model_validate` wrapper — needs verification.

Documented and acceptable boundaries (Google / Playwright stubs):
`_calc_sheets_apply.py:118`, `_google_drive.py:322`, `session.py:69,184`.

Remediation: introduce `ReplayPayload(BaseModel)` base + per-oracle
subclasses; replace `dict[str, Any]` return with the typed envelope.

### A5 duplication

Helper duplication driven by per-module self-sufficiency rather than
architectural reason:

- **A5.1** `_storage_path` defined in seven places under
  `src/aeat/application/` (evidence, inventory, ledger ×2, live ×3) —
  identical `root.mkdir(...) / return root / f"{bucket_id}.*"` shape
  with different roots.
- **A5.2** `_now` / `_utcnow` defined in six modules
  (`ledger/_business_operation_invoice.py:285`, `ledger/_evidence.py:121`,
  `live/_expedientes.py:76`, `live/_notifications.py:78`,
  `live/_verify.py:73`, `workflow/_engine.py:99`) — all return
  `datetime.now(UTC)`.
- **A5.3** **`_ensure_utc` has conflicting semantics across four sites**
  (`auth/certificate.py:296`, `storage/bucket/_manifest.py:33`,
  `storage/master_key/_recovery_record.py:36`,
  `user_profile/_aggregate.py:34`) — two coerce naive datetimes to UTC,
  two reject them. **This is a correctness hazard, not just duplication.**
- **A5.4** `_round_to_cents` in three `domain/fincas/` modules.
- **A5.5** `_parse_bool` with different return types (`bool` vs
  `bool | None`) between `domain/deadlines/_profiles.py:173` and
  `adapters/outbound/aeat/sede/_censo.py:249`.
- **A5.6** `_format_decimal` in four places; `_coerce_decimal` in three.
- **A5.7** `extract_verdict_from_response_text` near-identical in
  `_groi_check.py:438` and `_nif_iva_check.py:453`.

Remediation: introduce `aeat.core.time._utils`, `aeat.core.decimal`,
and `aeat.core.parsing._utils`; canonicalise the conflicting
`_ensure_utc` pair with explicit names (`_coerce_utc_aware` vs
`_validate_utc_aware`) before consolidation.

### A6 stubs and dead code

Single real finding: empty `if TYPE_CHECKING: pass` block at
`src/aeat/application/modelo/_taxation_comparison.py:34-35`. All other
suspected stubs are legitimate (ABC contracts in
`core/resources/_repository.py`, `SecureBoundRepository` abstract
`extract_identifier`, idiomatic exception class `pass` bodies). One
explicit legacy compat path —
`_legacy_iva_wallet_decision_key` in
`application/calculations/_observations_repository.py:134-141` — is a
documented migration bridge; flagged for deferred cleanup, not
violation.

### A7 hardcoded values and enum bypass

Two patterns dominate:

- **A7.1 enum bypass** Existing `Literal` / `StrEnum` types are
  ignored in favour of bare string comparisons. Top offenders:
  - `input_kind` Literal: 27 bare `== "computed"` / `== "manual"`
    sites across 12 files. Promote to `InputKind` StrEnum.
  - `AggregationSourceKind` already a StrEnum but 53 raw `"ledger_transaction"`
    / `"purchase_invoice_evidence"` / `"payable_invoice"` /
    `"collectible_invoice"` literals across 8 files.
  - Review status: `"pending"` / `"reviewed"` / `"skipped"` returned raw
    from 4 sites even though `ReviewStatusFilter` StrEnum exists.
  - `IVARegime` bypassed by `frozenset({"SIMPLIFICADO"})` and
    `click.Choice([...])`.
  - `OracleEnvironment` `Literal` used as default value 6× — should be
    a StrEnum.
- **A7.2 magic strings / constants** missing from
  `external_constants.py`:
  - `"es"` locale fallback hard-coded in 8 sites — needs
    `DEFAULT_OUTPUT_LANGUAGE`.
  - `"EUR"` currency in 20 sites across 8 files — needs
    `DEFAULT_CURRENCY`.
  - `"application/octet-stream"` MIME type in 3 sites (one already
    extracted) — needs `BINARY_MIME_TYPE`.
  - CSV encoding fallback chain hard-coded inline in
    `providers/_csv.py:299`.
  - File-extension sets duplicated across financial providers.

No naked `os.environ` reads detected outside the legitimate
`COLUMNS` display side-effect.

### A8 typecheck escape hatches

Healthiest axis. Zero bare `# type: ignore`. Zero bare `# noqa`. 21
`cast()` calls — two are documented third-party API boundaries
(pikepdf, SQLAlchemy `CursorResult`), eleven sit in test files casting
CLI output without typed schemas, the rest are envelope-layer generic
narrowing.

Production-side priorities:

- **A8.1** `cast(T, envelope.payload)` at
  `_secure_repository.py:174` — add inline justification or refine the
  envelope generic.
- **A8.2** `cast(Any, Envelope).__class_getitem__(...)` at
  `_secure_repository.py:248` — accessing `__class_getitem__` on `Any`
  is a smell; needs a typed factory.
- **A8.3** `cast(Callable[P, R], existing)` at
  `entrypoints/cli/_errors.py:214` — replace with `TypeGuard`.
- **A8.4** Five `-> Any` returns concentrated in Google adapters and
  `aeat.core.logging._scrub_value` (logging scrubber is justified by
  recursive heterogeneous payload; Google adapters should refine via
  `google-api-python-client-stubs` if present).

Tool-runner output:

- `ty` reports 142 diagnostics across ~12 files; top categories are
  unresolved-reference (imports), invalid-argument-type union
  mismatches, not-subscriptable, annotation gaps. **Tracked
  separately — not part of this audit's remediation queue.**
- `ruff --select=ANN,F,E,UP` reports 691 findings (mostly missing
  annotations and `typing.Iterator` → `collections.abc.Iterator`
  upgrades, 23 auto-fixable).

## Recommendations

Process every finding via the standard incremental pattern (structural
fix + roundtrip test, vault note explaining wontfix, or follow-up Step
linked back to this document) — do not let findings rot.

Suggested execution order (highest leverage first):

1. **A1 + A2** in a single sweep: introduce missing `_errors.py`
   subclasses, swap all stdlib raises and raw loggers in the
   high-traffic modules (wizard setup-answers, namespace registry,
   workflow engine, sede adapters). These two axes co-locate cleanly
   per leaf.
2. **A5.3 conflicting `_ensure_utc` rename + consolidation** first
   (correctness hazard), then bulk-merge the other helper duplicates.
3. **A7.1 enum-bypass campaign**: promote `InputKind` and the
   `OracleEnvironment` Literal to `StrEnum`; replace the 27 + 53 + N
   bare-string callsites; add `DEFAULT_OUTPUT_LANGUAGE`,
   `DEFAULT_CURRENCY`, `BINARY_MIME_TYPE` to `external_constants.py`.
4. **A3 locale**: scaffold catalog keys for the three patterns A/B/C;
   `ModeloVerificationFinding` constructors and `Sede*Error` raises
   should be the first surface to land.
5. **A4** typed `ReplayPayload` and per-oracle subclasses.
6. **A6** delete the one stub; schedule the legacy IVA wallet decision
   key bridge for migration close-out.
7. **A8** documented; address case-by-case during touched-area work,
   not as a campaign.

A targeted follow-up plan in `.vault/plan/` should sequence A1+A2 and
A7 as two parallel L2 plans (clean leaf-by-leaf surface), with A3 and
A5 as separate single-feature plans. The `ty` / `ruff` raw counts in
A8 belong to a tooling-config conversation, not this drift sweep.

The eight transcripts are summarised inline above; raw agent outputs
sit under the harness task store and are not preserved in the vault.
