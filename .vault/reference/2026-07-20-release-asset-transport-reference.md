---
tags:
  - '#reference'
  - '#release-asset-transport'
date: '2026-07-20'
modified: '2026-07-20'
related:
  - "[[2026-07-20-release-asset-transport-adr]]"
---

# `release-asset-transport` reference: `industry grounding and workflow fragments for the release-asset evidence transport`

## Summary

Grounding pass (2026-07-20) behind the accepted release-asset-transport ADR: how mature projects run release-asset-based artifact promotion, the documented draft-release pitfalls that shaped the topology, and the mechanical workflow fragments the implementer converts. Sources were public documentation and issue trackers examined via web research; issue numbers are cited inline for re-verification.

## Industry grounding

### GoReleaser (draft-as-container precedent)

- Every GitHub release GoReleaser creates starts as a draft while assets upload; publication is a separate final act. `draft: true` keeps it unpublished for human review. Since v2.5 it can reuse an existing draft.
- On an HTTP 422 asset-upload collision it deletes the matching asset from the release and retries — precedent for `--clobber` semantics and bounded retry on the upload path.
- Confirms: a draft release is a workable, widely-deployed upload-in-progress container addressed by tag with an authenticated token.

### cargo-dist / axodotdev (the deliberate counter-example)

- cargo-dist's generated `release.yml` implements plan, build, host, publish, announce as coordinated jobs. Inter-job transport is Actions upload-artifact/download-artifact; the project explicitly avoids using a draft GitHub release as scratch storage so the full release is created transactionally at the very end (`dist host --steps=upload --steps=release`).
- Its transport choice presumes available Actions artifact storage, which the zero-spend Free plan removes for this account. Its transactional-final-release principle is adopted in the ADR (drafts are read-only inputs; the one `v<version>` release is minted in a single terminal gate); its transport is not.

### PyPI Trusted Publishing (run identity as the trust anchor)

- `pypa/gh-action-pypi-publish` with Trusted Publishing anchors trust in the OIDC-attested workflow run identity (repository, workflow path, environment). Supports the ADR's D3: run ids stay the promotion inputs because the Actions run record is the identity GitHub attests; evidence tags are derived, never free-form.

### Sigstore / GitHub artifact attestations (deferred)

- `actions/attest-build-provenance` gives cryptographic Sigstore provenance but needs `id-token: write` plus `attestations: write`, and verification UX presumes a public repo or paid features. Operator-ruled deferred; the manifest-plus-Actions-API cross-check covers the threat model meanwhile.

### Documented draft-release pitfalls (load-bearing)

- **Duplicate drafts per tag name.** A draft creates no tag ref, so the tag name is not reserved; `gh release create` against a tag existing only as a draft mints a second draft instead of failing. Documented in cli/cli issue 4270 (race leaves a draft plus a published release for one tag), actions/create-release issue 72, GitHub community discussion 51299, release-drafter issue 1146 (concurrency mints multiple drafts), softprops/action-gh-release issue 602 (pagination past 100 releases causes duplicate draft creation). Consequence: the draft proposal's `gh release create ... || true` in every uploader job is unsafe under concurrency; the ADR mandates a single-creator topology (one root job creates; all others upload-only) plus an exactly-one-draft assertion in the verify path.
- **Draft asset download requires auth and API-mediated URLs.** Draft assets are invisible to unauthenticated clients; `gh release download <tag>` resolves drafts for tokens with push access (the workflow `GITHUB_TOKEN` qualifies). Proven in-repo: `publish-release.yml` already downloads the operator's draft claude-evidence release by tag.
- **Same-run consumption.** Release-asset upload is a synchronous API operation (durably stored when the call returns), so a `needs:`-downstream job in the same run can download immediately; residual API transients are handled with a short bounded retry in the verify helper.
- **Quota facts.** Release assets are stored outside the shared Actions/Packages pool and do not count against the roughly 500 MB Free-plan Actions storage; per-file cap 2 GiB, up to 1000 assets per release. GitHub's terms reserve the right to police excessive release storage — the ADR's K=3 keep-window bounds standing usage to a few GiB.

## Workflow conversion fragments

Baseline: origin/main `22b642533d`. Helper module (new): `dev/packaging/evidence_release.py` with subcommands `emit-manifest` (hash assets, stamp `workflow_path`/`run_id`/`run_attempt`/`head_sha`/`head_branch`/`event`, upload `evidence-manifest.json`), `verify` (download manifest plus assets by derived tag, cross-check the Actions API run record, assert exactly one draft per tag and `target_commitish == head_sha`, re-hash every asset, bounded retry on download; exit 1 naming any mismatch), `leak-sweep` (run the field-agnostic runner-metadata leak detector over a directory of assets about to be published — hostnames, usernames including username-bearing absolute paths in transcripts, machine identifiers, UNC and cohort-embedded forms — exit 1 naming the leaking asset and pattern; no rewriting: rows are scrubbed at mint time inside the evidence builders per the reconciled D9, commit `be4eca4708`), and `gc` (keep-window plus reserved-namespace refusal, tested in Python, not inline shell).

### `packaging-smoke.yml`

