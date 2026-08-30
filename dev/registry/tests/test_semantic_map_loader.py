"""Real-filesystem proof for the persisted semantic-map fragment contract."""

from __future__ import annotations

import ast
import inspect
from importlib import import_module
from pathlib import Path

import pytest

from cadrumo.core import M303ProrrataActivityProjectionField, M303ProrrataActivityProjectionRef
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_semantics import ExportComputedKey, ExportDraftAttribute
from cadrumo.domain.calculations.registry.schema_exports import RecordDiscriminator

from .. import SEMANTIC_MAP_FRAGMENT_SCHEMA_VERSION, load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

registry_facade = import_module("..", __package__)


_RECORD = """
[[records]]
sheet = "Registro tipo 1"
record_identity = "registro-tipo-1"
export_record_id = "registro-tipo-1"
record_type = "declaracion"
"""

_ENTRY = """
[[entries]]
export_field_id = "registro-tipo-1.declarante-nif"
kind = "header"
producer_key = "presenter.tax_id"
legal_refs = ["orden-eha-3786-2008:art-1"]
source_refs = ["aeat-dr-303-2026"]

[entries.anchor]
sheet = "Registro tipo 1"
source_row = 14
source_cell = "A14"
ordinal = 1
record_identity = "registro-tipo-1"
"""

_PROJECTION_ENTRY = """
[[entries]]
export_field_id = "registro-tipo-1.prorrata-cnae"
kind = "projection"
legal_refs = ["orden-eha-3786-2008:art-1"]
source_refs = ["aeat-dr-303-2026"]

[entries.projection_ref]
projection_kind = "m303_prorrata_activity"
slot = 1
field = "cnae"
casilla_id = "500"

[entries.anchor]
sheet = "Registro tipo 1"
source_row = 14
source_cell = "A14"
ordinal = 1
record_identity = "registro-tipo-1"
"""

_DRAFT_AND_COMPUTED_ENTRIES = """
[[entries]]
export_field_id = "registro-tipo-1.filing-year"
kind = "draft"
draft_attribute = "filing_year"
legal_refs = ["orden-eha-3786-2008:art-1"]
source_refs = ["aeat-dr-303-2026"]

[entries.anchor]
sheet = "Registro tipo 1"
source_row = 15
source_cell = "A15"
ordinal = 2
record_identity = "registro-tipo-1"

[[entries]]
export_field_id = "registro-tipo-1.no-activity"
kind = "computed"
computed_key = "m303_no_activity_marker"
legal_refs = ["orden-eha-3786-2008:art-1"]
source_refs = ["aeat-dr-303-2026"]

[entries.anchor]
sheet = "Registro tipo 1"
source_row = 16
source_cell = "A16"
ordinal = 3
record_identity = "registro-tipo-1"
"""


def _fragment(
    *,
    fragment_id: str,
    body: str,
    epoch: str = "2026",
    source_ref: str = "aeat-dr-303-2026",
    source_sha256: str = "a" * 64,
) -> str:
    return (
        f"schema_version = {SEMANTIC_MAP_FRAGMENT_SCHEMA_VERSION}\n"
        f'fragment_id = "{fragment_id}"\n'
        'modelo = "303"\n'
        f'design_epoch = "{epoch}"\n'
        f'source_ref = "{source_ref}"\n'
        f'source_sha256 = "{source_sha256}"\n'
        f"{body.strip()}\n"
    )


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_fragments_in_filename_order_independent_of_creation_order(tmp_path: Path) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    _write(root / "0002-fields.toml", _fragment(fragment_id="fields", body=_ENTRY))
    _write(root / "0001-records.toml", _fragment(fragment_id="records", body=_RECORD))

    semantic_map = load_semantic_map(root)

    assert semantic_map.modelo == "303"
    assert semantic_map.design_epoch == "2026"
    assert semantic_map.source_ref == "aeat-dr-303-2026"
    assert semantic_map.source_sha256 == "a" * 64
    assert tuple(record.export_record_id for record in semantic_map.records) == ("registro-tipo-1",)
    assert tuple(entry.export_field_id for entry in semantic_map.entries) == ("registro-tipo-1.declarante-nif",)


