"""Official Modelo 194 record boundaries needed for its pending full enrollment."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingProvider

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from ...compiler.record_design import extract_record_design
from ..record_design_intermediate import load_record_design_intermediate
from ..render_profile_loading import load_render_profile
from ..semantic_map import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("filename", "recipient_fields", "territorial_indicator"),
    [
        ("03-194-orden-de-18-de-enero-de-1999-actualizado-por-orden-hac-1276-2019.pdf", 23, False),
        ("02-194-diseno-de-registro-actualizado-en-2023.pdf", 24, True),
        ("01-194-diseno-de-registro-actualizado-en-2024.pdf", 24, True),
    ],
)
def test_exact_source_geometry_preserves_both_base_signs_and_revision_fields(
    filename: str, recipient_fields: int, territorial_indicator: bool
) -> None:
    source = Path("src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_194/files") / filename
    sheets = extract_record_design(source).require_complete()
    assert len(sheets) == 2
    declarant, recipient = sheets
    assert len(declarant.fields) == 17
    assert len(recipient.fields) == recipient_fields
    for sheet in sheets:
        cursor = 1
        for field in sheet.fields:
            assert field.offset == cursor
            cursor += field.length
        assert cursor == 251
    summary = {field.offset: field for field in declarant.fields}
    assert [summary[offset].length for offset in (136, 145, 160, 175, 184)] == [9, 15, 15, 9, 15]
    assert "PERCEPTORES" in summary[136].description
    assert "PERCEPTORES" in summary[175].description
    assert "BASE" in summary[145].description and "BASE" in summary[184].description
    detail = {field.offset: field for field in recipient.fields}
    assert ("CEUTA" in detail[188].description) is territorial_indicator
    assert detail[188].length == (1 if territorial_indicator else 63)
    if not territorial_indicator:
        assert "BLANCOS" in detail[188].description
    assert "CEROS" in detail[144].description
    assert detail[144].length == 13
    assert detail[118].length == detail[131].length == detail[157].length == 13
    assert "ADQUISICIÓN" in detail[118].description
    assert "TRANSMISIÓN" in detail[131].description
    assert "BASE" in detail[157].description


@pytest.mark.parametrize("epoch", ["2019", "2023", "2024"])
def test_semantic_inputs_cover_exact_source_anchors_and_keep_identity_owners(epoch: str) -> None:
    import hashlib
    import tomllib

    mapping = load_semantic_map(Path(f"dev/registry/mappings/modelo_194/{epoch}"))
    catalogue = tomllib.loads(
        Path("src/cadrumo/_data/registry/aeat/legal/enrolled-forms-sources.toml").read_text(encoding="utf-8")
    )
    source = catalogue["sources"][mapping.source_ref]
    path = Path("src/cadrumo/_data") / source["corpus_path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == mapping.source_sha256
    root = Path("src/cadrumo/_data")
    design = load_record_design_intermediate(
        root,
        load_shared_catalogues(root / "registry/aeat").sources,
        source_ref=mapping.source_ref,
        filing_year=int(epoch),
        design_epoch=epoch,
    )
    fields = {(f.sheet, f.source_row, f.ordinal) for s in design.sheets for f in s.fields}
    anchors = {(e.anchor.sheet, e.anchor.source_row, e.anchor.ordinal) for e in mapping.entries}
    assert anchors == fields
    entries = {e.export_field_id: e for e in mapping.entries}
    assert entries["modelo-194-decl-nif"].producer_key == "taxpayer.tax_id"
    assert entries["modelo-194-perc-declarante-nif"].producer_key == "taxpayer.tax_id"
    assert entries["modelo-194-perc-nif"].binding == "modelo-194-perceptor-row-nif"
    assert not any(e.producer_key == "presenter.tax_id" for e in mapping.entries)
    assert entries["modelo-194-perc-ceros"].literal == "0" * 13
    assert ("modelo-194-perc-ceuta-melilla" in entries) == (epoch != "2019")
    assert mapping.records[1].repeat == "binding_rows"
    assert mapping.records[1].binding_record == "perceptor"
    revision = load_modelo_directory(root / "registry/aeat/modelos/194").revisions[epoch]
    for casilla in revision.casillas:
        if str(casilla.id).startswith(("decl.", "perc.")):
            assert mapping.source_ref in casilla.source_refs
            assert all(
                not str(ref).startswith("aeat-dr-194-") or ref == mapping.source_ref for ref in casilla.source_refs
            )
    bindings = {
        str(binding.id): binding
        for binding in revision.bindings
        if isinstance(binding.provider, WithholdingProvider) and binding.provider.fact == "row_field"
    }
    assert {str(entry.binding) for entry in mapping.entries if entry.binding is not None} == set(bindings)
    for binding in bindings.values():
        assert isinstance(binding.provider, WithholdingProvider)
        assert binding.provider.grouping == "per_source_allocation"
        assert tuple(binding.source_refs) == (mapping.source_ref, "aeat-modelo-194-procedure")
    assert {str(c.id) for c in revision.casillas} == {
        str(e.casilla_id) for e in mapping.entries if e.casilla_id is not None
    } | {str(casilla) for _, casilla in mapping.records[1].row_field_casilla_ids}
    # Both byte halves project the same supplied rate, never two editable amounts.
    assert (
        entries["modelo-194-perc-porcentaje-src-170"].binding == entries["modelo-194-perc-porcentaje-src-172"].binding
    )


@pytest.mark.parametrize("epoch", ["2019", "2023", "2024"])
def test_render_profiles_keep_signed_base_and_reserved_zero_scale(epoch: str) -> None:
    mapping = load_semantic_map(Path(f"dev/registry/mappings/modelo_194/{epoch}"))
    profile = load_render_profile(Path(f"dev/registry/render_profiles/modelo_194/{epoch}"))
    assert profile.design_identity.source_ref == mapping.source_ref
    assert profile.design_identity.source_sha256 == mapping.source_sha256
    (signed,) = profile.signed_composite_rules
    assert signed.integer_digits == 10
    assert signed.decimal_digits == 2
    assert signed.sign_policy == "blank-or-n-leading"
    base = next(e for e in mapping.entries if e.export_field_id == "modelo-194-perc-base")
    assert signed.anchor.source_row == base.anchor.source_row
    assert signed.anchor.record_identity == base.anchor.record_identity
    # Reserved CEROS has no monetary scale: its wire bytes are a literal,
    # not an editable reductions amount inherited from the old paper form.
    assert not profile.literal_numeric_rules
    phone_entry = next(e for e in mapping.entries if e.export_field_id == "modelo-194-decl-persona-contacto-telefono")
    phone = next(rule for rule in profile.singleton_rules if rule.anchor.source_row == phone_entry.anchor.source_row)
    assert phone.integer_digits == 9
    assert phone.semantic_kind == "digit_string"
    for offset, policy in ((170, "integer-part"), (172, "fractional-digits")):
        entry = next(e for e in mapping.entries if e.export_field_id == f"modelo-194-perc-porcentaje-src-{offset}")
        rule = next(r for r in profile.singleton_rules if r.anchor.source_row == entry.anchor.source_row)
        assert rule.value_policy == policy
    assert len(profile.telematic_transport_choice_rules) == (0 if epoch == "2024" else 1)
