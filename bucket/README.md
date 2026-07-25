# Scoop bucket

This directory makes the repository its own Scoop bucket. Scoop resolves app
manifests from a `bucket/` subdirectory when one is present, so no separate
bucket repository exists or needs to be created.

Once a release has been published, install with:

    scoop bucket add cadrumo https://github.com/nevenincs/cadrumo
    scoop install cadrumo

`cadrumo.json` is generated from the immutable release cohort and pushed here by
the publish workflow at release time — it is never hand-authored, and it is
absent until the first publication. Do not commit a placeholder manifest: a
manifest names a version and pins a SHA-256, so a placeholder is a claim that a
user could act on and fail against.

Every product published under this account repeats this same layout in its own
repository. That is what keeps the count of distribution repositories at zero
per product.
