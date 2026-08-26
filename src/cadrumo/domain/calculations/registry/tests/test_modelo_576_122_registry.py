"""Registry foundations for the final UNMODELED tail: 576, 122.

576 (IEDMT por matriculacion) now carries a bounded 2007 BOE-form revision and
a separate 2008-onward AEAT fixed-width design revision; its 2007 legal form
does not establish byte geometry. 122 (regularizacion de la deduccion por
familia numerosa/discapacidad) remains the sibling applicability case. Both
have windowless, event/campaign-driven timing rather than fabricated recurring
calendar windows.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test loader for the committed registry definitions and legal catalogues.
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Registry validator that checks the authored legal/source references.
    :class:`~core.TaxDomain`
        Closed tax-family enum extended for the plastico and IEDMT registrations.
    :data:`~core.access_gate.CANONICAL_MODELO_FLEET`
        Canonical fleet membership reached after this final-tail promotion.
    :data:`~core.UNMODELED_OBLIGATIONS`
        Former residual obligation set that this tail reduces to empty.
    :mod:`~domain.calculations.registry.tests.test_modelo_iva_batch4_registry`
        Sibling registry-foundation coverage for windowless IVA promotions.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core import RegistryAuthorityGrade, RevisionReviewStatus, TaxDomain
from .....core.resources import bundled_path
from ..errors import RegistryValidationError
from ..snapshot import build_snapshot, build_validated_snapshot
from ..support_matrix import revision_capability_probe
from ..validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# (modelo_id, revision, approval, plazo, doc, tax_domain)
_MODELOS = [
    (
        "576",
        "2008-y-siguientes",
        "orden-eha-3851-2007:art-1",
        "orden-eha-3851-2007:art-1",
        "BOE-A-2007-22442",
        TaxDomain.IEDMT,
    ),
    (
        "122",
        "2017-y-siguientes",
        "orden-hfp-105-2017:art-5",
        "orden-hfp-105-2017:art-7",
        "BOE-A-2017-1334",
        TaxDomain.IRPF,
    ),
]


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,domain", _MODELOS)
def test_committed_definition_legal_authority_and_windowless_plazo(
    mid: str, rev: str, approval: str, plazo: str, doc: str, domain: TaxDomain
) -> None:
    """Each cadence-dependent tail modelo validates without fabricated deadline windows."""
    modelo, catalogues = _committed_modelo(mid)
    assert modelo.id == mid
    assert modelo.tax_domain is domain
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    for ref in {approval, plazo}:
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == doc

    assert modelo.revisions[rev].deadline_windows == ()


def test_modelo_576_selects_the_2007_form_only_revision_before_the_2008_record_design() -> None:
    """The proven legal form year never acquires the later fixed-width writer."""
    modelo, catalogues = _committed_modelo("576")

    historical = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2007,
        period="0A",
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    design_era = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2008,
        period="0A",
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )

    assert historical.revision.id == "2007"
    assert historical.revision.casillas[0].id == "decl.ejercicio"
    assert historical.revision.constructs == ()
    assert historical.revision.export_layouts == ()
    assert historical.revision.application_links[0].id == "modelo-576-filing"
    assert historical.revision.application_links[0].surface == "filing"
    assert historical.revision.application_links[0].consumer == "cadrumo.application.filing"
    assert historical.revision.workbook_parity_refs[0].source_refs == (
        "boe-modelo-576-2005-form",
    )
    assert set(historical.revision.source_refs) == {
        "boe-modelo-576-2005-form",
        "boe-modelo-576-2005-procedure",
    }
    historical_capability = revision_capability_probe(historical.revision, modelo_id=modelo.id)
    assert not historical_capability.has_fixed_width_export
    assert not historical_capability.has_xml_dictionary_export
    assert not historical_capability.has_extractor
    assert historical_capability.extraction_profile_count == 0

    assert design_era.revision.id == "2008-y-siguientes"
    layout = design_era.revision.export_layouts[0]
    fields = layout.records[0].fields
    assert len(design_era.revision.casillas) == 42
    assert len(design_era.revision.application_links) == 2
    assert layout.source_refs == ("aeat-dr-576-2008",)
    assert len(fields) == 60
    assert max(field.offset + field.length - 1 for field in fields) == 1517


def test_modelo_576_2007_filing_mutation_reaches_the_generic_no_layout_refusal() -> None:
    """Even a hypothetical filing-grade promotion cannot manufacture a 2007 writer."""
    modelo, catalogues = _committed_modelo("576")
    historical = modelo.revisions["2007"]
    promoted = historical.model_copy(
        update={
            "authority_grade": RegistryAuthorityGrade.FILING,
            "review_status": RevisionReviewStatus.OPERATOR_REVIEWED,
            "reviewed_by": "operator",
            "reviewed_at": date(2026, 8, 26),
        },
    )
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, promoted.id: promoted}})

    with pytest.raises(
        RegistryValidationError,
        match=r"modelo 576 revision 2007 declares no export layout",
    ):
        build_validated_snapshot(
            mutated,
            catalogues,
            filing_year=2007,
            period="0A",
            revision_id="2007",
        )
