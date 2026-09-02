# How to publish a Cadrumo product release

Cadrumo releases are driven by one manual dispatch of
`.github/workflows/release-orchestrator.yml`. The workflow computes and commits the
version, builds one immutable cohort, proves it, publishes those exact bytes, and
retires the sealed candidate only after publication succeeds. There is no release PR,
normal-path soak, or second approval step.

A successful release uses one version, source commit, and set of artifact digests.
The currently claimed registry tier publishes the three PyPI distributions and the
GitHub release cohort. Scoop and Homebrew publication remain conditional until the
channel descriptor claims them and their prerequisites are met.

## Release path

| Stage | Authority | Result |
| --- | --- | --- |
| Start | `release-orchestrator.yml` | Computes the version and, for a real release, commits and pushes all version surfaces and `vX.Y.Z` |
| Build | `packaging-smoke.yml` | Builds and retains the immutable release cohort once |
| Prove | Packaging and acquisition lanes | Produces the evidence derived from the channels this release claims |
| Seal | Release orchestrator | Stores the cohort identity in a draft candidate |
| Publish | `publish-release.yml` | Revalidates the cohort, writes reversible destinations first, and uploads to PyPI last without rebuilding |
| Close | Release orchestrator | Waits for successful publication, then moves the candidate out of the selectable namespace |

The workflow run and its logs are the authoritative operational record. A
`release-alert` issue is a notification, not a substitute for the run result.

## One-time setup

