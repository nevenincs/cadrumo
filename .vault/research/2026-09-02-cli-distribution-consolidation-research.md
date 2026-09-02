---
tags:
  - '#research'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:76252cbc89220914e41467e64b19c27a9e03d1e205cafcdd65ca66543fa06f01'
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
That asymmetry matters for the trust bindings: a pending publisher applies only to a
name with no project behind it, so the two corpus distributions take the ordinary
project-level publisher form instead, registered per project. Until both carry one,
`uv publish dist/*` uploads the primary distribution and is refused on the other two.

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
