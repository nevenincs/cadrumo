---
tags:
  - '#research'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:6b07f32cb389821d92516b4609001862f11da7e04fa00e11f3035598ed0b308c'
related:
  - "[[2026-07-25-account-distribution-standard-adr]]"
  - "[[2026-07-27-canonical-release-pipeline-adr]]"
  - "[[2026-06-28-product-packaging-adr]]"
---
# `cli-distribution-consolidation` research: `account distribution baseline and measured cadrumo gap`

Cadrumo has never published a release: no git tags, no GitHub releases, and no
`cadrumo` project on PyPI. Two sibling products in the same account, on the same
self-hosted fleet, have published 67 and 64 releases through a materially simpler
pipeline. This record establishes what the siblings do, what cadrumo does instead,
and which of cadrumo's divergences are load-bearing.

## Findings

### The account has a working pure-Python release path that cadrumo does not use

`vaultspec-core` serves 0.1.73 and `vaultspec-rag` serves 0.4.21 on PyPI, with 67 and
64 releases respectively. Both drive publication from `release-please.yml` on push to
main, which dispatches a `publish.yml` of roughly one hundred lines: `uv build`, a
smoke check against the built wheel and sdist, then `uv publish` with Trusted
Publishing.

Cadrumo carries `release-please-config.json` and a bootstrapped
`.release-please-manifest.json` but no release-please workflow. Publication instead
runs through `release-orchestrator.yml`, `publish-release.yml` and
`packaging-smoke.yml`. `publish-release.yml` has never executed; the orchestrator that
dispatches it fails at its campaign stage.

### The siblings publish from hosted runners deliberately

Both sibling publish workflows run on `ubuntu-latest`. The reasoning recorded at the
call site is that the distributions are `py3-none-any`, so the build host cannot
affect the artifact, and the repositories are public, so hosted minutes are free.

Cadrumo's `dev/ci/tests/test_self_hosted_fleet.py` requires every job to be
self-hosted, with two enumerated polling jobs exempt. Its publication path therefore
depends on runner availability. The fleet has one Linux x86-64 runner for this
repository, and the fleet manifest records the macOS host as power-gated to AC.

### Cadrumo's declared fleet role already describes a single-artifact product

The canonical fleet manifest declares cadrumo as `packaging: pure-python` - one
`py3-none-any` cohort built once, then installed and proven everywhere else - with
`role: build-and-prove` on `linux-x86_64` and `role: prove` on the other three
targets. Its vocabulary for a dropped target is `role: excluded` with a technical
`reason`; existing exclusions cite a glibc floor and a missing `cryptography` wheel.

`docs/_data/download_channels.toml` carries a parallel, product-local vocabulary:
`tier`, `availability`, `claimed`, `pending_tiers`, and three `[matrix]` booleans
feeding a cross-product tier rule. Every channel is `availability = "public_launch"`.

### Both siblings ship their MCP server inside the product wheel

`vaultspec-core` declares console scripts `vaultspec-core` and `vaultspec-mcp`;
`vaultspec-rag` declares `vaultspec-rag` and `vaultspec-search-mcp`. Neither ships a
Claude plugin, a marketplace listing, or an MCPB bundle.

Cadrumo's `cadrumo-mcp` lives in a separate distribution, `src/cadrumo-harness`, at
version 0.1.0 against the product's 0.2.2. It is built into the release cohort but
uploaded to no index, and excluded from the Homebrew and Scoop artifacts by design.
Its dependency direction is one-way, asserted by
`src/cadrumo/entrypoints/cli/tests/test_metadata_only_cli_contract.py`. It is the sole
justification for `extends_host_application = true`, which is what selects the Claude
plugin and MCPB channels for this product.

The published marketplace still serves plugin `aeat` at 0.1.1 under the pre-rename
owner name, referencing an `aeat-mcp` server.

### The full-screen surface is already a mode, and its root entry is one line short

`--tui` is declared as a root `OptionSpec` in
`src/cadrumo/entrypoints/cli/_root_command_specs.py`, and
`src/cadrumo/entrypoints/cli/_tui_policy.py` routes it per command via
`TuiCapability`. Five command-graph nodes declare `AVAILABLE`; eleven declare
`NOT_IMPLEMENTED`.

`aeat --tui` currently refuses: the root spec declares no `tui_capability` and the
field defaults to `NOT_IMPLEMENTED`. `root_command` in
`src/cadrumo/entrypoints/cli/_root_cli.py` already calls `enforce_tui_request` and
discards its boolean return.

A second console script, `aeat-tui`, reaches the root Textual session directly. It is
referenced in two places: `pyproject.toml` and
`src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py`. The import edge from
CLI to TUI already exists and is lazy, in `_modelo_work_select_cli.py` and
`_modelo_work_review_cli.py`; no module under `entrypoints/tui` imports
`entrypoints.cli`.

`enforce_tui_request` refuses when the console is not full-screen, which a headless
runner never is.

### The install proof requires a docker daemon the fleet cannot supply everywhere

The siblings prove an install with `uv run --isolated --no-project --with dist/*.whl`,
which needs no daemon.

