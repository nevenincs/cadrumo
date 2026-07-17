---
tags:
  - '#audit'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-17'
related: []
---

# `obligation-coverage-completeness` audit: `obligation enrollment corpus-ceiling audit`

## Scope

Audits the state of AEAT-wide obligation enrollment after the coverage-completeness
campaign. The goal was to drive the registry from its ~30-modelo subset toward AEAT's
full ~200-form set so the `overview` surface never silently under-scopes what a
taxpayer must file. This audit records what was enrolled, the grounding standard
applied, and the precise reason the remainder is blocked — so a follow-on session or
the parallel AEAT-instruction fetch pipeline can complete sub-goal (1) deterministically.

## Findings

### enrolled-set | low | Ten forms enrolled and grounding-verified, registry 30 to 40, seed-ruled 16 to 26

The campaign enrolled ten previously-unmodeled forms with real deadline windows and
applicability rules, each grounded in a bundled Orden verified against its literal
approval clause: 216, 296 (Orden HAC/56/2024); 117, 126, 128 (Orden EHA/3435/2007,
autoliquidaciones); 187, 188, 194 (Orden EHA/3377/2011, capital-mobiliario resumen
diseños family); 231 (Orden HAC/941/2018, country-by-country report); 361
(Orden EHA/789/2010, IVA refund for EU-established non-residents). Two new payer facts
were added to the applicability table for the last two: `member_of_large_multinational_group`
and `eu_business_seeking_spanish_vat_refund`. Registry validation, the applicability
canonical gate, and the obligation-coverage gate are all green. Deadline windows follow
the standard AEAT plazo conventions their already-enrolled sibling forms use (quarterly
retención = first 20 days of the following month; annual resumen = enero; CBC = 12 months
after group period end; IVA refund = 30 September of the following year per Directiva
2008/9/CE art. 15).

### grounding-standard | medium | A strict approval-clause grounding standard caught two mis-grounding defects

Enrollment was gated on a strict standard: a form is enrolled only if a bundled Orden
*genuinely governs* it, verified against the literal `se aprueba el modelo N` approval
head rather than an incidental in-text mention. This caught two defects that were then
corrected. Modelo 198 was initially enrolled against Orden EHA/3435/2007, but that Orden
approves only the autoliquidaciones 117/123/124/126/128/300 — 198 is an informativa
mentioned only under its telemática measures — so 198 was de-enrolled back to the advised
(UNMODELED) universe. Modelo 182 was found to have no bundled approving Orden at all (its
matches were incidental cross-references in the IRNR Orden EHA/3316/2010 and the general
presentación Orden), so it was not enrolled and its speculative payer fact was reverted.
A stale corpus hash on the 361 source (copied from an unrelated catalogue entry) was
caught by the evidence gate's byte-count check and corrected to the real file hash.

### corpus-ceiling | high | The remaining ~160 forms are corpus-blocked, not effort-blocked

An exhaustive scan of all 275 bundled Ordenes for every unmodeled form's exact approval
head confirmed that ten forms is the complete bundled-corpus-groundable set. Every
candidate beyond it is a false positive where the form number appears incidentally, not
as the approved form (222 to 202; 182 to IRNR 210/211/213; 189/289/165 to 430; 270 to
347/190). The still-unmodeled obligations — 136, 165, 179, 181, 182, 189, 222, 233, 234,
238, 270, 280, 289, 345, 368, 379 — have no governing Orden in `src/aeat/_data/corpus/`.
Neither their existence-grounding nor, critically, their exact deadline dates can be
sourced from the bundled corpus, so enrolling them would require fabricating corpus and
plazo dates, which the safety-legal gate forbids. These forms remain visible: the
coverage reconciliation surfaces every one of them as an advised (investigate) row on
every overview surface, so none is silently absent — sub-goals (2), (3), (4), and (5)
are complete and verified.

## Recommendations

Complete sub-goal (1) through the parallel AEAT-instruction fetch pipeline (the
`corpus/aeat_official/instructions/modelo_NNN/` convention with real sede-procedure HTML
and computed sha256), which is the correct owner of authoritative-corpus breadth and is
already enrolling forms in parallel. For each remaining unmodeled form, that pipeline
should: fetch its governing Orden or AEAT sede procedure page as authoritative corpus,
verify the plazo against that text, add the modelo definition (deadline windows +
casillas) plus an applicability rule (reusing an existing payer fact where the obligation
is a retención/informativa, or adding a form-specific fact for institution-only forms),
and remove the form from `UNMODELED_OBLIGATIONS`. Agent-authored source entries for
fetched corpus must record honest `review_status` provenance pending operator re-stamp,
per the legal-grounding rule — do not stamp `reviewed` on unverified fetched corpus.
Institution-only forms whose filers are never the app's taxpayer users (e.g. CRS/FATCA
account reporting by financial institutions) may alternatively be classified into the
hardened out-of-scope set rather than enrolled, which also resolves them to a confident
does-not-apply. The enrolled/blocked partition in the findings above is the deterministic
work-list for that completion.
