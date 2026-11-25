"""The cross-process copy of the validated bundled registry.

One module compiles the real bundled registry from its TOML once, with the
compiled-tree pickle pointed at an empty directory, and every test publishes
and reads copies of that compile in its own directory. The copy must restore
typed content equal to the compile, refuse every torn, altered or stale copy,
and never exist for a tree other than the bundled one.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.tests.env_scope import scoped_env_var

from ..authority import (
    CompilationReceipt,
    StructuralRegistryComponents,
    compilation_receipt,
    compile_structural_authority,
)
from ..loader import clear_registry_tree_cache
from ..loader_cache import REGISTRY_DISK_CACHE_DIR_ENV
from ..validated_authority_copy import (
    ValidatedAuthorityCopy,
    publish_validated_authority_copy,
    read_validated_authority_copy,
    validated_authority_copy_key,
    validated_authority_copy_path,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


@dataclass(frozen=True, slots=True)
class _FreshCompile:
    receipt: CompilationReceipt
    components: StructuralRegistryComponents
    key: str

    def copy(self) -> ValidatedAuthorityCopy:
        return ValidatedAuthorityCopy(
            modelos=self.components.modelos,
            catalogues=self.components.catalogues,
            identity_digest=self.components.identity_digest,
            profile_schema=self.components.profile_schema,
        )


@pytest.fixture(scope="module")
def fresh_compile(tmp_path_factory: pytest.TempPathFactory) -> _FreshCompile:
    """Compile the bundled registry from TOML, bypassing every cached tree."""
    tree_cache = tmp_path_factory.mktemp("registry-disk-cache")
    clear_registry_tree_cache()
    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV, str(tree_cache)):
        receipt = compilation_receipt(bundled_path("registry", "aeat"), bundled_path())
        components = compile_structural_authority(
            receipt.pair.registry_root,
            receipt.pair.source_root,
            identity=receipt.identity,
            profile_schema_path=receipt.profile_schema_path,
            captured_profile_schema=receipt.captured_profile_schema,
        )
    assert receipt.verdicts is not None
    key = validated_authority_copy_key(
        registry_root=receipt.pair.registry_root,
        source_root=receipt.pair.source_root,
        registry_identity_digest=receipt.identity.digest,
        source_receipt=receipt.source_receipt,
        compiler_source_tree_digest=receipt.compiler_source_tree_digest,
        validation_key=receipt.verdicts.registry_key,
    )
    assert key is not None, "the bundled registry must be eligible for a copy"
    return _FreshCompile(receipt=receipt, components=components, key=key)


def test_the_copy_restores_what_a_fresh_compile_produced(fresh_compile: _FreshCompile, tmp_path: Path) -> None:
    expected = fresh_compile.components
    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV, str(tmp_path)):
        assert read_validated_authority_copy(fresh_compile.key) is None, "an empty store must miss"
        assert publish_validated_authority_copy(fresh_compile.key, fresh_compile.copy())
        restored = read_validated_authority_copy(fresh_compile.key)

    assert restored is not None
    assert restored.catalogues is not expected.catalogues, "the copy must be decoded, not shared"
    assert restored.identity_digest == expected.identity_digest == fresh_compile.receipt.identity.digest
    assert restored.modelos == expected.modelos
    assert restored.catalogues == expected.catalogues
    assert restored.profile_schema == expected.profile_schema
    through_copy = ValidatedRegistryAuthority.from_validated_components(
        modelos=restored.modelos,
        catalogues=restored.catalogues,
        identity_digest=restored.identity_digest,
        profile_schema=restored.profile_schema,
    )
    compiled = ValidatedRegistryAuthority.from_validated_components(
        modelos=expected.modelos,
        catalogues=expected.catalogues,
        identity_digest=expected.identity_digest,
        profile_schema=expected.profile_schema,
    )
    assert through_copy.modelos_by_id == compiled.modelos_by_id
    assert through_copy.profile_schema() == compiled.profile_schema()


def test_a_torn_or_altered_copy_is_refused_and_removed(fresh_compile: _FreshCompile, tmp_path: Path) -> None:
    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV, str(tmp_path)):
        path = validated_authority_copy_path(fresh_compile.key)
        assert publish_validated_authority_copy(fresh_compile.key, fresh_compile.copy())
        published = path.read_bytes()

        altered = bytearray(published)
        altered[len(altered) // 2] ^= 0x01
        path.write_bytes(bytes(altered))
        assert read_validated_authority_copy(fresh_compile.key) is None
        assert not path.exists(), "a refused copy must be removed so the next publication replaces it"

        path.write_bytes(published[: len(published) // 2])
        assert read_validated_authority_copy(fresh_compile.key) is None
        assert not path.exists()

        other_key = "f" * len(fresh_compile.key)
        validated_authority_copy_path(other_key).write_bytes(published)
        assert read_validated_authority_copy(other_key) is None, "a copy filed under another key must be refused"


def test_an_edited_module_the_compile_had_loaded_refuses_the_copy(
    fresh_compile: _FreshCompile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "module_source" / "compile_input.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\n", encoding="utf-8")
    module = ModuleType("dev.compile_input_probe")
    module.__file__ = str(source)
    monkeypatch.setitem(sys.modules, module.__name__, module)

    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV, str(tmp_path / "copies")):
        assert publish_validated_authority_copy(fresh_compile.key, fresh_compile.copy())
        assert read_validated_authority_copy(fresh_compile.key) is not None

        source.write_text("VALUE = 2\n", encoding="utf-8")
        assert read_validated_authority_copy(fresh_compile.key) is None


def test_a_live_publication_claim_holds_off_a_second_publisher(fresh_compile: _FreshCompile, tmp_path: Path) -> None:
    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV, str(tmp_path)):
        path = validated_authority_copy_path(fresh_compile.key)
        claim = path.with_name(f"{path.name}.claim")
        claim.write_text(str(os.getpid()), encoding="ascii")

        assert not publish_validated_authority_copy(fresh_compile.key, fresh_compile.copy())
        assert not path.exists()
        assert claim.exists(), "a publisher must not remove a claim held by a live peer"


def test_no_copy_exists_for_a_mutable_or_foreign_root(tmp_path: Path) -> None:
    bundled_registry = bundled_path("registry", "aeat").resolve()
    bundled_sources = bundled_path().resolve()
    mutable_registry = tmp_path / "registry" / "aeat"
    mutable_registry.mkdir(parents=True)
    digests = {
        "registry_identity_digest": "1" * 64,
        "source_receipt": "2" * 64,
        "compiler_source_tree_digest": "3" * 64,
    }

    assert (
        validated_authority_copy_key(
            registry_root=bundled_registry, source_root=bundled_sources, validation_key="4" * 64, **digests
        )
        is not None
    ), "the refusals below mean nothing unless the bundled pair is eligible"
    assert (
        validated_authority_copy_key(
            registry_root=mutable_registry.resolve(), source_root=bundled_sources, validation_key="4" * 64, **digests
        )
        is None
    )
    assert (
        validated_authority_copy_key(
            registry_root=bundled_registry, source_root=tmp_path.resolve(), validation_key="4" * 64, **digests
        )
        is None
    )
    assert (
        validated_authority_copy_key(
            registry_root=bundled_registry, source_root=bundled_sources, validation_key=None, **digests
        )
        is None
    )
