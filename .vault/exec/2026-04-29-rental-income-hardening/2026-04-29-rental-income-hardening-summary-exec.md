---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/exec/ location)
# Feature tag (replace rental-income-hardening with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#exec'
  - '#rental-income-hardening'
# ISO date format (e.g., 2026-02-06)
date: '2026-04-29'
# Related documents as quoted wiki-links - MUST link to parent PLAN
# (e.g., "[[2026-02-04-feature-plan]]")
related:
  - "[[2026-04-29-rental-income-hardening-plan]]"
  - "[[2026-04-29-rental-income-hardening-adr]]"
  - "[[2026-04-29-rental-income-hardening-research]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `rental-income-hardening` summary

Per-finca + per-contract rental register, LIRPF art. 23.2 four-tier
auto-resolver post Ley 12/2023 (BOE-A-2023-12203), and LIRPF
art. 23.1.f amortización 3 % multi-year ledger with cost-basis cap.
Closes the gap from PR #448 where every M100 Anexo C casilla was
caller-supplied — the new register derives 0061/0066/0072/0078/0085
from per-finca metadata while preserving the pre-#454 caller-
supplied path through a backwards-compat shim.

## Phase commit log

- `99b0e3c` — `docs(research,adr,plan)`: vault pipeline (research +
  ADR + plan + feature index).
- `a9a170f` — `feat(storage)`: rental register schema (5 ORM tables
  + alembic 0003 migration).
- `c4fe52c` — `feat(rental)`: public records + repositories +
  6 #398-registered errors.
- `2a2043e` — `feat(rental)`: tier auto-resolver (Ley 12/2023 BOE
  priority order with qualifying-share split).
- `2dda9d3` — `feat(rental)`: amortización 3 % ledger + LIRPF
  art. 23.1.a) expense rollup with 4-year carry-forward.
- `34b4e02` — `feat(rental)`: Anexo C aggregator + M100 backwards-
  compat shim.
- `882d7dc` — `feat(cli/rental)`: aeat rental sub-app (5 command
  groups, 12 commands, --json schemas).
- `99334a0` — `docs(concepts)`: rental-income concept doc + Kent
  capability matrix row.
- `367d4e5` — `fix(rental,cli/rental)`: defer aeat.storage imports
  for json-pipe-safety contract; register schemas in conformance
  test.

## Source files

Created: rental subpackage (`__init__`, `_enums`, `_models`,
`_errors`, `_repository`, `_tier_resolver`, `_amortization_ledger`,
`_expense_rollup`, `_anexo_c_aggregator`, `anexo_c_provider`); 5
test modules (49 unit tests + 6 CLI tests + 6 aggregator tests = 86
new tests); CLI sub-app (`__init__`, `_helpers`, `finca`, `contract`,
`income`, `expense`, `anexo_c`, `test_cli`); alembic 0003 migration;
docs/concepts/rental-income.md; vault research + ADR + plan + index.

Modified: storage `_orm.py` (5 new ORM Row classes + EncryptedString
import); `aeat.errors._registry` (6 new ErrorCode rows); CLI
`__init__.py` (sub-app registration);
`test_json_schema_conformance.py` (12 new command paths in expected
set); `kent-capabilities.md` (capability row).

## Worked examples

### Tier 90-a — landlord rebaja in zona tensionada

Contract 2024-01-01; finca in zona tensionada; prior-contract last
rent 1 000 €; new initial rent 940 € (rebaja 6 % > BOE threshold
5 %). Result: `tier=TIER_90`, `reduccion_pct=0.90`,
`qualifying_share=1`, `boe_citation_id="art_23_2_a"`.

### Tier 70-b-1 — joven inquilino, partial qualifying share

Contract 2024-06-01; finca in zona tensionada; 3 co-tenants of
which 2 qualify (ages 22 + 28); is_first_rental. Result:
`tier=TIER_70_JOVEN`, `reduccion_pct=0.70`, `qualifying_share=2/3`,
`boe_citation_id="art_23_2_b_1"`.

