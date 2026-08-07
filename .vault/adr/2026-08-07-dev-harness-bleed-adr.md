---
tags:
  - '#adr'
  - '#dev-harness-bleed'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b31bf89afbdb9c0a20c33f51ffcf95e56b94cfbcbb09baccd1a75df899fd5f4b'
related:
  - '[[2026-08-07-dev-harness-bleed-research]]'
  - '[[2026-06-14-docs-tooling-separation-adr]]'
  - '[[2026-08-07-pdf-sanitizer-contributor-tooling-adr]]'
  - '[[2026-07-08-importlinter-test-carveout-adr]]'
---
# `dev-harness-bleed` adr: `locales tooling boundary` | (**status:** `accepted`)

## Problem Statement

`src/cadrumo/locales/` is a mixed package. Five artefacts are genuine runtime
data: `en.yml`, `es.yml`, `ca.yml`, `hu.yml` and `_intentional_identical.json`,
loaded by the renderer at `src/cadrumo/core/i18n/_render.py:128` and `:491`. Seven
modules are dev/CI catalogue-maintenance tooling that ships in the wheel with no
runtime importer: `manager.py`, `_ast_scanner.py`, `_registry_scanner.py`,
`_fstring_registry.py`, `_status.py`, `cli.py`, `__main__.py`, plus the package
facade `__init__.py`, which re-exports only tooling symbols. The six tooling
tests under `locales/tests/` do *not* ship; every `tests/` tree is excluded from
the wheel at `pyproject.toml:280-283`.

An accepted decision already governs this class: documentation tooling stays
outside the production package, and the identical data-stays / code-moves split
was applied to the Terminology Handbook (`2026-06-14-docs-tooling-separation-adr`).

This is **not** the only outstanding instance of that shape. The PDF sanitiser is
a second one, ten modules under the inbound-adapters tree with no production
caller, ruled on the same day by `2026-08-07-pdf-sanitizer-contributor-tooling-adr`
(proposed). Earlier framing of the locales case as "the sole remaining instance"
was a completeness claim over a *detection method* — a sweep for argparse, click
and typer entrypoints and for stray `__main__.py` and `cli.py` under `src` — not
over the concept of non-production code living in the shipped package. The
sanitiser carries no CLI entrypoint and is invisible to that sweep. The claim is
withdrawn; this record decides the locales case only.

A decision is needed rather than a direct relocation because the move touches a
boundary question the terminology precedent did not face: several unrelated src
subpackages import this tooling as a general-purpose test utility.

## Considerations

- Severity is code weight, not security. The tooling reads nothing outside the
  wheel, executes no untrusted input, and exposes nothing a readable `.py` wheel
  does not already expose.
- Packaging needs zero edits: `pyproject.toml` ships `src/cadrumo` wholesale via
  a single package entry, and its only other `locales` mention (`:442`) refers to
  the unrelated `docs/locales/` catalogues.
- **Sub-decision A has since been executed** (commit `1a160fa04f`). At HEAD
  `locales/cli.py` makes zero `tr()` calls and no `cli.locales` block survives in
  any of the four catalogues, so the parity-orphan blocker described below is
  discharged rather than pending. The blocker was real when this record was
  opened; the decision is retained because it is the ruling the execution
  implemented, not because work remains.
- The count of self-localising calls was measured at twenty. An earlier figure of
  twenty-six came from a naive grep whose pattern also matched `str(` and one
  docstring mention; that figure reached this record unchallenged and is
  corrected here.
- `LocaleManager.get_codebase_keys()` scans the source tree with `rglob("*.py")`
  over src only, at `src/cadrumo/locales/manager.py:198`.
- **Six src test modules consume the tooling, across three unrelated domains.**
  The canonical tree-wide parity gate is itself a consumer:
  `src/cadrumo/tests/test_parity.py:8-13` imports the `locales` facade, the CLI
  app and `locales.manager`, and pins the logger name
  `"cadrumo.locales._ast_scanner"` at `:585`. Three sit in unrelated domains and
  use `LocaleManager` as a general utility:
  `src/cadrumo/adapters/persistence/storage/tests/test_hardening_convention_guards.py:13`,
  which reaches it by a five-dot relative import of the private `manager`
  submodule; `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py:73`
  (the `:47` occurrence cited by an earlier draft is prose naming the
  `python -m cadrumo.locales set` command, not an import); and
  `src/cadrumo/application/operator_surface/tests/test_contract.py:41`, which
  constructs a manager and reads catalogues at `:438-441`. Two further gates
  consume it: `src/cadrumo/tests/test_registry_locale_key_parity.py:26-27` and
  `src/cadrumo/tests/test_locale_translation_honesty.py:26`.
