---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:a6bdad6de7e7b29ca9213ba046f4dea9c6b959b41e7eeb68b174bb7c883382b8'
step_id: 'S78'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---
# Burn down the incidental literal corpus one test package at a time across the roughly 108 files carrying path-valued overrides and the roughly 350 hand-rolled override sites, each package gated by the provenance gate scoped to it plus its own suite

## Scope

- `src/cadrumo/tests/`

## Description

- Partial progress only. This record covers a single named ten-file batch
  scoped to the per-bucket database path/filename literal
  (`storage_root / "buckets" / bucket_id / "db" / "cadrumo.db"` and its
  `BUCKET_DATABASE_FILE` taxonomy member), not the Step's full ~108-file /
  ~350-site corpus. `S78` stays unchecked; a ten-file batch against a
  stated ~108 would misrepresent the Step as closed.
- **Enumeration method (amended)**: unrecoverable. This record's own text
  describes the ten files as "pre-identified" without stating how the list
  was produced, and nothing in the tree records the selection method --
  neither a saved grep command, a script, nor a cross-referenced task
  description. The site list below IS recoverable from the two commits
  this batch's own description matches (`722cdc1c67`, "declare
  route-classification cadrumo.db literals as pins, not drift"; `278d1c6d8a`,
  "migrate scaffolding db-path literals onto bucket_paths().database_file"
  -- their diffs are exactly the 4 migrated / 7 declared-pin split this
  record states), so the WORK is reconstructable even though the SELECTION
  is not. Recorded as unrecoverable rather than reconstructed with a
  plausible-sounding method neither commit's author is confirmed to have
  used.
- Migrated three files (four occurrences) onto `bucket_paths(...)
  .database_file`: `entrypoints/cli/_config/tests/test_certificate.py`
  (3x, each feeding `_blocking_certificate_secret_event_commit(db_path)` --
  scaffolding to locate the file, not the subject),
  `domain/tests/test_runtime_repository_enrollment.py` (2x, splitting the
  two literals on one expression -- kept `tmp_path / "cadrumo-storage"` as
  the default-settings-root claim, migrated only the
  `buckets/.../db/cadrumo.db` tail), `entrypoints/cli/tests/
  test_workflow_surface.py` (1x, feeding a raw-bytes plaintext-leak check).
  All green under their real markers.
- Declared, not migrated: `core/tests/test_storage_route_classification.py`
  (7 occurrences). `classify_storage_route`'s `database_path` assertions
  check an end-to-end round trip (Settings URL derivation plus
  classification) against the real on-disk shape, independent of what
  `bucket_paths()` computes internally -- migrating collapses the
  assertion to the accessor compared against itself. Two of the seven are
  `not (...).exists()` refusal guards for the former-product `aeat.db`
  case: an absence assertion is trivially satisfied by a wrong path, so a
  literal is the only form that still fails loudly if the accessor pointed
  elsewhere. Added a module docstring recording both reasons, matching the
  declaration already present in `test_layout.py` and
  `test_login_throttle.py`.
