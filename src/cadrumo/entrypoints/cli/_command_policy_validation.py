"""Canonical execution-policy vocabularies and invariant checks."""

from __future__ import annotations

from typing import Any, cast

CAPABILITIES = frozenset(
    {
        "state-free",
        "local-storage",
        "registry",
        "profile-custody",
        "encrypted-facts",
        "network",
        "browser",
        "google",
        "calculation",
        "filing",
        "crypto",
        "subprocess",
    }
)
SIDE_EFFECTS = frozenset({"none", "local-state", "network", "browser", "google"})
PERFORMANCE_CLASSES = frozenset({"metadata", "local-io", "compute", "external-io", "interactive"})
IMPLIED_CAPABILITIES: dict[str, frozenset[str]] = {
    "encrypted-facts": frozenset({"profile-custody"}),
    "browser": frozenset({"network"}),
    "google": frozenset({"network"}),
    "calculation": frozenset({"registry"}),
    "filing": frozenset({"registry"}),
}


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _raise_first(checks: tuple[tuple[bool, str], ...]) -> None:
    """Raise the first failed invariant in declaration order."""
    for failed, message in checks:
        if failed:
            raise ValueError(message)


def validate_deferred_target(module: str, qualname: str, package: str | None = None) -> None:
    """Validate a deferred Python identity and its optional relative anchor."""
    relative_module = module.startswith(".")
    _raise_first(
        (
            (
                not module
                or not module.lstrip(".")
                or any(not part.isidentifier() for part in module.lstrip(".").split(".")),
                "deferred target module must be a dotted Python module name",
            ),
            (
                relative_module and not package,
                "relative deferred target modules require their importing package",
            ),
            (
                package is not None and (not package or any(not part.isidentifier() for part in package.split("."))),
                "deferred target package must be a dotted Python package name",
            ),
            (
                module.startswith("cadrumo.") and package is None,
                "first-party deferred target modules must use relative syntax",
            ),
            (
                not qualname or any(not part.isidentifier() for part in qualname.split(".")),
                "deferred target qualname must be a dotted Python identifier",
            ),
        )
    )


def validate_translation_key(value: str) -> None:
    """Validate a non-empty dotted catalogue key."""
    _raise_first(
        ((not value or value.strip() != value or "." not in value, "translation key must be a non-empty dotted key"),)
    )


def validate_lazy_binding(
    state: object,
    target: object,
    reason_key: object,
    optional_dependencies: tuple[str, ...],
    *,
    require_token: Any,
) -> None:
    """Validate state-dependent binding shape and dependency tokens."""
    _raise_first(
        ((len(set(optional_dependencies)) != len(optional_dependencies), "optional dependency names must be unique"),)
    )
    for dependency in optional_dependencies:
        require_token(dependency, field="optional dependency")
    state_value = _enum_value(state)
    _raise_first(
        (
            (
                state_value == "target" and (target is None or reason_key is not None),
                "target binding requires only a deferred target",
            ),
            (
                state_value == "unavailable" and (target is not None or reason_key is None),
                "unavailable binding requires only a localized reason",
            ),
            (state_value not in {"target", "unavailable"}, f"unknown binding state: {state!r}"),
        )
    )


def validate_parameter_default(kind: object, literal: object, factory: object) -> None:
    """Validate the literal/factory shape of one parameter default."""
    kind_value = _enum_value(kind)
    messages = {
        "required": (literal is not None or factory is not None, "required parameter default cannot carry a value"),
        "literal": (factory is not None, "literal parameter default cannot carry a factory"),
        "factory": (
            factory is None or literal is not None,
            "factory parameter default requires only a deferred factory",
        ),
    }
    failure = messages.get(cast(str, kind_value))
    _raise_first(((failure is not None and failure[0], failure[1] if failure is not None else ""),))


def validate_value_contract(
    click_type: object,
    parser: object,
    choices: tuple[str, ...],
) -> None:
    """Validate mutually exclusive conversion hooks and choices."""
    _raise_first(
        (
            (
                click_type is not None and parser is not None,
                "value contract cannot declare both a Click type and parser",
            ),
            (
                len(choices) != len(set(choices)) or any(not choice for choice in choices),
                "value contract choices must be unique non-empty strings",
            ),
            (
                bool(choices) and (click_type is not None or parser is not None),
                "value contract choices cannot be combined with a Click type or parser",
            ),
        )
    )


def validate_parameter_constraint(minimum: int | float | None, maximum: int | float | None, clamp: bool) -> None:
    """Validate scalar bounds and clamping requirements."""
    _raise_first(
        (
            (
                minimum is not None and maximum is not None and minimum > maximum,
                "parameter minimum cannot exceed maximum",
            ),
            (clamp and minimum is None and maximum is None, "clamping requires a minimum or maximum"),
        )
    )


def validate_machine_secret_field(name: str, *, require_identifier: Any) -> None:
    require_identifier(name, field="machine-secret field name")


def validate_machine_secret_condition(option_name: str, *, require_identifier: Any) -> None:
    require_identifier(option_name, field="machine-secret condition option")


def validate_machine_secret_variant(
    key: str,
    fields: tuple[Any, ...],
    *,
    require_identifier: Any,
) -> None:
    require_identifier(key, field="machine-secret variant key")
    names = tuple(field.name for field in fields)
    _raise_first(
        (
            (not fields, "machine-secret variant must declare at least one field"),
            (len(names) != len(set(names)), "machine-secret variant fields must be unique"),
        )
    )