- **The cross-domain consumers use only the catalogue-reading half.** No consumer
  outside `locales/` calls `get_codebase_keys` or `get_codebase_namespaces`
  except `test_parity.py` (`:53`, `:702`, `:725`). The three unrelated-domain
  gates use `LocaleManager` purely as a strict YAML catalogue reader,
  functionally a strict-mode near-duplicate of the renderer's private
  `_load_locale_yaml` and `_flatten_translations` at
  `src/cadrumo/core/i18n/_render.py:544` and `:560`. That overlap is a candidate
  deduplication finding in its own right and is not resolved here.
- **`test_parity.py` is substantially the mutation tooling's own unit suite**, not
  only a consuming gate: it exercises `set_locale_value`, `remove_locale_value`,
  scaffold, canonicalise and the CLI app directly. Where it should live is
  therefore a genuine question rather than a mechanical repoint.
- **A src test importing the dev tree is established, ruled practice, not a
  violation.** `dev/import_hygiene_scan.py:474-494` scopes its
  `DevToolingImportViolation` family deliberately to *shipped* modules, and its
  docstring states that an excluded test tree's `dev.` import encodes the fact
  that the suite requires the repo checkout and the dev dependency group, which
  is already true and intended; it adds that widening the family to unshipped
  tests would be an ownership preference rather than a correctness gate, and must
  be revisited by ruling, never by drift. Thirteen src test modules already
  import `dev.` across unrelated domains.
- **A move out of the walked package reds the error-registry gate loudly, not
  silently.** `src/cadrumo/core/errors/tests/test_registry_enforcement.py:173-183`
  imports every `cadrumo` module, collects the codes reachable from
  `CadrumoError` subclasses, and asserts the registered code set equals the
  reachable set. Relocating `LocaleError` leaves `FAIL_LOCALE_MANAGER` registered
  at `src/cadrumo/core/errors/registry/_core.py:451` with no subclass supplying
  it, so the equality fails.
- **Deleting that registry row alone is impossible.**
  `CadrumoError.__init_subclass__` at `src/cadrumo/core/errors/__init__.py:92-97`
  calls `bind_error_code(cls)` at class-definition time, which refuses a subclass
  carrying no registry row, so removing the row breaks import of
  `locales/manager.py`. `LocaleError` is nonetheless dead in product terms: it is
  raised only inside `locales/manager.py` and `locales/cli.py`, and no production
  module imports it.
- `LocaleError` is raised by the catalogue-reading path as well as the mutation
  path — `manager.py:145`, the strict loader's duplicate-key refusal — so it does
  not partition cleanly along a read/mutate split.
- The accepted `2026-07-08-importlinter-test-carveout-adr` already names
  `cadrumo.locales` as one of the shared cross-cutting helper packages that test
  edges legitimately route through. Its chosen carve-out is a wildcard over
  test importers rather than per-package entries, so no literal `locales` string
  survives in `.importlinter` at HEAD and there is no config edit to carry.
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
  Mirrors the terminology precedent and the sanitiser record. Chosen, subject to
  the three sub-decisions below.
- **De-ship the catalogue data as well.** Rejected: the renderer loads the YAML
  at runtime through `importlib.resources`, so the data is production input, not
  tooling. This is not the terminology situation, where the data was doc-build
  input.
- **Leave a thin `cadrumo.locales.__main__` in src dispatching to the moved
  implementation, preserving the mandated CLI surface.** Rejected. This is a
  compatibility shim in the exact sense the no-shims rule forbids: its only
  purpose is keeping an old invocation path alive after the canonical home moved,
  and it re-ships an entrypoint module in the wheel, defeating the goal of the
  decision to avoid editing one rule and five literal strings. It would also
  itself be a shipped module importing `dev.`, which is precisely the one
  direction `dev/import_hygiene_scan.py` fails, so the option is not merely
  discouraged but gate-blocked.

