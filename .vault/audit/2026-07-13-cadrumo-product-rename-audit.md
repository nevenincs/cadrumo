---
tags:
  - '#audit'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:f461c9dba58ab66a41a91a84dd14bba32a5184bceb7eb02a0acf07414699f94d'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-12-cadrumo-cli-executable-adr]]"
---

# `cadrumo-product-rename` audit: `aeat residue and compatibility-absence audit (W06.P14.S76-S77)`

## Scope

This audit executes plan Step `W06.P14.S76` (referent-aware residue inventory) and
records the verification of Step `W06.P14.S77` (compatibility-absence gate). It
inventories retained `aeat` / `Aeat` / `AEAT` tokens across `src/cadrumo`,
`packaging`, `dev`, and `.github`, and classifies each cluster against the accepted
`2026-07-12-cadrumo-cli-executable-adr` casing-and-referent contract: `Cadrumo`
product, `cadrumo` machine identity, `aeat` the sole human CLI executable, `AEAT`
the Spanish tax authority. Roughly 4,463 lowercase `aeat` word occurrences exist in
`src/cadrumo` alone; the overwhelming majority are authority-correct and are
classified by cluster rather than line-by-line. The audit reports only the clusters
and the genuine defects. It modifies no production code.

## Findings

### aeat-residue-class-a-authority | low | Authority-owned `aeat`/`AEAT` uses are correct and must be preserved

The following clusters denote the Spanish tax authority, its portals, protocols,
credentials, legal provenance, official corpus, registry taxonomy, and evidence.
They are correct under the ADR and MUST NOT be renamed: the AEAT portal adapter
tree `src/cadrumo/adapters/outbound/aeat/**`; the registry taxonomy
`src/cadrumo/_data/registry/aeat/**`; the official corpus
`src/cadrumo/_data/corpus/aeat_official/**`; the 49 authority-owned `AEAT_*`
environment variables classified in the `W01.P01.S02` product-and-authority matrix
(portal hosts, credentials, auth-gate, autorizada); the `aeat_live` pytest marker
(`pyproject.toml:787`); authority prose and the `MISSING_AEAT_ACCEPTANCE`
cross-period blocker; and the `aeat` command token wherever it appears inside an
operator invocation (`aeat config ...`, `aeat app ...`, `aeat --help`). No action.

### aeat-residue-class-b-crypto-labels | low | Versioned cryptographic protocol domains remain byte-stable

The `aeat.*.v1`/`v2` HKDF contexts and AEAD associated-data values are
cryptographic protocol constants, not executable aliases, compatibility
branches, namespaces, or product-facing identifiers. Renaming one changes the
derived key or authenticated bytes: the real DEK-wrap reference vector fails
with `InvalidTag`, and already encrypted current-format data becomes
undecryptable. They therefore remain byte-stable across blob storage, encrypted
columns, envelopes, DEK wrapping, recovery, secret storage, profile bundles,
rotation, and review-package recipient encryption. There is one current
read/write path for each format and no fallback for a second label.

The product-owned user-profile schema moved from
`registry/aeat/user_profile` / `aeat.user_profile` to
`registry/cadrumo/user_profile` / `cadrumo.user_profile`; the former registry
path and identifier are not retained as aliases.

### aeat-residue-class-b-aeaterror | medium | `AeatError` base class (645 references) needs its own reconciliation, tracked as follow-up

`class AeatError(Exception)` (`src/cadrumo/core/errors/__init__.py:85`) is the
product's error base and is referenced 645 times across `src/cadrumo`. It names the
product surface, not the authority, so under the product/authority boundary it would
ideally be `CadrumoError`. Its blast radius (645 sites plus error-registry structural
assertions) makes it a distinct reconciliation, not an in-scope edit of this rename.
Tracked as follow-up `F-ERR-01`; not a blocking defect of this campaign.

### aeat-residue-class-c-ci-executable | high | `ci.yml` invokes a nonexistent `cadrumo` executable — defect D-CI-01 (S58 reopened)

`.github/workflows/ci.yml:80` (`run: uv run --no-sync cadrumo app registry verify
--json`) and `:87` (`... cadrumo app registry audit-oracles --json`), plus the `:86`
comment hint, invoke a bare `cadrumo` command. No such console script exists: the
only declared scripts are `aeat` and `cadrumo-mcp` (`pyproject.toml
[project.scripts]`). Both `run:` lines would fail at CI time. The executable token
must be `aeat`. This was checked complete under `W05.P11.S58` on the belief that
`cadrumo` is the command; the belief predates the executable ADR. `S58` has been
reopened. Defect D-CI-01.

