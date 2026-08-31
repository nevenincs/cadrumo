"""No binding that reads an enrolled observation may name a skippable casilla.

Non-numeric casillas are skipped rather than fatal. That is only safe because no
consumer of an enrolled observation substitutes a zero for one it cannot find --
and two consumers DO substitute zeros: the declared-optional previous-filing
carry, and two derived Modelo 303 fields. They are unreachable from the skippable
set today, so a skip can never become a fabricated declaration.

"Unreachable today" is a property of the current registry bindings, not an
invariant, and the act that would break it is entirely ordinary: authoring a
``previous_filing`` or ``relation_prefill`` binding that names a text or boolean
casilla. No reviewer would catch it, because nothing else says it matters. This
gate is what says it.

Only those two source kinds read an enrolled observation. A ``manual_input``
binding resolves from operator input and never touches one, so an id-level match
against one is not reachability -- measured: Modelo 100 casilla ``0168`` matches
by id across three revisions and is a ``manual_input`` boolean, which is why this
gate filters by source rather than by name.
"""

from __future__ import annotations

import pytest

from ......core.casilla_value_kind import CasillaValueKind
from ......core.resources.bundled_data import bundled_path
from ......domain.calculations.registry.authority import bundled_authority
from ......domain.calculations.registry.binding_selector_utils import selector_as_dict
from ......domain.calculations.registry.export_parse import xml_dictionary_entries
from ..declarations_observations import _observed_value_kind

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

#: Binding sources that resolve from an enrolled ``RegistryModeloObservation``.
_OBSERVATION_READING_SOURCES = frozenset({"previous_filing", "relation_prefill"})
_NUMERIC_DICTIONARY_PREFIX = ("N", "P")
#: Revisions with any non-numeric casilla, so the gate has subjects to check.
_SUBJECTS = (("100", 2023, "0A"), ("100", 2024, "0A"), ("100", 2025, "0A"), ("180", 2024, "0A"))


def _skippable_casilla_ids(modelo: str, year: int, period: str) -> set[str]:
    snapshot = bundled_authority().snapshot(modelo, filing_year=year, period=period)
    skippable: set[str] = set()
    for layout in snapshot.revision.export_layouts:
        if str(layout.format).endswith("xml_dictionary"):
            entries = xml_dictionary_entries(layout, source_root=bundled_path(), sources=snapshot.sources)
            skippable.update(
                entry.casilla_id
                for entry in entries
                if entry.casilla_id is not None and not entry.data_type.upper().startswith(_NUMERIC_DICTIONARY_PREFIX)
            )
            continue
        for record in layout.records:
            skippable.update(
                field.casilla_id
                for field in record.fields
                if field.casilla_id is not None and field.data_type in {"text", "date", "boolean"}
            )
    return skippable


def _observation_read_casilla_ids(modelo: str, year: int, period: str) -> set[str]:
    snapshot = bundled_authority().snapshot(modelo, filing_year=year, period=period)
    referenced: set[str] = set()
    for binding in snapshot.revision.bindings:
        if str(binding.source).split(".")[-1] not in _OBSERVATION_READING_SOURCES:
            continue
        for key, value in selector_as_dict(binding).items():
            if "casilla" not in key.lower():
                continue
            if isinstance(value, str):
                referenced.add(value)
            elif isinstance(value, list | tuple):
                referenced.update(item for item in value if isinstance(item, str))
    return referenced


def test_gate_has_subjects_and_its_classifier_fires() -> None:
    """Neither side may be silently empty, or this gate passes forever.

    A registry refactor that emptied the skippable set, or a rename that stopped
    matching the source kinds, would leave the check green over any violation.
    """
    skippable_total = sum(len(_skippable_casilla_ids(*subject)) for subject in _SUBJECTS)
    assert skippable_total > 0, "no revision reports a skippable casilla; the reachability check below is vacuous"
    assert _observed_value_kind("free text") is CasillaValueKind.TEXT, "the skippable classifier no longer classifies"


@pytest.mark.parametrize(("modelo", "year", "period"), _SUBJECTS)
def test_no_observation_reading_binding_names_a_skippable_casilla(modelo: str, year: int, period: str) -> None:
    """A skipped casilla must never be a value some binding expected to find."""
    reachable = sorted(
        _skippable_casilla_ids(modelo, year, period) & _observation_read_casilla_ids(modelo, year, period)
    )

    assert reachable == [], (
        f"modelo {modelo} revision for {year}/{period} has previous_filing or relation_prefill binding(s) "
        f"naming casilla(s) that the observation channel skips: {reachable}.\n\n"
        "A skipped casilla is absent from the enrolled observation, and the carry path substitutes zero for an "
        "absent declared-optional source -- so this would file a fabricated zero rather than the taxpayer's value.\n\n"
        "Resolve it by making the casilla numeric, or by stopping the binding from reading it. Do NOT add the "
        "casilla to a carve-out: an exemption here reinstates exactly the silent zero this gate exists to prevent."
    )
