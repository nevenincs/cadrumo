# How to publish a Cadrumo product release

A Cadrumo release is cut by merging a pull request. There is no dispatch to start one,
no rehearsal mode, and no sealed candidate to retire afterwards.

`release-please` watches `main`, keeps a release pull request up to date from the
conventional commits merged since the last release, and does the whole release when that
pull request merges: it computes the version, writes the version surfaces and the
changelog, tags `vX.Y.Z`, creates the GitHub release, and dispatches the publish
workflow. The publish workflow builds the three distributions from that tag, refuses any
file the index would reject, proves the sealed files on every stable runtime across Linux,
macOS and Windows, and uploads to PyPI with Trusted Publishing.

PyPI is the primary target. Homebrew and Scoop are downstream of what it serves.

## Release path

| Stage | Authority | Result |
| --- | --- | --- |
| Propose | `release-please.yml` | Keeps a release pull request current from conventional commits on `main` |
| Release | `release-please.yml` | On merge: writes version surfaces and changelog, tags `vX.Y.Z`, creates the GitHub release |
| Build | `publish.yml` | Builds the three distributions from the tag and refuses any file at or over the index cap |
| Prove | `publish.yml` | Installs the sealed distributions on every stable inventory runtime across Linux, macOS and Windows |
| Publish | `publish.yml` | Uploads every distribution to PyPI over OIDC, without rebuilding |

The workflow runs and their logs are the authoritative operational record.

## One-time setup

Publication authenticates with PyPI Trusted Publishing over OIDC. No token is stored
anywhere, so the one-time setup is three publisher registrations rather than a secret.
All three carry the same four values:

| Field | Value |
| --- | --- |
| Owner | `nevenincs` |
| Repository | `cadrumo` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

Which registration form to use is decided by the index, not by preference. A name the
index does not carry takes the **pending publisher** form at
<https://pypi.org/manage/account/publishing/>, which also reserves the name. A name the
index already carries takes the ordinary **project-level** form at
`https://pypi.org/manage/project/<name>/settings/publishing/`.

- `cadrumo` — no project on the index yet, so it takes the pending form, which is also
  what reserves the name.
- `cadrumo-data-manuals` — published at `0.0.0`, so it takes the project-level form.
- `cadrumo-data-official` — published at `0.0.0`, so it takes the project-level form.

All three are registered. A registration is visible only from inside the account, so
neither this document nor any check in this repository can confirm one: the first publish
run is what demonstrates them. An upload is per-file, so a distribution whose binding is
missing or misspelled is refused on its own while the others succeed, and re-running the
workflow against the same tag reconciles the partial upload. Remove any obsolete
registration naming
`pypi-upload.yml` or `publish-release.yml`. The `pypi` environment is the OIDC trust
anchor and must exist on the repository; the workflow does not require environment
reviewers.

Confirm the repository configuration used by the destinations that are enabled:

- variable `HOMEBREW_TAP_REPO` and secret `HOMEBREW_TAP_TOKEN`
- the `release-alert` repository label, or the configured webhook fallback

## Per-release preflight

Both workflows run on hosted runners, so no self-hosted runner needs to be online to
release. Work from a clean `main` checkout with an authenticated GitHub CLI:

```console
git status --short
gh auth status
just release-readiness
```

Stop if the checkout is dirty, the repository identity is not `nevenincs/cadrumo`, or a
`priority:P0-blocker` issue is open.

Confirm every deployment environment a workflow claims exists on the forge, and that no
environment is left behind that none of them claims. A publish job whose environment is
absent cannot have its OIDC claim attested, and the failure names the token rather than
the missing environment:

```console
gh api repos/nevenincs/cadrumo/environments --jq '.environments[].name'
grep -rhA1 "^\s*environment:$\|^\s*environment: " .github/workflows/ | grep -oE "(environment|name): [a-z-]+" | awk '{print $2}' | sort -u
```

The first list is what the forge has, the second what the workflows claim. Every claimed
environment must appear in the first, or its job's OIDC claim cannot be attested and the
failure names the token rather than the missing environment. An environment in the first
that no workflow claims is residue: delete it, then check separately whether any index
publisher registration still names it, which is neither in this repository nor on this
forge.

`just release-readiness` also blocks on a distribution-evidence set that cannot be
satisfied before a first release: every row in it is an acquisition proof that installs
the product from a channel that does not serve it yet. Read those two checks as
reporting, not as authorisation, until the first release exists.

