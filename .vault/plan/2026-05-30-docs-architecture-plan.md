---
tags:
  - '#plan'
  - '#docs-architecture'
date: '2026-05-30'
modified: '2026-05-30'
tier: L4
related:
  - '[[2026-05-30-docs-architecture-research]]'
  - '[[2026-05-30-docs-architecture-adr]]'
  - '[[2026-05-30-docs-sphinx-build-adr]]'
  - '[[2026-05-30-docs-cli-conformance-adr]]'
---


# `docs-architecture` `documentation epic` plan

## Epic intent

Establish governed, conformance-gated documentation across the project's three English surfaces - repo-bootstrap markdown, in-source docstrings, and the generated Sphinx API plus CLI reference - with a declared seam for a future multilang user-help surface. The strategic goal is to make documentation truth codebase-state-driven and programmatically enforced from day one, with hard-cut gates. Project-management association: this epic is tracked factory-direct on the shared worktree branch - there is no GitHub issue; progress is tracked by this plan's Step completion and frequent explicit-pathspec commits on the shared tree, with peer-WIP safeguards on every edit. Timeline horizon: multi-wave, sequenced. Teams: the documentation PM plus parallel coder agents across the hexagonal subpackages for the remediation wave.

## Wave `W01` - tooling and scaffolding foundation

Install the enforcement toolchain and repair the docs build to a runnable, gate-ready state. Every later Wave depends on this one. Authorised by the conventions ADR and the Sphinx build architecture ADR.

### Phase `W01.P01` - enforcement tool dependencies and ruff D ruleset

Add the docstring and link enforcement tooling and enable the ruff D ruleset with Google convention and audience-scoping, per the conventions ADR hard-cut decision.

- [x] `W01.P01.S01` - add pydoclint, interrogate, and doc8 to the dev dependency group; `pyproject.toml`.
- [x] `W01.P01.S02` - enable the ruff D ruleset with pydocstyle convention google; `pyproject.toml`.
- [x] `W01.P01.S03` - add D-rule audience-scoping per-file-ignores for test and private modules matching interrogate; `pyproject.toml`.
- [x] `W01.P01.S04` - run the docstring lint gate and confirm it reports the expected backlog; `pyproject.toml`.
- [x] `W01.P01.S64` - pin the sphinx version floor so the nitpicky gate flag semantics stay stable across the fleet; `pyproject.toml`.

### Phase `W01.P02` - lint recipe restoration

Restore the lint recipe to green so the docstring gate can be wired onto a working recipe; the referenced relative-imports check script is currently absent.

- [x] `W01.P02.S05` - restore the relative-imports check script the lint recipe references; `scripts/check_relative_imports.py`.
- [x] `W01.P02.S06` - confirm the lint recipe runs green end to end; `justfile`.

### Phase `W01.P03` - documentation build recipes

Add the runnable docs build and docs-check entrypoints the pyproject comment promises but the justfile lacks.

- [x] `W01.P03.S07` - add the docs build recipe producing furo html; `justfile`.
- [x] `W01.P03.S08` - add the docs-check conformance recipe; `justfile`.
- [x] `W01.P03.S09` - confirm both documentation recipes run; `justfile`.
- [x] `W01.P03.S65` - wire doc8 rst formatting linting into the docs-check recipe; `justfile`.

### Phase `W01.P04` - sphinx config and toctree repair

Repair the inconsistent Sphinx config: fix the toctree, remove stale exclusions and warning suppression, drop the unconsumed markdown builder, and curate the nitpick baseline.

- [x] `W01.P04.S10` - repair the index toctree to reference only existing pages; `docs/index.rst`.
- [x] `W01.P04.S11` - delete the stale exclude_patterns entries for removed legacy docs; `docs/conf.py`.
- [x] `W01.P04.S12` - remove the myst xref warning suppression; `docs/conf.py`.
- [x] `W01.P04.S13` - drop the sphinx_markdown_builder extension; `docs/conf.py`.
- [x] `W01.P04.S14` - curate the nitpick_ignore baseline coupled to autodoc_mock_imports; `docs/conf.py`.
- [x] `W01.P04.S15` - confirm a nitpicky build surfaces only curated ignores; `docs/conf.py`.
- [x] `W01.P04.S66` - document the deferred multilang attachment point as a seam comment; `docs/conf.py`.
- [x] `W01.P04.S67` - seed the linkcheck_ignore baseline and add the advisory linkcheck lane; `docs/conf.py`.

