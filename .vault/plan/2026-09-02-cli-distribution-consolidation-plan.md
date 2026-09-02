---
tags:
  - '#plan'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
tier: L2
related:
  - '[[2026-09-02-cli-distribution-consolidation-adr]]'
  - '[[2026-09-02-cli-distribution-consolidation-research]]'
modified: '2026-09-02'
body_schema: body-v2
body_hash: 'sha256:9d731b060110d983027cdb12f1b85989190915561a46ec17c93ddea9a1490bac'
---

# `cli-distribution-consolidation` plan

## Description

Converge cadrumo's distribution on the account's proven pure-Python release path, as
decided in `2026-09-02-cli-distribution-consolidation-adr` and grounded in
`2026-09-02-cli-distribution-consolidation-research`.

One ADR governs the whole plan. The eight Phases follow its dependency order rather
than its narrative order: P01 removes the gate defect that prevents any cohort from
building, P02 secures the registry names publication needs, and P03 lands the adopted
release path together with the CI invariant restatements it requires. P04 through P06
reduce the product to one distribution with one application and a daemon-free install
proof. P07 removes the launch-phase vocabulary from the tooling once the surfaces
carrying most of it have gone. P08 closes the naming and retirement work that no
longer has a dependent.

## Steps

### Phase `P01` - Unblock the cohort

Correct the import-budget gate so packaging lanes can build a cohort; nothing downstream is measurable until they do.

- [x] `P01.S01` - Warm the root surface before the import-budget measurement window opens; `dev/packaging/python_cohort.py`.
- [x] `P01.S02` - Re-pin the three selected-path import contracts against a real cohort run; `dev/packaging/python_cohort.py`.

### Phase `P02` - Reserve the distribution names

Hold the primary PyPI name and register the Trusted Publisher bindings against the adopted workflow and environment.

- [x] `P02.S03` - Publish an initial reservation for the primary distribution name; `pyproject.toml`.
- [x] `P02.S04` - Respecify the three Trusted Publisher bindings against the adopted workflow and environment; `RELEASING.md`.

### Phase `P03` - Adopt the account release path

Replace bespoke orchestration with the sibling release-please and publish pair, restating the CI invariants it contradicts.

- [x] `P03.S05` - Add the release-please workflow dispatching publication and documentation delivery; `.github/workflows/release-please.yml`.
- [x] `P03.S06` - Add the publish workflow building, proving and uploading the three distributions; `.github/workflows/publish.yml`.
- [x] `P03.S07` - Add the distribution smoke check asserting both console scripts; `dev/smoke/smoke_check.py`.
- [x] `P03.S08` - Restate the self-hosted runner invariant as a workflow-level split; `dev/ci/tests/test_self_hosted_fleet.py`.
- [x] `P03.S09` - Restate the artifact-storage prohibition as a no-cross-run assertion; `dev/ci/tests/test_change_class_tiers.py`.
- [x] `P03.S10` - Retire the orchestrator, publication and soak workflows with their release-candidate modules; `.github/workflows/release-orchestrator.yml`.

### Phase `P04` - Dissolve the agent harness into the product wheel

Merge the MCP console script into the product distribution and remove the two host-extension channels.

- [x] `P04.S11` - Move the MCP console script into the product distribution and assert it in the distribution smoke check; `pyproject.toml`.
- [x] `P04.S12` - Remove the harness distribution and its workspace membership; `src/cadrumo-harness/pyproject.toml`.
- [x] `P04.S13` - Delete the host-extension channel artifacts and their acquisition lanes; `packaging/mcpb/build.py`.
- [x] `P04.S14` - Rewrite the agent connection guide around the installed console script; `docs/how-to/connect-an-agent.md`.
- [x] `P04.S15` - Unlist the superseded plugin from the marketplace descriptor; `packaging/marketplace/.claude-plugin/marketplace.json`.

### Phase `P05` - Collapse the full-screen surface into the application

Route the root option to the full-screen session, add a headless self-test, and retire the second console script.

