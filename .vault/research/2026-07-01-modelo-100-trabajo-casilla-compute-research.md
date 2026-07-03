---
tags:
  - '#research'
  - '#modelo-100-trabajo-casilla-compute'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - '[[2026-06-15-art20-trabajo-reduccion-compute-adr]]'
---

# `modelo-100-trabajo-casilla-compute` research: `Modelo 100 trabajo-casilla auto-apply and cap gaps`

Several Modelo 100 rendimientos-del-trabajo casillas that the AEAT program applies
automatically are modelled as bare MANUAL inputs, and the net-trabajo formula carries no
clamp. A filer who leaves an auto-applied box blank is mis-taxed. This research grounds the
exact figures, casilla wiring, and the letter-f cap against the bundled consolidated LIRPF
corpus, and scopes the fix against the accepted art-20 precedent
(2026-06-15-art20-trabajo-reduccion-compute-adr, casilla 0023).

## Findings

### Gap A - casilla 0019 art. 19.2.f EUR 2.000 otros gastos is a bare MANUAL input (issue #568)

Casilla 0019 (label "Otros gastos deducibles (*)", semantic_role
irpf_rendimiento_trabajo_gasto_otros, legal_refs ley-35-2006:art-19) has no input_kind and
no formula - a bare manual box - in every revision 2021, 2022, 2023, 2024, 2025
(.../modelos/100/revisions/<year>/casillas/0023-0019.toml). Art. 19.2.f LIRPF (verified
verbatim against bundled src/aeat/_data/corpus/normatives/html/ley-35-2006.html, anchor
a19): "f) En concepto de otros gastos distintos de los anteriores, 2.000 euros anuales."
The AEAT program writes this EUR 2.000 for any contribuyente with rendimientos integros del
trabajo. A blank 0019 therefore OVER-taxes by omitting a determinable EUR 2.000 deduction -
the no-silent-under-declaration shape (here an over-tax through a silent under-deduction).

The two sibling boxes are genuinely conditional and must stay MANUAL:

- 0020 (Incremento para contribuyentes desempleados que acepten un puesto ... traslado de
  residencia; role irpf_rendimiento_trabajo_incremento_traslado_residencia) - art. 19.2.f
  "se incrementara dicha cuantia ... en 2.000 euros anuales adicionales" - conditional on
  unemployment plus relocation acceptance.
- 0021 (Incremento para trabajadores activos que sean personas con discapacidad; role
  irpf_rendimiento_trabajo_incremento_discapacitado_activo) - art. 19.2.f "se incrementara
  dicha cuantia en 3.500 euros anuales. Dicho incremento sera de 7.750 euros anuales, para
  las personas con discapacidad que ... acrediten necesitar ayuda de terceras personas o
  movilidad reducida, o un grado ... igual o superior al 65 por ciento" - conditional on
  disability status.

So the auto-apply target is 0019 only (the unconditional EUR 2.000). 0020 and 0021 are
correctly manual conditional increments.

### Gap B - the net-trabajo formula has no max(0,...) clamp and does not enforce the letter-f cap

Casilla 0022 (Rendimiento neto) is COMPUTED by renta-<year>-trabajo-rendimiento-neto,
expression sum(0018, -0019, -0020, -0021), identical across 2021-2025 - a plain subtraction
with no clamp. The letter-f statutory cap (bundled corpus a19, verbatim): "Los gastos
deducibles a que se refiere esta letra f) tendran como limite el rendimiento integro del
trabajo una vez minorado por el resto de gastos deducibles previstos en este apartado."

Chain: 0017 = 0012 - 0013(sindicatos) - 0014(SS) - 0015(colegio) - 0016(defensa) (gastos
letras a-e); 0018 = copy(0017). So 0018 is exactly "rendimiento integro minorado por el resto
de gastos deducibles" - the letter-f cap base. The cap (0019 + 0020 + 0021) <= 0018 is
therefore MATHEMATICALLY IDENTICAL to clamping the result:
0022 = max(0, 0018 - 0019 - 0020 - 0021). A single max(0,...) on 0022 implements BOTH the
missing clamp and the art. 19.2.f letter-f cap in one expression. Today, an operator who
over-enters 0019/0020/0021 beyond 0018 drives 0022 negative - a wrong, uncapped net.

### Gap C - casilla 0468 applies the EUR 10.000 combined cap but not the art. 52 EUR 1.500 individual sub-limit (issue #574 followup)

Casilla 0468 (Reduccion por aportaciones a sistemas de prevision social) is COMPUTED by
renta-<year>-reduccion-prevision-social-total, expression min(0467, 10000, percent(0432,
30)), legal_refs ley-35-2006:art-52. 0467 is the sum of all contribution inputs sum(0463,
0464, 0465, 0438, 0426, 0427, 0499, 0466).

Art. 52.1 LIRPF (bundled corpus a52, verbatim): the joint limit is "la menor de: a) El 30
por 100 de la suma de los rendimientos netos del trabajo y de actividades economicas ...; b)
1.500 euros anuales. Este limite se incrementara ... En 8.500 euros anuales, siempre que tal
incremento provenga de contribuciones empresariales, o de aportaciones del trabajador al
mismo instrumento de prevision social ...". The art-52 legal-catalogue entry
(src/aeat/_data/registry/aeat/legal/irpf.toml, legal ley-35-2006:art-52, reviewed) already
documents "lesser-of 30 percent / 1,500 EUR limit ... 8,500 EUR maximum increment cap".

