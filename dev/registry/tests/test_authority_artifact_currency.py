"""The indexed-authority currency gate refuses a stale publication and accepts a fresh one.

Every case runs on an isolated temporary registry, source tree and compiler
checkout: the artifact is installed through the real SQLite publisher, read back
through the real runtime reader, and judged against the identity the live inputs
and the re-hashed recorded compiler closure derive.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest
from typer.testing import CliRunner

from cadrumo.core.hashing import canonical_json_bytes, content_hash_hex, sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityBuildIdentity,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
)
from cadrumo.domain.calculations.registry.authority_compiler_closure import AuthorityCompilerClosure
from cadrumo.domain.calculations.registry.authority_store import SQLiteAuthorityReader
from cadrumo.domain.calculations.registry.runtime_catalogues import (
    ApoderamientoScopeRecord,
    CountryVocabularyRecord,
    PublishedIvaPlaceOfSupplyRule,
    PublishedIvaRegulation,
    PublishedRecargoBand,
    RuntimeRegistryCatalogues,
    SpanishPostalTerritory,
    TerritoryCarveOut,
)
from cadrumo.domain.calculations.registry.schema import RegistryCatalogues
from dev.registry.compiler.authority import compiled_bundled_authority

from ..compiler.build_identity import live_compiler_environment, observe_compiler_closure
from ..conformance.cli import app as conformance_app
from ..pipeline.authority_publication import (
    AuthorityBuildInput,
    AuthorityDatabaseCurrency,
    AuthorityDatabaseCurrencyStatus,
    authority_database_currency,
    authority_source_identity,
    install_validated_authority_database,
)
from ._referential_integrity_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REVISION_TOML = 'id = "2025"\nvalid_from = 2025-01-01\n'
_LEGAL_ID = "ley-35-2006:art-1"
_LEGAL_TEXT = "art-1 fixture authority text"
_LOADED_CORE = ("src", "cadrumo", "core", "loaded.py")
_LOADED_COMPILER = ("dev", "registry", "compiler", "loaded_compiler.py")
_UNLOADED_APPLICATION = ("src", "cadrumo", "application", "unloaded.py")
_LOADED_TEST = ("src", "cadrumo", "core", "tests", "test_loaded.py")


def _publication_catalogues() -> RegistryCatalogues:
    """Build the smallest complete typed catalogue set accepted by the artifact boundary."""
    catalogues = minimal_catalogues()
    runtime = RuntimeRegistryCatalogues(
        iva_regulations={
            "fixture-exempt": PublishedIvaRegulation(
                category="fixture-exempt",
                requires_reverse_charge=False,
                requires_supplier_iva_id=False,
                manual_references=(),
                citations=(),
                notes="No legal treatment is asserted by this fixture row.",
                legal_basis_exempt=True,
            )
        },
        iva_place_of_supply={
            "fixture-exempt": PublishedIvaPlaceOfSupplyRule(
                rule_id="fixture-exempt",
                notes="No placement is asserted by this fixture row.",
                legal_basis_exempt=True,
            )
        },
        countries={"ES": CountryVocabularyRecord(code="ES", alpha3="ESP", names=("Espana",))},
        spanish_postal_territories={
            "28": SpanishPostalTerritory(
                postal_prefixes=("28",),
                scope="peninsula_baleares",
                name="Madrid",
                legal_refs=(_LEGAL_ID,),
            )
        },
        territory_carve_outs={
            "ES": TerritoryCarveOut(
                code="ES",
                name="Espana",
                establishes_nothing=True,
                legal_refs=(_LEGAL_ID,),
            )
        },
        recargo_bands={
            "all": PublishedRecargoBand(
                id="all",
                min_completed_months=0,
                surcharge_pct=Decimal("1"),
                legal_ref=_LEGAL_ID,
            )
        },
        apoderamientos_version="fixture-v1",
        apoderamientos_scopes={
            "GENERAL": ApoderamientoScopeRecord(
                code="GENERAL",
                name_es="General",
                name_en="General",
                name_ca="General",
                name_hu="Altalanos",
            )
        },
    ).require_complete()
    compiled = compiled_bundled_authority()
    published_facts = compiled.catalogues.facts
    tax_id_fact = published_facts.facts["spanish-tax-identifier-format"]
    return catalogues.model_copy(
        update={
            "runtime": runtime,
            "facts": published_facts.model_copy(update={"facts": {tax_id_fact.fact_id: tax_id_fact}}),
        }
    )


def _publication_evidence() -> AuthorityEvidenceProjection:
    return AuthorityEvidenceProjection(
        legal=(
            PublishedLegalEvidence(
                legal_reference_id=_LEGAL_ID,
                anchored_text=_LEGAL_TEXT,
                text_sha256=sha256_hex(_LEGAL_TEXT.encode("utf-8")),
            ),
        )
    )


def _stage_inputs(root: Path) -> tuple[Path, Path]:
    """Lay out a small registry and source-evidence tree with LF line endings."""
    registry_root = root / "registry" / "aeat"
    revision_dir = registry_root / "modelos" / "999" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    (registry_root / "modelos" / "999" / "manifest.toml").write_bytes(b'[modelo]\nid = "999"\n')
    (revision_dir / "revision.toml").write_bytes(_REVISION_TOML.encode())
    evidence_dir = root / "corpus" / "test"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "ley.html").write_bytes(b"<html>provision text</html>\r\n")
    profile_schema = root / "registry" / "cadrumo" / "user_profile" / "schema.toml"
    profile_schema.parent.mkdir(parents=True)
    shutil.copyfile(bundled_path("registry", "cadrumo", "user_profile", "schema.toml"), profile_schema)
    return registry_root, root


def _stage_compiler_checkout(root: Path) -> dict[str, Path]:
    """Lay out compiler sources and return the portable roots that anchor them."""
    for parts, text in (
        (_LOADED_CORE, "VALUE = 1\n"),
        (_LOADED_COMPILER, "COMPILED = True\r\n"),
        (_UNLOADED_APPLICATION, "UNUSED = 1\n"),
        (_LOADED_TEST, "def test_value() -> None: ...\n"),
    ):
        path = root.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
    return {"cadrumo": root / "src" / "cadrumo", "dev/registry": root / "dev" / "registry"}


def _loaded_module(path: Path) -> ModuleType:
    module = ModuleType(path.stem)
    module.__file__ = str(path)
    return module


def _observed_closure(checkout: Path, roots: dict[str, Path]) -> AuthorityCompilerClosure:
    """Observe the closure of a process that loaded the core, compiler and test modules only."""
    return observe_compiler_closure(
        modules=(
            *(_loaded_module(checkout.joinpath(*parts)) for parts in (_LOADED_CORE, _LOADED_COMPILER, _LOADED_TEST)),
            ModuleType("namespace_without_file"),
            _loaded_module(checkout.parent / "outside.py"),
        ),
        roots=roots,
    )


def _publish(artifact_path: Path, build_identity: AuthorityBuildIdentity, closure: AuthorityCompilerClosure) -> None:
    """Install a generation recording ``build_identity`` and ``closure`` through the real publisher."""
    install_validated_authority_database(
        AuthorityArtifact(
            modelos=(minimal_modelo(minimal_revision()),),
            catalogues=_publication_catalogues(),
            build_identity=build_identity,
            compiler_closure=closure,
            identity_digest=build_identity.identity_digest,
            profile_schema=compiled_bundled_authority().profile_schema(),
            evidence=_publication_evidence(),
        ),
        destination=artifact_path.parent,
        require_current=lambda: None,
    )


@dataclass(frozen=True, slots=True)
class _Publication:
    registry_root: Path
    source_root: Path
    artifact_path: Path
    compiler_checkout: Path
    compiler_roots: dict[str, Path]
    closure: AuthorityCompilerClosure

    def currency(self, artifact_path: Path | None = None) -> AuthorityDatabaseCurrency:
        return authority_database_currency(
            artifact_path or self.artifact_path,
            registry_root=self.registry_root,
            source_root=self.source_root,
            compiler_source_roots=self.compiler_roots,
        )

    def compiler_file(self, parts: tuple[str, ...]) -> Path:
        return self.compiler_checkout.joinpath(*parts)


def _fresh_publication(tmp_path: Path) -> _Publication:
    """Stage inputs and a compiler checkout, then publish an artifact recording their live identity."""
    registry_root, source_root = _stage_inputs(tmp_path / "candidate")
    checkout = tmp_path / "compiler"
    roots = _stage_compiler_checkout(checkout)
    closure = _observed_closure(checkout, roots)
    artifact_path = tmp_path / "published" / "authority.current.json"
    artifact_path.parent.mkdir()
    build = AuthorityBuildIdentity.from_inputs(
        authority_source_identity(registry_root=registry_root, source_root=source_root),
        closure.identity_digest,
    )
    _publish(artifact_path, build, closure)
    return _Publication(registry_root, source_root, artifact_path, checkout, roots, closure)


def _stale_receipts() -> tuple[AuthorityBuildIdentity, AuthorityCompilerClosure]:
    """Receipts for another candidate, whose closure names files no checkout holds."""
    closure = AuthorityCompilerClosure(
        (("cadrumo/stale_fixture.py", sha256_hex(b"stale fixture authority compiler")),),
        live_compiler_environment(),
    )
    build = AuthorityBuildIdentity.from_inputs(sha256_hex(b"stale fixture authority sources"), closure.identity_digest)
    return build, closure


def test_an_artifact_published_from_the_live_inputs_is_current(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)

    currency = publication.currency()

    assert currency.is_current
    assert currency.recorded_identity_digest == currency.candidate_identity_digest
    assert currency.recorded_build_identity == currency.candidate_build_identity
    assert currency.drifted_inputs == ()


def test_the_observed_closure_records_loaded_compiler_sources_portably(tmp_path: Path) -> None:
    """Only loaded, non-test files under a root are recorded, CRLF folded, under their portable prefix."""
    publication = _fresh_publication(tmp_path)

    assert publication.closure.sources == (
        ("cadrumo/core/loaded.py", sha256_hex(b"VALUE = 1\n")),
        ("dev/registry/compiler/loaded_compiler.py", sha256_hex(b"COMPILED = True\n")),
    )


def test_a_publication_observing_this_process_records_the_compiler_itself(tmp_path: Path) -> None:
    """The real observation over this checkout names the compiler and publisher modules and no tests."""
    registry_root, source_root = _stage_inputs(tmp_path / "candidate")
    closure = observe_compiler_closure()
    artifact_path = tmp_path / "published" / "authority.current.json"
    artifact_path.parent.mkdir()
    _publish(
        artifact_path,
        AuthorityBuildIdentity.from_inputs(
            authority_source_identity(registry_root=registry_root, source_root=source_root),
            closure.identity_digest,
        ),
        closure,
    )

    currency = authority_database_currency(artifact_path, registry_root=registry_root, source_root=source_root)
    reader = SQLiteAuthorityReader(artifact_path)
    try:
        recorded = reader.compiler_closure()
    finally:
        reader.close()

    assert currency.is_current
    assert recorded == closure
    recorded_paths = {path for path, _digest in recorded.sources}
    assert {
        "dev/registry/compiler/authority.py",
        "dev/registry/compiler/build_identity.py",
        "dev/registry/pipeline/authority_publication.py",
        "cadrumo/domain/calculations/registry/authority_compiler_closure.py",
    } <= recorded_paths
    assert not any("/tests/" in path for path in recorded_paths)


def test_unchanged_inputs_reproduce_the_same_source_identity(tmp_path: Path) -> None:
    """A no-op build derives the same source identity twice."""
    registry_root, source_root = _stage_inputs(tmp_path / "candidate")

    first = authority_source_identity(registry_root=registry_root, source_root=source_root)
    second = authority_source_identity(registry_root=registry_root, source_root=source_root)

    assert second == first


def test_an_identical_compiler_checkout_elsewhere_observes_the_same_closure(tmp_path: Path) -> None:
    """The closure is path-independent but changes with the recorded sources' content."""
    original = tmp_path / "original"
    original_closure = _observed_closure(original, _stage_compiler_checkout(original))
    relocated = tmp_path / "elsewhere" / "relocated"
    shutil.copytree(original, relocated)
    relocated_roots = {"cadrumo": relocated / "src" / "cadrumo", "dev/registry": relocated / "dev" / "registry"}

    assert _observed_closure(relocated, relocated_roots) == original_closure

    relocated.joinpath(*_LOADED_COMPILER).write_bytes(b"COMPILED = False\n")

    assert _observed_closure(relocated, relocated_roots).identity_digest != original_closure.identity_digest