- [x] `P05.S16` - Declare the root command's full-screen capability; `src/cadrumo/entrypoints/cli/_root_command_specs.py`.
- [x] `P05.S17` - Route a bare full-screen request to the root session; `src/cadrumo/entrypoints/cli/_root_cli.py`.
- [x] `P05.S18` - Add the headless self-test option and its console-capability bypass; `src/cadrumo/entrypoints/cli/_tui_policy.py`.
- [x] `P05.S19` - Translate the self-test help key across every supported locale; `src/cadrumo/locales/en/cli.yml`.
- [x] `P05.S20` - Retire the second console script, repoint its entry-point test, and assert the headless full-screen start in the distribution smoke check; `src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py`.

### Phase `P06` - Replace the install proof mechanism

Prove installs in an isolated environment holding only the artifact, removing the container-daemon dependency.

- [x] `P06.S21` - Replace nested-container install proof with an isolated environment probe; `dev/packaging/smoke_core.py`.
- [x] `P06.S22` - Remove the container-daemon prerequisite from the prove legs; `dev/packaging/smoke_docker.py`.

### Phase `P07` - Remove launch-phase vocabulary from the tooling

Rewrite the channel descriptor as a flat inventory and strip tier, availability and claim derivation from the release surfaces.

- [x] `P07.S23` - Rewrite the channel descriptor as a flat three-channel inventory; `docs/_data/download_channels.toml`.
- [x] `P07.S24` - Remove the tier rule, availability states and claim derivation; `dev/docs/download_matrix.py`.
- [x] `P07.S25` - Derive the required evidence rows from the whole inventory; `dev/release/readiness.py`.
- [x] `P07.S26` - Rename the sealed release record's channel field to drop the claim vocabulary; `dev/release/release_candidate.py`.
- [x] `P07.S27` - Rewrite the install page around the primary registry; `docs/download.md`.

### Phase `P08` - Harmonize naming and retire dead surfaces

Align runner names and the Python floor with the account, and delete workflows and documents that no longer have a target to serve.

- [x] `P08.S28` - Run the suite under the newer interpreter and raise the declared floor to the account range; `pyproject.toml`.
- [x] `P08.S29` - Rename the runners to the product-prefixed account convention; `.github/workflows/ci.yml`.
- [x] `P08.S30` - Delete the branch-only runner probe workflows; `.github/workflows/ci-runner-probe.yml`.
- [x] `P08.S31` - Delete the control-plane document and restate its sizing rule at the call sites; `.github/ci-control-plane.md`.
- [x] `P08.S32` - Drop the stale runner count from the load-sizing gate, leaving the invariant it actually asserts; `dev/ci/tests/test_machine_aware_load.py`.

### Phase `P09` - Compile to every target as evidence

Build every declared distribution and channel artifact from one command and prove the result runs, so the adopted pipeline is demonstrated capable rather than asserted.

- [ ] `P09.S33` - Bind the two corpus distributions to project-level Trusted Publishers; `RELEASING.md`.
- [x] `P09.S34` - Build every declared distribution from one command and refuse any file over the index cap; `justfile`.
- [x] `P09.S35` - Prove both console scripts from the built wheel in an isolated interpreter; `dev/smoke/smoke_check.py`.
- [x] `P09.S36` - Render the Homebrew formula and the Scoop manifest from the built cohort; `dev/packaging/cohort_manifest.py`.
- [ ] `P09.S37` - Produce the distribution evidence rows the three channels declare; `dev/release/readiness.py`.

### Phase `P10` - Prune the release and packaging surfaces without consumers

Delete the development and release modules the adopted path no longer invokes, each verified to have no consumer outside its own test.

- [x] `P10.S38` - Remove the publication-input dispatcher left without a consumer; `dev/packaging/publication_inputs.py`.
- [ ] `P10.S39` - Remove the container base-image declaration the install proof no longer reads; `dev/packaging/_base_image.py`.
- [ ] `P10.S40` - Remove the evidence leak sweep left without a caller; `dev/packaging/evidence_leak_sweep.py`.
- [x] `P10.S41` - Reduce the release module family to what the adopted path invokes; `dev/release/environment_inventory.py`.

