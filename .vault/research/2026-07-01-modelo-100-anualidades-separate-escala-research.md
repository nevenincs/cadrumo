---
tags:
  - '#research'
  - '#modelo-100-anualidades-separate-escala'
date: '2026-07-01'
modified: '2026-07-01'
related: []
---

# `modelo-100-anualidades-separate-escala` research: `Modelo 100 anualidades por alimentos separate-escala regime`

Grounding for correcting a confirmed silent under-declaration in the Modelo 100
cuota-integra chain (issue #532, P1): the anualidades por alimentos a favor de
los hijos satisfechas por decision judicial separate-escala benefit is partially
and incorrectly modelled across revisions 2020-2025. An interim non-blocking
advisory already landed (advisory_when_positive on casilla 0527 in the 2024/2025
revisions, commit 3aaf44f15); this research grounds the full determination the
ADR must decide, and the conditions under which the interim advisory is retired.

## The benefit, grounded in bundled authoritative corpus

Both provisions are present verbatim in the bundled consolidated LIRPF
(src/aeat/_data/corpus/normatives/html/ley-35-2006.html, 1.9 MB; the per-article
snippet files such as ley-35-2006-art-1.html are anchor stubs and must not be
used). Verified against that file (not a secondary source), per rule
legal-grounding-verifies-bundled-authoritative-corpus:

Art. 64 (estatal), bloque a64 (paraphrased, accents stripped): contribuyentes who
satisfy anualidades por alimentos a sus hijos, sin derecho a la aplicacion por
estos ultimos del minimo por descendientes previsto en el articulo 58, cuando el
importe de aquellas sea inferior a la base liquidable general, apply la escala del
articulo 63 separadamente al importe de las anualidades y al resto de la base
liquidable general; la cuantia total resultante se minora en el importe derivado
de aplicar la escala del articulo 63 a la parte de la base liquidable general
correspondiente al minimo personal y familiar incrementado en 1.980 euros
anuales, sin que pueda resultar negativa como consecuencia de tal minoracion.

Art. 75 (autonomica): the mirror provision, referencing the escala autonomica of
art. 74 (not art. 63), and the autonomic minimo que resulte de los incrementos o
disminuciones del articulo 56.3, incrementado en 1.980 euros anuales.

Confirmations for the ADR context:

- Binding provisions are art. 64 (estatal) + art. 75 (autonomica). Art. 65 is
  Escala aplicable a los residentes en el extranjero and is unrelated -- do not
  cite it. Both are already the legal_refs on the existing anualidades formulas
  and on the interim advisory.
- The escala the separate treatment applies is art. 63 (estatal general tarifa) /
  art. 74 (autonomica) -- the same parameters the normal cuota chain already
  consumes (renta-{year}-escala-estatal-base-general,
  renta-{year}-escala-autonomica-<ccaa>-base-general).
- The +1.980 EUR minimo increment and the floor at 0 (sin que pueda resultar
  negativa) are stated in the law text itself -- derivable from art. 64/75, not
  manual-only. The casilla-level wiring (which casilla holds which term) is NOT
  derivable from the law and is grounded against the AEAT Renta manual
  (aeat-renta-2024-manual-parte1, already a registry source_ref) and the
  live-oracle / workbook parity the state-scale research established.
- The 2025 revision carries a marginal LO 1/2025 (efectos 3-abr-2025)
  modification of the art. 64/75 wording (the letra-k cross-reference), noted in
  the corpus alongside the retained 1.980 figure; the algorithm and the 1.980
  amount are unchanged for filing years in scope.

The correct determination (state; autonomic mirrors with the art. 74 escala and
the autonomic minimo), floored at 0, applies only when anualidades > 0 AND
anualidades < base liquidable general AND the payer has no right to the minimo por
descendientes for those hijos:

    cuota_estatal_BLG = max(0,
        [ escala63(anualidades) + escala63(base_liq_general - anualidades) ]
        - escala63(minimo_personal_familiar + 1.980) )

## Current (defective) wiring -- cross-revision inventory

The cuota-escala sub-chain has the same shape in every revision 2020-2025; the
escala formulas all read casilla 0505 as the escala input. Files under
src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/:

- 0527 total anualidades: sum(1741,1744,1749,1754,1759), refs art-64/75 (0022-...-anualidades-alimentos-hijos-suma.toml)
- 0505 base liq. general sometida a gravamen: max(0, 0500 - 0527) (0168-...-sometida-a-gravamen.toml)
- 0528 escala estatal s/ base: lookup_bracket(0505, escala-estatal) (0148)
- 0529 escala autonomica s/ base: lookup_bracket_by_ccaa(0505, ccaa-binding, dispatch) (0150)
- 0530 escala estatal s/ minimo: lookup_bracket(0521, escala-estatal) (0149)
- 0531 escala autonomica s/ minimo: lookup_bracket_by_ccaa(0521, ...) (0151)
- 0532 cuota base gral estatal: subtract(0528, 0530) -- NO floor (0152)
- 0533 cuota base gral autonomica: subtract(0529, 0531) -- NO floor (0153)
- 0521 minimo estatal aplicable: min(0505, 0519) (0074)
- 0523 minimo autonomico aplicable: min(0505, 0520) (0076)

Two distinct defect shapes:

1. 2024/2025 (0505 formula present): 0505 = max(0, 0500 - 0527) subtracts
   anualidades from the base and applies a single escala to the reduced base,
   yielding escala(base - anualidades) - escala(minimo). It omits the
   escala(anualidades) term and the +1.980 increment, and applies no floor.
2. 2020-2023 (no 0505 formula): 0505 is a manual input feeding the same escala
   formulas; the anualidades regime is not modelled at all (the 0505->0532
   computed sub-chain must be built from 0500 first).

Direction of error: the separate-escala regime produces a cuota higher than the
current shortcut (the shortcut under-taxes) and lower than a single escala on the
full base (the benefit is real). Worked figures below.

## Formula-runtime capability -- the algorithm is fully expressible

src/aeat/domain/calculations/registry/_formula_runtime.py (dispatch at
_evaluate_expression, ~line 519) and _formula_runtime_ops.py::evaluate_args_op
provide every primitive needed:

- arithmetic add/sum, subtract, multiply, min, max (_formula_runtime_ops.py:28-72);
- comparison ops returning 1/0: less_than, greater_than, greater_equal, equal (_COMPARISON_OPS, line 24);
- if_then_else -- short-circuit, predicate truthy when != 0 (_evaluate_if_then_else, line 1387);
- lookup_bracket(base, parameter) and lookup_bracket_by_ccaa(base, ccaa-binding, dispatch_table) -- already used by the escala formulas.

There is no boolean and/or op; a multi-condition predicate is composed as the
product of 1/0 comparison results -- multiply(cond_a, cond_b, flag) -- which
if_then_else reads as truthy iff all factors are non-zero. Existing precedent for
a comparison-gated conditional cuota formula:
.../revisions/2024/formulas/0033-renta-2024-tipo-medio-gravamen-estatal-base-liquidable-general.toml
declares if_then_else(greater_than(0505,0), divide(...), 0).

## The no-minimo-por-descendientes gating input needs a new modelled fact

Two of the three gate conditions are expressible from existing casillas:
anualidades > 0 is greater_than(0527, 0); anualidades < base is
less_than(0527, 0505). The third -- sin derecho al minimo por descendientes por
esos hijos (art. 64) -- is a per-filing fact that cannot be derived from other
casillas and requires a new typed input.

Idiomatic precedent exists under .../revisions/2024/bindings/: a family of
source = "profile" scalar/boolean bindings, e.g.
renta-2024-profile-descendientes-count (profile_key
"renta_family.descendientes_count", refs art-58), and the boolean manual-input
renta-2024-modelo-100-estimacion-directa-es-normal
(selector casilla_id 0168, data_type boolean, true_value N, false_value S,
aggregation op copy). Either shape -- a source = "profile" boolean binding, or a
data_type = "boolean" manual-input binding on a dedicated indicator casilla --
supplies a 1/0 flag into the predicate multiply(...). Grounding refs for the flag:
art-58 (the minimo por descendientes it negates) plus art-64.

## Non-tautological test anchors (worked example, 2024 state, Cataluna)

Base liq. general 14.896 EUR, anualidades 3.000 EUR, minimo 5.550 EUR. The 2024
state escala first bracket is 9,5% (half the tarifa); verified against the
existing test oracle values (escala(5.550)=527,25, escala(11.896)=1.130,12,
escala(14.896)=1.476,27 in
src/aeat/domain/calculations/registry/tests/test_modelo_100_tarifa_real.py:495-545):

- no benefit (single escala, full base): 949,02 = escala(14.896) - escala(5.550)
- current shortcut (defective): 602,87 = escala(11.896) - escala(5.550)
- correct separate-escala: 699,77 = [escala(3.000)+escala(11.896)] - escala(7.530)

Ordering 602,87 < 699,77 < 949,02 holds: the fix raises cuota over the shortcut
(closes the under-declaration, ~+96,90 EUR state-only for this profile) and stays
below the no-benefit single escala (the benefit is genuine). Both inequalities are
properties (not recomputations of the formula under test), so a test asserting the
ordering is non-tautological per no-tautological-calculation-tests; the exact
expected value should be pinned to an AEAT Renta manual worked example or
live-oracle capture rather than hand-computed. The existing
test_anti_tautology_anualidades_changes_cuota asserts only cuota_with < cuota_no
and currently encodes the 602,87 shortcut value -- it must be updated or it locks
in the defect.

## Blast radius for the sweep

Per revision (read both inline and fragmented registry forms per
registry-revision-content-inline-or-fragmented; here all fragmented under
.../revisions/<year>/formulas/):

- Revert 0505 to the full base liquidable general (drop the - 0527) in 2024/2025;
  build the 0505 formula (from 0500) in 2020-2023. Re-verify all seven 0505
  consumers per revision (0521, 0523, 0528, 0529, 0534 tipo medio, and others)
  still want the full base -- they do (the minimo cap and the escala both operate
  on the full base; the regime handles anualidades separately).
- Make 0528/0529/0530/0531 conditional (if_then_else on the regime predicate) and
  floor 0532/0533 at max(0, ...).
- Add the new gating-input binding (plus its casilla/construct enrolment) per revision.
- Sweep casilla legal_refs, the cuota construct, and the previous_filing /
  per-source bindings coherently in one change per revision (the registry
  validator requires the legal_refs of a construct to cover the refs of both its
  member casillas and its bindings -- casilla-grounding-corrects-actividades-default-by-section).
- Retire the interim advisory advisory_when_positive on 0527 (2024/2025
  verification_expectations/0002-verification_predicates.toml) only when the full
  compute lands for that revision; the mechanical follow-up that would add the
  advisory to 2020-2023 is superseded by the compute rather than added.

Scope note: issue #532 names 2021-2025; 2020 has the identical defective shape
(manual 0505, escala on 0505, refs art-64/75 on 0022) and is a discovered
in-family revision the plan should fold in or explicitly defer.

## Peer WIP

An untracked peer file
.../revisions/2024/constructs/0013-renta-2024-personal-family.toml is present in
the working tree (git status: ??). It is untouched by this read-only research; the
sweep must re-check HEAD and abort-on-WIP before editing the 2024 construct.
