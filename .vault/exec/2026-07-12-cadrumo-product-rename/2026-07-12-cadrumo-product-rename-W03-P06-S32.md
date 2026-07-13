---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S32'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S32 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Rename official distribution metadata, repository URLs, and companion install guidance and ## Scope

- `packaging/cadrumo_data_official/pyproject.toml`
- `packaging/cadrumo_data_official/README.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename official distribution metadata, repository URLs, and companion install guidance

## Scope

- `packaging/cadrumo_data_official/pyproject.toml`
- `packaging/cadrumo_data_official/README.md`

## Description

- Reconcile the companion metadata cutover already delivered by `f99ee0c821`.
- Align the remaining repository URLs with the root Cadrumo metadata authority.
- Preserve official AEAT corpus descriptions and the `aeat_official` source subtree name.
- Build and inspect the real companion wheel metadata and owned archive partitions.

## Outcome

The companion declares `cadrumo-data-official` version `0.1.1`, matching the root
distribution. Its project URLs and README point to the canonical Cadrumo
repository; install guidance uses `cadrumo[corpus-sources]`; and the documented
PEP 420 namespace is `cadrumo_data`. The real wheel reports the same name/version
and canonical URLs. All 177 payload members belong beneath the official AEAT or
normative Cadrumo-data partitions, with no former product namespace members.

## Notes

`f99ee0c821` overtook the distribution-name, version, namespace, description,
and install-guidance work. This step corrected only the repository URL drift it
left behind. The `aeat_official` directory and AEAT wording remain because they
identify official authority corpus material. S33's hatch mapping was not edited.
