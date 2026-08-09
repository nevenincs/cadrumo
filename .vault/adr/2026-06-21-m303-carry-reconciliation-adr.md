---
tags:
  - '#adr'
  - '#m303-carry-reconciliation'
date: '2026-06-21'
modified: '2026-08-09'
body_hash: 'sha256:28bdc7fadf1f477a26410e456a26548d69636bd5c617d5838dc72c25c82297c5'
related:
  - "[[2026-06-21-redeme-company-refund-adr]]"
  - "[[2026-06-21-redeme-company-refund-research]]"
---

# `m303-carry-reconciliation` adr: `Modelo 303 refunded period generates zero carry-forward: disposition feeds compensacion-disponible` | (**status:** `accepted`)

## Problem Statement

The Modelo 303 refund (devolución, Tipo de declaración `D`) election now emits the
refund in the fichero header for a REDEME company's negative period, but the
period's credit is STILL carried forward. The end-of-period available credit
`iva.compensacion-disponible-fin-periodo` is generated unconditionally from the
negative result — `available = casilla 87 (pendiente posterior) + max(0, -casilla
69 (resultado))` — so a refunded period both requests the money back AND carries
the same credit into the next period's casilla 110. The credit is double-counted:
the fichero says "devolución" while the cross-period carry says "compensación".
This is the pitfall the refund ADR flagged. The grounding pass confirmed it is a
real gap reachable through the app's own file-then-recalculate flow.

## Considerations

- The carry is produced by TWO mechanisms, neither disposition-aware: a registry
  FORMULA computes `iva.compensacion-disponible-fin-periodo` on the calculate path
  (the value persisted in `CalculationRevision.observations` and read next period),
  and `derive_303_compensation_available` (`domain/iva_compensation/_carry_forward`)
  recomputes the same quantity on the filed-history path
  (`iva_compensation_state_from_filed_observation`). This duplication touches the
  one-canonical-aggregation-mechanism discipline; the disposition signal must reach
  whichever mechanism is authoritative for the carry the next period reads.
- The disposition (refunded vs carried) is currently determined only at EXPORT time
  (`_apply_refund_election`), from the profile REDEME axis + the eligibility gate.
  It is not a persisted fact, so the calculate/carry path cannot see it.
- For a REDEME taxpayer the refund is DETERMINISTIC (the inscription is the standing
  monthly-refund election), so "refunded" is recomputable from
  `(redeme_enrolled, modelo == 303, result < 0, eligible)` wherever the redeme axis
  is in scope — it need not be an operator choice.
- The 303 registry has NO devolución casilla; the refund is the disposition, not a
  box. So the filed-observation casillas alone cannot recover "was this refunded" —
  the AEAT-pull path would need the justificante Tipo de declaración, a separate
  recovery concern from the app's own local-file path.

## Constraints

- **No double mechanism drift.** Whatever carries the disposition into the carry
  derivation must keep the calculate path and the filed-history path in agreement
  (the pull-equals-calculate discipline); a fix on one mechanism only re-opens the
  drift.
- **Behaviour-preserving default.** The carry derivation's new disposition input
  MUST default to "carried" (the current behaviour), so every existing non-refund
  filing and every carry regression test is unchanged; only a refunded period zeroes
  the generated carry.
- **Grounded, not heuristic, for official data.** The AEAT-pull path must recover
  the disposition from the filed artefact (justificante Tipo de declaración), never
  from the CURRENT profile's REDEME flag applied to a historical filing — a taxpayer
  may not have been REDEME in the pulled year. The local-file path may recompute it
  from the revision's own profile context.
- **Carry-forward correctness is cross-compounding.** A wrong carry injects into
  every later period that folds it in (the carried-observations discipline), so the
  fix needs a multi-persona cross-period regression, not a single-period assertion.

## Implementation

- **Disposition becomes a determined fact at calculate/file time.** Compute the
  M303 negative-result disposition (`devolver` vs `compensar`) once from the profile
  REDEME axis + the eligibility gate at the calculate/file boundary, persist it on
  the revision's observation context, and have BOTH the export (fichero `D`) and the
  carry derivation read the same determined fact — collapsing the export-only
  determination into one shared source.
- **Carry derivation gains a refunded input.** `derive_303_compensation_available`
  and the registry compensación-disponible derivation take a `refunded` signal;
  when refunded, the generated component is zero (`available = posterior` only, which
  for a full monthly refund is also zero), so the refunded period carries nothing.
