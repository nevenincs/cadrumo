"""Structural tests for the registry casilla schema projection.

Asserts that legal_refs and source_refs survive the projection from
CasillaDefinition through to RegistryCasillaSchema so that filing-layer
consumers have access to regulatory grounding.

Modelo 130 is used as the reference fixture because it is fully validated
and representative of the registry's legal-grounding requirements.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pytest
from pydantic import ValidationError

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.tax_domain import TaxDomain
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ids import FormulaId
from ....domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, RegistrySnapshot
from ....domain.filing.errors import ModeloBuilderError
from ..runtime import (
    RegistryCasillaCollection,
    RegistryCasillaSchema,
    build_runtime_schema_provider,
    collection_from_snapshot,
    registry_value_type,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TEST_MODELO = "130"
_TEST_YEAR = 2026
_TEST_PERIOD = Period.from_year_and_code(_TEST_YEAR, "1T")
_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_CASILLA_01")
_CASILLA_02: CasillaId = validated_casilla_id("02", surface="_CASILLA_02")
_MISSING_INPUT_CASILLA: CasillaId = validated_casilla_id("missing", surface="_MISSING_INPUT_CASILLA")


def _source_casilla_refs(operation: PinnedAuthorityOperation) -> dict[CasillaId, tuple[str, ...]]:
    """Return {casilla_id: legal_refs} from the authoritative CasillaDefinition."""
    snapshot = operation.snapshot(
        _TEST_MODELO,
        filing_year=_TEST_YEAR,
        period=_TEST_PERIOD.registry_token,
    )
    return {casilla.id: casilla.legal_refs for casilla in snapshot.revision.casillas}


def _source_casilla_source_refs(operation: PinnedAuthorityOperation) -> dict[CasillaId, tuple[str, ...]]:
    """Return {casilla_id: source_refs} from the authoritative CasillaDefinition."""
    snapshot = operation.snapshot(
        _TEST_MODELO,
        filing_year=_TEST_YEAR,
        period=_TEST_PERIOD.registry_token,
    )
    return {casilla.id: casilla.source_refs for casilla in snapshot.revision.casillas}


@pytest.mark.parametrize(
    ("source_factory", "attribute"),
    [
        (_source_casilla_refs, "legal_refs"),
        (_source_casilla_source_refs, "source_refs"),
    ],
    ids=("legal-refs", "source-refs"),
)
def test_refs_survive_projection(
    operation: PinnedAuthorityOperation,
    source_factory: Callable[[PinnedAuthorityOperation], dict[CasillaId, tuple[str, ...]]],
    attribute: str,
) -> None:
    """RegistryCasillaSchema must carry the same refs as the source CasillaDefinition."""
    source = source_factory(operation)
    provider = build_runtime_schema_provider(
        modelos=[_TEST_MODELO], filing_year=_TEST_YEAR, period=_TEST_PERIOD, operation=operation
    )
    collection = provider.get_collection(_TEST_MODELO)
    schemas = collection.all()

    casillas_with_refs = [s for s in schemas if source.get(s.casilla_id)]
    assert casillas_with_refs, f"No casillas with {attribute} found in modelo {_TEST_MODELO} — test would be vacuous"

    for schema in schemas:
        assert isinstance(schema, RegistryCasillaSchema)
        expected = source.get(schema.casilla_id, ())
        projected = getattr(schema, attribute)
        assert projected == expected, (
            f"{attribute} mismatch for casilla {schema.casilla_id}: projected={projected!r}, source={expected!r}"
        )


def test_complete_constraints_survive_projection(operation: PinnedAuthorityOperation) -> None:
    """Filing schemas carry the registry's complete constraint contract verbatim."""
    snapshot = operation.snapshot(
        _TEST_MODELO,
        filing_year=_TEST_YEAR,
        period=_TEST_PERIOD.registry_token,
    )
    source_constraints = {casilla.id: casilla.constraints for casilla in snapshot.revision.casillas}
    provider = build_runtime_schema_provider(
        modelos=[_TEST_MODELO], filing_year=_TEST_YEAR, period=_TEST_PERIOD, operation=operation
    )
    schemas = provider.get_collection(_TEST_MODELO).all()

    assert any(constraints is not None and constraints.sign != "any" for constraints in source_constraints.values())
    for schema in schemas:
        assert schema.constraints == source_constraints[schema.casilla_id]


def test_subview_catalogue_ref_ids_survive_projection(operation: PinnedAuthorityOperation) -> None:
    """RegistryModeloSubview must carry the same catalogue refs as the source snapshot."""
    snapshot = operation.snapshot(
        _TEST_MODELO,
        filing_year=_TEST_YEAR,
        period=_TEST_PERIOD.registry_token,
    )
    provider = build_runtime_schema_provider(
        modelos=[_TEST_MODELO], filing_year=_TEST_YEAR, period=_TEST_PERIOD, operation=operation
    )
    subview = provider.get_subview(_TEST_MODELO)

    assert subview.legal_ref_ids == tuple(sorted(snapshot.legal))
    assert subview.source_ref_ids == tuple(sorted(snapshot.sources))