def test_an_edit_outside_the_recorded_closure_keeps_the_artifact_current(tmp_path: Path) -> None:
    """An unloaded module and a loaded test module cannot change what the compiler ran."""
    publication = _fresh_publication(tmp_path)
    publication.compiler_file(_UNLOADED_APPLICATION).write_bytes(b"UNUSED = 2\n")
    publication.compiler_file(_LOADED_TEST).write_bytes(b"def test_value() -> None:\n    assert False\n")

    assert publication.currency().status is AuthorityDatabaseCurrencyStatus.CURRENT


def test_an_edit_inside_the_recorded_closure_makes_the_compiler_stale(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)
    publication.compiler_file(_LOADED_CORE).write_bytes(b"VALUE = 2\n")

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.STALE
    assert currency.drifted_inputs == (AuthorityBuildInput.COMPILER,)
    assert "drifted: compiler" in currency.detail


def test_a_line_ending_change_inside_the_recorded_closure_is_not_drift(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)
    loaded = publication.compiler_file(_LOADED_CORE)
    loaded.write_bytes(loaded.read_bytes().replace(b"\n", b"\r\n"))

    assert publication.currency().status is AuthorityDatabaseCurrencyStatus.CURRENT


def test_a_deleted_recorded_closure_file_makes_the_compiler_stale(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)
    publication.compiler_file(_LOADED_COMPILER).unlink()

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.STALE
    assert currency.drifted_inputs == (AuthorityBuildInput.COMPILER,)


