"""Provider-route and binding-consumer evidence rules for the binding audit."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from .common import mapping, rows, string_values

BINDING_REF_KEYS = frozenset(
    {
        "binding",
        "binding_id",
        "binding_ids",
        "bindings",
        "target_binding",
        "source_binding",
        "source_bindings",
        "alternate_bindings",
    }
)
_AUTHORING_DELTA_FAMILIES = frozenset({"casilla_overrides", "family_overrides"})
_NON_CONSUMING_SURFACES = {
    "casillas": "unbound_casilla",
    "constructs": "construct_membership",
    "form_layouts": "form_input",
}


def provider(binding: Mapping[str, object]) -> tuple[str | None, Mapping[str, object], str]:
    """Read current provider-union or legacy source-selector declaration shape."""
    provider_value = binding.get("provider")
    provider_mapping = mapping(provider_value)
    if provider_mapping is not None:
        kind = provider_mapping.get("kind")
        return (kind if isinstance(kind, str) else None, provider_mapping, "provider_union")
    source = binding.get("source")
    selector = mapping(binding.get("selector"))
    return (
        source if isinstance(source, str) else None,
        selector if selector is not None else {},
        "source_selector_legacy" if source is not None or binding.get("selector") is not None else "unclassified",
    )


def temporal_shape(provider_payload: Mapping[str, object]) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Report relative and absolute temporal loci without changing the provider."""
    temporal = provider_payload.get("temporal")
    temporal_kind = "none"
    if isinstance(temporal, Mapping):
        kind = temporal.get("kind")
        temporal_kind = kind if isinstance(kind, str) else "untyped"
    relative: list[str] = []
    absolute: list[str] = []
    _collect_temporal_fields(provider_payload, (), False, relative, absolute)
    return temporal_kind, tuple(sorted(set(relative))), tuple(sorted(set(absolute)))


def _collect_temporal_fields(
    value: object,
    parts: tuple[str, ...],
    inside_temporal: bool,
    relative: list[str],
    absolute: list[str],
) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            _collect_temporal_fields(
                item, (*parts, key_text), inside_temporal or key_text == "temporal", relative, absolute
            )
        return
    leaf = parts[-1] if parts else ""
    locus = ".".join(parts)
    if inside_temporal and any(token in leaf for token in ("year", "period", "offset", "span")):
        relative.append(locus)
    elif not inside_temporal and _is_absolute_temporal_leaf(leaf):
        absolute.append(locus)


def _is_absolute_temporal_leaf(leaf: str) -> bool:
    return (
        leaf in {"filing_year", "revision", "revision_id", "year"}
        or leaf.endswith("_filing_year")
        or leaf.endswith("_revision")
    )


def walk_binding_refs(value: object, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], str]]:
    """Yield binding-id tokens and their authored field path recursively."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            child = (*path, key_text)
            if _is_binding_reference_key(key_text):
                for binding_id in string_values(item):
                    yield child, binding_id
            yield from walk_binding_refs(item, child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            yield from walk_binding_refs(item, (*path, str(index)))


def _is_binding_reference_key(key: str) -> bool:
    return key in BINDING_REF_KEYS or key.endswith("_binding") or key.endswith("_binding_id")


def finding(
    code: str,
    *,
    severity: str,
    actionability: str,
    coordinate: Mapping[str, object],
    message: str,
    evidence: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Construct a stable finding key from its code and coordinate."""
    key_parts = [code, *(f"{key}={coordinate[key]}" for key in sorted(coordinate))]
    return {
        "key": "|".join(key_parts),
        "code": code,
        "severity": severity,
        "actionability": actionability,
        "coordinate": dict(coordinate),
        "message": message,
        "evidence": list(evidence),
    }


def structural_binding_mentions(
    families: Mapping[str, object],
) -> Iterable[tuple[str, Mapping[str, object], tuple[str, ...], str]]:
    """Yield non-binding fields that name a binding, skipping authoring deltas."""
    for family, family_rows in sorted(families.items()):
        if family == "bindings" or family in _AUTHORING_DELTA_FAMILIES:
            continue
        for row in rows(family_rows):
            for field_path, binding_id in walk_binding_refs(row):
                yield family, row, field_path, binding_id


def unconsumed_classification(*, applicability_kind: object, provider_disposition: str) -> str:
    """Classify a binding that no bound casilla, formula, or export consumes."""
    if applicability_kind == "non_calculation":
        return "excluded_non_calculation"
    return {
        "filing_grade": "filing_grade_unconsumed",
        "deferred": "deferred_provider",
        "non_runtime": "non_runtime_provider",
    }.get(provider_disposition, "unregistered_provider")


