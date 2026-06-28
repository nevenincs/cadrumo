"""Real-behaviour tests for aeat.core.wizard_catalogue.

These tests assert:

1. After importing aeat.application.wizard._catalogue, the core registry
   slot is filled and get_setup_flow() / get_wizard_flows() return the
   same objects that _catalogue exposes as SETUP_FLOW / WIZARD_FLOWS.

2. No deferred lazy upward imports from aeat.application.wizard._catalogue
   remain in aeat.domain.deadlines._profiles or aeat.domain.contribuyente._keys.
   The check reads the source text and greps for the bypass pattern, which
   is the real enforcement surface — static analysis on the source file is
   independent of import order.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _source_of(module_path: str) -> str:
    """Return the source text for the named module."""
    spec = importlib.util.find_spec(module_path)
    assert spec is not None, f"Cannot find module {module_path!r}"
    assert spec.origin is not None
    return Path(spec.origin).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# contract gate 1: SETUP_FLOW / WIZARD_FLOWS round-trip identity from core
# ---------------------------------------------------------------------------


def test_setup_flow_round_trip_identity() -> None:
    """get_setup_flow() returns the exact SETUP_FLOW object from _catalogue."""

    # Import _catalogue first — its module body calls register_wizard_catalogue.
    from ...application.wizard import _catalogue as catalogue
    from ..wizard_catalogue import get_setup_flow

    assert get_setup_flow() is catalogue.SETUP_FLOW, (
        "get_setup_flow() must return the identical SETUP_FLOW object "
        "that _catalogue registered — got a different object"
    )


def test_wizard_flows_round_trip_identity() -> None:
    """get_wizard_flows() returns the exact WIZARD_FLOWS tuple from _catalogue."""

    from ...application.wizard import _catalogue as catalogue
    from ..wizard_catalogue import get_wizard_flows

    assert get_wizard_flows() is catalogue.WIZARD_FLOWS, (
        "get_wizard_flows() must return the identical WIZARD_FLOWS tuple "
        "that _catalogue registered — got a different object"
    )


def test_setup_flow_id_is_setup() -> None:
    """The registered SETUP_FLOW carries the canonical 'setup' identifier."""

    from ..wizard_catalogue import get_setup_flow

    flow = get_setup_flow()
    assert flow.id == "setup", f"Expected flow.id == 'setup', got {flow.id!r}"


def test_wizard_flows_contains_setup_flow() -> None:
    """WIZARD_FLOWS is a tuple that contains the SETUP_FLOW descriptor."""

    from ..wizard_catalogue import get_setup_flow, get_wizard_flows

    flows = get_wizard_flows()
    assert isinstance(flows, tuple), f"WIZARD_FLOWS must be a tuple, got {type(flows)}"
    assert len(flows) >= 1, "WIZARD_FLOWS must contain at least one flow"
    setup = get_setup_flow()
    assert setup in flows, "SETUP_FLOW must be a member of WIZARD_FLOWS"


# ---------------------------------------------------------------------------
# contract gate 2: no deferred lazy upward imports remain in domain modules
# ---------------------------------------------------------------------------

_UPWARD_PATTERN = "from ...application.wizard._catalogue import"
_ALT_UPWARD_PATTERN = "from aeat.application.wizard._catalogue import"


def test_no_deferred_upward_import_in_deadlines_profiles() -> None:
    """aeat.domain.deadlines._profiles must not import from _catalogue (lazy or top-level)."""

    source = _source_of("aeat.domain.deadlines._profiles")
    assert _UPWARD_PATTERN not in source, (
        "aeat.domain.deadlines._profiles still contains a direct import from "
        "aeat.application.wizard._catalogue. Remove it and use get_setup_flow() from "
        "aeat.core.wizard_catalogue instead."
    )
    assert _ALT_UPWARD_PATTERN not in source, (
        "aeat.domain.deadlines._profiles still contains an absolute import from "
        "aeat.application.wizard._catalogue. Remove it and use get_setup_flow() from "
        "aeat.core.wizard_catalogue instead."
    )


def test_no_deferred_upward_import_in_profile_keys() -> None:
    """aeat.domain.contribuyente._keys must not import from _catalogue (lazy or top-level)."""

    source = _source_of("aeat.domain.contribuyente._keys")
    assert _UPWARD_PATTERN not in source, (
        "aeat.domain.contribuyente._keys still contains a direct import from "
        "aeat.application.wizard._catalogue. Remove it and use get_wizard_flows() from "
        "aeat.core.wizard_catalogue instead."
    )
    assert _ALT_UPWARD_PATTERN not in source, (
        "aeat.domain.contribuyente._keys still contains an absolute import from "
        "aeat.application.wizard._catalogue. Remove it and use get_wizard_flows() from "
        "aeat.core.wizard_catalogue instead."
    )


def test_wizard_catalogue_exports_are_callable() -> None:
    """All public symbols in aeat.core.wizard_catalogue are importable and callable."""

    from .. import wizard_catalogue
    from ..errors import CoreError

    assert callable(wizard_catalogue.register_wizard_catalogue)
    assert callable(wizard_catalogue.get_setup_flow)
    assert callable(wizard_catalogue.get_wizard_flows)
    assert issubclass(wizard_catalogue.WizardCatalogueNotRegisteredError, CoreError)
