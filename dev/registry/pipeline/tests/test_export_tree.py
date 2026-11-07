"""Real filesystem and loader proofs for generated export-tree rendering."""

from __future__ import annotations

from typing import override

import pytest
import rtoml

from cadrumo.core.directory_scan import (
    scan_directory,
)
from cadrumo.core.filing_projection_ref import (
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
)
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import (
    RegistryError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.schema_exports import ProjectionEndpointDeclaration, RecordDiscriminator

from ...author_family_identities import derive_projection_endpoint_id
from ...compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ...compiler.loader import load_modelo_directory
from .. import export_tree_serialization as serialization
from ..export_fragment_provenance import (
    ExportFragmentTarget,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
    verify_export_fragment_provenance_manifest,
)
from ..export_tree import render_complete_export_tree
from ..joined_record_design import join_record_design_semantics
from .export_tree_support import (
    DESIGN_EPOCH,
    SHELL_EXERCISE,
    SHELL_REVISION,
    export_tree_intermediate,
    export_tree_joined,
    export_tree_profile,
    export_tree_semantic_map,
    m130_inspection,
    wire_evidence,
    wire_profile,
    write_modelo_shell,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_toml_serialization_refusal_never_carries_the_offending_value() -> None:
    """``render_toml_bytes``'s ``rtoml.dumps`` refusal must never echo a payload value.

    ``rtoml.dumps`` raises ``TomlSerializationError`` (a ``ValueError``
    subclass) whose sole ``args[0]`` bakes the offending value's own ``repr``
    into the message, with no structured field that omits it -- measured:
    ``rtoml.dumps({"bad": object()})`` produces a string naming the object's
    default ``repr`` verbatim. Reproduced here with a payload carrying a
    short, easy-to-miss string alongside an unserializable object whose
    ``repr`` embeds that same string, proving the raw exception would carry
    it before pinning that the registry's own message never does.
    """
    probe_value = "nif-Z-taxpayer-value"

    class _Unserializable:
        @override
        def __repr__(self) -> str:
            return f"<unserializable probe_value={probe_value}>"

    with pytest.raises(ValueError) as raw_excinfo:
        rtoml.dumps({"bad": _Unserializable()}, pretty=True, none_value=None)
    assert probe_value in str(raw_excinfo.value), "premise: rtoml's own error must actually carry the value"

    with pytest.raises(RegistryValidationError) as excinfo:
        serialization.render_toml_bytes("generated/example.toml", {"bad": _Unserializable()})

    message = str(excinfo.value)
    assert probe_value not in message
    assert "unserializable" not in message
    assert "cannot serialize generated export TOML" in message
    assert "generated/example.toml" in message


_VALIDATION_MANIFEST = """\
[modelo]
id = "130"
tax_domain = "irpf"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["rd-439-2007:art-110", "orden-eha-672-2007:art-1"]
source_refs = ["aeat-dr-130-2019-v12", "aeat-modelo-130-instructions"]
"""


_VALIDATION_REVISION = f"""\
[revisions."{SHELL_REVISION}"]
authority_grade = "applicability"
valid_from = {SHELL_EXERCISE}-01-01
period_selector = {{ years = [{SHELL_EXERCISE}], periods = ["0A"] }}
legal_refs = ["rd-439-2007:art-110", "orden-eha-672-2007:art-1"]
source_refs = ["aeat-dr-130-2019-v12", "aeat-modelo-130-instructions"]
orden_aplicabilidad = ["orden-eha-672-2007:art-1"]
"""


_VALIDATION_APPLICATION_LINKS = f"""\
[[revisions."{SHELL_REVISION}".application_links]]
id = "generated-export-link"
surface = "export"
consumer = "cli.app"
requires_snapshot = true
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-dr-130-2019-v12"]

[[revisions."{SHELL_REVISION}".application_links]]
id = "generated-filing-link"
surface = "filing"
consumer = "cli.app"
requires_snapshot = true
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-modelo-130-instructions"]
"""


_VALIDATION_CASILLAS = f"""\
[[revisions."{SHELL_REVISION}".casillas]]
id = "01"
number = "01"
section = ["generated"]
data_type = "integer"
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-dr-130-2019-v12"]
"""


_VALIDATION_WORKBOOK_PARITY = f"""\
[[revisions."{SHELL_REVISION}".workbook_parity_refs]]
id = "generated-workbook-parity"
workbook_source = "aeat-dr-130-2019-v12"
fixture_id = "generated-tree-validation"
formula_coverage = "record_design_layout"
runner_required = false
tolerance = "0.00"
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-dr-130-2019-v12"]
"""


def test_renderer_writes_stable_complete_tree_that_real_directory_loader_merges(tmp_path) -> None:
    """The output is fresh canonical TOML that the real loader compiles by its fragment rules."""
    revision_dir = write_modelo_shell(tmp_path / "modelos" / "130")
    first = render_complete_export_tree(
        revision_dir / "export",
        revision_id=SHELL_REVISION,
        joined=export_tree_joined(m130_inspection()),
        semantic_map=export_tree_semantic_map(),
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )
    duplicate_revision_dir = write_modelo_shell(tmp_path / "comparison" / "modelos" / "130")
    second = render_complete_export_tree(
        duplicate_revision_dir / "export",
        revision_id=SHELL_REVISION,
        joined=export_tree_joined(m130_inspection()),
        semantic_map=export_tree_semantic_map(),
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    assert first.output_files == (
        "0000-export-layout.toml",
        "0001-record-generated-registro-tipo-1.toml",
        "0002-record-generated-registro-tipo-2.toml",
    )
    assert first.field_derivations[-1].derivation_code == "numeric-decimal-v1"
    assert first.layout == second.layout
    assert {
        path.relative_to(revision_dir / "export").as_posix(): path.read_bytes()
        for path in scan_directory(revision_dir / "export")
    } == {
        path.relative_to(duplicate_revision_dir / "export").as_posix(): path.read_bytes()
        for path in scan_directory(duplicate_revision_dir / "export")
    }

    loaded = load_modelo_directory(tmp_path / "modelos" / "130")
    layout = loaded.revisions[SHELL_REVISION].export_layouts[0]
    manifest_path = revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    assert manifest_path.is_file()
    assert manifest_path.name not in first.output_files
    assert load_export_fragment_provenance_manifest(manifest_path.read_bytes()) == first.provenance_manifest
    assert (
        verify_export_fragment_provenance_manifest(
            export_root=revision_dir / "export",
            joined=export_tree_joined(m130_inspection()),
            semantic_map=export_tree_semantic_map(),
            target=ExportFragmentTarget(modelo="130", revision_id=SHELL_REVISION, design_epoch=DESIGN_EPOCH),
            loaded_layout=layout,
            field_derivations=first.field_derivations,
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )
        == first.provenance_manifest
    )
    assert layout == first.layout


def test_real_loader_accepts_only_generator_owned_export_provenance(tmp_path) -> None:
    """The generated JSON sidecar is structural evidence, not a TOML fragment."""
    revision_dir = write_modelo_shell(tmp_path / "modelos" / "130")
    render_complete_export_tree(
        revision_dir / "export",
        revision_id=SHELL_REVISION,
        joined=export_tree_joined(m130_inspection()),
        semantic_map=export_tree_semantic_map(),
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    loaded = load_modelo_directory(tmp_path / "modelos" / "130")
    assert loaded.revisions[SHELL_REVISION].export_layouts

    unexpected = revision_dir / "export" / "unexpected.json"
    unexpected.write_text("{}\n", encoding="utf-8", newline="\n")
    with pytest.raises(RegistryError, match="unrecognized revision fragment file"):
        load_modelo_directory(tmp_path / "modelos" / "130")


@pytest.mark.parametrize("required", [False, True])
def test_renderer_carries_semantic_projection_occurrence_authority_into_generated_record(
    tmp_path,
    required: bool,
) -> None:
    semantic_map = export_tree_semantic_map()
    projection_entry = semantic_map.entries[-1].model_copy(
        update={
            "kind": CasillaFieldKind.PROJECTION,
            "producer_key": None,
            "projection_ref": M303ProrrataActivityProjectionRef(
                projection_kind="m303_prorrata_activity",
                slot=1,
                field=M303ProrrataActivityProjectionField.CNAE,
                casilla_id="500",
            ),
        },
    )
    records = tuple(
        record.model_copy(update={"repeat": "projection_rows", "required": required}) if index == 1 else record
        for index, record in enumerate(semantic_map.records)
    )
    semantic_map = semantic_map.model_copy(
        update={"records": records, "entries": (*semantic_map.entries[:-1], projection_entry)},
    )
    assert projection_entry.projection_ref is not None
    projection_endpoints = (
        ProjectionEndpointDeclaration(
            id=derive_projection_endpoint_id(
                {"projection_ref": projection_entry.projection_ref.model_dump(mode="json")}
            ),
            projection_ref=projection_entry.projection_ref,
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-dr-130-2019-v12",),
        ),
    )
    inspection = m130_inspection().model_copy(update={"projection_endpoints": projection_endpoints})
    joined = join_record_design_semantics(semantic_map, export_tree_intermediate(), inspection)

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=SHELL_REVISION,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    assert rendered.layout.records[1].repeat == "projection_rows"
    assert rendered.layout.records[1].required is required


def test_renderer_carries_semantic_record_discriminator_into_generated_record(
    tmp_path,
) -> None:
    semantic_map = export_tree_semantic_map()
    records = tuple(
        record.model_copy(update={"discriminator": RecordDiscriminator(offset=3, length=1, requires="blank")})
        if index == 1
        else record
        for index, record in enumerate(semantic_map.records)
    )
    semantic_map = semantic_map.model_copy(update={"records": records})
    joined = join_record_design_semantics(semantic_map, export_tree_intermediate(), m130_inspection())

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=SHELL_REVISION,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    assert rendered.layout.records[1].discriminator == RecordDiscriminator(offset=3, length=1, requires="blank")


def test_renderer_manifest_refuses_file_tampering_derivation_drift_and_partial_field_evidence(
    tmp_path,
) -> None:
    """Only the fresh full renderer result can attest its real generated tree."""
    revision_dir = write_modelo_shell(tmp_path / "modelos" / "130")
    rendered = render_complete_export_tree(
        revision_dir / "export",
        revision_id=SHELL_REVISION,
        joined=export_tree_joined(m130_inspection()),
        semantic_map=export_tree_semantic_map(),
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )
    layout = load_modelo_directory(tmp_path / "modelos" / "130").revisions[SHELL_REVISION].export_layouts[0]
    export_root = revision_dir / "export"
    manifest_path = revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    original_fragment = export_root / "0001-record-generated-registro-tipo-1.toml"
    original_bytes = original_fragment.read_bytes()

    original_fragment.write_bytes(original_bytes + b"# tampered\n")
    with pytest.raises(RegistryValidationError, match="output-file digests"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=export_tree_semantic_map(),
            target=ExportFragmentTarget(modelo="130", revision_id=SHELL_REVISION, design_epoch=DESIGN_EPOCH),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )
    original_fragment.write_bytes(original_bytes)

    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    authority_tampered_manifest = manifest.model_copy(update={"source_sha256": "b" * 64})
    manifest_path.write_bytes(export_fragment_provenance_manifest_json_bytes(authority_tampered_manifest))
    with pytest.raises(RegistryValidationError, match="current generation authorities"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=export_tree_semantic_map(),
            target=ExportFragmentTarget(modelo="130", revision_id=SHELL_REVISION, design_epoch=DESIGN_EPOCH),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    drifted_derivation = manifest.field_derivations[0].model_copy(update={"derivation_code": "filler-v1"})
    drifted_manifest = manifest.model_copy(
        update={"field_derivations": (drifted_derivation, *manifest.field_derivations[1:])},
    )
    manifest_path.write_bytes(export_fragment_provenance_manifest_json_bytes(drifted_manifest))
    with pytest.raises(RegistryValidationError, match="field derivations do not match"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=export_tree_semantic_map(),
            target=ExportFragmentTarget(modelo="130", revision_id=SHELL_REVISION, design_epoch=DESIGN_EPOCH),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    partial_manifest = manifest.model_copy(update={"field_derivations": manifest.field_derivations[:-1]})
    manifest_path.write_bytes(export_fragment_provenance_manifest_json_bytes(partial_manifest))
    with pytest.raises(RegistryValidationError, match="do not cover exactly"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=export_tree_semantic_map(),
            target=ExportFragmentTarget(modelo="130", revision_id=SHELL_REVISION, design_epoch=DESIGN_EPOCH),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )


def test_generated_export_target_refuses_a_link_even_though_the_name_and_kind_look_right(
    tmp_path,
) -> None:
    """The renderer must not write through a link masquerading as the export target.

    The module docstring promises a tree written "without opening a shipped
    fragment directory or deriving any output fact from one." A link named
    ``export`` that resolves elsewhere is exactly how that isolation would be
    defeated silently: `.exists()` and `.is_dir()` both admit it, so only the
    dedicated link check stands between this call and writing through it.
    """
    real_elsewhere = tmp_path / "real_elsewhere"
    real_elsewhere.mkdir()
    link_target = tmp_path / "export"
    link_target.symlink_to(real_elsewhere, target_is_directory=True)

    with pytest.raises(RegistryValidationError, match="must not be a link"):
        render_complete_export_tree(
            link_target,
            revision_id=SHELL_REVISION,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=export_tree_semantic_map(),
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )
    assert not any(real_elsewhere.iterdir())


def test_generated_export_target_accepts_a_real_preexisting_empty_directory(
    tmp_path,
) -> None:
    """Sibling-blindness check: a genuine empty directory is not mistaken for a link.

    Same name, same "already exists as a directory" shape as the refused link
    above, but no reparse point involved. The link guard must not fire here,
    and the render must proceed and populate the real directory in place.
    """
    real_target = tmp_path / "export"
    real_target.mkdir()

    rendered = render_complete_export_tree(
        real_target,
        revision_id=SHELL_REVISION,
        joined=export_tree_joined(m130_inspection()),
        semantic_map=export_tree_semantic_map(),
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    assert rendered.output_files
    assert all((real_target / relative_path).is_file() for relative_path in rendered.output_files)