### Sub-decision A: the tooling CLI and its own localisation

`locales/cli.py` localised itself from the four shipped catalogues, twenty `tr()`
calls in all. Moving it to dev would strand those `cli.*` keys: the scanner at
`manager.py:198` would no longer see an in-src caller, and the parity gate would
flag them as orphaned, so the relocation would fail its own check. Keeping them
was also wrong on the merits, leaving dev-tool UI strings inside shipped runtime
data, the mirror image of the bleed being fixed.

- **A1, de-localise the tooling CLI:** replace the `tr()` calls with plain
  English strings and remove the `cli.*` keys from all four catalogues through
  the locale CLI removal verb.
- **A2, give the tooling its own catalogue under dev:** preserves translated
  dev-tool output at the cost of a second catalogue mechanism, a second parity
  surface, and a scanner that must cover two source roots.
- **A3, widen the scanner to cover dev too:** keeps the keys in the shipped
  catalogues, which is the outcome this decision exists to prevent.

**Recommendation: A1.** The audience is contributors, who already read
English-only output from every other dev tool. A2 buys translated dev output by
permanently doubling the catalogue and parity machinery this repo has repeatedly
consolidated; A3 keeps shipping dev strings to taxpayers. A1 is the only option
leaving exactly one catalogue mechanism and one shipped catalogue set, and it is
the same disposition the sanitiser record takes for its six localised messages.
Removal must route through the locale CLI: hand-editing the catalogues or the
intentional-identical allowlist is refused by the shipped parity and honesty
gates. This sub-decision has been executed; see Considerations.

### Sub-decision B: src gates that import the tooling

This was framed as the contentious sub-decision on the premise that a src test
importing a dev utility is a boundary violation. **That premise is false, and the
question is already ruled.** The import-hygiene scanner scopes its violation
family to shipped modules by deliberate design and states in terms that an
unshipped test tree `dev.` import is intended, not tolerated. Thirteen src test
modules already do it. Every `tests/` tree is wheel-excluded, so such an import
cannot reach an installed operator.

- **B1, move every consumer gate to dev as well.** Clean, but it relocates the
  canonical locale parity gate out of the production test tree, and the
  unrelated-domain consumers are storage, CLI-conformance and operator-surface
  gates that merely need a catalogue reader; filing them under `dev/locales/`
  puts them under the wrong owner. Rejected as ownership churn buying nothing the
  existing rule does not already grant.
- **B2, leave the consumer gates in src importing the relocated dev utility.**
  Chosen. It is the established, gate-sanctioned pattern, it keeps each gate
  under its own domain owner, and it is the smallest change consistent with the
  existing ruling.
- **B3, split the tooling** into a production-resident key-inventory module plus
  a dev-resident mutation half. Rejected: it invents a new production module to
  avoid a boundary crossing that is explicitly permitted, leaving more shipped
  code than B2, the opposite of the goal of this record.

**Recommendation: B2.** An earlier draft recommended B3 with B1 as fallback, on
the reasoning that B2 traded a visible violation for an invisible one. That
reasoning does not survive the rationale block of the scanner: there is no
violation to trade, the crossing is ruled intended, and the stated cost of B2, a
test suite unrunnable from a wheel-only install, is void because the tests are
not in the wheel.

Two measurements sharpen the rejection of B3. An independent split assessment put
roughly 1,185 of 2,317 tooling lines, about half, on the production side of the
split, all with zero production importers, and found the extracted module would
have no production consumer at all; that figure is recorded as reference and was
not re-derived here, though the current seven-module total of 2,271 lines is
consistent with it. Independently, no cross-domain consumer calls the
key-inventory methods at all, since they use the catalogue reader, so the
capability B3 would promote to production is not the capability those consumers
need.

The one real defect here is independent of the choice:
`test_hardening_convention_guards.py:13` reaches the tooling by a five-dot
relative import of the private `locales.manager` submodule, which violates the
facade rule today and should be repointed at the package facade whatever else
happens.

### Sub-decision C: the central error-registry entry

`src/cadrumo/core/errors/registry/_core.py:451` maps the string
`"cadrumo.locales.manager.LocaleError"` to `FAIL_LOCALE_MANAGER`.

