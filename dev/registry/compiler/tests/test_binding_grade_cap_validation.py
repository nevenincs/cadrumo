"""Registry build refuses a binding grade cap that cannot narrow, cite, reach or agree.

Each refusal is exercised on one isolated defect: a copy of the compiled
Modelo 130 revision, or of another compiled revision, with exactly one
declaration changed in memory. The live corpus caps no binding since the
withholding credits were promoted, so the Modelo 130 copy re-declares the cap
on casilla 06's binding, where it was first declared. The live corpus and that
copy are the passing controls, so a rule that refused everything, or nothing,
fails here. Nothing in the bundled registry tree is read for writing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cadrumo.core.authority_grade import BindingGradeCapReason, RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.binding_grade_cap import BindingGradeCap
from cadrumo.domain.calculations.registry.binding_provider_registration import BINDING_PROVIDER_REGISTRATIONS
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision
from cadrumo.domain.calculations.registry.tests.grade_cap_support import recapped_revision

from ..validate_binding_grade_caps import validate_binding_grade_cap_section

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
    from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_CAPPED_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"
_INCOME_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"
_CAP_LEGAL_REF = "rd-439-2007:art-79"


def _published_m130(authority: ValidatedRegistryAuthority) -> ModeloRevision:
    (modelo,) = [modelo for modelo in authority.modelos if modelo.id == "130"]
    return modelo.revisions[str(open_ended_revision("130").id)]


def _m130(authority: ValidatedRegistryAuthority) -> ModeloRevision:
    """The compiled Modelo 130 revision with casilla 06's binding capped in memory."""
    return recapped_revision(_published_m130(authority), _CAPPED_BINDING, _cap())


def _failures(
    authority: ValidatedRegistryAuthority, revision: ModeloRevision, *, without: tuple[str, ...] = ()
) -> list[str]:
    legal = {ref: entry for ref, entry in authority.catalogues.legal.items() if ref not in without}
    return validate_binding_grade_cap_section(prefix="modelo 130", revision=revision, legal_refs=legal)


def _with_bindings(revision: ModeloRevision, bindings: tuple[BindingDefinition, ...]) -> ModeloRevision:
    return revision.model_copy(update={"bindings": bindings})


def _cap() -> BindingGradeCap:
    return BindingGradeCap(
        grade=RegistryAuthorityGrade.CALCULATION,
        reason=BindingGradeCapReason.IMPUTATION_PERIOD_UNGROUNDED,
        legal_refs=(_CAP_LEGAL_REF,),
    )


def test_every_compiled_revision_passes_and_a_declared_modelo_130_cap_is_admitted(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    """The passing controls: the live corpus caps nothing, and a well-formed cap on casilla 06 is admitted."""
    published = _published_m130(_worker_compiled_authority)
    assert not [binding.id for binding in published.bindings if binding.grade_cap is not None]
    assert _failures(_worker_compiled_authority, _m130(_worker_compiled_authority)) == []
    for modelo in _worker_compiled_authority.modelos:
        for revision_id, candidate in modelo.revisions.items():
            assert (
                validate_binding_grade_cap_section(
                    prefix=f"{modelo.id} {revision_id}",
                    revision=candidate,
                    legal_refs=_worker_compiled_authority.catalogues.legal,
                )
                == []
            )


@pytest.mark.parametrize("grade", [RegistryAuthorityGrade.CALCULATION, RegistryAuthorityGrade.APPLICABILITY])
def test_a_cap_on_a_revision_that_already_stops_at_or_below_it_is_refused(
    _worker_compiled_authority: ValidatedRegistryAuthority, grade: RegistryAuthorityGrade
) -> None:
    revision = _m130(_worker_compiled_authority).model_copy(update={"authority_grade": grade})

    (failure,) = _failures(_worker_compiled_authority, revision)

    assert f"binding {_CAPPED_BINDING} grade_cap" in failure
    assert "a cap must narrow the revision's reach" in failure


def test_a_cap_on_a_provider_kind_with_no_executable_resolver_is_refused(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    """A deferred or non-runtime kind produces no value, so a cap on it would narrow nothing."""
    unexecuted = None
    for modelo in _worker_compiled_authority.modelos:
        for candidate in modelo.revisions.values():
            if candidate.effective_authority_grade is not RegistryAuthorityGrade.FILING:
                continue
            for binding in candidate.bindings:
                registration = BINDING_PROVIDER_REGISTRATIONS.get(binding.source)
                if registration is not None and registration.disposition != "filing_grade":
                    unexecuted = (candidate, binding)
                    break
            if unexecuted is not None:
                break
        if unexecuted is not None:
            break
    assert unexecuted is not None, "the corpus keeps a filing-grade revision with a non-executable binding"
    candidate, binding = unexecuted
    capped = binding.model_copy(update={"grade_cap": _cap()})
    revision = _with_bindings(
        candidate, tuple(capped if item.id == binding.id else item for item in candidate.bindings)
    )

    failures = _failures(_worker_compiled_authority, revision)

    assert any(
        f"binding {binding.id} grade_cap is declared on provider kind {binding.source.value!r}" in failure
        for failure in failures
    ), failures


def test_a_cap_citing_a_provision_the_legal_catalogue_lacks_is_refused(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    revision = _m130(_worker_compiled_authority)

    (failure,) = _failures(_worker_compiled_authority, revision, without=(_CAP_LEGAL_REF,))

    assert _CAP_LEGAL_REF in failure
    assert f"binding {_CAPPED_BINDING} grade_cap" in failure


def test_a_cap_whose_binding_reaches_no_casilla_is_refused(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    """Casilla 06 is reached only through the governed routing fact; without the box the cap withholds nothing."""
    original = _m130(_worker_compiled_authority)
    revision = original.model_copy(
        update={"casillas": tuple(casilla for casilla in original.casillas if str(casilla.id) != "06")}
    )

    (failure,) = _failures(_worker_compiled_authority, revision)

    assert f"binding {_CAPPED_BINDING} grade_cap reaches no casilla" in failure


def test_a_reviewed_alternate_whose_cap_differs_from_its_primary_is_refused(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    original = _m130(_worker_compiled_authority)
    casillas = tuple(
        casilla.model_copy(update={"alternate_bindings": (_CAPPED_BINDING,)})
        if casilla.input_kind is InputKind.BOUND and casilla.binding == _INCOME_BINDING
        else casilla
        for casilla in original.casillas
    )
    revision = original.model_copy(update={"casillas": casillas})

    (failure,) = _failures(_worker_compiled_authority, revision)

    assert f"alternate binding {_CAPPED_BINDING!r} declares grade cap" in failure
    assert f"primary binding {_INCOME_BINDING!r}" in failure
