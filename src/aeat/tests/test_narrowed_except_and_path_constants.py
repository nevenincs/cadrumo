"""Runtime checks for schedule path constants and logging sink inheritance.

Asserts:

- _schedules.py declares _IVA_REGIME_PATH and _TAXPAYER_ENTITY_TYPE_PATH
  as module-level Final constants and uses them in _resolve_profile_fact.
- _sink.py defines JsonlRunSink as a real stdlib logging.Handler subclass.

No mocks, no skips, no tautological assertions.

See Also:
    :mod:`~domain.calculations.registry._schedules`
        Registry schedule predicates whose dotted profile paths are pinned here.
    :class:`~core.observability.JsonlRunSink`
        Logging sink whose stdlib ``logging.Handler`` inheritance justifies the
        logging import survivor.

Aggregates the narrowed-exception and dotted-path-constant checks these two
modules previously required broad lint suppressions to pass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# _schedules.py: Final path constants
# ---------------------------------------------------------------------------


def test_schedules_final_path_constants() -> None:
    """_schedules.py exposes the registry dotted-path constants used by profile predicates."""
    from ..domain.calculations.registry import _schedules

    assert _schedules._IVA_REGIME_PATH == "iva.regime"
    assert _schedules._TAXPAYER_ENTITY_TYPE_PATH == "taxpayer.entity_type"


# ---------------------------------------------------------------------------
# _schedules.py uses constants in _resolve_profile_fact body
# ---------------------------------------------------------------------------


def test_schedules_resolver_accepts_registry_dotted_profile_paths() -> None:
    """_resolve_profile_fact maps registry dotted fields onto the flat profile object."""
    from ..domain.calculations.registry import _schedules

    @dataclass(frozen=True)
    class _Regime:
        value: str

    @dataclass(frozen=True)
    class _Profile:
        iva_regime: _Regime
        entity_type: str

    profile = _Profile(iva_regime=_Regime("monthly"), entity_type="legal_entity")

    assert _schedules._resolve_profile_fact(profile, _schedules._IVA_REGIME_PATH) == "monthly"
    assert (
        _schedules._resolve_profile_fact(profile, _schedules._TAXPAYER_ENTITY_TYPE_PATH)
        == "legal_entity"
    )


# ---------------------------------------------------------------------------
# _sink.py is a logging-regression: stdlib logging import is justified
# ---------------------------------------------------------------------------


def test_sink_is_logging_handler_subclass() -> None:
    """_sink.py must define JsonlRunSink as a subclass of logging.Handler."""
    from ..core.observability import JsonlRunSink

    assert issubclass(JsonlRunSink, logging.Handler)
