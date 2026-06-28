---
tags:
  - '#adr'
  - '#docs-architecture'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - "[[2026-05-30-docs-architecture-research]]"
  - "[[2026-04-12-docs-rewrite-adr]]"
  - "[[2026-04-17-relative-imports-adr]]"
  - "[[2026-04-25-json-output-contract-adr]]"
---



# `docs-architecture` adr: `documentation surface taxonomy and conventions` | (**status:** `accepted`)

This is the first of three ADRs in the documentation epic. It sets the
surface model and authoring conventions that the Sphinx build
architecture ADR and the CLI documentation conformance ADR build on. It
supersedes the 2026-04-12 docs-rewrite ADR.

## Problem Statement

The project's documentation has grown across several surfaces with no
governing decision and conflicting authority. The only accepted
documentation ADR — the 2026-04-12 docs-rewrite ADR — scoped a
markdown-only README plus two narrative pages and a single smoke test,
and explicitly deferred API docs, a docs site, and translations as out of
scope. Since then a full Sphinx pipeline has appeared on disk (a `furo`
HTML build, autodoc over the package, a 147-file API stub tree, a
markdown builder) with no ADR behind it, while the smoke test it mandated
was deleted and the two narrative pages it created were removed. The
result is an authority conflict: the accepted ADR's scope statement
directly contradicts the code on disk, and there is no codified answer to
the foundational questions — what documentation surfaces exist, who each
serves, in what language, with what source of truth, and under what
authoring conventions.

Without that taxonomy and a convention baseline, documentation drifts
from the code (the README is already self-flagged out of date), and no
programmatic gate can be meaningful because there is no agreed definition
of what "conformant documentation" is. This ADR establishes the surface
model, the authoring conventions, and the principle that documentation
truth is derived from codebase state — the foundation the rest of the
epic enforces.

## Considerations

The `docs-architecture` research established the relevant landscape. Key
factors:

- **Distinct audiences and languages.** Repo-bootstrap documentation
  serves a general, possibly non-technical operator; in-source and
  generated API documentation serve contributors. These are different
  surfaces with different language postures, and conflating them (as the
  prior framing did) produces incoherent decisions.
- **Existing, reusable infrastructure.** `conf.py` already assumes
  Google-style docstrings via napoleon; the CLI already localizes help
  through `tr()` against the locale catalogue; the
  `operator_surface` contract and the `SCHEMA_REGISTRY` in
  `json_contract.py` already expose machine-readable descriptions of the
  command surface. Documentation conventions should ride these, not
  duplicate them.
- **Enforcement tooling.** For docstring presence and Google-style
  conformance, `ruff`'s pydocstyle (`D`) ruleset with
  `convention = "google"` is the fast lint gate; for docstring-versus-
  signature accuracy, `pydoclint --style=google` is the dedicated tool;
  for coverage, `interrogate` provides a percentage gate. These are
  distinct guarantees — presence is not style, and neither is accuracy.
- **Adjacent accepted ADRs.** The relative-imports ADR constrains how
  autodoc imports the package (resolved via `sys.path` insertion of
  `src/` plus a mock-imports allowlist); the json-output-contract ADR
  defines the `--json` envelope, exit-code table, and TTY contract that
  CLI documentation must reflect. This ADR references both rather than
  re-deciding them.

## Constraints

- **No lint skips, no baselines, no tautological tests.** The repository
  prohibits suppressing lint or type findings and forbidding mock/skip
  shortcuts. Enforcement decided here is therefore hard-cut, not phased.
- **CLI help is a runtime-only, localized surface.** Help text is
  resolved by `tr()` at definition time against the locale catalogue.
  Documentation generation and conformance must NOT reuse those locale
  ymls as a documentation translation source; the CLI `--help` surface
  stays technical and runtime-only.
- **English-first.** The multilang user-facing help/docs surface is not
  yet implemented; this ADR declares it as a deferred surface and keeps
  all three active surfaces English-only.
- **Autodoc import strategy is fixed by the relative-imports mandate.**
  Any convention touching autodoc must remain compatible with
  `sys.path`-based import and the `autodoc_mock_imports` allowlist.
- **Conformance tests are colocated under `src/aeat/`**, never in a
  top-level `tests/` package (which the architecture-boundaries rule
  forbids). Repo-level invariant tests live under `src/aeat/tests/`, and
  surface-specific tests sit beside the code they govern (for example the
  existing CLI invariant tests under `src/aeat/entrypoints/cli/`);
  documentation conformance tests follow the same placement.

## Implementation

This ADR decides the following. Concrete build wiring (the Sphinx nitpick
baseline, the `-n -W` build gate, the `just` recipes, the module-to-stub
correspondence test) is deferred to the Sphinx build architecture ADR;
CLI-specific documentation conformance is deferred to the CLI
documentation conformance ADR.

**1. Documentation surface taxonomy.** Documentation is partitioned into
four surfaces, each with a fixed audience, language posture, and source
of truth:

