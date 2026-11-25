"""The desktop host's provider wire structs carry exactly the field names of the service's models.

The host relays each provider answer and sign-in snapshot in the service's field names, and the
window's generated types are derived from the service's models, so a field added on one side only
would be dropped or never filled. This reads the host's own source.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import BaseModel

from ...providers.application.contracts import ProviderSettingsAnswer, ProviderSignInSnapshot, ProviderStatusEntry

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROOT = Path(__file__).resolve().parents[4]
_WIRE = _ROOT / "native" / "desktop" / "src-tauri" / "src" / "shell" / "provider_settings" / "wire.rs"


def _host_fields(struct: str) -> set[str]:
    source = _WIRE.read_text(encoding="utf-8")
    block = re.search(r"pub struct " + struct + r" \{(.*?)\n\}", source, re.DOTALL)
    assert block is not None
    return set(re.findall(r"^\s*pub (\w+):", block.group(1), re.MULTILINE))


@pytest.mark.parametrize(
    ("struct", "model"),
    [
        ("Entry", ProviderStatusEntry),
        ("Status", ProviderSettingsAnswer),
        ("SignInSnapshot", ProviderSignInSnapshot),
    ],
)
def test_host_struct_fields_equal_the_service_model_fields(struct: str, model: type[BaseModel]) -> None:
    assert _host_fields(struct) == set(model.model_fields)
