# Filing-envelope integrity, export parity, and producer values

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-046` · **Topic:** [Filing exports and live state](../topics/filing-and-live-state.md)

<!-- preserved:article -->
## Scope

This chunk covers seven filing-application modules (3,108 lines; 37,787 measured proxy tokens). I read every assigned range across seven bounded pages. This is static inspection only; no declaration was rendered, verified, or filed. The application surface writes local artifacts and does not submit them to AEAT.

## Envelope contracts and prefix rendering

The filing-envelope request binds one approved draft, producer snapshot, selected registry snapshot, and layout. Validation checks model, year/period, stamped revision, schema version, snapshot-owned layout identity, and the envelope source digest; taxpayer identity must match the approved subject. Modelo-specific policy can add constraints, including Modelo 303 election equality and applicability. Prefix construction is registry-declared by typed roles and exact byte lengths, while model/period/version/developer identity values come from their respective typed authorities. Unsupported period representations and non-ASCII or wrong-length values refuse. The result model recomputes each occurrence digest, verifies declared record-family order and contiguous occurrence numbering, and checks that payload bytes are exactly prefix + ordered body + relative closer. Envelope request checks (`src/cadrumo/application/filing/export_envelope.py`) Draft/snapshot/layout binding (`src/cadrumo/application/filing/export_envelope.py`) Prefix construction (`src/cadrumo/application/filing/export_envelope.py`)

## Pre-write structural parity

The fixed-width parity gate treats a valid SHA-256 as insufficient evidence that the return is complete. It derives representable casillas from the official layout, including row-field mappings and the disposition-suppressed DID page, then requires values for manifest casillas that are formula outputs or schema-required. Optional operator inputs may remain blank. It also rechecks record ordering and duplicate order values, and compares manifest casilla numbers/segmentos against registry-projected metadata rather than trusting the manifest copy. DID-page predicate (`src/cadrumo/application/filing/export_parity.py`) Representable casillas (`src/cadrumo/application/filing/export_parity.py`) Completeness and structure gate (`src/cadrumo/application/filing/export_parity.py`)

Rate-specific boxes are checked separately against their declared total for any export format. The refusal names each shortfall and relies on the same registry partition calculation used for the calculate-path advisory. XML dictionary files do not use the fixed-width blank-slot completeness gate because absent optional elements are an allowed representation; the shared arithmetic consistency gate still runs. The XML auxiliary-header check refuses absent language/version values before treating an artifact as ready. Rate-box parity (`src/cadrumo/application/filing/export_parity.py`) XML auxiliary fields (`src/cadrumo/application/filing/export_parity.py`)

The DID predicate is shared between rendering and parity derivation: it includes dispositions that need an account and the independent Modelo 303 Nota 3 case (rectificativa, semantically present casilla 111 including zero, and KEEP election). This protects the debit-account case as well as refunds. In normal export the disposition and election come from typed producer facts; the fallback for an invalid disposition in this helper treats it as not requiring an account, so confirm all production call paths always provide the validated disposition producer. DID suppression rule (`src/cadrumo/application/filing/export_parity.py`)

## Filing producer projection

`filing_producer_values` maps one immutable typed producer snapshot into the closed filing-producer vocabulary. Shared fields include presenter/taxpayer identity, contact person, disposition, amendment facts, selected refund or charge account, prior-domiciliation election, and period-specific IVA facts. Model-specific projections cover M200, M202, M210, M222, M296, and M353 profile fields. An exhaustive ownership check ensures the shared projection produces exactly the keys assigned to that owner. Wrong-model profile types yield `None` in model-specific projectors so unrelated filings can use the common resolver; the target model’s own snapshot validation must decide whether missing required facts can proceed. Complete producer projection (`src/cadrumo/application/filing/export_producer.py`) Account projection (`src/cadrumo/application/filing/export_producer.py`)

M303 lexical projection separates period facts from IVA profile facts, represents boolean design codes consistently, and gates the annual-volume/exonerado-390 answers to the final filing period. Foral territory overrides set national-regime fields and suppress inapplicable insolvency/exonerado facts as explicit values. These helpers render typed model/profile state; they do not independently validate the truth of taxpayer elections or legal classification. M303 profile values (`src/cadrumo/application/filing/export_producer.py`) M303 period values (`src/cadrumo/application/filing/export_producer.py`)

## Read-back verification and local history

Export receipts carry draft/model/period, format, path, byte size, file digest, timestamp, and casilla provenance. The receipt checker recomputes the on-disk hash and extent. `verify_export` requires the current schema version, parses the selected layout, and compares parser-covered casilla wire values against the draft; XML verification also compares expected root identity fields. Its result reports unchecked casillas separately. A `MATCH` therefore means all checked values and expected root fields match, not that every draft value is represented by the file; fixed-width completeness is enforced by the separate pre-write gate. Verification entry point (`src/cadrumo/application/filing/export_verification.py`) Casilla comparison (`src/cadrumo/application/filing/export_verification.py`) XML comparison (`src/cadrumo/application/filing/export_verification.py`)

Filing history is a bucket-bound repository facade over an outer persistence capability, marked audit sensitivity and schema version 1. `ModeloHistory` validates that entries agree with their parent modelo, while entries carry period, submission timestamp, and a bounded status string. This is a lightweight local history view; richer current/superseded calculation filing authority remains elsewhere. The application contract does not itself impose uniqueness or ordering across history periods, so those properties, if needed, belong to producer or storage admission. History records (`src/cadrumo/application/filing/history_models.py`) Repository capability (`src/cadrumo/application/filing/history_ports.py`) Repository facade (`src/cadrumo/application/filing/history_repository.py`)

## Implementation assessment

The strongest controls are the exact snapshot/layout/identity binding for envelopes, deterministic byte derivation, disposition-aware required-casilla accounting, registry-backed metadata parity, shared rate-box arithmetic checks, typed producer ownership, parser-based read-back comparison, and explicit distinction between verified values and unchecked casillas. Scoped follow-ups are confirming disposition validation at every DID predicate call, confirming target-model validators refuse missing model-specific producer data, and preserving the distinction between a parser-level `MATCH` and a complete pre-write parity result. No runtime or external legal validation was performed.

## Complete assigned-file coverage

- export_envelope.py (354 lines) (`src/cadrumo/application/filing/export_envelope.py`)
- export_parity.py (768 lines) (`src/cadrumo/application/filing/export_parity.py`)
- export_producer.py (1,208 lines) (`src/cadrumo/application/filing/export_producer.py`)
- export_verification.py (536 lines) (`src/cadrumo/application/filing/export_verification.py`)
- history_models.py (71 lines) (`src/cadrumo/application/filing/history_models.py`)
- history_ports.py (79 lines) (`src/cadrumo/application/filing/history_ports.py`)
- history_repository.py (92 lines) (`src/cadrumo/application/filing/history_repository.py`)
<!-- /preserved:article -->
