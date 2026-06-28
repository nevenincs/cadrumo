---
tags:
  - '#reference'
  - '#user-profile-filing-export-dependencies'
date: '2026-05-07'
modified: '2026-05-07'
related: []
---



# `user-profile-filing-export-dependencies` reference: `User Profile Filing Export Dependencies`

Topic: filing, declaration, export, reconciliation, complementaria, and import
edges that consume taxpayer profile information or profile-derived export
metadata.

Audit surface: declaration CLI, filing draft identity, registry export layouts,
export renderer, review/staleness fingerprinting, reconciliation, complementaria
creation, and justificante import.

Rewrite scope: this document records profile dependencies for a clean
replacement. Existing free-form header maps and active-profile reads are not
preserved as runtime compatibility surfaces.

## Findings

### Filing identity is currently narrower than export identity

Declaration calculation requires the active profile `tax.id`, copies it into
`FilingOperatorProfile.tax_id`, and persists it as `FilingDraft.profile_tax_id`.
Draft identity includes `profile_tax_id`, so changing taxpayer identity changes
draft identity.

Declaration edit rebuilds from the old draft `profile_tax_id` and does not
recover the full active profile identity context. Complementaria and justificante
import also carry tax ID but not full declarant name, address, residence, or
export-context state.

Evidence anchors: `src/aeat/entrypoints/cli/_declaration.py:65`,
`src/aeat/application/filing/__init__.py:178`,
`src/aeat/domain/filing/_schema.py:166`,
`src/aeat/entrypoints/cli/_declaration.py:225`,
`src/aeat/application/filing/_complementaria.py:63`,
`src/aeat/application/filing/_import.py:113`.

### Export reads live active profile headers late

Declaration export converts active profile dot keys to underscore header keys,
then registry export fields of kind `header` consume those values. Export draft
attributes separately read `profile_tax_id`, `filing_year`, and `period_code`
from the draft.

This means some identity-like values are frozen into the draft, while other
export-affecting values are read from the active live profile at export time.
Approval stale detection fingerprints draft data, transactions, category
profiles, and formulas, but not export header/profile fields.

Evidence anchors: `src/aeat/entrypoints/cli/_declaration.py:407`,
`src/aeat/application/filing/_export.py:440`,
`src/aeat/application/filing/_export.py:457`,
`src/aeat/application/filing/_review.py:181`,
`src/aeat/application/filing/_review.py:521`.

### Registry export layouts require more than NIF

Profile-like export fields include `declaration.type`, `name`, `surnames`,
`legal.name`, `first.name`, `complementaria`, `previous.receipt`,
`previous.justificante`, `justificante.anterior`, `fecha.inicio.periodo`,
`fecha.fin.periodo`, `devengo.start.date`, `cnae`,
`datos.adicionales.*`, `iban`, `program.version`, `developer.nif`,
`developer.tax.id`, and `aeat.seal`.

The editable profile key registry does not cover many consumed headers, so the
supported CLI cannot discover or set all registry-required export values.

Evidence anchors: `registry/aeat/modelos/130.toml:739`,
`registry/aeat/modelos/130.toml:753`,
`registry/aeat/modelos/232.toml:447`,
`registry/aeat/modelos/200.toml:42258`,
`registry/aeat/modelos/200.toml:42272`,
`registry/aeat/modelos/111.toml:739`,
`registry/aeat/modelos/349.toml:657`,
`src/aeat/domain/profile/_keys.py:108`.

### Reconciliation currently checks only tax ID

Reconciliation compares `draft.profile_tax_id` with justificante `tax_id` and
reports `TAX_ID_MISMATCH` after strip/uppercase normalization. It does not
validate name, address, CCAA, regime, or export header identity.

Evidence anchors: `src/aeat/application/filing/reconciliation/_reconcile.py:160`.

## Requirements

Define `filing/export context` as a projection from centralized profile data,
not a separate live profile. It must cover declarant identity, display/legal
name, surnames/name split, contact/address where required, IBAN/payment facts,
complementaria metadata, previous justificante metadata, developer/export
metadata, and model-specific header keys.

Export preflight must validate every registry `header_key` against declared
profile/export-context fields before bytes are rendered.

Draft approval must persist either an immutable profile snapshot or enough
schema-versioned snapshot metadata to detect staleness before review, verify,
and export.

Model/revision preflight must assert that the draft was built from the selected
registry snapshot and from profile values effective for the filing period.

Profile-driven export validation must be model/revision aware. Generic profile
validation is insufficient because required header fields differ across modelos.

## Risks And Open Questions

Some export header keys are operator profile values, some are filing-session
values, and some are tool metadata. The schema must classify these explicitly
so secure DB live values are not confused with per-export inputs.

The ADR must choose the stale-check policy for export-affecting facts:
immutable snapshot copy, snapshot hash, or effective-dated reconstruction with
hash verification.

Existing tests and CLI paths that pass explicit headers should be rewritten to
assemble typed profile/export context through the centralized API.