def test_a_registry_edit_after_publication_makes_the_artifact_stale(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)
    revision = publication.registry_root / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    revision.write_bytes(revision.read_bytes().replace(b"2025-01-01", b"2025-01-02"))

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.STALE
    assert currency.recorded_identity_digest != currency.candidate_identity_digest
    assert currency.drifted_inputs == (AuthorityBuildInput.SOURCE,)
    assert "drifted: source" in currency.detail


def test_a_same_size_registry_edit_with_its_timestamp_restored_is_still_stale(tmp_path: Path) -> None:
    """The identity is content-addressed, so a stat-preserving edit cannot hide."""
    publication = _fresh_publication(tmp_path)
    revision = publication.registry_root / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    before = revision.stat()
    revision.write_bytes(revision.read_bytes().replace(b'"2025"', b'"2026"'))
    os.utime(revision, ns=(before.st_atime_ns, before.st_mtime_ns))

    assert revision.stat().st_size == before.st_size
    assert publication.currency().status is AuthorityDatabaseCurrencyStatus.STALE


def test_a_source_evidence_edit_after_publication_makes_the_artifact_stale(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)
    (publication.source_root / "corpus" / "test" / "ley.html").write_bytes(b"<html>amended provision</html>\r\n")

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.STALE
    assert "logical identity differs" in currency.detail