def unconsumed_binding_report(
    binding: Mapping[str, object],
    *,
    typed_consumers: Sequence[Mapping[str, object]],
    structural_mentions: Sequence[Mapping[str, object]],
    provider_disposition: str,
    python_literal_references: int,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    """Return an unconsumed row and blocking finding when typed use is absent."""
    if typed_consumers:
        return None, None
    applicability = mapping(binding.get("applicability"))
    applicability_kind = applicability.get("kind") if applicability is not None else None
    classification = unconsumed_classification(
        applicability_kind=applicability_kind,
        provider_disposition=provider_disposition,
    )
    mentions = sorted(
        {_NON_CONSUMING_SURFACES.get(str(item["family"]), str(item["family"])) for item in structural_mentions}
    )
    row: dict[str, object] = {
        "modelo": binding["modelo"],
        "revision": binding["revision"],
        "binding": binding["binding_id"],
        "provider_kind": binding.get("provider_kind"),
        "provider_disposition": provider_disposition,
        "applicability": applicability_kind,
        "classification": classification,
        "structural_mentions": mentions,
        "exact_python_literal_references": python_literal_references,
        "location": binding["location"],
    }
    if classification != "filing_grade_unconsumed":
        return row, None
    return row, finding(
        "UNCONSUMED_FILING_GRADE_BINDING",
        severity="error",
        actionability="actionable",
        coordinate={"modelo": binding["modelo"], "revision": binding["revision"], "binding": binding["binding_id"]},
        message=_unconsumed_message(mentions),
        evidence=(row,),
    )


def _unconsumed_message(mentions: list[str]) -> str:
    mentioned = f"; it is only named as {', '.join(mentions)}" if mentions else ""
    return f"filing-grade binding feeds no bound casilla, formula or export{mentioned}"


def binding_closure(
    binding: Mapping[str, object],
    registration: Mapping[str, object] | None,
    runtime_resolvers: Mapping[str, Mapping[str, object]],
) -> tuple[str, tuple[str, ...]]:
    """Grade one binding against its static contract and registered route."""
    if registration is None:
        return _missing_registration(binding)
    failures = _contract_failures(binding, registration)
    if failures:
        return "open_contract", tuple(sorted(set(failures)))
    return _registered_route_status(registration, runtime_resolvers)


def _missing_registration(binding: Mapping[str, object]) -> tuple[str, tuple[str, ...]]:
    failures: list[str] = []
    provider_payload = binding.get("provider")
    if not isinstance(provider_payload, Mapping) or not isinstance(provider_payload.get("kind"), str):
        failures.append("provider_union_member_missing")
    if not isinstance(binding.get("value"), Mapping):
        failures.append("value_contract_missing")
    failures.append("provider_registration_missing")
    return "open_registration", tuple(failures)


def _contract_failures(binding: Mapping[str, object], registration: Mapping[str, object]) -> list[str]:
    failures: list[str] = []
    provider_payload = binding.get("provider")
    value = binding.get("value")
    if not isinstance(provider_payload, Mapping) or not isinstance(provider_payload.get("kind"), str):
        failures.append("provider_union_member_missing")
    if not isinstance(value, Mapping):
        failures.append("value_contract_missing")
    _check_value_channel(value, registration, failures)
    _check_aggregation(binding.get("aggregation"), registration, failures)
    _check_terminal_origins(binding, registration, failures)
    return failures


def _check_value_channel(value: object, registration: Mapping[str, object], failures: list[str]) -> None:
    channel = value.get("channel") if isinstance(value, Mapping) else None
    if channel not in string_values(registration.get("permitted_value_channels", ())):
        failures.append("value_channel_not_permitted")


def _check_aggregation(aggregation: object, registration: Mapping[str, object], failures: list[str]) -> None:
    if not isinstance(aggregation, Mapping):
        return
    operation = aggregation.get("op")
    if operation not in string_values(registration.get("permitted_aggregation_ops", ())):
        failures.append("aggregation_operation_not_permitted")


def _check_terminal_origins(
    binding: Mapping[str, object],
    registration: Mapping[str, object],
    failures: list[str],
) -> None:
    origins = rows(binding.get("terminal_origins"))
    permitted = string_values(registration.get("permitted_terminal_origins", ()))
    for origin in origins:
        if origin.get("source_class") not in permitted:
            failures.append("terminal_origin_not_permitted")
    if not permitted:
        failures.append("terminal_origin_contract_missing")


def _registered_route_status(
    registration: Mapping[str, object],
    runtime_resolvers: Mapping[str, Mapping[str, object]],
) -> tuple[str, tuple[str, ...]]:
    disposition = registration.get("disposition")
    route = registration.get("route")
    resolver_id = route.get("resolver_id") if isinstance(route, Mapping) else None
    if disposition == "non_runtime":
        return "closed_non_runtime", ()
    if disposition == "deferred":
        return "closed_deferred", ()
    if disposition == "advisory":
        return "closed_advisory", ()
    if disposition != "filing_grade":
        return "open_disposition", ("unknown_registration_disposition",)
    if not isinstance(resolver_id, str):
        return "open_runtime_route", ("filing_grade_resolver_id_missing",)
    if resolver_id not in runtime_resolvers:
        return "open_runtime_route", ("filing_grade_resolver_not_executable",)
    return "closed_filing", ()
