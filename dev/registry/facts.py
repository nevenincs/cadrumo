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
import sys
import tokenize
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

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
BUNDLED_AUTHORITY_ARTIFACT = SOURCE_ROOT / "_data" / "registry" / "authority" / "authority.json"
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
        "digest",
        "compiled",
        "published",
        "provenance_digest",
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


def _source_scan(
    manifest: dict[str, Any],
    enrichment: dict[str, Any],
) -> dict[str, Any]:
    """Collect bounded source observations for every manifest evidence path."""
    relocations = _source_relocations(manifest.get("source_relocations"))
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
            "enrichment_declaration_count": (identity_matched + identity_missing + identity_drifted),
            "enrichment_identity_matched_count": identity_matched,
            "enrichment_identity_missing_count": identity_missing,
            "enrichment_identity_drifted_count": identity_drifted,
            "enrichment_identity_error_count": identity_missing + identity_drifted,
        },
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


CONSUMER_QUERY_SYMBOLS = frozenset({"MappingFactQuery", "ScalarFactQuery", "EntitySetFactQuery"})


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
        return node.attr.lower()
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for item in node.elts for name in _target_names(item)]
    return []


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


class _ConsumerQueryVisitor(ast.NodeVisitor):
    """Find statically named governed-fact query seams in one module."""

    def __init__(self, *, file: str, constants: dict[str, str]) -> None:
        self.file = file
        self.constants = constants
        self.symbol_stack: list[str] = []
        self.observations: list[dict[str, Any]] = []

    def _visit_symbol(self, node: ast.AST, name: str) -> None:
        self.symbol_stack.append(name)
        self.generic_visit(node)
        self.symbol_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_symbol(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_symbol(node, node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_symbol(node, node.name)

    def visit_Call(self, node: ast.Call) -> None:
        query_kind = _call_symbol(node.func)
        if query_kind in CONSUMER_QUERY_SYMBOLS:
            fact_expr = next((keyword.value for keyword in node.keywords if keyword.arg == "fact_id"), None)
            fact_id = _static_string(fact_expr, self.constants)
            if fact_id:
                axis_expr = next((keyword.value for keyword in node.keywords if keyword.arg == "date_axis"), None)
                effective_expr = next(
                    (keyword.value for keyword in node.keywords if keyword.arg == "effective_date"),
                    None,
                )
                observation: dict[str, Any] = {
                    "fact_id": fact_id,
                    "query_kind": query_kind,
                    "file": self.file,
                    "line": node.lineno,
                    "column": node.col_offset,
                    "enclosing_symbol": "::".join(self.symbol_stack) or "<module>",
                    "date_axis": _date_axis_name(axis_expr),
                    "date_axis_expression": ast.unparse(axis_expr) if axis_expr is not None else None,
                    "effective_date_expression": ast.unparse(effective_expr) if effective_expr is not None else None,
                    "source_kind": "ast_query_call",
                }
                self.observations.append(observation)
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


def _consumer_fact_scan(
    manifest: dict[str, Any],
    universe_scan: dict[str, Any],
) -> dict[str, Any]:
    """Reconcile every named consumer fact through the authority proof chain."""
    callsites_by_fact: dict[str, list[dict[str, Any]]] = {}
    parse_errors: list[str] = []
    for relative in universe_scan["paths"]:
        path = REPO_ROOT / Path(*PurePosixPath(relative).parts)
        try:
            text = _decode_python_source(path.read_bytes())
            tree = ast.parse(text, filename=relative)
        except (OSError, SyntaxError, LookupError, UnicodeDecodeError, ValueError, TypeError) as exc:
            parse_errors.append(f"{relative}:{type(exc).__name__}")
            continue
        visitor = _ConsumerQueryVisitor(file=relative, constants=_module_string_constants(tree))
        visitor.visit(tree)
        for observation in visitor.observations:
            callsites_by_fact.setdefault(observation["fact_id"], []).append(observation)

    external_observations, external_errors = _consumer_requirement_file()
    for external in external_observations:
        fact_id = external["fact_id"]
        for callsite in external["source_call_sites"]:
            observation = dict(callsite)
            observation.setdefault("query_kind", external.get("query_kind"))
            observation.setdefault("date_axis", external.get("date_axis"))
            observation.setdefault("date_axis_expression", external.get("date_axis_expression"))
            observation.setdefault("effective_date_expression", external.get("effective_date_expression"))
            observation.setdefault("source_kind", "external_runtime_probe")
            callsites_by_fact.setdefault(fact_id, []).append(observation)

    authored, authored_errors = _authored_fact_index()
    artifact_payload, artifact_status = _load_authority_artifact(BUNDLED_AUTHORITY_ARTIFACT)
    compiled = _compiled_fact_index(artifact_payload) if artifact_status == "ok" else {}
    row_files: dict[str, set[str]] = {}
    for row in manifest["candidates"]:
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
        axis_declared = bool(deduped_callsites) and bool(requested_axes)
        axis_compatible = bool(compiled_fact is not None and requested_axes <= compiled_axes)
        axis_resolved = axis_declared and axis_compatible
        associated_row_ids = sorted(
            row_id
            for row_id, paths in row_files.items()
            if any(callsite.get("file") in paths for callsite in deduped_callsites)
        )
        blockers: list[str] = []
        if not authored_paths:
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
        observation = {
            "fact_id": fact_id,
            "source_call_sites": deduped_callsites,
            "authored_presence": bool(authored_paths),
            "authored_paths": authored_paths,
            "bundled_authority_presence": compiled_fact is not None,
            "bundled_authority_artifact": _display_path(BUNDLED_AUTHORITY_ARTIFACT),
            "bundled_authority_artifact_status": artifact_status,
            "compiled_variant_date_axes": sorted(compiled_axes),
            "requested_query_date_axes": sorted(requested_axes),
            "query_date_axis_recognized": axis_declared,
            "query_date_axis_resolved": axis_resolved,
            "proof_chain": {
                "authored_presence": bool(authored_paths),
                "bundled_authority_presence": compiled_fact is not None,
                "query_date_axis_resolution": axis_resolved,
                "consumer_seam_loadability": not blockers,
            },
            "consumer_seam_loadability": ("query_shape_resolved" if not blockers else "blocked:" + ",".join(blockers)),
            "associated_row_ids": associated_row_ids,
            "blockers": blockers,
            "blocking": bool(blockers),
        }
        observations.append(observation)

    blockers = [item for item in observations if item["blocking"]]
    return {
        "observations": observations,
        "blockers": blockers,
        "errors": sorted(set(parse_errors + external_errors + authored_errors)),
        "counts": {
            "consumer_fact_required_count": len(observations),
            "consumer_fact_callsite_count": sum(len(item["source_call_sites"]) for item in observations),
            "consumer_fact_authored_present_count": sum(item["authored_presence"] for item in observations),
            "consumer_fact_compiled_present_count": sum(item["bundled_authority_presence"] for item in observations),
            "consumer_fact_resolved_count": sum(not item["blocking"] for item in observations),
            "consumer_fact_blocker_count": len(blockers),
            "consumer_fact_error_count": len(consumer_errors := (parse_errors + external_errors + authored_errors)),
        },
        "associated_row_ids": sorted({row_id for item in blockers for row_id in item["associated_row_ids"]}),
    }


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
    candidates = discover_governed_literal_candidates(SOURCE_ROOT)
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


def _load_authority_artifact(path: Path) -> tuple[Any, str]:
    """Parse a published artifact using only deterministic stdlib parsers."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        return None, f"read-error:{type(exc).__name__}"
    suffix = path.suffix.casefold()
    try:
        if suffix == ".toml":
            import tomllib

            return tomllib.loads(data.decode("utf-8")), "ok"
        return json.loads(data.decode("utf-8")), "ok"
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return None, f"parse-error:{type(exc).__name__}"


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
    consumer_resolved = False
    registry_query_present = bool(source_observation.get("_symbols", set()) & REGISTRY_QUERY_SYMBOLS)
    if isinstance(consumer_resolution, dict) and consumer_resolution.get("resolved") is True:
        seam = consumer_resolution.get("seam")
        consumer_source = consumer_resolution.get("source_file")
        consumer_resolved = (
            isinstance(seam, str)
            and bool(seam.strip())
            and seam in source_text
            and isinstance(consumer_source, str)
            and consumer_source == source_relative
            and registry_query_present
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
            revisions = payload.get("revisions") if isinstance(payload, dict) else None
            revision_payload = revisions.get(destination["revision"]) if isinstance(revisions, dict) else None
            declarations_payload = (
                revision_payload.get(destination["family"]) if isinstance(revision_payload, dict) else None
            )
            declaration_by_id = (
                {
                    item.get("id"): item
                    for item in declarations_payload
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                }
                if isinstance(declarations_payload, list)
                else {}
            )
            fact_missing_fields = {}
        else:
            declaration_by_id = {}
            fact_missing_fields = {}
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
    failure_reasons: list[str] = []
    if not source_ok:
        failure_reasons.append("source_missing_or_unreadable_or_unparsed")
    if not forbidden_symbols_absent:
        failure_reasons.append("python_declaration_symbol_present")
    if not forbidden_literals_absent:
        failure_reasons.append("python_fact_literal_present")
    if not todo_present and not consumer_resolved:
        failure_reasons.append("todo_hole_missing")
    if (
        isinstance(consumer_resolution, dict)
        and consumer_resolution.get("resolved") is True
        and not registry_query_present
    ):
        failure_reasons.append("registry_query_symbol_missing")
    if not destination_verified:
        failure_reasons.append("canonical_destination_missing_or_incomplete")
    verified = bool(
        placement["publication"]["published"] is False
        and source_ok
        and forbidden_symbols_absent
        and forbidden_literals_absent
        and (todo_present or consumer_resolved)
        and destination_verified
    )
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
        "registry_query_present": registry_query_present,
        "destinations": destination_observations,
        "destination_verified": destination_verified,
        "failure_reasons": failure_reasons,
        "verified": verified,
    }


def _authority_scan(
    manifest: dict[str, Any],
    source_scan: dict[str, Any],
) -> dict[str, Any]:
    """Verify claimed migrated/bridge destinations mechanically.

    Authoring-path existence is intentionally reported separately from proof
    that a compiled artifact is published and carries provenance.  Closure
    metadata is a claim; only bytes read from the referenced artifact and data
    read from referenced authoring files can satisfy the authority proof checks.
    Placement closures use the same byte-level discipline while explicitly
    recording that publication is false.
    """
    observations: list[dict[str, Any]] = []
    placement_observations: list[dict[str, Any]] = []
    for row in manifest["candidates"]:
        if row["status"] not in {"migrated", "bridge"}:
            continue
        closure = row["closure"]
        if closure.get("kind") == PLACEMENT_CLOSURE_KIND:
            placement_observations.append(_placement_scan(row, source_scan))
            continue
        authority = closure["authority"]
        artifact_path, artifact_relative = _authority_path(
            authority["artifact"],
            label=f"{row['id']}: closure.authority.artifact",
        )
        authoring_observations: list[dict[str, Any]] = []
        expected_identity = [
            authority["declaration_id"],
            authority["model"],
            authority["revision"],
            authority["family"],
            authority["consumer"],
        ]
        for index, raw_path in enumerate(authority["authoring_paths"]):
            authoring_path, authoring_relative = _authoring_path(
                raw_path,
                label=f"{row['id']}: closure.authority.authoring_paths[{index}]",
            )
            try:
                data = authoring_path.read_bytes()
            except OSError as exc:
                authoring_observations.append(
                    {
                        "file": authoring_relative,
                        "exists": False,
                        "read_status": f"read-error:{type(exc).__name__}",
                        "identity_tokens_found": [],
                    }
                )
                continue
            text = data.decode("utf-8", errors="replace").casefold()
            found = [value for value in expected_identity if value.casefold() in text]
            authoring_observations.append(
                {
                    "file": authoring_relative,
                    "exists": authoring_path.is_file(),
                    "read_status": "ok",
                    "identity_tokens_found": found,
                }
            )

        artifact_exists = artifact_path.is_file()
        artifact_actual_digest: str | None = None
        artifact_payload: Any = None
        artifact_status = "missing"
        if artifact_exists:
            try:
                data = artifact_path.read_bytes()
                artifact_actual_digest = "sha256:" + hashlib.sha256(data).hexdigest()
                artifact_payload, artifact_status = _load_authority_artifact(artifact_path)
                if artifact_status == "ok" and not isinstance(artifact_payload, dict):
                    artifact_status = "invalid-shape"
            except OSError as exc:
                artifact_exists = False
                artifact_status = f"read-error:{type(exc).__name__}"

        artifact_strings = {value.casefold() for value in _flatten_strings(artifact_payload)}
        declared_provenance = authority["provenance_digest"].casefold()
        identity_proof = all(value.casefold() in artifact_strings for value in expected_identity)
        digest_proof = artifact_actual_digest == authority["digest"]
        compiled_proof = _payload_has_true(
            artifact_payload,
            frozenset({"compiled", "is_compiled"}),
        )
        published_proof = _payload_has_true(
            artifact_payload,
            frozenset({"published", "is_published"}),
        ) or _payload_has_status(artifact_payload, frozenset({"published"}))
        provenance_proof = declared_provenance in artifact_strings
        authoring_presence = bool(authoring_observations) and all(
            item["exists"] and item["read_status"] == "ok" for item in authoring_observations
        )
        authoring_identity_proof = authoring_presence and all(
            item["identity_tokens_found"] for item in authoring_observations
        )
        source_retirement_evidence = bool(closure.get("retirement_evidence"))
        verified = all(
            (
                authoring_presence,
                authoring_identity_proof,
                artifact_exists,
                artifact_status == "ok",
                digest_proof,
                compiled_proof,
                published_proof,
                provenance_proof,
                identity_proof,
                authority["parity"] in {"exact", "semantic"},
                authority["duplicate_retired"] is True,
                source_retirement_evidence,
            )
        )
        observations.append(
            {
                "candidate_id": row["id"],
                "item_id": _item_id(row),
                "status": row["status"],
                "artifact": artifact_relative,
                "declared_digest": authority["digest"],
                "observed_digest": artifact_actual_digest,
                "artifact_status": artifact_status,
                "authoring": authoring_observations,
                "authoring_presence": authoring_presence,
                "authoring_identity_proof": authoring_identity_proof,
                "compiled_proof": compiled_proof,
                "published_proof": published_proof,
                "provenance_proof": provenance_proof,
                "identity_proof": identity_proof,
                "digest_proof": digest_proof,
                "parity_declared": authority["parity"],
                "duplicate_retired_declared": authority["duplicate_retired"],
                "source_retirement_evidence": source_retirement_evidence,
                "verified": verified,
            }
        )

    failed = sum(not item["verified"] for item in observations)
    placement_failed = sum(not item["verified"] for item in placement_observations)
    return {
        "observations": sorted(observations, key=lambda item: item["item_id"]),
        "placement_observations": sorted(
            placement_observations,
            key=lambda item: item["item_id"],
        ),
        "counts": {
            "authority_claim_count": len(observations),
            "authoring_presence_count": sum(item["authoring_presence"] for item in observations),
            "authoring_missing_count": sum(not item["authoring_presence"] for item in observations),
            "authoring_identity_proof_count": sum(item["authoring_identity_proof"] for item in observations),
            "compiled_proof_count": sum(item["compiled_proof"] for item in observations),
            "published_proof_count": sum(item["published_proof"] for item in observations),
            "provenance_proof_count": sum(item["provenance_proof"] for item in observations),
            "authority_verified_count": sum(item["verified"] for item in observations),
            "authority_integrity_error_count": failed,
            "placement_claim_count": len(placement_observations),
            "placement_verified_count": sum(item["verified"] for item in placement_observations),
            "placement_integrity_error_count": placement_failed,
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
    _validate_hash(authority.get("digest"), label=f"{label}.digest")
    _validate_hash(
        authority.get("provenance_digest"),
        label=f"{label}.provenance_digest",
    )
    if authority.get("compiled") is not True:
        raise ManifestError(f"{label}.compiled must be true")
    if authority.get("published") is not True:
        raise ManifestError(f"{label}.published must be true")
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
    _, placement_source = _source_path(
        placement.get("source_file"),
        label=f"{candidate_id}: closure.placement.source_file",
    )
    _, consumer_source = _source_path(
        resolution["source_file"],
        label=f"{label}.source_file",
    )
    if consumer_source != placement_source:
        raise ManifestError(f"{label}.source_file must equal closure.placement.source_file")
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
                if not isinstance(relation["legacy_declaration_id"], str) or not relation["legacy_declaration_id"].strip():
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
) -> dict[str, Any]:
    candidates = manifest["candidates"]
    actionable = [row for row in candidates if row["status"] in BLOCKING_STATUSES]
    failed_placement_ids = {
        item["candidate_id"] for item in authority_scan["placement_observations"] if not item["verified"]
    }
    todo_row_ids = {
        candidate_id for occurrence in todo_debt["occurrences"] for candidate_id in occurrence["candidate_ids"]
    }
    consumer_row_ids = set(consumer_fact_scan.get("associated_row_ids", []))
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
    )
    publication_blocker_count = (
        authority_counts["authority_integrity_error_count"] + consumer_counts["consumer_fact_blocker_count"]
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
    ):
        return 3
    if counts["authority_integrity_error_count"]:
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
                            item["candidate_id"] == row["id"] and item["identity_status"] != "matched"
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
        "authority_observations": authority_scan["observations"],
        "placement_observations": authority_scan["placement_observations"],
        "consumer_fact_observations": consumer_fact_scan["observations"],
        "consumer_fact_blockers": consumer_fact_scan["blockers"],
        "consumer_fact_scan_errors": consumer_fact_scan["errors"],
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
    lines = [
        "registry fact-boundary signal",
        "=============================",
        "driving gates: "
        f"campaign_work={counts['campaign_work_remaining_count']}, "
        f"publication={counts['publication_blocker_count']}, "
        f"accounting={counts['accounting_error_count']}",
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Emit the fact-boundary signal and return its gate-specific exit code."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
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
