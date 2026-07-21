---
tags:
  - '#research'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
related: []
---

# `data-output-standardization` research: `Data output location and naming standardization discovery`

Discovery for a campaign to standardize where and under what names the project
writes generated data — durable outputs, temp/scratch files, logs, caches,
diagnostic dumps, test artifacts, and dev-tool/package generators. Motivation:
the project must not pollute the operator's machine, the repo tree, or the OS
temp directory with unmanaged artifacts, and every generated file must land in
a mandated, settings-driven location under a coherent naming schema. Conducted
as a six-axis read-only discovery swarm (settings-driven locations, production
temp writers, test-suite writers, dev/packaging generators, logs/caches,
naming-schema synthesis), grounded via vaultspec-rag and confirmed against
HEAD. Prior art: the secure-persistence-foundation research (2026-04-27), the
secure-persistence-enforcement ADR (2026-05-06), and the cadrumo product
rename doctrine (2026-07-12) — this campaign covers the non-secure-storage
remainder those left open: location authority and naming for everything that
legitimately lives outside the encrypted secure-object backend.

## Findings

### Axis 1 — Settings-driven output locations

The central `Settings` model is `src/cadrumo/core/config.py` (with field mixins
in `core/_config_integration_fields.py`, `core/_config_runtime_fields.py`,
`core/_config_timeouts.py`; installed-vs-checkout root logic in
`core/_config_state_root.py`).

**F1.1 — Two coexisting default roots that disagree (the central defect).**
Only 7 destinations are installed-run-aware and reroot under
`cadrumo_local_storage_root` (`CADRUMO_LOCAL_STORAGE_ROOT`; checkout default
`PROJECT_ROOT/var/storage`, installed default `<platform-user-data>/cadrumo/storage`):
tokens (`<root>/tokens`), logs (`<root>/logs`), secrets (`<root>/secrets`),
blobs (`<root>/blobs`), audit (`<root>/audit`), and the SQLite `database_url`
(`<root>/buckets/<bucket>/db/cadrumo.db`). The other **~22 output directories**
default to `PROJECT_ROOT/var/...` and are NOT rerooted — on an installed run
`PROJECT_ROOT` resolves inside site-packages/venv/uv-cache, so durable and
partly sensitive outputs (backups, llm-cache, llm-usage, llm-run-telemetry,
submissions, browser-traces, inbox, inbox/pdfs, workflow-runs, drafts,
status-cache, runs, justificantes, filing-history, registry-parity store,
financial/transactions, financial/invoices, financial/attachments,
financial/purchase-invoice-evidence, financial/usage-ratios.json,
financial/ledgers) scatter into the package tree — the exact hazard
`_config_state_root.py` was written to avoid for the storage root. (Some
`var/financial/*` catalogue dirs may be vestigial now that sensitive financial
bytes persist in the encrypted store; verify live-write status per dir before
migrating.)

**F1.2 — Env-var prefix split on app-owned settings.** Three prefixes coexist:
`CADRUMO_*` (majority, correct), `AEAT_*`, and bare (`financial_*`,
`site_health_*`, `no_color`). Legitimately `AEAT_*` (authority referent):
`aeat_base_url`, sede path templates, status URL templates. App-owned but
still `AEAT_*` (flag for rename adjudication): browser control
(`aeat_browser_*`, `config.py:463-470`), proxy/rate policy (`aeat_proxy_*`,
`aeat_rate_limit_delay_seconds`), auth timeouts/policy (`aeat_auth_*`,
`aeat_clave_*` timeouts/flags), certificate backend fields, corpus root dirs
(`aeat_manuals_root`, `aeat_normatives_root`, `aeat_iva_catalogue_root` —
borderline: AEAT-content referent, app-owned setting). The dotenv hard-cut
filter `_LEGACY_PRODUCT_DOTENV_NAMES` (`config.py:94-102`) already refuses
five former-product `AEAT_*` keys — the rename swept storage/secret settings
but left browser/proxy/auth/timeout fields untouched.

**F1.3 — Hard-coded outputs bypassing Settings.**
- `domain/calculations/registry/_validate_evidence.py:35,51` — durable JSON
  cache `Path(tempfile.gettempdir())/"aeat_corpus_text_cache.json"`:
  hard-coded location, persists beyond process life, former-product filename.
