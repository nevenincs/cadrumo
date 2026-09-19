---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:a34c5fdb8e971498d0b005518802e5e8afbec5dee0b50d07dcdd284f8db5f6b8'
step_id: 'S36'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Delete the three orphaned Rung-2 build-time modules

## Scope

- `dev/docs/terminology/_jcs.py`
- `dev/docs/terminology/jcs_vectors/`
- `dev/docs/terminology/_content_manifest.py`
- `dev/docs/terminology/__init__.py`
- `pyproject.toml`

## Description

- Confirm the remedy is unconditional: the operator ruled the Rung-2 deletion intended, so the recovery branch that would have restored the browser validator is closed and the deferred remedy fires.
- Confirm no surviving consumer. The only importers of the canonical-JSON module were the vector corpus inside the same orphan set and the package facade; the raw-byte content manifest had the facade alone. Every real consumer in the tree already imports the core hashing home.
- Delete the canonical-JSON module, the vector corpus directory including its Python and Node verifiers, and the raw-byte content manifest.
- Strip the nine orphaned re-exports from the package facade and its `__all__`.
- Remove the ruff per-file ignore for the static-matrix contract test, which was deleted with the Rung-2 tier and left a rule exemption naming a file that no longer exists.

## Outcome

The three modules are gone and the facade no longer advertises a second byte-contract authority beside the one in core. The finding was that these modules did not merely lack consumers but redeclared capabilities whose canonical homes are in core: the canonical-JSON module reimplemented a byte contract core hashing already owns while importing nothing from it, and the raw-byte manifest reimplemented the relative-path plus byte-length plus digest shape the core corpus manifest owns. The divergence had been justified while a browser validator needed stricter cross-runtime bytes than the core serializer emits; that consumer was deleted, so the justification lost its subject.

The facade imports and collects clean, ruff passes across the package, and no reference to the removed symbols survives outside the vault record of the finding.

## Verification

The package facade imports and exposes 86 symbols. Ruff reports all checks passed across the package. Test collection over the package test directory is clean. A tree-wide search for the removed symbol names returns only core-hashing call sites, which is the intended single authority.

## Notes

The fourth residue finding, the query/alias authority, is not part of this deletion: its premise is falsified at HEAD and it is handled as a re-homing under its own row.

One historical mention of the deleted runtime embedding stack survives in the type-checker configuration as a reviewed note on a deliberately empty suppression set. It documents why the set is empty rather than suppressing anything, so it is left standing.
