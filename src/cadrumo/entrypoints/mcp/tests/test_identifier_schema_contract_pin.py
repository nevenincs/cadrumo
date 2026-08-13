"""Pin the advertised JSON Schema of every identifier field on the operator wire.

Retyping an identifier field from a plain ``str`` onto a :mod:`core.identity`
alias changes the schema the CLI ``--json`` envelope and the MCP
``tools/list`` descriptor ADVERTISE, not merely the value the model accepts.
``minLength``, ``maxLength`` and ``pattern`` appear where a consumer previously
saw an unconstrained string, and a later loosening of one alias silently
relaxes that published contract at every field carrying it. This module makes
such a change a reviewed diff.

Two properties are asserted, both over the LIVE surfaces:

* every field on a model reachable from :data:`~core.json_contract.SCHEMA_REGISTRY`
  whose annotation carries a canonical identifier alias advertises exactly the
  constraint object pinned in :data:`_PINNED_SCHEMAS`; and
* the MCP ``output_schema`` built from the same registry advertises the same
  constraints, so the two operator surfaces cannot drift apart.

The pinned expectations are LITERALS transcribed from each alias declaration,
never computed from the alias. Deriving them would make the assertion
tautological: a loosened alias would loosen the expectation in lock-step and
the gate would stay green through the exact change it exists to catch.
Classification, by contrast, IS done against the live alias objects, so a
loosened alias still classifies its fields into the same family and is then
caught by the literal comparison.

The module lives on the MCP side because :func:`.._tools._output_schema_for` is
private to this package and a CLI-side test could not reach it without a
cross-package private import. The CLI side needs no such reach: its payload
classes arrive through the public :data:`~core.json_contract.SCHEMA_REGISTRY`
facade, so one module covers both surfaces rather than splitting the contract
across two homes.
"""

from __future__ import annotations

import typing
from collections.abc import Iterator, Mapping
from typing import Any, Final

import pytest
from pydantic import BaseModel

from ....core import Hex16Str, Hex64Str
from ....core.identity import (
    AeatBoxNumber,
    AeatCertificadoId,
    AeatClaveLiquidacion,
    AeatCsv,
    AeatExpedienteId,
    AeatPresentationId,
    BucketId,
    ContentDigestOrAbsent,
    ProfileId,
    ProfileLabel,
    RegistrySnapshotId,
    SubjectTaxId,
    TaxIdIdentityToken,
)
from ....core.json_contract import SCHEMA_REGISTRY
from .._dispatch import is_exposable_command
from .._result_thinning import THINNED_VERBS
from .._tools import _output_schema_for, build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Constraint keys that make up the advertised shape of a constrained string.
_CONSTRAINT_KEYS: Final = ("type", "minLength", "maxLength", "pattern")

#: The canonical identifier aliases, paired with the family name the pinned
#: expectation is keyed by. Several aliases are ONE object -- every hex-64
#: identity concept resolves to ``Hex64Str`` -- so they share one family and one
#: pinned shape by construction.
_ALIAS_FAMILIES: Final[tuple[tuple[str, Any], ...]] = (
    ("hex64", Hex64Str),
    ("hex16", Hex16Str),
    ("bucket_id", BucketId),
    ("registry_snapshot_id", RegistrySnapshotId),
    ("profile_id", ProfileId),
    ("profile_label", ProfileLabel),
    ("content_digest_or_absent", ContentDigestOrAbsent),
    ("aeat_csv", AeatCsv),
    ("aeat_expediente_id", AeatExpedienteId),
    ("aeat_certificado_id", AeatCertificadoId),
    ("aeat_clave_liquidacion", AeatClaveLiquidacion),
    ("aeat_presentation_id", AeatPresentationId),
    ("aeat_box_number", AeatBoxNumber),
    ("subject_tax_id", SubjectTaxId),
    ("tax_id_identity_token", TaxIdIdentityToken),
)