Cadrumo proves through nested containers over a mounted host socket, with WSL path
translation, in `dev/packaging/smoke_docker.py`. The Linux arm64 runner is a colima
guest whose docker client has no reachable daemon, so the leg backing
`homebrew-linux-arm64` has never passed. The fleet manifest records cadrumo as the
only repository in the account whose hygiene rules prune docker state on the host.

### The packaging blocker is a defect in the import-budget gate, not in the application

Every packaging lane fails identically with `selected help loaded foreign handler
family` naming `cadrumo.entrypoints.cli._root_cli`, raised at
`dev/packaging/python_cohort.py:286`.

The gate opens its measurement window before invoking the selected path's `--help`, so
the root callback's own lazy imports land in the delta and are charged to the selected
command. Rendering `aeat config profile list --help` imports four modules -
`_log_levels`, `_root_cli`, `_root_support`, `_terminal_errors` - all root-callback
machinery; the gate's contract for that path names one of them. Only `_root_cli` fails
loudly, because only `_root_cli` is a registered handler target: commit `c771bffe46`
moved the root handler from `cadrumo.entrypoints.cli` to
`cadrumo.entrypoints.cli._root_cli`, while the gate's allowance stayed hardcoded to
the package.

Measured with the root surface warmed before the window opens, `aeat config profile
list` and `aeat app registry inspect` import nothing, and `aeat app modelo work
calculate` imports `cadrumo.core.irnr` and `cadrumo.core.rescate_type`.

These figures are confirmed under the probe's own conditions, not only in a
development environment: building the three distributions, installing them into an
isolated site, and running the probe with `AEAT_INSTALL_SITE` and
`AEAT_DEPENDENCY_SITE` bound to it returns the same deltas and exits zero for all
three paths. The three built wheels measure 74 to 78 MB, inside the index's
hundred-megabyte per-file cap.

`src/cadrumo/entrypoints/cli/__init__.py` holds the root `app`, `main()`,
`full_command_tree()` and two import-time side effects, against an architecture rule
requiring package initialisers to be inert.

### Launch-phase vocabulary is confined to tooling, not the application

`public_launch`, `pending_tiers`, `ChannelTier`, `claimed_channels`, `derived_tiers`
and the `[matrix]` booleans occur across sixteen files under `dev/`, `docs/`,
`.github/` and `RELEASING.md`. None occur under `src/cadrumo/`. Dated comments in
`src/cadrumo/` are overwhelmingly legal citations - `effective_from`, `Ley N/YYYY`,
BOE and Real Decreto references - which the calculation-grounding rule requires.

`claimed_channels` reaches the sealed release record as a typed field on
`ReleaseCandidate` in `dev/release/release_candidate.py`, filled by
`dev/release/seal_candidate.py`.

### Publication state and name reservations

No git tags exist locally or on origin. No GitHub releases exist, drafts included, so
no release candidate has ever been sealed and `docs/download.md`'s links to the latest
release resolve to nothing. `dev/release/burned_versions.json` records 0.2.0 and 0.2.1
as published-then-deleted and permanently retired.

`cadrumo-data-manuals` and `cadrumo-data-official` each serve exactly one version,
0.0.0, as name reservations. `cadrumo` returns 404 and is unreserved. Issue 612 holds
the three Trusted Publisher bindings and is labelled blocked; it specifies them
against `publish-release.yml` and environment `release`, while the account convention
uses environment `pypi`.

### Merging the harness changes the distribution name, not the package name

Twenty-two files outside the harness tree name the distribution `cadrumo-harness`:
cohort and evidence constants, the installed-oracle probes, the homebrew acquisition
and smoke lanes, the import-hygiene and locale scanners, the agent-evaluation harness
and its workflow, the justfile and the root project file. Those are the merge's real
surface.

A further twelve files import only the package `cadrumo_harness`. Keeping that package
name while merging the distribution leaves them untouched, and preserves the one-way
import boundary the metadata-only CLI contract asserts: the package stays distinct, so
`cadrumo` still never imports it.

Two consumers need more than a name change. `dev/packaging/tests/test_distribution_evidence_emit.py`
asserts an installed console entry point against `distribution="cadrumo-harness"` with
`expected_value="cadrumo_harness.mcp:main"`, and the root project file carries the
workspace membership and source pin that the merge removes.

### Packaging-suite failures are not caused by this decision's work

Every confirmed failure under `dev/packaging/tests` predates this work or is
environmental. Seven of the failing files reference no surface this decision changes;
the justfile recipe-ownership gate names six unowned tests in files it never touches;
and the launcher-semantics refusal resolves `cadrumo-mcp` from the development
environment, which is present and unmodified.

Measurements taken while editing the same tree are not evidence: a cohort-stamping gate
reported as failing in a concurrent run passes on a quiet one.

### The host-extension removal is one indivisible change

The acquisition-lane map, the channel descriptor, the derived-tier rule and the
artifact-kind taxonomy validate against each other, so the host-extension channels
cannot be withdrawn in stages. Deleting the lanes alone leaves the lane map naming
absent workflows; dropping the map entries alone leaves channels with no evidence
source; dropping the channels alone leaves the tier rule selecting a tier nothing
serves; and dropping the artifact kinds alone breaks the gate requiring every kind to
be surfaced by exactly one channel. Each of those four failures was observed by
applying the corresponding half on its own.

