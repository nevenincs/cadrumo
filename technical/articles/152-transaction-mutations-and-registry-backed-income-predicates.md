# Transaction mutations and registry-backed income predicates

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-152` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope

This chunk covers three files (510 lines; 4,337 measured tokens): pure transaction-catalogue update helpers, dated selector resolution for M036 activity codes, and two agricultural income predicates. It builds on the transaction models and governed-fact contracts reviewed in the preceding chunk; it contains no persistence adapter or application command.

## Product capabilities

The transaction service returns fresh immutable catalogues when it links an invoice or changes a classification. Classification updates preserve an append-only sequence of prior states only when the incoming decision signature differs. Signatures include classification, business share, classifier identity, reason, category, notes, and confidence; default confidence is 1.0 for manual decisions and absent for other classifier paths. Snapshot creation uses the active classification timestamp, then source-ingestion time, then an explicit fallback, so an unclassified imported row can still enter the history chain with a stable chronology. Validation failures are translated to a catalogue-domain error and the source object is left untouched (classification update (`src/cadrumo/domain/transactions/service.py`), history snapshot (`src/cadrumo/domain/transactions/service.py`)).

Activity-selector helpers resolve selector membership and code sets through a caller-supplied or scoped governed authority, always at an explicit filing-period date. A registry catalogue first declares which selector facts are valid; each selector is then resolved as an entity-set fact. The batch loader deduplicates repeated fact IDs and refuses a code that appears under multiple selectors, enforcing at most one route for each activity code (selector resolution (`src/cadrumo/domain/transactions/tipo_actividad_partitions.py`), unique-code guard (`src/cadrumo/domain/transactions/tipo_actividad_partitions.py`)).

The agricultural income module keeps two closely related legal tests distinct. `counts_toward_volumen_de_ingresos` applies the registry’s Article 110 exclusions for the quarterly payment volume; the code comments specifically distinguish current subsidies, which count, from capital subsidies and indemnities, which do not. `counts_toward_art_109_activity_income` resolves a separate exclusion set for withholding-coverage calculations, where both kinds of subsidies and indemnities are excluded. Ordinary income and an undeclared concept count under both predicates. Each uses an explicit effective date and the same pinned authority for fact and concept-catalogue resolution (Article 110 predicate (`src/cadrumo/domain/transactions/volumen_ingresos.py`), Article 109 predicate (`src/cadrumo/domain/transactions/volumen_ingresos.py`)).

## Security and quality assessment

The strongest design choice is that these are domain transformations over typed immutable records rather than direct writes. Governed-fact helpers reject a missing or malformed selector/exclusion fact, and the activity loader refuses ambiguous overlapping membership rather than taking the first match. The income predicates do not duplicate concept lists in Python; they project IDs from registry-owned entity sets into the canonical concept catalogue. This keeps temporal legal data outside the decision code and makes the rule coordinate visible at every public call.

One local idempotence defect occurs in `set_classification`: the incoming classifier and reason are stripped before comparison, but `category_id` and `notes` are compared in their raw caller form and are only stripped later when the transaction model validates the new payload. For example, if the current category is `travel`, calling the helper with `category_id=" travel "` compares unequal, appends a history snapshot, then stores the normalized value `travel`. The business state has not changed, yet history grows. Whitespace-padded notes behave the same way. This is a local mismatch between the documented byte-identical/no-op rule and the normalized persistence boundary; callers cannot reliably make idempotence decisions themselves. Normalize these values before building the signature, using the same rules as the model (signature comparison (`src/cadrumo/domain/transactions/service.py`), ID normalization (`src/cadrumo/domain/transactions/models.py`), text normalization (`src/cadrumo/domain/transactions/models.py`)).

Both mutators also return a changed row with the old `modified_at`: `link_invoice` copies the model and changes `invoice_id`, while `set_classification` changes classification fields, but neither supplies a new modification timestamp. The model contract says this timestamp is re-stamped on every mutating edit and exists to make modification-time sorting honest. Callers may wrap these helpers and restamp outside this module, but the returned catalogue alone does not satisfy that stated contract. Update the timestamp here or document the additional caller obligation (mutators (`src/cadrumo/domain/transactions/service.py`), timestamp contract (`src/cadrumo/domain/transactions/models.py`)).

The optional `category_id` argument also cannot clear an existing category through this helper: `None` means “reuse the current value,” and the update payload only includes a category when non-null. This may be intentional for callers that treat classification categories as sticky, but the interface offers no explicit clear operation. Confirm whether category removal belongs on another service path and make the semantics visible to classification callers.

The income predicates deliberately choose inclusion when the concept is absent. That is an explicit asymmetry: silence may include an exceptional receipt, but excluding by default could omit ordinary income from a filing base. Since callers might otherwise reuse one agricultural predicate for both questions, keeping distinct Article 109 and 110 functions is a meaningful safety feature. End-to-end accuracy still depends on callers supplying the filing-year date and an authority operation pinned to the same generation as the surrounding calculation.

## Dependencies and follow-up

These helpers depend on the strict transaction catalogue and history records, canonical concepts, governed entity-set/mapping facts, and a valid pinned authority scope. Application commands own persistence and user-facing clear/reset semantics; no deletion, reconciliation, or database transaction behavior is defined here. Normalize optional signature fields before comparing them, confirm how callers clear categories, and check that both agricultural predicates are used only for their intended statutory question with matching filing coordinates. No tests or callers are included in this chunk, so this review does not establish the actual mutation workflow or tax-year authority pinning.

## Complete assigned-file coverage

- `src/cadrumo/domain/transactions/service.py`
- `src/cadrumo/domain/transactions/tipo_actividad_partitions.py`
- `src/cadrumo/domain/transactions/volumen_ingresos.py`
<!-- /preserved:article -->