#: The advertised constraint object each family publishes, transcribed by hand
#: from the alias declarations in ``core.identity`` and ``core._hex``.
#:
#: ``aeat_csv`` carries NO ``pattern`` on purpose: its alias runs a normalising
#: ``BeforeValidator`` ahead of its ``StringConstraints``, so the pattern
#: constrains the validator's OUTPUT rather than a consumer's input and pydantic
#: withholds it from the validation-mode schema. The pattern is still enforced
#: (proved below); it is simply not part of the published input contract, and
#: pinning the absence keeps a pydantic upgrade that starts publishing it from
#: passing unnoticed.
#:
#: ``subject_tax_id`` and ``tax_id_identity_token`` are pure validator aliases
#: with no ``StringConstraints`` at all, so they publish a bare string. Their
#: presence here records that the retype is deliberately invisible on the wire.
_PINNED_SCHEMAS: Final[Mapping[str, Mapping[str, object]]] = {
    "hex64": {"type": "string", "minLength": 64, "maxLength": 64, "pattern": r"^[0-9a-f]{64}$"},
    "hex16": {"type": "string", "minLength": 16, "maxLength": 16, "pattern": r"^[0-9a-f]{16}$"},
    "bucket_id": {"type": "string", "minLength": 1, "maxLength": 128},
    "registry_snapshot_id": {"type": "string", "minLength": 1, "maxLength": 128},
    "profile_id": {
        "type": "string",
        "minLength": 1,
        "maxLength": 36,
        "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    },
    "profile_label": {"type": "string", "minLength": 1, "maxLength": 64},
    "content_digest_or_absent": {"type": "string", "maxLength": 64, "pattern": r"^(?:[0-9a-f]{64})?$"},
    "aeat_csv": {"type": "string", "minLength": 8, "maxLength": 32},
    "aeat_expediente_id": {"type": "string", "minLength": 12, "maxLength": 32, "pattern": r"^[0-9]{4,}[A-Z0-9]+$"},
    "aeat_certificado_id": {"type": "string", "minLength": 10, "maxLength": 16, "pattern": r"^\d{10,16}$"},
    "aeat_clave_liquidacion": {"type": "string", "minLength": 1, "maxLength": 64},
    "aeat_presentation_id": {"type": "string", "maxLength": 64},
    "aeat_box_number": {"type": "string", "minLength": 1, "maxLength": 16, "pattern": r"^\d+$"},
    "subject_tax_id": {"type": "string"},
    "tax_id_identity_token": {"type": "string"},
}

#: Named field sites that MUST stay alias-typed. The sweep below is discovered
#: from the live annotations, so a field silently regressed to a bare ``str``
#: would simply drop out of it and take its coverage with it. These entries make
#: that regression a failure. The list is a floor, not an inventory: a new
#: alias-typed field needs no entry here and is still swept.
_NAMED_SITES: Final[tuple[tuple[str, str, str, str], ...]] = (
    (
        "cadrumo.entrypoints.cli._overview_payloads",
        "OverviewCalendarEventPayload",
        "verified_justificante_csv",
        "aeat_csv",
    ),
    (
        "cadrumo.entrypoints.cli._overview_payloads",
        "OverviewCalendarFilingEvidencePayload",
        "verified_justificante_csv",
        "aeat_csv",
    ),
    (
        "cadrumo.entrypoints.cli._app_live_payloads",
        "ExpedienteDeclarationPayload",
        "expediente_id",
        "aeat_expediente_id",
    ),
    ("cadrumo.entrypoints.cli._app_live_payloads", "Borrador100LatestResult", "snapshot_id", "hex64"),
    ("cadrumo.entrypoints.cli._app_live_payloads", "Borrador100LatestResult", "bucket_id", "bucket_id"),
    ("cadrumo.entrypoints.cli._config_payloads", "ConfigProfilePreflightResult", "profile_id", "profile_id"),
    (
        "cadrumo.entrypoints.cli._ledger_business_payloads",
        "EvidenceExtractResult",
        "supplier_tax_id",
        "tax_id_identity_token",
    ),
)


@pytest.fixture(scope="module", autouse=True)
def _populate_schema_registry() -> None:
    """Drive the real CLI payload discovery so the registry is fully populated."""
    build_tool_descriptors()


def _family_of(annotation: object) -> str | None:
    """Return the identifier family an annotation carries, if any.

    Classification runs against the LIVE alias objects, so a loosened alias
    still sorts its fields into the same family and is then caught by the
    literal comparison rather than dropping silently out of the sweep.

    Matching is by CARRIED METADATA, not only by whole-annotation equality,
    because ``Annotated`` flattens: writing ``Annotated[Hex64Str, Field(...)]``
    to overlay a bound produces ``Annotated[str, StringConstraints(...),
    FieldInfo(...)]``, in which the alias object no longer appears. That
    overlay is the cheapest way to publish a loosened bound on an
    alias-typed field, so an equality-only classifier would let precisely the
    change this module exists to catch walk straight out of the sweep.
    """
    for family, alias in _ALIAS_FAMILIES:
        if annotation == alias:
            return family
    carried = getattr(annotation, "__metadata__", ())
    if carried:
        for family, alias in _ALIAS_FAMILIES:
            required = getattr(alias, "__metadata__", ())
            if required and all(any(item == entry for item in carried) for entry in required):
                return family
    for argument in typing.get_args(annotation):
        nested = _family_of(argument)
        if nested is not None:
            return nested
    return None


def _reachable_models(annotation: object, seen: set[type[BaseModel]]) -> None:
    """Collect every pydantic model reachable from an annotation.

    Field annotations are resolved through :func:`typing.get_type_hints` rather
    than read off ``model_fields``: a payload class referenced before its own
    definition leaves an unresolved forward reference on the field, and reading
    it raw silently loses the whole subtree behind that field.
    """
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if annotation in seen:
            return
        seen.add(annotation)
        hints = typing.get_type_hints(annotation, include_extras=True)
        for name in annotation.model_fields:
            _reachable_models(hints.get(name), seen)
        return
    for argument in typing.get_args(annotation):
        _reachable_models(argument, seen)


def _string_leaves(
    node: object,
    definitions: Mapping[str, Any],
    seen_refs: frozenset[str],
    *,
    follow_refs: bool,
) -> Iterator[dict[str, object]]:
    """Yield the constraint object of every string leaf reachable in a schema."""
    if not isinstance(node, Mapping):
        return
    reference = node.get("$ref")
    if isinstance(reference, str):
        name = reference.rsplit("/", 1)[-1]
        if name in seen_refs:
            return
        target = definitions.get(name)
        # A PEP-695 ``type`` alias publishes through a NAMED definition rather
        # than inline, so a per-field walk that refuses every ``$ref`` loses it.
        # Follow a definition that is not an object model even when the caller
        # asked not to descend into nested payload classes.
        if not follow_refs and (not isinstance(target, Mapping) or "properties" in target):
            return
        yield from _string_leaves(target, definitions, seen_refs | {name}, follow_refs=follow_refs)
        return
    if node.get("type") == "string":
        yield {key: node[key] for key in _CONSTRAINT_KEYS if key in node}
    for branch in ("anyOf", "oneOf", "allOf", "prefixItems"):
        for member in node.get(branch, ()) or ():
            yield from _string_leaves(member, definitions, seen_refs, follow_refs=follow_refs)
    for nested in ("items", "additionalProperties", "contains"):
        yield from _string_leaves(node.get(nested), definitions, seen_refs, follow_refs=follow_refs)
    for sub in (node.get("properties") or {}).values():
        yield from _string_leaves(sub, definitions, seen_refs, follow_refs=follow_refs)


def _alias_typed_sites() -> tuple[tuple[str, str, str, str, tuple[dict[str, object], ...]], ...]:
    """Return every alias-typed field reachable from the registry.

    Each entry is ``(module, class, field, family, advertised_leaves)``. The
    advertised leaves are read from the OWNING class's own schema without
    following ``$ref``, so a nested model's constraints are attributed to that
    model rather than double-counted at every field pointing at it.
    """
    models: set[type[BaseModel]] = set()
    for schema in SCHEMA_REGISTRY.values():
        _reachable_models(schema, models)

    sites: list[tuple[str, str, str, str, tuple[dict[str, object], ...]]] = []
    for model in sorted(models, key=lambda entry: (entry.__module__, entry.__name__)):
        schema = model.model_json_schema()
        properties = schema.get("properties") or {}
        definitions = schema.get("$defs", {}) or {}
        hints = typing.get_type_hints(model, include_extras=True)
        for field in model.model_fields:
            family = _family_of(hints.get(field))
            if family is None:
                continue
            leaves = tuple(_string_leaves(properties.get(field), definitions, frozenset(), follow_refs=False))
            sites.append((model.__module__, model.__name__, field, family, leaves))
    return tuple(sites)


def test_every_alias_typed_field_advertises_the_pinned_cli_constraints() -> None:
    """Each identifier field publishes exactly the constraints pinned for its family."""
    sites = _alias_typed_sites()
    assert sites, "no alias-typed identifier field was discovered on the registered wire surface"

    divergent: list[str] = []
    for module, cls, field, family, leaves in sites:
        expected = _PINNED_SCHEMAS[family]
        for leaf in leaves:
            if leaf != expected:
                divergent.append(f"{module}.{cls}.{field} [{family}] advertises {leaf!r}, pinned {expected!r}")
        if not leaves:
            divergent.append(f"{module}.{cls}.{field} [{family}] advertises no string leaf at all")
    assert not divergent, "advertised identifier constraints diverged from the pin:\n" + "\n".join(divergent)


def test_the_named_identifier_sites_are_still_alias_typed() -> None:
    """A field regressed to a bare string cannot quietly leave the sweep."""
    discovered = {(module, cls, field): family for module, cls, field, family, _ in _alias_typed_sites()}
    missing = [
        f"{module}.{cls}.{field} expected family {family}, found {discovered.get((module, cls, field))!r}"
        for module, cls, field, family in _NAMED_SITES
        if discovered.get((module, cls, field)) != family
    ]
    assert not missing, "pinned identifier sites lost their canonical typing:\n" + "\n".join(missing)


def _constrained_shapes(leaves: Iterator[dict[str, object]]) -> set[tuple[tuple[str, object], ...]]:
    """Return the distinct constrained string shapes among the given leaves.

    A bare ``{"type": "string"}`` carries no constraint and is dropped, so the
    comparison is about published bounds rather than about how many strings a
    payload happens to hold.
    """
    return {tuple(sorted(leaf.items())) for leaf in leaves if len(leaf) > 1}


def _mcp_result_leaves(command: str) -> tuple[dict[str, object], ...]:
    """Return the string-leaf constraint objects of one command's MCP output schema."""
    output_schema = _output_schema_for(command)
    return tuple(
        _string_leaves(
            output_schema["oneOf"][0]["properties"]["result"],
            output_schema.get("$defs", {}) or {},
            frozenset(),
            follow_refs=True,
        ),
    )


def _mcp_commands_by_reachable_model() -> dict[type[BaseModel], tuple[str, ...]]:
    """Map each registered-result projection model to every exposing MCP command.

    The map begins at the production ``SCHEMA_REGISTRY`` rather than at a test
    allowlist, then follows the same resolved annotations as the CLI sweep.
    This keeps nested rows tied to their actual command envelope and includes a
    thinned command: thinning changes the advertised result schema, it does not
    make its still-present identifier fields exempt from the pin.
    """
    commands_by_model: dict[type[BaseModel], set[str]] = {}
    for command, schema in SCHEMA_REGISTRY.items():
        models: set[type[BaseModel]] = set()
        _reachable_models(schema, models)
        if not is_exposable_command(command):
            continue
        for model in models:
            commands_by_model.setdefault(model, set()).add(command)
    return {model: tuple(sorted(commands)) for model, commands in commands_by_model.items()}


def _mcp_model_field_leaves(
    command: str,
    model: type[BaseModel],
    field: str,
) -> tuple[dict[str, object], ...]:
    """Return the advertised leaves for one exact model field on one MCP result.

    The success envelope in :func:`_output_schema_for` carries its registered
    root inline and nested payload models under ``$defs``.  Looking up the
    concrete model's own property prevents a matching hex or bucket field
    elsewhere in the same command from standing in for this field.
    """
    output_schema = _output_schema_for(command)
    definitions_value = output_schema.get("$defs")
    assert isinstance(definitions_value, Mapping), f"{command} MCP schema has no definitions mapping"
    definitions = definitions_value
    one_of = output_schema.get("oneOf")
    assert isinstance(one_of, list) and one_of, f"{command} has no MCP success envelope"
    success = one_of[0]
    assert isinstance(success, Mapping), f"{command} has no object-shaped MCP success envelope"
    properties = success.get("properties")
    assert isinstance(properties, Mapping), f"{command} MCP success envelope has no properties"
    result = properties.get("result")
    assert isinstance(result, Mapping), f"{command} MCP success envelope has no result schema"

    model_schema: Mapping[object, object]
    if SCHEMA_REGISTRY[command] is model:
        model_schema = result
    else:
        nested = definitions.get(model.__name__)
        assert isinstance(nested, Mapping), (
            f"{command} has no MCP definition for reachable {model.__module__}.{model.__name__}"
        )
        model_schema = nested
    field_schemas = model_schema.get("properties")
    assert isinstance(field_schemas, Mapping) and field in field_schemas, (
        f"{command} MCP schema omits {model.__module__}.{model.__name__}.{field}"
    )
    return tuple(_string_leaves(field_schemas[field], definitions, frozenset(), follow_refs=False))


def test_every_mcp_output_schema_advertises_each_enrolled_identifier_field() -> None:
    """Every reachable identifier field has its literal pin on its actual MCP path.

    This is deliberately per-model-field, rather than a representative command
    per alias family or a set comparison over a whole result.  An unrelated
    same-shaped field cannot therefore conceal a missing or loosened bound, and
    thinned verbs remain covered for every identifier field they still expose.
    """
    models: set[type[BaseModel]] = set()
    for schema in SCHEMA_REGISTRY.values():
        _reachable_models(schema, models)
    models_by_key = {(model.__module__, model.__name__): model for model in models}
    commands_by_model = _mcp_commands_by_reachable_model()

    divergent: list[str] = []
    for module, cls, field, family, _ in _alias_typed_sites():
        model = models_by_key.get((module, cls))
        if model is None:
            divergent.append(f"registry walk lost {module}.{cls}.{field} [{family}]")
            continue
        commands = commands_by_model.get(model, ())
        if not commands:
            divergent.append(f"{module}.{cls}.{field} [{family}] has no MCP-exposable command")
            continue
        expected = _PINNED_SCHEMAS[family]
        for command in commands:
            leaves = _mcp_model_field_leaves(command, model, field)
            if not leaves:
                divergent.append(f"{command} omits a string leaf for {module}.{cls}.{field} [{family}]")
            for leaf in leaves:
                if leaf != expected:
                    divergent.append(
                        f"{command} {module}.{cls}.{field} [{family}] advertises {leaf!r}, pinned {expected!r}",
                    )
    assert not divergent, "MCP identifier constraints diverged from the pin:\n" + "\n".join(divergent)


def test_cli_and_mcp_advertise_the_same_constrained_string_shapes() -> None:
    """Neither operator surface may publish a bound the other does not.

    Compares the two independently-generated schemas against each other rather
    than against the pinned table, so this catches a divergence in shapes the
    table does not enumerate.

    Thinning is the one sanctioned asymmetry and it moves in both directions: a
    thinned verb drops its bulk array's item shapes from the MCP schema and adds
    the non-empty ``<key>_resource`` marker, which is a ``minLength``-bounded
    string the CLI envelope never carries. Both are scoped to
    :data:`.._result_thinning.THINNED_VERBS`; an UNTHINNED verb must publish
    exactly the same bounds on both surfaces.
    """
    divergent: list[str] = []
    for command in sorted(SCHEMA_REGISTRY):
        if not is_exposable_command(command):
            continue
        cli_schema = SCHEMA_REGISTRY[command].model_json_schema()
        cli_shapes = _constrained_shapes(
            _string_leaves(cli_schema, cli_schema.get("$defs", {}) or {}, frozenset(), follow_refs=True),
        )
        mcp_shapes = _constrained_shapes(iter(_mcp_result_leaves(command)))
        if command in THINNED_VERBS:
            continue
        if mcp_shapes != cli_shapes:
            divergent.append(
                f"{command}: MCP-only {sorted(mcp_shapes - cli_shapes)}, CLI-only {sorted(cli_shapes - mcp_shapes)}",
            )
    assert not divergent, "CLI and MCP published string bounds diverged:\n" + "\n".join(divergent)