def validate_machine_secret(variants: tuple[Any, ...]) -> None:
    keys = tuple(variant.key for variant in variants)
    targets = tuple(variant.model.identity for variant in variants)
    _raise_first(
        (
            (not variants, "machine-secret spec must declare at least one variant"),
            (len(keys) != len(set(keys)), "machine-secret variant keys must be unique"),
            (len(targets) != len(set(targets)), "machine-secret payload model targets must be unique"),
        )
    )


def validate_profile_secret(fields: tuple[Any, ...]) -> None:
    names = tuple(field.name for field in fields)
    _raise_first(
        (
            (not fields, "profile-secret spec must declare at least one field"),
            (len(names) != len(set(names)), "profile-secret fields must be unique"),
        )
    )


def expanded_capabilities(capabilities: frozenset[str]) -> frozenset[str]:
    """Return the transitive capability closure used by policy gates."""
    expanded = set(capabilities)
    pending = list(capabilities)
    while pending:
        for implied in IMPLIED_CAPABILITIES.get(pending.pop(), ()):
            if implied not in expanded:
                expanded.add(implied)
                pending.append(implied)
    return frozenset(expanded)


def validate_policy_types(
    capabilities: frozenset[str],
    side_effects: frozenset[str],
    destructive: bool,
    handoff: bool,
    live_write: bool,
) -> None:
    """Validate the policy container and risk-flag runtime types."""
    if not isinstance(capabilities, frozenset):
        raise TypeError("execution policy capabilities must be a frozenset")
    if not isinstance(side_effects, frozenset):
        raise TypeError("execution policy side effects must be a frozenset")
    if any(not isinstance(value, bool) for value in (destructive, handoff, live_write)):
        raise TypeError("execution policy risk flags must be bools")


def validate_policy_membership(
    capabilities: frozenset[str],
    side_effects: frozenset[str],
    performance: str,
    write_route: str,
) -> None:
    """Validate capability, effect, performance, and write-route vocabularies."""
    _raise_first(
        (
            (
                not capabilities or bool(capabilities - CAPABILITIES),
                "execution policy has missing or unknown capabilities",
            ),
            (
                not side_effects or bool(side_effects - SIDE_EFFECTS),
                "execution policy has missing or unknown side effects",
            ),
            (performance not in PERFORMANCE_CLASSES, "execution policy has an unknown performance class"),
            (
                write_route not in {"none", "profile-bound", "bootstrap-root"},
                "execution policy has an unknown write route",
            ),
        )
    )


def validate_policy_exclusive_values(
    capabilities: frozenset[str],
    side_effects: frozenset[str],
) -> None:
    """Enforce mutually exclusive state-free and no-effect vocabularies."""
    _raise_first(
        (
            (
                "state-free" in capabilities and capabilities != frozenset({"state-free"}),
                "state-free cannot be combined with authority capabilities",
            ),
            (
                "none" in side_effects and side_effects != frozenset({"none"}),
                "none cannot be combined with observable side effects",
            ),
            (
                capabilities == frozenset({"state-free"}) and side_effects != frozenset({"none"}),
                "state-free execution must be effect-free",
            ),
        )
    )


def validate_policy_effect_capabilities(
    side_effects: frozenset[str],
    expanded_capabilities: frozenset[str],
) -> None:
    """Require each observable effect to carry its owning capability."""
    required_by_effect = {"network": "network", "browser": "browser", "google": "google"}
    _raise_first(
        (
            (
                any(
                    effect in side_effects and capability not in expanded_capabilities
                    for effect, capability in required_by_effect.items()
                ),
                "execution policy side effect lacks its owning capability",
            ),
        )
    )


def validate_policy_write_route(
    write_route: str,
    side_effects: frozenset[str],
    expanded_capabilities: frozenset[str],
) -> None:
    """Require storage writes to carry local-state effects and profile custody."""
    _raise_first(
        (
            (
                write_route != "none"
                and ("local-state" not in side_effects or "profile-custody" not in expanded_capabilities),
                "storage write routes require profile custody and local-state effects",
            ),
        )
    )


def validate_policy_destructive(destructive: bool, side_effects: frozenset[str]) -> None:
    """Require destructive operations to declare local-state effects."""
    _raise_first(
        ((destructive and "local-state" not in side_effects, "destructive execution requires a local-state effect"),)
    )


def validate_policy_handoff(
    handoff: bool,
    expanded_capabilities: frozenset[str],
    side_effects: frozenset[str],
) -> None:
    """Require filing handoffs to carry filing authority and local-state effects."""
    _raise_first(
        (
            (
                handoff and ("filing" not in expanded_capabilities or "local-state" not in side_effects),
                "filing handoff requires filing authority and a local-state effect",
            ),
        )
    )


def validate_policy_live_write(
    live_write: bool,
    expanded_capabilities: frozenset[str],
    side_effects: frozenset[str],
) -> None:
    """Require live writes to carry network authority and a network/browser effect."""
    _raise_first(
        (
            (
                live_write
                and ("network" not in expanded_capabilities or not side_effects.intersection({"network", "browser"})),
                "live writes require network authority and a network/browser effect",
            ),
        )
    )


__all__ = [
    "CAPABILITIES",
    "IMPLIED_CAPABILITIES",
    "PERFORMANCE_CLASSES",
    "SIDE_EFFECTS",
    "validate_policy_destructive",
    "validate_policy_effect_capabilities",
    "validate_policy_exclusive_values",
    "validate_policy_handoff",
    "validate_policy_live_write",
    "validate_policy_membership",
    "validate_policy_types",
    "validate_policy_write_route",
]
