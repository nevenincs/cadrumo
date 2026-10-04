"""Modelo 360 export reads the encrypted solicitud register, and refuses without it.

The solicitud facts and its account choice are declared through the real
:class:`Modelo360SolicitudRepository`, a solicitante's own account through the real
:class:`OwnAccountRepository`, and both are read back by the real ``export_modelo_revision``
through the composed export ports. Página 1's rendering from these facts is asserted at
DR360's positions in ``application/filing/tests/test_modelo_360_header_export.py``; the
written fichero's página 2 is asserted here against DR360 página 2 (``aeat-dr-360-2010``,
versión 2.1), transcribed by hand rather than read from the layout under test. All data
is synthetic.
"""

from __future__ import annotations

from pathlib import Path

import pydantic
import pytest

from cadrumo.adapters.persistence.profile.modelo_360_solicitud import Modelo360SolicitudRepository
from cadrumo.adapters.persistence.profile.own_accounts import OwnAccountRepository
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
    Modelo360AccountChoice,
    Modelo360CuentaTitularFacts,
    Modelo360EstablecimientoFacts,
    Modelo360OwnAccountChoice,
    Modelo360ProfileFacts,
    Modelo360RepresentanteAccountChoice,
    Modelo360RepresentanteFacts,
    Modelo360SolicitanteFacts,
    Modelo360SolicitudEntry,
    Modelo360SolicitudFacts,
)
from cadrumo.application.modelo.action_errors import ModeloRefundAccountMissingError
from cadrumo.application.modelo.export import (
    ModeloExportAccountReference,
    ModeloExportCommand,
    ModeloExportResult,
    export_modelo_revision,
)
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.deadlines.models import RefundAccount
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.errors import ModeloExportError
from cadrumo.domain.transactions.own_accounts import (
    OwnAccountHolding,
    OwnAccountRegister,
    OwnAccountRole,
    OwnBankAccountDetails,
)

__all__ = ["isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_YEAR = 2025
_PERIOD = Period.from_year_and_code(_YEAR, "AD-HOC")
_TAX_ID = "12345678Z"
_SYNTHETIC_IBAN = "ES9121000418450200051332"
_SYNTHETIC_BIC = "CAIXESBBXXX"
_REPRESENTANTE_IBAN = "DE89370400440532013000"
_REPRESENTANTE_BIC = "COBADEFFXXX"


def _casilla(raw: str) -> CasillaId:
    return validated_casilla_id(raw, surface="modelo 360 solicitud export test")


def _facts(*, holder: M360TitularEnCalidadDe = M360TitularEnCalidadDe.SOLICITANTE) -> Modelo360ProfileFacts:
    representante = (
        Modelo360RepresentanteFacts(tax_id="00000000T", full_name="ASESORES PRUEBA SL")
        if holder is M360TitularEnCalidadDe.REPRESENTANTE
        else None
    )
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
            titular_en_calidad_de=holder,
            divisa="EUR",
        ),
        representante=representante,
    )


def _entry(*, account: Modelo360AccountChoice | None) -> Modelo360SolicitudEntry:
    holder = (
        M360TitularEnCalidadDe.REPRESENTANTE
        if isinstance(account, Modelo360RepresentanteAccountChoice)
        else M360TitularEnCalidadDe.SOLICITANTE
    )
    return Modelo360SolicitudEntry(period=_PERIOD, facts=_facts(holder=holder), account=account)


def _register_own_account(bucket_id: str, *, swift_bic: str = _SYNTHETIC_BIC) -> Modelo360OwnAccountChoice:
    """Enter the solicitante's own account in the encrypted register and reference it."""
    details = OwnBankAccountDetails(
        label="Cuenta solicitante",
        holding=OwnAccountHolding.TITULAR,
        iban=_SYNTHETIC_IBAN,
        swift_bic=swift_bic,
    )

    def add(register: OwnAccountRegister) -> OwnAccountRegister:
        return register.with_new_account(details)

    added = OwnAccountRepository(bucket_id=bucket_id).mutate(add)
    return Modelo360OwnAccountChoice(own_account_id=added.accounts[-1].own_account_id)


def _representante_account() -> Modelo360RepresentanteAccountChoice:
    return Modelo360RepresentanteAccountChoice(
        account=RefundAccount(iban=_REPRESENTANTE_IBAN, swift_bic=_REPRESENTANTE_BIC),
    )


