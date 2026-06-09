---
tags:
  - '#audit'
  - '#quality-hardening-campaign'
date: '2026-06-09'
related:
  - "[[2026-06-08-repo-health-diagnostics-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace quality-hardening-campaign with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `quality-hardening-campaign` audit: `justfile audit baseline: 2026-06-09 quality hardening kickoff`

## Scope

Full read-only sweep of every quality lane exposed by the repository `justfile`,
run on 2026-06-09 against the shared `chore/eliminate-shims` worktree, to
establish the consolidated baseline for the quality-hardening campaign. Lanes
covered: the static `check-*` gates (`check-style`, `check-format`,
`check-imports`, `check-relative-imports`, `check-dependencies`,
`check-security`, `check-types`) and the advisory `audit-*` lanes
(`audit-complexity`, `audit-dead-code`, `audit-duplication`). This audit is the
campaign root; each red lane becomes a tracked workstream burned down
incrementally. It continues the rolling repo-health trail without restating its
closed steps.

## Findings

### QHC-000 | GREEN | Five lanes already pass on the current baseline

`check-format`, `check-imports` (hexagonal layering contracts), `check-relative-imports`,
`check-dependencies` (deptry), and `audit-dead-code` (vulture) all exit 0 on
HEAD. The earlier repo-health pass recorded broken import-linter contracts and
relative-import violations; both are now green, so the structural-boundary
workstream is no longer red. No action required beyond keeping them green as a
regression guard during the campaign.

### QHC-001 | CLOSED | check-style: one E501 over-long docstring line

`just check-style` reported a single E501 (155 > 120) at
`src/aeat/application/calculations/_cross_period_clean_state.py:5` — a docstring
line cross-linking `RegistrySnapshot` and `ValidatedRegistryAuthority`.
Resolution: wrapped the sentence across lines, preserving both core-struct
cross-references. `just check-style` now exits 0. Landed on the campaign branch.

### QHC-002 | CLOSED | check-security: two semgrep pickle findings in the registry cache

`just check-security` reported 2 blocking semgrep findings
(`python.lang.security.deserialization.pickle.avoid-pickle`) at
`src/aeat/domain/calculations/registry/_loader.py:1064` (load) and `:1074`
(dump), in the `_load_registry_tree_cached` performance cache introduced by the
recent registry-perf commit. The cache deserialises only first-party data the
same process wrote, keyed by a sha256 of the registry-tree fingerprints; no
untrusted input crosses the boundary and a foreign/corrupt file is suppressed
and recomputed. Resolution: documented the trust rationale inline and added
`nosemgrep` markers at the two audited lines (fix-or-justify-at-line, not a
blanket production exclusion, per the `.semgrepignore` policy). `just check-security`
now exits 0.

### QHC-003 | OPEN | audit-complexity: 28 production functions above cognitive threshold 20

`just audit-complexity` exits 1: 260 cyclomatic grade-C+ blocks, 8 files below
maintainability grade A, and 28 production functions above the cognitive
threshold of 20. The dominant hotspots, in descending cognitive cost:

- 108: `src/aeat/domain/calculations/registry/_loader.py::_apply_locales` — by
  far the worst; a locale-merge routine.
- 48: `src/aeat/application/calculations/_cross_period_clean_state.py::_evaluate_requirement`.
- 44: `src/aeat/domain/calculations/registry/_bindings_previous_filing.py::resolve_previous_filing_binding_values`.
- 37: `src/aeat/domain/calculations/registry/_record_design_coverage.py::calculation_closure_identities`.
- 37: `src/aeat/entrypoints/cli/_config/_google.py::_push_secure_object_mirror_rows`.
- 34: `src/aeat/domain/calculations/registry/_cross_revision_divergence.py::_iter_cross_revision_casilla_divergences`.
- 32: `src/aeat/application/live/_errors.py::classify_live_iva_acquisition_failure`.
- 30: `src/aeat/domain/calculations/registry/_invoice_bindings.py::_validate_invoice_fact_and_aggregation`.
- 29: `_record_design_coverage.py::calculation_closure_numbers`, `_config/_repair_profile.py::register_repair_profile_command`.
- 27: `calc_sheets/_workbook_export.py::_apply_styling`, `_remote_state_guard.py::_validate_policy`, `_validate_semantic_role_typos.py::_semantic_role_looks_like_typo`.
- 25–26: a cluster across sede `_declarations`, secure-object migration, declaracion `_parser`, auth `_authenticator`, modelo `_m210_rate`/`_profile_binding`, cross-period `_evaluate_filing_history`.

