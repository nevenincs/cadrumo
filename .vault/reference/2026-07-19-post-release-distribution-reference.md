---
tags:
  - '#reference'
  - '#post-release-distribution'
date: '2026-07-19'
modified: '2026-08-23'
body_hash: 'sha256:75d5b7bce6e8f4a619aa3f4278e5705aab1740b7d90dda00f8c17e92ec6c5348'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

> Persisted from the 2026-07-19 Fable holistic pipeline review. Gaps G2 (marketplace publication), G1(a) (readiness --cohort-dir/--evidence-dir wiring), and G7 (mcpb version surface) were actioned in commit `17abf9c021`. Gaps G3 (RELEASING.md rewrite), G4/G6 (homebrew/scoop row emission), G5 (claude-row aggregation + `just release-collect-evidence`), and G8 (housekeeping) remain open and are tracked below.

> **Transport supersession (2026-07-20).** The Actions-artifact transport this review
> describes, and every fix it prescribes in artifact terms â€” the G4 "uploading into a
> predictable artifact" step, the G5/G6 `just release-collect-evidence RUN_ID` recipe
> built on `gh run download` â€” are superseded by
> `[[2026-07-20-release-asset-transport-adr]]`: cohort and evidence payloads now ride
> per-run draft GitHub Release assets with provenance manifests, and Gate 2 aggregates
> rows from verified release assets, not run artifacts. The gap *diagnoses* (missing
> Homebrew row emission, undocumented claude-row aggregation) remain valid; their
> remedies must follow the transport ADR's mechanism.

# Cadrumo release & orchestration pipeline â€” holistic review

