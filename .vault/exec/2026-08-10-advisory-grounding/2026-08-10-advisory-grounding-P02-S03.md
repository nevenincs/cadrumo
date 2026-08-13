---
tags:
  - '#exec'
  - '#advisory-grounding'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:b6bcca7aaa24da46f4a24ba6c04d0fbf5929d505ecce9cadd05d8752389b2317'
step_id: 'S03'
related:
  - "[[2026-08-10-advisory-grounding-plan]]"
---

# HARD GATE, read before any conversion. Do not convert the art-81 advisory sites until the ley-35-2006 art-81 catalogue entry is repointed off the two-vintage excerpt, or exclude them explicitly from every conversion row. Record in this row which of the two dispositions was taken

## Scope

- `src/cadrumo/_data/registry/aeat/legal/irpf.toml`
- `src/cadrumo/application/modelo/`

## Description

- Established which of the two dispositions was available by checking the state of the repoint rather than assuming it: the sibling campaign's candidate diff is prepared and waiting on an operator stamp, so the entry still cites the two-vintage excerpt today.
- Enumerated the art-81 advisory sites by parsing the advisory module rather than by grepping a name, so the exclusion names every site that asserts the article and not merely the ones with `guarderia` in their identifier.
- Took the SECOND disposition and wrote the exclusion into the conversion row itself through the owning plan verb, so it binds the row that would otherwise convert them.
- Verified against the live BOE text in force what the excerpt does and does not contain, which surfaced a finding beyond this row's question. Recorded below, not acted on.

## Outcome

**Disposition taken: the second one. The art-81 sites are excluded explicitly from the conversion row, and the repoint was not waited for.**

The first disposition was unavailable rather than declined. The catalogue entry carries `review_status = "reviewed"` with `reviewed_by = "operator"` and the type admits no draft state, so an agent cannot repoint it. The candidate diff is prepared in the sibling campaign and sits behind an operator gate, so "convert once repointed" would have meant blocking this row on an act neither this plan nor this agent controls.

### The excluded sites

Four, all in `src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`, each asserting an Art. 81 clause in its message text:

| function | source kind | clause asserted |
| --- | --- | --- |
| `_guarderia_shape_advisory` | `guarderia_spend_needs_monthly_detail` | Art. 81.2 turning-three window, both directions |
| `_segundo_ciclo_month_advisory` | `guarderia_segundo_ciclo_month_undeclared` | Art. 81.2 second-cycle month |
| `_cotizaciones_ceiling_advisory` | `guarderia_cotizaciones_ceiling_unbounded` | the Art. 81 cotizaciones bound |
| `_guarderia_madre_meses_advisory` | `guarderia_madre_meses_undeclared` | Art. 81.2 read with the Art. 81.1 requirement |

The exclusion is now carried in the conversion row's own text, naming all four functions and all four source kinds, with the reason and the condition for re-opening them. It is not recorded only here, because a note in an execution record does not bind the row that does the converting.

### Why converting first would have been worse than leaving the prose

The messages assert the turning-three extension, the second-cycle month and the cotizaciones bound. The entry those sites would resolve against cites the excerpt, and the excerpt does not contain the first two clauses at all. A declared id that resolves to a document lacking the rule reads as corroborated grounding, and the id resolves — the build-time refusal added earlier in this plan checks that an id EXISTS in the catalogue, not that the cited document carries the clause the message states. Prose at least claims nothing.

### A finding this row surfaced and did not act on

Measuring the live text in force to confirm the excerpt's defect produced an observation about the code rather than the citation, and it is recorded because it would otherwise be lost.

In LIRPF art. 81 as in force from 2023-01-01 (norm `BOE-A-2022-22128`), the string `cotizaci` occurs exactly ONCE, in the alta rule of apartado 3: the 30-day cotización period that triggers the 150-euro increment. No cotizaciones ceiling on the guardería increment survives in that text — neither the repealed per-hijo cap `las cotizaciones y cuotas totales a la Seguridad Social`, which the bundled consolidated file and the live text both lack and only the excerpt carries, nor the second-cycle-month limb on the cotizaciones computation quoted by the accepted sibling decision record that governs `_cotizaciones_ceiling_advisory`.

That decision record is `accepted` and grounds the bound in the bundled AEAT renta manuals for 2020 through 2025, which is real authority for the filing years in which the ceiling applied. So the honest statement is narrow and is NOT that the decision is wrong: for filing years governed by the pre-2023 redaction the bound is law, and for the text in force it is not in the article. Whether the advisory and the registry formula behind it are correctly scoped per filing year is a tax review against each M100 revision, and it is neither this row's question nor an agent's call. Flagged, with the sibling campaign's operator gate as its natural home, since that gate already puts the same article in front of the operator.

This is also the exact direction the standing apparatus does not watch. A surviving repealed ceiling caps a deduction below entitlement, so it overpays: valid output, no refusal, and no signal to the taxpayer.

## Notes

**Nothing in the registry or the advisory module was modified by this Step.** The disposition is a plan-row edit plus this record. No catalogue entry was authored, edited or re-stamped, no corpus excerpt was authored, and no advisory site declared a provision.

**Re-opening condition, stated once so it is not lost.** The four sites become convertible when the art-81 entry's repoint lands under an operator stamp. At that point the entry cites the consolidated file, the three clauses the messages assert are present in the cited document, and the conversion row's exclusion should be lifted through the same plan verb that added it.
