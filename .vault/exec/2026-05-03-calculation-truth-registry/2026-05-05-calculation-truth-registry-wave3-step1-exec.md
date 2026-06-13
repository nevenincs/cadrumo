---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `Wave 3` `Modelo 115 registry foundation`

Established Modelo 115 as a registry-backed current-revision modelo.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_remote_state_guard.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `corpus/normatives/rd-439-2007.json`
- Modified: `registry/aeat/legal/irpf.toml`
- Created: `registry/aeat/modelos/115.toml`
- Modified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_remote_state_guard.py`
- Modified: `src/aeat/application/filing/test_export.py`
- Modified: `src/aeat/domain/deadlines/test_engine.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Wave 3 moved Modelo 115 from discovery into the centralized registry. The
current official AEAT record design is a five-casilla 2019-and-later shape:
recipient count, withholding base, withholding amount, prior declarations, and
payable amount. Older internal six-casilla notes were not used as registry
authority.

The registry now carries the Modelo 115 identity, current revision, legal
references, source references, five casillas, 19 percent rental withholding
parameter, computed casillas 03 and 05, record-design export layout, extraction
profiles, static official cross-reference guard, workbook layout evidence,
verification expectation, application links, and 2026 quarterly deadline
windows.

The shared IRPF legal/source catalogue now includes `rd-439-2007:art-100`, the
official AEAT 2019-and-later Modelo 115 record-design workbook, and the captured
AEAT Modelo 115 guidance pages. The RD 439/2007 corpus includes article 100
text sufficient for required-text validation.

The deadline schema now accepts `pays_rent_with_retencion`, matching the
existing `AutonomoProfile` field. Modelo 115 applicability is therefore carried
by the registry deadline windows rather than by Python-side modelo branching.

Registry cross-reference decisions can now be converted into executable
remote-state guard policies. The committed static official cross-reference
policies allow local workbook work and block live HTTP/browser state-changing
operations through the guard.

The authority scan found no active non-test Modelo 115 calculation authority in
rulesets, category mappings, generated export code, hydration paths, or casilla
projection code outside the new registry. Remaining hits are official corpus
material, portal metadata, registry behaviour tests, storage temp-file lint
comments unrelated to Modelo 115, and Modelo 100 official corpus casilla numbers
that happen to contain `115`.

Live filed-data discovery now completed after a fresh Clave Movil session. The
read-only declaration register scan for Modelo 115 covering 2020 through 2026
returned zero rows. A committed sanitized live fixture and filed-data parity
tests remain open because no live Modelo 115 artefact exists in the scanned
account and period range.

## Tests

- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_registry_schema.py src\aeat\domain\deadlines\test_engine.py -q`
- `uv run pytest src\aeat\domain\calculations\registry\test_workbook_parity.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py -q`
- `uv run pytest src\aeat\application\filing\test_export.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py -q`
- `uv run pytest src\aeat\domain\calculations\registry\test_remote_state_guard.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\application\filing\test_export.py src\aeat\domain\deadlines\test_engine.py -q`
- `uv run ruff check src\aeat\application\filing\test_export.py src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py`
- `uv run ty check src\aeat\application\filing\test_export.py src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py`
- `uv run ruff check src\aeat\domain\calculations\registry\_remote_state_guard.py src\aeat\domain\calculations\registry\__init__.py src\aeat\domain\calculations\registry\test_remote_state_guard.py src\aeat\application\filing\test_export.py src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py`
- `uv run ty check src\aeat\domain\calculations\registry\_remote_state_guard.py src\aeat\domain\calculations\registry\__init__.py src\aeat\domain\calculations\registry\test_remote_state_guard.py src\aeat\application\filing\test_export.py src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py`
- `uv run aeat app registry list-filed-data --modelo 115 --from-year 2020 --to-year 2026 --json` returned zero rows after Clave Movil reauthentication.
- `git diff --check -- registry\aeat\modelos\115.toml registry\aeat\legal\irpf.toml corpus\normatives\rd-439-2007.json src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py src\aeat\application\filing\test_export.py .vault\plan\2026-05-03-calculation-truth-registry-rebuild-plan.md`
