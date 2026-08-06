---
tags:
  - '#audit'
  - '#release-asset-transport'
date: '2026-07-20'
modified: '2026-07-20'
body_hash: 'sha256:b9d0a8fb49755bfcd6cc3dd65a483cfd5e08e53ee4dfd7831bfdc6c3a8b4ebf1'
related:
  - "[[2026-07-20-release-asset-transport-adr]]"
  - "[[2026-07-15-distribution-installation-readiness-adr]]"
  - "[[2026-07-04-release-readiness-gate-adr]]"
  - "[[2026-04-12-release-please-adr]]"
---

# `release-asset-transport` audit: `release corpus curation`

## Scope

Curation pass (2026-07-20, operator-authorized auto-approve) reconciling the
RELEASE / DISTRIBUTION / PACKAGING / PUBLICATION ADR corpus against the code at
HEAD `53ecce87a4` on branch `chore/release-asset-transport`, after the
release-asset-transport ADR landed. Family members were enumerated mechanically
(filename and full-text sweep of `.vault/adr` and `.vault/reference`) and
grounded by direct file reads; the resident RAG service was re-pointed at this
worktree and its vault reindexed before the sweep. Each member received a
verdict — GOVERNING, SUPERSEDED-BY, or AMEND — and every amendment was executed
in this pass.

## Verdict table

| ADR / reference | Verdict | Action taken |
| --- | --- | --- |
| `2026-07-20-release-asset-transport-adr` | GOVERNING (transport layer) | none — cross-checked against the family; no missed conflict found |
| `2026-07-15-distribution-installation-readiness-adr` | GOVERNING (evidence + publication authority) | AMENDED: added the 2026-07-20 amendments section — transport-layer pointer, and the operator's 12-row restore ruling with the offline-legs-queue/skip doctrine |
| `2026-07-04-release-readiness-gate-adr` | GOVERNING (soak + rollback) — already reconciled to OIDC on 2026-07-17 | AMENDED: transport-layer pointer; cross-reference to the 12-row restore ruling |
| `2026-04-12-release-please-adr` | AMEND — partially superseded | AMENDED: added a current-authority section retiring the "no GitHub Actions workflow ever" absolute and the "no PyPI publishing" non-goal (superseded by the OIDC publication authority); the local versioning/CHANGELOG/tag surface survives as governing |
| `2026-07-19-post-release-distribution-adr` | GOVERNING (lifecycle home, purely derivative) | none |
| `2026-07-19-post-release-distribution-reference` | AMEND — stale transport prescriptions | AMENDED: dated supersession note — the G4/G5/G6 artifact-upload and `gh run download` remedies are superseded by the transport ADR; the gap diagnoses remain valid |
| `2026-07-03-claude-ecosystem-packaging-adr` | GOVERNING (plugin, split, integrity) — already carries its 2026-07-15 amendment section | none |
| `2026-07-16-distribution-harness-identity-adr` | GOVERNING | none |
| `2026-07-18-mcpb-signing-publisher-adr` | GOVERNING — coheres with the transport ADR (the release-manifest SHA-256 integrity channel is preserved; drafts are collaborator-only, published rows are scrubbed at birth per D9) | none |
| `2026-06-28-product-packaging-adr` | AMEND — internal status contradiction | AMENDED: heading said accepted while two body paragraphs still said "remains proposed"; body prose updated to record the ratification (status flip landed 2026-07-17 in `ba2d7d494d`) |
| `2026-07-12-license-posture-adr` | GOVERNING — no transport interaction | none |
| `2026-05-15-corpus-registry-packaging-adr` | GOVERNING — in-wheel data packaging, orthogonal to transport | none |
| `2026-07-17-export-publication-adr` | GOVERNING — despite the name, it is a CLI export-writer rescope grounding record, not release publication; no interaction | none |
| `2026-06-10` / `2026-06-13-llm-evidence-classification-adr` | GOVERNING — no conflict: their never-off-host constraint covers taxpayer financial evidence; `DistributionEvidence` rows are CI/packaging metadata, and operator-machine metadata is handled by the transport ADR's scrub-at-birth ruling | none |
| `2026-04-21-integration-tests-ci-adr` | GOVERNING in its own scope — its `actions/upload-artifact` usage is for CI quality-metric JSON, outside the transport ADR's "cohort or evidence payloads" scope | none; recorded here so a later sweep does not over-apply the transport supersession |

