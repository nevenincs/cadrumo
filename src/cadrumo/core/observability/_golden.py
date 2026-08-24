"""Canonicalise / mask / compare primitive for golden-output determinism.

One substrate, two consumers: the observability
:func:`core.observability.replay_run` envelope-assertion tier and
the harness operator golden gate both call this primitive; neither
re-implements capture or compare.

The captured payload is the verbatim emitted
:class:`~core.json_contract.SchemaEnvelope` document. On load it is
re-validated against its caller-supplied authored result schema by
:func:`validate_captured_envelope` so the captured payload is a typed
envelope around a registered :class:`OutputSchema`, never a
``dict[str, Any]`` bag. Comparison
(:func:`assert_golden_match`) is over the FULL envelope (shared spine
plus ``result``), key-sorted and canonicalised, after a declared narrow
field mask that hides only the residual non-deterministic surrogate
keys.

Masking honesty
---------------
:data:`GOLDEN_MASK_FIELDS` is a declared, narrow allowlist — the two
opaque surrogate keys that still flap once the clock seam
(:func:`core.time.frozen_clock`) is frozen and ``profile_id`` is
injected: ``snapshot_id`` (its ``profile_id`` prefix and timestamp are
deterministic, only the trailing ``uuid4().hex`` flaps) and the
observability ``run_id`` (a minted ``uuid4`` tail). A mask broad enough
to hide a real regression voids the gate, so the mask is kept minimal
and is proven minimal by an anti-tautology test that asserts, for a
scenario captured twice under a frozen clock and injected identity, the
set of differing JSON paths reduces to exactly these masked fields —
:func:`differing_field_names` and :func:`differing_paths` exist for that
proof.

One command also has a path-specific residual: the profile-delete result
fingerprint hashes the encrypted bytes it has just destroyed, whose encryption
material is freshly minted for every hermetic profile.  Only
``config.profile.delete``'s ``result.fingerprint.digest`` is masked.  A generic
``digest`` leaf, the rest of that fingerprint, and the same path on any other
command remain assertable.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from ..json_contract import (
    OutputSchema,
    RegisteredSchema,
    SchemaEnvelope,
)
from ._errors import GoldenCaptureError, GoldenReplayMismatchError

#: The sentinel a masked leaf is replaced with before comparison.
MASK_SENTINEL = "<masked>"

#: Declared, narrow allowlist of leaf field names whose values are opaque,
#: non-assertable surrogate keys carrying an unseedable ``uuid4`` tail. These
#: are the ONLY residual non-deterministic leaves once
#: :func:`core.time.frozen_clock` is frozen and ``profile_id`` is injected.
#: Widening this set is a standing honesty hazard; every addition must be
#: proven minimal by the anti-tautology gate.
GOLDEN_MASK_FIELDS: frozenset[str] = frozenset({"snapshot_id", "run_id"})

#: Exact ``(command, dotted result path)`` leaves whose values are irreducibly
#: nondeterministic.  This is central policy, not a caller/sequence extension.
GOLDEN_MASK_PATHS: frozenset[tuple[str, str]] = frozenset(
    {("config.profile.delete", "result.fingerprint.digest")},
)


def canonicalise(document: Mapping[str, object]) -> str:
    """Return the UTF-8, key-sorted, fixed-indent canonical form of ``document``.

    The canonical form is the byte string two captures are compared on.
    Key-sorting makes the comparison insensitive to emit-time key order;
    the fixed indent keeps a mismatch diff human-readable.
    """
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        default=str,
    )


def mask_document(
    document: Mapping[str, object],
    *,
    fields: frozenset[str] = GOLDEN_MASK_FIELDS,
) -> dict[str, object]:
    """Return a deep copy of ``document`` with masked leaves replaced by a sentinel.

    Any mapping value stored under a key in ``fields`` — at any depth —
    is replaced by :data:`MASK_SENTINEL`. The rest of the document is
    copied verbatim, so a real output difference outside the masked
    fields is preserved for comparison.

    Args:
        document: The envelope document to mask.
        fields: Leaf field names to mask; defaults to
            :data:`GOLDEN_MASK_FIELDS`.

    Returns:
        A new dict with the masked leaves replaced.
    """
    masked = {
        key: (MASK_SENTINEL if key in fields else _mask_value(item, fields))
        for key, item in document.items()
    }
    command = document.get("command")
    if isinstance(command, str):
        for masked_command, path in GOLDEN_MASK_PATHS:
            if command == masked_command:
                _mask_existing_path(masked, path)
    return masked


def _mask_existing_path(document: dict[str, object], path: str) -> None:
    """Mask ``path`` only when every mapping segment already exists."""
    segments = path.split(".")
    node: object = document
    for segment in segments[:-1]:
        if not isinstance(node, dict) or segment not in node:
            return
        node = node[segment]
    leaf = segments[-1]
    if isinstance(node, dict) and leaf in node:
        node[leaf] = MASK_SENTINEL


def _mask_value(value: object, fields: frozenset[str]) -> object:
    """Recursively copy ``value``, masking mapping entries whose key is in ``fields``."""
    if isinstance(value, Mapping):
        return {key: (MASK_SENTINEL if key in fields else _mask_value(item, fields)) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_mask_value(item, fields) for item in value]
    return value


def flatten_paths(document: Mapping[str, object]) -> dict[str, object]:
    """Return a flat ``{dotted-path: leaf-value}`` view of ``document``.

    List elements are addressed with ``[index]`` segments (e.g.
    ``notices[0].code``). Leaves are scalars; empty containers are
    recorded as their own leaf so a container that gains its first element
    still surfaces as a differing path.
    """
    flat: dict[str, object] = {}
    _flatten_into(document, "", flat)
    return flat


def _flatten_into(value: object, prefix: str, out: dict[str, object]) -> None:
    """Populate ``out`` with the flattened ``path -> leaf`` mapping for ``value``."""
    if isinstance(value, Mapping):
        if not value:
            out[prefix] = {}
            return
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            _flatten_into(item, child, out)
        return
    if isinstance(value, list | tuple):
        if not value:
            out[prefix] = []
            return
        for index, item in enumerate(value):
            _flatten_into(item, f"{prefix}[{index}]", out)
        return
    out[prefix] = value


def differing_paths(
    left: Mapping[str, object],
    right: Mapping[str, object],
) -> frozenset[str]:
    """Return the set of dotted JSON paths whose leaves differ between two documents.

    A path is included when it is present in only one document, or when
    it is present in both with unequal leaf values. This is the raw,
    UNMASKED diff used by the anti-tautology proof to show the mask is
    exactly the residual non-deterministic field set.
    """
    left_flat = flatten_paths(left)
    right_flat = flatten_paths(right)
    paths = set(left_flat) | set(right_flat)
    return frozenset(path for path in paths if left_flat.get(path) != right_flat.get(path))


def differing_field_names(
    left: Mapping[str, object],
    right: Mapping[str, object],
) -> frozenset[str]:
    """Return the leaf field names of the paths that differ between two documents.

    The leaf field name of ``result.snapshot_id`` is ``snapshot_id`` and
    of ``notices[0].code`` is ``code``. Used by the anti-tautology proof
    to assert the residual diff reduces to exactly
    :data:`GOLDEN_MASK_FIELDS`.
    """
    return frozenset(_leaf_field_name(path) for path in differing_paths(left, right))


def _leaf_field_name(path: str) -> str:
    """Return the trailing field-name segment of a dotted/bracketed JSON path."""
    tail = path.rsplit(".", 1)[-1]
    # Strip any trailing ``[index]`` list-addressing segments.
    return tail.split("[", 1)[0]


def assert_golden_match(
    expected: Mapping[str, object],
    actual: Mapping[str, object],
    *,
    fields: frozenset[str] = GOLDEN_MASK_FIELDS,
) -> None:
    """Assert two envelope documents are byte-identical after masking, else raise.

    Both documents are masked with ``fields`` and canonicalised; if the
    canonical byte strings differ, a :class:`GoldenReplayMismatchError`
    is raised carrying the differing masked paths.

    Args:
        expected: The captured golden expectation.
        actual: The replayed / re-emitted envelope document.
        fields: Leaf field names to mask; defaults to
            :data:`GOLDEN_MASK_FIELDS`.

    Raises:
        GoldenReplayMismatchError: When the masked canonical forms differ.
    """
    masked_expected = mask_document(expected, fields=fields)
    masked_actual = mask_document(actual, fields=fields)
    if canonicalise(masked_expected) == canonicalise(masked_actual):
        return
    diff = tuple(sorted(differing_paths(masked_expected, masked_actual)))
    detail = (
        "replayed envelope diverged from its captured golden expectation "
        f"at {len(diff)} path(s): {', '.join(diff) or '<whole-document>'}"
    )
    raise GoldenReplayMismatchError(differing_paths=diff, detail=detail)


def validate_captured_envelope(
    document: Mapping[str, object],
    *,
    schema: RegisteredSchema,
) -> SchemaEnvelope[OutputSchema]:
    """Re-validate a captured envelope document through its registered schema.

    Specialises :class:`~core.json_contract.SchemaEnvelope` over the
    caller-supplied authored result schema and strictly validates the document. The
    return value is a typed envelope, never a ``dict[str, Any]`` bag —
    this is the typed boundary the substrate keeps captured payloads
    behind.

    Args:
        document: The emitted envelope document to re-validate.
        schema: The caller-owned strict result schema for the captured command.

    Returns:
        The strictly-validated :class:`SchemaEnvelope` whose result is the
        registered :class:`OutputSchema` for the captured command.

    Raises:
        GoldenCaptureError: When the document has no ``command`` string,
            the command is unregistered, or the payload fails strict
            validation against the registered schema.
    """
    command = document.get("command")
    if not isinstance(command, str) or not command:
        raise GoldenCaptureError(
            f"captured envelope has no usable 'command' field: {command!r}",
        )
    # Parametrise the generic envelope over the runtime-resolved result
    # schema. ``__class_getitem__`` is the runtime hook behind ``[...]``;
    # calling it explicitly keeps the dynamic parametrisation out of a
    # static type-expression position (which no type checker can express).
    # CAST-RATIONALE-GOLDEN-ENVELOPE-PARAMETRISE: `__class_getitem__` returns
    # `types.GenericAlias`, not the runtime-resolved parametrised class; the
    # cast restores the declared generic type for the constructor call below.
    envelope_model = cast(
        "type[SchemaEnvelope[OutputSchema]]",
        SchemaEnvelope.__class_getitem__(schema),
    )
    # The captured document is JSON primitives (status as a string, any
    # datetime as an ISO string). Re-validate through JSON mode so strict
    # ``StrEnum`` / ``datetime`` fields coerce from their JSON forms while
    # every other field stays strictly validated.
    try:
        return envelope_model.model_validate_json(json.dumps(document, default=str))
    except Exception as exc:  # re-raised as a registered golden error
        raise GoldenCaptureError(
            f"captured envelope for command {command!r} failed strict "
            f"re-validation against its registered schema: {exc}",
        ) from exc


__all__ = [
    "GOLDEN_MASK_FIELDS",
    "MASK_SENTINEL",
    "assert_golden_match",
    "canonicalise",
    "differing_field_names",
    "differing_paths",
    "flatten_paths",
    "mask_document",
    "validate_captured_envelope",
]