### Tier 60-c — rehabilitación 730-day boundary

Contract 2025-06-01; rehab finished 2023-06-02 (730 days before).
Result: `tier=TIER_60_REHAB`, `reduccion_pct=0.60`. Day 731 boundary
returns `TIER_50`.

### Amortización ledger — multi-year cap

Finca with `coste_adquisicion_construccion=10000` and
`valor_catastral_construccion=8000` (basis = 10 000); 365 días
alquilados → gross 300 €/yr. Year-N cumulative-prior=9700 →
remaining cap 300 → no clamp; year-N+1 cumulative-prior=10000 →
remaining cap 0 → year-N+1 capped_amortization clamps to 0
(`clamp_applied=True`).

### M100 Anexo C end-to-end

1 finca (coste construcción 100 000, catastral 80 000) with 1
contract (initial rent 1 000), 1 income record (12 000 gross over
365 days). No expenses. Aggregates derived from register:

- 0061 ingresos = 12 000.00
- 0066 gastos = 0.00
- 0072 amortización = 100 000 × 0.03 = 3 000.00
- rendimiento = 12 000 - 0 - 3 000 = 9 000
- tier = TIER_50 → reducción = 0.50 × 9 000 = 4 500
- 0078 = 4 500.00; 0085 = 0 (use_type is VIVIENDA_ARRENDADA)

Verified cent-exact via `aeat rental anexo-c compute --year 2025
--json` in the CLI integration test.

### Backwards-compat passthrough

Empty rental store; caller supplies the five casillas. The shim
returns `AnexoCMergeReport(register_used=False, aggregates=None,
effective_casillas=<unchanged>)`. Pre-#454 M100 audit flow
preserved.

## Tests

86 new tests, all green on Windows:

- `_test_repository.py` — 8 round-trip CRUD + invariants per
  repository.
- `_test_tier_resolver.py` — 23 tests covering every BOE trigger
  condition, every priority-order edge, every effective-date
  branch, LAU 17.6 forfeit, qualifying-share split, 730 vs 731-day
  rehab boundary, exactly-5 % rebaja.
- `_test_amortization_ledger.py` — 9 tests: single-year, multi-
  year, cap-mid-year clamping, strict-mode overflow.
- `_test_expense_rollup.py` — 9 tests: per-category, art. 23.1.a)
  cap, carry-forward consumption, 4-year expiration.
- `_test_anexo_c_aggregator.py` — 8 tests including art. 85
  imputación 1,1 % vs 2 % rate selection.
- `cli/rental/test_cli.py` — 6 tests: registration, JSON envelope,
  error path, full pipeline cent-exact.

Pre-existing tests preserved:

- 7 M100 Anexo C tests in `test_anexo_c_2025.py` still pass
  unchanged (backwards-compat shim verified).
- `test_json_pipe_safety.py` (7 cases) and
  `test_json_schema_conformance.py` (16 cases) pass after the
  deferred-storage-import fix and the schema-conformance update.

## Honest limitations

- Per-CCAA stressed-area auto-detection deferred (post-#452).
- Partial-year imputación pro-rate deferred (current scope is
  full-year non-let only).
- Multi-tenant mid-year tier transitions deferred (BOE anchors
  evaluation to contract celebration date).
- Schema-version forward-compat field is wired but not exercised
  against mismatched data.
- The CLI surface is exercised through Typer's `CliRunner`; no
  visual smoke test in a real terminal.

## Pre-existing test failures on the branch (NOT introduced by #454)

Inherited from the merged `feature/216-bank-import-persistence`
(WIP, deliberately merged per user direction). Reproduce on a
clean checkout of this branch but NOT on `origin/main`:

- 9 `ty` type-check errors in `browser/test_session.py`,
  `schema/test_cache.py`, `schema/test_models.py`,
  `sede/_declarations.py`.
- 1 workflow test (`test_next_json_round_trips`): code persists
  `{run_id}.envelope.json` but test expects `{run_id}.json`.

These are upstream of #454 and out of scope for this PR.