- **Two paths, one contract.** The local-file path supplies `refunded` from the
  determined disposition; the AEAT-pull path recovers it from the justificante Tipo
  de declaración. A parity regression asserts both paths agree for a shared period.
- **Reconcile with the IVA-wallet decision.** A refunded period must also not be
  read as a prior compensación by the wallet reconciliation (casilla 110); the
  determined disposition feeds that gate so a period is refunded OR compensated,
  never both.

## Rationale

The grounding pass established the gap is real and that its root is a missing fact:
the disposition lives only at export, so the carry cannot honour it. Making the
disposition a determined fact shared by the export and the carry is the minimal
change that keeps the two carry mechanisms in agreement and the common
carry-forward path untouched. Defaulting the carry input to "carried" makes the
change non-regressive; recovering official-data disposition from the justificante
(not the live profile) keeps historical pulls correct. Grounded in RD 1624/1992
art. 30 / Ley 37/1992 art. 116 (a refunded credit is returned, not carried).

## Consequences

- **Gain:** a REDEME company's refunded period stops double-counting its credit; the
  fichero disposition and the cross-period casilla 110 finally agree.
- **Difficulty:** the disposition must be threaded to two carry mechanisms and two
  file paths; the AEAT-pull recovery needs the justificante Tipo de declaración,
  which is a parsing concern beyond the local-file fix.
- **Pitfall:** fixing only the calculate-path formula (or only the history function)
  re-opens pull-vs-calculate drift; the parity regression guards it.
- **Pitfall:** applying the current profile's REDEME flag to a historical pulled
  filing would mis-zero a legitimately-carried prior period; the official path must
  read the filed artefact.

## Codification candidates

- **Rule slug:** `m303-refunded-period-carries-nothing`.
  **Rule:** A Modelo 303 period filed as a refund (Tipo de declaración `D`) MUST
  generate zero `iva.compensacion-disponible-fin-periodo`; the disposition that
  drives the fichero `D` and the disposition that drives the cross-period carry MUST
  be the one determined fact, never computed twice and never allowed to disagree.

## Status

`proposed`. The carry mechanism this ADR decides is a child of the canonical
compensación-carry direction set by the PHASE ADRs (not a central apex doc): the
foundational `live-iva-compensation-wallet-adr` is the carry anchor, and the future
phase-2.3 (fold-in/carry) ADR unifies the carry mechanism. This ADR lands its specific
refunded-period-zeroing mechanics under that one authority.

## Amendment: the observation envelope is the disposition authority

The earlier `refunded` boolean and behaviour-preserving `carried` default are
superseded. They create a second authority and silently invent a disposition when evidence is
missing. `RegistryModeloObservation` remains casilla-only; no header fact or synthetic
disposition casilla is added to it. The canonical persisted unit for disposition-aware carry
is `ObservationEnvelopePayload`, which owns the observation, typed `source_headers`, source
kind and provenance, revision stamp, and one normalized typed disposition projection.

For official AEAT evidence, the projection resolves exactly one
`source_headers[header_key="declaration_type"]`. For a local app filing, the filing boundary
persists its already-determined `ResultDisposition` with provenance. The raw header remains
evidence and the typed disposition is its validated interpretation; a free `refunded` boolean
is never another authority. History, annual partition, and wallet consume the validated
envelope projection, not a bare observation or prior calculation-revision casillas for
disposition-sensitive carry.

There is no carried default. Missing, duplicate or conflicting declaration-type evidence;
invalid or non-M303 codes; sign-incompatible disposition; typed-versus-header disagreement;
incomplete derivation operands; absent canonical available after ingress; and any
available/generated pair inconsistent with the disposition-aware derivation all refuse carry
participation. Legacy envelopes remain readable evidence but are ineligible for carry until
their disposition is grounded. At ingress, available may be synthesized only from a known
disposition and complete supported operands, preserving the accepted
absent-posterior-as-zero rule; the normalized persisted record thereafter carries available
explicitly. A semantic available value never wins over a contradictory generated value.

