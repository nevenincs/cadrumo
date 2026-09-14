"""The indexed-authority currency gate refuses a stale publication and accepts a fresh one.

Every case runs on an isolated temporary registry and source tree: the artifact
is installed through the real SQLite publisher, read back through the real runtime reader,
and judged against the identity the publisher derives for the live inputs.
"""

from __future__ import annotations

import json
import os
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cadrumo.core.hashing import sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityBuildIdentity,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
)
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

from ..compiler.build_identity import authority_compiler_identity
from ..conformance.cli import app as conformance_app
from ..pipeline.authority_publication import (
    AuthorityDatabaseCurrencyStatus,
    authority_candidate_identity,
    authority_database_currency,
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
_STALE_BUILD_IDENTITY = AuthorityBuildIdentity.from_inputs(
    source_identity_digest=sha256_hex(b"stale fixture authority sources"),
    compiler_identity_digest=sha256_hex(b"stale fixture authority compiler"),
)


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


def _publish(artifact_path: Path, build_identity: AuthorityBuildIdentity) -> None:
    """Install a generation recording ``build_identity`` through the real publisher."""
    install_validated_authority_database(
        AuthorityArtifact(
            modelos=(minimal_modelo(minimal_revision()),),
            catalogues=_publication_catalogues(),
            build_identity=build_identity,
            identity_digest=build_identity.identity_digest,
            profile_schema=compiled_bundled_authority().profile_schema(),
            evidence=_publication_evidence(),
        ),
        destination=artifact_path.parent,
        require_current=lambda: None,
    )


def _fresh_publication(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Stage inputs and publish an artifact recording their live identity."""
    registry_root, source_root = _stage_inputs(tmp_path / "candidate")
    artifact_path = tmp_path / "published" / "authority.current.json"
    artifact_path.parent.mkdir()
    candidate = authority_database_currency(
        artifact_path,
        registry_root=registry_root,
        source_root=source_root,
    ).candidate_build_identity
    _publish(artifact_path, candidate)
    return registry_root, source_root, artifact_path


def _status(artifact_path: Path, registry_root: Path, source_root: Path) -> AuthorityDatabaseCurrencyStatus:
    return authority_database_currency(artifact_path, registry_root=registry_root, source_root=source_root).status


def test_an_artifact_published_from_the_live_inputs_is_current(tmp_path: Path) -> None:
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)

    currency = authority_database_currency(artifact_path, registry_root=registry_root, source_root=source_root)

    assert currency.is_current
    assert currency.recorded_identity_digest == currency.candidate_identity_digest


def test_unchanged_inputs_reproduce_the_same_candidate_identity(tmp_path: Path) -> None:
    """A no-op build derives the same whole-candidate identity twice."""
    registry_root, source_root = _stage_inputs(tmp_path / "candidate")

    first = authority_candidate_identity(registry_root=registry_root, source_root=source_root)
    second = authority_candidate_identity(registry_root=registry_root, source_root=source_root)

    assert second == first


def test_compiler_source_change_updates_portable_compiler_identity(tmp_path: Path) -> None:
    """Compiler identity is path-independent but changes with production source semantics."""
    original = tmp_path / "original"
    source_roots = {"domain": original / "domain", "compiler": original / "compiler"}
    for root in source_roots.values():
        root.mkdir(parents=True)
        (root / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    first = authority_compiler_identity(source_roots=source_roots)

    relocated = tmp_path / "relocated"
    shutil.copytree(original, relocated)
    relocated_roots = {name: relocated / name for name in source_roots}
    assert authority_compiler_identity(source_roots=relocated_roots) == first

    (relocated_roots["compiler"] / "module.py").write_text("VALUE = 2\n", encoding="utf-8")

    assert authority_compiler_identity(source_roots=relocated_roots) != first


def test_a_registry_edit_after_publication_makes_the_artifact_stale(tmp_path: Path) -> None:
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    revision = registry_root / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    revision.write_bytes(revision.read_bytes().replace(b"2025-01-01", b"2025-01-02"))

    currency = authority_database_currency(artifact_path, registry_root=registry_root, source_root=source_root)

    assert currency.status is AuthorityDatabaseCurrencyStatus.STALE
    assert currency.recorded_identity_digest != currency.candidate_identity_digest


def test_a_same_size_registry_edit_with_its_timestamp_restored_is_still_stale(tmp_path: Path) -> None:
    """The identity is content-addressed, so a stat-preserving edit cannot hide."""
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    revision = registry_root / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    before = revision.stat()
    revision.write_bytes(revision.read_bytes().replace(b'"2025"', b'"2026"'))
    os.utime(revision, ns=(before.st_atime_ns, before.st_mtime_ns))

    assert revision.stat().st_size == before.st_size
    assert _status(artifact_path, registry_root, source_root) is AuthorityDatabaseCurrencyStatus.STALE


def test_a_source_evidence_edit_after_publication_makes_the_artifact_stale(tmp_path: Path) -> None:
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    (source_root / "corpus" / "test" / "ley.html").write_bytes(b"<html>amended provision</html>\r\n")

    currency = authority_database_currency(
        artifact_path,
        registry_root=registry_root,
        source_root=source_root,
    )
    assert currency.status is AuthorityDatabaseCurrencyStatus.STALE
    assert "logical identity differs" in currency.detail


def test_a_compiler_only_change_is_reported_separately_from_sources(tmp_path: Path) -> None:
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    current = authority_database_currency(
        artifact_path,
        registry_root=registry_root,
        source_root=source_root,
    ).candidate_build_identity
    compiler_changed = AuthorityBuildIdentity.from_inputs(
        source_identity_digest=current.source_identity_digest,
        compiler_identity_digest=sha256_hex(b"changed compiler fixture"),
    )
    _publish(artifact_path, compiler_changed)

    currency = authority_database_currency(
        artifact_path,
        registry_root=registry_root,
        source_root=source_root,
    )
    assert currency.status is AuthorityDatabaseCurrencyStatus.STALE
    assert "logical identity differs" in currency.detail


def test_a_planted_artifact_recording_another_candidate_is_stale(tmp_path: Path) -> None:
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    _publish(artifact_path, _STALE_BUILD_IDENTITY)

    assert _status(artifact_path, registry_root, source_root) is AuthorityDatabaseCurrencyStatus.STALE


def test_an_identical_checkout_elsewhere_derives_the_recorded_identity(tmp_path: Path) -> None:
    """A clone at another absolute path, with fresh timestamps, agrees with the publisher."""
    _registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    clone = tmp_path / "elsewhere" / "clone"
    shutil.copytree(source_root, clone)

    assert _status(artifact_path, clone / "registry" / "aeat", clone) is AuthorityDatabaseCurrencyStatus.CURRENT


def test_registry_line_endings_and_working_tree_byproducts_do_not_change_the_identity(tmp_path: Path) -> None:
    """A CRLF working copy of the LF registry, a lock sidecar and bytecode are not candidate changes."""
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    revision = registry_root / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    revision.write_bytes(revision.read_bytes().replace(b"\n", b"\r\n"))
    (registry_root / ".generated-export-transaction-999-2025.lock").write_bytes(b"")
    (registry_root / "modelos" / "999" / "__pycache__").mkdir()
    (registry_root / "modelos" / "999" / "__pycache__" / "x.cpython-313.pyc").write_bytes(b"\x00")
    (source_root / "corpus" / "test" / "ley.html.lock").write_bytes(b"")

    assert _status(artifact_path, registry_root, source_root) is AuthorityDatabaseCurrencyStatus.CURRENT


def test_source_evidence_line_endings_are_byte_exact(tmp_path: Path) -> None:
    """Legal evidence is digested raw: a line-ending translation is a real evidence change."""
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    evidence = source_root / "corpus" / "test" / "ley.html"
    evidence.write_bytes(evidence.read_bytes().replace(b"\r\n", b"\n"))

    assert _status(artifact_path, registry_root, source_root) is AuthorityDatabaseCurrencyStatus.STALE


def test_a_missing_or_malformed_artifact_is_unreadable_rather_than_current(tmp_path: Path) -> None:
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    missing = authority_database_currency(
        tmp_path / "authority.current.json", registry_root=registry_root, source_root=source_root
    )
    artifact_path.write_bytes(b'{"payload":')
    malformed = authority_database_currency(artifact_path, registry_root=registry_root, source_root=source_root)

    assert missing.status is AuthorityDatabaseCurrencyStatus.UNREADABLE
    assert "AuthorityStoreError" in missing.detail
    assert malformed.status is AuthorityDatabaseCurrencyStatus.UNREADABLE
    assert "AuthorityStoreError" in malformed.detail
    assert missing.recorded_identity_digest is None


def test_the_integrity_gate_refuses_a_stale_database_on_stderr_before_compiling(tmp_path: Path) -> None:
    """The planted stale copy fails the owning gate with exit 1; the registry is never compiled."""
    registry_root, source_root, _artifact_path = _fresh_publication(tmp_path)
    stale = tmp_path / "stale" / "authority.current.json"
    stale.parent.mkdir()
    _publish(stale, _STALE_BUILD_IDENTITY)

    result = CliRunner().invoke(
        conformance_app,
        [
            "integrity",
            "--json",
            "--registry-root",
            str(registry_root),
            "--source-root",
            str(source_root),
            "--authority-descriptor",
            str(stale),
        ],
    )

    assert result.exit_code == 1, result.output
    assert result.stdout == ""
    refusal = json.loads(result.stderr)
    assert refusal["status"] == "refused"
    assert refusal["currency"] == "stale"
    assert refusal["recorded_identity_digest"] == _STALE_BUILD_IDENTITY.identity_digest
    assert refusal["candidate_identity_digest"] == authority_candidate_identity(
        registry_root=registry_root, source_root=source_root
    )
    assert refusal["republish_with"] == "python -m dev.registry.pipeline publish-authority"
