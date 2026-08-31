---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:bb4f202bb3d19968a6731926986635d9ffc76a6df0d1d686846779eecc43bf5b'
step_id: 'S143'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Refactor the size-budget subjects in _producer_snapshot.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/filing/_producer_snapshot.py`

## Changes

- `M` `src/cadrumo/application/filing/_producer_snapshot.py`
- `A` `src/cadrumo/application/filing/_producer_snapshot_m200.py`
- `A` `src/cadrumo/application/filing/_producer_snapshot_m390.py`
- `M` `src/cadrumo/application/filing/_m200_projection.py`
- `M` `src/cadrumo/application/filing/_export_producer.py`

## Verification

```text
uv run --no-sync ruff check src/cadrumo/application/filing/_producer_snapshot.py src/cadrumo/application/filing/_producer_snapshot_m200.py src/cadrumo/application/filing/_producer_snapshot_m390.py src/cadrumo/application/filing/_m200_projection.py src/cadrumo/application/filing/_export_producer.py
All checks passed!
exit 0

uv run --no-sync ruff format --check src/cadrumo/application/filing/_producer_snapshot.py src/cadrumo/application/filing/_producer_snapshot_m200.py src/cadrumo/application/filing/_producer_snapshot_m390.py src/cadrumo/application/filing/_m200_projection.py src/cadrumo/application/filing/_export_producer.py
5 files already formatted
exit 0

uv run --no-sync python -m compileall -q src/cadrumo/application/filing/_producer_snapshot.py src/cadrumo/application/filing/_producer_snapshot_m200.py src/cadrumo/application/filing/_producer_snapshot_m390.py src/cadrumo/application/filing/_m200_projection.py src/cadrumo/application/filing/_export_producer.py
exit 0

uv run --no-sync python -c 'import cadrumo.application.filing._producer_snapshot as old; moved=("Modelo200AdministradorRow","Modelo200EntidadMenorDependienteRow","Modelo200EntidadParticipadaRow","Modelo200EstablecimientoPermanenteRow","Modelo200IncnGrupoSociedadRow","Modelo200OperacionReestructuracionRow","Modelo200ParticipacionDirectaRow","Modelo200ParticipacionSocioRow","Modelo200ParticipeAieUteRow","Modelo200ProjectionRows","Modelo200ProfileFacts","Modelo200RepresentanteLegalRow","Modelo200SecretarioConsejoRow","Modelo200SocioSicavDisolucionRow","Modelo200TransparenciaFiscalInternacionalRow","M390ActivityValueArrival","M390DifferentiatedDeductionValueArrival","M390FilingFacts","M390ProjectionScalar","M390ProrrataActivityValueArrival","M390RegimenSimplificadoActivityValueArrival","M390RegimenSimplificadoModuleValueArrival","M390RepresentativeValueArrival"); exposed=sorted(name for name in moved if hasattr(old,name)); assert not exposed,exposed; print(f"OLD_PRODUCER_SNAPSHOT_MOVED_BINDINGS={len(exposed)}")'
OLD_PRODUCER_SNAPSHOT_MOVED_BINDINGS=0
exit 0

uv run --no-sync pytest -n 0 -o addopts= --collect-only -q src/cadrumo/application/filing/tests/test_export_value_policy.py src/cadrumo/application/filing/tests/test_export_post_write_verification.py src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py
32 tests collected in 0.87s
No marker selector or --deselect option was supplied; deselected 0.
exit 0

uv run --no-sync pytest -n 0 -o addopts= -q src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py
12 passed in 1.68s
exit 0

(Get-Content src/cadrumo/application/filing/_producer_snapshot.py).Count; (Get-Content src/cadrumo/application/filing/_producer_snapshot_m200.py).Count; (Get-Content src/cadrumo/application/filing/_producer_snapshot_m390.py).Count
1209
416
120
exit 0

Isolated-index staged-diff review: source peer import-order hunk was rebuilt out of the staged blob; `PEER_HUNK_EXCLUDED=true` and `git diff --cached --check` exit 0 before commit.
```
