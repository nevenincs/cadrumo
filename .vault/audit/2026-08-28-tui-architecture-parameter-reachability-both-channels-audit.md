---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:b3d63c846da25af5f2ecc1eb0123984815a9cbf5a762078410e2cbba8e901c2b'
related: []
---

# `tui-architecture` audit: parameter reachability, measured across both channels

## The question, finally answerable

Earlier sweeps reported 200 then 130 "unreferenced" registry parameters and both
counts were disowned as untrustworthy, because production Python also resolves
parameter ids by f-string construction — `f"renta-{filing_year}-minimo-
descendientes-{infix}{suffix}-{filing_year}"` — which a string-equality sweep
cannot see.

That channel is now modelled: every production f-string becomes an anchored
regex, literal parts kept and interpolated slots widened, and declared ids are
tested against it. Combined with TOML references, **59 of 413 declared parameters
are unreachable by either channel.**

The first run of that probe returned ZERO, which was wrong: with unanchored
templates, `f"{a}-{b}"` compiles to a pattern matching nearly every hyphenated id
and silently absorbs the whole declared set. Requiring a real literal prefix and
15+ characters of literal text fixed it. The tell was that zero contradicted two
independently known-unconsumed parameters.

## 49 of the 59 are declared pre-staged data, not orphans

The repository already owns a better fold for Modelo 100:
`test_no_orphan_parameters_in_any_revision` in
`registry/tests/test_modelo_100_drift_detection.py`. It resolves references from
formula expression trees AND from in-tree `read_parameter(...)` calls, and it
carries `_PRE_STAGED_PARAMETERS` — 124 entries covering parameters "declared in
the registry with authoritative tax data ... but whose consuming formula has not
yet been wired", with the discipline stated on the set itself: "Removing an entry
from this set is the gate that the corresponding formula work must clear."

**All 49 Modelo 100 entries in my unreachable set are on that allow-list.** They
are deferred data with a named clearing condition — the same shape as the 2025
casilla deferral, and not a defect.

### Correcting an earlier claim of mine

A previous pass recorded "minimo-ascendientes and minimo-discapacidad are
VERIFIED REACHABLE via casillas 0515-0518". That was wrong. Those casillas carry
`semantic_role = "irpf_minimo_ascendientes_estatal"` and a matching
`continuidad_id`; neither names the parameter id. A stem grep matched the role
string and I read reachability into it. The exact ids appear nowhere outside
their own declarations. The conclusion changes from "reachable" to "pre-staged
and allow-listed" — same verdict of not-a-defect, reached for the right reason.

## 10 sit outside any orphan gate

The Modelo 100 gate is Modelo 100 only: it loads `_modelo_100()` and reads
`_read_parameter_refs_for_modelo("100")`. Nothing equivalent guards the rest.

| parameter | modelo |
|---|---|
| `is.modelo-200.tipo-gravamen-erd` | 200 |
| `m210-tipo-renta-code-2025` | 210 |
| `m303-modulos-iva-dificil-justificacion-forfait` | 303 |
| `modelo-232-related-party-threshold-eur` | 232 |
| `modelo-347-tercero-anual-threshold-eur` | 347 |
| `modelo-360-{annual,quarterly}-refund-threshold-eur` | 360 |
| `rd-439-2007-art-109:conceptos-ingreso-excluidos-base-agraria` | legal |
| `rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario` | legal |
| `rirpf-art-95:retencion-actividades-profesionales-colectivos-especificos` | legal |

Some are self-declared: the Modelo 347 threshold file says in its own comment
"No formula consumes this parameter today", which is exactly the honest form.
Others carry no such statement, and no gate would notice if one silently stopped
being consumed.

**Direction.** The set skews toward reliefs, where non-application over-charges:
the Modelo 200 ERD reduced corporate rate (unread ⇒ taxed at the general rate),
the Modelo 303 simplified-regime difficult-justification forfait, and the RIRPF
art. 95 reduced 7 % retención for specific collectives (unread ⇒ the general 15 %
withheld). Four more are already-open findings whose "no formula consumes this"
property this second, independent method now confirms.

## For an owner

The Modelo 100 orphan gate is the right shape and is worth generalising to the
other modelos, together with its allow-list discipline: a parameter may sit
unconsumed provided it is declared as such and the declaration is the gate future
work must clear. Extending it would convert the ten above from unnoticed to
either consumed or explicitly pre-staged.

Probe kept at `tmp/reachability.py`. Its anchoring constraint is load-bearing —
loosen it and it silently reports zero.