The tier rule is withdrawn by setting `extends_host_application` false, which is the
same fact the decision records: the MCP server ships as a second console script inside
the product wheel, so no host application carries a channel.

### The working tree currently declares channels whose lanes are deleted

The acquisition workflows and the publication workflow are deleted and committed, while
the descriptor still declares the host-extension channels and the lane map still names
the deleted acquisition workflow. Five modules reference workflow files that are absent:
the publication-input map, the evidence-transport gate, the environment-inventory and
external-client-boundary tests, and the documentation-site module in prose.

This is not a property of the decision; it is a half-applied state. Reconciling it means
applying the indivisible change above in full.

### The work is already fragmented across the vault

Twenty-six distribution-related features carry documents, including
account-distribution-standard, canonical-release-pipeline,
release-pipeline-full-automation, post-release-distribution,
distribution-installation-readiness, claude-ecosystem-packaging,
distribution-harness-identity, product-packaging, standalone-executable-tier,
publication-lane-consolidation, scoop-runner-topology and
shared-distribution-repository. None produced a published release.

### The dependency closure already supports the interpreter cadrumo excludes

The siblings admit `>=3.13,<3.15`; cadrumo declares `>=3.13,<3.14`. Resolving
cadrumo's twenty-seven third-party direct dependencies in an isolated probe project
under `>=3.13,<3.15` succeeds, and every compiled dependency publishes a
3.14-compatible wheel for all three shipped platforms - verified for `cryptography`,
`argon2-cffi-bindings`, `pikepdf`, `pypdfium2`, `pillow`, `lxml`, `rtoml` and
`pydantic-core`, with `cryptography` and `pikepdf` covered by `abi3` and `rtoml` by
explicit `cp314` builds.

This establishes that nothing in the dependency closure blocks the floor moving. It
does not establish that cadrumo's own code runs under 3.14: no suite has been executed
on that interpreter. Raising the floor therefore requires a test run, not only a
metadata edit.

### Two cohort members are consumed only by surfaces the decision removes

`cadrumo-runtime-wheelhouse` has four consumers: `packaging/mcpb/build.py`,
`dev/packaging/smoke_mcpb.py`, `dev/packaging/smoke_plugin_install.py` and
`src/cadrumo-harness/src/cadrumo_harness/_workspace.py`. All four are host-extension
or harness surfaces. Neither installer generator reads it; `packaging/homebrew/generate.py`
and `packaging/scoop/generate.py` resolve dependencies from the index.

`cadrumo-source-archive` is consumed by the cohort's own digest assertions. Homebrew's
use of the phrase "source archive" is a different thing: `dev/packaging/acquire_homebrew.py`
maps the formula's stable archive and its two resources onto the cohort's *sdists*, not
onto the `python-source-archive` artifact kind.

Both members therefore lose every consumer when the host-extension channels and the
harness distribution go.

### The frozen-count problem is real but lies outside this decision

Most constants matching a floor or ceiling naming pattern are legitimate: legal values
such as the Article 20 reduction ceiling, the maternity deduction's retired filing
year and the record retention floor; policy values such as the credential length
floor; and technical values such as the terminal size floor and the platform glibc
floors.

The genuine dated ratchets are `_UNVERIFIED_ANCHOR_CEILING`,
`_ANCHOR_ABSENT_FROM_DECLARED_IDS_CEILING`, `_UNCHECKED_BODY_FLOOR` and
`_HEADING_ONLY_CEILING` in the registry legal-anchor gates, and `_MODULE_VACUITY_FLOOR`
and `_DATA_VACUITY_FLOOR` in the governance corpus isolation gate, together with the
checkout-drift, size-budget, import-hygiene and conformance baseline files. All sit on
registry and governance surfaces and none is part of the distribution path.

`dev/ci/tests/test_machine_aware_load.py` carries no frozen constant at all: its only
stale figure is a runner count in prose, which the metanarration ruling already covers.

The ratchets therefore belong to the registry and quality-gate features that already
carry plans, not to this one.

### No continuous-integration run has exercised this decision's work

Every verification behind the completed Steps was taken locally, on one operating
system, in a development environment. A wheel builds carrying both packages, installing
it yields two working console scripts, they run under both interpreters in the declared
range, and the gates that were changed pass when run directly.

None of that is a release qualification. The adopted release-path workflows exist only
in the working tree and have never executed. No packaging campaign has run, so the
evidence directory the readiness gate and the claims gate both read is empty - which is
why the install page cannot yet state its acquisition command. The macOS and Linux
targets are unverified entirely; the suite has not been run in full; and the server's
most recent runs predate this work and were failing.

The distribution therefore builds and installs, and is not shown to be publishable. The
sequence that would establish it is a green quick campaign across the three targets,
then a full campaign minting the rows, before any name is claimed on the index.

### The index credential is absent by design, not by oversight

No PyPI credential exists in the environment, the user configuration, the operating
system keyring, or the repository's secrets - which hold only a marketplace token and a
tap token. That is consistent rather than missing: publication was designed for Trusted
Publishing over OIDC, so a long-lived token was never meant to exist.