## Wave `W02` - conformance harness

Build the programmatic gates that make every documentation surface conformant: the Sphinx link build gate, the module-to-stub correspondence test, the CLI reference generator, and the docs-versus-tree and schema-registry conformance tests. Depends on the tooling Wave; the remediation Wave brings the tree to green against these gates. Authorised by the Sphinx build and CLI conformance ADRs.

### Phase `W02.P05` - sphinx link build gate

Wrap a real nitpicky warnings-as-errors sphinx build as a hermetic, fast-lane-excluded test.

- [x] `W02.P05.S16` - add the nitpicky build-gate test building to tmp_path with offline intersphinx; `src/aeat/tests/test_docs_build.py`.
- [x] `W02.P05.S17` - mark the build-gate test for the docs-check lane outside the fast unit gate; `src/aeat/tests/test_docs_build.py`.
- [x] `W02.P05.S18` - confirm the build-gate test fails on an injected broken cross-reference; `src/aeat/tests/test_docs_build.py`.

### Phase `W02.P06` - module to stub correspondence

Pin the generated API surface to the module tree so a rename or new module fails the gate.

- [x] `W02.P06.S19` - add the module-to-stub set-correspondence test excluding test, tests, data, and private modules; `src/aeat/tests/test_docs_api_stubs.py`.
- [x] `W02.P06.S20` - confirm the correspondence test fails on a missing or orphan stub; `src/aeat/tests/test_docs_api_stubs.py`.

### Phase `W02.P07` - cli reference generator

Generate the CLI reference from the materialized command tree, committed and drift-tested, English pinned before first import.

- [x] `W02.P07.S21` - add the cli reference generator walking the materialized click tree with language pinned to en; `src/aeat/entrypoints/cli/_doc_reference.py`.
- [x] `W02.P07.S22` - generate and commit the cli reference pages under the docs cli subtree; `docs/cli/index.rst`.
- [x] `W02.P07.S23` - add the committed-versus-regenerated drift test on the docs-check lane; `src/aeat/entrypoints/cli/test_doc_reference_drift.py`.
- [x] `W02.P07.S24` - assert the generator detects and rejects any import-failure fallback subtree; `src/aeat/entrypoints/cli/_doc_reference.py`.

### Phase `W02.P08` - docs versus tree conformance

Assert the reference matches the live tree, the schema registry, and the accepted-surface contract, honest about partial migration.

- [x] `W02.P08.S25` - add the docs-versus-tree completeness test walking the live tree for non-retired commands; `src/aeat/entrypoints/cli/test_doc_reference_conformance.py`.
- [x] `W02.P08.S26` - add the schema-registry-versus-tree assertions honest about partial envelope migration; `src/aeat/entrypoints/cli/test_doc_reference_conformance.py`.
- [x] `W02.P08.S27` - assert retired surfaces appear only as redirect suggestions or as permanently removed; `src/aeat/entrypoints/cli/test_doc_reference_conformance.py`.
- [x] `W02.P08.S28` - confirm the conformance test fails on an undocumented live command; `src/aeat/entrypoints/cli/test_doc_reference_conformance.py`.

## Wave `W03` - full-tree docstring and link remediation

Bring the entire in-scope source tree to a true-to-reality documented state so the hard-cut gates pass green: every module a module docstring, every public symbol a signature-matching Google docstring, every cross-reference resolving. One Phase per hexagonal subpackage, parallelizable across coder agents. This Wave is the precondition for flipping the gates to blocking. Sized against the order-of-3800 raw interrogate findings, roughly 70 percent audience-exempt. Authorised by the conventions ADR.

### Phase `W03.P09` - remediate domain docstrings and links

Bring the domain subpackage to green against ruff D, pydoclint, interrogate, and the nitpicky build.

- [x] `W03.P09.S29` - bring every domain module to a true module docstring; `src/aeat/domain`.
- [x] `W03.P09.S30` - bring every domain public symbol to a signature-matching google docstring; `src/aeat/domain`.
- [x] `W03.P09.S31` - confirm ruff D, pydoclint, interrogate, and the nitpicky build pass for domain; `src/aeat/domain`.

