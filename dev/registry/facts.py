#!/usr/bin/env python3
"""Detect Python-owned regulatory facts and verify their registry relocation.

The signal combines live AST discovery with the fact-relocation evidence
ledger. It derives remaining campaign work from untriaged high-confidence
discoveries, failed placements, unresolved consumer seams, and declared-open
rows; manifest status alone cannot manufacture zero. Publication and signal
accounting are independent gates so an external authority blocker cannot hide
the remaining relocation queue.

This remains a mechanical detector. It establishes observable source absence,
consumer wiring, and destination structure, not legal correctness or semantic
equivalence. Every heuristic discovery requires an explicit disposition.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tokenize
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityComponentKind,
    GovernedFactComponentQuery,
)
from cadrumo.domain.calculations.registry.authority_store import AuthorityStoreError, SQLiteAuthorityReader
from dev._paths import REPO_ROOT
from dev.registry.analysis.governed_literal_discovery import (
    GovernedLiteralCandidate,
    discover_governed_literal_candidates,
)

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = (REPO_ROOT / "src" / "cadrumo").resolve()
AUTHORED_DATA_ROOT = (SOURCE_ROOT / "_data").resolve()
CAMPAIGN_DIR = REPO_ROOT / "tmp" / "fact-relocation"
DEFAULT_MANIFEST = CAMPAIGN_DIR / "fact_relocation_signal_manifest.json"
DEFAULT_ENRICHMENT = CAMPAIGN_DIR / "signal-symbol-enrichment.json"
DEFAULT_TODO_BASELINE = CAMPAIGN_DIR / "fact_relocation_todo_baseline.json"
DEFAULT_CONSUMER_REQUIREMENTS = CAMPAIGN_DIR / "consumer_fact_requirements.json"
BUNDLED_AUTHORITY_DESCRIPTOR = bundled_authority_descriptor_path()
SCHEMA_VERSION = 1
CONTRACT_VERSION = 2
ACTIONABLE_STATUS = "open"
CLOSED_STATUSES = frozenset({"migrated", "retained", "bridge"})
BLOCKING_STATUSES = frozenset({ACTIONABLE_STATUS, "deferred", "unsupported"})
ALLOWED_STATUSES = frozenset({*CLOSED_STATUSES, *BLOCKING_STATUSES})
ALLOWED_CATEGORIES = frozenset({"formula", "verification", "mapping", "catalogue"})
ALLOWED_LANES = frozenset(
    {
        "lane-1-lun-max",
        "lane-2-lun-max",
        "lane-3-lun-max",
        "lane-4-lun-max",
        "lane-5-lun-max",
        "lane-6-lun-max",
    }
)
FACT_RELOCATION_TODO_RE = re.compile(r"#\s*TODO\(fact-relocation\)")
REGISTRY_QUERY_SYMBOLS = frozenset(
    {
        "RegistryQueryService",
        "MappingFactQuery",
        "ScalarFactQuery",
        "EntitySetFactQuery",
        "BracketFactQuery",
        "OverrideFactQuery",
        "EventFactQuery",
        "MultiOutputFactQuery",
        "RegistrySnapshot",
        # Typed catalogue resolvers are query seams too: their implementation
        # owns the MappingFactQuery, while the consumer intentionally imports
        # only the narrow projection boundary.
        "resolve_iva_deduction_catalogue",
    }
)
RETAIN_KINDS = frozenset(
    {
        "generic_mechanism",
        "closed_type_vocabulary",
        "presentation_or_workflow",
        "parser_or_serializer",
        "evidence_plumbing",
        "registry_runtime",
        "already_authority_backed_bridge",
    }
)
REQUIRED_TOP_LEVEL = {
    "schema_version",
    "campaign",
    "scope",
    "source_reports",
    "exclusions",
    "ownership",
    "candidates",
}
REQUIRED_CANDIDATE = {
    "id",
    "category",
    "status",
    "evidence",
    "target",
}
AUTHORITY_REQUIRED_FIELDS = frozenset(
    {
        "artifact",
        "model",
        "revision",
        "family",
        "declaration_id",
        "consumer",
        "parity",
        "duplicate_retired",
        "authoring_paths",
    }
)
AUTHORITY_LEGACY_FIELDS = frozenset({"digest", "compiled", "published", "provenance_digest"})
PLACEMENT_CLOSURE_KIND = "placement"
PLACEMENT_REQUIRED_FIELDS = frozenset(
    {
        "schema",
        "source_file",
        "forbidden_symbols",
        "forbidden_literals",
        "destinations",
        "publication",
    }
)
PLACEMENT_DESTINATION_REQUIRED_FIELDS = frozenset({"path", "revision", "family", "declaration_ids", "required_fields"})
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ANCHOR_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]{2,}")
ANCHOR_STOPWORDS = frozenset(
    {
        "and",
        "article",
        "base",
        "category",
        "code",
        "codes",
        "constant",
        "data",
        "family",
        "field",
        "fields",
        "formula",
        "group",
        "ids",
        "kind",
        "kinds",
        "legal",
        "map",
        "model",
        "output",
        "period",
        "record",
        "records",
        "relation",
        "rows",
        "rule",
        "rules",
        "set",
        "sets",
        "source",
        "table",
        "target",
        "used",
        "value",
        "values",
    }
)


class ManifestError(ValueError):
    """Raised when the signal ledger is malformed or ambiguous."""


def _repo_relative_path(raw: Any, *, label: str) -> tuple[Path, str]:
    """Resolve a manifest path without allowing it to escape the repository.

    Manifest paths are deliberately POSIX-style repository-relative strings so
    that a copied manifest has the same meaning on every runner.  Syntax and
    containment failures are input errors (exit code 2), while a valid path
    that is absent on disk is reported later as an integrity observation.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ManifestError(f"{label}: path must be a non-empty string")
    value = raw.strip().replace("\\", "/")
    if value.startswith("/") or re.match(r"^[A-Za-z]:/", value):
        raise ManifestError(f"{label}: path must be repository-relative")
    parts = PurePosixPath(value).parts
    if ".." in parts:
        raise ManifestError(f"{label}: path must not contain '..'")
    resolved = (REPO_ROOT / Path(*parts)).resolve()
    try:
        relative = resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ManifestError(f"{label}: path escapes repository") from exc
    return resolved, relative.as_posix()


def _source_path(raw: Any, *, label: str) -> tuple[Path, str]:
    resolved, relative = _repo_relative_path(raw, label=label)
    try:
        resolved.relative_to(SOURCE_ROOT)
    except ValueError as exc:
        raise ManifestError(f"{label}: source evidence must be under src/cadrumo") from exc
    path = PurePosixPath(relative)
    if (
        path.name.startswith("__")
        or path.name == "conftest.py"
        or "__pycache__" in path.parts
        or any(part.casefold() in {"test", "tests"} for part in path.parts)
    ):
        raise ManifestError(f"{label}: test/cache source is excluded")
    if path.suffix != ".py":
        raise ManifestError(f"{label}: source evidence must name a Python file")
    return resolved, relative


def _source_relocations(value: Any) -> dict[str, dict[str, str]]:
    """Validate and normalize exact legacy-to-live source relocations.

    A relocation is deliberately an explicit pair, not a filename heuristic.
    The live byte digest is checked again during source observation, so a
    copied or fabricated replacement cannot satisfy a missing legacy path.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ManifestError("source_relocations must be an object")

    normalized: dict[str, dict[str, str]] = {}
    live_paths: set[str] = set()
    for raw_old, record in value.items():
        label = f"source_relocations[{raw_old!r}]"
        _, old_relative = _source_path(raw_old, label=f"{label}.legacy_file")
        if not isinstance(record, dict):
            raise ManifestError(f"{label} must be an object")
        live_file = record.get("live_file")
        _, live_relative = _source_path(
            live_file,
            label=f"{label}.live_file",
        )
        if old_relative == live_relative:
            raise ManifestError(f"{label}: legacy and live files must differ")
        if live_relative in live_paths:
            raise ManifestError(f"{label}: live_file is already the target of another relocation")
        history_sha256 = record.get("history_sha256")
        live_sha256 = record.get("live_sha256")
        _validate_hash(history_sha256, label=f"{label}.history_sha256")
        _validate_hash(live_sha256, label=f"{label}.live_sha256")
        basis = record.get("basis")
        if not isinstance(basis, str) or not basis.strip():
            raise ManifestError(f"{label}.basis is required")
        normalized[old_relative] = {
            "legacy_file": old_relative,
            "live_file": live_relative,
            "history_sha256": history_sha256,
            "live_sha256": live_sha256,
            "basis": basis,
        }
        live_paths.add(live_relative)

    if set(normalized) & live_paths:
        raise ManifestError("source_relocations must not form relocation chains")
    return normalized


def _relocated_source_relative(
    relative: str,
    relocations: dict[str, dict[str, str]],
) -> str:
    record = relocations.get(relative)
    if record is None:
        return relative
    legacy_path = REPO_ROOT / Path(*PurePosixPath(relative).parts)
    live_relative = record["live_file"]
    live_path = REPO_ROOT / Path(*PurePosixPath(live_relative).parts)
    # Keep an intact legacy checkout authoritative when its declared live
    # counterpart is not present.  When the legacy path is absent, retain the
    # live target (even if absent) so the normal missing-file gate stays red.
    if live_path.is_file() or not legacy_path.is_file():
        return live_relative
    return relative


def _authority_path(raw: Any, *, label: str) -> tuple[Path, str]:
    resolved, relative = _repo_relative_path(raw, label=label)
    path = PurePosixPath(relative)
    if "__pycache__" in path.parts or any(part.casefold() in {"test", "tests"} for part in path.parts):
        raise ManifestError(f"{label}: test/cache authority path is excluded")
    return resolved, relative


def _authoring_path(raw: Any, *, label: str) -> tuple[Path, str]:
    resolved, relative = _authority_path(raw, label=label)
    try:
        resolved.relative_to(AUTHORED_DATA_ROOT)
    except ValueError as exc:
        raise ManifestError(f"{label}: authoring path must be under src/cadrumo/_data") from exc
    return resolved, relative


def _anchor_tokens(anchor: str) -> list[str]:
    """Return distinctive, deterministic tokens for a prose audit anchor."""
    tokens: list[str] = []
    for token in ANCHOR_TOKEN_RE.findall(anchor):
        folded = token.casefold()
        distinctive = (
            len(token) >= 4
            and folded not in ANCHOR_STOPWORDS
            and (
                any(character.isdigit() for character in token)
                or "_" in token
                or "." in token
                or ":" in token
                or (token.isupper() and len(token) >= 4)
            )
        )
        if distinctive and token not in tokens:
            tokens.append(token)
    if tokens:
        return tokens
    # Some anchors are intentionally descriptive and have no model-shaped
    # token.  Keep a conservative fallback so their disappearance is still
    # observable without treating every common word as an identity.
    for token in ANCHOR_TOKEN_RE.findall(anchor):
        if len(token) >= 5 and token.casefold() not in ANCHOR_STOPWORDS and token not in tokens:
            tokens.append(token)
    return tokens


def _has_distinctive_anchor_token(tokens: list[str]) -> bool:
    return any(
        len(token) >= 4
        and (
            any(character.isdigit() for character in token)
            or "_" in token
            or "." in token
            or ":" in token
            or (token.isupper() and len(token) >= 4)
        )
        for token in tokens
    )


def _target_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in target.elts:
            names.extend(_target_names(element))
        return names
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    return []


def _node_span(node: ast.AST) -> str:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", start)
    if not isinstance(start, int) or not isinstance(end, int):
        return "unknown"
    return f"L{start}-L{end}"


def _enrichment_symbol_leaf(symbol: str) -> str:
    """Return the live AST name from a possibly qualified enrichment symbol."""
    return symbol.rsplit("/", 1)[-1]


def _ast_declarations(tree: ast.AST) -> list[dict[str, str]]:
    """Collect stable module/class declaration identities from an AST."""
    declarations: list[dict[str, str]] = []

    def add(node: ast.AST, symbol: str, scope: str) -> None:
        declarations.append(
            {
                "symbol": symbol,
                "scope": scope,
                "ast_node_kind": type(node).__name__,
                "source_span": _node_span(node),
            }
        )

    def visit_block(block: list[ast.stmt], scope: str) -> None:
        for node in block:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add(node, node.name, scope)
                # Function-local assignments are mechanics, not module-level
                # declaration identities for this signal.  Enrichment records
                # function identity itself, but not every local variable.
                continue
            if isinstance(node, ast.ClassDef):
                add(node, node.name, scope)
                visit_block(node.body, f"class:{node.name}")
                continue
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    for symbol in _target_names(target):
                        add(node, symbol, scope)
            elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
                for symbol in _target_names(node.target):
                    add(node, symbol, scope)

            if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While)):
                visit_block(node.body, scope)
                visit_block(node.orelse, scope)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                visit_block(node.body, scope)
            elif isinstance(node, ast.Try):
                visit_block(node.body, scope)
                visit_block(node.orelse, scope)
                visit_block(node.finalbody, scope)
                for handler in node.handlers:
                    visit_block(handler.body, scope)
            elif isinstance(node, ast.Match):
                for case in node.cases:
                    visit_block(case.body, scope)

    if isinstance(tree, ast.Module):
        visit_block(tree.body, "module")
    return sorted(
        declarations,
        key=lambda item: (
            item["source_span"],
            item["scope"],
            item["symbol"],
            item["ast_node_kind"],
        ),
    )


def _ast_symbols(tree: ast.AST) -> set[str]:
    symbols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        elif isinstance(node, ast.Name):
            symbols.add(node.id)
        elif isinstance(node, ast.Attribute):
            symbols.add(node.attr)
        elif isinstance(node, ast.alias):
            symbols.add(node.asname or node.name.split(".")[-1])
        elif isinstance(node, ast.arg):
            symbols.add(node.arg)
    return symbols


def _parse_ast_anchor(
    anchor: str,
    *,
    label: str,
    relocations: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Parse one or more canonical enrichment fingerprints from an anchor.

    The enrichment artifact records the immutable source identity as
    ``v1|file|scope|symbol|ast_node_kind|source_span``.  Evidence anchors use
    ``ast:`` for one identity and ``ast-set:`` for a deterministic semicolon
    separated set.  Keeping the path in each fingerprint prevents a symbol
    with the same name in another module from satisfying the evidence.
    """
    if anchor.startswith("ast-set:"):
        payload = anchor[len("ast-set:") :]
        raw_fingerprints = payload.split(";") if payload else []
    elif anchor.startswith("ast:"):
        raw_fingerprints = [anchor[len("ast:") :]]
    else:
        raise ManifestError(f"{label}: not an AST fingerprint anchor")
    if not raw_fingerprints or any(not value for value in raw_fingerprints):
        raise ManifestError(f"{label}: AST fingerprint set must not be empty")

    identities: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for index, fingerprint in enumerate(raw_fingerprints):
        parts = fingerprint.split("|")
        if len(parts) != 6 or parts[0] != "v1":
            raise ManifestError(f"{label}[{index}]: expected v1|file|scope|symbol|kind|span")
        _, raw_file, scope, symbol, ast_node_kind, source_span = parts
        if not all((raw_file, scope, symbol, ast_node_kind, source_span)):
            raise ManifestError(f"{label}[{index}]: fingerprint fields are required")
        _, relative = _source_path(
            raw_file,
            label=f"{label}[{index}].file",
        )
        relative = _relocated_source_relative(relative, relocations or {})
        if not re.fullmatch(r"L[0-9]+-L[0-9]+", source_span):
            raise ManifestError(f"{label}[{index}]: source span is invalid")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_:/.-]*", symbol):
            raise ManifestError(f"{label}[{index}]: symbol is invalid")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", ast_node_kind):
            raise ManifestError(f"{label}[{index}]: AST node kind is invalid")
        if scope != "module" and not re.fullmatch(
            r"class:[A-Za-z_][A-Za-z0-9_:/.-]*",
            scope,
        ):
            raise ManifestError(f"{label}[{index}]: scope is invalid")
        identity = (relative, scope, _enrichment_symbol_leaf(symbol), ast_node_kind, source_span)
        if identity in seen:
            raise ManifestError(f"{label}[{index}]: duplicate AST fingerprint")
        seen.add(identity)
        identities.append(
            {
                "fingerprint": "|".join(("v1", relative, scope, symbol, ast_node_kind, source_span)),
                "file": relative,
                "scope": scope,
                "symbol": symbol,
                "ast_node_kind": ast_node_kind,
                "source_span": source_span,
            }
        )
    return identities


def _decode_python_source(data: bytes) -> str:
    """Decode a Python file according to its encoding declaration."""
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    return data.decode(encoding)


def _observe_source_file(relative: str) -> dict[str, Any]:
    """Observe one candidate source file without judging its legal meaning."""
    path = REPO_ROOT / Path(*PurePosixPath(relative).parts)
    observation: dict[str, Any] = {
        "file": relative,
        "exists": path.is_file(),
        "sha256": None,
        "size_bytes": None,
        "ast_parse_status": "missing",
        "ast_node_count": 0,
        "ast_symbol_count": 0,
        "ast_declaration_count": 0,
        "read_status": "missing",
        "_text": "",
        "_symbols": set(),
        "_declarations": [],
    }
    if not path.is_file():
        return observation
    try:
        data = path.read_bytes()
    except OSError as exc:
        observation["exists"] = False
        observation["read_status"] = f"read-error:{type(exc).__name__}"
        return observation
    observation["read_status"] = "ok"
    observation["size_bytes"] = len(data)
    observation["sha256"] = "sha256:" + hashlib.sha256(data).hexdigest()
    try:
        text = _decode_python_source(data)
    except (SyntaxError, LookupError, UnicodeDecodeError) as exc:
        observation["ast_parse_status"] = f"decode-error:{type(exc).__name__}"
        return observation
    observation["_text"] = text
    try:
        tree = ast.parse(text, filename=relative)
    except (SyntaxError, ValueError, TypeError) as exc:
        observation["ast_parse_status"] = f"error:{type(exc).__name__}"
        return observation
    symbols = _ast_symbols(tree)
    declarations = _ast_declarations(tree)
    observation["ast_parse_status"] = "ok"
    observation["ast_node_count"] = sum(1 for _ in ast.walk(tree))
    observation["ast_symbol_count"] = len(symbols)
    observation["ast_declaration_count"] = len(declarations)
    observation["_symbols"] = symbols
    observation["_declarations"] = declarations
    return observation


