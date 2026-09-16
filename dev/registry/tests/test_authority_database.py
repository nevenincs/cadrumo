"""SQLite authority compiler and read-only admission contracts."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Concatenate

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityBuildIdentity,
    AuthorityComponentCodecError,
    AuthorityEvidenceProjection,
    ModeloDirectoryComponentQuery,
    ProfileSchemaComponentQuery,
)
from cadrumo.domain.calculations.registry.authority_store import (
    AuthorityDescriptor,
    AuthorityStoreCorruptionError,
    SQLiteAuthorityReader,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import MappingFactQuery
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.tests.artifact_runtime_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
)
from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition

from ..compiler import authority_database as authority_database_compiler
from ..compiler.authority_database import build_authority_database, require_acyclic_authority_dependencies
from ..compiler.profile_schema import capture_profile_schema
from ..pipeline import authority_publication
from ..pipeline.authority_publication import install_validated_authority_database, promote_accepted_authority_database

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_retired_whole_authority_json_surfaces_do_not_exist() -> None:
    """Keep SQLite as the only authority publication and admission implementation."""
    repository_root = Path(__file__).resolve().parents[3]
    retired_paths = (
        repository_root / "dev/registry/authority_json.py",
        repository_root / "dev/registry/benchmark_authority.py",
        repository_root / "src/cadrumo/_data/registry/authority/authority.json",
    )

    assert not tuple(path.relative_to(repository_root) for path in retired_paths if path.exists())


def test_publication_proof_refuses_a_complete_dependency_cycle() -> None:
    rows = [
        ("modelo_revision", "100rev", "governed_fact", "fact-a"),
        ("governed_fact", "fact-a", "modelo_revision", "100rev"),
    ]

    with pytest.raises(RegistryValidationError, match="dependency cycle"):
        require_acyclic_authority_dependencies(rows)


def _publishes_nothing(destination: Path) -> bool:
    return not (destination / "authority.current.json").exists() and not list(destination.glob("authority-*.sqlite3"))


def _followed_by[**P](
    real: Callable[Concatenate[sqlite3.Connection, P], None],
    extra: Callable[[sqlite3.Connection], None],
) -> Callable[Concatenate[sqlite3.Connection, P], None]:
    """Run ``real`` unchanged, then ``extra`` on the same candidate connection."""

    def wrapped(connection: sqlite3.Connection, /, *args: P.args, **kwargs: P.kwargs) -> None:
        real(connection, *args, **kwargs)
        extra(connection)

    return wrapped


def test_publication_refuses_a_cyclic_candidate_before_writing_a_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def add_a_reverse_edge(connection: sqlite3.Connection) -> None:
        component_kind, component_key, dependency_kind, dependency_key = connection.execute(
            "SELECT component_kind, component_key, dependency_kind, dependency_key FROM dependencies LIMIT 1"
        ).fetchone()
        connection.execute(
            "INSERT INTO dependencies(component_kind, component_key, ordinal, dependency_kind, dependency_key) "
            "VALUES (?, ?, 0, ?, ?)",
            (dependency_kind, dependency_key, component_kind, component_key),
        )

    monkeypatch.setattr(
        authority_database_compiler,
        "_insert_dependencies",
        _followed_by(authority_database_compiler._insert_dependencies, add_a_reverse_edge),
    )

    with pytest.raises(RegistryValidationError, match="dependency cycle"):
        install_validated_authority_database(_artifact(), destination=tmp_path, require_current=lambda: None)
    assert _publishes_nothing(tmp_path)


def test_publication_refuses_a_candidate_with_a_dangling_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def add_a_dangling_edge(connection: sqlite3.Connection) -> None:
        component_kind, component_key = connection.execute(
            "SELECT component_kind, component_key FROM dependencies LIMIT 1"
        ).fetchone()
        connection.execute(
            "INSERT INTO dependencies(component_kind, component_key, ordinal, dependency_kind, dependency_key) "
            "VALUES (?, ?, 999, 'governed_fact', 'no-such-fact')",
            (component_kind, component_key),
        )

    monkeypatch.setattr(
        authority_database_compiler,
        "_insert_dependencies",
        _followed_by(authority_database_compiler._insert_dependencies, add_a_dangling_edge),
    )

    with pytest.raises(RegistryValidationError, match="authority database compilation failed"):
        install_validated_authority_database(_artifact(), destination=tmp_path, require_current=lambda: None)
    assert _publishes_nothing(tmp_path)


def test_publication_foreign_key_check_refuses_an_unenforced_dangling_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The closure scan must catch a dangling edge that insert-time enforcement never saw."""

    def disable_enforcement(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA foreign_keys = OFF")

    def add_a_dangling_edge(connection: sqlite3.Connection) -> None:
        component_kind, component_key = connection.execute(
            "SELECT component_kind, component_key FROM dependencies LIMIT 1"
        ).fetchone()
        connection.execute(
            "INSERT INTO dependencies(component_kind, component_key, ordinal, dependency_kind, dependency_key) "
            "VALUES (?, ?, 999, 'governed_fact', 'no-such-fact')",
            (component_kind, component_key),
        )

    monkeypatch.setattr(
        authority_database_compiler,
        "_create_schema",
        _followed_by(authority_database_compiler._create_schema, disable_enforcement),
    )
    monkeypatch.setattr(
        authority_database_compiler,
        "_insert_dependencies",
        _followed_by(authority_database_compiler._insert_dependencies, add_a_dangling_edge),
    )

    with pytest.raises(RegistryValidationError, match="foreign-key closure failed"):
        install_validated_authority_database(_artifact(), destination=tmp_path, require_current=lambda: None)
    assert _publishes_nothing(tmp_path)


def _artifact() -> AuthorityArtifact:
    build_identity = AuthorityBuildIdentity.from_inputs(sha256_hex(b"source"), sha256_hex(b"compiler"))
    profile_schema = capture_profile_schema(bundled_path("registry", "cadrumo", "user_profile", "schema.toml"))[1]
    catalogues = minimal_catalogues()
    # Snapshot validation resolves this declaration even when the miniature
    # revision has no retenciones binding and therefore requires no redirect.
    route = GovernedFact.model_validate(
        {
            "fact_id": "m130-retenciones-output-routing",
            "family": "mapping",
            "provider_id": "artifact-fixture",
            "variants": (
                {
                    "variant_id": "m130-retenciones-output-routing:fixture",
                    "date_axis": "filing_period",
                    "valid_from": date(2024, 1, 1),
                    "legal_refs": ("ley-35-2006:art-1",),
                    "review_status": "agent_reviewed",
                    "ownership": "authored",
                    "payload": {
                        "kind": "mapping",
                        "entries": (
                            {"key": "modelo", "value": "130"},
                            {"key": "binding_id", "value": "fixture-retenciones"},
                            {"key": "output_casilla", "value": "01"},
                        ),
                    },
                },
            ),
        }
    )
    catalogues = catalogues.model_copy(
        update={"facts": GovernedFactCatalogue(facts={**catalogues.facts.facts, route.fact_id: route})}
    )
    return AuthorityArtifact(
        modelos=(minimal_modelo(minimal_revision()),),
        catalogues=catalogues,
        identity_digest=build_identity.identity_digest,
        build_identity=build_identity,
        evidence=AuthorityEvidenceProjection(),
        profile_schema=profile_schema,
    )


def _published_candidate(directory: Path) -> Path:
    compiled = build_authority_database(directory / "candidate.sqlite3", _artifact())
    database_name = f"authority-{compiled.physical_sha256}.sqlite3"
    compiled.path.replace(directory / database_name)
    descriptor = AuthorityDescriptor(
        database=database_name,
        database_size=compiled.byte_count,
        database_sha256=compiled.physical_sha256,
        logical_generation=compiled.logical_generation,
    )
    descriptor_path = directory / "authority.current.json"
    descriptor_path.write_bytes(descriptor.to_bytes())
    return descriptor_path


def test_profile_component_load_is_generation_pinned_and_lazy(tmp_path: Path) -> None:
    reader = SQLiteAuthorityReader(_published_candidate(tmp_path), max_connections=2)
    try:
        assert reader.telemetry().entries == 0
        with reader.lease() as pin:
            profile = reader.load(ProfileSchemaComponentQuery(), pin=pin)
        assert isinstance(profile, ProfileSchemaDefinition)
        assert profile.id == "cadrumo.user_profile"
        assert reader.telemetry().entries == 1
        assert reader.active_leases == 0
    finally:
        reader.close()


def test_cached_loads_verify_database_identity_once_per_lease_not_per_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader = SQLiteAuthorityReader(_published_candidate(tmp_path), max_connections=2)
    verifications: list[None] = []
    real_verify = reader._verify_database_identity

    def counting_verify() -> None:
        verifications.append(None)
        real_verify()

    monkeypatch.setattr(reader, "_verify_database_identity", counting_verify)
    try:
        with reader.lease() as pin:
            first = reader.load(ProfileSchemaComponentQuery(), pin=pin)
            repeats = [reader.load(ProfileSchemaComponentQuery(), pin=pin) for _ in range(50)]

        assert all(repeat is first for repeat in repeats)
        # One for the lease's pin, one for the single database read.
        assert len(verifications) == 2

        verifications.clear()
        with reader.lease() as pin:
            warm = [reader.load(ProfileSchemaComponentQuery(), pin=pin) for _ in range(50)]

        assert all(value is first for value in warm)
        assert len(verifications) == 1
    finally:
        reader.close()


def test_a_database_changed_under_the_reader_is_refused_at_its_next_database_touch(tmp_path: Path) -> None:
    descriptor_path = _published_candidate(tmp_path)
    database = tmp_path / AuthorityDescriptor.read(descriptor_path).database
    reader = SQLiteAuthorityReader(descriptor_path, max_connections=2)
    try:
        with reader.lease() as pin:
            profile = reader.load(ProfileSchemaComponentQuery(), pin=pin)
            status = database.stat()
            os.utime(database, ns=(status.st_atime_ns, status.st_mtime_ns + 1_000_000_000))

            # The lease pinned this generation, and a cache hit reads no file.
            assert reader.load(ProfileSchemaComponentQuery(), pin=pin) is profile
            with pytest.raises(AuthorityStoreCorruptionError, match="changed after admission"):
                reader.load(ModeloDirectoryComponentQuery("130"), pin=pin)

        assert reader.telemetry().entries == 0
        with pytest.raises(AuthorityStoreCorruptionError, match="changed after admission"), reader.lease():
            pass
    finally:
        reader.close()


def test_revision_context_selects_directory_before_one_complete_revision(tmp_path: Path) -> None:
    authority = IndexedRegistryAuthority(_published_candidate(tmp_path))
    try:
        with authority.operation() as operation:
            directory = operation.modelo_directory("130")
            selected = operation.revision_for_context("130", filing_year=2025, period="0A")
            assert str(selected.id) == str(directory.revisions[0].id)
            snapshot = operation.snapshot(
                "130",
                filing_year=2025,
                period="0A",
                grade=RegistryAuthorityGrade.CALCULATION,
            )
            assert snapshot.modelo.revisions == {snapshot.revision.id: snapshot.revision}
            assert operation.legal_reference("ley-35-2006:art-1").id == "ley-35-2006:art-1"
            assert operation.source_reference("aeat-dr-130-2019-v12").id == "aeat-dr-130-2019-v12"
    finally:
        authority.close()


def test_operation_reuses_generation_scoped_fact_resolutions(tmp_path: Path) -> None:
    authority = IndexedRegistryAuthority(_published_candidate(tmp_path))
    query = MappingFactQuery(
        fact_id="spanish-tax-identifier-format",
        date_axis=DateAxis.FILING_PERIOD,
        effective_date=date(2025, 1, 1),
    )
    try:
        with authority.operation() as first_operation:
            first = first_operation.resolve_governed_fact(query)
        with authority.operation() as second_operation:
            second = second_operation.resolve_governed_fact(query)

        assert second_operation is first_operation
        assert second is first
    finally:
        authority.close()


def test_admission_refuses_physical_database_tamper(tmp_path: Path) -> None:
    descriptor_path = _published_candidate(tmp_path)
    descriptor = AuthorityDescriptor.read(descriptor_path)
    database = tmp_path / descriptor.database
    payload = bytearray(database.read_bytes())
    payload[-1] ^= 1
    database.write_bytes(payload)

    with pytest.raises(AuthorityStoreCorruptionError, match="disagree with the published descriptor"):
        SQLiteAuthorityReader(descriptor_path)


def test_digest_consistent_unused_component_refuses_only_when_requested(tmp_path: Path) -> None:
    """Admission is physical/global; strict typed decoding remains on demand."""
    descriptor_path = _published_candidate(tmp_path)
    original = AuthorityDescriptor.read(descriptor_path)
    database = tmp_path / original.database
    with closing(sqlite3.connect(database)) as connection:
        (encoded,) = connection.execute(
            "SELECT payload FROM components WHERE kind = ? AND key = ?",
            ("profile_schema", "cadrumo.user_profile"),
        ).fetchone()
        frame = json.loads(encoded)
        frame["payload"] = {}
        malformed = json.dumps(frame).encode("utf-8")
        connection.execute(
            "UPDATE components SET payload = ?, payload_sha256 = ?, retained_weight = ? WHERE kind = ? AND key = ?",
            (malformed, sha256_hex(malformed), len(malformed), "profile_schema", "cadrumo.user_profile"),
        )
        connection.commit()
    payload = database.read_bytes()
    physical_digest = sha256_hex(payload)
    renamed = tmp_path / f"authority-{physical_digest}.sqlite3"
    database.replace(renamed)
    descriptor_path.write_bytes(
        AuthorityDescriptor(
            database=renamed.name,
            database_size=len(payload),
            database_sha256=physical_digest,
            logical_generation=original.logical_generation,
        ).to_bytes()
    )

    reader = SQLiteAuthorityReader(descriptor_path)
    try:
        assert reader.telemetry().entries == 0
        with reader.lease() as pin, pytest.raises(AuthorityComponentCodecError, match="failed typed decoding"):
            reader.load(ProfileSchemaComponentQuery(), pin=pin)
        assert reader.telemetry().entries == 0
    finally:
        reader.close()


def test_failed_currentness_check_preserves_the_previous_descriptor(tmp_path: Path) -> None:
    descriptor_path = tmp_path / "authority.current.json"
    descriptor_path.write_bytes(b"previous descriptor bytes")

    def refuse() -> None:
        raise RuntimeError("candidate changed")

    with pytest.raises(RuntimeError, match="candidate changed"):
        install_validated_authority_database(_artifact(), destination=tmp_path, require_current=refuse)

    assert descriptor_path.read_bytes() == b"previous descriptor bytes"
    assert list(tmp_path.glob("authority-*.sqlite3")) == []


def test_failed_database_flush_removes_the_partial_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_flush(_file_descriptor: int) -> None:
        raise OSError("simulated flush failure")

    monkeypatch.setattr(authority_publication.os, "fsync", refuse_flush)

    with pytest.raises(OSError, match="simulated flush failure"):
        install_validated_authority_database(_artifact(), destination=tmp_path, require_current=lambda: None)

    assert not (tmp_path / "authority.current.json").exists()
    assert list(tmp_path.glob("authority-*.sqlite3")) == []


def test_content_addressed_install_refuses_an_existing_collision(tmp_path: Path) -> None:
    descriptor = install_validated_authority_database(
        _artifact(),
        destination=tmp_path,
        require_current=lambda: None,
    )
    database = tmp_path / descriptor.database
    database.write_bytes(b"different bytes under an accepted digest name")

    with pytest.raises(RegistryValidationError, match="content-addressed authority collision"):
        install_validated_authority_database(
            _artifact(),
            destination=tmp_path,
            require_current=lambda: None,
        )


def test_promotion_copies_the_exact_accepted_bytes_without_recompiling(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    candidate_descriptor = _published_candidate(candidate)
    destination = tmp_path / "published"

    descriptor = promote_accepted_authority_database(candidate_descriptor, destination=destination)

    assert (destination / "authority.current.json").read_bytes() == candidate_descriptor.read_bytes()
    assert (destination / descriptor.database).read_bytes() == (candidate / descriptor.database).read_bytes()


def test_public_installers_serialize_different_generations(tmp_path: Path) -> None:
    first = _artifact()
    second_build = AuthorityBuildIdentity.from_inputs("3" * 64, "4" * 64)
    second = first.__class__(
        modelos=first.modelos,
        catalogues=first.catalogues,
        identity_digest=second_build.identity_digest,
        build_identity=second_build,
        profile_schema=first.profile_schema,
        evidence=first.evidence,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        descriptors = tuple(
            executor.map(
                lambda artifact: install_validated_authority_database(
                    artifact,
                    destination=tmp_path,
                    require_current=lambda: None,
                ),
                (first, second),
            )
        )

    selected = AuthorityDescriptor.read(tmp_path / "authority.current.json")
    assert selected in descriptors
    assert (tmp_path / selected.database).is_file()


def test_candidate_preparation_does_not_hold_the_destination_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A barrier-held validation leaves the publication lock available to another publisher."""
    preparation_started = Event()
    finish_preparation = Event()
    prepared_candidate = SimpleNamespace(artifact=object())
    published_descriptor = object()

    def prepare_candidate(**_kwargs: object) -> object:
        preparation_started.set()
        assert finish_preparation.wait(timeout=5)
        return prepared_candidate

    monkeypatch.setattr(authority_publication, "validate_authority_candidate", prepare_candidate)
    monkeypatch.setattr(authority_publication, "_require_candidate_receipt", lambda candidate: None)
    monkeypatch.setattr(
        authority_publication,
        "_install_validated_authority_database",
        lambda artifact, *, destination, require_current: published_descriptor,
    )
    destination = tmp_path / "published"
    descriptor_path = destination / "authority.current.json"

    with ThreadPoolExecutor(max_workers=1) as executor:
        publication = executor.submit(
            authority_publication.publish_sqlite_authority_candidate,
            registry_root=tmp_path / "registry",
            source_root=tmp_path / "source",
            profile_schema_path=tmp_path / "schema.toml",
            destination=destination,
        )
        assert preparation_started.wait(timeout=5)
        with exclusive_file_lock(descriptor_path, timeout=0, retry_backoff=0.01):
            finish_preparation.set()
        assert publication.result(timeout=5) is published_descriptor


def test_receipt_drift_after_preparation_refuses_before_installation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Locked admission reports input drift and preserves the accepted pointer."""
    destination = tmp_path / "published"
    destination.mkdir()
    descriptor_path = destination / "authority.current.json"
    accepted_descriptor = b"previously accepted descriptor"
    descriptor_path.write_bytes(accepted_descriptor)
    prepared_candidate = SimpleNamespace(
        artifact=object(),
        registry_root=tmp_path / "registry",
        source_root=tmp_path / "source",
        profile_schema_path=tmp_path / "schema.toml",
        receipt=object(),
    )

    monkeypatch.setattr(authority_publication, "validate_authority_candidate", lambda **_kwargs: prepared_candidate)
    monkeypatch.setattr(authority_publication, "_capture_receipt", lambda *_args, **_kwargs: object())

    def unexpected_install(*_args: object, **_kwargs: object) -> None:
        pytest.fail("receipt drift must refuse before database installation")

    monkeypatch.setattr(authority_publication, "_install_validated_authority_database", unexpected_install)

    with pytest.raises(RegistryValidationError, match="input receipt changed") as refusal:
        authority_publication.publish_sqlite_authority_candidate(
            registry_root=tmp_path / "registry",
            source_root=tmp_path / "source",
            profile_schema_path=tmp_path / "schema.toml",
            destination=destination,
        )

    assert "lock" not in str(refusal.value).lower()
    assert "stale" not in str(refusal.value).lower()
    assert descriptor_path.read_bytes() == accepted_descriptor
