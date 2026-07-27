"""The pre-write completeness gate panics on a structurally-thin fichero-BOE.

A fixed-width ``.boe`` always occupies every field's byte slot, so a required
casilla the draft omits renders as a blank slot behind a valid SHA-256 digest.
``assert_export_mirrors_manifest`` runs before the bytes are written and refuses
that thin file with a loud, enumerated ``FilingExportError``. The gate does not
apply to the ``xml_dictionary`` transport, where an absent casilla is a
legitimately-absent optional element rather than a blank slot.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.filing import FilingExportError, ModeloDraft, ModeloValueKind
from .._export import export_draft
from ..runtime import RegistrySchemaAccessor
from ._export_support import (
    _approved_modelo_390_registry_draft,
    _approved_registry_draft,
    _modelo_130_export_headers,
    _modelo_390_export_headers,
    _required_set_partition,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True)
class _CompletenessGateCase:
    modelo: str
    draft_factory: Callable[[], ModeloDraft]
    headers_factory: Callable[[], dict[str, str]]
    provider_factory: Callable[[], RegistrySchemaAccessor]
    output_name: str


def _modelo_130_case() -> _CompletenessGateCase:
    return _CompletenessGateCase(
        modelo="130",
        draft_factory=_approved_registry_draft,
        headers_factory=_modelo_130_export_headers,
        provider_factory=_schema_provider,
        output_name="modelo-130.txt",
    )


def _modelo_390_case() -> _CompletenessGateCase:
    return _CompletenessGateCase(
        modelo="390",
        draft_factory=_approved_modelo_390_registry_draft,
        headers_factory=_modelo_390_export_headers,
        provider_factory=lambda: _schema_provider(filing_year=2025, period="0A", modelos=("390",)),
        output_name="modelo-390.txt",
    )


_COMPLETENESS_GATE_CASES = (
    pytest.param(_modelo_130_case, id="modelo-130"),
    pytest.param(_modelo_390_case, id="modelo-390"),
)


def _valued_casilla_ids(draft: ModeloDraft) -> set[CasillaId]:
    """Return the casillas the draft carries a real value for (EMPTY rows excluded)."""
    return {value.casilla_id for value in draft.values if value.value is not None}


def _emptied_draft(draft: ModeloDraft, casilla_id: CasillaId) -> ModeloDraft:
    """Return ``draft`` with ``casilla_id`` demoted to the production EMPTY shape.

    The casilla id stays present in ``draft.values`` -- that is the real production
    thin state, since ``build_draft`` emits a row for every declared casilla and
    marks an unsupplied one EMPTY (``value=None``). Only the value goes away, so the
    slot would render blank on disk.
    """
    thin_values = tuple(
        value.model_copy(update={"value": None, "kind": ModeloValueKind.EMPTY})
        if value.casilla_id == casilla_id
        else value
        for value in draft.values
    )
    thin_draft: ModeloDraft = draft.model_copy(update={"values": thin_values})
    assert casilla_id in {value.casilla_id for value in thin_draft.values}
    return thin_draft


@pytest.mark.parametrize("case_factory", _COMPLETENESS_GATE_CASES)
def test_complete_fixed_width_draft_exports_without_panic(
    tmp_path: Path,
    case_factory: Callable[[], _CompletenessGateCase],
) -> None:
    case = case_factory()
    provider = case.provider_factory()
    draft = case.draft_factory()
    output = tmp_path / case.output_name

    receipt = export_draft(draft, output_path=output, headers=case.headers_factory(), schema_provider=provider)

    assert output.exists()
    assert receipt.file_sha256


@pytest.mark.parametrize("case_factory", _COMPLETENESS_GATE_CASES)
def test_thin_fixed_width_draft_panics_before_writing(
    tmp_path: Path,
    case_factory: Callable[[], _CompletenessGateCase],
) -> None:
    # Reproduce the REAL production thin state, not an artificial one: build_draft
    # emits a ModeloValue for every declared casilla and marks an unsupplied one
    # EMPTY (value=None), so its id is present in draft.values even though it would
    # render as a blank slot. The gate must key on value presence, not id
    # membership, so setting a required-applicable casilla to EMPTY must panic.
    #
    # The emptied casilla is chosen from the registry-derived partition, NOT from
    # the production required-set derivation: picking it from the subject would make
    # this test follow a relaxed predicate to a casilla that predicate still
    # requires, so it would keep passing while a required casilla silently left the
    # gate. Both required classes are exercised where the revision declares them, so
    # relaxing either clause of the predicate strands a witness this test empties.
    case = case_factory()
    provider = case.provider_factory()
    draft = case.draft_factory()
    headers = case.headers_factory()
    layout = provider.get_subview(case.modelo).export_layouts[0]
    oracle = _required_set_partition(modelo=case.modelo, provider=provider, layout=layout, headers=headers)
    valued = _valued_casilla_ids(draft)

    exercised: list[str] = []
    for class_name, class_ids in (
        ("calculation-result", oracle.calculation_results),
        ("schema-required", oracle.schema_required_inputs),
    ):
        candidates = sorted(class_ids & valued)
        if not candidates:
            continue
        emptied = candidates[0]
        output = tmp_path / f"{case.modelo}-thin-{class_name}.txt"

        with pytest.raises(FilingExportError) as exc_info:
            export_draft(_emptied_draft(draft, emptied), output_path=output, headers=headers, schema_provider=provider)

        # The panic names the emptied casilla and never writes the thin file.
        assert emptied in str(exc_info.value), (class_name, emptied)
        assert "structurally-thin" in str(exc_info.value), class_name
        assert not output.exists(), class_name
        exercised.append(class_name)

    assert exercised, (
        f"modelo {case.modelo}: fixture must carry a value for at least one required-applicable casilla, "
        f"otherwise this gate assertion is vacuous"
    )


def test_schema_required_formula_less_casilla_panics_when_emptied(tmp_path: Path) -> None:
    # End-to-end pin for the second clause of the required-set predicate, on the
    # revision that exercises it. Modelo 130 casilla 02 (gastos) declares no formula
    # -- the taxpayer supplies it -- but the registry marks it required, so a blank
    # slot for it is an omission, not a valid zero. The parametrized thin-draft test
    # above covers whichever class the fixture happens to populate; this one names
    # the class directly, so relaxing the predicate to formulas alone cannot be
    # absorbed by falling through to a formula casilla the relaxed gate still
    # catches. Its qualification is read from the registry, never assumed from the id.
    modelo = "130"
    casilla = validated_casilla_id("02", surface="test_export_completeness_gate.schema_required_anchor")
    provider = _schema_provider(modelos=(modelo,))
    draft = _approved_registry_draft()
    headers = _modelo_130_export_headers()
    layout = provider.get_subview(modelo).export_layouts[0]

    schema = provider.get_collection(modelo).get(casilla)
    assert schema is not None, f"modelo {modelo}: casilla {casilla} is absent from the registry collection"
    assert schema.formula is None, (
        f"modelo {modelo}: casilla {casilla} now declares a formula, so it no longer witnesses the "
        f"schema-required clause; re-anchor this test on a required, formula-less casilla"
    )
    assert schema.required, (
        f"modelo {modelo}: casilla {casilla} is no longer registry-required, so it no longer witnesses the "
        f"schema-required clause; re-anchor this test on a required, formula-less casilla"
    )
    oracle = _required_set_partition(modelo=modelo, provider=provider, layout=layout, headers=headers)
    assert casilla in oracle.schema_required_inputs
    assert casilla in _valued_casilla_ids(draft), (
        f"modelo {modelo}: fixture must supply casilla {casilla} for this thin-state reproduction to bite"
    )

    output = tmp_path / f"{modelo}-schema-required-thin.txt"

    with pytest.raises(FilingExportError) as exc_info:
        export_draft(_emptied_draft(draft, casilla), output_path=output, headers=headers, schema_provider=provider)

    assert casilla in str(exc_info.value)
    assert "structurally-thin" in str(exc_info.value)
    assert not output.exists()
