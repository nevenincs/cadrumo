"""PROFILE_KEYS-driven validation projection used by the CLI status surface.

The wizard catalogue (``application/wizard/_catalogue.py``) declares
each ``WizardQuestion.profile_key`` as a canonical schema-TOML path
(e.g. ``identity.tax_id``, ``preferences.output_language``).
``compile_profile_keys`` produces :data:`PROFILE_KEYS` as a tuple of
:class:`ProfileKey` records keyed by those canonical paths. The
helpers in this module project a flat operator-supplied
``Mapping[str, str]`` over that registry and report which required
keys are missing or set so the CLI status surface can render a
deterministic readiness summary.

These helpers are intentionally projection-only: they do not read or
write secure storage, do not touch :class:`WorkflowState`, and do
not depend on any CLI state. The flat-dict input is produced by
:func:`application.user_profile.record_to_values` or by the wizard
runner's canonical projection.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.contribuyente.keys import ProfileKey, ProfileKeyRequirement, optional_profile_keys
from ...domain.contribuyente.keys import profile_keys as _get_profile_keys
from .completeness import (
    IVA_REGIME_PATH,
    conditional_profile_required_paths,
    iva_regime_required,
    profile_value_is_present,
)


class ProfileValidationResult(BaseModel):
    """Typed result of :func:`validate_profile_values`."""

    model_config = _STRICT_FROZEN

    valid: bool
    missing_required: tuple[str, ...] = ()
    present_required: tuple[str, ...] = ()
    present_optional: tuple[str, ...] = ()
    unknown_keys: tuple[str, ...] = ()
    present_keys: int
    total_keys: int


def _has_value(values: Mapping[str, str], key: str) -> bool:
    return profile_value_is_present(values.get(key))


def _conditional_requirement_applies(values: Mapping[str, str], entry: ProfileKey) -> bool:
    if entry.required_when_key is None or entry.required_when_value is None:
        return False
    raw = values.get(entry.required_when_key)
    return raw is not None and raw.strip() == entry.required_when_value


def validate_profile_values(values: Mapping[str, str]) -> ProfileValidationResult:
    """Validate ``values`` against :data:`PROFILE_KEYS`.

    ``values`` is keyed by canonical schema path
    (``identity.tax_id``, ``preferences.output_language`` etc.).

    Returns a :class:`ProfileValidationResult`.
    """
    entries = _registered_profile_keys()
    static_required_keys = tuple(
        entry.key
        for entry in entries
        if (entry.requirement is ProfileKeyRequirement.REQUIRED or _conditional_requirement_applies(values, entry))
        and (entry.key != IVA_REGIME_PATH or iva_regime_required(values))
    )
    required_keys = tuple(dict.fromkeys((*static_required_keys, *conditional_profile_required_paths(values))))
    optional_keys = tuple(entry.key for entry in optional_profile_keys())
    known_keys = set(required_keys) | set(optional_keys)

    missing_required = tuple(key for key in required_keys if not _has_value(values, key))
    present_required = tuple(key for key in required_keys if _has_value(values, key))
    present_optional = tuple(key for key in optional_keys if _has_value(values, key))
    unknown_keys = tuple(sorted(set(values) - known_keys))
    present_keys = sum(1 for entry in entries if _has_value(values, entry.key))

    return ProfileValidationResult(
        valid=not missing_required,
        missing_required=missing_required,
        present_required=present_required,
        present_optional=present_optional,
        unknown_keys=unknown_keys,
        present_keys=present_keys,
        total_keys=len(entries),
    )


def list_profile_key_records() -> tuple[ProfileKey, ...]:
    """Return the full :data:`PROFILE_KEYS` tuple in registry order.

    Each element is a :class:`ProfileKey` describing one profile field.
    """
    return _registered_profile_keys()


def _registered_profile_keys() -> tuple[ProfileKey, ...]:
    """Return the profile-key registry, registering it first if nothing has.

    Every reader in this module goes through here, and the reason is that
    only one of them used to. The registry is populated by the wizard
    catalogue's import side effect, so a reader that calls the domain
    accessor directly is not reading a registry -- it is betting that some
    unrelated module already imported the wizard. Two of the three readers
    took that bet and lost it in a cold process: the domain registry raises
    :class:`ProfileKeysRegistrationError` rather than returning an empty
    tuple, so ``validate_profile_values`` raised on a fresh interpreter
    while ``list_profile_key_records`` -- the one reader that registered --
    succeeded and left the others working for the rest of the process.

    That is why the defect hides from the test suite. Any module that
    touches the wizard catalogue first repairs the import order for
    everything after it, so the failure only reaches an operator through
    a cold entry point (workflow profile health) that does not.

    The import in :func:`_ensure_profile_keys_registered` MUST stay
    function-local; see that function for the import cycle it breaks.
    """
    _ensure_profile_keys_registered()
    return _get_profile_keys()


def _ensure_profile_keys_registered() -> None:
    """Import the wizard catalogue so the compiled profile keys are pushed.

    Idempotent: the import system runs the registration side effect once and
    every later call is a dict lookup in ``sys.modules``.

    This import MUST stay function-local, and the reason is not the cold-start
    budget it also happens to protect. Hoisting it to module scope deadlocks a
    real import: this module is reached through the package's own lazy
    ``__getattr__``, so while that resolver is on the stack the wizard package
    loads, and ``wizard.status`` imports a name back out of this package that
    the resolver has not bound yet. The failure is an ``ImportError`` for a
    name that plainly exists, from a chain that looks acyclic in the static
    import graph, which is exactly why a graph-based check will keep declaring
    the hoist safe.
    """
    # Importing the CATALOGUE no longer registers anything: the compiled keys
    # are pushed by `wizard.compiler`, which calls
    # `ensure_profile_keys_registered()` at its own import. Importing
    # `catalogue` therefore left the registry empty and every cold reader
    # raised `ProfileKeysRegistrationError`. Calling the compiler's own
    # idempotent entry is what it documents itself for -- "an entrypoint may
    # call this unconditionally without ordering knowledge".
    from ..wizard.compiler import ensure_profile_keys_registered

    ensure_profile_keys_registered()


__all__ = [
    "ProfileValidationResult",
    "list_profile_key_records",
    "validate_profile_values",
]
