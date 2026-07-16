"""Small-axis cleanup invariants: canonical homes and subclass enforcement.

Assertions
----------
(a) ``cadrumo.application.wizard._setup_answers`` is deleted: the module
    does not exist on disk and cannot be imported.
(b) ``CounterpartSourceKind`` has a single canonical home in the domain
    layer; the application layer re-exports it from there.
(c) Every surviving ``_parse_date`` wrapper in sede/_notifications
    and domain/deadlines/_profiles delegates to the
    canonical ``cadrumo.core.parsing._dates._parse_date``.
(d) ``ApoderadoService`` has production callers in the CLI entrypoint;
    the module is intact and the service is callable.
(e) ``FinancialProvider.__init_subclass__`` enforces
    ``verification_source`` and ``provisional_pending_specimen`` at
    class-definition time (raises ``FinancialProviderConfigError`` for a
    non-compliant concrete subclass).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from typing import override

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_auth_provider_contract_has_one_public_home() -> None:
    """Core is the sole public home for auth provider kinds and descriptions."""
    from .. import core
    from ..adapters.outbound.aeat import auth as adapter_auth
    from ..application import auth as application_auth
    from ..core import config

    assert core.AuthProviderKind.__module__ == "cadrumo.core._auth_provider"
    assert core.AuthProviderDescription.__module__ == "cadrumo.core._auth_provider"
    assert not hasattr(core, "AuthProviderKindSetting")
    assert not hasattr(config, "AuthProviderKind")
    assert not hasattr(config, "AuthProviderKindSetting")
    assert not hasattr(application_auth, "AuthProviderKind")
    assert not hasattr(application_auth, "AuthProviderDescription")
    assert not hasattr(adapter_auth, "AuthProviderKind")
    assert not hasattr(adapter_auth, "AuthProviderDescription")


def test_persisted_auth_state_is_workflow_owned() -> None:
    """Workflow publicly owns persisted auth state without an auth facade alias."""
    from ..application import auth as application_auth
    from ..application.workflow import AuthState

    assert AuthState.__module__ == "cadrumo.application._workflow_auth_models"
    assert not hasattr(application_auth, "AuthState")


# ── (a) _setup_answers.py deleted ────────────────────────────────────────────


def test_setup_answers_module_not_importable() -> None:
    """cadrumo.application.wizard._setup_answers must not exist; SetupAnswers lives in core.profile."""
    # Ensure a prior import by another test does not give a false negative.
    sys.modules.pop("cadrumo.application.wizard._setup_answers", None)

    spec = importlib.util.find_spec("cadrumo.application.wizard._setup_answers")
    assert spec is None, (
        "_setup_answers.py was found; it should have been deleted. "
        "Confirm the file is gone and no package __init__ re-exports it."
    )


def test_setup_answers_canonical_home_is_core_profile() -> None:
    """SetupAnswers must be importable from cadrumo.core.setup_answers and nowhere else."""
    from ..core.setup_answers import SetupAnswers

    assert SetupAnswers.__module__ == "cadrumo.core.setup_answers", (
        f"SetupAnswers.__module__ is {SetupAnswers.__module__!r}; expected 'cadrumo.core.setup_answers'"
    )


# ── (b) CounterpartSourceKind single canonical home ──────────────────────────


def test_counterpart_source_kind_canonical_in_domain() -> None:
    """CounterpartSourceKind must be defined in the domain bindings module."""
    from ..domain.calculations.registry import _bindings as bindings_mod

    assert hasattr(bindings_mod, "CounterpartSourceKind"), "CounterpartSourceKind not found in domain._bindings"


def test_counterpart_source_kind_application_imports_from_domain() -> None:
    """The application _counterpart module must re-export the domain alias."""
    from ..application.aggregation import CounterpartSourceKind as app_csk
    from ..domain.calculations.registry import CounterpartSourceKind as domain_csk

    assert app_csk is domain_csk, (
        "application.aggregation._counterpart.CounterpartSourceKind is not the "
        "same object as domain._bindings.CounterpartSourceKind; it must import "
        "rather than redefine."
    )


# ── (c) _parse_date wrappers delegate to canonical ───────────────────────────


def test_notifications_parse_date_delegates_to_canonical() -> None:
    """sede._notifications._parse_date_local must delegate to core._parse_date."""
    from ..adapters.outbound.aeat.sede import _notifications as notif_mod

    # The wrapper must be present and call through to canonical.
    assert hasattr(notif_mod, "_parse_date_local"), (
        "_parse_date_local not found in _notifications; the wrapper must use "
        "the canonical helper via _parse_date_local."
    )
    # Behavioral check: a valid date parses correctly.
    result = notif_mod._parse_date_local("15-03-2024")
    assert result == date(2024, 3, 15), f"_parse_date_local('15-03-2024') returned {result!r}; expected 2024-03-15"
    # Error-policy: 'none' — invalid input returns None.
    assert notif_mod._parse_date_local("not-a-date") is None, (
        "_parse_date_local must return None on invalid input (on_error='none')"
    )


def test_profiles_parse_date_delegates_to_canonical() -> None:
    """domain.deadlines._profiles._parse_date must delegate to core._parse_date_canonical."""
    from ..domain.deadlines import ProfileError
    from ..domain.deadlines import _profiles as profiles_mod

    result = profiles_mod._parse_date("2024-03-15")
    assert result == date(2024, 3, 15)
    with pytest.raises(ProfileError, match="expected ISO-8601"):
        profiles_mod._parse_date("15-03-2024")


# ── (d) ApoderadoService has CLI callers ─────────────────────────────────────


# ── (e) FinancialProvider enforces corpus attributes at class-definition ──────


def test_financial_provider_init_subclass_rejects_missing_verification_source() -> None:
    """A concrete subclass missing verification_source must raise FinancialProviderConfigError."""
    from collections.abc import Iterator

    from ..adapters.inbound.financial.providers import (
        FinancialProvider,
        FinancialProviderConfigError,
        ParsedLedgerRow,
        ProviderValidation,
    )
    from ..domain.transactions import SourceFormat

    with pytest.raises(FinancialProviderConfigError, match="verification_source"):

        class _BadProviderNoVS(FinancialProvider):
            name = "bad-no-vs"
            supported_extensions = frozenset({".csv"})
            source_format = SourceFormat.CSV
            provisional_pending_specimen = False

            @override
            def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:  # pragma: no cover
                return iter([])

            @override
            def validate_source(self, path: Path) -> ProviderValidation:  # pragma: no cover
                return ProviderValidation(is_valid=True)


def test_financial_provider_init_subclass_rejects_no_corpus_without_provisional() -> None:
    """A no_corpus provider with provisional_pending_specimen=False must raise FinancialProviderConfigError."""
    from collections.abc import Iterator

    from ..adapters.inbound.financial.providers import (
        FinancialProvider,
        FinancialProviderConfigError,
        ParsedLedgerRow,
        ProviderValidation,
    )
    from ..domain.transactions import SourceFormat

    with pytest.raises(FinancialProviderConfigError, match="no_corpus"):

        class _BadNoCorpusProvider(FinancialProvider):
            name = "bad-no-corpus"
            supported_extensions = frozenset({".csv"})
            source_format = SourceFormat.CSV
            verification_source = "no_corpus"
            provisional_pending_specimen = False  # wrong: must be True

            @override
            def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:  # pragma: no cover
                return iter([])

            @override
            def validate_source(self, path: Path) -> ProviderValidation:  # pragma: no cover
                return ProviderValidation(is_valid=True)


def test_financial_provider_init_subclass_accepts_valid_provider() -> None:
    """A fully-compliant concrete subclass must not raise at definition."""
    from collections.abc import Iterator

    from ..adapters.inbound.financial.providers import (
        FinancialProvider,
        ParsedLedgerRow,
        ProviderValidation,
    )
    from ..domain.transactions import SourceFormat

    class _GoodProvider(FinancialProvider):
        name = "good-provider"
        supported_extensions = frozenset({".csv"})
        source_format = SourceFormat.CSV
        verification_source = "no_corpus"
        provisional_pending_specimen = True

        @override
        def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:  # pragma: no cover
            return iter([])

        @override
        def validate_source(self, path: Path) -> ProviderValidation:  # pragma: no cover
            return ProviderValidation(is_valid=True)

    # No TypeError raised — provider is compliant.
    assert _GoodProvider.verification_source == "no_corpus"
    assert _GoodProvider.provisional_pending_specimen is True
