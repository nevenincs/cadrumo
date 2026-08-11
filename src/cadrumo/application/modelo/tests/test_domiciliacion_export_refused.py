"""Domiciliación DID input is charge-only and refuses without debit authority."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....application.filing import build_runtime_schema_provider, render_layout
from ....core import Period, ResultDisposition
from ....domain.calculations.registry import RegistrySnapshotRef
from ....domain.deadlines import ChargeAccount, ModeloIVAProfile, RefundAccount
from ....domain.filing import ModeloDraft
from ....domain.submission import ModeloDraftStatus
from .._action_errors import ModeloChargeAccountMissingError
from .._export import _compose_charge_account_block

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REFUND_IBAN = "ES9121000418450200051332"
_CHARGE_IBAN = "ES7921000813610123456789"
_DID_TAG = "<T303DID00>"
_DID_PAGE_LENGTH = 823


def _render_domiciliacion_did(charge_block: dict[str, str]) -> str:
    """Render the real U DID record through the registered 2026 M303 layout."""
    period = Period.from_year_and_code(2026, "02")
    provider = build_runtime_schema_provider(filing_year=2026, period=period, modelos=("303",))
    subview = provider.get_subview("303")
    draft = ModeloDraft(
        draft_id="d" + "0" * 63,
        modelo="303",
        period=period,
        profile_tax_id="X1234567L",
        subject_tax_id="X1234567L",
        snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id="2026-y-siguientes",
            modelo_year=2026,
            period="02",
        ),
        status=ModeloDraftStatus.APROBADO,
        values=(),
        created_at=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
        updated_at=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
        schema_version=subview.schema_version,
    )
    headers = {
        "declaration_type": ResultDisposition.DOMICILIACION.value,
        "full_name": "Charge Operator",
        "surnames": "Charge",
        "name": "Operator",
        "entity_type": "",
        "fecha_inicio_periodo": "01042026",
        "fecha_fin_periodo": "30062026",
        "devengo_start_date": "01042026",
        "tax_id": "X1234567L",
        "presenter_nif": "X1234567L",
        "program_version": "A001",
        "redeme": "2",
        **charge_block,
    }
    rendered = render_layout(subview.export_layouts[0], draft=draft, headers=headers).decode("latin-1")
    start = rendered.index(_DID_TAG)
    return rendered[start : start + _DID_PAGE_LENGTH]


def test_domiciliacion_refuses_when_only_a_refund_account_is_recorded() -> None:
    """A payable refund destination is not a debit authorisation.

    The profile deliberately contains the tempting value that must never become
    a U instruction. Only the separately modelled ``charge_account`` is passed
    to the U composer, so there is no fallback branch that could reuse it.
    """
    iva = ModeloIVAProfile(refund_account=RefundAccount(iban=_REFUND_IBAN))

    with pytest.raises(ModeloChargeAccountMissingError) as caught:
        _compose_charge_account_block(iva.charge_account)

    assert "domiciliación" in str(caught.value)
    assert "charge account" in str(caught.value).lower()
    assert "refund account" in str(caught.value).lower()


def test_domiciliacion_uses_only_the_explicit_charge_iban() -> None:
    """The U DID block holds exactly position 23's debit IBAN, nothing refund-only."""
    iva = ModeloIVAProfile(
        refund_account=RefundAccount(
            iban=_REFUND_IBAN,
            swift_bic="CHASUS33XXX",
            bank_name="Refund Bank",
            bank_address="Refund Street 1",
            bank_city="New York",
            bank_country_code="US",
        ),
        charge_account=ChargeAccount(iban=_CHARGE_IBAN),
    )

    block = _compose_charge_account_block(iva.charge_account)

    assert block == {"iban": _CHARGE_IBAN}
    assert _REFUND_IBAN not in block.values()
    assert not (
        {"sepa_marca", "swift_bic", "bank_name", "bank_address", "bank_city", "bank_country_code"} & block.keys()
    )

    did = _render_domiciliacion_did(block)
    assert did[22:56].rstrip() == _CHARGE_IBAN
    # Positions 12, 57, 127, 162 and 192 are refund-only fields. A U record
    # carries the debit IBAN and no foreign/refund metadata. Position 194 is
    # the layout's fixed ``0`` default when no SEPA Marca header is supplied;
    # it is not an emitted charge or refund value (1/2/3).
    assert did[11:22].strip() == ""
    assert did[56:126].strip() == ""
    assert did[126:161].strip() == ""
    assert did[161:191].strip() == ""
    assert did[191:193].strip() == ""
    assert did[193] == "0"


def test_charge_account_iban_is_not_optional() -> None:
    """The domain model refuses a blank debit instruction before export composition."""
    with pytest.raises(ValidationError) as caught:
        ChargeAccount(iban="")

    assert "charge-account iban" in str(caught.value)
