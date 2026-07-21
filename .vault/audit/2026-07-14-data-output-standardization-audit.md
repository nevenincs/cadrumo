---
tags:
  - '#audit'
  - '#data-output-standardization'
date: '2026-07-14'
modified: '2026-07-14'
related:
  - '[[2026-07-13-data-output-standardization-adr]]'
  - '[[2026-07-13-data-output-standardization-plan]]'
  - '[[2026-07-13-data-output-standardization-research]]'
---

# `data-output-standardization` audit: `campaign close honesty review`

## Scope

Mandated fresh-context honesty review (plan step `W06.P10.S30`) run before the
data-output-standardization campaign is declared structurally complete, per the
campaign-close honesty-review discipline. Conducted with no prior campaign
context: read the ADR, plan, research, all 30 exec records, and the three
in-campaign audits, then INDEPENDENTLY verified rulings R1-R8 against HEAD of
`chore/eliminate-shims` rather than trusting the records. Probes: the state-root
derivation table and its validator, the three structural gates (lifecycle,
isolation-coverage, retention-wiring) for tautology, `gettempdir`/`tempfile`
production writers, `aeat[-_]` artifact literals, the env-var field-rename sweep,
the atomic-write consolidation, tracked-artifact removal, and the disposition of
every deferral the records name. The three campaign gates were executed at HEAD
(15 passed). Verdict: NO close-blockers — every ruling is landed and
gate-enforced, the gates are sound and non-tautological. Findings below are
formal deferrals (pre-recorded, needing an owner) and accepted items (scoped out
at ADR time or cosmetic).

## Findings

### r1-root-derivation-sound | low | R1 landed and comprehensive; PROJECT_ROOT/var defaults are inert placeholders re-rooted by one validator

R1 is satisfied. Every output-dir field still carries a `PROJECT_ROOT/var/...`
default in `config.py` and `_config_integration_fields.py`, but these are inert
placeholders: `Settings._resolve_output_dirs_under_storage_root` iterates
`_STATE_ROOT_DERIVED_DIRS` and re-roots each unset field under
`cadrumo_local_storage_root`. The table is comprehensive — it covers the state
substrate, telemetry logs, caches (`cache/*`), durable outputs, AND the
integration-mixin fields (`financial/transactions|invoices|attachments`,
`financial/usage-ratios.json`, `audit/registry/parity`) — so no output dir
escapes to site-packages on an installed run. The S02 vestigial-field deletions
(`cadrumo_purchase_invoice_evidence_dir`, `cadrumo_ledgers_dir`) are verified
gone. The lifecycle gate's `test_non_exempt_output_dirs_derive_from_the_state_root`
independently enforces that a future field cannot land with a concrete
`PROJECT_ROOT` default. No action.

### r2-gettempdir-production-clean | low | No durable OS-tempdir writer in production; the one residual gettempdir is the by-design pytest branch

R2 is satisfied. The only `gettempdir()` in a non-test production path is
`_loader_cache.py:169`, and it is gated behind `_running_under_pytest()`:
production (`:170`) derives `<storage-root>/cache/registry`. This is the exact
xdist-shared-pickle branch the ADR (R2, "the test-only redirect env var stays")
and research F3.1 sanction. The corpus-text cache now derives from
`cadrumo_corpus_text_cache_dir` (`cache/corpus-text`) and no longer references
`gettempdir`. The remaining `aeat_*` literals in the tree are all in tests
(`aeat_registry_legacy.pkl` is a deliberate foreign-file eviction fixture;
`aeat_corpus_text_cache.json` appears in an assertion that the OLD name does NOT
exist; `aeat_workbook_2024` is test source data). No production artifact-name
literal survives. No action.

### gates-sound-not-tautological | low | The three structural gates enumerate dynamically and are non-tautological — the taxonomy cannot rot silently

The lifecycle gate (`test_settings_lifecycle_gate.py`) enumerates Path-typed
`Settings` fields dynamically from `model_fields` and asserts each maps to
exactly one lifecycle class via hand-maintained frozensets — a new field forces a
conscious classification (intended friction) and fails until classified;
pairwise-disjointness and state-root-derivation are separately asserted. The
isolation-coverage gate (`test_isolation_fixture_state_root_coverage.py`) iterates
`_STATE_ROOT_DERIVED_DIRS` dynamically and asserts each relocates under the test's
`tmp_path`, so a new derived dir is covered automatically. The retention-wiring
gate (`test_retention_wiring_gate.py`) scans each RETENTION family's production
module for the prune call token, subtracting the definition count, so a defined-
but-never-called prune fails. None asserts a value the campaign itself computed;
all three are genuine structural invariants. Ran at HEAD: 15 passed. No action.

### r6-env-rename-sweep-complete | low | The 39 app-owned AEAT_ fields are renamed; residual aeat_ tokens are legitimate keeps (URL templates, function names, HKDF namespace keys)

