"""Input validation checks for external Modelo filing imports."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import Period
from .._action_errors import ExternalModeloImportError
from .._work_lifecycle import create_work_unit
from ._import_flow_support import (
    _IMPORT_INCOME_CASILLA,
    _M303_PRINTED_RESULT_TOKEN,
    _PROFILE_ID,
    _T0,
    _T1,
    _UNKNOWN_IMPORT_CASILLA,
    _import_external_filing,
    _Repos,
    _seed_work_unit,
    repos,
)

__all__ = ["repos"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_import_refuses_casilla_ids_not_in_registry(repos: _Repos) -> None:
    """The import path refuses casilla ids the registry does not
    declare for the work unit's modelo / filing_year / period.
    Imported baselines are the legal source of truth for amend
    paths - fabricated casilla ids cannot be silently accepted."""

    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as exc_info:
        _import_external_filing(
            repos,
            work_unit,
            casilla_values={_UNKNOWN_IMPORT_CASILLA: Decimal("100")},
            evidence_reference_id="JUST-FABRICATED",
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.external_import_unknown_casillas"
    assert exc_info.value.context is not None
    casillas_obj = exc_info.value.context.get("casillas", [])
    assert isinstance(casillas_obj, (list, tuple))
    assert _UNKNOWN_IMPORT_CASILLA in casillas_obj


def test_import_refuses_printed_number_metadata_token(repos: _Repos) -> None:
    """External imports must not treat a printed number as a casilla reference."""

    wu_repo, _, _, _, _ = repos
    work_unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="303",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        revision_id="2025",
        repository=wu_repo,
        clock=_T0,
    )

    with pytest.raises(ExternalModeloImportError, match="non-canonical reference tokens") as exc_info:
        _import_external_filing(
            repos,
            work_unit,
            casilla_values={_M303_PRINTED_RESULT_TOKEN: Decimal("100")},
            evidence_reference_id="JUST-PRINTED-NUMBER",
            clock=_T1,
        )

    assert exc_info.value.translated_message == "application.modelo.errors.external_import_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == [_M303_PRINTED_RESULT_TOKEN]
    assert "iva.resultado" in str(exc_info.value)


def test_import_refuses_non_string_casilla_keys_without_coercion(repos: _Repos) -> None:
    """Malformed external casilla keys fail before registry membership checks."""

    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as exc_info:
        _import_external_filing(
            repos,
            work_unit,
            casilla_values={1: Decimal("100")},
            evidence_reference_id="JUST-MALFORMED",
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.external_import_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == ["1"]


def test_import_refuses_empty_casilla_values(repos: _Repos) -> None:
    """The import path requires at least one casilla value."""

    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            casilla_values={},
            evidence_reference_id="JUST-WHATEVER",
            clock=_T1,
        )
    assert raised.value.translated_message == "application.modelo.errors.external_filing_no_casilla_values"


def test_import_refuses_empty_evidence_reference(repos: _Repos) -> None:
    """The import path requires a non-empty evidence reference id."""

    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500")},
            evidence_reference_id="   ",
            clock=_T1,
        )
    assert raised.value.translated_message == "application.modelo.errors.external_filing_evidence_reference_blank"
