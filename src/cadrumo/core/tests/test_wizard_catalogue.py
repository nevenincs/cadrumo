"""Real-behaviour tests for cadrumo.core.wizard_catalogue.

These tests assert:

1. After importing cadrumo.application.wizard.catalogue, the core registry
   slot is filled and get_setup_flow() / get_wizard_flows() return the
   same objects that _catalogue exposes as SETUP_FLOW / WIZARD_FLOWS.

2. No deferred lazy upward imports from cadrumo.application.wizard.catalogue
   remain in cadrumo.domain.deadlines._profiles or cadrumo.domain.contribuyente._keys.
   A fresh Python interpreter imports those domain modules and asserts the
   application wizard catalogue was not loaded as an import-time side effect.

See Also:
    :mod:`~core.wizard_catalogue`
        Core registry slot this test expects domain code to consume.
    :mod:`~application.wizard.catalogue`
        Application-owned descriptor catalogue that registers into the core slot.
    :mod:`~domain.contribuyente._keys`
        Domain registry that must receive pushed profile keys without pulling
        upward into the application wizard layer.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# contract gate 1: SETUP_FLOW / WIZARD_FLOWS round-trip identity from core
# ---------------------------------------------------------------------------


def test_setup_flow_round_trip_identity() -> None:
    """get_setup_flow() returns the exact SETUP_FLOW object from _catalogue."""

    # Import catalogue first — its module body calls register_wizard_catalogue.
    import cadrumo.application.wizard.catalogue as catalogue
    from ..wizard_catalogue import get_setup_flow

    assert get_setup_flow() is catalogue.SETUP_FLOW, (
        "get_setup_flow() must return the identical SETUP_FLOW object "
        "that _catalogue registered — got a different object"
    )


def test_wizard_flows_round_trip_identity() -> None:
    """get_wizard_flows() returns the exact WIZARD_FLOWS tuple from _catalogue."""

    import cadrumo.application.wizard.catalogue as catalogue
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


def test_no_deferred_upward_import_from_wizard_catalogue() -> None:
    """Domain modules must not import from the application wizard catalogue."""

    script = """
import importlib
import sys

for module_name in (
    "cadrumo.domain.deadlines._profiles",
    "cadrumo.domain.contribuyente._keys",
):
    importlib.import_module(module_name)

if "cadrumo.application.wizard.catalogue" in sys.modules:
    raise SystemExit("domain imports loaded cadrumo.application.wizard.catalogue")
"""

    result = subprocess.run(  # noqa: S603 - fixed interpreter and literal script for import isolation.
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_wizard_catalogue_exports_are_callable() -> None:
    """All public symbols in cadrumo.core.wizard_catalogue are importable and callable."""

    from .. import wizard_catalogue
    from ..errors import CoreError

    assert callable(wizard_catalogue.register_wizard_catalogue)
    assert callable(wizard_catalogue.get_setup_flow)
    assert callable(wizard_catalogue.get_wizard_flows)
    assert issubclass(wizard_catalogue.WizardCatalogueNotRegisteredError, CoreError)
