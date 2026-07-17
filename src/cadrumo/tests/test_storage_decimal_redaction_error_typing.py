"""Storage / decimal / redaction error class typing and raise contracts.

Verifies:
- MRO: FinancialValidationError, DecimalFormatError, RedactionError are NOT
  ValueError subclasses.
- All migrated error classes are reachable via the ERROR_REGISTRY.
- ErrorEnvelope roundtrip: build_error_envelope produces a valid envelope.
- Raise behavior: each migrated site raises the correct typed error.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict, cast

import pytest
from sqlalchemy.engine import Dialect

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# FinancialValidationError no longer inherits ValueError
# ---------------------------------------------------------------------------


def test_financial_validation_error_typing_and_registry() -> None:
    """FinancialValidationError is an CadrumoError, not a ValueError, and is registered."""
    from ..adapters.inbound.financial.providers import FinancialValidationError
    from ..core.errors import ERROR_REGISTRY, CadrumoError, get_registered_error_code

    assert not issubclass(FinancialValidationError, ValueError), (
        "FinancialValidationError must not inherit from ValueError after the MRO cleanup"
    )
    assert issubclass(FinancialValidationError, CadrumoError)
    err = FinancialValidationError("test")
    code = get_registered_error_code(err)
    assert code.code in ERROR_REGISTRY


# ---------------------------------------------------------------------------
# EncryptedString / Bytes / JSON / HashedLookup TypeError -> StorageValidationError
# ---------------------------------------------------------------------------


def _encrypted_string_bind_with_wrong_type() -> None:
    from ..adapters.persistence.storage.crypto import EncryptedString

    EncryptedString().process_bind_param(cast(str, 12345), cast(Dialect, None))


def _encrypted_bytes_bind_with_wrong_type() -> None:
    from ..adapters.persistence.storage.crypto import EncryptedBytes

    EncryptedBytes().process_bind_param(cast(bytes, "not-bytes"), cast(Dialect, None))


def _hashed_lookup_compute_with_wrong_type() -> None:
    from ..adapters.persistence.storage.crypto import HashedLookup

    HashedLookup.compute(cast(str, 12345))


def _hashed_lookup_bind_with_wrong_type() -> None:
    from ..adapters.persistence.storage.crypto import HashedLookup

    HashedLookup().process_bind_param(cast(str | bytes, 99.9), cast(Dialect, None))


@pytest.mark.parametrize(
    "call",
    (
        _encrypted_string_bind_with_wrong_type,
        _encrypted_bytes_bind_with_wrong_type,
        _hashed_lookup_compute_with_wrong_type,
        _hashed_lookup_bind_with_wrong_type,
    ),
)
def test_encrypted_column_type_guards_raise_storage_validation_error(call: Callable[[], object]) -> None:
    """Encrypted-column type guards raise StorageValidationError before key resolution.

    The type-guard fires before key resolution so no master-key provider is needed.
    Dialect argument is irrelevant at this error path.
    """
    from ..adapters.persistence.storage.errors import StorageValidationError

    with pytest.raises(StorageValidationError) as exc_info:
        call()
    assert exc_info.type is StorageValidationError


# ---------------------------------------------------------------------------
# DecimalFormatError(CoreError)
# ---------------------------------------------------------------------------


def test_decimal_format_error_typing_registry_and_raise_site() -> None:
    """DecimalFormatError is registered, not a ValueError, and raised by format_decimal."""
    from ..core.decimal import format_decimal
    from ..core.errors import ERROR_REGISTRY, DecimalFormatError, get_registered_error_code

    assert not issubclass(DecimalFormatError, ValueError)

    with pytest.raises(DecimalFormatError):
        format_decimal(None)

    err = DecimalFormatError("test")
    code = get_registered_error_code(err)
    assert code.code in ERROR_REGISTRY


# ---------------------------------------------------------------------------
# RedactionError(CoreError)
# ---------------------------------------------------------------------------


def _redact_with_non_string_value() -> None:
    from ..core.redaction import redact

    redact(cast(str, 12345), rules=())


def _redact_cli_output_with_non_string_value() -> None:
    from ..core.redaction import redact_for_cli_output

    redact_for_cli_output(cast(str, {"not": "a string"}))


@pytest.mark.parametrize("call", (_redact_with_non_string_value, _redact_cli_output_with_non_string_value))
def test_redaction_error_raise_sites(call: Callable[[], object]) -> None:
    """Redaction entrypoints raise RedactionError for non-string input."""
    from ..core.errors import RedactionError

    with pytest.raises(RedactionError) as exc_info:
        call()
    assert exc_info.type is RedactionError


def test_redaction_error_typing_and_registry() -> None:
    """RedactionError is registered and not a ValueError."""
    from ..core.errors import ERROR_REGISTRY, RedactionError, get_registered_error_code

    assert not issubclass(RedactionError, ValueError)

    err = RedactionError("test")
    code = get_registered_error_code(err)
    assert code.code in ERROR_REGISTRY


# ---------------------------------------------------------------------------
# OverviewAgendaError raised at agenda-build entry
# ---------------------------------------------------------------------------


def test_overview_agenda_error_raised_for_non_positive_horizon() -> None:
    """build_overview_agenda raises OverviewAgendaError for horizon_days <= 0."""
    from datetime import date

    from ..application.overview import OverviewAgendaError, build_overview_agenda

    # OverviewAgendaError is raised before any network or profile access so
    # no fixture setup is needed.
    from ..domain.deadlines import DeadlineEngine
    from ..domain.deadlines.taxpayer_model import TaxpayerProfile

    with pytest.raises(OverviewAgendaError):
        build_overview_agenda(
            # negative test: None rejected where TaxpayerProfile is required
            profile=cast(TaxpayerProfile, None),
            as_of=date.today(),
            horizon_days=0,
            # negative test: None rejected where the engine is required
            engine=cast(DeadlineEngine, None),
            raw_values={},
        )


# ---------------------------------------------------------------------------
# CensoSyncError typing (independent of CensoSyncService construction)
# ---------------------------------------------------------------------------


def test_censo_sync_error_typing() -> None:
    """CensoSyncError is an CadrumoError subclass and not a ValueError.

    CensoSyncService cannot be instantiated in a pure unit context here;
    the contract tested is that the error class itself is properly typed.
    """
    from ..application.user_profile import CensoSyncError
    from ..core.errors import CadrumoError

    assert issubclass(CensoSyncError, CadrumoError)
    assert not issubclass(CensoSyncError, ValueError)


# ---------------------------------------------------------------------------
# PortalValidationError for the build_entry factory
# ---------------------------------------------------------------------------


class _PortalEntryOverrides(TypedDict, total=False):
    """The two ``build_entry`` keywords these malformed-shape cases vary."""

    url: str
    path: str


@pytest.mark.parametrize(
    "kwargs",
    (
        {"url": "https://example.com", "path": "/also-present"},
        {"path": "no-leading-slash"},
    ),
)
def test_portal_validation_error_for_invalid_entry_shapes(kwargs: _PortalEntryOverrides) -> None:
    """build_entry raises PortalValidationError for mutually exclusive or malformed URL fields."""
    from ..domain.portals import (
        AuthMethod,
        Portal,
        PortalCategory,
        PortalHost,
        PortalValidationError,
        UrlStability,
        build_entry,
    )

    with pytest.raises(PortalValidationError) as exc_info:
        # negative test: None passed for enum/struct args; rejected before use
        build_entry(
            portal=cast(Portal, None),
            subdomain=cast(PortalHost, None),
            category=cast(PortalCategory, None),
            auth_methods=cast(list[AuthMethod], []),
            url_stability=cast(UrlStability, None),
            label="test",
            purpose="test",
            **kwargs,
        )
    assert exc_info.type is PortalValidationError


# ---------------------------------------------------------------------------
# ProfileAnswerTypeError in profile parsing helpers
# ---------------------------------------------------------------------------


def _parse_descendiente_discapacidad_with_wrong_type() -> None:
    from ..domain.contribuyente import parse_descendiente_flag

    parse_descendiente_flag("NACIMIENTO=2010-01-01,DISCAPACIDAD=50")


def _parse_marriage_date_with_wrong_type() -> None:
    from ..domain.contribuyente import parse_marriage_date_flag

    parse_marriage_date_flag("not-a-date")


def _parse_ccaa_label_with_unknown_value() -> None:
    from ..domain.contribuyente import CCAA

    CCAA.from_label("xyzzy")


@pytest.mark.parametrize(
    "call",
    (
        _parse_descendiente_discapacidad_with_wrong_type,
        _parse_marriage_date_with_wrong_type,
        _parse_ccaa_label_with_unknown_value,
    ),
)
def test_profile_answer_type_error_raise_sites(call: Callable[[], object]) -> None:
    """Profile parsing helpers raise ProfileAnswerTypeError for invalid typed answers."""
    from ..core.errors import ProfileAnswerTypeError

    with pytest.raises(ProfileAnswerTypeError) as exc_info:
        call()
    assert exc_info.type is ProfileAnswerTypeError


# ---------------------------------------------------------------------------
# RegistryValidationError in M232 row bindings
# ---------------------------------------------------------------------------


def test_m232_binding_error_too_many_rows() -> None:
    """materialize_m232_related_party_rows raises RegistryValidationError for >5 rows."""
    from decimal import Decimal as _Decimal

    from ..domain.calculations.registry import ModeloRevision, RegistryValidationError
    from ..domain.modelos import Modelo232VinculadaRow, materialize_m232_related_party_rows

    sample_row = Modelo232VinculadaRow(
        nif="12345678A",
        tipo_vinculacion="1",
        tipo_operacion="01",
        importe=_Decimal("0"),
    )
    six_rows = tuple([sample_row] * 6)

    with pytest.raises(RegistryValidationError):
        # negative test: None rejected where ModeloRevision is required
        materialize_m232_related_party_rows(cast(ModeloRevision, None), six_rows)


# ---------------------------------------------------------------------------
# Envelope roundtrip: build_error_envelope for all new classes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error_name", "expected_code"),
    (
        ("decimal", "ERROR_DECIMAL_FORMAT"),
        ("redaction", "ERROR_REDACTION"),
    ),
)
def test_error_envelope_roundtrip_for_core_error_classes(error_name: str, expected_code: str) -> None:
    """build_error_envelope produces valid ErrorEnvelopes for migrated core errors."""
    from ..core.errors import DecimalFormatError, RedactionError, build_error_envelope

    err = (
        DecimalFormatError("test decimal format") if error_name == "decimal" else RedactionError("test redaction error")
    )
    envelope = build_error_envelope(err)
    assert envelope.code == expected_code
    assert envelope.message