R6 is satisfied. The residual `aeat_*` production references are all out-of-scope
keeps: `aeat_clave_sede_access_url_template` /
`aeat_clave_permanente_sede_access_url_template` are two of the 7
authority-referent URL-template fields the ownership audit ruled KEEP;
`aeat_auth_session_storage_state_path` and `is_aeat_auth_gate_redirect` are
function names (not `Settings` fields or artifact names); `key="aeat_browser_sessions"`
in `_namespace_registry.py` is an encrypted secure-object namespace key (an AAD
binding, out of scope by the same reasoning the financial-liveness audit applied
to HKDF contexts). `docs/reference/environment-overrides.md` and `env/.env.example`
both cite the new `CADRUMO_*` names (21 / 22 hits). The locale-catalogue
`AEAT_CLAVE_MOVIL_DNI_NIE` citations the ownership audit flagged for S19 should be
spot-confirmed by the owner, but no `AEAT_CLAVE`/`AEAT_BROWSER`/`AEAT_PROXY`/
`AEAT_IVA_CATALOGUE_ROOT` literal remains in the locales tree. No action.

### r7-atomic-write-consolidation-landed | low | Storage dialects delegate to the helper; two registry-cache streaming writers legitimately do not

R7 is substantially satisfied: the storage-dialect sites (`secret_store`,
`bucket/_manifest_io`, `_bucket_pointer_io`, `corpus_manifest`, `envelope`,
`blob_store`, `_rotation`, `env_io`, `locales`, outbound `_local` sidecar via
S31) all delegate to `core.atomic_write` (the residual `os.replace` mentions in
those files are docstrings). Two `NamedTemporaryFile`+`os.replace` sites do NOT
delegate: `_loader.py:1237` (registry pickle) and `_validate_evidence.py:94`
(corpus cache). Both are legitimate: they `pickle.dump` / `json.dump`-STREAM to
the open handle, so delegating to the bytes/text helper would force buffering the
whole payload in memory, and both were authored in W01 before the W05 helper
existed. The plan's verification line "the sole `NamedTemporaryFile`+`os.replace`
implementation site (grep-verified)" is therefore slightly overstated — there are
three implementation sites, two of them deliberate streaming exceptions. No
functional gap; noted for accuracy.

### deferral-runtime-s-dirs | medium | ~17 .runtime-sNN-* dirs still at repo root; formally deferred to a post-2026-07-20 re-sweep but with no named owner

The scratch-runtime-cleanup audit (S22) deferred deletion of the ~17
`.runtime-sNN-*` repo-root directories because every one had a newest-file mtime
inside the seven-day age gate (freshly re-created by running test suites reusing
the historical directory-name convention). They are confirmed still present at
HEAD (`.runtime-s62-locale` … `.runtime-s102-personas`) and remain untracked; the
`.gitignore` `.runtime-*/` pattern (S20) prevents any from landing tracked. This
is a legitimate deferral (today is 2026-07-14, inside the window), but the trigger
("re-run the age-and-pattern sweep after 2026-07-20") is recorded only in the
audit recommendations with NO named owner and NO tracked follow-up step. FORMAL
DEFERRAL: assign an owner (the swarm coordinator, or a dated follow-up task) so
the 2026-07-20 re-sweep is not orphaned.

### deferral-modelo-216-scratch-wip | medium | scratch/modelo-216-registry-wip/ retained pending owner confirmation; still unresolved, no owner assigned