- `build-release-cohort` (sole creator): tar the cohort deterministically (`tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner`), `gh release create evidence-smoke-$GITHUB_RUN_ID --draft --target $GITHUB_SHA --title "EVIDENCE (non-release): smoke run ..."`, upload the archive with `--clobber`. Job-level `permissions: contents: write`.
- `oracle-emit-{linux,windows,macos}`: replace artifact download with `gh release download evidence-smoke-$GITHUB_RUN_ID --pattern cadrumo-release-cohort.tar.gz` and extract (Windows uses OS-bundled bsdtar `tar.exe`); within-run integrity is the cohort's own manifest (the loader refuses a corrupt cohort). Replace evidence artifact upload with `gh release upload ... --clobber` of the row JSONs. Upload-only — no create fallback.
- Per-OS smoke jobs: python cohort and smoke-evidence bundles tar to per-OS asset names (`cadrumo-python-cohort-<os>.tar.gz`, `packaging-smoke-evidence-<os>.tar.gz`) and upload to the same draft, upload-only.
- New terminal `seal-evidence-manifest` job (`needs:` every uploader, self-hosted Linux): `emit-manifest` then upload. The manifest must be last so it covers all assets.
- Open implementation checks: verify the three legs' evidence-row basenames are pairwise disjoint (rename on disk before upload if not — `gh release upload` has no localpath-hash-assetname form); pin with a conformance test which per-OS python cohort each acquisition lane consumes (today all lanes consume the Linux-built cohort; wheels are `py3-none-any`, so cross-OS use is intended parity).

### `packaging-scoop.yml` / `packaging-homebrew.yml` / `packaging-claude.yml`

- Source-cohort download becomes `evidence_release verify --tag evidence-smoke-<source_run_id> --expect-run-id ... --expect-workflow .github/workflows/packaging-smoke.yml --pattern cadrumo-python-cohort[-<os>].tar.gz`, then extract — the acquisition lanes gain integrity checking they never had. The existing source-workflow identity step stays (defense in depth).
- Evidence upload: single-job workflows create their own draft (`evidence-scoop-<run_id>`, `evidence-claude-<run_id>`) then upload rows and `emit-manifest`. Homebrew's four matrix legs are upload-only against `evidence-homebrew-<run_id>` created by a dedicated setup job the matrix `needs:` (single-creator; no create-or-ignore), with a terminal seal job manifesting only on full matrix success.

### `publish-release.yml`

- Gate 2: derive tags from the run-id inputs; `evidence_release verify` each of smoke/scoop/homebrew into `rows-raw/` subdirectories; `gh release download` the operator's `claude_evidence_release` tag as today; extract the cohort archive; aggregate `distribution-evidence-*.json` plus `claude-*.json` into the flat rows directory; then the unchanged `promote_python_cohort --check-pypi-only` and `readiness --json --skip-network --cohort-dir ... --evidence-dir ...` invocations. Job permissions: keep `actions: read`; `contents: read` suffices for draft download with the workflow token.
- Gate 3: re-download and re-verify the cohort by the same derived tag (no rebuild), then `evidence_release leak-sweep` over every asset about to be attached (rows, per-lane manifests, transcript/bundle assets) — hard fail on any residual runner metadata, no rewriting — and attach the swept twelve rows plus manifests to the `v<version>` release (self-evidencing; bytes are identical to the Gate-2-verified draft assets because rows are clean at birth, so the draft manifests' digests remain valid; the existing duplicate-basename refusal guards collisions). Gate 3 attaches nothing that has not passed the sweep — conformance-pinned.
- Operator-preflight text: item 4 becomes "Ensure the packaging-smoke run sealed its evidence draft (evidence-smoke-<run id> with cadrumo-release-cohort.tar.gz and evidence-manifest.json)"; items 5 and 6 unchanged.

### New `evidence-gc.yml`

- `workflow_dispatch`-only (operator ruling: no schedule), inputs `keep_per_workflow` (default 3) and `dry_run` (default true), self-hosted Linux, `permissions: contents: write`. Delegates to `evidence_release gc`: candidates are drafts matching `^evidence-(smoke|scoop|homebrew|claude)-[0-9]+$` only; keeps the newest K per lane plus every draft referenced by the most recent successful promotion; refuses any non-matching tag; never touches non-draft releases.

### Conformance-test deltas (`dev/packaging/tests/test_ci_workflow.py` family)

- No packaging workflow uses `actions/upload-artifact` / `actions/download-artifact` for cohort or distribution-evidence payloads.
- Every packaging `gh release create` carries `--draft` and an `evidence-` tag; exactly one creator job per workflow; only publish-release Gate 3 creates a non-draft release.
- publish-release derives evidence tags from run-id inputs (no free-form evidence-tag input except `claude_evidence_release`).
- The GC tag regex excludes `v*`; oracle-leg asset names pairwise disjoint; Gate 3 attaches only sweep-passed evidence.
- Existing per-OS-cohort-not-for-publication test updated to the release-asset spellings.

## Migration order

1. Land `dev/packaging/evidence_release.py` (emit-manifest, verify, leak-sweep, gc) with tests. (Row scrubbing itself already lives in the evidence builders — scrub-at-birth with a fail-closed mint refusal, landed at `be4eca4708`.)
2. Convert `packaging-smoke.yml` (biggest storage win); verify one green end-to-end run: draft exists and is unique, assets plus manifest present, oracle legs consumed the release cohort.
3. Convert scoop/homebrew/claude producers and consumers.
4. Rework publish-release Gates 2 and 3; acceptance gate is a full `dry_run: true` dispatch (validates everything, publishes nothing).
5. Add `evidence-gc.yml`; delete dead artifact uploads; update operator-preflight wording and the release checklist.
6. Purge existing stored artifacts to clear the quota debt (in-flight operator task).
