"""Contract tests for the cross-cutting Convenio doble imposición treaty authority.

Covers the typed override-row validators, the treaty/authority shapes, the
``resolve`` lookup semantics, the loader (including duplicate-country rejection),
and the legal-grounding gate. Rate figures asserted here trace to the migrated,
BOE-grounded treaty data (GB art 6, MA art 11, AR art 19, DE art 11), not to a
formula under test — so no assertion is tautological.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from pydantic import ValidationError

from cadrumo.core.irnr import ConvenioOverrideKind, TipoRentaIrnr
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.convenio import (
    ConvenioAuthority,
    ConvenioOverrideRow,
    ConvenioTreaty,
    resolve_convenio_override,
)
from cadrumo.domain.calculations.registry.irnr_tipo_renta import resolve_tipo_renta_irnr_catalogue

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EFFECTIVE_DATE = date(2025, 1, 1)


@cache
def _authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


def _tipo_renta(value: str) -> TipoRentaIrnr:
    """Resolve a named test category through the compiled IRNR catalogue."""
    return resolve_tipo_renta_irnr_catalogue(
        effective_date=_EFFECTIVE_DATE,
        authority=_authority(),
    ).require(value)


def _kind(country_code: str, tipo_renta: str) -> ConvenioOverrideKind:
    """Reuse a kind projected by the compiled convenio authority."""
    token = _tipo_renta(tipo_renta)
    override = _authority().catalogues.convenio.resolve(country_code, token, _EFFECTIVE_DATE.year)
    assert override is not None
    return override.kind


def _row(
    tipo_renta: TipoRentaIrnr,
    kind: ConvenioOverrideKind,
    *,
    rate: str | None = None,
    legal_ref_anchor: str = "convenio-es-ma-1978:art-11",
    legal_refs: tuple[str, ...] = ("convenio-es-ma-1978:art-11",),
) -> ConvenioOverrideRow:
    return ConvenioOverrideRow(
        tipo_renta=tipo_renta,
        kind=kind,
        rate=rate,
        legal_ref_anchor=legal_ref_anchor,
        legal_refs=legal_refs,
        valid_from=date(2025, 1, 1),
    )


def test_flat_and_ceiling_rows_require_a_parseable_rate_in_unit_interval() -> None:
    flat = _row(_tipo_renta("general"), _kind("GB", "general"), rate="0.24")
    assert flat.rate_decimal == Decimal("0.24")

    ceiling = _row(_tipo_renta("interest"), _kind("MA", "interest"), rate="0.10")
    assert ceiling.rate_decimal == Decimal("0.10")

    with pytest.raises(ValidationError, match="requires a rate"):
        _row(_tipo_renta("general"), _kind("GB", "general"), rate=None)

    with pytest.raises(ValidationError, match=r"within \[0, 1\]"):
        _row(_tipo_renta("general"), _kind("GB", "general"), rate="1.5")

    with pytest.raises(ValidationError, match="parseable Decimal"):
        _row(_tipo_renta("general"), _kind("GB", "general"), rate="not-a-rate")

    with pytest.raises(ValidationError, match=r"within \[0, 1\]"):
        _row(_tipo_renta("general"), _kind("GB", "general"), rate="NaN")


def test_allocation_and_exempt_rows_must_not_declare_a_rate() -> None:
    allocation = _row(_tipo_renta("pension"), _kind("AR", "pension"))
    assert allocation.rate_decimal is None

    exempt = _row(_tipo_renta("interest"), _kind("DE", "interest"))
    assert exempt.rate_decimal is None

    with pytest.raises(ValidationError, match="must not declare a rate"):
        _row(_tipo_renta("pension"), _kind("AR", "pension"), rate="0.30")

    with pytest.raises(ValidationError, match="must not declare a rate"):
        _row(_tipo_renta("interest"), _kind("DE", "interest"), rate="0.00")


def test_resolved_override_predicates_cover_each_registry_semantic() -> None:
    flat = resolve_convenio_override(
        country_code="GB",
        tipo_renta=_tipo_renta("general"),
        devengo_date=_EFFECTIVE_DATE,
    )
    ceiling = resolve_convenio_override(
        country_code="MA",
        tipo_renta=_tipo_renta("interest"),
        devengo_date=_EFFECTIVE_DATE,
    )
    allocation = resolve_convenio_override(
        country_code="AR",
        tipo_renta=_tipo_renta("pension"),
        devengo_date=_EFFECTIVE_DATE,
    )
    exempt = resolve_convenio_override(
        country_code="DE",
        tipo_renta=_tipo_renta("interest"),
        devengo_date=_EFFECTIVE_DATE,
    )

    assert flat is not None and flat.has_flat_rate and flat.rate == Decimal("0.24")
    assert ceiling is not None and ceiling.has_ceiling_rate and ceiling.rate == Decimal("0.10")
    assert allocation is not None and allocation.delegates_to_domestic_tariff and allocation.rate is None
    assert exempt is not None and exempt.is_exempt and exempt.rate is None


def test_override_row_anchor_must_be_included_in_legal_refs() -> None:
    with pytest.raises(ValidationError, match="legal_ref_anchor must be included in legal_refs"):
        _row(
            _tipo_renta("interest"),
            _kind("MA", "interest"),
            rate="0.10",
            legal_ref_anchor="convenio-es-ma-1978:art-11",
            legal_refs=("trlirnr-rdleg-5-2004:art-25.1.f",),
        )


def test_override_row_projects_registry_tokens_from_plain_strings() -> None:
    # The registry TOML declares tipo_renta / kind as plain strings; the loader
    # boundary projects them into the opaque typed tokens under strict config.
    row = ConvenioOverrideRow.model_validate(
        {
            "tipo_renta": "interest",
            "kind": "exempt",
            "legal_ref_anchor": "convenio-es-de-2011:art-11",
            "legal_refs": ("convenio-es-de-2011:art-11",),
            "valid_from": date(2025, 1, 1),
        }
    )
    assert row.tipo_renta == _tipo_renta("interest")
    assert row.kind == _kind("DE", "interest")


def test_treaty_rejects_duplicate_override_for_same_tipo_and_window() -> None:
    with pytest.raises(ValidationError, match="duplicate override"):
        ConvenioTreaty(
            country_code="MA",
            document_id="BOE-A-1985-9280",
            overrides=(
                _row(_tipo_renta("interest"), _kind("MA", "interest"), rate="0.10"),
                _row(_tipo_renta("interest"), _kind("MA", "interest"), rate="0.12"),
            ),
        )


def test_authority_resolve_filters_by_year_window_and_returns_none_off_window() -> None:
    row = ConvenioOverrideRow(
        tipo_renta=_tipo_renta("interest"),
        kind=_kind("MA", "interest"),
        rate="0.10",
        legal_ref_anchor="convenio-es-ma-1978:art-11",
        legal_refs=("convenio-es-ma-1978:art-11",),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    authority = ConvenioAuthority(
        treaties={"MA": ConvenioTreaty(country_code="MA", document_id="BOE-A-1985-9280", overrides=(row,))},
    )

    interest = _tipo_renta("interest")
    assert authority.resolve("MA", interest, 2025) is not None
    assert authority.resolve("ma", interest, 2025) is not None  # case-insensitive
    assert authority.resolve("MA", interest, 2026) is None  # after valid_to
    assert authority.resolve("MA", _tipo_renta("general"), 2025) is None  # wrong income type
    assert authority.resolve("ZW", interest, 2025) is None  # no treaty
