# modelo calculation, evidence and filing lifecycle

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-146` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope

This chunk covers 15 files, 4,663 manifest-counted lines, 210,955 bytes, and 45,124 measured tokens. All nine bounded pages were read through their listed ranges. This is static inspection only; I did not import or execute the application, modify `src/`, run tests, or verify legal propositions against external authorities.

## Product capabilities

The model lifecycle separates a calculation attempt from its filing event. A `CalculationRevision` holds inputs, overrides, outputs, typed casilla observations, repeating-row data and source identities, registry snapshot, unresolved source issues, and lifecycle metadata. Its deterministic SHA-256 identity covers canonical calculation inputs and provenance, including row materialization, explicit clears, operator-authored values, amendments, and the Modelo 303 annual-summary handoff. Draft, fully verified, filed, superseded-filed, and discarded states carry distinct metadata requirements; a verified or filed revision is sealed, and recalculation creates another revision revision identity contract (`src/cadrumo/domain/modelos/calculation_revision.py`) canonical revision hashing (`src/cadrumo/domain/modelos/calculation_revision_identity.py`) lifecycle validation (`src/cadrumo/domain/modelos/calculation_revision.py`).

Revision validation checks that output values agree with the typed observations, that row coordinates have source identities and matching values, that provenance contributors resolve to primary sources, that replay channels do not reuse IDs, and that an annual handoff’s values match the target revision. Catalogue upsert preserves already validated aggregate context when updating an ordinary revision and requires that context to validate amendment-bound changes revision invariants (`src/cadrumo/domain/modelos/calculation_revision.py`) row validation and secure serialization (`src/cadrumo/domain/modelos/calculation_revision.py`) catalogue upsert (`src/cadrumo/domain/modelos/calculation_repository.py`).

The M303 evidence family records filing-instance elections, insolvency facts, the evidence supporting an exonerado-390 claim, annual simplified-regime activities and module calculations, DANA/Lorca reductions, and the digest of the complete annual result. A separate immutable 303-to-390 handoff binds source and target work units, periods, registry revisions, result digest, evidence references, and selected casilla values. It resolves the selected source and target registry revisions and requires a digest-consistent, non-empty value map. Rectificativa aggregate validation joins the revision to its parent work unit, exact registry snapshot and record-design source, prior accepted filing record, matching receipt, and authoritative taxpayer identity M303 evidence models (`src/cadrumo/domain/modelos/calculation_revision_m303_evidence.py`) annual handoff (`src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py`) rectificativa authority join (`src/cadrumo/domain/modelos/calculation_revision_aggregate.py`).

`ModeloRecord` represents a local or externally confirmed filing event independently of the calculation. It records the filing actor and time, declaration kind, AEAT confirmation/register evidence, settlement facts, amendment/supersession links, and ledger transaction footprint. Catalogues enforce unique current records per bucket/model/year/period/member, resolve same-coordinate amendment links in both directions, and expose current, latest-confirmed, and historical queries record model (`src/cadrumo/domain/modelos/filing_record.py`) catalogue and chain checks (`src/cadrumo/domain/modelos/filing_record.py`) filing record upsert (`src/cadrumo/domain/modelos/filing_repository.py`). For Modelo 303, settlement snapshots keep declaration liability separate from evidenced payments and from the refund lifecycle; payment state is derived from recorded evidence, and credit snapshots enforce opening plus generated minus applied equals remaining settlement records and invariants (`src/cadrumo/domain/modelos/filing_record.py`) derived payment state (`src/cadrumo/domain/modelos/filing_record.py`).

The chunk also supplies a strict three-digit `ModeloCode` value object, bounded operator labels/reasons/notes, and a DT 12ª pension-plan reduction. The reduction uses the fact-resolved rate and cent rounding, rejects invalid amounts or a pre-2007 contribution share above total contributions, and has a separate predicate for the fact-resolved contingency-year window modelo code (`src/cadrumo/domain/modelos/codes.py`) DT 12 reduction (`src/cadrumo/domain/modelos/dt12_reduccion.py`) eligibility window (`src/cadrumo/domain/modelos/dt12_reduccion.py`) bounded filing text (`src/cadrumo/domain/modelos/filing_text.py`).

## How it works and knowledge

The revision identity is assembled by one shared builder and projected through one canonical hash function, so write-side validation and read-side reconstruction use the same identity axes. Decimal values, row maps, detail rows, source provenance, issue records, and optional payloads are normalized and sorted before hashing. Some fields are deliberately derived evidence rather than independent identity inputs: unresolved outcomes and ledger snapshot/evidence are carried alongside the calculation but excluded from the hash; a separate post-roundtrip check compares ledger snapshot and evidence contributor sets identity inputs (`src/cadrumo/domain/modelos/calculation_revision.py`) excluded derived fields (`src/cadrumo/domain/modelos/calculation_revision.py`) snapshot/evidence coverage check (`src/cadrumo/domain/modelos/calculation_revision.py`).

The annual M303 result binds formula results to a source Orden, record design, epoch and filing year, then checks activity and module order against the immutable filing rows. Handoff selection resolves from caller-pinned authority and refuses when the selected M390 revision lacks the declared handoff bindings. Some capability lookups still create a bundled authority operation if none is passed. Rectificativa applicability also resolves registry declarations using `today_madrid()` even when given a revision ID and source design; that may be an intentional current-capability gate, but historical amendment use should be checked against the desired temporal policy annual result digest and coordinate (`src/cadrumo/domain/modelos/calculation_revision_m303_evidence.py`) handoff authority selection (`src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py`) current-date rectificativa lookup (`src/cadrumo/domain/modelos/calculation_revision_amendment.py`).

The legal amounts, fact rates, filing availability, and record-design meaning are not authored entirely in these models. DT 12 inputs come through `ModeloFactResolutionContext`; amendment declarations and M303/M390 bindings come from registry authority; persistence errors point to encrypted adapter repositories not included here. This report describes the code’s contracts, not the current legal correctness or freshness of its registry data fact-resolved pension inputs (`src/cadrumo/domain/modelos/dt12_reduccion.py`) calculation repository boundary (`src/cadrumo/domain/modelos/calculation_repository.py`) filing repository boundary (`src/cadrumo/domain/modelos/filing_repository.py`).

## Security and implementation assessment

The code has strong local integrity controls: strict frozen records, content digests, exact registry/source coordinates, canonical row serialization, digest checks, and typed unresolved-source findings. The default revision serializer removes sensitive row materialization fields unless the secure-calculation context is set; the secure form serializes the fields in canonical list form. Callers and persistence adapters must use that explicit context when those fields need to survive a secure round trip secure revision validator (`src/cadrumo/domain/modelos/calculation_revision.py`) contextual row serialization (`src/cadrumo/domain/modelos/calculation_revision.py`).

One type contract is inconsistent: `CalculationRevision.source_transaction_ids` is documented as ledger transaction IDs but annotated as `tuple[CalculationRevisionId, ...]`; the filing-record footprint in the same domain uses `TransactionId`. The revision’s before-validator checks only that the values are strings and canonicalizes them; the field annotation therefore misstates the domain identity for static callers even if both ID forms share a compatible wire shape. Align the type with the ledger transaction ID or document why the revision ID type is intended revision field and validator (`src/cadrumo/domain/modelos/calculation_revision.py`) filing record transaction type (`src/cadrumo/domain/modelos/filing_record.py`).

The filing catalogue checks reciprocal same-coordinate links and at most one current record, but does not require a current tip or traverse the graph to prove it is acyclic. The local checks appear to admit a two-record reciprocal supersession cycle if both records carry valid superseded timestamps and point to one another. That conflicts with the module’s stated linear-chain model; add a traversal/chronology invariant if the catalogue itself must guarantee a linear history rather than relying on mutation workflows supersession metadata (`src/cadrumo/domain/modelos/filing_record.py`) catalogue amendment-link validation (`src/cadrumo/domain/modelos/filing_record.py`).

The registry-date choice for rectificativa applicability also deserves a policy check: the method verifies the exact revision/source digest/epoch against declarations selected for today. If capability is supposed to follow the filing’s historical revision date, this current-date lookup can differ from the supplied filing coordinate. No tests are included in the assigned chunk, so the static reading does not establish whether callers or catalogue fixtures constrain these cases date selection (`src/cadrumo/domain/modelos/calculation_revision_amendment.py`).

## Dependencies and follow-up

Trace secure serialization through the encrypted revision adapter and confirm row identities and provenance survive storage/load. Confirm that the type of `source_transaction_ids` agrees at the aggregation, revision, snapshot, and filing-record boundaries. Verify catalogue mutation code always maintains an acyclic supersession chain with an intended current tip. Finally, confirm whether rectificativa capability is selected by today’s declarations or by the filing’s historical authority coordinate, and surface that rule consistently to the operator.

## Complete assigned-file coverage

- modelos/__init__.py (`src/cadrumo/domain/modelos/__init__.py`)
- modelos/calculation_repository.py (`src/cadrumo/domain/modelos/calculation_repository.py`)
- modelos/calculation_revision.py (`src/cadrumo/domain/modelos/calculation_revision.py`)
- modelos/calculation_revision_aggregate.py (`src/cadrumo/domain/modelos/calculation_revision_aggregate.py`)
- modelos/calculation_revision_amendment.py (`src/cadrumo/domain/modelos/calculation_revision_amendment.py`)
- modelos/calculation_revision_identity.py (`src/cadrumo/domain/modelos/calculation_revision_identity.py`)
- modelos/calculation_revision_m303_evidence.py (`src/cadrumo/domain/modelos/calculation_revision_m303_evidence.py`)
- modelos/calculation_revision_m303_handoff.py (`src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py`)
- modelos/calculation_revision_operator_layer.py (`src/cadrumo/domain/modelos/calculation_revision_operator_layer.py`)
- modelos/codes.py (`src/cadrumo/domain/modelos/codes.py`)
- modelos/dt12_reduccion.py (`src/cadrumo/domain/modelos/dt12_reduccion.py`)
- modelos/errors.py (`src/cadrumo/domain/modelos/errors.py`)
- modelos/filing_record.py (`src/cadrumo/domain/modelos/filing_record.py`)
- modelos/filing_repository.py (`src/cadrumo/domain/modelos/filing_repository.py`)
- modelos/filing_text.py (`src/cadrumo/domain/modelos/filing_text.py`)
<!-- /preserved:article -->
