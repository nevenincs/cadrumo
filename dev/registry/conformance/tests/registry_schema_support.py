"""Shared builders for the registry schema conformance tests."""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.governed_fact_scope import (
    CandidateFactAuthority,
    validating_governed_facts,
)
from cadrumo.domain.calculations.registry.schema import (
    BindingDefinition,
    ModeloDefinition,
    ModeloRevision,
)
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision

from ...compiler.loader import load_modelo_directory
from ...compiler.validator import RegistryValidator
from ...form_layout.generator import generate_revision_layout
from ...record_design_labels import DATA_ROOT
from ...tests.profile_schema_support import load_user_profile_schema
from ..loader_directory_mode_support import (
    write_fragmented_modelo_from_text,
)
from ..registry_schema_support import (
    with_revision,
)

MISSING_CASILLA: CasillaId = validated_casilla_id("missing", surface="MISSING_CASILLA")


NAMED_LABEL_CASILLA: CasillaId = validated_casilla_id("my-label", surface="NAMED_LABEL_CASILLA")


DECL_CNAE_CASILLA: CasillaId = validated_casilla_id("decl.cnae", surface="DECL_CNAE_CASILLA")


_MODELO_130_DIR = bundled_path("registry", "aeat", "modelos", "130")


def object_boundary(value: object) -> object:
    """Preserve runtime validation for intentionally malformed fixture values."""
    return value


def committed_modelo_revision_id() -> str:
    """Return the id of the one authored revision of the committed M130 source tree."""
    return str(open_ended_revision("130").id)


def committed_modelo_text() -> str:
    """Flatten the committed M130 source tree into one editable TOML text.

    A mutation test wants to change one declaration and see the compiler refuse
    it; reading the fragments into one string keeps the edit a single
    substitution. The mutated text is always written back out as the fragmented
    directory layout before it is compiled.
    """
    revision_dir = _MODELO_130_DIR / "revisions" / committed_modelo_revision_id()
    fragments = [revision_dir / "revision.toml"]
    fragments.extend(
        item
        for item in scan_directory(revision_dir, pattern="*.toml", recursive=True, prune_directories=("locales",))
        if item.name != "revision.toml"
    )
    text = _MODELO_130_DIR.joinpath("manifest.toml").read_text(encoding="utf-8")
    return text + "".join(fragment.read_text(encoding="utf-8") for fragment in fragments)


def load_modelo_text(root: Path, text: str) -> ModeloDefinition:
    """Compile one whole-modelo TOML text through the directory-mode loader."""
    target = root / "isolated-registry" / "modelos" / "130"
    return load_modelo_directory(write_fragmented_modelo_from_text(target, text))


def with_first_export_field(revision: ModeloRevision, field: ExportFieldDefinition) -> ModeloRevision:
    layout = revision.export_layouts[0]
    record = layout.records[0]
    updated_record = record.model_copy(update={"fields": (field, *record.fields[1:])})
    updated_layout = layout.model_copy(update={"records": (updated_record, *layout.records[1:])})
    return revision.model_copy(update={"export_layouts": (updated_layout, *revision.export_layouts[1:])})


def _validate_modelo(modelo: ModeloDefinition, catalogues: RegistryCatalogues) -> None:
    with validating_governed_facts(
        CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years())
    ):
        RegistryValidator(
            catalogues,
            source_root=bundled_path(),
            user_profile_schema=load_user_profile_schema(),
        ).validate_modelo(modelo)


def validate_revision(modelo: ModeloDefinition, catalogues: RegistryCatalogues, revision: ModeloRevision) -> None:
    """Validate an edited revision after regenerating its generator-owned form layout.

    The layout is pinned to the revision facts it was generated from, so an
    edit that moves an export field or casilla leaves it stale until the
    generator runs again. Regenerating here, exactly as the generator's CLI
    would after the edit, keeps each test measuring only its own declaration.
    """
    generated = generate_revision_layout(str(modelo.id), revision, sources=catalogues.sources, data_root=DATA_ROOT)
    layouts = () if generated.layout is None else (generated.layout,)
    _validate_modelo(with_revision(modelo, revision.model_copy(update={"form_layouts": layouts})), catalogues)


def with_binding(revision: ModeloRevision, binding: BindingDefinition) -> ModeloRevision:
    return revision.model_copy(
        update={"bindings": tuple(binding if item.id == binding.id else item for item in revision.bindings)},
    )
