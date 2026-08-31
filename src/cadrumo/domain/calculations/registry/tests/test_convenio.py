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
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.irnr import ConvenioOverrideKind, TipoRentaIrnr
from .....core.resources.bundled_data import bundled_path
from ..convenio import (
    ConvenioAuthority,
    ConvenioOverrideRow,
    ConvenioTreaty,
    collect_convenio_fingerprints,
    load_convenio_authority,
    validate_convenio_legal_refs,
)
from ..errors import RegistryLoadError, RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
    flat = _row(TipoRentaIrnr.GENERAL, ConvenioOverrideKind.FLAT, rate="0.24")
    assert flat.rate_decimal == Decimal("0.24")

    ceiling = _row(TipoRentaIrnr.INTEREST, ConvenioOverrideKind.CEILING, rate="0.10")
    assert ceiling.rate_decimal == Decimal("0.10")

    with pytest.raises(ValidationError, match="requires a rate"):
        _row(TipoRentaIrnr.GENERAL, ConvenioOverrideKind.FLAT, rate=None)

    with pytest.raises(ValidationError, match=r"within \[0, 1\]"):
        _row(TipoRentaIrnr.GENERAL, ConvenioOverrideKind.FLAT, rate="1.5")

    with pytest.raises(ValidationError, match="parseable Decimal"):
        _row(TipoRentaIrnr.GENERAL, ConvenioOverrideKind.FLAT, rate="not-a-rate")


def test_allocation_and_exempt_rows_must_not_declare_a_rate() -> None:
    allocation = _row(TipoRentaIrnr.PENSION, ConvenioOverrideKind.ALLOCATION_DOMESTIC_TARIFF)
    assert allocation.rate_decimal is None

    exempt = _row(TipoRentaIrnr.INTEREST, ConvenioOverrideKind.EXEMPT)
    assert exempt.rate_decimal is None

    with pytest.raises(ValidationError, match="must not declare a rate"):
        _row(TipoRentaIrnr.PENSION, ConvenioOverrideKind.ALLOCATION_DOMESTIC_TARIFF, rate="0.30")

    with pytest.raises(ValidationError, match="must not declare a rate"):
        _row(TipoRentaIrnr.INTEREST, ConvenioOverrideKind.EXEMPT, rate="0.00")


def test_override_row_anchor_must_be_included_in_legal_refs() -> None:
    with pytest.raises(ValidationError, match="legal_ref_anchor must be included in legal_refs"):
        _row(
            TipoRentaIrnr.INTEREST,
            ConvenioOverrideKind.CEILING,
            rate="0.10",
            legal_ref_anchor="convenio-es-ma-1978:art-11",
            legal_refs=("trlirnr-rdleg-5-2004:art-25.1.f",),
        )


def test_override_row_hydrates_enum_tokens_from_plain_strings() -> None:
    # The registry TOML declares tipo_renta / kind as plain strings; the loader
    # boundary hydrates them into the closed core enums under the strict config.
    row = ConvenioOverrideRow.model_validate(
        {
            "tipo_renta": "interest",
            "kind": "exempt",
            "legal_ref_anchor": "convenio-es-de-2011:art-11",
            "legal_refs": ("convenio-es-de-2011:art-11",),
            "valid_from": date(2025, 1, 1),
        }
    )
    assert row.tipo_renta is TipoRentaIrnr.INTEREST
    assert row.kind is ConvenioOverrideKind.EXEMPT


def test_treaty_rejects_duplicate_override_for_same_tipo_and_window() -> None:
    with pytest.raises(ValidationError, match="duplicate override"):
        ConvenioTreaty(
            country_code="MA",
            document_id="BOE-A-1985-9280",
            overrides=(
                _row(TipoRentaIrnr.INTEREST, ConvenioOverrideKind.CEILING, rate="0.10"),
                _row(TipoRentaIrnr.INTEREST, ConvenioOverrideKind.CEILING, rate="0.12"),
            ),
        )


