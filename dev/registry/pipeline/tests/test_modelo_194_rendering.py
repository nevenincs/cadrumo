"""Actual Modelo 194 render inputs preserve text, cents, signs and reserved bytes."""

from decimal import Decimal
from pathlib import Path
from shutil import copytree, ignore_patterns

import pytest
import tomlkit

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from .._export_tree import render_complete_export_tree
from ..export_field_literal_derivation import _literal_derivation
from ..render_check import GeneratedExportBootstrapTransport, RevisionRenderInputs, _revision_render_inputs
from ..render_profile import _validate_telematic_transport_condition
from ..semantic_map import load_semantic_map
from ..source_stated_composites import source_stated_composite_integer_digits_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(params=["2019", "2023", "2024"])
def inputs(request: pytest.FixtureRequest) -> RevisionRenderInputs:
    epoch = str(request.param)
    root = Path("src/cadrumo/_data")
    mapping = load_semantic_map(Path(f"dev/registry/mappings/modelo_194/{epoch}"))
    return _revision_render_inputs(
        load_modelo_directory(root / "registry/aeat/modelos/194"),
        load_shared_catalogues(root / "registry/aeat"),
        modelo="194",
        revision=epoch,
        source_ref=mapping.source_ref,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id=f"generated-modelo-194-{epoch}-fichero",
            line_ending="crlf",
            source_ref=mapping.source_ref,
            source_sha256=mapping.source_sha256,
        ),
        filing_year=int(epoch),
        period="0A",
        source_root=root,
    )


def test_complete_render_preserves_actual_field_values(inputs: RevisionRenderInputs, tmp_path: Path) -> None:
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inputs.transport_profile.design_epoch,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )
    declarant, recipient = rendered.layout.records
    for record in rendered.layout.records:
        cursor = 1
        for field in record.fields:
            assert field.offset == cursor
            assert field.length is not None
            cursor += field.length
        assert cursor == 251
    fields = {field.offset: field for field in recipient.fields}
    contact = next(field for field in declarant.fields if field.offset == 68)
    assert render_fixed_width_export_field(contact, "ANA GARCIA") == "ANA GARCIA".ljust(40)
    assert render_fixed_width_export_field(fields[144], None) == "0" * 13
    assert render_fixed_width_export_field(fields[157], Decimal("-125.30")) == "N000000012530"
    assert render_fixed_width_export_field(fields[157], Decimal("125.30")) == " 000000012530"
    assert render_fixed_width_export_field(fields[170], Decimal("7.60")) == "07"
    assert render_fixed_width_export_field(fields[172], Decimal("7.60")) == "60"
    assert fields[170].binding == fields[172].binding
    if inputs.transport_profile.design_epoch != "2019":
        assert render_fixed_width_export_field(fields[188], 2) == "2"
        with pytest.raises(RegistryValidationError):
            render_fixed_width_export_field(fields[188], 3)


@pytest.mark.parametrize("inputs", ["2019"], indirect=True)
def test_installing_old_design_does_not_adopt_it_for_later_editions(
    inputs: RevisionRenderInputs, tmp_path: Path
) -> None:
    modelo_root = tmp_path / "194"
    copytree(Path("src/cadrumo/_data/registry/aeat/modelos/194"), modelo_root, ignore=ignore_patterns("export"))
    for revision in ("2023", "2024"):
        path = modelo_root / "revisions" / revision / "revision.toml"
        document = tomlkit.parse(path.read_text("utf-8"))
        document["revisions"][revision]["cleared_families"] = [
            {
                "family": "export_layouts",
                "cause": "not_authored_for_this_edition",
                "reason": "Isolated fixture awaits its own generated export.",
            }
        ]
        path.write_text(tomlkit.dumps(document), encoding="utf-8")
    rendered = render_complete_export_tree(
        modelo_root / "revisions/2019/export",
        revision_id="2019",
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )
    loaded = load_modelo_directory(modelo_root)
    assert loaded.revisions["2019"].export_layouts == (rendered.layout,)
    for revision in ("2023", "2024"):
        assert loaded.revisions[revision].export_layouts == ()
        assert any(
            binding.id == "modelo-194-perceptor-row-ceuta-melilla" for binding in loaded.revisions[revision].bindings
        )


def test_signed_base_refuses_changed_source_or_prose(inputs: RevisionRenderInputs) -> None:
    field = next(f.parser_field for r in inputs.joined.records for f in r.fields if f.parser_field.offset == 157)
    identity = inputs.render_profile.design_identity
    assert source_stated_composite_integer_digits_for(field, identity) == 10
    for altered in (
        field.model_copy(update={"content": (field.content or "").replace("negativo", "positivo")}),
        field.model_copy(update={"length": 14}),
    ):
        with pytest.raises(RegistryValidationError, match="anchor or complete prose changed"):
            source_stated_composite_integer_digits_for(altered, identity)
    with pytest.raises(RegistryValidationError, match="unreviewed or stale"):
        source_stated_composite_integer_digits_for(field, identity.model_copy(update={"source_sha256": "0" * 64}))


def test_reserved_zero_run_refuses_nonzero_or_space_payload(inputs: RevisionRenderInputs) -> None:
    field = next(f for r in inputs.joined.records for f in r.fields if f.parser_field.offset == 144)
    for literal in (" " * 13, "0" * 12 + "1", "0" * 12):
        altered = field.model_copy(
            update={"semantic_entry": field.semantic_entry.model_copy(update={"literal": literal})}
        )
        with pytest.raises(RegistryValidationError):
            _literal_derivation(
                altered,
                encoding=inputs.transport_profile.encoding,
                render_profile=inputs.render_profile,
                export_record_id="modelo-194-perceptor",
            )


@pytest.mark.parametrize(
    "condition", ["Si no es presentación telemática", "Presentación presencial", "Si es presentación en papel"]
)
def test_transport_choice_refuses_other_conditions(condition: str) -> None:
    with pytest.raises(RegistryValidationError, match="lacks the official telematic condition"):
        _validate_telematic_transport_condition(f"'T': {condition}.")
