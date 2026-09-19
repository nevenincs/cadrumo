---
tags:
  - '#research'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:e83eb8ed469e1fde6f93964ef18bb4957d4ce4a3a470fba20fdc839d01e742e6'
related:
  - "[[2026-08-14-registry-temporal-coverage-research]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
---

# `sociedades-manual-coverage` research: `temporal coverage`

The registry-wide supported filing-year declaration admits 2022 through 2026, whereas the bundled Sociedades manual family contains only 2024 and 2025. The evidence distinguishes two published manual gaps (2022 and 2023), an unpublished current-year gap (2026), and a separate Modelo 200 revision-authority gap. The latter cannot be repaired by adding manuals alone.

## Findings

### The canonical product horizon requires annual manual coverage through 2026

`registry/aeat/legal/supported-filing-years.toml:4-5` declares 2022, 2023, 2024, 2025, and 2026. `corpus/manuals/sociedades/` has only 2024 and 2025. The extraction freshness gate already identifies the master declaration as the sole authority and records the prior Sociedades-only 2024--2025 window as drift: `dev/corpus/tests/test_extraction_sidecar_freshness.py:52-60`.

### 2022 and 2023 are acquirable; 2026 is explicitly not yet published

AEAT's current archive lists Sociedades manuals for 2014--2025, including 2022 and 2023, but no 2026 manual. The exact official PDFs are https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/Sociedades/Manual_sociedades_2022.pdf and https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/Sociedades/Manual_Sociedades_2023.pdf. The archive is https://sede.agenciatributaria.gob.es/Sede/manuales-practicos.html. Treating 2025 as 2026 would falsely assert annual authority.

### Manual availability and Modelo 200 authority are distinct claims

The accepted temporal-coverage ADR requires a source-grounded revision for the exact filing context. Modelo 200 declares only `2024` and `2025-y-siguientes` revisions, so adding 2022 and 2023 manuals enables manual inspection and provenance, but cannot claim calculation or filing support for those years: `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/revision.toml:24-27`; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/revision.toml:25-28`; `2026-08-14-registry-temporal-coverage-adr`.

### The current open Modelo 200 epoch outlives its annual manual evidence

The `2025-y-siguientes` revision has no upper bound, while its annual manual source applies only through 2025-12-31: `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/revision.toml:25-28`; `src/cadrumo/_data/registry/aeat/legal/is.toml:1538-1549`. Both revision families also pool 2024 and 2025 manual references in dispositions, defeating exact-year provenance. A repair must prevent an annual manual from grounding a filing year outside its applicability interval.

### Discovery is present-only and therefore hides the deficit

`list_registry_manuals` scans directories under the configured manuals root rather than comparing discovered parts with the canonical horizon: `src/cadrumo/application/registry/corpus.py:1091-1120`. The live command consequently reports only 2024 and 2025 without a missing-year condition. A coverage contract/gate must make absent published years visible and distinguish the documented 2026 publication absence.

### Options for the ADR

- Keep discovery-only behaviour. Rejected by the master-year declaration and the no-silent-under-declaration rule: it turns an absent annual authority into an empty list.
- Backfill 2022--2023 and silently treat 2026 as unavailable. Rejected because a declared product year still has no visible evidence disposition.
- Define a manual-coverage contract keyed to the supported filing-year catalogue, with exact annual sources where published and an evidence-carrying unpublished disposition where AEAT has not published one. This best preserves the separation between corpus availability and Modelo authority while making every year auditable.

## Sources

- `src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml:4-5`
- `dev/corpus/tests/test_extraction_sidecar_freshness.py:52-60`
- `src/cadrumo/application/registry/corpus.py:1091-1120`
- `src/cadrumo/_data/registry/aeat/legal/is.toml:1525-1549`
- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/revision.toml:24-27`
- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/revision.toml:25-28`
- `2026-08-14-registry-temporal-coverage-adr`
- https://sede.agenciatributaria.gob.es/Sede/manuales-practicos.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/Sociedades/Manual_sociedades_2022.pdf
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/Sociedades/Manual_Sociedades_2023.pdf
