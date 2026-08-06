---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:089e073ccae27f4e14ff520c55b312f1889985c226f7a492673c580818a6e204'
step_id: 'S32'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

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
