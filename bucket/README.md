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
creates nothing.
