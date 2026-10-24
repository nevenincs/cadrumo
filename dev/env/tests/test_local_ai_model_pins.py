"""Gate: the committed local AI model pins are what the registry manifests derive, from declared hosts.

Nothing here downloads. The manifests under ``data/ollama_manifests`` are the
exact bytes the model registry served for each pinned tag, recorded when the
table was last regenerated; the generator runs on them through a fetch that
serves only those bytes, so its derivation and rendering are the real ones.
The defect cases change a copy of the committed table or a manifest and must
each be reported or refused.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from cadrumo.core.local_ai_pins import LocalAiModelPins

from .. import local_ai_pins
from ..local_ai_model_pins import (
    MODELS_PATH,
    check_model_pins,
    declared_hosts,
    generate_model_pins,
    load_model_pins,
    manifest_facts,
    manifest_url,
    render_model_pins,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MANIFESTS: Final = Path(__file__).parent / "data" / "ollama_manifests"


def _recorded(url: str) -> tuple[bytes, frozenset[str]]:
    prefix = "https://registry.ollama.ai/v2/library/"
    assert url.startswith(prefix)
    model, _, tag = url.removeprefix(prefix).partition("/manifests/")
    return (_MANIFESTS / f"{model}_{tag}.json").read_bytes(), frozenset({"registry.ollama.ai"})


@pytest.fixture(scope="module")
def committed() -> LocalAiModelPins:
    return load_model_pins()


def test_the_committed_table_names_only_declared_model_registry_hosts(committed: LocalAiModelPins) -> None:
    assert check_model_pins(committed, MODELS_PATH.read_text(encoding="utf-8")) == []
    assert set(committed.hosts) <= declared_hosts()
    assert declared_hosts(), "the model registry host group is declared"


def test_every_pin_is_what_its_recorded_manifest_derives(committed: LocalAiModelPins) -> None:
    regenerated = generate_model_pins(committed, _recorded)

    assert regenerated == committed
    assert render_model_pins(regenerated) == MODELS_PATH.read_text(encoding="utf-8")


def test_a_manifest_digest_is_of_its_exact_bytes_and_its_size_counts_config_and_layers() -> None:
    raw = (_MANIFESTS / "qwen3_1.7b.json").read_bytes()
    document = json.loads(raw)
    facts = manifest_facts(raw)

    assert facts.download_bytes == document["config"]["size"] + sum(layer["size"] for layer in document["layers"])
    assert manifest_facts(json.dumps(document, indent=2).encode()).manifest_digest != facts.manifest_digest
    assert manifest_url("qwen3-vl:2b") == "https://registry.ollama.ai/v2/library/qwen3-vl/manifests/2b"


def test_a_retagged_model_changes_its_pin(committed: LocalAiModelPins) -> None:
    def retagged(url: str) -> tuple[bytes, frozenset[str]]:
        body, hosts = _recorded(url)
        document = json.loads(body)
        document["layers"][0]["size"] += 1
        return json.dumps(document).encode(), hosts

    regenerated = generate_model_pins(committed, retagged)

    assert regenerated != committed
    assert check_model_pins(regenerated, MODELS_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "document",
    (
        {"schemaVersion": 1, "config": {"digest": "sha256:" + "0" * 64, "size": 1}, "layers": []},
        {"schemaVersion": 2, "config": {"digest": "sha256:" + "0" * 64, "size": 1}, "layers": []},
        {"schemaVersion": 2, "config": {"digest": "md5:00", "size": 1}, "layers": [{"digest": "x", "size": 1}]},
        {"schemaVersion": 2, "config": {"digest": "sha256:" + "0" * 64, "size": "1"}, "layers": []},
    ),
)
def test_a_manifest_that_is_not_a_registry_image_manifest_is_refused(document: object) -> None:
    with pytest.raises(ValidationError):
        manifest_facts(json.dumps(document).encode())


def test_a_host_outside_the_declared_group_is_reported(committed: LocalAiModelPins) -> None:
    pins = committed.model_copy(update={"hosts": tuple(sorted((*committed.hosts, "mirror.example")))})

    assert any("undeclared hosts" in problem for problem in check_model_pins(pins, render_model_pins(pins)))


def test_a_table_without_the_registry_host_is_reported(committed: LocalAiModelPins) -> None:
    pins = committed.model_copy(update={"hosts": ("mirror.example",)})
    problems = check_model_pins(pins, render_model_pins(pins))

    assert any("does not name" in problem for problem in problems)


def test_a_hand_edited_derived_fact_or_layout_is_reported(committed: LocalAiModelPins) -> None:
    text = MODELS_PATH.read_text(encoding="utf-8")
    first = committed.models[0]
    edited = text.replace(f"download_bytes = {first.download_bytes}", f"download_bytes = {first.download_bytes + 1}")
    assert edited != text
    hand_edited = load_model_pins(edited)
    assert generate_model_pins(hand_edited, _recorded) != hand_edited
    assert generate_model_pins(hand_edited, _recorded) == committed

    relaid = text.replace("[roles]", "[roles]\n")
    assert any("not what the generator renders" in problem for problem in check_model_pins(committed, relaid))


def test_the_pin_command_checks_both_tables(capsys: pytest.CaptureFixture[str]) -> None:
    assert local_ai_pins.main(["--check"]) == 0
    assert local_ai_pins.main(["--check", "--only", "models"]) == 0
    with pytest.raises(SystemExit):
        local_ai_pins.main(["--check", "--only", "models", "--version", "0.40.10"])
    assert "does not apply to the model table" in capsys.readouterr().err
