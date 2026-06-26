"""Storage / decimal / redaction error class typing and raise contracts.

Verifies:
- MRO: FinancialValidationError, DecimalFormatError, RedactionError are NOT
  ValueError subclasses.
- All migrated error classes are reachable via the ERROR_REGISTRY.
- ErrorEnvelope roundtrip: build_error_envelope produces a valid envelope.
- Raise behavior: each migrated site raises the correct typed error.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# FinancialValidationError no longer inherits ValueError
# ---------------------------------------------------------------------------


def test_financial_validation_error_not_value_error() -> None:
    """FinancialValidationError must not be a ValueError subclass."""
    from ..adapters.inbound.financial.providers._base import (
        FinancialValidationError,
    )

    assert not issubclass(FinancialValidationError, ValueError), (
        "FinancialValidationError must not inherit from ValueError after the MRO cleanup"
    )


def test_financial_validation_error_is_aeat_error() -> None:
    """FinancialValidationError still derives from AeatError."""
    from ..adapters.inbound.financial.providers._base import (
        FinancialValidationError,
    )
    from ..core.errors import AeatError

    assert issubclass(FinancialValidationError, AeatError)


def test_financial_validation_error_registered() -> None:
    """FinancialValidationError has a registered ErrorCode."""
    from ..adapters.inbound.financial.providers._base import (
        FinancialValidationError,
    )
    from ..core.errors import ERROR_REGISTRY, get_registered_error_code

    err = FinancialValidationError("test")
    code = get_registered_error_code(err)
    assert code.code in ERROR_REGISTRY


# ---------------------------------------------------------------------------
# EncryptedString / Bytes / JSON / HashedLookup TypeError -> StorageValidationError
# ---------------------------------------------------------------------------


def test_encrypted_string_raises_storage_validation_error() -> None:
    """EncryptedString.process_bind_param raises StorageValidationError for non-str.

    Dialect argument is irrelevant — type-guard fires before it is used.
    """
    from ..adapters.persistence.storage.crypto._encrypted_columns import (
        EncryptedString,
    )
    from ..adapters.persistence.storage.errors import StorageValidationError

    col = EncryptedString()
    with pytest.raises(StorageValidationError):
        # negative test: int rejected where str is required
        col.process_bind_param(12345, None)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def test_encrypted_bytes_raises_storage_validation_error() -> None:
    """EncryptedBytes.process_bind_param raises StorageValidationError for non-bytes.

    Dialect argument is irrelevant — type-guard fires before it is used.
    """
    from ..adapters.persistence.storage.crypto._encrypted_columns import (
        EncryptedBytes,
    )
    from ..adapters.persistence.storage.errors import StorageValidationError

    col = EncryptedBytes()
    with pytest.raises(StorageValidationError):
        # negative test: str rejected where bytes is required
        col.process_bind_param("not-bytes", None)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def test_hashed_lookup_compute_raises_storage_validation_error() -> None:
    """HashedLookup.compute raises StorageValidationError for non-str input.

    The type-guard fires before key resolution so no master-key provider is needed.
    """
    from ..adapters.persistence.storage.crypto._encrypted_columns import (
        HashedLookup,
    )
    from ..adapters.persistence.storage.errors import StorageValidationError

    with pytest.raises(StorageValidationError):
        # negative test: int rejected where str is required
        HashedLookup.compute(12345)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def test_hashed_lookup_process_bind_raises_storage_validation_error() -> None:
    """HashedLookup.process_bind_param raises StorageValidationError for wrong type.

    The type-guard fires before key resolution so no master-key provider is needed.
    Dialect argument is irrelevant at this error path.
    """
    from ..adapters.persistence.storage.crypto._encrypted_columns import (
        HashedLookup,
    )
    from ..adapters.persistence.storage.errors import StorageValidationError

    col = HashedLookup()
    with pytest.raises(StorageValidationError):
        # negative test: float rejected where str | bytes is required
        col.process_bind_param(99.9, None)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


# ---------------------------------------------------------------------------
# DecimalFormatError(CoreError)
# ---------------------------------------------------------------------------


def test_decimal_format_error_not_value_error() -> None:
    """DecimalFormatError must not be a ValueError subclass."""
    from ..core.errors import DecimalFormatError

    assert not issubclass(DecimalFormatError, ValueError)


def test_decimal_format_error_raised_on_none_without_fallback() -> None:
    """format_decimal raises DecimalFormatError when value is None and none_value omitted."""
    from ..core.decimal._format import format_decimal
    from ..core.errors import DecimalFormatError

    with pytest.raises(DecimalFormatError):
        format_decimal(None)


def test_decimal_format_error_registered() -> None:
    """DecimalFormatError has a registered ErrorCode in ERROR_REGISTRY."""
    from ..core.errors import ERROR_REGISTRY, DecimalFormatError, get_registered_error_code

    err = DecimalFormatError("test")
    code = get_registered_error_code(err)
    assert code.code in ERROR_REGISTRY


# ---------------------------------------------------------------------------
# RedactionError(CoreError)
# ---------------------------------------------------------------------------


def test_redaction_error_not_value_error() -> None:
    """RedactionError must not be a ValueError subclass."""
    from ..core.errors import RedactionError

    assert not issubclass(RedactionError, ValueError)


def test_redact_raises_redaction_error_for_non_str() -> None:
    """redact() raises RedactionError when passed a non-str value."""
    from ..core.errors import RedactionError
    from ..core.redaction import redact

    with pytest.raises(RedactionError):
        # negative test: int rejected where str is required
        redact(12345, rules=())  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def test_redact_for_cli_output_raises_redaction_error_for_non_str() -> None:
    """redact_for_cli_output() raises RedactionError for non-str input."""
    from ..core.errors import RedactionError
    from ..core.redaction import redact_for_cli_output

    with pytest.raises(RedactionError):
        # negative test: dict rejected where str is required
        redact_for_cli_output({"not": "a string"})  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def test_redaction_error_registered() -> None:
    """RedactionError has a registered ErrorCode in ERROR_REGISTRY."""
    from ..core.errors import ERROR_REGISTRY, RedactionError, get_registered_error_code

    err = RedactionError("test")
    code = get_registered_error_code(err)
    assert code.code in ERROR_REGISTRY


# ---------------------------------------------------------------------------
# OverviewAgendaError raised at agenda-build entry
# ---------------------------------------------------------------------------


def test_overview_agenda_error_raised_for_non_positive_horizon() -> None:
    """build_overview_agenda raises OverviewAgendaError for horizon_days <= 0."""
    from datetime import date

    # Import _agenda lazily; OverviewAgendaError is raised before any
    # network or profile access so no fixture setup is needed.
    from ..application.overview._agenda import build_overview_agenda
    from ..application.overview._errors import OverviewAgendaError

    with pytest.raises(OverviewAgendaError):
        build_overview_agenda(
            # negative test: None rejected where TaxpayerProfile is required
            profile=None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            as_of=date.today(),
            horizon_days=0,
            # negative test: None rejected where the engine is required
            engine=None,  # pyright: ignore[reportArgumentType]
            raw_values={},
        )


# ---------------------------------------------------------------------------
# CensoSyncError typing (independent of CensoSyncService construction)
# ---------------------------------------------------------------------------


def _load_censo_sync_error_class() -> type:
    """Load CensoSyncError without triggering the domain.user_profile.__init__."""
    import importlib.util
    import pathlib

    spec = importlib.util.spec_from_file_location(
        "aeat.application.user_profile._censo_errors",
        str(pathlib.Path(__file__).parent.parent / "application/user_profile/_censo_errors.py"),
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.CensoSyncError  # type: ignore[no-any-return]


def test_censo_sync_error_is_aeat_error() -> None:
    """CensoSyncError is an AeatError subclass and is registered.

    CensoSyncService cannot be instantiated in a pure unit context here;
    the contract tested is that the error class itself is properly
    typed and registered.
    """
    from ..core.errors import AeatError

    censo_sync_error_cls = _load_censo_sync_error_class()
    assert issubclass(censo_sync_error_cls, AeatError)


def test_censo_sync_error_no_longer_value_error() -> None:
    """CensoSyncError must not inherit ValueError."""
    censo_sync_error_cls = _load_censo_sync_error_class()
    assert not issubclass(censo_sync_error_cls, ValueError)


# ---------------------------------------------------------------------------
# PortalValidationError for the build_entry factory
# ---------------------------------------------------------------------------


def test_portal_validation_error_both_url_and_path() -> None:
    """build_entry raises PortalValidationError when both url and path are given."""
    from ..domain.portals._entries._common import build_entry
    from ..domain.portals._errors import PortalValidationError

    with pytest.raises(PortalValidationError):
        # negative test: None passed for enum/struct args; rejected before use
        build_entry(
            portal=None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            subdomain=None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            category=None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            auth_methods=[],
            url_stability=None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            label="test",
            purpose="test",
            url="https://example.com",
            path="/also-present",
        )


def test_portal_validation_error_path_not_starting_slash() -> None:
    """build_entry raises PortalValidationError when path does not start with /."""
    from ..domain.portals._entries._common import build_entry
    from ..domain.portals._errors import PortalValidationError

    with pytest.raises(PortalValidationError):
        # negative test: None passed for enum/struct args; rejected before use
        build_entry(
            portal=None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            subdomain=None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            category=None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            auth_methods=[],
            url_stability=None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            label="test",
            purpose="test",
            path="no-leading-slash",
        )


# ---------------------------------------------------------------------------
# ProfileAnswerTypeError in profile parsing helpers
# ---------------------------------------------------------------------------


def test_profile_answer_type_error_descendant_bad_discapacidad() -> None:
    """parse_descendiente_flag raises ProfileAnswerTypeError for invalid DISCAPACIDAD."""
    from ..core.errors import ProfileAnswerTypeError
    from ..domain.contribuyente._descendant_facts import parse_descendiente_flag

    with pytest.raises(ProfileAnswerTypeError):
        parse_descendiente_flag("NACIMIENTO=2010-01-01,DISCAPACIDAD=50")


def test_profile_answer_type_error_marriage_date_invalid() -> None:
    """parse_marriage_date_flag raises ProfileAnswerTypeError for non-ISO-8601 input."""
    from ..core.errors import ProfileAnswerTypeError
    from ..domain.contribuyente._marriage_facts import parse_marriage_date_flag

    with pytest.raises(ProfileAnswerTypeError):
        parse_marriage_date_flag("not-a-date")


def test_profile_answer_type_error_ccaa_unknown_label() -> None:
    """CCAA.from_label raises ProfileAnswerTypeError for an unknown CCAA label."""
    from ..core.errors import ProfileAnswerTypeError
    from ..domain.contribuyente._ccaa import CCAA

    with pytest.raises(ProfileAnswerTypeError):
        CCAA.from_label("xyzzy")


# ---------------------------------------------------------------------------
# RegistryValidationError in M232 row bindings
# ---------------------------------------------------------------------------


def test_m232_binding_error_too_many_rows() -> None:
    """materialize_m232_related_party_rows raises RegistryValidationError for >5 rows."""
    from decimal import Decimal as _Decimal

    from ..domain.calculations.registry._errors import RegistryValidationError
    from ..domain.modelos._m232_row_materialisation import (
        materialize_m232_related_party_rows,
    )
    from ..domain.modelos._row_models import Modelo232VinculadaRow

    dummy_row = Modelo232VinculadaRow(
        nif="12345678A",
        tipo_vinculacion="1",
        tipo_operacion="01",
        importe=_Decimal("0"),
    )
    six_rows = tuple([dummy_row] * 6)

    with pytest.raises(RegistryValidationError):
        # negative test: None rejected where ModeloRevision is required
        materialize_m232_related_party_rows(None, six_rows)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


# ---------------------------------------------------------------------------
# Envelope roundtrip: build_error_envelope for all new classes
# ---------------------------------------------------------------------------


def test_error_envelope_roundtrip_decimal_format_error() -> None:
    """build_error_envelope produces a valid ErrorEnvelope for DecimalFormatError."""
    from ..core.errors import DecimalFormatError, build_error_envelope

    err = DecimalFormatError("test decimal format")
    envelope = build_error_envelope(err)
    assert envelope.code == "ERROR_DECIMAL_FORMAT"
    assert envelope.message


def test_error_envelope_roundtrip_redaction_error() -> None:
    """build_error_envelope produces a valid ErrorEnvelope for RedactionError."""
    from ..core.errors import RedactionError, build_error_envelope

    err = RedactionError("test redaction error")
    envelope = build_error_envelope(err)
    assert envelope.code == "ERROR_REDACTION"
    assert envelope.message
