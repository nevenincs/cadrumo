"""The local AI model pin table: what it admits, what it refuses, and that the catalogue reads it.

The catalogue takes its local role defaults, weight pins and memory floors from
this table; the expected values are read from the committed file itself, so a
copy kept anywhere else would show up here as a disagreement.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..local_ai_pins import LOCAL_AI_MODEL_PINS_RESOURCE, load_local_ai_model_pins, parse_local_ai_model_pins
from ..model_catalogue import DEFAULT_MODEL_BY_RUNTIME_AND_ROLE, MODEL_CATALOGUE, ModelRole, ModelRuntime
from ..resources.bundled_data import packaged_data

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DIGEST = "ab" * 32


def _model(name: str = "qwen3:1.7b", *, digest: str = _DIGEST, size: int = 10) -> str:
    return (
        f'\n[[models]]\nname = "{name}"\nmanifest_digest = "{digest}"\ndownload_bytes = {size}\n'
        'memory_bytes = 20\nlicence = "Apache-2.0"\ncommercial_use_permitted = true\n'
    )


def _table(*models: str, role_model: str = "qwen3:1.7b", hosts: str = '["registry.ollama.ai"]') -> str:
    return f'hosts = {hosts}\n\n[roles]\ntext_extraction = "{role_model}"\n' + "".join(models)


def test_a_well_formed_table_loads() -> None:
    pins = parse_local_ai_model_pins(_table(_model(), _model("qwen3-vl:2b")))

    assert pins.roles == {"text_extraction": "qwen3:1.7b"}
    pinned = pins.model("qwen3:1.7b")
    assert pinned is not None
    assert pinned.manifest_digest == _DIGEST
    assert pins.model("llama3:8b") is None


@pytest.mark.parametrize(
    "text",
    (
        _table(_model(), _model()),
        _table(_model(), role_model="llama3:8b"),
        _table(_model(digest="AB" * 32)),
        _table(_model(size=0)),
        _table(_model("Qwen3")),
        _table(_model(), hosts="[]"),
        _table(_model(), hosts='["registry.ollama.ai", "registry.ollama.ai"]'),
    ),
)
def test_a_table_that_could_admit_other_weights_or_roles_is_refused(text: str) -> None:
    with pytest.raises(ValidationError):
        parse_local_ai_model_pins(text)


def test_the_catalogue_reads_its_local_defaults_floors_and_weights_from_the_bundled_table() -> None:
    bundled = parse_local_ai_model_pins(packaged_data(*LOCAL_AI_MODEL_PINS_RESOURCE).read_text(encoding="utf-8"))

    assert bundled == load_local_ai_model_pins()
    assert DEFAULT_MODEL_BY_RUNTIME_AND_ROLE[ModelRuntime.LOCAL_OLLAMA] == {
        ModelRole(role): model for role, model in bundled.roles.items()
    }
    assert set(bundled.roles) == {role.value for role in ModelRole}
    local = [candidate for candidate in MODEL_CATALOGUE if candidate.runtime is ModelRuntime.LOCAL_OLLAMA]
    assert sorted(candidate.runtime_id for candidate in local) == sorted(pin.name for pin in bundled.models)
    for candidate in local:
        pin = bundled.model(candidate.runtime_id)
        assert pin is not None
        assert candidate.weights_pin is not None
        assert (candidate.weights_pin.digest, candidate.weights_pin.download_bytes) == (
            pin.manifest_digest,
            pin.download_bytes,
        )
        assert candidate.memory_requirement_bytes == pin.memory_bytes
        assert (candidate.licence.spdx_id, candidate.licence.commercial_use_permitted) == (
            pin.licence,
            pin.commercial_use_permitted,
        )