def test_provider_absent_modelo_error_is_localized() -> None:
    provider = build_runtime_schema_provider(modelos=[_TEST_MODELO], filing_year=_TEST_YEAR, period=_TEST_PERIOD)

    with pytest.raises(ModeloBuilderError) as exc_info:
        provider.get_collection("999")

    assert exc_info.value.translated_message == "application.filing.runtime.errors.modelo_not_in_registry"
    assert exc_info.value.context == {"modelo": "999"}


def test_blank_modelo_selection_error_is_localized() -> None:
    with pytest.raises(ModeloBuilderError) as exc_info:
        build_runtime_schema_provider(
            modelos=[" "],
            filing_year=_TEST_YEAR,
            period=_TEST_PERIOD,
        )

    assert exc_info.value.translated_message == "application.filing.runtime.errors.blank_modelo_selection"


def test_missing_requested_modelo_error_is_localized() -> None:
    with pytest.raises(ModeloBuilderError) as exc_info:
        build_runtime_schema_provider(
            modelos=["999"],
            filing_year=_TEST_YEAR,
            period=_TEST_PERIOD,
        )

    assert exc_info.value.translated_message == "application.filing.runtime.errors.registry_missing_requested_modelos"
    assert exc_info.value.context == {"modelos": "999"}


def test_missing_period_error_is_localized() -> None:
    with pytest.raises(ModeloBuilderError) as exc_info:
        build_runtime_schema_provider(modelos=[_TEST_MODELO], filing_year=_TEST_YEAR, period=None)

    assert exc_info.value.translated_message == "application.filing.runtime.errors.period_type"
    assert exc_info.value.context == {"period_type": "NoneType"}


def test_runtime_schema_provider_rejects_raw_period_string() -> None:
    with pytest.raises(ModeloBuilderError) as exc_info:
        build_runtime_schema_provider(
            modelos=[_TEST_MODELO],
            filing_year=_TEST_YEAR,
            period=_TEST_PERIOD.registry_token,
        )

    assert exc_info.value.translated_message == "application.filing.runtime.errors.period_type"
    assert exc_info.value.context == {"period_type": "str"}


def test_unsupported_casilla_data_type_error_is_localized() -> None:
    with pytest.raises(ModeloBuilderError) as exc_info:
        registry_value_type("blob")

    assert exc_info.value.translated_message == "application.filing.runtime.errors.unsupported_casilla_data_type"
    assert exc_info.value.context is not None
    assert exc_info.value.context["data_type"] == "blob"


def _registry_casilla_schema(
    casilla_id: CasillaId,
    *,
    formula: FormulaId | None = None,
    formula_input_casilla_ids: tuple[CasillaId, ...] = (),
) -> RegistryCasillaSchema:
    return RegistryCasillaSchema(
        casilla_id=casilla_id,
        value_type="decimal",
        required=False,
        formula=formula,
        formula_input_casilla_ids=formula_input_casilla_ids,
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual",),
    )


def test_registry_casilla_schema_rejects_generic_id_key() -> None:
    with pytest.raises(ValidationError):
        RegistryCasillaSchema.model_validate(
            {
                "id": _CASILLA_01,
                "value_type": "decimal",
                "required": False,
                "formula": None,
                "formula_input_casilla_ids": (),
                "legal_refs": ("ley-58-2003:art-29",),
                "source_refs": ("aeat-manual",),
            },
        )


def test_registry_casilla_schema_rejects_legacy_formula_inputs_key() -> None:
    with pytest.raises(ValidationError, match="formula_inputs"):
        RegistryCasillaSchema.model_validate(
            {
                "casilla_id": _CASILLA_01,
                "value_type": "decimal",
                "required": False,
                "formula": None,
                "formula_inputs": (),
                "legal_refs": ("ley-58-2003:art-29",),
                "source_refs": ("aeat-manual",),
            },
        )


def test_registry_casilla_collection_rejects_duplicate_casilla_ids() -> None:
    casilla = _registry_casilla_schema(_CASILLA_01)

    with pytest.raises(ModeloBuilderError) as exc_info:
        RegistryCasillaCollection(
            casillas=(casilla, casilla.model_copy()),
            schema_version="registry:test:rev",
        )
    assert exc_info.value.translated_message == "application.filing.runtime.errors.ambiguous_casilla_schema"
    assert exc_info.value.context == {"schema_version": "registry:test:rev", "casilla_ids": _CASILLA_01}


