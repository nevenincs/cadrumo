# Scoop bucket

**This directory is not the bucket.** Cadrumo's Scoop manifest is published into the
shared account distribution repository, `nevenincs/homebrew-tap`, alongside its
Homebrew formula. Nothing is committed here, and `cadrumo.json` never appears here.

```powershell
scoop bucket add nevenincs https://github.com/nevenincs/homebrew-tap
scoop install nevenincs/cadrumo
```

```sh
brew tap nevenincs/tap
brew install nevenincs/tap/cadrumo
```

## Why one shared repository, not one per product

Homebrew requires a tap repository to be named `homebrew-<name>` for the one-argument
`brew tap nevenincs/tap` form to resolve. That repository therefore has to exist no
matter what. Scoop imposes no name constraint and resolves manifests from a `bucket/`
subdirectory, so the same repository carries the Scoop side at no extra cost.

The result is that the account's distribution-repository count is **one at one product
and one at a hundred**: a new product adds one formula file and one manifest file and
creates nothing. The publish workflow's push steps are safe to share because each
stages only its own product-scoped path, refuses a backward version bump, and retries a
lost push race — three properties pinned by 41 conformance assertions in
`dev/release/tests/test_publish_release_workflow.py`.

## What this file used to say, and why that mattered

This README previously stated that "this directory makes the repository its own Scoop
bucket" and that "no separate bucket repository exists or needs to be created". Both
were false. `nevenincs/homebrew-tap` exists, it is where `publish-release.yml` pushes,
and the workflow refuses to publish at all when `HOMEBREW_TAP_REPO` and
`HOMEBREW_TAP_TOKEN` are unset.

The claim was not harmless. It described the opposite architecture from the one the
code implements, in the one file a maintainer reads first when asking where the
manifest goes — and it sat directly above a correct, carefully argued rationale for the
shared repository in `publish-release.yml`. A reader trusting this file would have gone
looking for an in-repo manifest that is never written.

## Note for the vaultspec products

vaultspec-core and vaultspec-rag currently ship their channels **in-repo**, each
repository acting as its own bucket and tap. That works, but it costs the
one-argument tap form: because those repositories are not named `homebrew-*`, they
require `brew tap nevenincs/vaultspec-core https://github.com/nevenincs/vaultspec-core`
rather than `brew tap nevenincs/tap`.

The two models are both defensible and the choice between them is open. It is recorded
here so the difference is a decision rather than a drift.
