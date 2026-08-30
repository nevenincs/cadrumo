"""Focused unit tests for the pure helpers in _export.

`_export` resolves export layouts (fixed-width BOE-record fields) from
the registry. The public ``resolve_export_layout`` surface is covered
indirectly through the per-modelo registry tests (Modelo 100, 349,
record-design suite), but the small pure helpers underneath had no
direct unit-test coverage. A regression in (for example) interval-
overlap detection or numeric-padding dispatch would silently corrupt
every emitted export payload.

Tests here are structural / contract assertions on the helpers, not
calculation tautologies.
"""

from __future__ import annotations

import tomllib
from typing import Any

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingSourceKind
from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.resources import bundled_path
from ...export_field_kind import CasillaFieldKind
from ..binding_selector_utils import (
    BindingExportDataType,
    BindingFixedExportSelector,
    BindingRowExportSelector,
    binding_export_selector,
)
from ..errors import RegistryValidationError
from ..export import (
    _justification_for_binding_data_type,
    _padding_for_binding_data_type,
    export_fields_overlap,
)
from ..export_semantics import ExportDraftAttribute
from ..fixed_width_codec import ExportJustification, ExportPadding
from ..schema import DataBindingDefinition, ModeloRevision
from ..schema_exports import ExportFieldDefinition, FilingEnvelopePrefixFieldDeclaration, FilingEnvelopePrefixRole
from ._loader_directory_mode_support import _committed_modelo, _committed_registry_modelos

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Names the estado-de-cuentas axis would be declared under if it were ever
#: modelled: the axis itself, and the four non-Normal regimes AEAT's Modelo 200
#: page-000 sheet enumerates for the envelope discriminante.
#:
#: Scanned ONLY against closed typed declaration sets (see the guard below), never
#: against registry prose or ids. A substring sweep of the registry tree matches 61
#: files -- casilla labels quoting AEAT's own vocabulary, and unrelated bindings
#: whose names contain "creditos" for deterioro de créditos -- so it would need a
#: large exception allowlist and would detect nothing through the noise. The typed
#: sets carry none of these words today, so scanning them needs no allowlist at
#: all and stays keyed on the property rather than on a tally.
_ACCOUNTS_REGIME_DECLARATION_TOKENS = frozenset(
    {
        "accounts_regime",
        "aseguradora",
        "credito",
        "discriminante",
        "entidad_credito",
        "entity_regime",
        "estado_cuentas",
        "garantia_reciproca",
        "inversion_colectiva",
        "regimen_cuentas",
    },
)


#: Minimum byte width of fixed-width header values that have a known length, so a
#: copy-paste of the header_key onto a too-short field cannot silently truncate /
#: overflow the emitted fichero. ``devengo_start_date`` is a ``ddmmaaaa`` date.
_MIN_HEADER_FIELD_WIDTH: dict[str, int] = {
    "devengo_start_date": 8,
    "fecha_inicio_periodo": 8,
    "fecha_fin_periodo": 8,
}


