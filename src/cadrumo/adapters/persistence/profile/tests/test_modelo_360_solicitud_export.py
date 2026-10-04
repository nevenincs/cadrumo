"""Modelo 360 export reads the encrypted solicitud register, and refuses without it.

The solicitud facts and refund account are declared through the real
:class:`Modelo360SolicitudRepository` and read back by the real ``export_modelo_revision``
through the composed export ports. Página 1's rendering from these facts is asserted at
DR360's positions in ``application/filing/tests/test_modelo_360_header_export.py``. All
data is synthetic.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.modelo_360_solicitud import Modelo360SolicitudRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.modelo_export_support import (
    export_taxpayer_profile,
    isolated_backend,
    seed_profile,
    seed_revision,
)
from cadrumo.application.filing.producer_snapshot_m360 import (
    M360AmbitoEstablecimiento,
    M360CausaPresentacion,
    M360NivelCalidadDatos,
    M360TitularEnCalidadDe,
    Modelo360CuentaTitularFacts,
    Modelo360EstablecimientoFacts,
    Modelo360ProfileFacts,
    Modelo360SolicitanteFacts,
    Modelo360SolicitudEntry,
    Modelo360SolicitudFacts,
)
from cadrumo.application.modelo.export import ModeloExportCommand, export_modelo_revision
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.deadlines.models import RefundAccount
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.errors import ModeloExportError

__all__ = ["isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_YEAR = 2025
_PERIOD = Period.from_year_and_code(_YEAR, "AD-HOC")
_TAX_ID = "12345678Z"
_SYNTHETIC_IBAN = "ES9121000418450200051332"
_SYNTHETIC_BIC = "CAIXESBBXXX"


def _casilla(raw: str) -> CasillaId:
    return validated_casilla_id(raw, surface="modelo 360 solicitud export test")


def _facts() -> Modelo360ProfileFacts:
    return Modelo360ProfileFacts(
        solicitud=Modelo360SolicitudFacts(
            nivel_calidad_datos=M360NivelCalidadDatos.MAXIMA,
            pais_destino="DE",
            causa_presentacion=M360CausaPresentacion.INICIAL,
        ),
        solicitante=Modelo360SolicitanteFacts(
            email="solicitante@example.es",
            establecimiento=Modelo360EstablecimientoFacts(ambito=M360AmbitoEstablecimiento.TERRITORIO_COMUN),
        ),
        cuenta=Modelo360CuentaTitularFacts(
            titular_nombre="OPERATOR TEST",
            titular_en_calidad_de=M360TitularEnCalidadDe.SOLICITANTE,
            divisa="EUR",
        ),
    )


def _entry(*, refund_account: RefundAccount | None) -> Modelo360SolicitudEntry:
    return Modelo360SolicitudEntry(period=_PERIOD, facts=_facts(), refund_account=refund_account)


def _account() -> RefundAccount:
    return RefundAccount(iban=_SYNTHETIC_IBAN, swift_bic=_SYNTHETIC_BIC)


def _seed_360_revision(bucket_id: str) -> str:
    _, calculation_revision_id = seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="360",
        filing_year=_YEAR,
        period=_PERIOD.code,
        input_values_by_casilla_id={
            _casilla("decl.ejercicio"): str(_YEAR),
            _casilla("decl.estado-miembro"): "DE",
            _casilla("devolucion.divisa"): "EUR",
            _casilla("devolucion.periodo-fecha-inicio"): f"{_YEAR}-01-01",
            _casilla("devolucion.periodo-fecha-fin"): f"{_YEAR}-12-31",
            _casilla("devolucion.importe-solicitado"): "38.00",
        },
    )
    return calculation_revision_id


def _export(calculation_revision_id: str, output: Path) -> None:
    with bundled_indexed_authority().operation() as operation:
        export_modelo_revision(
            ModeloExportCommand(calculation_revision_id=calculation_revision_id, output_path=output, actor="operator"),
            workflow_profile=export_taxpayer_profile(),
            export_ports=modelo_export_ports_for_test(),
            operation=operation,
        )


def _cause_chain(error: BaseException) -> Iterator[BaseException]:
    current: BaseException | None = error
    while current is not None:
        yield current
        current = current.__cause__


def test_a_declared_solicitud_passes_the_producer_boundary_and_stops_only_at_page_2(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """The persisted solicitud and account satisfy every página 1 producer fact.

    The export now gets past the producer snapshot -- the boundary that refused every
    modelo 360 before the register existed -- and renders until página 2 campo 2. DR360
    prints that campo "obligatorio, blanco o C", yet the published layout declares it
    required with no blank, so an ordinary solicitud is refused there. That is a layout
    defect outside this register; when it is corrected this test must turn into the
    success assertion on the written fichero.
    """
    bucket_id = seed_profile(tax_id=_TAX_ID)
    calculation_revision_id = _seed_360_revision(bucket_id)
    Modelo360SolicitudRepository(bucket_id=bucket_id).declare(_entry(refund_account=_account()))
    output = tmp_path / "modelo-360.txt"

    with pytest.raises(ModeloExportError) as exc_info:
        _export(calculation_revision_id, output)

    causes = list(_cause_chain(exc_info.value))
    assert "FilingProducerSnapshotError" not in {type(cause).__name__ for cause in causes}
    assert any("m360-2010.pagina02.f002" in str(cause) for cause in causes)
    assert not output.exists()


def test_an_undeclared_solicitud_is_refused_before_any_file_is_written(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    bucket_id = seed_profile(tax_id=_TAX_ID)
    calculation_revision_id = _seed_360_revision(bucket_id)
    output = tmp_path / "modelo-360.txt"

    with pytest.raises(ModeloExportError) as exc_info:
        _export(calculation_revision_id, output)

    assert isinstance(exc_info.value.context, dict)
    assert exc_info.value.context["reason"] == "m360_solicitud_undeclared"
    assert not output.exists()


def test_a_solicitud_without_its_refund_account_is_refused(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """DR360 campos 115-116 are obligatorio: undeclared bank data is a refusal, never blanks."""
    bucket_id = seed_profile(tax_id=_TAX_ID)
    calculation_revision_id = _seed_360_revision(bucket_id)
    Modelo360SolicitudRepository(bucket_id=bucket_id).declare(_entry(refund_account=None))
    output = tmp_path / "modelo-360.txt"

    with pytest.raises(ModeloExportError) as exc_info:
        _export(calculation_revision_id, output)

    assert exc_info.value.__cause__ is not None
    assert "modelo 360 requires a selected refund account" in str(exc_info.value.__cause__)
    assert not output.exists()


def test_a_solicitud_declared_for_another_period_does_not_answer_this_one(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    bucket_id = seed_profile(tax_id=_TAX_ID)
    calculation_revision_id = _seed_360_revision(bucket_id)
    other_year = Modelo360SolicitudEntry(
        period=Period.from_year_and_code(_YEAR - 1, "AD-HOC"),
        facts=_facts(),
        refund_account=_account(),
    )
    Modelo360SolicitudRepository(bucket_id=bucket_id).declare(other_year)
    output = tmp_path / "modelo-360.txt"

    with pytest.raises(ModeloExportError) as exc_info:
        _export(calculation_revision_id, output)

    assert isinstance(exc_info.value.context, dict)
    assert exc_info.value.context["reason"] == "m360_solicitud_undeclared"
    assert not output.exists()
