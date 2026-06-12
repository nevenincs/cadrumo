---
tags:
  - '#audit'
  - '#llm-ledger-classification'
date: '2026-06-13'
related:
  - "[[2026-06-04-llm-ledger-classification-adr]]"
  - "[[2026-06-04-llm-ledger-classification-plan]]"
---



# `llm-ledger-classification` audit: `Saturation pipeline: peer review (PASS) + persona test findings`

## Scope

Verify the stage-2 rich-metadata saturation pipeline against the
`2026-06-04-llm-ledger-classification-adr` to the goal bar: robust,
peer-reviewed, agent-persona-tested, verified functional. Two activities: an
adversarial code review focused on the number-grounding boundary, and a naive
no-context persona attempting to saturate a transaction's tax fields using only
the docs. Functional baseline confirmed first: 43 saturation tests pass across
`domain.iva`, `domain.transactions`, `application.ledger`, and the CLI, and a
direct check confirms accuracy (`resolve_category_rate(DOMESTIC_GENERAL_21)` ->
0.21 from the registry; `split_gross_at_rate(121.00, 0.21)` -> 100.00 + 21.00).

## Findings

### F1 (PASS) The number-grounding boundary is structurally enforced

Peer review verdict: PASS, no revision required. The LLM response schema uses
`extra="forbid"` and declares no numeric tax fields, so a model that emits a
`iva_rate`/`taxable_base`/`iva_amount` key is rejected at parse time (proven by
a real parametrized validation test) — the ADR's "structurally impossible"
mandate is met, not merely prompted. The rate is registry-looked-up and
year-scoped (`lookup_rate`, `rates.toml`, LIVA art. 90/91); the base/IVA are a
rounding-stable inverse split (`round_to_cents`, ROUND_HALF_UP, base quantised
first so `base + iva == gross`); the `gross == base + iva` invariant gates
persistence to the cent and skips the unset-substrate common case; the
hallucination guard treats `iva_category` exactly as `classification`;
provenance cleanly separates `llm:` / `derived:` / `manual`; non-derivable
categories surface a grounded operator-facing reason rather than a guess.

### F2 (MEDIUM, code) Saturation derivation is unreachable operator-initiated

The naive persona reached an applied AI classification (BUSINESS + expense
category, `llm:codex` provenance) and understood that the model never invents a
number — but never saw the euro substrate derived. Two causes: (a) the model
(`codex`) returned `iva_category = unknown` for an ordinary domestic software
subscription, so nothing was derivable; and (b) there is no operator-initiated
derivation — `--saturate` is hard-locked to `--llm` (it refuses with
`saturate_requires_llm` otherwise), and a manual `classify --iva-category
domestic_general_21` sets the category but does NOT derive the base/IVA. So
when the model declines, the operator can only complete the tax fields by hand,
even though the grounded `_derive_iva_substrate` primitive exists and could
derive them from an operator-chosen category. The pipeline is functionally
correct, but the feature is not reliably USABLE for the common case.

### F3 (MEDIUM, test) Self-assessed invariant branch has no direct test

The reverse-charge / import branch of `_enforce_gross_equals_base_plus_iva`
(`taxable_base == gross`, IVA self-assessed not paid in cash) is unreachable
via the saturate path (those categories are non-derivable) but reachable via a
manual classify; it has no direct accept/reject unit test.

### F4 (LOW, docs) Persona doc gaps

The persona could not anticipate the `unknown` outcome (the docs warn about
intra-community/reverse-charge notes, not about the model simply declining on
an ordinary purchase), did not learn that manual `--iva-category` alone does
not derive numbers, and met two undocumented messages: the provider error
`no JSON object in LLM output` and a step-one
`The passphrase does not unwrap the master key` (a stale-key install state with
no troubleshooting heading).

### F5 (LOW, docs) `split_gross_at_rate` docstring says "signed"

Every production caller pre-abs's the gross; the primitive's docstring claims a
signed value is split as given — accurate in isolation, slightly divergent from
usage.

## Recommendations

- **F2 (top follow-up):** add an operator-initiated derivation — allow
  `classify <id> --iva-category <derivable> --saturate` WITHOUT `--llm` to call
  `_derive_iva_substrate` and persist the derived `iva_rate`/`taxable_base`/
  `iva_amount` with `derived:` provenance, reusing the manual write. Must only
  touch the IVA substrate (not the business classification or its provenance),
  must respect the BUSINESS/MIXED coupling (refuse or no-op for non-business
  rows), and must refuse instructively on a non-derivable category. This is the
  change that makes "saturate accurately" reliably usable.
- **F3:** add a focused accept/reject unit pair for the self-assessed branch.
- **F4:** document the `unknown` outcome and what to do; clarify manual
  `--iva-category` does not derive (today) while `--saturate` does; add the two
  error messages to the setup/troubleshooting pages.
- **F5:** tighten the docstring to note production always passes an absolute
  magnitude.

F1 confirms the feature is robust and grounded; F2 is the one substantive gap
to closing the operator experience and is tracked for the next increment.

## Resolution

### F2 (CLOSED) Operator-initiated derivation wired

`derive_operator_iva_substrate` (`application/ledger/_llm_classification.py`)
now lets an operator pick the IVA category and have the system derive the
base / rate / amount from the registry — the same grounded
`_derive_iva_substrate` path the LLM saturate uses, reached without `--llm`.
`aeat app ledger classify <id> --iva-category <derivable> --saturate` (no
`--llm`) derives and persists through the existing manual write, stamped with a
new `derived:iva-category` provenance. The derivation only touches the IVA
substrate (the business classification and its provenance are untouched), is
guarded to BUSINESS/MIXED rows (refuses a non-business row instructively), and
refuses a non-derivable category with the grounded reason rather than guessing.
The `classified_by` contract (`domain/transactions/_models.py`
`_validate_classified_by_shape`) gained a `derived:<basis>` shape so a
registry-derived value is auditable as distinct from a hand-typed `manual`
value and an `llm:<model>` value. Real-behavior coverage: operator-derive
persistence + provenance + non-derivable + non-business-refusal + zero-rate at
the application layer (`test_llm_saturation.py`), the reachable CLI route end to
end (`test_ledger_llm_saturate.py`), and the extended provenance whitelist
(`test_models.py`). The `--saturate`-without-`--llm` refusal was reworded across
all four locale catalogues to point at `--iva-category` or `--llm`, and
`docs/how-to/classify-with-llm.md` documents the derive-yourself path and the
`unknown` outcome (part of F4).

### F3 / F4 / F5 (open)

F3 (self-assessed-branch unit pair), the remaining F4 doc items (the two
undocumented provider/passphrase error messages in setup/troubleshooting), and
F5 (the `split_gross_at_rate` docstring) remain tracked follow-ups for a
subsequent increment.

## Codification candidates

None new. F1 confirms the team is already following the
`llm-selects-system-derives-tax-numbers` candidate authored in the stage-2 ADR
(an LLM selects a registry-grounded category but never emits a tax number;
rates are looked up and numbers derived with `round_to_cents`; a
`gross == base + iva` invariant guards the triple). The successful structural
enforcement is evidence the candidate is the right rule; promote it from the
ADR rather than restating it here.


