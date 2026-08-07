---
tags:
  - '#adr'
  - '#dev-harness-bleed'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:799709df191211ecaa541bd454c5a5f56c8dfb6ce94e5aafefdeb45628c2b8d8'
related:
  - '[[2026-06-14-docs-tooling-separation-adr]]'
  - '[[2026-06-14-docs-tooling-separation-research]]'
---
# `dev-harness-bleed` adr: `locales tooling boundary` | (**status:** `proposed`)

## Problem Statement

`src/cadrumo/locales/` is a mixed package. Five artefacts are genuine runtime
data: `en.yml`, `es.yml`, `ca.yml`, `hu.yml` and `_intentional_identical.json`,
loaded by the renderer at `src/cadrumo/core/i18n/_render.py:128` and `:491`. Seven
modules are dev/CI catalogue-maintenance tooling that ships in the wheel with no
runtime importer: `manager.py`, `_ast_scanner.py`, `_registry_scanner.py`,
`_fstring_registry.py`, `_status.py`, `cli.py`, `__main__.py`, plus the package
facade `__init__.py`, which re-exports only tooling symbols, and the six tooling
tests under `locales/tests/`.

An accepted decision already governs this class: documentation tooling stays
outside the production package, and the identical data-stays / code-moves split
was applied to the Terminology Handbook (`2026-06-14-docs-tooling-separation-adr`).
This is the sole remaining dev-harness-in-src instance of that shape. Sweeps
found no argparse, click or typer entrypoint outside `entrypoints/cli/` except
`locales/cli.py`, and the only `__main__.py` and `cli.py` under `src/cadrumo`
outside `entrypoints/` are both in `locales/`.

A decision is needed rather than a direct relocation because the naive move reds
its own verification gate, and because the move forces a boundary question the
terminology precedent never faced: three unrelated src subpackages import this
tooling as a general-purpose test utility.

## Considerations

- Severity is code weight, not security. Neither this tooling nor the second
  instance named below reads outside the wheel, executes untrusted input, or
  exposes anything a readable `.py` wheel does not already expose.
- Packaging needs zero edits: `pyproject.toml` ships `src/cadrumo` wholesale via
  a single package entry, with no include or exclude naming these modules.
- `locales/cli.py` makes 26 `tr()` calls localising its own operator output, and
  its `cli.*` keys are present in all four shipped catalogues.
- `LocaleManager.get_codebase_keys()` scans the source tree with `rglob("*.py")`
  over src only, at `src/cadrumo/locales/manager.py:198`.
- The canonical tree-wide parity gate is itself a consumer:
  `src/cadrumo/tests/test_parity.py:8-13` imports the `locales` facade, the CLI
  app and `locales.manager`, and pins the logger name
  `"cadrumo.locales._ast_scanner"` at `:585`.
- Two unrelated domains use the tooling as a utility:
  `src/cadrumo/adapters/persistence/storage/tests/test_hardening_convention_guards.py:13`,
  which reaches it by a five-dot relative import of the private `manager`
  submodule, and
  `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py:47`.
- Two further gates consume it:
  `src/cadrumo/tests/test_registry_locale_key_parity.py:26-27` and
  `src/cadrumo/tests/test_locale_translation_honesty.py:26`.
- `src/cadrumo/core/errors/registry/_core.py:451` registers the string
  `"cadrumo.locales.manager.LocaleError"` against `FAIL_LOCALE_MANAGER`.
  `LocaleError` is raised only inside `locales/manager.py` and `locales/cli.py`,
  never on a path reachable from the renderer or any operator command, and no
  production module imports it.
- The `aeat-locales-cli` rule mandates the `python -m cadrumo.locales` verbs
  verbatim as the only sanctioned authoring path, so the move changes a mandated
  operator command.
- Four consumers reference only the catalogue data or the CLI command string and
  are unaffected by a code move: the data-directory resolution at
  `src/cadrumo/application/export/tests/test_tabular.py:176`, and the
  assertion-text literals in `test_locale_coverage_inventory.py:94`,
  `test_locale_coverage_hardened_errors.py:84` and
  `application/wizard/tests/test_flow_description_keys.py:39`.

## Considered options

- **Leave the package as-is.** Zero risk, but leaves dev tooling in the shipped
  wheel and the accepted tooling-separation boundary inconsistently applied.
  Rejected as the standing goal.
- **Relocate the seven modules and the six tooling tests to `dev/locales/`,
  keeping the catalogues and the allowlist JSON in `src/cadrumo/locales/`.**
  Mirrors the terminology precedent exactly. Chosen, subject to the three
  sub-decisions below, each of which the naive form of this option gets wrong.
- **De-ship the catalogue data as well.** Rejected: the renderer loads the YAML
  at runtime through `importlib.resources`, so the data is production input, not
  tooling. This is not the terminology situation, where the data was doc-build
  input.