Reviewed 2026-07-19 on branch `chore/eliminate-shims` (== main), repo `nevenincs/cadrumo`,
worktree `Y:\code\aeat-worktrees\chore-476-restructure-execution`. Read-only review; no
production file was modified. RAG discovery was performed first (`vaultspec-rag` live on
port 8766; probes: "release cohort build and promotion", "publish artifacts to pypi scoop
homebrew", "distribution evidence readiness gate release", vault probe "release publishing
decision github actions"), then every claim below was confirmed by direct file reads.

Operator mandate audited against: **"Every GitHub release MUST contain the generated
cross-platform artefacts that we actually release, AND we must populate/push these to ALL
avenues we support."**

---

## (a) Executive summary

The pipeline is architecturally excellent: one immutable, hash-bound **release cohort** is
built once from a clean clone (`dev/packaging/release_cohort.py`), every distribution row
must present tamper-evident, cohort-bound **DistributionEvidence**
(`dev/packaging/evidence.py`), and the sole publication authority
(`.github/workflows/publish-release.yml`) *promotes stored bytes without rebuilding* to
PyPI (OIDC), a GitHub release carrying **every** cohort file, a public Scoop bucket, and a
public Homebrew tap. The design directly satisfies the mandate's "same bytes on every
avenue" clause.

However, the pipeline **cannot currently complete a publication end-to-end**:

1. **CRITICAL â€” the publish workflow's own evidence gate is structurally unsatisfiable.**
   `publish-release.yml:154-156` runs `dev.release.readiness` whose blocking
   `distribution-evidence-complete` check reads hard-coded default paths
   `var/release-cohort` and `var/distribution-install-readiness`
   (`dev/release/readiness.py:385-386`), while the workflow downloads the cohort and
   evidence into `var/promotion/*` (`publish-release.yml:91-93,120-128`). Additionally the
   check requires `manifest.source.tag == v{version}` (`readiness.py:402-408`), but the
   CI-built cohort is produced from a plain push-to-main checkout that fetches no tags
   (`packaging-smoke.yml:272-273`; `actions/checkout@v4` default `fetch-tags: false`), so
   `source.tag` is `None`. And of the 12 required rows, the packaging-smoke run holds only
   the 3 `python-*` rows â€” the other 9 live on other workflows' artifacts or on the
   operator's workstation and are never downloaded. Gate 2 refuses forever.
2. **Mandate gap â€” the Claude marketplace avenue is never populated.** The publish
   workflow pushes Scoop and Homebrew but has **no marketplace publication step**; the
   marketplace zip is only attached to the GitHub release. The post-publication verifier
   (`dev/packaging/acquire_claude_plugin.py:53`) expects a public marketplace source
   (`nevenincs/cadrumo`), which is a private repo today.
3. **Docs gap â€” an operator cannot run a release from the docs.** `RELEASING.md` still
   states "No publication authority currently exists" (`RELEASING.md:151-155`) and
   "Publication is blocked" (`RELEASING.md:376-386`), directly contradicting
   `publish-release.yml`, which its own tests call "the sole upload authority"
   (`dev/release/tests/test_publish_release_workflow.py:1-8`). There is no runbook for the
   dispatch, evidence aggregation, or the vars/secrets it needs.
4. **8 of 12 required evidence rows have no CI emission path.** Homebrew's 4 rows are
   emitted by no workflow (only post-publication `acquire_homebrew.py`); the 4 `claude-*`
   rows require an operator-run real-client capture (`emit_real_client_evidence.py`); the
   Scoop row is emitted inside the Scoop workflow's own artifact but never aggregated.

The GitHub-release half of the mandate is **satisfied by construction** (all cohort files
attached, `publish-release.yml:208-223`); the "all avenues populated" half is satisfied
for PyPI/GitHub/Scoop/Homebrew *in design* but blocked by finding 1, and **unsatisfied**
for the Claude marketplace. This matches the known in-flight plan state (post-release
distribution plan P03.S13 publication wiring pending).

---

## (b) The pipeline end-to-end

### Narrative

**Stage 0 â€” version authoring (local, human).** `just release` (justfile:577-635) runs a
release-please dry-run; `just release-apply` (justfile:639-730) verifies the readiness
gate and prints the 11-step manual checklist: bump `.release-please-manifest.json`,
`pyproject.toml`, both companion `pyproject.toml`s, `src/cadrumo/__init__.py`, companion
pins, CHANGELOG, `uv lock`, commit `chore(release): vX.Y.Z`, tag `vX.Y.Z`, push. Note:
the checklist omits `packaging/mcpb/manifest.json`, which the readiness version-parity
check *does* enforce (`readiness.py:157,178-217`) â€” see gap G7.

**Stage 1 â€” build + prove (CI, push to main).** `packaging-smoke.yml` (push-to-main with
vault/docs paths ignored, or dispatch; queueing concurrency, never cancel â€”
`packaging-smoke.yml:13-34`) runs:

- Three per-OS smoke legs (Linux self-hosted `packaging-smoke-ci`, Windows and macOS
  self-hosted `packaging-smoke`) proving wheel/sdist/extras/split/browser/Docker lanes on
  one transitional Python cohort (`justfile:192-258`), uploading
  `cadrumo-python-cohort[-windows|-macos]` and `cadrumo-packaging-smoke-evidence[-â€¦]`
  (14-day retention).
- `build-release-cohort` (`packaging-smoke.yml:267-298`): builds the **one immutable
  full cross-channel cohort** â€” `uv run python -m dev.packaging.release_cohort build
  --output var/release-cohort` â€” on exactly CPython 3.13.11 / uv 0.11.29
  (`release_cohort.py:46-47,252-278`), from a fresh `git clone` of HEAD into a temp dir
  with `SOURCE_DATE_EPOCH`, `PYTHONHASHSEED=0`, hash-pinned build constraints
  (`release_cohort.py:300-311,387-458`). Uploads `cadrumo-release-cohort`.
- Three `oracle-emit-*` legs (`packaging-smoke.yml:303-409`, `needs: build-release-cohort`)
  download that single cohort, install its three wheels into a fresh venv, run the
  grounded installed CLI + MCP tax oracles (Modelo 200 `DP200014:00562 == 23000.00` per
  the readiness ADR), and mint the sanctioned `python-linux-x86-64` /
  `python-windows-x86-64` / `python-macos-arm64` rows
  (`dev/packaging/oracle_emit_cohort.py`), uploaded as
  `cadrumo-distribution-evidence-{linux,windows,macos}`.

**Stage 2 â€” channel acquisition proof (CI, manual dispatch, keyed to the Stage-1 run).**
Each is `workflow_dispatch(source_run_id, source_commit)` with an identical source-identity
gate (run is packaging-smoke, success, `push` to `main`, same repo, head_sha matches):

- `packaging-scoop.yml` (hosted `windows-2022` Windows container): generates a
  cohort-bound Scoop manifest, installs inside `servercore:ltsc2022`, runs both oracles,
  and **emits the sanctioned `scoop-windows-x86-64` row**
  (`packaging-scoop.yml:202-227`) â€” but only into its own uploaded artifact.
- `packaging-homebrew.yml` (matrix: macos-15-intel hosted, self-hosted macOS-arm64 +
  Linux-x64, hosted ubuntu-24.04-arm): generates the tap snapshot and runs
  `smoke_homebrew.py` â€” **no sanctioned row is emitted** (no
  `distribution_evidence_emit` call anywhere in the workflow or `smoke_homebrew.py`).
- `packaging-claude.yml` (self-hosted Windows): installs pinned Claude Code 2.1.211,
  runs a **live headless Claude session** making the real MCP tool call
  (`packaging-claude.yml:161-178`), plus the MCPB runtime oracle â€” but its outputs
  (`plugin-evidence.json`, `mcpb-assembly-runtime-evidence.json`) are lane evidence,
  **not** `DistributionEvidence` rows. The four `claude-*` rows are real-client claims
  mintable only via the operator hook `dev/packaging/emit_real_client_evidence.py`
  (SDK-driven runs are refused by the honesty guard,
  `dev/packaging/distribution_evidence_emit.py:61-75,270-280`).

**Stage 3 â€” readiness aggregation (local, human).** `just release-readiness`
(justfile:515-520 â†’ `dev/release/readiness.py`) blocks on: canonical project names,
version parity across 6 surfaces + MCPB manifest + companion pins, changelog sanity, and
`check_distribution_evidence_set` â€” a local `var/release-cohort` whose commit == checked
out HEAD and tag == `v{version}`, plus a passing, cohort-bound, schema-valid evidence
record for **all 12 rows** in `REQUIRED_DISTRIBUTION_ROWS` (`readiness.py:159-172`),
with real-client identity on the 4 `claude-*` rows (`readiness.py:457-466`). How the
operator is supposed to assemble those 12 row files into
`var/distribution-install-readiness/` is documented nowhere (gap G3/G4).

**Stage 4 â€” publication (CI, `publish-release.yml`, manual dispatch with
`packaging_run_id`).** Three staged jobs:

- *Gate 1 operator-preflight* (`:36-73`): refuses unless repo var
  `CADRUMO_PUBLISH_ENABLED=true`; enumerates the human-only prerequisites (PyPI Trusted
  Publishing for 3 projects, protected `release` environment with required reviewers,
  public Scoop bucket + Homebrew tap repos with `CADRUMO_SCOOP_BUCKET_TOKEN` /
  `CADRUMO_HOMEBREW_TAP_TOKEN` secrets and `*_REPO` vars).
- *Gate 2 validate* (`:80-156`): re-checks the source run identity, downloads the stored
  python cohort + release cohort + 3 platform evidence artifacts, re-verifies exact
  hashes and every platform's installed evidence via `dev.release.promote_python_cohort`
  (`:130-152`), then requires the complete blocking evidence set (`:154-156`) â€” **the
  structurally broken step (finding 1)**.
- *Gate 3 publish* (`:164-261`, `environment: release` = human approval click):
  re-downloads (never rebuilds; enforced structurally by
  `test_publish_release_workflow.py:29-37`), then
  **PyPI** â€” `uv publish --trusted-publishing always` of all 6 dists (`:196-206`);
  **GitHub release** â€” `gh release create v$VERSION` attaching **every file** found in
  the release-cohort directory (`:208-223`);
  **Scoop** â€” clone bucket repo, copy `scoop/cadrumo.json` to `bucket/`, commit, push
  (`:225-242`); **Homebrew** â€” clone tap repo, copy `homebrew/Formula/cadrumo.rb` to
  `Formula/`, commit, push (`:244-261`). No marketplace step, no MCPB-directory step.
  (`publish.yml` is the retained validate-only diagnostic it supersedes.)

**Stage 5 â€” post-publication reacquisition (tooling built, not yet wired).**
`acquire_pypi.py` (index-only install, digest match, re-run oracles),
`acquire_github_release.py` (`gh release download v<version>`, verify all 12 assets),
`acquire_scoop.ps1` (public bucket in a Windows container), `acquire_homebrew.py`
(public tap), `acquire_claude_plugin.py` (public marketplace), `acquire_mcpb.py`
(GH-release `.mcpb` asset). Each re-emits evidence; docs promotion is gated on these by
the docs-claims gate `dev/docs/tests/test_distribution_claims.py`, which fails any
README/docs page advertising a channel (pip/uvx/scoop/brew/marketplace/mcpb) without a
passing row. README currently makes no positive claims (`README.md:19,46`), so the gate
passes vacuously â€” correct fail-closed behavior.

### Stage diagram

```mermaid
flowchart TD
    A["just release / release-apply<br/>version bump + tag (local, human)<br/>justfile:577-730"] --> B
    B["packaging-smoke.yml (push to main)<br/>3-OS smoke legs + build-release-cohort<br/>+ 3 oracle-emit legs"] -->|"artifacts: cadrumo-release-cohort,<br/>cadrumo-python-cohort,<br/>cadrumo-distribution-evidence-*"| C
    B --> D["packaging-scoop.yml (dispatch)<br/>scoop row emitted in own artifact"]
    B --> E["packaging-homebrew.yml (dispatch)<br/>4-row matrix â€” NO rows emitted"]
    B --> F["packaging-claude.yml (dispatch)<br/>live Claude session + MCPB oracle<br/>lane evidence only"]
    F -.-> G["operator real-client capture<br/>emit_real_client_evidence.py<br/>mints 4 claude-* rows"]
    C["just release-readiness (local)<br/>12/12 rows, cohort tag+commit bound<br/>dev/release/readiness.py"] --> H
    D -.->|"manual aggregation<br/>(undocumented)"| C
    G -.-> C
    E -.->|"missing emission path"| C
    H["publish-release.yml (dispatch)<br/>Gate1 opt-in â†’ Gate2 validate (BROKEN)<br/>â†’ Gate3 publish (release env approval)"] --> I["PyPI Ã—6 dists (OIDC)"]
    H --> J["GitHub release v{X.Y.Z}<br/>ALL 13 cohort files attached"]
    H --> K["Scoop bucket push"]
    H --> L["Homebrew tap push"]
    H -.->|"NO STEP"| M["Claude marketplace"]
    J --> N["acquire_* reacquisition lanes<br/>â†’ docs-claims gate unlocks<br/>test_distribution_claims.py"]
```

---

## (c) Artefact catalogue

The cohort directory contains **exactly** these files plus `release-cohort.json` â€” the
builder refuses undeclared/missing files (`release_cohort.py:377-383`) and the loader
re-verifies size+sha256 of every member on every load (`cohort_manifest.py:267-298`).
`cohort_id` = sha256 of canonical JSON of {schema, version, source{commit,tag},
artifact records(name,kind,path,sha256,size)} (`cohort_manifest.py:183-202`).

| Manifest name | Generator | Path in `var/release-cohort/` | Avenue(s) | Attach/push mechanism |
|---|---|---|---|---|
| `cadrumo-wheel` | `dev/packaging/python_cohort.py` via `release_cohort.py:315` | `python/cadrumo-{v}-py3-none-any.whl` | PyPI + GH release | `uv publish` `publish-release.yml:196-206`; `gh release create` `:208-223` |
| `cadrumo-sdist` | idem | `python/cadrumo-{v}.tar.gz` | PyPI + GH release + Homebrew source | idem; formula references release URL |
| `cadrumo-data-manuals-wheel/-sdist` | idem | `python/cadrumo_data_manuals-{v}*` | PyPI + GH release | idem |
| `cadrumo-data-official-wheel/-sdist` | idem | `python/cadrumo_data_official-{v}*` | PyPI + GH release | idem |
| `python-cohort-manifest` | idem | `python/python-cohort.json` | GH release | attached |
| `claude-plugin` | `cadrumo.agent.materialise_marketplace` â†’ deterministic zip (`release_cohort.py:128-160`, epoch-1980 zip `:94-116`) | `claude/cadrumo-plugin-{v}.zip` | GH release only | attached; **no marketplace push** |
| `claude-marketplace` | idem | `claude/cadrumo-marketplace-{v}.zip` | GH release only | attached; **no marketplace push** |
| `scoop-manifest` | `packaging/scoop/generate.py` (`release_cohort.py:182-198`) | `scoop/cadrumo.json` | Scoop bucket + GH release | pushed to `bucket/cadrumo.json` `:225-242`; URLs point at `https://github.com/nevenincs/cadrumo/releases/download/v{v}` (`release_cohort.py:45,181`) |
| `homebrew-formula` | `packaging/homebrew/generate.py` (`release_cohort.py:199-217`) | `homebrew/Formula/cadrumo.rb` | Homebrew tap + GH release | pushed to `Formula/cadrumo.rb` `:244-261`; same release-URL base |
| `mcpb` | `packaging/mcpb/build.py` (embeds the exact 3 wheels; **unsigned** per accepted ADR `2026-07-18-mcpb-signing-publisher-adr:63-71`) | `mcpb/cadrumo-{v}.mcpb` | GH release only | attached; reacquired by `acquire_mcpb.py` from the release asset |
| manifest | `cohort_manifest.write_manifest` | `release-cohort.json` | GH release | attached |

Evidence records: `var/distribution-install-readiness/{row_id}-{evidence_id}.json`,
write-once (`evidence.py:306-316`), `evidence_id` = sha256 of full content
(`evidence.py:243-246`), each embedding the complete `CohortBinding` (cohort_id, version,
source commit/tag, manifest sha, all artifact digests â€” `evidence.py:39-56`), the runtime,
isolation proof (checkout imports removed, ambient executables removed, installed-exe
sha256s), acquisition, command transcripts with stream digests, and result assertions.
Passing evidence structurally cannot contain a failed command, missing isolation, or a
version mismatch (`evidence.py:202-216`). CI artifact retention is uniformly **14 days**.

Versioning flow: one version across `.release-please-manifest.json`, 3 pyprojects,
`__init__.py`, CHANGELOG, companion pins, and `packaging/mcpb/manifest.json`, enforced by
`check_version_surfaces_agree` (`readiness.py:187-217`). `source_commit` binding flows:
git HEAD â†’ clean clone assertion (`release_cohort.py:292-294,424-427`) â†’ manifest â†’
every evidence record â†’ publish-run identity gate (`publish-release.yml:96-108`) â†’
GH release `--target $SOURCE_COMMIT` (`:221`).

---

## (d) The `just` command map (packaging/release subset)

`set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]` (justfile:2); dual
`[windows]`/`[unix]` recipe bodies where shell syntax diverges.

| Recipe | What it does | Depends on |
|---|---|---|
| `packaging-smoke-dependencies` (:178) | pyproject/extras/frozen-export preflight | â€” |
| `packaging-smoke-preflight-tests` (:182) | pytest `dev/packaging/tests` | â€” |
| `packaging-smoke-source` (:187) | deleted-shipped-data preflight | â€” |
| `packaging-build-python-cohort` (:192) | transitional python cohort â†’ `var/packaging-smoke-cohort/python` | source preflight |
| `packaging-smoke-core/-pip-core/-sdist-core/-extras/-split/-browser[-linux]` (:197-232) | per-lane installs into fresh venvs + installed oracles | build-python-cohort |
| `packaging-smoke-installed-oracles` (:251) | both public transports vs exact cohort bytes | build-python-cohort |
| `packaging-smoke` (:255) | host-portable aggregate (used by Windows/macOS CI legs) | 8 lanes |
| `packaging-smoke-ci` (:258) | full Linux campaign incl. dev + docker lanes (one invocation = one cohort bytes) | 5 aggregates |
| `packaging-smoke-docker[-core/-browser]` (:239-248) | python:3.13-slim container lanes | build-python-cohort |
| `release-readiness[-json]` (:515-520) | audit-state gate (blocking: names, versions, changelog, 12-row evidence; advisory: gh blockers) | â€” |
| `release` (:577-635) | release-please dry-run â†’ `var/release/release-please.log` | node, gh auth |
| `release-apply` (:639-730) | readiness gate + printed 11-step manual checklist (no mutation) | readiness pass, main, clean tree, dry-run log |
| `release-rollback version` (:526-573) | printed rollback checklist (revert, rollback tag, PyPI yank Ã—3) | â€” |
| `docs-site-dry-run` / `docs-deploy` | validate or publish product documentation | AWS session required only for publication |

Notably there is **no `just` recipe** for: building the full release cohort
(`python -m dev.packaging.release_cohort build` is invoked raw in CI), emitting a
distribution row, minting the claude-* client rows, or running any `acquire_*`
reacquisition lane â€” all raw `python -m` invocations, undocumented outside module
docstrings (feeds gap G3).

---

## (e) GitHub workflow map

| Workflow | Trigger | Runner(s) | Purpose / gates | Chain |
|---|---|---|---|---|
| `ci.yml` | push main / PR / dispatch; ignores vault/docs/md paths | self-hosted Linux (single-platform per cost directive 2026-07-19, `ci.yml:44-58`) | lint, type, unit, hooks | â€” |
| `packaging-smoke.yml` | push main (artifact-relevant paths only) / dispatch; queue-not-cancel concurrency | 3 self-hosted legs (Linux X64, Windows X64, macOS ARM64) | full smoke lanes; **build-release-cohort**; 3 oracle-emit rows | its run id is the identity anchor for every downstream workflow |
| `packaging-scoop.yml` | dispatch(source_run_id, source_commit) | **hosted** windows-2022 (Windows container) | source-identity gate; container install; emits `scoop-windows-x86-64` row | consumes smoke run artifacts |
| `packaging-homebrew.yml` | dispatch(source_run_id, source_commit) | matrix: **hosted** macos-15-intel + ubuntu-24.04-arm; self-hosted macOS-arm64, Linux-x64 (honest hosted fallback comment `:52-55`) | tap-snapshot source install per row; no row emission | consumes smoke run artifacts |
| `packaging-claude.yml` | dispatch(source_run_id, source_commit) | self-hosted Windows | live Claude Code 2.1.211 session gate (subscription-auth fleet posture, `:161-167`); MCPB runtime oracle | consumes smoke run artifacts |
| `publish-release.yml` | dispatch(packaging_run_id) | **hosted** ubuntu-latest Ã—3 jobs | opt-in var â†’ no-rebuild validate â†’ `release` environment, OIDC `id-token: write` confined to publish job | consumes smoke run artifacts; **sole upload authority** |
| `publish.yml` | dispatch(packaging_run_id) | hosted ubuntu | retained validate-only diagnostic; "Keep publication blocked" (`publish.yml:82-87`) | superseded once publish-release armed |
| `durable-maintenance-gates.yml` | schedule + dispatch | self-hosted Linux | vault structural gate + ledger/storage roundtrip gate (do-not-remove banner) | â€” |
| `agent-harness-eval.yml` | push (harness paths) / dispatch | self-hosted Linux | harness eval | â€” |
| `aeat-drift-detector.yml` | schedule / dispatch | self-hosted Linux | live AEAT surface drift | â€” |
| `code-health-report.yml` | schedule / dispatch | self-hosted Linux | non-blocking health dashboard | â€” |
| `l1-anchor-drift.yml` | schedule / dispatch | self-hosted Linux | L1 anchor drift | â€” |

Cost posture is consistent and deliberate: everything runs on the self-hosted fleet
(the Windows build host, the WSL Linux build host, the macOS build host) except where hosting is a
correctness requirement (Windows-container Scoop, macOS-Intel + Linux-arm64 Homebrew
rows) or an isolation/trust requirement (all three publish jobs on hosted ubuntu).
Source-identity gates are byte-identical across the three acquisition workflows and
publish-release (success + `.github/workflows/packaging-smoke.yml` + `push` + `main` +
same repo + head_sha match) â€” good; but note `publish.yml:36-48` (the old diagnostic)
checks only success+path, **not** event/branch/repo â€” weaker than its successor.

---

## (f) MANDATE AUDIT

Avenues the project *supports* (claimed by the readiness rows `readiness.py:159-172`, the
docs-claims map `test_distribution_claims.py:56-102`, and `docs/download.md`): PyPI,
GitHub release, Scoop bucket, Homebrew tap, Claude plugin marketplace, Claude Desktop
MCPB.

| Avenue | Artefact attached to GH release? | Pushed to avenue by publish-release? | Automated? | Same cohort guaranteed? | Verdict |
|---|---|---|---|---|---|
| **PyPI** (cadrumo + 2 data dists, wheel+sdist each) | PASS â€” all 6 under `python/` attached via `find -type f` (`publish-release.yml:212-223`) | PASS â€” `uv publish --trusted-publishing always` of the 6 stored files (`:196-206`) | Yes (after operator preflight + env approval) | PASS â€” stored bytes only; hash re-verified in validate (`:130-152`); no-rebuild pinned by tests | **PASS (design)** â€” blocked in practice by G1 |
| **GitHub release** | PASS â€” attaches *every* file of the validated cohort (13 files incl. wheels, sdists, plugin zip, marketplace zip, scoop json, formula, mcpb, both manifests); empty-set hard-fails (`:212-218`); cohort inventory closed-world (`cohort_manifest.py:117-121, 274-279`) | PASS â€” `gh release create v$VERSION --target $SOURCE_COMMIT` (`:219-223`) | Yes | PASS â€” cohort dir is digest-locked before attach | **PASS (design)** |
| **Scoop bucket** | manifest attached | PASS â€” commit+push `bucket/cadrumo.json` (`:225-242`); refuses instructively without token/repo | Yes | PASS â€” manifest generated in-cohort, URLs point at the same release assets (`release_cohort.py:45,181-198`) | **PASS (design)** â€” bucket repo/creds not yet provisioned (operator item) |
| **Homebrew tap** | formula attached | PASS â€” commit+push `Formula/cadrumo.rb` (`:244-261`) | Yes | PASS â€” formula generated in-cohort against the same sdists/release URLs | **PASS (design)** â€” tap repo/creds not yet provisioned; **evidence rows for its 4 platforms have no emission path (G4)** |
| **Claude plugin marketplace** | plugin + marketplace zips attached | **GAP â€” no publish step exists** (no `marketplace` string anywhere in `publish-release.yml`); the public marketplace source `acquire_claude_plugin.py:53` expects (`nevenincs/cadrumo`) is a private repo | No â€” undefined manual step | n/a (nothing published) | **GAP** |
| **MCPB (Claude Desktop)** | `.mcpb` attached â€” this *is* its distribution point (`acquire_mcpb.py` downloads the `v<version>` release asset) | PASS via the GH release attach | Yes | PASS â€” bundle embeds the exact cohort wheels (`packaging/mcpb/build.py:1-12`); unsigned by accepted ADR (`2026-07-18-â€¦-adr:63-71`), docs must not imply verified publisher | **PASS (design)** |
| **Evidence gate feeding all of the above** | â€” | â€” | â€” | â€” | **CRITICAL GAP G1**: `publish-release.yml:154-156` cannot pass (paths, tag, 9 missing rows) |

Cross-avenue consistency: **strong by construction.** One `cohort_id` binds version +
commit + every digest; publication is promotion-only (structural tests forbid any build
verb in the workflow, `test_publish_release_workflow.py:29-37,91`); Scoop and Homebrew
artefacts reference the GitHub-release URLs of the same cohort, so all avenues converge
on identical bytes. Two soft risks: (i) `gh release create` flattens asset paths to
basenames â€” currently collision-free, but a future cohort member sharing a basename would
silently collide; (ii) 14-day artifact retention means a cohort older than 14 days can no
longer be promoted, forcing a fresh matrix run (fine, but undocumented).

---

## (g) Prioritised gap list

**G1 (CRITICAL) â€” publish-release's evidence gate is unsatisfiable as wired.**
Evidence: `publish-release.yml:154-156` vs `readiness.py:385-386` (default dirs),
`readiness.py:395-408` (commit+tag binding), `packaging-smoke.yml` (only 3 rows minted;
tags not fetched at cohort build). Fix:
(a) give `dev.release.readiness` CLI flags `--cohort-dir` / `--evidence-dir` (the Python
API already accepts them, `readiness.py:377-383`) and pass
`var/promotion/release-cohort` + a `var/promotion/rows` directory;
(b) in validate, additionally download `cadrumo-distribution-evidence-{linux,windows,macos}`
plus the Scoop workflow's row (needs the scoop run id as a second input, or move row
emission into an artifact the smoke run owns), and accept operator-uploaded
homebrew/claude rows (see G4/G5);
(c) resolve the tag: either `fetch-tags: true` in `build-release-cohort` **and** trigger
the authoritative matrix from the tag push, or relax the readiness tag equality to
"tag matches when present" in the CI promotion context and keep the strict check for the
local operator gate. Also note the commit check compares against the *checked-out* commit
â€” in publish-release the checkout is at `source_commit`, so that half is fine.

