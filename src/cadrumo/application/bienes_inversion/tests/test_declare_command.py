"""The disposal pairing rule, and what a declaration carries into the register.

A disposal is a year AND a regime. The year alone does not say how the
remaining regularización window is imputed; the regime alone does not say when
the good left. Accepting either half on its own would write a record whose
art-110 treatment cannot be computed, so the pair is refused together — and
because that is a fact about the declaration rather than about a command line,
it is refused here rather than at whichever surface collected it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.bienes_inversion.vocabulary import BienInversionDisposalRegime

from ....domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord
from ....domain.bienes_inversion.vocabulary import BienInversionKind
from ..declare_command import (
    BienInversionDeclarationCommand,
    BienInversionDisposalIncompleteError,
    declare_bien_inversion,
    resolve_bien_inversion_disposal,
)
from ..service import BienesInversionRegisterService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "88888888-8888-4888-8888-888888888888"


class _InMemoryRegisterRepository:
    """Inward fake for the command's required register capability."""

    def __init__(self) -> None:
        self._register = BienesInversionIvaRegister()

    def load(self) -> BienesInversionIvaRegister:
        return self._register

    def add(self, record: BienInversionIvaRecord) -> BienesInversionIvaRegister:
        self._register = BienesInversionIvaRegister(records=(*self._register.records, record))
        return self._register


def _register() -> BienesInversionRegisterService:
    """Build the application service over an inward in-memory capability fake."""
    return BienesInversionRegisterService(repository=_InMemoryRegisterRepository())


def _command(**overrides: object) -> BienInversionDeclarationCommand:
    payload: dict[str, object] = {
        "identifier": "bien-1",
        "description": "Delivery van",
        "acquisition_year": 2024,
        "acquisition_ledger_id": "a" * 64,
        "cuota_soportada": Decimal("2100.00"),
        "prorrata_inicial_pct": Decimal("60"),
        "kind": BienInversionKind.from_registry("mueble"),
    }
    payload.update(overrides)
    return BienInversionDeclarationCommand.model_validate(payload)


def test_a_declaration_with_no_disposal_carries_none() -> None:
    """Most capital goods are still held; that is the ordinary case."""
    assert resolve_bien_inversion_disposal(disposal_year=None, disposal_regime=None) is None


def test_a_year_without_a_regime_is_refused() -> None:
    """A disposal year alone cannot say how the remaining window is imputed."""
    with pytest.raises(BienInversionDisposalIncompleteError) as excinfo:
        resolve_bien_inversion_disposal(disposal_year=2026, disposal_regime=None)

    assert excinfo.value.missing == "regime"


def test_a_regime_without_a_year_is_refused() -> None:
    """A regime alone cannot say when the good left."""
    with pytest.raises(BienInversionDisposalIncompleteError) as excinfo:
        resolve_bien_inversion_disposal(
            disposal_year=None,
            disposal_regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta"),
        )

    assert excinfo.value.missing == "year"


def test_both_halves_together_build_the_disposal() -> None:
    """The supported path, so the refusals above are not vacuous."""
    disposal = resolve_bien_inversion_disposal(
        disposal_year=2026,
        disposal_regime=BienInversionDisposalRegime.from_registry("exenta_o_no_sujeta"),
    )

    assert disposal is not None
    assert disposal.year == 2026
    assert disposal.regime == BienInversionDisposalRegime.from_registry("exenta_o_no_sujeta")


def test_the_declaration_reaches_the_register_intact() -> None:
    """Every operator-supplied fact must survive into the persisted record."""
    service = _register()
    outcome = declare_bien_inversion(
        _command(prorrata_sector_id="sector-2"),
        service=service,
    )
    stored = service.list_all().records

    assert len(stored) == 1
    record = stored[0]
    assert record.identifier == "bien-1"
    assert record.acquisition_year == 2024
    assert record.cuota_soportada == Decimal("2100.00")
    assert record.prorrata_inicial_pct == Decimal("60")
    assert record.prorrata_sector_id == "sector-2"
    assert record.disposal is None
    assert outcome.record == record


def test_a_declared_disposal_is_carried_onto_the_record() -> None:
    """The pairing is not merely validated; it lands on the persisted record."""
    service = _register()
    outcome = declare_bien_inversion(
        _command(disposal_year=2026, disposal_regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta")),
        service=service,
    )

    assert outcome.record.disposal is not None
    assert outcome.record.disposal.year == 2026
    assert outcome.record.disposal.regime == BienInversionDisposalRegime.from_registry("sujeta_no_exenta")


def test_a_half_declared_disposal_never_reaches_the_register() -> None:
    """The refusal must fire before persistence, not after a partial write."""
    service = _register()
    with pytest.raises(BienInversionDisposalIncompleteError):
        declare_bien_inversion(_command(disposal_year=2026), service=service)

    assert service.list_all().records == ()
