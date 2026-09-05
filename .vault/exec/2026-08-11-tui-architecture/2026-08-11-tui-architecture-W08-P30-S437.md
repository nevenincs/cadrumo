---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:c066d1931a8d5c4a764834eb79b0436621f15e5e8cd632ffc992e3ed9f848ea6'
step_id: 'S437'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Adjudicate the 16 M200/2024 casillas whose declaration appeared to contradict its own authority. Nine are not contradictions at all: their declared section carries a year prefix that does not name the label's cohort year, and each already carries a pin that settles the text. Three are genuine, their number appearing in neither design under the section they declare. Four are structural: two symbolic identifiers that name no design row, and two whose number repeats on their own page.

## Scope

- `src/cadrumo/locales/*/modelo/schema/200.yml`

## Changes

Unlabelled M200/2024 casillas: 16 -> 7. Nine were never contradictions, and the
gate caught me getting them wrong.

I reasoned that a declared section beginning "2025_" names the 2025 cohort row,
checked it corpus-wide (465 of 534 labelled casillas with a year-prefixed
section agree with the year in their label), resolved all nine in the 2025
design, and wrote them. The pinned-label gate then failed on 02287: it already
carried a pin, and the pin names the 2024 row. Every one of the nine turned out
to be pinned, and every pin points at the 2024 design.

The pin wins, and the reason it wins is the whole point of pinning. My rule was
a derivation from a naming convention that holds 87% of the time; a pin is an
explicit per-casilla commitment to one cell. Where they disagree the derivation
is what is wrong, and here it was: the section's year prefix does not name the
label's cohort year. All nine were rewritten from their pinned text and both
label gates pass.

Three are genuine contradictions and stay unlabelled. 01264, 01265 and 01266
declare "2025 innovacion tecnologica (IT)", and the only cell carrying those
numbers -- in the 2024 design, absent from the 2025 one -- reads "2024
Reconstruccion de la Piscina Historica cubierta de saltos del Club Natacio
Barcelona (CNB)". That is not a near miss. Their earlier "no cell in the 2025
design" reading was partly an extraction artefact: the design's cell text wraps
across two lines and a line-based parser splits it, so the row was being read as
a fragment starting "del Club Natacio Barcelona". Joining rows before matching
fixes the reading and leaves the contradiction standing.

Four are structural rather than adjudicable. DP200014:SAL_RESERVA_DOTACION and
DP200014:bin-aplicada-maxima carry symbolic identifiers, not casilla numbers, so
no design row names them. DP200014B:00599 and DP200018:00588 repeat on their own
page, so the page that disambiguates every other record-qualified casilla does
not disambiguate these two.

## Notes

A CORRECTNESS AUDIT CAME OUT OF THE PARSER FIX. Joining wrapped rows revealed
182 shipped labels that match no design cell in either year. NONE of them is
mine: of roughly 897 labels written across S429 to S436, every one matches a
design cell verbatim. The 182 are the pre-existing deliberate shortenings
measured in S431, and they are not touched here.

The runtime localization gate now fails on 7 casillas, down from 644 failures
when this work began. The work-review screen still cannot render for M200/2024,
because one absent label is enough.

The three contradicted casillas need a registry decision, not a locale one:
either the declaration's section is wrong and 01264-01266 are the Club Natacio
Barcelona rows, or the numbers are wrong and the IT rows live elsewhere. The
four structural ones need a rule for identifiers the design does not name.