The consequence is that reserving the primary name is not a credential-handling problem
to solve. It unblocks by registering the three publisher bindings against the adopted
workflow and environment, after which publication happens through the workflow rather
than beside it. Uploading by hand with a personal token would work once and leave the
path it bypassed still unexercised.

A reservation should also carry the placeholder version the two corpus distributions
already use rather than the product version, so that holding the name costs no release
number - two are already permanently retired.

Nothing else stands between the name and the index. `uv build --no-sources` produces
both distributions from the merged tree - a 74.5 MB wheel and a 59.6 MB source
distribution - and each sits comfortably under the index's 100 MB per-file cap, the one
limit that could have forced a repackaging before a first upload. The remaining action
is the upload itself, and it is external to this tree.

The binding a publisher registration must claim is fully determined by the adopted
workflow: owner `nevenincs`, repository `cadrumo`, workflow `publish.yml`, environment
`pypi` - the same environment name the sibling publish workflow claims. One registration
per distribution, so three. Because none of the three names exists on the index yet,
each is registered as a pending publisher, which is also what reserves the name.

The deployment environment `pypi` did not exist on the repository and has been created;
without it the publish job claims an environment the OIDC token cannot attest. The
repository also carries an orphaned `release` environment: no workflow references it, it
holds no secret or variable, and its only protection rule is a branch policy. It is
residue of the deleted release machinery and can be removed.

### Two gaps survive the consolidation

The index already carries `cadrumo-data-manuals` and `cadrumo-data-official`, both at
`0.0.0` and both uploaded on 2026-07-19. Only the primary name was ever unregistered.
That asymmetry decides the binding form rather than leaving it to preference: a pending
publisher applies only to a name with no project behind it, so the two corpus
distributions take the ordinary project-level form, registered per project.

The first publish run measured it, and only one of the three was bound. The primary
name's pending publisher worked - `cadrumo` uploaded - and the next file was refused:
`OIDC scoped token is not valid for project 'cadrumo-data-manuals'`. Neither companion
carries a binding.

This record twice got that wrong in opposite directions. It first asserted the two
companion bindings were outstanding, inferring it from the distributions merely existing.
It then retracted that on the operator's word and wrote that operator confirmation was
sufficient evidence. Neither was defensible: the first was an inference dressed as a
finding, and the second treated an unverifiable claim as settled rather than as
unverifiable. A publisher registration is visible only from inside the account, so the
honest state was "cannot be confirmed here" until an upload tested it. The upload has now
tested it.

Because an upload is per-file and not atomic, the run left the index in a mixed state:
`cadrumo` at `0.4.0`, both companions still at `0.0.0`. That is worse than a clean
failure. The published root distribution pins both companions at `0.4.0` exactly, so
`pip install cadrumo` cannot resolve until they land - the product is on the index and not
installable from it.

The release runbook still drives the retired orchestrator. `release-orchestrator.yml`
no longer exists in the workflow directory, yet `RELEASING.md` names it eight times as
the command that starts a release, and its publisher section still states that no
publisher is registered. The document therefore describes a path that cannot be
followed, and it is the only tracked file the plan left pointing at the deleted
machinery.

### The MCP console script is served by a package initialiser

`cadrumo-mcp` resolves to `cadrumo_harness.mcp:main`, and that `main` is defined in the
package's `__init__.py` alongside an `__all__` re-exporting roughly a dozen symbols out
of sibling private modules. Every implementation module under that package carries a
leading underscore, so the initialiser is not a convenience over a public surface - it
is the only public surface, which makes the facade load-bearing rather than removable in
isolation. Relocating the entry point therefore means promoting the modules a consumer
legitimately needs at the same time.

The console script itself works: it resolves from the built wheel, reaches its argument
parser, and the server runtime it defers importing is present in the artifact. This is a
placement defect, not a packaging one.

### The container base-image gate outlived one of its two surfaces

Retiring the nested-container install proof deleted `dev/packaging/smoke_docker`, and
two of the four assertions in the base-image singularity gate were written about that
module. They did not start reporting a problem; they started erroring on a missing path,
which is a different failure and a louder one. The gate has been red since the proof
mechanism was replaced.

The resolver those assertions used is not residue. The repository-root `Dockerfile`
still declares the base image, the devcontainer still builds from it, and the resolver
is what reads the declaration back so nothing can restate it. Deleting the module would
delete the only enforcement over a surface that is still live, so the step proposing its
removal rests on a premise the tree disproves.

The surviving invariant was widened while repairing it. It previously named three files,
one of which no longer existed, so it asserted nothing about that surface at all - the
characteristic failure of an enumerated list. It now walks the tree, and distinguishes a
binding from a mention structurally: in Python a bare tag counts only where it is
assigned or passed as a keyword argument, never in a docstring or an assertion message.
Documentation is out of scope by construction, because a table describing the declared
tag is not a second declaration.

### Neither managed channel ships the second console script

Rendered against a real cohort, the Scoop manifest exposes one shim, `aeat`, and the
Homebrew formula asserts one executable, `aeat`. `cadrumo-mcp` appears in neither. A user
who installs through either managed channel receives the application and not the server
that fronts it, so the two-console-script product is only actually two on the index.

The wheel is not at fault - it declares both entry points and both were proven to run
from the built artifact. The gap is in what each channel chooses to expose, which means
the generators are where it closes.

