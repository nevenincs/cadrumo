---
tags:
  - '#reference'
  - '#registry-authoring-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:8df554068288261a5656739b58521ed501e18bb589beb0fa73e3e3f0f80a20ce'
related: []
---

# `registry-authoring-boundary` reference: `completion boundary inventory`

## Summary

The runtime boundary is the immutable `bundled_authority()` and its typed
snapshots. A product command may query a snapshot, calculate from it, or retain
its provenance. It must not accept a registry directory, source directory, or
other unvalidated tree coordinate.

The existing `dev.registry.conformance` package is the development home for
corpus quality, conformance, release closure, and mutable-tree analysis. The
empty production `app registry` command module was a retired facade, not a
runtime contract, and must be removed with every direct command-graph consumer.

## Findings

- `app live filed pull-sources` formerly accepted `--registry-root` and
  `--source-root`, forwarding them to `capture_source_filed_data`. That service
  read the tree with `load_registry_tree`, bypassing validation. The supported
  path is `bundled_authority().snapshot(modelo, filing_year, period).revision`.
- The command graph must not retain an empty registry command-spec module after
  registry verbs are retired. Removing its direct import proves that the
  production graph has no registry-command compatibility seam.
- The lazy-resolution exception list is a live-node allowlist. Removed registry
  manual nodes must leave it, otherwise the integrity check excuses paths that
  no longer exist.
- Documentation catalogues are generated through `python -m dev.docs.i18n`.
  Direct execution of `dev/docs/i18n.py` shadows the third-party `i18n` module;
  use the package invocation. The current generator preserves still-current
  catalogue entries, so source and catalogue changes must be reviewed together.

## Focused gates

- `aeat app registry --help` must refuse because `registry` is not a live
  production command.
- `aeat app live filed pull-sources --help` must expose only modelo, year,
  period, and output-root inputs; it must not expose either root override.
- `test_app_live_command_specs.py` asserts the exact source-pull parameter
  vector, while the real command help verifies the emitted surface.
- Future production-boundary coverage should reject public registry/source-root
  parameters and direct raw-tree loaders outside development publishing code.
