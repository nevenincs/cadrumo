---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S74'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# W09.P21.S74 constants centralization

Scope: Move remaining executable AEAT/Sede portal host and route source-of-truth literals into centralized settings/schema authorities.

## Description

- Added a typed `AeatPortalPaths` external-constants section backed by `[aeat.portal_paths]` and `[aeat.portal_paths.paths]` in `external_constants.toml`.
- Rewrote portal entry modules to call `portal_path(Portal...)` instead of embedding `/Sede/...` or `/wlpl/...` path literals.
- Changed `PortalHost` enum values from hostname literals to stable registry keys and resolved hostnames through central AEAT domain constants.
- Updated portal metadata validation and local portal CLI output to use central host and filing/censo path-shape authorities.
- Verified the Cl@ve browser-global token from the S73 inventory is already centralized under the Cl@ve external-constants surface.
- Replaced synthetic justificante generator runtime Sede origin and CSV verification URL literals with values from the external constants registry.

## Verification

- `PYTHONPATH=src .venv\Scripts\python.exe -m pytest -q src/aeat/domain/portals src/aeat/core/test_external_constants.py` passed with 128 tests.
- `PYTHONPATH=src .venv\Scripts\python.exe -m ruff check src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/domain/portals src/aeat/entrypoints/cli/_app_live.py` passed.
- `PYTHONPATH=src .venv\Scripts\python.exe -m pytest -q src/aeat/core/test_external_constants.py::test_portal_paths_registry_covers_literal_free_portal_entries src/aeat/domain/portals/test_metadata.py::test_filing_url_must_match_gcode_pattern src/aeat/domain/portals/test_metadata.py::test_valid_filing_entry_constructs src/aeat/domain/portals/test_registry.py::test_registry_is_typed_schema_authority_for_portal_route_metadata` passed.
- `PYTHONPATH=src .venv\Scripts\python.exe -m ruff check src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/domain/portals/_metadata.py src/aeat/domain/portals/test_metadata.py src/aeat/domain/portals/test_registry.py src/aeat/tests/fixtures/justificantes/_generate.py` passed.
- Non-test portal literal scan for `path="/..."` and AEAT/Cl@ve host literals returned no executable matches.
- Expanded AST inventory found remaining test-suite literals outside S74 scope; they are tracked separately under S88.

## Notes

No live AEAT request was made. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
