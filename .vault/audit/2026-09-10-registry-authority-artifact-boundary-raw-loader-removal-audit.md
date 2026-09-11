---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:3bf118dbd56892f1e4bf186f068505228b032fcba059c1c81e9b8df26a77c2fe'
related: []
---

# `registry-authority-artifact-boundary` audit: `raw loader removal`

## Scope

The W02.P03.S04 deletion of the production raw loader and relocation of development compilation were audited before the runtime split is closed.

## Findings

### raw-loader-removal | high | IVA catalogue still imports the deleted raw loader

The IVA grounding path imports `load_shared_catalogues` from the removed production loader. Its direct runtime entry now raises `ModuleNotFoundError`; it must consume catalogues from the artifact authority rather than restore a compatibility loader.

### raw-loader-removal | high | Development compiler remains implemented by production modules

The new development compiler facade still imports source-authoring modules from `src`, and a production fact module imports the dev compiler. The compiler, validation, source-evidence, cache, and fact-provider family must be development-owned before package exclusion can be real.

### raw-loader-removal | high | Runtime corpus assets need an explicit artifact boundary

Artifact authority still resolves source-backed citation and inspection from package data. W03 must serialize required runtime material or separately package immutable runtime assets, without shipping authoring, validation, repair, or recompilation inputs.

### raw-loader-removal | medium | Unused mutable-root lifecycle machinery remains

The artifact path no longer uses root-pair cache-transition machinery in `authority.py`; remove it after development compiler ownership is complete.

## Recommendations

- Migrate IVA catalogue lookup to artifact authority immediately and prove its consumer path.
- Relocate the complete authoring compiler family and update development callers in W03.
- Define immutable runtime citation/inspection assets and exercise them from an isolated installed package.