### The managed channels source release assets, not the index

Both generators take a release base URL and pin digests against artifacts served from it:
the Scoop manifest fetches three wheels from a release tag, and the Homebrew formula
fetches the source archive from the same place. The accepted decision says the managed
channels install what the index serves, and these install what a release page serves -
the same bytes by construction today, but a second distribution surface with its own
availability and its own retention.

That is resolved, and against the generators. Nothing in the tree attaches an asset to a
GitHub release: `gh release upload` appears in no workflow, the release configuration
declares no extra assets, and a standing gate forbids every packaging workflow from
reaching the releases API at all. The base URL both generators pin therefore addresses a
surface the adopted path never populates, so a formula or manifest rendered today points
at downloads that do not exist. Both managed channels would fail at install.

The accepted decision already says what the fix is - the managed channels install what
the index serves - so this is the generators failing to follow the decision rather than
the decision needing revision. It is the first defect found that makes the pipeline
incapable end to end rather than merely unproven.

### The evidence rows cannot exist before a first release

Every one of the seven rows the three channels declare is an acquisition proof: the
producers install the product from the real channel and repeat grounded tax work from
that environment. The index acquirer refuses instructively while the index does not yet
serve the promoted version, and the tap and bucket acquirers have nothing to install
from until a first publication writes the formula and manifest. Four distinct platforms
are needed to mint the full set, only one of which is a workstation.

So the readiness gate's blocking evidence set is not merely unmet, it is unmeetable
before the first release - which makes the first release the act that produces its own
preconditions, and means the gate cannot be the thing that authorises it.

### The publication leak sweep guards a transport that no longer exists

The sweep is the tripwire above the evidence builders: it refuses a promotion when an
asset about to be attached to a public release still carries a runner hostname or an
operating-system username. Nothing attaches assets any more, and a standing gate forbids
packaging workflows from reaching the releases API, so it has no payload to sweep.

Whether it is dead or merely dormant depends on how the channel-source defect above is
settled. Sourcing the managed channels from the index keeps release assets absent and
the sweep permanently unreachable; populating release assets to satisfy the generators
as written brings the hazard straight back and needs the sweep wired into the new path.
Deleting it before that is decided would remove a security control on the strength of a
guess.

### Deletions landed; the gates naming what was deleted did not

Five separate gates in this repository police an artefact that an earlier step of this
same work removed. Each fails by raising a missing-path error rather than reporting a
violation, which is the more dangerous shape: it reads as the invariant failing when the
invariant no longer has a subject.

The base-image singularity gate names a container proof retired with the nested-container
install path. The wall advisory's consumer-parity check reads a benchmark file deleted in
the import promotion. The distribution-readiness suite builds a fixture wheel from a
harness directory folded into the product package. The external-client boundary asserts a
workflow retired with the plugin channel. And the recipe-guidance suite asserted the
contents of an evidence-collection recipe removed one step earlier in this phase - that
last one introduced by this work and repaired in the same run that found it.

The common cause is that all five name their subject as a literal path. A gate that
enumerates what it checks cannot distinguish "this is gone" from "this is wrong", and
stops asserting anything about a surface nobody added to its list. Both gates repaired so
far were converted to discover their subjects and to fail when discovery finds nothing,
which is the shape that survives a deletion in either direction.

Ten of these failures predate this phase and remain open: eight in the
distribution-readiness suite and two in the external-client boundary, all traceable to
the harness fold and the channel retirement.

### The absent-inference smoke lane cannot import what it drives

Retiring the inference package's namespace left its initialiser inert, which is what the
architecture requires of every package initialiser. The absent-inference smoke lane did
not follow: its child-interpreter script still reaches eight surfaces through
`from cadrumo.llm import ...` at two places, and that package root now exports nothing.
The lane fails on its import line, which is precisely the failure its own non-vacuity
gate was written to prevent - and that gate is red for the same reason, asserting
membership in an `__all__` that policy requires to be empty.

This is an application defect wearing a gate defect's clothes. The check is correct to
fail; the lane is what is broken. Every one of the eight names resolves at a defining
module - the rasteriser at `llm/providers/local.py`, the transcriber at
`llm/evidence_draft_vision.py`, the field extractor at `llm/evidence_draft_text.py`, the
classifiers and the column mapper at their own modules - so the repair is to import each
from where it is defined and to assert resolution there rather than at a namespace that
no longer has one.

Both are repaired. The inventory now carries the defining module beside each surface, so
the driver's import block is rendered from the same declaration the lane drives rather
than restated beside it, and the non-vacuity gate resolves each name at that module.

The second gate had the same root cause with a worse consequence. It split guarded
surfaces into reachable and internal by reading the package's `__all__`, so once that
was inert every surface classified as internal, the reachable set emptied, and the
coverage claim it feeds became vacuously true. Reachability is now read from the module
a surface is defined in, which is the rule consumers import by. Repairing it immediately
surfaced a real hole the old rule had been hiding: `SupplyNatureProposer` carries the
guard and is public, and the lane had never driven it, so the claim that every guarded
surface returns to the refusal was never true of it. It is enrolled now.

### What the packaging suite still reports, and what it cannot report here