def test_compiled_semantics_have_canonical_order_across_fragments(tmp_path: Path) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    zeta = (_RECORD + _ENTRY).replace("Registro tipo 1", "Zeta").replace("registro-tipo-1", "zeta")
    alpha = (_RECORD + _ENTRY).replace("Registro tipo 1", "Alpha").replace("registro-tipo-1", "alpha")
    _write(root / "0002-alpha.toml", _fragment(fragment_id="alpha", body=alpha))
    _write(root / "0001-zeta.toml", _fragment(fragment_id="zeta", body=zeta))

    semantic_map = load_semantic_map(root)

    assert tuple(record.sheet for record in semantic_map.records) == ("Alpha", "Zeta")
    assert tuple(entry.anchor.sheet for entry in semantic_map.entries) == ("Alpha", "Zeta")


def test_entry_order_uses_the_canonical_cell_before_ordinal_anchor_key(tmp_path: Path) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    later_cell_lower_ordinal = _ENTRY.replace("source_row = 14", "source_row = 20").replace(
        'source_cell = "A14"',
        'source_cell = "B20"',
    )
    earlier_cell_higher_ordinal = (
        _ENTRY.replace("source_row = 14", "source_row = 20")
        .replace('source_cell = "A14"', 'source_cell = "A20"')
        .replace("ordinal = 1", "ordinal = 2")
        .replace("declarante-nif", "declarante-name")
    )
    _write(
        root / "0001-authority.toml",
        _fragment(
            fragment_id="authority",
            body=_RECORD + later_cell_lower_ordinal + earlier_cell_higher_ordinal,
        ),
    )

    semantic_map = load_semantic_map(root)

    assert tuple(entry.anchor.source_cell for entry in semantic_map.entries) == ("A20", "B20")


def test_loader_is_the_sole_projection_ref_hydration_boundary(tmp_path: Path) -> None:
    """A persisted projection table compiles to the strict core discriminated union."""
    root = tmp_path / "semantic-map"
    root.mkdir()
    _write(root / "0001-authority.toml", _fragment(fragment_id="authority", body=_RECORD + _PROJECTION_ENTRY))

    semantic_map = load_semantic_map(root)

    projection_ref = semantic_map.entries[0].projection_ref
    assert isinstance(projection_ref, M303ProrrataActivityProjectionRef)
    assert projection_ref.projection_kind == "m303_prorrata_activity"
    assert projection_ref.slot == 1
    assert projection_ref.field is M303ProrrataActivityProjectionField.CNAE
    assert projection_ref.casilla_id == "500"


def test_loader_hydrates_draft_and_computed_tokens_once_into_the_closed_vocabulary(tmp_path: Path) -> None:
    """Real authored tokens enter the map through the same strict loader boundary."""
    root = tmp_path / "semantic-map"
    root.mkdir()
    _write(
        root / "0001-authority.toml",
        _fragment(fragment_id="authority", body=_RECORD + _DRAFT_AND_COMPUTED_ENTRIES),
    )

    semantic_map = load_semantic_map(root)

    draft_entry, computed_entry = semantic_map.entries
    assert draft_entry.draft_attribute is ExportDraftAttribute.FILING_YEAR
    assert computed_entry.computed_key is ExportComputedKey.M303_NO_ACTIVITY_MARKER


def test_loader_preserves_projection_record_occurrence_authority(tmp_path: Path) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    projection_record = _RECORD.replace(
        'record_type = "declaracion"',
        'record_type = "declaracion"\nrequired = false\nrepeat = "projection_rows"',
    )
    _write(root / "0001-record.toml", _fragment(fragment_id="record", body=projection_record + _ENTRY))

    semantic_map = load_semantic_map(root)

    assert semantic_map.records[0].repeat == "projection_rows"
    assert semantic_map.records[0].required is False