- **C1, retire the entry**: reparent `LocaleError` off `CadrumoError` onto plain
  `Exception`, drop the now-unused import, then delete the registry row, its
  `errors.fail.fail_locale_manager` message key, and the four catalogue strings
  behind it.
- **C2, keep the entry** and make `LocaleError` genuinely reachable from an
  operator command.

**Recommendation: C1**, on corrected grounds and with a corrected action. An
earlier draft argued the string coupling means a move breaks silently, leaving a
dangling key nobody notices. That is wrong: the enforcement gate asserts the
registered code set equals the walked-subclass set, so relocating `LocaleError`
reds it loudly. The correction strengthens C1, because the retirement is not
optional hygiene that could be deferred but a mandatory part of the same atomic
change, exactly as the sanitiser record constrains its own six codes.

The same draft described the action as deleting the entry, which is not
executable on its own: the subclass hook refuses a `CadrumoError` subclass with
no registry row, so deleting the row first breaks import. The reparenting step is
therefore part of the decision, not an implementation detail. It is
behaviour-preserving: every real catcher names `LocaleError` explicitly
(`manager.py:333`, a tuple catch naming it, and `cli.py:139`, `:172`, `:197`, `:214`, `:233`), and the
`except CadrumoError` sites sit on production paths that cannot raise it. C2
remains rejected: it would mean inventing operator reachability for a contributor
tool.

## Constraints

- No parent-feature or third-party risk; every dependency is in-tree.
- The relocation must be atomic: one commit per symbol with an explicit
  pathspec, a clean collect-only run immediately before, and no bridging
  re-export at any point.
- The error-registry retirement and the module move are one atomic change, not a
  move followed by a cleanup, because the enforcement gate package walk no longer
  reaches the class.
- Locale removal must route through the locale CLI; hand-editing the catalogues
  or the intentional-identical allowlist is refused by the shipped gates.
- The generated API stubs are CLI-owned and the scaffold run sweeps peer modules,
  so only the deltas of this package may be staged.
- The shared worktree carries concurrent peer work in `test_parity.py`, package
  facades and the catalogues, so the commit shape must assume contention.

## Implementation

Land the boundary in the order A, then C, then the relocation. De-localise the
tooling CLI and remove its `cli.*` keys from the four catalogues through the
locale CLI, which frees the scanner-scope constraint; this step is done.
Reparent `LocaleError` and retire the error-registry row and message key in the
same change as the move, because the enforcement gate reds the moment the class
leaves the walked package. Then relocate the seven modules and the six tooling
tests to `dev/locales/`, preserving the existing facade discipline so the
exported surface stays the public names and the private modules stay private.

Sub-decision B requires no work beyond repointing imports: the six consumer gates
stay where they are, under their own domain owners, and import the relocated
package. The one substantive import fix is replacing the five-dot
private-submodule import in the storage hardening guard with a facade import.

Two details bite during execution. `_status.py:28-34` imports four private names
from `manager` alongside `LocaleManager`, which is a non-issue under this
decision because the whole package moves together, but would have been a blocker
under a split. And `manager.py:199` self-excludes two files from its scan by
literal filename, `test_parity.py` and `manager.py`; once both leave `src`, that
clause matches nothing and is silently over-broad, so it should be deleted with
the move rather than carried.

The catalogues, `_intentional_identical.json` and their `importlib.resources`
load path do not move and are not touched.

## Rationale

The decision follows `2026-06-14-docs-tooling-separation-adr` in shape, code out
and data stays, with the tooling reading the data through a public boundary. That
precedent is the knockout argument for the top-level choice: the boundary is
already accepted policy, and `2026-08-07-pdf-sanitizer-contributor-tooling-adr`
applies the same shape to a sibling package on the same evidence.

What this record adds is the three couplings the terminology precedent did not
face. Terminology tooling had no self-localisation, no cross-domain test
consumers and no entry in the central error registry; locales tooling has all
three. Two of them turn out to be already-ruled rather than open: the test-tree
crossing is settled by the scoping rationale of the import-hygiene scanner and by
the accepted import-linter carve-out, and the error-registry coupling is caught
by an existing equality gate rather than failing silently. Recording that
explicitly is most of the value of this record, because both were independently
mis-read as open questions before the prior rulings were searched for.

## Consequences

- The production wheel stops carrying catalogue-maintenance tooling. It does not
  stop carrying the tooling tests, which were never in it.
