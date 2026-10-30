"""Activity-asset read controls declare their finite translation vocabulary."""

from __future__ import annotations

import pytest

from .._ast_scanner import scan_namespace_markers_in_text, scan_source_text
from .._paths import SRC_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("relative_path", "prefix", "suffixes"),
    [
        (
            "entrypoints/cli/_app_ledger_actividad_asset_command_specs.py",
            "cli.app.ledger.actividad_asset.",
            ("list_help", "plan_help", "timeline_help", "form_options_help", "acquisition_candidates_help"),
        ),
        (
            "entrypoints/tui/ledger/actividad_asset.py",
            "tui.ledger.activity_asset.",
            ("list", "plan", "timeline", "acquisition_candidates"),
        ),
    ],
)
def test_every_read_key_is_discovered_without_an_unbounded_family(
    relative_path: str, prefix: str, suffixes: tuple[str, ...]
) -> None:
    path = SRC_DIR / relative_path
    source = path.read_text(encoding="utf-8")
    discovered = scan_source_text(source, filename=str(path))
    assert {prefix + suffix for suffix in suffixes} <= discovered
    assert prefix + "*" not in scan_namespace_markers_in_text(source, filename=str(path))