With the absent-inference lane repaired the packaging suite runs 264 passed against three
failures, every one of them reproducible at the clean commit and so none introduced by
this work.

Six tests under `dev/packaging/tests` had no packaging-scoped owner. All six are
`integration and serial`; the preflight lane excludes serial deliberately, and the
installed-oracle lane names one module, so the remainder was reachable only through the
tree-wide serial recipe. Someone verifying packaging alone got a green result that never
touched them - and two of the six are the gates asserting the inference lane covers every
guarded entry point, the claim this phase found vacuous. A recipe owning the serial
remainder closes it. The tests were never absent from CI, which runs the tree-wide lane;
what was missing was the directory-scoped ownership the gate exists to require.

One inference test imports `pydantic_core` directly while no declaration names it, so the
package is relied on as an incidental transitive. That one is open.

The third failure is environmental rather than a finding: the core-payload gate shells out
to `git archive HEAD` and that command fails in this worktree. A fourth, in the evidence
emitter, does not fail but times out during a large `copytree` under host load. Neither
can be resolved by reading the tree, and both mean the suite has no clean whole-run
verdict on this workstation - only on a runner.

### The release path was already running, and being refused in seconds

`release-please` has fired on every push to the default branch since it landed and failed
each time in six to eight seconds. The forge refuses a workflow whose actions are not
pinned to full-length commit SHAs, and it refuses it before any step runs. Both workflows
ported for this work referenced their actions by tag.

Nothing downstream could happen: no release pull request was opened, so no tag was cut,
so the publish workflow it dispatches never ran, so the project never rendered on the
index and the pending publisher holding the name had nothing to admit. Every conclusion
recorded above about publication being "not yet attempted" was true of the outcome and
wrong about the cause - the attempt was being made, several times an hour, and discarded.

The failure is the quiet kind. It is reported as an actions-permission error, which reads
as a repository settings problem rather than as a defect in the workflow just added, and
the run is short enough to look like a no-op. The one gate asserting SHA pins covered the
artifact actions of the packaging workflows, and the release path is neither an artifact
action nor a packaging workflow, so the tree said nothing.

Both workflows now pin every action to the SHA the rest of the tree already uses, so
there is one pin per action across the repository rather than a second opinion in the
release path. A gate now asserts the rule the forge applies - every action, every
workflow - and refuses an abbreviated SHA as well as a tag, because a short SHA looks
pinned and a check that only rejected a leading `v` would pass it.

Pinning is the whole of the constraint: the repository allows all actions and requires
SHA pinning, so no allowlist stands behind the refusal and nothing else about these two
workflows was rejected. Every other workflow in the repository was already pinned and is
green across recent runs; the release path was the only failing workflow in the tree.

An earlier version of this record added that the publish workflow had no runs at all. It
has several, from early July, some of them successful. They belong to a different
workflow that occupied the same filename: the current one was added on 2026-09-02, and
run history is keyed to the path rather than to the file. The claim was read off a run
list without checking whether those runs predated the file, and the correct statement is
narrower - the publish workflow as it now stands has never been dispatched.

### What the first release pull request actually carries

With the pin refusal lifted, release-please ran to completion: it created the release
branch, wrote the version bump across the manifest, `pyproject.toml` and the package
initialiser, and rendered the changelog. The computed version is `0.3.0`. Five commits
carry a breaking marker, and the configuration sets `bump-minor-pre-major`, so below
`1.0.0` those bump the minor rather than the major - the setting exists for exactly this
and is doing its job.

The changelog window itself was never the problem: release-please takes its base from the
version in the manifest and renders `v0.2.2...v0.3.0`, so the bootstrap commit only bounds
where a search may begin. An earlier prediction that the notes would span every commit
since that point - 8,640 of them - was wrong on that count.

But the retraction of that prediction went too far, and a run settled it. The notes are
too large for a pull request body: the `0.3.0` section measures 78,218 characters against
the 65,536 limit. The retraction was made on the strength of the changelog diff adding
only 461 lines, which conflated line count with byte count - 461 lines of dense changelog
entries is 78 KB. The original concern was right in substance and wrong in its arithmetic,
and dismissing it took a real defect off the board for several hours.

The weight is concentrated and the fix follows from where it sits. Documentation
(25,760 characters), Code Refactoring (25,813) and Tests (12,485) are 82% of the notes;
Features, Bug Fixes and Reverts together are 8,669. Those three, plus performance, are
what a reader of a release needs, and hiding the rest brings the notes to 8,669 characters
with 56 KB of headroom. That is also the conventional shape - a product changelog listing
three thousand documentation commits serves nobody.

The run still failed, at the last step and for a reason unrelated to any of the above:
the repository does not permit GitHub Actions to create pull requests. Everything the
release needed was computed and committed to the branch; only the pull request that would
carry it could not be opened.

### The publish step offered the index files it would refuse

Auditing one link further down the chain found the failure waiting after the pin refusal
is lifted. The build job seals a checksum manifest into `dist/` and then publishes
`dist/*`, so the upload offers `manifest.sha256` alongside the six distributions. An
upload is not atomic and is per-file, so this fails part-way through rather than before
it starts - the worst place for it, and the one the `--check-url` retry exists to
recover from.

