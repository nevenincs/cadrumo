"""Modelo 347 extractors — Operaciones con terceros (>= 3005.06 EUR)."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

from .....domain.modelos.m347 import ClaveOperacion, Modelo347RecordLine
from .._generic_extractor import GenericDeclaracionExtractor
from .._parsers import extract_pages_text
from .._schema import DeclaracionFiling, TemplateRevision

_DETAIL_RE = re.compile(r"^M347-RECORD\s*\|\s*(?P<body>.+)$", re.MULTILINE)
_HUMAN_DETAIL_RE = re.compile(
    r"^Declarado\s+"
    r"(?P<nif>[0-9A-Z][0-9A-Z -]{6,15})\s+"
    r"(?P<name>.+?)\s+"
    r"Clave\s+(?P<key>[A-G])\s+"
    r"Total\s+(?P<total>-?[0-9]+(?:\.[0-9]{2})?)\s+"
    r"1T\s+(?P<q1>-?[0-9]+(?:\.[0-9]{2})?)\s+"
    r"2T\s+(?P<q2>-?[0-9]+(?:\.[0-9]{2})?)\s+"
    r"3T\s+(?P<q3>-?[0-9]+(?:\.[0-9]{2})?)\s+"
    r"4T\s+(?P<q4>-?[0-9]+(?:\.[0-9]{2})?)"
    r"(?:\s+Metalico\s+(?P<cash>-?[0-9]+(?:\.[0-9]{2})?)\s+Origen\s+(?P<cash_year>[0-9]{4}))?"
    r"\s*$",
    re.MULTILINE,
)
_AMOUNT_FIELDS = {
    "annual_operation_amount",
    "first_quarter_amount",
    "second_quarter_amount",
    "third_quarter_amount",
    "fourth_quarter_amount",
    "cash_received_amount",
    "real_estate_transmission_amount",
    "first_quarter_real_estate_transmission_amount",
    "second_quarter_real_estate_transmission_amount",
    "third_quarter_real_estate_transmission_amount",
    "fourth_quarter_real_estate_transmission_amount",
    "cash_accounting_annual_amount",
}

_FIELD_ALIASES = {
    "RECORD_TYPE": "record_type",
    "MODELO": "modelo",
    "EJERCICIO": "ejercicio",
    "DECLARANT_NIF": "declarant_tax_id",
    "NIF": "declared_tax_id",
    "EU_VAT": "eu_vat_operator_id",
    "NAME": "declared_name",
    "KEY": "operation_key",
    "TOTAL": "annual_operation_amount",
    "Q1": "first_quarter_amount",
    "Q2": "second_quarter_amount",
    "Q3": "third_quarter_amount",
    "Q4": "fourth_quarter_amount",
    "PROVINCE": "province_code",
    "COUNTRY": "country_code",
    "REPRESENTATIVE": "representative_tax_id",
    "INSURANCE": "insurance_operation",
    "RENTAL": "business_premises_rental",
    "CASH": "cash_received_amount",
    "CASH_YEAR": "cash_origin_year",
    "REAL_ESTATE": "real_estate_transmission_amount",
    "RE_Q1": "first_quarter_real_estate_transmission_amount",
    "RE_Q2": "second_quarter_real_estate_transmission_amount",
    "RE_Q3": "third_quarter_real_estate_transmission_amount",
    "RE_Q4": "fourth_quarter_real_estate_transmission_amount",
    "CASH_ACCOUNTING_IVA": "cash_accounting_iva",
    "REVERSE_CHARGE": "reverse_charge_operation",
    "NON_CUSTOMS_DEPOSIT": "non_customs_deposit_operation",
    "CASH_ACCOUNTING_TOTAL": "cash_accounting_annual_amount",
    "BDNS": "bdns_call_number",
    "CCAA": "autonomous_community_code",
}
_BOOL_FIELDS = {
    "insurance_operation",
    "business_premises_rental",
    "cash_accounting_iva",
    "reverse_charge_operation",
    "non_customs_deposit_operation",
}
_INT_FIELDS = {"ejercicio", "cash_origin_year"}


class Modelo347V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 347 tax year 2025 (periodo 0A)."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="347",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "01",  # Nº total de declarados
        "02",  # Importe total anual de operaciones declaradas
        "03",  # Nº total registros por cobros en metálico
        "04",  # Importe total cobros en metálico
    )

    def extract(self, pdf_path: Path) -> DeclaracionFiling:
        filing = super().extract(pdf_path)
        full_text = "\n".join(extract_pages_text(pdf_path))
        records = tuple(_parse_detail_records(full_text))
        return filing.model_copy(update={"modelo_347_records": records})


class Modelo347V2024Extractor(Modelo347V2025Extractor):
    """Concrete extractor for Modelo 347 tax year 2024."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="347",
        año=2024,
        revision="2024.01",
    )


class Modelo347V2026Extractor(Modelo347V2025Extractor):
    """Concrete extractor for Modelo 347 tax year 2026."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="347",
        año=2026,
        revision="2026.01",
    )


def _parse_detail_records(text: str) -> list[Modelo347RecordLine]:
    records: list[Modelo347RecordLine] = []
    for match in _DETAIL_RE.finditer(text):
        records.append(_record_from_fields(_split_detail_fields(match.group("body"))))
    for match in _HUMAN_DETAIL_RE.finditer(text):
        raw_fields = {
            "NIF": match.group("nif"),
            "NAME": match.group("name"),
            "KEY": match.group("key"),
            "TOTAL": match.group("total"),
            "Q1": match.group("q1"),
            "Q2": match.group("q2"),
            "Q3": match.group("q3"),
            "Q4": match.group("q4"),
            "CASH": match.group("cash") or "0.00",
            "CASH_YEAR": match.group("cash_year") or "",
        }
        records.append(_record_from_fields(raw_fields))
    return records


def _record_from_fields(raw_fields: dict[str, str]) -> Modelo347RecordLine:
    parsed: dict[str, object] = {}
    for raw_key, raw_value in raw_fields.items():
        field_name = _FIELD_ALIASES.get(raw_key.upper())
        if field_name is None:
            continue
        value = raw_value.strip()
        if value == "":
            continue
        if field_name in _AMOUNT_FIELDS:
            parsed[field_name] = Decimal(value)
        elif field_name in _BOOL_FIELDS:
            parsed[field_name] = value.upper() in {"1", "Y", "YES", "S", "SI", "TRUE", "X"}
        elif field_name in _INT_FIELDS:
            parsed[field_name] = int(value)
        elif field_name == "operation_key":
            parsed[field_name] = ClaveOperacion(value.upper())
        else:
            parsed[field_name] = value
    return Modelo347RecordLine.model_validate(parsed)


def _split_detail_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in body.split("|"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields[key.strip()] = value.strip()
    return fields


__all__ = ["Modelo347V2024Extractor", "Modelo347V2025Extractor", "Modelo347V2026Extractor"]
