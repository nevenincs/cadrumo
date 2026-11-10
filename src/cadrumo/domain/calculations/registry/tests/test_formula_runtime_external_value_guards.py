"""External binding value guards and registry path/code tokens."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from .....core.casilla_id import validated_casilla_id
from ..errors import RegistryValidationError
from ..formula_runtime_ops import reject_non_decimal, reject_non_string
from ..irnr_ledger_bindings import LedgerIrnrIncomeProvider
from ..schema_references import SourceReference

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_reject_non_decimal_accepts_finite_decimals() -> None:
    reject_non_decimal({"a": Decimal("0"), "b": Decimal("-12.50")}, "binding")


@pytest.mark.parametrize(
    "bad",
    [1.5, 1, True, "1.0", Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")],
)
def test_reject_non_decimal_refuses_non_decimal_and_non_finite(bad: object) -> None:
    with pytest.raises(RegistryValidationError, match="binding 'a'"):
        reject_non_decimal(cast("Mapping[str, Decimal]", {"a": bad}), "binding")


def test_reject_non_string_refuses_empty_and_non_str() -> None:
    reject_non_string({"a": "x"}, "enum_binding")
    for bad in ("", 3, b"x", None):
        with pytest.raises(RegistryValidationError, match="enum_binding"):
            reject_non_string(cast("Mapping[str, str]", {"a": bad}), "enum_binding")


def _source(corpus_path: str) -> SourceReference:
    return SourceReference(
        id="aeat-manual-2025",
        evidence_tier="official_source_guidance",
        authority="aeat",
        kind="manual_pdf",
        corpus_path=corpus_path,
        sha256="a" * 64,
        bytes=1,
        retrieved_at=date(1980, 8, 1),
        source_url="https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186",
        review_status="pending_review",
    )


def test_corpus_path_accepts_relative_posix_path() -> None:
    assert _source("aeat/manuals/manual-2025.pdf").corpus_path == "aeat/manuals/manual-2025.pdf"


@pytest.mark.parametrize(
    "bad",
    ["corpus/../../x.pdf", "C:/x.pdf", "", "a//b.pdf", " a.pdf", "a.pdf ", "/a.pdf", "a/./b.pdf", "a\\b.pdf"],
)
def test_corpus_path_refuses_noncanonical_paths(bad: str) -> None:
    with pytest.raises((ValidationError, RegistryValidationError)):
        _source(bad)


def _irnr(codes: tuple[str, ...]) -> LedgerIrnrIncomeProvider:
    return LedgerIrnrIncomeProvider(
        target_casilla_id=validated_casilla_id("0001", surface="test"),
        source_jurisdictions=codes,
    )


def test_irnr_jurisdictions_accept_ascii_alpha2_only() -> None:
    assert _irnr(("ES", "FR")).source_jurisdictions == ("ES", "FR")
    for bad in ("\u0415S", "\u00c9S", "es"):
        with pytest.raises(ValidationError):
            _irnr((bad,))
