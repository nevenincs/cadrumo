"""The profile provider: a binding that reads the taxpayer's own censo record.

A profile binding names a field of the taxpayer profile substrate (declarante,
conyuge, hijos, ascendientes, ...) rather than a filed value or a ledger fold.
The three shapes it admits -- a scalar key, a composite projection of several
keys through a format renderer, and a field of a typed profile model -- are
mutually exclusive by validation, because a declaration that named two of them
would leave the value's origin ambiguous.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, model_validator

from ....core.aggregation import BindingSourceKind
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_value_contract import BindingValueChannel
from .errors import RegistryValidationError

if TYPE_CHECKING:
    from .schema import BindingDefinition

__all__ = ["ProfileProvider", "validate_profile_binding"]


class ProfileProvider(BaseModel):
    """Strict validator for the selector mapping of a profile-source binding.

    Profile-source bindings read values from the taxpayer profile substrate
    (declarante, conyuge, hijos, ascendientes, ...). They land on the
    fichero-BOE record either as a typed scalar (single ``profile_key``)
    or via a composite projection (``profile_keys`` with a ``format``
    rendering function), and optionally as a sub-collection field of a
    typed profile model (``profile_model`` + ``collection`` + ``field``).

    Two cross-cutting fields apply to every shape:

    * ``xsd_path`` / ``xsd_attribute`` / ``dictionary_field``: how the
      value is addressed on the on-wire record.
    * ``required_when_profile_key`` / ``required_when_value``: a
      conditional applicability gate; only certain profile shapes set
      these.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.PROFILE] = BindingSourceKind.PROFILE

    # Scalar shape
    profile_key: str | None = Field(default=None, min_length=1, max_length=128)
    # Composite shape
    profile_keys: tuple[str, ...] = ()
    # Collection shape (typed sub-models on the profile)
    profile_model: str | None = Field(default=None, min_length=1, max_length=128)
    collection: str | None = Field(default=None, min_length=1, max_length=64)
    field: str | None = Field(default=None, min_length=1, max_length=128)
    repeating: bool = False
    # On-wire addressing
    xsd_path: str | None = Field(default=None, min_length=1, max_length=512)
    xsd_attribute: str | None = Field(default=None, min_length=1, max_length=128)
    dictionary_field: str | None = Field(default=None, min_length=1, max_length=128)
    # Rendering / formatting
    format: str | None = Field(default=None, min_length=1, max_length=64)
    # Conditional applicability
    required_when_profile_key: str | None = Field(default=None, min_length=1, max_length=128)
    required_when_value: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_profile_shape(self) -> ProfileProvider:
        has_scalar = self.profile_key is not None
        has_composite = bool(self.profile_keys)
        has_collection = self.profile_model is not None
        shape_count = sum((has_scalar, has_composite, has_collection))
        if shape_count != 1:
            raise RegistryValidationError(
                "profile selector must declare exactly one of profile_key (scalar), "
                "profile_keys (composite), or profile_model (collection)",
            )
        if has_composite and self.format is None:
            raise RegistryValidationError("profile composite selector (profile_keys) requires a format renderer")
        if self.repeating and not has_collection:
            raise RegistryValidationError("profile selector with repeating=true must declare profile_model")
        if has_collection:
            if self.field is None:
                raise RegistryValidationError("profile model selector must declare field")
            # ``collection`` is only required when the profile model
            # selector targets a repeating sub-collection
            # (``repeating = true`` plus a named ``collection``). Scalar
            # fields on a typed profile model (e.g. ``profile_model =
            # "TaxResidenceProfile"`` + ``field = "ccaa"``) omit
            # ``collection`` because the field IS at the model root.
            if self.repeating and self.collection is None:
                raise RegistryValidationError("profile collection selector with repeating=true must declare collection")
        # required_when_* must be paired
        if (self.required_when_profile_key is None) != (self.required_when_value is None):
            raise RegistryValidationError(
                "profile selector required_when_profile_key and required_when_value must be declared together",
            )
        return self


def validate_profile_binding(binding: BindingDefinition) -> list[str]:
    """Return the build-time diagnostics for one profile binding.

    A repeating profile collection emits provider-native rows, so it must travel
    the row-set channel, and a scalar or composite profile value has no rows to
    emit, so it must not. The composite projection renders text through its
    format renderer, so its value must travel the text channel.
    """
    provider = binding.provider
    if not isinstance(provider, ProfileProvider):
        return [f"binding {binding.id!r} (source={binding.source!r}) is not a profile provider"]
    channel = binding.value.channel
    prefix = f"binding {binding.id!r} (source={binding.source!r}) profile invariants violated:"
    failures: list[str] = []
    if provider.repeating and channel is not BindingValueChannel.ROW_SET:
        failures.append(
            f"{prefix} a repeating collection must use the row_set channel, not {channel.value!r}",
        )
    if not provider.repeating and channel is BindingValueChannel.ROW_SET:
        failures.append(f"{prefix} the row_set channel requires a repeating collection selector")
    if provider.profile_keys and channel is not BindingValueChannel.TEXT:
        failures.append(
            f"{prefix} a composite projection renders text and must use the text channel, not {channel.value!r}",
        )
    return failures