### Phase `W03.P10` - remediate adapters docstrings and links

Bring the adapters subpackage to green against ruff D, pydoclint, interrogate, and the nitpicky build.

- [x] `W03.P10.S32` - bring every adapters module to a true module docstring; `src/aeat/adapters`.
- [x] `W03.P10.S33` - bring every adapters public symbol to a signature-matching google docstring; `src/aeat/adapters`.
- [x] `W03.P10.S34` - confirm ruff D, pydoclint, interrogate, and the nitpicky build pass for adapters; `src/aeat/adapters`.

### Phase `W03.P11` - remediate application docstrings and links

Bring the application subpackage to green against ruff D, pydoclint, interrogate, and the nitpicky build.

- [x] `W03.P11.S35` - bring every application module to a true module docstring; `src/aeat/application`.
- [x] `W03.P11.S36` - bring every application public symbol to a signature-matching google docstring; `src/aeat/application`.
- [x] `W03.P11.S37` - confirm ruff D, pydoclint, interrogate, and the nitpicky build pass for application; `src/aeat/application`.

### Phase `W03.P12` - remediate entrypoints docstrings and links

Bring the entrypoints subpackage to green against ruff D, pydoclint, interrogate, and the nitpicky build. This Phase owns docstring conformance for the CLI reference generator and conformance-test modules introduced in the conformance-harness Wave, and treats the module-docstring obligation on re-export shims such as the schemas re-export as a signal for the no-shims sweep rather than mechanical docstring-stuffing.

- [x] `W03.P12.S38` - bring every entrypoints module to a true module docstring; `src/aeat/entrypoints`.
- [x] `W03.P12.S39` - bring every entrypoints public symbol to a signature-matching google docstring; `src/aeat/entrypoints`.
- [x] `W03.P12.S40` - confirm ruff D, pydoclint, interrogate, and the nitpicky build pass for entrypoints; `src/aeat/entrypoints`.

### Phase `W03.P13` - remediate core docstrings and links

Bring the core subpackage to green against ruff D, pydoclint, interrogate, and the nitpicky build.

- [x] `W03.P13.S41` - bring every core module to a true module docstring; `src/aeat/core`.
- [x] `W03.P13.S42` - bring every core public symbol to a signature-matching google docstring; `src/aeat/core`.
- [x] `W03.P13.S43` - confirm ruff D, pydoclint, interrogate, and the nitpicky build pass for core; `src/aeat/core`.

### Phase `W03.P14` - remediate diagnostics docstrings and links

Bring the diagnostics subpackage to green against ruff D, pydoclint, interrogate, and the nitpicky build.

- [x] `W03.P14.S44` - bring every diagnostics module to a true module docstring; `src/aeat/diagnostics`.
- [x] `W03.P14.S45` - bring every diagnostics public symbol to a signature-matching google docstring; `src/aeat/diagnostics`.
- [x] `W03.P14.S46` - confirm ruff D, pydoclint, interrogate, and the nitpicky build pass for diagnostics; `src/aeat/diagnostics`.

### Phase `W03.P15` - remediate locales docstrings and links

Bring the locales subpackage to green against ruff D, pydoclint, interrogate, and the nitpicky build.

- [x] `W03.P15.S47` - bring every locales module to a true module docstring; `src/aeat/locales`.
- [x] `W03.P15.S48` - bring every locales public symbol to a signature-matching google docstring; `src/aeat/locales`.
- [x] `W03.P15.S49` - confirm ruff D, pydoclint, interrogate, and the nitpicky build pass for locales; `src/aeat/locales`.

## Wave `W04` - user-doc rewrite via the documentation pipeline

Author the English repo-bootstrap surface through the documentation pipeline researcher-author-editor flow, and re-establish the bootstrap-presence pin the superseded docs-rewrite ADR left as an interim obligation. Depends on the conformance harness so authored pages build green. Authorised by the conventions ADR.

### Phase `W04.P16` - rewrite the bootstrap readme

Replace the self-flagged out-of-date README via the documentation pipeline so it reflects shipped features.

- [x] `W04.P16.S50` - rewrite the stale readme through the documentation pipeline researcher author editor flow; `README.md`.
- [x] `W04.P16.S51` - confirm the readme reflects shipped features and passes editorial review; `README.md`.

