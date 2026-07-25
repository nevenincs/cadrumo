---
tags:
  - '#audit'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-26'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-layout-blind-corpus-audit]]"
  - "[[2026-07-25-declaracion-profile-printed-box-scope-adr]]"
---

# `declaracion-profile-printed-box-scope` audit: `closing the gaps the printed-box audit named`

## Scope

The printed-box change left two gaps its own audit named but did not close: no
test in the repository read a real AEAT render, and the misnaming that hid the
original defect was repaired on Modelo 303 by hand with nothing to stop it
recurring. This pass closes both, and reports what closing them found.

It also corrects a finding that pass published. Numbers here were measured
against the working tree; the semantic code index remained truncated throughout —
roughly 1027 chunks against roughly 4546 files, reporting itself healthy with an
empty degraded-reasons list — so every site claim rests on literal-string walks,
targeted search, and loading revisions through the registry authority.

## Findings

### m130-finding-was-wrong-and-the-defect-is-worse | high | The withdrawn finding claimed a missing sidecar; the sidecar exists and the name contradicts it

The prior audit recorded that the Modelo 130 fixture constant pointed at a
fixture carrying no provenance sidecar, and treated the gap as undeclared
metadata. That is false. All 15 Modelo 130 justificante fixtures carry sidecars,
and the one this constant names declares `synthetic_generated` /
`formula_verification`.

The error was in the probe. The constant resolves to the `2024-1T` fixture and
the check was run against `2024-0A`, a path that does not exist; the absent file
was read as an absent declaration. It is precisely the failure mode the same
audit described one finding earlier — a clean negative accepted without
confirming the probe fitted the data — committed in the act of writing that
finding up.

The corrected defect is the more serious one. Provenance was declared all along
and the name contradicted it, making this the identical misnaming found on
Modelo 303 rather than a metadata gap. The consuming test's own docstring
already read "synthetic" while its name read "real", so the contradiction sat
inside a single file and was still missed by review.

### no-real-corpus-modelo-130-fixture-exists | medium | The name could not have been repaired by re-pointing it

Enumerating every fixture sidecar by declared provenance gives 9 `real_corpus`
specimens, spanning Modelos 100, 111, 190 and 390 only; 7
`aeat_published_facsimile` annex specimens for Modelos 303 and 390; and 51
`synthetic_generated`. Modelo 130 has no real-corpus specimen at all, and
neither does Modelo 303.

This matters for how the misnaming is read. It was not a constant pointed at the
wrong file, recoverable by re-pointing it at the right one — there was no right
one. The name asserted a class of evidence the repository has never held for
that modelo.

### fixture-naming-is-now-bound-to-declared-provenance | high | A gate replaces the review that missed both defects

Both misnamings were found by hand, months apart, and neither by a failing test.
A gate now binds each fixture-path constant in the shared parser-boundary
support module to the provenance its sidecar declares: a name carrying the real
marker must resolve to `real_corpus`, one carrying the synthetic marker to
`synthetic_generated`, and every such constant must carry one marker and point
at a fixture that declares provenance at all.

Its falsifiability was proven rather than assumed. Re-injecting the exact
historical defect — a real-marked name over the synthetic Modelo 130 fixture —
fails the gate with the mismatch named explicitly, so both defects would have
failed on the commit that introduced them. A companion test guards against the
gate silently auditing nothing if the constants are moved or renamed out of
reach.

### real-render-coverage-is-now-enforced | critical | The claim that a profile can read a real AEAT render is tested for the first time

Nothing in the repository read a real AEAT render. The generated corpus scores
full coverage at any threshold, so the coverage floors the printed-box change
established rested on measurements no test repeated.

A gate now runs the production extraction path over all five bundled
AEAT-published annex specimens — the four Modelo 303 quarters and the Modelo 390
annual — and asserts each is accepted at its profile's own declared floor, with
the extracted casilla set matching exactly what the printed document carries.
The set is asserted rather than the ratio, because a ratio hides substitution: a
pattern that stops matching one box while another starts matching leaves the
count unchanged.

It bites. Raising the Modelo 303 floor from the measured 0.8333 to 0.95 fails
seven cases, exactly the three quarters that score below it plus the
anti-vacuity guard. Before this gate that same edit was green.

The suite also asserts that at least one specimen falls short of full coverage.
Every other assertion would pass against specimens that all scored 1.0, and such
a corpus would have stopped exercising the blank optional box — the one thing
the generated fixtures cannot express.

### m390-silently-dropped-a-printed-box-on-every-real-render | critical | The same defect class as Modelo 303, found by pointing the new gate at it

Extending the gate to Modelo 390 immediately found the Modelo 303 defect in
another profile. Its `iva.anual.resultado-regimen-general` target matched the
literal `(47 - 64)` from the box's printed label, but the real AEAT render kerns
that reference so text extraction yields `(4 7 - 64)`. The pattern therefore
failed on every real render while matching the generated corpus, and box 65 —
carrying 20.214,00 in the bundled annex — was silently dropped.

The pattern now tolerates the internal spacing, taking the specimen from 7 of 10
targets to 8. The extracted value is independently corroborated by the form's own
printed arithmetic: 88.416,00 minus 68.202,00 is exactly the 20.214,00 the box
prints, which is asserted in the gate so a pattern that matched a neighbouring
figure would fail rather than pass the set check. The two remaining absent
targets are the 4% and 10% rate rows the worked example never exercises.

This is the pitfall the governing decision named — that the printed-versus-
primitive distinction is not Modelo 303 trivia. It took one specimen and one
gate to confirm.

### m390-coverage-floor-cannot-refuse-anything | high | A fail_hard profile with a floor of zero is a guard that cannot fail

The Modelo 390 profile declares `min_coverage = "0"` with `failure_semantics =
"fail_hard"`. No document can score below zero, so the coverage arm of that gate
can never refuse — which is why the dropped box above went unnoticed for as long
as it did. The governing decision rejected an option on exactly this reasoning:
a guard that cannot fail is not a guard.

The floor was deliberately **not** changed. Setting one needs evidence of what
the form yields across filings, and the repository holds exactly one Modelo 390
real render. Deriving a floor from a single specimen is the error the printed-box
change was careful to avoid when it refused to assume the 1T shape, and doing it
here would trade a vacuous gate for an under-evidenced one that refuses valid
filings.

The practical protection is in place regardless: the new gate pins Modelo 390's
extracted set exactly, which is strictly stronger than any ratio. Raising the
floor should follow more specimens, not precede them.

## Recommendations

Point the real-render gate at each remaining `declaracion_pdf` profile as
specimens for it are acquired. It found a critical defect in the first profile it
was extended to, on the first run, having been built for a different modelo
entirely.

Set the Modelo 390 coverage floor once more than one real render exists, and read
the current zero as an open gap rather than a deliberate tolerance. Until then the
extracted-set assertion is the gate.

Acquire real renders for Modelos 130 and 303, which have none. This remains the
only thing that would let their parser tests claim external grounding, and the
naming gate now makes the absence explicit rather than letting a name paper over
it.

Treat the withdrawn finding as evidence for the standing discipline rather than a
one-off slip. It was a clean negative accepted without confirming the probe fitted
the data, produced while documenting that exact failure mode, which suggests the
rule is easy to state and hard to apply under load. Probes that establish absence
should assert the target path exists before concluding anything from its silence.