def _seed_360_revision(bucket_id: str, operations: dict[CasillaId, str] | None = None) -> str:
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
            **(operations or {}),
        },
    )
    return calculation_revision_id


def _export(calculation_revision_id: str, output: Path, *, refund_account_id: str | None = None) -> ModeloExportResult:
    with bundled_indexed_authority().operation() as operation:
        return export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calculation_revision_id,
                output_path=output,
                actor="operator",
                refund_account_id=refund_account_id,
            ),
            workflow_profile=export_taxpayer_profile(),
            export_ports=modelo_export_ports_for_test(),
            operation=operation,
        )


#: DR360's two page lengths: página 1 closes with ``</T360010>`` at position 3391 and
#: página 2 with ``</T360020>`` at position 6391, each ten bytes wide.
_DR360_PAGINA_1_LENGTH = 3400
_DR360_PAGINA_2_LENGTH = 6400


def _dr360_slice(page: str, position: int, length: int) -> str:
    """Read one DR360 campo by its printed 1-based position and width."""
    return page[position - 1 : position - 1 + length]


def _operation_inputs(ordinal: int, *, factura: str, base: str, cuota: str, importe: str) -> dict[CasillaId, str]:
    prefix = f"decl.op{ordinal}"
    return {
        _casilla(f"{prefix}-numero"): str(ordinal),
        _casilla(f"{prefix}-tipo"): "P",
        _casilla(f"{prefix}-factura"): factura,
        # Entered as an ISO date; DR360 campos 7 and 56 print it as ddmmaaaa.
        _casilla(f"{prefix}-fecha"): f"{_YEAR}-03-15",
        _casilla(f"{prefix}-codigo-1"): "1",
        _casilla(f"{prefix}-base"): base,
        _casilla(f"{prefix}-cuota"): cuota,
        _casilla(f"{prefix}-importe"): importe,
        _casilla(f"{prefix}-divisa"): "EUR",
        _casilla(f"{prefix}-simplificada"): "0",
    }


