"""The M369 source declares a declarant prefix and three disjoint body ranges."""

from __future__ import annotations

import json

import pytest

from cadrumo.application.filing.export_envelope import envelope_closer_bytes, render_declared_prefix
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_exports import (
    FilingEnvelopeDefinition,
    FilingEnvelopePrefixFieldDeclaration,
)
from cadrumo.domain.calculations.registry.schema_exports import (
    FilingEnvelopePrefixRole as R,
)
from cadrumo.domain.filing.errors import FilingExportValidationError

from ...compiler.loader import load_catalogue_file
from ..record_design_intermediate import load_record_design_intermediate
from ..record_design_revision_projection import project_record_design_for_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE_SHA = "b59ade58821e8e0988a1aa4e2a7f52c97b21375fc0a6720d76ca0601a7c8b1a3"
_ROLES = (
    (R.OPENING_TAG, 2),
    (R.MODELO, 3),
    (R.DISCRIMINANT, 1),
    (R.FILING_YEAR, 4),
    (R.PERIOD, 2),
    (R.RECORD_TYPE, 5),
    (R.PRE_DECLARANT_FILLER, 92),
    (R.DECLARANT_TAX_ID, 9),
    (R.POST_DECLARANT_FILLER, 210),
)


def _declaration(*, roles: tuple[tuple[R, int], ...] = _ROLES) -> FilingEnvelopeDefinition:
    return FilingEnvelopeDefinition(
        source_ref="aeat-dr-369-2021",
        source_sha256=_SOURCE_SHA,
        record_identity="T3690 Estruc. gral",
        prefix_fields=tuple(FilingEnvelopePrefixFieldDeclaration(role=role, length=length) for role, length in roles),
        prefix_extent=328,
        body_record_ids=("m369-body",),
        product_identity_requirement=None,
        closer_derivation="relative-closer-v1",
        total_derivation="emitted-byte-total-v1",
    )


def test_declarant_prefix_and_closer_use_only_source_stated_slots() -> None:
    declaration = _declaration()
    period = Period.from_year_and_code(2025, "1T")
    rendered = render_declared_prefix(
        declaration.prefix_fields,
        prefix_extent=declaration.prefix_extent,
        modelo=Modelo("369"),
        period=period,
        product_software_identity=None,
        declarant_tax_id="Y0000001S",
    )
    assert len(rendered) == 328
    assert rendered[:17] == b"<T369020251T0000>"
    assert rendered[17:109] == b" " * 92
    assert rendered[109:118] == b"Y0000001S"
    assert rendered[118:] == b" " * 210
    assert declaration.closer_for(rendered[:17]) == envelope_closer_bytes(modelo=Modelo("369"), period=period)
    serialised = declaration.model_dump(mode="json", exclude_none=True)
    assert "product_identity_requirement" not in serialised
    assert FilingEnvelopeDefinition.model_validate_json(json.dumps(serialised)) == declaration
    with pytest.raises(ValueError, match="no software identity"):
        FilingEnvelopeDefinition.model_validate_json(
            json.dumps({**serialised, "product_identity_requirement": "aeat-product-software-identity-v1"})
        )
    with pytest.raises(FilingExportValidationError, match="monthly/quarterly"):
        render_declared_prefix(
            declaration.prefix_fields,
            prefix_extent=328,
            modelo=Modelo("369"),
            period=Period.from_year_and_code(2025, "0A"),
            product_software_identity=None,
            declarant_tax_id="Y0000001S",
        )


@pytest.mark.parametrize("quarter", ("1T", "4T"))
def test_exterior_quarter_uses_source_pinned_369_envelope(quarter: str) -> None:
    declaration = _declaration()
    period = Period.from_year_and_code(2025, f"EXT-{quarter}")
    with pytest.raises(FilingExportValidationError, match="exact official Modelo 369 envelope"):
        envelope_closer_bytes(modelo=Modelo("369"), period=period)
    rendered = render_declared_prefix(
        declaration.prefix_fields,
        prefix_extent=declaration.prefix_extent,
        modelo=Modelo("369"),
        period=period,
        product_software_identity=None,
        declarant_tax_id="Y0000001S",
        envelope=declaration,
    )
    assert rendered[:17] == f"<T36902025{quarter}0000>".encode("ascii")
    assert envelope_closer_bytes(modelo=Modelo("369"), period=period, envelope=declaration) == (
        f"</T36902025{quarter}0000>".encode("ascii")
    )
    for changed in (
        declaration.model_copy(update={"source_sha256": "0" * 64}),
        declaration.model_copy(update={"source_ref": "aeat-dr-369-2022"}),
    ):
        with pytest.raises(FilingExportValidationError, match="exact official Modelo 369 envelope"):
            envelope_closer_bytes(modelo=Modelo("369"), period=period, envelope=changed)
    with pytest.raises(FilingExportValidationError, match="exact official Modelo 369 envelope"):
        envelope_closer_bytes(modelo=Modelo("370"), period=period, envelope=declaration)


def test_declarant_prefix_cannot_claim_auxiliary_or_partial_roles() -> None:
    with pytest.raises(ValueError, match=r"canonical source order|nine-role prefix"):
        _declaration(roles=(*_ROLES[:-1], (R.AUX_CLOSING_TAG, 210)))
    with pytest.raises(ValueError, match=r"canonical source order|nine-role prefix"):
        _declaration(roles=(*_ROLES[:7], (R.POST_DECLARANT_FILLER, 9), (R.DECLARANT_TAX_ID, 210)))


@pytest.mark.parametrize(
    "revision,expected",
    (
        ("esquema-exterior", ("T36900 Info Adicional", "T36901 Ext", "T36902 Ext", "T36903 Ext")),
        (
            "esquema-union",
            (
                "T36900 Info Adicional",
                "T36904 Un",
                "T36905 Un",
                "T36906 Un",
                "T36907 Un",
                "T36908 Un",
                "T36909 Un",
            ),
        ),
        ("esquema-importacion", ("T36900 Info Adicional", "T36910 Imp", "T36911 Imp", "T36912 Imp")),
    ),
)
def test_official_body_ranges_project_only_for_the_exact_revision(revision: str, expected: tuple[str, ...]) -> None:
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    intermediate = load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref="aeat-dr-369-2021",
        filing_year=2021,
        design_epoch="2021",
    )
    selected = project_record_design_for_revision(intermediate, revision)
    assert tuple(sheet.record_identity for sheet in selected.sheets) == expected
    assert project_record_design_for_revision(selected, revision) is selected
    with pytest.raises(RegistryValidationError, match="projection requires"):
        other = "esquema-importacion" if revision != "esquema-importacion" else "esquema-union"
        project_record_design_for_revision(selected, other)
    with pytest.raises(RegistryValidationError, match="exact reviewed official source"):
        changed_source = intermediate.source.model_copy(update={"source_sha256": "0" * 64})
        project_record_design_for_revision(
            intermediate.model_copy(update={"source": changed_source}),
            revision,
        )