Lowest-maintainability files: `_record_design.py` (0.0), sede
`_iva_compensation_wallet.py` (1.3), `_loader.py` (7.3),
`_workbook_parity.py` (9.4), `_schema.py` (14.8), `_formula_runtime.py` (16.2),
ledger `_models.py` (17.0), `_cross_period_clean_state.py` (18.7). Burn down via
behaviour-preserving helper extraction, worst-first, each paired with focused
tests and a re-run of the production complexity lane.

### QHC-004 | OPEN | audit-duplication: 51 clone groups (0.5% duplicated lines)

`just audit-duplication` reports 51 clone groups. The actionable clone families:

- Sede `_groi_check.py` / `_nif_iva_check.py` checker shapes (two clones, the
  largest 17 lines / 184 tokens).
- Registry `_counterpart_bindings.py` / `_invoice_bindings.py` binding builders
  (33-line / 452-token clone plus a 19-line clone).
- Registry `_bindings_previous_filing.py` / `_relations.py` relation-validation
  helpers.
- Registry `_aeat_nif_iva_oracle.py` / `_groi_oracle.py` oracle logic (26 lines).
- `core/errors/registry/_domain_part2.py` / `_domain_part3.py` error-hierarchy
  blocks (62-line / 379-token clone, plus intra-file repeats).
- Modelo work CLI `_modelo_work_verification_cli.py` / `_modelo_work_runs_cli.py`
  / `_modelo_work_revision_cli.py` rendering/addressing blocks (41-line clone).
- `_config/_google_sync_calc.py` intra-file repeats.

Consolidate one cohesive subsystem at a time. Apply the substitutability
pre-filter before promoting any "X where Y exists" — only merge when the
constraint shapes match.

### QHC-005 | OPEN | check-types: 3282 diagnostics (2383 ty + 899 pyright)

`just check-types` exits 1. ty over full `src` reports 2383 diagnostics;
pyright over the strict domain+application lane reports 899. The ty profile is
dominated by `unknown-argument` (1134) and `missing-argument` (116), which
cluster almost entirely in Typer-decorated CLI command modules
(`entrypoints/cli/_app_live.py` 154, `_config/__init__.py` 146, `_config/_google.py`
127, `_modelo_discovery_cli.py` 85) — i.e. checker mismodelling of the Typer
callback signature, not production bugs; these need a triage decision (per-module
suppression vs. a typed-callback pattern) rather than blind edits. The
mechanically-real, high-value subset:

- `missing-override-decorator` (174, ty) — add `@override`; purely mechanical.
- `reportMissingParameterType` (320, pyright) — annotate parameters.
- `reportArgumentType` (334) / `invalid-argument-type` (575, ty) — real boundary
  type drift (constructor normalisation, optional narrowing).
- `reportUnsupportedDunderAll` (36) — `__all__` entries that do not resolve.

Worst pyright file is `application/user_profile/_commands.py` (105). This lane is
the largest and is ratchet-shaped: burn down by diagnostic class, typed-boundary
fixes preferred over blanket ignores, and separate the Typer-callback noise from
genuine drift before quoting a target number.

## Recommendations

1. Quick-win gates (QHC-001, QHC-002) are closed; keep them green as regression
   guards.
2. Drive `audit-complexity` (QHC-003) worst-first, starting with
   `_loader.py::_apply_locales` (108) and `_evaluate_requirement` (48). Behaviour
   preserving extraction only; pair every reduction with focused tests and a
   complexity-lane re-run.
3. Consolidate `audit-duplication` (QHC-004) families one subsystem at a time;
   the sede checkers, the registry binding builders, and the modelo work CLI
   blocks are the cleanest first slices.
4. Triage the `check-types` (QHC-005) Typer-callback noise before quoting a
   target; land the mechanical `@override` and parameter-annotation classes
   first, then the real argument-type drift by package.
5. Treat suite runs as rolling checkpoints; never declare the campaign "done".
   Re-run the relevant lane after each landed slice and update this audit.

## ALL-GREEN re-scope and progress (2026-06-09)