def test_a_declared_solicitud_writes_the_fichero_with_a_blank_page_2_marker(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """An ordinary solicitud writes both pages, página 2 campo 2 left blank.

    DR360 página 2 campo 2, ``Indicador de página complementaria``, is printed
    ``obligatorio`` with contenido ``blanco o "C" (compl.)``: the position is always
    written and blank is one of its two values. An initial solicitud carries no
    amendment evidence, so the marker is that blank. The operation campos are read back
    at their printed positions: Num campos zero-filled to width, An campos left-aligned
    and space-filled, N amounts in cents zero-filled to fifteen digits, the fecha --
    entered as an ISO date -- as DDMMAAAA.
    """
    bucket_id = seed_profile(tax_id=_TAX_ID)
    calculation_revision_id = _seed_360_revision(
        bucket_id,
        {
            **_operation_inputs(1, factura="FAC-2025-0001", base="100.00", cuota="21.00", importe="20.00"),
            **_operation_inputs(2, factura="FAC-2025-0002", base="90.00", cuota="18.90", importe="18.00"),
        },
    )
    Modelo360SolicitudRepository(bucket_id=bucket_id).declare(_entry(account=_register_own_account(bucket_id)))
    output = tmp_path / "modelo-360.txt"

    _export(calculation_revision_id, output)

    fichero = output.read_bytes().decode("iso-8859-1")
    assert len(fichero) == _DR360_PAGINA_1_LENGTH + _DR360_PAGINA_2_LENGTH
    pagina_1 = fichero[:_DR360_PAGINA_1_LENGTH]
    pagina_2 = fichero[_DR360_PAGINA_1_LENGTH:]
    assert _dr360_slice(pagina_1, 1, 9) == "<T360010>"
    assert _dr360_slice(pagina_1, 3391, 10) == "</T360010>"

    expected_pagina_2 = {
        (1, 9): "<T360020>",
        (10, 1): " ",
        (11, 5): "00001",
        (16, 1): " ",
        (17, 3): "P  ",
        (20, 50): "FAC-2025-0001".ljust(50),
        (70, 8): f"1503{_YEAR}",
        (78, 10): "1".ljust(10),
        (2698, 15): "000000000010000",
        (2713, 15): "000000000002100",
        (2733, 15): "000000000002000",
        (2748, 3): "EUR",
        (2751, 1): "0",
        (3111, 5): "00002",
        (3117, 3): "P  ",
        (3120, 50): "FAC-2025-0002".ljust(50),
        (3170, 8): f"1503{_YEAR}",
        (5798, 15): "000000000009000",
        (5813, 15): "000000000001890",
        (5833, 15): "000000000001800",
        (5848, 3): "EUR",
        (5851, 1): "0",
        (6391, 10): "</T360020>",
    }
    actual_pagina_2 = {
        (position, length): _dr360_slice(pagina_2, position, length) for position, length in expected_pagina_2
    }
    assert actual_pagina_2 == expected_pagina_2


def test_a_one_operation_solicitud_leaves_the_second_operation_block_blank(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """DR360 página 2 carries operations 1 and 2; a solicitud with one leaves block 2 empty.

    Campos 52-100 are obligatorio for the operation they carry, so with no operation 2
    the block holds its blank fill -- Num campos zero-filled, An campos space-filled --
    and campo 2 stays blank: this is the principal página 2, not a continuation page.
    """
    bucket_id = seed_profile(tax_id=_TAX_ID)
    calculation_revision_id = _seed_360_revision(
        bucket_id,
        _operation_inputs(1, factura="FAC-2025-0001", base="100.00", cuota="21.00", importe="20.00"),
    )
    Modelo360SolicitudRepository(bucket_id=bucket_id).declare(_entry(account=_register_own_account(bucket_id)))
    output = tmp_path / "modelo-360.txt"

    _export(calculation_revision_id, output)

    pagina_2 = output.read_bytes().decode("iso-8859-1")[_DR360_PAGINA_1_LENGTH:]
    assert len(pagina_2) == _DR360_PAGINA_2_LENGTH
    expected = {
        (10, 1): " ",
        (11, 5): "00001",
        (70, 8): f"1503{_YEAR}",
        (2733, 15): "000000000002000",
        (3111, 5): "00000",
        (3116, 1): " ",
        (3117, 3): "   ",
        (3120, 50): " " * 50,
        # DR360 states no fill for an empty fecha; the registry writes an absent date as blanks.
        (3170, 8): " " * 8,
        (3178, 10): " " * 10,
        (5798, 15): "0" * 15,
        (5813, 15): "0" * 15,
        (5833, 15): "0" * 15,
        (5848, 3): "   ",
        (5851, 1): " ",
        (6391, 10): "</T360020>",
    }
    assert {(position, length): _dr360_slice(pagina_2, position, length) for position, length in expected} == expected


def test_a_second_operation_campo_without_its_numero_is_refused(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """An operation-2 campo with no número de operación would print an operation with no identity."""
    bucket_id = seed_profile(tax_id=_TAX_ID)
    calculation_revision_id = _seed_360_revision(
        bucket_id,
        {
            **_operation_inputs(1, factura="FAC-2025-0001", base="100.00", cuota="21.00", importe="20.00"),
            _casilla("decl.op2-factura"): "FAC-2025-0002",
        },
    )
    Modelo360SolicitudRepository(bucket_id=bucket_id).declare(_entry(account=_register_own_account(bucket_id)))
    output = tmp_path / "modelo-360.txt"

    with pytest.raises(ModeloExportError) as exc_info:
        _export(calculation_revision_id, output)

    assert isinstance(exc_info.value.context, dict)
    assert "block anchor 'decl.op2-numero'" in str(exc_info.value.context["cause"])
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


@pytest.mark.parametrize(
    ("holder", "expected_holder_code", "expected_iban", "expected_bic", "expected_reference"),
    [
        pytest.param(
            "solicitante",
            "A",
            _SYNTHETIC_IBAN,
            _SYNTHETIC_BIC,
            ModeloExportAccountReference(role=OwnAccountRole.REFUND, own_account_id="acc-01"),
            id="solicitante-own-account",
        ),
        pytest.param(
            "representante",
            "R",
            _REPRESENTANTE_IBAN,
            _REPRESENTANTE_BIC,
            ModeloExportAccountReference(role=OwnAccountRole.REFUND, own_account_id=None),
            id="representante-embedded-account",
        ),
    ],
)
def test_the_solicitud_account_choice_fills_datos_bancarios_and_names_its_holder(
    isolated_backend: None,
    tmp_path: Path,
    holder: str,
    expected_holder_code: str,
    expected_iban: str,
    expected_bic: str,
    expected_reference: ModeloExportAccountReference,
) -> None:
    """DR360 página 1 campos 114-116: holder "A" or "R", then the IBAN and banco-BIC of that holder."""
    bucket_id = seed_profile(tax_id=_TAX_ID)
    calculation_revision_id = _seed_360_revision(
        bucket_id,
        {
            **_operation_inputs(1, factura="FAC-2025-0001", base="100.00", cuota="21.00", importe="20.00"),
            **_operation_inputs(2, factura="FAC-2025-0002", base="90.00", cuota="18.90", importe="18.00"),
        },
    )
    account = _register_own_account(bucket_id) if holder == "solicitante" else _representante_account()
    Modelo360SolicitudRepository(bucket_id=bucket_id).declare(_entry(account=account))
    output = tmp_path / "modelo-360.txt"

    result = _export(calculation_revision_id, output)

    pagina_1 = output.read_bytes().decode("iso-8859-1")[:_DR360_PAGINA_1_LENGTH]
    assert _dr360_slice(pagina_1, 1937, 1) == expected_holder_code
    assert _dr360_slice(pagina_1, 1938, 34) == expected_iban.ljust(34)
    assert _dr360_slice(pagina_1, 1972, 11) == expected_bic.ljust(11)
    assert _dr360_slice(pagina_1, 1983, 3) == "EUR"
    assert result.selected_account == expected_reference
    assert expected_iban not in result.model_dump_json()


@pytest.mark.parametrize(
    ("declare", "refund_account_id", "reason"),
    [
        pytest.param("undeclared", None, "m360_account_undeclared", id="no-account-declared"),
        pytest.param("own-without-bic", None, "refund_account_bic_missing", id="own-account-without-bic"),
        pytest.param("own", "acc-01", "m360_account_declared_on_solicitud", id="per-filing-override"),
    ],
)
def test_a_solicitud_without_a_usable_account_is_a_typed_refusal(
    isolated_backend: None,
    tmp_path: Path,
    declare: str,
    refund_account_id: str | None,
    reason: str,
) -> None:
    """DR360 campos 115-116 are obligatorio: missing bank data is a typed refusal, never blanks or FAIL.

    Modelo 360 resolves the fixed DEVOLUCION disposition, so the same refund-account
    refusal as every refund export answers before the producer snapshot is built.
    """
    bucket_id = seed_profile(tax_id=_TAX_ID)
    calculation_revision_id = _seed_360_revision(bucket_id)
    account = {
        "undeclared": lambda: None,
        "own-without-bic": lambda: _register_own_account(bucket_id, swift_bic=""),
        "own": lambda: _register_own_account(bucket_id),
    }[declare]()
    Modelo360SolicitudRepository(bucket_id=bucket_id).declare(_entry(account=account))
    output = tmp_path / "modelo-360.txt"

    with pytest.raises(ModeloRefundAccountMissingError) as exc_info:
        _export(calculation_revision_id, output, refund_account_id=refund_account_id)

    assert get_registered_error_code(exc_info.value).code == "REFUSED_MODELO_REFUND_ACCOUNT_MISSING"
    assert isinstance(exc_info.value.context, dict)
    assert exc_info.value.context["reason"] == reason
    assert _SYNTHETIC_IBAN not in str(exc_info.value.context)
    assert not output.exists()


def test_campo_114_must_name_the_holder_of_the_declared_account() -> None:
    with pytest.raises(pydantic.ValidationError, match="campo 114"):
        Modelo360SolicitudEntry(
            period=_PERIOD,
            facts=_facts(holder=M360TitularEnCalidadDe.SOLICITANTE),
            account=_representante_account(),
        )


def test_a_solicitud_declared_for_another_period_does_not_answer_this_one(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    bucket_id = seed_profile(tax_id=_TAX_ID)
    calculation_revision_id = _seed_360_revision(bucket_id)
    other_year = Modelo360SolicitudEntry(
        period=Period.from_year_and_code(_YEAR - 1, "AD-HOC"),
        facts=_facts(),
        account=_register_own_account(bucket_id),
    )
    Modelo360SolicitudRepository(bucket_id=bucket_id).declare(other_year)
    output = tmp_path / "modelo-360.txt"

    with pytest.raises(ModeloExportError) as exc_info:
        _export(calculation_revision_id, output)

    assert isinstance(exc_info.value.context, dict)
    assert exc_info.value.context["reason"] == "m360_solicitud_undeclared"
    assert not output.exists()