def _observe_anchor(
    anchor: str,
    observation: dict[str, Any],
    *,
    relocations: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    if anchor.startswith(("ast:", "ast-set:")):
        identities = _parse_ast_anchor(
            anchor,
            label="evidence.anchor",
            relocations=relocations,
        )
        live_declarations = observation.get("_declarations", [])
        matched_identities: list[dict[str, str]] = []
        shape_matches: list[dict[str, str]] = []
        for identity in identities:
            expected = (
                _enrichment_symbol_leaf(identity["symbol"]),
                identity["scope"],
                identity["ast_node_kind"],
                identity["source_span"],
            )
            exact = any(
                (
                    live["symbol"],
                    live["scope"],
                    live["ast_node_kind"],
                    live["source_span"],
                )
                == expected
                for live in live_declarations
            )
            same_shape = any(
                (
                    live["symbol"],
                    live["scope"],
                    live["ast_node_kind"],
                )
                == expected[:3]
                for live in live_declarations
            )
            if exact:
                matched_identities.append(identity)
            elif same_shape:
                shape_matches.append(identity)

        if not observation.get("exists") or observation.get("read_status") != "ok":
            identity_status = "missing"
            status = "missing"
        elif observation.get("ast_parse_status") != "ok":
            identity_status = "missing"
            status = "parse-error"
        elif len(matched_identities) == len(identities):
            identity_status = "matched"
            status = "observed"
        elif shape_matches:
            identity_status = "drifted"
            status = "unresolved"
        else:
            identity_status = "missing"
            status = "unresolved"
        matched_symbols = sorted(
            {_enrichment_symbol_leaf(identity["symbol"]) for identity in matched_identities},
            key=str.casefold,
        )
        return {
            "anchor": anchor,
            "tokens": [],
            "matched_tokens": [],
            "matched_ast_symbols": matched_symbols,
            "anchor_status": status,
            "identity_status": identity_status,
            "identity_fingerprints": [identity["fingerprint"] for identity in identities],
            "matched_identity_fingerprints": [identity["fingerprint"] for identity in matched_identities],
        }

    tokens = _anchor_tokens(anchor)
    text = observation.get("_text", "")
    folded_text = text.casefold()
    symbols = observation.get("_symbols", set())
    folded_symbols = {symbol.casefold(): symbol for symbol in symbols}
    matched_tokens = [token for token in tokens if token.casefold() in folded_text]
    matched_symbols = [folded_symbols[token.casefold()] for token in tokens if token.casefold() in folded_symbols]
    if not observation.get("exists") or observation.get("read_status") != "ok":
        status = "missing"
    elif observation.get("ast_parse_status") != "ok":
        status = "parse-error"
    elif matched_tokens:
        status = "observed"
    elif not _has_distinctive_anchor_token(tokens):
        status = "descriptive"
    else:
        status = "unresolved"
    return {
        "anchor": anchor,
        "tokens": tokens,
        "matched_tokens": matched_tokens,
        "matched_ast_symbols": sorted(set(matched_symbols), key=str.casefold),
        "anchor_status": status,
    }


def _source_identity_retirement_scope(row: Mapping[str, Any]) -> str | None:
    """Return a nonblocking retirement scope only for complete relocation proof.

    A missing enrichment declaration is not enough to infer that a symbol was
    intentionally removed.  The row must preserve its source hashes and
    explicit retirement evidence, name at least one destination, and record a
    resolved consumer seam.  This deliberately derives the classification
    from evidence shape and destination ownership rather than from candidate
    IDs, so historical identity records remain auditable without becoming
    false live-source errors.
    """
    closure = row.get("closure")
    if not isinstance(closure, Mapping) or closure.get("source_disposition") != "removed":
        return None
    source_hashes = closure.get("source_hashes")
    retirement_evidence = closure.get("retirement_evidence")
    if not isinstance(source_hashes, list) or not source_hashes:
        return None
    if not isinstance(retirement_evidence, list) or not retirement_evidence:
        return None

    placement = closure.get("placement")
    if not isinstance(placement, Mapping):
        return None
    destinations = placement.get("destinations")
    consumer_resolution = placement.get("consumer_resolution")
    if not isinstance(destinations, list) or not destinations:
        return None
    if not isinstance(consumer_resolution, Mapping) or consumer_resolution.get("resolved") is not True:
        return None

    destination_paths = [
        destination.get("path")
        for destination in destinations
        if isinstance(destination, Mapping) and isinstance(destination.get("path"), str)
    ]
    if closure.get("contains_model_fact") is True or any(
        "modelos" in {part.casefold() for part in PurePosixPath(path).parts} for path in destination_paths
    ):
        return "modelo_registry"
    return "facts_registry"


def _source_scan(
    manifest: dict[str, Any],
    enrichment: dict[str, Any],
) -> dict[str, Any]:
    """Collect bounded source observations for every manifest evidence path."""
    relocations = _source_relocations(manifest.get("source_relocations"))
    rows_by_id = {row["id"]: row for row in manifest["candidates"]}
    path_refs: dict[str, list[tuple[str, str]]] = {}
    identity_refs: dict[str, list[tuple[str, str]]] = {}
    declared_source_paths: set[str] = set()
    for row in manifest["candidates"]:
        for evidence in row["evidence"]:
            _, declared_relative = _source_path(
                evidence["file"],
                label=f"{row['id']} evidence",
            )
            declared_source_paths.add(declared_relative)
            relative = _relocated_source_relative(
                declared_relative,
                relocations,
            )
            path_refs.setdefault(relative, []).append((row["id"], evidence["anchor"]))
        closure = row.get("closure", {})
        if isinstance(closure, dict):
            for source_hash in closure.get("source_hashes", []) or []:
                _, declared_relative = _source_path(
                    source_hash["path"],
                    label=f"{row['id']} closure source hash",
                )
                declared_source_paths.add(declared_relative)
                relative = _relocated_source_relative(
                    declared_relative,
                    relocations,
                )
                path_refs.setdefault(relative, [])

    if enrichment["status"] == "ready":
        for candidate_id, record in enrichment["records"].items():
            for declaration in record["declarations"]:
                _, declared_relative = _source_path(
                    declaration["file"],
                    label=f"{candidate_id} enrichment declaration",
                )
                declared_source_paths.add(declared_relative)
                relative = _relocated_source_relative(
                    declared_relative,
                    relocations,
                )
                identity_refs.setdefault(relative, []).append((candidate_id, declaration["symbol"]))
                path_refs.setdefault(relative, [])

    for legacy_relative, relocation in relocations.items():
        if legacy_relative not in declared_source_paths:
            raise ManifestError(
                f"source relocation is not referenced by evidence, closure, or symbol enrichment: {legacy_relative}"
            )
        path_refs.setdefault(relocation["live_file"], [])

    observations: dict[str, dict[str, Any]] = {
        relative: _observe_source_file(relative) for relative in sorted(path_refs)
    }
    evidence_observations: dict[tuple[str, int], dict[str, Any]] = {}
    for row in manifest["candidates"]:
        for index, evidence in enumerate(row["evidence"]):
            _, declared_relative = _source_path(evidence["file"], label=f"{row['id']} evidence")
            relative = _relocated_source_relative(
                declared_relative,
                relocations,
            )
            evidence_observations[(row["id"], index)] = _observe_anchor(
                evidence["anchor"],
                observations[relative],
                relocations=relocations,
            ) | {"file": relative}

    identity_observations: list[dict[str, Any]] = []
    identity_matched = 0
    identity_missing = 0
    identity_drifted = 0
    identity_retired_by_relocation = 0
    retired_by_relocation_identities: list[dict[str, Any]] = []
    if enrichment["status"] == "ready":
        for candidate_id in sorted(enrichment["records"]):
            for declaration in enrichment["records"][candidate_id]["declarations"]:
                _, declared_relative = _source_path(
                    declaration["file"],
                    label=f"{candidate_id} enrichment declaration",
                )
                relative = _relocated_source_relative(
                    declared_relative,
                    relocations,
                )
                observation = observations[relative]
                expected = (
                    _enrichment_symbol_leaf(declaration["symbol"]),
                    declaration["scope"],
                    declaration["ast_node_kind"],
                    declaration["source_span"],
                )
                live_declarations = observation.get("_declarations", [])
                exact = any(
                    (
                        live["symbol"],
                        live["scope"],
                        live["ast_node_kind"],
                        live["source_span"],
                    )
                    == expected
                    for live in live_declarations
                )
                same_symbol_shape = any(
                    (
                        live["symbol"],
                        live["scope"],
                        live["ast_node_kind"],
                    )
                    == expected[:3]
                    for live in live_declarations
                )
                same_shape_declarations = [
                    live
                    for live in live_declarations
                    if (
                        live["symbol"],
                        live["scope"],
                        live["ast_node_kind"],
                    )
                    == expected[:3]
                ]
                relocation = relocations.get(declared_relative)
                relocation_continuity = (
                    relocation is not None
                    and len(same_shape_declarations) == 1
                    and observation.get("sha256") == relocation["live_sha256"]
                )
                if exact:
                    status = "matched"
                    identity_matched += 1
                elif relocation_continuity:
                    # A proven source rename may shift line spans while
                    # retaining one exact declaration shape.  The relocation's
                    # independently recorded live digest prevents a fabricated
                    # same-shaped file from passing this continuity exception.
                    status = "matched"
                    identity_matched += 1
                elif same_symbol_shape:
                    status = "drifted"
                    identity_drifted += 1
                else:
                    retirement_scope = _source_identity_retirement_scope(rows_by_id[candidate_id])
                    if retirement_scope is not None:
                        status = "retired_by_relocation"
                        identity_retired_by_relocation += 1
                        retired_by_relocation_identities.append(
                            {
                                "candidate_id": candidate_id,
                                "file": relative,
                                "symbol": declaration["symbol"],
                                "scope": declaration["scope"],
                                "ast_node_kind": declaration["ast_node_kind"],
                                "expected_source_span": declaration["source_span"],
                                "retirement_scope": retirement_scope,
                                "reason": (
                                    "historical declaration is absent after an explicit source removal with "
                                    "preserved source hashes, retirement evidence, a destination, and a "
                                    "resolved consumer seam"
                                ),
                            }
                        )
                    else:
                        status = "missing"
                        identity_missing += 1
                identity_observations.append(
                    {
                        "candidate_id": candidate_id,
                        "file": relative,
                        "symbol": declaration["symbol"],
                        "scope": declaration["scope"],
                        "ast_node_kind": declaration["ast_node_kind"],
                        "expected_source_span": declaration["source_span"],
                        "source_fingerprint_input": declaration["source_fingerprint_input"],
                        "identity_status": status,
                        **(
                            {
                                "retirement_scope": retirement_scope,
                                "retirement_reason": (
                                    "explicit source removal has complete destination and consumer proof"
                                ),
                            }
                            if status == "retired_by_relocation"
                            else {}
                        ),
                    }
                )

    hash_observations: list[dict[str, Any]] = []
    for row in manifest["candidates"]:
        closure = row.get("closure", {})
        for source_hash in closure.get("source_hashes", []) if isinstance(closure, dict) else []:
            _, relative = _source_path(source_hash["path"], label=f"{row['id']} closure source hash")
            observed = observations[relative]
            actual = observed.get("sha256")
            expected = source_hash["sha256"]
            hash_observations.append(
                {
                    "candidate_id": row["id"],
                    "file": relative,
                    "expected_sha256": expected,
                    "observed_sha256": actual,
                    "hash_status": ("match" if actual == expected else "missing" if actual is None else "mismatch"),
                }
            )

    evidence_statuses = list(evidence_observations.values())
    missing_evidence = sum(item["anchor_status"] == "missing" for item in evidence_statuses)
    unresolved = sum(item["anchor_status"] == "unresolved" for item in evidence_statuses)
    descriptive = sum(item["anchor_status"] == "descriptive" for item in evidence_statuses)
    parse_errors = sum(
        observation["ast_parse_status"] != "ok" and observation["exists"] for observation in observations.values()
    )
    read_errors = sum(observation["read_status"] not in {"ok", "missing"} for observation in observations.values())
    missing_files = sum(not observation["exists"] for observation in observations.values())
    hash_mismatches = sum(item["hash_status"] == "mismatch" for item in hash_observations)
    hash_missing = sum(item["hash_status"] == "missing" for item in hash_observations)
    relocation_hash_mismatches = sum(
        observations.get(relocation["live_file"], {}).get("exists")
        and observations.get(relocation["live_file"], {}).get("read_status") == "ok"
        and observations.get(relocation["live_file"], {}).get("sha256") != relocation["live_sha256"]
        for relocation in relocations.values()
    )
    closed_without_hash = sum(
        row["status"] in CLOSED_STATUSES and not row.get("closure", {}).get("source_hashes")
        for row in manifest["candidates"]
    )
    source_integrity_error_count = sum(
        (
            missing_evidence,
            unresolved,
            parse_errors,
            read_errors,
            missing_files,
            hash_mismatches,
            hash_missing,
            relocation_hash_mismatches,
            closed_without_hash,
            identity_missing,
            identity_drifted,
        )
    )
    return {
        "observations": observations,
        "path_refs": path_refs,
        "identity_refs": identity_refs,
        "evidence": evidence_observations,
        "identities": identity_observations,
        "hashes": hash_observations,
        "counts": {
            "source_file_count": len(observations),
            "source_evidence_count": len(evidence_statuses),
            "source_files_observed_count": sum(
                observation["read_status"] == "ok" for observation in observations.values()
            ),
            "source_missing_count": missing_evidence,
            "source_file_missing_count": missing_files,
            "source_read_error_count": read_errors,
            "source_anchor_unresolved_count": unresolved,
            "source_anchor_descriptive_count": descriptive,
            "source_parse_error_count": parse_errors,
            "source_hash_mismatch_count": hash_mismatches,
            "source_hash_missing_count": hash_missing,
            "source_relocation_hash_mismatch_count": relocation_hash_mismatches,
            "closed_without_source_hash_count": closed_without_hash,
            "source_integrity_error_count": source_integrity_error_count,
            "enrichment_declaration_count": (
                identity_matched + identity_missing + identity_drifted + identity_retired_by_relocation
            ),
            "enrichment_identity_matched_count": identity_matched,
            "enrichment_identity_missing_count": identity_missing,
            "enrichment_identity_drifted_count": identity_drifted,
            "enrichment_identity_retired_by_relocation_count": identity_retired_by_relocation,
            "enrichment_identity_error_count": identity_missing + identity_drifted,
        },
        "retired_by_relocation_identities": retired_by_relocation_identities,
    }


def _hash_lines(values: list[str]) -> str:
    canonical = "\n".join(values).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _fd_excluded(relative: PurePosixPath) -> bool:
    """Mirror the exact fd exclusions used for the original audit intake."""
    name = relative.name
    return (
        any(part in {"test", "tests", "__pycache__"} for part in relative.parts)
        or name.startswith("__")
        or name.endswith("_test.py")
        or name.startswith("test_")
        or name == "conftest.py"
        or any(part.startswith(".") for part in relative.parts)
    )


def _enumerate_frozen_universe() -> dict[str, Any]:
    """Enumerate and parse the audit universe with pathlib and stdlib AST."""
    paths: list[tuple[Path, str]] = []
    enumeration_errors: list[str] = []
    try:
        discovered = SOURCE_ROOT.rglob("*.py")
        for path in discovered:
            try:
                if not path.is_file():
                    continue
                resolved = path.resolve()
                relative = resolved.relative_to(REPO_ROOT)
                relative_posix = relative.as_posix()
                if _fd_excluded(PurePosixPath(relative_posix)):
                    continue
                paths.append((resolved, relative_posix))
            except (OSError, ValueError) as exc:
                enumeration_errors.append(f"{path.as_posix()}:{type(exc).__name__}")
    except OSError as exc:
        enumeration_errors.append(f"{SOURCE_ROOT.as_posix()}:{type(exc).__name__}")

    paths.sort(key=lambda item: (PurePosixPath(item[1]).parent.as_posix(), PurePosixPath(item[1]).name))
    parse_failure_files: list[str] = []
    read_failure_files: list[str] = []
    for path, relative in paths:
        try:
            data = path.read_bytes()
            text = _decode_python_source(data)
            ast.parse(text, filename=relative)
        except (OSError, SyntaxError, LookupError, UnicodeDecodeError, ValueError, TypeError) as exc:
            if isinstance(exc, OSError):
                read_failure_files.append(relative)
            else:
                parse_failure_files.append(relative)

    relative_paths = [relative for _, relative in paths]
    return {
        "paths": relative_paths,
        "counts": {
            "universe_count": len(relative_paths),
            "universe_parse_count": len(relative_paths) - len(parse_failure_files) - len(read_failure_files),
            "universe_parse_failures": len(parse_failure_files),
            "universe_read_failures": len(read_failure_files),
            "universe_enumeration_failures": len(enumeration_errors),
            "universe_path_digest": _hash_lines(relative_paths),
        },
        "parse_failure_files": sorted(parse_failure_files),
        "read_failure_files": sorted(read_failure_files),
        "enumeration_errors": sorted(enumeration_errors),
    }


def _consumer_source_paths() -> dict[str, Any]:
    """Find only source files that can contain governed-fact query calls.

    The ordinary signal deliberately audits the frozen Python universe.  That
    audit is intentionally expensive and includes historical discovery work,
    so it must not be a prerequisite for a facts-publication measurement.  A
    facts-only run uses ripgrep's indexed text scan to narrow the AST pass to
    files containing one of the closed query-family constructors.  The
    pathlib fallback preserves portability when the developer tool is absent;
    it remains conservative and reports that fallback in the result.
    """
    query_pattern = r"(?:MappingFactQuery|ScalarFactQuery|EntitySetFactQuery|BracketFactQuery|OverrideFactQuery|EventFactQuery|MultiOutputFactQuery)\s*\("
    rg = shutil.which("rg")
    if rg is not None:
        try:
            result = subprocess.run(
                [
                    rg,
                    "--files-with-matches",
                    "--no-ignore-vcs",
                    "--glob",
                    "*.py",
                    "--glob",
                    "!**/tests/**",
                    "--glob",
                    "!**/test/**",
                    "--glob",
                    "!**/test_*.py",
                    "--glob",
                    "!**/*_test.py",
                    "--glob",
                    "!**/conftest.py",
                    "-e",
                    query_pattern,
                    "src/cadrumo",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            result = None
            rg_error = f"rg-error:{type(exc).__name__}"
        else:
            rg_error = None if result.returncode in {0, 1} else f"rg-exit:{result.returncode}"
        if result is not None and rg_error is None:
            paths = sorted(
                {
                    line.replace("\\", "/").strip()
                    for line in result.stdout.splitlines()
                    if line.strip() and not _fd_excluded(PurePosixPath(line.replace("\\", "/").strip()))
                }
            )
            return {
                "paths": paths,
                "method": "rg",
                "errors": [],
            }
    else:
        rg_error = "rg-unavailable"

    paths: list[str] = []
    fallback_errors: list[str] = [rg_error]
    try:
        candidates = SOURCE_ROOT.rglob("*.py")
        for path in candidates:
            relative = path.resolve().relative_to(REPO_ROOT).as_posix()
            if _fd_excluded(PurePosixPath(relative)):
                continue
            try:
                text = _decode_python_source(path.read_bytes())
            except (OSError, UnicodeDecodeError, LookupError, ValueError) as exc:
                fallback_errors.append(f"{relative}:{type(exc).__name__}")
                continue
            if re.search(query_pattern, text):
                paths.append(relative)
    except OSError as exc:
        fallback_errors.append(f"{SOURCE_ROOT.as_posix()}:{type(exc).__name__}")
    return {
        "paths": sorted(set(paths)),
        "method": "pathlib-fallback",
        "errors": sorted(set(fallback_errors)),
    }


CONSUMER_QUERY_SYMBOLS = frozenset(
    {
        "MappingFactQuery",
        "ScalarFactQuery",
        "EntitySetFactQuery",
        "BracketFactQuery",
        "OverrideFactQuery",
        "EventFactQuery",
        "MultiOutputFactQuery",
    }
)

QUERY_FAMILY_BY_SYMBOL = {
    "MappingFactQuery": "mapping",
    "ScalarFactQuery": "scalar",
    "EntitySetFactQuery": "entity_set",
    "BracketFactQuery": "bracket",
    "OverrideFactQuery": "override",
    "EventFactQuery": "event",
    "MultiOutputFactQuery": "multi_output",
}
CLOSED_WORLD_A_HELPER_NAMES = frozenset({"_resolved_scalar_fact", "_excluded_concepts"})


def _call_symbol(node: ast.AST) -> str | None:
    """Return the final symbol for a call target without importing the module."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _static_string(node: ast.AST | None, constants: dict[str, str]) -> str | None:
    """Resolve only literal string expressions and local constant aliases."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string(node.left, constants)
        right = _static_string(node.right, constants)
        if left is not None and right is not None:
            return left + right
    return None


def _date_axis_name(node: ast.AST | None) -> str | None:
    """Map a static ``DateAxis`` enum member to its serialized axis name.

    The enum members intentionally use the registry token as their lower-case
    snake-case spelling. Reading the member attribute from the AST keeps this
    detector closed over the enum owner while recognizing every current and
    future member without a hand-maintained fact/callsite list. Dynamic axis
    expressions remain unresolved and therefore blocking.
    """
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "DateAxis":
        # Resolve against the enum owner instead of maintaining a second list
        # in this detector.  An attribute that is not a real DateAxis member is
        # intentionally unresolved and therefore remains a signal blocker.
        try:
            from cadrumo.domain.calculations.registry.schema_base import DateAxis

            member = DateAxis.__members__.get(node.attr)
        except (ImportError, AttributeError):
            return None
        return member.value if member is not None else None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for item in node.elts for name in _target_names(item)]
    return []


def _literal_string(node: ast.AST | None) -> str | None:
    """Resolve one literal string without evaluating Python source."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_string(node.left)
        right = _literal_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _literal_string_sequence(node: ast.AST | None) -> tuple[str, ...] | None:
    """Resolve only a finite tuple/list made entirely from literal strings.

    This deliberately does not follow names, calls, comprehensions, starred
    values, or arbitrary iterable protocols.  The consumer scanner may use
    the result as a loop domain only when the source contains this closed
    literal shape.
    """
    if not isinstance(node, (ast.Tuple, ast.List)):
        return None
    values: list[str] = []
    for element in node.elts:
        value = _literal_string(element)
        if value is None:
            return None
        values.append(value)
    return tuple(values)


def _literal_string_mapping(node: ast.AST | None) -> dict[str, str] | None:
    """Resolve a finite mapping whose keys and values are literal strings."""
    if not isinstance(node, ast.Dict) or any(key is None for key in node.keys):
        return None
    mapping: dict[str, str] = {}
    for key_node, value_node in zip(node.keys, node.values):
        key = _literal_string(key_node)
        value = _literal_string(value_node)
        if key is None or value is None or key in mapping:
            return None
        mapping[key] = value
    return mapping


def _simple_assignment_names(targets: Sequence[ast.AST]) -> list[str]:
    """Return names for direct ``name = value`` targets only."""
    names: list[str] = []
    for target in targets:
        if not isinstance(target, ast.Name):
            return []
        names.append(target.id)
    return names


class _ScopeWriteCollector(ast.NodeVisitor):
    """Collect writes in one lexical scope, excluding nested scopes."""

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.assignments: list[ast.Assign | ast.AnnAssign] = []

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.counts[node.id] += 1

    def visit_Assign(self, node: ast.Assign) -> None:
        self.assignments.append(node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.assignments.append(node)
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        self.counts[node.arg] += 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.counts[node.name] += 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.counts[node.name] += 1

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.counts[node.name] += 1

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # Lambda arguments/body belong to a nested scope.  A named expression
        # in a lambda is intentionally not used as a static binding here.
        return

    def visit_comprehension(self, node: ast.comprehension) -> None:
        # Comprehension targets have their own Python 3 scope.  The consumer
        # visitor handles them separately as finite loop domains.
        return

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        return

    def visit_ListComp(self, node: ast.ListComp) -> None:
        return

    def visit_SetComp(self, node: ast.SetComp) -> None:
        return

    def visit_DictComp(self, node: ast.DictComp) -> None:
        return


def _scope_bindings(
    body: Sequence[ast.stmt],
    *,
    arguments: ast.arguments | None = None,
) -> dict[str, Any]:
    """Build conservative literal bindings for one lexical scope.

    A name is usable only when it has exactly one write in this scope and the
    write is a direct literal string or literal string sequence assignment.
    Any other write blocks fallback to an outer scope.  This prevents a later
    reassignment from being mistaken for a constant.
    """
    collector = _ScopeWriteCollector()
    for statement in body:
        collector.visit(statement)
    if arguments is not None:
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ):
            collector.visit(argument)
        if arguments.vararg is not None:
            collector.visit(arguments.vararg)
        if arguments.kwarg is not None:
            collector.visit(arguments.kwarg)

    literal_mapping_candidates: dict[str, list[dict[str, str]]] = {}
    for statement in collector.assignments:
        if isinstance(statement, ast.Assign):
            targets = _simple_assignment_names(statement.targets)
            mapping = _literal_string_mapping(statement.value)
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            targets = [statement.target.id]
            mapping = _literal_string_mapping(statement.value)
        else:
            continue
        if mapping is not None:
            for target in targets:
                literal_mapping_candidates.setdefault(target, []).append(mapping)
    literal_mappings = {
        name: candidates[0]
        for name, candidates in literal_mapping_candidates.items()
        if collector.counts.get(name) == 1 and len(candidates) == 1
    }

    candidates: dict[str, list[tuple[str, str | tuple[str, ...] | dict[str, str]]]] = {}
    for statement in collector.assignments:
        if isinstance(statement, ast.Assign):
            targets = _simple_assignment_names(statement.targets)
            value_string = _literal_string(statement.value)
            value_sequence = _literal_string_sequence(statement.value)
            value_mapping = _literal_string_mapping(statement.value)
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            targets = [statement.target.id]
            value_string = _literal_string(statement.value)
            value_sequence = _literal_string_sequence(statement.value)
            value_mapping = _literal_string_mapping(statement.value)
        else:
            continue
        value: str | tuple[str, ...] | dict[str, str] | None
        if value_mapping is not None:
            value = value_mapping
        elif value_sequence is not None:
            value = value_sequence
        else:
            value = value_string
        if value is None and isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value_node = statement.value
            if isinstance(value_node, ast.Subscript) and isinstance(value_node.value, ast.Name):
                mapping = literal_mappings.get(value_node.value.id)
                if mapping is not None:
                    key = _literal_string(value_node.slice)
                    if key is not None:
                        value = (mapping[key],) if key in mapping else None
                    else:
                        value = tuple(mapping.values())
        if value is None:
            continue
        for target in targets:
            kind = "mapping" if isinstance(value, dict) else "sequence" if isinstance(value, tuple) else "string"
            candidates.setdefault(target, []).append((kind, value))

    strings: dict[str, str] = {}
    sequences: dict[str, tuple[str, ...]] = {}
    mappings: dict[str, dict[str, str]] = {}
    blocked: set[str] = set()
    for name, count in collector.counts.items():
        entries = candidates.get(name, [])
        if count == 1 and len(entries) == 1:
            kind, value = entries[0]
            if kind == "sequence" and isinstance(value, tuple):
                sequences[name] = value
                continue
            if kind == "string" and isinstance(value, str):
                strings[name] = value
                continue
            if kind == "mapping" and isinstance(value, dict):
                mappings[name] = value
                continue
        blocked.add(name)
    return {"strings": strings, "sequences": sequences, "mappings": mappings, "blocked": blocked}


def _all_binding_writes(tree: ast.AST) -> set[str]:
    """Collect conservative writes used to reject reassigned imports."""
    writes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            writes.add(node.id)
        elif isinstance(node, ast.arg):
            writes.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            if isinstance(node, ast.Lambda):
                continue
            writes.add(node.name)
    return writes


def _python_module_name(relative: str) -> str | None:
    parts = list(PurePosixPath(relative).parts)
    if len(parts) < 3 or parts[0] != "src" or parts[1] != "cadrumo":
        return None
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    else:
        return None
    return ".".join(parts[1:]) or None


def _resolve_import_module(relative: str, *, level: int, module: str | None) -> str | None:
    """Resolve a relative import name without importing its module."""
    current = _python_module_name(relative)
    if current is None or level < 0:
        return None
    if level == 0:
        base: list[str] = []
    else:
        package = current.split(".")[:-1]
        remove = level - 1
        if remove > len(package):
            return None
        base = package[: len(package) - remove]
    if module:
        base.extend(part for part in module.split(".") if part)
    resolved = ".".join(base)
    return resolved if resolved.startswith("cadrumo") else None


def _local_module_path(module: str) -> Path | None:
    if not module.startswith("cadrumo"):
        return None
    parts = module.split(".")
    if not parts or parts[0] != "cadrumo":
        return None
    base = SOURCE_ROOT.joinpath(*parts[1:])
    candidates = [base.with_suffix(".py"), base / "__init__.py"]
    existing = [candidate for candidate in candidates if candidate.is_file()]
    return existing[0] if len(existing) == 1 else None


def _module_top_level_literal_string(tree: ast.AST, name: str) -> str | None:
    """Resolve one direct module-level literal assignment only."""
    if not isinstance(tree, ast.Module):
        return None
    candidates: list[str] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            targets = _simple_assignment_names(statement.targets)
            if name in targets:
                value = _literal_string(statement.value)
                if value is not None:
                    candidates.append(value)
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if statement.target.id == name:
                value = _literal_string(statement.value)
                if value is not None:
                    candidates.append(value)
    if len(candidates) != 1:
        return None
    writes = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == name
    )
    return candidates[0] if writes == 1 else None


def _module_enum_member_literal(tree: ast.AST, class_name: str, member_name: str) -> str | None:
    """Resolve one member of an explicitly imported ``StrEnum`` class."""
    if not isinstance(tree, ast.Module):
        return None
    has_strenum_import = any(
        isinstance(statement, ast.ImportFrom)
        and statement.module == "enum"
        and any(alias.name == "StrEnum" and alias.asname in {None, "StrEnum"} for alias in statement.names)
        for statement in tree.body
    )
    if not has_strenum_import:
        return None
    classes = [
        statement for statement in tree.body if isinstance(statement, ast.ClassDef) and statement.name == class_name
    ]
    if len(classes) != 1:
        return None
    class_node = classes[0]
    if not any(isinstance(base, ast.Name) and base.id == "StrEnum" for base in class_node.bases):
        return None
    candidates: list[str] = []
    for statement in class_node.body:
        if isinstance(statement, ast.Assign):
            targets = _simple_assignment_names(statement.targets)
            if member_name in targets:
                value = _literal_string(statement.value)
                if value is not None:
                    candidates.append(value)
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if statement.target.id == member_name:
                value = _literal_string(statement.value)
                if value is not None:
                    candidates.append(value)
    return candidates[0] if len(candidates) == 1 else None


def _module_string_constants(tree: ast.AST) -> dict[str, str]:
    """Collect literal string assignments used as fact-id aliases."""
    constants: dict[str, str] = {}
    # A few modules alias a module-level constant to another module-level
    # constant.  A bounded fixed point keeps this scanner static and avoids
    # executing arbitrary source while still resolving those aliases.
    for _ in range(4):
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = [target for target in node.targets for target in _target_names(target)]
                value = _static_string(node.value, constants)
            elif isinstance(node, ast.AnnAssign):
                targets = _target_names(node.target)
                value = _static_string(node.value, constants)
            else:
                continue
            if value is None:
                continue
            for target in targets:
                if constants.get(target) != value:
                    constants[target] = value
                    changed = True
        if not changed:
            break
    return constants


def _immutable_module_values(tree: ast.AST) -> dict[str, tuple[str, ...]]:
    """Resolve direct module constants whose finite string values are closed.

    Unlike ``_module_string_constants`` this also follows a tuple of immutable
    string aliases.  Every candidate must have exactly one store in the module
    tree and a direct top-level assignment; conditional, dynamic, or repeated
    bindings are intentionally omitted.
    """
    if not isinstance(tree, ast.Module):
        return {}
    assignments: dict[str, list[ast.AST]] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            targets = _simple_assignment_names(statement.targets)
            for target in targets:
                assignments.setdefault(target, []).append(statement.value)
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            assignments.setdefault(statement.target.id, []).append(statement.value)
    writes = Counter(
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    )
    values: dict[str, tuple[str, ...]] = {}

    def resolve(node: ast.AST | None) -> tuple[str, ...] | None:
        literal = _literal_string(node)
        if literal is not None:
            return (literal,)
        if isinstance(node, ast.Name):
            return values.get(node.id)
        if isinstance(node, (ast.Tuple, ast.List)):
            result: list[str] = []
            for element in node.elts:
                if isinstance(element, ast.Starred):
                    return None
                element_value = resolve(element)
                if element_value is None:
                    return None
                result.extend(element_value)
            return tuple(result)
        return None

    for _ in range(max(4, len(assignments) + 1)):
        changed = False
        for name, candidates in assignments.items():
            if writes.get(name) != 1 or len(candidates) != 1:
                continue
            value = resolve(candidates[0])
            if value is not None and values.get(name) != value:
                values[name] = value
                changed = True
        if not changed:
            break
    return values


def _module_exported_names(tree: ast.AST) -> set[str]:
    if not isinstance(tree, ast.Module):
        return set()
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and "__all__" in _simple_assignment_names(statement.targets):
            values = _literal_string_sequence(statement.value)
            return set(values or ())
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "__all__"
        ):
            values = _literal_string_sequence(statement.value)
            return set(values or ())
    return set()


def _function_parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    arguments = node.args
    names = [argument.arg for argument in arguments.posonlyargs]
    names.extend(argument.arg for argument in arguments.args)
    names.extend(argument.arg for argument in arguments.kwonlyargs)
    if arguments.vararg is not None:
        names.append(arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.append(arguments.kwarg.arg)
    return names


def _merge_finite_values(
    left: tuple[str, ...] | None,
    right: tuple[str, ...] | None,
) -> tuple[str, ...] | None:
    """Union finite alternatives, with ``None`` representing unknown."""
    if left is None or right is None:
        return None
    result = list(left)
    for value in right:
        if value not in result:
            result.append(value)
    return tuple(result)


class _ClosedWorldFlowVisitor(ast.NodeVisitor):
    """Propagate finite argument alternatives through one local function."""

    def __init__(
        self,
        *,
        caller: str,
        functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
        module_values: dict[str, tuple[str, ...]],
        parameter_values: dict[str, tuple[str, ...] | None],
    ) -> None:
        self.caller = caller
        self.functions = functions
        self.module_values = module_values
        self.environment = dict(parameter_values)
        self.edges: list[tuple[str, dict[str, tuple[str, ...] | None]]] = []

    def _expression_values(self, node: ast.AST | None) -> tuple[str, ...] | None:
        literal = _literal_string(node)
        if literal is not None:
            return (literal,)
        if isinstance(node, ast.Name):
            if node.id in self.environment:
                return self.environment[node.id]
            return self.module_values.get(node.id)
        if isinstance(node, (ast.Tuple, ast.List)):
            result: list[str] = []
            for element in node.elts:
                if isinstance(element, ast.Starred):
                    return None
                values = self._expression_values(element)
                if values is None:
                    return None
                result.extend(values)
            return tuple(result)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._expression_values(node.left)
            right = self._expression_values(node.right)
            if left is not None and right is not None and len(left) == len(right) == 1:
                return (left[0] + right[0],)
        return None

    def _assign(self, name: str, values: tuple[str, ...] | None) -> None:
        if name in self.environment:
            # Parameters and prior local assignments are not immutable after a
            # write, even when the replacement happens to have the same value.
            self.environment[name] = None
        else:
            self.environment[name] = values

    def _call_arguments(
        self,
        node: ast.Call,
        callee: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> dict[str, tuple[str, ...] | None]:
        parameters = _function_parameter_names(callee)
        values: dict[str, tuple[str, ...] | None] = {parameter: None for parameter in parameters}
        positional = [argument for argument in node.args if not isinstance(argument, ast.Starred)]
        if any(isinstance(argument, ast.Starred) for argument in node.args):
            return values
        for index, argument in enumerate(positional):
            if index >= len(parameters):
                return {parameter: None for parameter in parameters}
            values[parameters[index]] = self._expression_values(argument)
        for keyword in node.keywords:
            if keyword.arg is None or keyword.arg not in values:
                return {parameter: None for parameter in parameters}
            values[keyword.arg] = self._expression_values(keyword.value)
        return values

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in self.functions:
            callee = self.functions[node.func.id]
            self.edges.append((node.func.id, self._call_arguments(node, callee)))
        self.generic_visit(node)

    def _visit_loop(self, node: ast.For | ast.AsyncFor) -> None:
        iterable = self._expression_values(node.iter)
        self.visit(node.iter)
        saved = dict(self.environment)
        target_names = _target_names(node.target)
        if not isinstance(node.target, ast.Name):
            iterable = None
        for name in target_names:
            self._assign(name, iterable)
        for statement in node.body:
            self.visit(statement)
        self.environment = saved
        for statement in node.orelse:
            self.visit(statement)
        self.environment = saved

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_loop(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        values = self._expression_values(node.value)
        target_names = _target_names(node.targets[0]) if node.targets else []
        if node.targets and not isinstance(node.targets[0], ast.Name):
            values = None
        for name in target_names:
            self._assign(name, values)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        values = self._expression_values(node.value)
        for name in _target_names(node.target):
            self._assign(name, values)
        if node.value is not None:
            self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        for name in _target_names(node.target):
            self._assign(name, None)
        self.visit(node.value)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


def _closed_world_parameter_values(
    tree: ast.AST,
) -> dict[tuple[str, str], tuple[str, ...] | None]:
    """Resolve parameters of private functions only through proven local callers."""
    if not isinstance(tree, ast.Module):
        return {}
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    duplicate_names: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if statement.name in functions:
                duplicate_names.add(statement.name)
            else:
                functions[statement.name] = statement
    exported = _module_exported_names(tree)
    private = {
        name for name in functions if name.startswith("_") and name not in exported and name not in duplicate_names
    }
    targets = private & CLOSED_WORLD_A_HELPER_NAMES
    if not targets:
        return {}

    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    def enclosing_function(node: ast.AST) -> str | None:
        parent = parents.get(node)
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return parent.name
            if isinstance(parent, ast.Lambda):
                return None
            parent = parents.get(parent)
        return None

    call_sites: dict[str, list[str | None]] = {name: [] for name in private}
    invalid_reference: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in private:
            call_sites[node.func.id].append(enclosing_function(node))
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in private:
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                invalid_reference.add(node.id)

    module_values = _immutable_module_values(tree)
    contexts: dict[str, dict[str, tuple[str, ...] | None]] = {}
    queue: list[str] = []
    for name, function in functions.items():
        if name in private:
            continue
        contexts[name] = {parameter: None for parameter in _function_parameter_names(function)}
        queue.append(name)

    def merge_context(
        name: str,
        incoming: dict[str, tuple[str, ...] | None],
    ) -> bool:
        function = functions[name]
        parameters = _function_parameter_names(function)
        if name not in contexts:
            contexts[name] = {parameter: incoming.get(parameter) for parameter in parameters}
            return True
        current = contexts[name]
        changed = False
        for parameter in parameters:
            merged = _merge_finite_values(current.get(parameter), incoming.get(parameter))
            if merged != current.get(parameter):
                current[parameter] = merged
                changed = True
        return changed

    processed = 0
    while processed < len(queue):
        caller = queue[processed]
        processed += 1
        flow = _ClosedWorldFlowVisitor(
            caller=caller,
            functions=functions,
            module_values=module_values,
            parameter_values=contexts[caller],
        )
        for statement in functions[caller].body:
            flow.visit(statement)
        for callee, incoming in flow.edges:
            if callee not in private:
                continue
            if merge_context(callee, incoming):
                queue.append(callee)

    # Re-run each proven context once to collect final argument alternatives.
    edge_values: dict[tuple[str, str, str], tuple[str, ...] | None] = {}
    for caller, context in contexts.items():
        flow = _ClosedWorldFlowVisitor(
            caller=caller,
            functions=functions,
            module_values=module_values,
            parameter_values=context,
        )
        for statement in functions[caller].body:
            flow.visit(statement)
        for callee, incoming in flow.edges:
            for parameter in _function_parameter_names(functions[callee]):
                key = (caller, callee, parameter)
                incoming_value = incoming.get(parameter)
                if key not in edge_values:
                    edge_values[key] = incoming_value
                else:
                    edge_values[key] = _merge_finite_values(edge_values[key], incoming_value)

    function_query_families = _function_query_families(tree)
    query_parameters = {
        function_name: {
            parameter
            for (candidate_function, parameter) in function_query_families
            if candidate_function == function_name
        }
        for function_name in functions
    }
    result: dict[tuple[str, str], tuple[str, ...] | None] = {}
    for callee in targets:
        sites = call_sites[callee]
        if not sites or callee in invalid_reference or any(caller not in contexts for caller in sites):
            continue
        parameters = _function_parameter_names(functions[callee])
        for parameter in parameters:
            if parameter not in query_parameters.get(callee, set()):
                continue
            body_collector = _ScopeWriteCollector()
            for statement in functions[callee].body:
                body_collector.visit(statement)
            if body_collector.counts.get(parameter, 0):
                # The parameter is no longer an immutable call input once the
                # helper writes it, even if every caller supplied a literal.
                continue
            values: tuple[str, ...] | None = ()
            proven = True
            for caller in sites:
                if caller is None:
                    proven = False
                    break
                edge = edge_values.get((caller, callee, parameter))
                if edge is None:
                    proven = False
                    break
                values = _merge_finite_values(values, edge)
            if proven and values:
                result[(callee, parameter)] = values
    return result


def _function_query_families(tree: ast.AST) -> dict[tuple[str, str], set[str]]:
    """Map function parameters used as query IDs to their query families."""
    if not isinstance(tree, ast.Module):
        return {}
    query_families = dict(QUERY_FAMILY_BY_SYMBOL)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in QUERY_FAMILY_BY_SYMBOL:
                    query_families[alias.asname or alias.name] = QUERY_FAMILY_BY_SYMBOL[alias.name]
    result: dict[tuple[str, str], set[str]] = {}
    for function in tree.body:
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        parameters = set(_function_parameter_names(function))
        for node in ast.walk(function):
            if not isinstance(node, ast.Call) or not isinstance(node.func, (ast.Name, ast.Attribute)):
                continue
            family = query_families.get(_call_symbol(node.func))
            if family is None:
                continue
            fact_expr = next((keyword.value for keyword in node.keywords if keyword.arg == "fact_id"), None)
            if isinstance(fact_expr, ast.Name) and fact_expr.id in parameters:
                result.setdefault((function.name, fact_expr.id), set()).add(family)
    return result


MAPPING_PROVENANCE_HELPER_NAMES = frozenset({"_modelo_202_applicability_declarations"})
_MAPPING_CANDIDATE_CACHE: dict[tuple[str, str], tuple[str, ...] | None] = {}


def _mapping_return_fact_ids(tree: ast.AST) -> dict[str, str]:
    """Find the registry mapping fact returned by the bounded helper set."""
    if not isinstance(tree, ast.Module):
        return {}
    module_values = _immutable_module_values(tree)
    constants = _module_string_constants(tree)
    result: dict[str, str] = {}
    for function in tree.body:
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if function.name not in MAPPING_PROVENANCE_HELPER_NAMES:
            continue
        fact_ids: list[str] = []
        for node in ast.walk(function):
            if not isinstance(node, ast.Call) or _call_symbol(node.func) != "MappingFactQuery":
                continue
            expression = next((keyword.value for keyword in node.keywords if keyword.arg == "fact_id"), None)
            if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
                fact_ids.append(expression.value)
            elif isinstance(expression, ast.Name):
                values = module_values.get(expression.id)
                if values is None:
                    value = constants.get(expression.id)
                    if value is not None:
                        values = (value,)
                if values is not None and len(values) == 1:
                    fact_ids.append(values[0])
        if len(set(fact_ids)) == 1:
            result[function.name] = fact_ids[0]
    return result


def _registry_mapping_candidates(mapping_fact_id: str, key: str) -> tuple[str, ...] | None:
    """Return all authored mapping values for one key, or ``None`` if unproven."""
    cache_key = (mapping_fact_id, key)
    if cache_key in _MAPPING_CANDIDATE_CACHE:
        return _MAPPING_CANDIDATE_CACHE[cache_key]
    try:
        artifact_payload, artifact_status, _metadata = _load_indexed_fact_authority(BUNDLED_AUTHORITY_DESCRIPTOR)
        compiled = _compiled_fact_index(artifact_payload) if artifact_status == "ok" else {}
    except (NameError, OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        compiled = {}
    fact = compiled.get(mapping_fact_id)
    variants = fact.get("variants") if isinstance(fact, dict) else None
    values: list[str] = []
    if not isinstance(variants, list) or not variants or not isinstance(fact, dict) or fact.get("family") != "mapping":
        _MAPPING_CANDIDATE_CACHE[cache_key] = None
        return None
    for variant in variants:
        payload = variant.get("payload") if isinstance(variant, dict) else None
        entries = payload.get("entries") if isinstance(payload, dict) else None
        matches = (
            [entry.get("value") for entry in entries if isinstance(entry, dict) and entry.get("key") == key]
            if isinstance(entries, list)
            else []
        )
        if len(matches) != 1 or not isinstance(matches[0], str) or not matches[0].strip():
            _MAPPING_CANDIDATE_CACHE[cache_key] = None
            return None
        values.append(matches[0])
    result = tuple(dict.fromkeys(values))
    _MAPPING_CANDIDATE_CACHE[cache_key] = result or None
    return _MAPPING_CANDIDATE_CACHE[cache_key]


# These are intentionally named seams rather than concrete fact consumers.  A
# generic resolver must not be made to look like one required fact merely
# because its ``fact_id`` parameter is not statically known at the definition
# site.  The scanner therefore records them separately and only clears one
# when the source proves the query family, temporal coordinate, closed failure
# behaviour, and a real authored/bundled caller or catalogue.
DYNAMIC_SEAM_SPECS: tuple[dict[str, Any], ...] = (
    {
        "file": "src/cadrumo/application/modelo/_objective_estimation_advisory.py",
        "symbol": "_resolve_objective_estimation_threshold",
        "query_family": "scalar",
        "fact_parameter": "fact_id",
        "axis_mode": "direct",
        "candidate_mode": "helper_calls",
        "candidate_helper": "_resolve_objective_estimation_threshold",
        "candidate_constant_names": (
            "_OBJECTIVE_ESTIMATION_SETTLED_MIN_FACT_ID",
            "_OBJECTIVE_ESTIMATION_SETTLED_MAX_FACT_ID",
        ),
    },
    {
        "file": "src/cadrumo/domain/calculations/registry/setup_profile_bindings.py",
        "symbol": "mapping_fact_entries",
        "query_family": "mapping",
        "fact_parameter": "fact_id",
        "axis_mode": "direct",
        "candidate_mode": "helper_calls",
        "candidate_helper": "mapping_fact_entries",
    },
    {
        "file": "src/cadrumo/domain/contribuyente/family_fact_context.py",
        "symbol": "FamilyFactResolutionContext::resolved_scalar",
        "query_family": "scalar",
        "fact_parameter": "fact_id",
        "axis_mode": "typed_module_mapping",
        "axis_mapping": "_FAMILY_FACT_DATE_AXES",
        "candidate_mode": "module_mapping_keys",
        "candidate_mapping": "_FAMILY_FACT_DATE_AXES",
    },
    {
        "file": "src/cadrumo/domain/deadlines/fact_context.py",
        "symbol": "DeadlineFactResolutionContext::resolved_scalar",
        "query_family": "scalar",
        "fact_parameter": "fact_id",
        "axis_mode": "registry_mapping_helper",
        "candidate_mode": "module_constants",
        "candidate_constant_names": ("_DEADLINE_FACT_DATE_AXIS_MAPPING_FACT_ID",),
    },
    {
        "file": "src/cadrumo/domain/deadlines/fact_context.py",
        "symbol": "DeadlineFactResolutionContext::resolved_mapping",
        "query_family": "mapping",
        "fact_parameter": "fact_id",
        "axis_mode": "registry_mapping_helper",
        "candidate_mode": "module_constants",
        "candidate_constant_names": ("_DEADLINE_FACT_DATE_AXIS_MAPPING_FACT_ID",),
    },
    {
        "file": "src/cadrumo/domain/modelos/modelo_fact_context.py",
        "symbol": "ModeloFactResolutionContext::resolved_scalar",
        "query_family": "scalar",
        "fact_parameter": "fact_id",
        "axis_mode": "typed_module_mapping",
        "axis_mapping": "_MODELO_FACT_DATE_AXES",
        "candidate_mode": "module_mapping_keys",
        "candidate_mapping": "_MODELO_FACT_DATE_AXES",
    },
    {
        "file": "src/cadrumo/domain/renta/_first_slice_routing.py",
        "symbol": "resolve_first_slice_expense_routing",
        "query_family": "mapping",
        "fact_parameter": "fact_id",
        "axis_mode": "direct",
        "candidate_mode": "helper_calls",
        "candidate_helper": "resolve_first_slice_expense_routing",
        "requires_query_service": True,
    },
    {
        "file": "src/cadrumo/domain/transactions/tipo_actividad_partitions.py",
        "symbol": "resolve_tipo_actividad_selector",
        "query_family": "entity_set",
        "fact_parameter": "fact_id",
        "query_fact_parameter": "normalized_fact_id",
        "axis_mode": "direct",
        "candidate_mode": "query_literals",
        "candidate_query": "MappingFactQuery",
        "requires_catalogue_membership": True,
    },
)


def _dynamic_seam_spec(file: str, symbol: str) -> dict[str, Any] | None:
    """Return the reviewed rule for one deliberately generic resolver seam."""
    for spec in DYNAMIC_SEAM_SPECS:
        if file == spec["file"] and symbol == spec["symbol"]:
            return spec
    return None


def _call_argument_for_parameter(
    node: ast.Call,
    parameter_names: Sequence[str],
    parameter: str,
) -> ast.AST | None:
    """Resolve one call argument without executing or guessing Python binding."""
    for keyword in node.keywords:
        if keyword.arg == parameter:
            return keyword.value
        if keyword.arg is None:
            return None
    try:
        index = parameter_names.index(parameter)
    except ValueError:
        return None
    return node.args[index] if index < len(node.args) else None


def _target_contains_name(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, (ast.Tuple, ast.List)):
        return any(_target_contains_name(element, name) for element in node.elts)
    if isinstance(node, ast.Starred):
        return _target_contains_name(node.value, name)
    return False


def _static_mapping_query_ids(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    constants: dict[str, str],
) -> tuple[str, ...] | None:
    """Return a function's fully static, typed mapping-query IDs."""
    query_ids: list[str] = []
    query_count = 0
    for node in ast.walk(function_node):
        if not isinstance(node, ast.Call) or _call_symbol(node.func) != "MappingFactQuery":
            continue
        query_count += 1
        fact_expression = next((keyword.value for keyword in node.keywords if keyword.arg == "fact_id"), None)
        fact_id = _static_string(fact_expression, constants)
        date_axis = next((keyword.value for keyword in node.keywords if keyword.arg == "date_axis"), None)
        effective_date = next((keyword.value for keyword in node.keywords if keyword.arg == "effective_date"), None)
        if fact_id is None or _date_axis_name(date_axis) is None or effective_date is None:
            return None
        query_ids.append(fact_id)
    return tuple(dict.fromkeys(query_ids)) if query_count else None


def _generic_mapping_producers(
    tree: ast.AST,
    constants: dict[str, str],
) -> dict[str, tuple[str, ...]]:
    """Find private helpers that validate and return a finite mapping result."""
    if not isinstance(tree, ast.Module):
        return {}
    producers: dict[str, tuple[str, ...]] = {}
    for function_node in tree.body:
        if not isinstance(function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not function_node.name.startswith("_"):
            continue
        mapping_ids = _static_mapping_query_ids(function_node, constants)
        if not mapping_ids:
            continue
        if not _function_has_authority_query(function_node):
            continue
        if not _function_has_raise(function_node) or _function_has_fallback_return_in_except(function_node):
            continue
        if not any(isinstance(node, ast.Name) and node.id == "ResolvedMappingFact" for node in ast.walk(function_node)):
            continue
        mapping_names: set[str] = set()
        for node in ast.walk(function_node):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                mapping_names.update(_simple_assignment_names(node.targets))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Dict):
                mapping_names.update(_target_names(node.target))
        if not mapping_names:
            continue
        returns_mapping = any(
            isinstance(node, ast.Return)
            and node.value is not None
            and any(
                isinstance(name_node, ast.Name) and name_node.id in mapping_names for name_node in ast.walk(node.value)
            )
            for node in ast.walk(function_node)
        )
        if returns_mapping:
            producers[function_node.name] = mapping_ids
    return producers


def _compiled_mapping_value_candidates(
    compiled: dict[str, dict[str, Any]],
    mapping_fact_ids: Sequence[str],
) -> tuple[str, ...]:
    """Extract finite mapping values from already bundled governed facts."""
    values: set[str] = set()
    for mapping_fact_id in mapping_fact_ids:
        fact = compiled.get(mapping_fact_id)
        if not isinstance(fact, dict) or fact.get("family") != "mapping":
            return ()
        variants = fact.get("variants")
        if not isinstance(variants, list) or not variants:
            return ()
        for variant in variants:
            payload = variant.get("payload") if isinstance(variant, dict) else None
            entries = payload.get("entries") if isinstance(payload, dict) else None
            if not isinstance(entries, list) or not entries:
                return ()
            for entry in entries:
                value = entry.get("value") if isinstance(entry, dict) else None
                if not isinstance(value, str) or not value.strip():
                    return ()
                values.add(value)
    # A formula-spec mapping can contain prose, operands, and derived
    # expressions alongside fact IDs.  Only values that are themselves
    # governed declarations in the bundled catalogue are valid candidates;
    # this keeps the inference finite without maintaining a name allowlist.
    return tuple(sorted(value for value in values if value in compiled))


def _generic_mapping_provenance_candidates(
    tree: ast.AST,
    *,
    helper_name: str,
    helper_node: ast.FunctionDef | ast.AsyncFunctionDef,
    constants: dict[str, str],
    compiled: dict[str, dict[str, Any]],
) -> tuple[tuple[str, ...], dict[str, Any]]:
    """Trace every private helper caller to a validated finite mapping."""
    if not isinstance(tree, ast.Module) or not helper_name.startswith("_"):
        return (), {}
    producers = _generic_mapping_producers(tree, constants)
    if not producers:
        return (), {}
    parameter_names = _function_parameter_names(helper_node)
    fact_parameters = [name for name in parameter_names if name == "fact_id"]
    if len(fact_parameters) != 1:
        return (), {}
    fact_parameter = fact_parameters[0]
    call_count = 0
    proven_call_count = 0
    mapping_ids: set[str] = set()
    for caller in tree.body:
        if not isinstance(caller, (ast.FunctionDef, ast.AsyncFunctionDef)) or caller.name == helper_name:
            continue
        scope_writes = _ScopeWriteCollector()
        for statement in caller.body:
            scope_writes.visit(statement)
        for call in ast.walk(caller):
            if not isinstance(call, ast.Call) or _call_symbol(call.func) != helper_name:
                continue
            call_count += 1
            fact_expression = _call_argument_for_parameter(call, parameter_names, fact_parameter)
            if not isinstance(fact_expression, ast.Subscript) or not isinstance(fact_expression.value, ast.Name):
                continue
            mapping_name = fact_expression.value.id
            if scope_writes.counts.get(mapping_name) != 1:
                continue
            producer_name: str | None = None
            for statement in caller.body:
                if isinstance(statement, ast.Assign):
                    targets = statement.targets
                    value = statement.value
                elif isinstance(statement, ast.AnnAssign):
                    targets = [statement.target]
                    value = statement.value
                else:
                    continue
                if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
                    continue
                if _target_contains_name(targets[0], mapping_name) and value.func.id in producers:
                    producer_name = value.func.id
                    break
            if producer_name is None:
                continue
            mapping_ids.update(producers[producer_name])
            proven_call_count += 1
    if not call_count or proven_call_count != call_count or not mapping_ids:
        return (), {}
    candidates = _compiled_mapping_value_candidates(compiled, sorted(mapping_ids))
    if not candidates:
        return (), {}
    return candidates, {
        "mapping_fact_ids": sorted(mapping_ids),
        "proven_call_count": proven_call_count,
        "call_count": call_count,
        "candidate_fact_ids": list(candidates),
    }


def _infer_dynamic_seam_spec(
    *,
    tree: ast.AST,
    function_node: ast.AST | None,
    query_node: ast.Call,
    fact_expression: ast.AST | None,
    query_family: str | None,
    constants: dict[str, str],
    compiled: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Infer a generic seam only when its complete finite provenance is proven."""
    if not isinstance(function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    if not function_node.name.startswith("_") or query_family is None:
        return None
    if not isinstance(fact_expression, ast.Name) or fact_expression.id != "fact_id":
        return None
    candidates, provenance = _generic_mapping_provenance_candidates(
        tree,
        helper_name=function_node.name,
        helper_node=function_node,
        constants=constants,
        compiled=compiled,
    )
    if not candidates:
        return None
    axis_expression = next((keyword.value for keyword in query_node.keywords if keyword.arg == "date_axis"), None)
    effective_date = next((keyword.value for keyword in query_node.keywords if keyword.arg == "effective_date"), None)
    if _date_axis_name(axis_expression) is None or effective_date is None:
        return None
    if not _function_has_authority_query(function_node):
        return None
    if not _function_has_raise(function_node) or _function_has_fallback_return_in_except(function_node):
        return None
    return {
        "query_family": query_family,
        "fact_parameter": "fact_id",
        "axis_mode": "direct",
        "candidate_mode": "inferred_mapping_provenance",
        "candidate_fact_ids": candidates,
        "mapping_provenance": provenance,
    }


def _module_literal_mapping_keys(tree: ast.AST, name: str) -> tuple[str, ...] | None:
    """Resolve keys of one immutable top-level literal mapping."""
    if not isinstance(tree, ast.Module):
        return None
    assignments: list[ast.Dict] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and name in _simple_assignment_names(statement.targets):
            if isinstance(statement.value, ast.Dict):
                assignments.append(statement.value)
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if statement.target.id == name and isinstance(statement.value, ast.Dict):
                assignments.append(statement.value)
    writes = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == name
    )
    if writes != 1 or len(assignments) != 1:
        return None
    keys: list[str] = []
    for key_node in assignments[0].keys:
        key = _literal_string(key_node)
        if key is None or key in keys:
            return None
        keys.append(key)
    return tuple(keys) if keys else None


def _typed_date_axis_mapping_proof(tree: ast.AST, name: str) -> tuple[bool, tuple[str, ...]]:
    """Prove that a module mapping is a closed map of valid DateAxis members."""
    if not isinstance(tree, ast.Module):
        return False, ()
    assignments: list[ast.Dict] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and name in _simple_assignment_names(statement.targets):
            if isinstance(statement.value, ast.Dict):
                assignments.append(statement.value)
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if statement.target.id == name and isinstance(statement.value, ast.Dict):
                assignments.append(statement.value)
    writes = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == name
    )
    if writes != 1 or len(assignments) != 1:
        return False, ()
    keys: list[str] = []
    for key_node, value_node in zip(assignments[0].keys, assignments[0].values):
        key = _literal_string(key_node)
        axis = _date_axis_name(value_node)
        if key is None or axis is None or key in keys:
            return False, ()
        keys.append(key)
    return bool(keys), tuple(keys)


def _helper_fact_expression(node: ast.Call, helper: str) -> ast.AST | None:
    """Get the fact ID expression from a reviewed helper call shape."""
    if _call_symbol(node.func) != helper:
        return None
    for keyword in node.keywords:
        if keyword.arg == "fact_id":
            return keyword.value
    if helper in {"mapping_fact_entries", "resolve_tipo_actividad_selector"} and node.args:
        return node.args[0]
    return None


def _collect_helper_call_candidates(source_paths: Sequence[str], helpers: set[str]) -> dict[str, tuple[str, ...]]:
    """Collect only literal fact IDs supplied to generic helper callers."""
    candidates: dict[str, set[str]] = {helper: set() for helper in helpers}
    for relative in source_paths:
        path = REPO_ROOT / Path(*PurePosixPath(relative).parts)
        try:
            tree = ast.parse(_decode_python_source(path.read_bytes()), filename=relative)
        except (OSError, SyntaxError, LookupError, UnicodeDecodeError, ValueError, TypeError):
            continue
        constants = _module_string_constants(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            helper = _call_symbol(node.func)
            if helper not in helpers:
                continue
            expression = _helper_fact_expression(node, helper)
            value = _static_string(expression, constants)
            if value:
                candidates[helper].add(value)
    return {helper: tuple(sorted(values)) for helper, values in candidates.items()}


def _query_literal_candidates(tree: ast.AST, query_symbol: str, constants: dict[str, str]) -> tuple[str, ...]:
    """Collect direct literal IDs from one bounded registry catalogue query."""
    values: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_symbol(node.func) != query_symbol:
            continue
        expression = next((keyword.value for keyword in node.keywords if keyword.arg == "fact_id"), None)
        value = _static_string(expression, constants)
        if value:
            values.add(value)
    return tuple(sorted(values))


def _function_has_raise(node: ast.AST) -> bool:
    return any(isinstance(item, ast.Raise) for item in ast.walk(node))


def _function_has_fallback_return_in_except(node: ast.AST) -> bool:
    for item in ast.walk(node):
        if not isinstance(item, ast.ExceptHandler):
            continue
        if any(isinstance(child, ast.Return) for statement in item.body for child in ast.walk(statement)):
            return True
    return False


def _function_has_fact_reassignment(node: ast.AST, parameter: str) -> bool:
    return any(
        isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store) and item.id == parameter
        for item in ast.walk(node)
    )


def _function_has_strip_normalization(node: ast.AST, parameter: str, normalized: str) -> bool:
    for item in ast.walk(node):
        if not isinstance(item, ast.Assign):
            continue
        targets = _simple_assignment_names(item.targets)
        if targets != [normalized]:
            continue
        value = item.value
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "strip"
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == parameter
            and not value.args
            and not value.keywords
        ):
            return True
    return False


def _function_has_catalogue_membership(node: ast.AST, normalized: str) -> bool:
    for item in ast.walk(node):
        if not isinstance(item, ast.Compare) or len(item.ops) != 1 or len(item.comparators) != 1:
            continue
        if not isinstance(item.left, ast.Name) or item.left.id != normalized:
            continue
        if not isinstance(item.ops[0], (ast.In, ast.NotIn)):
            continue
        right = item.comparators[0]
        if isinstance(right, ast.Call) and _call_symbol(right.func) == "_registry_activity_selector_catalogue":
            return True
    return False


def _function_has_typed_axis_map_use(node: ast.AST, mapping_name: str, fact_parameter: str) -> bool:
    for item in ast.walk(node):
        if not isinstance(item, ast.Assign):
            continue
        targets = _simple_assignment_names(item.targets)
        if not targets or not isinstance(item.value, ast.Subscript):
            continue
        if not isinstance(item.value.value, ast.Name) or item.value.value.id != mapping_name:
            continue
        key = item.value.slice
        if isinstance(key, ast.Name) and key.id == fact_parameter:
            return True
    return False


def _function_has_registry_date_axis_helper(tree: ast.AST, node: ast.AST, fact_parameter: str) -> bool:
    """Prove a deadline axis is validated by its registry mapping helper."""
    called = any(
        isinstance(item, ast.Call)
        and _call_symbol(item.func) == "_date_axis"
        and len(item.args) == 1
        and isinstance(item.args[0], ast.Name)
        and item.args[0].id == fact_parameter
        for item in ast.walk(node)
    )
    if not called:
        return False
    has_mapping_query = any(
        isinstance(item, ast.Call) and _call_symbol(item.func) == "MappingFactQuery" for item in ast.walk(tree)
    )
    has_axis_validation = any(
        isinstance(item, ast.Call) and _call_symbol(item.func) == "DateAxis" for item in ast.walk(tree)
    )
    return has_mapping_query and has_axis_validation and _function_has_raise(tree)


def _authority_receiver_proven(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "resolve_governed_fact":
        return False
    receiver = node.func.value
    if isinstance(receiver, ast.Name):
        return receiver.id in {"authority", "selected_authority"}
    if isinstance(receiver, ast.Attribute):
        return isinstance(receiver.value, ast.Name) and receiver.value.id == "self" and receiver.attr == "authority"
    return isinstance(receiver, ast.Call) and _call_symbol(receiver.func) == "bundled_authority"


def _function_has_authority_query(node: ast.AST | None) -> bool:
    """Find the validated-authority call that consumes the query object."""
    if node is None:
        return False
    return any(isinstance(item, ast.Call) and _authority_receiver_proven(item) for item in ast.walk(node))


def _dynamic_seam_static_proof(
    *,
    spec: dict[str, Any],
    tree: ast.AST,
    function_node: ast.AST | None,
    query_node: ast.Call,
    fact_expression: ast.AST | None,
) -> dict[str, Any]:
    """Return an auditable AST proof for one generic resolver call."""
    proof: list[str] = []
    failures: list[str] = []
    family = spec["query_family"]
    if function_node is None:
        failures.append("function_scope_unresolved")
    else:
        parameters = (
            set(_function_parameter_names(function_node))
            if isinstance(function_node, (ast.FunctionDef, ast.AsyncFunctionDef))
            else set()
        )
        parameter = spec["fact_parameter"]
        query_parameter = spec.get("query_fact_parameter", parameter)
        if parameter not in parameters:
            failures.append("fact_id_parameter_missing")
        if not isinstance(fact_expression, ast.Name) or fact_expression.id != query_parameter:
            failures.append("fact_id_not_formal_or_validated_binding")
        elif query_parameter == parameter:
            if _function_has_fact_reassignment(function_node, parameter):
                failures.append("fact_id_reassigned")
            else:
                proof.append("fact_id_passed_unchanged_from_formal")
        elif not _function_has_strip_normalization(function_node, parameter, query_parameter):
            failures.append("fact_id_normalization_unproven")
        elif not _function_has_catalogue_membership(function_node, query_parameter):
            failures.append("registry_catalogue_membership_unproven")
        else:
            proof.append("fact_id_normalized_then_membership_checked_against_registry_catalogue")

        if spec["axis_mode"] == "direct":
            axis_expression = next(
                (keyword.value for keyword in query_node.keywords if keyword.arg == "date_axis"), None
            )
            axis_name = _date_axis_name(axis_expression)
            if axis_name is None:
                failures.append("typed_date_axis_unproven")
            else:
                proof.append(
                    "typed_filing_period_axis" if axis_name == "filing_period" else f"typed_date_axis:{axis_name}"
                )
        elif spec["axis_mode"] == "typed_module_mapping":
            axis_expression = next(
                (keyword.value for keyword in query_node.keywords if keyword.arg == "date_axis"), None
            )
            mapping_name = spec["axis_mapping"]
            valid_mapping, _ = _typed_date_axis_mapping_proof(tree, mapping_name)
            if (
                not isinstance(axis_expression, ast.Name)
                or not valid_mapping
                or not _function_has_typed_axis_map_use(function_node, mapping_name, parameter)
            ):
                failures.append("typed_date_axis_mapping_unproven")
            else:
                proof.append(f"typed_date_axis_mapping:{mapping_name}")
        elif spec["axis_mode"] == "registry_mapping_helper":
            if not _function_has_registry_date_axis_helper(tree, function_node, parameter):
                failures.append("registry_date_axis_mapping_unproven")
            else:
                proof.append("registry_validated_date_axis_mapping")
        else:
            failures.append("unknown_axis_proof_rule")

        effective_date = next(
            (keyword.value for keyword in query_node.keywords if keyword.arg == "effective_date"), None
        )
        if effective_date is None:
            failures.append("effective_date_missing")
        else:
            proof.append("effective_date_supplied")
        if not _function_has_raise(function_node):
            failures.append("closed_failure_raise_unproven")
        elif _function_has_fallback_return_in_except(function_node):
            failures.append("exception_fallback_return_present")
        else:
            proof.append("failure_is_closed_without_payload_fallback")

    if not _function_has_authority_query(function_node):
        failures.append("validated_authority_query_receiver_unproven")
    else:
        proof.append("validated_authority_resolve_governed_fact")
    if spec.get("requires_query_service"):
        if function_node is None or not any(
            isinstance(item, ast.Call) and _call_symbol(item.func) == "RegistryQueryService"
            for item in ast.walk(function_node)
        ):
            failures.append("validated_registry_query_service_scope_unproven")
        else:
            proof.append("validated_registry_query_service_scope")
    if (
        spec.get("requires_catalogue_membership")
        and function_node is not None
        and _function_has_catalogue_membership(function_node, spec.get("query_fact_parameter", spec["fact_parameter"]))
    ):
        proof.append("bounded_registry_catalogue_membership")
    elif spec.get("requires_catalogue_membership"):
        failures.append("bounded_registry_catalogue_membership_unproven")
    return {
        "static_proven": not failures,
        "proof": proof,
        "failures": failures,
        "query_family": family,
    }


class _ConsumerQueryVisitor(ast.NodeVisitor):
    """Find statically named governed-fact query seams in one module."""

    def __init__(
        self,
        *,
        file: str,
        constants: dict[str, str],
        tree: ast.AST,
        helper_call_candidates: dict[str, tuple[str, ...]] | None = None,
        compiled_fact_index: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.file = file
        self.constants = constants
        self.tree = tree
        self.symbol_stack: list[str] = []
        self.function_node_stack: list[ast.AST] = []
        self.observations: list[dict[str, Any]] = []
        self.malformed_observations: list[dict[str, Any]] = []
        self.dynamic_observations: list[dict[str, Any]] = []
        self.helper_call_candidates = helper_call_candidates or {}
        self.compiled_fact_index = compiled_fact_index or {}
        self.query_symbols = set(CONSUMER_QUERY_SYMBOLS)
        self.query_family_by_symbol = dict(QUERY_FAMILY_BY_SYMBOL)
        module_body = tree.body if isinstance(tree, ast.Module) else []
        self.scope_stack: list[dict[str, Any]] = [_scope_bindings(module_body)]
        self.loop_bindings: list[dict[str, tuple[str, ...] | None]] = []
        self.function_scope_stack: list[str] = []
        self.mapping_return_facts = _mapping_return_fact_ids(tree)
        self.mapping_scope_stack: list[dict[str, str]] = [self._mapping_scope_bindings(module_body)]
        self.immutable_module_values = _immutable_module_values(tree)
        self.closed_world_values = _closed_world_parameter_values(tree)
        self.closed_world_families = _function_query_families(tree)
        self.import_bindings, self.invalid_import_bindings = self._import_bindings(tree)
        self.module_tree_cache: dict[str, ast.Module | None] = {}

    def _dynamic_candidate_ids(self, spec: dict[str, Any]) -> tuple[str, ...]:
        mode = spec.get("candidate_mode")
        if mode == "helper_calls":
            helper = spec.get("candidate_helper")
            candidates = self.helper_call_candidates.get(helper, ()) if isinstance(helper, str) else ()
            names = spec.get("candidate_constant_names", ())
            if names:
                candidates = tuple(candidates) + tuple(self.constants[name] for name in names if name in self.constants)
            return tuple(sorted(set(candidates)))
        if mode == "module_mapping_keys":
            mapping_name = spec.get("candidate_mapping")
            if isinstance(mapping_name, str):
                return _module_literal_mapping_keys(self.tree, mapping_name) or ()
            return ()
        if mode == "module_constants":
            names = spec.get("candidate_constant_names", ())
            return tuple(sorted({self.constants[name] for name in names if name in self.constants}))
        if mode == "query_literals":
            query_symbol = spec.get("candidate_query")
            if isinstance(query_symbol, str):
                return _query_literal_candidates(self.tree, query_symbol, self.constants)
        if mode == "inferred_mapping_provenance":
            candidates = spec.get("candidate_fact_ids", ())
            return tuple(sorted({value for value in candidates if isinstance(value, str) and value.strip()}))
        return ()

    def _dynamic_observation(
        self,
        *,
        node: ast.Call,
        observation: dict[str, Any],
        fact_expression: ast.AST | None,
        resolution: dict[str, Any],
    ) -> dict[str, Any] | None:
        symbol = "::".join(self.symbol_stack)
        query_family = self.query_family_by_symbol.get(_call_symbol(node.func) or "")
        function_node = self.function_node_stack[-1] if self.function_node_stack else None
        # Structural inference supersedes the legacy reviewed specs whenever
        # the source itself proves finite mapping provenance.  The bounded
        # specs remain only for existing generic seams whose caller/catalogue
        # shape is not expressible through this inference yet.
        spec = _infer_dynamic_seam_spec(
            tree=self.tree,
            function_node=function_node,
            query_node=node,
            fact_expression=fact_expression,
            query_family=query_family,
            constants=self.constants,
            compiled=self.compiled_fact_index,
        )
        if spec is None:
            spec = _dynamic_seam_spec(self.file, symbol)
        if spec is None:
            return None
        if query_family != spec.get("query_family"):
            return {
                **observation,
                "dynamic_seam": True,
                "candidate_fact_ids": [],
                "dynamic_seam_proof": {
                    "static_proven": False,
                    "proof": [],
                    "failures": ["query_family_mismatch"],
                },
                "blocking": True,
                "blockers": ["dynamic_seam_proof_failed", "query_family_mismatch"],
            }
        proof = _dynamic_seam_static_proof(
            spec=spec,
            tree=self.tree,
            function_node=function_node,
            query_node=node,
            fact_expression=fact_expression,
        )
        if spec.get("mapping_provenance"):
            proof["mapping_provenance"] = spec["mapping_provenance"]
            proof.setdefault("proof", []).append("finite_mapping_spec_provenance")
        candidates = self._dynamic_candidate_ids(spec)
        return {
            **observation,
            "dynamic_seam": True,
            "candidate_fact_ids": list(candidates),
            "fact_id_resolution": {
                **observation.get("fact_id_resolution", {}),
                "mode": "typed_dynamic_seam",
                "candidate_fact_ids": list(candidates),
            },
            "dynamic_seam_proof": proof,
            "blocking": not bool(proof.get("static_proven")) or not candidates,
            "blockers": (
                ["dynamic_seam_proof_failed", *proof.get("failures", [])]
                if not proof.get("static_proven")
                else (["dynamic_seam_coverage_missing"] if not candidates else [])
            ),
            "resolution_mode": resolution.get("mode"),
        }

    def _mapping_scope_bindings(self, body: Sequence[ast.stmt]) -> dict[str, str]:
        collector = _ScopeWriteCollector()
        for statement in body:
            collector.visit(statement)
        bindings: dict[str, str] = {}
        for statement in body:
            if isinstance(statement, ast.Assign):
                targets = _simple_assignment_names(statement.targets)
                value = statement.value
            elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                targets = [statement.target.id]
                value = statement.value
            else:
                continue
            if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
                continue
            mapping_fact_id = self.mapping_return_facts.get(value.func.id)
            if mapping_fact_id is None:
                continue
            for target in targets:
                if collector.counts.get(target) == 1:
                    bindings[target] = mapping_fact_id
        return bindings

    def _import_bindings(self, tree: ast.AST) -> tuple[dict[str, dict[str, Any]], set[str]]:
        """Index only explicit, local-source imports; never execute imports."""
        bindings: dict[str, dict[str, Any]] = {}
        invalid: set[str] = set()
        if not isinstance(tree, ast.Module):
            return bindings, invalid
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom):
                if any(alias.name == "*" for alias in statement.names):
                    # A star import cannot contribute a statically attributable
                    # fact ID.  It is deliberately not indexed as a binding.
                    continue
                module = _resolve_import_module(
                    self.file,
                    level=statement.level,
                    module=statement.module,
                )
                if module is None:
                    continue
                for alias in statement.names:
                    bound_name = alias.asname or alias.name
                    binding = {
                        "kind": "from",
                        "module": module,
                        "name": alias.name,
                    }
                    if bound_name in bindings:
                        invalid.add(bound_name)
                    else:
                        bindings[bound_name] = binding
            elif isinstance(statement, ast.Import):
                for alias in statement.names:
                    # An unaliased dotted import binds its first component,
                    # whose attribute chain is ambiguous for this detector.
                    if alias.asname is None and "." in alias.name:
                        continue
                    bound_name = alias.asname or alias.name
                    module = alias.name
                    if not module.startswith("cadrumo"):
                        continue
                    binding = {"kind": "module", "module": module}
                    if bound_name in bindings:
                        invalid.add(bound_name)
                    else:
                        bindings[bound_name] = binding
        # Any assignment/argument/definition with the same name invalidates an
        # imported alias.  This is conservative across local scopes, which is
        # preferable to attributing a dynamic or shadowed value as a fact.
        invalid.update(name for name in bindings if name in _all_binding_writes(tree))
        return bindings, invalid

    def _local_module_tree(self, module: str) -> ast.Module | None:
        if module in self.module_tree_cache:
            return self.module_tree_cache[module]
        path = _local_module_path(module)
        if path is None:
            self.module_tree_cache[module] = None
            return None
        try:
            source = _decode_python_source(path.read_bytes())
            tree = ast.parse(source, filename=path.as_posix())
        except (OSError, LookupError, UnicodeDecodeError, SyntaxError, ValueError, TypeError):
            tree = None
        self.module_tree_cache[module] = tree
        return tree

    def _resolve_imported_string(self, binding: dict[str, Any]) -> str | None:
        module = binding.get("module")
        name = binding.get("name")
        if not isinstance(module, str) or not isinstance(name, str):
            return None
        tree = self._local_module_tree(module)
        if tree is None:
            return None
        return _module_top_level_literal_string(tree, name)

    def _resolve_imported_member(self, binding: dict[str, Any], member: str) -> str | None:
        module = binding.get("module")
        class_name = binding.get("name")
        if not isinstance(module, str) or not isinstance(class_name, str):
            return None
        tree = self._local_module_tree(module)
        if tree is None:
            return None
        return _module_enum_member_literal(tree, class_name, member)

    def _scope_value(self, name: str) -> str | tuple[str, ...] | None:
        for loop_scope in reversed(self.loop_bindings):
            if name in loop_scope:
                return loop_scope[name]
        for function_name in reversed(self.function_scope_stack):
            key = (function_name, name)
            if key in self.closed_world_values:
                return self.closed_world_values[key]
        for scope in reversed(self.scope_stack):
            if name in scope["sequences"]:
                return scope["sequences"][name]
            if name in scope["strings"]:
                return scope["strings"][name]
            if name in scope["blocked"]:
                return None
        if name in self.invalid_import_bindings:
            return None
        binding = self.import_bindings.get(name)
        if binding is not None and binding.get("kind") == "from":
            return self._resolve_imported_string(binding)
        if name in self.immutable_module_values:
            return self.immutable_module_values[name]
        return self.constants.get(name)

    def _scope_mapping(self, name: str) -> dict[str, str] | None:
        for scope in reversed(self.scope_stack):
            mapping = scope.get("mappings", {}).get(name)
            if mapping is not None:
                return mapping
            if name in scope.get("blocked", set()):
                return None
        return None

    def _registry_mapping_for_name(self, name: str) -> str | None:
        for scope in reversed(self.mapping_scope_stack):
            if name in scope:
                return scope[name]
        return None

    def _resolve_attribute(self, node: ast.Attribute) -> str | None:
        if not isinstance(node.value, ast.Name):
            # In particular, reject unknown/nested module attributes rather
            # than recursively evaluating arbitrary expression trees.
            return None
        binding_name = node.value.id
        if binding_name in self.invalid_import_bindings:
            return None
        binding = self.import_bindings.get(binding_name)
        if binding is None:
            return None
        kind = binding.get("kind")
        if kind == "from":
            return self._resolve_imported_member(binding, node.attr)
        if kind == "module":
            module = binding.get("module")
            if not isinstance(module, str):
                return None
            tree = self._local_module_tree(module)
            return _module_top_level_literal_string(tree, node.attr) if tree is not None else None
        return None

    def _resolve_string_expression(self, node: ast.AST | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            value = self._scope_value(node.id)
            return value if isinstance(value, str) else None
        if isinstance(node, ast.Attribute):
            return self._resolve_attribute(node)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._resolve_string_expression(node.left)
            right = self._resolve_string_expression(node.right)
            if left is not None and right is not None:
                return left + right
        return None

    def _fact_id_resolution(self, node: ast.AST | None) -> dict[str, Any]:
        if node is None:
            return {"ids": None, "mode": "unresolved"}
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {"ids": (node.value,), "mode": "exact_literal"}
        if isinstance(node, ast.Name):
            value = self._scope_value(node.id)
            if isinstance(value, tuple):
                return {
                    "ids": value,
                    "mode": "finite_candidates" if len(value) != 1 else "exact_binding",
                }
            if isinstance(value, str):
                return {"ids": (value,), "mode": "exact_binding"}
            return {"ids": None, "mode": "unresolved"}
        if isinstance(node, ast.Attribute):
            value = self._resolve_attribute(node)
            return {
                "ids": (value,) if value is not None else None,
                "mode": "exact_imported_attribute" if value is not None else "unresolved",
            }
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            mapping_name = node.value.id
            key = self._resolve_string_expression(node.slice)
            local_mapping = self._scope_mapping(mapping_name)
            if local_mapping is not None:
                if key is None:
                    values = tuple(dict.fromkeys(local_mapping.values()))
                    return {
                        "ids": values or None,
                        "mode": "finite_mapping_candidates" if values else "typed_dynamic_mapping",
                        "mapping_name": mapping_name,
                    }
                if key in local_mapping:
                    return {
                        "ids": (local_mapping[key],),
                        "mode": "exact_mapping_key",
                        "mapping_name": mapping_name,
                        "mapping_key": key,
                    }
                return {
                    "ids": None,
                    "mode": "mapping_key_missing",
                    "mapping_name": mapping_name,
                    "mapping_key": key,
                }
            mapping_fact_id = self._registry_mapping_for_name(mapping_name)
            if mapping_fact_id is not None:
                if key is None:
                    return {
                        "ids": None,
                        "mode": "typed_dynamic_mapping",
                        "mapping_fact_id": mapping_fact_id,
                        "mapping_name": mapping_name,
                    }
                values = _registry_mapping_candidates(mapping_fact_id, key)
                if values:
                    return {
                        "ids": values,
                        "mode": "finite_registry_mapping_candidates",
                        "mapping_fact_id": mapping_fact_id,
                        "mapping_name": mapping_name,
                        "mapping_key": key,
                    }
                return {
                    "ids": None,
                    "mode": "typed_dynamic_mapping",
                    "mapping_fact_id": mapping_fact_id,
                    "mapping_name": mapping_name,
                    "mapping_key": key,
                }
            return {"ids": None, "mode": "unresolved"}
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            value = self._resolve_string_expression(node)
            return {
                "ids": (value,) if value is not None else None,
                "mode": "exact_expression" if value is not None else "unresolved",
            }
        return {"ids": None, "mode": "unresolved"}

    def _resolve_fact_ids(self, node: ast.AST | None) -> tuple[str, ...] | None:
        return self._fact_id_resolution(node).get("ids")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Recognize aliases of every governed-fact query family."""
        for imported in node.names:
            if imported.name in CONSUMER_QUERY_SYMBOLS:
                symbol = imported.asname or imported.name
                self.query_symbols.add(symbol)
                self.query_family_by_symbol[symbol] = QUERY_FAMILY_BY_SYMBOL[imported.name]
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Retain module imports for attribute-shaped query calls."""
        self.generic_visit(node)

    def _visit_symbol(
        self,
        node: ast.AST,
        name: str,
        *,
        body: Sequence[ast.stmt] | None = None,
        arguments: ast.arguments | None = None,
    ) -> None:
        self.symbol_stack.append(name)
        self.function_node_stack.append(node)
        if body is not None:
            self.scope_stack.append(_scope_bindings(body, arguments=arguments))
            self.mapping_scope_stack.append(self._mapping_scope_bindings(body))
        if arguments is not None:
            self.function_scope_stack.append(name)
        try:
            self.generic_visit(node)
        finally:
            if arguments is not None:
                self.function_scope_stack.pop()
            if body is not None:
                self.mapping_scope_stack.pop()
                self.scope_stack.pop()
            self.function_node_stack.pop()
            self.symbol_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_symbol(node, node.name, body=node.body, arguments=node.args)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_symbol(node, node.name, body=node.body, arguments=node.args)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_symbol(node, node.name, body=node.body)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_symbol(node, "<lambda>", body=[], arguments=node.args)

    def _visit_comprehension_expression(
        self,
        node: ast.GeneratorExp | ast.ListComp | ast.SetComp | ast.DictComp,
    ) -> None:
        local_bindings: dict[str, tuple[str, ...] | None] = {}
        self.loop_bindings.append(local_bindings)
        try:
            for generator in node.generators:
                values = self._resolve_fact_ids(generator.iter)
                self.visit(generator.iter)
                target_names = _target_names(generator.target)
                if isinstance(generator.target, ast.Name):
                    target_names = [generator.target.id]
                for target_name in target_names:
                    local_bindings[target_name] = values
                for condition in generator.ifs:
                    self.visit(condition)
            if isinstance(node, ast.DictComp):
                self.visit(node.key)
                self.visit(node.value)
            else:
                self.visit(node.elt)
        finally:
            self.loop_bindings.pop()

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension_expression(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension_expression(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension_expression(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension_expression(node)

    def _visit_loop(self, node: ast.For | ast.AsyncFor) -> None:
        values = self._resolve_fact_ids(node.iter)
        self.visit(node.iter)
        local_bindings: dict[str, tuple[str, ...] | None] = {}
        if not isinstance(node.target, ast.Name):
            values = None
        for target_name in _target_names(node.target):
            local_bindings[target_name] = values
        self.loop_bindings.append(local_bindings)
        try:
            for statement in node.body:
                self.visit(statement)
            for statement in node.orelse:
                self.visit(statement)
        finally:
            self.loop_bindings.pop()

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_loop(node)

    def visit_Call(self, node: ast.Call) -> None:
        query_kind = _call_symbol(node.func)
        if query_kind in self.query_symbols:
            fact_expr = next((keyword.value for keyword in node.keywords if keyword.arg == "fact_id"), None)
            resolution = self._fact_id_resolution(fact_expr)
            fact_ids = resolution.get("ids")
            axis_expr = next((keyword.value for keyword in node.keywords if keyword.arg == "date_axis"), None)
            effective_expr = next(
                (keyword.value for keyword in node.keywords if keyword.arg == "effective_date"),
                None,
            )
            observation: dict[str, Any] = {
                "fact_id": None,
                "query_kind": query_kind,
                "query_family": self.query_family_by_symbol.get(query_kind),
                "file": self.file,
                "line": node.lineno,
                "column": node.col_offset,
                "enclosing_symbol": "::".join(self.symbol_stack) or "<module>",
                "date_axis": _date_axis_name(axis_expr),
                "date_axis_expression": ast.unparse(axis_expr) if axis_expr is not None else None,
                "effective_date_expression": ast.unparse(effective_expr) if effective_expr is not None else None,
                "source_kind": "ast_query_call",
                "fact_id_resolution": {key: value for key, value in resolution.items() if key != "ids"},
            }
            if isinstance(fact_expr, ast.Name) and self.function_scope_stack:
                function_name = self.function_scope_stack[-1]
                family_key = (function_name, fact_expr.id)
                if family_key in self.closed_world_values and (
                    query_family := self.query_family_by_symbol.get(query_kind)
                ):
                    allowed_families = self.closed_world_families.get(family_key, set())
                    if query_family not in allowed_families:
                        fact_ids = None
            if fact_ids and all(isinstance(fact_id, str) and fact_id for fact_id in fact_ids):
                for fact_id in fact_ids:
                    self.observations.append({**observation, "fact_id": fact_id})
            else:
                dynamic = self._dynamic_observation(
                    node=node,
                    observation=observation,
                    fact_expression=fact_expr,
                    resolution=resolution,
                )
                if dynamic is not None:
                    self.dynamic_observations.append(dynamic)
                else:
                    observation["blockers"] = ["consumer_query_fact_id_unresolved"]
                    self.malformed_observations.append(observation)
        self.generic_visit(node)


def _consumer_requirement_file() -> tuple[list[dict[str, Any]], list[str]]:
    """Read externally captured runtime probes without importing consumers.

    The AST pass is authoritative for source-visible query calls.  A failed
    startup can still prove a required fact through its stack trace before a
    concurrent source move lands.  Such probes are kept in a small, reviewed
    scratch manifest and remain blocking until the authored and bundled
    authority chains are both observable.
    """
    if not DEFAULT_CONSUMER_REQUIREMENTS.is_file():
        return [], []
    try:
        payload = json.loads(DEFAULT_CONSUMER_REQUIREMENTS.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return [], [f"{_display_path(DEFAULT_CONSUMER_REQUIREMENTS)}:{type(exc).__name__}"]
    raw_observations = payload.get("observations") if isinstance(payload, dict) else None
    if not isinstance(raw_observations, list):
        return [], [f"{_display_path(DEFAULT_CONSUMER_REQUIREMENTS)}:observations-missing"]
    observations: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, raw in enumerate(raw_observations):
        if not isinstance(raw, dict) or not isinstance(raw.get("fact_id"), str) or not raw["fact_id"].strip():
            errors.append(f"{_display_path(DEFAULT_CONSUMER_REQUIREMENTS)}:observations[{index}]:invalid")
            continue
        fact_id = raw["fact_id"].strip()
        callsites = raw.get("source_call_sites", [])
        if not isinstance(callsites, list):
            errors.append(f"{_display_path(DEFAULT_CONSUMER_REQUIREMENTS)}:{fact_id}:source_call_sites-invalid")
            continue
        normalized_callsites: list[dict[str, Any]] = []
        for callsite in callsites:
            if not isinstance(callsite, dict) or not isinstance(callsite.get("file"), str):
                errors.append(f"{_display_path(DEFAULT_CONSUMER_REQUIREMENTS)}:{fact_id}:callsite-invalid")
                continue
            item = dict(callsite)
            item["fact_id"] = fact_id
            item.setdefault("source_kind", "external_runtime_probe")
            normalized_callsites.append(item)
        observations.append(
            {
                "fact_id": fact_id,
                "query_kind": raw.get("query_kind", "runtime-governed-fact-resolution"),
                "date_axis": raw.get("date_axis"),
                "date_axis_expression": raw.get("date_axis_expression"),
                "effective_date_expression": raw.get("effective_date_expression"),
                "source_call_sites": normalized_callsites,
                "evidence": raw.get("evidence"),
                "source_kind": "external_runtime_probe",
            }
        )
    return observations, errors


def _authored_fact_index() -> tuple[dict[str, list[str]], list[str]]:
    """Index authored scalar/mapping/entity-set fact IDs by TOML path."""
    facts_root = AUTHORED_DATA_ROOT / "registry" / "aeat" / "facts"
    facts: dict[str, list[str]] = {}
    errors: list[str] = []
    if not facts_root.is_dir():
        return facts, [f"{_display_path(facts_root)}:missing"]
    try:
        import tomllib

        paths = sorted(facts_root.rglob("*.toml"), key=lambda path: path.as_posix())
    except OSError as exc:
        return facts, [f"{_display_path(facts_root)}:{type(exc).__name__}"]
    for path in paths:
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
            declaration = payload.get("fact") if isinstance(payload, dict) else None
            fact_id = declaration.get("fact_id") if isinstance(declaration, dict) else None
            if isinstance(fact_id, str) and fact_id.strip():
                relative = _display_path(path)
                facts.setdefault(fact_id.strip(), []).append(relative)
        except (OSError, UnicodeDecodeError, ValueError, TypeError) as exc:
            errors.append(f"{_display_path(path)}:{type(exc).__name__}")
    return facts, errors


def _compiled_fact_index(payload: Any) -> dict[str, dict[str, Any]]:
    """Extract the published fact catalogue without validating unrelated schema."""
    candidates: list[Any] = []
    if isinstance(payload, dict):
        candidates.extend(
            [
                payload.get("payload", {}).get("catalogues", {}).get("facts", {}).get("facts")
                if isinstance(payload.get("payload"), dict)
                else None,
                payload.get("catalogues", {}).get("facts", {}).get("facts")
                if isinstance(payload.get("catalogues"), dict)
                else None,
                payload.get("facts"),
            ]
        )
    for candidate in candidates:
        if isinstance(candidate, dict):
            return {str(key): value for key, value in candidate.items() if isinstance(value, dict)}
    return {}


_UNORDERED_FACT_WIRE_ARRAY_KEYS = frozenset(
    {
        "variants",
        "selectors",
        "legal_refs",
        "source_refs",
        "source_citations",
        "precedence_over",
        "entries",
        "entities",
        "outputs",
        "periods",
        "period_overrides",
        "required_text",
    }
)


def _normalise_fact_wire_value(value: Any, *, key: str | None = None) -> Any:
    """Normalize only schema collections whose order is not semantic."""
    if isinstance(value, dict):
        return {
            str(item_key): _normalise_fact_wire_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        normalized = [_normalise_fact_wire_value(item) for item in value]
        if key in _UNORDERED_FACT_WIRE_ARRAY_KEYS:
            return sorted(
                normalized,
                key=lambda item: canonical_json_bytes(item),
            )
        return normalized
    return value


def _canonical_fact_wire_digest(fact: Any) -> str:
    """Digest one fact through the existing facts compiler serialization."""
    from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
    from dev.registry.compiler.fact_providers import serialize_fact_catalogue

    provider_neutral = fact.model_copy(update={"provider_id": None})
    serialized = serialize_fact_catalogue(
        GovernedFactCatalogue(facts={provider_neutral.fact_id: provider_neutral}),
    )
    normalized = _normalise_fact_wire_value(json.loads(serialized))
    return sha256_hex(canonical_json_bytes(normalized))


def _authored_indexed_payload_staleness(
    artifact_status: str,
    indexed_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare shared authored facts with the typed indexed authority payload."""
    result: dict[str, Any] = {
        "status": "ok",
        "shared_fact_count": 0,
        "compared_fact_count": 0,
        "provider_only_compiled_count": 0,
        "stale": [],
        "errors": [],
    }
    if artifact_status != "ok":
        result["status"] = "blocked:bundled_authority_unavailable"
        result["errors"] = [f"bundled-authority-status:{artifact_status}"]
        return result
    try:
        from dev.registry.compiler.fact_providers import (
            AUTHORED_FACT_PROVIDER_ID,
            compile_authored_fact_catalogue,
        )

        authored_catalogue = compile_authored_fact_catalogue(AUTHORED_DATA_ROOT / "registry" / "aeat")
        authored_facts = authored_catalogue.facts
        shared_ids = sorted(set(authored_facts) & set(indexed_facts))
        provider_only_ids = {
            fact_id
            for fact_id, fact in indexed_facts.items()
            if (
                fact_id not in authored_facts
                and fact.provider_id is not None
                and str(fact.provider_id) != AUTHORED_FACT_PROVIDER_ID
                and all(variant.ownership.value == "generated" for variant in fact.variants)
            )
        }
        result["shared_fact_count"] = len(shared_ids)
        result["provider_only_compiled_count"] = len(provider_only_ids)
        stale: list[dict[str, Any]] = []
        for fact_id in shared_ids:
            authored_digest = _canonical_fact_wire_digest(authored_facts[fact_id])
            bundled_digest = _canonical_fact_wire_digest(indexed_facts[fact_id])
            result["compared_fact_count"] += 1
            if authored_digest == bundled_digest:
                continue
            stale.append(
                {
                    "fact_id": fact_id,
                    "blocker": "published_fact_payload_stale",
                    "authored_payload_sha256": authored_digest,
                    "bundled_payload_sha256": bundled_digest,
                },
            )
        result["stale"] = stale
    except Exception as exc:
        result["status"] = f"error:{type(exc).__name__}"
        result["errors"] = [f"authored-bundled-payload-comparison:{type(exc).__name__}:{exc}"]
    return result


def _compiled_provider_id(compiled_fact: Any) -> str | None:
    """Return provider provenance only for a wholly generated compiled fact.

    Directly authored facts carry their own provider identity and authored
    variants.  A compiled fact is provider-owned for accounting only when the
    authority payload supplies a non-empty provider identity and every variant
    is explicitly generated.  This keeps provider projections out of the
    authored-file denominator without maintaining a fact-ID allowlist.
    """
    if not isinstance(compiled_fact, dict):
        return None
    provider_id = compiled_fact.get("provider_id")
    variants = compiled_fact.get("variants")
    if not isinstance(provider_id, str) or not provider_id.strip():
        return None
    if not isinstance(variants, list) or not variants:
        return None
    if any(not isinstance(variant, dict) or variant.get("ownership") != "generated" for variant in variants):
        return None
    return provider_id.strip()


def _consumer_fact_scan(
    manifest: dict[str, Any],
    universe_scan: dict[str, Any] | None = None,
    *,
    source_paths: list[str] | None = None,
    authority_probe: tuple[Any, str] | None = None,
) -> dict[str, Any]:
    """Reconcile every named consumer fact through the authority proof chain."""
    callsites_by_fact: dict[str, list[dict[str, Any]]] = {}
    malformed_callsites: list[dict[str, Any]] = []
    dynamic_callsites: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    if source_paths is None:
        source_paths = list((universe_scan or {}).get("paths", []))
    if authority_probe is None:
        artifact_payload, artifact_status, _metadata = _load_indexed_fact_authority(BUNDLED_AUTHORITY_DESCRIPTOR)
    else:
        artifact_payload, artifact_status = authority_probe
    compiled = _compiled_fact_index(artifact_payload) if artifact_status == "ok" else {}
    helper_names = {
        str(spec["candidate_helper"])
        for spec in DYNAMIC_SEAM_SPECS
        if spec.get("candidate_mode") == "helper_calls" and isinstance(spec.get("candidate_helper"), str)
    }
    helper_scan_paths = set(source_paths)
    if helper_names:
        # The facts-only query inventory intentionally narrows to modules that
        # contain a query constructor.  A generic helper can have its concrete
        # caller in a thin domain adapter which only invokes the helper, so
        # include the non-test Python universe for this caller-coverage proof.
        try:
            for path in SOURCE_ROOT.rglob("*.py"):
                relative = path.resolve().relative_to(REPO_ROOT).as_posix()
                if not _fd_excluded(PurePosixPath(relative)):
                    helper_scan_paths.add(relative)
        except OSError:
            pass
    helper_call_candidates = _collect_helper_call_candidates(sorted(helper_scan_paths), helper_names)
    for relative in source_paths:
        path = REPO_ROOT / Path(*PurePosixPath(relative).parts)
        try:
            text = _decode_python_source(path.read_bytes())
            tree = ast.parse(text, filename=relative)
        except (OSError, SyntaxError, LookupError, UnicodeDecodeError, ValueError, TypeError) as exc:
            parse_errors.append(f"{relative}:{type(exc).__name__}")
            continue
        visitor = _ConsumerQueryVisitor(
            file=relative,
            constants=_module_string_constants(tree),
            tree=tree,
            helper_call_candidates=helper_call_candidates,
            compiled_fact_index=compiled,
        )
        visitor.visit(tree)
        for observation in visitor.observations:
            callsites_by_fact.setdefault(observation["fact_id"], []).append(observation)
        malformed_callsites.extend(visitor.malformed_observations)
        dynamic_callsites.extend(visitor.dynamic_observations)

    external_observations, external_errors = _consumer_requirement_file()
    for external in external_observations:
        fact_id = external["fact_id"]
        for callsite in external["source_call_sites"]:
            observation = dict(callsite)
            observation.setdefault("query_kind", external.get("query_kind"))
            observation.setdefault(
                "query_family",
                QUERY_FAMILY_BY_SYMBOL.get(str(external.get("query_kind", ""))),
            )
            observation.setdefault("date_axis", external.get("date_axis"))
            observation.setdefault("date_axis_expression", external.get("date_axis_expression"))
            observation.setdefault("effective_date_expression", external.get("effective_date_expression"))
            observation.setdefault("source_kind", "external_runtime_probe")
            callsites_by_fact.setdefault(fact_id, []).append(observation)

    authored, authored_errors = _authored_fact_index()
    dynamic_seams: list[dict[str, Any]] = []
    dynamic_blockers: list[dict[str, Any]] = []
    for dynamic in dynamic_callsites:
        candidate_ids = tuple(
            fact_id for fact_id in dynamic.get("candidate_fact_ids", ()) if isinstance(fact_id, str) and fact_id.strip()
        )
        authored_missing = sorted(set(candidate_ids) - set(authored))
        compiled_missing = sorted(set(candidate_ids) - set(compiled))
        dynamic["candidate_fact_ids"] = list(candidate_ids)
        dynamic["candidate_authored_presence"] = {fact_id: bool(authored.get(fact_id)) for fact_id in candidate_ids}
        dynamic["candidate_bundled_presence"] = {fact_id: fact_id in compiled for fact_id in candidate_ids}
        dynamic["dynamic_seam_proof"] = {
            **dict(dynamic.get("dynamic_seam_proof") or {}),
            "candidate_authored_presence": not authored_missing,
            "candidate_bundled_presence": not compiled_missing,
            "candidate_coverage": bool(candidate_ids) and not authored_missing and not compiled_missing,
            "missing_authored_fact_ids": authored_missing,
            "missing_bundled_fact_ids": compiled_missing,
        }
        blockers = list(dynamic.get("blockers") or [])
        if authored_missing:
            blockers.append("dynamic_candidate_authored_fact_missing")
        if compiled_missing:
            blockers.append("dynamic_candidate_bundled_fact_missing")
        dynamic["blockers"] = list(dict.fromkeys(blockers))
        dynamic["blocking"] = bool(dynamic["blockers"])
        dynamic["consumer_seam_loadability"] = (
            "typed_dynamic_seam" if not dynamic["blocking"] else "blocked:" + ",".join(dynamic["blockers"])
        )
        dynamic["source_call_sites"] = [
            {
                key: value
                for key, value in dynamic.items()
                if key
                in {
                    "file",
                    "line",
                    "column",
                    "enclosing_symbol",
                    "query_kind",
                    "query_family",
                    "date_axis",
                    "date_axis_expression",
                    "effective_date_expression",
                    "source_kind",
                }
            }
        ]
        dynamic["associated_row_ids"] = []
        dynamic_seams.append(dynamic)
        if dynamic["blocking"]:
            dynamic_blockers.append(dynamic)
    row_files: dict[str, set[str]] = {}
    for row in manifest.get("candidates", []):
        paths: set[str] = set()
        for evidence in row.get("evidence", ()):
            if isinstance(evidence, dict) and isinstance(evidence.get("file"), str):
                paths.add(evidence["file"].replace("\\", "/"))
        closure = row.get("closure")
        if isinstance(closure, dict):
            placement = closure.get("placement")
            if isinstance(placement, dict) and isinstance(placement.get("source_file"), str):
                paths.add(placement["source_file"].replace("\\", "/"))
            for source_hash in closure.get("source_hashes", ()):
                if isinstance(source_hash, dict) and isinstance(source_hash.get("path"), str):
                    paths.add(source_hash["path"].replace("\\", "/"))
        row_files[row["id"]] = paths

    observations: list[dict[str, Any]] = []
    for fact_id in sorted(callsites_by_fact):
        callsites = sorted(
            callsites_by_fact[fact_id],
            key=lambda item: (
                str(item.get("file", "")),
                int(item.get("line", 0) or 0),
                str(item.get("enclosing_symbol", "")),
                str(item.get("query_kind", "")),
            ),
        )
        deduped_callsites: list[dict[str, Any]] = []
        seen_callsites: set[str] = set()
        for callsite in callsites:
            identity = json.dumps(callsite, ensure_ascii=False, sort_keys=True, default=str)
            if identity not in seen_callsites:
                seen_callsites.add(identity)
                deduped_callsites.append(callsite)
        authored_paths = sorted(authored.get(fact_id, []))
        compiled_fact = compiled.get(fact_id)
        compiled_provider_id = _compiled_provider_id(compiled_fact)
        provider_owned_compiled = compiled_provider_id is not None
        variants = compiled_fact.get("variants", []) if isinstance(compiled_fact, dict) else []
        compiled_axes = {
            str(variant.get("date_axis"))
            for variant in variants
            if isinstance(variant, dict) and isinstance(variant.get("date_axis"), str)
        }
        requested_axes = {
            str(callsite.get("date_axis"))
            for callsite in deduped_callsites
            if isinstance(callsite.get("date_axis"), str) and callsite.get("date_axis")
        }
        axis_declared = bool(deduped_callsites) and all(
            isinstance(callsite.get("date_axis"), str) and bool(callsite.get("date_axis"))
            for callsite in deduped_callsites
        )
        axis_compatible = bool(compiled_fact is not None and requested_axes <= compiled_axes)
        axis_resolved = axis_declared and axis_compatible
        query_families = {
            str(callsite.get("query_family"))
            for callsite in deduped_callsites
            if isinstance(callsite.get("query_family"), str)
        }
        compiled_family = compiled_fact.get("family") if isinstance(compiled_fact, dict) else None
        family_compatible = bool(
            compiled_fact is not None and query_families and query_families == {str(compiled_family)}
        )
        associated_row_ids = sorted(
            row_id
            for row_id, paths in row_files.items()
            if any(callsite.get("file") in paths for callsite in deduped_callsites)
        )
        blockers: list[str] = []
        if not authored_paths and not provider_owned_compiled:
            blockers.append("authored_fact_missing")
        if compiled_fact is None:
            blockers.append("bundled_authority_fact_missing")
        # A missing bundled fact already has its own named blocker. Do not
        # mislabel a statically recognized axis as absent merely because the
        # compiled authority is not present yet. A genuinely missing axis, or
        # an axis incompatible with an available compiled variant, remains
        # blocking.
        if not axis_declared or (compiled_fact is not None and not axis_compatible):
            blockers.append("query_date_axis_unresolved")
        if compiled_fact is not None and not family_compatible:
            blockers.append("query_family_unresolved")
        if any(
            callsite.get("source_kind") == "ast_query_call" and not callsite.get("effective_date_expression")
            for callsite in deduped_callsites
        ):
            blockers.append("query_effective_date_unresolved")
        observation = {
            "fact_id": fact_id,
            "source_call_sites": deduped_callsites,
            "authored_presence": bool(authored_paths),
            "authored_paths": authored_paths,
            "bundled_authority_presence": compiled_fact is not None,
            "compiled_provider_id": compiled_provider_id,
            "provider_owned_compiled": provider_owned_compiled,
            "bundled_authority_artifact": _display_path(BUNDLED_AUTHORITY_DESCRIPTOR),
            "bundled_authority_artifact_status": artifact_status,
            "compiled_variant_date_axes": sorted(compiled_axes),
            "compiled_family": compiled_family,
            "requested_query_families": sorted(query_families),
            "query_family_resolved": family_compatible,
            "requested_query_date_axes": sorted(requested_axes),
            "query_date_axis_recognized": axis_declared,
            "query_date_axis_resolved": axis_resolved,
            "proof_chain": {
                "authored_presence": bool(authored_paths),
                "bundled_authority_presence": compiled_fact is not None,
                "provider_owned_compiled": provider_owned_compiled,
                "query_date_axis_resolution": axis_resolved,
                "consumer_seam_loadability": not blockers,
            },
            "consumer_seam_loadability": ("query_shape_resolved" if not blockers else "blocked:" + ",".join(blockers)),
            "associated_row_ids": associated_row_ids,
            "blockers": blockers,
            "blocking": bool(blockers),
        }
        observations.append(observation)

    malformed_observations = sorted(
        malformed_callsites,
        key=lambda item: (
            str(item.get("file", "")),
            int(item.get("line", 0) or 0),
            str(item.get("query_kind", "")),
        ),
    )
    malformed_blockers = [
        {
            "fact_id": None,
            "source_call_sites": [item],
            "authored_presence": False,
            "authored_paths": [],
            "bundled_authority_presence": False,
            "compiled_provider_id": None,
            "provider_owned_compiled": False,
            "bundled_authority_artifact": _display_path(BUNDLED_AUTHORITY_DESCRIPTOR),
            "bundled_authority_artifact_status": artifact_status,
            "compiled_variant_date_axes": [],
            "requested_query_date_axes": [],
            "query_date_axis_recognized": bool(item.get("date_axis")),
            "query_date_axis_resolved": False,
            "proof_chain": {
                "authored_presence": False,
                "bundled_authority_presence": False,
                "provider_owned_compiled": False,
                "query_date_axis_resolution": False,
                "consumer_seam_loadability": False,
            },
            "consumer_seam_loadability": "blocked:consumer_query_fact_id_unresolved",
            "associated_row_ids": [],
            "blockers": ["consumer_query_fact_id_unresolved"],
            "blocking": True,
        }
        for item in malformed_observations
    ]
    blockers = [item for item in observations if item["blocking"]] + malformed_blockers + dynamic_blockers
    return {
        "observations": observations,
        "blockers": blockers,
        "malformed_callsites": malformed_observations,
        "dynamic_seams": dynamic_seams,
        "errors": sorted(set(parse_errors + external_errors + authored_errors)),
        "counts": {
            "consumer_fact_required_count": len(observations),
            "consumer_fact_callsite_count": sum(len(item["source_call_sites"]) for item in observations),
            "consumer_fact_authored_present_count": sum(item["authored_presence"] for item in observations),
            "consumer_fact_compiled_present_count": sum(item["bundled_authority_presence"] for item in observations),
            "consumer_fact_provider_owned_count": sum(item["provider_owned_compiled"] for item in observations),
            "consumer_fact_resolved_count": sum(not item["blocking"] for item in observations),
            "consumer_fact_blocker_count": len(blockers),
            "consumer_fact_error_count": len(consumer_errors := (parse_errors + external_errors + authored_errors)),
            "consumer_query_malformed_count": len(malformed_observations),
            "consumer_dynamic_seam_count": len(dynamic_seams),
            "consumer_dynamic_seam_proven_count": sum(not item["blocking"] for item in dynamic_seams),
            "consumer_dynamic_seam_blocker_count": len(dynamic_blockers),
            "consumer_source_path_count": len(source_paths),
        },
        "associated_row_ids": sorted({row_id for item in blockers for row_id in item["associated_row_ids"]}),
    }


def _facts_only_signal() -> dict[str, Any]:
    """Measure authored-to-consumer fact publication without the full campaign scan."""
    source_inventory = _consumer_source_paths()
    source_paths = source_inventory["paths"]
    artifact_payload, artifact_status, artifact_metadata = _load_indexed_fact_authority(BUNDLED_AUTHORITY_DESCRIPTOR)
    consumer_scan = _consumer_fact_scan(
        {},
        source_paths=source_paths,
        authority_probe=(artifact_payload, artifact_status),
    )
    indexed_facts = artifact_payload.get("facts", {}) if isinstance(artifact_payload, dict) else {}
    bundled_probe = {
        "status": artifact_status,
        "fact_count": len(indexed_facts),
        "identity_digest": artifact_metadata["identity_digest"],
        "error": artifact_metadata.get("error"),
    }
    if bundled_probe["status"] != "ok":
        for observation in consumer_scan["observations"]:
            if "bundled_authority_load_error" not in observation["blockers"]:
                observation["blockers"].append("bundled_authority_load_error")
            observation["blocking"] = True
            observation["consumer_seam_loadability"] = "blocked:" + ",".join(observation["blockers"])
            observation["proof_chain"]["consumer_seam_loadability"] = False
        consumer_scan["blockers"] = [item for item in consumer_scan["observations"] if item["blocking"]] + [
            item for item in consumer_scan["blockers"] if item.get("fact_id") is None
        ]

    authored, authored_errors = _authored_fact_index()
    compiled = _compiled_fact_index(artifact_payload) if artifact_status == "ok" else {}
    payload_staleness = _authored_indexed_payload_staleness(artifact_status, indexed_facts)
    required_ids = sorted({item["fact_id"] for item in consumer_scan["observations"]})
    authored_ids = sorted(authored)
    compiled_ids = sorted(compiled)
    provider_owned_compiled_by_provider: dict[str, list[str]] = {}
    for fact_id in compiled_ids:
        provider_id = _compiled_provider_id(compiled[fact_id])
        if provider_id is not None:
            provider_owned_compiled_by_provider.setdefault(provider_id, []).append(fact_id)
    provider_owned_compiled_ids = sorted(
        fact_id for fact_id in compiled_ids if _compiled_provider_id(compiled[fact_id]) is not None
    )
    provider_owned_required_ids = sorted(set(required_ids) & set(provider_owned_compiled_ids))
    compiled_unaccounted_ids = sorted(set(compiled_ids) - set(authored_ids) - set(provider_owned_compiled_ids))
    authored_uncompiled_ids = sorted(set(authored_ids) - set(compiled_ids))
    resolved_ids = sorted(item["fact_id"] for item in consumer_scan["observations"] if not item["blocking"])
    authored_missing = sorted(set(required_ids) - set(authored) - set(provider_owned_required_ids))
    compiled_missing = sorted(set(required_ids) - set(compiled))
    axis_blockers = [
        item for item in consumer_scan["blockers"] if "query_date_axis_unresolved" in item.get("blockers", [])
    ]
    authority_errors = (
        sum(status != "ok" for status in (artifact_status, bundled_probe["status"]))
        + len(authored_errors)
        + len(payload_staleness["errors"])
    )
    publication_blockers = list(consumer_scan["blockers"])
    publication_blockers.extend(
        {
            "fact_id": item["fact_id"],
            "source_call_sites": [],
            "blockers": ["published_fact_payload_stale"],
            "authored_payload_sha256": item["authored_payload_sha256"],
            "bundled_payload_sha256": item["bundled_payload_sha256"],
            "blocking": True,
        }
        for item in payload_staleness["stale"]
    )
    publication_blockers.extend(
        {
            "fact_id": None,
            "source_call_sites": [],
            "blockers": ["authored_bundled_payload_comparison_error"],
            "errors": payload_staleness["errors"],
            "blocking": True,
        }
        for _ in payload_staleness["errors"]
    )
    publication_blockers.extend(
        {
            "fact_id": fact_id,
            "source_call_sites": [],
            "blockers": ["authored_fact_missing"],
        }
        for fact_id in authored_missing
        if not any(item.get("fact_id") == fact_id for item in publication_blockers)
    )
    publication_blockers.extend(
        {
            "fact_id": fact_id,
            "source_call_sites": [],
            "blockers": ["bundled_authority_fact_missing"],
        }
        for fact_id in compiled_missing
        if not any(item.get("fact_id") == fact_id for item in publication_blockers)
    )
    if artifact_status == "ok":
        publication_blockers.extend(
            {
                "fact_id": fact_id,
                "source_call_sites": [],
                "blockers": ["compiled_fact_without_authored_or_provider_provenance"],
            }
            for fact_id in compiled_unaccounted_ids
            if not any(item.get("fact_id") == fact_id for item in publication_blockers)
        )
        publication_blockers.extend(
            {
                "fact_id": fact_id,
                "source_call_sites": [],
                "blockers": ["authored_fact_not_in_bundled_authority"],
            }
            for fact_id in authored_uncompiled_ids
            if not any(item.get("fact_id") == fact_id for item in publication_blockers)
        )
    counts = {
        "required_fact_count": len(required_ids),
        "authored_fact_count": len(authored_ids),
        "compiled_fact_count": len(compiled_ids),
        "resolved_fact_count": len(resolved_ids),
        "required_authored_present_count": len(set(required_ids) & set(authored)),
        "required_provider_owned_present_count": len(provider_owned_required_ids),
        "required_authored_or_provider_present_count": len(
            set(required_ids) & (set(authored) | set(provider_owned_compiled_ids))
        ),
        "required_compiled_present_count": len(set(required_ids) & set(compiled)),
        "required_resolved_count": len(resolved_ids),
        "authored_fact_missing_count": len(authored_missing),
        "compiled_fact_missing_count": len(compiled_missing),
        "query_date_axis_unresolved_count": len(axis_blockers),
        "consumer_fact_blocker_count": len(publication_blockers),
        "consumer_fact_error_count": len(consumer_scan["errors"]),
        "consumer_query_malformed_count": consumer_scan["counts"]["consumer_query_malformed_count"],
        "authority_error_count": authority_errors,
        "facts_publication_blocker_count": len(publication_blockers) + authority_errors,
        "published_fact_payload_stale_count": len(payload_staleness["stale"]),
        "authored_bundled_payload_shared_count": payload_staleness["shared_fact_count"],
        "authored_bundled_payload_compared_count": payload_staleness["compared_fact_count"],
        "authored_bundled_payload_provider_only_count": payload_staleness["provider_only_compiled_count"],
        "authored_bundled_payload_error_count": len(payload_staleness["errors"]),
        "provider_owned_compiled_fact_count": len(provider_owned_compiled_ids),
        "compiled_unaccounted_count": len(compiled_unaccounted_ids),
        "authored_uncompiled_count": len(authored_uncompiled_ids),
        "fact_accounting_error_count": len(compiled_unaccounted_ids) + len(authored_uncompiled_ids),
        "fact_count_equality": not compiled_unaccounted_ids and not authored_uncompiled_ids,
    }
    return {
        "schema": "cadrumo.fact-relocation.facts-publication-signal",
        "mode": "facts-only",
        "artifact": artifact_metadata,
        "bundled_authority": bundled_probe,
        "source_inventory": source_inventory,
        "fact_ids": {
            "required": required_ids,
            "authored": authored_ids,
            "compiled": compiled_ids,
            "provider_owned_compiled": provider_owned_compiled_ids,
            "compiled_unaccounted": compiled_unaccounted_ids,
            "authored_uncompiled": authored_uncompiled_ids,
            "resolved": resolved_ids,
            "authored_missing": authored_missing,
            "compiled_missing": compiled_missing,
        },
        "consumer_fact_observations": consumer_scan["observations"],
        "consumer_dynamic_seams": consumer_scan["dynamic_seams"],
        "consumer_fact_blockers": publication_blockers,
        "consumer_fact_scan_errors": sorted(set(consumer_scan["errors"] + authored_errors)),
        "payload_staleness": payload_staleness,
        "provider_ownership": {
            "compiled_by_provider": {
                provider_id: sorted(fact_ids)
                for provider_id, fact_ids in sorted(provider_owned_compiled_by_provider.items())
            },
            "required_provider_owned_ids": provider_owned_required_ids,
        },
        "counts": counts,
        "authority_digest_status": {
            "descriptor_sha256": artifact_metadata["descriptor_sha256"],
            "digest_verified": artifact_status == "ok",
            "bundled_loader_status": bundled_probe["status"],
            "identity_digest": bundled_probe["identity_digest"],
        },
        "exit_code": 0 if counts["facts_publication_blocker_count"] == 0 else 1,
    }


def _facts_only_human(signal: dict[str, Any]) -> str:
    """Render the bounded facts-publication measurement for a human operator."""
    counts = signal["counts"]
    lines = [
        "facts-only publication signal",
        "=============================",
        (
            "facts: "
            f"required={counts['required_fact_count']}, "
            f"authored={counts['authored_fact_count']}, "
            f"compiled={counts['compiled_fact_count']}, "
            f"resolved={counts['resolved_fact_count']}"
        ),
        (
            "blockers: "
            f"authored_missing={counts['authored_fact_missing_count']}, "
            f"compiled_missing={counts['compiled_fact_missing_count']}, "
            f"date_axis={counts['query_date_axis_unresolved_count']}, "
            f"authority_errors={counts['authority_error_count']}, "
            f"payload_stale={counts['published_fact_payload_stale_count']}, "
            f"publication={counts['facts_publication_blocker_count']}"
        ),
        (
            "fact ownership: "
            f"provider_owned_compiled={counts['provider_owned_compiled_fact_count']}, "
            f"compiled_unaccounted={counts['compiled_unaccounted_count']}, "
            f"authored_uncompiled={counts['authored_uncompiled_count']}"
        ),
        f"artifact: {signal['artifact']['status']}",
        f"bundled loader: {signal['bundled_authority']['status']}",
        "consumer fact blockers:",
    ]
    dynamic_seams = signal.get("consumer_dynamic_seams", [])
    if dynamic_seams:
        lines.append(
            "dynamic seams: "
            f"{sum(not item.get('blocking', True) for item in dynamic_seams)} proven / "
            f"{len(dynamic_seams)} observed"
        )
    blockers = signal["consumer_fact_blockers"]
    if not blockers:
        lines.append("(none)")
    else:
        for blocker in blockers:
            callsites = (
                ", ".join(
                    f"{item.get('file')}:{item.get('line', '?')}" for item in blocker.get("source_call_sites", [])
                )
                or "(no callsite)"
            )
            lines.append(
                f"- {blocker.get('fact_id') or '<malformed-query>'}: "
                f"{', '.join(blocker.get('blockers', []))}; source={callsites}"
            )
    lines.append(f"result exit code: {signal['exit_code']}")
    return "\n".join(lines)


def _candidate_payload(candidate: GovernedLiteralCandidate) -> dict[str, Any]:
    """Return the stable public representation of one live discovery hit."""
    identity = {
        "path": candidate.path,
        "enclosing_symbol": candidate.enclosing_symbol,
        "semantic_role": candidate.semantic_role,
        "kind": candidate.kind.value,
        "excerpt": candidate.excerpt,
    }
    candidate_id = (
        "fact-discovery:"
        + hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    )
    return {"candidate_id": candidate_id, "line": candidate.line, **identity}


_ENUM_DIRECT_BASE_NAMES = frozenset({"Enum", "StrEnum"})
_ENUM_NEGATIVE_CLASS_TOKENS = frozenset(
    {
        "availability",
        "binding",
        "cohort",
        "confidence",
        "diagnostic",
        "disposition",
        "error",
        "evidence",
        "failure",
        "fact",
        "field",
        "grounding",
        "health",
        "issue",
        "lifecycle",
        "mismatch",
        "module",
        "outcome",
        "phase",
        "precondition",
        "provenance",
        "reason",
        "readiness",
        "review",
        "severity",
        "stage",
        "state",
        "status",
        "surface",
        "workflow",
    }
)
_ENUM_NEGATIVE_CONTEXT_TOKENS = frozenset({"ledger", "manual", "provenance", "residual"})
_ENUM_LEGAL_CONTEXT_TOKENS = frozenset({"article", "ley", "lis", "lirpf", "liva", "rd", "rdl"})
_ENUM_MODEL_RE = re.compile(r"^m[0-9]{3}$", re.IGNORECASE)


def _enum_identifier_tokens(value: str) -> frozenset[str]:
    """Split snake/camel/model identifiers into conservative context tokens."""
    expanded = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", expanded)
    expanded = re.sub(r"[^A-Za-z0-9]+", "_", expanded)
    return frozenset(part.casefold() for part in expanded.split("_") if part)


def _enum_base_aliases(tree: ast.Module) -> tuple[frozenset[str], frozenset[str]]:
    """Return direct enum names and aliases for the :mod:`enum` module."""
    direct = set(_ENUM_DIRECT_BASE_NAMES)
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "enum":
            for imported in node.names:
                if imported.name in _ENUM_DIRECT_BASE_NAMES:
                    direct.add(imported.asname or imported.name)
        elif isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name == "enum":
                    modules.add(imported.asname or "enum")
    return frozenset(direct), frozenset(modules)


def _enum_members(node: ast.ClassDef) -> list[dict[str, str]]:
    """Collect direct finite enum member declarations without evaluating code."""
    members: list[dict[str, str]] = []
    for child in node.body:
        if isinstance(child, ast.Assign):
            targets = child.targets
            value = child.value
        elif isinstance(child, ast.AnnAssign):
            targets = [child.target]
            value = child.value
        else:
            continue
        if value is None:
            continue
        for target in targets:
            if not isinstance(target, ast.Name) or target.id.startswith("_"):
                continue
            members.append(
                {
                    "name": target.id,
                    "value": ast.unparse(value),
                    "source_span": _node_span(child),
                }
            )
    return members


def _enum_is_direct_base(base: ast.expr, direct_names: frozenset[str], module_names: frozenset[str]) -> bool:
    if isinstance(base, ast.Name):
        return base.id in direct_names
    return (
        isinstance(base, ast.Attribute)
        and isinstance(base.value, ast.Name)
        and base.value.id in module_names
        and base.attr in _ENUM_DIRECT_BASE_NAMES
    )


def _enum_is_tax_catalogue(
    *,
    relative: str,
    node: ast.ClassDef,
    members: Sequence[dict[str, str]],
) -> tuple[bool, str | None, frozenset[str]]:
    """Recognize tax vocabulary enums while excluding workflow/provenance types.

    The rule requires a domain anchor in class/member names or values. A
    directory or filename alone cannot promote a generic enum. Model-shaped
    tokens are accepted only with an adjacent tax vocabulary token, while legal
    article markers are accepted independently.
    """
    class_tokens = _enum_identifier_tokens(node.name)
    member_text = " ".join(f"{member['name']} {member['value']}" for member in members)
    member_tokens = _enum_identifier_tokens(member_text)
    path_tokens = _enum_identifier_tokens(relative)
    all_tokens = class_tokens | member_tokens | path_tokens
    class_and_member_tokens = class_tokens | member_tokens

    if class_tokens & _ENUM_NEGATIVE_CLASS_TOKENS:
        return False, None, all_tokens
    if class_and_member_tokens & _ENUM_NEGATIVE_CONTEXT_TOKENS:
        return False, None, all_tokens
    if "rate" in class_tokens and "verified" in class_and_member_tokens:
        return False, None, all_tokens

    def is_numbered_legal_marker(value: str) -> bool:
        expanded = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
        expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", expanded)
        expanded = re.sub(r"[^A-Za-z0-9]+", "_", expanded).casefold()
        return bool(re.search(r"(?:^|_)(?:art|article|articulo|ley|rdl?|liva|lirpf|lis)_?\d+", expanded))

    class_has_numbered_legal_marker = is_numbered_legal_marker(node.name)
    member_has_numbered_legal_marker = is_numbered_legal_marker(member_text)
    has_iva_anchor = "iva" in class_tokens or "iva" in path_tokens
    has_irnr_anchor = "irnr" in class_tokens or "irnr" in path_tokens
    has_withholding_anchor = bool(class_tokens & {"withholding", "retencion", "retenciones"})
    has_invoice_iva_anchor = "invoice" in class_tokens and bool(
        class_and_member_tokens & {"cash", "charge", "exempt", "exemption", "regime", "regimen", "reverse"}
    )
    has_model_anchor = any(_ENUM_MODEL_RE.fullmatch(token) for token in class_tokens) or (
        "modelo" in class_tokens and any(token.isdigit() for token in class_tokens)
    )
    has_legal_marker = (
        bool(class_tokens & _ENUM_LEGAL_CONTEXT_TOKENS)
        or class_has_numbered_legal_marker
        or (member_has_numbered_legal_marker and (has_iva_anchor or has_irnr_anchor or has_model_anchor))
    )
    has_iva_vocabulary = has_iva_anchor and bool(
        class_and_member_tokens
        & {"cash", "category", "exempt", "exemption", "rate", "regime", "regimen", "scheme", "service"}
    )
    has_withholding_vocabulary = has_withholding_anchor and bool(
        class_and_member_tokens
        & {"category", "clave", "code", "income", "kind", "rate", "regime", "regimen", "scheme", "tipo"}
    )
    has_irnr_income_vocabulary = has_irnr_anchor and bool(class_and_member_tokens & {"code", "income", "renta", "tipo"})
    has_model_tax_vocabulary = has_model_anchor and bool(
        class_and_member_tokens
        & {"category", "code", "income", "rate", "regime", "regimen", "scheme", "tipo", "territory"}
    )

    if has_legal_marker:
        family = "legal_article_identifiers"
    elif has_iva_vocabulary or has_invoice_iva_anchor or ("iva" in path_tokens and "regime" in class_and_member_tokens):
        family = "iva_tax_vocabulary"
    elif has_withholding_vocabulary:
        family = "withholding_scheme_vocabulary"
    elif has_irnr_income_vocabulary:
        family = "irnr_income_vocabulary"
    elif has_model_tax_vocabulary:
        family = "modelo_tax_vocabulary"
    else:
        return False, None, all_tokens
    return True, family, all_tokens


def _discover_tax_enum_catalogues(source_root: Path = SOURCE_ROOT) -> list[dict[str, Any]]:
    """Return one stable discovery candidate per tax-vocabulary enum class."""
    catalogues: list[dict[str, Any]] = []
    for path in sorted(source_root.rglob("*.py")):
        if any(part.casefold() in {"test", "tests", "__pycache__"} for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError, TypeError):
            continue
        relative = path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else path.as_posix()
        direct_names, module_names = _enum_base_aliases(tree)

        def visit(node: ast.AST, scope: str) -> None:
            if not isinstance(node, ast.ClassDef):
                for child in ast.iter_child_nodes(node):
                    visit(child, scope)
                return
            members = _enum_members(node)
            if members and any(_enum_is_direct_base(base, direct_names, module_names) for base in node.bases):
                is_tax, family, tokens = _enum_is_tax_catalogue(
                    relative=relative,
                    node=node,
                    members=members,
                )
                if is_tax and family is not None:
                    symbol = f"{scope}::{node.name}" if scope != "module" else node.name
                    source_span = _node_span(node)
                    anchor_scope = scope if scope == "module" else f"class:{scope}"
                    source_anchor = "ast:" + "|".join(
                        ("v1", relative, anchor_scope, node.name, "ClassDef", source_span)
                    )
                    identity = {
                        "path": relative,
                        "enclosing_symbol": symbol,
                        "semantic_role": "tax_enum_catalogue",
                        "kind": "mapping",
                    }
                    candidate_id = (
                        "fact-discovery:enum-catalogue:" + hashlib.sha256(canonical_json_bytes(identity)).hexdigest()
                    )
                    catalogues.append(
                        {
                            "candidate_id": candidate_id,
                            "line": node.lineno,
                            "path": relative,
                            "enclosing_symbol": symbol,
                            "semantic_role": "tax_enum_catalogue",
                            "kind": "mapping",
                            "excerpt": f"{node.name} ({len(members)} enum members)",
                            "confidence": "high",
                            "enum_catalogue": True,
                            "catalogue_family": family,
                            "member_count": len(members),
                            "members": members,
                            "base_classes": [ast.unparse(base) for base in node.bases],
                            "source_anchor": source_anchor,
                            "context_tokens": sorted(tokens),
                        }
                    )
            for child in node.body:
                if isinstance(child, ast.ClassDef):
                    visit(child, f"{scope}::{node.name}" if scope != "module" else node.name)

        for child in tree.body:
            if isinstance(child, ast.ClassDef):
                visit(child, "module")
    return sorted(catalogues, key=lambda item: (item["path"], item["line"], item["enclosing_symbol"]))


def _discovery_scan(manifest: dict[str, Any]) -> dict[str, Any]:
    """Discover live governed literals outside the hand-curated ledger boundary.

    A ledger row can account for the module it explicitly observed. It does not
    account for candidates in newly added modules. This deliberately conservative
    comparison turns the existing broad discovery report into a review queue
    without pretending that its heuristic hits are established legal facts.
    """
    relocations = _source_relocations(manifest.get("source_relocations"))
    ledger_paths: set[str] = set()
    for row in manifest["candidates"]:
        for evidence in row.get("evidence", ()):
            if isinstance(evidence, dict) and isinstance(evidence.get("file"), str):
                declared = _source_path(evidence["file"], label=f"{row['id']}: discovery evidence")[1]
                ledger_paths.add(_relocated_source_relative(declared, relocations))
        closure = row.get("closure")
        if not isinstance(closure, dict):
            continue
        placement = closure.get("placement")
        if isinstance(placement, dict) and isinstance(placement.get("source_file"), str):
            declared = _source_path(placement["source_file"], label=f"{row['id']}: discovery placement")[1]
            ledger_paths.add(_relocated_source_relative(declared, relocations))
        for source_hash in closure.get("source_hashes", ()):
            if isinstance(source_hash, dict) and isinstance(source_hash.get("path"), str):
                declared = _source_path(source_hash["path"], label=f"{row['id']}: discovery source hash")[1]
                ledger_paths.add(_relocated_source_relative(declared, relocations))

    raw_dispositions = manifest.get("discovery_dispositions", [])
    dispositions = {
        item["candidate_id"]: item["disposition"]
        for item in raw_dispositions
        if isinstance(item, dict)
        and isinstance(item.get("candidate_id"), str)
        and item.get("disposition") in {"registry_consumer", "relocated", "retained_mechanic", "not_a_fact"}
    }
    # The broad discovery helper is intentionally reusable and has a looser
    # filesystem walk than this campaign.  Apply the same path predicate as
    # the frozen universe before any candidate can become campaign work; this
    # keeps test/dunder/private paths out without filtering production files.
    candidates = [
        candidate
        for candidate in discover_governed_literal_candidates(SOURCE_ROOT)
        if not _fd_excluded(PurePosixPath(candidate.path.replace("\\", "/")))
    ]
    observations = [
        _candidate_payload(candidate)
        | {
            "confidence": (
                "high" if candidate.kind.value in {"decimal", "numeric", "legal_text", "mapping"} else "review"
            ),
            "ledger_context": candidate.path in ledger_paths,
        }
        for candidate in candidates
    ]
    observations.extend(
        catalogue | {"ledger_context": catalogue["path"] in ledger_paths}
        for catalogue in _discover_tax_enum_catalogues(SOURCE_ROOT)
        if not _fd_excluded(PurePosixPath(catalogue["path"].replace("\\", "/")))
    )
    observations.sort(key=lambda item: (item["path"], item["line"], item["candidate_id"]))
    for item in observations:
        item["disposition"] = dispositions.get(item["candidate_id"], "untriaged")
    observed_ids = {item["candidate_id"] for item in observations}
    stale_disposition_ids = sorted(set(dispositions) - observed_ids)
    untriaged = [item for item in observations if item["disposition"] == "untriaged"]
    blocking = [item for item in untriaged if item["confidence"] == "high"]
    review = [item for item in untriaged if item["confidence"] == "review"]
    return {
        "observations": observations,
        "untriaged": untriaged,
        "blocking": blocking,
        "review": review,
        "stale_disposition_ids": stale_disposition_ids,
        "counts": {
            "discovery_candidate_count": len(observations),
            "discovery_candidate_file_count": len({item["path"] for item in observations}),
            "discovery_dispositioned_count": len(observations) - len(untriaged),
            "discovery_untriaged_count": len(untriaged),
            "discovery_untriaged_file_count": len({item["path"] for item in untriaged}),
            "discovery_blocking_count": len(blocking),
            "discovery_blocking_file_count": len({item["path"] for item in blocking}),
            "discovery_review_count": len(review),
            "discovery_review_file_count": len({item["path"] for item in review}),
            "discovery_stale_disposition_count": len(stale_disposition_ids),
        },
    }


def _normalise_todo_text(value: str) -> str:
    """Normalise the comment prefix while retaining the exact TODO message."""
    normalised = value.strip()
    if normalised.startswith("#"):
        normalised = normalised[1:].lstrip()
    return normalised


def _todo_debt_scan(
    manifest: dict[str, Any],
    universe_scan: dict[str, Any],
) -> dict[str, Any]:
    """Count only exact fact-relocation TODO comments in the eligible universe.

    Tokenising comments keeps docstrings, ordinary strings, and generic TODOs out
    of this secondary debt signal.  The debt stream is deliberately independent
    of ledger actionability: a marker may be associated with a migrated row while
    remaining an open seam that still needs wiring.
    """
    relocations = _source_relocations(manifest.get("source_relocations"))
    closure_by_signature: dict[str, list[dict[str, Any]]] = {}
    for row in manifest["candidates"]:
        if row.get("status") not in CLOSED_STATUSES:
            continue
        closure = row.get("closure")
        if not isinstance(closure, dict):
            continue
        placement = closure.get("placement")
        todo_text = placement.get("todo_text") if isinstance(placement, dict) else closure.get("todo_text")
        if not isinstance(todo_text, str) or not todo_text.strip():
            continue
        paths: set[str] = set()
        if isinstance(placement, dict) and isinstance(placement.get("source_file"), str):
            declared = _source_path(
                placement["source_file"],
                label=f"{row['id']}: TODO placement source",
            )[1]
            paths.add(_relocated_source_relative(declared, relocations))
        for evidence in row.get("evidence", ()):
            if not isinstance(evidence, dict) or not isinstance(evidence.get("file"), str):
                continue
            declared = _source_path(
                evidence["file"],
                label=f"{row['id']}: TODO evidence source",
            )[1]
            paths.add(_relocated_source_relative(declared, relocations))
        for source_hash in closure.get("source_hashes", ()):
            if not isinstance(source_hash, dict) or not isinstance(source_hash.get("path"), str):
                continue
            declared = _source_path(
                source_hash["path"],
                label=f"{row['id']}: TODO closure source",
            )[1]
            paths.add(_relocated_source_relative(declared, relocations))
        signature = _normalise_todo_text(todo_text)
        closure_by_signature.setdefault(signature, []).append(
            {
                "row_id": row["id"],
                "status": row["status"],
                "paths": sorted(paths),
                "todo_text": todo_text,
            }
        )

    occurrences: list[dict[str, Any]] = []
    scan_errors: list[dict[str, str]] = []
    for relative in universe_scan["paths"]:
        path = REPO_ROOT / Path(*PurePosixPath(relative).parts)
        try:
            data = path.read_bytes()
            tokens = tokenize.tokenize(io.BytesIO(data).readline)
            for token in tokens:
                if token.type != tokenize.COMMENT:
                    continue
                for match in FACT_RELOCATION_TODO_RE.finditer(token.string):
                    comment = token.string.strip()
                    signature = _normalise_todo_text(comment)
                    closure_matches = [
                        item
                        for item in closure_by_signature.get(signature, ())
                        if not item["paths"] or relative in item["paths"]
                    ]
                    candidate_ids = sorted({item["row_id"] for item in closure_matches})
                    migrated_row_ids = sorted(
                        {item["row_id"] for item in closure_matches if item["status"] == "migrated"}
                    )
                    occurrences.append(
                        {
                            "file": relative,
                            "line": token.start[0],
                            "column": token.start[1] + match.start(),
                            "marker": match.group(0),
                            "text": comment,
                            "candidate_ids": candidate_ids,
                            "migrated_row_ids": migrated_row_ids,
                            "association_status": (
                                "migrated_row" if migrated_row_ids else "closed_row" if candidate_ids else "unresolved"
                            ),
                            "resolution_status": "open",
                        }
                    )
        except (OSError, SyntaxError, LookupError, UnicodeDecodeError, tokenize.TokenError) as exc:
            scan_errors.append(
                {
                    "file": relative,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    occurrences.sort(key=lambda item: (item["file"], item["line"], item["column"]))
    migrated_rows_with_unresolved_todos: list[dict[str, Any]] = []
    for entries in closure_by_signature.values():
        for entry in entries:
            if entry["status"] != "migrated":
                continue
            associated = any(entry["row_id"] in occurrence["migrated_row_ids"] for occurrence in occurrences)
            if associated:
                migrated_rows_with_unresolved_todos.append(
                    {
                        "row_id": entry["row_id"],
                        "source_files": entry["paths"],
                        "todo_text": entry["todo_text"],
                        "reason": "exact comment marker remains open",
                    }
                )
    migrated_rows_with_unresolved_todos.sort(key=lambda item: item["row_id"])
    baseline: dict[str, Any] = {
        "path": _display_path(DEFAULT_TODO_BASELINE),
        "status": "not_configured",
        "total_count": None,
        "open_count": None,
        "total_delta": None,
        "open_delta": None,
        "resolved_delta": None,
    }
    if DEFAULT_TODO_BASELINE.is_file():
        try:
            raw_baseline = json.loads(DEFAULT_TODO_BASELINE.read_text(encoding="utf-8"))
            baseline_total = raw_baseline.get("total_count")
            baseline_open = raw_baseline.get("open_count")
            if not isinstance(baseline_total, int) or not isinstance(baseline_open, int):
                raise ValueError("total_count and open_count must be integers")
            baseline.update(
                {
                    "status": "ready",
                    "total_count": baseline_total,
                    "open_count": baseline_open,
                    "total_delta": len(occurrences) - baseline_total,
                    "open_delta": sum(occurrence["resolution_status"] == "open" for occurrence in occurrences)
                    - baseline_open,
                    "resolved_delta": baseline_open
                    - sum(occurrence["resolution_status"] == "open" for occurrence in occurrences),
                }
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            baseline["status"] = f"invalid:{type(exc).__name__}"
    return {
        "marker": "# TODO(fact-relocation)",
        "eligible_file_count": len(universe_scan["paths"]),
        "total_count": len(occurrences),
        "open_count": sum(occurrence["resolution_status"] == "open" for occurrence in occurrences),
        "resolved_count": sum(occurrence["resolution_status"] == "resolved" for occurrence in occurrences),
        "occurrences": occurrences,
        "migrated_rows_with_unresolved_todos": migrated_rows_with_unresolved_todos,
        "migrated_rows_with_unresolved_count": len(migrated_rows_with_unresolved_todos),
        "baseline": baseline,
        "scan_errors": scan_errors,
        "scan_error_count": len(scan_errors),
    }


def _load_symbol_enrichment(manifest: dict[str, Any]) -> dict[str, Any]:
    """Load and validate the optional canonical AST identity enrichment."""
    path = DEFAULT_ENRICHMENT
    if not path.is_file():
        return {
            "status": "unavailable",
            "path": _display_path(path),
            "reason": "file not found",
            "records": {},
            "disposition_mismatches": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ManifestError(f"symbol enrichment cannot be read: {type(exc).__name__}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"symbol enrichment is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ManifestError("symbol enrichment root must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError("symbol enrichment schema_version is incompatible")
    source_scope = payload.get("source_scope")
    if not isinstance(source_scope, dict):
        raise ManifestError("symbol enrichment source_scope must be an object")
    if source_scope.get("root") != "src/cadrumo":
        raise ManifestError("symbol enrichment source root is incompatible")
    if source_scope.get("parser") != "Python ast.parse":
        raise ManifestError("symbol enrichment parser is incompatible")
    exclusions = source_scope.get("excluded")
    if not isinstance(exclusions, list):
        raise ManifestError("symbol enrichment exclusions must be a list")
    exclusion_text = " ".join(str(item) for item in exclusions)
    for required in (
        "test",
        "tests",
        "*_test.py",
        "test_*.py",
        "conftest.py",
        "__pycache__",
        "__*.py",
    ):
        if required not in exclusion_text:
            raise ManifestError(f"symbol enrichment is missing exclusion {required!r}")
    records = payload.get("records")
    if not isinstance(records, dict):
        raise ManifestError("symbol enrichment records must be an object")
    candidate_rows = {row["id"]: row for row in manifest["candidates"]}
    if set(records) != set(candidate_rows):
        missing = sorted(set(candidate_rows) - set(records))
        extra = sorted(set(records) - set(candidate_rows))
        raise ManifestError(f"symbol enrichment IDs do not match manifest (missing={missing}, extra={extra})")

    normalized_records: dict[str, dict[str, Any]] = {}
    disposition_mismatches: list[str] = []
    total_declarations = 0
    for candidate_id in sorted(candidate_rows):
        row = candidate_rows[candidate_id]
        record = records[candidate_id]
        if not isinstance(record, dict):
            raise ManifestError(f"symbol enrichment record {candidate_id} must be an object")
        if record.get("category") != row["category"]:
            raise ManifestError(f"symbol enrichment category mismatch for {candidate_id}")
        if record.get("resolution_status") != "resolved":
            raise ManifestError(f"symbol enrichment record {candidate_id} is unresolved")
        if record.get("declaration_observable") is not True:
            raise ManifestError(f"symbol enrichment record {candidate_id} is not observable")
        declarations = record.get("declarations")
        if not isinstance(declarations, list) or not declarations:
            raise ManifestError(f"symbol enrichment record {candidate_id} has no declarations")
        seen_declarations: set[tuple[str, str, str, str, str]] = set()
        normalized_declarations: list[dict[str, Any]] = []
        for index, declaration in enumerate(declarations):
            label = f"symbol enrichment {candidate_id} declaration[{index}]"
            if not isinstance(declaration, dict):
                raise ManifestError(f"{label} must be an object")
            required_fields = (
                "file",
                "symbol",
                "scope",
                "ast_node_kind",
                "source_span",
                "source_fingerprint_input",
            )
            if any(
                not isinstance(declaration.get(field), str) or not declaration[field].strip()
                for field in required_fields
            ):
                raise ManifestError(f"{label} is incomplete")
            if declaration.get("declaration_observable") is not True:
                raise ManifestError(f"{label} is not observable")
            _, relative = _source_path(declaration["file"], label=label)
            source_span = declaration["source_span"]
            if not re.fullmatch(r"L[0-9]+-L[0-9]+", source_span):
                raise ManifestError(f"{label}.source_span is invalid")
            identity = (
                relative,
                declaration["symbol"],
                declaration["scope"],
                declaration["ast_node_kind"],
                source_span,
            )
            if identity in seen_declarations:
                raise ManifestError(f"{label} duplicates a declaration identity")
            seen_declarations.add(identity)
            expected_fingerprint = "|".join(
                (
                    "v1",
                    relative,
                    declaration["scope"],
                    _enrichment_symbol_leaf(declaration["symbol"]),
                    declaration["ast_node_kind"],
                    source_span,
                )
            )
            if declaration["source_fingerprint_input"] != expected_fingerprint:
                raise ManifestError(f"{label}.source_fingerprint_input drifted")
            normalized_declarations.append(
                {
                    **declaration,
                    "file": relative,
                }
            )
        total_declarations += len(normalized_declarations)
        normalized_records[candidate_id] = {
            **record,
            "declarations": normalized_declarations,
        }
        manifest_actionable = row["status"] in BLOCKING_STATUSES
        enrichment_actionable = record.get("canonical_actionable")
        if not isinstance(enrichment_actionable, bool):
            raise ManifestError(f"symbol enrichment canonical_actionable missing for {candidate_id}")
        if manifest_actionable != enrichment_actionable:
            disposition_mismatches.append(candidate_id)

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ManifestError("symbol enrichment summary must be an object")
    expected_total = len(candidate_rows)
    for field, expected in (
        ("canonical_total", expected_total),
        ("resolved", expected_total),
        ("unresolved", 0),
        ("declaration_observable_records", expected_total),
    ):
        if summary.get(field) != expected:
            raise ManifestError(f"symbol enrichment summary.{field} is incompatible")
    readiness = payload.get("integration_readiness")
    if not isinstance(readiness, dict) or readiness.get("ready_for_lane_1") is not True:
        raise ManifestError("symbol enrichment is not marked ready for lane 1")
    return {
        "status": "ready",
        "path": _display_path(path),
        "records": normalized_records,
        "summary": summary,
        "total_declarations": total_declarations,
        "disposition_mismatches": disposition_mismatches,
        "scope_only_count": sum(
            record.get("identity_precision") == "scope_only" for record in normalized_records.values()
        ),
    }


def _declared_set_value(
    manifest: dict[str, Any],
    name: str,
) -> tuple[Any, str | None]:
    baseline = manifest.get("baseline", {})
    source_sets = baseline.get("source_sets", {}) if isinstance(baseline, dict) else {}
    if not isinstance(source_sets, dict):
        source_sets = {}
    for container, prefix in (
        (source_sets, "baseline.source_sets"),
        (baseline, "baseline"),
        (manifest.get("source_sets", {}), "source_sets"),
        (manifest, "manifest"),
    ):
        if isinstance(container, dict):
            for key in (f"{name}_paths", f"{name}_files", name):
                if key in container:
                    return container[key], f"{prefix}.{key}"
    return None, None


def _reconcile_declared_set(
    manifest: dict[str, Any],
    name: str,
    universe_paths: set[str],
) -> dict[str, Any]:
    raw, source_key = _declared_set_value(manifest, name)
    companion = manifest.get("baseline", {}).get(f"{name}_files")
    if raw is None:
        return {
            "name": name,
            "status": "unavailable",
            "source_key": None,
            "declared_count": companion if isinstance(companion, int) else None,
            "declared_path_count": None,
            "observed_in_universe_count": None,
            "missing_from_universe_count": 0,
            "duplicate_path_count": 0,
            "count_drift": 0,
            "set_digest": None,
            "reconciliation_error_count": 0,
        }
    if isinstance(raw, int):
        if raw < 0:
            raise ManifestError(f"{source_key}: count must not be negative")
        return {
            "name": name,
            "status": "count-only",
            "source_key": source_key,
            "declared_count": raw,
            "declared_path_count": None,
            "observed_in_universe_count": None,
            "missing_from_universe_count": 0,
            "duplicate_path_count": 0,
            "count_drift": 0,
            "set_digest": None,
            "reconciliation_error_count": 0,
        }
    if not isinstance(raw, list):
        raise ManifestError(f"{source_key}: expected an integer or path list")
    normalized: list[str] = []
    for index, value in enumerate(raw):
        _, relative = _source_path(value, label=f"{source_key}[{index}]")
        normalized.append(relative)
    duplicate_count = len(normalized) - len(set(normalized))
    declared_paths = sorted(set(normalized))
    missing_count = sum(path not in universe_paths for path in declared_paths)
    count_drift = abs(len(normalized) - companion) if isinstance(companion, int) else 0
    return {
        "name": name,
        "status": "path-set",
        "source_key": source_key,
        "declared_count": companion if isinstance(companion, int) else len(normalized),
        "declared_path_count": len(normalized),
        "observed_in_universe_count": len(declared_paths) - missing_count,
        "missing_from_universe_count": missing_count,
        "duplicate_path_count": duplicate_count,
        "count_drift": count_drift,
        "set_digest": _hash_lines(declared_paths),
        "reconciliation_error_count": missing_count + duplicate_count + count_drift,
    }


def _reconcile_frozen_universe(
    manifest: dict[str, Any],
    universe: dict[str, Any],
) -> dict[str, Any]:
    counts = universe["counts"]
    baseline = manifest["baseline"]
    live_record = baseline.get("live_universe_reconciliation")
    historical_count = baseline.get("audit_eligible_python_files")
    expected_count = (
        live_record["live_expected_eligible_python_files"] if isinstance(live_record, dict) else historical_count
    )
    if not isinstance(expected_count, int) or expected_count < 1:
        raise ManifestError("baseline.audit_eligible_python_files must be a positive integer")
    actual_count = counts["universe_count"]
    count_drift = abs(actual_count - expected_count)
    universe_paths = set(universe["paths"])
    delta_paths = set(live_record["delta_paths"]) if isinstance(live_record, dict) else set()
    delta_paths_missing_count = sum(path not in universe_paths for path in delta_paths)
    candidate_paths = {evidence["file"] for row in manifest["candidates"] for evidence in row["evidence"]}
    delta_candidate_path_count = len(delta_paths & candidate_paths)
    delta_candidate_flag_drift = (
        int(delta_candidate_path_count > 0) != int(live_record["delta_adds_candidate"])
        if isinstance(live_record, dict)
        else 0
    )
    broad = _reconcile_declared_set(manifest, "broad_prefilter", universe_paths)
    direct = _reconcile_declared_set(
        manifest,
        "direct_model_legal_filename",
        universe_paths,
    )
    reconciliation_error_count = (
        count_drift
        + counts["universe_parse_failures"]
        + counts["universe_read_failures"]
        + counts["universe_enumeration_failures"]
        + delta_paths_missing_count
        + delta_candidate_flag_drift
        + broad["reconciliation_error_count"]
        + direct["reconciliation_error_count"]
    )
    return {
        "expected_count": expected_count,
        "historical_count": historical_count,
        "actual_count": actual_count,
        "count_drift": count_drift,
        "delta_paths_missing_count": delta_paths_missing_count,
        "delta_candidate_path_count": delta_candidate_path_count,
        "delta_candidate_flag_drift": delta_candidate_flag_drift,
        "broad_prefilter": broad,
        "direct_model_legal_filename": direct,
        "reconciliation_error_count": reconciliation_error_count,
        "complete": reconciliation_error_count == 0,
    }


def _flatten_strings(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, dict):
        for key in sorted(value, key=str):
            values.extend(_flatten_strings(key))
            values.extend(_flatten_strings(value[key]))
    elif isinstance(value, (list, tuple)):
        for item in value:
            values.extend(_flatten_strings(item))
    return values


def _payload_has_true(value: Any, keys: frozenset[str]) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in keys and item is True:
                return True
            if _payload_has_true(item, keys):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_payload_has_true(item, keys) for item in value)
    return False


def _payload_has_status(value: Any, statuses: frozenset[str]) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            key_name = str(key).casefold()
            if (
                key_name in {"status", "publication_status", "release_status"}
                and isinstance(item, str)
                and item.casefold() in statuses
            ):
                return True
            if _payload_has_status(item, statuses):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_payload_has_status(item, statuses) for item in value)
    return False


def _load_indexed_fact_authority(path: Path) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    """Load the governed-fact directory through the admitted typed SQLite reader."""
    metadata: dict[str, Any] = {
        "artifact": _display_path(path),
        "descriptor_sha256": None,
        "identity_digest": None,
        "fact_count": 0,
        "status": "missing",
        "error": None,
    }
    try:
        data = path.read_bytes()
    except OSError as exc:
        metadata["status"] = f"read-error:{type(exc).__name__}"
        metadata["error"] = str(exc)
        return None, metadata["status"], metadata
    metadata["descriptor_sha256"] = "sha256:" + hashlib.sha256(data).hexdigest()
    reader: SQLiteAuthorityReader | None = None
    try:
        reader = SQLiteAuthorityReader(path)
        pin = reader.pin()
        queries = tuple(
            query for query in reader.component_queries() if query.kind is AuthorityComponentKind.GOVERNED_FACT
        )
        facts = {
            query.fact_id: reader.load(query, pin=pin)
            for query in queries
            if isinstance(query, GovernedFactComponentQuery)
        }
        raw_facts = {fact_id: fact.model_dump(mode="json") for fact_id, fact in facts.items()}
        identity_digest = pin.logical_generation
    except (AuthorityStoreError, AttributeError, OSError, TypeError, ValueError) as exc:
        metadata["status"] = f"invalid-authority:{type(exc).__name__}"
        metadata["error"] = str(exc)
        return None, metadata["status"], metadata
    finally:
        if reader is not None:
            reader.close()
    metadata["identity_digest"] = identity_digest
    metadata["fact_count"] = len(facts)
    metadata["status"] = "ok"
    return (
        {
            "identity_digest": identity_digest,
            "facts": facts,
            "raw_facts": raw_facts,
        },
        "ok",
        metadata,
    )


def _authoring_fact_proof(
    path: Path,
    *,
    declaration_id: str,
    family: str,
) -> dict[str, Any]:
    """Prove an authored fact path by parsing its exact ``[fact]`` table."""
    result: dict[str, Any] = {
        "file": _display_path(path),
        "exists": path.is_file(),
        "read_status": "missing",
        "declaration_id": None,
        "family": None,
        "variant_ids": [],
        "exact_fact_proof": False,
    }
    if not result["exists"]:
        return result
    try:
        import tomllib

        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, TypeError) as exc:
        result["read_status"] = f"parse-error:{type(exc).__name__}"
        return result
    result["read_status"] = "ok"
    declaration = payload.get("fact") if isinstance(payload, dict) else None
    if not isinstance(declaration, dict):
        result["read_status"] = "fact-declaration-missing"
        return result
    declared_id = declaration.get("fact_id")
    declared_family = declaration.get("family")
    variants = declaration.get("variants")
    variant_ids = (
        [
            variant.get("variant_id")
            for variant in variants
            if isinstance(variant, dict) and isinstance(variant.get("variant_id"), str)
        ]
        if isinstance(variants, list)
        else []
    )
    result.update(
        {
            "declaration_id": declared_id,
            "family": declared_family,
            "variant_ids": variant_ids,
        }
    )
    result["exact_fact_proof"] = bool(
        declared_id == declaration_id
        and declared_family == family
        and isinstance(variants, list)
        and bool(variants)
        and len(variant_ids) == len(variants)
        and all(isinstance(variant, dict) and isinstance(variant.get("payload"), dict) for variant in variants)
    )
    return result


def _governed_fact_proof(
    frame: dict[str, Any] | None,
    *,
    declaration_id: str,
    family: str,
) -> dict[str, Any]:
    """Prove the exact fact/family/variant tuple in a validated v4 frame."""
    result: dict[str, Any] = {
        "declaration_id": declaration_id,
        "family": family,
        "observed_declaration_id": None,
        "observed_family": None,
        "variant_ids": [],
        "variant_proof": False,
        "present": False,
    }
    if frame is None:
        return result
    facts = frame.get("raw_facts")
    fact = facts.get(declaration_id) if hasattr(facts, "get") else None
    if fact is None:
        return result
    observed_id = fact.get("fact_id") if isinstance(fact, dict) else None
    observed_family = fact.get("family") if isinstance(fact, dict) else None
    variants = fact.get("variants", ()) if isinstance(fact, dict) else ()
    variant_ids = [
        variant.get("variant_id")
        for variant in variants
        if isinstance(variant, dict) and isinstance(variant.get("variant_id"), str)
    ]
    result.update(
        {
            "observed_declaration_id": observed_id,
            "observed_family": observed_family,
            "variant_ids": variant_ids,
        }
    )
    result["variant_proof"] = bool(
        isinstance(variants, (list, tuple))
        and bool(variants)
        and len(variant_ids) == len(variants)
        and all(isinstance(variant, dict) and isinstance(variant.get("payload"), dict) for variant in variants)
    )
    result["present"] = bool(observed_id == declaration_id and observed_family == family and result["variant_proof"])
    return result


def _fact_declaration(
    payload: Any,
    destination: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    """Return a top-level ``[fact]`` declaration and schema-field errors.

    Authored facts are individual TOML files, unlike Modelo revision files
    whose declarations live below ``revisions.<revision>.<family>``.  Keep
    the two shapes explicit: a fact destination is verified by its declared
    ``fact_id`` and by the variant payload that carries the fact value (or
    the family-specific collection for non-scalars).
    """
    fact_payload = payload.get("fact") if isinstance(payload, dict) else None
    if not isinstance(fact_payload, dict):
        return {}, {}

    fact_id = fact_payload.get("fact_id")
    declaration_by_id = {fact_id: fact_payload} if isinstance(fact_id, str) and fact_id else {}
    declaration_id = destination["declaration_ids"]
    missing_fields: dict[str, list[str]] = {}
    for requested_id in declaration_id:
        if requested_id not in declaration_by_id:
            continue
        missing: list[str] = [field for field in destination["required_fields"] if field not in fact_payload]
        if not isinstance(fact_id, str) or not fact_id:
            missing.append("fact_id")
        family = fact_payload.get("family")
        if not isinstance(family, str) or not family:
            missing.append("family")

        variants = fact_payload.get("variants")
        if not isinstance(variants, list) or not variants:
            missing.append("variants")
        else:
            for variant_index, variant in enumerate(variants):
                variant_label = f"variants[{variant_index}]"
                if not isinstance(variant, dict):
                    missing.append(f"{variant_label}")
                    continue
                variant_id = variant.get("variant_id")
                if not isinstance(variant_id, str) or not variant_id:
                    missing.append(f"{variant_label}.variant_id")
                variant_payload = variant.get("payload")
                if not isinstance(variant_payload, dict):
                    missing.append(f"{variant_label}.payload")
                    continue
                kind = variant_payload.get("kind")
                if not isinstance(kind, str) or not kind:
                    missing.append(f"{variant_label}.payload.kind")
                elif kind == "scalar":
                    if "value" not in variant_payload:
                        missing.append(f"{variant_label}.payload.value")
                elif kind == "mapping":
                    if "entries" not in variant_payload:
                        missing.append(f"{variant_label}.payload.entries")
                elif kind == "entity_set" and "entities" not in variant_payload:
                    missing.append(f"{variant_label}.payload.entities")
        if missing:
            missing_fields[requested_id] = sorted(set(missing))
    return declaration_by_id, missing_fields


def _missing_typed_binding_fields(
    declaration: dict[str, Any],
    destination: dict[str, Any],
) -> list[str]:
    """Validate the live typed binding surface used by placement closures.

    Older placement claims named the pre-refactor ``source`` and ``selector``
    siblings.  Those keys are intentionally no longer part of
    :class:`BindingDefinition`: the provider discriminator and its typed
    members are now the source/selector contract.  Keep this check local to
    binding destinations so a stale claim cannot be made to pass merely by
    adding forbidden compatibility keys to authored TOML.
    """
    missing: list[str] = []
    provider = declaration.get("provider")
    value = declaration.get("value")
    legal_refs = declaration.get("legal_refs")
    source_refs = declaration.get("source_refs")
    if not isinstance(provider, dict):
        missing.append("provider")
    elif not isinstance(provider.get("kind"), str) or not provider["kind"].strip():
        missing.append("provider.kind")
    if not isinstance(value, dict):
        missing.append("value")
    if not isinstance(legal_refs, list) or not legal_refs:
        missing.append("legal_refs")
    if not isinstance(source_refs, list) or not source_refs:
        missing.append("source_refs")

    semantic_requirements = destination.get("semantic_requirements", {})
    if not isinstance(semantic_requirements, dict):
        missing.append("semantic_requirements")
        return sorted(set(missing))
    declaration_requirements = semantic_requirements.get(declaration.get("id"), {})
    if declaration_requirements is None:
        declaration_requirements = {}
    if not isinstance(declaration_requirements, dict):
        missing.append("semantic_requirements[declaration]")
        return sorted(set(missing))

    def compare(actual: Any, expected: Any, path: str) -> None:
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                missing.append(path)
                return
            for key, nested in expected.items():
                compare(actual.get(key), nested, f"{path}.{key}")
            return
        if actual != expected:
            missing.append(path)

    for key, expected in declaration_requirements.items():
        compare(declaration.get(key), expected, key)
    return sorted(set(missing))


def _validate_absorbed_relation_requirements(
    declaration_by_id: dict[str, dict[str, Any]],
    destination: dict[str, Any],
) -> dict[str, list[str]]:
    """Check relation claims that were absorbed into typed binding providers.

    Relation TOMLs are no longer a live schema family.  A manifest may retain
    the old relation identity as an audit label, but it must point at an
    existing binding declaration and state the exact provider/applicability/
    aggregation shape that proves the equivalence.
    """
    missing: dict[str, list[str]] = {}
    absorbed = destination.get("absorbed_relations")
    if absorbed is None:
        return missing
    if not isinstance(absorbed, list):
        return {"<destination>": ["absorbed_relations"]}

    def compare(actual: Any, expected: Any, path: str, errors: list[str]) -> None:
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                errors.append(path)
                return
            for key, nested in expected.items():
                compare(actual.get(key), nested, f"{path}.{key}", errors)
            return
        if actual != expected:
            errors.append(path)

    for index, relation in enumerate(absorbed):
        label = f"absorbed_relations[{index}]"
        if not isinstance(relation, dict):
            missing.setdefault(label, []).append(label)
            continue
        canonical_id = relation.get("canonical_declaration_id")
        legacy_id = relation.get("legacy_declaration_id")
        if not isinstance(canonical_id, str) or not canonical_id.strip():
            missing.setdefault(label, []).append(f"{label}.canonical_declaration_id")
            continue
        declaration = declaration_by_id.get(canonical_id)
        if declaration is None:
            missing.setdefault(canonical_id, []).append("absorbed canonical declaration")
            continue
        errors: list[str] = []
        requirements = relation.get("requirements", {})
        if not isinstance(requirements, dict):
            errors.append(f"{label}.requirements")
        else:
            for key, expected in requirements.items():
                compare(declaration.get(key), expected, key, errors)
        if not isinstance(legacy_id, str) or not legacy_id.strip():
            errors.append(f"{label}.legacy_declaration_id")
        if not isinstance(relation.get("legacy_path"), str) or not relation["legacy_path"].strip():
            errors.append(f"{label}.legacy_path")
        if errors:
            missing[canonical_id] = sorted(set(errors))
    return missing


def _typed_modelo_declarations(
    destination_relative: str,
    destination: dict[str, Any],
    diagnostics: list[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    """Materialise one live Modelo family through the production typed loader.

    Placement evidence must not trust a raw revision fragment for fields that
    the live compiler supplies through defaults or predecessor inheritance.
    A loader failure, malformed typed member, or missing typed identity returns
    an empty index so the caller remains fail-closed; the raw TOML is never a
    fallback for Modelo declarations.
    """
    parts = PurePosixPath(destination_relative).parts
    modelos_index = next(
        (index for index, part in enumerate(parts) if part.casefold() == "modelos"),
        None,
    )
    if modelos_index is None or modelos_index + 1 >= len(parts):
        return {}, {}
    modelo_directory = REPO_ROOT / Path(*parts[: modelos_index + 2])
    try:
        from dev.registry.compiler.loader import load_modelo_directory

        modelo = load_modelo_directory(modelo_directory)
        revisions = getattr(modelo, "revisions", None)
        revision = revisions.get(destination["revision"]) if isinstance(revisions, Mapping) else None
        members = getattr(revision, destination["family"], None) if revision is not None else None
    except Exception as exc:
        # The typed loader owns schema, defaults, and predecessor resolution.
        # Any import/compile/schema error must leave the evidence unresolved.
        if diagnostics is not None:
            diagnostics.append(f"typed-loader:{type(exc).__name__}: {exc}")
        return {}, {}

    if not isinstance(members, Sequence) or isinstance(members, (str, bytes, bytearray)):
        return {}, {}

    declarations: dict[str, dict[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for member in members:
        model_dump = getattr(member, "model_dump", None)
        if not callable(model_dump):
            continue
        try:
            declaration = model_dump(mode="json", exclude_defaults=False)
        except Exception as exc:
            if diagnostics is not None:
                diagnostics.append(f"typed-member:{type(exc).__name__}: {exc}")
            continue
        if not isinstance(declaration, dict):
            continue
        declaration_id = declaration.get("id")
        if not isinstance(declaration_id, str) or not declaration_id.strip():
            continue
        if declaration_id in declarations:
            duplicate_ids.add(declaration_id)
            continue
        declarations[declaration_id] = declaration

    missing_fields: dict[str, list[str]] = {}
    for declaration_id in destination["declaration_ids"]:
        declaration = declarations.get(declaration_id)
        if declaration is None:
            continue
        missing: list[str] = [field for field in destination["required_fields"] if field not in declaration]
        if declaration_id in duplicate_ids:
            missing.append("duplicate id")
        for field in ("legal_refs", "source_refs"):
            if field not in destination["required_fields"]:
                continue
            refs = declaration.get(field)
            if (
                not isinstance(refs, (list, tuple))
                or not refs
                or any(not isinstance(reference, str) or not reference.strip() for reference in refs)
            ):
                missing.append(field)
        if missing:
            missing_fields[declaration_id] = sorted(set(missing))
    return declarations, missing_fields


def _ast_registry_symbols(tree: ast.AST) -> set[str]:
    """Return query/snapshot symbols, including aliases proven by imports."""
    symbols = set(REGISTRY_QUERY_SYMBOLS)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for alias in node.names:
            imported = alias.name.rsplit(".", 1)[-1]
            if imported in REGISTRY_QUERY_SYMBOLS:
                symbols.add(alias.asname or imported)
    return symbols


def _ast_registry_query_call(node: ast.AST, symbols: set[str]) -> bool:
    """Require a real query-constructor call in an AST subtree."""
    query_symbols = symbols - {"RegistrySnapshot"}
    return any(isinstance(item, ast.Call) and _call_symbol(item.func) in query_symbols for item in ast.walk(node))


def _ast_registry_snapshot_use(node: ast.AST, symbols: set[str]) -> bool:
    """Recognise a snapshot type/value use, excluding comment-only mentions."""
    return any(
        (isinstance(item, ast.Name) and item.id in symbols)
        or (isinstance(item, ast.Attribute) and item.attr in symbols)
        for item in ast.walk(node)
    )


def _ast_direct_walk(node: ast.AST) -> list[ast.AST]:
    """Walk a node without treating nested definitions as enclosing evidence."""
    pending = list(ast.iter_child_nodes(node))
    walked: list[ast.AST] = []
    while pending:
        item = pending.pop()
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        walked.append(item)
        pending.extend(ast.iter_child_nodes(item))
    return walked


def _ast_import_aliases(tree: ast.AST, canonical: str) -> set[str]:
    """Return a canonical imported symbol and aliases proven by import syntax."""
    aliases = {canonical}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for alias in node.names:
            imported = alias.name.rsplit(".", 1)[-1]
            if imported == canonical:
                aliases.add(alias.asname or imported)
    return aliases


def _ast_registry_service_parameters(
    node: ast.AST,
    service_symbols: set[str],
) -> set[str]:
    """Return parameters whose annotations prove a registry query service."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return set()
    arguments = [
        *getattr(node.args, "posonlyargs", []),
        *node.args.args,
        *node.args.kwonlyargs,
    ]
    if node.args.vararg is not None:
        arguments.append(node.args.vararg)
    if node.args.kwarg is not None:
        arguments.append(node.args.kwarg)
    return {
        argument.arg
        for argument in arguments
        if argument.annotation is not None
        and any(
            (isinstance(item, ast.Name) and item.id in service_symbols)
            or (isinstance(item, ast.Attribute) and item.attr in service_symbols)
            for item in ast.walk(argument.annotation)
        )
    }


def _ast_registry_query_call_direct(
    node: ast.AST,
    symbols: set[str],
    service_symbols: set[str],
    service_parameters: set[str],
) -> bool:
    """Recognise query construction or calls on an annotated query service."""
    query_symbols = symbols - {"RegistrySnapshot"}
    for item in _ast_direct_walk(node):
        if not isinstance(item, ast.Call):
            continue
        if _call_symbol(item.func) in query_symbols:
            return True
        if not isinstance(item.func, ast.Attribute):
            continue
        receiver = item.func.value
        if isinstance(receiver, ast.Name) and receiver.id in service_parameters:
            return True
        if isinstance(receiver, ast.Attribute) and receiver.attr in service_parameters:
            return True
    return False


def _ast_registry_snapshot_use_direct(node: ast.AST, symbols: set[str]) -> bool:
    """Recognise snapshot syntax in the current definition only."""
    return any(
        (isinstance(item, ast.Name) and item.id in symbols)
        or (isinstance(item, ast.Attribute) and item.attr in symbols)
        for item in _ast_direct_walk(node)
    )


def _ast_function_definitions(tree: ast.AST) -> dict[str, list[ast.AST]]:
    """Index local function/class definitions by their declared name."""
    definitions: dict[str, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.setdefault(node.name, []).append(node)
    return definitions


def _ast_function_call_graph(
    tree: ast.AST,
    definitions: dict[str, list[ast.AST]],
) -> tuple[dict[str, set[str]], set[str]]:
    """Build local call edges and module-level function roots from real Calls."""
    graph = {name: set() for name in definitions}
    for name, nodes in definitions.items():
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                graph[name].update(
                    child.name
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name in definitions
                )
            for item in _ast_direct_walk(node):
                if not isinstance(item, ast.Call):
                    continue
                target = _call_symbol(item.func)
                if target in definitions:
                    graph[name].add(target)

    module_targets: set[str] = set()
    for item in _ast_direct_walk(tree):
        if not isinstance(item, ast.Call):
            continue
        target = _call_symbol(item.func)
        if target in definitions:
            module_targets.add(target)
    return graph, module_targets


def _ast_exported_names(tree: ast.AST) -> set[str]:
    """Read literal names from a module's ``__all__`` declaration."""
    exported: set[str] = set()
    for node in getattr(tree, "body", []):
        value: ast.AST | None = None
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
        ) or (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__"):
            value = node.value
        if value is None:
            continue
        for item in ast.walk(value):
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                exported.add(item.value)
    return exported


def _ast_reachable_functions(
    tree: ast.AST,
    definitions: dict[str, list[ast.AST]],
    graph: dict[str, set[str]],
    module_targets: set[str],
) -> set[str]:
    """Return functions reachable from public/exported/module-level roots."""
    roots = {name for name in definitions if not name.startswith("_")}
    roots.update(_ast_exported_names(tree) & definitions.keys())
    roots.update(module_targets)
    reachable: set[str] = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(graph.get(name, ()))
    return reachable


def _ast_scoped_registry_evidence(
    tree: ast.AST,
    symbols: set[str],
    *,
    snapshot_kind: bool,
) -> tuple[set[str], bool]:
    """Resolve query evidence through live local call chains, not module text."""
    definitions = _ast_function_definitions(tree)
    graph, module_targets = _ast_function_call_graph(tree, definitions)
    service_symbols = _ast_import_aliases(tree, "RegistryQueryService")
    evidence_symbols = _ast_import_aliases(tree, "RegistrySnapshot") if snapshot_kind else symbols
    direct_evidence: dict[str, bool] = {}
    for name, nodes in definitions.items():
        direct_evidence[name] = any(
            _ast_registry_snapshot_use_direct(node, evidence_symbols)
            if snapshot_kind
            else _ast_registry_query_call_direct(
                node,
                symbols,
                service_symbols,
                _ast_registry_service_parameters(node, service_symbols),
            )
            for node in nodes
        )

    cache: dict[str, bool] = {}

    def has_evidence(name: str, visiting: set[str] | None = None) -> bool:
        if name in cache:
            return cache[name]
        active = set() if visiting is None else set(visiting)
        if name in active:
            return False
        active.add(name)
        result = direct_evidence.get(name, False) or any(has_evidence(target, active) for target in graph.get(name, ()))
        cache[name] = result
        return result

    reachable = _ast_reachable_functions(tree, definitions, graph, module_targets)
    module_evidence = (
        _ast_registry_snapshot_use_direct(tree, evidence_symbols)
        if snapshot_kind
        else _ast_registry_query_call_direct(tree, symbols, service_symbols, set())
    )
    reachable_evidence = any(has_evidence(name) for name in reachable)
    return reachable, module_evidence or reachable_evidence


def _consumer_registry_resolution(
    consumer_resolution: Any,
) -> tuple[bool, bool, str | None]:
    """Verify a declared consumer seam against its live AST.

    The placement source and the consumer source may be different modules.
    Named seams must contain the corresponding query/snapshot use in the seam
    or a local call chain reachable from it.  Descriptive seams are accepted
    only when a production-reachable function contains the same use.  Text or
    comments alone never satisfy this check.
    """
    if not isinstance(consumer_resolution, dict) or consumer_resolution.get("resolved") is not True:
        return False, False, None
    consumer_source = consumer_resolution.get("source_file")
    seam = consumer_resolution.get("seam")
    kind = str(consumer_resolution.get("kind", "")).casefold().replace("-", "_")
    if not isinstance(consumer_source, str) or not consumer_source.strip():
        return False, False, None
    if not isinstance(seam, str) or not seam.strip():
        return False, False, None
    try:
        _, consumer_relative = _source_path(
            consumer_source,
            label="closure.placement.consumer_resolution.source_file",
        )
    except ManifestError:
        return False, False, None
    observation = _observe_source_file(consumer_relative)
    if (
        observation.get("exists") is not True
        or observation.get("read_status") != "ok"
        or observation.get("ast_parse_status") != "ok"
    ):
        return False, False, consumer_relative
    source_text = observation.get("_text", "")
    try:
        tree = ast.parse(source_text, filename=consumer_relative)
    except (SyntaxError, ValueError, TypeError):
        return False, False, consumer_relative

    symbols = _ast_registry_symbols(tree)
    snapshot_kind = kind in {"registry_snapshot", "snapshot"}
    definitions = _ast_function_definitions(tree)
    graph, module_targets = _ast_function_call_graph(tree, definitions)
    reachable, scoped_present = _ast_scoped_registry_evidence(
        tree,
        symbols,
        snapshot_kind=snapshot_kind,
    )
    identifier_seam = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", seam) is not None
    if not identifier_seam:
        return scoped_present, scoped_present, consumer_relative

    if seam not in definitions:
        return False, False, consumer_relative

    # A proof-only private function is not a production seam.  Reachability is
    # rooted in exported/public functions and module-level calls, then follows
    # only real local Call nodes.  This still accepts public API seams whose
    # caller is outside the consumer module.
    seam_present = (
        seam in reachable
        and _ast_scoped_registry_evidence(
            tree,
            symbols,
            snapshot_kind=snapshot_kind,
        )[1]
    )
    if seam_present:
        # The scoped helper above proves that some reachable function contains
        # evidence.  Re-evaluate the declared seam's own call chain so another
        # unrelated consumer cannot satisfy this row.
        service_symbols = _ast_import_aliases(tree, "RegistryQueryService")
        evidence_symbols = _ast_import_aliases(tree, "RegistrySnapshot") if snapshot_kind else symbols
        direct_evidence = {
            name: any(
                _ast_registry_snapshot_use_direct(node, evidence_symbols)
                if snapshot_kind
                else _ast_registry_query_call_direct(
                    node,
                    symbols,
                    service_symbols,
                    _ast_registry_service_parameters(node, service_symbols),
                )
                for node in nodes
            )
            for name, nodes in definitions.items()
        }
        cache: dict[str, bool] = {}

        def has_seam_evidence(name: str, visiting: set[str] | None = None) -> bool:
            if name in cache:
                return cache[name]
            active = set() if visiting is None else set(visiting)
            if name in active:
                return False
            active.add(name)
            result = direct_evidence.get(name, False) or any(
                has_seam_evidence(target, active) for target in graph.get(name, ())
            )
            cache[name] = result
            return result

        seam_present = has_seam_evidence(seam)
    return seam_present, seam_present, consumer_relative


def _facts_publication_scan(
    publication: Any,
    destinations: list[dict[str, Any]],
    destination_observations: list[dict[str, Any]],
    *,
    consumer_resolved: bool,
) -> dict[str, Any]:
    """Prove an optional facts-authority publication without publishing Modelos.

    Placement rows can contain both governed fact destinations and Modelo
    destinations.  The latter remain an independent, non-blocking publication
    concern here: a facts-only closure is proven only by the explicit
    ``publication.facts`` claim, the validated current facts authority, the
    corresponding authored destinations, and the already-proven consumer seam.
    """
    claim = publication.get("facts") if isinstance(publication, dict) else None
    result: dict[str, Any] = {
        "claimed": isinstance(claim, dict),
        "published": claim.get("published") if isinstance(claim, dict) else None,
        "artifact": None,
        "authority_status": "not-claimed",
        "authority_fact_count": 0,
        "declaration_ids": list(claim.get("declaration_ids", [])) if isinstance(claim, dict) else [],
        "missing_destination_ids": [],
        "missing_authority_ids": [],
        "unverified_destination_ids": [],
        "consumer_resolved": consumer_resolved,
        "failure_reasons": [],
        "verified": True,
        "blocking": False,
    }
    if not isinstance(claim, dict) or claim.get("published") is not True:
        return result

    artifact_path, artifact_relative = _authority_path(
        claim.get("artifact"),
        label="placement publication.facts.artifact",
    )
    result["artifact"] = artifact_relative
    frame, artifact_status, metadata = _load_indexed_fact_authority(artifact_path)
    result["authority_status"] = artifact_status
    result["authority_fact_count"] = metadata.get("fact_count", 0)

    facts_destinations: dict[str, dict[str, Any]] = {}
    for destination, observation in zip(destinations, destination_observations, strict=True):
        path_parts = {part.casefold() for part in PurePosixPath(destination["path"]).parts}
        if "facts" not in path_parts:
            continue
        for declaration_id in destination["declaration_ids"]:
            facts_destinations[declaration_id] = observation

    declaration_ids = result["declaration_ids"]
    result["missing_destination_ids"] = [
        declaration_id for declaration_id in declaration_ids if declaration_id not in facts_destinations
    ]
    result["unverified_destination_ids"] = [
        declaration_id
        for declaration_id in declaration_ids
        if declaration_id in facts_destinations and not facts_destinations[declaration_id]["verified"]
    ]
    raw_facts = frame.get("raw_facts") if isinstance(frame, dict) else None
    result["missing_authority_ids"] = [
        declaration_id
        for declaration_id in declaration_ids
        if not isinstance(raw_facts, dict) or not isinstance(raw_facts.get(declaration_id), dict)
    ]
    reasons: list[str] = []
    if artifact_path.resolve() != BUNDLED_AUTHORITY_DESCRIPTOR.resolve():
        reasons.append("facts_publication_artifact_is_not_current_bundled_authority")
    if artifact_status != "ok":
        reasons.append("facts_publication_authority_unreadable_or_invalid")
    if result["missing_destination_ids"]:
        reasons.append("facts_publication_destination_missing")
    if result["unverified_destination_ids"]:
        reasons.append("facts_publication_destination_unverified")
    if result["missing_authority_ids"]:
        reasons.append("facts_publication_payload_missing")
    if not consumer_resolved:
        reasons.append("facts_publication_consumer_unresolved")
    result["failure_reasons"] = reasons
    result["verified"] = not reasons
    result["blocking"] = not result["verified"]
    return result


def _placement_scan(
    row: dict[str, Any],
    source_scan: dict[str, Any],
) -> dict[str, Any]:
    """Verify an unpublished placement using source and authored TOML bytes."""
    closure = row["closure"]
    placement = closure["placement"]
    source_relative = _source_path(
        placement["source_file"],
        label=f"{row['id']}: closure.placement.source_file",
    )[1]
    source_observation = source_scan["observations"].get(source_relative, {})
    source_text = source_observation.get("_text", "")
    declarations = {item["symbol"] for item in source_observation.get("_declarations", [])}
    forbidden_symbols_absent = all(
        symbol not in declarations and symbol.casefold() not in source_text.casefold()
        for symbol in placement["forbidden_symbols"]
    )
    forbidden_literals_absent = all(
        literal.casefold() not in source_text.casefold() for literal in placement["forbidden_literals"]
    )
    source_ok = all(
        (
            source_observation.get("exists") is True,
            source_observation.get("read_status") == "ok",
            source_observation.get("ast_parse_status") == "ok",
        )
    )
    todo_text = placement.get("todo_text")
    todo_present = isinstance(todo_text, str) and bool(todo_text.strip()) and todo_text in source_text
    consumer_resolution = placement.get("consumer_resolution")
    consumer_resolved, consumer_registry_query_present, consumer_source_relative = _consumer_registry_resolution(
        consumer_resolution,
    )
    registry_query_present = (
        consumer_registry_query_present
        if isinstance(consumer_resolution, dict) and consumer_resolution.get("resolved") is True
        else bool(source_observation.get("_symbols", set()) & REGISTRY_QUERY_SYMBOLS)
    )

    destination_observations: list[dict[str, Any]] = []
    for index, destination in enumerate(placement["destinations"]):
        label = f"{row['id']}: placement destination[{index}]"
        destination_path, destination_relative = _authoring_path(
            destination["path"],
            label=f"{label}.path",
        )
        observation: dict[str, Any] = {
            "file": destination_relative,
            "exists": destination_path.is_file(),
            "read_status": "missing",
            "toml_status": "missing",
            "revision": destination["revision"],
            "family": destination["family"],
            "declaration_ids": destination["declaration_ids"],
            "found_declaration_ids": [],
            "missing_declaration_ids": list(destination["declaration_ids"]),
            "missing_required_fields": {},
            "typed_loader_diagnostics": [],
            "verified": False,
        }
        if not destination_path.is_file():
            destination_observations.append(observation)
            continue
        try:
            data = destination_path.read_bytes()
            observation["read_status"] = "ok"
            import tomllib

            payload = tomllib.loads(data.decode("utf-8"))
            observation["toml_status"] = "ok"
        except (OSError, UnicodeDecodeError, ValueError, TypeError) as exc:
            observation["toml_status"] = f"parse-error:{type(exc).__name__}"
            destination_observations.append(observation)
            continue

        path_parts = {part.casefold() for part in PurePosixPath(destination_relative).parts}
        if "facts" in path_parts:
            declaration_by_id, fact_missing_fields = _fact_declaration(
                payload,
                destination,
            )
        elif "modelos" in path_parts:
            typed_loader_diagnostics: list[str] = []
            declaration_by_id, typed_missing_fields = _typed_modelo_declarations(
                destination_relative,
                destination,
                diagnostics=typed_loader_diagnostics,
            )
            observation["typed_loader_diagnostics"] = typed_loader_diagnostics
            fact_missing_fields = {}
        else:
            declaration_by_id = {}
            fact_missing_fields = {}
            typed_missing_fields = {}
        if "facts" in path_parts:
            typed_missing_fields = {}
        found_ids = [
            declaration_id for declaration_id in destination["declaration_ids"] if declaration_id in declaration_by_id
        ]
        missing_ids = [
            declaration_id
            for declaration_id in destination["declaration_ids"]
            if declaration_id not in declaration_by_id
        ]
        missing_fields: dict[str, list[str]] = {}
        for declaration_id in found_ids:
            missing = [
                field for field in destination["required_fields"] if field not in declaration_by_id[declaration_id]
            ]
            missing.extend(fact_missing_fields.get(declaration_id, []))
            missing.extend(typed_missing_fields.get(declaration_id, []))
            if destination.get("family") == "bindings":
                missing.extend(_missing_typed_binding_fields(declaration_by_id[declaration_id], destination))
            if missing:
                missing_fields[declaration_id] = sorted(set(missing))
        absorbed_missing = _validate_absorbed_relation_requirements(declaration_by_id, destination)
        for declaration_id, fields in absorbed_missing.items():
            missing_fields.setdefault(declaration_id, []).extend(fields)
            missing_fields[declaration_id] = sorted(set(missing_fields[declaration_id]))
        observation["found_declaration_ids"] = found_ids
        observation["missing_declaration_ids"] = missing_ids
        observation["missing_required_fields"] = missing_fields
        observation["verified"] = bool(observation["toml_status"] == "ok" and not missing_ids and not missing_fields)
        destination_observations.append(observation)

    destination_verified = bool(destination_observations) and all(item["verified"] for item in destination_observations)
    fact_destination_observations = [
        observation
        for destination, observation in zip(placement["destinations"], destination_observations, strict=True)
        if "facts" in {part.casefold() for part in PurePosixPath(destination["path"]).parts}
    ]
    modelo_destination_observations = [
        observation
        for destination, observation in zip(placement["destinations"], destination_observations, strict=True)
        if "modelos" in {part.casefold() for part in PurePosixPath(destination["path"]).parts}
    ]
    fact_destination_verified = bool(fact_destination_observations) and all(
        item["verified"] for item in fact_destination_observations
    )
    modelo_destination_verified = bool(modelo_destination_observations) and all(
        item["verified"] for item in modelo_destination_observations
    )
    unclassified_destination_observations = [
        observation
        for destination, observation in zip(placement["destinations"], destination_observations, strict=True)
        if not ({part.casefold() for part in PurePosixPath(destination["path"]).parts} & {"facts", "modelos"})
    ]
    facts_publication = _facts_publication_scan(
        placement["publication"],
        placement["destinations"],
        destination_observations,
        consumer_resolved=consumer_resolved,
    )
    failure_reasons: list[str] = []
    if not source_ok:
        failure_reasons.append("source_missing_or_unreadable_or_unparsed")
    if not forbidden_symbols_absent:
        failure_reasons.append("python_declaration_symbol_present")
    if not forbidden_literals_absent:
        failure_reasons.append("python_fact_literal_present")
    if not todo_present and not consumer_resolved:
        failure_reasons.append("todo_hole_missing")
    if isinstance(consumer_resolution, dict) and consumer_resolution.get("resolved") is True and not consumer_resolved:
        failure_reasons.append("consumer_resolution_unresolved")
    if (
        isinstance(consumer_resolution, dict)
        and consumer_resolution.get("resolved") is True
        and not registry_query_present
    ):
        failure_reasons.append("registry_query_symbol_missing")
    # A facts-only closure must not inherit the historical Modelo registry
    # placement denominator.  Those observations remain visible below, but
    # only authored governed-fact destinations (and any unclassified
    # destination, which is still a contract error) can block this gate.
    if unclassified_destination_observations:
        destination_gate_verified = destination_verified
    elif fact_destination_observations:
        destination_gate_verified = fact_destination_verified
    else:
        destination_gate_verified = True
    if not destination_gate_verified:
        failure_reasons.append("canonical_destination_missing_or_incomplete")
    if facts_publication["blocking"]:
        failure_reasons.append("facts_publication_unverified")
    verified = bool(
        placement["publication"]["published"] is False
        and source_ok
        and forbidden_symbols_absent
        and forbidden_literals_absent
        and (todo_present or consumer_resolved)
        and destination_gate_verified
        and not facts_publication["blocking"]
    )
    modelo_destinations = [
        destination
        for destination in placement["destinations"]
        if "modelos" in {part.casefold() for part in PurePosixPath(destination["path"]).parts}
    ]
    return {
        "candidate_id": row["id"],
        "item_id": _item_id(row),
        "status": row["status"],
        "kind": PLACEMENT_CLOSURE_KIND,
        "published": placement["publication"]["published"],
        "source_file": source_relative,
        "source_ok": source_ok,
        "forbidden_symbols_absent": forbidden_symbols_absent,
        "forbidden_literals_absent": forbidden_literals_absent,
        "todo_present": todo_present,
        "consumer_resolved": consumer_resolved,
        "consumer_source_file": consumer_source_relative,
        "registry_query_present": registry_query_present,
        "destinations": destination_observations,
        "destination_verified": destination_verified,
        "fact_destination_verified": fact_destination_verified,
        "modelo_destination_verified": modelo_destination_verified,
        "modelo_destination_error_count": sum(not item["verified"] for item in modelo_destination_observations),
        "modelo_destinations_nonblocking": True,
        "destination_gate_verified": destination_gate_verified,
        "facts_publication": facts_publication,
        "modelo_publication": {
            "published": placement["publication"].get("model_registry_published"),
            "destination_count": len(modelo_destinations),
            "destination_verified": modelo_destination_verified,
            "blocking": False,
        },
        "failure_reasons": failure_reasons,
        "verified": verified,
    }


def _authority_claim_scope(authority: dict[str, Any]) -> str:
    """Classify an authority claim by its authored destination family.

    Governed facts and Modelo-registry declarations share the published
    authority artifact, but they are proved by different contracts. A claim
    whose authored destination is under ``_data/registry/.../modelos`` is a
    Modelo placement/exclusion observation, not a facts-registry authority
    claim. Keep this derived from the destination path so the separation does
    not depend on a ledger row identifier or a hardcoded model list.
    """
    authoring_paths = authority.get("authoring_paths", ())
    if isinstance(authoring_paths, (list, tuple)) and any(
        "modelos" in {part.casefold() for part in PurePosixPath(path).parts}
        for path in authoring_paths
        if isinstance(path, str)
    ):
        return "modelo_registry"
    return "facts_registry"


def _authority_scan(
    manifest: dict[str, Any],
    source_scan: dict[str, Any],
) -> dict[str, Any]:
    """Verify claimed migrated/bridge destinations mechanically.

    Indexed authority is proven by the descriptor-admitted SQLite reader, its
    logical generation identity, and the exact typed governed-fact component.
    Legacy closure metadata cannot manufacture proof. Placement closures use
    the same declaration discipline while explicitly recording publication is
    false.
    """
    observations: list[dict[str, Any]] = []
    excluded_modelo_authority_observations: list[dict[str, Any]] = []
    placement_observations: list[dict[str, Any]] = []
    frame_cache: dict[str, tuple[dict[str, Any] | None, str, dict[str, Any]]] = {}
    for row in manifest["candidates"]:
        if row["status"] not in {"migrated", "bridge"}:
            continue
        closure = row["closure"]
        if closure.get("kind") == PLACEMENT_CLOSURE_KIND:
            placement_observations.append(_placement_scan(row, source_scan))
            continue
        authority = closure["authority"]
        authority_scope = _authority_claim_scope(authority)
        artifact_path, artifact_relative = _authority_path(
            authority["artifact"],
            label=f"{row['id']}: closure.authority.artifact",
        )
        authoring_observations: list[dict[str, Any]] = []
        for index, raw_path in enumerate(authority["authoring_paths"]):
            authoring_path, authoring_relative = _authoring_path(
                raw_path,
                label=f"{row['id']}: closure.authority.authoring_paths[{index}]",
            )
            proof = _authoring_fact_proof(
                authoring_path,
                declaration_id=authority["declaration_id"],
                family=authority["family"],
            )
            proof["file"] = authoring_relative
            authoring_observations.append(proof)

        cache_key = artifact_path.as_posix()
        if cache_key not in frame_cache:
            frame_cache[cache_key] = _load_indexed_fact_authority(artifact_path)
        frame, artifact_status, artifact_metadata = frame_cache[cache_key]
        artifact_exists = artifact_path.is_file()
        artifact_actual_digest = artifact_metadata.get("descriptor_sha256")
        identity_digest = artifact_metadata.get("identity_digest")
        identity_digest_proof = bool(
            artifact_status == "ok"
            and isinstance(identity_digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", identity_digest) is not None
        )
        governed_fact = _governed_fact_proof(
            frame,
            declaration_id=authority["declaration_id"],
            family=authority["family"],
        )
        authoring_presence = bool(authoring_observations) and all(
            item["exists"] and item["read_status"] == "ok" for item in authoring_observations
        )
        authoring_fact_proof = authoring_presence and all(item["exact_fact_proof"] for item in authoring_observations)
        legacy_metadata_stale: list[str] = []
        declared_digest = authority.get("digest")
        if declared_digest is not None and declared_digest != artifact_actual_digest:
            legacy_metadata_stale.append("digest")
        declared_provenance = authority.get("provenance_digest")
        if declared_provenance is not None:
            normalized_provenance = declared_provenance.removeprefix("sha256:")
            if normalized_provenance != identity_digest:
                legacy_metadata_stale.append("provenance_digest")
        source_retirement_evidence = bool(closure.get("retirement_evidence"))
        verified = all(
            (
                authoring_presence,
                authoring_fact_proof,
                artifact_exists,
                artifact_status == "ok",
                identity_digest_proof,
                governed_fact["present"],
                authority["parity"] in {"exact", "semantic"},
                authority["duplicate_retired"] is True,
                source_retirement_evidence,
            )
        )
        observation = {
            "candidate_id": row["id"],
            "item_id": _item_id(row),
            "status": row["status"],
            "authority_scope": authority_scope,
            "artifact": artifact_relative,
            "declared_digest": declared_digest,
            "observed_digest": artifact_actual_digest,
            "artifact_status": artifact_status,
            "identity_digest": identity_digest,
            "identity_digest_proof": identity_digest_proof,
            "authoring": authoring_observations,
            "authoring_presence": authoring_presence,
            "authoring_fact_proof": authoring_fact_proof,
            "governed_fact": governed_fact,
            "governed_fact_presence": governed_fact["present"],
            "legacy_metadata_stale": legacy_metadata_stale,
            "parity_declared": authority["parity"],
            "duplicate_retired_declared": authority["duplicate_retired"],
            "source_retirement_evidence": source_retirement_evidence,
            "verified": verified,
        }
        if authority_scope == "modelo_registry":
            # This proof remains intentionally false: a Modelo declaration is
            # not facts-authority proof. It is retained for nonblocking
            # placement/exclusion accounting instead of being counted as a
            # governed-fact authority error.
            observation["nonblocking_exclusion"] = True
            observation["exclusion_reason"] = (
                "authored destination is under the Modelo registry; governed-fact authority proof is not applicable"
            )
            excluded_modelo_authority_observations.append(observation)
        else:
            observations.append(observation)

    failed = sum(not item["verified"] for item in observations)
    placement_failed = sum(not item["verified"] for item in placement_observations)
    facts_publication_claims = [
        item["facts_publication"]
        for item in placement_observations
        if item.get("facts_publication", {}).get("claimed") is True
    ]
    return {
        "observations": sorted(observations, key=lambda item: item["item_id"]),
        "excluded_modelo_authority_observations": sorted(
            excluded_modelo_authority_observations,
            key=lambda item: item["item_id"],
        ),
        "placement_observations": sorted(
            placement_observations,
            key=lambda item: item["item_id"],
        ),
        "counts": {
            "authority_claim_count": len(observations),
            "authoring_presence_count": sum(item["authoring_presence"] for item in observations),
            "authoring_missing_count": sum(not item["authoring_presence"] for item in observations),
            "authoring_fact_proof_count": sum(item["authoring_fact_proof"] for item in observations),
            "payload_digest_proof_count": sum(item["payload_digest_proof"] for item in observations),
            "identity_digest_proof_count": sum(item["identity_digest_proof"] for item in observations),
            "governed_fact_presence_count": sum(item["governed_fact_presence"] for item in observations),
            "legacy_metadata_stale_count": sum(bool(item["legacy_metadata_stale"]) for item in observations),
            "authority_verified_count": sum(item["verified"] for item in observations),
            "authority_integrity_error_count": failed,
            "excluded_modelo_authority_claim_count": len(excluded_modelo_authority_observations),
            "excluded_modelo_authority_verified_count": sum(
                item["verified"] for item in excluded_modelo_authority_observations
            ),
            "excluded_modelo_authority_error_count": sum(
                not item["verified"] for item in excluded_modelo_authority_observations
            ),
            "placement_claim_count": len(placement_observations),
            "placement_verified_count": sum(item["verified"] for item in placement_observations),
            "placement_integrity_error_count": placement_failed,
            "facts_publication_claim_count": len(facts_publication_claims),
            "facts_publication_verified_count": sum(item["verified"] for item in facts_publication_claims),
            "facts_publication_integrity_error_count": sum(not item["verified"] for item in facts_publication_claims),
        },
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ManifestError("manifest root must be an object")
    missing = sorted(REQUIRED_TOP_LEVEL - payload.keys())
    if missing:
        raise ManifestError(f"manifest missing top-level keys: {', '.join(missing)}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(f"unsupported schema_version {payload.get('schema_version')!r}; expected {SCHEMA_VERSION}")
    if payload.get("campaign") != "fact-relocation":
        raise ManifestError("manifest campaign must be 'fact-relocation'")
    if not isinstance(payload["scope"], dict):
        raise ManifestError("scope must be an object")
    baseline = payload.get("baseline")
    if not isinstance(baseline, dict):
        raise ManifestError("baseline must be an object")
    grouped_findings = baseline.get("grouped_findings")
    if not isinstance(grouped_findings, int) or grouped_findings < 1:
        raise ManifestError("baseline.grouped_findings must be a positive integer")
    _validate_live_universe_reconciliation(baseline)
    source_relocations = _source_relocations(payload.get("source_relocations"))
    if not isinstance(payload["source_reports"], list) or not payload["source_reports"]:
        raise ManifestError("source_reports must be a non-empty list")
    if not isinstance(payload["exclusions"], list):
        raise ManifestError("exclusions must be a list")
    if not isinstance(payload["candidates"], list):
        raise ManifestError("candidates must be a list")
    dispositions = payload.get("discovery_dispositions", [])
    if not isinstance(dispositions, list):
        raise ManifestError("discovery_dispositions must be a list")
    disposition_ids: set[str] = set()
    for index, disposition in enumerate(dispositions):
        label = f"discovery_dispositions[{index}]"
        if not isinstance(disposition, dict):
            raise ManifestError(f"{label} must be an object")
        candidate_id = disposition.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.startswith("fact-discovery:"):
            raise ManifestError(f"{label}.candidate_id is invalid")
        if candidate_id in disposition_ids:
            raise ManifestError(f"duplicate discovery disposition: {candidate_id}")
        disposition_ids.add(candidate_id)
        if disposition.get("disposition") not in {
            "registry_consumer",
            "relocated",
            "retained_mechanic",
            "not_a_fact",
        }:
            raise ManifestError(f"{label}.disposition is invalid")
        reason = disposition.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ManifestError(f"{label}.reason is required")
    _validate_ownership(payload["ownership"], payload["candidates"])

    ids: set[str] = set()
    for row in payload["candidates"]:
        _validate_candidate(
            row,
            ids,
            payload["ownership"],
            source_relocations,
        )
    if not payload["candidates"]:
        raise ManifestError("candidate ledger must not be empty")
    _validate_identity(payload["candidates"])
    return payload


def _validate_hash(value: Any, *, label: str) -> None:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise ManifestError(f"{label}: expected sha256:<64 lowercase hex> digest")


def _validate_live_universe_reconciliation(baseline: dict[str, Any]) -> None:
    record = baseline.get("live_universe_reconciliation")
    if record is None:
        return
    if not isinstance(record, dict):
        raise ManifestError("baseline.live_universe_reconciliation must be an object")
    historical = record.get("historical_audit_eligible_python_files")
    live_expected = record.get("live_expected_eligible_python_files")
    delta_count = record.get("delta_count")
    delta_paths = record.get("delta_paths")
    if historical != baseline.get("audit_eligible_python_files"):
        raise ManifestError("live universe reconciliation historical count disagrees with baseline")
    if not isinstance(live_expected, int) or live_expected < 1:
        raise ManifestError("live universe reconciliation live expected count must be positive")
    if not isinstance(delta_count, int) or delta_count < 0:
        raise ManifestError("live universe reconciliation delta_count must be non-negative")
    if not isinstance(delta_paths, list) or len(delta_paths) != delta_count:
        raise ManifestError("live universe reconciliation delta_paths must match delta_count")
    normalized_paths: set[str] = set()
    for index, value in enumerate(delta_paths):
        _, relative = _source_path(
            value,
            label=f"baseline.live_universe_reconciliation.delta_paths[{index}]",
        )
        if relative in normalized_paths:
            raise ManifestError("live universe reconciliation delta_paths must be unique")
        normalized_paths.add(relative)
    reason = record.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ManifestError("live universe reconciliation reason is required")
    for field in ("historical_snapshot",):
        snapshot = record.get(field)
        if not isinstance(snapshot, dict):
            raise ManifestError(f"live universe reconciliation {field} must be an object")
        for required in ("date", "timestamp", "evidence"):
            if not isinstance(snapshot.get(required), str) or not snapshot[required].strip():
                raise ManifestError(f"live universe reconciliation {field}.{required} is required")
    recorded_at = record.get("recorded_at")
    if not isinstance(recorded_at, str) or not recorded_at.strip():
        raise ManifestError("live universe reconciliation recorded_at is required")
    if not isinstance(record.get("delta_adds_candidate"), bool):
        raise ManifestError("live universe reconciliation delta_adds_candidate must be boolean")
    classification = record.get("delta_classification")
    if not isinstance(classification, dict):
        raise ManifestError("live universe reconciliation delta_classification must be an object")
    for field in (
        "broad_prefilter_paths_present",
        "direct_model_legal_filename_paths_present",
        "canonical_candidate_paths_present",
    ):
        if not isinstance(classification.get(field), int) or classification[field] < 0:
            raise ManifestError(f"live universe reconciliation {field} must be non-negative")
    if not isinstance(classification.get("basis"), str) or not classification["basis"].strip():
        raise ManifestError("live universe reconciliation classification basis is required")


def _validate_evidence_records(value: Any, *, label: str) -> None:
    if not isinstance(value, list) or not value:
        raise ManifestError(f"{label} must be a non-empty list")
    for index, item in enumerate(value):
        entry_label = f"{label}[{index}]"
        if not isinstance(item, dict):
            raise ManifestError(f"{entry_label} must be an object")
        if not isinstance(item.get("kind"), str) or not item["kind"].strip():
            raise ManifestError(f"{entry_label}.kind is required")
        if not isinstance(item.get("ref"), str) or not item["ref"].strip():
            raise ManifestError(f"{entry_label}.ref is required")


def _validate_source_hashes(candidate_id: str, closure: dict[str, Any]) -> None:
    if "source_hashes" not in closure:
        return
    source_hashes = closure["source_hashes"]
    if not isinstance(source_hashes, list) or not source_hashes:
        raise ManifestError(f"{candidate_id}: closure.source_hashes must be a non-empty list")
    seen: set[str] = set()
    for index, source_hash in enumerate(source_hashes):
        label = f"{candidate_id}: closure.source_hashes[{index}]"
        if not isinstance(source_hash, dict):
            raise ManifestError(f"{label} must be an object")
        if not isinstance(source_hash.get("path"), str) or not source_hash["path"].strip():
            raise ManifestError(f"{label}.path is required")
        _, relative = _source_path(source_hash["path"], label=label)
        if relative in seen:
            raise ManifestError(f"{candidate_id}: duplicate closure source hash path {relative}")
        seen.add(relative)
        _validate_hash(source_hash.get("sha256"), label=f"{label}.sha256")


def _validate_authority(candidate_id: str, authority: Any) -> None:
    label = f"{candidate_id}: closure.authority"
    if not isinstance(authority, dict):
        raise ManifestError(f"{label} must be an object")
    missing = sorted(AUTHORITY_REQUIRED_FIELDS - authority.keys())
    if missing:
        raise ManifestError(f"{label} missing fields: {', '.join(missing)}")
    if not isinstance(authority.get("artifact"), str) or not authority["artifact"].strip():
        raise ManifestError(f"{label}.artifact is required")
    _authority_path(authority["artifact"], label=f"{label}.artifact")
    # These fields belong to the pre-v4 manifest dialect.  Accept them as
    # descriptive metadata when present, but never require or trust them as
    # authority proof: v4 proves the frame through its typed decoder and
    # payload digest below.
    for field in AUTHORITY_LEGACY_FIELDS:
        if field not in authority:
            continue
        value = authority[field]
        if field in {"compiled", "published"}:
            if type(value) is not bool:
                raise ManifestError(f"{label}.{field} must be boolean when present")
        elif not isinstance(value, str) or not value.strip():
            raise ManifestError(f"{label}.{field} must be a non-empty string when present")
    for field in ("model", "revision", "family", "declaration_id", "consumer"):
        if not isinstance(authority.get(field), str) or not authority[field].strip():
            raise ManifestError(f"{label}.{field} is required")
    if authority.get("parity") not in {"exact", "semantic"}:
        raise ManifestError(f"{label}.parity must be exact or semantic")
    if authority.get("duplicate_retired") is not True:
        raise ManifestError(f"{label}.duplicate_retired must be true")
    authoring_paths = authority.get("authoring_paths")
    if not isinstance(authoring_paths, list) or not authoring_paths:
        raise ManifestError(f"{label}.authoring_paths must be a non-empty list")
    seen: set[str] = set()
    for index, authoring_path in enumerate(authoring_paths):
        entry_label = f"{label}.authoring_paths[{index}]"
        _, relative = _authoring_path(authoring_path, label=entry_label)
        if relative in seen:
            raise ManifestError(f"{label}: duplicate authoring path {relative}")
        seen.add(relative)


def _validate_consumer_resolution(candidate_id: str, placement: dict[str, Any]) -> None:
    """Validate a resolved consumer seam used after its temporary TODO is removed."""
    label = f"{candidate_id}: closure.placement.consumer_resolution"
    resolution = placement.get("consumer_resolution")
    if not isinstance(resolution, dict):
        raise ManifestError(f"{label} is required when closure.placement.todo_text is absent")
    for field in ("kind", "source_file", "seam"):
        if not isinstance(resolution.get(field), str) or not resolution[field].strip():
            raise ManifestError(f"{label}.{field} is required")
    if resolution.get("resolved") is not True:
        raise ManifestError(f"{label}.resolved must be true")
    _source_path(
        placement.get("source_file"),
        label=f"{candidate_id}: closure.placement.source_file",
    )
    _source_path(
        resolution["source_file"],
        label=f"{label}.source_file",
    )
    _validate_evidence_records(resolution.get("evidence"), label=f"{label}.evidence")


def _validate_placement(candidate_id: str, closure: dict[str, Any]) -> None:
    """Validate an unpublished, mechanically observable placement closure."""
    label = f"{candidate_id}: closure.placement"
    placement = closure.get("placement")
    if not isinstance(placement, dict):
        raise ManifestError(f"{label} must be an object")
    missing = sorted(PLACEMENT_REQUIRED_FIELDS - placement.keys())
    if missing:
        raise ManifestError(f"{label} missing fields: {', '.join(missing)}")
    if placement.get("schema") != "registry-toml":
        raise ManifestError(f"{label}.schema must be registry-toml")

    source_file = placement.get("source_file")
    source_path, source_relative = _source_path(
        source_file,
        label=f"{label}.source_file",
    )
    if not source_path.is_file():
        raise ManifestError(f"{label}.source_file is missing: {source_relative}")
    todo_text = placement.get("todo_text")
    if todo_text is not None:
        if not isinstance(todo_text, str) or not todo_text.strip():
            raise ManifestError(f"{label}.todo_text must be a non-empty string when present")
    else:
        _validate_consumer_resolution(candidate_id, placement)

    for field in ("forbidden_symbols", "forbidden_literals"):
        values = placement.get(field)
        if not isinstance(values, list) or not values:
            raise ManifestError(f"{label}.{field} must be a non-empty list")
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ManifestError(f"{label}.{field} must contain non-empty strings")
        if len(values) != len(set(values)):
            raise ManifestError(f"{label}.{field} must not contain duplicates")

    publication = placement.get("publication")
    if not isinstance(publication, dict) or publication.get("published") is not False:
        raise ManifestError(f"{label}.publication.published must be false")
    facts_publication = publication.get("facts")
    if facts_publication is not None:
        if not isinstance(facts_publication, dict):
            raise ManifestError(f"{label}.publication.facts must be an object when present")
        if type(facts_publication.get("published")) is not bool:
            raise ManifestError(f"{label}.publication.facts.published must be boolean")
        if facts_publication.get("published") is True:
            artifact = facts_publication.get("artifact")
            if not isinstance(artifact, str) or not artifact.strip():
                raise ManifestError(f"{label}.publication.facts.artifact is required when published")
            _authority_path(
                artifact,
                label=f"{label}.publication.facts.artifact",
            )
            declaration_ids = facts_publication.get("declaration_ids")
            if not isinstance(declaration_ids, list) or not declaration_ids:
                raise ManifestError(
                    f"{label}.publication.facts.declaration_ids must be non-empty when published",
                )
            if any(not isinstance(value, str) or not value.strip() for value in declaration_ids):
                raise ManifestError(
                    f"{label}.publication.facts.declaration_ids must contain non-empty strings",
                )
            if len(declaration_ids) != len(set(declaration_ids)):
                raise ManifestError(f"{label}.publication.facts.declaration_ids must be unique")
    model_registry_published = publication.get("model_registry_published")
    if model_registry_published is not None and type(model_registry_published) is not bool:
        raise ManifestError(f"{label}.publication.model_registry_published must be boolean when present")

    destinations = placement.get("destinations")
    if not isinstance(destinations, list) or not destinations:
        raise ManifestError(f"{label}.destinations must be a non-empty list")
    destination_paths: set[str] = set()
    declaration_ids: set[str] = set()
    for index, destination in enumerate(destinations):
        destination_label = f"{label}.destinations[{index}]"
        if not isinstance(destination, dict):
            raise ManifestError(f"{destination_label} must be an object")
        missing = sorted(PLACEMENT_DESTINATION_REQUIRED_FIELDS - destination.keys())
        if missing:
            raise ManifestError(f"{destination_label} missing fields: {', '.join(missing)}")
        _, relative = _authoring_path(
            destination.get("path"),
            label=f"{destination_label}.path",
        )
        if relative == source_relative:
            raise ManifestError(f"{destination_label}.path must not be the Python source")
        if relative in destination_paths:
            raise ManifestError(f"{label}: duplicate destination path {relative}")
        destination_paths.add(relative)
        revision = destination.get("revision")
        family = destination.get("family")
        if not isinstance(revision, str) or not revision.strip():
            raise ManifestError(f"{destination_label}.revision is required")
        if not isinstance(family, str) or not family.strip():
            raise ManifestError(f"{destination_label}.family is required")
        path_parts = {part.casefold() for part in PurePosixPath(relative).parts}
        if revision.casefold() not in path_parts:
            raise ManifestError(f"{destination_label}.revision must be represented in the canonical path")
        if family.casefold() not in path_parts:
            raise ManifestError(f"{destination_label}.family must be represented in the canonical path")
        ids = destination.get("declaration_ids")
        if not isinstance(ids, list) or not ids:
            raise ManifestError(f"{destination_label}.declaration_ids must be non-empty")
        if any(not isinstance(value, str) or not value.strip() for value in ids):
            raise ManifestError(f"{destination_label}.declaration_ids must contain non-empty strings")
        fields = destination.get("required_fields")
        if not isinstance(fields, list) or not fields:
            raise ManifestError(f"{destination_label}.required_fields must be non-empty")
        if any(not isinstance(value, str) or not value.strip() for value in fields):
            raise ManifestError(f"{destination_label}.required_fields must contain non-empty strings")
        semantic_requirements = destination.get("semantic_requirements")
        if semantic_requirements is not None:
            if not isinstance(semantic_requirements, dict) or not semantic_requirements:
                raise ManifestError(f"{destination_label}.semantic_requirements must be a non-empty object")
            unknown_requirement_ids = sorted(set(semantic_requirements) - set(ids))
            if unknown_requirement_ids:
                raise ManifestError(
                    f"{destination_label}.semantic_requirements reference undeclared IDs: "
                    + ", ".join(unknown_requirement_ids),
                )
            if any(not isinstance(value, dict) for value in semantic_requirements.values()):
                raise ManifestError(f"{destination_label}.semantic_requirements values must be objects")
        absorbed_relations = destination.get("absorbed_relations")
        if absorbed_relations is not None:
            if family != "bindings":
                raise ManifestError(f"{destination_label}.absorbed_relations requires family=bindings")
            if not isinstance(absorbed_relations, list) or not absorbed_relations:
                raise ManifestError(f"{destination_label}.absorbed_relations must be a non-empty list")
            for relation_index, relation in enumerate(absorbed_relations):
                relation_label = f"{destination_label}.absorbed_relations[{relation_index}]"
                if not isinstance(relation, dict):
                    raise ManifestError(f"{relation_label} must be an object")
                for field in ("legacy_path", "legacy_declaration_id", "canonical_declaration_id", "requirements"):
                    if field not in relation:
                        raise ManifestError(f"{relation_label}.{field} is required")
                if not isinstance(relation["legacy_path"], str) or not relation["legacy_path"].strip():
                    raise ManifestError(f"{relation_label}.legacy_path is required")
                if (
                    not isinstance(relation["legacy_declaration_id"], str)
                    or not relation["legacy_declaration_id"].strip()
                ):
                    raise ManifestError(f"{relation_label}.legacy_declaration_id is required")
                canonical_id = relation["canonical_declaration_id"]
                if canonical_id not in ids:
                    raise ManifestError(f"{relation_label}.canonical_declaration_id must be declared")
                if not isinstance(relation["requirements"], dict) or not relation["requirements"]:
                    raise ManifestError(f"{relation_label}.requirements must be a non-empty object")
        duplicate_ids = declaration_ids.intersection(ids)
        if duplicate_ids:
            raise ManifestError(f"{label}: duplicate declaration IDs: {', '.join(sorted(duplicate_ids))}")
        declaration_ids.update(ids)


def _validate_ownership(ownership: Any, candidates: Any) -> None:
    if not isinstance(ownership, dict):
        raise ManifestError("ownership must be an object")
    declared_lanes = ownership.get("allowed_lanes")
    if (
        not isinstance(declared_lanes, list)
        or set(declared_lanes) != ALLOWED_LANES
        or len(declared_lanes) != len(ALLOWED_LANES)
    ):
        raise ManifestError("ownership.allowed_lanes must list each of the six named lanes exactly once")
    defaults = ownership.get("default_by_category")
    overrides = ownership.get("overrides", {})
    if not isinstance(defaults, dict):
        raise ManifestError("ownership.default_by_category must be an object")
    if not isinstance(overrides, dict):
        raise ManifestError("ownership.overrides must be an object")
    for category in ALLOWED_CATEGORIES:
        owner = defaults.get(category)
        if owner not in ALLOWED_LANES or owner == "lane-6-lun-max":
            raise ManifestError(f"ownership default for {category!r} must be one of the five declaration lanes")
    candidate_ids = {row.get("id") for row in candidates if isinstance(row, dict)}
    unknown_overrides = sorted(set(overrides) - candidate_ids)
    if unknown_overrides:
        raise ManifestError("ownership overrides reference unknown candidates: " + ", ".join(unknown_overrides))
    for candidate_id, owner in overrides.items():
        if owner not in ALLOWED_LANES or owner == "lane-6-lun-max":
            raise ManifestError(f"ownership override for {candidate_id!r} must be one of the five declaration lanes")


def _owner_for(row: dict[str, Any], ownership: dict[str, Any]) -> str:
    return ownership.get("overrides", {}).get(row["id"], ownership["default_by_category"][row["category"]])


def _identity_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Return fields that identify a declaration independently of its status."""
    evidence = sorted(
        (
            {
                "file": item.get("stable_file", item["file"]),
                # A legacy stable_anchor is retained only when replacing an
                # explanatory prose anchor with a canonical AST fingerprint.
                # It preserves the pre-enrichment FR identity while the live
                # evidence and integrity checks use the new fingerprint.
                "anchor": item.get("stable_anchor", item["anchor"]),
            }
            for item in row["evidence"]
        ),
        key=lambda item: (item["file"], item["anchor"]),
    )
    return {
        "candidate_id": row["id"],
        "category": row["category"],
        "evidence": evidence,
        "target": row["target"],
    }


def _item_id(row: dict[str, Any]) -> str:
    canonical = json.dumps(
        _identity_payload(row),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "FR-" + hashlib.sha256(b"fact-relocation-signal-v1\0" + canonical).hexdigest()[:20]


def _signal_digest(signal: dict[str, Any]) -> str:
    canonical_signal = {key: value for key, value in signal.items() if key not in {"manifest", "signal_digest"}}
    canonical = json.dumps(
        canonical_signal,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _display_path(path: Path) -> str:
    """Use a stable repository-relative path when the manifest is in-repo."""
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _validate_identity(candidates: list[dict[str, Any]]) -> None:
    identities: dict[str, str] = {}
    for row in candidates:
        item_id = _item_id(row)
        canonical = json.dumps(
            _identity_payload(row),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        previous = identities.get(item_id)
        if previous is not None and previous != canonical:
            raise ManifestError(f"identity collision for {item_id}: declaration payloads differ")
        if previous is not None:
            raise ManifestError(f"duplicate stable identity: {item_id}")
        identities[item_id] = canonical


def _validate_candidate(
    row: Any,
    ids: set[str],
    ownership: dict[str, Any],
    relocations: dict[str, dict[str, str]],
) -> None:
    if not isinstance(row, dict):
        raise ManifestError("each candidate must be an object")
    missing = sorted(REQUIRED_CANDIDATE - row.keys())
    if missing:
        raise ManifestError(f"candidate missing keys: {', '.join(missing)}")

    candidate_id = row["id"]
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ManifestError("candidate id must be a non-empty string")
    if candidate_id in ids:
        raise ManifestError(f"duplicate candidate id: {candidate_id}")
    ids.add(candidate_id)

    category = row["category"]
    if category not in ALLOWED_CATEGORIES:
        raise ManifestError(f"{candidate_id}: category must be one of {', '.join(sorted(ALLOWED_CATEGORIES))}")
    status = row["status"]
    if status not in ALLOWED_STATUSES:
        raise ManifestError(f"{candidate_id}: status must be one of {', '.join(sorted(ALLOWED_STATUSES))}")
    owner = _owner_for(row, ownership)
    if owner not in ALLOWED_LANES or owner == "lane-6-lun-max":
        raise ManifestError(f"{candidate_id}: owner must be exactly one valid declaration lane")
    if not isinstance(row["target"], str) or not row["target"].strip():
        raise ManifestError(f"{candidate_id}: target must be a non-empty string")

    evidence = row["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ManifestError(f"{candidate_id}: evidence must be a non-empty list")
    for item in evidence:
        if not isinstance(item, dict):
            raise ManifestError(f"{candidate_id}: each evidence item must be an object")
        if not isinstance(item.get("file"), str) or not item["file"].strip():
            raise ManifestError(f"{candidate_id}: evidence file is required")
        if not isinstance(item.get("anchor"), str) or not item["anchor"].strip():
            raise ManifestError(f"{candidate_id}: evidence anchor is required")
        _, evidence_relative = _source_path(item["file"], label=f"{candidate_id}: evidence file")
        if "stable_anchor" in item and (
            not isinstance(item["stable_anchor"], str) or not item["stable_anchor"].strip()
        ):
            raise ManifestError(f"{candidate_id}: stable_anchor must be a non-empty string")
        if "stable_file" in item:
            if not isinstance(item["stable_file"], str) or not item["stable_file"].strip():
                raise ManifestError(f"{candidate_id}: stable_file must be a non-empty string")
            _source_path(
                item["stable_file"],
                label=f"{candidate_id}: stable_file",
            )
        if item["anchor"].startswith(("ast:", "ast-set:")):
            identities = _parse_ast_anchor(
                item["anchor"],
                label=f"{candidate_id}: evidence anchor",
                relocations=relocations,
            )
            if any(identity["file"] != evidence_relative for identity in identities):
                raise ManifestError(f"{candidate_id}: AST evidence fingerprint file differs from evidence file")

    # A closure is explicit.  ``open`` rows may have no closure because they
    # are the signal.  Blocking dispositions remain blockers even when they
    # have a recorded reason; only a valid closure disposition can leave the
    # clean-zero invariant.
    if status != ACTIONABLE_STATUS:
        closure = row.get("closure")
        if not isinstance(closure, dict):
            raise ManifestError(f"{candidate_id}: closed rows require a closure object")
        if not isinstance(closure.get("reason"), str) or not closure["reason"].strip():
            raise ManifestError(f"{candidate_id}: closure.reason is required")
        evidence = closure.get("evidence")
        _validate_evidence_records(evidence, label=f"{candidate_id}: closure.evidence")
        _validate_source_hashes(candidate_id, closure)
        if status == "retained":
            if closure.get("kind") not in RETAIN_KINDS:
                raise ManifestError(f"{candidate_id}: retained rows require a non-fact closure kind")
            if closure.get("contains_model_fact") is not False:
                raise ManifestError(f"{candidate_id}: retained rows must assert contains_model_fact=false")
        elif status == "bridge":
            if not closure.get("source_hashes"):
                raise ManifestError(f"{candidate_id}: bridge rows require source_hashes")
            _validate_authority(candidate_id, closure.get("authority"))
            source_disposition = closure.get("source_disposition")
            if source_disposition not in {"unchanged", "bridged"}:
                raise ManifestError(f"{candidate_id}: bridge rows require source_disposition=unchanged|bridged")
            retirement_evidence = closure.get("retirement_evidence")
            _validate_evidence_records(
                retirement_evidence,
                label=f"{candidate_id}: retirement_evidence",
            )
        elif status == "migrated":
            if not closure.get("source_hashes"):
                raise ManifestError(f"{candidate_id}: migrated rows require source_hashes")
            source_disposition = closure.get("source_disposition")
            if source_disposition not in {"removed", "bridged"}:
                raise ManifestError(f"{candidate_id}: migrated rows require source_disposition=removed|bridged")
            retirement_evidence = closure.get("retirement_evidence")
            _validate_evidence_records(
                retirement_evidence,
                label=f"{candidate_id}: retirement_evidence",
            )
            if closure.get("kind") == PLACEMENT_CLOSURE_KIND:
                _validate_placement(candidate_id, closure)
            else:
                _validate_authority(candidate_id, closure.get("authority"))
        elif status in {"deferred", "unsupported"}:
            if not isinstance(closure.get("next_disposition"), str) or not closure["next_disposition"].strip():
                raise ManifestError(f"{candidate_id}: {status} rows require next_disposition")
    elif "closure" in row:
        closure = row["closure"]
        if not isinstance(closure, dict):
            raise ManifestError(f"{candidate_id}: closure must be an object when present")
        if "source_hashes" in closure:
            _validate_source_hashes(candidate_id, closure)


def _consumer_publication_only_blocker(item: Any) -> bool:
    """Identify the one authored-only blocker that is not row work."""
    if not isinstance(item, dict):
        return False
    blockers = item.get("blockers")
    return (
        item.get("authored_presence") is True
        and item.get("bundled_authority_presence") is False
        and isinstance(blockers, list)
        and blockers == ["bundled_authority_fact_missing"]
    )


def _consumer_tracked_row_ids(consumer_fact_scan: dict[str, Any]) -> set[str]:
    """Keep every associated row except mechanically publication-only blockers."""
    tracked: set[str] = set()
    blockers = consumer_fact_scan.get("blockers", [])
    if not isinstance(blockers, (list, tuple)):
        return tracked
    for item in blockers:
        if not isinstance(item, dict) or _consumer_publication_only_blocker(item):
            continue
        row_ids = item.get("associated_row_ids", [])
        if not isinstance(row_ids, (list, tuple, set, frozenset)):
            continue
        tracked.update(row_id for row_id in row_ids if isinstance(row_id, str))
    return tracked


def _counts(
    manifest: dict[str, Any],
    source_scan: dict[str, Any],
    authority_scan: dict[str, Any],
    universe_scan: dict[str, Any],
    universe_reconciliation: dict[str, Any],
    enrichment: dict[str, Any],
    todo_debt: dict[str, Any],
    discovery_scan: dict[str, Any],
    consumer_fact_scan: dict[str, Any],
    facts_publication_signal: dict[str, Any],
) -> dict[str, Any]:
    candidates = manifest["candidates"]
    actionable = [row for row in candidates if row["status"] in BLOCKING_STATUSES]
    failed_placement_ids = {
        item["candidate_id"] for item in authority_scan["placement_observations"] if not item["verified"]
    }
    todo_row_ids = {
        candidate_id for occurrence in todo_debt["occurrences"] for candidate_id in occurrence["candidate_ids"]
    }
    consumer_row_ids = _consumer_tracked_row_ids(consumer_fact_scan)
    tracked_row_work_ids = sorted(
        {row["id"] for row in actionable} | failed_placement_ids | todo_row_ids | consumer_row_ids
    )
    tracked_row_work_id_set = set(tracked_row_work_ids)
    unassociated_todo_count = sum(not occurrence["candidate_ids"] for occurrence in todo_debt["occurrences"])
    clean_closed = [row for row in candidates if row["status"] in CLOSED_STATUSES]
    status_counts = Counter(row["status"] for row in candidates)
    category_counts = Counter(row["category"] for row in actionable)
    all_category_counts = Counter(row["category"] for row in candidates)
    by_lane = Counter(_owner_for(row, manifest["ownership"]) for row in actionable)
    declared_actionable_files = sorted({item["file"] for row in actionable for item in row["evidence"]})
    files = sorted(
        {item["file"] for row in candidates if row["id"] in tracked_row_work_id_set for item in row["evidence"]}
    )
    consumer_files = sorted(
        {
            callsite["file"]
            for item in consumer_fact_scan.get("blockers", [])
            for callsite in item.get("source_call_sites", [])
            if isinstance(callsite, dict) and isinstance(callsite.get("file"), str)
        }
    )
    files = sorted(set(files) | set(consumer_files))
    source_counts = source_scan["counts"]
    authority_counts = authority_scan["counts"]
    universe_counts = universe_scan["counts"]
    discovery_counts = discovery_scan["counts"]
    consumer_counts = consumer_fact_scan["counts"]
    facts_publication_counts = facts_publication_signal.get("counts", {})
    fact_accounting_error_count = facts_publication_counts.get("fact_accounting_error_count", 0)
    if type(fact_accounting_error_count) is not int or fact_accounting_error_count < 0:
        # A malformed auxiliary signal must fail closed rather than silently
        # disappearing from the campaign gates.
        fact_accounting_error_count = 1
    identity_ids = [_item_id(row) for row in candidates]
    identity_count = len(identity_ids)
    duplicate_identity_count = identity_count - len(set(identity_ids))
    owners = [_owner_for(row, manifest["ownership"]) for row in candidates]
    unowned_count = sum(owner not in ALLOWED_LANES for owner in owners)
    baseline_expected = manifest.get("baseline", {}).get("grouped_findings")
    coverage_gap_count = (
        max(int(baseline_expected) - len(candidates), 0)
        if isinstance(baseline_expected, int) and baseline_expected >= 0
        else 0
    )
    coverage_overrun_count = (
        max(len(candidates) - int(baseline_expected), 0)
        if isinstance(baseline_expected, int) and baseline_expected >= 0
        else 0
    )
    unknown_count = (
        source_counts["source_missing_count"]
        + source_counts["source_anchor_unresolved_count"]
        + source_counts["source_parse_error_count"]
        + universe_counts["universe_parse_failures"]
        + universe_counts["universe_read_failures"]
    )
    universe_coverage_error_count = universe_reconciliation["reconciliation_error_count"]
    integrity_error_count = (
        source_counts["source_integrity_error_count"]
        + authority_counts["authority_integrity_error_count"]
        + authority_counts.get("placement_integrity_error_count", 0)
        + coverage_gap_count
        + coverage_overrun_count
        + universe_coverage_error_count
        + unowned_count
        + duplicate_identity_count
        + discovery_counts["discovery_stale_disposition_count"]
        + consumer_counts["consumer_fact_blocker_count"]
        + consumer_counts["consumer_fact_error_count"]
        + fact_accounting_error_count
    )
    ledger_coverage_complete = coverage_gap_count == 0 and coverage_overrun_count == 0
    frozen_coverage_complete = universe_reconciliation["complete"]
    campaign_work_remaining_count = (
        len(tracked_row_work_ids)
        + unassociated_todo_count
        + discovery_counts["discovery_blocking_count"]
        + consumer_counts["consumer_fact_blocker_count"]
        + consumer_counts["consumer_fact_error_count"]
    )
    accounting_error_count = (
        source_counts["source_integrity_error_count"]
        + coverage_gap_count
        + coverage_overrun_count
        + universe_coverage_error_count
        + unowned_count
        + duplicate_identity_count
        + discovery_counts["discovery_stale_disposition_count"]
        + consumer_counts["consumer_fact_error_count"]
        + fact_accounting_error_count
    )
    publication_blocker_count = (
        authority_counts["authority_integrity_error_count"]
        + consumer_counts["consumer_fact_blocker_count"]
        + fact_accounting_error_count
    )
    zero_target = (
        campaign_work_remaining_count == 0
        and integrity_error_count == 0
        and unknown_count == 0
        and ledger_coverage_complete
        and frozen_coverage_complete
    )
    return {
        "audit_hit_count": manifest.get("baseline", {}).get("direct_model_legal_filename_files", 0),
        "candidate_count": len(candidates),
        "total_ledger_rows": len(candidates),
        "actionable_count": len(actionable),
        "actionable_undeclared_fact_count": len(actionable),
        "tracked_row_work_count": len(tracked_row_work_ids),
        "tracked_row_work_ids": tracked_row_work_ids,
        "unassociated_todo_count": unassociated_todo_count,
        "open_count": sum(row["status"] == ACTIONABLE_STATUS for row in candidates),
        "deferred_count": status_counts.get("deferred", 0),
        "unsupported_count": status_counts.get("unsupported", 0),
        "closed_count": len(clean_closed),
        "identity_count": identity_count,
        "unknown_count": unknown_count,
        "unowned_count": unowned_count,
        "duplicate_identity_count": duplicate_identity_count,
        "coverage_expected_count": baseline_expected,
        "coverage_observed_count": len(candidates),
        "coverage_gap_count": coverage_gap_count,
        "coverage_overrun_count": coverage_overrun_count,
        "ledger_coverage_complete": ledger_coverage_complete,
        "universe_expected_count": universe_reconciliation["expected_count"],
        "universe_historical_count": universe_reconciliation["historical_count"],
        "universe_count": universe_reconciliation["actual_count"],
        "universe_count_drift": universe_reconciliation["count_drift"],
        "universe_delta_paths_missing_count": universe_reconciliation["delta_paths_missing_count"],
        "universe_delta_candidate_path_count": universe_reconciliation["delta_candidate_path_count"],
        "universe_delta_candidate_flag_drift": universe_reconciliation["delta_candidate_flag_drift"],
        "universe_parse_count": universe_counts["universe_parse_count"],
        "universe_parse_failures": universe_counts["universe_parse_failures"],
        "universe_read_failures": universe_counts["universe_read_failures"],
        "universe_enumeration_failures": universe_counts["universe_enumeration_failures"],
        "universe_path_digest": universe_counts["universe_path_digest"],
        "universe_coverage_error_count": universe_coverage_error_count,
        "universe_coverage_complete": frozen_coverage_complete,
        "symbol_enrichment_status": enrichment["status"],
        "symbol_enrichment_declaration_count": enrichment.get("total_declarations", 0),
        "symbol_enrichment_disposition_mismatch_count": len(enrichment.get("disposition_mismatches", [])),
        "symbol_enrichment_scope_only_count": enrichment.get("scope_only_count", 0),
        "broad_prefilter_reconciliation": universe_reconciliation["broad_prefilter"],
        "direct_model_legal_filename_reconciliation": universe_reconciliation["direct_model_legal_filename"],
        "integrity_error_count": integrity_error_count,
        "campaign_work_remaining_count": campaign_work_remaining_count,
        "accounting_error_count": accounting_error_count,
        "publication_blocker_count": publication_blocker_count,
        "fact_accounting_error_count": fact_accounting_error_count,
        "source_integrity_ok": source_counts["source_integrity_error_count"] == 0,
        "authority_integrity_ok": authority_counts["authority_integrity_error_count"] == 0,
        "consumer_fact_integrity_ok": consumer_counts["consumer_fact_blocker_count"] == 0
        and consumer_counts["consumer_fact_error_count"] == 0,
        "placement_integrity_ok": authority_counts.get("placement_integrity_error_count", 0) == 0,
        "coverage_complete": ledger_coverage_complete and frozen_coverage_complete,
        # TODO debt is an orthogonal seam metric. It must not alter the
        # ledger's actionability, integrity, or zero-target contract.
        "todo_total_count": todo_debt["total_count"],
        "todo_open_count": todo_debt["open_count"],
        "todo_resolved_count": todo_debt["resolved_count"],
        "todo_migrated_rows_with_unresolved_count": todo_debt["migrated_rows_with_unresolved_count"],
        "todo_migrated_rows_with_open_marker_count": todo_debt["migrated_rows_with_unresolved_count"],
        "todo_resolved_delta": todo_debt["baseline"]["resolved_delta"],
        "zero_target": zero_target,
        "by_lane": {lane: by_lane.get(lane, 0) for lane in sorted(ALLOWED_LANES)},
        "status_counts": {key: status_counts.get(key, 0) for key in sorted(ALLOWED_STATUSES)},
        "actionable_by_category": {key: category_counts.get(key, 0) for key in sorted(ALLOWED_CATEGORIES)},
        "ledger_by_category": {key: all_category_counts.get(key, 0) for key in sorted(ALLOWED_CATEGORIES)},
        "actionable_files": files,
        "declared_actionable_files": declared_actionable_files,
        "consumer_fact_blocker_files": consumer_files,
        **consumer_counts,
        **source_counts,
        **authority_counts,
        **discovery_counts,
    }


def _public_source_observation(observation: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in observation.items() if not key.startswith("_")}


def _exit_code(signal: dict[str, Any]) -> int:
    counts = signal["counts"]
    if counts["campaign_work_remaining_count"]:
        return 1
    if (
        counts["source_integrity_error_count"]
        or counts.get("placement_integrity_error_count", 0)
        or counts["unknown_count"]
        or counts["unowned_count"]
        or counts["duplicate_identity_count"]
        or counts["coverage_gap_count"]
        or counts["coverage_overrun_count"]
        or counts["universe_coverage_error_count"]
        or counts["discovery_stale_disposition_count"]
    ):
        return 3
    if counts["authority_integrity_error_count"] or counts["fact_accounting_error_count"]:
        return 4
    return 0


def _signal(
    manifest: dict[str, Any],
    manifest_path: Path,
    source_scan: dict[str, Any],
    authority_scan: dict[str, Any],
    universe_scan: dict[str, Any],
    universe_reconciliation: dict[str, Any],
    enrichment: dict[str, Any],
    discovery_scan: dict[str, Any],
    consumer_fact_scan: dict[str, Any],
    facts_publication_signal: dict[str, Any],
) -> dict[str, Any]:
    todo_debt = _todo_debt_scan(manifest, universe_scan)
    counts = _counts(
        manifest,
        source_scan,
        authority_scan,
        universe_scan,
        universe_reconciliation,
        enrichment,
        todo_debt,
        discovery_scan,
        consumer_fact_scan,
        facts_publication_signal,
    )
    items = [
        {
            "id": row["id"],
            "source_finding_id": row["id"],
            "item_id": _item_id(row),
            "owner_lane": _owner_for(row, manifest["ownership"]),
            "category": row["category"],
            "status": row["status"],
            "target": row["target"],
            "evidence": row["evidence"],
            "source_evidence": [
                {
                    "file": source_scan["evidence"][(row["id"], index)]["file"],
                    "anchor": source_scan["evidence"][(row["id"], index)]["anchor"],
                    "anchor_status": source_scan["evidence"][(row["id"], index)]["anchor_status"],
                    "matched_tokens": source_scan["evidence"][(row["id"], index)]["matched_tokens"],
                    "matched_ast_symbols": source_scan["evidence"][(row["id"], index)]["matched_ast_symbols"],
                    **(
                        {
                            "identity_status": source_scan["evidence"][(row["id"], index)]["identity_status"],
                            "identity_fingerprints": source_scan["evidence"][(row["id"], index)][
                                "identity_fingerprints"
                            ],
                            "matched_identity_fingerprints": source_scan["evidence"][(row["id"], index)][
                                "matched_identity_fingerprints"
                            ],
                        }
                        if "identity_status" in source_scan["evidence"][(row["id"], index)]
                        else {}
                    ),
                }
                for index, _ in enumerate(row["evidence"])
            ],
            **(
                {
                    "canonical_identity": {
                        "enrichment": enrichment["status"],
                        "declaration_count": len(enrichment["records"][row["id"]]["declarations"]),
                        "canonical_actionable": enrichment["records"][row["id"]].get("canonical_actionable"),
                        "identity_error": any(
                            item["candidate_id"] == row["id"] and item["identity_status"] in {"missing", "drifted"}
                            for item in source_scan["identities"]
                        ),
                    }
                }
                if enrichment["status"] == "ready"
                else {}
            ),
            **({"registry_state": row["registry_state"]} if "registry_state" in row else {}),
        }
        for row in manifest["candidates"]
    ]
    items.sort(key=lambda row: row["item_id"])
    tracked_row_work_ids = set(counts["tracked_row_work_ids"])
    actionable = [row for row in items if row["id"] in tracked_row_work_ids]
    signal = {
        "schema": "cadrumo.fact-relocation.signal",
        "contract_version": CONTRACT_VERSION,
        "signal": "fact-relocation-residual-python-declarations",
        "schema_version": SCHEMA_VERSION,
        "campaign": manifest["campaign"],
        "manifest": _display_path(manifest_path),
        "scope": manifest["scope"],
        "baseline": manifest.get("baseline", {}),
        "counts": counts,
        "zero_target": counts["zero_target"],
        "items": items,
        "actionable": actionable,
        "exclusions": manifest["exclusions"],
        "limitations": manifest.get("limitations", []),
        "source_observations": [
            _public_source_observation(source_scan["observations"][relative])
            | {
                "candidate_ids": sorted(
                    {candidate_id for candidate_id, _ in source_scan["path_refs"].get(relative, [])}
                    | {candidate_id for candidate_id, _ in source_scan["identity_refs"].get(relative, [])}
                ),
                "evidence_count": len(source_scan["path_refs"].get(relative, [])),
            }
            for relative in sorted(source_scan["observations"])
        ],
        "source_hash_observations": source_scan["hashes"],
        "enrichment_identity_observations": sorted(
            source_scan["identities"],
            key=lambda item: (
                item["candidate_id"],
                item["file"],
                item["scope"],
                item["symbol"],
                item["ast_node_kind"],
                item["expected_source_span"],
            ),
        ),
        "retired_by_relocation_identity_observations": sorted(
            source_scan["retired_by_relocation_identities"],
            key=lambda item: (
                item["candidate_id"],
                item["file"],
                item["scope"],
                item["symbol"],
                item["ast_node_kind"],
                item["expected_source_span"],
            ),
        ),
        "authority_observations": authority_scan["observations"],
        "excluded_modelo_authority_observations": authority_scan["excluded_modelo_authority_observations"],
        "placement_observations": authority_scan["placement_observations"],
        "consumer_fact_observations": consumer_fact_scan["observations"],
        "consumer_fact_blockers": consumer_fact_scan["blockers"],
        "consumer_fact_scan_errors": consumer_fact_scan["errors"],
        "facts_publication_accounting": {
            "fact_accounting_error_count": counts["fact_accounting_error_count"],
            "facts_publication_blocker_count": facts_publication_signal.get("counts", {}).get(
                "facts_publication_blocker_count", 0
            ),
            "published_fact_payload_stale_count": facts_publication_signal.get("counts", {}).get(
                "published_fact_payload_stale_count", 0
            ),
        },
        "discovery": {
            "counts": discovery_scan["counts"],
            "untriaged": discovery_scan["untriaged"],
            "blocking": discovery_scan["blocking"],
            "review": discovery_scan["review"],
            "stale_disposition_ids": discovery_scan["stale_disposition_ids"],
            "observations": discovery_scan["observations"],
        },
        "todo_debt": todo_debt,
        "symbol_enrichment": {
            key: enrichment[key]
            for key in (
                "status",
                "path",
                "reason",
                "summary",
                "total_declarations",
                "disposition_mismatches",
                "scope_only_count",
            )
            if key in enrichment
        },
        "frozen_universe": {
            **universe_scan["counts"],
            "historical_count": universe_reconciliation["historical_count"],
            "expected_count": universe_reconciliation["expected_count"],
            "delta_paths": (manifest["baseline"].get("live_universe_reconciliation", {}).get("delta_paths", [])),
            "count_drift": universe_reconciliation["count_drift"],
            "delta_paths_missing_count": universe_reconciliation["delta_paths_missing_count"],
            "delta_candidate_path_count": universe_reconciliation["delta_candidate_path_count"],
            "delta_candidate_flag_drift": universe_reconciliation["delta_candidate_flag_drift"],
            "complete": universe_reconciliation["complete"],
            "parse_failure_files": universe_scan["parse_failure_files"],
            "read_failure_files": universe_scan["read_failure_files"],
            "enumeration_errors": universe_scan["enumeration_errors"],
            "broad_prefilter": universe_reconciliation["broad_prefilter"],
            "direct_model_legal_filename": universe_reconciliation["direct_model_legal_filename"],
        },
    }
    signal["exit_code"] = _exit_code(signal)
    signal["signal_digest"] = _signal_digest(signal)
    return signal


def _human(signal: dict[str, Any]) -> str:
    counts = signal["counts"]
    category_counts = counts["actionable_by_category"]
    status_counts = counts["status_counts"]
    stale_disposition_ids = [
        value for value in signal.get("discovery", {}).get("stale_disposition_ids", []) if isinstance(value, str)
    ]
    stale_disposition_line = f"stale discovery dispositions: {counts['discovery_stale_disposition_count']}"
    if stale_disposition_ids:
        stale_disposition_line += "; ids=" + ", ".join(stale_disposition_ids)
    lines = [
        "registry fact-boundary signal",
        "=============================",
        "driving gates: "
        f"campaign_work={counts['campaign_work_remaining_count']}, "
        f"publication={counts['publication_blocker_count']}, "
        f"accounting={counts['accounting_error_count']}",
        f"facts-only authored/bundled accounting: errors={counts['fact_accounting_error_count']}",
        stale_disposition_line,
        "accounting components: "
        f"source_integrity={counts['source_integrity_error_count']}, "
        f"coverage_gap={counts['coverage_gap_count']}, "
        f"coverage_overrun={counts['coverage_overrun_count']}, "
        f"universe_coverage={counts['universe_coverage_error_count']}, "
        f"unowned={counts['unowned_count']}, "
        f"duplicate_identity={counts['duplicate_identity_count']}, "
        f"stale_discovery_dispositions={counts['discovery_stale_disposition_count']}, "
        f"consumer_errors={counts['consumer_fact_error_count']}, "
        f"facts_only={counts['fact_accounting_error_count']}",
        f"ledger rows: {counts['total_ledger_rows']}",
        f"declared-open ledger rows: {counts['actionable_count']}",
        f"tracked rows requiring work: {counts['tracked_row_work_count']}",
        f"closed rows: {counts['closed_count']}",
        f"source evidence: {counts['source_evidence_count']} observations across {counts['source_file_count']} files",
        f"frozen universe: historical={counts['universe_historical_count']}, "
        f"expected_live={counts['universe_expected_count']}, "
        f"observed={counts['universe_count']}; "
        f"AST parsed={counts['universe_parse_count']}; "
        f"parse failures={counts['universe_parse_failures']}; "
        f"count drift={counts['universe_count_drift']}",
        "integrity: "
        f"missing={counts['source_missing_count']}, "
        f"unresolved_anchors={counts['source_anchor_unresolved_count']}, "
        f"parse_errors={counts['source_parse_error_count']}, "
        f"hash_mismatches={counts['source_hash_mismatch_count']}, "
        f"authority_errors={counts['authority_integrity_error_count']}, "
        f"placement_errors={counts.get('placement_integrity_error_count', 0)}, "
        f"universe_errors={counts['universe_coverage_error_count']}",
        "source identity retirements: "
        f"total={counts.get('enrichment_identity_retired_by_relocation_count', 0)} "
        "(nonblocking; historical identity evidence retained)",
        "facts-only placement publication: "
        f"claims={counts.get('facts_publication_claim_count', 0)}, "
        f"verified={counts.get('facts_publication_verified_count', 0)}, "
        f"errors={counts.get('facts_publication_integrity_error_count', 0)} "
        "(Modelo-registry publication is reported separately and nonblocking)",
        "excluded Modelo authority claims: "
        f"claims={counts.get('excluded_modelo_authority_claim_count', 0)}, "
        f"verified={counts.get('excluded_modelo_authority_verified_count', 0)}, "
        f"errors={counts.get('excluded_modelo_authority_error_count', 0)} "
        "(nonblocking; not governed-fact authority proof)",
        "governed consumer facts: "
        f"required={counts['consumer_fact_required_count']}, "
        f"callsites={counts['consumer_fact_callsite_count']}, "
        f"authored={counts['consumer_fact_authored_present_count']}, "
        f"compiled={counts['consumer_fact_compiled_present_count']}, "
        f"resolved={counts['consumer_fact_resolved_count']}, "
        f"blockers={counts['consumer_fact_blocker_count']}",
        "named missing/unresolvable governed facts:",
        "status counts: " + ", ".join(f"{status}={status_counts[status]}" for status in sorted(status_counts)),
        f"tracked files requiring work: {len(counts['actionable_files'])}",
        "live discovery: "
        f"candidates={counts['discovery_candidate_count']}, "
        f"files={counts['discovery_candidate_file_count']}, "
        f"blocking={counts['discovery_blocking_count']} across "
        f"{counts['discovery_blocking_file_count']} files, "
        f"review={counts['discovery_review_count']} across "
        f"{counts['discovery_review_file_count']} files, "
        f"dispositioned={counts['discovery_dispositioned_count']}",
        f"fact-relocation TODO debt: total={counts['todo_total_count']}, "
        f"open={counts['todo_open_count']}, "
        f"resolved={counts['todo_resolved_count']}, "
        "migrated rows with unresolved TODOs="
        f"{counts['todo_migrated_rows_with_unresolved_count']}",
        f"TODO baseline resolved delta: {signal.get('todo_debt', {}).get('baseline', {}).get('resolved_delta')}",
        "fact-relocation TODO paths:",
    ]
    consumer_blockers = signal.get("consumer_fact_blockers", [])
    consumer_lines: list[str] = []
    if not consumer_blockers:
        consumer_lines.append("(none)")
    else:
        for blocker in consumer_blockers:
            callsites = (
                "; ".join(
                    f"{callsite.get('file')}:{callsite.get('line', '?')}"
                    f" [{callsite.get('enclosing_symbol', '<unknown>')}]"
                    for callsite in blocker.get("source_call_sites", [])
                )
                or "<no source call site>"
            )
            consumer_lines.append(f"- {blocker['fact_id']}: {', '.join(blocker['blockers'])}; source={callsites}")
    heading_index = lines.index("named missing/unresolvable governed facts:")
    lines[heading_index + 1 : heading_index + 1] = consumer_lines
    lines.append(
        "actionable by category: "
        + ", ".join(f"{category}={category_counts[category]}" for category in sorted(category_counts))
    )
    todo_occurrences = signal.get("todo_debt", {}).get("occurrences", [])
    if not todo_occurrences:
        lines.append("(none)")
    else:
        for occurrence in todo_occurrences:
            associated = ",".join(occurrence["migrated_row_ids"]) or "unassociated"
            lines.append(f"- {occurrence['file']}:{occurrence['line']} [{associated}] {occurrence['text']}")
    lines.extend(
        [
            "migrated rows with unresolved TODOs:",
        ]
    )
    unresolved_todos = signal.get("todo_debt", {}).get("migrated_rows_with_unresolved_todos", [])
    if not unresolved_todos:
        lines.append("(none)")
    else:
        for entry in unresolved_todos:
            lines.append(f"- {entry['row_id']}: {entry['reason']} ({entry['todo_text']})")
    lines.extend(
        [
            "",
            "blocking live discovery by file:",
        ]
    )
    discovery_by_file = Counter(item["path"] for item in signal.get("discovery", {}).get("blocking", []))
    if not discovery_by_file:
        lines.append("(none)")
    else:
        for path, count in sorted(discovery_by_file.items(), key=lambda item: (-item[1], item[0]))[:50]:
            lines.append(f"- {path}: {count}")
        if len(discovery_by_file) > 50:
            lines.append(f"... {len(discovery_by_file) - 50} more files; use --json for every hit")
    lines.extend(
        [
            "",
            "actionable evidence:",
        ]
    )
    if not signal["actionable"]:
        lines.append("(none)")
    else:
        human_rows = sorted(
            signal["actionable"],
            key=lambda row: (
                row["owner_lane"],
                row["category"],
                row["evidence"][0]["file"],
                row["id"],
                row["item_id"],
            ),
        )
        for row in human_rows:
            evidence = "; ".join(f"{item['file']} [{item['anchor']}]" for item in row["evidence"])
            lines.append(
                f"- {row['id']} ({row['owner_lane']}; {row['category']}; {row['status']}): "
                f"{evidence} -> {row['target']}"
            )
    lines.extend(
        [
            "",
            "exit contract: 0 means campaign, publication, and accounting gates are clean; "
            "1 means campaign work remains (ledger, placement, TODO, or untriaged discovery); "
            "2 means the ledger is invalid; 3 means source/coverage integrity is "
            "incomplete; 4 means an authority destination proof failed.",
            f"result exit code: {signal['exit_code']}",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the fact-boundary signal."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="path to the candidate ledger (default: fact-relocation campaign manifest)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of the human summary",
    )
    parser.add_argument(
        "--facts-only",
        action="store_true",
        help=(
            "measure authored, compiled, bundled, and consumer-resolved facts only; "
            "skip the historical relocation ledger and live-discovery scan"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Emit the fact-boundary signal and return its gate-specific exit code."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.facts_only:
        signal = _facts_only_signal()
        if args.json:
            print(json.dumps(signal, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            print(_facts_only_human(signal))
        return signal["exit_code"]
    manifest_path = args.manifest.resolve()
    try:
        manifest = _load_manifest(manifest_path)
        enrichment = _load_symbol_enrichment(manifest)
        source_scan = _source_scan(manifest, enrichment)
        authority_scan = _authority_scan(manifest, source_scan)
        universe_scan = _enumerate_frozen_universe()
        universe_reconciliation = _reconcile_frozen_universe(
            manifest,
            universe_scan,
        )
        consumer_fact_scan = _consumer_fact_scan(manifest, universe_scan)
        facts_publication_signal = _facts_only_signal()
        discovery_scan = _discovery_scan(manifest)
        signal = _signal(
            manifest,
            manifest_path,
            source_scan,
            authority_scan,
            universe_scan,
            universe_reconciliation,
            enrichment,
            discovery_scan,
            consumer_fact_scan,
            facts_publication_signal,
        )
    except ManifestError as exc:
        print(f"fact-relocation signal error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(signal, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(_human(signal))
    return signal["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