### Phase `W04.P17` - author the narrative bootstrap pages

Author the getting-started and architecture pages the toctree depends on, through the documentation pipeline, with domain-driven filenames.

- [x] `W04.P17.S52` - author the getting-started narrative page through the documentation pipeline; `docs/getting-started.md`.
- [x] `W04.P17.S53` - author the architecture narrative page through the documentation pipeline; `docs/architecture.md`.
- [x] `W04.P17.S54` - confirm both narrative pages build under the nitpicky gate and pass editorial review; `docs/getting-started.md`.

### Phase `W04.P18` - bootstrap presence pin

Re-establish the deleted bootstrap-presence conformance test against the current surfaces, discharging the docs-rewrite interim obligation.

- [x] `W04.P18.S55` - add the bootstrap-presence conformance test re-establishing the deleted pin; `src/aeat/tests/test_docs_bootstrap.py`.
- [x] `W04.P18.S56` - confirm the pin fails when a bootstrap document is removed; `src/aeat/tests/test_docs_bootstrap.py`.

## Wave `W05` - editorial workflow and rollout

Codify the documentation editorial workflow, flip every gate to blocking once the tree is green, and close the epic with a fresh-context honesty review. Depends on every prior Wave being complete. Authorised by the conventions ADR and the campaign-close honesty-review rule.

### Phase `W05.P19` - codify the editorial workflow

Document the researcher-author-editor authoring workflow as a domain-named contributor guide.

- [x] `W05.P19.S57` - codify the documentation authoring and editorial review workflow through the documentation pipeline; `docs/authoring-guide.md`.
- [x] `W05.P19.S58` - confirm the authoring guide builds under the nitpicky gate and passes editorial review; `docs/authoring-guide.md`.

### Phase `W05.P20` - flip gates to blocking

Wire docs-check into the standing gate set and make the docstring, correspondence, and CLI conformance tests blocking now the tree is green.

- [x] `W05.P20.S59` - wire docs-check into the standing gate set; `justfile`.
- [x] `W05.P20.S60` - make the docstring, correspondence, and cli conformance tests blocking in the unit gate; `pyproject.toml`.
- [x] `W05.P20.S61` - confirm a full green run across lint, docs-check, and the suite; `justfile`.

### Phase `W05.P21` - epic closure honesty review

Run a fresh-context honesty review against the closure summary before declaring the epic structurally complete, per the campaign-close rule.

- [x] `W05.P21.S62` - run a fresh-context honesty review against the epic closure summary; `.vault/audit`.
- [x] `W05.P21.S63` - track honesty-review findings as new steps with verification gates; `.vault/plan/2026-05-30-docs-architecture-plan.md`.

## Wave `W06` - build-time CLI reference migration

Replace the generate-and-commit CLI reference (supersedes W02.P07 and decisions 1-2 of the CLI-conformance ADR) with a build-time projection of the live command tree rendered from the English tr() help by the existing flat renderer, run in a builder-inited hook into a gitignored docs/cli. Retire the committed pages and the byte-for-byte drift test; conformance shifts to rendering the reference in a fresh English-pinned subprocess.

### Phase `W06.P22` - build-time flat-renderer projection

Pin English output language before any project import, render the CLI reference from the materialised command tree via the existing flat renderer in a builder-inited hook into a gitignored docs/cli, retire the committed pages and drift test, reframe the conformance test to render into a temporary directory, and confirm the offline nitpicky build renders the reference green.

- [x] `W06.P22.S68` - Pin English output language and render the CLI reference from the live command tree in a builder-inited hook; `docs/conf.py`.
- [x] `W06.P22.S69` - Gitignore the build-time CLI reference directory and retire the committed pages and byte-for-byte drift test; `.gitignore`.
- [x] `W06.P22.S70` - Reframe the CLI reference conformance test to render into a fresh English-pinned temporary directory rather than reading committed pages; `src/aeat/entrypoints/cli/test_doc_reference_conformance.py`.
- [x] `W06.P22.S71` - Stop rewriting __module__ on re-exported json-contract primitives so the build-time CLI import no longer drops them from autodoc; `src/aeat/entrypoints/cli/_schemas.py`.