def test_loader_carries_the_existing_typed_record_discriminator(tmp_path: Path) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    record = _RECORD + 'discriminator = { offset = 500, length = 1, requires = "blank" }\n'
    _write(root / "0001-record.toml", _fragment(fragment_id="record", body=record + _ENTRY))

    semantic_map = load_semantic_map(root)

    assert semantic_map.records[0].discriminator == RecordDiscriminator(offset=500, length=1, requires="blank")


@pytest.mark.parametrize("slot_literal", ['"1"', "1.0", "true"])
def test_loader_refuses_projection_slot_coercion(tmp_path: Path, slot_literal: str) -> None:
    """A slot ordinal is an exact integer; no string, float or boolean is coerced."""
    root = tmp_path / "semantic-map"
    root.mkdir()
    authored = (_RECORD + _PROJECTION_ENTRY).replace("slot = 1", f"slot = {slot_literal}")
    _write(root / "0001-authority.toml", _fragment(fragment_id="authority", body=authored))

    with pytest.raises(RegistryValidationError, match=r"projection_ref is not canonical: .*exact integer"):
        load_semantic_map(root)


@pytest.mark.parametrize(
    ("target", "replacement", "message"),
    (
        (
            'projection_kind = "m303_prorrata_activity"',
            'projection_kind = "m303_inferred_projection"',
            "projection_ref is not canonical",
        ),
        (
            "[entries.projection_ref]",
            'projection_ref = "prorrata.slot.1.cnae"',
            "projection_ref is not canonical",
        ),
    ),
)
def test_loader_refuses_invalid_projection_discriminants_and_string_keys(
    tmp_path: Path,
    target: str,
    replacement: str,
    message: str,
) -> None:
    """Projection identity is a closed typed union, never a string-key fallback."""
    root = tmp_path / "semantic-map"
    root.mkdir()
    authored = (_RECORD + _PROJECTION_ENTRY).replace(target, replacement)
    _write(root / "0001-authority.toml", _fragment(fragment_id="authority", body=authored))

    with pytest.raises(RegistryValidationError, match=message):
        load_semantic_map(root)


def test_lexical_filename_order_determines_the_first_fragment_failure(tmp_path: Path) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    _write(root / "0002-second.toml", "not = [valid")
    _write(root / "0001-first.toml", "also = [invalid")

    with pytest.raises(RegistryValidationError, match=r"0001-first\.toml"):
        load_semantic_map(root)


@pytest.mark.parametrize(
    ("second_body", "message"),
    (
        (_RECORD, "exact record anchors"),
        (
            _RECORD.replace('record_identity = "registro-tipo-1"', 'record_identity = "other"'),
            "export record ids",
        ),
        (_ENTRY, "exact field anchors"),
        (
            _ENTRY.replace("source_row = 14", "source_row = 15").replace('source_cell = "A14"', 'source_cell = "A15"'),
            "export field ids",
        ),
    ),
)
def test_refuses_cross_fragment_semantic_collisions(
    tmp_path: Path,
    second_body: str,
    message: str,
) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    first_body = _RECORD if "record" in message else _ENTRY
    other_required = _ENTRY if "record" in message else _RECORD
    _write(root / "0001-authority.toml", _fragment(fragment_id="authority", body=first_body + other_required))
    _write(root / "0002-collision.toml", _fragment(fragment_id="collision", body=second_body))

    with pytest.raises(RegistryValidationError, match=message):
        load_semantic_map(root)


def test_refuses_duplicate_fragment_ids(tmp_path: Path) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    _write(root / "0001-same.toml", _fragment(fragment_id="same", body=_RECORD))
    _write(root / "0002-same.toml", _fragment(fragment_id="same", body=_ENTRY))

    with pytest.raises(RegistryValidationError, match="duplicate fragment ids"):
        load_semantic_map(root)


