"""The local AI model pins: the model each role reads with, and the weights each model was tested with.

The pins are declarative package data, ``_data/dependencies/local_ai_models.toml``,
read by two owners: the native component engine, which downloads and checks the
models, and :mod:`~cadrumo.core.model_catalogue`, which takes its role defaults,
weight digests, download sizes and memory floors from the same file instead of
keeping a copy of its own. A pin states what this release was tested with; a
model tag is mutable upstream, so a different installed digest is reported as a
different version rather than refused.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from typing import Annotated, Final

from pydantic import BaseModel, Field, PositiveInt, StringConstraints, field_validator, model_validator

from .errors.hierarchy import pydantic_validation_boundary
from .models import STRICT_FROZEN_CONFIG
from .resources.bundled_data import packaged_data
from .toml import parse_toml
from .type_guards import is_object_list

__all__ = [
    "LOCAL_AI_MODEL_PINS_RESOURCE",
    "LocalAiModelPin",
    "LocalAiModelPins",
    "load_local_ai_model_pins",
    "parse_local_ai_model_pins",
]

#: Where the table lives under the bundled data root.
LOCAL_AI_MODEL_PINS_RESOURCE: Final = ("dependencies", "local_ai_models.toml")

type _ModelName = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*:[a-z0-9][a-z0-9._-]*$", max_length=128)
]
type _RoleName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]
type _HostName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$", max_length=253)]


class LocalAiModelPin(BaseModel):
    """One local model: its tested manifest digest, download size, memory floor and licence.

    ``licence`` is the licence's SPDX identifier and ``licence_name`` its own
    title, the words a licence notice names it by.
    """

    model_config = STRICT_FROZEN_CONFIG

    name: _ModelName
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    download_bytes: PositiveInt
    memory_bytes: PositiveInt
    licence: str = Field(min_length=1, max_length=128)
    licence_name: str = Field(min_length=1, max_length=128, pattern=r"^\S(?:[^\x00-\x1f\x7f-\x9f]*\S)?$")
    commercial_use_permitted: bool


class LocalAiModelPins(BaseModel):
    """Every pinned local model, the model each role reads with, and the registry hosts they come from."""

    model_config = STRICT_FROZEN_CONFIG

    hosts: tuple[_HostName, ...] = Field(min_length=1)
    roles: Mapping[_RoleName, _ModelName] = Field(min_length=1)
    models: tuple[LocalAiModelPin, ...] = Field(min_length=1)

    @field_validator("hosts", "models", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _tuple_from_toml_array(cls, value: object) -> object:
        return tuple(value) if is_object_list(value) else value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_table(self) -> LocalAiModelPins:
        names = [pin.name for pin in self.models]
        if len(set(names)) != len(names):
            raise ValueError("the table pins each model once")
        if len(set(self.hosts)) != len(self.hosts):
            raise ValueError("the table names each host once")
        unpinned = sorted(set(self.roles.values()) - set(names))
        if unpinned:
            raise ValueError(f"a role reads with a model the table does not pin: {unpinned}")
        return self

    def model(self, name: str) -> LocalAiModelPin | None:
        """Return the pin of the model called ``name``, or ``None`` when the table does not pin it."""
        return next((pin for pin in self.models if pin.name == name), None)


def parse_local_ai_model_pins(text: str) -> LocalAiModelPins:
    """Validate the model pin table ``text`` holds.

    Raises:
        pydantic.ValidationError: When the table is malformed.
    """
    return LocalAiModelPins.model_validate(parse_toml(text))


@cache
def load_local_ai_model_pins() -> LocalAiModelPins:
    """Return the bundled model pin table; every build carries it.

    Raises:
        pydantic.ValidationError: When the bundled table is malformed.
    """
    return parse_local_ai_model_pins(packaged_data(*LOCAL_AI_MODEL_PINS_RESOURCE).read_text(encoding="utf-8"))
