---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:d0d835845795cf035c0bb9532b64df525ef4cae50a8e844325980826428d1bad'
step_id: 'S424'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Sweep every projection and gate still shaped by the retired redaction assumption. DECIDED 2026-09-04. Find each model documented as safe, redacted, or 'without values', each screen docstring promising never to reconstruct a payload, and each test asserting that operator data is ABSENT from a rendered surface. Re-derive the models from the accepted visibility record and rewrite or delete those gates -- a gate asserting the retired policy will otherwise block the fix and read as a safety property while doing it. Gates asserting absence from a log, an exception, a cache, a temporary file or an off-host payload are UNAFFECTED and stay required; do not weaken them while removing the others. CLITUI_LEDGER_DISPOSITION: DISPLACED_AND_HELD_UNTIL_G3; clitui-ledger is the sole owner of this row's Ledger parity slice; do not implement that slice in this plan; non-Ledger scope remains owned here.

## Scope

- `src/cadrumo/application/ and src/cadrumo/entrypoints/tui/`

## Changes

- `A` `src/cadrumo/application/modelo/settlement_casilla.py`
- `A` `src/cadrumo/application/modelo/tests/test_settlement_casilla.py`
- `M` `src/cadrumo/application/modelo/_settlement_grade_advisory.py`
- `verify:` `pytest -n0 -m '' application/modelo/tests/test_settlement_casilla.py` -> `pass` (5)

## Notes

Step still OPEN. This lands the registry read a declaration result needs; the
projection and surface wiring follow.

`SETTLEMENT_SEMANTIC_ROLES` was defined inside the private
`_settlement_grade_advisory` module, so a second consumer could only reach it
across a package boundary into an underscore module. It now lives in the public
`settlement_casilla` module with its grounding -- the #39 audit, casillas 0595
and 0670 -- and the advisory imports it, so the advisory and the result reader
cannot disagree about which cells settle a revision.

READING THE REAL REGISTRY CAUGHT A DESIGN ERROR BEFORE IT SHIPPED. The first
resolver matched the whole settlement set, and Modelo 100 declares TWO of those
roles: `irpf_cuota_resultante_autoliquidacion` (0595, the liability before
pagos a cuenta) and `irpf_resultado_declaracion` (0670, what the declaration
settles). It would have raised ambiguity on the only modelo it covers.
`DECLARATION_RESULT_SEMANTIC_ROLES` is now a strict subset naming the result
alone, and the gate asserts that subset relation so the two cannot be
re-conflated.

Measured against the bundled registry rather than a fixture, because a fixture
proves the matching logic and nothing about whether the shipped registry
declares the role: modelo 100 resolves to 0670; modelos 303 and 130 resolve to
NOTHING, which is the honest answer for a settlement chain that is not
modelled. 303's casillas carry positional roles like `dr303_23` that name no
meaning, and returning a plausible cell for them would put a number under
"result" that no authority supports.

Ambiguity refuses rather than picking a first match: a declaration with two
results has none, and the registry declaration is wrong rather than something
to resolve at read time.

Teeth proven by conflating the two role sets -- the subset guard fails AND
modelo 100 raises `declares 2 final-result casillas (0595, 0670)`, which is
exactly the error this design avoided. Restored by copy.
