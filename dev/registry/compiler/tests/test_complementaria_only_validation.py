"""Registry build refuses a complementaria-only declaration it cannot ground.

Each refusal is exercised on one isolated defect: a copy of the compiled
Modelo 130 or 131 revision with exactly one declaration changed in memory. The
live corpus is the passing control, so a rule that refused everything, or
nothing, fails here. Nothing in the bundled registry tree is read for writing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema_base import SourceCitation
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition, ComplementariaOnlyDeclaration
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions, open_ended_revision

from ..validate_complementaria_only_casillas import validate_complementaria_only_section
from ..validate_evidence import EvidenceValidator

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
    from cadrumo.domain.calculations.registry.schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_M130_REVISION = str(open_ended_revision("130").id)
_M131_REVISIONS = tuple(str(revision.id) for revision in authored_revisions("131"))


def _revision(authority: ValidatedRegistryAuthority, modelo_id: str, revision_id: str) -> ModeloRevision:
    (modelo,) = [modelo for modelo in authority.modelos if modelo.id == modelo_id]
    return modelo.revisions[revision_id]


def _failures(authority: ValidatedRegistryAuthority, revision: ModeloRevision) -> list[str]:
    sources = authority.catalogues.sources
    evidence = EvidenceValidator(
        legal_refs=authority.catalogues.legal,
        source_refs=sources,
        source_root=bundled_path(),
    )
    return validate_complementaria_only_section(
        prefix="modelo",
        revision=revision,
        source_refs=sources,
        evidence=evidence,
    )


def _complementaria_only_ids(revision: ModeloRevision) -> list[str]:
    return [str(casilla.id) for casilla in revision.casillas if casilla.complementaria_only is not None]


def _with_casilla(revision: ModeloRevision, casilla_id: str, **changes: object) -> ModeloRevision:
    casillas = tuple(
        casilla.model_copy(update=changes) if str(casilla.id) == casilla_id else casilla
        for casilla in revision.casillas
    )
    return revision.model_copy(update={"casillas": casillas})


def test_every_compiled_revision_passes_and_the_two_result_carries_are_declared(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    """The passing control: Modelo 130 casilla 18 and Modelo 131 casilla 14 alone are declared."""
    authority = _worker_compiled_authority
    assert _complementaria_only_ids(_revision(authority, "130", _M130_REVISION)) == ["18"]
    for modelo in authority.modelos:
        for revision_id, candidate in modelo.revisions.items():
            assert _failures(authority, candidate) == [], (modelo.id, revision_id)
            if modelo.id not in {"130", "131"}:
                assert _complementaria_only_ids(candidate) == [], (modelo.id, revision_id)


@pytest.mark.parametrize("revision_id", _M131_REVISIONS)
def test_modelo_131_casilla_14_inherits_the_declaration_into_every_revision(
    _worker_compiled_authority: ValidatedRegistryAuthority, revision_id: str
) -> None:
    """Authored once at the 2019-2023 baseline, the declaration reaches every later edition."""
    assert _complementaria_only_ids(_revision(_worker_compiled_authority, "131", revision_id)) == ["14"]


def test_a_citation_the_source_does_not_contain_is_refused(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    original = _revision(_worker_compiled_authority, "130", _M130_REVISION)
    declaration = ComplementariaOnlyDeclaration(
        source_refs=("aeat-modelo-130-instructions",),
        source_citations=(
            SourceCitation(
                source_ref="aeat-modelo-130-instructions",
                required_text=("casilla que solo rellena una declaracion original",),
            ),
        ),
    )
    revision = _with_casilla(original, "18", complementaria_only=declaration)

    (failure,) = _failures(_worker_compiled_authority, revision)

    assert "casilla 18 complementaria_only source citation 'aeat-modelo-130-instructions' missing text" in failure


def test_a_source_absent_from_the_catalogue_is_refused(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    original = _revision(_worker_compiled_authority, "130", _M130_REVISION)
    declaration = ComplementariaOnlyDeclaration(
        source_refs=("no-such-source",),
        source_citations=(SourceCitation(source_ref="no-such-source", required_text=("Casilla 18.",)),),
    )
    revision = _with_casilla(original, "18", complementaria_only=declaration)

    failures = _failures(_worker_compiled_authority, revision)

    assert any("no-such-source" in failure and "casilla 18 complementaria_only" in failure for failure in failures)


def test_a_source_below_official_guidance_tier_is_refused(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    """The record design is layout authority, not guidance that can prove a value zero."""
    original = _revision(_worker_compiled_authority, "130", _M130_REVISION)
    declaration = ComplementariaOnlyDeclaration(
        source_refs=("aeat-dr-130-2019-v12",),
        source_citations=(SourceCitation(source_ref="aeat-dr-130-2019-v12", required_text=("complementaria",)),),
    )
    revision = _with_casilla(original, "18", complementaria_only=declaration)

    failures = _failures(_worker_compiled_authority, revision)

    assert any("official_source_guidance" in failure for failure in failures), failures


def test_a_required_casilla_is_refused(_worker_compiled_authority: ValidatedRegistryAuthority) -> None:
    original = _revision(_worker_compiled_authority, "130", _M130_REVISION)
    revision = _with_casilla(original, "18", required=True)

    (failure,) = _failures(_worker_compiled_authority, revision)

    assert "casilla 18 complementaria_only is declared on a required casilla" in failure


def test_the_schema_refuses_the_declaration_on_a_computed_or_non_money_casilla(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    revision = _revision(_worker_compiled_authority, "130", _M130_REVISION)
    (carry,) = [casilla for casilla in revision.casillas if str(casilla.id) == "18"]
    (computed,) = [casilla for casilla in revision.casillas if str(casilla.id) == "19"]
    payload = computed.model_dump(mode="python") | {
        "localization_keys": computed.localization_keys,
        "complementaria_only": carry.complementaria_only,
    }

    with pytest.raises(ValidationError, match="must be an operator-entered casilla"):
        CasillaDefinition.model_validate(payload)
    assert computed.input_kind is InputKind.COMPUTED

    text_payload = carry.model_dump(mode="python") | {
        "localization_keys": carry.localization_keys,
        "data_type": "text",
    }
    with pytest.raises(ValidationError, match="must be a money casilla"):
        CasillaDefinition.model_validate(text_payload)
