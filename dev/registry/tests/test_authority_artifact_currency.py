"""The indexed-authority currency gate follows the law's sources and nothing else.

Every case runs on an isolated temporary registry and source tree: the artifact
is installed through the real SQLite publisher, read back through the real
runtime reader, and judged against the legal identity the live inputs derive.
The compiler and the development environment that built an authority are not
part of its identity, so they are neither recorded nor compared.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
)
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor, SQLiteAuthorityReader
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

from ..conformance.cli import app as conformance_app
from ..pipeline.authority_publication import (
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
_STALE_IDENTITY = sha256_hex(b"stale fixture authority sources")


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


def _publish(artifact_path: Path, identity_digest: str) -> None:
    """Install a generation recording ``identity_digest`` through the real publisher."""
    install_validated_authority_database(
        AuthorityArtifact(
            modelos=(minimal_modelo(minimal_revision()),),
            catalogues=_publication_catalogues(),
            identity_digest=identity_digest,
            profile_schema=compiled_bundled_authority().profile_schema(),
            evidence=_publication_evidence(),
        ),
        destination=artifact_path.parent,
        require_current=lambda: None,
    )


class _Publication:
    def __init__(self, registry_root: Path, source_root: Path, artifact_path: Path) -> None:
        self.registry_root = registry_root
        self.source_root = source_root
        self.artifact_path = artifact_path

    def currency(self, artifact_path: Path | None = None) -> AuthorityDatabaseCurrency:
        return authority_database_currency(
            artifact_path or self.artifact_path,
            registry_root=self.registry_root,
            source_root=self.source_root,
        )

    def source_identity(self) -> str:
        return authority_source_identity(registry_root=self.registry_root, source_root=self.source_root)


def _fresh_publication(tmp_path: Path) -> _Publication:
    """Stage inputs, then publish an artifact recording their live legal identity."""
    registry_root, source_root = _stage_inputs(tmp_path / "candidate")
    artifact_path = tmp_path / "published" / "authority.current.json"
    artifact_path.parent.mkdir()
    _publish(artifact_path, authority_source_identity(registry_root=registry_root, source_root=source_root))
    return _Publication(registry_root, source_root, artifact_path)


def test_an_artifact_published_from_the_live_inputs_is_current(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)

    currency = publication.currency()

    assert currency.is_current
    assert currency.recorded_identity_digest == currency.candidate_identity_digest


def test_the_published_generation_is_the_legal_source_identity(tmp_path: Path) -> None:
    """The runtime reader reports exactly the identity the legal inputs derive, with nothing folded in."""
    publication = _fresh_publication(tmp_path)
    reader = SQLiteAuthorityReader(publication.artifact_path)
    try:
        generation = reader.pin().logical_generation
    finally:
        reader.close()

    assert generation == publication.source_identity()
    assert AuthorityDescriptor.read(publication.artifact_path).logical_generation == generation


def test_the_published_database_records_nothing_about_the_compiler_or_its_environment(tmp_path: Path) -> None:
    """The artifact holds the law and its component graph only: no compiler, interpreter or dependency rows."""
    publication = _fresh_publication(tmp_path)
    descriptor = AuthorityDescriptor.read(publication.artifact_path)
    connection = sqlite3.connect(publication.artifact_path.parent / descriptor.database)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        manifest_columns = {row[1] for row in connection.execute("PRAGMA table_info(authority_manifest)")}
    finally:
        connection.close()

    assert tables == {"authority_manifest", "components", "dependencies"}
    assert manifest_columns == {"singleton", "format", "logical_generation", "component_count"}


def test_unchanged_inputs_reproduce_the_same_source_identity(tmp_path: Path) -> None:
    """A no-op build derives the same source identity twice."""
    registry_root, source_root = _stage_inputs(tmp_path / "candidate")

    first = authority_source_identity(registry_root=registry_root, source_root=source_root)
    second = authority_source_identity(registry_root=registry_root, source_root=source_root)

    assert second == first


def test_a_registry_edit_after_publication_makes_the_artifact_stale(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)
    revision = publication.registry_root / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    revision.write_bytes(revision.read_bytes().replace(b"2025-01-01", b"2025-01-02"))

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.STALE
    assert currency.recorded_identity_digest != currency.candidate_identity_digest
    assert "legal sources changed" in currency.detail


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

    assert publication.currency().status is AuthorityDatabaseCurrencyStatus.STALE


def test_a_profile_schema_edit_after_publication_makes_the_artifact_stale(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)
    schema = publication.source_root / "registry" / "cadrumo" / "user_profile" / "schema.toml"
    schema.write_bytes(schema.read_bytes() + b"\n# amended\n")

    assert publication.currency().status is AuthorityDatabaseCurrencyStatus.STALE


def test_a_planted_artifact_recording_other_sources_is_stale(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)
    _publish(publication.artifact_path, _STALE_IDENTITY)

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.STALE
    assert currency.recorded_identity_digest == _STALE_IDENTITY


def test_an_identical_checkout_elsewhere_derives_the_recorded_identity(tmp_path: Path) -> None:
    """A clone at another absolute path, with fresh timestamps, agrees with the publisher."""
    publication = _fresh_publication(tmp_path)
    clone = tmp_path / "elsewhere" / "clone"
    shutil.copytree(publication.source_root, clone)

    currency = authority_database_currency(
        publication.artifact_path,
        registry_root=clone / "registry" / "aeat",
        source_root=clone,
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
    assert missing.candidate_identity_digest == publication.source_identity()


def test_the_integrity_gate_refuses_a_stale_database_on_stderr_before_compiling(tmp_path: Path) -> None:
    """The planted stale copy fails the owning gate with exit 1; the registry is never compiled."""
    publication = _fresh_publication(tmp_path)
    stale = tmp_path / "stale" / "authority.current.json"
    stale.parent.mkdir()
    _publish(stale, _STALE_IDENTITY)

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
    assert refusal["recorded_identity_digest"] == _STALE_IDENTITY
    assert refusal["candidate_identity_digest"] == publication.source_identity()
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


def test_a_generation_of_an_earlier_format_is_refused_as_unsupported(tmp_path: Path) -> None:
    """A v3 database, which recorded the compiler and its environment, is never admitted or coerced."""
    publication = _fresh_publication(tmp_path)
    _rewrite_published_manifest(
        publication.artifact_path,
        (("UPDATE authority_manifest SET format = ?", ("cadrumo-authority-sqlite-v3",)),),
    )

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.UNSUPPORTED_FORMAT
    assert "AuthorityStoreFormatError" in currency.detail
    assert currency.recorded_identity_digest is None
    assert not currency.is_current


def test_a_manifest_disagreeing_with_its_descriptor_is_refused_at_admission(tmp_path: Path) -> None:
    publication = _fresh_publication(tmp_path)
    _rewrite_published_manifest(
        publication.artifact_path,
        (("UPDATE authority_manifest SET logical_generation = ?", (_STALE_IDENTITY,)),),
    )

    currency = publication.currency()

    assert currency.status is AuthorityDatabaseCurrencyStatus.UNREADABLE
    assert "AuthorityStoreCorruptionError" in currency.detail
