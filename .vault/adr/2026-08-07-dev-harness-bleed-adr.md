---
tags:
  - '#adr'
  - '#dev-harness-bleed'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:053073019d99c4c800932b3061e7a7a27348718dea6979b1091b3585879dd4e0'
related:
  - '[[2026-06-14-docs-tooling-separation-adr]]'
  - '[[2026-06-14-docs-tooling-separation-research]]'
  - '[[2026-08-07-pdf-sanitizer-contributor-tooling-adr]]'
  - '[[2026-07-08-importlinter-test-carveout-adr]]'
  - '[[2026-08-07-dev-harness-bleed-research]]'
---
# `dev-harness-bleed` adr: `locales tooling boundary` | (**status:** `proposed`)

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

A decision is needed rather than a direct relocation because the naive move reds
its own verification gate, and because the move touches a boundary question the
terminology precedent did not face: several unrelated src subpackages import this
tooling as a general-purpose test utility.

## Considerations

- Severity is code weight, not security. The tooling reads nothing outside the
  wheel, executes no untrusted input, and exposes nothing a readable `.py` wheel
  does not already expose.
- Packaging needs zero edits: `pyproject.toml` ships `src/cadrumo` wholesale via
  a single package entry, and its only other `locales` mention (`:442`) refers to
  the unrelated `docs/locales/` catalogues.
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
  Two further gates consume it:
  `src/cadrumo/tests/test_registry_locale_key_parity.py:26-27` and
  `src/cadrumo/tests/test_locale_translation_honesty.py:26`.
- **A src test importing the dev tree is established, ruled practice, not a
  violation.** `dev/import_hygiene_scan.py:474-494` scopes its
  `DevToolingImportViolation` family deliberately to *shipped* modules, and its
  docstring states that an excluded test tree's `dev.` import "encodes 'this
  suite requires the repo checkout and the dev dependency group', which is
  already true and intended", adding that widening the family to unshipped tests
  "would be an ownership preference, not a correctness gate" and must be revisited
  "by ruling, never by drift". Thirteen src test modules already import `dev.`
  across unrelated domains, including `adapters/inbound/einvoice/tests/`,
  `_data/corpus/tests/`, `entrypoints/mcp/tests/` and `entrypoints/cli/tests/`.
- **A move out of the walked package reds the error-registry gate loudly, not
  silently.** `src/cadrumo/core/errors/tests/test_registry_enforcement.py:173-183`
  imports every `cadrumo` module, collects the codes reachable from
  `CadrumoError` subclasses, and asserts `set(reverse) == set(ERROR_REGISTRY)`.
  Relocating `LocaleError` leaves `FAIL_LOCALE_MANAGER` registered at
  `src/cadrumo/core/errors/registry/_core.py:451` with no subclass supplying it,
  so the set equality fails. The sanitiser record records the identical
  constraint for its six codes. `LocaleError` is nonetheless dead in product
  terms: it is raised only in `locales/manager.py` and `locales/cli.py`, and no
  production module imports it.
- The accepted `2026-07-08-importlinter-test-carveout-adr` already names
  `cadrumo.locales` as one of the shared cross-cutting helper packages that test
  edges legitimately route through. Its chosen carve-out is a wildcard over
  `.tests.` importers rather than per-package entries, so no literal `locales`
  string survives in `.importlinter` at HEAD and there is no config edit to
  carry.
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
  and it re-ships an entrypoint module in the wheel, defeating the decision's own
  goal to avoid editing one rule and five literal strings. The honest alternative
  is to change the mandated command and sweep it, which the carry list below
  already requires. It would also itself be a shipped module importing `dev.`,
  which is precisely the one direction `dev/import_hygiene_scan.py` fails, so the
  option is not merely discouraged but gate-blocked.

### Sub-decision A: the tooling CLI's own localisation

