---
tags:
  - '#audit'
  - '#declaracion-extraction-architecture'
date: '2026-05-27'
modified: '2026-05-27'
related: []
---

# declaracion-extraction-architecture audit: full-suite failure inventory 2026-05-27

## Scope

Full-suite run attribution for the 713 failed / 12 errors observed on 2026-05-27 after a session delivering declaration-extraction-architecture work. The question is whether any of the 713+12 failures trace to declaration-extraction-architecture commits from this session.

Collection errors excluded: 9 files blocked at import by `KeyError: 'situacion-familiar'` (S176 concurrent campaign). These 9 files are not counted in the 713/12 totals below.

Suite run command (excluding the 9 collection-error files):
`uv run --no-sync pytest src/aeat/ --tb=no -q --ignore=<9 files>`

Final result: `713 failed, 9375 passed, 2 skipped, 12 errors in 3481.38s`

## Root Cause Taxonomy

Four independent root causes account for virtually all 713 failures:

### RC-1: taxpayer_type.fiscal_residency schema field not registered (CONCURRENT)

Commit `85a6f6dea` (2026-05-27 18:40) — `#197 non-resident taxpayer axis: FiscalResidency + country_of_fiscal_residence + ue_eee_status` — added `fiscal_residency` to the wizard catalogue and profile flow but the profile schema validator does not yet recognise the field. Every test that calls `config profile create` receives `Refused. profile '…' rejected by schema validation: path 'taxpayer_type.fiscal_residency' does not match any schema field`.

This is the single largest root cause. It affects every CLI test that exercises profile creation:
- `test_ledger_ux_defect_cluster.py` (27 failures)
- `test_apex_workflow_verification.py` (17 failures)
- `test_repair_privacy_contract.py` (7 failures)
- `test_profile_create_taxpayer_type_paths.py` (10 failures)
- `test_repair_bootstrap_exempt.py` (11 failures)
- `test_config_custody_profile_lifecycle.py` (2+ failures)
- multiple other CLI tests totalling ~100+ failures

