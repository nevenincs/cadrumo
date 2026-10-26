"""Documentation prerequisites use real distribution metadata before launching Sphinx."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ..docs_build import require_host_product_metadata
from ..docs_stage import DocsPackagingError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("installed_version", [None, "1.2.2", "1.2.3"])
def test_documentation_requires_selected_checkout_distribution_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, installed_version: str | None
) -> None:
    if installed_version is not None:
        metadata = tmp_path / f"cadrumo-{installed_version}.dist-info"
        metadata.mkdir()
        (metadata / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: cadrumo\nVersion: {installed_version}\n", encoding="utf-8"
        )
    monkeypatch.setattr(sys, "path", [str(tmp_path)])
    if installed_version == "1.2.3":
        require_host_product_metadata("1.2.3")
    else:
        with pytest.raises(DocsPackagingError, match=r"lacks|requires 1\.2\.3"):
            require_host_product_metadata("1.2.3")
