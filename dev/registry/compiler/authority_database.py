"""Compile a complete validated authority into an indexed SQLite generation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityComponentKind,
    AuthorityComponentQuery,
    EvidenceComponentQuery,
    ExportLayoutComponentQuery,
    GovernedFactComponentQuery,
    ModeloDirectoryComponentQuery,
    ModeloRevisionComponentQuery,
    ProfileSchemaComponentQuery,
    ReferenceComponentQuery,
    RuntimeCatalogueComponentQuery,
    SnapshotGlobalsComponentQuery,
    authority_component_identity,
    encode_authority_component,
)
from cadrumo.domain.calculations.registry.authority_store import AUTHORITY_DATABASE_FORMAT
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import SnapshotGlobalCatalogues
from cadrumo.domain.calculations.registry.snapshot import collect_snapshot_ref_ids
from cadrumo.domain.calculations.registry.temporal import ModeloRevisionDirectory


@dataclass(frozen=True, slots=True)
class CompiledAuthorityDatabase:
    """Closed candidate database and its distinct logical/physical identities."""

    path: Path
    logical_generation: str
    physical_sha256: str
    byte_count: int
    component_count: int


def build_authority_database(path: Path, artifact: AuthorityArtifact) -> CompiledAuthorityDatabase:
    """Write one new complete SQLite candidate from an already validated authority."""
    if artifact.profile_schema is None:
        raise RegistryValidationError("SQLite authority publication requires an enrolled profile schema")
    if path.exists():
        raise RegistryValidationError(f"authority database staging path already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    components = _authority_components(artifact)
    try:
        connection = sqlite3.connect(path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            _create_schema(connection)
            _insert_components(connection, components)
            _insert_dependencies(connection, components)
            connection.execute(
                "INSERT INTO authority_manifest(singleton, format, logical_generation, component_count) "
                "VALUES (1, ?, ?, ?)",
                (AUTHORITY_DATABASE_FORMAT, artifact.identity_digest, len(components)),
            )
            connection.commit()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity != ("ok",):
                raise RegistryValidationError(f"compiled authority database integrity_check failed: {integrity!r}")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise RegistryValidationError("compiled authority database foreign-key closure failed")
            connection.execute("VACUUM")
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise RegistryValidationError(f"authority database compilation failed at {path}") from exc
    payload = path.read_bytes()
    return CompiledAuthorityDatabase(
        path=path,
        logical_generation=artifact.identity_digest,
        physical_sha256=sha256_hex(payload),
        byte_count=len(payload),
        component_count=len(components),
    )


@dataclass(frozen=True, slots=True)
class _CompiledComponent:
    query: AuthorityComponentQuery
    payload: bytes
    dependencies: tuple[AuthorityComponentQuery, ...] = ()


def _authority_components(artifact: AuthorityArtifact) -> tuple[_CompiledComponent, ...]:
    profile_schema = artifact.profile_schema
    if profile_schema is None:
        raise RegistryValidationError("SQLite authority publication requires an enrolled profile schema")
    fact_queries = tuple(GovernedFactComponentQuery(fact_id) for fact_id in sorted(artifact.catalogues.facts.facts))
    components: list[_CompiledComponent] = [
        _CompiledComponent(
            query,
            encode_authority_component(query, artifact.catalogues.facts.facts[query.fact_id]),
        )
        for query in fact_queries
    ]
    profile_query = ProfileSchemaComponentQuery(profile_schema.id)
    components.append(_CompiledComponent(profile_query, encode_authority_component(profile_query, profile_schema)))
    snapshot_globals_query = SnapshotGlobalsComponentQuery()
    components.append(
        _CompiledComponent(
            snapshot_globals_query,
            encode_authority_component(
                snapshot_globals_query,
                SnapshotGlobalCatalogues.from_catalogues(artifact.catalogues),
            ),
            dependencies=fact_queries,
        )
    )
    for family in type(artifact.catalogues.runtime).model_fields:
        query = RuntimeCatalogueComponentQuery(family)
        components.append(
            _CompiledComponent(query, encode_authority_component(query, getattr(artifact.catalogues.runtime, family)))
        )
    for reference_id, reference in sorted(artifact.catalogues.legal.items()):
        query = ReferenceComponentQuery(str(reference_id), AuthorityComponentKind.LEGAL_REFERENCE)
        components.append(_CompiledComponent(query, encode_authority_component(query, reference)))
    for reference_id, reference in sorted(artifact.catalogues.sources.items()):
        query = ReferenceComponentQuery(str(reference_id), AuthorityComponentKind.SOURCE_REFERENCE)
        components.append(_CompiledComponent(query, encode_authority_component(query, reference)))
    for modelo in sorted(artifact.modelos, key=lambda item: str(item.id)):
        directory_query = ModeloDirectoryComponentQuery(str(modelo.id))
        directory = ModeloRevisionDirectory.from_modelo(
            modelo,
            support=artifact.catalogues.supported_filing_years,
        )
        components.append(_CompiledComponent(directory_query, encode_authority_component(directory_query, directory)))
        for revision_id, revision in sorted(modelo.revisions.items(), key=lambda item: str(item[0])):
            query = ModeloRevisionComponentQuery(str(modelo.id), str(revision_id))
            legal_ids, source_ids = collect_snapshot_ref_ids(modelo, revision)
            reference_queries = tuple(
                ReferenceComponentQuery(str(reference_id), AuthorityComponentKind.LEGAL_REFERENCE)
                for reference_id in sorted(legal_ids)
            ) + tuple(
                ReferenceComponentQuery(str(reference_id), AuthorityComponentKind.SOURCE_REFERENCE)
                for reference_id in sorted(source_ids)
            )
            components.append(
                _CompiledComponent(query, encode_authority_component(query, revision), fact_queries + reference_queries)
            )
            for layout in revision.export_layouts:
                layout_query = ExportLayoutComponentQuery(str(modelo.id), str(revision_id), str(layout.id))
                components.append(_CompiledComponent(layout_query, encode_authority_component(layout_query, layout)))
    for item in artifact.evidence.legal:
        query = EvidenceComponentQuery(item.legal_reference_id, AuthorityComponentKind.LEGAL_EVIDENCE)
        components.append(_CompiledComponent(query, encode_authority_component(query, item)))
    for item in artifact.evidence.sources:
        query = EvidenceComponentQuery(item.source_reference_id, AuthorityComponentKind.SOURCE_EVIDENCE)
        components.append(_CompiledComponent(query, encode_authority_component(query, item)))
    return tuple(
        sorted(
            components,
            key=lambda item: (
                authority_component_identity(item.query)[0].value,
                authority_component_identity(item.query)[1],
            ),
        )
    )


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE authority_manifest (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            format TEXT NOT NULL,
            logical_generation TEXT NOT NULL CHECK (length(logical_generation) = 64),
            component_count INTEGER NOT NULL CHECK (component_count > 0)
        ) STRICT;
        CREATE TABLE components (
            kind TEXT NOT NULL,
            key TEXT NOT NULL,
            codec TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
            retained_weight INTEGER NOT NULL CHECK (retained_weight >= 0),
            payload BLOB NOT NULL,
            PRIMARY KEY (kind, key)
        ) STRICT;
        CREATE TABLE dependencies (
            component_kind TEXT NOT NULL,
            component_key TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
            dependency_kind TEXT NOT NULL,
            dependency_key TEXT NOT NULL,
            PRIMARY KEY (component_kind, component_key, ordinal),
            UNIQUE (component_kind, component_key, dependency_kind, dependency_key),
            FOREIGN KEY (component_kind, component_key) REFERENCES components(kind, key),
            FOREIGN KEY (dependency_kind, dependency_key) REFERENCES components(kind, key)
        ) STRICT, WITHOUT ROWID;
        CREATE INDEX dependencies_target ON dependencies(dependency_kind, dependency_key);
        """
    )


def _insert_components(connection: sqlite3.Connection, components: tuple[_CompiledComponent, ...]) -> None:
    for component in components:
        kind, key = authority_component_identity(component.query)
        connection.execute(
            "INSERT INTO components(kind, key, codec, payload_sha256, retained_weight, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                kind.value,
                key,
                "cadrumo-authority-component-v1",
                sha256_hex(component.payload),
                len(component.payload),
                component.payload,
            ),
        )


def _insert_dependencies(connection: sqlite3.Connection, components: tuple[_CompiledComponent, ...]) -> None:
    for component in components:
        kind, key = authority_component_identity(component.query)
        for ordinal, dependency in enumerate(component.dependencies):
            dependency_kind, dependency_key = authority_component_identity(dependency)
            connection.execute(
                "INSERT INTO dependencies(component_kind, component_key, ordinal, dependency_kind, dependency_key) "
                "VALUES (?, ?, ?, ?, ?)",
                (kind.value, key, ordinal, dependency_kind.value, dependency_key),
            )
