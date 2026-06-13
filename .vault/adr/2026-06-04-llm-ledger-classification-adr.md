---
tags:
  - '#adr'
  - '#llm-ledger-classification'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - "[[2026-06-03-llm-ledger-classification-adr]]"
  - "[[2026-06-03-llm-ledger-classification-research]]"
---



# `llm-ledger-classification` adr: `Saturate transactions with grounded rich tax metadata via LLM (stage 2)` | (**status:** `accepted`)

## Problem Statement

The stage-1 MVP wired the LLM classifier into an operator suggest/apply/
override/reject loop, but it sets only the non-regulated dimensions
(business/personal and expense category). The operator still enters the rich
tax substrate — IVA category, IVA rate, taxable base, IVA amount — entirely by
hand, which is the heaviest part of the work. This ADR decides how to saturate
a transaction with that rich metadata ACCURATELY, leveraging the LLM where
judgement is appropriate while keeping every regulated number grounded and
derived rather than guessed.

## Considerations

- The grounding investigation established a clean separation: the LLM can
  reliably SELECT a category from a closed, registry-grounded allow-list
  (expense `SpendingCategory`, 41 members; `IvaCategory`, 17 members), but it
  must NOT originate a regulated number.
- The IVA rate is authoritative data, not a judgement: `domain.iva`'s
  `lookup_rate(member_state, kind, on_date)` returns the registry rate
  (`rates.toml`, Spain general 21 / reduced 10 / super-reduced 4 / zero 0,
  grounded in LIVA art. 90/91, year-scoped).
- Taxable base and IVA amount are pure arithmetic: an inverse split of the
  gross at the looked-up rate (`base = gross / (1 + rate)`,
  `iva = gross - base`), quantised with the canonical `round_to_cents`
  (ROUND_HALF_UP, the AEAT-mandated rounding).
- The operator must keep final authority: review the full saturated suggestion
  and accept it, override any field manually, or reject it — exactly the
  stage-1 contract, extended to the richer field set.
- Provenance must distinguish three origins: `llm:<model>` (selected by the
  model), `derived:` (computed by the system), and manual.

## Constraints

- **Regulated numbers are derived, never LLM-emitted.** The LLM response may
  carry `iva_category` (a selection) but MUST NOT carry `iva_rate`,
  `taxable_base`, or `iva_amount`; those are computed from the looked-up rate
  and the gross. The hallucination guard (`parse_response` allow-list) must
  reject any out-of-allow-list `iva_category` just as it does `classification`
  and `category` today.
- **A consistency invariant is mandatory.** A saturated triple must satisfy
  `gross == taxable_base + iva_amount` (to the cent). The `Transaction` model
  has no such validator today; one must be added so a derived or manual triple
  cannot drift.
- **Missing primitives must be authored, grounded.** There is no
  `IvaCategory -> rate-kind -> lookup_rate` resolver (only a partial
  rate-kind→domestic-category map and a rate→kind reverse map), and the inverse
  split exists only in a test. Both must be promoted into `domain.iva` using
  the registry rate authority and `core.money.round_to_cents`. Non-domestic
  categories (intra-community, export, exempt, recargo, no-sujeta) that carry
  no simple positive rate must be handled explicitly (zero/exempt → zero IVA;
  reverse-charge and recargo are out of scope for derivation here and left to
  the operator).
- **IRPF category stays operator-only this stage.** `irpf_category` is
  unbounded free text with no closed vocabulary or legal grounding, so it
  cannot be LLM-selected accurately. Authoring an `IrpfCategory` enum + its
  grounding is deferred to its own decision; the LLM does not touch IRPF here.
- **Rate legal-grounding hardening is noted, not blocking.** The `rates.toml`
  references are reference strings, not the structured `corpus_ref`-backed
  chain the registry-legal-grounding rule mandates; hardening them is a
  follow-up. This stage consumes the existing authority and records its
  provenance.
- **Parent stability.** Builds on stage-1's stable suggest/apply plumbing, the
  manual-command write path (which already persists the regulated fields with
  their validators), and the stable `domain.iva` rate authority.

## Implementation

The LLM response schema gains optional `iva_category` (and, where the model
offers it, a proposed `business_pct` for MIXED), selected from a grounded
allow-list built the same way the expense-category choices are — from the
`IvaRegulation` catalogue labels — and guarded by `parse_response`. A new
grounded `domain.iva` resolver maps a selected `IvaCategory` to its rate-kind
and looks the rate up via `lookup_rate`; a promoted inverse-split utility then
derives `taxable_base` and `iva_amount` from the transaction gross at that
rate, quantised with `round_to_cents`. Zero/exempt categories derive a zero
IVA; categories with no derivable rate are surfaced for manual completion
rather than guessed.

The application saturate path composes these: it runs the classifier, looks up
the rate for the selected IVA category, derives the base and amount, and
returns a full suggestion carrying each field with its origin
(`llm:` / `derived:`). On apply it persists through the manual-command write
(not the classification-only `set_classification`), so the regulated fields
land with their existing validators plus the new
`gross == base + iva` invariant. The operator surface keeps the stage-1 verbs:
suggest previews the saturated set, `--apply` persists it, and any manual
`classify` flag overrides the corresponding field and re-stamps manual
provenance. Rejecting remains "do not apply".

## Rationale

Splitting selection (LLM, judgement, allow-list-guarded) from computation
(system, arithmetic, registry-grounded) is what makes saturation both rich and
accurate: the model does the hard part it is good at (which category fits this
transaction) while every euro figure traces to the registry rate and a
deterministic split, never to a model's guess. This satisfies the
calculation-grounding mandate, keeps the operator in final control, and reuses
the validated manual write path so the regulated fields are persisted exactly
as a hand-entered filing would be.

## Consequences

- **Gain:** a transaction can be saturated — business/personal, expense
  category, IVA category, IVA rate, taxable base, IVA amount — from one
  reviewed LLM suggestion, with the numbers grounded and the model's role
  bounded to selection.
- **Gain:** the new `IvaCategory→rate` resolver, the inverse-split utility, and
  the `gross == base + iva` invariant are reusable well beyond the LLM path
  (manual classify, imports, aggregation all benefit).
- **Honest limitation:** IRPF category and the reverse-charge/recargo IVA
  categories are not saturated by the LLM this stage; the operator completes
  them. Accuracy of the rate depends on the registry being current for the
  filing year.
- **Pitfall to avoid:** letting the model emit a number. The schema must make
  that structurally impossible (no numeric tax fields on the LLM response), not
  merely discouraged.
- **Dependency surfaced:** the rate legal_refs hardening (to corpus-backed
  citations) becomes more pressing once derived numbers flow toward a filing.

## Codification candidates

- **Rule slug:** `llm-selects-system-derives-tax-numbers`.
  **Rule:** An LLM may select a regulated tax category only from a closed,
  registry-grounded allow-list with a hallucination guard; it must never emit a
  tax rate, base, or amount — those are looked up from the registry and derived
  arithmetically with `round_to_cents`, recorded with `derived:` provenance,
  and a saturated triple must satisfy `gross == base + iva` to the cent.