- **Leave a thin `cadrumo.locales.__main__` in src dispatching to the moved
  implementation, preserving the mandated CLI surface.** Rejected. This is a
  compatibility shim in the exact sense the no-shims rule forbids: its only
  purpose is keeping an old invocation path alive after the canonical home moved,
  and it re-ships an entrypoint module in the wheel, defeating the decision's own
  goal to avoid editing one rule and five literal strings. The honest alternative
  is to change the mandated command and sweep it, which the carry list below
  already requires.

### Sub-decision A: the tooling CLI's own localisation

`locales/cli.py` localises itself from the four shipped catalogues. Move it to
dev and its 26 `cli.*` keys lose their in-src caller; the scanner at
`manager.py:198` no longer sees them, and the parity gate flags them as
orphaned. The relocation fails its own check. Keeping them is also wrong on the
merits: it leaves dev-tool UI strings inside shipped runtime data, the mirror
image of the bleed being fixed.

- **A1, de-localise the tooling CLI:** replace the 26 `tr()` calls with plain
  English strings and remove the `cli.*` keys from all four catalogues.
- **A2, give the tooling its own catalogue under dev:** preserves translated
  dev-tool output at the cost of a second catalogue mechanism, a second parity
  surface, and a scanner that must cover two source roots.
- **A3, widen the scanner to cover dev too:** keeps the keys in the shipped
  catalogues, which is the outcome this decision exists to prevent.

**Recommendation: A1.** The tooling's audience is contributors, who already read
English-only output from every other dev tool. A2 buys translated dev output by
permanently doubling the catalogue and parity machinery this repo has repeatedly
consolidated; A3 keeps shipping dev strings to taxpayers. A1 is the only option
leaving exactly one catalogue mechanism and one shipped catalogue set.

### Sub-decision B: src gates that import the tooling

This is the contentious one, and it should not be papered over. Five test
modules import the tooling, and two of them, the storage hardening guard at
`test_hardening_convention_guards.py:13` and the CLI suggestion conformance gate
at `test_suggestion_command_conformance.py:47`, do so from unrelated domains,
treating `LocaleManager` as a general utility. A third, `test_parity.py`, is the
canonical tree-wide parity gate itself.

- **B1, move every consumer gate to dev as well.** Clean boundary: nothing in src
  imports dev. But it relocates the canonical locale parity gate out of the
  production test tree, and the two unrelated-domain consumers are not locale
  gates at all: they are storage and CLI conformance gates that happen to need a
  key inventory. Filing them under `dev/locales/` puts them under the wrong owner.
- **B2, accept src tests importing a dev utility.** Pragmatic, and test-only. But
  it is the same boundary violation in the opposite direction, and it makes the
  production test suite unrunnable from a wheel-only install.
- **B3, split the tooling.** Extract the key-inventory scanning the cross-domain
  consumers actually need into a small production-resident module, and move only
  the catalogue-mutation tooling (`cli.py`, `__main__.py`, and the scaffold and
  audit half of `manager.py`) to dev. Each src gate then imports a production
  module, and dev holds only what mutates catalogues.

**Recommendation: B3, with B1 as the fallback.** The two unrelated-domain
consumers are the tell: a key inventory over the source tree is a legitimate
production-adjacent capability that three domains independently reached for, and
the honest reading is that `LocaleManager` fuses two responsibilities, reading
the catalogues and codebase keys (which gates need, in src) and mutating the
catalogues (dev-only). B3 draws the boundary where the responsibility actually
splits rather than where the directory currently is. It is more work than B1 and
requires judging how much of `manager.py` and the three scanners falls on each
side; if that split proves not to be clean, B1 is correct and B2 is not. B2
trades a visible violation for an invisible one.

Note that `test_hardening_convention_guards.py:13` reaches the tooling by a
five-dot relative import of the private `locales.manager` submodule, a
cross-package private import that already violates the facade rule independently
of this decision.

### Sub-decision C: the dead central error-registry entry

`src/cadrumo/core/errors/registry/_core.py:451` maps the string
`"cadrumo.locales.manager.LocaleError"` to `FAIL_LOCALE_MANAGER`. Because the
coupling is a string, a move breaks it silently: no import error, just a
permanently dangling key.

- **C1, delete the entry**, its `errors.fail.fail_locale_manager` message key and
  the four catalogue strings behind it.
- **C2, keep the entry** and make `LocaleError` genuinely reachable from an
  operator command.

**Recommendation: C1.** The entry is already dead at HEAD: `LocaleError` is
raised only in the two tooling modules and no production path reaches it. C2
would require inventing operator reachability for a contributor tool. Under A1
the four catalogue strings go the same way as the `cli.*` keys, so C1 and A1 are
one sweep.

