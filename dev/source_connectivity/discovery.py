"""Structural discovery for source capabilities that may feed modelo casillas.

Discovery is intentionally syntax-driven and produces evidence locators.  It
does not decide that a repository's payload is legally equivalent to a casilla;
that decision belongs to the reviewed connectivity census.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

type SecureRepositoryMechanism = Literal["secure_bound", "profile_secure_document", "secure_object"]

_SECURE_NAMES = frozenset(
    {
        "ProfileBareModelSecurePersistence",
        "SecureBoundRepository",
        "SecureObjectRepository",
        "_SecureBoundRepository",
        "resolve_profile_secure_object_repository",
        "secure_object_repository_for_bucket",
    }
)


@dataclass(frozen=True, slots=True)
class SecureRepositoryCapability:
    """One typed production repository backed by encrypted secure storage."""

    module: str
    repository_name: str
    line: int
    mechanism: SecureRepositoryMechanism
    payload_types: tuple[str, ...]
    aggregate_grain: str

    @property
    def evidence_locator(self) -> str:
        """Return a re-fetchable source locator for review and census rows."""
        return f"{self.module}:{self.line}"


def _production_python_files(source_root: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(source_root.rglob("*.py"))
        if "tests" not in path.relative_to(source_root).parts and path.name != "__init__.py"
    )


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _dotted_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    if isinstance(node, ast.Subscript):
        return _dotted_name(node.value)
    return ""


def _class_names(node: ast.ClassDef) -> frozenset[str]:
    return frozenset(
        name.rsplit(".", maxsplit=1)[-1]
        for child in ast.walk(node)
        if (name := _dotted_name(child))
    )


def _secure_mechanism(node: ast.ClassDef) -> SecureRepositoryMechanism | None:
    base_names = {_dotted_name(base).rsplit(".", maxsplit=1)[-1] for base in node.bases}
    if base_names & {"SecureBoundRepository", "_SecureBoundRepository"}:
        return "secure_bound"
    names = _class_names(node)
    if "ProfileBareModelSecurePersistence" in names:
        return "profile_secure_document"
    if names & _SECURE_NAMES:
        return "secure_object"
    return None


def _payload_types(node: ast.ClassDef) -> tuple[str, ...]:
    payloads: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Subscript) and _dotted_name(base.value).rsplit(".", maxsplit=1)[-1] in {
            "SecureBoundRepository",
            "_SecureBoundRepository",
        }:
            payloads.add(ast.unparse(base.slice))
    for child in ast.walk(node):
        if isinstance(child, ast.keyword) and child.arg == "model_type":
            payloads.add(ast.unparse(child.value))
        if isinstance(child, (ast.Assign, ast.AnnAssign)):
            targets = child.targets if isinstance(child, ast.Assign) else [child.target]
            value = child.value
            if value is not None and any(
                isinstance(target, ast.Name) and target.id == "payload_type" for target in targets
            ):
                payloads.add(ast.unparse(value))
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name in {
            "add",
            "create",
            "load",
            "record",
            "save",
            "upsert",
        }:
            annotations = [child.returns, *(argument.annotation for argument in child.args.args[1:])]
            for annotation in annotations:
                if annotation is None:
                    continue
                for name in (_dotted_name(part).rsplit(".", maxsplit=1)[-1] for part in ast.walk(annotation)):
                    if name and name not in {
                        "None",
                        "Path",
                        "bool",
                        "bytes",
                        "dict",
                        "int",
                        "list",
                        "str",
                        "tuple",
                    }:
                        payloads.add(name)
    return tuple(sorted(payloads))


def _aggregate_grain(node: ast.ClassDef, mechanism: SecureRepositoryMechanism) -> str:
    for child in ast.walk(node):
        if isinstance(child, ast.keyword) and child.arg == "definition":
            return f"namespace_definition:{ast.unparse(child.value)}"
    if mechanism == "secure_bound":
        extractor = next(
            (child for child in node.body if isinstance(child, ast.FunctionDef) and child.name == "extract_identifier"),
            None,
        )
        return "natural_identifier:extract_identifier" if extractor is not None else "natural_identifier:inherited"
    names = sorted(
        {
            name
            for child in ast.walk(node)
            if isinstance(child, ast.Name)
            and ((name := child.id).endswith("_NAMESPACE") or name.lower().endswith(("_key", "_object_key")))
        }
    )
    if names:
        return "declared_key:" + ",".join(names)
    return "secure_object_key:repository_declared"


def discover_secure_repositories(repo_root: Path) -> tuple[SecureRepositoryCapability, ...]:
    """Enumerate typed production repositories that structurally use secure storage."""
    source_root = repo_root / "src" / "cadrumo"
    capabilities: list[SecureRepositoryCapability] = []
    for path in _production_python_files(source_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or not node.name.endswith(("Repository", "Storage")):
                continue
            mechanism = _secure_mechanism(node)
            if mechanism is None:
                continue
            payload_types = _payload_types(node)
            if not payload_types:
                continue
            capabilities.append(
                SecureRepositoryCapability(
                    module=path.relative_to(repo_root).as_posix(),
                    repository_name=node.name,
                    line=node.lineno,
                    mechanism=mechanism,
                    payload_types=payload_types,
                    aggregate_grain=_aggregate_grain(node, mechanism),
                )
            )
    return tuple(sorted(capabilities, key=lambda item: (item.module, item.repository_name, item.line)))


__all__ = ["SecureRepositoryCapability", "SecureRepositoryMechanism", "discover_secure_repositories"]
