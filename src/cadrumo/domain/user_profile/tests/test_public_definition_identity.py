"""Hard-cut identity inventory for user-profile domain contracts."""

from __future__ import annotations

import ast
import importlib
import inspect
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PACKAGE = "cadrumo.domain.user_profile"
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _PACKAGE_ROOT.parents[2]
_PROJECT_ROOT = _SOURCE_ROOT.parent

PUBLIC_DEFINITIONS: dict[str, frozenset[str]] = {
    "errors": frozenset(
        {
            "SCHEMA_LOAD_MESSAGE_KEY",
            "STORED_PROFILE_DRIFT_MESSAGE_KEY",
            "UserProfileError",
            "UserProfileSchemaLoadError",
            "UserProfileValidationError",
            "UserProfileNotFoundError",
            "ProfileNotFoundError",
            "ProfileAlreadyExistsError",
            "ProfileSchemaValidationError",
            "ProfilePreflightMissingError",
            "ProfileSnapshotHashMismatchError",
            "ProfileSnapshotNotFoundError",
            "ProfileBucketMismatchError",
            "ProfileExportError",
            "ProfileImportError",
            "ProfileImportSignatureError",
            "ProfileImportCollisionError",
            "StoredProfileDriftError",
        },
    ),
    "labels": frozenset(
        {
            "profile_section_title_key",
            "profile_field_label_key",
            "profile_section_title",
            "profile_field_label",
            "profile_schema_locale_keys",
        },
    ),
    "loader": frozenset(
        {
            "CONDITION_SCHEMA_PATH_STAT",
            "CONDITION_SCHEMA_TOML_PARSE",
            "CONDITION_SCHEMA_TABLE_PRESENT",
            "CONDITION_SECTIONS_TABLE_PRESENT",
            "CONDITION_DERIVED_SELECTORS_ARRAY",
            "CONDITION_SCHEMA_MODEL_VALID",
            "load_user_profile_schema",
        },
    ),
    "portable_export": frozenset({"CarriedSecureObject", "CoverageManifest", "UserProfilePortableExport"}),
    "registry_contract": frozenset(
        {
            "UserProfileRegistryContractIssue",
            "UserProfileSelectorIndex",
            "UserProfileRegistryContractReport",
            "build_user_profile_selector_index",
            "validate_user_profile_registry_contract",
            "profile_binding_selectors",
        },
    ),
    "schema": frozenset(
        {
            "ProfileFieldType",
            "ProfileSnapshotPolicy",
            "ProfileRemovePolicy",
            "ProfileFieldDefinition",
            "ProfileSectionDefinition",
            "ProfileDerivedSelectorDefinition",
            "derived_selector_for_path",
            "ProfileSchemaDefinition",
            "NUMERIC_PROFILE_FIELD_TYPES",
            "numeric_value_refusal",
            "boolean_value_refusal",
            "ProfileValueRefusalKind",
            "ProfileValueRefusal",
            "date_value_refusal",
            "email_value_refusal",
            "enum_value_refusal",
            "profile_value_refusal",
        },
    ),
    "values": frozenset(
        {
            "declared_provenance_sources",
            "declared_field_paths",
            "section_field_key",
            "UserProfileFactValue",
            "ProfileSetupState",
            "new_profile_id",
            "new_profile_snapshot_id",
            "UserProfileFact",
            "UserProfileRecord",
            "UserProfileSnapshot",
        },
    ),
}

_PRIVATE_LEAVES = frozenset(
    {"errors", "labels", "loader", "portable_export", "registry_contract", "schema", "values"},
)


def _defined_public_names(path: Path) -> set[str]:
    """Return public definitions declared directly by one module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            name = node.name
            if not name.startswith("_"):
                names.add(name)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            if not node.name.id.startswith("_"):
                names.add(node.name.id)
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            names.update(
                target.id for target in targets if isinstance(target, ast.Name) and not target.id.startswith("_")
            )
    return names


def test_public_definition_inventory_is_exhaustive_and_identity_preserving() -> None:
    """Every public user-profile contract has one defining module and one identity."""
    assert set(PUBLIC_DEFINITIONS) == _PRIVATE_LEAVES
    for module_name, expected_names in PUBLIC_DEFINITIONS.items():
        module_path = _PACKAGE_ROOT / f"{module_name}.py"
        assert _defined_public_names(module_path) == set(expected_names), module_name
        module = importlib.import_module(f"{_PACKAGE}.{module_name}")
        for symbol_name in expected_names:
            value = getattr(module, symbol_name)
            assert module.__dict__[symbol_name] is value
            if inspect.isclass(value) or inspect.isfunction(value):
                assert value.__module__ == module.__name__, f"{module.__name__}.{symbol_name} is not defined here"


def test_package_namespace_is_inert() -> None:
    """The structural package root imports, exports, and lazily resolves nothing."""
    package = importlib.import_module(_PACKAGE)
    assert package.__all__ == []
    tree = ast.parse((_PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8"))
    assert not [
        node
        for node in tree.body
        if isinstance(node, ast.Import | ast.ImportFrom | ast.FunctionDef | ast.AsyncFunctionDef)
    ]


def test_no_facade_or_private_user_profile_reference_remains() -> None:
    """Static, dynamic, type, embedded, and doc consumers name defining modules."""
    private = "|".join(sorted(_PRIVATE_LEAVES))
    private_pattern = re.compile(rf"(?:cadrumo\.)?domain\.user_profile\._(?:{private})\b")
    facade_import_pattern = re.compile(r"from\s+(?:cadrumo\.|\.+)?domain\.user_profile\s+import\b")
    violations: list[str] = []
    for root in (_PROJECT_ROOT / "src", _PROJECT_ROOT / "docs"):
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".rst", ".md", ".toml", ".json"}:
                continue
            text = path.read_text(encoding="utf-8")
            if private_pattern.search(text) or facade_import_pattern.search(text):
                violations.append(path.relative_to(_PROJECT_ROOT).as_posix())
    assert not violations, "stale user-profile facade/private references:\n  " + "\n  ".join(sorted(violations))
