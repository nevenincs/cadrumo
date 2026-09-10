"""Authority-publication coverage for record-design catalog identity bindings."""

from __future__ import annotations

import json
import shutil
from pathlib import Path, PurePosixPath

import pytest
from dev.registry.compiler.authority import compile_validated_authority
from dev.registry.compiler.loader import load_registry_tree

from .....core.resources.bundled_data import bundled_path
from ..errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _copied_registry_root(root: Path) -> Path:
    """Return a mutable registry declaration tree over the real bundled corpus."""
    registry_root = root / "registry" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat"), registry_root)
    return registry_root


def _remove_unrelated_invalid_provision_tiers(registry_root: Path) -> None:
    """Keep the temporary fixture focused on catalog bindings, not tier naming."""
    declaration = 'corpus_tier = "provision_excerpt"\n'
    suppressed = 0
    for path in registry_root.rglob("*.toml"):
        contents = path.read_text(encoding="utf-8")
        count = contents.count(declaration)
        if count:
            path.write_text(contents.replace(declaration, ""), encoding="utf-8")
            suppressed += count
    assert suppressed > 0


def test_authority_publication_rejects_divergent_record_design_manifest_binding(tmp_path: Path) -> None:
    """A real authority publishes only while its catalog identity join is exact."""
    registry_root = _copied_registry_root(tmp_path)
    _remove_unrelated_invalid_provision_tiers(registry_root)
    _modelos, catalogues = load_registry_tree(registry_root)
    source = next(
        source
        for source in catalogues.sources.values()
        if source.corpus_path.startswith("corpus/aeat_official/disenos_registro/")
    )
    parts = PurePosixPath(source.corpus_path).parts
    manifest_path = bundled_path(*parts[:4], "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stored_path = PurePosixPath(*parts[4:]).as_posix()
    artifact = next(item for item in manifest["artefacts"] if item["stored_path"] == stored_path)
    assert artifact["url"] == source.source_url

    published = compile_validated_authority(registry_root, bundled_path())

    assert published._registry_validated is True

    declaration_path = next(path for path in registry_root.rglob("*.toml") if f'"{source.id}"' in path.read_text())
    declaration = declaration_path.read_text(encoding="utf-8")
    section_start = declaration.index(f'[sources."{source.id}"]')
    section_end = declaration.find("\n[sources.", section_start + 1)
    if section_end < 0:
        section_end = len(declaration)
    section = declaration[section_start:section_end]
    divergent_url = f"{source.source_url}?divergent-catalogue-binding=1"
    assert f'source_url = "{source.source_url}"' in section
    declaration_path.write_text(
        declaration[:section_start]
        + section.replace(f'source_url = "{source.source_url}"', f'source_url = "{divergent_url}"')
        + declaration[section_end:],
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError, match="does not exactly bind an official artifact catalog identity"):
        compile_validated_authority(registry_root, bundled_path())
