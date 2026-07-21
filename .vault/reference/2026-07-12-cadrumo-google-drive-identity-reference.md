---
tags:
  - '#reference'
  - '#cadrumo-google-drive-identity'
date: '2026-07-12'
modified: '2026-07-12'
related: []
---

# `cadrumo-google-drive-identity` reference: Drive ownership cutover

## Summary

The accepted Cadrumo product-rename decision makes the Google Drive vault a
product-owned persistence boundary. The rename plan's S03 classification calls
out one Drive vault folder; it must move with the hard cut. The authoritative
runtime identity keeps `aeat` exclusively as the human CLI and keeps AEAT
terminology for external-authority concepts, not product storage.

The pre-cut Drive provider, Sheets apply/pull adapters, and localized operator
messages all shared the former folder name and ownership/metadata prefix. These
are one contract: the provider owns the ciphertext mirror and the Sheets
adapters use the same Drive folder and ownership proof before a workbook can be
read. Updating only one element would either adopt former product state or
produce workbooks the pull gate cannot recognize.

The cutover therefore uses `cadrumo-vault`,
`cadrumo_vault_app=cadrumo`, and `cadrumo_*` Sheets developer metadata,
including relation provenance. The setting and direct provider constructor both
refuse the former folder name, so a previous folder or workbook is not silently
adopted, migrated, or read through a compatibility path. Operators export a new
workbook under the Cadrumo-owned folder before pulling edits.

AEAT retains its authority meaning in values such as `aeat_live` provenance and
in official-source, legal, authentication, and portal vocabulary. It is not a
prefix for Cadrumo-owned Drive persistence.
