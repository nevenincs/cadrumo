"""Closed-schema validation helpers for the operation registry.

The public registry keeps the model and registry classes in their historical
module.  These helpers own the recursive schema rules that those classes use,
so the rules can evolve without turning the registry facade into one large
validation unit.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, PydanticInvalidForJsonSchema

from ...core.hex import HEX_PATTERN_64
from ...core.type_guards import is_object_dict, is_object_list, is_str_keyed_dict
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
