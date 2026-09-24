"""Every shipped modelo catalogue text fits the workspace's localized display field.

Official casilla labels are quoted in full, so the field's length bound is a
claim about the catalogue. A single label longer than the bound once made its
whole workspace unopenable, and the failure surfaced only when a screen
rendered that modelo. Running every shipped text through the field here makes
the next long official text fail the build instead.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from pydantic import TypeAdapter, ValidationError

from ..workspace_models import ModeloWorkspaceLocalizedTextV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES_ROOT = Path(__file__).resolve().parents[3] / "locales"
_VALUE = TypeAdapter(ModeloWorkspaceLocalizedTextV1.model_fields["value"].annotation)


def _schema_texts() -> Iterator[tuple[str, str]]:
    """Yield ``(locale:key, text)`` for every string leaf of every shipped modelo schema shard."""

    def walk(node: object, path: str) -> Iterator[tuple[str, str]]:
        if isinstance(node, dict):
            for key, child in node.items():
                yield from walk(child, f"{path}.{key}" if path else str(key))
        elif isinstance(node, str):
            yield path, node

    for shard in sorted(_LOCALES_ROOT.glob("*/modelo/schema/*.yml")):
        locale = shard.relative_to(_LOCALES_ROOT).parts[0]
        with shard.open(encoding="utf-8") as handle:
            for key, text in walk(yaml.safe_load(handle), ""):
                yield f"{locale}:{key}", text


def test_every_shipped_modelo_text_fits_the_localized_display_field() -> None:
    texts = list(_schema_texts())
    assert len(texts) > 40_000, f"only {len(texts)} catalogue texts were found; the sweep is not reaching the shards"

    refused: list[str] = []
    for address, text in texts:
        if not text:
            continue
        try:
            _VALUE.validate_python(text)
        except ValidationError:
            refused.append(f"{address} ({len(text)} characters)")

    assert refused == [], f"{len(refused)} shipped texts do not fit the display field: {refused[:5]}"


def test_the_display_field_still_refuses_an_unbounded_text() -> None:
    """The bound stays a bound: the sweep above must not pass merely because nothing is checked."""
    with pytest.raises(ValidationError):
        _VALUE.validate_python("x" * 100_000)
