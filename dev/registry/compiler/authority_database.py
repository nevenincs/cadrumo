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
    decode_authority_component,
    encode_authority_component,
)
from cadrumo.domain.calculations.registry.authority_cache import retained_object_size
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
            require_acyclic_authority_dependencies(
                connection.execute(
                    "SELECT component_kind, component_key, dependency_kind, dependency_key FROM dependencies"
                ).fetchall()
            )
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


def require_acyclic_authority_dependencies(rows: list[tuple[str, str, str, str]]) -> None:
    """Refuse a component dependency graph containing any cycle.

    The runtime reader resolves a component's dependencies recursively and does
    not re-prove this graph, so a cycle must never reach a published database.
    """
    graph: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for component_kind, component_key, dependency_kind, dependency_key in rows:
        graph.setdefault((component_kind, component_key), []).append((dependency_kind, dependency_key))
    visiting: set[tuple[str, str]] = set()
    visited: set[tuple[str, str]] = set()

    def visit(node: tuple[str, str]) -> None:
        if node in visiting:
            raise RegistryValidationError(f"compiled authority database dependency cycle includes {node!r}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph.get(node, ()):
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


@dataclass(frozen=True, slots=True)
class _CompiledComponent:
    query: AuthorityComponentQuery
    payload: bytes
    retained_weight: int
    dependencies: tuple[AuthorityComponentQuery, ...] = ()


def _compiled_component(
    query: AuthorityComponentQuery,
    value: object,
    *,
    payload: bytes | None = None,
    dependencies: tuple[AuthorityComponentQuery, ...] = (),
) -> _CompiledComponent:
    """Encode one component and publish the weight its decoded graph retains.

    The reader charges exactly this weight against its budget instead of
    re-measuring the graph on every load, so it is measured once here.
    """
    encoded = encode_authority_component(query, value) if payload is None else payload
    return _CompiledComponent(query, encoded, max(len(encoded), retained_object_size(value)), dependencies)


def _authority_components(artifact: AuthorityArtifact) -> tuple[_CompiledComponent, ...]:
    profile_schema = artifact.profile_schema
    facts = artifact.catalogues.facts.facts
    fact_queries = tuple(GovernedFactComponentQuery(fact_id) for fact_id in sorted(facts))
    fact_values = tuple(facts[query.fact_id] for query in fact_queries)
    components: list[_CompiledComponent] = [
        _compiled_component(query, artifact.catalogues.facts.facts[query.fact_id]) for query in fact_queries
    ]
    profile_query = ProfileSchemaComponentQuery(profile_schema.id)
    components.append(_compiled_component(profile_query, profile_schema))
    snapshot_globals_query = SnapshotGlobalsComponentQuery()
    snapshot_globals = SnapshotGlobalCatalogues.from_catalogues(artifact.catalogues)
    snapshot_globals_payload = encode_authority_component(snapshot_globals_query, snapshot_globals)
    components.append(
        _compiled_component(
            snapshot_globals_query,
            snapshot_globals,
            payload=snapshot_globals_payload,
            dependencies=_decoded_fact_dependencies(
                snapshot_globals_query,
                snapshot_globals_payload,
                fact_queries,
                fact_values,
            ),
        )
    )
    for family in type(artifact.catalogues.runtime).model_fields:
        query = RuntimeCatalogueComponentQuery(family)
        components.append(_compiled_component(query, getattr(artifact.catalogues.runtime, family)))
    for reference_id, reference in sorted(artifact.catalogues.legal.items()):
        query = ReferenceComponentQuery(str(reference_id), AuthorityComponentKind.LEGAL_REFERENCE)
        components.append(_compiled_component(query, reference))
    for reference_id, reference in sorted(artifact.catalogues.sources.items()):
        query = ReferenceComponentQuery(str(reference_id), AuthorityComponentKind.SOURCE_REFERENCE)
        components.append(_compiled_component(query, reference))
    for modelo in sorted(artifact.modelos, key=lambda item: str(item.id)):
        directory_query = ModeloDirectoryComponentQuery(str(modelo.id))
        directory = ModeloRevisionDirectory.from_modelo(
            modelo,
            support=artifact.catalogues.supported_filing_years,
        )
        components.append(_compiled_component(directory_query, directory))
        for revision_id, revision in sorted(modelo.revisions.items(), key=lambda item: str(item[0])):
            query = ModeloRevisionComponentQuery(str(modelo.id), str(revision_id))
            base_revision = revision.model_copy(update={"export_layouts": ()})
            payload = encode_authority_component(query, base_revision)
            legal_ids, source_ids = collect_snapshot_ref_ids(modelo, base_revision)
            reference_queries = tuple(
                ReferenceComponentQuery(str(reference_id), AuthorityComponentKind.LEGAL_REFERENCE)
                for reference_id in sorted(legal_ids)
            ) + tuple(
                ReferenceComponentQuery(str(reference_id), AuthorityComponentKind.SOURCE_REFERENCE)
                for reference_id in sorted(source_ids)
            )
            revision_fact_queries = _decoded_fact_dependencies(query, payload, fact_queries, fact_values)
            components.append(
                _compiled_component(
                    query,
                    base_revision,
                    payload=payload,
                    dependencies=revision_fact_queries + reference_queries,
                )
            )
            for layout in revision.export_layouts:
                layout_query = ExportLayoutComponentQuery(str(modelo.id), str(revision_id), str(layout.id))
                layout_dependencies = tuple(
                    ReferenceComponentQuery(str(reference_id), AuthorityComponentKind.LEGAL_REFERENCE)
                    for reference_id in sorted(set(layout.legal_refs))
                ) + tuple(
                    ReferenceComponentQuery(str(reference_id), AuthorityComponentKind.SOURCE_REFERENCE)
                    for reference_id in sorted(set(layout.source_refs))
                )
                components.append(_compiled_component(layout_query, layout, dependencies=layout_dependencies))
    for item in artifact.evidence.legal:
        query = EvidenceComponentQuery(item.legal_reference_id, AuthorityComponentKind.LEGAL_EVIDENCE)
        components.append(_compiled_component(query, item))
    for item in artifact.evidence.sources:
        query = EvidenceComponentQuery(item.source_reference_id, AuthorityComponentKind.SOURCE_EVIDENCE)
        components.append(_compiled_component(query, item))
    return tuple(
        sorted(
            components,
            key=lambda item: (
                authority_component_identity(item.query)[0].value,
                authority_component_identity(item.query)[1],
            ),
        )
    )


def _decoded_fact_dependencies(
    query: AuthorityComponentQuery,
    payload: bytes,
    fact_queries: tuple[GovernedFactComponentQuery, ...],
    fact_values: tuple[object, ...],
) -> tuple[GovernedFactComponentQuery, ...]:
    """Return only facts exercised while strictly decoding one typed component."""
    observed: set[str] = set()
    decode_authority_component(
        query,
        payload,
        dependencies=fact_values,
        fact_query_observer=lambda fact_query: observed.add(str(fact_query.fact_id)),
    )
    # Tax-ID format is the bootstrap decode context and is read directly from
    # the supplied catalogue before Pydantic validators enter the observed scope.
    if isinstance(query, ModeloRevisionComponentQuery):
        observed.add("spanish-tax-identifier-format")
    return tuple(fact_query for fact_query in fact_queries if fact_query.fact_id in observed)


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
                component.retained_weight,
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