- CWD-anchored `source_path` provenance literals with retired `.aeat-` prefix:
  `application/ledger/_actions_split_merge.py:355` (`.aeat-ledger-split`),
  `:575` (`.aeat-ledger-merge`), `application/ledger/_actions_manual.py:998`
  (`.aeat-manual-ledger`).
- `application/provisioning.py:161-165` — `LOCALAPPDATA`/`Path.home()` for the
  ms-playwright browser cache (third-party cache; likely legitimate, document).
- The previously-flagged hard-coded `.aeat/live-submit-audit.log` no longer
  exists at HEAD (resolved).

**F1.4 — Duplicate default dir.** `cadrumo_submission_browser_trace_dir` and
`cadrumo_status_browser_trace_dir` share the identical
`PROJECT_ROOT/var/browser-traces` default (two settings, one directory).

### Axis 2 — Temp/scratch writers in production code

**F2.1 — Atomic-write siblings are sound but carry four naming/strength
variants.** Thirteen sites stage a `.tmp` sibling in the target's directory
and `os.replace` it. Naming: `{stem}. + .tmp` (envelope `_envelope.py:234,422`,
blob store `_blob_store.py:602`, secret store `_secret_store.py:245`,
`_rotation.py:232`, `core/corpus_manifest/__init__.py:394`, `core/env_io.py:68`),
hidden-file `.{name}..tmp` (`locales/manager.py:575`), collision-hardened
`{name}.{pid}.{token_hex}.tmp` (`bucket/_output_language_hint.py:81`,
`master_key/_master_key_io.py:48` — the strongest, `O_EXCL` + mode 0o600 +
fsync), and weak plain-write variants with no fsync
(`core/_bucket_pointer_io.py:176`, `adapters/outbound/storage/_local.py:213`,
`bucket/_manifest_io.py:114`, `corpus_manifest/__init__.py:570-577`). One
pattern, four dialects — a standardization target (one shared atomic-write
helper).

**F2.2 — OS-tempdir durable artifacts (pollution class).**
- `aeat_corpus_text_cache.json` (`_validate_evidence.py:35,51`): fixed name in
  the shared system temp dir, no user/pid/hash scoping, no env override, no
  TTL; two users/CI containers on one host share and can clobber it; corrupt
  content silently degrades to cache-miss. Worst offender.
- `aeat_registry_{sha256}.pkl` (`_loader.py:1187`, dir from
  `_loader_cache.py:144`): content-hash-keyed (safer) and redirectable via
  `CADRUMO_REGISTRY_DISK_CACHE_DIR`, but the filename keeps the stale `aeat_`
  prefix and there is no eviction — one pickle per registry fingerprint
  accumulates forever.

**F2.3 — Secret materialisation helpers are dormant.**
`blob_store/_materialisation.py` (`materialise_secret`, `export_to_temp_path`;
mkstemp 0o600, FD-only write, default prefix `aeat-secret` at line 46) has
zero production call sites beyond its re-export facades — capability shipped
but unconsumed; prefix stale.

**F2.4 — TemporaryDirectory work areas, all self-cleaning, split-brand
prefixes.** `aeat-workbook-` / `aeat-xls-conversion-`
(`_workbook_parity.py:397,548`), `aeat-review-package-`
(`application/modelo/_review_package.py:270`) vs
`cadrumo-review-package-draft-` (`entrypoints/cli/_modelo_review_package_cli.py:308`)
— two staging areas of the SAME review-package feature on opposite sides of
the brand rename — and `cadrumo-cli-metadata-` (`entrypoints/cli/__init__.py:1001`).
Awareness flag: both review-package staging dirs write real filing-artefact
bytes (fichero-BOE draft, revision JSON, ledger evidence) transiently to the
OS temp dir outside the encrypted store; short-lived and self-cleaning, but a
policy call for the ADR.

### Axis 3 — Test-suite and fixture disk writers

**F3.1 — Collection-time OS-temp roots outside pytest management.** Two
conftests independently derive `Path(gettempdir())/f"cadrumo-pytest-{os.getpid()}"`
and export it as `CADRUMO_LOCAL_STORAGE_ROOT` at module-import/collection time
(`src/cadrumo/conftest.py:35,43` and repo-root `conftest.py:38`). Documented
rationale (collection-time CLI/i18n imports precede tmp_path fixtures), but
the per-PID directories are never cleaned by pytest and the two derivations
could diverge.