def test_a_planted_artifact_recording_another_candidate_is_stale(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)
    _publish(publication.artifact_path, *_stale_receipts())

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.STALE
    assert currency.drifted_inputs == (AuthorityBuildInput.SOURCE, AuthorityBuildInput.COMPILER)


def test_an_identical_checkout_elsewhere_derives_the_recorded_identity(tmp_path: Path) -> None:
    """A clone at another absolute path, with fresh timestamps, agrees with the publisher."""
    publication = _fresh_publication(tmp_path)
    clone = tmp_path / "elsewhere" / "clone"
    shutil.copytree(publication.source_root, clone)

    currency = authority_database_currency(
        publication.artifact_path,
        registry_root=clone / "registry" / "aeat",
        source_root=clone,
        compiler_source_roots=publication.compiler_roots,
    )

    assert currency.status is AuthorityDatabaseCurrencyStatus.CURRENT


def test_registry_line_endings_and_working_tree_byproducts_do_not_change_the_identity(tmp_path: Path) -> None:
    """A CRLF working copy of the LF registry, a lock sidecar and bytecode are not candidate changes."""
    publication = _fresh_publication(tmp_path)
    registry_root, source_root = publication.registry_root, publication.source_root
    revision = registry_root / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    revision.write_bytes(revision.read_bytes().replace(b"\n", b"\r\n"))
    (registry_root / ".generated-export-transaction-999-2025.lock").write_bytes(b"")
    (registry_root / "modelos" / "999" / "__pycache__").mkdir()
    (registry_root / "modelos" / "999" / "__pycache__" / "x.cpython-313.pyc").write_bytes(b"\x00")
    (source_root / "corpus" / "test" / "ley.html.lock").write_bytes(b"")

    assert publication.currency().status is AuthorityDatabaseCurrencyStatus.CURRENT


def test_source_evidence_line_endings_are_byte_exact(tmp_path: Path) -> None:
    """Legal evidence is digested raw: a line-ending translation is a real evidence change."""
    publication = _fresh_publication(tmp_path)
    evidence = publication.source_root / "corpus" / "test" / "ley.html"
    evidence.write_bytes(evidence.read_bytes().replace(b"\r\n", b"\n"))

    assert publication.currency().status is AuthorityDatabaseCurrencyStatus.STALE


