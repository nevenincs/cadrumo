---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S01'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Verify M390 against its untested real_corpus specimen 2021-0A, covering routes R2 kerning drift and R6 bbox fragility, on a profile with a confirmed R2 defect

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/390`
- `declaracion tests`

## Description

The Modelo 390 real specimen had never been read by anything. The per-modelo
boundary test parametrises `2022-0A` and `2023-0A`, both synthetic, so the one
genuine filed annual summary in the repository was untested against its own
profile exactly as the brief stated.

Reading it found a defect the anticipated routes did not name. AEAT issues the
sede justificante in the language the filer chose, and this render is English
throughout: its page one reads `INFORMATION ON FILING THE TAX RETURN / FORM
390`, and every printed label is translated with it. All five of the profile's
`named_label` patterns were Spanish-only, so the render scored 1 of 10 targets.
The single match was `iva.anual.soportado.interiores`, which is `bbox_anchored`
and therefore keys on the printed box number rather than on prose.

Four labels were widened to accept the wording the render literally prints:
`Total deductions` for box 64, `Result of the general system (47 - 64)` for box
65, `To offset` for box 97, and `Amounts pending offset arising in the year` for
box 662. Each alternate was read off the extracted text of the document, not
translated or inferred. Box 47 was deliberately left Spanish-only: the render
prints form pages 1, 3, 4 and 6, its page 3 opens on `5. Transactions made under
the general system (continued)` with no preceding start, so the devengado page
carrying box 47 and the four rate rows is absent and no English wording for them
is observable in bundled evidence.

Route R2 (kerning drift) was already closed on this profile by the prior pass and
the fix holds on the real render: the box-65 pattern's tolerant `\(\s*4\s*7\s*-\s*64\s*\)`
matches the English line unchanged. Route R6 (bbox fragility) could not be
exercised against this specimen for the four devengado rate rows, because the
page carrying them is not in the document; that is an evidence gap, not a pass.
Route R3 is confirmed defective and unfixable from one specimen, as recorded
below.

## Outcome

Coverage on `390/2021-0A` rose from 0.1000 (1 of 10) to 0.4000 (4 of 10). Boxes
64, 65 and 97 are recovered and each reads the sanitiser constant `1000.00`,
which is the value the specimen's own manifest declares was written there.

Box 662 became reachable with them and is printed blank, so this render now
exercises the blank-box guard end to end on real evidence for the first time.
Driving `_classify_target` directly with production code: with the guard armed
(`casilla.number = '662'`) the target is reported missing; with the guard given
no number to compare against it returns `Decimal('662')`. That second column is
the live state of six other targets and is recorded as an open hazard below.

The profile's `min_coverage` remains `"0"` and was deliberately not raised. It
cannot refuse anything, which is why the language mismatch survived, but the
repository holds exactly one real Modelo 390 render and deriving a floor from a
single specimen is the error the governing decision was careful to avoid. The
extracted-set assertion is the gate instead, and it is strictly stronger than a
ratio.

Verification: the M390 gates pass (`21 passed`), the full declaracion suite
passes (`227 passed`), and the facsimile specimen is unregressed - its Spanish
matches are unchanged at 88.416,00 / 68.202,00 / 20.214,00 / 2.226,00 /
2.106,00.

Falsifiability was proven rather than assumed. Reverting the single
`Total deductions` alternate fails
`test_real_filed_declaration_yields_exactly_the_expected_casillas[390/2021-0A]`
naming `iva.anual.cuota-deducible-total` as unexpectedly absent, with 41 other
cases still passing. Raising `min_coverage` from 0 to 0.5 fails five cases. Both
perturbations were restored from a copy taken beforehand and the restored file's
digest was confirmed to match.

## Notes

Two defects found here cannot be fixed from the files this step owns and are
reported rather than closed.

The blank-box guard is inert on three of this profile's targets:
`iva.anual.cuota-devengada-total`, `iva.anual.cuota-deducible-total` and
`iva.anual.resultado-regimen-general` each carry a `casilla.number` equal to
their own casilla id string rather than the printed 47, 64 and 65. The guard
compares the captured token against that field, so it can never match, and a
blank box 64 on a future render would be read as 64 euros. The printed lines end
in the box number before the value, so the hazard is concrete rather than
theoretical. Correcting `number` means editing casilla TOMLs, which are not
extraction-profile TOMLs and so fall outside this step's grant.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy with an empty
degraded-reasons list. No semantic result was relied on. Every claim here rests
on loading the revision through the registry authority, on literal extraction of
the document's own text, or on glyph-level inspection of the rendered PDF.