| Surface | Audience | Language | Source of truth |
| :------ | :------- | :------- | :-------------- |
| Repo bootstrap docs (markdown) | General / non-technical operator | English only | Hand-authored, pinned by a conformance test |
| In-source docstrings | Contributor / technical | English only | Google-style docstrings under `src/aeat/` |
| Generated Sphinx API docs | Contributor / technical | English only | Autodoc over docstrings plus narrative pages |
| User help / user-docs page | General operator | Multilang | DEFERRED — not yet implemented; NOT driven by the CLI `tr()` ymls |

The first three are in scope and English-only. The fourth is declared
here as a deliberate seam so later work has a named home, but its
implementation, language workflow, and translation source are out of
scope for this epic.

**2. Codebase-state-as-truth principle.** Documentation truth is derived
from and verified against codebase state — the materialized command
tree, in-source docstrings, the `SCHEMA_REGISTRY`, and the
`operator_surface` contract — never hand-maintained in isolation and
hoped to stay correct. Every surface either is generated from code or is
pinned by a conformance test that fails when it drifts from code.

**3. Authoring conventions.** In-source documentation uses Google-style
docstrings (matching the existing napoleon configuration) and the Sphinx
cross-reference and module-linking vocabulary (`:mod:`, `:class:`,
`:func:`, `:py:obj:` and peers) as the standard for linking symbols.
Repo-bootstrap markdown follows the existing conventional-commit and
operator-voice conventions and is written for a non-technical reader.

User-facing narrative documentation (the repo-bootstrap surface) is
authored through the project's documentation pipeline — a
researcher/author/editor separation in which context is gathered first,
the draft is written only from gathered context, and an editorial review
runs last — rather than written ad hoc.

**3a. Documentation layout and filenames are domain-driven, never
framework-driven.** The `docs/` folder structure and every documentation
filename derive from the documentation's own domain — the surfaces, the
package layout, and user-facing topics. They MUST NOT encode any
documentation-framework or project-management metadata: no vaultspec
wave / phase / step identifiers, no ADR or plan references, no agent,
campaign, or milestone labels in any documentation path or filename. This
is the source-hygiene rule applied to the documentation tree — the layout
must remain true after the current epic's plan structure changes, because
that structure is metadata, not content. (The dated, identifier-bearing
filenames of `.vault/` records are a separate, framework-internal surface
governed by the vaultspec templates and are explicitly not the
documentation tree this rule covers.)

**4. Every mandate is bound to a programmatic check.** A style mandate
with no enforcing gate is decoration. Each convention above is bound to
a concrete check (enumerated next), and a convention without a passing
gate is treated as not-yet-implemented rather than aspirational prose.

Within this ADR, only the in-source docstring surface is actually gated
(by the `ruff`, `pydoclint`, and `interrogate` checks in decision 5). The
cross-reference-vocabulary gate (the nitpicky Sphinx build), the
generated-API-docs conformance test (module-to-stub correspondence), and
the bootstrap-markdown presence test are *declared* here as obligations
but *enforced* by the Sphinx build architecture ADR and the CLI
documentation conformance ADR. Those surfaces are therefore
declared-not-yet-enforced until those ADRs land; this ADR does not claim
otherwise.

**5. Hard-cut enforcement from day one.** The following are enabled
together, with no baselines, ratchets, or suppression of real defects:

- `ruff` pydocstyle: select the `D` ruleset with
  `[tool.ruff.lint.pydocstyle] convention = "google"`. Module-file-level
  coverage is guaranteed by `D100` (module docstring) and `D104`
  (package `__init__` docstring); class and public-function presence by
  `D101` and `D103`. This is the fast lint gate.
- `pydoclint --style=google`: verifies that documented arguments,
  returns, and raises match the actual signature — the symbol-level
  true-to-reality guarantee.
- `interrogate`: the public-symbol docstring-coverage gate (its
  configuration already exists; the tool becomes a declared
  dependency).

**Audience-scoping is not a skip.** The hard-cut "no skips" stance
prohibits suppressing a real defect on an in-scope symbol; it does not
prohibit scoping the gate to the surface it governs. Three scoping
decisions are fixed here so they are not improvised at remediation time:

- *Colocated test modules* (`test_*.py`, `_test_*.py`, `tests/**`) are
  presence-exempt from the `D` gate, matching their existing exclusion
  from autodoc and from `interrogate`. They are not a contributor-facing
  documentation surface.
- *Private and magic symbols* (`_`-prefixed, dunder) follow the
  public/private boundary `interrogate` already uses (`ignore-private`,
  `ignore-semiprivate`, `ignore-magic`); the `D` gate is configured to
  the same public surface so the two tools agree on scope.
- *No content allowlist.* Unlike the i18n `_intentional_identical`
  ceiling, there is no docs waiver: every in-scope symbol carries a real,
  signature-true docstring. The only exemptions are the audience-scoping
  ones above. The Typer command modules that already carry a `B008`
  per-file-ignore need no `D`-specific accommodation and are not
  exempted.

