"""Closed-schema validation helpers for the operation registry.

The public registry keeps the model and registry classes in their historical
module.  These helpers own the recursive schema rules that those classes use,
so the rules can evolve without turning the registry facade into one large
validation unit.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field, is_dataclass
from typing import TypeAliasType, get_args, get_origin

from pydantic import BaseModel, PydanticInvalidForJsonSchema
from pydantic.fields import FieldInfo

from ...core.hex import HEX_PATTERN_64
from ...core.type_guards import is_object_dict, is_object_list, is_object_list_or_tuple, is_str_keyed_dict
from ._dataclass_fields import dataclass_instance_fields
from ._model_contract import require_strict_frozen_operation_model_graph

#: Field-name tokens a credential-free journal request may not carry.
#:
#: A NAME tripwire, not the wall. What actually keeps a secret out of the
#: journal is the storage policy plus the separate ephemeral-secret channel;
#: this catches the case where a field is added whose name says plainly what it
#: holds. Matching is on whole ``_``-separated tokens, so it never fires on a
#: word that merely contains one of these.
#:
#: The second group are the words THIS codebase uses for credential material
#: and that the first group missed: the certificate path spells its material
#: ``cert``/``certificate``/``pem``/``private``, and the Cl@ve factors are a
#: ``pin`` and a one-time code. ``certificate_pem``, ``clave_pin`` and
#: ``otp_code`` all split into tokens the original set did not hold, so each
#: would have journalled its own name unchallenged.
#:
#: ``clave`` is deliberately ABSENT despite naming the Cl@ve authentication
#: system, because it is a homonym: AEAT also spells an operation key
#: ``clave``, and ``clave``/``clave_operacion``/``clave_declarado`` are real
#: fields on the detail rows an amendment journals. Adding it would refuse a
#: lawful M184 or M347 amendment to catch a credential nothing names that way.
FORBIDDEN_CREDENTIAL_FREE_FIELD_PARTS = frozenset(
    {
        "auth",
        "bearer",
        "callback",
        "cookie",
        "credential",
        "ciphertext",
        "digest",
        "encrypted",
        "frontend",
        "hash",
        "key",
        "passphrase",
        "password",
        "proof",
        "secret",
        "session",
        "signature",
        "token",
        "transport",
        "verifier",
        "wrapped",
        "cert",
        "certificate",
        "challenge",
        "jwt",
        "nonce",
        "otp",
        "pem",
        "pin",
        "private",
        "salt",
        "totp",
    }
)
FORBIDDEN_OPERATION_SCHEMA_FORMATS = frozenset({"binary", "byte", "password"})
HEX64_DIGEST_PATTERN = HEX_PATTERN_64


@dataclass(frozen=True)
class _CompiledModelSchema:
    schema: dict[str, object]
    model_graph: dict[type[BaseModel], tuple[object, ...]]
    core_schemas: Mapping[type[BaseModel], object]


@dataclass
class _SchemaCompilationMemo:
    schemas: dict[type[BaseModel], _CompiledModelSchema] = field(default_factory=dict)
    active: bool = True


_SCHEMA_COMPILATION_MEMO: ContextVar[_SchemaCompilationMemo | None] = ContextVar(
    "operation_schema_compilation_memo", default=None
)
_SCHEMA_ATOMIC_TYPES = frozenset((str, int, float, bool, bytes, type(None)))


@contextmanager
def operation_schema_compilation_scope() -> Generator[None]:
    """Reuse validated schemas during one registry build, with isolated copies.

    Each invocation owns a fresh memo, including nested scopes. Leaving the
    scope restores the caller's context even when compilation raises.
    """
    memo = _SchemaCompilationMemo()
    token = _SCHEMA_COMPILATION_MEMO.set(memo)
    try:
        yield
    finally:
        memo.active = False
        memo.schemas.clear()
        _SCHEMA_COMPILATION_MEMO.reset(token)


def _copy_model_schema(schema: dict[str, object]) -> dict[str, object]:
    """Copy JSON containers while preserving aliases and custom metadata types."""
    if type(schema) is not dict:
        return deepcopy(schema)
    copied: dict[str, object] = {}
    copy_memo: dict[int, object] = {id(schema): copied}
    originals: list[object] = [schema]
    for key, value in schema.items():
        copied[key if type(key) is str else deepcopy(key, copy_memo)] = _copy_schema_value(value, copy_memo, originals)
    return copied


def _copy_schema_value(value: object, copy_memo: dict[int, object], originals: list[object]) -> object:
    """Avoid generic copy dispatch for the built-in containers of a JSON schema."""
    value_type = type(value)
    if value_type in _SCHEMA_ATOMIC_TYPES:
        return value
    identity = id(value)
    if identity in copy_memo:
        return copy_memo[identity]
    # A custom deepcopy hook can release a previously copied source node.
    # Keep those sources alive so its identity cannot be recycled in the memo.
    if value_type is dict and is_object_dict(value):
        copied: dict[object, object] = {}
        copy_memo[identity] = copied
        originals.append(value)
        for key, item in value.items():
            copied[key if type(key) is str else deepcopy(key, copy_memo)] = _copy_schema_value(
                item, copy_memo, originals
            )
        return copied
    if value_type is list and is_object_list(value):
        copied_items: list[object] = []
        copy_memo[identity] = copied_items
        originals.append(value)
        copied_items.extend(_copy_schema_value(item, copy_memo, originals) for item in value)
        return copied_items
    return deepcopy(value, copy_memo)


def _model_schema_graph_state(
    model_type: type[BaseModel], *, rebuilt_models: set[type[BaseModel]] | None = None
) -> dict[type[BaseModel], tuple[object, ...]]:
    """Capture live schema state, including nested models and editable metadata."""
    graph: dict[type[BaseModel], tuple[object, ...]] = {}
    snapshots: dict[int, tuple[object, object]] = {}

    def visit(annotation: object) -> None:
        if isinstance(annotation, TypeAliasType):
            visit(annotation.__value__)
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if annotation in graph:
                return
            if not annotation.__pydantic_complete__:
                annotation.model_rebuild()
                if rebuilt_models is not None:
                    rebuilt_models.add(annotation)
            graph[annotation] = (
                _schema_state(annotation.model_config, snapshots),
                annotation.model_json_schema,
                tuple((name, _field_schema_state(field, snapshots)) for name, field in annotation.model_fields.items()),
            )
            for field in annotation.model_fields.values():
                visit(field.annotation)
        else:
            for argument in get_args(annotation):
                visit(argument)

    visit(model_type)
    return graph


def _field_schema_state(field: FieldInfo, snapshots: dict[int, tuple[object, object]]) -> object:
    """Freeze field metadata without retaining temporary field dictionaries."""
    document = field.asdict()
    # The attribute names are fixed by FieldInfo; omitted None values still
    # distinguish every transition to or from a populated attribute.
    return (
        _annotation_schema_state(field.annotation, snapshots),
        _schema_state(document["metadata"], snapshots),
        tuple(
            (name, _schema_state(value, snapshots))
            for name, value in document["attributes"].items()
            if value is not None
        ),
    )


def _schema_state(value: object, snapshots: dict[int, tuple[object, object]]) -> object:
    """Freeze schema containers and metadata without cloning identity-based types."""
    # Field metadata contains mostly immutable built-in leaves. They cannot
    # carry mutable attributes, so avoid walking the container/dataclass checks
    # for every leaf on every fingerprint revalidation. Subclasses still take
    # the full path because they may carry editable metadata of their own.
    value_type = type(value)
    if value_type in _SCHEMA_ATOMIC_TYPES:
        return value
    if isinstance(value, type) or callable(value):
        return value
    if id(value) in snapshots:
        return snapshots[id(value)][1]
    state = _structured_schema_state(value, snapshots)
    if state is None:
        return value
    snapshots[id(value)] = value, state
    return state


def _structured_schema_state(value: object, snapshots: dict[int, tuple[object, object]]) -> object | None:
    """Freeze supported mutable containers and metadata as structural values."""
    if is_object_dict(value):
        return tuple((key, _schema_state(item, snapshots)) for key, item in value.items())
    if is_object_list_or_tuple(value):
        return type(value), tuple(_schema_state(item, snapshots) for item in value)
    if isinstance(value, FieldInfo):
        return type(value), _field_schema_state(value, snapshots)
    if is_dataclass(value):
        return _dataclass_schema_state(value, snapshots)
    if hasattr(value, "__dict__"):
        return type(value), _schema_state(vars(value), snapshots)
    return None


def _dataclass_schema_state(value: object, snapshots: dict[int, tuple[object, object]]) -> object:
    """Freeze editable dataclass metadata without copying its identity."""
    return (
        type(value),
        tuple(
            (attribute.name, _schema_state(getattr(value, attribute.name), snapshots))
            for attribute in dataclass_instance_fields(value)
        ),
    )


def _annotation_schema_state(annotation: object, snapshots: dict[int, tuple[object, object]]) -> object:
    """Capture annotation metadata structurally while preserving type identities."""
    if isinstance(annotation, TypeAliasType):
        return "alias", annotation, _annotation_schema_state(annotation.__value__, snapshots)
    arguments = get_args(annotation)
    if arguments:
        # Tag typing nodes so tuple-valued metadata cannot alias their state.
        return (
            "arguments",
            get_origin(annotation),
            tuple(_annotation_schema_state(argument, snapshots) for argument in arguments),
        )
    return _schema_state(annotation, snapshots)


def is_hex64_shaped_schema(
    value: object,
    *,
    definitions: Mapping[str, object] | None = None,
    _seen_refs: frozenset[str] = frozenset(),
) -> bool:
    """Report whether one field's JSON-schema fragment matches Hex64 shape.

    ``ContentDigest`` is a bare assignment to ``Hex64Str`` (``ContentDigest
    is Hex64Str``), not a distinct type, and ``Hex64Str`` is deliberately
    shared by several unrelated concepts (``WorkUnitId``,
    ``CalculationRevisionId``, ``SnapshotId``, ``TransactionId``). There is
    therefore no runtime type-identity test for ``ContentDigest`` specifically
    - only a SHAPE test for ``64 lowercase hex characters``. Recurses through
    local ``$defs`` references, ``anyOf`` (an ``X | None`` field), and
    ``items`` (a ``tuple[X, ...]`` field) to reach the underlying string
    schema.
    """
    if not is_str_keyed_dict(value):
        return False
    mapping = value
    resolved = _resolve_local_schema_ref(mapping, definitions)
    if resolved is not None:
        ref, target = resolved
        if ref in _seen_refs:
            return False
        return is_hex64_shaped_schema(target, definitions=definitions, _seen_refs=_seen_refs | {ref})
    if is_hex64_string_schema(mapping):
        return True
    if is_hex64_any_of_schema(mapping, definitions=definitions, _seen_refs=_seen_refs):
        return True
    return is_hex64_items_schema(mapping, definitions=definitions, _seen_refs=_seen_refs)


def _resolve_local_schema_ref(
    mapping: Mapping[str, object],
    definitions: Mapping[str, object] | None,
) -> tuple[str, Mapping[str, object]] | None:
    """Resolve one local ``$defs`` reference without following external schemas."""
    ref = mapping.get("$ref")
    if definitions is None or not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        return None
    encoded_name = ref.removeprefix("#/$defs/")
    if "/" in encoded_name:
        return None
    definition_name = encoded_name.replace("~1", "/").replace("~0", "~")
    target = definitions.get(definition_name)
    if not is_str_keyed_dict(target):
        return None
    return ref, target


def is_hex64_string_schema(mapping: Mapping[str, object]) -> bool:
    """Recognize the direct JSON-schema shape of one lowercase Hex64 value."""
    return (
        mapping.get("type") == "string"
        and mapping.get("pattern") == HEX64_DIGEST_PATTERN
        and mapping.get("minLength") == 64
        and mapping.get("maxLength") == 64
    )


def is_hex64_any_of_schema(
    mapping: Mapping[str, object],
    *,
    definitions: Mapping[str, object] | None = None,
    _seen_refs: frozenset[str] = frozenset(),
) -> bool:
    """Search non-null branches of an optional JSON-schema value for Hex64."""
    any_of = mapping.get("anyOf")
    if not is_object_list(any_of):
        return False
    non_null_branches: list[Mapping[str, object]] = []
    for item in any_of:
        if not is_str_keyed_dict(item):
            return False
        if item.get("type") == "null":
            continue
        non_null_branches.append(item)
    return bool(non_null_branches) and all(
        is_hex64_shaped_schema(branch, definitions=definitions, _seen_refs=_seen_refs) for branch in non_null_branches
    )


def is_hex64_items_schema(
    mapping: Mapping[str, object],
    *,
    definitions: Mapping[str, object] | None = None,
    _seen_refs: frozenset[str] = frozenset(),
) -> bool:
    """Search a homogeneous tuple/array item schema for Hex64."""
    items = mapping.get("items")
    if is_str_keyed_dict(items):
        return is_hex64_shaped_schema(items, definitions=definitions, _seen_refs=_seen_refs)
    return False


def validate_credential_free_schema(schema: object, *, definitions: Mapping[str, object] | None = None) -> None:
    """Reject request schemas capable of carrying credentials or transports.

    A field name matching ONLY the ``digest`` forbidden token (no other
    forbidden token also matches) is admitted when its schema shape is exactly
    Hex64 - a compare-and-swap content digest, never a bearer token or
    passphrase by shape. A field matching any OTHER forbidden token is refused
    regardless of shape, and regardless of whether it also matches ``digest``;
    the exemption never widens any token but ``digest`` and never overrides a
    second, independently-matched forbidden token on the same field.
    """
    root_document = definitions is None
    if definitions is None:
        definitions = {}
    if is_object_list(schema):
        validate_credential_free_schema_items(schema, definitions=definitions)
        return
    if not is_object_dict(schema):
        return
    # Every JSON object names its members with strings; a mapping that does not
    # cannot be walked by name, so it is refused rather than skipped unread.
    if not is_str_keyed_dict(schema):
        raise ValueError("credential-free journal request schema has a non-string field name")
    mapping = schema
    local_definitions = mapping.get("$defs")
    if root_document and is_str_keyed_dict(local_definitions):
        definitions = local_definitions
    validate_credential_free_schema_format(mapping)
    validate_credential_free_schema_properties(mapping, definitions=definitions)
    for value in mapping.values():
        validate_credential_free_schema(value, definitions=definitions)


def validate_credential_free_schema_items(
    items: list[object], *, definitions: Mapping[str, object] | None = None
) -> None:
    """Recursively inspect every branch in a JSON-schema list container."""
    for item in items:
        validate_credential_free_schema(item, definitions=definitions)


def validate_credential_free_schema_format(mapping: Mapping[str, object]) -> None:
    """Reject schema formats that can carry credentials in journal input."""
    if mapping.get("format") in FORBIDDEN_OPERATION_SCHEMA_FORMATS:
        raise ValueError("credential-free journal request schema contains a secret-capable format")


def validate_credential_free_schema_properties(
    mapping: Mapping[str, object], *, definitions: Mapping[str, object] | None = None
) -> None:
    """Reject forbidden names while admitting only digest-shaped exceptions."""
    properties = mapping.get("properties")
    if not is_object_dict(properties):
        return
    # A non-string property name cannot be token-matched against the forbidden
    # set, so the tripwire refuses it rather than walking past it unexamined.
    if not is_str_keyed_dict(properties):
        raise ValueError("credential-free journal request schema has a non-string field name")
    for field_name, field_schema in properties.items():
        parts = set(field_name.lower().replace("-", "_").split("_"))
        matched = parts & FORBIDDEN_CREDENTIAL_FREE_FIELD_PARTS
        if not matched:
            continue
        if matched == {"digest"} and is_hex64_shaped_schema(field_schema, definitions=definitions):
            continue
        raise ValueError(f"credential-free journal request field {field_name!r} has a forbidden security meaning")


def strict_model_json_schema(model_type: type[BaseModel]) -> dict[str, object]:
    """Return one exact closed schema after enforcing the public model baseline."""
    require_strict_frozen_operation_model_graph(model_type, path="public schema")
    memo = _active_schema_compilation_memo()
    rebuilt_models: set[type[BaseModel]] = set()
    model_graph = _model_schema_graph_state(model_type, rebuilt_models=rebuilt_models) if memo is not None else None
    # Deferred rebuilding can reveal nested models the first contract check could not inspect.
    if rebuilt_models:
        require_strict_frozen_operation_model_graph(model_type, path="public schema")
    cached_schema = _cached_model_schema(memo, model_type, model_graph)
    if cached_schema is not None:
        return cached_schema
    original_graph = model_graph
    original_core_schemas = (
        {nested: nested.__pydantic_core_schema__ for nested in model_graph} if model_graph is not None else {}
    )
    closed_schema = _generate_closed_model_schema(model_type)
    _remember_compiled_model_schema(
        memo,
        model_type,
        closed_schema,
        original_graph,
        original_core_schemas,
    )
    return closed_schema


def _active_schema_compilation_memo() -> _SchemaCompilationMemo | None:
    """Return the context memo only while its registry build remains active."""
    memo = _SCHEMA_COMPILATION_MEMO.get()
    return memo if memo is None or memo.active else None


def _cached_model_schema(
    memo: _SchemaCompilationMemo | None,
    model_type: type[BaseModel],
    model_graph: dict[type[BaseModel], tuple[object, ...]] | None,
) -> dict[str, object] | None:
    """Return an isolated cached schema after rechecking its live model graph."""
    compiled = memo.schemas.get(model_type) if memo is not None else None
    if compiled is None:
        return None
    if compiled.model_graph != model_graph or any(
        nested.__pydantic_core_schema__ is not core for nested, core in compiled.core_schemas.items()
    ):
        raise ValueError("public operation schema model graph changed during compilation")
    return _copy_model_schema(compiled.schema)


def _generate_closed_model_schema(model_type: type[BaseModel]) -> dict[str, object]:
    """Generate both public schema modes and validate their closed shape."""
    validation_schema: object
    serialization_schema: object
    try:
        validation_schema = model_type.model_json_schema(mode="validation")
        serialization_schema = model_type.model_json_schema(mode="serialization")
    except PydanticInvalidForJsonSchema as error:
        raise ValueError("public operation schema model must have a closed JSON schema") from error
    if validation_schema != serialization_schema:
        raise ValueError("public operation schema validation and serialization shapes must be identical")
    if not is_str_keyed_dict(validation_schema):
        raise ValueError("public operation schema model must have a closed JSON schema")
    closed_schema = validation_schema
    validate_closed_json_schema(closed_schema, path=model_type.__name__)
    return closed_schema


def _remember_compiled_model_schema(
    memo: _SchemaCompilationMemo | None,
    model_type: type[BaseModel],
    schema: dict[str, object],
    original_graph: dict[type[BaseModel], tuple[object, ...]] | None,
    original_core_schemas: Mapping[type[BaseModel], object],
) -> None:
    """Cache only when the complete live model graph still matches its entry state."""
    if memo is None or original_graph is None:
        return
    if original_graph != _model_schema_graph_state(model_type) or any(
        nested.__pydantic_core_schema__ is not core for nested, core in original_core_schemas.items()
    ):
        raise ValueError("public operation schema model graph changed during compilation")
    memo.schemas[model_type] = _CompiledModelSchema(_copy_model_schema(schema), original_graph, original_core_schemas)


def validate_closed_json_schema(schema: Mapping[str, object], *, path: str) -> None:
    """Refuse every untyped or open branch of one generated public schema."""
    reject_secret_capable_schema_branch(schema, path=path)
    validate_schema_definitions(schema, path=path)
    if schema.get("patternProperties") is not None:
        raise ValueError(f"public operation schema {path} contains a pattern-properties payload bag")
    if "$ref" in schema or "enum" in schema or "const" in schema:
        return
    if validate_schema_combinator(schema, path=path):
        return
    schema_type = schema.get("type")
    if not isinstance(schema_type, str):
        raise ValueError(f"public operation schema {path} contains an untyped branch")
    if schema_type == "object":
        validate_closed_object_schema(schema, path=path)
    elif schema_type == "array":
        validate_closed_array_schema(schema, path=path)


def reject_secret_capable_schema_branch(schema: Mapping[str, object], *, path: str) -> None:
    """Reject public schema branches that can carry opaque secrets."""
    if schema.get("format") in FORBIDDEN_OPERATION_SCHEMA_FORMATS or schema.get("writeOnly") is True:
        raise ValueError(f"public operation schema {path} contains a secret-capable branch")


def validate_schema_definitions(schema: Mapping[str, object], *, path: str) -> None:
    """Validate every named schema definition recursively."""
    definitions = schema.get("$defs")
    if not is_object_dict(definitions):
        return
    if not is_str_keyed_dict(definitions):
        raise ValueError(f"public operation schema {path} has an invalid definition")
    for definition_name, definition in definitions.items():
        if not is_str_keyed_dict(definition):
            raise ValueError(f"public operation schema {path} has an invalid definition")
        validate_closed_json_schema(
            definition,
            path=f"{path}.$defs.{definition_name}",
        )


def validate_schema_combinator(schema: Mapping[str, object], *, path: str) -> bool:
    """Validate the first declared JSON-schema combinator and its branches."""
    for combinator in ("anyOf", "oneOf", "allOf"):
        branches = schema.get(combinator)
        if branches is None:
            continue
        if not is_object_list(branches) or not branches:
            raise ValueError(f"public operation schema {path} has an invalid {combinator}")
        for index, branch in enumerate(branches):
            if not is_str_keyed_dict(branch):
                raise ValueError(f"public operation schema {path} has an invalid {combinator} branch")
            validate_closed_json_schema(
                branch,
                path=f"{path}.{combinator}[{index}]",
            )
        return True
    return False


def validate_closed_object_schema(schema: Mapping[str, object], *, path: str) -> None:
    """Require an object branch to enumerate and close every property."""
    if schema.get("additionalProperties") is not False:
        raise ValueError(f"public operation schema {path} contains an open object branch")
    properties = schema.get("properties", {})
    if not is_str_keyed_dict(properties):
        raise ValueError(f"public operation schema {path} has invalid properties")
    for field_name, field_schema in properties.items():
        if not is_str_keyed_dict(field_schema):
            raise ValueError(f"public operation schema {path}.{field_name} is invalid")
        validate_closed_json_schema(
            field_schema,
            path=f"{path}.{field_name}",
        )


def validate_closed_array_schema(schema: Mapping[str, object], *, path: str) -> None:
    """Require a homogeneous array or a fully fixed tuple to be closed."""
    prefix_items = schema.get("prefixItems")
    if prefix_items is not None:
        validate_closed_tuple_schema(schema, prefix_items, path=path)
        return
    items = schema.get("items")
    if not is_str_keyed_dict(items):
        raise ValueError(f"public operation schema {path} contains an untyped array")
    validate_closed_json_schema(items, path=f"{path}.items")


def validate_closed_tuple_schema(
    schema: Mapping[str, object],
    prefix_items: object,
    *,
    path: str,
) -> None:
    """Require fixed tuple bounds and recursively validate each item."""
    if not is_object_list(prefix_items) or not prefix_items:
        raise ValueError(f"public operation schema {path} has invalid fixed tuple items")
    typed_prefix_items = prefix_items
    item_count = len(typed_prefix_items)
    if schema.get("minItems") != item_count or schema.get("maxItems") != item_count:
        raise ValueError(f"public operation schema {path} contains an open fixed tuple")
    trailing_items = schema.get("items")
    if trailing_items is not None and trailing_items is not False:
        raise ValueError(f"public operation schema {path} permits undeclared trailing tuple items")
    for index, item in enumerate(typed_prefix_items):
        if not is_str_keyed_dict(item):
            raise ValueError(f"public operation schema {path} has an invalid fixed tuple item")
        validate_closed_json_schema(
            item,
            path=f"{path}.prefixItems[{index}]",
        )


__all__ = [
    "FORBIDDEN_CREDENTIAL_FREE_FIELD_PARTS",
    "FORBIDDEN_OPERATION_SCHEMA_FORMATS",
    "HEX64_DIGEST_PATTERN",
    "is_hex64_any_of_schema",
    "is_hex64_items_schema",
    "is_hex64_shaped_schema",
    "is_hex64_string_schema",
    "operation_schema_compilation_scope",
    "reject_secret_capable_schema_branch",
    "strict_model_json_schema",
    "validate_closed_array_schema",
    "validate_closed_json_schema",
    "validate_closed_object_schema",
    "validate_closed_tuple_schema",
    "validate_credential_free_schema",
    "validate_credential_free_schema_format",
    "validate_credential_free_schema_items",
    "validate_credential_free_schema_properties",
    "validate_schema_combinator",
    "validate_schema_definitions",
]
