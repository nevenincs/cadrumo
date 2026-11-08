"""The shipped Modelo 111 colegio concertado requirement, judged on the committed sources.

The header mark is about the payroll of a centro docente concertado's teaching
staff paid by the Administración in pago delegado. The design in force across
the supported filing years is the 2019-y-siguientes record design
(``aeat-dr-111-2019-v18``), whose field 44 sits at position 552, length 1, An,
"X" o blanco; the mark first appeared in the 2012-2015 design
(``aeat-dr-111-2012``, position 732). The committed profile schema therefore
conditions the requirement on the two facts that decide whether the mark can
apply: the declarant pays employees, and one of the declared activities is
classified in the IAE enseñanza groups.

Read through the committed registry sources rather than the published authority,
because the declaration under test is a source change that no publication has
consumed yet. The schema comes from the committed TOML and the payer fact, IAE
group set and modelo revisions from the compiled authored sources, so what
passes here is what the runtime will read once the authority is republished.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.user_profile.modelo_scoped_conditions import (
    ModeloScopedRequirementState,
    field_declaring_selector,
    modelo_scoped_requirement,
)
from cadrumo.core.modelo import Modelo
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.text_fold import normalise_corpus_text
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.iva_regime_vocabulary import require_iva_regime
from cadrumo.domain.contribuyente.entity_type import require_entity_type
from cadrumo.domain.deadlines.models import TaxpayerProfile
from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition
from dev.registry.compiler.authority import admitted_revision_id
from dev.registry.compiler.loader import load_shared_catalogues
from dev.registry.compiler.validate_evidence import EvidenceValidator

from .profile_schema_support import committed_supported_filing_years, load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("governed_fact_scope")]

_SELECTOR = "colegio_concertado"
_EXPORT_FIELD_ID = "modelo-111-page-01-colegio-concertado"
_CURRENT_DESIGN_SOURCE = "aeat-dr-111-2019-v18"
_ORIGIN_DESIGN_SOURCE = "aeat-dr-111-2012"
_CURRENT_DESIGN_OFFSET = 552
#: The design row the current source carries, as the bundled extraction renders it.
_CURRENT_DESIGN_LINE = (
    '44 | 552 | 1 | An | Reservado. Administración presentando declaración de Colegio Concertado (CC) | "X" o blanco'
)
#: What survives the .xls source's own lossy encoding, so the citation is read
#: from the cited artifact rather than only from its extraction. The accented
#: words in the row above decode to replacement characters in the workbook
#: bytes, so quoting the whole row against the source would assert a shape the
#: source does not have.
_CURRENT_DESIGN_SOURCE_FRAGMENT = "Colegio Concertado (CC)"
_SUPPORTED_YEARS = tuple(committed_supported_filing_years().years)
_FIELD_PATH = "withholding.colegio_concertado"
_HAS_EMPLOYEES_PATH = "withholding.has_employees"
_EPIGRAPH_PATH = "activities.iae_epigraph"
#: A tax adviser's activity (IAE 849.7 group 849) and a reglada teaching one (931.1).
_CONSULTANT_EPIGRAPH = "849.7"
_TEACHING_EPIGRAPH = "931.1"
_EFFECTIVE = date(2025, 3, 31)


def _schema() -> ProfileSchemaDefinition:
    return load_user_profile_schema()


def _profile(
    *,
    has_employees: bool | None,
    epigraphs: tuple[str | None, ...],
) -> TaxpayerProfile:
    """A natural person with economic-activity income, as the defect's consultant is."""
    return TaxpayerProfile(
        tax_id="00000000T",
        entity_type=require_entity_type("natural_person"),
        iva_regime=require_iva_regime("GENERAL"),
        has_employees=has_employees,
        activity_iae_epigraphs=epigraphs,
    )


def _requirement(profile: TaxpayerProfile) -> ModeloScopedRequirementState:
    schema = _schema()
    field = field_declaring_selector(schema, _SELECTOR)
    assert field is not None, "the committed schema must declare the colegio concertado field"
    return modelo_scoped_requirement(
        field,
        profile=profile,
        schema=schema,
        effective_date=_EFFECTIVE,
    ).state


