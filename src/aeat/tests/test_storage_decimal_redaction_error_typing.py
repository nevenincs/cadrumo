"""Storage / decimal / redaction error class typing and raise contracts.

Verifies:
- MRO: FinancialValidationError, DecimalFormatError, RedactionError are NOT
  ValueError subclasses.
- All migrated error classes are reachable via the ERROR_REGISTRY.
- ErrorEnvelope roundtrip: build_error_envelope produces a valid envelope.
- Raise behavior: each migrated site raises the correct typed error.
"""

from __future__ import annotations

from typing import TypedDict, cast

import pytest
from sqlalchemy.engine import Dialect

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# FinancialValidationError no longer inherits ValueError
# ---------------------------------------------------------------------------


def test_financial_validation_error_typing_and_registry() -> None:
    """FinancialValidationError is an AeatError, not a ValueError, and is registered."""
    from ..adapters.inbound.financial.providers import FinancialValidationError
    from ..core.errors import ERROR_REGISTRY, AeatError, get_registered_error_code

    assert not issubclass(FinancialValidationError, ValueError), (
        "FinancialValidationError must not inherit from ValueError after the MRO cleanup"
    )
    assert issubclass(FinancialValidationError, AeatError)
    err = FinancialValidationError("test")
    code = get_registered_error_code(err)
    assert code.code in ERROR_REGISTRY


# ---------------------------------------------------------------------------
# EncryptedString / Bytes / JSON / HashedLookup TypeError -> StorageValidationError
# ---------------------------------------------------------------------------


def test_encrypted_column_type_guards_raise_storage_validation_error() -> None:
    """Encrypted-column type guards raise StorageValidationError before key resolution.

    The type-guard fires before key resolution so no master-key provider is needed.
    Dialect argument is irrelevant at this error path.
    """
    from ..adapters.persistence.storage.crypto import (
        EncryptedBytes,
        EncryptedString,
        HashedLookup,
    )
    from ..adapters.persistence.storage.errors import StorageValidationError

    cases = (
        (
            "encrypted-string-bind",
            lambda: EncryptedString().process_bind_param(cast(str, 12345), cast(Dialect, None)),
        ),
        (
            "encrypted-bytes-bind",
            lambda: EncryptedBytes().process_bind_param(cast(bytes, "not-bytes"), cast(Dialect, None)),
        ),
        ("hashed-lookup-compute", lambda: HashedLookup.compute(cast(str, 12345))),
        (
            "hashed-lookup-bind",
            lambda: HashedLookup().process_bind_param(cast(str | bytes, 99.9), cast(Dialect, None)),
        ),
    )

    for case_id, call in cases:
        with pytest.raises(StorageValidationError) as exc_info:
            call()
        assert exc_info.type is StorageValidationError, case_id


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


def test_redaction_error_typing_registry_and_raise_sites() -> None:
    """RedactionError is registered, not a ValueError, and raised by redaction entrypoints."""
    from ..core.errors import ERROR_REGISTRY, RedactionError, get_registered_error_code
    from ..core.redaction import redact, redact_for_cli_output

    assert not issubclass(RedactionError, ValueError)
    cases = (
        ("redact", lambda: redact(cast(str, 12345), rules=())),
        ("redact-for-cli-output", lambda: redact_for_cli_output(cast(str, {"not": "a string"}))),
    )
    for case_id, call in cases:
        with pytest.raises(RedactionError) as exc_info:
            call()
        assert exc_info.type is RedactionError, case_id

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
    spec.loader.exec_module(mod)
    error_cls = vars(mod)["CensoSyncError"]
    assert isinstance(error_cls, type)
    return error_cls


def test_censo_sync_error_typing() -> None:
    """CensoSyncError is an AeatError subclass and not a ValueError.

    CensoSyncService cannot be instantiated in a pure unit context here;
    the contract tested is that the error class itself is properly typed.
    """
    from ..core.errors import AeatError

    censo_sync_error_cls = _load_censo_sync_error_class()
    assert issubclass(censo_sync_error_cls, AeatError)
    assert not issubclass(censo_sync_error_cls, ValueError)


# ---------------------------------------------------------------------------
# PortalValidationError for the build_entry factory
# ---------------------------------------------------------------------------


class _PortalEntryOverrides(TypedDict, total=False):
    """The two ``build_entry`` keywords these malformed-shape cases vary."""

    url: str
    path: str


def test_portal_validation_error_for_invalid_entry_shapes() -> None:
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

    cases: tuple[tuple[str, _PortalEntryOverrides], ...] = (
        ("url-and-path", {"url": "https://example.com", "path": "/also-present"}),
        ("path-without-leading-slash", {"path": "no-leading-slash"}),
    )
    for case_id, kwargs in cases:
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
        assert exc_info.type is PortalValidationError, case_id


# ---------------------------------------------------------------------------
# ProfileAnswerTypeError in profile parsing helpers
# ---------------------------------------------------------------------------


def test_profile_answer_type_error_raise_sites() -> None:
    """Profile parsing helpers raise ProfileAnswerTypeError for invalid typed answers."""
    from ..core.errors import ProfileAnswerTypeError
    from ..domain.contribuyente import CCAA, parse_descendiente_flag, parse_marriage_date_flag

    cases = (
        ("descendant-discapacidad", lambda: parse_descendiente_flag("NACIMIENTO=2010-01-01,DISCAPACIDAD=50")),
        ("marriage-date", lambda: parse_marriage_date_flag("not-a-date")),
        ("ccaa-label", lambda: CCAA.from_label("xyzzy")),
    )
    for case_id, call in cases:
        with pytest.raises(ProfileAnswerTypeError) as exc_info:
            call()
        assert exc_info.type is ProfileAnswerTypeError, case_id


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


def test_error_envelope_roundtrip_for_core_error_classes() -> None:
    """build_error_envelope produces valid ErrorEnvelopes for migrated core errors."""
    from ..core.errors import DecimalFormatError, RedactionError, build_error_envelope

    cases = (
        (DecimalFormatError("test decimal format"), "ERROR_DECIMAL_FORMAT"),
        (RedactionError("test redaction error"), "ERROR_REDACTION"),
    )
    for err, expected_code in cases:
        envelope = build_error_envelope(err)
        assert envelope.code == expected_code
        assert envelope.message