def test_registry_casilla_collection_rejects_dangling_formula_inputs() -> None:
    computed = _registry_casilla_schema(
        _CASILLA_02,
        formula="test.formula",
        formula_input_casilla_ids=(_MISSING_INPUT_CASILLA,),
    )

    with pytest.raises(ModeloBuilderError) as exc_info:
        RegistryCasillaCollection(casillas=(computed,), schema_version="registry:test:rev")
    assert exc_info.value.translated_message == "application.filing.runtime.errors.ambiguous_casilla_schema"
    assert exc_info.value.context == {
        "schema_version": "registry:test:rev",
        "casilla_ids": f"{_CASILLA_02}: {_MISSING_INPUT_CASILLA}",
    }


def test_runtime_projection_rejects_ambiguous_revision_casilla_identity() -> None:
    revision = ModeloRevision.model_validate(
        {
            "id": "2025",
            "localization_key": "test.schema.revision.2025.label",
            "valid_from": date(2025, 1, 1),
            "period_selector": {"years": (2025,), "periods": ("0A",)},
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "casillas": (
                {
                    "id": "01",
                    "number": "99",
                    "localization_keys": ("test.schema.casilla.label",),
                    "section": ("test",),
                    "legal_refs": ("ley-58-2003:art-29",),
                    "source_refs": ("aeat-manual",),
                },
                {
                    "id": "DPX:01",
                    "number": "01",
                    "segmento": "DPX",
                    "localization_keys": ("test.schema.casilla.label",),
                    "section": ("test",),
                    "legal_refs": ("ley-58-2003:art-29",),
                    "source_refs": ("aeat-manual",),
                },
            ),
        },
    )
    modelo = ModeloDefinition(
        id="999",
        title_localization_key="test.schema.modelo.999.title",
        official_name_localization_key="test.schema.modelo.999.official_name",
        tax_domain=TaxDomain("iva"),
        cadence="annual",
        jurisdiction="ES-AEAT",
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual",),
        revisions={"2025": revision},
    )
    snapshot = RegistrySnapshot(
        modelo=modelo,
        revision=revision,
        filing_year=2025,
        period="0A",
        legal={},
        sources={},
        extraction_profiles={},
        live_cross_references={},
        workbook_parity_refs={},
        verification_expectations={},
        application_links={},
        deadline_windows={},
        filing_schedules={},
        constructs={},
        dependency_classifications={},
    )

    with pytest.raises(ModeloBuilderError) as exc_info:
        collection_from_snapshot(snapshot)

    assert exc_info.value.translated_message == "application.filing.runtime.errors.ambiguous_casilla_schema"
    assert exc_info.value.context is not None
    assert exc_info.value.context["schema_version"] == "registry:999:2025"
    assert exc_info.value.context["modelo"] == "999"
    assert exc_info.value.context["revision_id"] == "2025"
    assert exc_info.value.context["filing_year"] == 2025
    assert exc_info.value.context["period"] == "0A"
    assert "casilla reference token '01' is ambiguous" in str(exc_info.value.context["casilla_ids"])


def test_runtime_projection_rejects_casilla_binding_id_collision() -> None:
    revision = ModeloRevision.model_validate(
        {
            "id": "2025",
            "localization_key": "test.schema.revision.2025.label",
            "valid_from": date(2025, 1, 1),
            "period_selector": {"years": (2025,), "periods": ("0A",)},
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "casillas": (
                {
                    "id": "01",
                    "number": "01",
                    "localization_keys": ("test.schema.casilla.label",),
                    "section": ("test",),
                    "legal_refs": ("ley-58-2003:art-29",),
                    "source_refs": ("aeat-manual",),
                },
            ),
            "bindings": (
                {
                    "id": "01",
                    "provider": {
                        "kind": "manual_input",
                        "record": "DPA",
                        "field": "test",
                        "offset": 1,
                        "length": 1,
                        "data_type": "integer",
                    },
                    "value": {
                        "data_type": "integer",
                        "channel": "integer",
                    },
                    "legal_refs": ("ley-58-2003:art-29",),
                    "source_refs": ("aeat-manual",),
                },
            ),
        },
    )
    modelo = ModeloDefinition(
        id="999",
        title_localization_key="test.schema.modelo.999.title",
        official_name_localization_key="test.schema.modelo.999.official_name",
        tax_domain=TaxDomain("iva"),
        cadence="annual",
        jurisdiction="ES-AEAT",
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual",),
        revisions={"2025": revision},
    )
    snapshot = RegistrySnapshot(
        modelo=modelo,
        revision=revision,
        filing_year=2025,
        period="0A",
        legal={},
        sources={},
        extraction_profiles={},
        live_cross_references={},
        workbook_parity_refs={},
        verification_expectations={},
        application_links={},
        deadline_windows={},
        filing_schedules={},
        constructs={},
        dependency_classifications={},
    )

    with pytest.raises(ModeloBuilderError) as exc_info:
        collection_from_snapshot(snapshot)

    assert exc_info.value.translated_message == "application.filing.runtime.errors.ambiguous_casilla_schema"
    assert exc_info.value.context is not None
    assert "duplicate registry id '01' shared by casilla, binding" in str(exc_info.value.context["casilla_ids"])
