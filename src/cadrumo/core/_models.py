"""Shared pydantic model configuration constants.

Provides the canonical :data:`STRICT_FROZEN_CONFIG` used across domain,
application, and adapter pydantic models that require strict-mode, frozen,
no-extra-fields configuration. It is a :class:`pydantic.ConfigDict` value shared
by records that need immutable boundary contracts, including
:class:`domain.calculations.registry._schema_base.RegistryModel`,
:class:`core._optional_extras.OptionalExtra`, and encrypted-storage
envelope records.

The constant is intentionally only a config value, not a base class or a
validation policy. Domain modules still own field validators, serializers,
model rebuilds, and any richer invariants on their own records; this module
only centralises the common ``strict=True``, ``frozen=True``, and
``extra="forbid"`` baseline.

Modules with intentionally divergent ``ConfigDict`` values (e.g.
``arbitrary_types_allowed=True`` in storage adapter models, or
``validate_assignment=True`` in JSON contract models) must keep their own
module-local config constant and must NOT import :data:`STRICT_FROZEN_CONFIG`
from here. The CLI JSON contract is such an exception:
:class:`core.json_contract.OutputSchema` and
:class:`core.json_contract.SchemaEnvelope` add assignment validation for
machine-output conformance.
"""

from __future__ import annotations

from pydantic import ConfigDict

#: Canonical pydantic ConfigDict for strict-mode, frozen, no-extra-fields models.
#:
#: Modules that require a different config (e.g. ``arbitrary_types_allowed=True``
#: for ORM-mapped types, or ``validate_assignment=True`` for mutable contract
#: types) must declare a module-local constant instead. This constant deliberately
#: does not set ``validate_assignment``; it is the default for frozen value
#: objects, not for settings models, mutable accumulators, or the CLI JSON schema
#: registry.
STRICT_FROZEN_CONFIG: ConfigDict = ConfigDict(strict=True, frozen=True, extra="forbid")

#: Canonical strict, frozen, no-extra-fields configuration that also prevents
#: Pydantic from echoing rejected input in validation errors. Use it for models
#: whose values can contain opaque or sensitive source identifiers.
STRICT_FROZEN_HIDDEN_INPUT_CONFIG: ConfigDict = ConfigDict(
    strict=True,
    frozen=True,
    extra="forbid",
    hide_input_in_errors=True,
)

__all__ = ["STRICT_FROZEN_CONFIG", "STRICT_FROZEN_HIDDEN_INPUT_CONFIG"]
