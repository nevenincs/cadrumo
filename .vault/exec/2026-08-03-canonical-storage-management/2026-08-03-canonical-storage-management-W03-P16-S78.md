---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:b510836132d750e055859fb8aa17960c28878167b9f82296e1593fc9821622c3'
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

## Notes

No incidents, no data loss, no `rm`/`Remove-Item` of any form. The
provenance-gate and taxonomy false positives in the originally-handed-off
file list were resolved by reading, not by editing -- two files were
correctly left untouched rather than churned against a stale count.

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
