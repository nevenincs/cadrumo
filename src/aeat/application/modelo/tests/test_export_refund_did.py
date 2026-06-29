"""Modelo 303 refund DID export tests split from the export service suite."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.deadlines import TaxpayerProfile
from ....domain.deadlines._models import IVARegime, ModeloIVAProfile, RefundAccount
from ....domain.modelos._calculation_revision import CalculationRevisionState
from .._export import compose_export_headers
from ._export_test_support import (
    _M303_RESULT_CASILLA,
    _SPANISH_IBAN,
    _load_seeded_work_unit_and_revision,
    _seed_profile,
    _seed_revision,
    _snapshot_ref,
    _synthetic_valid_nif,
    isolated_backend_context,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("isolated_backend")]


@pytest.fixture
def isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_backend_context(tmp_path):
        yield


# The DR303 Diseño positions the REDEME indicator at page-1 offset 110 (length 1)
# and the refund-account block on the DP303DID page (SWIFT-BIC offset 12, IBAN
# offset 23, Marca SEPA offset 194). These tests drive the real header composition
# and registry-backed layout render, never a hand-built byte string.
_DID_OPEN_TAG = "<T303DID00>"
_PAGE1_OPEN_TAG = "<T30301000>"
_DID_PAGE_LENGTH = 823
_DID_SWIFT_OFFSET = 12
_DID_IBAN_OFFSET = 23
_DID_BANK_NAME_OFFSET = 57
_DID_SEPA_OFFSET = 194
_REDEME_OFFSET = 110


def _redeme_byte(text: str) -> str:
    """Return the page-1 REDEME indicator byte."""
    start = text.index(_PAGE1_OPEN_TAG)
    return text[start + _REDEME_OFFSET - 1]


def _did_page(text: str) -> str:
    start = text.index(_DID_OPEN_TAG)
    page = text[start : start + _DID_PAGE_LENGTH]
    assert page.startswith(_DID_OPEN_TAG)
    assert len(page) == _DID_PAGE_LENGTH
    return page


def _redeme_profile(*, refund_account: RefundAccount | None = None) -> TaxpayerProfile:
    """A REDEME-enrolled IVA profile so a negative M303 period resolves to a refund."""
    return TaxpayerProfile(
        tax_id=_synthetic_valid_nif(12_345_678),
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(redeme_enrolled=True, refund_account=refund_account),
    )


def _ordinary_valid_nif_profile() -> TaxpayerProfile:
    """A non-REDEME IVA profile with a valid 9-char NIF (carries forward -> "C")."""
    return TaxpayerProfile(
        tax_id=_synthetic_valid_nif(87_654_321),
        iva_regime=IVARegime.GENERAL,
    )


def _render_modelo_303_fichero(
    *,
    workflow_profile: TaxpayerProfile,
    casilla_71: Decimal,
    period_code: str = "02",
) -> str:
    """Compose real headers and render the real M303 layout as latin-1 text."""
    from ....application.filing import build_runtime_schema_provider, render_layout
    from ....domain.filing import ModeloDraft
    from ....domain.filing._schema import ModeloValue, ModeloValueKind
    from ....domain.submission._protocols import ModeloDraftStatus

    bucket_id = _seed_profile(profile_overrides={"identity.surnames": "Redeme", "identity.name": "Company"})
    work_unit_id, revision_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period=period_code,
        casilla_values={_M303_RESULT_CASILLA: casilla_71},
    )
    work_unit, revision = _load_seeded_work_unit_and_revision(work_unit_id, revision_id)

    period = Period.from_year_and_code(2026, period_code)
    headers = compose_export_headers(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        period=period,
    )

    provider = build_runtime_schema_provider(filing_year=2026, period=period, modelos=("303",))
    subview = provider.get_subview("303")
    now_ts = datetime(2026, 5, 21, 12, 3, tzinfo=UTC)
    draft = ModeloDraft(
        draft_id="d" + "0" * 63,
        modelo="303",
        period=period,
        profile_tax_id=str(workflow_profile.tax_id),
        subject_tax_id=str(workflow_profile.tax_id),
        snapshot_ref=_snapshot_ref(modelo="303", period=period, revision_id=work_unit.revision_id),
        status=ModeloDraftStatus.APROBADO,
        values=(
            ModeloValue(
                casilla_id=_M303_RESULT_CASILLA,
                value=casilla_71,
                kind=ModeloValueKind.LITERAL,
                source="test-supplied result",
            ),
        ),
        created_at=now_ts,
        updated_at=now_ts,
        schema_version=subview.schema_version,
    )
    payload = render_layout(subview.export_layouts[0], draft=draft, headers=headers)
    return payload.decode("latin-1")


def test_refund_export_emits_iban_redeme_and_marca_for_sepa_account() -> None:
    """A REDEME refund with a Spanish IBAN emits the DID IBAN, REDEME byte, and SEPA mark."""
    account = RefundAccount(iban=_SPANISH_IBAN)
    text = _render_modelo_303_fichero(
        workflow_profile=_redeme_profile(refund_account=account),
        casilla_71=Decimal("-210.00"),
    )

    assert _redeme_byte(text) == "1"
    did = _did_page(text)
    iban_field = did[_DID_IBAN_OFFSET - 1 : _DID_IBAN_OFFSET - 1 + 34]
    assert iban_field.rstrip() == _SPANISH_IBAN
    assert did[_DID_SEPA_OFFSET - 1] == "1"
    assert text.count(_SPANISH_IBAN) == 1


def test_refund_export_emits_swift_and_bank_block_for_non_sepa_account() -> None:
    """A REDEME refund with a non-SEPA SWIFT account emits the foreign-bank DID block."""
    account = RefundAccount(
        iban=None,
        swift_bic="CHASUS33XXX",
        bank_name="Synthetic US Bank",
        bank_address="1 Synthetic Plaza",
        bank_city="New York",
        bank_country_code="US",
    )
    text = _render_modelo_303_fichero(
        workflow_profile=_redeme_profile(refund_account=account),
        casilla_71=Decimal("-210.00"),
    )

    assert _redeme_byte(text) == "1"
    did = _did_page(text)
    assert did[_DID_SEPA_OFFSET - 1] == "3"
    assert did[_DID_SWIFT_OFFSET - 1 : _DID_SWIFT_OFFSET - 1 + 11].rstrip() == "CHASUS33XXX"
    assert did[_DID_BANK_NAME_OFFSET - 1 : _DID_BANK_NAME_OFFSET - 1 + 70].rstrip() == "Synthetic US Bank"
    assert did[_DID_IBAN_OFFSET - 1 : _DID_IBAN_OFFSET - 1 + 34].strip() == ""


def test_refund_disposition_without_account_refuses_rather_than_emitting_empty_did() -> None:
    """A refund disposition with no refund account is refused, never rendered as an empty DID block."""
    from .._action_errors import ModeloRefundAccountMissingError

    with pytest.raises(ModeloRefundAccountMissingError):
        _render_modelo_303_fichero(
            workflow_profile=_redeme_profile(refund_account=None),
            casilla_71=Decimal("-210.00"),
        )


def test_non_refund_filing_emits_no_did_page_and_redeme_two() -> None:
    """An ordinary non-REDEME negative M303 period carries forward and emits no DID page."""
    text = _render_modelo_303_fichero(
        workflow_profile=_ordinary_valid_nif_profile(),
        casilla_71=Decimal("-210.00"),
    )

    assert _redeme_byte(text) == "2"
    assert _DID_OPEN_TAG not in text
    assert "DID00" not in text
