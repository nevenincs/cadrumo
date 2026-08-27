---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:c064454c056b1b146c21cb13114623820f7de0ab4cd1eef1af289fb0911a4cbf'
step_id: 'S22'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Ground every category citation on inline corpus text with a declared verified, refused or not-bundled state

## Scope

- `src/cadrumo/domain/categories/tests/test_citation_quote_grounding.py`

## Changes

- `A` `src/cadrumo/core/citation_grounding.py`
- `D` `src/cadrumo/domain/iva/_schema.py` (IvaCitationGrounding relocated out)
- `M` `src/cadrumo/domain/iva/_schema.py`
- `M` `src/cadrumo/domain/iva/__init__.py`
- `M` `src/cadrumo/domain/iva/_catalogue.py`
- `M` `src/cadrumo/domain/iva/verify.py`
- `M` `src/cadrumo/domain/iva/tests/test_rules.py`
- `M` `src/cadrumo/domain/categories/_proportionality.py`
- `M` `src/cadrumo/domain/categories/_registry.py`
- `M` `src/cadrumo/_data/registry/aeat/categories/profiles.toml`
- `A` `src/cadrumo/domain/categories/tests/test_citation_quote_grounding.py`
- `M` `src/cadrumo/domain/categories/tests/test_profile.py`
- `M` `src/cadrumo/locales/en/*`, `es/*`, `ca/*`, `hu/*`
- `M` `dev/locales/tests/test_registry_locale_key_parity.py`
- `verify:` `pytest domain/categories domain/iva domain/usage_ratios dev/locales` -> `1556 passed, 4 failed (peer CLI locale keys)`
- `verify:` `bite proofs over the shipped TOML, four probes` -> `pass`

## Notes

The mis-citation this pass surfaced is the substantive finding. `seguros_salud_autonomo`
cited LIRPF "art. 30.2.5.c regla 1.a"; letter c of that rule is gastos de manutencion
and regla 1.a is aportaciones a mutualidades. Seguro de enfermedad is letter a. The
locale key is why nobody saw it: a citation rendering as the literal word "Quote"
cannot be read against the article it names. Locator corrected and pinned by a
regression.

Two defects of my own from earlier in this campaign were found and fixed here. The
mutualidad rule's `notes` sat after its cap-schedule array-of-tables, so TOML bound it
to the final schedule row and the rule carried none; the scanner stringified the
absence into the literal locale key "None", unauthorable in any catalogue. And the two
statutory-cap variant labels added with the seguro fix were never authored in the four
catalogues. Both are now closed, with the "None" shape gated.

Scope note against the standing goal: the 41 annual-edition citations are recorded
`source_not_bundled` rather than grounded. That is the honest state, not a narrowing --
the AEAT Manual practico editions and portal help pages they name are not among the
bundled consolidated BOE texts, so no verbatim excerpt can be transcribed from anything
this repository holds. What the standing goal still asks for and this excludes is
first-party evidence text for those 41; obtaining it needs the Manual editions bundled,
which is an operator decision about corpus scope, not authoring work.

The pinned key count in the locale parity gate was replaced rather than raised. A tally
reds on every new spending category, trains the reader to bump the number, and says
nothing about which key appeared.
