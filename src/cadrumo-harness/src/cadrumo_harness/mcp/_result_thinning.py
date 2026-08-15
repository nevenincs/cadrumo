"""Result thinning: bulk result arrays ride as ``resource_link`` URIs.

Structured output double-emits (text ``content`` plus ``structuredContent`` -
roughly 2x tokens by construction), so a verb whose result inlines a large bulk
array - the calculation observation provenance, the evidence-record rows -
inflates every call. ``structuredContent`` stays the typed SUMMARY a client
acts on, while the bulk collections move to ``resource_link`` URIs a
resources-capable client fetches on demand, resolved from persisted state by
the resource read handlers.

This module is the SINGLE declared authority for that split, keyed by command
key, so the three consumers cannot drift:

* the server thins the runtime envelope (:func:`thin_envelope`) - it pops the
  declared bulk arrays from ``envelope["result"]`` and returns the
  :class:`ResourceLinkRef` set to emit as ``resource_link`` content items;
* the tool descriptor thins its declared output schema in lock-step
  (:func:`thin_output_schema`) - the same properties leave the schema, so the
  thinned ``structuredContent`` still validates and the static size-budget gate
  (``test_result_size_budget.py``) measures the thinned shape;
* the resource read handler resolves a link back to the real persisted rows via
  the declared resolver verb (:data:`BULK_RESOLUTION`), re-run as a supervised
  subprocess so it carries the active bucket session the server process lacks.

Like ``_resources`` / ``_tools`` this is SDK-independent pure functions over typed
models; ``_server`` adapts :class:`ResourceLinkRef` onto the SDK ``ResourceLink``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from ._resources import HarnessResourceKind, resource_uri

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

#: The MIME type a thinned bulk resource resolves to - a JSON array of the
#: persisted rows (the same typed payload the inline array carried).
_BULK_MIME = "application/json"


class ThinnedArray(BaseModel):
    """One declared bulk array a verb moves out of ``structuredContent``.

    ``result_key`` is the array's key under ``envelope["result"]``;
    ``resource_kind`` selects the canonical Cadrumo resource URI kind; ``uri_id_key``
    is the sibling ``result`` field whose value identifies the persisted record the
    read handler resolves (a calculation-revision id, a bucket id). Thinning pops
    ``result_key`` and replaces it with a ``{result_key}_resource`` URI plus a
    ``{result_key}_count`` marker, so a client acting on the summary alone still
    sees how many rows are one fetch away.
    """

    model_config = _STRICT_FROZEN

    result_key: str = Field(min_length=1)
    resource_kind: HarnessResourceKind
    uri_id_key: str = Field(min_length=1)

    @property
    def ref_key(self) -> str:
        """The summary marker key carrying the resource URI (``<result_key>_resource``)."""
        return f"{self.result_key}_resource"

    @property
    def count_key(self) -> str:
        """The summary marker key carrying the moved-row count (``<result_key>_count``)."""
        return f"{self.result_key}_count"


class BulkResolution(BaseModel):
    """How a bulk resource kind resolves back to its persisted rows.

    ``resolver_command_key`` is the read verb whose result field
    (``result_field``) IS the bulk array; the resource read handler re-runs that
    verb as a supervised subprocess (carrying the active bucket session) and
    returns its rows. ``id_arg`` names the positional argument that scopes the
    read to the URI's record (``None`` when the verb reads the active bucket and
    the URI id is only cross-checked against the result).
    """

    model_config = _STRICT_FROZEN

    resolver_command_key: str = Field(min_length=1)
    result_field: str = Field(min_length=1)
    id_arg: str | None = None


class ResourceLinkRef(BaseModel):
    """An SDK-independent ``resource_link`` to emit for one thinned bulk array."""

    model_config = _STRICT_FROZEN

    uri: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    count: int = Field(ge=0)
    mime_type: str = _BULK_MIME


#: The declared thinning map: command key -> the bulk arrays it moves to links.
#: One canonical mechanism per bulk class: calculation observations ride
#: on the ``observations`` array of both the calculate result and the dedicated
#: observations read verb; evidence rows ride on the evidence-list ``rows`` array.
THINNED_VERBS: dict[str, tuple[ThinnedArray, ...]] = {
    "modelo.work.calculate": (
        ThinnedArray(
            result_key="observations",
            resource_kind=HarnessResourceKind.OBSERVATIONS,
            uri_id_key="calculation_revision_id",
        ),
    ),
    "modelo.work.observations": (
        ThinnedArray(
            result_key="observations",
            resource_kind=HarnessResourceKind.OBSERVATIONS,
            uri_id_key="calculation_revision_id",
        ),
    ),
    "modelo.work.revision": (
        ThinnedArray(
            result_key="observations",
            resource_kind=HarnessResourceKind.OBSERVATIONS,
            uri_id_key="calculation_revision_id",
        ),
    ),
    "ledger.evidence.list": (
        ThinnedArray(
            result_key="rows",
            resource_kind=HarnessResourceKind.EVIDENCE,
            uri_id_key="bucket_id",
        ),
    ),
}

#: The declared resolution map: bucket resource kind -> the read verb that
#: reconstitutes its rows from persisted state. The resource read handler re-runs
#: the verb as a subprocess so the resolution carries the active bucket session.
BULK_RESOLUTION: dict[HarnessResourceKind, BulkResolution] = {
    HarnessResourceKind.OBSERVATIONS: BulkResolution(
        resolver_command_key="modelo.work.observations",
        result_field="observations",
        id_arg="calculation_revision_id",
    ),
    HarnessResourceKind.EVIDENCE: BulkResolution(
        resolver_command_key="ledger.evidence.list",
        result_field="rows",
        id_arg=None,
    ),
}


def thinned_arrays_for(command_key: str) -> tuple[ThinnedArray, ...]:
    """Return the declared bulk arrays a command thins, or an empty tuple."""
    return THINNED_VERBS.get(command_key, ())


def thin_envelope(
    command_key: str,
    envelope: Mapping[str, object],
) -> tuple[dict[str, object], tuple[ResourceLinkRef, ...]]:
    """Thin one command's runtime envelope: pop bulk arrays, return summary + links.

    For each declared bulk array present as a non-empty list under
    ``envelope["result"]`` whose ``uri_id_key`` resolves to a non-empty string,
    the array is removed and replaced by a ``<key>_resource`` URI and a
    ``<key>_count`` marker; a :class:`ResourceLinkRef` is returned for the server
    to emit as a ``resource_link`` content item. An array that is absent, empty,
    or whose id is unresolvable is left inline (nothing to thin), so an error
    envelope or a zero-row result is untouched.

    Returns:
        The (possibly unchanged) envelope and the tuple of links to emit.
    """
    specs = thinned_arrays_for(command_key)
    if not specs:
        return dict(envelope), ()
    result = envelope.get("result")
    if not isinstance(result, Mapping):
        return dict(envelope), ()
    new_result = dict(result)
    links: list[ResourceLinkRef] = []
    for spec in specs:
        array = new_result.get(spec.result_key)
        identity = new_result.get(spec.uri_id_key)
        if not isinstance(array, list) or not array or not isinstance(identity, str) or not identity:
            continue
        uri = resource_uri(spec.resource_kind, identity)
        del new_result[spec.result_key]
        new_result[spec.ref_key] = uri
        new_result[spec.count_key] = len(array)
        links.append(
            ResourceLinkRef(
                uri=uri,
                name=f"{spec.resource_kind.value}:{identity}",
                description=f"{len(array)} {spec.result_key} rows for {spec.resource_kind.value} {identity}",
                count=len(array),
            ),
        )
    if not links:
        return dict(envelope), ()
    new_envelope = dict(envelope)
    new_envelope["result"] = new_result
    return new_envelope, tuple(links)


def thin_output_schema(command_key: str, schema: dict[str, object]) -> dict[str, object]:
    """Thin a command's declared output schema in lock-step with :func:`thin_envelope`.

    The output schema is the command's result-model JSON Schema. A thinned verb
    advertises two disjoint shapes: a zero-row result keeps its bulk array inline
    as ``[]``; a non-empty result drops the array and carries the two summary
    markers (``<key>_resource`` string, ``<key>_count`` positive integer). The
    array's ITEM schema is dropped either way, because no item can occur in
    either shape - that is what lets :func:`_prune_orphan_defs` retire the row
    payload's definitions, and it is where thinning's size saving comes from.

    The two shapes are expressed as a ``oneOf`` over only the fields that
    DIFFER - which of the array and the markers is required, and which is
    forbidden - above one shared property set. Duplicating the whole property
    body into each branch instead (the previous shape) cost more than pruning
    the row payload saved whenever the pruned definitions were still reachable
    from another property, so thinning could ENLARGE a schema and silently
    worsen the position of any verb that reached for it to get under the
    output-schema size budget.

    Factoring also fixes a latent hole: a result model that does not set
    ``additionalProperties: false`` used to have both branches accept a linked
    payload, so ``oneOf``'s exactly-one rule rejected the very shape the server
    emits. Forbidding the other shape explicitly, rather than relying on
    ``additionalProperties``, makes the branches disjoint for every model.

    Returns:
        A thinned copy of the schema, or the input unchanged for a non-thinned verb.
    """
    specs = thinned_arrays_for(command_key)
    if not specs:
        return schema
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return schema
    thinned_keys = [spec.result_key for spec in specs]
    marker_keys = [key for spec in specs for key in (spec.ref_key, spec.count_key)]
    required = schema.get("required")
    original_required = list(required) if isinstance(required, list) else []

    shared_properties = dict(properties)
    for spec in specs:
        if spec.result_key in shared_properties:
            shared_properties[spec.result_key] = {"type": "array", "maxItems": 0}
        shared_properties[spec.ref_key] = {
            "type": "string",
            "minLength": 1,
            "description": f"Resource URI resolving the full {spec.result_key} rows (result thinning).",
        }
        shared_properties[spec.count_key] = {
            "type": "integer",
            "minimum": 1,
            "description": f"Number of {spec.result_key} rows available at the resource URI.",
        }

    # ``False`` as a property schema matches no instance, so naming a key there
    # forbids it outright -- the branch discriminator, independent of whether the
    # model closes itself with ``additionalProperties``.
    inline_branch: dict[str, object] = {
        "required": [name for name in original_required if name in set(thinned_keys)],
        "properties": dict.fromkeys(marker_keys, False),
    }
    linked_branch: dict[str, object] = {
        "required": list(marker_keys),
        "properties": dict.fromkeys(thinned_keys, False),
    }

    thinned = dict(schema)
    thinned["properties"] = shared_properties
    thinned["required"] = [name for name in original_required if name not in set(thinned_keys)]
    thinned["oneOf"] = [inline_branch, linked_branch]
    return _prune_orphan_defs(thinned)


def _prune_orphan_defs(schema: dict[str, object]) -> dict[str, object]:
    """Drop ``$defs`` entries no longer referenced after a property was thinned.

    Removing a bulk-array property can orphan the ``$defs`` model it referenced
    (e.g. ``ObservationPayload``); an orphaned definition is dead weight the
    static size-budget gate would still count. This iterates to a fixpoint - a
    def may reference another def - removing only definitions whose
    ``#/$defs/<name>`` anchor appears nowhere else in the schema, so a shared
    definition is always kept.

    Returns:
        The schema with orphaned definitions removed (or unchanged when it has none).
    """
    defs = schema.get("$defs")
    if not isinstance(defs, Mapping) or not defs:
        return schema
    remaining = dict(defs)
    while True:
        referenced = _reachable_def_names(schema, remaining)
        if referenced == set(remaining):
            break
        remaining = {name: value for name, value in remaining.items() if name in referenced}
    return _schema_with_defs(schema, remaining)


def _reachable_def_names(schema: dict[str, object], remaining: dict[str, object]) -> set[str]:
    """Return the ``$defs`` names still reachable from the schema body (mark phase).

    A name is reachable when its ``#/$defs/<name>`` anchor appears in the non-``$defs``
    body, or, transitively, in a def that is itself reachable — a kept def may
    reference another def.
    """
    body = dict(schema)
    body["$defs"] = remaining
    serialized = json.dumps({key: value for key, value in body.items() if key != "$defs"})
    referenced = {name for name in remaining if f'"#/$defs/{name}"' in serialized}
    frontier = set(referenced)
    while frontier:
        name = frontier.pop()
        payload = json.dumps(remaining.get(name, {}))
        for candidate in remaining:
            if candidate not in referenced and f'"#/$defs/{candidate}"' in payload:
                referenced.add(candidate)
                frontier.add(candidate)
    return referenced


def _schema_with_defs(schema: dict[str, object], remaining: dict[str, object]) -> dict[str, object]:
    """Return ``schema`` carrying the surviving ``$defs`` (sweep phase), or dropping it when empty."""
    pruned = dict(schema)
    if remaining:
        pruned["$defs"] = remaining
    else:
        pruned.pop("$defs", None)
    return pruned


__all__ = [
    "BULK_RESOLUTION",
    "THINNED_VERBS",
    "BulkResolution",
    "ResourceLinkRef",
    "ThinnedArray",
    "thin_envelope",
    "thin_output_schema",
    "thinned_arrays_for",
]
