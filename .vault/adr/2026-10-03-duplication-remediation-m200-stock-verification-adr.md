---
tags:
  - '#adr'
  - '#duplication-remediation'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:0f654138be50e64a017fdf70650a6f3e5b2310d5cf974165032162897d6c9bc2'
related:
  - "[[2026-10-02-duplication-remediation-reference]]"
  - "[[2026-10-02-duplication-remediation-audit]]"
  - "[[2026-06-02-modelo-multiyear-renta-income-adr]]"
  - "[[2026-06-02-modelo-200-base-determination-adr]]"
  - "[[2026-06-24-modelo-200-bin-continuity-adr]]"
  - "[[2026-06-03-m200-internal-casilla-discipline-adr]]"
---

# `duplication-remediation` adr: `Bound positive elective M200 compensation by present opening stock` | (**status:** `accepted`)

## Problem Statement

The S07 public-profile regression found that a positive M200 compensation did not produce the expected stock BLOCKING_RULE when clean prior-filing evidence supplied an explicit zero opening stock. The accepted income-hook decision uses cap_le_when_positive for both the statutory ceiling and opening stock, although that operator deliberately holds when its ceiling is non-positive. The failure and tested generation are retained in 2026-10-02-duplication-remediation-audit; this decision does not claim the current or a future authority generation is fixed.

## Considerations

The 2024 and 2025 AEAT Sociedades manuals distinguish the amount elected for application from pending opening stock and describe applying part or all of the available prior balance. The official source locators and ordinary-case limits are retained in 2026-10-02-duplication-remediation-reference and the S07 proposal evidence. Other modelos intentionally use the existing positive-ceiling operator. Neither source cleanliness nor nonnegative stock is guaranteed by the present numeric DTO alone. Internal computed casillas participate in calculation snapshots and revision identity even when not exported.

## Considered options

- Change cap_le_when_positive globally: rejected because its non-positive-ceiling behavior is an accepted contract for other uses.
- Add implies_nonzero beside the existing stock cap: rejected because negative stock can satisfy nonzero and magnitude remains a separate condition.
- Compute a new internal comparison casilla and use equals: rejected because it adds calculation state and content-address inputs solely to encode a comparison, and cannot itself distinguish missing evidence from lawful zero.
- Add one closed, optional-positive-application stock operator: selected, with reference/type/arity validation through the existing authoring pipeline and no second syntax parser.

## Constraints

The accepted positive_application_le_present_stock([application_id, stock_id]) contract is: omitted or non-positive application holds for this check; positive application requires the stock key to be present in the Decimal value mapping and requires application <= actual stock. Present zero or negative stock therefore cannot support a positive application. This is not independent sign validation and does not establish that a negative form amount is lawful. Missing stock must not be described as verified legal zero; upstream binding/source diagnostics remain independently responsible for evidence and provenance.

Keep 00547 manual/elective, including partial or zero application. Keep the existing statutory-limit predicate and generic cap operator unchanged. Keep the 00671 roll-forward ADVISORY, source-clean gates blocking at their current owner, and the existing finding taxonomy, narrative predicate identifier and locale key. No new casilla, formula, export field, public DTO, profile default or persistence wire format is authorized by this decision. The authored predicate identity changes with its operator; source installation, validated publication and runtime adoption are separate deliverables.

The authorized scoped amendment to 2026-06-02-modelo-multiyear-renta-income-adr is: "00547 remains an optional operator election. The statutory-limit predicate keeps cap_le_when_positive and its existing positive-ceiling semantics. The opening-stock predicate uses positive_application_le_present_stock: omitted or non-positive application holds for this stock check; a positive application requires a present stock value and must not exceed it. Source-clean verification remains independent. This scoped ruling replaces the earlier choice that both guards use cap_le_when_positive and that no new operator is added; the elective and partial-application commitment is preserved."

The authorized dated clarification to 2026-06-02-modelo-200-base-determination-adr is: "Computing the base chain or maximum permitted compensation does not select or populate 00547. It remains the taxpayer's manual/elective amount and may be below the applicable maximum. A verification constraint bounds an election without forcing it to the cap. The separate 00547/00550 condition, including statutory adjustments, remains unresolved by this stock ruling."

Leave the accepted BIN-continuity and internal-casilla-exemption decisions unchanged. Their advisory and exemption scopes do not grant or prohibit this separate stock-operator change. Apply only the authorized scoped amendments to the income and base-determination ADRs, preserving their earlier choice as dated history; do not supersede the entire cross-modelo income ADR.

## Implementation

Select one typed operator in the existing canonical VerificationPredicateOperator/specification/evaluator ownership, using CASILLA_LIST with exactly two numeric casilla references. Authoring must reject wrong arity, unknown references and incompatible operand kinds through its existing validator path. The first Temp proposal's separate CASILLA_PAIR syntax bypassed that dispatch and is rejected; no new grammar family or parser is needed.

Replace only the authored M200 2024 opening-stock predicate and verify inherited 2025 source meaning through the owning source-authoring gates. Keep the existing positive/zero public-profile regression intact. Require independent truth-table boundaries, real generic BLOCKING findings and authoring-gate refusal tests before a validated source result. A changed published authority must be explicitly authorized and pinned before claiming the public workflow defect is corrected at runtime. These implementation details may adapt within the stated constraints.

## Rationale

The selected operator expresses the missing elective-application invariant in one executable owner while preserving accepted cap behavior elsewhere. It distinguishes a present operand from an absent map entry and avoids incidental calculation state. The S07 audit supplies the concrete failure; the current evaluator and source trace explain it. Existing syntax and authoring validators provide a smaller, auditable extension than a new parser, and protective tests must exercise that whole path.

## Consequences

The closed DSL and authored stock-rule identity expand, requiring coordinated source validation and later authority rollout. This decision grants neither publication nor full M200 acceptance. The manuals' separate 00550 condition includes adjustments and remains a recorded neighboring gap; stock enforcement alone cannot resolve it. Special-regime applicability, negative applications, source cleanliness, total detail/roll-forward coherence and other statutory ceilings retain their own evidence and decisions. Reconsider this ruling if the actual source/value channel cannot preserve operand presence or if grounded special-regime behavior conflicts with the intended stock invariant.

## Authorization and acceptance (2026-10-03)

Accepted under the user's explicit instruction, "make the decisision", delegating selection to the session architect after the separate M200 failure investigation and tested candidate had been reported. The accepted commitment is the populated stock-only proposal; the earlier Jev-assisted placement review is reused because its commitment and affected decision set are unchanged. That bounded review and the whole-record income/base/BIN/internal-casilla reading are placement evidence, not independent approval or corpus-wide conflict proof.

The tested implementation handoff is `<operator-home>/AppData/Local/Temp/s07-sol61-high-candidate-20261003T142931Z-ebd90ff4/implementation-review-brief.md` (raw SHA256 `FE1AB1B184C7ED256879182D9BE9E6C8BA46FDD932BE03C23DE08CE418A8E828`), with final eight-file candidate patch SHA256 `72BC83A30B8D3FE1D1537575A64B39068F488DDBE684435652C590D8D7D08D8A`. Temp application/dispatcher evidence supports this choice but does not substitute for compiler-backed source validation or the unchanged public-profile regression against a newly authorized, pinned authority. The retained failed candidate run is not reclassified as a pass.

The same authorization covers the concrete scoped income and base-determination amendments stated above. Existing foreign writer reservations, source-authoring ownership and publication authority remain separate; acceptance releases no shared source path and creates no published authority. Coding continues to belong to Sol 6.1 medium/high under an explicit disjoint write grant; Luna Max remains investigation-only.