The S22 audit retained `scratch/modelo-216-registry-wip/` (three registry TOML
fragments — manifest, revision, completeness-manifest for a Modelo 216 revision)
because it reads as genuine unlanded registry-authoring work rather than debris,
and explicitly declined to delete it unilaterally. It is confirmed still present
at HEAD. Its disposition ("land under the registry authoring tree, or mark
disposable") is recorded in the audit recommendations with no named owner. FORMAL
DEFERRAL: route to whoever owns Modelo 216 registry authoring for a land-or-delete
decision; do not let it rot in `scratch/`.

### deferral-financial-catalogue-liveness | low | S04's residual dead-mechanism question (do the four financial file-envelope catalogues still accumulate on disk) is deferred with no tracked step

The S04 financial-catalogue-liveness audit kept
`cadrumo_financial_txs_dir`/`invoices_dir`/`attachments_dir`/`usage_ratios_path`
as live (consumed by `default_rotation_plan`) and correctly derived them, but
flagged an open residual: whether those rotation-plan catalogues still accumulate
real on-disk envelopes in the common secure-object-only flow, or whether rotation
now visits directories that are empty in practice. This is a dead-mechanism /
lifecycle question, not a settings-field question, and does not affect any R1-R8
ruling. It is recorded in the S04 exec and audit as "deferred to a later wave"
with no tracked step. FORMAL DEFERRAL (low): record it as a follow-up
lifecycle-audit task so the question is not lost; it is out of this campaign's
location/naming scope.

### accepted-devdocs-temporarydirectory | low | The dev/docs raw TemporaryDirectory tests (research F3.2) were scoped out at ADR time, not silently dropped from the plan

Answering the review brief's explicit question: NO plan step converts the
dev/docs `TemporaryDirectory()` tests to `tmp_path`, and this is NOT a silent
plan drop — ADR ruling R8 deliberately confined the test-isolation work to the
`src/cadrumo` fixture families and "raw `gettempdir()` use in tests is confined to
the white-box registry-cache tests", never committing to sweep dev-side tests. At
HEAD only two dev/docs tests still use `TemporaryDirectory()`
(`test_glossary_reference.py`, `test_cli_reference_conformance.py`), down from the
seven research F3.2 listed (the reduction is peer churn, not this campaign). The
`src/cadrumo/tests/env_scope.py` support helper's `TemporaryDirectory(prefix=
"cadrumo-settings-")` is likewise out of R8 scope. All are self-cleaning. ACCEPTED
— consciously scoped out at the ADR, correctly-branded, no operator-machine or
repo pollution.

### accepted-export-composer-and-schema-vacuums | low | The export-filename composer, separator split, and Spanish-stem unevenness (research D8) were consciously deferred by the ADR, not dropped

Research D8 named three naming-schema vacuums. Each was consciously scoped by ADR
R4, not silently dropped: (1) the export-filename schema was FIXED as
`modelo-<id>-<year>-<period>` and applied to the test corpus (S16), but R4's own
wording defers the runtime composer ("used by tests and any future default
composer") — no production composer exists at HEAD, by design. (2) The separator
split (`--` secure objects vs `-` session state) and (3) the Spanish-stem
unevenness under `var/` (`justificantes` vs English `drafts`/`submissions`/
`filing-history`) were never taken into R4's scope — R4 kept directory stems
as-is per the existing stem rule. ACCEPTED — deferred by explicit ADR decision,
not a plan omission.

### accepted-s29-owner-triage | low | The full-suite S29 run (94 fails, 2 campaign-owned fixed) is honestly triaged per the full-tree-gate owner-distinction rule; not independently re-run here

S29 ran the full `src/cadrumo` suite (94 failed / 12796 passed), fixed the two
campaign-owned failures (marker-metadata in the two new gate docstrings; the
`config.py`/`_loader.py` size-budget re-pins), and attributed the remaining 92 to
peer campaigns (the 55 registry-renta calc-data cluster + its 12-test application
cascade, confirmed red under `-n 0`) or to `-n auto`-only parallel races
(`import_hygiene_gate`, `loader_cache_isolation`). This follows
`full-tree-gate-must-distinguish-owner` and the absorb-in-scope-regressions rule
(the peer failures are calc-data, untouched by a location/naming campaign). This
honesty review did not re-run the 11-minute suite, so the peer attribution is
accepted on the strength of the documented `-n 0` sequential triage, not
independently reproduced. ACCEPTED.

### accepted-commit-attribution-mislabel | low | Commit 96eefdac00 subject mislabels its plan coordinate as W05.P06.S18 (actual W03.P06.S18); cosmetic, immutable history

The env-var field rename in `application/auth` was committed as `96eefdac00`
"refactor(data-output-standardization): rename aeat_* env-var fields to cadrumo_*
in application/auth (W05.P06.S18 partial)". The env-var adjudication is Wave W03
Phase P06 Step S18, not W05.P06 — the wave/phase coordinate in the subject is
wrong. The code change is correct and complete; only the commit-message
plan-coordinate is mislabelled, and history is immutable. ACCEPTED — cosmetic, no
action beyond this note.

## Recommendations

- CLOSE DECISION: no close-blockers. Rulings R1-R8 are all landed and
  gate-enforced (state-root derivation table + validator, lifecycle gate,
  isolation-coverage gate, retention-wiring gate, cache relocation with eviction,
  atomic-write helper, env-var adjudication, scratch/gitignore repair). The three
  structural gates pass at HEAD and are non-tautological. The campaign may be
  declared structurally complete once the two medium formal deferrals below carry
  a named owner.
- FORMAL DEFERRAL (medium): assign an owner and a dated follow-up for the
  post-2026-07-20 `.runtime-sNN-*` re-sweep (finding `deferral-runtime-s-dirs`);
  it currently has a trigger date but no owner.
- FORMAL DEFERRAL (medium): route `scratch/modelo-216-registry-wip/` to the
  Modelo 216 registry-authoring owner for a land-or-delete decision (finding
  `deferral-modelo-216-scratch-wip`).
- FORMAL DEFERRAL (low): record the S04 financial-catalogue-liveness dead-mechanism
  question as a follow-up lifecycle-audit task (finding
  `deferral-financial-catalogue-liveness`).
- ACCEPTED, no action: dev/docs `TemporaryDirectory` tests (ADR-scoped out),
  export-filename composer + separator + stem vacuums (ADR-deferred), the two
  registry-cache streaming `NamedTemporaryFile` writers (legitimate non-delegation;
  correct the plan's "sole site" phrasing if reused), the S29 peer-failure
  attribution, and the `96eefdac00` cosmetic wave-label mislabel.
- Owner spot-check (low): confirm the 16 locale-catalogue
  `AEAT_CLAVE_MOVIL_DNI_NIE` citations the env-var ownership audit flagged for S19
  were routed through the locales CLI to the new `CADRUMO_*` name (no
  `AEAT_CLAVE_*` literal remains in the locales tree, but the positive presence of
  the new name in all four catalogues was not exhaustively re-verified here).
</content>
</invoke>