- Under A1 the tooling CLI output is English-only. Contributors lose translated
  dev-tool messages; taxpayers stop receiving dev-tool strings in their shipped
  catalogues.
- Under C1 `FAIL_LOCALE_MANAGER` leaves the central error catalogue and
  `LocaleError` stops being a registry-bound error. Nothing operator-facing
  changes, because nothing operator-facing could raise it.
- Under B2 the production test tree keeps its locale gates under their own
  owners, and the count of src test modules importing `dev.` rises from thirteen
  to about eighteen. That is an increase in an already-sanctioned pattern, not a
  new class of coupling, but it is a real increase, and if the project ever wants
  that number bounded, this record is one of the contributions to it.
- The mandated authoring command changes, so the `aeat-locales-cli` rule changes
  with it.
- The dev-harness-bleed question is not closed by this record. The sanitiser is
  decided separately, and no gate detects non-production code merely living
  under `src`; only the reverse direction, a shipped module importing `dev.`, is
  enforced. Closing the class would need either such a gate or a standing sweep;
  this record neither builds one nor pretends the need away.
- A candidate duplication is surfaced and left open: the strict catalogue reader
  in `LocaleManager` overlaps the private loader helpers in the renderer, and
  three unrelated domains reach for the tooling only for that capability. If it
  is deduplicated later, the cross-domain consumers stop needing the dev package
  at all.

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
- Repoint the five-dot private-submodule import at
  `src/cadrumo/adapters/persistence/storage/tests/test_hardening_convention_guards.py:13`
  at the relocated package facade.
- Delete the dead literal-filename self-exclusion at
  `src/cadrumo/locales/manager.py:199`.
- Edit the mandate at `.vaultspec/rules/aeat-locales-cli.md` and propagate with
  the spec sync verb; never the generated `.claude/` copy.
- Sweep the literal invocation strings at
  `dev/registry/newmodelo/manager.py:130-131` and
  `dev/registry/newmodelo/checklist.py:40,120`, and the assertion text at
  `src/cadrumo/tests/test_registry_locale_key_parity.py:78-79,128` and
  `src/cadrumo/tests/test_locale_translation_honesty.py:229,250`.
- No `pyproject.toml` edit and no `.importlinter` edit is required; the existing
  wildcard test carve-out already covers the relocated importers.

### Out of scope

`src/cadrumo/application/wizard/_translations.py` is a further dev-bleed
candidate, with zero production importers and no re-export. Its consolidation was
separately assessed and resolved as do-not-consolidate, the scanner difference
being three rather than zero. It is named here so no reader mistakes this record
for a sweep of the class, and is not governed by this decision.

## Ratification

Accepted by the operator on 2026-08-07, on the amended record: decisions A1, B2
and C1. Implementation is authorised.

The acceptance is of this form of the record, not a carry-over. An earlier
approval was given to the A1 / **B3** / C1 form. Sub-decision B then reversed on
evidence — the src-test-imports-dev crossing turned out to be already ruled and
permitted rather than a violation — and the operator was re-asked rather than the
prior approval being extended to a decision they had not seen. B2 did not ship
under an approval given for B3.

The operator reasoning recorded for B2: the crossing is permitted by an existing
ruling, since `dev/import_hygiene_scan.py:474-494` scopes its violation family to
shipped modules, thirteen src test modules already import `dev.`, and every
`tests/` tree is wheel-excluded at `pyproject.toml:280-283`; while B3 would
invent a production module with no production consumer and still leave roughly
half the tooling lines in the wheel.

Sub-decision A was executed ahead of this ratification under separate
authorisation. C1 and the relocation are authorised by it and not yet done.

C1's safety rests on no production path being able to raise `LocaleError`, and
that was closed at the source rather than by walking the seventeen
`except CadrumoError` sites individually. No production module imports the
locales tooling at all, and the runtime renderer reaches the catalogues through
its own private `_load_locale_yaml` at `src/cadrumo/core/i18n/_render.py:544`
rather than through `LocaleManager`. With no production caller able to construct
a manager, no production catcher can receive the exception — which also disposes
of the concern that `LocaleError` is raised by the reading path as well as the
mutating one. Reparenting it onto `Exception` is therefore behaviour-preserving.
