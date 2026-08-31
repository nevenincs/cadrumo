---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:b7bab6c12f560d66b76d9a67d3635387037ce66ced11669ddd210b2dac16e94c'
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

git diff --cached --check
exit 0

$commit='80417ba85f'; $path='src/cadrumo/application/filing/_producer_snapshot.py'; $names=@('from ...core.refund_election import RefundElection','from ...core.payment_election import PaymentElection','from ...core.prior_domiciliation_election import PriorDomiciliationElection','from ...core.result_disposition import ResultDisposition, result_disposition_is_refund','from ...core.modelo import Modelo','from ...core.models import STRICT_FROZEN_CONFIG','from ...core.period import Period, StandardPeriodCode','from ...core.identity import SubjectTaxId'); $parent=git show "${commit}^:$path" | Where-Object { $_ -in $names }; $step=git show "${commit}:$path" | Where-Object { $_ -in $names }; if($parent.Count -ne $names.Count -or $step.Count -ne $names.Count -or (($parent -join "`n") -cne ($step -join "`n"))){throw 'immutable peer import-order mismatch'}; Write-Output ('IMMUTABLE_PARENT_ORDER=' + ($parent -join ' | ')); Write-Output ('IMMUTABLE_STEP_ORDER=' + ($step -join ' | ')); Write-Output 'IMMUTABLE_PEER_IMPORT_ORDER_UNCHANGED=true'; Write-Output 'exit 0'
IMMUTABLE_PARENT_ORDER=from ...core.refund_election import RefundElection | from ...core.payment_election import PaymentElection | from ...core.prior_domiciliation_election import PriorDomiciliationElection | from ...core.result_disposition import ResultDisposition, result_disposition_is_refund | from ...core.modelo import Modelo | from ...core.models import STRICT_FROZEN_CONFIG | from ...core.period import Period, StandardPeriodCode | from ...core.identity import SubjectTaxId
IMMUTABLE_STEP_ORDER=from ...core.refund_election import RefundElection | from ...core.payment_election import PaymentElection | from ...core.prior_domiciliation_election import PriorDomiciliationElection | from ...core.result_disposition import ResultDisposition, result_disposition_is_refund | from ...core.modelo import Modelo | from ...core.models import STRICT_FROZEN_CONFIG | from ...core.period import Period, StandardPeriodCode | from ...core.identity import SubjectTaxId
IMMUTABLE_PEER_IMPORT_ORDER_UNCHANGED=true
exit 0
```
