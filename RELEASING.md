# How to publish a Cadrumo product release

A Cadrumo release is cut by merging a pull request. There is no dispatch to start one,
no rehearsal mode, and no sealed candidate to retire afterwards.

`release-please` watches `main`, keeps a release pull request up to date from the
conventional commits merged since the last release, and dispatches `release.yml` in its
prove phase against that pull request's branch. The prove run builds the release cohort
once, refuses any file the index would reject, and proves the sealed files on every stable
runtime and channel across Linux, macOS and Windows. When the pull request merges,
release-please writes the version surfaces and the changelog, tags `vX.Y.Z`, creates the
GitHub release, and dispatches `release.yml` in its publish phase, which reuses the proven
cohort and uploads it to PyPI with Trusted Publishing.

PyPI is the primary target. Homebrew and Scoop are downstream of what it serves.

## Release path

| Stage | Authority | Result |
| --- | --- | --- |
| Propose | `release-please.yml` | Keeps a release pull request current from conventional commits on `main` |
| Release | `release-please.yml` | On merge: writes version surfaces and changelog, tags `vX.Y.Z`, creates the GitHub release |
| Prove | `release.yml` (`phase=prove`) | Runs the merge gate and full suites, builds and seals the cohort once, and proves it on every runtime and channel |
| Publish | `release.yml` (`phase=publish`) | Locates the proven cohort for the tag, uploads it to PyPI over OIDC without rebuilding, then updates and reacquires the channels |

The workflow runs and their logs are the authoritative operational record.

## The authority is staged, never committed

The runtime authority is generated output that the distributions nevertheless
ship: a released package carries the descriptor and the one database it names
at `cadrumo/_data/registry/authority/`, and resolves it there with no
environment variable set. It is not in the repository. A checkout publishes its
own into the gitignored `.authority/` directory, and the build stages that
descriptor-selected pair into the isolated build root, so what ships is the
pair the builder published rather than anything read from the working tree.

This has one consequence for a local release build: publish before you build.
`just build-distributions` cannot produce a complete distribution from a
checkout that has never run `just registry-publish-authority`, and it refuses
rather than emitting a package without its only registry payload.

Selection is descriptor-driven. A superseded content-addressed database that a
checkout retains, the publisher's lock sidecar, and any in-flight staging
directory are not members of the release cohort.

## One-time setup

Publication authenticates with PyPI Trusted Publishing over OIDC. No token is stored
anywhere, so the one-time setup is three publisher registrations rather than a secret.
All three carry the same four values:

| Field | Value |
| --- | --- |
| Owner | `nevenincs` |
| Repository | `cadrumo` |
| Workflow | `release.yml` |
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
`publish.yml`, `pypi-upload.yml` or `publish-release.yml`. The `pypi` environment is the OIDC trust
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
just release-check
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

`just release-check` also blocks on a distribution-evidence set that cannot be
satisfied before a first release: every row in it is an acquisition proof that installs
the product from a channel that does not serve it yet. Read those two checks as
reporting, not as authorisation, until the first release exists.

To see what will be built before releasing anything:

```console
just build-distributions
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
2. Run `just test-python-compatibility` locally from a clean checkout and run the
   dedicated compatibility workflow. Require source, binary, and sealed-artifact
   evidence for the new stable row on every supported platform.
3. Add the exact `Programming Language :: Python :: 3.N` classifier to the root
   project and both data companions only after the inventory marks that row
   eligible and the parity gate passes.

Never add a stable classifier for a prerelease row, and never change
`.python-version` as part of runtime promotion; the builder identity is an
independent reproducibility coordinate.

## Release-candidate evidence

The distribution evidence rows the readiness gate requires come from the prove run of
`release.yml` that release-please dispatches for the release pull request. Every row in
that run is bound to the one cohort it built. To prove the pull request again, dispatch
the same phase against its branch:

```console
gh workflow run release.yml --repo nevenincs/cadrumo --ref <RELEASE_BRANCH> \
  -f phase=prove -f ref=<RELEASE_BRANCH> -f version=<VERSION>
```

The prove run needs all three self-hosted runner shapes online — Linux x64, Windows x64
and macOS ARM64. A queue watchdog cancels the run when a lane has no runner, but confirm
before dispatching:

```console
gh api repos/nevenincs/cadrumo/actions/runners --jq '.runners[] | "\(.status)  \(.name)"'
```

Merge the release PR once the prove run is green.

## Release

Merge the open release PR. Everything else follows from that merge.

```console
gh pr list --repo nevenincs/cadrumo --label "autorelease: pending"
gh run list --repo nevenincs/cadrumo --workflow release-please.yml --limit 5
gh run list --repo nevenincs/cadrumo --workflow release.yml --limit 5
```

If the publish phase of `release.yml` did not start within a minute of the release being
created, the dispatch step failed. Start it by hand against the tag that was cut:

```console
gh workflow run release.yml --repo nevenincs/cadrumo --ref v<VERSION> \
  -f phase=publish -f ref=v<VERSION> -f version=<VERSION>
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
just release-rollback-plan <VERSION>
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

## Managed channels

After the PyPI upload, the publish phase of `release.yml` updates the channels from the
same proven cohort: it commits the cohort's Homebrew formula to the tap and its Scoop
manifest to the bucket, skipping a commit when the channel already serves that version.
It then reacquires the release from PyPI, the tap and the bucket on their own runners.

Both channel jobs refuse to start without their credentials:

| Channel | Repository | Credential |
| --- | --- | --- |
| Homebrew | variable `HOMEBREW_TAP_REPOSITORY` (default `nevenincs/homebrew-tap`) | secret `HOMEBREW_TAP_TOKEN` |
| Scoop | variable `SCOOP_BUCKET_REPOSITORY` | secret `SCOOP_BUCKET_TOKEN` |

A channel failure does not undo the PyPI upload. Fix the credential or the channel and
re-run the failed jobs of the same run.

## Authorities

- `.github/workflows/release-please.yml` — computes the version, cuts the release, dispatches proof and publication
- `.github/workflows/release.yml` — sole proof and publication authority
- `.github/workflows/merge-gate.yml` — the required pull request verdict, reused by the prove phase
- `dev/smoke/smoke_check.py` — the check that proves an installed artifact
- `dev/packaging/_distribution_limits.py` — the index file cap, declared once
- `SECURITY.md` — private security reporting
