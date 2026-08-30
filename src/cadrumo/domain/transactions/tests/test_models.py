"""Unit tests for transaction models and identity semantics."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core import Art104TresExclusion, ConceptoIngreso, TipoActividad
from ...iva import (
    InputClassification,
    IvaCategory,
    IvaExemptionArticle,
)
from ..enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ..models import (
    ClassificationHistoryEntry,
    DecisionProvenance,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    derive_import_fingerprint,
    derive_movement_day_key,
    derive_transaction_id,
    normalise_movement_reference,
)
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..volumen_ingresos import counts_toward_volumen_de_ingresos

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _sample_raw(
    *,
    provider_id: str = "provider-row-1",
    value_date: date | None = date(2026, 4, 10),
    amount: Decimal = Decimal("123.45"),
    currency: str = "EUR",
    description: str = "Office rent",
    source_row_index: int = 1,
    counterparty: str | None = "Landlord SL",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty=counterparty,
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=source_row_index,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )


def test_provenance_source_path_is_stored_as_basename_only() -> None:
    """An absolute source path is reduced to its basename, leaking no directory."""
    provenance = RawProvenance(
        source_path=Path("/home/alice/private-statements/bank-2026.csv"),
        source_sha256="b" * 64,
        source_row_index=1,
        source_format=SourceFormat.CSV,
        ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        provider_name="CSV provider",
    )
    assert provenance.source_path == Path("bank-2026.csv")
    serialised = provenance.model_dump_json()
    assert "alice" not in serialised
    assert "private-statements" not in serialised


def test_provenance_basename_survives_rehydration_unchanged() -> None:
    """Re-validating a persisted bare filename is a no-op (no cross-OS mutation).

    The prior ``.resolve()`` validator re-anchored the path on every load, so a
    POSIX-authored bundle imported on Windows mutated the stored value and broke
    strict roundtrip equality. The basename is platform-neutral and idempotent.
    """
    original = RawProvenance(
        source_path=Path("/var/data/movements.csv"),
        source_sha256="c" * 64,
        source_row_index=3,
        source_format=SourceFormat.CSV,
        ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        provider_name="CSV provider",
    )
    rehydrated = RawProvenance.model_validate_json(original.model_dump_json())
    assert rehydrated == original
    assert rehydrated.source_path == Path("movements.csv")


def test_transaction_id_hash_is_stable_for_same_identity_tuple() -> None:
    """Equal identity tuples must derive the same transaction ID."""
    raw_a = _sample_raw(source_row_index=1, counterparty="First counterparty")
    raw_b = _sample_raw(source_row_index=99, counterparty="Second counterparty")

    tx_a = Transaction.model_validate(
        {"raw": raw_a, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )
    tx_b = Transaction.model_validate(
        {"raw": raw_b, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )

    assert tx_a.transaction_id == tx_b.transaction_id


def test_direction_enum_round_trips_through_json() -> None:
    """TransactionDirection must survive a JSON round-trip."""
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INTERNAL_TRANSFER,
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.direction is TransactionDirection.INTERNAL_TRANSFER


def test_business_pct_is_only_allowed_for_mixed_transactions() -> None:
    """business_pct must be constrained to MIXED transactions in the 0..1 range."""
    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="x" * 64,
            raw=_sample_raw(),
            direction=TransactionDirection.OUTGOING,
            group_label=None,
            source_jurisdiction="ES",
            business_classification=BusinessClassification.BUSINESS,
            business_pct=Decimal("0.2"),
        )

    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="x" * 64,
            raw=_sample_raw(),
            direction=TransactionDirection.OUTGOING,
            group_label=None,
            source_jurisdiction="ES",
            business_classification=BusinessClassification.MIXED,
            business_pct=Decimal("1.2"),
        )

    mixed = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.MIXED,
            "business_pct": Decimal("0.5"),
        },
    )

    assert mixed.business_pct == Decimal("0.5")


def test_transaction_tax_fields_are_typed_and_round_trip_through_json() -> None:
    """Manual ledger tax fields must be first-class transaction attributes."""

    original = Transaction.model_validate(
        {
            # Gross 121.00 reconstitutes the 100.00 base + 21.00 IVA triple
            # (the gross == base + iva consistency invariant on Transaction).
            "raw": _sample_raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "office-supplies",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "irpf_category": "actividad_economica",
            "usage_ratio_id": "ratio-office",
            "prorrata_reference": "prorrata-2026",
            "purchase_invoice_evidence_id": "purchase-evidence-1",
            "attachment_ids": ("attachment-1",),
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored.taxable_base == Decimal("100.00")
    assert restored.iva_rate == Decimal("0.21")
    assert restored.iva_amount == Decimal("21.00")
    assert restored.irpf_category == "actividad_economica"
    assert restored.usage_ratio_id == "ratio-office"
    assert restored.prorrata_reference == "prorrata-2026"
    assert restored.purchase_invoice_evidence_id == "purchase-evidence-1"
    assert restored.attachment_ids == ("attachment-1",)


def test_transaction_json_roundtrip_preserves_non_default_fields_and_derived_id() -> None:
    raw = _sample_raw(amount=Decimal("121.00"), description="Consulting invoice")
    original = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": "Client A",
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.MIXED,
            "business_pct": Decimal("0.50"),
            "category_id": "professional-services",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "irpf_category": "actividad_economica",
            "usage_ratio_id": "ratio-office",
            "prorrata_reference": "prorrata-2026",
            "purchase_invoice_evidence_id": "purchase-evidence-1",
            "attachment_ids": ("attachment-1",),
            "classified_by": "manual",
            "classification_reason": "operator classified from invoice evidence",
            "classification_confidence": Decimal("1.00"),
            "created_by": "operator-A",
            "source_command": "aeat ledger add",
            "created_event_id": "c" * 64,
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert original.transaction_id == derive_transaction_id(raw)
    assert restored == original
    assert restored.transaction_id == derive_transaction_id(restored.raw)
    assert restored.business_classification is BusinessClassification.MIXED
    assert restored.business_pct == Decimal("0.50")
    assert restored.group_label == "Client A"
    assert restored.classification_confidence == Decimal("1.00")
    assert restored.attachment_ids == ("attachment-1",)


def test_transaction_json_rejects_tampered_derived_id_in_storage_payload() -> None:
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("121.00"), description="Consulting invoice"),
            "direction": TransactionDirection.OUTGOING,
            "group_label": "Client A",
            "source_jurisdiction": "ES",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
        },
    )
    storage_payload = json.loads(original.model_dump_json())
    storage_payload["transaction_id"] = "0" * 64

    with pytest.raises(ValidationError, match="transaction_id must match"):
        Transaction.model_validate_json(json.dumps(storage_payload))


def test_art_104_tres_exclusion_roundtrips_for_judgment_exclusion() -> None:
    """A judgment art. 104.Tres exclusion tag survives a strict JSON save/load cycle.

    The field is populated with a NON-default judgment member so a
    save-drops-field / load-re-defaults-field regression cannot hide behind the
    ``None`` default.
    """
    raw = _sample_raw(amount=Decimal("5000.00"), description="Venta inmueble no habitual")
    original = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "art_104_tres_exclusion": Art104TresExclusion.NON_HABITUAL_REAL_ESTATE_OR_FINANCIAL,
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.art_104_tres_exclusion is Art104TresExclusion.NON_HABITUAL_REAL_ESTATE_OR_FINANCIAL


def test_concepto_ingreso_roundtrips_for_an_excluded_concept() -> None:
    """A declared income concept survives a strict JSON save/load cycle.

    Populated with the member that CHANGES the calculation -- a subvención de capital,
    which art. 110.1.c) removes from the volume base -- rather than with ``ORDINARIO``,
    which behaves like the ``None`` default and would prove nothing about persistence.
    """
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("9000.00"), description="Subvencion PAC de capital"),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "tipo_actividad": TipoActividad.B01_AGRICOLA,
            "concepto_ingreso": ConceptoIngreso.SUBVENCION_CAPITAL,
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.concepto_ingreso is ConceptoIngreso.SUBVENCION_CAPITAL


def test_concepto_ingreso_dropped_from_the_payload_surfaces_as_inequality() -> None:
    """Anti-tautology proof, and the one where the default is dangerous.

    Losing this field does not merely lose a label: ``None`` means INCLUDED, so a
    dropped ``SUBVENCION_CAPITAL`` silently pulls an excluded receipt back into the
    volume base and over-declares. The field is optional, so nothing raises -- which is
    exactly why the deletion has to be caught as inequality rather than trusted to fail
    loudly on its own.
    """
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("9000.00"), description="Subvencion PAC de capital"),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "concepto_ingreso": ConceptoIngreso.SUBVENCION_CAPITAL,
        },
    )
    storage_payload = json.loads(original.model_dump_json())
    del storage_payload["concepto_ingreso"]

    restored = Transaction.model_validate_json(json.dumps(storage_payload))

    assert restored != original
    assert restored.concepto_ingreso is None
    assert counts_toward_volumen_de_ingresos(restored.concepto_ingreso)
    assert not counts_toward_volumen_de_ingresos(original.concepto_ingreso)


def test_concepto_ingreso_rejects_a_token_outside_the_closed_set() -> None:
    """A persisted payload carrying an unknown income concept is refused at load."""
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("9000.00"), description="Subvencion PAC de capital"),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "concepto_ingreso": ConceptoIngreso.SUBVENCION_CAPITAL,
        },
    )
    storage_payload = json.loads(original.model_dump_json())
    storage_payload["concepto_ingreso"] = "subvencion_qualquiera"

    with pytest.raises(ValidationError):
        Transaction.model_validate_json(json.dumps(storage_payload))


def test_tipo_actividad_roundtrips_for_a_declared_activity() -> None:
    """A declared Modelo 036 activity code survives a strict JSON save/load cycle.

    Populated with a NON-default member so a save-drops-field /
    load-re-defaults-field regression cannot hide behind the ``None`` default.
    """
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("1800.00"), description="Venta de cosecha"),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "tipo_actividad": TipoActividad.B01_AGRICOLA,
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.tipo_actividad is TipoActividad.B01_AGRICOLA


def test_tipo_actividad_dropped_from_the_payload_surfaces_as_inequality() -> None:
    """Anti-tautology proof: deleting the persisted code is DETECTED, not defaulted away.

    The field is optional, so a dropped value re-defaults to ``None`` rather than
    raising -- which is exactly the regression shape a roundtrip test can miss.
    Removing the key from the payload must therefore surface as strict inequality;
    if this assertion ever held with the field silently restored, the roundtrip
    above would be proving nothing.
    """
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("1800.00"), description="Venta de cosecha"),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "tipo_actividad": TipoActividad.B01_AGRICOLA,
        },
    )
    storage_payload = json.loads(original.model_dump_json())
    del storage_payload["tipo_actividad"]

    restored = Transaction.model_validate_json(json.dumps(storage_payload))

    assert restored != original
    assert restored.tipo_actividad is None


def test_tipo_actividad_rejects_a_token_outside_the_modelo_036_table() -> None:
    """A persisted payload carrying an unknown activity code is refused at load."""
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("1800.00"), description="Venta de cosecha"),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "tipo_actividad": TipoActividad.B01_AGRICOLA,
        },
    )
    storage_payload = json.loads(original.model_dump_json())
    storage_payload["tipo_actividad"] = "Z99"

    with pytest.raises(ValidationError):
        Transaction.model_validate_json(json.dumps(storage_payload))


def test_art_104_tres_exclusion_rejects_auto_derived_operator_tag() -> None:
    """An auto-derived art. 104.Tres member is refused as an operator transaction tag."""
    with pytest.raises(ValidationError, match="art_104_tres_exclusion is operator-declared only"):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "art_104_tres_exclusion": Art104TresExclusion.NON_SUBJECT_ART_7,
            },
        )


def test_art_104_tres_exclusion_rejects_tampered_auto_derived_value_on_load() -> None:
    """A persisted payload mutated to an auto-derived member is refused at load.

    Anti-tautology proof: the operator-declared-only invariant fires on the
    load path, not only at construction, so a corrupted on-disk value cannot
    silently mis-scope the prorrata denominator.
    """
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("5000.00"), description="Venta inmueble no habitual"),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "art_104_tres_exclusion": Art104TresExclusion.FOREIGN_PERMANENT_ESTABLISHMENT,
        },
    )
    storage_payload = json.loads(original.model_dump_json())
    storage_payload["art_104_tres_exclusion"] = Art104TresExclusion.DIRECT_IVA_CUOTAS.value

    with pytest.raises(ValidationError, match="art_104_tres_exclusion is operator-declared only"):
        Transaction.model_validate_json(json.dumps(storage_payload))


def test_input_classification_roundtrips_for_especial_common_use() -> None:
    """The operator-declared LIVA art. 106 input_classification survives a strict JSON cycle.

    The field is populated with a NON-default member so a save-drops / load-re-defaults
    regression cannot hide behind the ``None`` default.
    """
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("121.00"), description="Compra de uso comun"),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "input_classification": InputClassification.COMMON,
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.input_classification is InputClassification.COMMON


def test_input_classification_rejects_unknown_member_on_load() -> None:
    """A persisted payload mutated to a non-member input_classification is refused at load."""
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("121.00"), description="Compra exclusiva deducible"),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "input_classification": InputClassification.EXCLUSIVELY_DEDUCTIBLE,
        },
    )
    storage_payload = json.loads(original.model_dump_json())
    storage_payload["input_classification"] = "not_a_real_classification"

    with pytest.raises(ValidationError):
        Transaction.model_validate_json(json.dumps(storage_payload))


def test_prorrata_sector_id_roundtrips_for_declared_sector() -> None:
    """The operator-declared LIVA arts. 9.1.c/101 sector reference survives a strict JSON cycle.

    The field is populated with a NON-default sector id so a save-drops / load-re-defaults
    regression cannot hide behind the ``None`` (common-use / whole-entity) default.
    """
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("242.00"), description="Compra sector arrendamiento"),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "prorrata_sector_id": "arrendamiento",
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.prorrata_sector_id == "arrendamiento"


def test_prorrata_sector_id_rejects_blank_value_on_load() -> None:
    """A persisted payload mutated to an empty prorrata_sector_id is refused at load.

    Anti-tautology: the ``min_length=1`` constraint fires on the load path, not
    only at construction, so a corrupted on-disk empty string cannot silently
    masquerade as a declared sector (which would mis-route the deducible cuota).
    """
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("242.00"), description="Compra sector arrendamiento"),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "prorrata_sector_id": "arrendamiento",
        },
    )
    storage_payload = json.loads(original.model_dump_json())
    storage_payload["prorrata_sector_id"] = ""

    with pytest.raises(ValidationError):
        Transaction.model_validate_json(json.dumps(storage_payload))


def test_transaction_exemption_article_round_trips_for_domestic_exempt_category() -> None:
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "iva_category": IvaCategory.DOMESTIC_EXEMPT,
            "exemption_article": IvaExemptionArticle.ART_20_UNO_8,
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.iva_category is IvaCategory.DOMESTIC_EXEMPT
    assert restored.exemption_article is IvaExemptionArticle.ART_20_UNO_8


def test_transaction_rejects_exemption_article_without_domestic_exempt_category() -> None:
    for iva_category in (None, IvaCategory.DOMESTIC_GENERAL):
        payload: dict[str, object] = {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "exemption_article": IvaExemptionArticle.ART_20_UNO_8,
        }
        if iva_category is not None:
            payload["iva_category"] = iva_category

        with pytest.raises(ValidationError, match="exemption_article"):
            Transaction.model_validate(payload)


def test_transaction_lineage_fields_are_typed_and_round_trip_through_json() -> None:
    """Evidence provenance and edit lineage must stay on the transaction payload."""

    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "created_by": "operator-A",
            "source_command": "aeat app ledger add",
            "created_event_id": "c" * 64,
            "purchase_invoice_evidence_id": "purchase-evidence-1",
            "attachment_ids": ("a" * 64,),
            "evidence_provenance": (
                {
                    "evidence_id": "purchase-evidence-1",
                    "evidence_kind": "purchase_invoice_evidence",
                    "actor": "operator-A",
                    "source_command": "aeat app ledger add",
                    "linked_at": datetime(2026, 4, 14, 10, 0, tzinfo=UTC),
                    "bucket_event_id": "c" * 64,
                },
            ),
            "edit_lineage": (
                {
                    "previous_transaction_id": "b" * 64,
                    "actor": "operator-B",
                    "source_command": "aeat app ledger update",
                    "edited_at": datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
                    "bucket_event_id": "d" * 64,
                },
            ),
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored.created_by == "operator-A"
    assert restored.source_command == "aeat app ledger add"
    assert restored.created_event_id == "c" * 64
    assert restored.evidence_provenance[0].evidence_kind == "purchase_invoice_evidence"
    assert restored.evidence_provenance[0].actor == "operator-A"
    assert restored.edit_lineage[0].previous_transaction_id == "b" * 64
    assert restored.edit_lineage[0].actor == "operator-B"


def test_transaction_lifecycle_lineage_round_trips_through_json() -> None:
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "lifecycle_state": TransactionLifecycleState.ARCHIVED,
            "lifecycle_lineage": (
                {
                    "previous_state": TransactionLifecycleState.ACTIVE,
                    "state": TransactionLifecycleState.ARCHIVED,
                    "actor": "operator-A",
                    "source_command": "aeat app ledger archive",
                    "changed_at": datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
                    "reason": "wrong account import",
                    "bucket_event_id": "e" * 64,
                },
            ),
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored.lifecycle_state is TransactionLifecycleState.ARCHIVED
    assert restored.lifecycle_lineage[0].previous_state is TransactionLifecycleState.ACTIVE
    assert restored.lifecycle_lineage[0].state is TransactionLifecycleState.ARCHIVED
    assert restored.lifecycle_lineage[0].reason == "wrong account import"
    assert restored.lifecycle_lineage[0].bucket_event_id == "e" * 64


def test_transaction_lifecycle_lineage_rejects_noop_transition() -> None:
    with pytest.raises(ValidationError, match="lifecycle transition must change state"):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "lifecycle_state": TransactionLifecycleState.ACTIVE,
                "lifecycle_lineage": (
                    {
                        "previous_state": TransactionLifecycleState.ACTIVE,
                        "state": TransactionLifecycleState.ACTIVE,
                        "actor": "operator-A",
                        "source_command": "aeat app ledger archive",
                        "changed_at": datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
                    },
                ),
            },
        )


def test_transaction_tax_fields_reject_negative_values_and_legacy_multi_purchase_evidence() -> None:
    """Tax substrate values and evidence refs must fail at the domain boundary."""

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "taxable_base": Decimal("-1.00"),
            },
        )

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "purchase_invoice_evidence_id": ("evidence-1", "evidence-2"),
            },
        )


def test_classified_by_accepts_only_whitelisted_shapes() -> None:
    """classified_by must be auto, manual, or rule:<rule-id>."""
    for classified_by in ("auto", "manual", "rule:vendor-map", "derived:iva-category"):
        transaction = Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "classified_by": classified_by,
            },
        )
        assert transaction.classified_by == classified_by

    for classified_by in ("rule:", "derived:", "bot"):
        with pytest.raises(ValidationError):
            Transaction.model_validate(
                {
                    "raw": _sample_raw(),
                    "direction": TransactionDirection.INCOMING,
                    "group_label": None,
                    "source_jurisdiction": "ES",
                    "classified_by": classified_by,
                },
            )


def test_business_classification_rejects_unclassified_literal() -> None:
    """`BusinessClassification("UNCLASSIFIED")` must raise."""
    with pytest.raises(ValueError):
        BusinessClassification("UNCLASSIFIED")


def test_classification_history_entry_round_trips_through_json() -> None:
    """`ClassificationHistoryEntry` must survive JSON round-trip with reserved slots."""
    entry = ClassificationHistoryEntry(
        business_classification=BusinessClassification.BUSINESS,
        classified_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
        classified_by="manual",
        reason="client invoice",
    )
    restored = ClassificationHistoryEntry.model_validate_json(entry.model_dump_json())
    assert restored == entry
    assert restored.confidence is None
    assert restored.provenance is None


def test_classification_history_entry_round_trips_typed_decision_provenance() -> None:
    """A populated typed `DecisionProvenance` must survive the JSON boundary intact."""
    entry = ClassificationHistoryEntry(
        business_classification=BusinessClassification.BUSINESS,
        classified_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
        classified_by="manual",
        reason="operator override of the rule engine",
        confidence=Decimal("0.85"),
        provenance=DecisionProvenance(
            decided_by="rule:utilities-v2",
            decided_at=datetime(2026, 4, 18, 8, 30, tzinfo=UTC),
            reason="matched recurring utilities pattern",
            confidence=Decimal("0.62"),
            manual_override=True,
        ),
    )
    restored = ClassificationHistoryEntry.model_validate_json(entry.model_dump_json())
    assert restored == entry
    assert isinstance(restored.provenance, DecisionProvenance)
    assert restored.provenance.decided_by == "rule:utilities-v2"
    assert restored.provenance.confidence == Decimal("0.62")
    assert restored.provenance.manual_override is True


def test_decision_provenance_rejects_bare_dict_payload() -> None:
    """Anti-tautology: a malformed provenance payload must be refused, not silently coerced."""
    payload = json.loads(
        ClassificationHistoryEntry(
            business_classification=BusinessClassification.BUSINESS,
            classified_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
            classified_by="manual",
            provenance=DecisionProvenance(
                decided_by="manual",
                decided_at=datetime(2026, 4, 18, 8, 30, tzinfo=UTC),
            ),
        ).model_dump_json()
    )
    # Corrupt the on-wire provenance: drop the mandatory decided_at.
    del payload["provenance"]["decided_at"]
    with pytest.raises(ValidationError):
        ClassificationHistoryEntry.model_validate(payload)


# ---------------------------------------------------------------------------
# Cross-format / post-edit import-dedup fingerprint
# ---------------------------------------------------------------------------


def _ofx_sample_raw(*, provider_id: str, description: str = "Office rent") -> RawTransaction:
    """Return a sample row tagged as an OFX export of the same movement."""
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("123.45"),
        currency="EUR",
        counterparty="Landlord SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.OFX,
            ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            provider_name="OFX provider",
        ),
        raw_fields={"MEMO": description},
    )


def test_import_fingerprint_ignores_provider_id_and_file_format() -> None:
    """The same movement exported by two providers shares one fingerprint.

    `derive_import_fingerprint` keys on the movement identity (date,
    amount, currency, direction, normalised narrative) — not on the
    provider-assigned id or the source file format — so an OFX export
    and a CSV export of the same bank movement deduplicate against each
    other.
    """
    ofx_row = _ofx_sample_raw(provider_id="ofx-fitid-1")
    csv_row = _sample_raw(provider_id="csv-row-7")

    assert derive_import_fingerprint(ofx_row, direction=TransactionDirection.OUTGOING) == derive_import_fingerprint(
        csv_row,
        direction=TransactionDirection.OUTGOING,
    )
    # The legacy transaction id still diverges — it folds in the
    # provider id — which is exactly why a coarser dedup key is needed.
    assert derive_transaction_id(ofx_row) != derive_transaction_id(csv_row)


def test_import_fingerprint_normalises_accents_and_punctuation() -> None:
    """Narratives differing only in accents / casing / punctuation match."""
    accented = _sample_raw(description="Reunió de negòcis - Òscar")
    plain = _sample_raw(description="reunio  de negocis: oscar")

    assert derive_import_fingerprint(accented, direction=TransactionDirection.OUTGOING) == derive_import_fingerprint(
        plain,
        direction=TransactionDirection.OUTGOING,
    )


def test_import_fingerprint_distinguishes_genuinely_different_movements() -> None:
    """A different amount, date, currency, or direction produces a different fingerprint."""
    base = _sample_raw()
    other_amount = _sample_raw(amount=Decimal("999.99"))
    other_date = _sample_raw(value_date=date(2026, 4, 11))
    other_currency = _sample_raw(currency="USD")

    base_fingerprint = derive_import_fingerprint(base, direction=TransactionDirection.OUTGOING)
    assert base_fingerprint != derive_import_fingerprint(other_amount, direction=TransactionDirection.OUTGOING)
    assert base_fingerprint != derive_import_fingerprint(other_date, direction=TransactionDirection.OUTGOING)
    assert base_fingerprint != derive_import_fingerprint(other_currency, direction=TransactionDirection.OUTGOING)
    assert base_fingerprint != derive_import_fingerprint(base, direction=TransactionDirection.INCOMING)


def test_movement_day_key_groups_same_date_and_amount() -> None:
    """The coarse day key matches on date + amount regardless of narrative."""
    a = _sample_raw(description="Transferencia 1")
    b = _sample_raw(description="Pago cliente nota 4471")

    assert derive_movement_day_key(a) == derive_movement_day_key(b)
    assert derive_movement_day_key(a) != derive_movement_day_key(_sample_raw(amount=Decimal("1.00")))


def test_normalise_movement_reference_strips_accents_case_and_noise() -> None:
    """The reference normaliser collapses accents, casing, and punctuation."""
    assert normalise_movement_reference("Compra à material  ÒSCAR!") == "compraamaterialoscar"
    assert normalise_movement_reference("a-b_c") == "abc"


# ---------------------------------------------------------------------------
# source_jurisdiction axis (Spanish-source vs foreign-source)
# ---------------------------------------------------------------------------


def test_source_jurisdiction_validation_and_json_roundtrip() -> None:
    """Rows must carry a nullable ISO alpha-2 source-jurisdiction axis."""
    for raw_value, expected in (("ES", "ES"), (None, None), (" FR ", "FR")):
        original = Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "source_jurisdiction": raw_value,
            },
        )
        restored = Transaction.model_validate_json(original.model_dump_json())

        assert restored == original
        assert restored.source_jurisdiction == expected

    with pytest.raises(ValidationError, match="Field required"):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
            },
        )

    for invalid in ("INVALID", "es", "E1", "E", "ESP", "  "):
        with pytest.raises(ValidationError):
            Transaction.model_validate(
                {
                    "raw": _sample_raw(),
                    "direction": TransactionDirection.INCOMING,
                    "group_label": None,
                    "source_jurisdiction": invalid,
                },
            )


def test_group_label_is_required_but_nullable() -> None:
    """Rows must carry the grouping key, while explicit ungrouped remains valid."""
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )
    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.group_label is None
    with pytest.raises(ValidationError, match="Field required"):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.INCOMING,
                "source_jurisdiction": "ES",
            },
        )


def test_dict_mode_model_validate_accepts_json_shaped_dict_values() -> None:
    """A strict-mode ``model_validate`` call accepts JSON-shaped strings too.

    ``Transaction`` is strict-mode, but a python-mode ``dict`` (real
    enum/``Decimal``/``date`` instances, as ``model_dump(mode="python")``
    produces) and a JSON-decoded ``dict`` (string stand-ins for those types,
    as ``model_dump(mode="json")`` or a deserialised storage payload
    produces) are BOTH valid ``model_validate`` inputs -- neither is a
    second-class caller. Field-level ``mode="before"`` coercions on the
    affected fields (enum/Decimal/datetime/the nested ``raw`` record) bridge
    the JSON-shaped case without a model-level re-route: a model-level
    ``mode="before"`` that re-dispatched to ``model_validate_json`` would
    recurse forever, because ``model_validate_json`` re-decodes to a plain
    dict and re-runs every model-level ``mode="before"`` validator on that
    still string-shaped dict before applying the rest of the schema.
    """
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "group_label": None,
            "source_jurisdiction": "ES",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
        },
    )

    json_shaped_dict = original.model_dump(mode="json")
    assert isinstance(json_shaped_dict["direction"], str)
    assert isinstance(json_shaped_dict["taxable_base"], str)
    assert isinstance(json_shaped_dict["raw"]["booked_date"], str)

    restored = Transaction.model_validate(json_shaped_dict)
    assert restored == original
    assert restored.direction is TransactionDirection.INCOMING
    assert restored.business_classification is BusinessClassification.BUSINESS
    assert restored.taxable_base == Decimal("100.00")

    restored_via_json = Transaction.model_validate_json(json.dumps(json_shaped_dict))
    assert restored_via_json == original


def test_dict_mode_model_validate_still_rejects_genuinely_malformed_payload() -> None:
    """The JSON-shaped-dict coercion must not launder a truly invalid payload."""
    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": "NOT_A_REAL_DIRECTION",
                "group_label": None,
                "source_jurisdiction": "ES",
                "created_at": "not-a-real-timestamp",
            },
        )


def test_python_mode_dict_with_real_instances_round_trips() -> None:
    """A genuine python-mode dict (as ``model_dump(mode="python")`` produces) validates directly.

    ``model_dump(mode="python")`` always flattens a nested ``BaseModel`` field
    (``raw``) to a plain ``dict``, even in python mode; the leaf scalar values
    inside it (``Decimal``, ``date``, enums) stay their real Python types
    rather than JSON-string stand-ins, which is what strict-mode
    ``model_validate`` accepts for a nested model field.
    """
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )
    python_mode_dict = original.model_dump(mode="python")
    assert isinstance(python_mode_dict["direction"], TransactionDirection)
    assert isinstance(python_mode_dict["raw"]["booked_date"], date)
    assert isinstance(python_mode_dict["raw"]["amount"], Decimal)

    restored = Transaction.model_validate(python_mode_dict)

    assert restored == original


def test_out_of_window_transaction_summary_carries_no_decrypted_field() -> None:
    """The diagnostics-only summary is structurally incapable of leaking decrypted facts.

    ``OutOfWindowTransactionSummary`` collapses N out-of-window
    ``OutOfWindowTransactionIndexEntry`` rows into one summary carrying ONLY the
    excluded-row count and the filing-date span. This pins that guarantee
    structurally -- the declared field set is exactly
    ``{count, min_filing_date, max_filing_date}`` -- so a future field
    addition (amount, counterparty, category, direction, business
    classification, or any other decrypted transaction fact) is a loud
    model-shape test failure, not a silent contract erosion.
    """
    assert set(OutOfWindowTransactionSummary.model_fields) == {
        "count",
        "min_filing_date",
        "max_filing_date",
    }

    index_entries = (
        OutOfWindowTransactionIndexEntry(transaction_id="a" * 64, filing_date=date(2026, 1, 5)),
        OutOfWindowTransactionIndexEntry(transaction_id="b" * 64, filing_date=date(2026, 3, 20)),
        OutOfWindowTransactionIndexEntry(transaction_id="c" * 64, filing_date=date(2026, 2, 1)),
    )
    summary = OutOfWindowTransactionSummary.from_index_entries(index_entries)

    assert summary is not None
    assert summary.count == 3
    assert summary.min_filing_date == date(2026, 1, 5)
    assert summary.max_filing_date == date(2026, 3, 20)
    assert summary.model_dump().keys() == {"count", "min_filing_date", "max_filing_date"}


def test_out_of_window_transaction_summary_is_none_for_empty_index_entries() -> None:
    """An empty out-of-window set collapses to ``None``, not a zero-count summary."""
    assert OutOfWindowTransactionSummary.from_index_entries(()) is None