def _colegio_concertado_export_field(authority: ValidatedRegistryAuthority, filing_year: int):
    """Return the colegio concertado export field of the 111 revision that year resolves to."""
    revision_id = admitted_revision_id(authority, "111", filing_year=filing_year, period="1T")
    revision = authority.modelo("111").revisions[revision_id]
    return next(
        (
            field
            for layout in revision.export_layouts
            for record in layout.records
            for field in record.fields
            if field.id == _EXPORT_FIELD_ID
        ),
        None,
    )


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_every_supported_year_resolves_a_revision_whose_header_cites_its_design(
    _worker_compiled_authority: ValidatedRegistryAuthority,
    filing_year: int,
) -> None:
    """The condition narrows a requirement the design still has a position for, in every supported year.

    The years are enumerated from the registry's own envelope, and the revision
    for each is the one ``revision_temporal_resolution`` admits, so a year
    calculated by projection is checked against the edition it projects from
    rather than skipped.
    """
    field = _colegio_concertado_export_field(_worker_compiled_authority, filing_year)

    assert field is not None, f"{filing_year} resolves a 111 revision without the colegio concertado field"
    assert field.offset == _CURRENT_DESIGN_OFFSET
    assert field.length == 1
    assert _CURRENT_DESIGN_SOURCE in field.source_refs


def test_the_current_design_source_carries_the_row_the_field_is_read_from() -> None:
    """The citation is checked against the cited artifact, not against its description."""
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    validator = EvidenceValidator(legal_refs={}, source_refs=catalogues.sources, source_root=bundled_path())

    source_text = validator.source_text(catalogues.sources[_CURRENT_DESIGN_SOURCE])

    assert source_text is not None
    assert normalise_corpus_text(_CURRENT_DESIGN_SOURCE_FRAGMENT) in source_text
    extraction = bundled_path(
        "corpus",
        "aeat_official",
        "disenos_registro",
        "modelo_111",
        "files",
        "01-111-orden-eha-3127-2009-ejercicios-2019-y-siguientes-actualizado-mayo-2021-179-kb-xls.xls.extracted.md",
    )
    assert _CURRENT_DESIGN_LINE in extraction.read_text(encoding="utf-8")


def test_the_schema_field_cites_the_current_design_and_the_one_the_mark_came_from() -> None:
    field = field_declaring_selector(_schema(), _SELECTOR)

    assert field is not None
    assert field.source_refs == (_CURRENT_DESIGN_SOURCE, _ORIGIN_DESIGN_SOURCE)


def test_the_committed_schema_conditions_the_requirement_rather_than_demanding_it_of_everyone() -> None:
    schema = _schema()
    field = field_declaring_selector(schema, _SELECTOR)

    assert field is not None
    assert Modelo("111") in field.required_for_modelos
    assert field.required_for_modelos_when_payer_facts == ("pays_employees",)
    assert field.required_for_modelos_when_activity_iae_groups_fact == "rdleg-1175-1990:iae-grupos-ensenanza"
    assert field.required_for_modelos_when_activity_iae_epigraph_path == _EPIGRAPH_PATH


def test_a_consultant_with_no_employees_owes_nothing() -> None:
    """The defect: this profile was refused Modelo 111 for an irrelevant prerequisite."""
    state = _requirement(_profile(has_employees=False, epigraphs=(_CONSULTANT_EPIGRAPH,)))

    assert state is ModeloScopedRequirementState.DERIVED_ABSENT


def test_a_teaching_centre_that_pays_employees_owes_the_attestation() -> None:
    state = _requirement(_profile(has_employees=True, epigraphs=(_TEACHING_EPIGRAPH,)))

    assert state is ModeloScopedRequirementState.REQUIRED


def test_an_employer_outside_the_ensenanza_groups_owes_nothing() -> None:
    state = _requirement(_profile(has_employees=True, epigraphs=(_CONSULTANT_EPIGRAPH,)))

    assert state is ModeloScopedRequirementState.DERIVED_ABSENT


def test_one_teaching_activity_among_several_is_enough_to_owe_it() -> None:
    state = _requirement(
        _profile(has_employees=True, epigraphs=(_CONSULTANT_EPIGRAPH, _TEACHING_EPIGRAPH)),
    )

    assert state is ModeloScopedRequirementState.REQUIRED


def test_an_unstated_employee_answer_owes_that_answer_instead() -> None:
    schema = _schema()
    field = field_declaring_selector(schema, _SELECTOR)
    assert field is not None

    requirement = modelo_scoped_requirement(
        field,
        profile=_profile(has_employees=None, epigraphs=(_TEACHING_EPIGRAPH,)),
        schema=schema,
        effective_date=_EFFECTIVE,
    )

    assert requirement.state is ModeloScopedRequirementState.DEFERRED
    assert requirement.deferred_paths == (_HAS_EMPLOYEES_PATH,)
    assert _FIELD_PATH not in requirement.deferred_paths


def test_an_unclassified_activity_owes_its_epigraph_instead() -> None:
    schema = _schema()
    field = field_declaring_selector(schema, _SELECTOR)
    assert field is not None

    requirement = modelo_scoped_requirement(
        field,
        profile=_profile(has_employees=True, epigraphs=(None,)),
        schema=schema,
        effective_date=_EFFECTIVE,
    )

    assert requirement.state is ModeloScopedRequirementState.DEFERRED
    assert requirement.deferred_paths == (_EPIGRAPH_PATH,)
