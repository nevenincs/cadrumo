---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:9e5f8ae4fb9e143602f6e2ba23c3087fbff1ea6a3b023d193d0973746836f0d3'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename` `W03.P06` summary

Phase W03.P06 moved and renamed both independently published corpus companion
projects and cut runtime discovery to the shared Cadrumo PEP 420 namespace.

- Moved: `packaging/aeat_data_manuals` to `packaging/cadrumo_data_manuals`
- Moved: `packaging/aeat_data_official` to `packaging/cadrumo_data_official`
- Modified: companion project metadata, URLs, README guidance, and Hatch hooks
- Modified: runtime companion discovery and real resource tests
- Renamed/repaired: `dev/packaging/tests/test_cadrumo_data_distribution.py`
- Created: S28 through S35 Step Records
- Modified: plan and rolling formal audit

## Description

The companions publish as `cadrumo-data-manuals` and
`cadrumo-data-official`, share version 0.1.1 with the root project, and point
to the Cadrumo repository. Their hooks contribute disjoint portions under
`cadrumo_data/_data/corpus`: manuals owns the manuals partition, while official
owns the `aeat_official` and normatives authority partitions.

Runtime discovery imports only `cadrumo_data` and has no `aeat_data` alias,
fallback, or initializer. Real wheels prove exact tracked ownership, disjoint
and exhaustive union, size caps, version parity, absence of former namespace
members, and byte-exact access to both portions through the production resolver.

Several move/metadata/hook Steps were materially overtaken by combined commit
`f99ee0c821`. Their records identify that provenance and separately verify the
current outcome rather than reverting or duplicating the committed changes.
Follow-up commits corrected repository URLs and repaired the stale packaging
gate. Ignored Hatch bytecode caches were removed and are not wheel members.

The independent phase review reran 12 companion wheel/runtime tests and found no
HIGH or CRITICAL issues. Focused Ruff, formatting, TOML, residue, diff, and plan
checks pass.