- Confirmed two of the ten pre-identified files carry no genuine
  occurrence of this Step's stated literal shape: `tests/
  test_storage_provenance_gate.py`'s only hit is a synthetic
  detector-input string inside the provenance gate's own AST-scanner test,
  not a real path assertion (and its `PENDING_ENROLLMENT` table is already
  the closed empty tuple); `core/tests/test_storage_taxonomy.py`'s `"db"`
  literal is `BUCKET_DATABASE` (the directory), a sibling taxonomy member
  outside this Step's `BUCKET_DATABASE_FILE` scope, and is already the
  taxonomy accessor's own correct self-test oracle. Neither file was
  edited.
- Confirmed the remaining named files needed no action: `core/tests/
  test_storage_taxonomy_name_unification.py` already carries an explicit
  R14 declaration for the same discrimination (found during `S77`);
  `bucket/tests/test_layout.py` and `bucket/tests/test_keystore_paths.py`
  already carry theirs (also `S77`); `tests/test_secure_sql.py` was
  confirmed still dirty with unrelated peer WIP and was not touched.
- Ran the full suite for every edited or read module
  (`test_certificate.py` and `test_workflow_surface.py` under
  `-m integration`, the rest under the default unit marker): all green.

## Outcome

Four occurrences across three files migrated onto the canonical
accessor; seven occurrences in one file declared as deliberate pins with
an inline rationale; two of the ten pre-identified files found to carry
no genuine occurrence of the Step's stated literal shape. `S78` remains
open: this batch closes ten named files against the Step's ~108-file
corpus, not the Step itself.

## Description (continued, treegates' literal-band batches)

Method divergence, recorded as fact rather than apology: the Step's own
text specifies one test package at a time, each gated by the provenance
gate scoped to that package. Every batch below (and the ten-file batch
above) instead worked by literal band -- one taxonomy-vocabulary word
across the whole test corpus -- verified with `ruff check`/`ruff format`
plus a targeted `pytest` run named per batch, never the package-by-package
provenance-gate walk the Step specifies. No package-by-package walk
exists anywhere in this feature's history. `S78` stays open under this
divergence too: closing it as written would require re-running the
literal-band work as a package walk, which did not happen.

Enumeration method, common to every batch below unless stated otherwise:
an ad hoc AST scan (not the Step's provenance gate) over every
`src/cadrumo/**/tests/*.py` file, matching string constants that are the
operand of a `/` `BinOp` or an argument to `joinpath`/`glob`/`rglob`, then
cross-referencing each module's `PINNED_TAXONOMY_LITERALS` declaration
(also read via the same AST walk) to separate already-declared sites from
open ones. A raw substring scan was tried first and discarded: it
inflated every band's true count by counting CLI argv tokens (`["app",
"live", ...]`) as if they were path segments -- confirmed directly by
diffing the two instruments' output on the "live" and "runs" bands, where
raw substring reported roughly 60-65 hits each and the AST instrument
reported 4-8 genuine path-composition sites.

- **`secrets`** (`dee79c3a3b`, `4d60fc7125`, `fdf203ed7d`). Enumeration:
  AST scan as above. Verification: targeted `pytest -n 0` per file named
  below (not the full suite). Site list: `test_bundle_export_recovery.py`,
  `_registry_cli_fixtures.py`, `test_m145_communication_cli.py` -- reverted
  from an earlier wrong "fallback-store" rename back to "secrets" and
  declared `PINNED_TAXONOMY_LITERALS`, because each spawns a CLI subprocess
  that must independently locate a master key an `isolated_profile_storage_root`
  / `isolated_runtime_profile` fixture already minted under the real
  taxonomy default; renaming only the subprocess override broke the
  handoff with a "no active profile" refusal (13/13 and 3/3 failures
  respectively, both reproduced before the revert). `test_custody_enrollment_prompt_guard.py`
  -- two sites renamed "secrets" to "fallback-store", genuinely injected
  (no fixture dependency), landed late after being edited and tested but
  never committed in an earlier session. `test_cli_startup_smoke.py`,
  `test_profile_login_session_lifecycle.py` -- confirmed self-contained
  (no `isolated_profile_storage_root`/`isolated_runtime_profile` use) and
  landed clean, also recovered from an earlier uncommitted state.

- **`master.recovery.key`** (`05efc71958`, `50ec933ca2`). Enumeration: AST
  scan as above. Verification: read against `_RECOVERY_WRAP_FILENAME` in
  `_custody.py` and `StorageCategory.SECRETS_MASTER_RECOVERY_KEY`'s declared
  subpath; no test run needed since no code changed, only
  `PINNED_TAXONOMY_LITERALS` declarations. Site list: all 20 hits across 6
  files (`test_recovery.py`, `test_recovery_facade.py`,
  `test_custody_enrollment_passphrase_channel.py`, `test_custody_store_matrix.py`,
  `test_custody_enrollment_prompt_guard.py`, `test_config_recovery_lifecycle.py`)
  declared pinned: the recovery-envelope provider chooses the filename, the
  caller supplies the directory -- the same boundary already drawn for
  `master.key`/`master.kdf`. One follow-up correction: the `not (...).exists()`
  refusal guard in `test_custody_enrollment_passphrase_channel.py` had been
  given the generic "provider chooses the filename" reason; corrected to
  the refusal-guard-specific reason (a wrong path trivially satisfies the
  assertion), matching `test_custody_enrollment_prompt_guard.py`'s existing
  phrasing.

- **`registry`** (`66d1b2951c`). Enumeration: AST scan as above, 54 raw
  hits across 24 files. Verification: none needed, declaration-only
  (both sites already correct accessor self-tests). Site list: 52 of 54
  are a different-namespace collision with the bundled calculation-registry
  TOML authoring tree (`_data/registry/aeat/...`), left untouched; 2 are
  the genuine `StorageCategory.REGISTRY_DISK_CACHE` (`cache/registry`)
  storage-taxonomy pin, declared.

- **`live`** (`a0b128e2c7`). Enumeration: AST scan as above, 5 raw hits in
  `application/live/tests/`. Verification: none needed, declaration-only.
  Site list: all 5 declared pins -- 3 are `not (...).exists()` refusal
  guards proving captured PII never leaks into a plaintext audit-trail file
  (`test_expedientes.py`, `test_notifications.py`, `test_verify.py`); 1
  mirrors `StorageCategory.AUDIT_LIVE_IVA_WALLET`'s declared subpath the
  same way the `SECRETS_MASTER_KEY` family does (`AUDIT` is
  operator-overridable, so production reads the same bare leaf names off
  the accessor-derived root rather than calling `storage_path()` directly).
  This band's outcome (5/5 genuine pins) explicitly refuted a predicted
  "mostly injected, will collapse like the other bands" hypothesis stated
  before the sweep.

- **`runs`** (`df842a9fd8`, `624ee75618`). Enumeration: AST scan as above.
  Verification: per-file `pytest` runs, all green. Site list: 2 genuine
  pins (`test_storage_scope.py`'s widened marker; `test_run_trace_shape_conformance.py`'s
  positive-control malformed run-id shape); 9 injected sites renamed
  `"runs"` -> `"probe-runs"` (`test_config.py`'s env-anchoring round-trip
  test, plus 8 `CADRUMO_RUNS_DIR`/`cadrumo_runs_dir` overrides confirmed
  self-contained -- none derives its runs directory from a sibling
  `isolated_profile_storage_root`/`isolated_runtime_profile` fixture, since
  only `cadrumo_secret_store_dir` is accessor-derived by those fixtures).

- **`financial`** (`1a89afbc82`). Enumeration: AST scan as above, 29 raw
  hits. Verification: none needed for the pins (accessor self-tests); the
  2 renamed sites' owning suites green. Site list: 4 genuine pins
  (`test_storage_scope.py`'s widened marker; `test_storage_materialisation_parity.py`'s
  detector's own ancestor-segment example); 2 injected sites renamed to
  fictional segments (`test_config.py`'s env-round-trip anchoring test;
  `test_rotation.py`'s lock-target-matching test, `store_dir` a
  caller-supplied `RotationPlanEntry` parameter); 22 of 29 are a
  different-namespace collision with the bundled ledger/financial-provider
  fixture corpus (`FIXTURES_DIR / "financial"`), left untouched.

- **`cache`** (`76b9575eb2`). Enumeration: AST scan as above. Verification:
  per-file `pytest` runs across the touched files, all green. Site list: 10
  genuine pins (default-derivation and accessor self-tests for
  `REGISTRY_DISK_CACHE`, corpus-text cache, validation-verdict cache;
  positive-control malformed shapes for llm-cache and registry-verdict;
  the materialisation-parity detector's own ancestor-segment example,
  widened alongside its existing "financial" marker); 11 injected sites
  renamed `"cache"` -> `"probe-cache"` across `test_cache.py`,
  `test_redaction.py`, `test_client.py`, `test_live_anthropic.py`
  (`LLMCache.root_dir` is a constructor parameter, never a taxonomy
  accessor; confirmed not entangled with
  `isolated_profile_storage_root`/`isolated_runtime_profile`, since neither
  fixture derives `cadrumo_llm_cache_dir`).

- **`drafts`** (`fc3ef4c951`). Enumeration: AST scan as above, 15 raw hits
  across 11 files (one already pinned by a prior pass). Verification:
  full `pytest` run across the 10 touched files (`-m ""`), 119 passed, 1
  pre-existing unrelated failure (see below); `ruff check`/`ruff format`
  clean. Site list: 5 sites in `test_rotation.py`
  (`RotationPlanEntry.store_dir`, a generic caller-supplies-the-directory
  mechanism with no taxonomy dependency) plus 9 occurrences of the same
  "populate every `Settings` dir field with a tmp_path subdir" boilerplate
  builder across `application/review`, `application/setup`,
  `domain/calculations/registry`, and `entrypoints/cli` test files, all
  renamed `"drafts"` -> `"probe-drafts"` after confirming
  `drafts_pending`/`ModeloDraftRepository` read from secure SQL storage,
  never the filesystem `cadrumo_drafts_dir` field, and none of the ten
  files import `isolated_profile_storage_root`/`isolated_runtime_profile`.
  The one remaining `"drafts"` site (`test_output_dir_state_root.py`) is
  the real default-derivation assertion its own `PINNED_TAXONOMY_LITERALS`
  already defends -- left untouched, correctly resolved before this batch.

- **`logs`** (`f9cb8468c7`). Enumeration: AST scan as above, applied across
  7 files. Verification: 54 unit tests plus 21 of 22 integration tests
  passed; the one integration failure
  (`test_installed_console_exposes_contextual_product_identity`) is
  pre-existing and unrelated -- it hardcodes `__version__ == "0.2.1"` while
  the installed console reports the current `0.2.2`, and this batch
  touched only docstrings, one import, and rename sites, never that
  assertion (the stale pin was later deleted outright as part of `#56`'s
  `StoragePathAnchor` work, `ccff620297`, once its root cause -- a
  deliberate version bump nobody updated the test for -- was confirmed).
  Site list: 3 sites renamed `"logs"` -> `"probe-logs"` in
  `test_logging.py`; 2 in `test_logging_rotation.py`; 4 in
  `test_path_resolution_memo.py`; 4 in
  `test_collection_storage_root_log_lock.py`; 1 targeted rename in
  `test_logging_override.py` (leaving a second, genuinely-different
  `.name ==` default-assertion site on the same literal untouched); 2
  pins declared in `test_json_error_contract.py` and
  `test_root_help_shape.py` (both default-derived: the crash-subprocess
  and `_console_env` harnesses set `cadrumo_local_storage_root` with no
  log-directory override, so `<root>/logs` is the real unoverridden
  default the `config repair logs` output must report). This batch was
  authored across a session boundary; the working tree was rescued and
  committed by a teammate, verified line-by-line against the authoring
  session's own edits before landing.

Separately, two ad hoc structural items landed under the same `S78`
umbrella but scoped to `_storage_path_definitions.py` rather than a test
literal, tracked as their own team-lead-assigned items (not part of the
literal-band burndown method above, so not subject to the same
enumeration-method note): interpolating the eleven `STORAGE_PATH_DEFINITIONS`
grammars S114 had not covered (`520f74f769`), and the `StoragePathAnchor`
docstring/gate-widening correction (`156dc48b24`, superseded by
`ccff620297` after three proposed justifications were each measured and
refuted in turn).

## Outcome (continued)

Roughly 95 individual sites classified across 9 literal bands (secrets,
master.recovery.key, registry, live, runs, financial, cache, drafts,
logs): about half declared as genuine storage-taxonomy pins with an inline
or `PINNED_TAXONOMY_LITERALS`-declared reason, the rest renamed to a
`probe-`/fictional segment once confirmed free of any cross-process
fixture dependency. Two renames were caught and reverted after breaking a
real fixture handoff, both before landing. `S78` remains open: none of
this closes the Step's ~108-file / ~350-site corpus or satisfies its
stated package-by-package provenance-gate method: this record exists so
that gap is visible rather than merely relayed. `#49`'s own accounting
(442 path-composition hits in files without a pin declaration measured at
`5da2b328f9`) makes explicit that most raw hits are correctly-untouched
different-namespace collisions, not remaining work -- but the tree cannot
distinguish "correctly untouched" from "never examined" for any band this
record does not name, which is the reason this record exists.

## Notes (continued)

No incidents, no data loss, no `rm`/`Remove-Item` of any form across any
of the batches above. Two genuine near-misses, both caught before
landing rather than after: a rename that broke a cross-process fixture
handoff (`secrets`, reproduced and reverted twice, independently, in two
different files across two different sessions -- the same mistake was
not learned from the first time), and uncommitted work surviving across
a session boundary three separate times (`test_custody_enrollment_prompt_guard.py`,
the `test_config_reset_recovery.py` trio, and the full `logs` band),
each recovered by reading the dirty working tree rather than by
re-deriving the work. The enumeration-method gap this record's opening
section names -- literal-band sweeps verified by targeted suites, not the
Step's specified package-by-package provenance-gate walk -- applies to
every batch in this continuation exactly as it does to the ten-file batch
above.

## Batch: scanner tooling built to support this Step's triage

Not a literal-migration batch; the supporting instrument several later
batches (`secrets`, `registry`, `drafts`, `master.recovery.key`, `cache`,
`logs`, the small-band tail) read against.

- **Enumeration method**: extended `dev/write_site_census.py`'s
  `--scope production` write-primitive census with a `--scope tests`
  walk. Two site-discovery mechanisms feed one shared classification
  path (`classify()`, `_is_constrained()`): the existing write-primitive
  gate (`write_target()`), plus a new maximal-`/`-join-chain walk
  (`_top_level_div_chains()`) that also reaches bare path expressions no
  write primitive ever consumes (a fixture lookup fed to `open(..., "rb")`,
  a dict value handed to an env-var override, a path built only to appear
  on the right of an `assert`) -- the shape the `--scope production` gate
  was correctly narrow enough to miss. Also added a `fixture` provenance
  bucket (`FIXTURES_DIR`/`bundled_path`, following import aliases through
  `_bindings()`) so a bundled-corpus reference is not misclassified as a
  taxonomy write site.
- **Verification actually run**: 65 unit tests in
  `dev/tests/test_write_site_census.py` pinning each new primitive's
  discrimination in both directions (real shape vs. lookalike), including
  a real-`git ls-tree` disjoint-partition check between
  `production_modules()`/`test_modules()`. A follow-on "injected-but-
  constrained" co-occurrence heuristic (`WriteSite.constrained`) was
  built, measured against three known-positive oracles and the discard
  population it silently produced, found to miss 2 of 3 oracles and
  over-fire roughly 30x tree-wide, and retired as untrusted rather than
  shipped -- full diagnosis, decision history, and two in-place
  corrections in `.vault/audit/2026-08-04-canonical-storage-management-constrained-detector-sweep-diagnosis-audit.md`.
  Also fixed a pre-existing `--json`-mode crash (`site.__dict__` on a
  `slots=True` dataclass) found while extending the tool.
- **Site list**: not applicable in the literal-migration sense -- this
  batch is the instrument, not a set of edited test files. The instrument's
  own sweep output (the flagged/discard split, the oracle validation, the
  per-mechanism over-firing breakdown) is the site list, and it lives in
  the audit document above rather than duplicated here.
- **Commits**: `1cd16de6c3` (`--scope tests` walk), `5d0af05dd3` (constrained
  detector, later retired), `8f0981a2d1` (retraction/revert of an attempted
  signal-set fix once a sampled-recall measurement disqualified it).

This Step remains open. The scanner did not close any literal band itself;
every band closed in this campaign (`secrets`, `registry`, `blobs`,
`cadrumo.db`, `justificantes`, `manifest.toml`, `cache`, `logs`,
`master.recovery.key`, the small-band tail) was closed by a human reading
the sites the write-primitive gate or the `--scope tests` walk surfaced,
not by the tool alone.

## Batch: `drafts` literal band (`StorageCategory.DRAFTS`)

Method divergence recorded as fact: the Step's specified gate (provenance
gate scoped to the package, plus that package's own suite) did not run.
Execution was a targeted `rg` sweep plus reading, verified with `ruff` and
no test edits (nothing needed migrating), not a package-by-package walk.

- **Enumeration method**: `rg '"drafts"'` across `src/cadrumo` (23 raw
  hits), then a manual AST-shape filter to the same corrected definition
  this Step's later bands used -- a string constant that is a `/` operand
  or a keyword-argument value feeding one (`tmp_path / "drafts"`,
  `cadrumo_drafts_dir=tmp_path / "drafts"`), excluding set/tuple
  membership literals, a dict value mapping a settings-field name to its
  subpath, an enum-value assignment (`DRAFTS = "drafts"`), the taxonomy's
  own `subpath=` declaration, and a dict-subscript assertion. The
  prediction (low collapse: no known different-namespace collision, the
  domain's English word `drafts` has no Spanish-stem competitor the way
  `borrador` does) was stated in
  `.vault/audit/2026-08-04-canonical-storage-management-collapse-predictor-verification-audit.md`
  before this enumeration was read, not after.
- **Verification**: no code changed (all 15 sites already resolve through
  the real `cadrumo_drafts_dir` settings field), so verification was the
  read itself -- confirmed each of the 15 against its call site, plus one
  cross-check that the word's only OTHER referent in the codebase
  (`filing_drafts.py`'s SQL-backed `ModeloDraft` repository, namespace
  `"cadrumo.domain.filing.drafts"`) is a dot-separated namespace string,
  never a `/`-joined path segment, so it does not collide with the
  path-composition definition above. `ruff check` clean (no files touched).
- **Site list**: 15 of 23 raw hits are genuine path-composition sites, all
  15 already enrolled via `cadrumo_drafts_dir` --
  `adapters/persistence/storage/tests/test_rotation.py` (5),
  `application/review/tests/test_adapters.py`,
  `application/review/tests/test_aggregator.py`,
  `application/review/tests/test_confidence_filter.py`,
  `application/setup/tests/test_cli.py`,
  `core/tests/test_output_dir_state_root.py`,
  `domain/calculations/registry/tests/test_inss_maternidad_paternidad_art7h.py`,
  `entrypoints/cli/tests/test_language_flag_help_honesty.py`,
  `entrypoints/cli/tests/test_repair_privacy_contract.py`,
  `entrypoints/cli/tests/test_root_help_shape.py`,
  `entrypoints/cli/tests/test_workflow_surface.py`. Disposition for all 15:
  already-enrolled, no action. The other 8 raw hits are non-path-composition
  mentions (excluded above), no action.
- **Reference**: full prediction-versus-measured writeup in the audit
  document cited above; no separate commit, since nothing was edited.

**Reconciliation, added by treegates**: this batch's "already-enrolled, no
action" disposition on the same 15 sites is superseded by the `drafts`
entry earlier in this record (`fc3ef4c951`). "Enrolled via `cadrumo_drafts_dir`"
(the settings field the site sets carries the real field name) and "a
genuine default-derivation pin" (the VALUE assigned to that field is
actually consulted by the code path under test) are different claims --
`drafts_pending`/`ModeloDraftRepository` load drafts from secure SQL
storage and never read the filesystem `cadrumo_drafts_dir` field for
these test paths, so the value each site assigned it was inert
regardless of what it said, and 14 of the 15 were renamed
`"drafts"` -> `"probe-drafts"` rather than left as-is. Left in place
rather than corrected in place: the discrepancy is itself evidence for
this Step's own finding that no two lanes' classification passes agreed
on the same site without cross-checking, and deleting the earlier read
would erase that evidence. (This batch's text predates any edit by
`census` -- it landed with `4297576fda`; the reconciliation is not a
correction of `census`'s work.)

Cross-reference to the dormancy lineage: `cadrumo_drafts_dir` has exactly
three non-test production references -- `core/config.py`'s own `Field`
declaration and a settings-field name list, `_storage_taxonomy_locations.py`'s
`settings_field=` declaration, and `_rotation.py`'s
`default_rotation_plan`, the only site that actually READS it
(`settings.cadrumo_drafts_dir`). No production reader ever consults the
value for anything a draft-loading test path exercises -- the same shape
as `JUSTIFICANTES`, `ATTACHMENTS`, and the other rotation-only entries
`conv2` catalogued from the opposite direction (reading production
docstrings for a stated no-filesystem-write claim). This reconciliation
re-derives the same fact for `DRAFTS` by asking what actually consumes
the field rather than what claims to; the two are the same finding
reached two ways, not two findings.

**Provenance note**: the four batches below (`secrets`, `manifest.toml`,
`iva-wallet`/`invoices`/`llm-cache`/`llm-usage`/`llm-run-telemetry`, and the
small-band tail) were authored by a different lane than the sections above
this note. The commit that landed all of them together
(`docs(exec): record treegates' S78 literal-band batches and the method
divergence`) attributes the whole diff to one lane by subject line, because a
pathspec commit takes the working tree for the named path -- it landed these
four sections along with the others in one hunk. Recorded here so a reader
tracing authorship by commit subject alone does not misattribute.

## Batch: `secrets` literal band (`StorageCategory.SECRETS`)

Method divergence recorded as fact: the Step's specified gate (provenance gate
scoped to the package, plus that package's own suite) did not run. Execution
was a raw literal grep across the whole `src/cadrumo` tree, filtered to test
paths after the fact, not a package-by-package walk.

- **Enumeration method**: `git grep -nE "['\"]secrets['\"]" -- 'src/cadrumo' |
  grep -i "/tests/"` (exact-quoted literal grep). 26 hits / 11 files measured
  at the cited pin `0341f5864d`; 21 hits / 7 files at HEAD `08705ee6f0` --
  four files (`test_config_reset_recovery.py`, `test_custody_enrollment_prompt_guard.py`,
  `test_cli_startup_smoke.py`, `test_profile_login_session_lifecycle.py`) had
  already been fixed by other lanes between the pin and HEAD, not by this pass.
- **Verification actually run**: no code changed (every remaining site was
  already correctly resolved), so verification was reading each site against
  its module's `PINNED_TAXONOMY_LITERALS` declaration. No `ruff`/`pytest`
  invocation, since nothing was edited.
- **Site list**: 21 sites across 7 files. 18 code-level sites already
  pin-declared -- `tests/test_storage_scope.py`, `core/tests/
  test_storage_substrate_state_root.py`, `entrypoints/cli/tests/
  test_cold_start_wizard_registration.py` (each declared before this pass),
  `core/tests/test_ensure_storage_tree.py` and `core/tests/
  test_output_dir_state_root.py` (declared by a peer commit `d80e996623`
  landing concurrently with this read). 2 sites are pure docstring prose, not
  code (`adapters/persistence/storage/master_key/tests/
  test_master_key_file_fallback.py`, `tests/
  test_isolation_fixture_state_root_coverage.py`). A wider net beyond the
  exact-quote pattern found 2 more sites correctly out of scope: `core/tests/
  test_config_state_root.py`'s `"operator-secrets"` (an injected override
  deliberately renamed off the real vocabulary, same shape as the accepted
  `"fallback-store"` precedent) and `entrypoints/cli/_config/tests/
  test_status_frontend_gate.py`'s `"secrets.api_token"` (a profile-field
  mask-path string, different namespace entirely). Disposition: zero migrate,
  no commit from this pass -- everything was already resolved by the time it
  was read.
- **Note**: a separate lane (`treegates`) independently found and reverted
  three sites in this same corpus that HAD been incorrectly renamed away from
  `"secrets"` earlier in the campaign, breaking a cross-process fixture
  handoff (`isolated_profile_storage_root` mints a master key at the real
  taxonomy default; a CLI subprocess spawned by the same test must
  independently locate it, and the earlier rename pointed the subprocess's
  literal at a location the fixture never wrote to). Reverted at `dee79c3a3b`;
  verified post-hoc against HEAD by this pass, not touched further.

## Batch: `manifest.toml` literal band (bucket manifest, distinct from the registry's own directory-mode manifest.toml)

Method divergence recorded as fact: the Step's specified gate did not run.
Execution was a literal grep, corrected mid-pass for an instrument bug, not a
package-by-package walk.

- **Enumeration method**: `git grep -n '"manifest\.toml"'` (escaped dot).
  The first pass used an unescaped `"manifest.toml"` regex, where the bare
  `.` matched any character and silently caught every occurrence of the
  unrelated function name `_manifest_toml` (definition and every call site)
  in `application/workflow/tests/test_profile_bucket_scan.py`, inflating
  that file's count from 6 to 11. Caught and corrected before landing
  anything, by re-running with the dot escaped. Final count at HEAD: 45 raw
  hits / 20 files, split into two namespaces by reading each site -- 34
  hits / 15 files are the calculation registry's own directory-mode
  fragment manifest (`domain/calculations/registry/tests/`,
  `core/tests/test_resources.py`'s `packaged_data(...)` tuples,
  `core/tests/test_modelo.py`, `core/tests/test_toml_registry_parity.py`,
  `locales/tests/test_modelo_manager.py` -- same filename, unrelated
  concept, out of this band's scope), and 11 hits / 5 files are the bucket
  manifest this band covers.
- **Verification actually run**: `ruff check` on the four edited files
  (`application/wizard/tests/test_create_pointer_atomicity.py`,
  `entrypoints/cli/tests/test_profile_lifecycle_verbs.py`,
  `application/workflow/tests/test_profile_bucket_scan.py`,
  `entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`) --
  clean. `pytest` on the same four files plus `core/tests/
  test_storage_taxonomy.py` (read, not edited): 36 passed.
- **Site list**: 10 of the 11 bucket-manifest sites migrated onto the
  canonical `BUCKET_MANIFEST_FILENAME` constant -- two duplicated
  `_bucket_directories_without_manifest` helpers (one site each), six
  malformed-manifest write targets in one file, two real-CLI-output reads
  in a third file. The eleventh (`core/tests/test_storage_taxonomy.py:293`)
  stays a literal: it tests `bucket_scoped_storage_path` directly
  (accessor-is-the-subject), so composing the expectation independently is
  the point. Commit `26beb3cace`.

## Batch: `iva-wallet` / `invoices` / `llm-cache` / `llm-usage` / `llm-run-telemetry` literal bands

Method divergence recorded as fact: the Step's specified gate did not run
for any of these five. Execution was a literal grep per band, reading only
-- no files were edited in this batch.

- **Enumeration method**: `git grep -c '"<literal>"' -- 'src/cadrumo' |
  grep -i "/tests/"` per band, exact-quoted. Raw hit counts at the time of
  reading: `iva-wallet` 26, `invoices` 21, `llm-cache` 21, `llm-usage` 19,
  `llm-run-telemetry` 14 (these differ slightly from the ~26/20/19/17/12
  figures cited in the assignment; treated as independent re-measurement,
  not a correction of someone else's count).
- **Verification actually run**: reading only. No `ruff`/`pytest`
  invocation in this batch, since nothing was edited.
- **Site list and disposition, per band**:
  - `iva-wallet`: 24 of 26 sites are a Typer CLI command-group name
    (`aeat app modelo iva-wallet correct/seed/balance`, `aeat app live
    iva-wallet pull/history`) across seven CLI/MCP test files -- different
    namespace, out of scope. The remaining 2
    (`application/live/tests/test_iva_wallet_live.py:50,54`,
    `settings.cadrumo_audit_dir / "live" / "iva-wallet"`) were independently
    resolved by a peer commit (`a0b128e2c7`, pin declaration with rationale)
    landing while this band was being read; not touched.
  - `invoices`: collapses to zero migrate work, but not into the same
    shape as `iva-wallet`. ~6 sites are dict/payload keys or a source
    package path (different namespace); ~11 sites are `cadrumo_invoices_dir=
    tmp_path / "invoices"` via `override_settings`/`Settings()` -- the
    sanctioned override mechanism, not a hand-composed path bypassing it;
    ~2 sites build synthetic path sets to test a comparison algorithm
    directly (accessor-is-the-subject); 2 sites are the existing pin
    declaration and its on-disk-name oracle assertion.
  - `llm-cache` / `llm-usage` / `llm-run-telemetry`: majority of each band
    (13 / 9 / 12 sites respectively) are `LLMCache`/`UsageRecorder`/
    `LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-...")` -- a genuine
    constructor-override parameter (`root_dir: Path | None = None`,
    defaulting to the real settings field), checked explicitly for the
    injected-but-constrained trap (no subprocess or sibling fixture in
    these files recomputes the same path independently) and found clean.
    2 sites per band are the existing pin declaration. `llm-usage` carries
    6 further different-namespace sites (`aeat app diagnostics llm-usage`,
    also a CLI verb). A few grammar-conformance sites deliberately build a
    malformed path resembling the real shape to prove a shape-validator
    catches the defect (accessor-is-the-subject).
- **A judgment call raised, not made unilaterally**: the ~34 injected
  `root_dir=tmp_path / "llm-..."` sites across the three `llm-*` bands
  coincide with an already-pinned taxonomy word, matching the shape of the
  `"fallback-store"`/`"operator-secrets"` rename precedent. Not renamed:
  unlike those precedents, no test in these files makes an adjacent claim
  about the real default that the literal could be confused with. Flagged
  to `team-lead` rather than executed silently; no further instruction to
  proceed was given, so the sites remain untouched.
- **Commits**: none. Every site in this batch was already correctly
  resolved (pin, injected-via-sanctioned-mechanism, accessor-is-the-subject,
  or different-namespace) by the time it was read.

## Batch: small-band tail -- `tokens`, `filed-declarations`, `filed-history`, `cadrumo.log`, `attachments`, `active-profile`, `transactions`, `corpus-text`, `submissions`, `usage-ratios.json`, `bucket.dek.json`, `reset-operations`, `registry-verdict`

Method divergence recorded as fact: the Step's specified gate did not run.
Execution was a literal grep per segment, reading exhaustively rather than
sampling, not a package-by-package walk.

- **Enumeration method**: `git grep -n '"<segment>"' -- 'src/cadrumo' |
  grep -i "/tests/"` per segment, exact-quoted, 58 hits / 40 files total
  across the 13 segments as assigned.
- **Verification actually run**: `ruff check` on the seven edited files
  (listed below) -- clean. `pytest` on the same seven files: 23 passed.
- **Site list and disposition**:
  - 5 sites migrated onto a real accessor across 5 files:
    `bucket.dek.json` at `adapters/persistence/storage/tests/
    test_rotation_crash_windows.py:184` and `entrypoints/cli/tests/
    test_config_custody_profile_lifecycle.py:137` -> `BUCKET_DEK_FILENAME`;
    `active-profile` at `entrypoints/cli/tests/test_fast_path_no_state.py:108,119`
    and `entrypoints/cli/tests/test_ledger_exception_propagation.py:79`
    -> `pointer_path()` (a local variable shadowing the imported function
    renamed `pointer_file`); `attachments` at `domain/attachments/tests/
    test_repository.py:129` -> `storage_path(StorageCategory.ATTACHMENTS)`,
    whose own assertion is that this location never materialises, since
    `AttachmentStore` persists to the encrypted SQL substrate rather than
    the filesystem.
  - 2 files gained a `PINNED_TAXONOMY_LITERALS` declaration they were
    missing despite carrying accessor-is-the-subject sites:
    `application/tests/test_config_reset_repository.py` (`reset-operations`,
    previously undeclared) and `tests/test_storage_scope.py` (adding
    `transactions`, already used at two sites but absent from an existing
    declaration a peer had landed concurrently for other segments).
  - The remaining 8 segments (`tokens`, `filed-declarations`,
    `filed-history`, `cadrumo.log`, `corpus-text`, `submissions`,
    `usage-ratios.json`, `registry-verdict`) were read exhaustively across
    every raw hit and found already correctly resolved: pin /
    accessor-is-the-subject, injected via `override_settings`/`Settings()`,
    or different-namespace (dict/payload keys, source package paths, JSON
    response count fields, a synthetic pydantic model's own default for a
    detector's self-test). Zero migrate beyond the 5 sites above.
- **Commit**: `7275e20b22`.

## Batch: `cadrumo.db` literal band (`BUCKET_DATABASE_FILE`, seven-chunk migrate population)

Method divergence recorded as fact, same shape as every batch above: the
Step's specified gate (provenance gate scoped to the package, plus that
package's own suite) did not run. Execution was a full per-site read of
every raw hit, chunked by directory for landing, each chunk verified with a
targeted `pytest` run plus `ruff check` -- not a package-by-package
provenance-gate walk.

This band was assigned as a coarse pattern-sample first; team-lead required
the full per-site read before any chunk landed, on the stated reasoning
that a wrong `migrate` classification is silent (a test that passes while
defending nothing) where a wrong `injected` rename is loud (an immediate
red test) -- so sampling cannot substitute for reading every site. The
full read, not the sample, is what this record reflects.

- **Enumeration method**: a raw literal grep for `"cadrumo.db"` across
  `src/cadrumo`, filtered to test paths, followed by a full per-site read
  of every hit (not a sample) classifying each as MIGRATE / PIN / INJECTED
  / different-namespace / accessor-is-the-subject, per the same discipline
  the rest of this Step's bands used. The equality-target rule applied
  throughout: an assertion comparing the taxonomy accessor's output
  against an independently-written literal is safe to migrate onto the
  same accessor; an assertion comparing the accessor against ANOTHER call
  to the same accessor is not, because migrating the literal side
  collapses the check to the accessor compared against itself. "Does the
  accessor have an opinion about this property" is not the right
  question -- what matters is what sits on the OTHER side of the
  comparison.
- **Verification actually run, per chunk**: a targeted `pytest` invocation
  scoped to that chunk's touched files (never the full suite) plus `ruff
  check` on the same files, both green before landing; each chunk
  committed separately, `git show <sha> --numstat` checked against the
  stated file/insertion counts before moving to the next chunk.
- **Site list**: 45 MIGRATE sites across 28 files, landed in seven chunks
  chunked by directory, each chunk's commit stating its own file and site
  count (verified again here against the commits' own `--stat` output,
  totalling exactly 45/28):
  - Chunk 1/7 (`91921ad634`, storage): `test_wal_sidecar_accounting.py`,
    `test_submission_repository.py` -- 2 files, 3 sites. The local
    `_db_path(db_dir)` helper wrapping the same join at two call sites was
    deleted rather than kept as a second wrapper around the accessor.
  - Chunk 2/7 (`f0b748ca8a`, `application/live/tests`): 8 files, 11 sites
    (`_filed_capture_history_support.py`, `test_borrador_100_roundtrip.py`,
    `test_expedientes.py`, `test_iva_remote_state_acquisition.py`,
    `test_iva_wallet_capture_backend.py`, `test_justificante_capture.py`,
    `test_notifications.py`, `test_verify.py`).
  - Chunk 3/7 (`5b73dcb883`, application/workflow + user_profile +
    calculations + domain/usage_ratios): 4 files, 10 sites
    (`test_observations_repository_roundtrip.py`, `test_lifecycle.py`,
    `test_per_bucket_engine_isolation.py`, `test_service.py`).
    `test_per_bucket_engine_isolation.py`'s structural assertion
    (`a_db.parent.parent.name == bucket_id`) stays meaningful under the
    accessor because the comparison target is an independent literal
    (`_BUCKET_A_ID`), not a second accessor call -- the equality-target
    rule applied to a site that is NOT itself a plain roundtrip.
  - Chunk 4/7 (`2f59886f75`, `adapters/persistence/profile/tests`): 5
    files, 5 sites (`test_assets.py`,
    `test_calculation_repository_roundtrip.py`, `test_inventory.py`,
    `test_justificante_repository.py`, `test_secure_model_document.py`).
  - Chunk 5/7 (`5a9b8f20b1`, `domain/attachments` + `domain/modelos` +
    `domain/submission`): 6 files, 7 sites (`test_repository.py`,
    `test_filing_record_repository_roundtrip.py`,
    `test_participation_index_roundtrip.py`,
    `test_secure_storage_roundtrip.py`,
    `test_verification_report_roundtrip.py`, `test_repository.py`
    [submission]). Self-caught arithmetic slip, recorded in the commit
    message itself: reported as 8 sites in an earlier count, corrected to
    7 before landing -- the classification did not change, only the
    subtraction.
  - Chunk 6/7 (`73021c6b94`, `adapters/outbound/llm` + `adapters/outbound/
    aeat/sede`): 2 files, 6 sites (`test_redaction.py`,
    `test_observation_store.py`).
  - Chunk 7/7 (`d8aa97cc8c`, final, `tests/test_secure_sql.py`): 1 file, 3
    of 6 sites migrated. The other 3 in the same file stay literal on
    purpose: two (lines 90, 98) are direct consequences of
    `isolated_ephemeral_secure_sql`'s own `database_name="cadrumo.db"`
    default parameter (`tests/secure_sql.py:278`), not independent
    choices; one (line 154, `assert not (profile.storage_root /
    "cadrumo.db").exists()`) is a routing-correctness pin verifying no
    stray root-fallback file exists alongside the routed bucket database,
    not scaffolding. Mid-landing fix: line 96's `control_database` had
    been hand-composed from `storage_root` and a bucket-id string with no
    `TestRuntimeProfile` in scope at that point, so it routes through
    `bucket_paths(storage_root, bucket_id).database_file` rather than a
    `profile.paths` accessor -- caught and corrected before the chunk
    landed, not after.
- **PIN sites independently reconfirmed in this pass** (a subset of the
  wider PIN population; the remainder is reported below rather than
  re-derived): `core/tests/test_storage_route_classification.py` (7
  sites, `cadrumo.db`/`buckets`/`db`/`active-profile` in the same chained
  expressions, declared via `722cdc1c67` and independently re-read during
  the void-assertion-class audit today -- the docstring names the exact
  reason: the `database_path` round-trip assertions would tautologically
  pass against the same accessor both derivation steps already consume,
  and the two `not (... ).exists()` refusal guards would be trivially
  satisfied by a wrong accessor target); `application/tests/
  test_config_reset.py:169,214` (2 sites, an **adversarial fixture** pin,
  distinct in kind from the other seventeen: the test deliberately writes
  a decoy file literally named `cadrumo.db` at the reset root to prove the
  config-reset scanner does not mistake it for a bucket-id-named
  directory -- `assert all(target.bucket_id != "cadrumo.db" for target in
  operation.targets)` -- so the literal IS the test subject here, not
  scaffolding reaching past it, and migrating it onto the accessor would
  remove the exact decoy the assertion needs).
- **Remainder of the classification, relayed rather than re-derived in
  this pass**: the full per-site read that gated the chunking reported 19
  PIN and 3 INJECTED sites in total. 9 of the 19 PIN sites are
  independently reconfirmed above against current source; the other 10,
  and the identity of the 3 INJECTED sites, are not re-verified against
  git artifacts in this record -- they were reported to `team-lead`
  during the original read and are not reconstructed here from memory
  alone, per the standing instruction to record `NOT STATED` rather than
  invent a plausible list. A follow-up pass that re-runs the same grep
  and re-reads every non-MIGRATE hit against current source would settle
  this rather than trusting either the original report or this partial
  reconfirmation.
- **Commits**: `91921ad634`, `f0b748ca8a`, `5b73dcb883`, `2f59886f75`,
  `5a9b8f20b1`, `73021c6b94`, `d8aa97cc8c`.

## Batch: six-band closure after the goal-hook reopened the Step

The Step had been reasoned off the closure path -- the plan's own text placed
W03.P14-P16 outside the operator's sharpened criterion. A goal hook rejected
that: the standing goal says *every codesite and api has been migrated*, and a
campaign narrowing its own completion criterion and then meeting the narrowed
version is not the same thing. Reopened and burned down.

### The population moved twice, both times against the coordinator's own instrument

A fresh AST scan at `fdc82ccb61` found 417 bare taxonomy-segment literals, of
which **210 sat in genuine path-composition position** across 88 files (6
production / 204 tests). That figure was wrong twice, in opposite directions:

- **Over-reporting.** The scanner matched segment names *without their anchor* --
  this campaign's founding defect, reproduced in the instrument built to measure
  it. Measured 33% false-positive rate on the production set:
  `locales/_modelo_manager.py` roots at `bundled_path("registry","aeat")`, while
  the taxonomy's `manifest.toml` is `<root>/buckets/<bucket_id>/manifest.toml`
  anchored `storage_root`.
- **Under-reporting, twice.** Four segments (`db`, `cache`, `audit`, `blobs`)
  had been excluded as "non-discriminating" -- `blobs` explicitly because it was
  *anchor-sensitive*, which is the reason to check a segment rather than skip it,
  and `blobs`/`blobs` is this campaign's founding defect. A probe with a positive
  control (same walker, production filter removed: 0 -> 57) recovered **57 sites
  across 30 files**. Separately, a segment bound to a *constant* never enters a
  `/` chain at all, so path-position scanning is blind to it; that recovered
  **5 production sites**.

Corrected population: **261 test sites plus 6 production candidates.** The 57
recovered sites were routed to the *owning* band as addenda rather than to a
seventh lane, because 13 of their 30 files were already open on a lane's desk.

### Per-band results

| band | scope | sites | migrate | pin | false-positive | commits |
|---|---|---|---|---|---|---|
| A | `core/tests` | 53 | 0 | 27 | 15 | `85a35a5711`, `446e349fe5`, `a7c457cd23` |
| B | `adapters/outbound` | 36 | 0 | 2 | 33 | no change needed |
| C | `adapters/persistence` | 55 | 0 | 34 | 21 | `70589f8d3d`, `d705ca546f` |
| D | `entrypoints/cli` | 33 | 14 | 8 | 11 | `1e37fde8f8` |
| E | observability + calculations | 41 | 10 | 4 | 23 | `7f3c38e951` |
| F | tail | 43 | 10 | 7 | 20 | `f4532e6090` |

**123 of 261 were the scanner's false positives and 82 were legitimate pins.**
Only 34 were real migrations. A bulk migration driven off the scan output would
have destroyed more than it fixed -- including `test_rotation.py:628`, where
`buggy_roots = (storage_root / "blobs",)` preserves the pre-fix doubled-`blobs`
root as a regression proof of the campaign's founding defect.

### Production was not clean, contrary to the earlier claim

- **MIGRATED** `_secret_store.py` -- `SECRET_INDEX_FILENAME` and
  `SECRET_INDEX_SCHEMA_VERSION` folded onto the taxonomy. The schema-version
  docstring moved to the version-gate *check* it documents, after confirming it
  explained why the comparison exists rather than why the value is 1.
- **MIGRATED** `core/observability` -- the intra-core `_EVENTS_FILENAME`
  duplicate merged (`a51b1cf041`). Real stakes rather than tidiness: had the two
  drifted, events written through the sink during `run_context()` would land in a
  different file than readers look for.
- **MIGRATED** `cli/__init__.py:1204` -- the filename now reads
  `storage_location(...).subpath`. Verified structurally rather than by timing
  (the box was under 144-process load, making timing meaningless):
  `cadrumo.core` is imported at module level regardless, and `storage_location`'s
  body is `return STORAGE_TAXONOMY[category]`. The temp root stays severed;
  root-anchor and filename are separate axes.
- **PINNED** `_config_llm_fields.py:54` and `config.py:503` -- pydantic requires
  a default and deriving it closes an import cycle.
- **FACADE GAP** `SECRET_INDEX_FILENAME` was never exported from the package
  `__init__` while every sibling constant was. This explains the *origin* of the
  duplication without excusing `_secret_store.py`, which is inside the package
  and had no barrier at all.

### The pin marker now enforces something

`PINNED_TAXONOMY_LITERALS` had 41 declaring files and **zero consumers** -- every
pin verdict this campaign produced lived only in prose. `7b10b17737` makes it a
gate over two independently discovered sides (a human-authored frozenset versus
an AST walk of the module body), so a rename moves one and not the other. Its
first design was falsified by the corpus: the dominant real pin shape is a
hand-maintained oracle *table*, where the literal never enters a join chain.

### Measurement after, same instrument as the baseline

```
before  210 sites / 88 files   6 production   (fdc82ccb61)
after   170 sites / 72 files   5 production   (3ab4dac368)
```

Same scanner and same definition, so the delta is comparable. It is *not*
comparable to the 261 population, which includes the 57 sites this scanner
cannot see. Production's remaining five are the two different-tree false
positives, the two pinned-by-design, and the rotation lock-suffix convention --
all verdicted, none unmigrated.

### Instrument blind spots, and one refuted claim

Five blind spots surfaced, four in instruments this campaign built: anchor-blind
matching; four segments excluded unchecked; constants invisible to path-position
scanning; `.with_suffix()` and `.with_name()` unrecognised as chain links (caught
by the census tool's own positive control *before* shipping, having made
`_rotation.py:180` invisible); and the inert pin marker. Three independent
instruments learned the same lesson: **path-shaped matching does not find path
literals, it finds literals in path syntax.**

One coordinator claim was refuted rather than confirmed: that
`git commit -- <pathspec>` bypasses `.git/index.lock` through a temporary index.
A direct test (`git commit --dry-run -m probe -- <path>`) failed on the lock. A
lane reported the technique as confirmed, but four lanes committed within 35
seconds of one another once the lock cleared, two via the ordinary `git add`
path -- the success was a confound, not a mechanism. How commits landed during
the genuine hold is NOT STATED; no further explanation is offered.

### Open

- The anchor-aware census (`e71e798292`) is the instrument that removes the 33%
  error bar from any future residual figure. Its full-corpus run had not
  completed when this record was written, so **no anchor-resolved headline number
  is recorded here.**
- `PENDING_UNDECLARED` in the pin gate carries two live entries (`master.key`,
  `master.kdf` in `test_config_custody_profile_lifecycle.py`), shrink-only and
  reconciled by their own test.
