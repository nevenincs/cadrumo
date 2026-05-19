---
tags:
  - "#audit"
  - "#alias-elimination-sweep"
date: "2026-05-19"
related:
  - "[[2026-05-19-code-duplication-sweep-plan]]"
  - "[[2026-05-19-code-duplication-sweep-audit]]"
  - "[[2026-05-19-spanish-stem-terminology-authority-adr]]"
---

# alias-elimination-sweep audit: read-only inventory of alias-shaped patterns in `src/aeat/**`

## Scope

Per user mandate paraphrased — legacy is never acceptable; the codebase tolerates no aliases for the sake of keeping two names — this audit inventories every alias-shaped pattern under `src/aeat/**` against the eight categories defined by the PM. Read-only; no code edits. Classification of intentional-vs-legacy is left to PM adjudication per finding, except for Pydantic Field-alias hits where the external-wire-format vs in-repo-residue distinction is mechanical.

## Findings

### Totals by category

- Category 1 (module-level type alias assignments): SIX findings.
- Category 2 (from-import with stem-changing `as`): SEVEN stem-changing hits, after excluding documented short-form import idioms (`as tr`, `as _Settings`).
- Category 3 (`__init__.py` exposing one symbol under two names): ONE finding (cross-listed from category 1).
- Category 4 (empty-body subclass): ONE production finding.
- Category 5 (enum top-level `OldEnum = NewEnum`): subsumed in category 1.
- Category 6 (locale keys mapping two key names to the same value): about 55 to 58 duplicate-value clusters per language file (4 locale files). Spot inspection: almost all are intentional UX repetition. Flagged for PM scan; not enumerated individually.
- Category 7 (CLI flag aliases — two flag names on one option): ZERO findings.
- Category 8 (Pydantic `Field(alias=...)` preserving an in-repo legacy name): ZERO findings. All twelve `Field(alias=...)` hits are external wire-format bindings (Gemini camelCase plus release-please kebab-case JSON).

### Category 1: module-level type alias assignments

Six top-level `NewName = OtherName` assignments at module scope where both sides are real bound classes / enums / types.

