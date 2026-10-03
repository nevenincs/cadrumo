# Domain evidence, filing periods, and capital-goods registers

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-123` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 24 domain modules, 3,872 physical lines, 163,096 bytes, and 35,913 measured `o200k_base` proxy tokens. All assigned files and line ranges were read in seven bounded pages, including the full 1,118-line capital-goods register. This is static inspection only: no application code or tests were run, no source was changed, and statutory statements in comments were not independently verified against current law.

## Domain evidence, identifiers, and filing periods

The root domain surface stays deliberately narrow. `FilingEvidenceReference` is an immutable, nominal wrapper around a trimmed, non-empty, 256-character-bounded string, so downstream filing facts can require an explicitly admitted evidence identity rather than accepting any arbitrary string. `ModeloIdentifier` validates only three decimal digits plus an optional uppercase suffix; it preserves the textual form and leading zeroes but explicitly does not prove registry membership. `canonical_decimal_string` supplies a stable fixed-point representation for hash payloads without rounding or display formatting. Evidence reference (`src/cadrumo/domain/filing_evidence.py`) Modelo identifier and canonical decimal (`src/cadrumo/domain/identifiers.py`) Domain error boundary (`src/cadrumo/domain/errors.py`)

The period helpers adapt the canonical core `Period` type for bare registry-token edges. They return inclusive start/end dates where a token has a contiguous span, add explicit payment-month boundaries for `1P`–`3P`, and provide a separate calculation filing date for extended, event, ad-hoc, and `4P` tokens. Invalid core period codes are wrapped in a domain-specific period error. This separates ledger span semantics from the filing-date convention used to resolve calculation parameters. The accepted token set and resulting date policy still depend on the core authority and callers, neither of which is independently assessed here. Start/end helpers (`src/cadrumo/domain/period.py`) Calculation filing-date rule (`src/cadrumo/domain/period.py`)

## Attachment custody and apoderamiento scope

The attachment model represents evidence bytes through a frozen manifest: its identifier must equal its SHA-256 digest, timestamps must be aware UTC values, MIME strings are normalized and link-only `text/uri-list` is rejected, linked IDs are trimmed/deduplicated, and metadata is constrained to string keys and values then exposed through an immutable mapping. It carries kind/source, bucket, capture actor/command, cross-links, and notes. A separate strict M303 applicability attestation binds a closed assertion to filing year/period, observation time, and a profile-revision/digest witness; parsing rejects duplicate JSON members and non-standard constants and requires exact canonical JSON bytes. These controls establish structure and byte spelling, but this module does not itself authenticate the profile witness or compare the attestation digest with an attachment blob. Attachment invariants (`src/cadrumo/domain/attachments/models.py`) Strict attestation payload (`src/cadrumo/domain/attachments/m303_filing_evidence.py`) Canonical parser (`src/cadrumo/domain/attachments/m303_filing_evidence.py`)

`add_attachment` accepts either a file path or already-fetched bytes, asks the store to persist content first, then constructs and writes the manifest. The protocol cleanly separates this domain service from its persistence adapter, and the two link helpers can update an existing manifest to record invoice/transaction relations after those business objects exist. They are intended to be idempotent. A failure while validating the manifest after `put_file`/`put_bytes` may leave an unreferenced blob, and the domain protocol does not promise a transaction spanning blob and manifest writes; cleanup/atomicity must therefore be checked at the concrete adapter and callers. The link helpers use `model_copy(update=...)`, which does not run the validators that ordinarily trim/deduplicate IDs, so correctness also depends on callers passing already-valid relation identifiers. Store port (`src/cadrumo/domain/attachments/protocols.py`) Ingest write order (`src/cadrumo/domain/attachments/service.py`) Post-creation links (`src/cadrumo/domain/attachments/service.py`)

The apoderamiento catalogue adapts scope records from a caller-pinned runtime authority; it does not contact AEAT or persist represented-party data. Token parsing rejects commas and lowercase input, expands `ALL` in sorted order, deduplicates while preserving first-occurrence placement, and refuses unknown codes with catalogue-version context. Scope codes are constrained to uppercase alphanumeric/underscore shape. `load_default_catalogue` consumes mapping values and version metadata from the supplied authority; registry validity and whether mapping keys agree with record codes are outside this module's evidence. Pinned catalogue loading (`src/cadrumo/domain/auth/apoderamientos/catalogue.py`) Scope parser (`src/cadrumo/domain/auth/apoderamientos/catalogue.py`) Token resolution (`src/cadrumo/domain/auth/apoderamientos/catalogue.py`)

## Capital-goods IVA regularisation

The largest capability here tracks durable capital-good facts and computes annual art-109 or disposal art-110 regularisations. Records carry acquisition year, input IVA, initial definitive prorrata, registry-backed good kind, art-108 eligibility, acquisition-ledger ID, optional sector, and optional disposal. The annual calculation validates percentages and positive IVA, applies the resolved threshold comparison, selects a registry-declared divisor, computes the signed difference, rounds to cents, and labels repayment versus additional deduction. Disposal calculation instead imputes 100% or 0% according to the selected disposal regime across the remaining window years; it applies the additional-deduction cap only when the caller supplies disposal IVA. That optionality is an explicit integration condition: a reachable caller that omits the amount for a regime requiring the cap can obtain an uncapped result. Record invariants and window (`src/cadrumo/domain/bienes_inversion/register.py`) Annual arithmetic (`src/cadrumo/domain/bienes_inversion/register.py`) Disposal arithmetic and optional cap (`src/cadrumo/domain/bienes_inversion/register.py`)

The register projection reports each eligible in-window asset, marks missing current-year percentages as pending, totals computed amounts into the proposed casilla 43, and carries per-asset sector contributions whose sum is checked against the total. Disposal-year projection uses recorded acquisition facts and produces no pending state. The domain function requires the parameter bundle's resolution year to equal the projection year. A reciprocal-observation validator binds acquisition ledger rows to assets through unique links, same profile, year, ledger ID, and prorrata sector, and refuses missing year-level observations. This is substantive consistency enforcement, although the surrounding application must ensure it supplies all observations from all periods as the contract requires. Annual register projection (`src/cadrumo/domain/bienes_inversion/register.py`) Disposal projection (`src/cadrumo/domain/bienes_inversion/register.py`) Acquisition reciprocity (`src/cadrumo/domain/bienes_inversion/register.py`)

Statutory figures are not hard-coded in the computation: the parameter resolver requires all five figures from the selected revision, checks the revision's validity window, resolves dated values on the filing-period axis, and records model, revision, parameter IDs, and resolution date in immutable provenance. No defaults allow arithmetic to proceed on an incomplete bundle. This is a useful fail-closed authority seam; its assurance rests on the compiled revision and application selection being trustworthy, and conversion/resolver failures are wrapped with underlying exception text. No legal conclusion about the current values follows from this code. Required parameters and provenance (`src/cadrumo/domain/bienes_inversion/regularizacion_parameters.py`) Resolution flow (`src/cadrumo/domain/bienes_inversion/regularizacion_parameters.py`)

## Bucket event history

The event catalogue models a broad, closed set of bucket-scoped workflow and custody transitions. Event IDs are derived from normalized event-body fields and UTC timestamps; payload keys/values are bounded strings, actor labels have a maximum, and events are frozen. Catalogue projections filter by bucket or object and sort by timestamp plus content ID for deterministic ties. Payload length and closed event types are enforced, but secrecy is only a documented producer contract: there is no redaction or secret detector in the event model, and free-form values can still hold sensitive text. The embedded comment also identifies a 500-character payload limit that can reject joined collections at ordinary sizes, making counts/digests or a durable detail record necessary at emitters. Payload bounds and event vocabulary (`src/cadrumo/domain/buckets/event.py`) Event ID derivation and model (`src/cadrumo/domain/buckets/event.py`) Canonical ordering and projections (`src/cadrumo/domain/buckets/event.py`)

Append refuses a reused event ID if payload versions disagree, addressing the fact that `payload_version` is deliberately omitted from the hash. Single and batch emit helpers share derivation and append logic; co-emission can return a secure-object write carrying an expected revision so a caller can commit state and event together. Production repositories may expose a guarded append path, but the narrow protocol does not declare the optional revision/guard methods. Injected implementations without them fall back to load-then-save, which the code documents as exposed to lost updates. History is one growing catalogue, so every append rewrites or composes the full collection; batching reduces round trips but no retention/partition strategy is present in this domain slice. Append collision handling (`src/cadrumo/domain/buckets/event_repository.py`) Revision-aware co-emission write (`src/cadrumo/domain/buckets/event_repository.py`) Guarded emission and fallback (`src/cadrumo/domain/buckets/event_repository.py`) Repository port (`src/cadrumo/domain/buckets/protocols.py`)

## Assessment and follow-up

Strong local controls include strict/frozen value models, canonical evidence serialization, fail-closed dated statutory-parameter resolution, reciprocal acquisition checks, deterministic content-addressed event IDs, and a revision-aware path for atomic audit writes. The most material integration questions are whether attachment blob/manifest persistence is cleaned up or transactionally coordinated, whether post-creation relation IDs are validated before `model_copy`, whether M303 witness authentication occurs at the custody boundary, whether all rule-1 disposals supply their cap input, and whether production event repositories always provide the guarded path. The event secrecy rule needs producer-side enforcement or evidence from callers because the event schema itself accepts arbitrary bounded strings. This chunk contains no tests or runtime call sites; the comment naming a payload-bounding static test is not evidence here that the test was read or passed. Follow-up should inspect the concrete attachment and event repositories, application projection/caller code, the runtime catalogue validator, and their tests.

## Complete assigned-file coverage

- domain/__init__.py (`src/cadrumo/domain/__init__.py`) — lines 1–5
- domain/errors.py (`src/cadrumo/domain/errors.py`) — lines 1–20
- domain/filing_evidence.py (`src/cadrumo/domain/filing_evidence.py`) — lines 1–30
- domain/identifiers.py (`src/cadrumo/domain/identifiers.py`) — lines 1–77
- domain/period.py (`src/cadrumo/domain/period.py`) — lines 1–155
- attachments/__init__.py (`src/cadrumo/domain/attachments/__init__.py`) — lines 1–8
- attachments/enums.py (`src/cadrumo/domain/attachments/enums.py`) — lines 1–95
- attachments/errors.py (`src/cadrumo/domain/attachments/errors.py`) — lines 1–44
- attachments/m303_filing_evidence.py (`src/cadrumo/domain/attachments/m303_filing_evidence.py`) — lines 1–108
- attachments/models.py (`src/cadrumo/domain/attachments/models.py`) — lines 1–279
- attachments/protocols.py (`src/cadrumo/domain/attachments/protocols.py`) — lines 1–60
- attachments/service.py (`src/cadrumo/domain/attachments/service.py`) — lines 1–242
- auth/__init__.py (`src/cadrumo/domain/auth/__init__.py`) — lines 1–20
- auth/apoderamientos/__init__.py (`src/cadrumo/domain/auth/apoderamientos/__init__.py`) — lines 1–29
- auth/apoderamientos/catalogue.py (`src/cadrumo/domain/auth/apoderamientos/catalogue.py`) — lines 1–215
- bienes_inversion/__init__.py (`src/cadrumo/domain/bienes_inversion/__init__.py`) — lines 1–45
- bienes_inversion/register.py (`src/cadrumo/domain/bienes_inversion/register.py`) — lines 1–1,118
- bienes_inversion/regularizacion_parameters.py (`src/cadrumo/domain/bienes_inversion/regularizacion_parameters.py`) — lines 1–268
- bienes_inversion/vocabulary.py (`src/cadrumo/domain/bienes_inversion/vocabulary.py`) — lines 1–25
- buckets/__init__.py (`src/cadrumo/domain/buckets/__init__.py`) — lines 1–8
- buckets/errors.py (`src/cadrumo/domain/buckets/errors.py`) — lines 1–77
- buckets/event.py (`src/cadrumo/domain/buckets/event.py`) — lines 1–544
- buckets/event_repository.py (`src/cadrumo/domain/buckets/event_repository.py`) — lines 1–331
- buckets/protocols.py (`src/cadrumo/domain/buckets/protocols.py`) — lines 1–69
<!-- /preserved:article -->