The campaign goal was raised to ALL-GREEN: every `check-all` hard gate plus all
test suites (unit, integration, live) green. The `check-all` suite hard-gates on
`check-style`, `check-format`, `check-types`, `check-imports`,
`check-relative-imports`, and `check-dependencies` — so `check-types` (0 ty over
`src` plus 0 pyright over domain+application) is a hard gate, not advisory. Live
tests skip cleanly unless `AEAT_LIVE_TESTS_ENABLED=1`, so "live green" means clean
collection and clean skips, not real AEAT access.

### QHC-006 | CLOSED | Keystone type fix: register_schema was not type-preserving

`register_schema` (in `src/aeat/core/json_contract.py`) returned
`Callable[[RegisteredSchema], RegisteredSchema]` where
`RegisteredSchema = type[OutputSchema] | type[OutputRootSchema[Any]]`. ty
therefore typed every `@register_schema`-decorated CLI payload as that union and
modelled its constructor as `RootModel(root=...)`, emitting a `missing-argument:
root` plus an `unknown-argument` for every real field across all CLI payload
modules. Making the decorator generic over the decorated class (PEP 695, matching
`SchemaEnvelope[ResultT: OutputSchema]`) preserves the exact subclass type.
Runtime behaviour unchanged. Impact: full-tree ty dropped 2383 -> 1126 (-1257);
the `unknown-argument` class is eliminated and `missing-argument` fell 116 -> 7.
`_app_live.py` alone went 154 -> 0. Landed `fix(types): make register_schema
type-preserving`.

### QHC-003 progress | 6 of 28 cognitive hotspots cleared

Cleared below threshold 20, each behaviour-preserving with focused tests green:
`_loader.py::_apply_locales` (108), `_cross_period_clean_state.py::_evaluate_requirement`
(48) and `::_evaluate_filing_history` (25, also converted `dict[str, object]` to a
typed `_FilingHistory` so ty for that file dropped 15 -> 9),
`_bindings_previous_filing.py::resolve_previous_filing_binding_values` (44), and
`_record_design_coverage.py::calculation_closure_identities` (37) +
`::calculation_closure_numbers` (29) via a shared `_walk_calculation_closure`
(also removed one clone family). Remaining over-threshold: ~22, led by
`_config/_google.py::_push_secure_object_mirror_rows` (37),
`_cross_revision_divergence.py::_iter_cross_revision_casilla_divergences` (34),
`live/_errors.py::classify_live_iva_acquisition_failure` (32).

### QHC-005 refresh | check-types now 2028 (1126 ty + 902 pyright)

After the keystone, no single further mega-fix remains; the residue is a genuine
long tail. ty classes: `invalid-argument-type` 604 (109 are `found object`, e.g.
the `**_verify_row(...)` `Mapping[str, object]` splat into CLI payloads),
`unresolved-attribute` 190, `missing-override-decorator` 174 (mechanical; spread
over ~50 files), then smaller classes. pyright classes: `reportMissingParameterType`
329 (mechanical), `reportArgumentType` 324, `reportAttributeAccessIssue` 89,
`reportUnsupportedDunderAll` 36. Burn-down order: mechanical classes
(`missing-override`, `reportMissingParameterType`) first as low-risk bulk, then
the row-splat helpers' return types, then genuine argument-type drift per package.

### QHC-007 | OPEN | Test-suite baseline (for the all-tests-green goal)

`test_json_schema_conformance.py::test_every_cli_leaf_has_a_registered_schema`
fails pre-existing on CLI/registry drift (201 registry keys with no matching CLI
leaf, 1 CLI leaf with no schema) — not caused by the keystone (runtime-identical).
A full `-m unit` run is in progress to enumerate the rest; treat each failure as
an in-scope all-green item.

## QHC-008 | OPEN | test-unit failure triage and burn-down (for all-tests-green)

The full `-m unit` run surfaced 46 failures + 3 errors, all pre-existing on the
branch except the 3 regressions this campaign's `@override` sweep introduced
(line-shifted rationale markers — fixed, QHC-006 family). Triage of the remainder:

Fixed this session (test-only, no production risk):
- `test_type_ignore_rationale_inventory`, `test_any_param_rationale_inventory`
  (the @override line-shift regressions).
- `test_calculation_grounding` (3 subtests): the grounding gate hardcoded
  pre-relocation paths for `test_tautology_gate.py` / `test_renta_chain_behaviour.py`;
  repointed to `registry/tests/`.
