"""Typed ``--json`` payload schemas for the modelo ``bindings`` sub-app.

Extracted from :mod:`~entrypoints.cli._modelo_payloads` to keep that
module under its size budget (`aeat-architecture-boundaries`,
`aeat-architecture-boundaries`), following the split pattern already
established by :mod:`~entrypoints.cli.modelo_aux_payloads`,
:mod:`~entrypoints.cli._modelo_revision_payload_parts`, and
:mod:`~entrypoints.cli._modelo_work_revision_payloads`. Covers the
``modelo bindings list`` and ``modelo bindings resolve`` (preview) command
envelopes. Every class declared here is a strict
:class:`OutputSchema` subclass referenced by
production-authored CommandSpec as deferred public schema targets for the bindings-list and
bindings-resolve command JSON-contract surface.

Per `aeat-registry-bindings`, every row here carries the binding's
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

from ...core.json_contract import OutputSchema
from ...domain.calculations.registry.ids import BindingId, RelationId
from ...domain.calculations.registry.schema_base import LegalRefs, SourceRefs


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


class BindingGroundingPayload(OutputSchema):
    """Identity and regulatory grounding shared by every binding row payload.

    Per `aeat-registry-bindings`, an operator-facing binding value
    carries its ``legal_refs`` / ``source_refs`` and its typed source kind at
    parity with the casilla half. The ``bindings list`` and ``bindings
    resolve`` (preview) surfaces describe the *same* binding, so they declare
    that grounding once here rather than twice: a constraint relaxed for one
    surface would otherwise leave the other silently covered, and operator
    list JSON could carry provenance the preview JSON refuses.

    Subclasses add only the fields that genuinely differ between the two
    surfaces -- listing context and input channel for the list row, the
    resolved override value for the preview row.
    """

    binding_id: BindingId
    source: str
    """The typed :class:`~core.BindingSourceKind` value rendered as a string."""
    readiness: str
    typed_enum: str | None
    legal_refs: LegalRefs
    source_refs: SourceRefs
    relation_inputs: tuple[RelationId, ...] = ()
    """Registry relation ids that feed this binding's value.

    Non-empty only for ``source = "relation_prefill"`` bindings, where the
    operator supplies each value through ``--relation RELATION_ID=VALUE``
    rather than ``--binding``. Derived from the resolved revision's
    relations (:class:`~domain.calculations.registry.RelationDefinition`
    ``target_binding``), so a relation-fed binding's source is discoverable
    before a calculation is attempted, for any modelo.
    """
    encoded_options: tuple[BindingEncodedOptionPayload, ...] = ()
    """Accepted decimal encodings for a boolean-typed ``input_channel=decimal`` binding.

    Non-empty only for a boolean-flag binding the registry consumes as a numeric
    ``1`` / ``0`` operand (the Modelo 100 estimación-directa modality flag). Each
    entry pairs the decimal the operator must type on ``--binding`` with its
    boolean meaning and the underlying casilla token, so the mapping is visible
    before a calculation is attempted.
    """


class BindingListRowPayload(BindingGroundingPayload):
    """One binding row in the bindings list output.

    Adds the listing context (which modelo/revision/period the row was listed
    for), the input channel, and borrador capability to the shared
    :class:`BindingGroundingPayload` identity and grounding.
    """

    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    input_channel: str
    borrador_capable: bool


class ModeloBindingsListResult(OutputSchema):
    """Bindings list result."""

    operation: str = "modelo.bindings.list"
    modelo_filter: str | None
    year_filter: int | None
    period_filter: str | None
    missing_filter: bool
    binding_count: int
    bindings: tuple[BindingListRowPayload, ...]


class BindingPreviewRowPayload(BindingGroundingPayload):
    """One binding preview row with optional override value.

    Adds the resolved override to the shared :class:`BindingGroundingPayload`
    identity and grounding.
    """

    override: str | None


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
