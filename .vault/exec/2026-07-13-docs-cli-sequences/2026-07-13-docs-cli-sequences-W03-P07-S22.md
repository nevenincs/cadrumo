---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:89145b6817c1e27486812adf8fce535384b90e44d274325906fef6fefefa33a7'
step_id: 'S22'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Implement the Python tokeniser against the materialised Click tree, classifying executable, verb path, option, option value, positional value, and interpolated placeholder tokens with a command-path key on each verb token

## Scope

- `dev/docs/sequences/_tokeniser.py`

## Description

- Add `_tokeniser.py` to the sequence engine: a build-time classifier that tokenises a frame's argv against the materialised Click tree.
- Materialise the tree once, cached, reusing the CLI-reference substrate (force lazy subtrees, name the root, walk to a node index) so the token grammar binds to the same tree the help projection is built from.
- Duck-type option params on the Click param kind rather than `isinstance`: Typer vendors its own Click fork, so a `TyperOption` is not the installed `click.Option`, and an isinstance check silently classifies every value option as a flag.
- Classify each token as executable, group verb, leaf verb, option, option value, positional argument, or interpolated `{name}` placeholder; carry the space-joined command-path key on the executable, every verb token, and each option token.
- Consume a value-taking option's following token as its option value, unless that token is itself a `{name}` placeholder; degrade an unresolved bare token to a positional argument so an unknown verb never raises.

## Outcome

- The tokeniser classifies real command lines correctly against the live tree (verified with `app modelo work create/calculate/verify`, `app ledger import --file`, inline `--format=json`, and threaded `{name}` placeholders).
- The command-path key is the space-joined path including the leading `aeat` token, byte-identical to the `cli-tree.json` projection keys the frontend widget resolves against, so hover-help is reconciled with the projection with no adapter.
- Ruff and ty are clean.

## Notes

- Materialising the tree needs an isolated storage root and English output pinned (the reference-generator environment); a bare interpreter with a stale retired-product database in the default storage root raises before the walk. The docs build already sandboxes storage, so the directive path is unaffected.
- Review LOW (informational, no code change): the `_is_option_token` helper classifies any token starting with a hyphen (length > 1) as an option, so a bare negative-number positional such as `-5` would be misclassified as an option token. This is latent and cosmetic — no current CLI leaf takes a bare negative-number positional, and a `{name}` placeholder or `--opt=value` is unaffected — so it is recorded rather than fixed; revisit if a leaf ever documents a negative-number positional.
