"""Teeth for export literals resolved statically from a governed fact.

The fixed-record AEAT envelopes bind their entidad-desarrolladora slots to the
development mock software identity fact instead of carrying the values inline.
These cases load COPIES of the shipped Modelo 111 tree through the real loader,
under the governed facts of the bundled tree, and resolve a synthetic catalogue
through the real resolver for the one shape no shipped fact has.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryError, RegistryValidationError
from cadrumo.domain.calculations.registry.export_literal_fact import ExportLiteralFact, resolve_export_literal_fact
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, governed_facts_in_scope
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.filing.software_identity import (
    DEVELOPMENT_MOCK_DEVELOPER_TAX_ID_FACT,
    DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER_FACT,
    AeatSoftwareIdentityGrade,
    development_mock_software_identity,
)

from ...conformance.stamp import bundled_registry_root
from ..loader import load_modelo_directory, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_REVISION = "2019-y-siguientes"
_RECORD = "modelo-111-envelope-header"
_LAYOUT = Path("revisions") / _REVISION / "export_layouts" / "0001-declarations.toml"
_SHIPPED_BINDING = (
    'literal_fact = { fact_id = "aeat-eedd:development-mock-software-identity", key = "developer_tax_id" }\n'
)


def _modelo_111(tmp_path: Path, *, binding: str = _SHIPPED_BINDING) -> Path:
    """Copy the shipped Modelo 111 tree, re-declaring the developer-NIF binding."""
    modelo_dir = tmp_path / "111"
    shutil.copytree(bundled_registry_root() / "modelos" / "111", modelo_dir)
    layout = modelo_dir / _LAYOUT
    text = layout.read_text(encoding="utf-8")
    assert text.count(_SHIPPED_BINDING) == 1
    layout.write_text(text.replace(_SHIPPED_BINDING, binding), encoding="utf-8")
    return modelo_dir


def _envelope_field(modelo_dir: Path, offset: int) -> ExportFieldDefinition:
    revision = load_modelo_directory(modelo_dir).revisions[_REVISION]
    record = next(record for layout in revision.export_layouts for record in layout.records if record.id == _RECORD)
    return next(field for field in record.fields if field.offset == offset)


def test_the_envelope_slots_take_the_development_mock_identity_from_its_fact(tmp_path: Path) -> None:
    """Both EEDD slots carry what the fact declares, and keep the reference they came from."""
    authority = governed_facts_in_scope()
    assert authority is not None
    modelo_dir = _modelo_111(tmp_path)

    program = _envelope_field(modelo_dir, 93)
    developer = _envelope_field(modelo_dir, 101)

    assert program.literal_fact == DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER_FACT
    assert developer.literal_fact == DEVELOPMENT_MOCK_DEVELOPER_TAX_ID_FACT
    assert program.literal == resolve_export_literal_fact(DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER_FACT, authority=authority)
    assert developer.literal == resolve_export_literal_fact(DEVELOPMENT_MOCK_DEVELOPER_TAX_ID_FACT, authority=authority)
    assert (len(program.literal or ""), len(developer.literal or "")) == (program.length, developer.length)


def test_the_envelope_identity_and_the_runtime_mock_are_the_same_identity(tmp_path: Path) -> None:
    """The fixed-record envelopes and the envelope-prefix renderer read one fact, graded as the mock."""
    modelo_dir = _modelo_111(tmp_path)
    mock = development_mock_software_identity()

    assert _envelope_field(modelo_dir, 93).literal == mock.program_identifier
    assert _envelope_field(modelo_dir, 101).literal == mock.developer_tax_id
    assert mock.grade is AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK


def test_an_inline_literal_contradicting_its_fact_is_refused(tmp_path: Path) -> None:
    """An authored value beside the reference must equal what the fact resolves to."""
    planted = _SHIPPED_BINDING + 'literal = "12345678Z"\n'

    with pytest.raises(RegistryError, match="resolves to 'X0000000T'"):
        load_modelo_directory(_modelo_111(tmp_path, binding=planted))


def test_a_reference_to_an_entry_the_fact_does_not_declare_is_refused(tmp_path: Path) -> None:
    """A mistyped key has no value to give, so the layout does not load."""
    planted = _SHIPPED_BINDING.replace('key = "developer_tax_id"', 'key = "developer_nif"')

    with pytest.raises(RegistryError, match="has no text entry 'developer_nif'"):
        load_modelo_directory(_modelo_111(tmp_path, binding=planted))


def test_a_fact_that_changes_within_the_support_envelope_has_no_static_literal() -> None:
    """A value that differs between filing years would be frozen at whichever year was asked."""
    support = load_shared_catalogues(bundled_registry_root()).require_supported_filing_years()
    boundary = support.floor + 1
    variant = {
        "date_axis": "filing_period",
        "source_refs": ["aeat-dr-111-2019-v18"],
        "source_citations": [{"source_ref": "aeat-dr-111-2019-v18", "required_text": ["EEDD"]}],
        "review_status": "agent_reviewed",
        "ownership": "authored",
    }
    fact = GovernedFact.model_validate(
        {
            "fact_id": "test:varying-identity",
            "family": "mapping",
            "variants": [
                {
                    **variant,
                    "variant_id": "test:varying-identity:before",
                    "valid_to": date(boundary - 1, 12, 31),
                    "payload": {"kind": "mapping", "entries": [{"key": "program_identifier", "value": "0000"}]},
                },
                {
                    **variant,
                    "variant_id": "test:varying-identity:after",
                    "valid_from": date(boundary, 1, 1),
                    "payload": {"kind": "mapping", "entries": [{"key": "program_identifier", "value": "0001"}]},
                },
            ],
        },
    )
    authority = CandidateFactAuthority(GovernedFactCatalogue(facts={fact.fact_id: fact}), support)

    with pytest.raises(RegistryValidationError, match="a static literal needs exactly one value"):
        resolve_export_literal_fact(
            ExportLiteralFact(fact_id="test:varying-identity", key="program_identifier"),
            authority=authority,
        )
