"""The profile provider: a binding that reads the taxpayer's own censo record.

A profile binding names a field of the taxpayer profile substrate (declarante,
conyuge, hijos, ascendientes, ...) rather than a filed value or a ledger fold.
The four shapes it admits -- a scalar key, a composite projection of several
keys through a format renderer, a field of a typed profile model, and one leaf
of a stored row object -- are mutually exclusive by validation, because a
declaration that named two of them would leave the value's origin ambiguous.
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

__all__ = ["ProfileProvider", "ProfileRowsSelector", "validate_profile_binding"]

_FACT_PATH_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"


class ProfileRowsSelector(BaseModel):
    """One leaf of a stored row object: ``{object_path}.{n}.{leaf}`` for each row ``n``.

    ``count_path`` names the profile fact that states how many rows the object
    holds. A stated count is the positive fact that lets a reader tell a filer
    who declared no rows from one who has not answered.

    ``required`` says the official design requires this leaf on every row the
    object holds. A stored row that states no value for it is then a fact the
    filer still owes, and the declaration cannot be checked, exported or filed
    until it is stated; the leaf is never filled with a stand-in.
    """

    model_config = STRICT_FROZEN_CONFIG

    object_path: str = Field(max_length=128, pattern=_FACT_PATH_PATTERN)
    leaf: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    count_path: str = Field(max_length=128, pattern=_FACT_PATH_PATTERN)
    required: bool = False

    def row_path(self, index: int) -> str:
        """Return the stored fact path of this leaf on row ``index``."""
        return f"{self.object_path}.{index}.{self.leaf}"


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
    # Stored row-object shape
    rows: ProfileRowsSelector | None = None
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
        has_collection = self.profile_model is not None
        _require_single_shape(self, has_collection=has_collection)
        if bool(self.profile_keys) and self.format is None:
            raise RegistryValidationError("profile composite selector (profile_keys) requires a format renderer")
        if self.rows is not None and not self.repeating:
            raise RegistryValidationError("profile row-object selector (rows) requires repeating=true")
        if self.repeating and not has_collection and self.rows is None:
            raise RegistryValidationError("profile selector with repeating=true must declare profile_model or rows")
        if has_collection:
            _require_collection_fields(self)
        _require_paired_required_when(self)
        return self


def _require_single_shape(provider: ProfileProvider, *, has_collection: bool) -> None:
    shape_count = sum(
        (provider.profile_key is not None, bool(provider.profile_keys), has_collection, provider.rows is not None)
    )
    if shape_count != 1:
        raise RegistryValidationError(
            "profile selector must declare exactly one of profile_key (scalar), "
            "profile_keys (composite), profile_model (collection), or rows (row object)",
        )


def _require_collection_fields(provider: ProfileProvider) -> None:
    if provider.field is None:
        raise RegistryValidationError("profile model selector must declare field")
    # ``collection`` is only required when the profile model
    # selector targets a repeating sub-collection
    # (``repeating = true`` plus a named ``collection``). Scalar
    # fields on a typed profile model (e.g. ``profile_model =
    # "TaxResidenceProfile"`` + ``field = "ccaa"``) omit
    # ``collection`` because the field IS at the model root.
    if provider.repeating and provider.collection is None:
        raise RegistryValidationError("profile collection selector with repeating=true must declare collection")


def _require_paired_required_when(provider: ProfileProvider) -> None:
    if (provider.required_when_profile_key is None) != (provider.required_when_value is None):
        raise RegistryValidationError(
            "profile selector required_when_profile_key and required_when_value must be declared together",
        )


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