**G2 (HIGH, mandate) â€” no Claude-marketplace publication.** Fix: add a fourth
credential-guarded push step publishing the materialised marketplace tree (the unzipped
`claude-marketplace` cohort member) to a public marketplace repository (var
`CADRUMO_MARKETPLACE_REPO` + token), mirroring the Scoop/Homebrew steps' refuse-when-
unconfigured shape; update `acquire_claude_plugin.py`'s default source to that repo.
Alternatively, formally decide (ADR) that the marketplace avenue is "GitHub-repo-served
at public launch" and encode that in the publish workflow + docs.

**G3 (HIGH, docs) â€” RELEASING.md contradicts the implemented authority.** It predates
the cohort/evidence/publish-release architecture (`RELEASING.md:3-6,93-96,151-155,
376-386`) and documents neither the 12-row evidence aggregation, the acquisition
dispatches, `emit_real_client_evidence`, nor the publish dispatch/vars/secrets/approval.
An operator following the docs today would stop at "Publication is blocked". Fix: rewrite
RELEASING.md around the runbook in (h); keep `docs/_release_checklist.yaml` in sync.

**G4 (HIGH) â€” Homebrew's 4 required rows have no pre-publication emission path.**
`packaging-homebrew.yml` proves installs but mints nothing; `acquire_homebrew.py` is
post-publication by design. Readiness therefore can never reach 12/12. Fix: add a
`distribution_evidence_emit` step per matrix row in `packaging-homebrew.yml` (download
`cadrumo-release-cohort` like the Scoop workflow does at `:193-200`, emit
`homebrew-<os>-<arch>` from the captured tax/mcp oracle JSONs), uploading into a
predictable artifact.