- `src/aeat/application/live/_censo.py` line 58: `CensusSnapshotState = SnapshotLifecycleState`. Inline comment states the alias is retained so existing imports keep working unchanged. Stem-change Census-prefix to generic-lifecycle. Legacy-shape per Reader-5; pre-positioned for deletion (task #26).
- `src/aeat/application/live/_borrador_100.py` line 47: `Borrador100SnapshotState = SnapshotLifecycleState`. Same shape; same legacy-residue indicator.
- `src/aeat/domain/submission/_protocols.py` line 104: `FilingFindingSeverity = BaseSeverity`. Part of the in-flight Severity consolidation cluster (task #8).
- `src/aeat/application/user_profile/__init__.py` line 165: `ProfileValidationSeverity = BaseSeverity`. Same consolidation shape.
- `src/aeat/application/transactions/_diagnostics.py` line 44: `LedgerImportDiagnosticSeverity = BaseSeverity`. Same consolidation shape.
- `src/aeat/domain/profile/_constants.py` line 34: `BucketId = ProfileName`. Documented as the storage-layer identifier for the encrypted slice behind one profile. Both names exported via the `__all__` tuple. Deliberate naming split — PM should adjudicate.

### Category 2: from-import with stem-changing `as`

Excludes documented short-form idioms (`as tr` ~50 occurrences; `as _Settings` / `as aeat_logging`). Remaining stem-changing re-imports:

- `src/aeat/application/aggregation/_renta_ledger.py` line 34 plus its test helper line 26: `from ...domain.transactions import TransactionDirection as LedgerTransactionDirection`.
- `src/aeat/adapters/persistence/storage/master_key/_kdf.py` line 19: `from ..bucket._manifest import KdfParams as ManifestKdfParams`.
- `src/aeat/adapters/outbound/aeat/export/test_preflight.py` line 16: `from .....domain.submission._protocols import FilingFindingSeverity as DomainSubmissionFindingSeverity`. Test-only.
- `src/aeat/domain/buckets/_event.py` line 24: `from ._constants import BucketId as _BucketId`. Re-stems to a private copy.
- `src/aeat/application/review/_operator.py` line 11: `from ...core.i18n import tr as render_translation`. Two-layer aliasing.
- `src/aeat/domain/calculations/registry/test_audit_oracle_surface_compatibility.py` line 18 plus `test_live_parity_audit.py` line 30: `from ._aeat_nif_iva_oracle import ORACLE_ID as AEAT_NIF_IVA_ORACLE_ID`.

Plus one private-prefix self-alias (intentional, not legacy):

- `src/aeat/adapters/outbound/llm/_providers/__init__.py` lines 11-12: explicit `name as name` re-exports of two private adapter classes.

### Category 3: `__init__.py` exposing same symbol under two names

- `src/aeat/application/user_profile/__init__.py` line 165 (cross-listed from category 1): `ProfileValidationSeverity = BaseSeverity`. Removal blocked on the Severity-consolidation cluster (task #8).

### Category 4: empty-body subclass

- `src/aeat/domain/calculations/registry/_schema.py` line 1112: `class DeadlineApplicabilityCondition(ProfilePredicateDefinition):` with body `pass`. Two test-file `pass`-only subclasses (`test_session.py` line 48 and `blob_store/test_materialisation.py` line 80) are throwaway local exception types inside test bodies — excluded.

### Category 5: enum top-level `OldEnum = NewEnum`

Subsumed in category 1.

### Category 6: locale keys mapping two key names to the same value

Locale duplicate-value scan against `en.yml`, `es.yml`, `ca.yml`, `hu.yml`: about 55-58 clusters per file. Spot inspection: almost all are intentional UX repetition (same help text for the same flag on multiple subcommands). Five distinct modelo subcommands (`bindings`, `casillas`, `describe`, `formulas`, `work`) share the same `modelo_help` text "Tax form code (e.g. 303, 130, 100)".

Not the alias shape the PM targets; it is one logical message duplicated across distinct command paths. Flagged for PM disposition; not enumerated individually. No literal rename-bridge locale aliases observed.

### Category 7: CLI flag aliases

Grep against the Click multi-flag-name shape returns zero matches across `src/aeat/**`. No findings.

### Category 8: Pydantic `Field(alias=...)` preserving in-repo legacy name

Twelve `Field(alias=...)` occurrences:

- `src/aeat/adapters/outbound/llm/_providers/gemini.py` lines 59, 60, 74: three aliases binding camelCase JSON keys (`promptTokenCount`, `candidatesTokenCount`, `usageMetadata`) from the Gemini API to snake_case Python attribute names. External wire format. STAY.
- `src/aeat/tests/test_release_config.py` lines 56-83: nine aliases binding kebab-case JSON keys from `release-please-config.json` to snake_case Python attribute names (`package-name`, `release-type`, `changelog-path`, `extra-files`, `$schema`, `include-component-in-tag`, `separate-pull-requests`, `changelog-sections`, `.`). External wire format. STAY.

Zero in-repo legacy-name preservers. Category 8 inventory empty of violations.

## Recommendations

Inventory only. PM adjudicates intentional vs legacy per finding. Three structural observations:

- The category 1 plus category 3 hits cluster around two ADR campaigns already in-flight: the censo / borrador snapshot-state cluster (Reader-5; task #26) and the Severity enum consolidation (task #8). Closing those removes 5 of the 6 category 1 findings. The remaining `BucketId = ProfileName` hit is a domain-naming question that needs its own adjudication.
- The category 2 hits cluster around two patterns: stem-changing imports inside renta / ledger / submission / preflight, and test-file re-imports for readability. The renta / ledger / preflight cases are candidates for collapse; test-file aliases are low-priority cosmetic.
- Category 6 is out-of-scope for alias elimination as the PM defines it; any cleanup belongs to a separate locale-key-deduplication initiative if desired.