## Findings

### release-please-dead-absolute | high | The release-please ADR still asserted "no GitHub Actions workflow ever" with no supersession note

The 2026-07-15 readiness ADR named the ecosystem-packaging and readiness-gate
local-only rulings in its supersession clause but omitted the release-please
ADR, leaving an accepted ADR asserting an Actions ban contradicted by
`.github/workflows/publish-release.yml` at HEAD. Resolved by amendment: the
publication half is superseded; the local versioning surface and the
human-gated invariant (now carried by `CADRUMO_PUBLISH_ENABLED` plus the
protected `release` environment) survive.

### twelve-row-restore-unrecorded | high | The operator's 12-row restore ruling existed only in a revert commit message

The descope of the required evidence contract (`7c7631fca7`, plus hosted-macOS
flip `d0fb466db5`) and its operator-ruled restore (`22b642533d`) had no ADR
record. The current contract — full 12-row `REQUIRED_DISTRIBUTION_ROWS` in
`dev/release/readiness.py`, self-hosted macOS ARM64 runner, offline legs
queue/skip without workflow rewrite or hosted spend, no conversion to passing
readiness skips — is now recorded in the readiness ADR's amendment section.

### product-packaging-status-contradiction | medium | Accepted heading over "remains proposed" body prose

The status flip to accepted (2026-07-17, bulk vault commit `ba2d7d494d`) never
updated the two body paragraphs asserting the ADR was still proposed and that
later decisions "must not cite this status as accepted". Body prose corrected.

### stale-artifact-remedies-in-reference | medium | The post-release pipeline review prescribed remedies in the retired transport vocabulary

The 2026-07-19 holistic review's open gaps G4/G5/G6 prescribe artifact uploads
and a `gh run download` aggregation recipe. Superseded on mechanism by the
transport ADR; a note now marks the diagnoses as still valid but the remedies
as transport-shaped. Code-level routing: whoever implements the Homebrew row
emission and claude-row aggregation must build on `dev/packaging/evidence_release.py`
draft-release verify/aggregate, not run artifacts.

### releasing-md-lag-risk | low | Operator runbook surfaces must be re-checked once the transport implementation lands

`RELEASING.md` already teaches the OIDC publish flow and the operator's
locally-minted claude evidence draft (a `vX.Y.Z-evidence` style tag, which is
deliberately outside the GC's reserved `evidence-(smoke|scoop|homebrew|claude)-<run_id>`
namespace and therefore safe from collection). Once the in-flight workflow
conversion commits, `RELEASING.md` and `docs/_release_checklist.yaml` must be
swept for any remaining `gh run download` / artifact vocabulary. Code surface —
routed to the pipeline implementation owner, not edited here.

## Recommendations

- Route the G4/G5/G6 implementations (Homebrew row emission, claude-row
  aggregation, scoop row de-stranding) through the transport helper's
  verified-draft mechanism; the reference's artifact-based recipes are dead.
- After the workflow conversion lands, sweep `RELEASING.md`,
  `docs/_release_checklist.yaml`, and any docs claiming artifact transport.
- No further ADR supersessions are pending in this family: the decision set is
  now non-contradictory at this HEAD — readiness ADR owns evidence and
  publication authority, transport ADR owns the storage substrate, readiness-gate
  ADR owns soak/rollback, release-please ADR owns local version hygiene,
  product-packaging ADR owns the cohort shape, ecosystem-packaging ADR owns the
  plugin/split, harness-identity ADR owns naming parity, mcpb ADR owns the
  unsigned posture.