To see what will be built before releasing anything:

```console
just packaging-distributions
```

That runs the same two operations the publish workflow performs, in the same order, and
writes to `var/distributions`.

## Python runtime evidence and promotion

The checked-in runtime inventory is the authority for the release matrix. The
publish workflow validates its stable rows, builds the three distributions once
with the exact [`.python-version`](.python-version) builder identity, seals the
result with a checksum manifest, and runs the same downloaded files on every
stable runtime in the Linux/macOS/Windows matrix. A runtime can therefore be
tested before its metadata classifier is promoted.

Keep source-vs-binary evidence separate. Source evidence builds from a clean
source snapshot and proves that the package can be produced for a runtime.
Binary evidence installs wheels from the one sealed cohort and proves that
native dependencies have compatible wheels. A source pass does not substitute
for a binary pass, and a failed or missing wheel must not be reported as a
skipped check. Artifact evidence is the final identity check: each runtime must
smoke-test the exact checksum-verified files that will be uploaded, without a
per-runtime rebuild.

Keep the prerelease `next` selector provisionable: use its rolling minor (for
example, `3.15`) while prereleases are available, and retain the observed patch
version (for example, CPython `3.15.0b4`) in evidence. A fixed RC selector must
not be declared unless the selected interpreter is actually provisionable.

When a new CPython minor reaches its final release, promote it in this order:

1. Move the `next` row into `stable`, set `current_stable_minor`, and add the
   following prerelease row in `dev/ci/python-runtime-matrix.json`. Keep the
   promoted stable row blocking but `classifier_eligible: false` initially.
2. Run `just python-compatibility` locally from a clean checkout and run the
   dedicated compatibility workflow. Require source, binary, and sealed-artifact
   evidence for the new stable row on every supported platform.
3. Add the exact `Programming Language :: Python :: 3.N` classifier to the root
   project and both data companions only after the inventory marks that row
   eligible and the parity gate passes.

Never add a stable classifier for a prerelease row, and never change
`.python-version` as part of runtime promotion; the builder identity is an
independent reproducibility coordinate.

## Release-candidate evidence

The channel descriptors declare distribution evidence rows, and the release-readiness
gate refuses a release until every declared row is present and passing. Those rows come
from one place: the `Cadrumo Packaging Smoke` workflow, dispatched by hand. It never runs
on push, because the three-OS matrix is the most expensive workflow in the repository.

Dispatch it after the release PR has merged, against the tag that merge created.

```console
gh workflow run packaging-smoke.yml --repo nevenincs/cadrumo --ref v<VERSION>
```

Then mint the acquisition rows from that run, naming the commit it built:

```console
gh workflow run packaging-homebrew.yml --repo nevenincs/cadrumo --ref main \
  -f source_run_id=<SMOKE_RUN_ID> -f source_commit=<SMOKE_HEAD_SHA>
gh workflow run packaging-scoop.yml --repo nevenincs/cadrumo --ref main \
  -f source_run_id=<SMOKE_RUN_ID> -f source_commit=<SMOKE_HEAD_SHA>
```

The timing is not a preference. The readiness gate binds every distribution-evidence row
to the cohort that produced it, and refuses unless that cohort's source commit equals the
checked-out commit and its tag equals `v<VERSION>`. Only the merged release commit
satisfies both: release-please creates the tag when the PR MERGES, so on the release
branch itself no tag points at the commit, the cohort records no tag at all, and the gate
refuses every row:

```text
[BLOCK] distribution-evidence-complete: cohort tag None does not match version tag 'v<VERSION>'
```

A campaign dispatched against `main` after later commits have landed fails the other half,
because the cohort's commit is no longer what is checked out:

```text
[BLOCK] distribution-evidence-complete: cohort commit <COMMIT> does not match checked-out commit <COMMIT>
```

The acquisition lanes agree independently: each resolves its source run's commit against
main's history and refuses one that is not on it, so a release-branch commit is rejected
there too, before any row is written.

Run the readiness gate with the tag checked out, not `main`, or the commit comparison
fails against a tree the cohort was never built from. All seven rows must come from ONE
smoke run: the gate compares the whole cohort binding, so rows mixed across two campaigns
are refused.

