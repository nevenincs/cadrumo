"""Contract pins for the wizard profile-schema re-export bridge.

``_wizard_payloads.py`` (see its module docstring) exists solely to import
``ConfigProfileCreateResult`` / ``ConfigProfileEditResult`` from
:mod:`application.wizard` so their ``@register_schema`` decorators fire before
the CLI capability manifest is built — a fresh-interpreter, subprocess-level
proof of that end-to-end behaviour (deletion silently drops both profile verbs
off the manifest) lives in
``test_json_schema_conformance.py::test_wizard_profile_schemas_reach_the_manifest_only_via_the_bridge_module``
/ ``test_deleting_the_bridge_module_drops_both_profile_schemas``.

This module pins the two things the bridge itself is responsible for that the
subprocess guard does not check: that its re-exported names are the SAME
objects as the wizard's canonical classes (never a diverged copy), and that
``SCHEMA_REGISTRY`` carries both under their documented command keys once the
bridge is imported.
"""

from __future__ import annotations

import pytest

from ....application import wizard
from ....core.json_contract import SCHEMA_REGISTRY
from .. import _wizard_payloads

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_reexported_result_classes_are_identity_equal_to_the_wizard_originals() -> None:
    """The bridge must not fork a second copy of either result class."""
    assert _wizard_payloads.ConfigProfileCreateResult is wizard.ConfigProfileCreateResult
    assert _wizard_payloads.ConfigProfileEditResult is wizard.ConfigProfileEditResult


def test_all_declares_exactly_the_two_wizard_result_classes() -> None:
    """``__all__`` is the bridge's whole purpose; it must name only the two classes."""
    assert _wizard_payloads.__all__ == ["ConfigProfileCreateResult", "ConfigProfileEditResult"]


def test_importing_the_bridge_registers_both_profile_schema_keys() -> None:
    """Importing the bridge is what makes ``register_schema`` fire for these two classes.

    Asserts the registry entries resolve to the exact re-exported objects, not
    merely that the keys are present (which a same-named but differently
    implemented class could also satisfy).
    """
    assert SCHEMA_REGISTRY["config.profile.create"] is _wizard_payloads.ConfigProfileCreateResult
    assert SCHEMA_REGISTRY["config.profile.edit"] is _wizard_payloads.ConfigProfileEditResult
