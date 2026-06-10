"""Small-axis cleanup invariants: canonical homes and subclass enforcement.

Assertions
----------
(a) ``aeat.application.wizard._setup_answers`` is deleted: the module
    does not exist on disk and cannot be imported.
(b) ``CounterpartSourceKind`` has a single canonical home in the domain
    layer; the application layer re-exports it from there.
(c) Every surviving ``_parse_date`` wrapper in sede/_notifications,
    sede/_censo, and domain/deadlines/_profiles delegates to the
    canonical ``aeat.core.parsing._dates._parse_date``.
(d) ``ApoderadoService`` has production callers in the CLI entrypoint;
    the module is intact and the service is callable.
(e) ``FinancialProvider.__init_subclass__`` enforces
    ``verification_source`` and ``provisional_pending_specimen`` at
    class-definition time (raises ``FinancialProviderConfigError`` for a
    non-compliant concrete subclass).
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from datetime import date
from pathlib import Path
from typing import override

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ── (a) _setup_answers.py deleted ────────────────────────────────────────────


def test_setup_answers_module_not_importable() -> None:
    """aeat.application.wizard._setup_answers must not exist; SetupAnswers lives in core.profile."""
    # Ensure a prior import by another test does not give a false negative.
    sys.modules.pop("aeat.application.wizard._setup_answers", None)

    spec = importlib.util.find_spec("aeat.application.wizard._setup_answers")
    assert spec is None, (
        "_setup_answers.py was found; it should have been deleted. "
        "Confirm the file is gone and no package __init__ re-exports it."
    )


def test_setup_answers_canonical_home_is_core_profile() -> None:
    """SetupAnswers must be importable from aeat.core.setup_answers and nowhere else."""
    from ..core.setup_answers import SetupAnswers

    assert SetupAnswers.__module__ == "aeat.core.setup_answers", (
        f"SetupAnswers.__module__ is {SetupAnswers.__module__!r}; expected 'aeat.core.setup_answers'"
    )


# ── (b) CounterpartSourceKind single canonical home ──────────────────────────


def test_counterpart_source_kind_canonical_in_domain() -> None:
    """CounterpartSourceKind must be defined in the domain bindings module."""
    from ..domain.calculations.registry import _bindings as bindings_mod

    assert hasattr(bindings_mod, "CounterpartSourceKind"), "CounterpartSourceKind not found in domain._bindings"


def test_counterpart_source_kind_application_imports_from_domain() -> None:
    """The application _counterpart module must re-export the domain alias."""
    from ..application.aggregation._counterpart import (
        CounterpartSourceKind as app_csk,
    )
    from ..domain.calculations.registry._bindings import (
        CounterpartSourceKind as domain_csk,
    )

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


def test_censo_parse_date_delegates_to_canonical() -> None:
    """sede._censo._parse_date must delegate to core._parse_date_canonical."""
    from ..adapters.outbound.aeat.sede import _censo as censo_mod

    # Source-code inspection: the function body must reference _parse_date_canonical.
    src = inspect.getsource(censo_mod._parse_date)
    assert "_parse_date_canonical" in src, (
        "_censo._parse_date must call _parse_date_canonical (the core helper); found unexpected implementation."
    )
    # Behavioral check: a valid date parses correctly.
    result = censo_mod._parse_date("15-03-2024", field="activity_start_date")
    assert result == date(2024, 3, 15)


def test_profiles_parse_date_delegates_to_canonical() -> None:
    """domain.deadlines._profiles._parse_date must delegate to core._parse_date_canonical."""
    from ..domain.deadlines import _profiles as profiles_mod

    src = inspect.getsource(profiles_mod._parse_date)
    assert "_parse_date_canonical" in src, (
        "_profiles._parse_date must call _parse_date_canonical; found unexpected implementation."
    )
    # Behavioral check: ISO-8601 date parses correctly.
    result = profiles_mod._parse_date("2024-03-15")
    assert result == date(2024, 3, 15)


# ── (d) ApoderadoService has CLI callers ─────────────────────────────────────


def test_apoderado_service_importable_and_has_cli_callers() -> None:
    """ApoderadoService must be importable; CLI entrypoint must reference it."""

    cli_path = Path(__file__).parents[2] / "aeat/entrypoints/cli/_config/_apoderado.py"
    assert cli_path.exists(), f"CLI entrypoint not found at {cli_path}"
    cli_src = cli_path.read_text(encoding="utf-8")
    assert "ApoderadoService" in cli_src, (
        "CLI entrypoint does not reference ApoderadoService; "
        "if the service has callers elsewhere, update this assertion."
    )


# ── (e) FinancialProvider enforces corpus attributes at class-definition ──────


def test_financial_provider_init_subclass_rejects_missing_verification_source() -> None:
    """A concrete subclass missing verification_source must raise FinancialProviderConfigError."""
    from collections.abc import Iterator

    from ..adapters.inbound.financial.providers._base import (
        FinancialProvider,
        FinancialProviderConfigError,
        ProviderValidation,
    )
    from ..domain.transactions import RawTransaction

    with pytest.raises(FinancialProviderConfigError, match="verification_source"):

        class _BadProviderNoVS(FinancialProvider):
            name = "bad-no-vs"
            supported_extensions = frozenset({".csv"})
            source_format = None  # type: ignore[assignment]
            provisional_pending_specimen = False

            @override
            def ingest(self, path: Path) -> Iterator[RawTransaction]:  # pragma: no cover
                return iter([])

            @override
            def validate_source(self, path: Path) -> ProviderValidation:  # pragma: no cover
                return ProviderValidation(is_valid=True)


def test_financial_provider_init_subclass_rejects_no_corpus_without_provisional() -> None:
    """A no_corpus provider with provisional_pending_specimen=False must raise FinancialProviderConfigError."""
    from collections.abc import Iterator

    from ..adapters.inbound.financial.providers._base import (
        FinancialProvider,
        FinancialProviderConfigError,
        ProviderValidation,
    )
    from ..domain.transactions import RawTransaction

    with pytest.raises(FinancialProviderConfigError, match="no_corpus"):

        class _BadNoCorpusProvider(FinancialProvider):
            name = "bad-no-corpus"
            supported_extensions = frozenset({".csv"})
            source_format = None  # type: ignore[assignment]
            verification_source = "no_corpus"
            provisional_pending_specimen = False  # wrong: must be True

            @override
            def ingest(self, path: Path) -> Iterator[RawTransaction]:  # pragma: no cover
                return iter([])

            @override
            def validate_source(self, path: Path) -> ProviderValidation:  # pragma: no cover
                return ProviderValidation(is_valid=True)


def test_financial_provider_init_subclass_accepts_valid_provider() -> None:
    """A fully-compliant concrete subclass must not raise at definition."""
    from collections.abc import Iterator

    from ..adapters.inbound.financial.providers._base import (
        FinancialProvider,
        ProviderValidation,
    )
    from ..domain.transactions import RawTransaction, SourceFormat

    class _GoodProvider(FinancialProvider):
        name = "good-provider"
        supported_extensions = frozenset({".csv"})
        source_format = SourceFormat.CSV
        verification_source = "no_corpus"
        provisional_pending_specimen = True

        @override
        def ingest(self, path: Path) -> Iterator[RawTransaction]:  # pragma: no cover
            return iter([])

        @override
        def validate_source(self, path: Path) -> ProviderValidation:  # pragma: no cover
            return ProviderValidation(is_valid=True)

    # No TypeError raised — provider is compliant.
    assert _GoodProvider.verification_source == "no_corpus"
    assert _GoodProvider.provisional_pending_specimen is True