The cohort seal itself does not refuse a version some destination already owns. Building a
cohort uploads nothing, and between releases the commit legitimately declares the version
that is already published, so the seal refuses only a version recorded in the burned
ledger. The collision rules are asked once, by `publish.yml`, immediately before the
upload.

The matrix needs all three self-hosted runner shapes online — Linux x64, Windows x64 and
macOS ARM64. Confirm before dispatching, or the jobs queue until they are cancelled:

```console
gh api repos/nevenincs/cadrumo/actions/runners --jq '.runners[] | "\(.status)  \(.name)"'
```

Merge the release PR once the campaign is green.

## Release

Merge the open release PR. Everything else follows from that merge.

```console
gh pr list --repo nevenincs/cadrumo --label "autorelease: pending"
gh run list --repo nevenincs/cadrumo --workflow release-please.yml --limit 5
gh run list --repo nevenincs/cadrumo --workflow publish.yml --limit 5
```

If `publish.yml` did not start within a minute of the release being created, the
dispatch step failed. Start it by hand against the tag that was cut:

```console
gh workflow run publish.yml --repo nevenincs/cadrumo -f tag=v<VERSION>
```

## Verify the published release

```console
gh release view v<VERSION> --repo nevenincs/cadrumo --json tagName,targetCommitish,isDraft
gh run view <PUBLISH_RUN_ID> --repo nevenincs/cadrumo
```

Confirm all three projects serve the released version and that the artifact runs from
the index rather than from a local build:

```console
curl -s https://pypi.org/pypi/cadrumo/json | python -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
curl -s https://pypi.org/pypi/cadrumo-data-manuals/json | python -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
curl -s https://pypi.org/pypi/cadrumo-data-official/json | python -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
uv run --isolated --no-project --with "cadrumo==<VERSION>" dev/smoke/smoke_check.py
```

The smoke check proves both console scripts: `aeat` reports the released version and
lists both root command families, and `cadrumo-mcp` resolves with its server runtime
present.

## Roll back a released version

An index upload cannot be undone, so a rollback is a forward action: yank the bad
version and release a corrected one. The recipe prints the procedure and runs nothing
destructive itself.

```console
just release-rollback <VERSION>
```

The conditions that oblige a rollback, the hotfix cycle times they must be answered
within, and the checks the audit-state gate applies are declared once in
`docs/_release_checklist.yaml` and consumed by the readiness gate. Change them there
rather than here.

## Diagnose and recover

```console
gh run view <RUN_ID> --repo nevenincs/cadrumo --log-failed
```

**The publish step is refused on some distributions and succeeds on others.** An upload
is per-file and each distribution carries its own publisher binding. Register the
missing ones from the one-time setup above and re-run the workflow against the same tag;
`uv publish` reconciles a partial upload rather than failing on what already landed. The
identity check ahead of the upload permits that re-run and names which projects already
carry the version:

```text
NOTE: the package index already carries <VERSION> for cadrumo, cadrumo-data-manuals and not yet for cadrumo-data-official; ...
```

It refuses only once every project carries the version, because at that point nothing is
left to converge and the run could only attempt bytes the index will not take back.

**A distribution is at or over the index file cap.** The build stops before anything is
uploaded. The corpus split exists to keep every file under that limit, so a refusal here
means a corpus slice outgrew its share rather than that the limit needs raising.

**The lockfile drifted.** `release-please.yml` opens a reconciling pull request when
`main` carries the previous version's `uv.lock`. Merge it; every job installing with
`--frozen` fails until it lands.

**A version is unusable.** PyPI does not allow a version to be re-uploaded, even after
deletion. Release the next patch version rather than trying to reuse one.

## Known limitation: the managed channels

The Homebrew formula and the Scoop manifest are generated with a release base URL and
pin their digests against artifacts served from it. No workflow attaches assets to a
GitHub release, so a formula or manifest generated today addresses downloads that do not
exist, and an install through either channel fails.

Publish to PyPI. Do not publish the tap or the bucket until the generators source what
the index serves.

## Authorities

- `.github/workflows/release-please.yml` — computes the version, cuts the release, dispatches publication
- `.github/workflows/publish.yml` — sole publication authority
- `dev/smoke/smoke_check.py` — the check that proves an installed artifact
- `dev/packaging/_distribution_limits.py` — the index file cap, declared once
- `SECURITY.md` — private security reporting