def test_refuses_conflicting_design_identity(tmp_path: Path) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    _write(root / "0001-records.toml", _fragment(fragment_id="records", body=_RECORD))
    _write(root / "0002-fields.toml", _fragment(fragment_id="fields", body=_ENTRY, epoch="2025"))

    with pytest.raises(RegistryValidationError, match="conflicting modelo/design/source identities"):
        load_semantic_map(root)


@pytest.mark.parametrize(
    ("identity_key", "identity_value"),
    (
        ("source_ref", "aeat-dr-303-2025"),
        ("source_sha256", "b" * 64),
    ),
)
def test_refuses_mixed_fragment_source_identity(
    tmp_path: Path,
    identity_key: str,
    identity_value: str,
) -> None:
    """All persisted fragments must attest one exact official source."""
    root = tmp_path / "semantic-map"
    root.mkdir()
    _write(root / "0001-records.toml", _fragment(fragment_id="records", body=_RECORD))
    fragment_arguments: dict[str, object] = {identity_key: identity_value}
    _write(root / "0002-fields.toml", _fragment(fragment_id="fields", body=_ENTRY, **fragment_arguments))

    with pytest.raises(RegistryValidationError, match="conflicting modelo/design/source identities"):
        load_semantic_map(root)


@pytest.mark.parametrize("identity_line", ("source_ref", "source_sha256"))
def test_refuses_design_epoch_only_fragment(tmp_path: Path, identity_line: str) -> None:
    """A fragment without its source identity is not a semantic-map authority."""
    root = tmp_path / "semantic-map"
    root.mkdir()
    fragment = _fragment(fragment_id="authority", body=_RECORD + _ENTRY)
    without_identity = "\n".join(line for line in fragment.splitlines() if not line.startswith(f"{identity_line} ="))
    _write(root / "0001-authority.toml", without_identity)

    with pytest.raises(RegistryValidationError, match=identity_line):
        load_semantic_map(root)


@pytest.mark.parametrize(
    ("name", "text", "message"),
    (
        ("not-toml.txt", "not toml", "accepts only regular TOML fragments"),
        ("invalid.toml", "not = [valid", "invalid TOML"),
        (
            "0001-unknown.toml",
            _fragment(fragment_id="unknown", body=_RECORD) + "unknown_key = true\n",
            "invalid semantic-map fragment",
        ),
        (
            "0001-version.toml",
            _fragment(fragment_id="version", body=_RECORD).replace("schema_version = 1", "schema_version = 2"),
            "invalid semantic-map fragment",
        ),
        (
            "0001-coercion.toml",
            _fragment(fragment_id="coercion", body=_RECORD).replace("schema_version = 1", 'schema_version = "1"'),
            "invalid semantic-map fragment",
        ),
        (
            "0001-nested.toml",
            _fragment(fragment_id="nested", body=_ENTRY) + "unknown_anchor_fact = true\n",
            "invalid semantic-map fragment",
        ),
    ),
)
def test_refuses_noncanonical_fragment_files(
    tmp_path: Path,
    name: str,
    text: str,
    message: str,
) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    _write(root / name, text)

    with pytest.raises(RegistryValidationError, match=message):
        load_semantic_map(root)


def test_refuses_empty_fragment_and_empty_directory(tmp_path: Path) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    with pytest.raises(RegistryValidationError, match="contains no TOML fragments"):
        load_semantic_map(root)

    _write(root / "0001-empty.toml", _fragment(fragment_id="empty", body=""))
    with pytest.raises(RegistryValidationError, match="must contain records, entries, or variable envelopes"):
        load_semantic_map(root)


def test_refuses_filename_fragment_id_drift(tmp_path: Path) -> None:
    root = tmp_path / "semantic-map"
    root.mkdir()
    _write(root / "0001-wrong.toml", _fragment(fragment_id="records", body=_RECORD))

    with pytest.raises(RegistryValidationError, match="NNNN-<fragment_id>"):
        load_semantic_map(root)