For dispositions `D`, `V`, and `X`, `generated = 0` and `available = posterior`. `C` carries
the supported result. Other valid dispositions do not fabricate credit. Implementation order
is S05 (shared envelope resolver, canonical ingress derivation, and truthful
`basis="refunded"`), S07 (atomic disposition/available/generated invariant), S06 (envelope
annual-partition reader and defensive validation), then S08 (validated envelope recurrence
feeding the wallet). The wallet remains the sole carry authority; prior calculation revisions
may be checked against its current decision but do not establish the prior filed disposition.

Verification must distinguish identical negative casillas under `C` and `D`, reject every
missing/conflicting/sign-incompatible evidence shape, prove atomic persistence refusal, prove
history and partition reject pair mismatches, keep refunded credit out of M390 boxes 97 and
662 and later M303 periods, and show pull/local-file parity. Exporter-generated payloads are
structural wiring evidence only: no real AEAT refund specimen is currently recorded.

## Amendment: positive payment election is distinct from refund election

`RefundElection` remains the negative-result C/D choice and must not be widened. A sibling
core `PaymentElection` owns the positive-result operator choice with semantic members
`INGRESO`, `DOMICILIACION`, and `CUENTA_CORRIENTE`. One shared fail-closed resolver is the
only authority mapping base result disposition plus the applicable election to final
`ResultDisposition`: positive I may remain I or become U/G, while D/V/X remain refund
dispositions. U/G never change compensation carry. A non-default election incompatible with
the computed sign refuses rather than being ignored.

The typed payment election is threaded through `ModeloExportCommand`, quickfile, filing
action/API, CLI, and every review or verification export wrapper. The misleading CLI
`--disposition` option, which currently carries `RefundElection`, is removed and replaced by
explicit `--refund-election`; `--payment-election` carries the sibling axis. No legacy alias
is retained. G belongs to the canonical type so the contract is not forked later, but remains
capability-gated and refused until its cuenta-corriente-tributaria semantics are officially
grounded. It must not infer or reuse `ChargeAccount`.

`ChargeAccount` is distinct encrypted durable profile data; an election is per-filing
provenance. The export receipt and `MODELO_EXPORTED` event persist the resolved result
disposition and semantic payment election (and the refund election symmetrically where
applicable), but never IBANs, rendered headers, or other account material. S18 remains open
until this public path reaches the existing charge-account U composer and proves a real
end-to-end U export. A separate follow-up Step owns the cross-command contract rather than
silently widening S18.

## Amendment: prior domiciliation action is a separate filing election

The page-3 X/blank marker is a distinct per-filing `PriorDomiciliationElection`, with
semantic values `KEEP` (blank) and `CANCEL_OR_MODIFY` (X). It is not amendment kind,
`PaymentElection`, or the misleading existing `tipo_rectificacion` header. It is legal only
for Modelo 303 rectificativas; X additionally requires authoritative baseline evidence whose
persisted resolved disposition was U. Unsupported modelo/kind, raw or unknown values,
missing baseline-U proof, and an election the selected registry revision cannot represent all
refuse before bytes, receipt, or event. KEEP is the neutral default.

One shared DID predicate governs renderer and parity:
`disposition_requires_bank_account OR (is_m303_rectificativa AND
casilla111_has_content AND prior_domiciliation_election is KEEP)`. Content means semantically
present, not merely non-zero. X disables only the Nota-3-added requirement; it never
suppresses DID independently required by current U or a refund disposition.

The registry layout must split. The current 2023-y-siguientes page-3 snapshot is bounded
through 2025 and retains the 2025 authority (marker offset 406, casilla 111 offset 424). A
2026-y-siguientes snapshot is grounded separately to the 2026 design (marker 440, casilla 111
441, including all adjacent moved page-3 positions). Both revisions use the truthful header
semantic `prior_domiciliation_action`; `tipo_rectificacion` is removed.

The typed election is threaded through export, quickfile, file action/API, CLI, verification
wrappers, receipt/event, and filing observation with safe semantic and baseline provenance,
never IBAN. The Nota-3-only DID uses the existing `RefundAccount`. The statutory 2025 and
2026 forms describe casilla 111 as money credited by bank transfer to the taxpayer's indicated
account; it is a refund destination, not a debit mandate. Current U continues to use
`ChargeAccount`. Missing `RefundAccount` refuses before output or event, and distinct
charge/refund specimens must prove the correct source. Casilla 111 requires a negative
casilla 71, so U is already sign-incompatible whenever Nota 3 applies; that fail-closed
invariant is retained rather than inventing a combined-account precedence rule.