### aeat-residue-class-c-packaging-smoke | high | Packaging smoke probes invoke a nonexistent `cadrumo` executable — defects D-PKG-01/02 (S39/S40 open)

`dev/packaging/smoke_docker.py:212,230,275` run `["cadrumo", "--version"]` and
`["cadrumo", "--format", "json", "config", "check"]`; `dev/packaging/smoke_split_install.py:145`
(`_venv_cadrumo`) resolves `cadrumo`/`cadrumo.exe` as the installed console script.
Both target a command that is not installed; the correct human executable is `aeat`.
Two tests lock the defect in: `dev/packaging/tests/test_smoke_docker_selection.py:32`
asserts `'run(["cadrumo", "--version"]'` and
`dev/packaging/tests/test_smoke_split_install_sequence.py:65` asserts the
`_venv_cadrumo` name is `cadrumo`. These belong to plan Steps `W03.P07.S39` and
`W03.P07.S40`, which correctly remain open. Defects D-PKG-01 (docker),
D-PKG-02 (split-install), D-PKG-03/04 (the two asserting tests).

### aeat-residue-class-c-companion-docs | medium | Companion READMEs and mcpb docstring cite `cadrumo app ...` — defects D-DOC-01/02

`packaging/cadrumo_data_manuals/README.md:22` and
`packaging/cadrumo_data_official/README.md:24` instruct the reader to run
`cadrumo app registry`; the human executable is `aeat`, so this must be
`aeat app registry` (D-DOC-01). `packaging/mcpb/build.py:5` docstring cites
`cadrumo app agent --layout plugin`, which must be `aeat app agent` (D-DOC-02).
These sit in already-checked Steps (`W03.P06.S32`, `W04.P10.S53`) whose primary
deliverables are otherwise correct; they are prose/docstring corrections tracked as
follow-ups rather than reopened structural work.

### aeat-residue-class-c-stale-env-docstring | low | Stale `AEAT_ACTIVE_BUCKET` product-env reference in a docstring — defect D-ENV-01

`src/cadrumo/adapters/persistence/storage/bucket/_errors.py:42`
(`NoActiveBucketError` docstring) names `AEAT_ACTIVE_BUCKET` in the active-bucket
precedence chain. Active-bucket selection is product-owned state, which the
`W01.P01.S02` matrix rules moves to the `CADRUMO_*` prefix. No live reader of either
`AEAT_ACTIVE_BUCKET` or `CADRUMO_ACTIVE_BUCKET` exists (no `os.environ`/`getenv`
site), so this is stale prose: it should read `CADRUMO_ACTIVE_BUCKET` or be removed.
Defect D-ENV-01, low severity.

### aeat-residue-class-review-argv | low | Test harnesses set `sys.argv[0] = "cadrumo"` — review cluster R-ARGV, not a runtime defect

Several in-process CLI tests set `sys.argv = ["cadrumo", *args]`
(e.g. `entrypoints/cli/tests/test_cold_start_wizard_registration.py:75`,
`test_config_custody_profile_lifecycle.py:44`, `test_root_fallback_write_guard.py:87,121`,
`test_s423_selected_language_cli.py:27`, `test_stdio.py:189`, and the replay tests'
`_argv_from_arguments("cadrumo workflow show", ...)`). `argv[0]` is the program name;
if any CLI usage/help text derives its prog token from `argv[0]`, it would render
`cadrumo` where the operator contract is `aeat`. This is a consistency review item,
not a runtime failure (the tests run in-process and do not spawn a `cadrumo`
console script). Recommend a follow-up sweep to `aeat` for argv[0] program-name
fidelity; not blocking.

### s89-s90-s93-casing-reconciliation | medium | The all-caps `CADRUMO` counter-direction is overruled; reconciliation is owned by peer Step S93