So the correct structure is 1.500 (general) + up to 8.500 (increment), and the EUR 8.500
slot is available ONLY when it is backed by employer contributions (0427) or worker
contributions to a plan de empleo (0426). The current flat 10000 literal grants the full EUR
10.000 to a purely-individual filer (0426 = 0 AND 0427 = 0) whose statutory cap is EUR 1.500
- an OVER-reduction (under-tax) when individual contributions exceed EUR 1.500 and 30% of
0432.

Complication for exact compute: 0463 mixes both sides in one box - label "Aportaciones
individuales y contribuciones empresariales ...", role
irpf_red_prevision_social_aportaciones_individuales. The clean individual-only signal is not
a single casilla; the reliably-observable discriminator is the ABSENCE of
plan-de-empleo/employer boxes (0426 = 0 AND 0427 = 0). Secondary observation: the 10000 is
an inline literal, not an external_constants figure (an aeat-schema-central-config smell to
fold into Phase-2 grounding).

### Precedent and mechanism inventory

2026-06-15-art20-trabajo-reduccion-compute-adr (accepted) decided the identical
advisory-first shape for 0023: Phase 1 non-blocking ADVISORY, Phase 2 compute-flip deferred
behind a cross-section aggregate plus the engine refactor. Phase 1 shipped as a Python helper
_art20_reduccion_advisory_finding (src/aeat/application/modelo/_art20_advisory.py), wired in
_verification_actions._collect_revision_verification_findings
(src/aeat/application/modelo/_verification_actions.py:1428 region) beside the DT-12a advisory
(_dt12_advisory.py) - NOT a registry verification_predicate, because the registry-predicate
mechanism needs the registry to load and a peer engine refactor blocked it. Both mechanisms
co-exist (M200 base-determination uses the predicate; DT-12a and art-20 use the helper). The
helper resolves casillas by semantic_role via
casilla_id_for_unique_revision_semantic_role (_semantic_role_resolution.py), never hard-coded
numbers, and grounds each finding with legal_refs. Its RNT ceiling rides
external_constants.MODELO_100_ART_20_TRABAJO_REDUCCION_RNT_CEILING_EUR, not an inline literal.

### Test-surface and parity constraints

- Cross-revision: Gaps A and B span 2021-2025 (five revisions, identical shape confirmed);
  Gap C spans the same. Any registry edit is per-revision (aeat-registry-authority-flow).
- no-tautological-calculation-tests: the EUR 2.000 auto-apply and the EUR 1.500 sub-limit
  have worked examples in the bundled AEAT Renta manuals
  (src/aeat/_data/corpus/manuals/renta/<year>/part1/...) - the individual/employer 1.500 vs
  8.500 split is worked in the 2023/2024/2025 manuals. Derive expected values from those,
  never from the same formula under test. The #574/#545 chain tests
  (src/aeat/domain/calculations/registry/tests/test_renta_chain_behaviour.py) already carry
  manual-grounded oracles for the prevision-social chain and are the extension point.
- Diseno-de-Registros parity: 0019 is listed by AEAT as an INPUT box. Flipping it to COMPUTED
  (Phase 2) needs the same parity-gate treatment the art-20 ADR used for 0023 (a computed
  casilla AEAT lists as input). Phase 1 (advisory) touches no input_kind, so it does not
  perturb the parity gate.

### Landing blocker (Phase 1)

Per the dispatch brief, new advisory prose needs locale keys, and the locale catalogues are
currently under a peer duplicate-key corruption; Phase 1 lands once that clears
(aeat-locales-cli - keys authored only through python -m aeat.locales set). No source WIP was
observed on the modelo/advisory/verification/external_constants/locale files at research time;
the only working-tree churn is modified:-stamp updates across .vault from a peer vault check
all --fix.

### Recent grounding lineage (git)

ad0835b14 grounded 0019/0020/0021 to art-19 (from art-17); bdff09f4b grounded the
prevision-social sections to arts. 51/52 and authored the art-51 entry; d484e32e8 (#574) and
ea11a6637 (#545) added individual/employer prevision-social chain guard tests; 71398c709
(#209) plan-de-empleo. The legal entries ley-35-2006:art-19 (irpf.toml:3368) and
ley-35-2006:art-52 (irpf.toml:2511) both exist, corpus-grounded and reviewed - the citations
this ADR needs are already in the catalogue.

## Sources

- Bundled consolidated LIRPF: src/aeat/_data/corpus/normatives/html/ley-35-2006.html (anchor
  a19 art. 19.2.f plus letter-f cap; anchor a52 art. 52.1 joint-limit / 1.500 / 8.500),
  BOE-A-2006-20764.
- Registry: M100 revisions 2021-2025 casillas 0018-0022, 0463/0426/0427, 0467/0468 and
  formulas renta-<year>-trabajo-rendimiento-neto, renta-<year>-reduccion-prevision-social-total.
- Legal catalogue: src/aeat/_data/registry/aeat/legal/irpf.toml legal ley-35-2006:art-19,
  legal ley-35-2006:art-52.
- Precedent: 2026-06-15-art20-trabajo-reduccion-compute-adr;
  src/aeat/application/modelo/_art20_advisory.py; _verification_actions.py;
  _semantic_role_resolution.py; src/aeat/core/external_constants.py.
- AEAT Renta manuals (worked oracles): src/aeat/_data/corpus/manuals/renta/{2023,2024,2025}/part1/.
- Chain tests extension point: test_renta_chain_behaviour.py (#574/#545 oracles).
