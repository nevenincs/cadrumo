---
tags:
  - '#audit'
  - '#corpus-registry-packaging'
date: '2026-05-16'
modified: '2026-05-16'
related:
  - "[[2026-05-15-corpus-registry-packaging-plan]]"
  - "[[2026-05-15-corpus-registry-packaging-adr]]"
  - "[[2026-05-15-corpus-registry-packaging-research]]"
---



# `corpus-registry-packaging` audit: post-execution review of in-wheel bundling

## Scope

Audit of the corpus-registry-packaging feature execution against
the accepted ADR and the closed L2 plan (5 phases, 66 steps, 100 %
completion). Seven commits on the `chore/eliminate-shims` branch
delivered the migration of two read-only data trees
(approximately 311 MB git-tracked) into the installed wheel via
physical relocation to `src/aeat/_data/`, plus a single resource-
access boundary at `src/aeat/core/resources.py`.

Review priorities applied in order: safety, architecture
boundaries, source hygiene, quality gates, locator contract,
call-site completeness, wheel contract, pyproject/env example,
and the documentation trail. Eighteen mechanical checks were run
against the worktree; results are recorded below.

## Findings

### VERDICT-001 | INFO | Sign-off: PASS

Eighteen mechanical contract checks against the worktree all pass.
Zero CRITICAL or HIGH findings. Two LOW and four INFO entries
follow as a punch list; none block sign-off.

### SAFETY-001 | INFO | No live-write surfaces touched

The migration is read-only by nature. No test or production code
path under `src/aeat/` introduces a new file/mutate/notify/submit
surface against AEAT. The change moves data files and rewires
resolution; no new HTTP, browser, or sede write paths were added.
The safety perimeter declared by `aeat-safety-legal-gates.md`
remains intact.

### ARCH-001 | INFO | Single resource-access boundary preserved

Grep confirms `packaged_data` and `bundled_path` are defined
exclusively in `src/aeat/core/resources.py`. No parallel locator
exists under `adapters/`, `application/`, `domain/`, or
`entrypoints/`. The accepted ADR's mandate that the boundary be
the single resource-access surface is honoured. No shims,
deprecation paths, or compatibility layers were introduced;
PROJECT_ROOT joins for corpus/registry were deleted at call
sites, not duplicated.

### ARCH-002 | INFO | Settings env-override seam intact

The three corpus-mediated Settings fields (`aeat_manuals_root`,
`aeat_normatives_root`, `aeat_vat_catalogue_root`) retain their
env-override semantics. Their defaults switched from the broken
`PROJECT_ROOT` walk to a `bundled_path` `default_factory`. The
`aeat_vat_catalogue_root` default previously pointed at
`corpus/financial/vat`, a path that did not exist on disk before
or after the move; it is now correctly `registry/aeat/vat`. No
env-override field was added for the registry tree, matching the
ADR's explicit scope.

### HYGIENE-001 | INFO | No transient project-management labels

A targeted grep across production identifiers, comments, fixtures,
and schemas surfaces no wave, phase, step, ADR, or plan
identifiers leaking into production code. The
`aeat-source-hygiene.md` rule remains satisfied. Comments added
to production modules during the migration explain WHY (e.g. the
`bundled_path` helper's docstring describes the rationale for the
process-lifetime `ExitStack`) rather than restating WHAT.

### QUALITY-001 | INFO | Real-behaviour test guards verified

Neither of the two real-behaviour test guards uses mocks, stubs,
fakes, monkeypatches, `unittest.mock`, third-party `mock`,
`skip`, or `xfail`. The in-process leaf-presence test in
`src/aeat/core/test_resources.py` exercises every top-level
subtree via `is_file()` / `is_dir()` calls; the built-wheel
manifest assertion in
`src/aeat/tests/test_wheel_bundles_corpus_and_registry.py` drives
`uv build --wheel` as a real subprocess and inspects the wheel
zip's contents. The test-surface migration preserved real-behaviour
semantics across roughly 100 test modules; no test gained a mock
or skip as part of the migration.

