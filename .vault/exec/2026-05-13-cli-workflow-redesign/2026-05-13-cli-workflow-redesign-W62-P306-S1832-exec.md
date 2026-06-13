---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W62.P306.S1832'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
---

# `cli-workflow-redesign` `W62.P306.S1832`

Implemented strict application registry corpus contracts for the topic-backed citation and manual registry surfaces.

## Description

The registry application layer now owns typed Pydantic command and report models for:

- `registry.citations.list`
- `registry.citations.show`
- `registry.citations.verify`
- `registry.manuals.list`
- `registry.manuals.show`
- `registry.manuals.rules`
- `registry.manuals.verify`

The citation reports consume the central topic catalogue and return resolved topic projections alongside normative reference and article projections. The manual reports consume the topic catalogue and expose typed manual part, section, rule, and verification projections.

The manual application contract is narrowed to the approved registry corpus vocabulary through `RegistryManualId`, which contains only `renta` and `iva`. The application layer converts that registry-specific id into the domain `ManualId` internally before calling the manuals backend. `sociedades` remains a domain enum member, but it is not accepted by the registry manual operator contract.

The Renta manual corpus was normalized to the canonical `ManualPart` directory values used by the existing domain loader. The committed corpus now uses `part1` and `part2-deducciones-autonomicas` filesystem roots, and the registry legal source paths point to those canonical roots. The application discovery path no longer carries legacy `parte*` alias mapping.

Manifest-backed manual rows now have complete application behavior even when extracted structure has not been materialized. `show_registry_manual()` returns manifest metadata with `structure_available=False`, and `list_registry_manual_rules()` returns an extracted-rule report with `structure_available=False` and zero rules. Requests for a specific section still require extracted structure and raise `RegistryApplicationInputError` when only a manifest is present.

The canonical Renta PDF paths are enrolled in `.gitignore` as explicit unignored evidence files. The old `parte*` source PDF paths are recorded as renames to the canonical `part*` paths, so the registry legal source catalogue does not point at absent files after checkout.

The CLI layer was not rewritten in this step. The next step applies these backend contracts to the mounted Typer handlers so command rendering stays thin and does not embed topic prose or payload shaping.

## Tests

Passed:

- `uv run --no-sync ruff check src/aeat/application/registry src/aeat/domain/manuals`
- `uv run --no-sync ty check src/aeat/application/registry src/aeat/domain/manuals`
- `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py -q`
- `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/domain/manuals/test_loader.py -q`
- `uv run --no-sync pytest src/aeat/domain/manuals/test_fetch.py src/aeat/domain/manuals/test_loader.py src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py -q`
- `uv run --no-sync pytest src/aeat/domain/manuals/test_fetch.py src/aeat/domain/manuals/test_loader.py src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_backend_boundary.py -q`

The final focused and broad slices passed with 9 and 50 tests respectively. `git ls-files -o --exclude-standard "corpus/manuals/renta/**/source.pdf"` returned no untracked canonical Renta PDFs after enrollment.