**F3.2 — Direct OS-temp use instead of tmp_path.**
`domain/calculations/registry/tests/test_authority.py:359` and
`tests/test_loader_cache_isolation.py:180` inspect `Path(tempfile.gettempdir())`
directly (white-box coupling to the loader's disk-pickle location). Seven more
dev-side tests use raw `tempfile.TemporaryDirectory()` instead of `tmp_path`
(`dev/docs/tests/test_cli_tree.py:65`, `test_glossary_reference.py:139`,
`test_cli_reference_conformance.py:75`, `test_acceptance_wall_catalogue.py:176`,
`test_diagnostics_and_sidecar_rationale.py:78`, `test_worker_count_hook.py:71`,
`application/aggregation/tests/test_ledger_scale_benchmark.py:347`); support
helper `src/cadrumo/tests/env_scope.py:89` uses
`TemporaryDirectory(prefix="cadrumo-settings-")`. Self-cleaning, but bypasses
pytest's tmp-path factory.

**F3.3 — Repo-root `scratch/` is the unmanaged-scratch epicenter.** Gitignored
(`.gitignore:283`, zero tracked files) so it is local-disk pollution, not repo
pollution — the gap is the absence of a mandated scratch location + retention
schema. Contents at HEAD: `registry_cache.pkl` (17.9 MB, written by
`scratch/test_pickle.py` — a naked `test_*.py` outside any `tests/` folder
with stale `aeat.*` imports), a second naked `scratch/test_conformance_check.py`,
7 campaign log captures (`docs-conformance-baseline*.log`, `hintfix-tests.log`),
5 CLI `--help` dumps (`*_help.txt`), 6 one-off scripts (`heal_snapshot.py`,
`measure_diagnostics.py`, `profile_registry_load.py`, `profile_test.py`,
`profile_typo_twins.py`, `run_and_trace.py`), and 5 ad-hoc subdirectories
(`cli-help/`, `modelo-216-registry-wip/`, `test_tmp/`, `tmp_diagnostics/`,
`tmp_diagnostics_measure/`).

**F3.4 — Isolation-fixture drift (no single source of truth for redirecting
output dirs in tests).** Canonical helpers exist
(`src/cadrumo/tests/secure_sql.py:228` `isolated_profile_storage_root`, `:449`
`isolated_cli_runtime_profile`, plus siblings), but ~22 test files each define
a private copy-pasted `_isolated_cli_backend` autouse fixture repeating the
same five `override_settings(cadrumo_token_dir=..., cadrumo_runs_dir=...,
cadrumo_financial_txs_dir=..., cadrumo_invoices_dir=..., cadrumo_drafts_dir=...)`
block (deliberate workaround for the cross-package private-import rule, per an
in-test docstring), and a second ~10-site `_isolated_storage` family overrides
`cadrumo_local_storage_root` directly. Adding a new `*_dir` Settings field
today requires a manual 22-site sweep. Two subprocess-script bodies inject
`CADRUMO_LOCAL_STORAGE_ROOT`/`CADRUMO_SECRET_STORE_DIR` env vars directly
(`entrypoints/cli/tests/test_s423_selected_language_cli.py:23-24,44-45`,
`test_work_calculate_row_flag.py:437,439`).

**F3.5 — Clean surfaces.** The synthetic justificante PDF generator family
(`src/cadrumo/tests/fixtures/justificantes/_generate*.py`) writes only under
its own namespaced fixtures tree with sidecar provenance — no drift.
`dev/registry/newmodelo/` asserts its checker never writes to disk.

### Axis 4 — Dev scripts, packaging, and generated-artifact producers

**F4.1 — Packaging generators are clean.** `materialise_plugin()` /
`materialise_marketplace()` (`src/cadrumo/agent/_workspace.py:369,428`) write
under operator-chosen output dirs with `cadrumo-` naming, and the checked-in
marketplace scaffold is generator-locked by test.
`dev/packaging/smoke_plugin_validate.py:86` (`cadrumo-plugin-smoke-`) and
`dev/docs/serve.py:514` (`cadrumo-docs-serve-`) use correct prefixes and
clean up by default.

**F4.2 — Docs generators route to gitignored or deliberately-tracked
surfaces.** `docs/api/*.rst` (tracked by design per the apidocs-CLI rule),
`docs/_generated/`, `docs/_build/`, `docs/cli/` (all gitignored),
`relevance.json` (committed light data by design). One real gap:
`.gitignore` (~lines 245-260) still ignores pre-rename
`src/aeat/_data/corpus/manuals/**` paths — dead rules, so the real corpus
manual source binaries under `src/cadrumo/_data/corpus/manuals/` are
currently unprotected by any ignore rule.

**F4.3 — Registry scaffolder is clean.** `dev/registry/newmodelo/manager.py`
writes only under the current registry root with clobber refusal;
`dev/registry/matrix` writes nothing.

**F4.4 — Tracked repo-root run artifacts (committed pollution).**
`scratch_pathspec.txt` (empty), `revert.patch`, `rail-snap.md` (browser
snapshot dump), `add_frontmatter.py` (one-off script with a hard-coded
absolute Windows path), `test_docs_output.txt` (captured test log) are
tracked at repo root; `_tmp_commit_iva_group.py` is untracked and not
structurally ignored. The existing `/_*.py` / `/scratch_*.py` ignore rules
are too narrow to catch these shapes.

**F4.5 — `.runtime-s*` per-session scratch convention is fully unmanaged.**
~15 untracked `.runtime-sNN-<label>/` directories at repo root, produced by
agents hand-setting the storage-root env var per session (documented only in
an exec-record narrative, which still cites the retired `AEAT_LOCAL_STORAGE_ROOT`
name). No `.gitignore` pattern, no naming convention, no code owner — the
standout unmanaged-location finding on this axis.

**F4.6 — Correction to one cross-axis claim.** The `AEAT_*` names at
`config.py:94-102` are NOT back-compat aliases: `_LEGACY_PRODUCT_DOTENV_NAMES`
is a hard-cut dotenv exclusion ("neither renamed nor read") — verified at
HEAD. No legacy-compat violation there.

### Axis 5 — Logs, diagnostics, and on-disk caches

**F5.1 — Diagnostic log: correct location authority, no rotation.** The file
handler writes fixed-name `cadrumo.log` under
`<cadrumo_local_storage_root>/logs` (`core/logging.py:104,323,402-421`; dir
derived at `config.py:1042-1069`). Plain `logging.FileHandler`, no
rotation/size cap — unbounded growth.

**F5.2 — Diagnostic dumps.** Wallet DOM-drift dump is opt-in via
`cadrumo_wallet_diagnostic_dump_dir` (`config.py:471`), redacted,
`{label}-summary.txt` naming, but no pruning
(`adapters/outbound/aeat/sede/_iva_compensation_wallet.py:722`). Clave-móvil
login-failure diagnostics and auth diagnostics persist through
`SecureObjectRepository` (encrypted) — clean, the pattern to hold up as the
model.

**F5.3 — Cache lifecycle is three-way inconsistent.** Managed:
LLM run-telemetry (retention-days prune, `_run_telemetry.py:245-280`,
`config.py:727`), status cache (TTL 900s, `config.py:872`), workflow-runs
(rotation store via `_rotation.py:462`). Unmanaged/unbounded: LLM response
cache (`adapters/outbound/llm/_cache.py:55,265` —
`<provider>/<model>/{hash}.json`, no cleanup), LLM usage JSONL
(`_usage.py:99`, `usage-{YYYY-MM-DD}.jsonl`, no retention), run traces
(`core/observability/_store.py:37-38,92`, one subdir per run under
`var/runs`), registry pickle (no eviction), corpus text cache (no TTL),
`cadrumo.log` (no rotation), wallet dumps (no prune).

**F5.4 — OS-tempdir caches recap (location-authority violations).** Registry
pickle: Settings-overridable (`CADRUMO_REGISTRY_DISK_CACHE_DIR`) but
production always falls back to world-readable `gettempdir()`; filename
`aeat_registry_{hash}.pkl` stale-branded. Corpus text cache: NO Settings
field at all — hard-coded `gettempdir()/aeat_corpus_text_cache.json`, module
global memo gives multi-process last-writer-wins clobber. The strongest
single location-authority violation found.

**F5.5 — Dormant Settings fields.** `cadrumo_submission_browser_trace_dir`
(`config.py:822`) and `cadrumo_status_browser_trace_dir` (`config.py:880`)
have no consumer anywhere in `src/cadrumo` outside `config.py` — dead fields
sharing one default dir (`var/browser-traces`); if reactivated they collide.
Candidates for deletion (no-dormant discipline) or re-pointing in the ADR.

**F5.6 — No unmanaged telemetry spools.** The LLM run-telemetry dir is the
only local telemetry sink and it is retention-pruned.

### Axis 6 — Naming-schema classification (against the Cadrumo doctrine)

Canonical identity source: `core/product_identity.py`
(`environment_prefix="CADRUMO_"`, `cli_executable="aeat"`,
`python_package="cadrumo"`).

**F6.1 — Tempfile prefixes.** The stem-derived `{stem}. + .tmp` sibling
convention is uniform across five core sites (neutral, good).
`cadrumo-cli-metadata-` and `cadrumo-review-package-draft-` are
doctrine-clean. Clear violation: `_DEFAULT_TEMPFILE_PREFIX = "aeat-secret"`
(`blob_store/_materialisation.py:46`) — app-owned, should be
`cadrumo-secret`. (Axis 2 adds `aeat-workbook-`, `aeat-xls-conversion-`,
`aeat-review-package-` as further legacy-brand work-area prefixes.)

**F6.2 — Env-var prefixes.** The `CADRUMO_*_DIR/_ROOT/_PATH` location set is
fully migrated and well-behaved; the legacy `AEAT_*` product dotenv keys are
hard-cut refused (`config.py:94-109`). Two unresolved ownership seams:
`AEAT_CERTIFICATE_PATH` (app-read location of an AEAT-issued credential) and
`AEAT_IVA_CATALOGUE_ROOT` (`core/resources/_repos/iva_catalogues.py:21`,
app-owned bundled-data root) — need an explicit ownership ruling; the
wallet-dump rename is the precedent that app-owned location controls migrate
to `CADRUMO_`. (Axis 1 adds the broader app-owned-but-`aeat_*` policy fields:
browser/proxy/auth-timeout settings.)

**F6.3 — Durable filename schemas: separator split.** Secure-storage objects
use double-dash `<hmac_prefix_8>--<label>.bin` + `.meta.json`
(`adapters/outbound/storage/_local.py:45-94`, byte-identical on the Drive
mirror — good parity); session/auth state uses single-dash
`{bucket_id}-storage.json` / `{bucket_id}-clave-movil-storage.json`
(`browser/_factory.py:184`, `core/auth_session_keys.py:66`). Both internally
consistent; `-` vs `--` not unified across families.

**F6.4 — No canonical export-filename composer.** Fichero-BOE/workbook export
paths are operator-supplied; the only observable schema is the test corpus,
which diverges on stem (`modelo-303-1T.boe` vs `m303-{year}-{period}.boe`)
and period casing (`1T`/`1P`/`1p`). A naming vacuum a future default composer
would inherit — the ADR should define the schema.

**F6.5 — Directory-stem language mixing under `var/`.** Kebab English
compounds (`browser-traces`, `workflow-runs`, `status-cache`,
`filing-history`), single-word English generics (`drafts`, `submissions`),
and one Spanish AEAT-domain stem (`justificantes`) coexist; the
Spanish-stem rule is applied unevenly (`justificantes` Spanish while
`drafts`/`submissions`/`filing-history` are equally AEAT-domain and English).

**F6.6 — Former-product namespaces handled correctly.** Storage namespaces
`aeat.`/`aeat-test.` are refused on load
(`_namespace_registry.py:36`), not migrated — the pattern the remaining
renames should follow (hard cut, no compatibility bridge).

## Synthesis — dominant defect classes

Ordered by severity for the standardization ADR:

**D1 — Split-brain default roots (location authority).** One installed-run-
aware state root exists (`cadrumo_local_storage_root` +
`_config_state_root.py`) but only 7 of ~29 output destinations use it; ~22
durable output dirs default to `PROJECT_ROOT/var/...`, which resolves inside
site-packages/venv on an installed run. The ADR's core decision: one root
taxonomy (state / cache / logs / exports / scratch), every Settings dir field
derived from it, `PROJECT_ROOT`-relative defaults eliminated.

**D2 — OS-tempdir durable caches bypassing Settings.** `aeat_corpus_text_cache.json`
(no Settings field, hard-coded gettempdir, shared-host clobber) and
`aeat_registry_{hash}.pkl` (tempdir fallback in production, no eviction).
Both belong under a settings-driven cache root with scoping and eviction.

**D3 — No lifecycle (retention/rotation) policy.** Managed exemplars exist
(run-telemetry retention-days, status-cache TTL, workflow-runs rotation) but
`cadrumo.log`, LLM cache, LLM usage, run traces, wallet dumps, and both temp
caches grow unbounded. The ADR should mandate a per-category lifecycle
declaration (rotation, TTL, retention days, or explicitly unbounded-by-design).

**D4 — Brand-stale artifact naming (`aeat-*`/`aeat_*` on app-owned
artifacts).** Temp prefixes `aeat-secret`, `aeat-workbook-`,
`aeat-xls-conversion-`, `aeat-review-package-`, `aeat-scale-bench-` (test);
cache filenames `aeat_corpus_text_cache.json`, `aeat_registry_{hash}.pkl`;
CWD provenance literals `.aeat-ledger-split`/`-merge`, `.aeat-manual-ledger`.
Plus the app-owned-but-`AEAT_*` env-var tail (browser/proxy/auth policy
fields; `AEAT_CERTIFICATE_PATH` and `AEAT_IVA_CATALOGUE_ROOT` need ownership
adjudication). Hard-cut rename per the namespace-refusal precedent.

**D5 — Unmanaged agent/dev scratch conventions.** Repo-root `scratch/`
(gitignored but no naming/retention schema, 17.9 MB pickle, stale naked
`test_*.py` scripts), the ad-hoc `.runtime-sNN-<label>/` session dirs (no
gitignore pattern, no owner, exec-narrative-only convention), tracked
run artifacts at repo root (`revert.patch`, `rail-snap.md`,
`add_frontmatter.py`, `test_docs_output.txt`, `scratch_pathspec.txt`), and
dead pre-rename `.gitignore` rules leaving corpus manual binaries
unprotected. The ADR should mandate one scratch root + gitignore shape +
naming schema for agent session work.

**D6 — Test-isolation redirection drift.** Two collection-time OS-temp roots
(`cadrumo-pytest-{pid}`, never cleaned, derived independently in two
conftests), ~22 copy-pasted `_isolated_cli_backend` fixtures repeating a
five-field `*_dir` override block, a second `_isolated_storage` family, and
raw-tempdir tests. Standardize on one canonical isolation fixture surface
(public, importable per the top-level-reexports rule) so a new dir field is a
one-site change.

**D7 — Atomic-write dialect divergence.** One sound pattern in four dialects
(stem-sibling, hidden-file, pid+token-hardened, weak no-fsync variants) —
consolidate on one shared atomic-write helper with the master-key variant's
strength tiers.

**D8 — Naming-schema vacuums.** No canonical export-filename composer
(divergent test-corpus conventions `modelo-303-1T` vs `m303-2024-1T` vs
`m202-2024-1p`), separator split (`--` secure objects vs `-` session state),
uneven Spanish-stem application under `var/` (`justificantes` vs `drafts`/
`submissions`/`filing-history`). Dormant fields (`*_browser_trace_dir` pair)
should be deleted or wired, not left as dead vocabulary.

## Sources

- Six-axis read-only discovery swarm over HEAD of `chore/eliminate-shims`
  (2026-07-13), findings verified by coordinator spot-checks
  (`config.py:94-123` read directly; `git check-ignore` on `scratch/*`).
- `src/cadrumo/core/config.py`, `core/_config_integration_fields.py`,
  `core/_config_state_root.py`, `core/logging.py`, `core/product_identity.py`
- `domain/calculations/registry/_validate_evidence.py`, `_loader.py`,
  `_loader_cache.py`, `_workbook_parity.py`
- `adapters/persistence/storage/` (envelope, blob_store, secret_store,
  master_key, bucket, `_rotation.py`), `adapters/outbound/storage/_local.py`,
  `adapters/outbound/llm/` (`_cache.py`, `_usage.py`, `_run_telemetry.py`)
- `application/modelo/_review_package.py`,
  `entrypoints/cli/_modelo_review_package_cli.py`,
  `application/ledger/_actions_split_merge.py`, `_actions_manual.py`
- `src/cadrumo/conftest.py`, repo-root `conftest.py`,
  `src/cadrumo/tests/secure_sql.py`, `src/cadrumo/tests/env_scope.py`
- `dev/packaging/smoke_plugin_validate.py`, `dev/docs/` generators,
  `dev/registry/newmodelo/manager.py`, `.gitignore`
- Prior art: secure-persistence-foundation research (2026-04-27),
  secure-persistence-enforcement ADR (2026-05-06), cadrumo product rename
  ADR + audit (2026-07-12), codebase-sanitization audit (2026-05-05),
  security-paths swarm audit (2026-05-30).
