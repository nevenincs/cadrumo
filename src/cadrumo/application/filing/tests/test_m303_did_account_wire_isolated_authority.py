"""Isolated M303 DID account-wire proof against the official 2026 design."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import Modelo, PaymentElection, Period, PriorDomiciliationElection, RefundElection, ResultDisposition
from ....core.resources import bundled_path
from ....domain.calculations.registry import (
    RegistrySnapshotRef,
    bundled_authority,
    extract_record_design,
    load_modelo_directory,
)
from ....domain.deadlines import ChargeAccount, IVARegime, RefundAccount, TaxpayerProfile
from ....domain.filing import ModeloDraft
from ....domain.submission import ModeloDraftStatus
from .. import (
    FilingElectionFacts,
    FilingProducerSnapshotError,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
    render_layout,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_REF = "aeat-dr-303-2026"
_SOURCE_SHA256 = "0be8b156da2250c6b11f6253e0165221ed2e549ec4c65a562021bec6b9b8489b"
_REVISION_ID = "2026-y-siguientes"
_TAXPAYER_TAX_ID = "12345678Z"
_REFUND_IBAN = "GB82WEST12345698765432"
_CHARGE_IBAN = "ES9121000418450200051332"
_LEGAL_REFS = '"ley-37-1992:art-88", "ley-37-1992:art-90", "ley-37-1992:art-91", "ley-37-1992:art-92", "rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"'

_OFFICIAL_DID_ROWS = (
    (1, 1, 2, "An", 'Constante "<T"'),
    (2, 3, 3, "Num", 'Constante "303"'),
    (3, 6, 5, "An", 'Constante "DID00"'),
    (4, 11, 1, "An", 'Constante ">"'),
    (5, 12, 11, "An", "Nota 3"),
    (6, 23, 34, "An", "Nota 3"),
    (7, 57, 70, "An", None),
    (8, 127, 35, "An", None),
    (9, 162, 30, "An", None),
    (10, 192, 2, "An", None),
    (11, 194, 1, "Num", '"0", "1", "2", "3" Nota 2, Nota 3'),
    (12, 195, 617, "An", None),
    (13, 812, 12, "An", 'Constante "</T303DID00>"'),
)


def _field_toml(
    *,
    field_id: str,
    offset: int,
    length: int,
    kind: str,
    data_type: str,
    required: bool,
    padding: str,
    justification: str,
    payload: str = "",
) -> str:
    return f'''\
[[revisions."{_REVISION_ID}".export_layouts.records.fields]]
id = "{field_id}"
offset = {offset}
length = {length}
kind = "{kind}"
{payload}data_type = "{data_type}"
required = {str(required).lower()}
padding = "{padding}"
justification = "{justification}"
signed = false
legal_refs = [{_LEGAL_REFS}]
source_refs = ["{_SOURCE_REF}"]
'''


def _did_layout_toml() -> str:
    return f'''\
[[revisions."{_REVISION_ID}".export_layouts]]
id = "test-owned-m303-did-2026"
format = "fixed_width"
legal_refs = [{_LEGAL_REFS}]
source_refs = ["{_SOURCE_REF}"]

[[revisions."{_REVISION_ID}".export_layouts.records]]
id = "test-owned-m303-page-did"
record_type = "page_did"
order = 1
encoding = "latin-1"
line_ending = "none"
required = true

{_field_toml(field_id="did-open", offset=1, length=2, kind="literal", payload='literal = "<T"\n', data_type="text", required=True, padding="none", justification="none")}
{_field_toml(field_id="did-modelo", offset=3, length=3, kind="literal", payload='literal = "303"\n', data_type="text", required=True, padding="none", justification="none")}
{_field_toml(field_id="did-page", offset=6, length=5, kind="literal", payload='literal = "DID00"\n', data_type="text", required=True, padding="none", justification="none")}
{_field_toml(field_id="did-tag-close", offset=11, length=1, kind="literal", payload='literal = ">"\n', data_type="text", required=True, padding="none", justification="none")}
{_field_toml(field_id="did-swift-bic", offset=12, length=11, kind="header", payload='producer_key = "selected_account.swift_bic"\n', data_type="text", required=False, padding="right_space", justification="left")}
{_field_toml(field_id="did-iban", offset=23, length=34, kind="header", payload='producer_key = "selected_account.iban"\n', data_type="text", required=True, padding="right_space", justification="left")}
{_field_toml(field_id="did-bank-name", offset=57, length=70, kind="header", payload='producer_key = "selected_account.bank_name"\n', data_type="text", required=False, padding="right_space", justification="left")}
{_field_toml(field_id="did-bank-address", offset=127, length=35, kind="header", payload='producer_key = "selected_account.bank_address"\n', data_type="text", required=False, padding="right_space", justification="left")}
{_field_toml(field_id="did-bank-city", offset=162, length=30, kind="header", payload='producer_key = "selected_account.bank_city"\n', data_type="text", required=False, padding="right_space", justification="left")}
{_field_toml(field_id="did-bank-country", offset=192, length=2, kind="header", payload='producer_key = "selected_account.bank_country_code"\n', data_type="text", required=False, padding="right_space", justification="left")}
{_field_toml(field_id="did-sepa", offset=194, length=1, kind="computed", payload='computed_key = "sepa_marca"\n', data_type="text", required=False, padding="left_zero", justification="right")}
{_field_toml(field_id="did-reserved", offset=195, length=617, kind="filler", data_type="text", required=False, padding="right_space", justification="left")}
{_field_toml(field_id="did-close", offset=812, length=12, kind="literal", payload='literal = "</T303DID00>"\n', data_type="text", required=True, padding="none", justification="none")}
'''


def _load_isolated_did_layout(tmp_path: Path):
    source = bundled_authority().catalogues.sources[_SOURCE_REF]
    assert source.sha256 == _SOURCE_SHA256
    parsed = extract_record_design(bundled_path() / source.corpus_path)
    did = next(sheet for sheet in parsed if sheet.name == "DP303DID")
    assert did.total_positions == 823
    assert (
        tuple((field.ordinal, field.offset, field.length, field.type_code, field.content) for field in did.fields)
        == _OFFICIAL_DID_ROWS
    )

    modelo_dir = tmp_path / "registry" / "aeat" / "modelos" / "303"
    revision_dir = modelo_dir / "revisions" / _REVISION_ID
    export_dir = revision_dir / "export"
    export_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(
        f'''\
[modelo]
id = "303"
tax_domain = "iva"
cadence = "quarterly"
jurisdiction = "ES-AEAT"
legal_refs = ["rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"]
source_refs = ["{_SOURCE_REF}"]
''',
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "revision.toml").write_text(
        f'''\
[revisions."{_REVISION_ID}"]
valid_from = 2026-01-01
period_selector = {{ years = [2026], periods = ["1T"] }}
legal_refs = ["rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"]
orden_aplicabilidad = ["orden-eha-3786-2008:art-1"]
source_refs = ["{_SOURCE_REF}"]
''',
        encoding="utf-8",
        newline="\n",
    )
    (export_dir / "0001-did.toml").write_text(_did_layout_toml(), encoding="utf-8", newline="\n")

    modelo = load_modelo_directory(modelo_dir)
    layout = modelo.revisions[_REVISION_ID].export_layouts[0]
    record = layout.records[0]
    assert record.encoding == "latin-1"
    assert record.line_ending == "none"
    assert tuple((field.offset, field.length) for field in record.fields) == tuple(
        (offset, length) for _ordinal, offset, length, _type_code, _content in _OFFICIAL_DID_ROWS
    )
    return layout


def _taxpayer_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAXPAYER_TAX_ID,
        iva_regime=IVARegime.GENERAL,
        iva={
            "refund_account": {
                "iban": _REFUND_IBAN,
                "swift_bic": "DEUTDEFF",
                "bank_name": "Refund Bank",
                "bank_address": "Refund Street 1",
                "bank_city": "Berlin",
                "bank_country_code": "DE",
            },
            "charge_account": {"iban": _CHARGE_IBAN},
        },
    )


def _elections(disposition: ResultDisposition) -> FilingElectionFacts:
    return FilingElectionFacts(
        result_disposition=disposition,
        payment=(
            PaymentElection.DOMICILIACION if disposition is ResultDisposition.DOMICILIACION else PaymentElection.INGRESO
        ),
        refund=RefundElection.DEVOLVER if disposition is ResultDisposition.DEVOLUCION else RefundElection.COMPENSAR,
        prior_domiciliation=PriorDomiciliationElection.KEEP,
    )


def _draft() -> ModeloDraft:
    period = Period.from_year_and_code(2026, "1T")
    timestamp = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    return ModeloDraft(
        draft_id="d" + "0" * 63,
        modelo="303",
        period=period,
        profile_tax_id=_TAXPAYER_TAX_ID,
        subject_tax_id=_TAXPAYER_TAX_ID,
        snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id=_REVISION_ID,
            modelo_year=period.filing_year,
            period=period.registry_token,
        ),
        status=ModeloDraftStatus.APROBADO,
        values=(),
        created_at=timestamp,
        updated_at=timestamp,
        schema_version=f"registry:303:{_REVISION_ID}",
    )


@pytest.mark.parametrize(
    ("disposition", "expected_iban", "unselected_iban", "expected_refund_detail"),
    (
        (ResultDisposition.DEVOLUCION, _REFUND_IBAN, _CHARGE_IBAN, b"DEUTDEFF   "),
        (ResultDisposition.DOMICILIACION, _CHARGE_IBAN, _REFUND_IBAN, b" " * 11),
    ),
)
def test_isolated_m303_did_wire_uses_only_the_snapshot_selected_account(
    tmp_path: Path,
    disposition: ResultDisposition,
    expected_iban: str,
    unselected_iban: str,
    expected_refund_detail: bytes,
) -> None:
    layout = _load_isolated_did_layout(tmp_path)
    taxpayer = _taxpayer_profile()
    iva_profile = taxpayer.iva
    assert iva_profile is not None
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=taxpayer.tax_id,
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None,
            given_name="María",
            surnames="García López",
            full_name="María García López",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Ejemplo"),
        model_profile=iva_profile,
        elections=_elections(disposition),
        amendment_evidence=None,
        refund_account=iva_profile.refund_account,
        charge_account=iva_profile.charge_account,
    )

    wire = render_layout(layout, draft=_draft(), producer_snapshot=snapshot)

    assert len(wire) == 823
    assert wire[:11] == b"<T303DID00>"
    assert wire[11:22] == expected_refund_detail
    assert wire[22:56] == expected_iban.encode("latin-1").ljust(34, b" ")
    assert unselected_iban.encode("latin-1") not in wire
    assert wire[811:] == b"</T303DID00>"


@pytest.mark.parametrize(
    ("disposition", "refund_account", "charge_account", "message"),
    (
        (ResultDisposition.DEVOLUCION, RefundAccount(iban=None), None, "refund account"),
        (ResultDisposition.DOMICILIACION, None, None, "charge account"),
    ),
)
def test_m303_account_bearing_dispositions_refuse_without_their_selected_account(
    disposition: ResultDisposition,
    refund_account: RefundAccount | None,
    charge_account: ChargeAccount | None,
    message: str,
) -> None:
    taxpayer = _taxpayer_profile()
    iva_profile = taxpayer.iva
    assert iva_profile is not None

    with pytest.raises(FilingProducerSnapshotError, match=message):
        build_filing_producer_snapshot(
            modelo=Modelo.M303,
            taxpayer_tax_id=taxpayer.tax_id,
            taxpayer_identity=TaxpayerIdentityFacts(
                legal_name=None,
                given_name="María",
                surnames="García López",
                full_name="María García López",
            ),
            presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Ejemplo"),
            model_profile=iva_profile,
            elections=_elections(disposition),
            amendment_evidence=None,
            refund_account=refund_account,
            charge_account=charge_account,
        )


def test_production_m303_keeps_no_export_layout_until_the_complete_authority_lands() -> None:
    snapshot = bundled_authority().snapshot("303", filing_year=2026, period="1T")

    assert snapshot.revision.export_layouts == ()