def _walk_header_fields(node: object) -> list[tuple[str, int, str]]:
    """Recursively collect (header_key, length, id) from any nested export-layout dict.

    Export-layout TOML nests differently across modelos (``export_layouts`` is a
    single table for some, an array of tables for others), so a recursive walk over
    dicts/lists is the robust way to reach every field record.
    """
    found: list[tuple[str, int, str]] = []
    if isinstance(node, dict):
        header_key = node.get("header_key")
        length = node.get("length")
        if isinstance(header_key, str) and isinstance(length, int):
            found.append((header_key, length, str(node.get("id", "?"))))
        for value in node.values():
            found.extend(_walk_header_fields(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_walk_header_fields(value))
    return found


def _walk_export_layout_fields() -> list[tuple[str, str, str, int]]:
    """Yield (file, field_id, header_key, length) for every export-layout header field."""
    registry_root = bundled_path("registry", "aeat")
    rows: list[tuple[str, str, str, int]] = []
    for toml_path in registry_root.glob("modelos/*/revisions/*/export*/*.toml"):
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        for header_key, length, field_id in _walk_header_fields(data):
            rows.append((toml_path.name, field_id, header_key, length))
    return rows


def test_no_fixed_width_header_field_is_too_short_for_its_value() -> None:
    """A header field must be wide enough for the fixed-width value it carries.

    Regression for the M202 export-blocking defect: several length-1
    "datos adicionales" indicator fields were copy-paste mis-keyed to
    ``header_key = "devengo_start_date"`` (an 8-char ``ddmmaaaa`` date), so
    ``encode`` raised "value exceeds length 1" and the IS pago fraccionado could
    not be exported at all. This scans every export-layout TOML and fails if any
    field carries a known fixed-width header value in a field too short to hold it.
    """
    offenders = [
        f"{file}:{field_id} header_key={header_key!r} length={length} < {_MIN_HEADER_FIELD_WIDTH[header_key]}"
        for file, field_id, header_key, length in _walk_export_layout_fields()
        if header_key in _MIN_HEADER_FIELD_WIDTH and length < _MIN_HEADER_FIELD_WIDTH[header_key]
    ]
    assert not offenders, "Fixed-width header value mapped to a too-short export field:\n  " + "\n  ".join(offenders)


def _field(
    *,
    field_id: str = "test.field",
    offset: int | None,
    length: int | None,
) -> ExportFieldDefinition:
    return ExportFieldDefinition.model_validate(
        {
            "id": field_id,
            "offset": offset,
            "length": length,
            "kind": "literal",
            "literal": "x",
            "data_type": "text",
            "required": False,
            "padding": "right_space",
            "justification": "left",
            "signed": False,
            "legal_refs": ("ley-37-1992:art-1",),
            "source_refs": ("aeat-dr-303-2025",),
        },
    )


def _binding(
    selector: dict[str, Any],
    *,
    source: BindingSourceKind = BindingSourceKind.MANUAL_INPUT,
    aggregation: BindingAggregation | None = None,
) -> DataBindingDefinition:
    return DataBindingDefinition.model_validate(
        {
            "id": "binding-under-test",
            "source": source,
            "selector": selector,
            "aggregation": aggregation,
            "legal_refs": ("ley-37-1992:art-1",),
            "source_refs": ("aeat-dr-303-2025",),
        },
    )


# ---------------------------------------------------------------------------
# export_fields_overlap
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("left_offset", "left_length", "right_offset", "right_length"),
    (
        pytest.param(None, 5, 1, 5, id="left-offset"),
        pytest.param(1, None, 1, 5, id="left-length"),
        pytest.param(1, 5, None, 5, id="right-offset"),
    ),
)
def test_export_fields_overlap_returns_false_when_position_is_incomplete(
    left_offset: int | None,
    left_length: int | None,
    right_offset: int | None,
    right_length: int | None,
) -> None:
    left = _field(field_id="a", offset=left_offset, length=left_length)
    right = _field(field_id="b", offset=right_offset, length=right_length)

    assert export_fields_overlap(left, right) is False


def test_export_fields_overlap_detects_partial_overlap() -> None:
    """Fields a[1..5] and b[4..8] share positions 4 and 5."""
    left = _field(field_id="a", offset=1, length=5)
    right = _field(field_id="b", offset=4, length=5)

    assert export_fields_overlap(left, right) is True


def test_export_fields_overlap_detects_full_overlap_when_offsets_match() -> None:
    left = _field(field_id="a", offset=10, length=4)
    right = _field(field_id="b", offset=10, length=4)

    assert export_fields_overlap(left, right) is True


def test_export_fields_overlap_returns_false_for_adjacent_fields() -> None:
    """a[1..5] ends at position 5; b[6..10] starts at 6 — no shared cell."""
    left = _field(field_id="a", offset=1, length=5)
    right = _field(field_id="b", offset=6, length=5)

    assert export_fields_overlap(left, right) is False


def test_export_fields_overlap_returns_false_for_separated_fields() -> None:
    left = _field(field_id="a", offset=1, length=5)
    right = _field(field_id="b", offset=21, length=5)

    assert export_fields_overlap(left, right) is False


# ---------------------------------------------------------------------------
# binding_export_selector
# ---------------------------------------------------------------------------


def test_every_fixed_width_export_surface_refuses_zero_offset() -> None:
    """A registry layout cannot declare a coordinate its binding or BOE wire model rejects."""
    with pytest.raises(ValidationError):
        _field(offset=0, length=1)
    with pytest.raises(ValidationError):
        BindingFixedExportSelector(record="DPA", offset=0, length=1, data_type="text")


