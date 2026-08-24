"""Standing gate: a closed-value CLI axis must reach the agent as a JSON enum.

The MCP input schema is *derived* from the Typer parameter type, so an option
annotated ``str`` ships ``{"type": "string"}`` with no ``enum`` and tells the
agent-operator nothing about the accepted set. Hand-parsing the token inside the
handler does not repair that: the refusal arrives after the agent has guessed.

This gate finds the shape mechanically — a bare-string parameter whose name
matches a field that some pydantic model types as a ``StrEnum`` — and requires
every occurrence to be either pinned or explicitly classified.

Promoting such an axis is NOT automatic. Three independent checks must pass, and
the last two are properties of the *code being deleted*, invisible at the
declaration site:

1. **Value containment** — the enum covers every value accepted on the success
   path.
2. **No instructive out-of-set refusal** — nothing downstream needs an out-of-set
   value to answer well. ``--modelo`` on ``modelo work create`` accepts ceded
   autonomic codes so it can name the regional filing authority; a ``Choice``
   would refuse first with a bare "not one of".
3. **No input normalisation** — the removed parser did not case-fold, strip, or
   rewrite separators. ``--ccaa`` resolves ``comunidad-valenciana`` to the
   underscored member, which a raw value ``Choice`` would reject.

Each allowlist entry names which check exempts it, so the exemption is reviewable
rather than a bare opt-out, and a stale entry fails rather than lingering.
"""

from __future__ import annotations

import inspect
import sys
from enum import Enum, StrEnum

import pytest
from pydantic import BaseModel

from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class AxisExemption(StrEnum):
    """Why a bare-string axis is not promoted to its enum."""

    #: The parameter shares a name with an unrelated enum-typed model field and
    #: does not range over that enum at all (``--output`` is a file path).
    NAME_COLLISION = "name-collision"
    #: The command body needs out-of-set values to raise an instructive refusal.
    INSTRUCTIVE_GUARD = "instructive-guard"
    #: A parser normalises the token, so a raw-value choice would narrow input.
    NORMALISING_PARSER = "normalising-parser"
    #: The CLI axis is a strict superset of the enum (enum plus "all", etc.).
    SUPERSET_AXIS = "superset-axis"
    #: Known debt: the shape matches and nobody has run the three checks yet.
    #: Legitimate, visible, and explicitly not a claim that the site is fine.
    UNADJUDICATED = "unadjudicated"


#: Exemptions that apply to every command carrying the parameter name.
_BY_PARAMETER_NAME: dict[str, tuple[AxisExemption, str]] = {
    "name": (
        AxisExemption.NAME_COLLISION,
        "Profile, certificate and secret names are free text; RootSurfaceName is the CLI root taxonomy.",
    ),
    "reason": (
        AxisExemption.NAME_COLLISION,
        "Operator-supplied free-text justification; the matching enums are internal issue taxonomies.",
    ),
    "output": (
        AxisExemption.NAME_COLLISION,
        "A filesystem destination path, unrelated to OutputSensitivityClass.",
    ),
    "recargo": (
        AxisExemption.NAME_COLLISION,
        "A decimal recargo amount, unrelated to IvaComponentPresence.",
    ),
    "iva_rate": (
        AxisExemption.NAME_COLLISION,
        'Carries a numeric rate, not a taxonomy token -- the help on these verbs reads "as a decimal, for example 0.21". IvaRate is a rate-band taxonomy and is not the accepted input set.',
    ),
    "provider": (
        AxisExemption.NAME_COLLISION,
        "Two different open axes, neither ranging over LLMProvider. The diagnostics verbs filter recorded run rows by a free-form runner label (claude, antigravity, codex), while config.auth resolves against a backend catalogue that distinguishes implemented from reserved providers -- a dynamic set a static Choice would misstate in both directions.",
    ),
    "kind": (
        AxisExemption.NAME_COLLISION,
        "The movement and amendment kinds are now pinned to their own enums. The one bare site left, registry.manuals.rules, filters on RegistryManualRulesCommand.kind -- a free-form str with no closed set behind it, so there is no enum to declare.",
    ),
    "valuation_method": (
        AxisExemption.INSTRUCTIVE_GUARD,
        "The domain accepts out-of-enum 'lifo' so it can refuse it citing LIS art. 17.1 -- \"LIFO valuation is not admitted for this tax ledger; use FIFO, PMP, or coste_medio\". A Choice would replace a legal citation with a bare not-one-of.",
    ),
    "ccaa": (
        AxisExemption.NORMALISING_PARSER,
        "parse_tax_region normalises 'comunidad-valenciana' to the underscored member, and raises "
        "ForalRegimeError for pais-vasco/navarra -- foral territories deliberately outside CCAA. "
        "Both a normalising parser and an instructive guard; either alone forbids promotion.",
    ),
}

#: Exemptions for one specific command, taking precedence over the name entry.
_BY_COMMAND: dict[tuple[str, str], tuple[AxisExemption, str]] = {
    ("modelo.work.create", "modelo"): (
        AxisExemption.INSTRUCTIVE_GUARD,
        "guard_unsupported_work_modelo answers ITP-AJD/ISD codes with the ceded autonomic "
        "redirect naming the regional filing route; a Choice would refuse first.",
    ),
}