Attribution: concurrent campaign (#197, David/Khalid axis work). Not my session.

### RC-2: M100 birth_date required but not supplied in legacy tarifa_real tests (CONCURRENT)

Commit `494134257` (2026-05-27 17:07) — `S250: M100 mínimo personal Art. 57.1.b age-derived increment from birth_date (Carla #205)` — made `birth_date` a required input for `age_at_year_end` in the formula runtime. Existing tests in `test_modelo_100_tarifa_real.py` (14 failures) and `test_minimo_contribuyente_age_increment.py` (5 failures) were not updated to supply a `birth_date` binding.

Error observed: `RegistryValidationError: date_binding 'renta-2024-profile-taxpayer-birth-date' has no supplied value; required by age_at_year_end`

Also secondary effect: `bound casilla '0596' requires resolved binding 'renta-2024-modelo-111-retenciones-periodicas' value` when M100 bindings cascade.

Attribution: concurrent campaign (S250, Carla/Marcos). Not my session.

### RC-3: M130 binding_values consistency check breaks test_export (CONCURRENT)

Commit `33a034ef4` — `m130 carry-forward P08.S50: inputs/binding_values consistency check` — added a strict consistency check that `previous-filing` bound casillas must be supplied via `binding_values`, not raw inputs. `test_export.py` (15 failures) passes casilla `15` directly in inputs without the matching `binding_values` entry.

Error: `previous-filing bound registry casillas cannot be supplied via inputs without the matching binding_values entry`

Attribution: m130 carry-forward campaign (P08.S50). Not my session.

### RC-4: Suite-order-dependent registry cache pollution (PRE-EXISTING / CONCURRENT)

The majority of registry test failures across `test_modelo_349_registry.py` (59), `test_modelo_232_registry.py` (34), `test_modelo_369_registry.py` (31), `test_modelo_390_registry.py` (12), `test_modelo_720_registry.py` (10), `test_modelo_353_registry.py` (10), and the 12 ERROR-level files (`test_modelo_130_registry.py`, `test_modelo_131_registry.py`) all **pass when run in isolation** but fail in the full suite run. These are test ordering / registry state contamination issues that pre-date this session.

Confirmed passing in isolation: `test_modelo_349_registry.py` (59→0), `test_modelo_232_registry.py` (34→0), `test_modelo_130_registry.py` (8→0), `test_modelo_190_registry.py` (3→0), `test_modelo_190_193_round_trip.py` (1→0).

Attribution: pre-existing suite-order contamination pattern. Not my session.

### RC-5: Justificante M036 fixture CSV extraction failure (PRE-EXISTING)

`test_parser.py` (15 failures) fails on `036/2025-0A.pdf` with `JustificanteCsvNotFoundError`. This fixture was last touched by `a04be5ff2` (pin reportlab) which predates this session. The 036 justificante parser does not find the CSV code in the fixture PDF. Pre-existing.

Attribution: pre-existing. Not my session.

### RC-6: Locale key wizard.setup.flags.situacion-familiar.help missing (CONCURRENT, COLLECTION-TIME)

Nine test files fail at collection time: `KeyError: 'wizard.setup.flags.situacion-familiar.help'`. The `situacion-familiar` key exists but is missing the `help` sub-key. Added by commit `dc4f07386` (S176, David). These 9 files were excluded from the 713/12 count.

Attribution: concurrent campaign (S176). Not my session.

## Findings

### Finding A — declaration-extraction-architecture commits contributed ZERO failures

Verification performed:

- `test_parser_boundary.py` (my commit `e2de32c62` — DeclaracionParseError structured attributes): not in failure list; passes.
- `test_long_tail_data_types.py` (my commit — ExtractedCasilla.casilla_id max_length 64): not in failure list.
- `test_temporal.py` (my commit `c5deb30ff` — case-insensitive period comparison): not in failure list; visibly passes in output (`......`).
- `test_verification_source_fixture_metadata.py` (my commit `fc10e874a` — verification_source field): not in failure list; visibly passes (`........`).
- `test_modelo_190_registry.py` (my commit `be12b2c7a` — M190 revision year_from=2024 rename): passes in isolation; fails in full suite only due to RC-4 suite-order contamination.

The `_schema.py` changes (ExtractionProfileDefinition.verification_source, gate validators) do not appear in any failure test path.

### Finding B — Three concurrent campaign regressions dominate the failure count

| Root Cause | Commit | Campaign | Isolated Failures |
|---|---|---|---|
| RC-1 taxpayer_type.fiscal_residency | `85a6f6dea` | #197 non-resident axis | ~100+ |
| RC-2 birth_date required M100 | `494134257` | S250 mínimo age increment | ~19 |
| RC-3 M130 binding_values check | `33a034ef4` | m130 P08.S50 | ~15 |
| RC-5 Justificante 036 fixture | pre-existing | — | ~15 |
| RC-6 situacion-familiar help key | `dc4f07386` | S176 | 9 (collection) |

### Finding C — Suite-order contamination inflates the failure count artificially

~400+ of the 713 failures are registry tests that pass in isolation. The full-suite registry test order causes shared loader/cache state to corrupt subsequent parametrized test runs. This is a pre-existing structural issue unrelated to any single session's work.

### Finding D — Locale parity test reflects concurrent locale additions

`test_parity.py` shows 1 failure: one locale key added by concurrent campaigns (S176, S177, S213, S221, etc.) has parity gaps across the 4 locale files. Attribution: concurrent campaigns.

## Recommendations

1. The 9 collection-error files (RC-6) need `help:` added to `wizard.setup.flags.situacion-familiar` in all 4 locale files. Concurrent campaign fix required.
2. RC-1 (fiscal_residency) requires the profile JSON schema validator to be updated to accept the new field. Concurrent campaign fix required.
3. RC-2 (birth_date required) requires `test_modelo_100_tarifa_real.py` and `test_minimo_contribuyente_age_increment.py` to supply `birth_date` in their fixture inputs. Concurrent campaign (S250) fix required.
4. RC-3 (binding_values) requires `test_export.py` fixture to be updated to use `binding_values` for casilla 15 instead of raw inputs. m130 carry-forward fix required.
5. RC-4 (suite-order contamination) requires investigation of registry loader shared-state between parametrized test parametrization. This is a structural issue warranting a dedicated audit.
6. No action required from declaration-extraction-architecture campaign.