## Constraints

- No parent-feature or third-party risk; every dependency is in-tree.
- The relocation must be atomic: one commit per symbol with an explicit
  pathspec, a clean collect-only run immediately before, and no bridging
  re-export at any point.
- The shared worktree carries concurrent peer work in `test_parity.py`, package
  facades and the catalogues, so the commit shape must assume contention.
- Sub-decision B3's scope cannot be fixed from this record alone: it depends on
  how cleanly `manager.py` separates its read half from its mutate half. That
  assessment is a precondition of executing B3, and B1 is the sanctioned fallback
  if the split is not clean.

## Implementation

Land the boundary in the order A, then C, then B, then the relocation, because
each earlier sub-decision removes a blocker from the later one. De-localise the
tooling CLI and drop its `cli.*` keys from the four catalogues, which frees the
scanner-scope constraint. Delete the dead error-registry entry and its message
key in the same sweep, which removes the silent string coupling. Then resolve the
read-versus-mutate split, or fall back to relocating the gates, so that at the
moment of the move no src module, production or test, names the tooling. Only
then relocate the mutation tooling and its six tests to `dev/locales/`, updating
the facade, the mandated CLI invocation and every literal naming it.

The catalogues, `_intentional_identical.json` and their `importlib.resources`
load path do not move and are not touched.

## Rationale

The decision follows `2026-06-14-docs-tooling-separation-adr` in shape, code out
and data stays, with the tooling reading the data through a public boundary. That
precedent is the knockout argument for the top-level choice: the boundary is
already accepted policy and this is its last unapplied instance.

The sub-decisions are where this record adds what the precedent does not cover.
Terminology tooling had no self-localisation, no cross-domain test consumers and
no entry in the central error registry; locales tooling has all three, and each
turns a mechanical move into a failing gate or a silent dangling reference.
Recommending A1 and C1 is straightforward: both delete dead or misfiled weight
and reduce the number of mechanisms. B3 is recommended with visible reservation.
It is the only option that does not resolve the boundary question by choosing
which direction to violate it in, but it is also the only one whose scope this
record cannot pin, which is why B1 is named as the fallback rather than left
implicit.

Five agents independently re-derived this fact set before it was written down
once; that cost is itself part of the argument for the record.

## Consequences

- The production wheel stops carrying catalogue-maintenance tooling; the
  dev-harness boundary is uniformly applied and this instance is closed.
- Under A1 the tooling CLI's operator output becomes English-only. Contributors
  lose translated dev-tool messages; taxpayers stop receiving dev-tool strings in
  their shipped catalogues.
- Under C1 `FAIL_LOCALE_MANAGER` leaves the central error catalogue. Nothing
  operator-facing changes, because nothing operator-facing could raise it.
- Under B3 the production test tree keeps its locale gates and gains a small
  production-resident key-inventory module. Under the B1 fallback the canonical
  parity gate moves to dev, a real loss of locality to be weighed at execution
  time.
- The mandated authoring command changes, so the `aeat-locales-cli` rule changes
  with it.

### Same-commit carry list

Each item breaks something if it lags the move; none is optional, and none is
solved by this record.

- Regenerate the eight autodoc stubs matching `docs/api/cadrumo.locales*.rst`
  with the apidocs scaffold verb. Orphaned stubs hard-crash the nitpicky Sphinx
  build. Stage only stubs whose added lines name these modules.
- Delete the now-moot coverage allowlist entry for
  `src/cadrumo/locales/__main__.py` at
  `src/cadrumo/tests/test_every_module_has_test_coverage.py:80-81`.
- Repoint the logger-name pin at `src/cadrumo/tests/test_parity.py:585`. This one
  breaks silently: the log capture stops asserting against the right logger
  rather than erroring.
- Edit the mandate at `.vaultspec/rules/aeat-locales-cli.md` and propagate with
  the spec sync verb; never the generated `.claude/` copy.
- Sweep the literal invocation strings at
  `dev/registry/newmodelo/manager.py:130-131` and
  `dev/registry/newmodelo/checklist.py:40,120`, and the assertion text at
  `src/cadrumo/tests/test_registry_locale_key_parity.py:78-79,128` and
  `src/cadrumo/tests/test_locale_translation_honesty.py:229,250`.
- Packaging: no `pyproject.toml` edit is required or wanted.

### Out of scope

`src/cadrumo/application/wizard/_translations.py` is a second dev-bleed instance,
with zero production importers and no re-export. Its consolidation was separately
assessed and resolved as do-not-consolidate, the scanner difference being three
rather than zero. It is named here so the completeness claim above is honest, and
is not governed by this decision.

## Ratification

Awaits operator acceptance. No implementation is authorised and no plan Steps are
opened by this record.