#: Names whose remaining sites are mid-migration rather than exempt.
_MIGRATION_IN_PROGRESS: dict[str, str] = {
    "modelo": (
        "Registry-resolving surfaces are pinned to MODELO_CODE_CHOICE and the portal filter to "
        "MODELO_CODE_CHOICE_ALL. The rest are un-swept, not cleared."
    ),
}


def _enum_typed_field_names() -> dict[str, set[str]]:
    """Map model field name -> enum class names that some model types it as.

    Read off ``sys.modules`` after the tool descriptors are built, which imports
    the whole CLI tree, rather than walking every package: the walk costs minutes
    and imports modules no command reaches. Under-collection can only cause a
    missed detection, never a false failure, and the size assertion below keeps a
    silently-broken collector from passing vacuously.
    """
    discovered: dict[str, set[str]] = {}
    for module in list(sys.modules.values()):
        if not getattr(module, "__name__", "").startswith("cadrumo."):
            continue
        for obj in vars(module).values():
            if not (inspect.isclass(obj) and issubclass(obj, BaseModel)):
                continue
            # A model whose forward references never resolved raises on
            # ``model_fields``. Skipping on the completeness flag reads the same
            # condition without a broad except swallowing unrelated failures.
            if not getattr(obj, "__pydantic_complete__", False):
                continue
            for field_name, field in obj.model_fields.items():
                annotation = field.annotation
                candidates = [annotation, *(getattr(annotation, "__args__", ()) or ())]
                for candidate in candidates:
                    if (
                        inspect.isclass(candidate)
                        and issubclass(candidate, Enum)
                        and getattr(candidate, "__module__", "").startswith("cadrumo")
                    ):
                        discovered.setdefault(field_name, set()).add(candidate.__qualname__)
    return discovered


def _bare_string_axes() -> dict[tuple[str, str], None]:
    """Every (command_key, parameter) whose schema is a bare string."""
    bare: dict[tuple[str, str], None] = {}
    for descriptor in build_tool_descriptors():
        for name, spec in descriptor.input_schema.get("properties", {}).items():
            if spec.get("enum") or spec.get("type") != "string":
                continue
            bare[(descriptor.command_key, name)] = None
    return bare


def test_every_bare_enum_shaped_axis_is_pinned_or_classified() -> None:
    """A bare axis matching an enum-typed field must carry a stated exemption.

    This is the standing half of the gate: a NEW option declared as ``str`` over a
    closed set fails here until someone runs the three checks and records which
    one exempts it. It does not assert the current tree is clean -- much of it is
    recorded as ``unadjudicated`` debt, which is a visible classification and not
    a claim of correctness.
    """
    field_enums = _enum_typed_field_names()
    assert len(field_enums) > 100, (
        f"only {len(field_enums)} enum-typed field names discovered; the collector is broken "
        "and every assertion below would pass vacuously"
    )

    unclassified: list[tuple[str, str]] = []
    for command_key, parameter in _bare_string_axes():
        if parameter not in field_enums:
            continue
        if (command_key, parameter) in _BY_COMMAND:
            continue
        if parameter in _BY_PARAMETER_NAME or parameter in _MIGRATION_IN_PROGRESS:
            continue
        unclassified.append((command_key, parameter))

    assert not unclassified, (
        "bare-string CLI axes matching an enum-typed model field, with no recorded exemption. "
        "Run the three checks in this module's docstring, then either declare the enum at the "
        f"Typer boundary or add an entry naming the exempting check: {sorted(unclassified)}"
    )


def test_every_exemption_still_describes_a_real_bare_axis() -> None:
    """A stale exemption fails instead of lingering after its site was fixed.

    Without this, an allowlist only ever grows: an entry written for a site that
    has since been pinned keeps granting an exemption nothing needs, and the next
    reader cannot tell live entries from dead ones.
    """
    bare = _bare_string_axes()
    bare_names = {parameter for _, parameter in bare}

    stale_commands = [key for key in _BY_COMMAND if key not in bare]
    assert not stale_commands, f"exemptions for axes that are no longer bare strings: {stale_commands}"

    stale_names = sorted(set(_BY_PARAMETER_NAME) - bare_names)
    assert not stale_names, f"parameter-name exemptions matching no bare axis: {stale_names}"

    stale_migrations = sorted(set(_MIGRATION_IN_PROGRESS) - bare_names)
    assert not stale_migrations, f"migration entries whose axis is fully pinned -- delete the entry: {stale_migrations}"


def test_every_exemption_states_a_reason() -> None:
    """An exemption without a reason is an opt-out, not a judgement."""
    for key, (exemption, reason) in {**_BY_COMMAND}.items():
        assert isinstance(exemption, AxisExemption), key
        assert len(reason.strip()) > 30, f"{key} states no substantive reason"
    for name, (exemption, reason) in _BY_PARAMETER_NAME.items():
        assert isinstance(exemption, AxisExemption), name
        assert len(reason.strip()) > 30, f"{name} states no substantive reason"
    for name, reason in _MIGRATION_IN_PROGRESS.items():
        assert len(reason.strip()) > 30, f"{name} states no substantive reason"