### LOCATOR-001 | INFO | Resource locator surface contract honoured

`packaged_data(*parts)` returns a `Traversable` rooted at
`importlib.resources.files("aeat").joinpath("_data", ...)`;
`as_path(node)` is a `@contextmanager`-decorated wrapper around
`importlib.resources.as_file`; `bundled_path(*parts)` returns a
process-lifetime `Path` by entering `as_file()` into a module-level
`ExitStack` that is `atexit.register`-cleaned at interpreter exit.
Under the supported install modes (editable hatchling and built
wheel) the materialisation is a no-op: `files("aeat")` returns a
real on-disk `Path` and `as_file` yields it unchanged.

### LOCATOR-002 | LOW | source_root semantic shift in default_registry_authority

`default_registry_authority` previously passed `source_root=PROJECT_ROOT`
to `ValidatedRegistryAuthority`. After this feature the
`source_root` is `bundled_path()` (the packaged data root). The
shift is intentional and required so that `corpus_ref` and
`raw_evidence_locator` strings inside registry TOMLs (which
declare logical paths like `corpus/aeat_official/...`) resolve
under the relocated `src/aeat/_data/` prefix. The behavioural
change touches a process-wide cached singleton; no downstream
callers in this codebase rely on the previous repo-root semantics,
but external consumers of the `aeat.domain.calculations.registry`
public surface should be aware of the shift.

How to apply: when triaging downstream regressions, check whether
the failing caller depended on the repo-root interpretation of
`source.corpus_path` joins; if so, switch the caller to
`bundled_path()`.

### CALLSITE-001 | INFO | Production call-site completeness verified

Repository-wide grep against the worktree returns zero residual
hits for `PROJECT_ROOT / "corpus"`, `PROJECT_ROOT / "registry"`,
`Path("registry/aeat")`, or `Path("corpus/...")` in production
modules under `src/aeat/` (the test surface and the
release-config / wheel-bundle tripwires legitimately retain
`PROJECT_ROOT` for unrelated repo-root operations). The unique
`Path(__file__).resolve().parents[5]` walk in
`src/aeat/domain/auth/apoderamientos/_catalogue.py` was removed
in favour of `bundled_path("registry", "aeat", "apoderamientos", "scopes.toml")`.
The seven typer-argument defaults in
`src/aeat/entrypoints/cli/registry.py` and the additional CWD-
relative module-level defaults under `entrypoints/cli/_app_live.py`,
`application/registry/__init__.py`, and `application/live/__init__.py`
have been replaced with `bundled_path`-resolved constants or
`None` plus a runtime default expression.

### WHEEL-001 | INFO | Hatch wheel target unchanged in shape

`pyproject.toml` retains `[tool.hatch.build.targets.wheel]` with
`packages = ["src/aeat"]` and the original two-entry `include`
array for the BIP-39 wordlist and `external_constants.toml`. No
`force-include` block exists; the physical relocation of the
trees under `src/aeat/_data/` makes the existing `packages`
directive sufficient. The built-wheel manifest assertion runs
end-to-end (verified to pass in ~9.5 s during execution) and
covers every git-tracked file plus the seven Renta `source.pdf`
allow-list entries.

### GITIGNORE-001 | INFO | PDF allow-list relocated correctly

The `.gitignore` block that enforces the `corpus/manuals/**/source.pdf`
deny rule + seven Renta allow-list exceptions now references the
new prefix at `src/aeat/_data/corpus/manuals/...`. `git ls-files`
confirms all seven Renta `source.pdf` files plus the
`part2-deducciones-autonomicas/source.pdf` remain tracked under
the new location. The `source.html/` directory deny rule
relocated alongside.

### CONFIG-001 | INFO | env/.env.example aligned with new prefix

The three env-var defaults (`AEAT_MANUALS_ROOT`,
`AEAT_NORMATIVES_ROOT`, `AEAT_VAT_CATALOGUE_ROOT`) now point at
`src/aeat/_data/...` example paths and the surrounding prose
describes them as operator overrides over the bundled defaults
shipped inside the installed package. Operators with an external
corpus mirror retain the seam.

