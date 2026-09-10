---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:ef55630bdc51b64e6233dc6da7f32d698b50d634eef29759cbac3509ccee3c67'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace registry-authority-artifact-boundary with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