### Phase `P11` - Restate the operator surface against the adopted path

Bring the runbook, the recipe surface and the workflow family back into agreement with the workflows that now exist.

- [x] `P11.S42` - Rewrite the release runbook against the adopted workflow pair; `RELEASING.md`.
- [x] `P11.S43` - Reduce the recipe surface to the commands the adopted path uses; `justfile`.
- [x] `P11.S44` - Reconcile the packaging workflow family against the sibling shape; `.github/workflows/packaging-quick.yml`.

## Parallelization

P01 and P02 are independent of each other and of everything else, and may run in
parallel; P02 needs no code change at all.

P03 depends on P01, because its publish workflow cannot be exercised until a cohort
builds. Within P03, the two workflow Steps and the smoke-check Step may proceed in
parallel, but both gate restatements must land before or with them, or the lanes go
red on arrival. The retirement Step is last in the Phase: nothing is deleted before
its replacement is proven.

P04, P05 and P06 are mutually independent and may run in parallel once P03 has landed.
Each touches a disjoint surface; only P04 and P05 both edit `pyproject.toml`, so they
take one writer between them or sequence those two Steps.

Removing the host-extension channels is ONE atomic change spanning two Phases as
written, and cannot be split. The acquisition-lane map, the channel descriptor and the
artifact-kind taxonomy all validate against each other: deleting the lanes alone leaves
a lane map pointing at absent workflows; removing the map entries alone leaves channels
with no evidence source; removing the channels alone leaves the derived-tier rule
selecting a tier nothing serves; and removing the artifact kinds alone breaks the parity
gate that requires every kind to be surfaced by exactly one channel. The descriptor
Steps in P07 that touch host-extension channels must therefore land in the same change
as the P04 deletion Step, not after it.

Within P04 the deletion Step precedes the merge Step. The harness is referenced from
forty-four files outside its own tree; roughly a third are host-extension surfaces the
deletion removes, so merging first means editing consumers that are about to disappear.
Order inside the Phase is therefore: delete the host-extension artifacts and lanes,
then merge the console script into the product distribution, then rewrite the
connection guide against the merged surface.

P07 depends on P04, which deletes the channels most of the vocabulary describes.
Cleaning the descriptor first would rewrite code that P04 removes.

The install page cannot land its final wording before the primary distribution name
resolves on the index. Its instructions are literal acquisition claims, and the claims
gate requires a passing evidence row for every channel a page advertises by hand - so
the page's PyPI section stays blocked on the name reservation Step in P02, which is
itself blocked on credentials the executing agent does not hold.

P08 depends on nothing but is scheduled last so its retirements cannot orphan a
surface an earlier Phase still needs.

## Verification

- The packaging lanes complete on all three platforms and produce a cohort, and the
  three selected-path import contracts are pinned to values measured on that cohort
  rather than in a development environment.
- The primary distribution name resolves on the index, and the three Trusted Publisher
  bindings exist against the adopted workflow and environment.
- A release cut through the adopted path publishes all three distributions, and a
  clean machine can install the product and run both console scripts.
- The distribution smoke check asserts that the application reports its version,
  renders its root command families, starts its full-screen mode headless, and that
  the MCP console script responds.
- The self-hosted runner and artifact-storage gates pass in their restated form, and
  each demonstrates refusal of the defect it names: a hosted job outside the release
  path, and an artifact read from another run.
- No workflow, module, test or document outside the vault carries `tier`,
  `availability`, `public_launch`, `pending_tiers` or claim-derivation vocabulary, and
  the channel descriptor validates as a flat inventory whose evidence rows are all
  required.
- The product declares one application console script and one MCP console script, and
  no second application entry point resolves.
- Every install channel named in the descriptor has a passing evidence row; a channel
  that cannot be proven is absent from the descriptor rather than declared and
  unproven.
- `vaultspec-core vault check all` is clean for this feature.

The plan is complete when every Step is closed.