The publish step now names distributions by suffix. The gate asserting it reads the
command line rather than the file, so it can be exercised against the shape it replaced
as well as the one that ships; a check that could only read the live workflow would be
the same enumerate-your-subject weakness found five times elsewhere in this work.

The marker `uv build` leaves in the output directory was never at risk - a shell glob
skips a dotfile - but it is the same class of passenger and the suffix rule covers both.

### The smoke gate could have passed by proving nothing

The publish path derives its smoke matrix from the stable runtime inventory and guarded
the result with a non-empty-string test. `{"include":[]}` is a non-empty string. An
inventory that yielded no stable rows would therefore emit a valid matrix expanding to
zero jobs, and a matrix job with no combinations does not fail - so the smoke stage would
report success having installed the artifact nowhere, and publication would proceed on
that.

The inventory currently yields two rows and six targets, so nothing was actually
unproven. The defect is that the only thing standing between an empty inventory and an
unproven publication was a test that could not tell the difference. It now counts the
entries and refuses at zero, naming the reason.

This is the third fail-open found in the release path in one pass, after a gate that
enumerated deleted subjects and a completeness claim over an empty set. The shape is
consistent: each measured something adjacent to what it claimed - a string's length, a
file's presence, a namespace's contents - rather than the property itself.

### The release would have been cut and then refused by the product's own gate

Six surfaces have to report one version before this product may release: the root
project, both companion projects, the package initialiser, the release manifest, and the
two exact pins binding the companions to the root. The blocking readiness check compares
all six, and the cohort builder refuses a set of distributions that do not share a
version.

Release-please was configured to bump three of them. Its Python release type moves the
root project version, the manifest, and - confirmed by an actual run rather than assumed
- the initialiser's `__version__` without needing to be told. The two companion
`pyproject.toml` files and the two `==` pins it never touched.

The failure mode is the expensive one. Nothing refuses at configuration time: the release
branch is written, the version bump is committed, the tag is cut, and only then does the
product's own gate refuse a version that already exists and cannot be reminted. The tool
and the gate disagreed about what a version is, and the tool goes first.

Every surface outside the release type's own knowledge now carries the annotation the
generic updater rewrites, and all four are configured. A gate compares the two sides
directly - what the readiness check demands against what the tool is configured to move -
so a new companion cannot be added without the versioning learning to bump it, and a
configured path carrying no annotation is reported rather than silently written back
unchanged.

A run confirms it rather than the configuration implying it. The release branch written
after the fix landed carries all six surfaces at `0.3.0`: the root project and both
companion projects, the initialiser, the manifest, and both exact pins rewritten in place
on their annotated lines. The branch written before it carried four, and the two it
omitted are exactly the two the readiness gate would have refused the release for.

### The release branch's content passes the gate, and its lockfile does not - yet

Run against the branch release-please actually wrote, the blocking version check reports
that every release authority and both exact companion pins agree on `0.3.0`, and the
changelog check passes beside it. That is the gate itself reading the real files rather
than the configuration being read as implying them.

Its `uv.lock` does not match, because bumping two exact pins invalidates a resolution
nothing has redone. That is a symptom of the same permission refusal rather than a
second defect: the workflow regenerates and pushes the lock onto the release branch, and
that step is conditioned on the release pull request existing. No pull request, no lock
regeneration - and the two failures therefore clear together.

Worth stating because the order looks alarming from outside. The first job of the publish
path runs `uv sync --frozen`, so a merge of the branch as it stands today would fail
before any distribution was built. Nothing about that is a reason to fix the lock by
hand: doing so would repair a symptom on a branch the tool rewrites on every push.

### The permission was the first of two refusals, not the only one

Granting Actions the ability to open pull requests changed the failure rather than
removing it. The run now reaches further and stops at `Invalid request.`, whose detail
line is `"sha" wasn't supplied` against the contents API - raised immediately after
release-please resets a `--release-notes` branch to match the default branch.

That branch is the tell. Release-please creates it only when the notes exceed what a pull
request body holds, offloading them to a file and linking to it, and the write of that
file is what fails. So the permission refusal had been masking an overflow the whole time:
two independent blocks in series, the second invisible until the first cleared.

Both branches now exist on the remote, `release-please--branches--main` carrying the
correct six-surface bump. Neither is a pull request, and neither cuts a tag.

### The release pull request merged, and the tag did not follow

The pull request is merged and the default branch carries `0.4.0` across every surface.
release-please then ran twice against that commit, succeeded both times, and produced no
tag, no release and no dispatch. Both runs end the same way: it finds pull request #670,
recognises it as merged and untagged, and aborts - correctly, since a merged release
awaiting a tag is a reason not to open another. What never happens is the other half. The
release-creation phase leaves no trace in either log.

The condition is the bootstrap one. The repository has never carried a tag, and the
manifest on the default branch now already reads the version being released, so the tool
looks for `v0.4.0`, finds no prior release to anchor against, and has nothing it
recognises as work. A first release has no predecessor by definition, and that is the
case this configuration has never been through.

Consequential because the dispatch is conditioned on it. `publish.yml` is triggered by
the release step reporting a release was created, so an untagged merge does not merely
delay publication - it removes the trigger. Creating the tag by hand would not dispatch
the workflow either; that takes an explicit dispatch against the tag.