def _export_eligible_revision() -> ModeloRevision:
    """Return a real committed revision declaring at least one export layout.

    ``binding_export_selector`` now asserts its revision precondition itself;
    these tests exercise the projection logic, not the precondition, so they
    need a genuinely export-eligible revision in scope. The binding under test
    is synthetic and unrelated to this revision's own bindings -- only
    ``export_layouts`` non-emptiness is read by the precondition.
    """
    return _committed_modelo("390").revisions["2025"]


def test_binding_export_selector_accepts_fixed_field_shape() -> None:
    binding = _binding(
        {
            "record": "DPA",
            "field": "ingresos-integros",
            "offset": 42,
            "length": 10,
            "data_type": "money",
        },
    )

    selector = binding_export_selector(binding, revision=_export_eligible_revision())

    assert isinstance(selector, BindingFixedExportSelector)
    assert selector.record == "DPA"
    assert selector.field == "ingresos-integros"
    assert selector.offset == 42
    assert selector.length == 10
    assert selector.data_type == "money"


def test_binding_export_selector_accepts_row_field_shape() -> None:
    binding = _binding(
        {
            "record": "perceptor",
            "row_field": "retencion_practicada",
            "fact": "row_field",
            "grouping": "per_perceptor",
        },
        source=BindingSourceKind.WITHHOLDING,
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    selector = binding_export_selector(binding, revision=_export_eligible_revision())

    assert isinstance(selector, BindingRowExportSelector)
    assert selector.record == "perceptor"
    assert selector.row_field == "retencion_practicada"


def test_binding_export_selector_ignores_non_export_row_fact_without_record() -> None:
    binding = _binding(
        {
            "row_field": "retencion_practicada",
            "fact": "row_field",
            "grouping": "per_perceptor",
        },
        source=BindingSourceKind.WITHHOLDING,
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    assert binding_export_selector(binding, revision=_export_eligible_revision()) is None


def test_binding_export_selector_ignores_value_data_type_without_record() -> None:
    binding = _binding({"casilla_id": "0168", "data_type": "boolean", "true_value": "N", "false_value": "S"})

    assert binding_export_selector(binding, revision=_export_eligible_revision()) is None


def test_binding_export_selector_rejects_layout_less_revision() -> None:
    """A binding belonging to a revision with no export layout is refused by name.

    ``m347``'s counterpart-summary bindings declare ``record`` for their OWN
    ``_InvoiceSelector`` grouping concept, unrelated to export -- exactly the
    shape that used to be misread as an incomplete export claim before the
    precondition moved into the callee.
    """
    binding = _binding(
        {"fact": "operator_count", "record": "m347_declarante_summary", "rectification_scope": "any"},
        source=BindingSourceKind.COLLECTIBLE_INVOICE,
    )
    # A revision that genuinely declares no export layout, FOUND rather than
    # pinned. This named modelo 200's 2024, which was layout-less
    # when the test was written and has since had its generated export tree
    # authored, so the precondition became false and the selector was never
    # reached. Fourteen bundled revisions still declare none, so the real-site
    # proof survives without naming any one of them.
    layout_less_revision = next(
        revision
        for modelo in _committed_registry_modelos()
        for revision in modelo.revisions.values()
        if not revision.export_layouts
    )

    with pytest.raises(RegistryValidationError, match="is not export-eligible"):
        binding_export_selector(binding, revision=layout_less_revision)


def test_binding_export_selector_rejects_partial_fixed_field_shape() -> None:
    with pytest.raises(ValidationError):
        _binding({"record": "DPA", "offset": 42, "data_type": "money"})


def test_binding_export_selector_rejects_ambiguous_fixed_and_row_shape() -> None:
    with pytest.raises(ValidationError):
        _binding(
            {
                "record": "DPA",
                "row_field": "importe",
                "offset": 42,
                "length": 10,
                "data_type": "money",
            },
        )


def test_binding_export_selector_rejects_unknown_data_type() -> None:
    with pytest.raises(ValidationError):
        _binding({"record": "DPA", "offset": 42, "length": 10, "data_type": "weird"})


def test_binding_export_selector_rejects_non_integer_offset() -> None:
    with pytest.raises(ValidationError):
        _binding({"record": "DPA", "offset": ("1", "2"), "length": 10, "data_type": "money"})


# ---------------------------------------------------------------------------
# _padding_for_binding_data_type — numeric → left_zero, others → right_space
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data_type", "padding"),
    (
        pytest.param("money", "left_zero", id="money"),
        pytest.param("integer", "left_zero", id="integer"),
        pytest.param("decimal", "left_zero", id="decimal"),
        pytest.param("text", "right_space", id="text"),
        pytest.param("date", "right_space", id="date"),
        pytest.param("boolean", "right_space", id="boolean"),
    ),
)
def test_padding_for_binding_data_type(data_type: BindingExportDataType, padding: ExportPadding) -> None:
    """Numeric fixed-width export fields pad with leading zeros so the
    parser can recover the magnitude unambiguously."""
    assert _padding_for_binding_data_type(data_type) == padding


# ---------------------------------------------------------------------------
# _justification_for_binding_data_type — numeric → right, others → left
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data_type", "justification"),
    (
        pytest.param("money", "right", id="money"),
        pytest.param("integer", "right", id="integer"),
        pytest.param("decimal", "right", id="decimal"),
        pytest.param("text", "left", id="text"),
        pytest.param("date", "left", id="date"),
        pytest.param("boolean", "left", id="boolean"),
    ),
)
def test_justification_for_binding_data_type(
    data_type: BindingExportDataType,
    justification: ExportJustification,
) -> None:
    assert _justification_for_binding_data_type(data_type) == justification


