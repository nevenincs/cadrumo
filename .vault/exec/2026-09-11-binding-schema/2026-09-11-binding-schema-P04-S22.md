---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:8858a6b1d92fe35d2d28c683c52b52f475178edd8a2bc12016b89fa9f02fed97'
step_id: 'S22'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Ground casilla 0224's data_type against each edition's official record design and author it explicitly on every edition of the lineage, recording the wrong edition; move the boolean-on-Decimal profile bindings (anualidades-sin-minimo-descendientes, has-economic-activity and siblings) to the boolean channel with their injectors emitting bool, contract and resolver in one change

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/casillas/*.toml`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/bindings/*.toml`
- `src/cadrumo/application/modelo/profile_binding.py`
- `src/cadrumo/domain/renta/`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/c0224.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2021/casillas/c0224.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/casillas/c0224.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/casillas/c0224.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/c0224.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0224.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/bindings/0007-renta-2020-profile-anualidades-sin-minimo-descendientes.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2021/bindings/0007-renta-2021-profile-anualidades-sin-minimo-descendientes.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0007-renta-2022-profile-anualidades-sin-minimo-descendientes.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/bindings/0007-renta-2023-profile-anualidades-sin-minimo-descendientes.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/0053-renta-2024-profile-anualidades-sin-minimo-descendientes.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/bindings/0051-renta-2025-profile-anualidades-sin-minimo-descendientes.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/bindings/0064-renta-2025-profile-has-economic-activity.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/formulas/0131-renta-2020-cuota-escala-estatal-sobre-base-liquidable-general.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2021/formulas/0133-renta-2021-cuota-escala-estatal-sobre-base-liquidable-general.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/formulas/0149-renta-2022-cuota-escala-estatal-sobre-base-liquidable-general.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/formulas/0150-renta-2023-cuota-escala-estatal-sobre-base-liquidable-general.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0149-renta-2024-cuota-escala-estatal-sobre-base-liquidable-general.toml`
- `M` `src/cadrumo/_data/registry/authority/authority.json`
- `M` `src/cadrumo/application/modelo/profile_binding.py`
- `M` `src/cadrumo/application/modelo/tests/test_anualidades_eligibility_derivation.py`
- `A` `dev/registry/tests/test_modelo_100_boolean_channel_profile_bindings.py`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline publish-authority` -> `pass`
- `verify:` `uv run pytest dev/registry/tests/test_modelo_100_boolean_channel_profile_bindings.py -n 0 -m integration` -> `pass`
- `verify:` `uv run ruff check` / `uv run ty check` / `uv run basedpyright` on touched files -> `pass`

## Notes

- `src/cadrumo/application/modelo/tests/test_anualidades_eligibility_derivation.py` could not be
  executed: `src/cadrumo/application/modelo/tests/conftest.py` fails to import at collection because
  `cadrumo.application.calculations.m303_carry_ingress` does not export `m303_carry_header_key`, an
  in-flight edit owned by another contributor. Pre-existing and unrelated to this change.
- Pre-existing unrelated failures observed while validating: 17 in
  `dev/registry/tests/test_modelo_100_anualidades_separate_escala_multiyear.py` (a concurrent
  uncommitted edit references year-prefixed binding ids that do not exist at HEAD), and 2 in
  `dev/registry/tests/test_modelo_100_casilla_wiring_contract.py` /
  `dev/registry/tests/test_modelo_100_drift_detection.py` (unauthored retired-provider legal facts and
  orphan parameters across modelos 131/303).