`locales/cli.py` localises itself from the four shipped catalogues. Move it to
dev and its 26 `cli.*` keys lose their in-src caller; the scanner at
`manager.py:198` no longer sees them, and the parity gate flags them as
orphaned. The relocation fails its own check. Keeping them is also wrong on the
merits: it leaves dev-tool UI strings inside shipped runtime data, the mirror
image of the bleed being fixed.

- **A1, de-localise the tooling CLI:** replace the 26 `tr()` calls with plain
  English strings and remove the `cli.*` keys from all four catalogues through
  the locale CLI's removal verb.
- **A2, give the tooling its own catalogue under dev:** preserves translated
  dev-tool output at the cost of a second catalogue mechanism, a second parity
  surface, and a scanner that must cover two source roots.
- **A3, widen the scanner to cover dev too:** keeps the keys in the shipped
  catalogues, which is the outcome this decision exists to prevent.

**Recommendation: A1.** The tooling's audience is contributors, who already read
English-only output from every other dev tool. A2 buys translated dev output by
permanently doubling the catalogue and parity machinery this repo has repeatedly
consolidated; A3 keeps shipping dev strings to taxpayers. A1 is the only option
leaving exactly one catalogue mechanism and one shipped catalogue set, and it is
the same disposition the sanitiser record takes for its six localised messages.
Note that removal must route through the locale CLI: hand-editing the catalogues
or the intentional-identical allowlist is refused by the shipped parity and
honesty gates.

### Sub-decision B: src gates that import the tooling

This was framed as the contentious sub-decision on the premise that a src test
importing a dev utility is a boundary violation. **That premise is false, and the
question is already ruled.** `dev/import_hygiene_scan.py:474-494` scopes its
violation family to shipped modules by deliberate design and states in terms that
an unshipped test tree's `dev.` import is intended, not tolerated. Thirteen src
test modules already do it. Every `tests/` tree is wheel-excluded, so such an
import cannot reach an installed operator.

- **B1, move every consumer gate to dev as well.** Clean, but it relocates the
  canonical locale parity gate out of the production test tree, and the two
  unrelated-domain consumers are storage and CLI conformance gates that merely
  need a key inventory — filing them under `dev/locales/` puts them under the
  wrong owner. Rejected as ownership churn buying nothing the existing rule does
  not already grant.
- **B2, leave the consumer gates in src importing the relocated dev utility.**
  Chosen. It is the established, gate-sanctioned pattern, it keeps each gate
  under its own domain owner, and it is the smallest change consistent with the
  existing ruling.
- **B3, split the tooling** into a production-resident key-inventory module plus
  a dev-resident mutation half. Rejected: it invents a new production module to
  avoid a boundary crossing that is explicitly permitted, leaving more shipped
  code than B2 — the opposite of this record's goal — and its scope cannot be
  pinned without first proving `manager.py` separates cleanly.

**Recommendation: B2.** An earlier draft of this record recommended B3 with B1 as
fallback, on the reasoning that B2 traded a visible violation for an invisible
one. That reasoning does not survive the scanner's own rationale block: there is
no violation to trade, the crossing is ruled intended, and the stated cost of B2
(a test suite unrunnable from a wheel-only install) is void because the tests are
not in the wheel. B3's remaining appeal was that three domains independently
reaching for `LocaleManager` suggests a genuine shared capability; that
observation stands, but it argues for a tidier dev-side facade, not for shipping
the capability to operators.

The one real defect here is independent of the choice:
`test_hardening_convention_guards.py:13` reaches the tooling by a five-dot
relative import of the private `locales.manager` submodule, which violates the
facade rule today and should be repointed at the package facade whatever else
happens.

### Sub-decision C: the central error-registry entry

`src/cadrumo/core/errors/registry/_core.py:451` maps the string
`"cadrumo.locales.manager.LocaleError"` to `FAIL_LOCALE_MANAGER`.

- **C1, delete the entry**, its `errors.fail.fail_locale_manager` message key and
  the four catalogue strings behind it.
- **C2, keep the entry** and make `LocaleError` genuinely reachable from an
  operator command.

