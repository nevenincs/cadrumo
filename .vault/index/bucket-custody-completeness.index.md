---
generated: true
tags:
  - '#index'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - '[[2026-06-30-bucket-custody-completeness-P01-S01]]'
  - '[[2026-06-30-bucket-custody-completeness-P01-S02]]'
  - '[[2026-06-30-bucket-custody-completeness-P01-S03]]'
  - '[[2026-06-30-bucket-custody-completeness-P02-S04]]'
  - '[[2026-06-30-bucket-custody-completeness-P02-S05]]'
  - '[[2026-06-30-bucket-custody-completeness-P02-S06]]'
  - '[[2026-06-30-bucket-custody-completeness-adr]]'
  - '[[2026-06-30-bucket-custody-completeness-audit]]'
  - '[[2026-06-30-bucket-custody-completeness-plan]]'
  - '[[2026-06-30-bucket-custody-completeness-research]]'
---

# `bucket-custody-completeness` feature index

Auto-generated index of all documents tagged with `#bucket-custody-completeness`.

## Documents

### adr

- `2026-06-30-bucket-custody-completeness-adr` - `bucket-custody-completeness` adr: `full per-bucket export/import custody` | (**status:** `accepted`)

### audit

- `2026-06-30-bucket-custody-completeness-audit` - `bucket-custody-completeness` audit: `P01 registry custody disposition review`

### exec

- `2026-06-30-bucket-custody-completeness-P01-S01` - Add StorageCustodyDisposition enum and a required custody_disposition field to SecureObjectNamespaceDefinition
- `2026-06-30-bucket-custody-completeness-P01-S02` - Declare custody_disposition on every namespace definition in the registry
- `2026-06-30-bucket-custody-completeness-P01-S03` - Add a registry projection helper returning the carry-set namespaces per custody profile
- `2026-06-30-bucket-custody-completeness-P02-S04` - Add typed CarriedSecureObject and CoverageManifest models
- `2026-06-30-bucket-custody-completeness-P02-S05` - Bump bundle_schema_version to 3 and add carried_objects and coverage_manifest fields to UserProfilePortableExport
- `2026-06-30-bucket-custody-completeness-P02-S06` - Bump _ARCHIVE_SCHEMA_VERSION to 2 and narrow SUPPORTED_BUNDLE_SCHEMA_VERSIONS to the single current version, deleting old-shape tolerance

### plan

- `2026-06-30-bucket-custody-completeness-plan` - `bucket-custody-completeness` plan

### research

- `2026-06-30-bucket-custody-completeness-research` - `bucket-custody-completeness` research: `per-bucket data-custody completeness`
