---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:d4a3a84dc5abe7f8e7a8afdfef0761657c24bbd04e344c0b9b62fdd92e1e2775'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
  - "[[2026-08-12-casilla-schema-s36-campaign-close-honesty-review-audit]]"
---

# `casilla-schema` audit: `S82 Spanish casilla-family rename review`

## Scope

Formal review at HEAD `245142a4ad` of the open `W05.P11.S82` implementation and its execution record against the accepted canonical-derivations decision, the standing Spanish-stem naming authority, the no-legacy rule, and the S36 close finding that authorized the destructive rename. Fresh semantic code and vault searches located the canonical classifier, its decision, plan row, S82 execution record, consumers, tests, locale registration, and catalogues before exact source inspection.

The review traced `EstadoCasillaOficial`, `estado_casilla_oficial`, and `clasificar_casillas_oficiales` through the core owner and facade, registry owner and facade, application review producer/context/reference derivation, TUI option registration/filter/rendering, JSON envelope, tests, dynamic locale registration, and all four catalogues. It also compared the working diff to the retired family and separated concurrent peer additions such as `confirm_supply_nature_help` from S82 ownership. No production, test, locale, plan, execution record, staging area, or commit was changed by this review.

## Findings

### retired-family-ratchet-scope | medium | The claimed zero-reference proof does not cover the surface or vocabulary it attests

`src/cadrumo/core/tests/test_estado_casilla_oficial.py:48-71` is real source inspection rather than a tautological mirror, but its search boundary is materially narrower than S82. It scans Python only under `src/cadrumo`, YAML only under `src/cadrumo/locales`, and Python only under `dev/locales`; the rest of `dev` and non-Python/non-locale files under `src` are invisible. Its retired vocabulary contains only `OfficialBoxStatus`, `official_box_status`, and `classify_official_boxes`, while the same change also retires `_official_box_representation_channels` and the dynamic/TUI locale axis `official_status`. Reintroducing either omitted token, or placing any listed token in another `dev` tool, would leave both assertions green.

The current tree itself is clean: an independent exact sweep across all of `src` and `dev` found no occurrence of the five retired S82 identifiers, no retired status/classification path, no alias assignment, facade bridge, validation alias, or tolerant old-field input. The defect is the future structural ratchet and the execution record's unqualified claim that the strengthened test proves zero retired references. Because S82 explicitly requires structural proof before close, current-tree cleanliness does not make the incomplete gate sufficient.

## Recommendations

- Expand the S82 structural gate to derive and scan the complete requested `src` and `dev` trees over relevant text-bearing files, and include every retired identifier and path segment from this change: `OfficialBoxStatus`, `official_box_status`, `classify_official_boxes`, `_official_box_representation_channels`, `official_status`, `_official_box_status`, and `official_box_classification`. Keep constructed literals in the gate so the gate does not match its own inventory, retain the independent facade-identity assertions, and add a planted temporary-source bite proof showing an omitted-token regression is detected. Then correct the S82 execution claim to name the actual expanded boundary and re-run this review.

Verdict: **CHANGES REQUIRED**. The rename itself is semantically precise and destructive: one Spanish-stem core type and registry classifier remain, all live producer/filter/render/envelope consumers use them, stable external enum values alone are retained, locales are migrated in all four languages, and no compatibility surface exists. S82 should remain open solely because its asserted zero-retired-reference ratchet does not yet protect the complete rename.

## Verification

- Focused core, registry, application read-model, envelope, and TUI unit lane: 16 passed and 12 non-unit tests deselected in 57.96 seconds.
- Independent core owner/retired-family structural module: 2 passed in 18.02 seconds; inspection exposed the coverage gap above.
- Exact current-tree retired-symbol/path and alias/tolerance sweeps across `src` and `dev`: clean for the S82 family. Separate pre-existing `official_box_unpopulated` advisory vocabulary is a different, out-of-scope concept and was not misreported as S82 residue.
- Direct runtime facade proof: the new core and registry facade objects resolve to their canonical owner modules; retired facade attributes are absent; the review model has only `estado_casilla_oficial`; enum values remain exactly `addressed`, `represented_via_binding`, and `undefined`.
- Locale migration: `estado_casilla_oficial` label and three option keys exist in ca/en/es/hu, the f-string registry expands the new axis, the retired `official_status` key is absent, and locale diffs preserve the peer-owned `confirm_supply_nature_help` hunks.
- Repository locale scaffold: red only on separately existing profile, retired-verification, IVA-wallet, dependency-help, and ledger drift; it reports no missing or extra S82 key.
- Scoped Ruff: passed. Scoped BasedPyright: 0 errors, 0 warnings, 0 notes. Scoped `git diff --check`: clean.
- A supplemental broad dynamic-locale structural module did not finish within 120 seconds and was terminated without a result; it is not represented as green and is not needed for the finding or the focused S82 evidence above.
