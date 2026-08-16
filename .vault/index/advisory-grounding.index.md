---
generated: true
tags:
  - '#index'
  - '#advisory-grounding'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:5d41a9e5891d66a24cfc749cf2ae2e7cdcc86fc7c421ce3026f345b3d18ab9fc'
related:
  - '[[2026-08-10-advisory-grounding-P01-S01]]'
  - '[[2026-08-10-advisory-grounding-P01-S02]]'
  - '[[2026-08-10-advisory-grounding-P02-S03]]'
  - '[[2026-08-10-advisory-grounding-P02-S04]]'
  - '[[2026-08-10-advisory-grounding-P03-S05]]'
  - '[[2026-08-10-advisory-grounding-P03-S06]]'
  - '[[2026-08-10-advisory-grounding-P03-S07]]'
  - '[[2026-08-10-advisory-grounding-P03-S09]]'
  - '[[2026-08-10-advisory-grounding-P03-S10]]'
  - '[[2026-08-10-advisory-grounding-adr]]'
  - '[[2026-08-10-advisory-grounding-plan]]'
  - '[[2026-08-10-advisory-grounding-reference]]'
---

# `advisory-grounding` feature index

Auto-generated index of all documents tagged with `#advisory-grounding`.

## Documents

### adr

- `2026-08-10-advisory-grounding-adr` - `advisory-grounding` adr: `How a calculation advisory carries its provision` | (**status:** `proposed`)

### exec

- `2026-08-10-advisory-grounding-P01-S01` - Give CalculationSourceDiagnostic a typed place for an advisory to declare the provisions it asserts itself, distinguished on the diagnostic from the casilla-derived path that the one existing correct instance uses. The two are not alternatives and neither replaces the other. Record the subject distinction on the type so a future author copying the casilla-derived instance onto an eligibility-rule advisory is stopped by the type rather than by convention
- `2026-08-10-advisory-grounding-P01-S02` - Refuse at registry build any declared provision id that does not resolve to a legal-catalogue entry. This is the check the prose form could never carry. State a control proving the legitimate population still passes and do not close on the refusal firing. The disconfirming observation: if the control shows a legitimate advisory declaring an id that does not resolve, the catalogue is incomplete for that provision and this row must stop and report rather than relax the refusal
- `2026-08-10-advisory-grounding-P02-S03` - HARD GATE, read before any conversion. Do not convert the art-81 advisory sites until the ley-35-2006 art-81 catalogue entry is repointed off the two-vintage excerpt, or exclude them explicitly from every conversion row. Record in this row which of the two dispositions was taken
- `2026-08-10-advisory-grounding-P02-S04` - Adjudicate per site which catalogue entry each advisory message actually asserts, and declare it. This is a tax review against the provision the message states, never a lookup, and it does not parallelise into a sweep. Where the casilla already carries the exact provision the derivation is correct and should be used. Where the catalogue carries a finer entry the casilla does not reference, declare the finer one and record why the casilla's coarser ref was not used. Do NOT append the finer entry to the casilla legal_refs to make a derivation work, because a casilla's refs describe what establishes that box and an eligibility rule governing one of its inputs is a different subject. EXCLUDED FROM THIS ROW BY THE S03 HARD GATE, and the exclusion is not a deferral of convenience: the four Art. 81 guarderia advisory sites in the minimo-descendientes advisory module are _guarderia_shape_advisory, _segundo_ciclo_month_advisory, _cotizaciones_ceiling_advisory and _guarderia_madre_meses_advisory, carrying source kinds guarderia_spend_needs_monthly_detail, guarderia_segundo_ciclo_month_undeclared, guarderia_cotizaciones_ceiling_unbounded and guarderia_madre_meses_undeclared. Do not declare a provision on any of them. The ley-35-2006 art-81 entry still cites the two-vintage excerpt: the repoint is prepared under the legal-corpus-vintage plan and is waiting on an operator stamp, so declaring these ids now would resolve them against a document that does not contain the clauses the messages assert, which is worse than the prose because the prose claims no corroboration. Re-open them here only once that stamp lands
- `2026-08-10-advisory-grounding-P03-S05` - Thread a registry object into the five modules that hold none, as its own change rather than inside a citation change. The invoice-devengo advisory, the retencion-rate advisory, the invoice source resolver and the prior-payment advisory hold no revision, snapshot or casilla definition anywhere. Every provision they cite has a catalogue entry, so this is threading rather than grounding. The disconfirming observation: if threading a revision into any of these modules would invert a dependency direction the architecture forbids, stop and report rather than route around it, because that would mean the advisory belongs at a different layer
- `2026-08-10-advisory-grounding-P03-S06` - Read the twelve modules that assert no provision in either form and record, per module, whether that silence is proper. Nothing measured so far says they are proper and nothing contradicts it, so this row exists to convert an untested assumption into a stated finding. A diagnostic about wiring rather than law correctly carries no provision. The disconfirming observation: any module found asserting a regulatory claim through a channel the earlier regex could not see, such as a formatted or multi-line message, belongs in the P02 population and this row must say so rather than close on the count
- `2026-08-10-advisory-grounding-P03-S07` - Author the LegalParameter fix for the standing rule violation P03.S05 surfaced rather than merely flagged: the administrador/consejero retencion rate figures (35 percent, 19 percent, the 100.000 EUR INCN threshold) were typed Python literals in core/aggregation.py carrying a legal_refs citation that read as verified without being registry-sourced, which is more dangerous than no citation at all. Ground the three figures against LIRPF art. 101.2 and RIRPF art. 80.1.3.o, author them as registry LegalParameter entries, migrate them out of core/aggregation.py into a registry-backed loader mirroring the sibling RIRPF art. 95 rate set already established in this module, and thread the loader into the advisory in place of the literal-backed treatment field
- `2026-08-10-advisory-grounding-P03-S09` - Ground the two P03.S06 escalated findings this campaign can adjudicate now. The three LIRPF DT 12a.4 sites in the calculate-input module (_dt12_window_decision's two diagnostics, _dt12_parcial_guidance_advisory) declare asserted_legal_refs against ley-35-2006:dt-12, which resolves cleanly with no gate, same as the sibling _dt12_advisory.py sites already cite it. The recargo-rate-mismatch diagnostic in the modelo-bindings module declares asserted_legal_refs against ley-37-1992:art-161, the recargo de equivalencia provision this project already has a standing rule about. No casilla is in reach for either population, so asserted_legal_refs is the fit, matching the P03.S05 population shape
- `2026-08-10-advisory-grounding-P03-S10` - Record the four LIRPF art. 81.1 maternidad sites in the calculate-input module (_maternidad_ceilings_unresolved_advisory, _maternidad_cotizaciones_ceiling_advisory, _maternidad_ambiguous_relacion_advisory, _maternidad_meses_withheld_advisory) as excluded from this campaign's grounding population rather than grounded or silently dropped. They hit the identical two-vintage-excerpt wall the P02.S03 hard gate already excludes four other sites over: ley-35-2006:art-81-1 has no catalogue entry of its own, only the whole-article ley-35-2006:art-81, which still cites the two-vintage excerpt awaiting an operator stamp under the legal-corpus-vintage plan. Adding a finer article-81-1 entry or repointing art-81 is a corpus-vintage decision, not an advisory-grounding one, so it is rowed against that campaign with this measurement attached rather than smuggled into this sweep. Re-open these four sites once that repoint lands

### plan

- `2026-08-10-advisory-grounding-plan` - `advisory-grounding` plan

### reference

- `2026-08-10-advisory-grounding-reference` - `advisory-grounding` reference: `Advisory provision-citation sites and their reachable refs`