The merge itself needed an administrative bypass. A ruleset named `protect-main` forbids
updates to the branch, and it carries no required review and no required status check, so
the bypass skipped no gate that exists - it is the same bypass an ordinary push by the
owner already uses.

### The pipeline is proven capable, up to the upload

The first real publish run exercised every stage the campaign had only measured locally,
and each one held. The runtime inventory produced a non-empty matrix. The three
distributions built from the tag. The index file-cap check passed against the single
declaration of the limit. The bytes were sealed and re-verified after transport. And the
smoke check ran on six legs - Linux, macOS and Windows, each on Python 3.13 and 3.14 -
proving both console scripts from the built wheel on every supported platform.

Then the upload refused on the second of six files. So the shape of the result is worth
stating precisely: the pipeline is demonstrated capable of building, proving and shipping
this product, and the one thing it could not do was authenticate for two distributions
whose registrations were never made. Nothing in the tree was at fault.

The release also needed a tag created by hand. release-please would not cut one, and its
dispatch is conditioned on cutting it, so the workflow had to be dispatched explicitly
against the tag as well.

### The product is installable from the index

Both companion registrations were made and the same workflow re-dispatched against the
same tag. It converged rather than needing a new version: the log reads `File
cadrumo-0.4.0-py3-none-any.whl already exists, skipping`, then uploads the remaining
five. That is what `--check-url` is for, and a partial upload is exactly the condition it
was added to recover from.

All three distributions now serve `0.4.0`, wheel and source archive each. Verified from
outside rather than from a local build: installing `cadrumo==0.4.0` into an isolated
environment holding only the artifact resolves both corpora at the matching version,
imports the package, runs `aeat --version` and `aeat --help` with both root command
families present, and resolves `cadrumo-mcp` with its server runtime importable.

One reading during that verification was wrong and worth noting: the index reported one
file for the primary distribution moments after the upload, which read as a missing
source archive. It was propagation, not absence - both files were there on the next
request. A single read of an index immediately after an upload is not a measurement.

### The acquisition evidence cannot be produced from a local rebuild

Reacquiring the published product refuses, and correctly: the index serves a wheel whose
digest does not match a cohort rebuilt here from the release commit. The index is not at
fault - the digest it declares is exactly the one the acquirer downloaded, so it is
serving precisely what the workflow uploaded.

Diffing the two wheels member by member locates it exactly. Of 24,838 entries every one
is byte-identical except two, present only in the local build:
`_data/registry/aeat-registry-identity.json` and
`_data/registry/aeat-validation-verdict.json`. `RECORD` differs as a consequence of
listing them. Both are the registry-validation verdict cache - a persisted certification
that a prior validation passed, written so a later load can skip re-validating an
immutable bundled registry. Neither is tracked, neither is ignored, and neither is in the
source tree now, so they are produced during the build and captured by it.

The build is therefore reproducible in everything except its own cache: a tree where
registry validation has run yields a wheel two files larger than a clean one. The
published artifact is the clean build, which is the right one to have shipped.

The consequence for the evidence set is structural rather than a matter of scheduling. An
acquisition row proves the installed bytes match the cohort that was promoted, so it can
only be minted against the cohort the workflow actually built - never against a local
rebuild of the same commit. Every one of the three `python-*` rows therefore belongs to
CI, alongside the four `homebrew-*` and `scoop-*` rows that need channels nobody has
published. Zero of the seven are producible on a workstation, and an earlier note in this
record that one of them was is wrong.

### Not investigated

Nothing outstanding for this decision.

## Sources

- `docs/_data/download_channels.toml`
- `dev/packaging/python_cohort.py:286`
- `dev/packaging/smoke_docker.py`
- `dev/release/burned_versions.json`
- `dev/release/release_candidate.py`
- `dev/release/seal_candidate.py`
- `dev/ci/tests/test_self_hosted_fleet.py`
- `src/cadrumo/entrypoints/cli/_root_cli.py`
- `src/cadrumo/entrypoints/cli/_root_command_specs.py`
- `src/cadrumo/entrypoints/cli/_tui_policy.py`
- `src/cadrumo/entrypoints/cli/__init__.py`
- `src/cadrumo-harness/pyproject.toml`
- `pyproject.toml`
- commit `c771bffe46`
- https://pypi.org/pypi/vaultspec-core/json
- https://pypi.org/pypi/vaultspec-rag/json
- https://pypi.org/pypi/cadrumo/json
- https://github.com/nevenincs/homebrew-tap
- https://github.com/nevenincs/neve-marketplace
- PyPI release metadata for `cryptography`, `argon2-cffi-bindings`, `pikepdf`,
  `pypdfium2`, `pillow`, `lxml`, `rtoml` and `pydantic-core`, read from their
  respective `https://pypi.org/pypi/<name>/json` endpoints
- The canonical runner-fleet manifest and the two sibling publish workflows are read
  from sibling checkouts outside this repository, at `Y:/code/ci-fleet/fleet.yml`,
  `Y:/code/vaultspec-core-worktrees/main/.github/workflows/publish.yml` and
  `Y:/code/vaultspec-core-worktrees/main/.github/workflows/release-please.yml`.