# ---------------------------------------------------------------------------
# The Modelo 200 envelope discriminante — one value, two hardcoded authorities
# ---------------------------------------------------------------------------


def _modelo_200_envelope_discriminante_field() -> ExportFieldDefinition:
    """Return the M200 page-000 field holding the envelope-tag discriminante byte.

    Located by BYTE POSITION -- the single character at offset 6 of the page-000
    record -- because that position is fixed by AEAT's published sheet while the
    field's id and kind are exactly what the guards below exist to watch. Finding
    it by id or by kind would make a rename or a re-kind pass vacuously.
    """
    revision = _committed_modelo("200").revisions["2024"]
    return next(
        field
        for layout in revision.export_layouts
        for record in layout.records
        if record.record_type == "page_000"
        for field in record.fields
        if field.offset == 6 and field.length == 1
    )


def _declarable_draft_attributes() -> set[str]:
    """Return every ``draft_attribute`` token an export field may declare."""
    return {member.value for member in ExportDraftAttribute}


def _declared_binding_source_kinds() -> set[str]:
    """Return every declared binding source kind's stored token."""
    return {member.value for member in BindingSourceKind}


def _accounts_regime_declarations(declared: set[str]) -> list[str]:
    """Return the tokens in ``declared`` that name the estado-de-cuentas axis.

    Factored out of the scan so the matcher can be exercised on a token set that
    does name the axis. A scan run only over a clean vocabulary cannot tell a
    working matcher from one that never fires.
    """
    return sorted(
        token
        for token in declared
        if any(candidate in token.lower().replace("-", "_") for candidate in _ACCOUNTS_REGIME_DECLARATION_TOKENS)
    )


def _discriminante_divergence_risks(field: ExportFieldDefinition) -> list[str]:
    """Return the reasons ``field`` would put the two discriminante sites out of step.

    Factored out of the guard so the detector can be exercised on a non-conforming
    field as well as on the committed one. A guard that only ever reads data
    satisfying it cannot distinguish a working detector from a no-op.
    """
    risks: list[str] = []
    if field.kind is not CasillaFieldKind.LITERAL:
        risks.append(
            "the envelope discriminante became registry-driven data; the closing tag's computed "
            "template still hardcodes its own discriminante character, so both sites must be moved "
            "onto the new source together or the two tags will disagree",
        )
    elif field.literal != "0":
        risks.append(
            "the opening tag's discriminante literal changed; the closing tag's computed template "
            "hardcodes the same character independently, so it must change with it",
        )
    return risks