Plan Steps `W01.P02.S90` (exec asserted "the binding product display contract is
again exactly `CADRUMO`") and the concurrent all-caps assertion alongside
`W05.P12.S89` pushed all-caps `CADRUMO` as the binding prose display. That premise is
OVERRULED by the second operator re-confirmation in
`2026-07-12-cadrumo-cli-executable-adr` (2026-07-13): running prose, the identity
tuple, and locale catalogue strings use `Cadrumo`; all-caps `CADRUMO` is the
wordmark/logotype treatment only. Verified at HEAD: `product_identity.py:48` binds
`display_name="Cadrumo"` (commit `38894cae07`, which reverted the all-caps display
`934a20eaaf`), and the four locale catalogues carry zero all-caps `CADRUMO` used as a
product name in prose — every all-caps occurrence is a `CADRUMO_*` environment
variable. During this bookkeeping pass a peer fleet added and closed
`W01.P02.S93` ("Repair the audited identity-authority regression chain and preserve
concurrent locale remediation"), which is the canonical reconciliation surface for
S89/S90; that peer edit reverted an interim annotation attempt on the plan and the
S89/S90 execution records. No conflict remains: the HEAD state already binds
`Cadrumo`. A resumed fleet MUST NOT re-enforce all-caps `CADRUMO` in prose, the
identity tuple, or the catalogues.

### s62-s67-locale-checkbox-note | low | Locale Steps S62-S67 are casing-complete at HEAD but left unchecked by peer plan churn

`W05.P12.S62`-`S67` (help-identity and the four locale catalogues plus scaffold
parity) are complete and casing-correct at HEAD: the catalogues use `Cadrumo` in
prose with all-caps confined to `CADRUMO_*` env tokens, `scaffold --check`/`audit`
pass per their execution records, and the landing commit is `38894cae07` atop the
locale-phase commits. These boxes were checked during this pass and then reverted to
unchecked by the concurrent peer plan rewrite that also introduced `S93`. They are
left as the peer set them to avoid a plan-edit collision loop; the peer managing the
locale remediation under `S93` should re-close them. The underlying work is not in
question.

### compatibility-absence-gate-s77 | low | S77 compatibility-absence gate verified PASS against the executable ADR

The `W06.P14.S77` gate expectations were re-verified at HEAD and pass, judged against
the superseding `2026-07-12-cadrumo-cli-executable-adr` (whose "old console script"
predecessor language the ADR overrides): (1) no `aeat` import root — `src/aeat` does
not exist; (2) no restored `import aeat` in source — 0 source matches (only stale
`.pyc` bytecode cache carries the old symbol and regenerates on next run, benign);
(3) console scripts are exactly `aeat = cadrumo.entrypoints.cli:main` and
`cadrumo-mcp = cadrumo.entrypoints.mcp:main` — the `aeat` script is the canonical
sole human executable per the ADR, not an old alias; (4) no dual environment reader —
`_CadrumoDotEnvSettingsSource` (`src/cadrumo/core/config.py`) filters out the five
former `_LEGACY_PRODUCT_DOTENV_NAMES` (`AEAT_LIVE_TESTS_ENABLED`,
`AEAT_LOCAL_STORAGE_ROOT`, `AEAT_SECRET_PASSPHRASE`, `AEAT_SECRET_STORE_BACKEND`,
`AEAT_SECRET_STORE_DIR`) so they are neither renamed nor read; (5) no namespace
fallback — companions resolve only under `cadrumo_data`; (6) no state migration —
former product state is refused, never read or moved.

## Recommendations

- Fix the three hard executable defects before closing their Steps: D-CI-01
  (`.github/workflows/ci.yml`, reopened `S58`), D-PKG-01 (`smoke_docker.py`, `S39`),
  and D-PKG-02 (`smoke_split_install.py`, `S40`). Each replaces the bare `cadrumo`
  command token with `aeat`; update the asserting tests D-PKG-03/04 in the same
  change so the fixed behavior is locked, not the defect.
- Correct the prose/docstring executable citations D-DOC-01 (both companion READMEs)
  and D-DOC-02 (`packaging/mcpb/build.py` docstring), and the stale env docstring
  D-ENV-01 (`bucket/_errors.py`), as low-risk follow-ups; they do not require
  reopening their otherwise-complete Steps but should be swept before campaign close.
- Run the R-ARGV consistency sweep to align test `argv[0]` program-name tokens with
  the `aeat` executable, verifying no user-facing usage/help string renders `cadrumo`
  as the command.
- Schedule follow-up F-ERR-01 (the `AeatError` -> `CadrumoError` reconciliation) as
  its own campaign given the 645-site blast radius; it is out of scope for this rename.
- Leave the class-a authority uses and the class-b crypto domain-separation labels
  unchanged; the crypto labels are rekeyed only under explicit operator sign-off.