Before a first real publication, issue
[#612](https://github.com/nevenincs/cadrumo/issues/612) must record the three exact
PyPI Trusted Publisher bindings. Each binding uses owner `nevenincs`, repository
`cadrumo`, workflow `publish-release.yml`, and environment `release`, for:

- `cadrumo`
- `cadrumo-data-manuals`
- `cadrumo-data-official`

Remove any obsolete publisher registration for `pypi-upload.yml`. The `release`
environment is the OIDC trust anchor; the workflow does not require environment
reviewers.

Confirm the repository configuration used by the destinations that are enabled:

- variable `HOMEBREW_TAP_REPO` and secret `HOMEBREW_TAP_TOKEN`
- the `release-alert` repository label, or the configured webhook fallback

## Per-release preflight

Confirm the self-hosted runner fleet is online for every requested shape: Linux/X64,
Linux/ARM64, macOS/ARM64, and Windows/X64. Scoop additionally requires a dedicated
non-administrator runner carrying the `windows-scoop` label. Do not dispatch while a
required runner shape is unavailable.

Use a clean `main` checkout with Python 3.13, `uv`, `just`, Git, and an authenticated
GitHub CLI:

```console
python --version
uv --version
just --version
git --version
gh auth status
git status --short
uv run --no-sync python -m dev.release.environment_inventory
just release-readiness
```

Stop if the checkout is dirty, the repository identity is not
`nevenincs/cadrumo`, a required external binding is unverified, a required runner is
offline, or a `priority:P0-blocker` issue is open. `docs/_release_checklist.yaml` is
machine-validated release policy; it is not proof that external account settings are
correct.

## Start with a rehearsal

Run the complete non-publishing path first. It uses `packaging-quick.yml`, so its child
run is deliberately different from a real release's `packaging-smoke.yml` run:

```console
gh workflow run release-orchestrator.yml --repo nevenincs/cadrumo --ref main -f dry_run=true
gh run list --repo nevenincs/cadrumo --workflow release-orchestrator.yml --limit 5
```

A rehearsal computes the candidate version, exercises packaging and evidence
selection, and seals a dry-run candidate under `release-candidate-<run-id>`. It does
not push a version commit or tag and
does not dispatch the publication authority.

Inspect the selected run:

```console
gh run view <RUN_ID> --repo nevenincs/cadrumo
gh run view <RUN_ID> --repo nevenincs/cadrumo --log-failed
```

Resolve every refusal before continuing. Do not turn a missing prerequisite into a
skip.

## Publish

Start a real release from `main`:

```console
gh workflow run release-orchestrator.yml --repo nevenincs/cadrumo --ref main -f dry_run=false
```

Monitor the orchestrator and the child run IDs it resolves:

```console
gh run list --repo nevenincs/cadrumo --workflow release-orchestrator.yml --limit 5
gh run view <RUN_ID> --repo nevenincs/cadrumo
gh run view <RUN_ID> --repo nevenincs/cadrumo --log-failed
```

The orchestrator performs these steps in order:

1. Computes the next version from conventional commits, updates all seven version
   surfaces, commits `chore(release): vX.Y.Z`, creates the annotated tag, and pushes
   the commit and tag directly to `main`.
2. Dispatches `packaging-smoke.yml` at that exact commit and resolves the run by
   immutable identity.
3. Builds the cohort once and gathers the evidence required by the claimed channels.
   The packaging run ID is always required. Other evidence run IDs are required only
   for claimed channels; missing, mismatched, or failed evidence is refused.
4. Seals a typed draft candidate containing the source commit, version, cohort run ID,
   evidence run IDs, channel set, and artifact identity.
5. Dispatches `publish-release.yml` at the campaign commit and waits for that exact run
   to finish successfully.
6. Revalidates all identities and digests, then writes GitHub Release assets, Scoop,
   and Homebrew state before the irreversible PyPI uploads.
7. Replaces `release-candidate-<run-id>` with
   `release-candidate-consumed-<run-id>` only after publication succeeds.

The publication workflow never rebuilds. PyPI upload uses Trusted Publishing and a
check-before-upload operation, allowing a retry with the same cohort to converge after
a partial upload.

## Verify the published cohort

First confirm the resolved publication run succeeded and inspect the final release:

```console
gh run view <PUBLICATION_RUN_ID> --repo nevenincs/cadrumo
gh release view v<VERSION> --repo nevenincs/cadrumo --json isDraft,targetCommitish,tagName,assets
```

Require `isDraft: false`, the expected tag and source commit, and the complete cohort
asset inventory before reacquisition.

Download the retained cohort from the packaging run recorded by the orchestrator:

```console
gh run download <PACKAGING_RUN_ID> --repo nevenincs/cadrumo --name cadrumo-release-cohort --dir var/post-release/v<VERSION>/download
```

Create a new cohort directory and extract the archive. Stop if the directory already
exists; mixing files from another attempt invalidates the check.

```powershell
$cohort = "var/post-release/v<VERSION>/cohort"
if (Test-Path -LiteralPath $cohort) { throw "$cohort already exists" }
New-Item -ItemType Directory -Path $cohort | Out-Null
tar -xzf var/post-release/v<VERSION>/download/cadrumo-release-cohort.tar.gz -C $cohort
```

Run only the reacquisition commands for destinations the channel descriptor claims:

```console
uv run --no-sync python -m dev.packaging.acquire_github_release --cohort-dir var/post-release/v<VERSION>/cohort --evidence-dir var/post-release/v<VERSION>/evidence/github-release --repo nevenincs/cadrumo
uv run --no-sync python -m dev.packaging.acquire_pypi --cohort-dir var/post-release/v<VERSION>/cohort/python --evidence-dir var/post-release/v<VERSION>/evidence/pypi
uv run --no-sync python -m dev.packaging.acquire_homebrew --cohort-dir var/post-release/v<VERSION>/cohort/python --evidence-dir var/post-release/v<VERSION>/evidence/homebrew --tap <OWNER/TAP>
```

On the dedicated Windows Scoop runner:

```powershell
$bucketSource = "OWNER/BUCKET"
& ./dev/packaging/acquire_scoop.ps1 -CohortDir var/post-release/v<VERSION>/cohort/python -BucketSource $bucketSource -EvidenceDir var/post-release/v<VERSION>/evidence/scoop
```

Every applicable command must exit zero. Fail closed unless every retained evidence
JSON file reports `status: passed`:

```console
uv run --no-sync python -c "import json,pathlib,sys; p=pathlib.Path(sys.argv[1]); rows=list(p.rglob('*.json')); assert rows and all(json.loads(x.read_text(encoding='utf-8')).get('status') == 'passed' for x in rows)" var/post-release/v<VERSION>/evidence
```

These local records are verification evidence; the current tooling
does not upload them into a durable release-close ledger, so retain them with the
operator record.

## Diagnose and recover

Start from the failed orchestrator or publication run:

```console
gh run view <RUN_ID> --repo nevenincs/cadrumo
gh run view <RUN_ID> --repo nevenincs/cadrumo --log-failed
```

Classify the failure before acting:

- Before a successful packaging run: fix the cause and start a new orchestrator run.
- After packaging succeeds but before publication: reuse the proven cohort; do not
  rebuild or restamp it.
- During a partial PyPI upload: reuse the same cohort and version. The upload checks
  existing files and publishes only the missing members.
- After any PyPI file is public: the version is burned. Never overwrite or reuse it.

Only a successful `packaging-smoke.yml` run is resumable. Resume it through the sole
entry point:

```console
gh workflow run release-orchestrator.yml --repo nevenincs/cadrumo --ref main -f dry_run=false -f resume_packaging_run_id=<PACKAGING_RUN_ID>
```

The resume path neither bumps the version nor rebuilds. It verifies the run identity
and selects the same sealed bytes. A failed,
cancelled, or timed-out publication leaves its candidate selectable; only a successful
publication consumes it.

There is no automatic compensation for destinations written before a failure. Inspect
each destination and record its state before retrying. If a published defect requires
withdrawal, run:

```console
just release-rollback X.Y.Z
```

This command prints a checklist only. Review and perform the required yanks, pointer
retractions, source revert, rollback tag, and incident updates manually. Preserve the
public tag and artifacts, never rewrite release history, and ship the correction under
a new patch version. Follow `SECURITY.md` for vulnerabilities or sensitive data.

## Close the release

A release is closed when:

- the orchestrator and its resolved publication run succeeded;
- the GitHub release targets the release commit and contains the sealed cohort assets;
- all three PyPI projects serve the same version and expected files;
- every claimed destination passed reacquisition against the cohort digests;
- the selectable candidate is gone and its consumed audit tag remains;
- release notes and the operator record contain the run IDs, version, source commit,
  cohort digests, and any recovery actions;
- no unresolved `release-alert` issue remains for the campaign.

## Authorities

- `.github/workflows/release-orchestrator.yml` — sole normal release entry point
- `.github/workflows/publish-release.yml` — sole publication authority
- `.github/workflows/packaging-smoke.yml` — immutable cohort producer
- `docs/_release_checklist.yaml` — machine release policy
- `docs/_release_notes_template.md` — release-note template
- `SECURITY.md` — private security reporting
