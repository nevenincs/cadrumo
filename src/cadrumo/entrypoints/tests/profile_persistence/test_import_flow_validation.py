"""Input validation checks for external Modelo filing imports."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.modelo.action_errors import ExternalModeloImportError
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.adapter_composition_work_ports import build_work_lifecycle_ports
from cadrumo.entrypoints.tests.profile_persistence.import_flow_support import (
    IMPORT_INCOME_CASILLA,
    M303_PRINTED_RESULT_TOKEN,
    PROFILE_ID,
    T0,
    T1,
    UNKNOWN_IMPORT_CASILLA,
    Repos,
    import_external_filing,
    repos,
    seed_work_unit,
)

__all__ = ["repos"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_import_refuses_casilla_ids_not_in_registry(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """The import path refuses casilla ids the registry does not
    declare for the work unit's modelo / filing_year / period.
    Imported baselines are the legal source of truth for amend
    paths - fabricated casilla ids cannot be silently accepted."""

    wu_repo, _, _, _, bucket_event_repository = repos
    work_unit = seed_work_unit(wu_repo, bucket_event_repository, operation=operation)

    with pytest.raises(ExternalModeloImportError) as exc_info:
        import_external_filing(
            repos,
            work_unit,
            casilla_values={UNKNOWN_IMPORT_CASILLA: Decimal("100")},
            evidence_reference_id="JUST-FABRICATED",
            clock=T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.external_import_unknown_casillas"
    assert exc_info.value.context is not None
    casillas_obj = exc_info.value.context.get("casillas", [])
    assert isinstance(casillas_obj, (list, tuple))
    assert UNKNOWN_IMPORT_CASILLA in casillas_obj


def test_import_refuses_printed_number_metadata_token(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """External imports must not treat a printed number as a casilla reference."""

    _wu_repo, _, _, _, _ = repos
    work_unit = create_work_unit(
        bucket_id=PROFILE_ID,
        modelo="303",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        revision_id="2025",
        ports=build_work_lifecycle_ports(bucket_id=PROFILE_ID),
        clock=T0,
        operation=operation,
    )

    with pytest.raises(ExternalModeloImportError, match="non-canonical reference tokens") as exc_info:
        import_external_filing(
            repos,
            work_unit,
            casilla_values={M303_PRINTED_RESULT_TOKEN: Decimal("100")},
            evidence_reference_id="JUST-PRINTED-NUMBER",
            clock=T1,
        )

    assert exc_info.value.translated_message == "application.modelo.errors.external_import_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == [M303_PRINTED_RESULT_TOKEN]
    assert "iva.resultado" in str(exc_info.value)


def test_import_refuses_non_string_casilla_keys_without_coercion(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """Malformed external casilla keys fail before registry membership checks."""

    wu_repo, _, _, _, bucket_event_repository = repos
    work_unit = seed_work_unit(wu_repo, bucket_event_repository, operation=operation)

    with pytest.raises(ExternalModeloImportError) as exc_info:
        import_external_filing(
            repos,
            work_unit,
            casilla_values={1: Decimal("100")},
            evidence_reference_id="JUST-MALFORMED",
            clock=T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.external_import_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == ["1"]


def test_import_refuses_empty_casilla_values(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """The import path requires at least one casilla value."""

    wu_repo, _, _, _, bucket_event_repository = repos
    work_unit = seed_work_unit(wu_repo, bucket_event_repository, operation=operation)

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing(
            repos,
            work_unit,
            casilla_values={},
            evidence_reference_id="JUST-WHATEVER",
            clock=T1,
        )
    assert raised.value.translated_message == "application.modelo.errors.external_filing_no_casilla_values"


def test_import_refuses_empty_evidence_reference(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """The import path requires a non-empty evidence reference id."""

    wu_repo, _, _, _, bucket_event_repository = repos
    work_unit = seed_work_unit(wu_repo, bucket_event_repository, operation=operation)

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing(
            repos,
            work_unit,
            casilla_values={IMPORT_INCOME_CASILLA: Decimal("1500")},
            evidence_reference_id="   ",
            clock=T1,
        )
    assert raised.value.translated_message == "application.modelo.errors.external_filing_evidence_reference_blank"