**G5 (MEDIUM) â€” claude-* rows and row aggregation are entirely manual and undocumented.**
The real-client honesty guard is correct policy, but nothing tells the operator to run
`python -m dev.packaging.emit_real_client_evidence â€¦` per row, nor how the four
artifact-scattered row sources get merged into `var/distribution-install-readiness/`.
Fix: a `just release-collect-evidence RUN_ID` recipe that `gh run download`s every row
artifact into the local evidence dir, plus RELEASING.md coverage of the client captures.

**G6 (MEDIUM) â€” packaging-scoop's row is stranded in its own artifact**
(`packaging-scoop.yml:202-236`), keyed to the scoop run id which publish-release never
learns. Folded into the G1(b)/G5 fix.

**G7 (LOW) â€” release-apply checklist omits `packaging/mcpb/manifest.json`** while
`check_version_surfaces_agree` blocks on it (`readiness.py:195,205-206`): the printed
"seven release authorities" (justfile:674-675, RELEASING.md:272-311) would leave
readiness red after a bump. Add it as the eighth surface (or wire it to regenerate).

**G8 (LOW) â€” housekeeping.** `publish.yml`'s weaker identity gate (no event/branch/repo
check, `publish.yml:36-48`) should be retired or hardened now that publish-release
exists; `cadrumo-python-cohort-windows/-macos` artifacts have no consumer; document the
14-day retention constraint vs the 48-72 h soak window; guard `gh release create`
basename collisions with an assertion in the attach step.