- `test_smoke.py` modelos + portals (3 subtests) and the sanitizer
  `TestPublicReexports`: the test-topology refactor relocated these into `tests/`,
  so `from . import __doc__/__name__/__all__` and `import_module(__package__)`
  began resolving to the `tests` package instead of the subpackage under test.
  Repointed to the parent (`from ..` / explicit package). **This is a recurring
  topology-regression pattern; future relocations must re-point `from .` self-
  imports and `__package__` derivations to the parent.**
- `test_no_bare_utf8_literals` (registry `_authority.py` validated-cache write →
  `UTF_8_ENCODING`), `test_no_bare_ledger_transaction_literals` (ledger test
  support → `AggregationSourceKind.LEDGER_TRANSACTION`).

Delegated (background subagent, in flight):
- `test_public_functions_link_their_aeat_return_type`: 145 public functions need a
  truthful `:class:`ReturnType`` docstring cross-reference (uniform, legitimate —
  same shape as the @override sweep).

Remaining ~34 + 3 errors (not yet actioned), categorised:
- **Production rationale-marker gates** (legitimate marker additions, must NOT be
  used to silence a real issue): `test_boundary_rationale` (3), browser-session
  boundary, sede `test_playwright_wait_constants` (2), secure-repo
  `cast_rationale`, `test_narrowed_except_*` (2), `sensitive_persistence_policy`,
  `no_write_surface`.
- **Real domain gaps / behaviour** (need careful per-case work, NOT marker
  shortcuts): manuals/corpus (4), attachments plaintext roundtrip, `oss_ioss`
  parallel-aggregator surface, `decimal_inputs_routing` (2), `ledger_modelo_staleness`,
  registry `runtime_graph` walkers, registry `no_print`, `event_emission_contract`
  (4 required events without an emission site).
- **Large ratchet backlog**: `test_no_aeat_error_raise_with_positional_tr` (26
  `raise AeatError(tr(...))` positional sites to convert to keyword).
- **Surface/inventory**: `external_constants` route literals,
  `cross_module_imports` `__all__` baseline, `decimal_enrollment` (1),
  `docstring_core_struct_links` (1: `_binding_prefill` → `:class:`CasillaObservation``),
  `output_language_typed`, `translatable_contract`, `modelo_authorization_gate`,
  i18n `placeholder_parity` (3 errors).

The integration `test_json_schema_conformance` harness bug is fixed (QHC-009);
`test-live` skips cleanly without AEAT credentials.

## QHC-010 | session result | 30 of 49 unit failures cleared; 19 hard-tail remain

Session end state. The original 46 failures + 3 errors were driven to **19 failures**
(30 of the 49-node set now pass). The cleared set was dominated by a single
recurring class — **test-topology-refactor regressions**: every relocated `test_*.py`
that resolved a sibling production module or repo root relative to its own location
broke when the relocation added a `tests/` directory level. The fixes were uniform:
climb one extra parent (`.parent`→`.parent.parent`, `parents[N]`→`parents[N+1]`),
repoint a `_read(...)` target at the relocated file, or point a `from .` self-import
at `..`. Files fixed this way: `calculation_grounding`, `smoke` (modelos/portals),
sanitizer `test_pipeline`/`test_no_write_surface`, `placeholder_parity`,
`playwright_wait_constants`, portals `test_registry`, storage `test_factory`,
`test_boundary_rationale`, browser `test_session`, secure-repo `cast_rationale`,
`output_language_typed`, plus the `narrowed_except` ledger/ratchet repoints. Also
cleared: utf-8/ledger-transaction/tr-alias canonical-constant fixes and the
`_binding_prefill` core-struct link. The CLI conformance harness (vendored-typer
`isinstance`) and the 145-function return-type-link backlog (delegated subagent)
also landed.

**Codification candidate (strong):** the topology-regression pattern is durable,
cross-session, and project-bound — a rule like `relocated-tests-repoint-roots`
would bind future `tests/` relocations to re-point every `__file__`-relative root
(self-imports, `parents[N]`, `_read`/path targets) at the new depth. See the
Codification candidates section.

The remaining 19 are NOT topology — they are real work and several are guards
flagging genuine issues that must be fixed in product code, not silenced:
- **Real domain gaps**: M200 `01494` previous-filing binding (2 `decimal_inputs_routing`);
  attachments blob/manifest plaintext roundtrip; manuals corpus (3 `test_corpus` +
  `test_manuals` get-raises); `oss_ioss` parallel-aggregator surface in
  `_ledger_bindings.py`; `ledger_modelo_staleness`; `modelo_authorization` coverage.
