---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S278'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S278 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Give the namespace-registry adoption gate an anti-vacuity floor and every production root, since it currently finds zero subjects and asserts an empty list and ## Scope

- `src/cadrumo/application/tests/test_namespace_registry_adoption.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Give the namespace-registry adoption gate an anti-vacuity floor and every production root, since it currently finds zero subjects and asserts an empty list

## Scope

- `src/cadrumo/application/tests/test_namespace_registry_adoption.py`

## Description

- Diagnose the vacuity: the gate found zero subjects across ~880 production files for two compounding reasons — its literal-detection prefix was still `aeat.` after the product rename moved every namespace to `cadrumo.`, and its guarded roots omitted `adapters/persistence`, where the registry declaration file lives. Every consumer now binds to the registry constant, so the only production namespace literals are the registry's own 64 declarations.
- Update the detection prefix to a named `_NAMESPACE_LITERAL_PREFIX = "cadrumo."` constant and route `_append_literal` through it.
- Expand the guarded roots to every production root (scan the whole `src/cadrumo` production tree), so a consumer re-introducing a drifted literal anywhere is caught.
- Add the anti-vacuity floor: assert at least 40 namespace-position literals were scanned, so a re-drift of the prefix or roots reds instead of passing an empty check.
- Add a hostile-input probe asserting an unregistered `cadrumo.`-prefixed namespace literal is extracted and flagged as an offence.
- Add a prefix-coherence probe asserting the registry's own namespaces still begin with the detection prefix, so the next such rename reds immediately rather than silently emptying the gate.

## Outcome

Verified at HEAD `1437055950f5b8f4082d323578294fc32ad1d9fe`.

Command: `uv run --no-sync pytest -p no:randomly -m "unit or integration" -n0 -q --no-header src/cadrumo/application/tests/test_namespace_registry_adoption.py` — `3 passed in 19.79s`.

Ground-truth: 64 `cadrumo.`-prefixed namespace-position literals across the production tree, all registry-declared, all in the registry declaration file; zero under the old `aeat.` prefix.

Mutation-check per added assertion (throwaway rebind probe; real passes, defect fails):

- floor `len(scanned) >= 40`: real_passes=True, stale-`aeat.`-prefix defect scans 0 → defect_fails=True.
- coherence `registry namespaces begin with prefix`: real_passes=True, `aeat.` prefix matches 0 → defect_fails=True.
- hostile-input `offences == [bogus, bogus]`: real_passes=True, registry-accepts-everything defect → offences empty → defect_fails=True.

All three namespace mutation probes reported OK. `ruff check` and `ruff format --check` clean on the touched file.

## Notes

The registry declaration file's own literals are the floor subjects: with all consumers bound to the constant, they are the only production namespace literals left. They are self-referential (trivially registry-declared), but they give the non-zero floor while the expanded roots make the gate a live tripwire for any consumer that re-introduces a drifted literal, and the hostile probe proves the offence cross-check discriminates. This step also satisfies the namespace-adoption portion of `S283`.