---

## (h) Operate a release in 5 steps (as the pipeline stands, with G1-G5 fixed)

1. **Version + tag.** On a clean `main`: `just release` (review the dry-run log), apply
   the release-apply checklist across all version surfaces **including
   `packaging/mcpb/manifest.json`**, `uv lock && uv lock --check`,
   `just release-readiness` (names/version/changelog PASS), commit
   `chore(release): vX.Y.Z`, tag `vX.Y.Z`, push main + the tag.
2. **Build + prove.** Wait for the push-triggered `Cadrumo Packaging Smoke` run on the
   release commit to go fully green (3 smoke legs, `build-release-cohort`, 3
   `oracle-emit-*` legs). Note its run id â€” it is the identity anchor for everything
   after.
3. **Channel proofs.** Dispatch `Cadrumo Scoop Acquisition`, `Cadrumo Homebrew
   Acquisition`, and `Cadrumo Claude Acquisition` with that run id + commit; perform the
   real-client captures in Claude Code / Desktop / Cowork and mint the four `claude-*`
   rows via `python -m dev.packaging.emit_real_client_evidence`. Aggregate all 12 row
   records into `var/distribution-install-readiness/` beside a local
   `var/release-cohort` built at the tag; `just release-readiness-json` must report
   `"ok": true` with `distribution-evidence-complete` PASS. Soak 48-72 h
   (docs/_release_checklist.yaml) â€” the cohort stays frozen.
4. **Arm publication (once per repo, operator-only).** Register PyPI Trusted Publishing
   for `cadrumo`, `cadrumo-data-manuals`, `cadrumo-data-official`
   (workflow `publish-release.yml`, environment `release`); create the protected
   `release` environment with yourself as required reviewer; create the public Scoop
   bucket + Homebrew tap (+ marketplace repo per G2) and set
   `CADRUMO_SCOOP_BUCKET_{REPO,TOKEN}`, `CADRUMO_HOMEBREW_TAP_{REPO,TOKEN}`; set
   `CADRUMO_PUBLISH_ENABLED=true`.
5. **Publish + verify.** Dispatch `Publish Cadrumo release` with the packaging run id;
   after validate goes green, approve the `release` environment. The run then publishes
   PyPI Ã—6, creates the GitHub release with all 13 cohort files, and pushes the Scoop
   bucket and Homebrew tap (and marketplace per G2). Then run the reacquisition lanes â€”
   `acquire_pypi`, `acquire_github_release`, `acquire_scoop.ps1`, `acquire_homebrew`,
   `acquire_claude_plugin`, `acquire_mcpb` â€” and only after they pass, land the docs
   install claims (the `test_distribution_claims.py` gate enforces this ordering).

---

# Appendix â€” distribution description reconciliation (2026-07-19)

Applied in commit `38e7555b27` after operator decisions: canonical EN one-liner approved, status = BETA, GitHub description+homepage fixed. Pinned bilingual client-display copy (plugin/marketplace/MCPB) and EN-only MCP model-facing copy left untouched. Follow-up (open): add a lightweight gate asserting the one canonical short description is identical across pyproject/Scoop so the now-reconciled metadata tier cannot silently re-drift.

# Distribution description reconciliation â€” proposal (discovery only, no edits made)

RAG (`vaultspec-rag --type code` / `--type vault`) is up and was queried first
(`"product description distribution identity"`, `"marketplace plugin description
bilingual"`, `"distribution harness identity approved product description"`); all
findings below were then confirmed by direct file reads and `rg`/`grep`.

## 1. Executive summary

**9 distinct description surfaces carry non-identical text**, split into two
governance classes:

- **5 client-display surfaces** (Claude plugin, marketplace, marketplace-served
  plugin, MCPB `description`, MCPB `long_description`) already carry
  **operator-approved bilingual EN/ES copy**, pinned byte-exact in
  `dev/packaging/verify_distribution_identity.py` `_APPROVED_PRODUCT_DESCRIPTION_PAIRS`
  (ADR `2026-07-16-distribution-harness-identity-adr`, exec record "S06 Revision 2").
  These five all restate the same six required claims (capability, safety, privacy,
  on-host storage, human confirmation, never-files-live) and are **internally
  consistent with each other**, but they do **not** match the README's framing at all
  â€” the README emphasises "turn Spanish tax records into locally verified filing
  artifacts" and never states the six-claim safety list; the approved copy emphasises
  the six-claim safety list and never states the README's "verified filing artifacts"
  framing. These are two different registers for two different audiences (a landing
  page vs. an in-chat trust disclosure) â€” see Â§3 for the recommended reconciliation
  rather than a rewrite.

- **4 one-line/metadata surfaces** are governed by nothing (no gate references them)
  and are freely divergent: the root `pyproject.toml` description, the two companion
  package descriptions, the Scoop manifest description, the Homebrew formula `desc`,
  and â€” worst of all â€” the **GitHub repository description**.

**Worst conflict:** the live GitHub repository description
(`gh repo view nevenincs/cadrumo`) is literally **`"Tax burden"`** â€” a two-word
placeholder with no product name, no capability statement, and no disclaimer. It is
the single most externally visible surface (shown on every GitHub search result,
every clone URL page, every social-preview card) and it says nothing true or useful
about Cadrumo. It is not governed by any gate.

**Second-worst conflict (not a "description" field but a description-adjacent
maturity claim worth flagging alongside):** the README status badge says
`status-alpha` while `docs/index.md`, `docs/download.md`, and `docs/updates.md` all
say "Cadrumo is in beta" three separate times. One of the two is stale.

## 2. Full inventory table

