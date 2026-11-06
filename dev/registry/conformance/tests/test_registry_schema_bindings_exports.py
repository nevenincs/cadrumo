"""Registry schema checks for generated casilla markers and user documentation adapters."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.aggregation import BindingAggregation, BindingAggregationOp
from cadrumo.core.identity.documents import IdentityError
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.export_semantics import ExportDraftAttribute
from cadrumo.domain.calculations.registry.governed_fact_scope import (
    CandidateFactAuthority,
    validating_governed_facts,
)
from cadrumo.domain.calculations.registry.invoice_bindings import M349IntracommunityOperationProvider
from cadrumo.domain.calculations.registry.profile_bindings import ProfileProvider
from cadrumo.domain.calculations.registry.schema import (
    ModeloRevision,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, FilingEnvelopePrefixRole
from cadrumo.domain.calculations.registry.schema_extraction import BboxAnchorSpec, ExtractionTargetDefinition
from cadrumo.domain.calculations.registry.schema_surfaces import (
    CasillaContinuidadEvolutionDefinition,
    CasillaDefinition,
)
from cadrumo.domain.calculations.registry.tax_id_format import runtime_tax_id_format
from cadrumo.domain.calculations.registry.tax_id_runtime import validate_runtime_spanish_tax_id

from ...compiler.validate_export_field_widths import (
    DRAFT_ATTRIBUTE_CANONICAL_WIDTHS,
    validate_draft_field_slot_width,
)
from ...compiler.validator import RegistryValidator
from ...tests.profile_schema_support import load_user_profile_schema
from ..registry_schema_support import (
    NUMERIC_CASILLA_01,
    committed_modelo,
    committed_registry,
)
from ..registry_schema_support import (
    revision as committed_revision,
)
from .registry_schema_support import (
    DECL_CNAE_CASILLA,
    MISSING_CASILLA,
    NAMED_LABEL_CASILLA,
    committed_modelo_text,
    load_modelo_text,
    object_boundary,
    validate_revision,
    with_binding,
    with_first_export_field,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_validator_rejects_invalid_invoice_binding_shapes() -> None:
    modelo, catalogues = committed_modelo("349")
    revision = modelo.revisions["2020-y-siguientes"]
    binding = next(item for item in revision.bindings if item.id == "iva-349-declarante-numero-operadores")
    committed = binding.provider
    assert isinstance(committed, M349IntracommunityOperationProvider)

    def with_provider(provider: M349IntracommunityOperationProvider, op: BindingAggregationOp) -> ModeloRevision:
        return with_binding(
            revision,
            binding.model_copy(update={"provider": provider, "aggregation": BindingAggregation(op=op)}),
        )

    rebuilt = M349IntracommunityOperationProvider(
        fact="operator_count",
        claves=committed.claves,
        rectification_scope=committed.rectification_scope,
    )
    validate_revision(modelo, catalogues, with_provider(rebuilt, BindingAggregationOp.COUNT_DISTINCT))

    M349IntracommunityOperationProvider.model_validate_json(
        json.dumps({"fact": "operator_count", "claves": list(committed.claves)})
    )
    with pytest.raises(ValidationError, match="fact"):
        M349IntracommunityOperationProvider.model_validate_json(json.dumps({"claves": list(committed.claves)}))

    cases = (
        (
            "aggregation-mismatch",
            rebuilt,
            BindingAggregationOp.SUM,
            "fact 'operator_count' requires aggregation op 'count_distinct'",
        ),
        (
            "rectification-delta-without-scope",
            M349IntracommunityOperationProvider(
                fact="rectified_base_delta_sum",
                claves=committed.claves,
                rectification_scope=committed.rectification_scope,
            ),
            BindingAggregationOp.SUM,
            "fact 'rectified_base_delta_sum' requires rectification_scope 'only_rectifications'",
        ),
        (
            "period-rows-without-scope",
            M349IntracommunityOperationProvider(
                fact="row_field",
                row_field="base_imponible",
                grouping="operator_clave_period",
                claves=committed.claves,
                rectification_scope=committed.rectification_scope,
            ),
            BindingAggregationOp.ROWS,
            "grouping 'operator_clave_period' requires rectification_scope 'only_rectifications'",
        ),
    )

    for case_id, provider, op, match in cases:
        with pytest.raises(RegistryValidationError, match=match) as excinfo:
            validate_revision(modelo, catalogues, with_provider(provider, op))
        assert excinfo.type is RegistryValidationError, case_id


def test_validator_rejects_profile_binding_selector_missing_from_user_profile_schema() -> None:
    modelo, catalogues = committed_modelo("100")
    revision = modelo.revisions["2025"]
    binding = next(
        item
        for item in revision.bindings
        if isinstance(item.provider, ProfileProvider) and item.provider.profile_key is not None
    )
    validate_revision(modelo, catalogues, revision)

    unknown_key = ProfileProvider.model_validate_json(
        json.dumps({**binding.provider.model_dump(mode="json"), "profile_key": "unknown.profile"}),
    )
    mutated = with_binding(revision, binding.model_copy(update={"provider": unknown_key}))

    with pytest.raises(
        RegistryValidationError,
        match=r"user-profile schema .* selector 'unknown\.profile'",
    ):
        validate_revision(modelo, catalogues, mutated)


def test_export_fields_can_reference_structured_bindings() -> None:
    modelo, catalogues = committed_modelo("131")
    revision = modelo.revisions["2026"]
    bound_revision = with_first_export_field(
        revision,
        ExportFieldDefinition.model_validate(
            {
                **revision.export_layouts[0].records[0].fields[0].model_dump(mode="python"),
                "id": "modelo-130-export-bound-net-income",
                "kind": "binding",
                "binding": revision.bindings[0].id,
                "casilla_id": None,
                "literal": None,
                "producer_key": None,
                "draft_attribute": None,
                "computed_key": None,
                "data_type": "money",
                "required": False,
                "padding": "left_zero",
                "justification": "right",
            },
        ),
    )

    new_field = bound_revision.export_layouts[0].records[0].fields[0]
    assert new_field.kind is CasillaFieldKind.BINDING
    assert new_field.binding == revision.bindings[0].id
    validate_revision(modelo, catalogues, bound_revision)


def test_validator_rejects_export_field_with_unknown_binding() -> None:
    modelo, catalogues = committed_modelo("131")
    revision = modelo.revisions["2026"]
    bound_revision = with_first_export_field(
        revision,
        ExportFieldDefinition.model_validate(
            {
                **revision.export_layouts[0].records[0].fields[0].model_dump(mode="python"),
                "id": "modelo-130-export-bound-missing",
                "kind": "binding",
                "binding": "missing.export.binding",
                "casilla_id": None,
                "literal": None,
                "producer_key": None,
                "draft_attribute": None,
                "computed_key": None,
                "data_type": "money",
                "required": False,
                "padding": "left_zero",
                "justification": "right",
            },
        ),
    )

    with pytest.raises(RegistryValidationError, match="unknown binding"):
        validate_revision(modelo, catalogues, bound_revision)


def test_validator_rejects_literal_export_field_longer_than_declared_length() -> None:
    modelo, catalogues = committed_modelo("131")
    revision = modelo.revisions["2026"]
    layout = revision.export_layouts[0]
    record = layout.records[0]
    field = next(item for item in record.fields if item.kind == "literal" and item.length is not None)
    assert field.length is not None
    oversized = field.model_copy(update={"literal": "X" * (field.length + 1)})
    fields = tuple(oversized if item.id == field.id else item for item in record.fields)
    records = tuple(
        record.model_copy(update={"fields": fields}) if item.id == record.id else item for item in layout.records
    )
    layouts = tuple(
        layout.model_copy(update={"records": records}) if item.id == layout.id else item
        for item in revision.export_layouts
    )
    mutated = revision.model_copy(update={"export_layouts": layouts})

    with pytest.raises(RegistryValidationError, match=r"literal length .* exceeds declared length"):
        validate_revision(modelo, catalogues, mutated)


#: The Modelo 200 page 001B slot the diseño reserves for the mercantile group's
#: ultimate parent company's foreign tax identification number.
_M200_PARENT_TIN_FIELD_ID = "modelo-200-page-001b-draft-profile_tax_id-pos-141"


def _export_field_by_id(
    revision: ModeloRevision,
    field_id: str,
) -> tuple[ExportFieldDefinition, str, str]:
    """Return one export field with its record and layout ids, or fail loudly."""
    for layout in revision.export_layouts:
        for record in layout.records:
            for field in record.fields:
                if field.id == field_id:
                    return field, record.id, layout.id
    raise AssertionError(f"the committed revision declares no export field {field_id!r}")


def _first_profile_tax_id_draft_field(
    revision: ModeloRevision,
) -> tuple[ExportFieldDefinition, str, str]:
    """Return the revision's first declarant-NIF draft field with its record and layout ids.

    Located by PROPERTY -- draft kind plus the ``profile_tax_id`` attribute -- not
    by a pinned field id, so renaming or renumbering the committed declaration
    cannot make the callers below pass without exercising anything.
    """
    for layout in revision.export_layouts:
        for record in layout.records:
            for field in record.fields:
                kind = object_boundary(field.kind)
                draft_attribute = object_boundary(field.draft_attribute)
                if kind == CasillaFieldKind.DRAFT and draft_attribute == "profile_tax_id":
                    return field, record.id, layout.id
    raise AssertionError("the committed revision declares no profile_tax_id draft export field to anchor on")


def _with_replaced_export_field(
    revision: ModeloRevision,
    *,
    layout_id: str,
    record_id: str,
    field: ExportFieldDefinition,
) -> ModeloRevision:
    def _replace_record(record):
        fields = tuple(field if item.id == field.id else item for item in record.fields)
        return record.model_copy(update={"fields": fields})

    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    _replace_record(record) if record.id == record_id else record for record in layout.records
                ),
            },
        )
        if layout.id == layout_id
        else layout
        for layout in revision.export_layouts
    )
    return revision.model_copy(update={"export_layouts": layouts})


@pytest.mark.usefixtures("governed_fact_scope")
def test_spanish_tax_id_width_is_the_width_the_identifier_validator_enforces() -> None:
    """The declared identifier width must still be the one the validator refuses around.

    The export slot-width check asserts a ``profile_tax_id`` slot is exactly
    the authority-declared number of characters. That assertion means nothing unless the
    governed declaration describes the identifier contract, so pin it against the
    validator's actual behaviour rather than against a second copy of the number:
    a canonical identifier of that width validates, and padding or truncating it
    by one character is refused.
    """
    canonical = validate_runtime_spanish_tax_id("B00015016")

    width = runtime_tax_id_format().width
    assert len(canonical) == width
    with pytest.raises(IdentityError, match=rf"exactly {width} characters"):
        validate_runtime_spanish_tax_id(f"{canonical}0")
    with pytest.raises(IdentityError, match=rf"exactly {width} characters"):
        validate_runtime_spanish_tax_id(canonical[:-1])


def test_draft_attribute_width_ruling_covers_every_declarable_attribute() -> None:
    """Every declarable draft attribute must carry a width ruling, gated or abstained.

    Keys the gate on the property rather than on today's declarations: a new
    ``draft_attribute`` added to the field schema without a ruling makes the width
    mapping non-total, and registry validation then refuses any field binding it.
    Asserting the mapping is total here names that obligation at the schema, so the
    refusal is a design prompt rather than a puzzling build failure.
    """
    declarable = set(ExportDraftAttribute)

    assert declarable
    assert set(DRAFT_ATTRIBUTE_CANONICAL_WIDTHS) == declarable
    assert "profile_tax_id" not in declarable


def test_validator_rejects_declarant_nif_draft_field_bound_to_a_wider_slot() -> None:
    """Deleted profile draft authority cannot be restored at any slot width."""
    modelo, catalogues = committed_modelo("131")
    revision = modelo.revisions["2026"]
    field = (
        revision.export_layouts[0]
        .records[0]
        .fields[0]
        .model_copy(
            update={"kind": CasillaFieldKind.DRAFT, "draft_attribute": "profile_tax_id", "literal": None, "length": 15},
        )
    )
    mutated = with_first_export_field(revision, field)

    with pytest.raises(RegistryValidationError, match="profile_tax_id"):
        validate_revision(modelo, catalogues, mutated)


@pytest.mark.usefixtures("governed_fact_scope")
def test_validator_accepts_declarant_nif_draft_field_at_the_identifier_width() -> None:
    """Deleted profile draft authority is refused even at the identifier width."""
    modelo, catalogues = committed_modelo("131")
    revision = modelo.revisions["2026"]
    field = (
        revision.export_layouts[0]
        .records[0]
        .fields[0]
        .model_copy(
            update={
                "kind": CasillaFieldKind.DRAFT,
                "draft_attribute": "profile_tax_id",
                "literal": None,
                "length": runtime_tax_id_format().width,
            },
        )
    )
    mutated = with_first_export_field(revision, field)

    with pytest.raises(RegistryValidationError, match="profile_tax_id"):
        validate_revision(modelo, catalogues, mutated)


def _committed_export_field(revision: ModeloRevision) -> ExportFieldDefinition:
    """Return one real field from ``revision``'s committed export layout.

    The width proofs below mutate a field that actually shipped rather than
    building one, so the legal and source references, data type and padding are
    the committed revision's own and only the width under test differs. A
    constructed field can satisfy a detector that the real declaration's shape
    would slip past.
    """
    return next(field for layout in revision.export_layouts for record in layout.records for field in record.fields)


def test_validator_rejects_the_modelo_200_envelope_open_tag_collapsed_onto_one_draft_field() -> None:
    """Collapsing M200's envelope-open composite back onto the year field must be refused.

    The real-site proof for the ``filing_year`` width ruling, and the standing
    regression against re-authoring the defect it replaced. Modelo 200's page-000
    record once declared the whole 17-character envelope-open constant as a single
    ``filing_year`` draft field: the year rendered into the first four bytes and the
    remaining thirteen padded to blanks, so every export omitted the ``<T``, the
    modelo code, the discriminante, the period token and the ``0000>`` marker
    AEAT's ``DP200000`` sheet requires there.

    The defect site is now gone by CONSTRUCTION rather than by a validator
    refusing it: the seventeen bytes are declared once as a typed
    :attr:`FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG`, and
    :class:`FilingEnvelopeDefinition` refuses a declaration carrying both that
    spelling and the six-role one. So there is no ``filing_year`` draft field on
    a Modelo 200 record for a collapse to be re-authored onto.

    Asserting the emptiness this test used to assert would now be false anyway --
    the campaign authored Modelo 200's generated export tree, so the revision
    declares a layout again. The proof therefore has two halves: the repaired
    state is asserted on the real committed revision, and the width detector is
    driven over a constructed field, because a detector proven only where the
    defect can no longer occur proves nothing.
    """
    modelo, _catalogues = committed_modelo("200")
    revision = modelo.revisions["2025-y-siguientes"]

    composed = tuple(
        prefix
        for layout in revision.export_layouts
        if layout.filing_envelope is not None
        for prefix in layout.filing_envelope.prefix_fields
        if prefix.role is FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG
    )
    assert len(composed) == 1, "Modelo 200 spells its envelope-open tag as one composed role"
    assert composed[0].length == 17, "the composed tag carries the whole AEAT identifier's width"

    collapsed_onto_a_record = tuple(
        field.id
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.DRAFT
        and field.draft_attribute is ExportDraftAttribute.FILING_YEAR
        and field.length != DRAFT_ATTRIBUTE_CANONICAL_WIDTHS[ExportDraftAttribute.FILING_YEAR]
    )
    assert collapsed_onto_a_record == (), (
        f"a record field binds the ejercicio to a slot that is not the year's own width: {collapsed_onto_a_record}"
    )

    collapsed = _committed_export_field(revision).model_copy(
        update={
            "kind": CasillaFieldKind.DRAFT,
            "draft_attribute": ExportDraftAttribute.FILING_YEAR,
            "casilla_id": None,
            "literal": None,
            "length": 17,
        },
    )
    failures = validate_draft_field_slot_width(prefix="modelo 200 revision 2025-y-siguientes", field=collapsed)
    assert any("to a slot of length 17" in failure for failure in failures), failures


@pytest.mark.usefixtures("governed_fact_scope")
def test_validator_rejects_the_grupo_mercantil_parent_tin_slot_rebound_to_the_declarant() -> None:
    """Re-binding M200's foreign-parent-TIN slot to the declarant must be refused.

    The real-site proof for the width check, and the standing regression against
    re-authoring the misbinding. The checks above widen a correct declaration, which
    shows the validator works on input the test itself shaped; this one restores the
    defect exactly as it shipped -- the committed Modelo 200 field, at its
    AEAT-correct 15-byte width, re-bound to the declarant's own NIF -- and drives the
    real registry validator over the real loaded revision. A detector that only fires
    on shaped input can still miss the site that matters.

    This one is closed harder than the sibling above. The misbinding needed a
    draft attribute yielding the DECLARANT's own tax id, and no such attribute
    exists any more: :class:`ExportDraftAttribute` declares four members, all of
    them period or ejercicio facts. A slot reserved for a group parent's foreign
    TIN therefore has nothing to be re-bound to.

    What keeps that closed is the width mapping's TOTALITY, so this asserts the
    property rather than the current membership: re-introducing an identity
    attribute without ruling on its width fails validation instead of passing
    silently, and a 15-wide slot fed a 9-character Spanish tax id is exactly the
    contradiction the detector reports.
    """
    modelo, _catalogues = committed_modelo("200")
    revision = modelo.revisions["2025-y-siguientes"]

    assert set(DRAFT_ATTRIBUTE_CANONICAL_WIDTHS) == set(ExportDraftAttribute), (
        "the width ruling must stay total over the declarable attributes, or a "
        "re-introduced identity attribute could be bound with no width ruling at all"
    )
    assert all(attribute.name.startswith(("FILING_", "PERIOD_")) for attribute in ExportDraftAttribute), (
        "a draft attribute yielding a party's identity is back; the grupo-mercantil "
        "parent-TIN misbinding becomes expressible again and needs its own width ruling"
    )

    declarant_bound_slots = tuple(
        field.id
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.DRAFT and field.length == runtime_tax_id_format().width
    )
    assert declarant_bound_slots == (), f"a draft field is bound at the Spanish tax id's width: {declarant_bound_slots}"

    misbound = _committed_export_field(revision).model_copy(
        update={
            "kind": CasillaFieldKind.DRAFT,
            "draft_attribute": ExportDraftAttribute.FILING_YEAR,
            "casilla_id": None,
            "literal": None,
            "length": runtime_tax_id_format().width,
        },
    )
    failures = validate_draft_field_slot_width(prefix="modelo 200 revision 2025-y-siguientes", field=misbound)
    width = runtime_tax_id_format().width
    assert any(f"to a slot of length {width}" in failure for failure in failures), failures


def test_validator_rejects_parameter_without_official_source_guidance() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
    parameters = tuple(
        parameter.model_copy(update={"source_refs": ("aeat-dr-130-2019-v12",)})
        if parameter.id == "irpf.direct_estimation_fractional_payment_rate"
        else parameter
        for parameter in revision.parameters
    )
    mutated = revision.model_copy(update={"parameters": parameters})

    with pytest.raises(RegistryValidationError, match="requires official_source_guidance source evidence"):
        validate_revision(modelo, catalogues, mutated)


def test_modelo_file_rejects_static_cross_reference_as_executable_parity(tmp_path: Path) -> None:
    text = committed_modelo_text().replace(
        'evidence_tier = "layout_authority"\nsurface = "static_official_documentation"',
        'evidence_tier = "executable_parity_evidence"\nsurface = "static_official_documentation"',
        1,
    )

    with pytest.raises(RegistryLoadError, match="static documentation is not executable parity evidence"):
        load_modelo_text(tmp_path, text)


def test_validator_rejects_cross_reference_source_tier_mismatch() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
    cross_reference = revision.live_cross_references[0].model_copy(update={"evidence_tier": "official_source_guidance"})
    mutated = revision.model_copy(update={"live_cross_references": (cross_reference,)})

    with pytest.raises(RegistryValidationError, match="requires official_source_guidance source evidence"):
        validate_revision(modelo, catalogues, mutated)


def test_modelo_file_rejects_runner_without_formula_workbook(tmp_path: Path) -> None:
    text = committed_modelo_text().replace("runner_required = false", "runner_required = true", 1)

    with pytest.raises(RegistryLoadError, match="runner requires formula coverage"):
        load_modelo_text(tmp_path, text)


def test_validator_rejects_missing_legal_reference() -> None:
    modelo, catalogues = committed_registry()
    missing_legal = catalogues.model_copy(update={"legal": {}})

    with (
        pytest.raises(RegistryValidationError, match="unknown legal id"),
        validating_governed_facts(
            CandidateFactAuthority(missing_legal.facts, missing_legal.require_supported_filing_years())
        ),
    ):
        RegistryValidator(
            missing_legal,
            source_root=bundled_path(),
            user_profile_schema=load_user_profile_schema(),
        ).validate_modelo(modelo)


def test_validator_rejects_extraction_profile_unknown_casilla() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
    profile = revision.extraction_profiles[0].model_copy(
        update={
            "target_casillas": (
                ExtractionTargetDefinition(
                    casilla_id=MISSING_CASILLA,
                    match_strategy="numeric_casilla",
                    value_kind="amount",
                ),
            ),
        },
    )
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match=r"extraction profile .* unknown casilla"):
        validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_extraction_profile_artefact_surface_mismatch() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
    profile = revision.extraction_profiles[0].model_copy(update={"accepted_artefact_kinds": ("justificante_pdf",)})
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match="surface 'declaracion_pdf' requires"):
        validate_revision(modelo, catalogues, mutated)


def test_extraction_target_definition_roundtrip() -> None:
    """ExtractionTargetDefinition strict-frozen roundtrip with non-default fields."""
    target = ExtractionTargetDefinition(
        casilla_id=NAMED_LABEL_CASILLA,
        match_strategy="named_label",
        value_kind="text",
        label_pattern=r"Mi etiqueta especial",
    )
    raw = target.model_dump()
    restored = ExtractionTargetDefinition.model_validate(raw)
    assert restored == target
    assert restored.casilla_id == NAMED_LABEL_CASILLA
    assert restored.match_strategy == "named_label"
    assert restored.value_kind == "text"
    assert restored.label_pattern == r"Mi etiqueta especial"


def test_bbox_anchor_rejects_inverted_anchor_x_range() -> None:
    with pytest.raises(ValidationError, match="bbox anchor_x_min must not exceed anchor_x_max"):
        BboxAnchorSpec(
            box_number_pattern=r"01",
            value_offset="right_of_number",
            anchor_x_min=200.0,
            anchor_x_max=100.0,
        )


def test_extraction_target_definition_anti_tautology() -> None:
    """Mutating the serialised payload surfaces inequality after reload."""
    target = ExtractionTargetDefinition(
        casilla_id=NUMERIC_CASILLA_01,
        match_strategy="numeric_casilla",
        value_kind="amount",
    )
    raw = target.model_dump()
    raw["match_strategy"] = "named_label"
    raw["label_pattern"] = "Retenciones"
    mutated = ExtractionTargetDefinition.model_validate(raw)
    assert mutated != target


def test_extraction_target_named_label_requires_label_pattern() -> None:
    with pytest.raises(ValidationError, match="named_label extraction targets require label_pattern"):
        ExtractionTargetDefinition(
            casilla_id=DECL_CNAE_CASILLA,
            match_strategy="named_label",
            value_kind="text",
        )


def test_extraction_target_numeric_casilla_rejects_label_pattern() -> None:
    with pytest.raises(ValidationError, match="numeric_casilla extraction targets must not define label_pattern"):
        ExtractionTargetDefinition(
            casilla_id=NUMERIC_CASILLA_01,
            match_strategy="numeric_casilla",
            value_kind="amount",
            label_pattern="Retenciones",
        )


def test_casilla_accepts_continuidad_id_roundtrip() -> None:
    casilla = CasillaDefinition.model_validate(
        {
            "id": "0700",
            "number": "0700",
            "localization_keys": ("test.schema.casilla.label",),
            "section": ("base",),
            "data_type": "money",
            "continuidad_id": "renta-base-liquidacion-general",
            "legal_refs": ("ley-35-2006:art-48",),
            "source_refs": ("aeat-manual",),
        },
    )

    restored = CasillaDefinition.model_validate(
        {**casilla.model_dump(), "localization_keys": casilla.localization_keys},
    )

    assert restored == casilla
    assert restored.continuidad_id == "renta-base-liquidacion-general"


def test_casilla_continuidad_id_refuses_a_dotted_segment() -> None:
    """A chain id must be one plain locale-key segment, so dots are refused.

    The chain id is embedded whole into the shared locale key as
    ``modelo.schema.<modelo>.casilla.continuidad.<chain-id>.<field>``, and
    ``encode_modelo_locale_segment`` base32-encodes any segment that is not
    ``[A-Za-z0-9_-]+``. A dotted id therefore renders its own continuity key as
    an opaque ``x-...`` blob in all four catalogues -- a translator sees the blob
    and never the concept.

    The pattern used to permit ``.`` and ``:``, so nothing refused such an id and
    the damage surfaced only as unreadable keys afterwards; eleven Modelo 100
    pilots shipped that way before being converted. This asserts the refusal at
    the boundary, so the class cannot return by loosening the pattern back.
    """
    for rejected in ("irpf.inmueble.porcentaje-propiedad", "irpf:inmueble"):
        with pytest.raises(ValidationError, match="continuidad_id"):
            CasillaDefinition.model_validate(
                {
                    "id": "0700",
                    "number": "0700",
                    "localization_keys": ("test.schema.casilla.label",),
                    "section": ("base",),
                    "data_type": "money",
                    "continuidad_id": rejected,
                    "legal_refs": ("ley-35-2006:art-48",),
                    "source_refs": ("aeat-manual",),
                },
            )


def test_casilla_continuidad_id_uses_registry_id_shape() -> None:
    with pytest.raises(ValidationError, match="continuidad_id"):
        CasillaDefinition.model_validate(
            {
                "id": "0700",
                "number": "0700",
                "localization_keys": ("test.schema.casilla.label",),
                "section": ("base",),
                "continuidad_id": "Renta Base",
                "legal_refs": ("ley-35-2006:art-48",),
                "source_refs": ("aeat-manual",),
            },
        )


def test_casilla_continuidad_evolution_rejects_same_revision_pair() -> None:
    with pytest.raises(ValidationError, match="must span two different revisions"):
        CasillaContinuidadEvolutionDefinition(
            id="renta-2024-self-evolution",
            continuidad_id="renta-base-liquidacion-general",
            from_revision="2024",
            to_revision="2024",
            evolution_kind="label_evolved",
            legal_refs=("ley-35-2006:art-48",),
            source_refs=("aeat-manual",),
        )


def test_modelo_revision_defaults_to_advisory_continuidad_validation() -> None:
    revision = ModeloRevision.model_validate(
        {
            "id": "2024",
            "localization_key": "test.schema.revision.label",
            "valid_from": date(2024, 1, 1),
            "period_selector": {"years": (2024,), "periods": ("0A",)},
            "legal_refs": ("ley-35-2006:art-48",),
            "source_refs": ("aeat-manual",),
        },
    )

    assert revision.continuidad_validation == "advisory"
    assert revision.casilla_continuidad_evolutions == ()
