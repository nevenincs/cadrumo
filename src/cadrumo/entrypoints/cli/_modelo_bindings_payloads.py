"""Typed ``--json`` payload schemas for the modelo ``bindings`` sub-app.

Extracted from :mod:`~entrypoints.cli._modelo_payloads` to keep that
module under its size budget (`aeat-architecture-boundaries`,
`registry-resolver-family-extraction`), following the split pattern already
established by :mod:`~entrypoints.cli._modelo_aux_payloads`,
:mod:`~entrypoints.cli._modelo_revision_payload_parts`, and
:mod:`~entrypoints.cli._modelo_work_revision_payloads`. Covers the
``modelo bindings list`` and ``modelo bindings resolve`` (preview) command
envelopes. Every class declared here is a strict
:class:`OutputSchema` subclass registered with
:func:`register_schema` for the bindings-list and
bindings-resolve command JSON-contract surface.

Per `binding-values-carry-provenance`, every row here carries the binding's
regulatory grounding (``legal_refs`` / ``source_refs``) at parity with the
casilla-side payloads (``CasillaRowPayload`` in
:mod:`~entrypoints.cli._modelo_payloads`).

See Also:
    :mod:`~entrypoints.cli._modelo_payloads`
        Re-imports every class from this module so existing
        ``from ._modelo_payloads import BindingListRowPayload`` (etc.) call
        sites keep resolving unchanged.
"""

from __future__ import annotations

from pydantic import Field

from ...domain.calculations.registry import BindingId, LegalRefId, RelationId, SourceRefId
from ._schemas import OutputSchema, register_schema


class BindingEncodedOptionPayload(OutputSchema):
    """One accepted decimal encoding of a boolean-typed decimal-channel binding.

    Projection of
    :class:`~domain.calculations.registry.BooleanBindingEncodedValue`.
    ``encoded_value`` is the decimal the operator types on ``--binding``,
    ``boolean_meaning`` is the affirmative/negative sense it carries, and
    ``registry_value`` is the underlying casilla token the boolean maps to. The
    mapping is derived from the binding's boolean selector, so the listing surface
    can teach the decimal-to-meaning encoding before a calculation is attempted.
    """

    encoded_value: str
    boolean_meaning: bool
    registry_value: str


class BindingListRowPayload(OutputSchema):
    """One binding row in the bindings list output.

    Carries the binding's regulatory grounding (``legal_refs`` /
    ``source_refs``, sourced from the registry binding definition) at
    parity with the casilla half (``CasillaRowPayload``). ``source`` renders
    the typed :class:`~core.BindingSourceKind` value as a string.
    """

    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    binding_id: BindingId
    source: str
    readiness: str
    typed_enum: str | None
    input_channel: str
    borrador_capable: bool
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    relation_inputs: tuple[RelationId, ...] = ()
    """Registry relation ids that feed this binding's value.

    Non-empty only for ``source = "relation_prefill"`` bindings, where the
    operator supplies each value through ``--relation RELATION_ID=VALUE``
    rather than ``--binding``. Derived from the resolved revision's
    relations (:class:`~domain.calculations.registry.RelationDefinition`
    ``target_binding``), so a relation-fed binding's source is discoverable
    in this listing before a calculation is attempted, for any modelo.
    """
    encoded_options: tuple[BindingEncodedOptionPayload, ...] = ()
    """Accepted decimal encodings for a boolean-typed ``input_channel=decimal`` binding.

    Non-empty only for a boolean-flag binding the registry consumes as a numeric
    ``1`` / ``0`` operand (the Modelo 100 estimación-directa modality flag). Each
    entry pairs the decimal the operator must type on ``--binding`` with its
    boolean meaning and the underlying casilla token, so the mapping is visible in
    the listing before a calculation is attempted.
    """


@register_schema("modelo.bindings.list")
class ModeloBindingsListResult(OutputSchema):
    """Bindings list result."""

    operation: str = "modelo.bindings.list"
    modelo_filter: str | None
    year_filter: int | None
    period_filter: str | None
    missing_filter: bool
    binding_count: int
    bindings: tuple[BindingListRowPayload, ...]


class BindingPreviewRowPayload(OutputSchema):
    """One binding preview row with optional override value.

    Carries the binding's regulatory grounding (``legal_refs`` /
    ``source_refs``, sourced from the registry binding definition) at
    parity with the casilla half.
    """

    binding_id: BindingId
    source: str
    readiness: str
    typed_enum: str | None
    override: str | None
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    relation_inputs: tuple[RelationId, ...] = ()
    """Registry relation ids that feed this binding (see ``BindingListRowPayload``)."""
    encoded_options: tuple[BindingEncodedOptionPayload, ...] = ()
    """Accepted decimal encodings for a boolean flag binding (see ``BindingListRowPayload``)."""


@register_schema("modelo.bindings.resolve")
class ModeloBindingsPreviewResult(OutputSchema):
    """Bindings resolve result."""

    operation: str = "modelo.bindings.resolve"
    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    override_count: int
    binding_count: int
    bindings: list[BindingPreviewRowPayload]