The Sphinx cross-reference validity gate (nitpicky `-n -W`) is part of
the same hard-cut posture, but — like the API-docs and bootstrap-markdown
conformance tests — its wiring is specified in later ADRs (see decision 4
on declared-versus-enforced).

**6. Editorial and review workflow.** Documentation changes follow a
researcher / author / editor separation for narrative surfaces (gather
context, write from gathered context, edit last), and all surfaces pass
their bound conformance gates before merge. Documentation that changes a
user-facing surface updates the corresponding bootstrap page in the same
change.

## Rationale

A surface taxonomy is the prerequisite for every other documentation
decision: language, source of truth, and enforcement all differ by
surface, and the prior ADR's incoherence came precisely from treating
documentation as one undifferentiated thing. Separating the operator
surfaces (English markdown, multilang help) from the contributor surfaces
(docstrings, API docs) lets each be governed correctly.

Hard-cut enforcement is chosen over phased adoption because the
repository already forbids lint skips and baselines, and because a phased
gate that tolerates existing violations cannot guarantee conformance "from
day one" — which is the stated goal. The cost (a full-tree remediation)
is real but bounded and parallelizable, and it is paid once; the benefit
is that drift becomes impossible afterward rather than merely discouraged.

The toolchain is chosen to match each distinct guarantee: `ruff` for
fast presence and style because it already runs in the lint gate;
`pydoclint` for signature accuracy because `ruff` does not verify that
docstrings describe the real signature; `interrogate` for the coverage
percentage. Reusing the `operator_surface` contract and `SCHEMA_REGISTRY`
as documentation sources, rather than re-authoring command descriptions,
is what makes codebase-state-as-truth enforceable rather than aspirational.

Superseding the docs-rewrite ADR (rather than amending it) resolves the
standing authority conflict cleanly: that ADR's scope statement is now
false on disk, and leaving it nominally accepted alongside contradictory
code is the drift this epic exists to end.

## Consequences

- **A full-tree remediation is required before the gates flip on.** A
  hard cut means a green build is a merge precondition, so the epic must
  bring every module to a true-to-reality module docstring and every
  public symbol to a signature-matching Google-style docstring as a
  dedicated remediation wave in the plan. This is large but
  parallelizable.
- **New dev dependencies.** `pydoclint` and `interrogate` are added to
  the dev dependency group; `ruff` and `sphinx` are already present.
- **The docs-rewrite ADR is superseded.** Its surviving intent — that the
  bootstrap documentation files exist and are pinned by a test — is
  re-established under this regime by the conformance tests specified in
  the later ADRs, against the current Sphinx reality rather than the
  removed markdown-only one.
- **A latent build-suppression problem is surfaced for the next ADR.**
  `conf.py` currently silences cross-reference warnings and mock-imports
  heavy dependencies, which would hide the very defects the link gate
  must catch. Removing that suppression and curating a nitpick baseline
  is called out here and decided in the Sphinx build architecture ADR.
- **The multilang user-docs surface has a named seam.** Future work has a
  defined home and an explicit constraint (not driven by the CLI locale
  ymls), without committing this epic to building it.
- **The remediation scale is non-trivial.** The audit that configured
  `interrogate` reported on the order of 3800 missing-docstring findings,
  roughly 70% of them private, magic, nested, or test symbols that the
  audience-scoping above exempts — leaving an estimated public residual on
  the order of a thousand symbols, plus a module docstring for every file.
  The plan must size the remediation wave against that surface, not assume
  it is small.
- **The lint gate inherits a pre-existing broken reference.** The
  docstring lint gate is wired into the existing lint recipe and commit
  hook, which currently reference `scripts/check_relative_imports.py` — a
  script absent from disk. Bringing the lint recipe green (resolving that
  pre-existing reference) is a precondition for the gate and is flagged
  for the plan; it is not fixed by this ADR.
- **A module-docstring obligation falls on re-export shims.** `D100`
  applies to every module, including re-export shims such as the current
  `_schemas.py`. This ADR carves no exception; the obligation is an
  additional signal for the standing no-shims sweep rather than a reason
  to exempt.
- **The supersession retains an interim pin.** Because the replacement
  bootstrap-markdown conformance test is deferred to a later ADR,
  superseding the docs-rewrite ADR would otherwise open a window with no
  pin on the bootstrap files. The docs-rewrite ADR is marked deprecated,
  but its bootstrap-presence intent is retained as an explicit interim
  obligation: the requirement that the bootstrap documents exist remains
  in force until the later conformance test re-establishes the pin.
- **Conventions become testable, not advisory.** Because every in-scope
  mandate is bound to a gate (or to an explicitly declared, deferred one),
  the project's documentation conventions are now encoded both here and in
  executable checks, which is the durable form this epic was chartered to
  produce.