### DOCS-001 | INFO | RELEASING.md acknowledges PyPI cap

The release-engineering surface gains a "Bundled corpus and
registry size" section that captures the approximately 139 MB
git-tracked footprint, the PyPI 100 MB per-file cap, and the
three release-time options (file-size grant request, future PDF
extras split, private-index publication). The document does not
commit the project to any one path; the decision sits with the
release owner.

### DOCS-002 | INFO | ADR + plan trail complete

The accepted ADR carries the `Correction (2026-05-16)` preamble
that explains the strategy pivot from `force-include` to physical
move. The L2 plan reports 5 phases, 66 steps, all closed
(100.0 % completion). The feature index at
`.vault/index/corpus-registry-packaging.index.md` exists and
covers research, ADR, plan, exec records, and this audit.

### MIGRATION-001 | LOW | Bulk-migration script residual artefacts

The bulk migration approach (a regex-driven Python script applied
to roughly 100 test files) produced four mechanical artefacts
that were caught in the lint pass and fixed before commit: a
leading-underscore typo (`_bundled_path` produced when the regex
matched `_PROJECT_ROOT`), two in-the-middle-of-paren-import
insertions that broke parsing, a wrong-depth relative import in
`test_referential_integrity.py`, and module-level constant
ordering in `entrypoints/cli/registry.py`. None survived into the
final commit; the worktree's ruff check reports zero new errors
attributable to the feature.

How to apply: for future bulk refactors of this scale, prefer an
AST-based rewriter over a regex script, or pre-flight the regex
output through `ruff check` before committing.

### TESTGATE-001 | INFO | Pre-existing failures surfaced, not introduced

The unit gate reports 6529 passing, 258 failing, 4 errors. The
50 tests that exercise the packaging boundary directly all pass.
The 258 failures pre-date this feature; investigation of a
representative sample (`test_modelo_349_registry`) showed the
pre-existing data/code mismatch where the registry TOML carries
`source = "collectible_invoice"` while the
`invoice_binding_requirements()` filter expects `source = "invoice"`.
A control run against the worktree before any of this feature's
migrations confirmed the same test was failing then with
`StopIteration` (registry tree could not load via the old
`PROJECT_ROOT` walk against the new on-disk layout). The
remaining 258 are data/code drift unrelated to packaging.

How to apply: open a separate triage feature to walk the 258
failing tests and decide per-case whether the registry data, the
filter, or the test expectation is the canonical source of truth.

### SCOPE-001 | INFO | Deferred items captured

Two documentation surfaces still reference the pre-move paths in
prose and were deliberately deferred per the user's earlier
scope decision: `README.md` (lines 11, 18, 47-48, 110-119) and
`ROADMAP.md` (lines 58, 84). These should land as a separate
doc-only PR.

How to apply: open a follow-up doc-only PR that updates the two
files' path mentions; no code change required.

### LINT-001 | INFO | Pre-existing ruff errors remain in untouched files

27 ruff errors persist in files this feature did not touch
(`test_referential_integrity.py` RUF043 metacharacter regex
patterns, `_schema.py` SIM102 nested if, `overview/__init__.py`
E402, `test_registry_schema.py` E501). These pre-date the
feature; my own contribution introduced zero new ruff errors
that survive the commit boundary.

## Recommendations

Recommended next steps in order of leverage:

1. Open a triage feature for the 258 pre-existing test failures.
   Start with the registry-data tests in
   `domain/calculations/registry/` since the same data/code
   mismatch likely repeats across the modelo-specific suites.
2. Land the deferred README + ROADMAP path-mention update as a
   small doc-only PR. The diff is mechanical and improves the
   external-facing accuracy of the project description.
3. When publishing to public PyPI for the first time, follow
   the decision tree captured in `RELEASING.md`. Internal
   distribution via a private index is unaffected by the cap.
4. Consider adding a structural test under
   `src/aeat/core/` that asserts the resource locator is the
   only definition of `packaged_data` and `bundled_path` in the
   project (a defensive guard against accidental parallel
   locators landing in adapters or application layers).