def test_the_modelo_200_envelope_discriminante_stays_an_unmodelled_literal() -> None:
    """The registry declares the discriminante SLOT and never its value.

    This asserted that M200's 2024 revision declared no fixed-width envelope at
    all, which made "exactly one authority for the literal" true by there being
    none. That envelope has since been authored, so the placeholder premise is
    gone and the real question is live: with a modelled envelope present, can the
    registry state a discriminante value that disagrees with the hardcoded one?

    It cannot, and structurally rather than by convention.
    :class:`FilingEnvelopePrefixFieldDeclaration` carries ``role`` and ``length``
    and nothing else, so a declaration can reserve the byte but never fill it;
    ``_ENVELOPE_GRAMMAR_LITERALS`` stays the single authority for the value. This
    reds the moment a value-bearing field is added to that model -- the exact
    window in which the two sites could begin to diverge.
    """
    declared_fields = set(FilingEnvelopePrefixFieldDeclaration.model_fields)

    assert declared_fields == {"role", "length"}, (
        f"the envelope prefix declaration gained a field beyond the slot it reserves: "
        f"{sorted(declared_fields - {'role', 'length'})}. If it can now carry a value, the "
        f"registry and _ENVELOPE_GRAMMAR_LITERALS are two authorities for the discriminante."
    )

    # ...and the role is really in use, so the guard is not watching a dead model.
    discriminante_slots = [
        prefix
        for modelo in _committed_registry_modelos()
        for revision in modelo.revisions.values()
        for layout in revision.export_layouts
        if layout.filing_envelope is not None
        for prefix in layout.filing_envelope.prefix_fields
        if prefix.role is FilingEnvelopePrefixRole.DISCRIMINANT
    ]
    assert discriminante_slots, "no bundled envelope declares a discriminante slot; the guard proves nothing"
    assert all(prefix.length == 1 for prefix in discriminante_slots)


def test_no_typed_declaration_channel_names_an_accounts_regime_concept() -> None:
    """No closed typed set may declare the estado-de-cuentas axis while it is unmodelled.

    The companion to the literal guard above, watching the other direction: that
    guard fires when the discriminante field stops being a literal, and this one
    fires when a typed channel capable of feeding it appears anywhere in the export
    or binding schema -- a new ``draft_attribute`` token or a new binding source
    kind -- even before any registry field binds it.

    Both are scanned rather than one, because a modeller would plausibly land the
    channel and the field binding in separate changes, and the window between them
    is exactly when the two hardcoded discriminante sites would silently diverge.

    The scan covers closed sets small enough to enumerate, so it needs no exception
    allowlist and cannot rot into one.
    """
    declarable_draft_attributes = _declarable_draft_attributes()
    binding_source_kinds = _declared_binding_source_kinds()

    assert declarable_draft_attributes, "the draft-attribute set must be readable for this scan to mean anything"
    assert binding_source_kinds, "the binding-source set must be readable for this scan to mean anything"

    assert _accounts_regime_declarations(declarable_draft_attributes) == []
    assert _accounts_regime_declarations(binding_source_kinds) == []


def test_the_accounts_regime_scan_fires_on_the_real_declaration_sets() -> None:
    """The scan must fire on the real vocabulary the day one regime token joins it.

    The fixture anchor. Both assertions in the guard above are green today because
    their subject does not exist yet, and a gate that passes because nothing matches
    it proves nothing about what it would do when something does. This scans the two
    REAL sets with one regime token added, which is the shape a future addition
    actually takes: a whole live vocabulary plus one new member. It proves the match
    survives contact with the real vocabulary -- that no real token's normalisation
    or ordering masks a positive, and that the scan reports the offender rather than
    merely reporting non-empty.

    What it does NOT prove is that the real sets are populated: an empty set plus the
    injected token would satisfy it too. That is the guard's job above, which asserts
    both sets are non-empty before scanning them; the two together close the vacuity.

    Both channels are anchored because they are read through different mechanisms --
    the draft attributes from a ``Literal`` annotation, the source kinds from an enum
    -- so a change breaking one would leave the other resolving.
    """
    for channel, declared in (
        ("draft attribute", _declarable_draft_attributes()),
        ("binding source kind", _declared_binding_source_kinds()),
    ):
        assert _accounts_regime_declarations(declared | {"estado_cuentas"}) == ["estado_cuentas"], (
            f"the {channel} scan did not fire on its real set plus one regime token"
        )


def test_the_accounts_regime_scan_flags_a_channel_that_names_the_axis() -> None:
    """The scan must flag a regime-named token and leave the real vocabulary alone.

    The anti-vacuity control for the scan above. Without it, a matcher that never
    fires -- a mis-normalised token, or a token set that silently became empty --
    would read as a clean tree. The negative half matters equally: the real
    ``draft_attribute`` and binding-source vocabulary must not be flagged, or the
    scan would be permanently red and get deleted.
    """
    assert _accounts_regime_declarations({"estado_cuentas"}) == ["estado_cuentas"]
    assert _accounts_regime_declarations({"profile-accounts-regime"}) == ["profile-accounts-regime"]
    assert _accounts_regime_declarations({"filing_year", "period_code", "ledger_iva_aggregation"}) == []