def test_a_missing_or_malformed_artifact_is_unreadable_rather_than_current(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)
    missing = publication.currency(tmp_path / "authority.current.json")
    publication.artifact_path.write_bytes(b'{"payload":')
    malformed = publication.currency()

    assert missing.status is AuthorityDatabaseCurrencyStatus.UNREADABLE
    assert "AuthorityStoreError" in missing.detail
    assert malformed.status is AuthorityDatabaseCurrencyStatus.UNREADABLE
    assert "AuthorityStoreError" in malformed.detail
    assert missing.recorded_identity_digest is None
    assert missing.candidate_identity_digest is None
    assert missing.candidate_source_identity_digest == authority_source_identity(
        registry_root=publication.registry_root, source_root=publication.source_root
    )


def test_the_integrity_gate_refuses_a_stale_database_on_stderr_before_compiling(tmp_path: Path) -> None:
    """The planted stale copy fails the owning gate with exit 1; the registry is never compiled."""
    publication = _fresh_publication(tmp_path)
    stale = tmp_path / "stale" / "authority.current.json"
    stale.parent.mkdir()
    stale_build, stale_closure = _stale_receipts()
    _publish(stale, stale_build, stale_closure)

    result = CliRunner().invoke(
        conformance_app,
        [
            "integrity",
            "--json",
            "--registry-root",
            str(publication.registry_root),
            "--source-root",
            str(publication.source_root),
            "--authority-descriptor",
            str(stale),
        ],
    )

    assert result.exit_code == 1, result.output
    assert result.stdout == ""
    refusal = json.loads(result.stderr)
    assert refusal["status"] == "refused"
    assert refusal["currency"] == "stale"
    assert refusal["recorded_identity_digest"] == stale_build.identity_digest
    assert (
        refusal["candidate_identity_digest"]
        == authority_database_currency(
            stale, registry_root=publication.registry_root, source_root=publication.source_root
        ).candidate_identity_digest
    )
    assert refusal["republish_with"] == "python -m dev.registry.pipeline publish-authority"


def _rewrite_published_manifest(descriptor_path: Path, statements: tuple[tuple[str, tuple[str, ...]], ...]) -> None:
    """Republish a modified copy of the current database under its own content address."""
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    source = descriptor_path.parent / descriptor["database"]
    staging = descriptor_path.parent / "rewrite.sqlite3"
    shutil.copyfile(source, staging)
    connection = sqlite3.connect(staging)
    try:
        for statement, parameters in statements:
            connection.execute(statement, parameters)
        connection.commit()
        connection.execute("VACUUM")
    finally:
        connection.close()
    payload = staging.read_bytes()
    digest = sha256_hex(payload)
    target = descriptor_path.parent / f"authority-{digest}.sqlite3"
    staging.replace(target)
    descriptor.update({"database": target.name, "database_sha256": digest, "database_size": len(payload)})
    descriptor_path.write_bytes(canonical_json_bytes(descriptor))


def _assert_unknown_generation(currency: AuthorityDatabaseCurrency) -> None:
    assert currency.status is AuthorityDatabaseCurrencyStatus.UNSUPPORTED_FORMAT
    assert currency.recorded_build_identity is None
    assert currency.candidate_build_identity is None
    assert currency.candidate_identity_digest is None
    assert currency.drifted_inputs == ()
    assert not currency.is_current


def test_a_generation_without_build_receipts_reports_them_as_unknown(tmp_path: Path) -> None:
    """A first-format database is refused, never admitted with receipts it did not record."""
    publication = _fresh_publication(tmp_path)
    _rewrite_published_manifest(
        publication.artifact_path,
        (
            (
                "CREATE TABLE legacy_manifest (singleton INTEGER PRIMARY KEY, format TEXT NOT NULL, "
                "logical_generation TEXT NOT NULL, component_count INTEGER NOT NULL) STRICT",
                (),
            ),
            (
                "INSERT INTO legacy_manifest SELECT singleton, ?, logical_generation, component_count "
                "FROM authority_manifest",
                ("cadrumo-authority-sqlite-v1",),
            ),
            ("DROP TABLE authority_manifest", ()),
            ("ALTER TABLE legacy_manifest RENAME TO authority_manifest", ()),
            ("DROP TABLE compiler_sources", ()),
            ("DROP TABLE compiler_environment", ()),
        ),
    )

    _assert_unknown_generation(publication.currency())


