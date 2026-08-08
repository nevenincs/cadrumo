---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:1d1ff1c91a3a188a44a8e763150414ceea58eb72fc124f4523215bf42ec24a59'
step_id: 'S18'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Declare a treatment for the seventeen carries that have none, because an undeclared treatment cannot later be cited as authority for having consumed the value. Fifteen previous_filing bindings and both iva_compensation_annual_partition bindings are governed by no dependency classification at all, spanning Modelo 100 negative-base carry, Modelo 130 prior pagos and negative results, Modelo 131 negative results across four revisions, Modelo 353 prior Modelo 322 figures, Modelo 720 prior-year valuation baselines and Modelo 390's two compensacion partition slots. Each declaration is grounded in that row's own provisions and never by analogy to a sibling modelo, since AEAT surfaces do not transfer between modelos and a Modelo 720 valuation baseline and a Modelo 130 negative result are not the same kind of carry. Gate: every one of the seventeen carries a declared treatment with its own legal refs and source refs resolving in the legal catalogue, no two are justified by the same transferred rationale, and the registry loads clean

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`

## Description

- Treated this as investigate-first, because a treatment declaration states what a filed figure is FOR, which is a tax judgement rather than a classification convenience.
- Enumerated all seventeen undeclared carries with the provisions each one already cites, from the loaded authority.
- Judged decidability per carry against its OWN cited provisions, never from a sibling modelo's rationale.
- Declared nothing. The output is an operator-gated list.

## Outcome

NO TREATMENT WAS DECLARED. The row asked for a declared treatment where none exists. Investigating first established that thirteen of the seventeen are decidable from provisions already in the legal catalogue, three need human tax review and cannot be decided from what they cite, and one must not be decided at all yet because its MECHANISM is unsettled. Declaring the thirteen is still an operator act rather than an agent one, for the reason the grounding discipline gives: an agent-authored legal judgement must not be stamped as reviewed under the operator's name.

DECIDABLE FROM CITED PROVISIONS, THIRTEEN.

Modelo 100 base liquidable negativa general anterior, two carries on the 2024 and 2025 revisions, citing LIRPF art. 50. Art. 50.3 governs compensación of prior negative general bases: the prior figure is applied against the current base subject to a limit. That is a figure settling into the current liquidation. Corroborated inside the registry rather than only by reading: the 2025 revision already carries BLOCKING predicates asserting the applied compensación does not exceed the prior stock, which only makes sense if the prior figure is an applied amount.

Modelo 130, two of its three carries, citing RIRPF art. 110 with art. 95. Art. 110 computes the pago fraccionado by deducting the year's prior pagos fraccionados and compensating prior negative results. Both are applied amounts in the current instalment.

Modelo 131 resultados negativos anteriores, four carries across the 2019-2023, 2024, 2025 and 2026 revisions, each citing RIRPF art. 110 with art. 95. Same instalment-compensation structure, and each row cites the provision itself rather than inheriting Modelo 130's, so this is four per-row groundings rather than one generalised across modelos.

Modelo 390's two iva_compensation_annual_partition slots, citing LIVA arts. 99, 115 and 116 with RIVA 71, 29 and 30. These establish that a pending compensación is carried and applied, and art. 116 governs the compensación-versus-devolución election. The two slots partition an amount that is already being applied, so the treatment follows. These are the easier pair, and the aggregation taxonomy already assigns the mechanism for this channel to the IVA wallet decision, so no mechanism question is open alongside the treatment one.

Modelo 720's three prior-year valuation baselines, citing Ley 58/2003 DA 18 with RD 1065/2007 arts. 42-bis, 42-ter and 54-bis. These establish an INFORMATIVE obligation. Modelo 720 determines no cuota and settles nothing, and the prior-year baseline exists to test whether the re-declaration threshold is met, so the prior figure is a fact compared against rather than a figure that settles. This is the one group whose decidable answer is factual_evidence rather than settlement, which is worth noting because a reader skimming for a pattern would otherwise assume the undeclared set is uniform.

NEEDS HUMAN TAX REVIEW, THREE, AND THE CITED REFS ARE INSUFFICIENT RATHER THAN MERELY THIN. Modelo 353's three carries read prior Modelo 322 cuota devengada, cuota deducible and resultado, citing LIVA arts. 88 and 92 with RIVA 71. Those are the substantive repercusión and deducción rules and the liquidación plazo, none of which decides whether an individual entity's prior figure SETTLES into the group return or is EVIDENCE the group reconciles against. That question belongs to the régimen especial del grupo de entidades, and none of LIVA art. 163 quinquies, 163 sexies or 163 nonies is declared in the legal catalogue at all. So deciding these three requires new legal-catalogue entries with corpus grounding, which is outside a classification row by construction, and the finding is not only that a human must decide but that the material to decide with is absent.

MUST NOT BE DECIDED YET, ONE. Modelo 130's previous_year_economic_activity_net_income reads Modelo 100 and is the cross-modelo carry whose mechanism occupies no row of the aggregation taxonomy. Its own row owns bringing it onto a canonical mechanism. Declaring what its value is FOR while what produces it is undecided would fix a treatment onto a channel that may be re-expressed as a relation, so it is deferred rather than counted as decidable.

## Verification

    uv run --no-sync python -c "<join over the loaded authority>"
    undeclared carries: 17

Seventeen, matching the count the ruling recorded, with each carry's binding id, source modelo and own legal refs printed individually rather than summarised, so each judgement above is checkable against the row it was made for.

    catalogue coverage probe
    ley-37-1992:art-163-quinquies   absent
    ley-37-1992:art-163-sexies      absent
    ley-37-1992:art-163-nonies      absent
    ley-58-2003:da-18               declared
    rd-439-2007:art-110             declared
    ley-35-2006:art-50              declared

That probe is what turns the Modelo 353 finding from an opinion into a measurement: the provisions that would decide those three are not in the catalogue, so no amount of reading the cited refs could have decided them.

No pytest lane was run. This step changed no production code, no registry data and no test, because its output is a list and a decision boundary rather than a declaration.

## Notes

AN UNDECLARED TREATMENT CANNOT BE READ AS ANY PARTICULAR ONE, AND THIS ROW IS THE ONLY SANCTIONED WAY FOR ONE TO BECOME DECLARED. The field defaults to the empty string at the resolver join, so anything that begins treating empty as a default has bypassed this row rather than satisfied it. That is stated here because the tempting shape is an inequality-shaped gate: a check written against the settlement value rather than for a declared value sweeps all seventeen into the other class silently.

WHAT MAKES THIRTEEN DECIDABLE IS NOT THAT I DECIDED THEM. The claim is narrower: each of the thirteen cites at least one provision that itself states whether the prior figure is applied or compared, so an operator can ratify or refuse the reading without commissioning new legal research. The three Modelo 353 carries fail exactly that test. Nothing here should be read as a ratified treatment, and the reading offered for each group is an agent reading presented for review.

NO ANALOGY WAS USED, and one case shows why the discipline matters. Modelo 131's four carries and Modelo 130's negative-results carry share a provision, so an analogy would have looked harmless. But Modelo 720's baselines sit in the same undeclared set and resolve the OTHER way, to factual_evidence, because Modelo 720 settles nothing at all. Had the set been treated as uniform on the strength of the majority, three informative-obligation carries would have been declared as settlement figures.
