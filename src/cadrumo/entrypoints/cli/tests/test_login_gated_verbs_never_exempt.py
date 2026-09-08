"""Security gate for archive output leaving the encrypted store."""

from __future__ import annotations

import pytest

from .._bootstrap_exempt import BOOTSTRAP_EXEMPT_VERB_PATHS, is_bootstrap_exempt
from ..command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_live_profile_archive_export_stays_login_gated() -> None:
    """Derive the live leaf and prove no exact or prefix exemption reaches it.

    Export emits a portable copy of encrypted financial records. A
    target-scoped unlock does not establish authentication recency, so this
    output path must retain the ordinary login gate.
    """
    node = next(node for node in COMMAND_GRAPH.nodes() if node.spec.key == "config_profile_archive_export")
    assert node.path[0] == "aeat"
    operator_path = " ".join(node.path[1:])

    swallowing = tuple(
        exempt
        for exempt in BOOTSTRAP_EXEMPT_VERB_PATHS
        if operator_path == exempt or operator_path.startswith(f"{exempt} ")
    )

    assert not swallowing, f"bootstrap exemption(s) {swallowing} bypass authentication for {operator_path!r}"
    assert not is_bootstrap_exempt(operator_path)
