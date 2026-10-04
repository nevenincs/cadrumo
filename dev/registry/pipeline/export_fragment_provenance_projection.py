"""Canonicalize semantic-map and loader projections for provenance digests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, cast

from cadrumo.core.hashing import content_hash_hex
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

from .semantic_map import SemanticMap

_LOADER_SEMANTIC_SCHEMA_VERSION: Final[int] = 7
"""Shape of the projection ``normalised_loader_semantics`` attests.

Every committed manifest's ``loader_semantic_sha256`` is a digest of this
projection, so adding, removing or renaming a projected key re-attests every
generated tree even though no tree byte moved. Bump it with any such change,
in the same change that republishes the trees.

Version 7 is the projection without ``aux_version``: the layout member was
retired, and version 6 had attested it as ``null`` for every layout.
"""


_SEMANTIC_MAP_KEYS: Final[frozenset[str]] = frozenset(
    {"modelo", "design_epoch", "source_ref", "source_sha256", "records", "entries", "variable_envelopes"},
)


_SEMANTIC_MAP_RECORD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "sheet",
        "record_identity",
        "export_record_id",
        "record_type",
        "required",
        "repeat",
        "binding_record",
        "requires_positive_casilla_id",
        "row_field_casilla_ids",
        "discriminator",
    },
)


_SEMANTIC_MAP_ENTRY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "anchor",
        "export_field_id",
        "kind",
        "casilla_id",
        "binding",
        "literal",
        "producer_key",
        "projection_ref",
        "draft_attribute",
        "computed_key",
        "legal_refs",
        "source_refs",
        "part",
        "required_with",
    },
)


#: ``ordinal_absent`` joined this set when the parser gained the ability to
#: read a row AEAT printed with NO ordinal -- a gap-filled position whose
#: naturaleza cell was empty. It is part of the anchor identity, so it is
#: normalised into the digest rather than dropped: two anchors differing only
#: in whether the design printed an ordinal are different anchors.
_SEMANTIC_MAP_ANCHOR_KEYS: Final[frozenset[str]] = frozenset(
    {"sheet", "source_row", "source_cell", "ordinal", "ordinal_absent", "record_identity"},
)


_VARIABLE_ENVELOPE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "source_ref",
        "source_sha256",
        "record_identity",
        "prefix_fields",
        "body_anchor",
        "body_record_ids",
        "closer_anchor",
        "total_anchor",
    },
)


_ENVELOPE_PREFIX_FIELD_KEYS: Final[frozenset[str]] = frozenset({"role", "anchor"})
_ENVELOPE_LANGUAGE_PREFIX_FIELD_KEYS: Final[frozenset[str]] = frozenset({"role", "anchor", "casilla_id"})


_ENVELOPE_TOTAL_ANCHOR_KEYS: Final[frozenset[str]] = frozenset({"source_row", "source_cell", "label", "length"})


_LAYOUT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "id",
        "format",
        "dictionary_source_ref",
        "source_refs",
        "legal_refs",
        "records",
        "filing_envelope",
        "auxiliary_envelope_header",
        "dictionary_path_overrides",
        "aux_idioma",
    },
)


_RECORD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "id",
        "record_type",
        "order",
        "encoding",
        "line_ending",
        "required",
        "repeat",
        "binding_record",
        "row_field_casilla_ids",
        "discriminator",
        "requires_positive_casilla_id",
        "fields",
    },
)


_FIELD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "id",
        "offset",
        "length",
        "kind",
        "casilla_id",
        "binding",
        "literal",
        "literal_fact",
        "producer_key",
        "projection_ref",
        "draft_attribute",
        "computed_key",
        "data_type",
        "required",
        "padding",
        "justification",
        "date_format",
        "decimals",
        "signed",
        "sign_position",
        "required_for",
        "required_with",
        "design_type",
        "value_policy",
        "allowed_values",
        "minimum_year",
        "legal_refs",
        "source_refs",
    },
)


#: Field keys added after trees were already attested. Each is serialised and
#: projected only when a field declares it, so a field without the key attests
#: exactly the bytes it did before the key existed, and no stored manifest or
#: loader digest has to be rewritten to admit it. An explicit ``null`` in a
#: stored manifest is therefore non-canonical and refuses on load.
_FIELD_KEYS_PRESENT_ONLY_WHEN_DECLARED: Final[tuple[str, ...]] = (
    "sign_position",
    "required_for",
    "required_with",
    "design_type",
    "literal_fact",
    "minimum_year",
)


_DISCRIMINATOR_KEYS: Final[frozenset[str]] = frozenset({"offset", "length", "requires"})


_DICTIONARY_OVERRIDE_KEYS: Final[frozenset[str]] = frozenset({"field_id", "path", "reason"})


def semantic_map_digest(semantic_map: SemanticMap) -> str:
    """Return a stable digest of reviewed semantic-map meaning, independent of entry order."""
    payload = semantic_map.model_dump(mode="json")
    _require_exact_keys(payload, _SEMANTIC_MAP_KEYS, subject="semantic-map")
    entries = _as_object_list(payload["entries"], subject="semantic-map entries")
    normalised_entries = [_normalise_semantic_map_entry(entry) for entry in entries]
    normalised_entries.sort(key=_semantic_entry_sort_key)
    records = _as_object_list(payload["records"], subject="semantic-map records")
    normalised_records = [_normalise_semantic_map_record(record) for record in records]
    normalised_records.sort(key=_semantic_record_sort_key)
    variable_envelopes = _as_object_list(payload["variable_envelopes"], subject="semantic-map variable envelopes")
    normalised_variable_envelopes = [_normalise_variable_envelope_contract(envelope) for envelope in variable_envelopes]
    normalised_variable_envelopes.sort(
        key=lambda envelope: _as_string(envelope["record_identity"], subject="envelope id"),
    )
    return content_hash_hex(
        {
            "modelo": payload["modelo"],
            "design_epoch": payload["design_epoch"],
            "source_ref": payload["source_ref"],
            "source_sha256": payload["source_sha256"],
            "records": normalised_records,
            "entries": normalised_entries,
            "variable_envelopes": normalised_variable_envelopes,
        },
    )


def normalised_loader_semantics(loaded_layout: ExportLayoutDefinition) -> dict[str, object]:
    """Project loader material into the stable semantics that provenance attests.

    The caller must provide the real loader's validated layout from the freshly
    generated target tree. This function receives no paths and has no legacy
    lookup or fallback surface. Exact-key checks are deliberate: an added loader
    schema field refuses until this projection and its version are reviewed.
    """
    payload = loaded_layout.model_dump(mode="json")
    _require_exact_keys(payload, _LAYOUT_KEYS, subject="loader export layout")
    records = [_normalise_loader_record(item) for item in _as_object_list(payload["records"], subject="loader records")]
    records.sort(key=_loader_record_sort_key)
    overrides = [
        _normalise_dictionary_override(item)
        for item in _as_object_list(payload["dictionary_path_overrides"], subject="loader dictionary overrides")
    ]
    overrides.sort(key=lambda item: _as_string(item["field_id"], subject="loader dictionary override field_id"))
    projected: dict[str, object] = {
        "loader_semantic_schema_version": _LOADER_SEMANTIC_SCHEMA_VERSION,
        "id": payload["id"],
        "format": payload["format"],
        "dictionary_source_ref": payload["dictionary_source_ref"],
        "source_refs": _sorted_strings(payload["source_refs"], subject="loader layout source_refs"),
        "legal_refs": _sorted_strings(payload["legal_refs"], subject="loader layout legal_refs"),
        "records": records,
        "filing_envelope": payload["filing_envelope"],
        "dictionary_path_overrides": overrides,
        "aux_idioma": payload["aux_idioma"],
    }
    # Projected only when declared, so a layout without the member attests
    # byte-identical semantics to the projection that preceded it.
    if payload["auxiliary_envelope_header"] is not None:
        projected["auxiliary_envelope_header"] = payload["auxiliary_envelope_header"]
    return projected


def loader_semantic_digest(loaded_layout: ExportLayoutDefinition) -> str:
    """Return the canonical digest of a real loader-materialised export layout."""
    return content_hash_hex(normalised_loader_semantics(loaded_layout))


def loader_semantic_drift(recorded: Mapping[str, object], current: Mapping[str, object]) -> tuple[str, ...]:
    """Name every projected loader-semantic path whose value differs between two projections.

    A digest can only say that two projections differ. This names where, so a
    refusal points at the key that moved rather than at the whole layout.
    Records and fields are addressed by their ids and dictionary overrides by
    their field id, never by list position, so a reported path is one a reviewer
    can find in the tree. Each entry ends in ``added``, ``removed`` or ``changed``.
    """
    drift: list[str] = []
    _collect_semantic_drift("", recorded, current, drift)
    return tuple(sorted(drift))


def _omit_undeclared_field_keys(field: dict[str, object]) -> dict[str, object]:
    for key in _FIELD_KEYS_PRESENT_ONLY_WHEN_DECLARED:
        if field[key] is None:
            del field[key]
    return field


def _normalise_semantic_map_entry(payload: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(payload, _SEMANTIC_MAP_ENTRY_KEYS, subject="semantic-map entry")
    anchor = _as_object(payload["anchor"], subject="semantic-map anchor")
    _require_exact_keys(anchor, _SEMANTIC_MAP_ANCHOR_KEYS, subject="semantic-map anchor")
    return {
        "anchor": {
            "sheet": anchor["sheet"],
            "source_row": anchor["source_row"],
            "source_cell": anchor["source_cell"],
            "ordinal": anchor["ordinal"],
            "ordinal_absent": anchor["ordinal_absent"],
            "record_identity": anchor["record_identity"],
        },
        "export_field_id": payload["export_field_id"],
        "kind": payload["kind"],
        "casilla_id": payload["casilla_id"],
        "binding": payload["binding"],
        "literal": payload["literal"],
        "producer_key": payload["producer_key"],
        "projection_ref": payload["projection_ref"],
        "draft_attribute": payload["draft_attribute"],
        "computed_key": payload["computed_key"],
        "legal_refs": _sorted_strings(payload["legal_refs"], subject="semantic-map legal_refs"),
        "source_refs": _sorted_strings(payload["source_refs"], subject="semantic-map source_refs"),
        # Digested only when declared, so a map without parts keeps its digest.
        **({"part": payload["part"]} if payload["part"] is not None else {}),
        **({"required_with": payload["required_with"]} if payload["required_with"] is not None else {}),
    }


def _normalise_variable_envelope_contract(payload: Mapping[str, object]) -> dict[str, object]:
    """Normalise the typed envelope contract without re-deriving its meaning."""
    _require_exact_keys(payload, _VARIABLE_ENVELOPE_KEYS, subject="variable envelope")
    prefix_fields = _as_object_list(payload["prefix_fields"], subject="variable envelope prefix fields")
    normalised_prefix_fields: list[dict[str, object]] = []
    for prefix_field in prefix_fields:
        actual_keys = frozenset(prefix_field)
        if actual_keys not in {_ENVELOPE_PREFIX_FIELD_KEYS, _ENVELOPE_LANGUAGE_PREFIX_FIELD_KEYS}:
            raise RegistryValidationError("envelope prefix field schema drift: unsupported key set")
        casilla_id = prefix_field.get("casilla_id")
        if prefix_field["role"] == "language":
            if actual_keys != _ENVELOPE_LANGUAGE_PREFIX_FIELD_KEYS or casilla_id != "decl.idioma":
                raise RegistryValidationError("language envelope prefix requires exact decl.idioma casilla")
        elif casilla_id is not None:
            raise RegistryValidationError("non-language envelope prefix cannot carry a casilla")
        anchor = _as_object(prefix_field["anchor"], subject="envelope prefix anchor")
        _require_exact_keys(anchor, _SEMANTIC_MAP_ANCHOR_KEYS, subject="envelope prefix anchor")
        normalised_prefix_fields.append(
            {
                "role": prefix_field["role"],
                **({"casilla_id": casilla_id} if casilla_id is not None else {}),
                "anchor": {
                    "sheet": anchor["sheet"],
                    "source_row": anchor["source_row"],
                    "source_cell": anchor["source_cell"],
                    "ordinal": anchor["ordinal"],
                    "ordinal_absent": anchor["ordinal_absent"],
                    "record_identity": anchor["record_identity"],
                },
            },
        )
    body_anchor = _as_object(payload["body_anchor"], subject="envelope body anchor")
    closer_anchor = _as_object(payload["closer_anchor"], subject="envelope closer anchor")
    for subject, anchor in (("body", body_anchor), ("closer", closer_anchor)):
        _require_exact_keys(anchor, _SEMANTIC_MAP_ANCHOR_KEYS, subject=f"envelope {subject} anchor")
    total_anchor = _as_object(payload["total_anchor"], subject="envelope total anchor")
    _require_exact_keys(total_anchor, _ENVELOPE_TOTAL_ANCHOR_KEYS, subject="envelope total anchor")
    body_record_ids = _strings_in_order(payload["body_record_ids"], subject="envelope body record ids")
    return {
        "source_ref": payload["source_ref"],
        "source_sha256": payload["source_sha256"],
        "record_identity": payload["record_identity"],
        "prefix_fields": normalised_prefix_fields,
        "body_anchor": {
            "sheet": body_anchor["sheet"],
            "source_row": body_anchor["source_row"],
            "source_cell": body_anchor["source_cell"],
            "ordinal": body_anchor["ordinal"],
            "ordinal_absent": body_anchor["ordinal_absent"],
            "record_identity": body_anchor["record_identity"],
        },
        "body_record_ids": body_record_ids,
        "closer_anchor": {
            "sheet": closer_anchor["sheet"],
            "source_row": closer_anchor["source_row"],
            "source_cell": closer_anchor["source_cell"],
            "ordinal": closer_anchor["ordinal"],
            "ordinal_absent": closer_anchor["ordinal_absent"],
            "record_identity": closer_anchor["record_identity"],
        },
        "total_anchor": {
            "source_row": total_anchor["source_row"],
            "source_cell": total_anchor["source_cell"],
            "label": total_anchor["label"],
            "length": total_anchor["length"],
        },
    }


def _semantic_entry_sort_key(payload: Mapping[str, object]) -> tuple[str, int, str, str, str, str]:
    anchor = _as_object(payload["anchor"], subject="normalised semantic-map anchor")
    source_cell = anchor["source_cell"]
    ordinal = anchor["ordinal"]
    return (
        _as_string(anchor["sheet"], subject="semantic-map anchor sheet"),
        _as_int(anchor["source_row"], subject="semantic-map anchor source_row"),
        "" if source_cell is None else _as_string(source_cell, subject="semantic-map anchor source_cell"),
        "" if ordinal is None else _as_string(ordinal, subject="semantic-map anchor ordinal"),
        _as_string(anchor["record_identity"], subject="semantic-map anchor record_identity"),
        _as_string(payload["export_field_id"], subject="semantic-map export_field_id"),
    )


def _normalise_semantic_map_record(payload: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(payload, _SEMANTIC_MAP_RECORD_KEYS, subject="semantic-map record")
    discriminator = payload["discriminator"]
    normalised_discriminator: dict[str, object] | None = None
    if discriminator is not None:
        discriminator_payload = _as_object(discriminator, subject="semantic-map record discriminator")
        _require_exact_keys(discriminator_payload, _DISCRIMINATOR_KEYS, subject="semantic-map record discriminator")
        normalised_discriminator = {
            "offset": discriminator_payload["offset"],
            "length": discriminator_payload["length"],
            "requires": discriminator_payload["requires"],
        }
    normalised: dict[str, object] = {
        "sheet": _as_string(payload["sheet"], subject="semantic-map record sheet"),
        "record_identity": _as_string(
            payload["record_identity"],
            subject="semantic-map record record_identity",
        ),
        "export_record_id": _as_string(
            payload["export_record_id"],
            subject="semantic-map record export_record_id",
        ),
        "record_type": _as_string(payload["record_type"], subject="semantic-map record record_type"),
        "required": _as_bool(payload["required"], subject="semantic-map record required"),
        "repeat": _as_optional_string(payload["repeat"], subject="semantic-map record repeat"),
    }
    # Adding an optional semantic-map field must not invalidate every existing
    # generated tree whose authored meaning did not use it. A present rule is
    # attested; absence retains the previous canonical representation.
    if normalised_discriminator is not None:
        normalised["discriminator"] = normalised_discriminator
    binding_record = payload["binding_record"]
    if binding_record is not None:
        normalised["binding_record"] = _as_string(binding_record, subject="semantic-map record binding_record")
    positive_casilla = payload["requires_positive_casilla_id"]
    if positive_casilla is not None:
        normalised["requires_positive_casilla_id"] = _as_string(
            positive_casilla, subject="semantic-map record requires_positive_casilla_id"
        )
    row_field_casilla_ids = _as_sorted_string_pairs(
        payload["row_field_casilla_ids"],
        subject="semantic-map record row_field_casilla_ids",
    )
    if row_field_casilla_ids:
        normalised["row_field_casilla_ids"] = row_field_casilla_ids
    return normalised


def _semantic_record_sort_key(payload: Mapping[str, object]) -> tuple[str, str, str, str, str]:
    return (
        _as_string(payload["sheet"], subject="semantic-map record sheet"),
        _as_string(payload["record_identity"], subject="semantic-map record record_identity"),
        _as_string(payload["export_record_id"], subject="semantic-map record export_record_id"),
        _as_string(payload["record_type"], subject="semantic-map record record_type"),
        _as_optional_string(payload["repeat"], subject="semantic-map record repeat") or "",
    )


def _normalise_loader_record(payload: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(payload, _RECORD_KEYS, subject="loader export record")
    fields = [
        _normalise_loader_field(item) for item in _as_object_list(payload["fields"], subject="loader record fields")
    ]
    fields.sort(key=_loader_field_sort_key)
    row_fields = _as_object(payload["row_field_casilla_ids"], subject="loader row-field casilla ids")
    discriminator = payload["discriminator"]
    normalised_discriminator: dict[str, object] | None = None
    if discriminator is not None:
        discriminator_payload = _as_object(discriminator, subject="loader record discriminator")
        _require_exact_keys(discriminator_payload, _DISCRIMINATOR_KEYS, subject="loader record discriminator")
        normalised_discriminator = {
            "offset": discriminator_payload["offset"],
            "length": discriminator_payload["length"],
            "requires": discriminator_payload["requires"],
        }
    return {
        "id": payload["id"],
        "record_type": payload["record_type"],
        "order": payload["order"],
        "encoding": payload["encoding"],
        "line_ending": payload["line_ending"],
        "required": payload["required"],
        "repeat": payload["repeat"],
        "binding_record": payload["binding_record"],
        "row_field_casilla_ids": {key: row_fields[key] for key in sorted(row_fields)},
        "discriminator": normalised_discriminator,
        "requires_positive_casilla_id": payload["requires_positive_casilla_id"],
        "fields": fields,
    }


def _normalise_loader_field(payload: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(payload, _FIELD_KEYS, subject="loader export field")
    normalised: dict[str, object] = {
        "id": payload["id"],
        "offset": payload["offset"],
        "length": payload["length"],
        "kind": payload["kind"],
        "casilla_id": payload["casilla_id"],
        "binding": payload["binding"],
        "literal": payload["literal"],
        "producer_key": payload["producer_key"],
        "projection_ref": payload["projection_ref"],
        "draft_attribute": payload["draft_attribute"],
        "computed_key": payload["computed_key"],
        "data_type": payload["data_type"],
        "required": payload["required"],
        "padding": payload["padding"],
        "justification": payload["justification"],
        "date_format": payload["date_format"],
        "decimals": payload["decimals"],
        "signed": payload["signed"],
        "value_policy": payload["value_policy"],
        "allowed_values": payload["allowed_values"],
        "legal_refs": _sorted_strings(payload["legal_refs"], subject="loader field legal_refs"),
        "source_refs": _sorted_strings(payload["source_refs"], subject="loader field source_refs"),
    }
    for key in _FIELD_KEYS_PRESENT_ONLY_WHEN_DECLARED:
        normalised[key] = payload[key]
    return _omit_undeclared_field_keys(normalised)


#: Projected arrays whose members carry a stable identity, keyed by the member
#: field holding it. Drift inside them is reported against that identity.
_IDENTIFIED_PROJECTION_ARRAYS: Final[Mapping[str, str]] = {
    "records": "id",
    "fields": "id",
    "dictionary_path_overrides": "field_id",
}


def _collect_semantic_drift(path: str, recorded: object, current: object, drift: list[str]) -> None:
    if recorded == current:
        return
    if _collect_mapping_semantic_drift(path, recorded, current, drift):
        return
    identity_key = _IDENTIFIED_PROJECTION_ARRAYS.get(path.rsplit(".", 1)[-1])
    recorded_members = _members_by_identity(recorded, identity_key)
    current_members = _members_by_identity(current, identity_key)
    if recorded_members is None or current_members is None:
        drift.append(f"{path} changed")
        return
    reported_before = len(drift)
    for identity in sorted(recorded_members.keys() | current_members.keys()):
        _collect_identity_member_drift(path, identity, recorded_members, current_members, drift)
    if len(drift) == reported_before:
        # Same members, same values: only their sequence differs, which is
        # still a difference the projection attests.
        drift.append(f"{path} reordered")


def _collect_mapping_semantic_drift(
    path: str,
    recorded: object,
    current: object,
    drift: list[str],
) -> bool:
    recorded_mapping = _mapping_or_none(recorded)
    current_mapping = _mapping_or_none(current)
    if recorded_mapping is None or current_mapping is None:
        return False
    for key in sorted(recorded_mapping.keys() | current_mapping.keys()):
        child = f"{path}.{key}" if path else key
        if key not in current_mapping:
            drift.append(f"{child} removed")
        elif key not in recorded_mapping:
            drift.append(f"{child} added")
        else:
            _collect_semantic_drift(child, recorded_mapping[key], current_mapping[key], drift)
    return True


def _collect_identity_member_drift(
    path: str,
    identity: str,
    recorded_members: Mapping[str, object],
    current_members: Mapping[str, object],
    drift: list[str],
) -> None:
    child = f"{path}[{identity}]"
    if identity not in current_members:
        drift.append(f"{child} removed")
    elif identity not in recorded_members:
        drift.append(f"{child} added")
    else:
        _collect_semantic_drift(child, recorded_members[identity], current_members[identity], drift)


def _mapping_or_none(value: object) -> Mapping[str, object] | None:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else None


def _members_by_identity(value: object, identity_key: str | None) -> dict[str, object] | None:
    """Index an identified projected array, or ``None`` when it cannot be addressed by identity."""
    if identity_key is None or not isinstance(value, list):
        return None
    members: dict[str, object] = {}
    items: list[object] = list(cast(list[object], value))
    for item in items:
        member = _mapping_or_none(item)
        if member is None:
            return None
        identity = member.get(identity_key)
        if not isinstance(identity, str) or identity in members:
            return None
        members[identity] = item
    return members


def _loader_record_sort_key(payload: Mapping[str, object]) -> tuple[int, str]:
    return (
        _as_int(payload["order"], subject="loader record order"),
        _as_string(payload["id"], subject="loader record id"),
    )


def _loader_field_sort_key(payload: Mapping[str, object]) -> tuple[int, str]:
    offset = payload["offset"]
    return (
        -1 if offset is None else _as_int(offset, subject="loader field offset"),
        _as_string(payload["id"], subject="loader field id"),
    )


def _normalise_dictionary_override(payload: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(payload, _DICTIONARY_OVERRIDE_KEYS, subject="loader dictionary override")
    return {
        "field_id": payload["field_id"],
        "path": payload["path"],
        "reason": payload["reason"],
    }


def _require_exact_keys(payload: Mapping[str, object], expected: frozenset[str], *, subject: str) -> None:
    actual = frozenset(payload)
    if actual == expected:
        return
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    raise RegistryValidationError(
        f"{subject} schema drift: missing={missing!r}, unknown={unknown!r}; review and version the normaliser",
    )


def _as_object(value: object, *, subject: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RegistryValidationError(f"{subject} schema drift: expected object")
    raw_mapping = cast(Mapping[object, object], value)
    result: dict[str, object] = {}
    for raw_key, raw_value in raw_mapping.items():
        if not isinstance(raw_key, str):
            raise RegistryValidationError(f"{subject} schema drift: expected string object keys")
        result[raw_key] = raw_value
    return result


def _as_sorted_string_pairs(value: object, *, subject: str) -> list[list[str]]:
    """Project a carried mapping (dumped as two-element pairs) in a stable order."""
    if not isinstance(value, list):
        raise RegistryValidationError(f"{subject} schema drift: expected pair array")
    pairs: list[list[str]] = []
    items: list[object] = list(value)
    for item in items:
        if not isinstance(item, list):
            raise RegistryValidationError(f"{subject} schema drift: expected two-element pairs")
        members: list[object] = list(item)
        if len(members) != 2:
            raise RegistryValidationError(f"{subject} schema drift: expected two-element pairs")
        pairs.append([_as_string(members[0], subject=subject), _as_string(members[1], subject=subject)])
    return sorted(pairs)


def _as_object_list(value: object, *, subject: str) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        raise RegistryValidationError(f"{subject} schema drift: expected array")
    items: list[object] = list(value)
    return [_as_object(item, subject=subject) for item in items]


def _sorted_strings(value: object, *, subject: str) -> list[str]:
    if not isinstance(value, list):
        raise RegistryValidationError(f"{subject} schema drift: expected string array")
    items: list[object] = list(value)
    strings: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise RegistryValidationError(f"{subject} schema drift: expected string array")
        strings.append(item)
    return sorted(strings)


def _strings_in_order(value: object, *, subject: str) -> list[str]:
    """Validate a string array while retaining semantic sequence order."""
    if not isinstance(value, list):
        raise RegistryValidationError(f"{subject} schema drift: expected string array")
    items: list[object] = list(value)
    strings: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise RegistryValidationError(f"{subject} schema drift: expected string array")
        strings.append(item)
    return strings


def _as_string(value: object, *, subject: str) -> str:
    if not isinstance(value, str):
        raise RegistryValidationError(f"{subject} schema drift: expected string")
    return value


def _as_optional_string(value: object, *, subject: str) -> str | None:
    if value is None:
        return None
    return _as_string(value, subject=subject)


def _as_bool(value: object, *, subject: str) -> bool:
    if type(value) is not bool:
        raise RegistryValidationError(f"{subject} schema drift: expected boolean")
    return value


def _as_int(value: object, *, subject: str) -> int:
    if not isinstance(value, int):
        raise RegistryValidationError(f"{subject} schema drift: expected integer")
    return value