| # | Surface | File:line | Current value (verbatim/truncated) | Language(s) | Governing gate | Client-display vs metadata |
|---|---|---|---|---|---|---|
| 1 | README.md tagline (H1) | `README.md:5` | "Cadrumo: turn Spanish tax records into locally verified filing artifacts" | EN only | none (docs-claims gate covers factual claims, not this exact string) | Canonical narrative source (per this task's directive) |
| 2 | README.md lede paragraph | `README.md:10` | "Cadrumo turns local financial records into calculated, checked, and exportable artifacts for supported Spanish tax forms. It keeps the calculation path deterministic and preserves each result's sources." | EN only | none | Canonical narrative source |
| 3 | README.md status badge | `README.md:8` | `status-alpha` (shields.io badge) | n/a | none | Metadata â€” **conflicts with #4/#5/#6 below** |
| 4 | docs/index.md landing | `docs/index.md:9-15` | "This is the documentation for Cadrumo and its `aeat` command-line interface (CLI). Cadrumo turns your records into checked modelo figures and an export file. You upload that file to the Agencia Estatal de AdministraciÃ³n Tributaria (AEAT) yourself. ... Cadrumo is in **beta** - interfaces may still change between releases." | EN only | Sphinx `-n -W` build gate (link/xref only, not string content) | Correctness reference (per this task's directive) |
| 5 | docs/download.md | `docs/download.md:3-10` | "This page covers how to install the current Cadrumo **beta**... Cadrumo is in **beta**." | EN only | none | Correctness reference |
| 6 | docs/updates.md | `docs/updates.md:8` | "Cadrumo is in **beta**. Treat every release note as potentially relevant" | EN only | none | Correctness reference |
| 7 | pyproject.toml `[project].description` | `pyproject.toml:4` | "Cadrumo: a deterministic Spanish tax calculation engine and agent harness that turns your financial records into modelo data, ready for you to file with the AEAT. Independent software; not affiliated with the AEAT." | EN only | none (PyPI metadata; no gate reads it) | Metadata (PyPI listing summary) |
| 8 | packaging/cadrumo_data_manuals/pyproject.toml `description` | `:14` | "AEAT/BOE prÃ¡ctico manuals (corpus source binaries) for the cadrumo distribution" | EN only, lowercase "cadrumo" | none | Metadata |
| 9 | packaging/cadrumo_data_official/pyproject.toml `description` | `:14` | "Official AEAT diseÃ±os de registro / workbooks and normative PDFs (corpus source binaries) for the cadrumo distribution" | EN only, lowercase "cadrumo" | none | Metadata |
| 10 | Scoop manifest `description` | `packaging/scoop/generate.py:161-164` | "Deterministic Spanish tax calculation CLI and MCP server; independent software, not affiliated with the AEAT." | EN only | none | Metadata |
| 11 | Homebrew formula `desc` | `packaging/homebrew/generate.py:381` | "Deterministic Spanish tax calculation CLI and MCP server" | EN only | none | Metadata (Homebrew style guide caps `desc` at ~80 chars, no trailing period, no "A"/"An" prefix â€” this one already conforms in style) |
| 12 | GitHub repository description | live, via `gh repo view` | **`"Tax burden"`** | EN, informal | none | Metadata â€” **the worst conflict** |
| 13 | GitHub repository `homepageUrl` | live, via `gh repo view` | *(empty)* | n/a | none | Metadata â€” README references `https://cadrumo.neve.md` as "product page" (`docs/index.md:13`) but the repo homepage field is unset |
| 14 | Claude plugin `plugin.json` `description` | `src/cadrumo/agent/_workspace.py:70-89`, enrolled `verify_distribution_identity.py:181-186` | EN: "Operate Cadrumo, the deterministic Spanish-tax CLI, from Claude: grounded search over the bundled BOE/AEAT legal corpus, situation-keyed guided workflows, and human-confirmed execution of every state-changing step. Cadrumo is read-only toward AEAT and never files..." / ES: "Opera Cadrumo, la CLI determinista de impuestos espaÃ±oles, desde Claude: ..." | **EN/ES, operator-approved** | `verify_distribution_identity.py` `_APPROVED_PRODUCT_DESCRIPTION_PAIRS[("claude_plugin_client_display","description")]` | Client-display â€” **PINNED, requires re-approval to touch** |
| 15 | Claude marketplace-served plugin `description` (same value re-emitted inside the marketplace `plugins/cadrumo` subtree) | `_workspace.py:70-89` (same constant reused) | identical to #14 | EN/ES, approved | same pinned set, key `("claude_marketplace_plugin_client_display","description")` | Client-display â€” PINNED |
| 16 | `marketplace.json` `description` | `_workspace.py:142-154` | EN: "Neve plugin marketplace - Claude plugins including the Cadrumo Spanish-tax assistant: read-only toward AEAT, it never files..." / ES: "Marketplace de plugins de Neve - plugins de Claude, incluido el asistente de impuestos espaÃ±oles Cadrumo: ..." | EN/ES, approved | `_APPROVED_PRODUCT_DESCRIPTION_PAIRS[("claude_marketplace_client_display","description")]` | Client-display â€” PINNED |
| 17 | `packaging/mcpb/manifest.json` `description` | `packaging/mcpb/manifest.json:6` | "English: Operate Cadrumo, a deterministic Spanish-tax CLI, as an MCP tool surface: grounded search over the bundled BOE/AEAT legal corpus... \nEspaÃ±ol: Opera Cadrumo, una CLI determinista de impuestos espaÃ±oles, como superficie de herramientas MCP: ..." | EN/ES labelled, approved | `_APPROVED_PRODUCT_DESCRIPTION_PAIRS[("mcpb_client_display","description")]` | Client-display â€” PINNED. **Note: wording differs slightly from #14/#15/#16** ("as an MCP tool surface" vs "from Claude") â€” this is an intentional, already-approved per-surface variant, not drift. |
| 18 | `packaging/mcpb/manifest.json` `long_description` | `manifest.json:7` | "English: The Cadrumo console exposes a deterministic Spanish-tax CLI to any MCP client... \nEspaÃ±ol: La consola de Cadrumo expone una CLI determinista de impuestos espaÃ±oles a cualquier cliente MCP..." | EN/ES labelled, approved | `_APPROVED_PRODUCT_DESCRIPTION_PAIRS[("mcpb_client_display","long_description")]` | Client-display â€” PINNED |
| 19 | MCP tool/prompt/resource/argument descriptions (`cadrumo_harness_load`, `cadrumo_corpus_search`, `search`, `execute`, etc.) | `src/cadrumo/entrypoints/mcp/_server.py` (multiple), `packaging/mcpb/manifest.json:37-44` | Short per-verb operational strings, e.g. "Load the operator rules and active persona...", "Search the bundled BOE/AEAT legal corpus for grounding." | **EN only, deliberately** | `ModelFacingDescriptionCheck` â€” frozen `sha256` `_EXPECTED_MODEL_FACING_DESCRIPTION_SHA256 = "4b53a667c7e0..."` over the four `_MODEL_FACING_DESCRIPTION_SURFACES` (MCP tool/prompt/resource/argument descriptions) | Model-facing (not client-display) â€” **PINNED, English-only by design; out of scope for bilingual reconciliation** |
| 20 | CHANGELOG.md header | `CHANGELOG.md:1-9` | "All notable changes to this project are documented here..." (Keep a Changelog boilerplate, no product summary sentence) | EN | none | Not a product description â€” no conflict, nothing to reconcile |
| 21 | release-please-config.json / manifest | root | no `description` field present | n/a | n/a | Not applicable |

## 3. The canonical source

### README.md verbatim (the directed canonical source)

> "**Cadrumo: turn Spanish tax records into locally verified filing artifacts**"
> (H1, `README.md:5`)
>
> "Cadrumo turns local financial records into calculated, checked, and exportable
> artifacts for supported Spanish tax forms. It keeps the calculation path
> deterministic and preserves each result's sources."
> (lede, `README.md:10`)
>
> "Cadrumo never submits a filing. Review every result, then file through official
> Agencia Estatal de AdministraciÃ³n Tributaria (AEAT) channels."
> (`README.md:16`)

### The user-docs sentence that anchors README's correctness

`docs/index.md:9-12` (the correctness reference this task designates):

> "This is the documentation for Cadrumo and its `aeat` command-line interface
> (CLI). Cadrumo turns your records into checked modelo figures and an export
> file. You upload that file to the Agencia Estatal de AdministraciÃ³n Tributaria
> (AEAT) yourself."

This confirms the README's core claim shape (turns records â†’ checked figures â†’
export file â†’ human uploads) is accurate and matches the operational reality
documented in the how-to guides. The README is safe to treat as canonical for the
one-line/metadata surfaces.

### (a) Proposed canonical EN short description â€” for one-language metadata surfaces

**REQUIRES OPERATOR APPROVAL** (new copy, not previously approved anywhere):

> "Cadrumo is a deterministic Spanish tax calculation CLI and MCP server that turns
> local financial records into checked, exportable modelo filing artifacts.
> Independent software; not affiliated with AEAT."

Rationale: this is the README's H1 + lede, compressed to one sentence, keeping the
two facts every metadata surface already independently states in some form
(deterministic CLI/MCP server; not affiliated with AEAT) and dropping the README's
narrative flourishes ("locally verified") that don't survive compression well.
It supersedes surfaces #7, #10, #11, #12 (see reconciliation map).

### (b) Canonical bilingual EN/ES client-display copy â€” reconciled against the already-approved six-claim pairs

**No new copy is proposed here.** The five pinned client-display surfaces (#14-#18)
are internally consistent, operator-approved, and digest/frozenset-enrolled under
ADR `2026-07-16-distribution-harness-identity-adr`. Per that ADR and per
`aeat-vaultspec-centralisation`/`compatibility-lifecycle-checkpoint`-adjacent
discipline, this task does not have authority to alter pinned, previously-approved
copy, and the task's own brief says to flag divergence rather than overwrite.

**Divergence to flag:** the README's framing ("turn Spanish tax records into
locally verified filing artifacts") and the approved client-display framing (the
six-claim safety/privacy/human-confirmation litany) do not overlap in emphasis.
Concretely:

- README never states the six required claims (capability, safety, privacy,
  on-host storage, human confirmation, never-files-live) as an explicit list â€”
  it states them narratively/individually across several sentences and the
  disclaimer block.
- The approved client-display copy never uses the README's "locally verified
  filing artifacts" phrase.

**This is very likely fine as-is** â€” the two surfaces serve different jobs (a
landing page selling the product vs. an in-chat trust/safety disclosure a model
must honor) â€” but because the operator explicitly asked to reconcile "ALL
distribution descriptions... so they derive from ONE centralized source," this
divergence is surfaced for an explicit operator ruling:

**OPERATOR DECISION NEEDED:** Should the pinned client-display copy be left as
governed by its own ADR (recommended â€” it passed a dedicated approval process with
per-claim keyword coverage proof), or should a future revision re-derive it from
the README once the README's own six claims are made explicit? Recommend: leave
pinned copy alone; this reconciliation only touches the ungoverned metadata tier.

## 4. Reconciliation map

| Surface | Target string | Current state | Edit needed | Approval tier |
|---|---|---|---|---|
| GitHub repo description | `Cadrumo â€” deterministic Spanish tax calculation CLI and MCP server. Turns local financial records into checked, exportable filing artifacts. Independent software; not affiliated with AEAT.` (GitHub descriptions have a ~350-char soft limit; this fits) | `"Tax burden"` | `gh repo edit nevenincs/cadrumo --description "..."` | **Mechanical, but touches a live public-facing GitHub setting â€” recommend explicit go-ahead even though it's not a pinned/gated surface, since it's outward-facing infra, not a file edit** |
| GitHub repo `homepageUrl` | `https://cadrumo.neve.md` (matches `docs/index.md:13`'s "product page" reference) | empty | `gh repo edit nevenincs/cadrumo --homepage "https://cadrumo.neve.md"` | Mechanical, same caution as above |
| `pyproject.toml` `[project].description` | canonical EN short description (Â§3a) | current text is close in spirit but longer/different wording ("agent harness", "ready for you to file with the AEAT") | Replace field value | **Safe mechanical edit** â€” deriving metadata from README is exactly this task's directive; no gate references this string |
| `packaging/cadrumo_data_manuals/pyproject.toml` `description` | keep as-is, but capitalize `Cadrumo` (currently lowercase `cadrumo distribution`) â€” minor consistency nit, not a real conflict since this is a corpus-data companion package, correctly scoped to its own purpose | "for the cadrumo distribution" | Optional casing fix only | Safe mechanical (cosmetic) |
| `packaging/cadrumo_data_official/pyproject.toml` `description` | same cosmetic note as above | same | Optional casing fix only | Safe mechanical (cosmetic) |
| Scoop manifest `description` (`packaging/scoop/generate.py:162-165`) | canonical EN short description (Â§3a), or a trimmed variant respecting Scoop's practice of shorter one-liners: `"Deterministic Spanish tax calculation CLI and MCP server; independent software, not affiliated with AEAT."` (essentially unchanged â€” already matches Homebrew and is already README-consistent in substance) | already close | **No edit strictly required** â€” already aligned; optionally sync verbatim with Homebrew's `desc` for exact parity | Safe mechanical (cosmetic/optional) |
| Homebrew formula `desc` (`packaging/homebrew/generate.py:381`) | `"Deterministic Spanish tax calculation CLI and MCP server"` (already conforms to Homebrew's style: no period, no article prefix, â‰¤80 chars) | matches, minus the "not affiliated with AEAT" clause the Scoop manifest carries | **No edit required** â€” Homebrew's `desc` field is deliberately terse per Homebrew's own style guide; adding the disclaimer clause would break the â‰¤80-char convention. Leave as-is. | No action |
| README status badge | `status-beta` (to match docs) OR update docs to `alpha` (to match README) â€” **operator decision required on which is factually true today** | `status-alpha` vs. three `docs/*.md` "beta" statements | Pick one, propagate | **REQUIRES OPERATOR DECISION** â€” this is a factual maturity claim, not a wording choice; getting it wrong misleads adopters either direction |
| Client-display pairs (#14-#18) | leave pinned copy unchanged | internally consistent, approved | **No edit** | N/A â€” out of scope, protected by ADR |
| Model-facing MCP tool/prompt/resource strings (#19) | leave EN-only, unchanged | approved, digest-pinned | **No edit** | N/A â€” deliberately English-only by design (per ADR, these are not client-display) |

## 5. Language policy (proposed, for operator ratification)

- **Client-display surfaces** (anything a human directly reads while installing or
  browsing a marketplace/plugin listing: Claude plugin `description`, marketplace
  `description`, marketplace-served plugin `description`, MCPB `description` and
  `long_description`) â†’ **bilingual EN/ES**, using the `"English: ...\nEspaÃ±ol:
  ..."` labelled-section convention already established and enforced by
  `verify_distribution_identity.py`'s `_LANGUAGE_LABEL_PATTERN`/`_ENGLISH_LANGUAGE_LABELS`/
  `_SPANISH_LANGUAGE_LABELS`. New client-display surfaces must follow this same
  labelled-pair shape and get enrolled in `_APPROVED_PRODUCT_DESCRIPTION_PAIRS`
  before shipping.
- **Model-facing surfaces** (MCP tool/prompt/resource/argument descriptions â€” text
  an LLM reads to decide how to call a tool, never rendered to the human installer)
  â†’ **English-only**, per the existing `ModelFacingDescriptionCheck` digest pin.
  Do not bilingualize these; the ADR treats this as deliberate, not an oversight.
- **Package-index / one-line metadata surfaces** (PyPI `pyproject.toml`
  descriptions, Scoop manifest `description`, Homebrew formula `desc`, GitHub repo
  description) â†’ **English-only**, one sentence, no gate today. These are the
  surfaces this reconciliation pass safely touches.
- **User-facing Spanish prose in the app itself** (CLI help text, error messages,
  locale catalogues) â†’ stays governed exclusively by the `cadrumo.locales` CLI per
  `aeat-locales-cli`; **out of scope** for this description-reconciliation pass
  entirely â€” never touch `src/cadrumo/locales/*.yml` by hand for this or any work.
- **docs/ prose** (index.md, download.md, updates.md) â†’ English-only per current
  Sphinx doc convention (no bilingual docs build exists); these stay the
  correctness reference this task designates, not a target for bilingual copy.

## 6. Risks / gates / landing order

1. **`verify_distribution_identity.py` / `_APPROVED_PRODUCT_DESCRIPTION_PAIRS`** â€”
   any edit to surfaces #14-#18 (plugin/marketplace/MCPB bilingual copy) trips this
   gate immediately; it fails closed on any byte-level mismatch against the pinned
   frozensets, and per-claim keyword coverage is also checked. **Do not touch these
   surfaces in this reconciliation** â€” confirmed out of scope per Â§3(b).
2. **`ModelFacingDescriptionCheck` sha256 pin** â€” any edit to MCP tool/prompt/
   resource/argument description strings (#19) breaks the frozen digest
   `4b53a667c7e0...`. Not touched by this reconciliation.
3. **No gate protects** the metadata tier this reconciliation *does* propose
   touching (pyproject descriptions, Scoop, Homebrew, GitHub repo description) â€”
   confirmed by `rg` across `dev/`, `.github/workflows/`, and
   `dev/packaging/verify_distribution_identity.py`; none of these strings appear
   in any test assertion. This makes them **safe mechanical edits** with no gate
   dependency, but also means nothing will catch future drift here â€” worth a
   follow-up: consider adding a lightweight "one canonical short description,
   asserted identical across pyproject.toml/Scoop/Homebrew" gate in a later step,
   mirroring the discipline `verify_distribution_identity.py` already applies to
   the client-display tier. (Proposal only â€” not requested by this task.)
4. **Locale parity gate** (`test_parity.py`, `test_locale_translation_honesty.py`)
   â€” irrelevant here; no locale catalogue keys are touched by any recommendation
   in this document.
5. **Docs-claims / Sphinx `-n -W` build gate** â€” the beta-vs-alpha status
   discrepancy (Â§4, README badge row) does not trip any existing gate (badges and
   prose maturity claims aren't cross-checked), but is a factual-honesty risk
   independent of any CI mechanism; flagged for operator decision, not a gate
   dependency.
6. **Recommended landing order** (once approved):
   1. Operator resolves the alpha/beta status question and the README-vs-approved-
      copy framing-divergence question (Â§3b) â€” these are judgment calls, land
      first so downstream copy is written against a settled maturity claim.
   2. Land the canonical EN short description into `pyproject.toml` (root) â€”
      lowest-risk, most-visible metadata surface.
   3. Land the same/derived string into Scoop and Homebrew generators (cosmetic
      parity only; neither currently conflicts materially).
   4. `gh repo edit` for the GitHub description + homepage â€” no code change,
      no PR, do this once the canonical sentence is settled so the repo
      description doesn't need a second edit.
   5. Optional cosmetic casing fix on the two companion-package descriptions.
   6. Do **not** touch #14-#19 in this pass.

## Summary for the coordinator

- **9 distinct description surfaces found**, split 5 pinned/approved (bilingual
  client-display) + 1 pinned/approved (English-only model-facing) + one large
  ungoverned tier (4 metadata surfaces plus the live GitHub repo description).
- **Worst conflict:** the live GitHub repository description is `"Tax burden"` â€”
  a placeholder, ungated, highly visible, and unrelated to the product.
- **README canonical vs. already-approved client-display copy: they do NOT
  restate each other** (different framing, different audience) but are not
  factually contradictory. Recommend leaving the approved client-display pairs
  untouched (protected by their own ADR/digest) and deriving only the ungoverned
  metadata tier from the README, per this task's directive. Flagged for an
  explicit operator ruling: (1) keep the two registers separate as designed, and
  (2) resolve the README-alpha vs. docs-beta status conflict, which is orthogonal
  to the description text itself but was found in the same sweep.