**Recommendation: C1**, unchanged, but on corrected grounds. An earlier draft
argued the string coupling means a move breaks *silently*, leaving a dangling key
nobody notices. That is wrong: `test_registry_enforcement.py:173-183` asserts the
registered code set equals the set reachable from walked `CadrumoError`
subclasses, so relocating `LocaleError` reds that gate loudly. The correction
strengthens rather than weakens C1 — the deletion is not optional hygiene that
could be deferred, it is a mandatory part of the same atomic change, exactly as
the sanitiser record constrains its own six codes. C2 remains rejected: it would
mean inventing operator reachability for a contributor tool. Under A1 the four
catalogue strings go the same way as the `cli.*` keys, so C1 and A1 are one sweep.

## Constraints

- No parent-feature or third-party risk; every dependency is in-tree.
- The relocation must be atomic: one commit per symbol with an explicit
  pathspec, a clean collect-only run immediately before, and no bridging
  re-export at any point.
- The error-registry deletion and the module move are one atomic change, not a
  move followed by a cleanup, because the enforcement gate's package walk no
  longer reaches the class.
- Locale removal must route through the locale CLI; hand-editing the catalogues
  or the intentional-identical allowlist is refused by the shipped gates.
- The generated API stubs are CLI-owned and the scaffold run sweeps peer modules,
  so only this package's deltas may be staged.
- The shared worktree carries concurrent peer work in `test_parity.py`, package
  facades and the catalogues, so the commit shape must assume contention.

## Implementation

Land the boundary in the order A, then C, then the relocation. De-localise the
tooling CLI and remove its `cli.*` keys from the four catalogues through the
locale CLI, which frees the scanner-scope constraint. Delete the dead
error-registry entry and its message key in the same change as the move, because
the enforcement gate reds the moment the class leaves the walked package. Then
relocate the seven modules and the six tooling tests to `dev/locales/`,
preserving the existing facade discipline so the package's exported surface stays
its public names and the private modules stay private.

Sub-decision B requires no work beyond repointing imports: the five consumer
gates stay where they are, under their own domain owners, and import the
relocated package. The one substantive import fix is replacing the five-dot
private-submodule import in the storage hardening guard with a facade import.

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
crossing is settled by the import-hygiene scanner's own scoping rationale and by
the accepted import-linter carve-out, and the error-registry coupling is caught
by an existing equality gate rather than failing silently. Recording that
explicitly is most of this record's value, because both were independently
mis-read as open questions before the prior rulings were searched for.

Only sub-decision A is genuinely open, and it is open in a narrow way: all three
options work, and A1 wins on having one mechanism rather than two.

## Consequences

- The production wheel stops carrying catalogue-maintenance tooling. It does not
  stop carrying the tooling tests, which were never in it.
- Under A1 the tooling CLI's operator output becomes English-only. Contributors
  lose translated dev-tool messages; taxpayers stop receiving dev-tool strings in
  their shipped catalogues.
- Under C1 `FAIL_LOCALE_MANAGER` leaves the central error catalogue. Nothing
  operator-facing changes, because nothing operator-facing could raise it.
- Under B2 the production test tree keeps its locale gates under their own
  owners, and the count of src test modules importing `dev.` rises from thirteen
  to about fifteen. That is an increase in an already-sanctioned pattern, not a
  new class of coupling — but it is a real increase, and if the project ever
  wants that number bounded, this record is one of the contributions to it.
- The mandated authoring command changes, so the `aeat-locales-cli` rule changes
  with it.
- The dev-harness-bleed question is not closed by this record. The sanitiser is
  decided separately, and no gate detects non-production code merely *living*
  under `src` — only the reverse direction, a shipped module importing `dev.`, is
  enforced. Closing the class would need either such a gate or a standing sweep;
  this record neither builds one nor pretends the need away.

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

Awaits operator acceptance. No implementation is authorised and no plan Steps are
opened by this record.