def test_authority_resolve_filters_by_year_window_and_returns_none_off_window() -> None:
    row = ConvenioOverrideRow(
        tipo_renta=TipoRentaIrnr.INTEREST,
        kind=ConvenioOverrideKind.CEILING,
        rate="0.10",
        legal_ref_anchor="convenio-es-ma-1978:art-11",
        legal_refs=("convenio-es-ma-1978:art-11",),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    authority = ConvenioAuthority(
        treaties={"MA": ConvenioTreaty(country_code="MA", document_id="BOE-A-1985-9280", overrides=(row,))},
    )

    assert authority.resolve("MA", TipoRentaIrnr.INTEREST, 2025) is not None
    assert authority.resolve("ma", TipoRentaIrnr.INTEREST, 2025) is not None  # case-insensitive
    assert authority.resolve("MA", TipoRentaIrnr.INTEREST, 2026) is None  # after valid_to
    assert authority.resolve("MA", TipoRentaIrnr.GENERAL, 2025) is None  # wrong income type
    assert authority.resolve("ZW", TipoRentaIrnr.INTEREST, 2025) is None  # no treaty


def test_load_convenio_authority_compiles_the_bundled_treaty_tree() -> None:
    convenio = load_convenio_authority(bundled_path("registry", "aeat", "treaties"))

    assert {"GB", "MA", "AR", "DE"} <= set(convenio.treaties)
    de = convenio.resolve("DE", TipoRentaIrnr.INTEREST, 2025)
    assert de is not None
    assert de.document_id == "BOE-A-2012-10212"
    assert de.kind is ConvenioOverrideKind.EXEMPT


def test_load_convenio_authority_rejects_duplicate_country(tmp_path: Path) -> None:
    body = (
        "[treaty]\n"
        'country_code = "MA"\n'
        'document_id = "BOE-A-1985-9280"\n'
        "[[treaty.overrides]]\n"
        'tipo_renta = "interest"\n'
        'kind = "ceiling"\n'
        'rate = "0.10"\n'
        'legal_ref_anchor = "convenio-es-ma-1978:art-11"\n'
        'legal_refs = ["convenio-es-ma-1978:art-11"]\n'
        "valid_from = 2025-01-01\n"
    )
    (tmp_path / "es-ma.toml").write_text(body, encoding="utf-8")
    (tmp_path / "ma-dup.toml").write_text(body, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="already declared"):
        load_convenio_authority(tmp_path)


def test_absent_treaty_tree_yields_empty_authority(tmp_path: Path) -> None:
    empty = load_convenio_authority(tmp_path / "does-not-exist")
    assert empty.treaties == {}
    assert ConvenioAuthority.empty().treaties == {}


def test_validate_convenio_legal_refs_rejects_ungrounded_override() -> None:
    authority = ConvenioAuthority(
        treaties={
            "MA": ConvenioTreaty(
                country_code="MA",
                document_id="BOE-A-1985-9280",
                overrides=(_row(TipoRentaIrnr.INTEREST, ConvenioOverrideKind.CEILING, rate="0.10"),),
            ),
        },
    )
    # The grounding gate passes when the ref exists in the catalogue and fails when absent.
    validate_convenio_legal_refs(authority, frozenset({"convenio-es-ma-1978:art-11"}))
    with pytest.raises(RegistryValidationError, match="missing from the legal catalogue"):
        validate_convenio_legal_refs(authority, frozenset())


def test_collect_convenio_fingerprints_covers_every_treaty_file() -> None:
    fingerprints = collect_convenio_fingerprints(bundled_path("registry", "aeat"))
    paths = {Path(entry[0]).name for entry in fingerprints}
    assert {"es-gb.toml", "es-ma.toml", "es-ar.toml", "es-de.toml"} <= paths
    # Fingerprints carry (path, size, mtime_ns, content_digest) so a treaty
    # content edit re-keys the cache even when (size, mtime_ns) collide; the
    # digest slot is empty here because the bundled tree is read-only package
    # data exempt from content hashing.
    assert all(len(entry) == 4 and entry[1] > 0 for entry in fingerprints)
