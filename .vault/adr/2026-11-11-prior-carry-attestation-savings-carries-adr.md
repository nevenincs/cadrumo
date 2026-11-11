---
tags:
  - '#adr'
  - '#prior-carry-attestation'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:4381278c190805c702efb6139728dffd04014729eac999c0a349c2270b977dea'
related:
  - "[[2026-11-08-prior-carry-attestation-adr]]"
  - '[[2026-11-08-prior-carry-attestation-reference]]'
---

# `prior-carry-attestation` adr: `negative savings balances pending from earlier ejercicios` | (**status:** `deprecated`)

Retired 2026-11-12: accepted by CADRUMO-PRIME at 00:51 with one condition and applied to `2026-11-08-prior-carry-attestation-adr` as its amendment of 2026-11-12, which is the authoritative text. This proposal is kept only as the drafting record.

## Problem Statement

A Modelo 100 compensates negative savings balances still pending from the four previous ejercicios (LIRPF art. 49.1.a and 49.1.b, `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:838-849`). Anexo C.3 holds them in two sections: ganancias y pérdidas patrimoniales (opening rows 1259, 1261, 1264, 1267) and rendimientos del capital mobiliario (opening rows 1272, 1274, 1277, 1280), with identical rows and order in every bundled dictionary (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/*-100-diccionario-*.properties`, fields C2PPAPEM4 to C2RCPFEM0). Today these rows, their applied and carry-forward rows, and the applied boxes 0439-0455 are free operator inputs. No earlier return feeds them, a filer with nothing pending cannot say so, and a filer whose earlier return is in the application must retype it. This is the gap the accepted record closed for the general bases (1380-1388), in a second place.

## Considerations

- Unknown, not zero: a pending balance exists only when an earlier ejercicio left one, so with no earlier return it is unknown, never zero. That is the accepted record's ground, unchanged.
- Two kinds: art. 49.1.a and 49.1.b and the form keep them apart, and a filer can hold one without the other, so one statement for both would assert a figure for a section the filer may have entered.
- The accepted record anticipates the extension: another earlier-filing carry takes the action through a new registry family and its served words (its Consequences). Schema enforcement (`src/cadrumo/domain/calculations/registry/schema.py:296-317`) already admits any decimal `previous_filing` binding.
- Fase 2 of the manual (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:39522-39582`): each kind's pending balances first offset the same kind's positive balance of the year, after the current-year cross offset; what remains then offsets the other kind's remaining positive balance within 25 per cent of it, jointly with the current-year cross offset. The worked example (`:39608-39692`, savings base 200) is the oracle.
- Art. 49.2: the maximum amount each year allows, and no compensation outside the four-year window (manual `:39519-39521`, `:39560-39561`). The applied amounts are fixed, not chosen.
- Open grounding item: the order among origin years inside a step is the same unstated order the general-base rows rest on (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/casillas/0001-declarations.toml:1695`). It needs an official citation before filing grade.
- Savings-base total: the registry's 0460 adds a +0041 term the official BIAHOH expression lacks (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/formulas/0001-declarations.toml:1976-2002` against the 2025 dictionary line 784 and the 2024 one line 758), and 0429/0430 have no source, so the 25 per cent cap in 0446 is always zero. Slice 6a corrects that under art. 49.1.a in the same train; it is a registry correction to the official design, not part of this decision.

## Considered options

- Extend the accepted record by two families (chosen): reuses intent, operator layer, admission, form, field origin, disagreement finding and stated-value path unchanged.
- One family for both kinds: rejected, it would state absence for a section the filer may hold.
- Leave the rows as free inputs: rejected, the return then reads an unknown as zero or forces retyping, which the accepted record refuses for the general bases.
- A new, separate decision record: rejected, there is no new intent, layer, schema or protocol; only the closed family set and the record's scope change.

## Constraints

- The closed family set gains `renta_negative_savings_capital_income_pending` (art. 49.1.a) and `renta_negative_savings_gains_losses_pending` (art. 49.1.b); the record's scope widens from four carries to these twelve.
- Each opening row is bound to the previous return's row one origin year newer, with `filing_year_offset` -1, declared once in the edition that declares the general-base carries; later editions inherit and no year is written anywhere.
- No applied amount is chosen by the operator; each is fixed by the maximum the year allows.
- The order among origin years stays calculation grade until an official text states it.

## Implementation

We will enrol the two families and their eight earlier-filing bindings, compute the applied and carry-forward rows, and serve the statement per family.

- Bindings: gains and losses 1263, 1266, 1269 to 1259, 1261, 1264, and generated balance 1270 to 1267; capital mobiliario 1276, 1279, 1282 to 1272, 1274, 1277, and 1283 to 1280 (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml`, beside the general-base carries at :1083-1115).
- Absent upstream return: state nothing pending (`attest_no_amount`, one action per family) or state the figure (`attest_prior_value`, unchanged under `2026-06-05-cross-period-filing-clean-state-adr` as amended 2026-11-11).
- Step 1 working figures (internal): the capital-mobiliario positive balance after the current-year gains offset, 0429 - 0446, and the gains positive balance after the current-year capital-mobiliario offset, 0424 - 0436. Each origin row's maximum is the lesser of its stock and what the rows before it leave; these fix 0449-0452 and 0439-0442.
- Step 2 working figures: each kind's remaining capacity is the lesser of what step 1 leaves of the other kind's positive balance and 25 per cent of that balance minus the current-year cross offset (0436 or 0446); these fix 0443, 0444, 0445, 0447 and 0453, 0454, 0455, 0448.
- Gates: each applied box takes the two blocking gates the general-base rows use, `positive_application_le_present_stock` and `application_equals_present_maximum`.
- Cascade: each Anexo C.3 applied row sums its two boxes (for example 1260 = 0439 + 0453 and 1273 = 0449 + 0443); each carry-forward row is its opening row minus its applied row; the fourth-year-back row lapses; 1270 and 1283 already compute this year's generated balance, so a return calculated in the application feeds the next one.
- Surfaces: refusal, statement, effect and origin words are served per family; the refusal message map in `src/cadrumo/application/modelo/work_missing_input.py:134-138` gains the import-time completeness check the form maps have; `attest-prior-carries` takes a `--family` option; the operation contract manifest is regenerated and the window's type regeneration is recorded as native debt (the desktop is frozen).
- Evidence: real resolvers and stores at every Modelo 100 year the envelope admits; the manual's worked example as oracle; a two-year cascade; a captured earlier return contradicting an attested zero raises `precedence_tier_divergence`.

## Rationale

The accepted record already holds the whole mechanism and names this extension as its path. The only change is two closed-set members and their bindings, which keeps one mechanism for every earlier-filing carry instead of a second one for savings.

## Consequences

- A saver can complete the savings base with or without an earlier return, and every statement of absence stays distinct from a typed zero.
- Revisions stored before the amendment keep their identity. An earlier return calculated before the carry-forward rows were computed lacks them, so the next year refuses with the unobserved-filing message until it is recalculated or the figure is stated.
- The order among origin years stays an open grounding item, limiting these rows to calculation grade until it is cited.
- The general-base gains carries (Anexo C 1246-1257, art. 48) remain outside this record and take the statement only through their own family.