def test_refuses_single_file_and_link_fallback_surfaces(tmp_path: Path) -> None:
    standalone = _write(
        tmp_path / "0001-authority.toml",
        _fragment(fragment_id="authority", body=_RECORD + _ENTRY),
    )
    with pytest.raises(RegistryValidationError, match="must be a real directory"):
        load_semantic_map(standalone)

    linked_directory = tmp_path / "linked-map"
    linked_directory.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RegistryValidationError, match="must be a real directory"):
        load_semantic_map(linked_directory)

    root = tmp_path / "semantic-map"
    root.mkdir()
    (root / "0001-authority.toml").symlink_to(standalone)
    with pytest.raises(RegistryValidationError, match="accepts only regular TOML fragments"):
        load_semantic_map(root)


def test_public_loader_has_one_toml_parser_owner() -> None:
    loader_module = inspect.getmodule(load_semantic_map)
    assert loader_module is not None
    tree = ast.parse(inspect.getsource(loader_module))
    import_from_nodes = tuple(node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    imported_modules = {node.module for node in import_from_nodes if node.module is not None} | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    direct_imports = {
        (alias.name, alias.asname) for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    imported_aliases = {
        alias.asname or alias.name: f"{node.module}.{alias.name}"
        for node in import_from_nodes
        if node.module is not None
        for alias in node.names
    } | {
        alias.asname or alias.name: alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    called_targets = {
        _resolved_call_target(node.func, imported_aliases) for node in ast.walk(tree) if isinstance(node, ast.Call)
    }

    assert imported_modules == {
        "__future__",
        "re",
        "collections.abc",
        "pathlib",
        "typing",
        "pydantic",
        "cadrumo.core",
        "cadrumo.domain.calculations.registry",
        "_semantic_map",
    }
    imported_names_by_module = {
        node.module: {alias.name for alias in node.names}
        for node in import_from_nodes
        if node.module
        in {
            "cadrumo.core",
            "cadrumo.domain.calculations.registry",
            "_semantic_map",
        }
    }
    assert imported_names_by_module == {
        "cadrumo.core": {
            "FilingProducerKey",
            "compile_filing_projection_ref",
            "freeze_toml",
            "read_toml",
            "iter_directory",
        },
        "cadrumo.domain.calculations.registry": {
            "ExportComputedKey",
            "ExportDraftAttribute",
            "ModeloId",
            "RegistryValidationError",
            "SourceRefId",
        },
        "_semantic_map": {"VariableEnvelopeSemantic", "SemanticMap", "SemanticMapEntry", "SemanticMapRecord"},
    }
    assert direct_imports == {("re", None)}
    assert not any(
        target.endswith(("load_modelo_directory", "load_record_design_intermediate", "load_render_profile"))
        for target in called_targets
    )
    assert registry_facade.__all__ == [
        "SEMANTIC_MAP_FRAGMENT_SCHEMA_VERSION",
        "EnvelopePrefixField",
        "EnvelopeTotalAnchor",
        "FilingEnvelopePrefixRole",
        "SemanticMap",
        "SemanticMapAnchor",
        "SemanticMapEntry",
        "SemanticMapFragment",
        "SemanticMapRecord",
        "VariableEnvelopeSemantic",
        "load_semantic_map",
    ]
    assert registry_facade.load_semantic_map is load_semantic_map
    assert called_targets & {"cadrumo.core.compile_filing_projection_ref"} == {
        "cadrumo.core.compile_filing_projection_ref",
    }


def test_projection_ref_hydration_cannot_spread_beyond_the_loader() -> None:
    """Raw TOML-to-union conversion has one dev-registry caller."""
    package_root = Path(__file__).resolve().parents[1]
    for module_name in (
        "_semantic_map.py",
        "_semantic_map_validation.py",
        "_semantic_map_join.py",
        "_export_tree.py",
        "_provenance_manifest.py",
    ):
        module_path = package_root / "pipeline" / module_name
        assert "compile_filing_projection_ref" not in module_path.read_text(encoding="utf-8")


def _resolved_call_target(node: ast.expr, imported_aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return imported_aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return f"{_resolved_call_target(node.value, imported_aliases)}.{node.attr}"
    return type(node).__name__