def test_a_generation_without_a_compiler_closure_reports_its_build_as_unknown(tmp_path: Path) -> None:
    """A receipts-only database is refused: its compiler receipt cannot be re-hashed without compiling."""
    publication = _fresh_publication(tmp_path)
    _rewrite_published_manifest(
        publication.artifact_path,
        (
            ("UPDATE authority_manifest SET format = ?", ("cadrumo-authority-sqlite-v2",)),
            ("DROP TABLE compiler_sources", ()),
            ("DROP TABLE compiler_environment", ()),
        ),
    )

    currency = publication.currency()

    _assert_unknown_generation(currency)
    assert "AuthorityStoreFormatError" in currency.detail


def test_build_receipts_that_do_not_recompute_the_generation_are_refused(tmp_path: Path) -> None:
    """Receipts are admitted only when they reproduce the published logical generation."""
    publication = _fresh_publication(tmp_path)
    forged, _closure = _stale_receipts()
    _rewrite_published_manifest(
        publication.artifact_path,
        (
            (
                "UPDATE authority_manifest SET source_identity_digest = ?, compiler_identity_digest = ?, "
                "component_dependency_digest = ?",
                (
                    forged.source_identity_digest,
                    forged.compiler_identity_digest,
                    forged.component_dependency_digest,
                ),
            ),
        ),
    )

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.UNREADABLE
    assert "do not recompute" in currency.detail


def test_a_tampered_compiler_closure_row_is_refused_at_admission(tmp_path: Path) -> None:
    """A recorded closure that no longer recomputes the compiler receipt is corruption, not drift."""
    publication = _fresh_publication(tmp_path)
    _rewrite_published_manifest(
        publication.artifact_path,
        (
            (
                "UPDATE compiler_sources SET sha256 = ? WHERE path = ?",
                (sha256_hex(b"VALUE = 2\n"), "cadrumo/core/loaded.py"),
            ),
        ),
    )
    publication.compiler_file(_LOADED_CORE).write_bytes(b"VALUE = 2\n")

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.UNREADABLE
    assert "AuthorityStoreCorruptionError" in currency.detail
    assert "compiler closure does not recompute" in currency.detail
    assert currency.recorded_build_identity is None


def test_the_recorded_dependency_receipt_is_derived_from_source_and_compiler(tmp_path: Path) -> None:
    """Recomputed here from its published schema, independently of the artifact code."""
    recorded = _fresh_publication(tmp_path).currency().recorded_build_identity
    assert recorded is not None

    independent = content_hash_hex(
        {
            "schema": "authority-component-dependencies/v1",
            "component": "complete-authority",
            "source_identity_digest": recorded.source_identity_digest,
            "compiler_identity_digest": recorded.compiler_identity_digest,
        }
    )

    assert recorded.component_dependency_digest == independent


def test_the_recorded_compiler_receipt_is_derived_from_the_recorded_closure(tmp_path: Path) -> None:
    """Recomputed here from its published schema, independently of the closure code."""
    publication = _fresh_publication(tmp_path)
    recorded = publication.currency().recorded_build_identity
    assert recorded is not None
    environment = publication.closure.environment

    independent = content_hash_hex(
        {
            "schema": "authority-compiler-identity/v2",
            "sources": [
                ["cadrumo/core/loaded.py", sha256_hex(b"VALUE = 1\n")],
                ["dev/registry/compiler/loaded_compiler.py", sha256_hex(b"COMPILED = True\n")],
            ],
            "python": environment.python,
            "dependency_manifests": {
                "pyproject.toml": environment.pyproject_sha256,
                "uv.lock": environment.uv_lock_sha256,
            },
            "dependencies": {"pydantic": environment.pydantic, "pydantic-core": environment.pydantic_core},
        }
    )

    assert recorded.compiler_identity_digest == independent


def test_a_dependency_only_receipt_change_is_refused_at_admission(tmp_path: Path) -> None:
    """A dependency receipt cannot drift alone: one that disagrees with its inputs is malformed."""
    publication = _fresh_publication(tmp_path)
    _rewrite_published_manifest(
        publication.artifact_path,
        (("UPDATE authority_manifest SET component_dependency_digest = ?", (sha256_hex(b"forged dependency"),)),),
    )

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.UNREADABLE
    assert "build receipts are malformed" in currency.detail
    assert currency.recorded_build_identity is None