- **Real feature gaps**: `event_emission_contract` — 4 required setup events
  (`auth.provider.configured`, `profile.activated`, `profile.bucket.created`,
  `profile.values.updated`) have no emission site.
- **Behaviour-changing**: `test_no_aeat_error_raise_with_positional_tr` — 26 sites
  passing `tr(...)` positionally as `message`; correcting to `translated_message=`
  changes `str(error)` rendering and needs per-site test verification.
- **Surface/inventory judgment**: `cross_module_imports` `__all__` drift
  (`core/access_gate`, `domain/contribuyente/assets`); `sensitive_persistence`
  production-write inventory; `external_constants` test URL; `decimal_enrollment`
  `Decimal(str())` at `overview/__init__.py:113`.

**check-types** remains the dominant hard gate at ~1850 (952 ty + ~900 pyright)
after the keystone + @override eliminations — a per-site typed-boundary grind.

## QHC-011 | session result (final) | 36 of 49 unit failures cleared; 13 genuine-hard remain

Correction to QHC-010's categorisation: three clusters I first read as "real
feature/domain gaps" were ALSO topology/refactor regressions and are now fixed —
`event_emission_contract` (4: `_AEAT_ROOT = parents[2]` resolved to `application`,
producing `application/application/...`; → `parents[3]`), `oss_ioss` parallel-
aggregator guard (the `resolve_ledger_oss_aggregation_binding_values` resolver
moved from `_bindings.py` to `_ledger_bindings.py`; skip both), and
`modelo_authorization` (30 `authorization.d/*.toml` manifests named `enrolling_test`
at `application/calculations/test_*.py` — all relocated into `tests/`; swept). The
emission sites, resolver, and enrolling tests existed all along.

Net: **36 of the 49-node set now pass**. The topology-regression pattern accounts
for the overwhelming majority of the cleared failures — the codification candidate
below is strongly warranted.

The 13 that remain are genuinely deep and require domain decisions or behaviour-
changing work; they are NOT mechanical and several are guards over real product
behaviour:
- manuals/corpus cluster (4): the bundled corpus's extraction state changed
  (`iva/2025/single` is now extracted, so the "unextracted manual raises
  ManualNotFoundError" contract needs a genuinely-unextracted fixture or a
  corpus-state decision) plus the 3 `test_corpus` manuals-report assertions.
- M200 `01494` previous-filing binding (2 `decimal_inputs_routing`).
- attachments blob/manifest plaintext roundtrip; `ledger_modelo_staleness`
  ValidationError; `sensitive_persistence` production-write inventory.
- `test_no_aeat_error_raise_with_positional_tr` (26 sites; `message`→`translated_message=`
  changes error rendering — per-site verification).
- surface/inventory judgment: `cross_module_imports` `__all__`
  (`core/access_gate`, `domain/contribuyente/assets`); `external_constants` test
  URL; `decimal_enrollment` `Decimal(str())` at `overview/__init__.py:113`.

**check-types** remains ~1850 (the per-site typed-boundary grind). These 13 + the
type lane are the genuine multi-session / domain-expert remainder; everything
mechanically or structurally tractable in one pass has been cleared.

## Codification candidates

- **Source:** QHC-010 topology-regression cluster (≈20 relocated-test failures from
  one root cause). **Rule slug:** `relocated-tests-repoint-file-relative-roots`.
  **Rule:** When relocating a `test_*.py` into a `tests/` subpackage, re-point every
  `__file__`-relative root it computes — `from . import` self-imports (→ `..`),
  `Path(__file__).parent[...]` / `parents[N]` depths (→ +1), `import_module(__package__)`
  (→ explicit package), and any `_read`/source-path targets — to the new depth, and
  run the relocated file before landing. (Promote only if the operator wants it; the
  pattern recurred ~20× this session.)

None yet. The campaign's mechanics (fix-or-justify-at-line for semgrep,
behaviour-preserving extraction for complexity, substitutability pre-filter for
duplication, typed-boundary-over-ignore for types) are already captured by
existing rules. A codification candidate will be reconsidered only if a burn-down
slice surfaces a durable, cross-session, project-bound constraint not already
covered.
