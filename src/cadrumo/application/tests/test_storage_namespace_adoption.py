"""Production-root adoption gate for secure-object namespace metadata.

Every secure-object namespace declared in
:data:`~adapters.persistence.storage._namespace_registry.STORAGE_NAMESPACE_REGISTRY`
carries a :class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition`
that is the single authority for its ``namespace`` string, ``sensitivity``
:class:`~core.classification.SensitivityClass`, and envelope ``schema_version``.
Production consumers MUST source those three metadata values off the registered
definition rather than restate them as raw ``SensitivityClass`` members or
integer literals at the write site.

This module is a *structural* gate, not a per-namespace round-trip proof (those
live beside each consumer as ``test_*_namespace_binding.py``). It replaces the
brittle literal-membership check — a hardcoded allowlist of namespace strings —
with three production-root scans:

1. **Recognition** — the authority set is the registry itself, and every
   registered namespace value uses a ``cadrumo``-family prefix, so a newly
   registered definition is covered automatically without editing this gate.
2. **Redeclaration detection** — an AST walk over the whole ``cadrumo`` package
   that flags any secure-object write site (a ``save(namespace=..., ...)`` call,
   an ``Envelope(...)`` construction, or a ``SecureBoundRepository`` metadata
   ClassVar) passing a *raw* ``SensitivityClass.X`` / integer literal for the
   metadata instead of a definition-sourced value. This set is empty on the
   canonical tree; a re-hardcoded literal would repopulate it.
3. **Consumption proof** — every ``SecureBoundRepository`` subclass in production
   binds its ``namespace`` / ``sensitivity`` / ``schema_version`` ClassVars to a
   ``<NAME>_NAMESPACE.<attr>`` attribute of a registered definition.

The detector is proven non-vacuous by a self-test that feeds it a synthetic
redeclaration fragment and asserts it flags, plus a definition-sourced fragment
it must leave clean.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

import cadrumo
from cadrumo.adapters.persistence.storage import STORAGE_NAMESPACE_REGISTRY

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# A registered namespace value uses one of these product-family prefixes. The
# gate recognises adoption by prefix (plus registry membership) rather than a
# hardcoded per-namespace allowlist, so a new definition is auto-covered. The
# closed cadrumo-family whitelist inherently excludes any retired ``aeat.*``
# product prefix, since a namespace cannot start with two different prefixes.
_CADRUMO_NAMESPACE_PREFIXES = ("cadrumo.", "cadrumo-test.", "cadrumo-tests.")

# Metadata attribute names a definition exposes; a value read as ``<def>.<attr>``
# is definition-sourced and never a redeclaration.
_DEFINITION_METADATA_ATTRS = frozenset({"namespace", "sensitivity", "schema_version"})

# The metadata-carrying ClassVars a ``SecureBoundRepository`` subclass binds.
_BOUND_METADATA_CLASSVARS = ("namespace", "sensitivity", "schema_version")

# The registry-authoring module legitimately constructs definitions from raw
# ``SensitivityClass`` members; it is the authority, not a consumer, so it is
# excluded from the redeclaration scan.
_REGISTRY_AUTHORING_MODULE = "_namespace_registry.py"


def _package_root() -> Path:
    """Return the on-disk root of the ``cadrumo`` package."""
    package_file = cadrumo.__file__
    assert package_file is not None, "cadrumo package must resolve to a file path"
    return Path(package_file).resolve().parent


def _is_test_path(path: Path, root: Path) -> bool:
    """Return whether ``path`` is test code rather than production source."""
    relative_parts = path.relative_to(root).parts
    if any(part == "tests" for part in relative_parts):
        return True
    return path.name.startswith("test_")


def _production_modules() -> Iterator[tuple[str, ast.Module]]:
    """Yield ``(label, parsed_module)`` for every production ``cadrumo`` module.

    Test modules and the registry-authoring module are excluded: the first are
    not consumers, the second is the metadata authority the gate protects.
    """
    root = _package_root()
    for path in sorted(root.rglob("*.py")):
        if _is_test_path(path, root):
            continue
        if path.name == _REGISTRY_AUTHORING_MODULE:
            continue
        label = str(path.relative_to(root).as_posix())
        yield label, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# ---------------------------------------------------------------------------
# Raw-literal predicates
# ---------------------------------------------------------------------------


def _is_raw_sensitivity_literal(node: ast.expr) -> bool:
    """Return whether ``node`` is a raw ``SensitivityClass.<MEMBER>`` access.

    A definition-sourced value (``<def>.sensitivity`` / ``self.sensitivity`` /
    a module constant bound to one) is an attribute whose *attr* is ``sensitivity``
    or a plain name; only a direct member of the ``SensitivityClass`` enum is a
    redeclaration.
    """
    if not isinstance(node, ast.Attribute):
        return False
    base = node.value
    return isinstance(base, ast.Name) and base.id.endswith("SensitivityClass")


def _is_raw_int_literal(node: ast.expr) -> bool:
    """Return whether ``node`` is a bare integer literal (a schema-version restatement)."""
    return isinstance(node, ast.Constant) and type(node.value) is int


# ---------------------------------------------------------------------------
# Redeclaration detector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Redeclaration:
    """One raw metadata literal found at a secure-object binding site."""

    module: str
    line: int
    site: str
    detail: str

    def render(self) -> str:
        return f"{self.module}:{self.line} [{self.site}] {self.detail}"


def _call_keyword(call: ast.Call, name: str) -> ast.keyword | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword
    return None


def _func_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _inspect_write_call(call: ast.Call, module: str) -> Iterator[_Redeclaration]:
    """Flag raw metadata literals passed to a secure-object write call.

    A secure-object write is recognised structurally as either a ``save(...)``
    with both ``namespace=`` and ``classification=`` keywords (the
    :meth:`SecureObjectRepository.save` shape), or an ``Envelope(...)``
    construction carrying a ``classification=`` keyword.
    """
    classification_kw = _call_keyword(call, "classification")
    if classification_kw is None:
        return
    namespace_kw = _call_keyword(call, "namespace")
    is_envelope_ctor = _func_name(call).endswith("Envelope")
    if namespace_kw is None and not is_envelope_ctor:
        return
    site = "envelope-construction" if is_envelope_ctor else "secure-object-save"
    if _is_raw_sensitivity_literal(classification_kw.value):
        member = ast.unparse(classification_kw.value)
        yield _Redeclaration(
            module=module,
            line=classification_kw.value.lineno,
            site=site,
            detail=f"classification={member} restated instead of sourced off the namespace definition",
        )
    schema_kw = _call_keyword(call, "schema_version")
    if schema_kw is not None and _is_raw_int_literal(schema_kw.value):
        yield _Redeclaration(
            module=module,
            line=schema_kw.value.lineno,
            site=site,
            detail=f"schema_version={ast.unparse(schema_kw.value)} restated instead of sourced off the namespace definition",
        )


def _annassign_target_name(node: ast.AnnAssign) -> str | None:
    return node.target.id if isinstance(node.target, ast.Name) else None


def _inspect_metadata_classvar(node: ast.AnnAssign, module: str) -> Iterator[_Redeclaration]:
    """Flag a ``sensitivity``/``schema_version`` ClassVar bound to a raw literal."""
    name = _annassign_target_name(node)
    if name not in {"sensitivity", "schema_version"}:
        return
    value = node.value
    if value is None:  # bare annotation on the base class — no binding to check
        return
    if name == "sensitivity" and _is_raw_sensitivity_literal(value):
        yield _Redeclaration(
            module=module,
            line=value.lineno,
            site="metadata-classvar",
            detail=f"sensitivity ClassVar = {ast.unparse(value)} restated instead of sourced off the namespace definition",
        )
    if name == "schema_version" and _is_raw_int_literal(value):
        yield _Redeclaration(
            module=module,
            line=value.lineno,
            site="metadata-classvar",
            detail=f"schema_version ClassVar = {ast.unparse(value)} restated instead of sourced off the namespace definition",
        )


def _find_redeclarations(tree: ast.Module, module: str) -> list[_Redeclaration]:
    """Return every raw-metadata redeclaration at a secure-object binding site in ``tree``.

    Two site kinds are scanned. Secure-object *write calls* are matched
    structurally across the whole module (the ``namespace=``+``classification=``
    / ``Envelope(classification=...)`` shape is itself the scope). *Metadata
    ClassVars* are scanned only inside :class:`SecureBoundRepository` subclass
    bodies, so an unrelated ``schema_version`` field on some other record model
    is not misread as a namespace-metadata restatement.
    """
    findings: list[_Redeclaration] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            findings.extend(_inspect_write_call(node, module))
        elif isinstance(node, ast.ClassDef) and _is_secure_bound_subclass(node):
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign):
                    findings.extend(_inspect_metadata_classvar(stmt, module))
    return findings


# ---------------------------------------------------------------------------
# 1. Recognition — the registry is the authority set, recognised by prefix
# ---------------------------------------------------------------------------


def test_registry_is_the_non_empty_authority_set() -> None:
    """The registry carries the secure-object namespaces this gate governs."""
    namespaces = STORAGE_NAMESPACE_REGISTRY.namespaces
    assert len(namespaces) >= 40, (
        f"expected the storage registry to carry the full namespace surface, saw {len(namespaces)}"
    )


def test_every_registered_namespace_uses_a_cadrumo_family_prefix() -> None:
    """Adoption is recognised by prefix, so a new definition is auto-covered.

    Recognising the authority set by ``cadrumo``-family prefix (rather than a
    hardcoded per-namespace allowlist) is what lets a newly registered
    definition fall under this gate with no edit here.
    """
    offenders = [
        definition.namespace
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces
        if not definition.namespace.startswith(_CADRUMO_NAMESPACE_PREFIXES)
    ]
    assert not offenders, (
        "every registered secure-object namespace must use a cadrumo-family prefix "
        f"(one of {_CADRUMO_NAMESPACE_PREFIXES}); unrecognised: {offenders}"
    )


# ---------------------------------------------------------------------------
# 2. Redeclaration detection — production tree carries none
# ---------------------------------------------------------------------------


def test_production_tree_has_no_namespace_metadata_redeclaration() -> None:
    """No production module restates namespace metadata at a secure-object write site."""
    findings: list[_Redeclaration] = []
    for label, tree in _production_modules():
        findings.extend(_find_redeclarations(tree, label))
    assert not findings, (
        "secure-object namespace metadata must be sourced off the registered definition, "
        "never restated as a raw SensitivityClass member or integer literal:\n"
        + "\n".join(finding.render() for finding in findings)
    )


# ---------------------------------------------------------------------------
# 3. Consumption proof — every bound repository reads metadata off a definition
# ---------------------------------------------------------------------------


def _is_definition_metadata_access(value: ast.expr | None) -> bool:
    """Return whether ``value`` reads a metadata attr off a ``*_NAMESPACE`` definition."""
    if not isinstance(value, ast.Attribute):
        return False
    if value.attr not in _DEFINITION_METADATA_ATTRS:
        return False
    base = value.value
    return isinstance(base, ast.Name) and base.id.endswith("_NAMESPACE")


def _classvar_value(class_node: ast.ClassDef, name: str) -> ast.expr | None:
    for stmt in class_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == name:
            return stmt.value
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return stmt.value
    return None


def _is_secure_bound_subclass(class_node: ast.ClassDef) -> bool:
    for base in class_node.bases:
        # ``SecureBoundRepository`` or ``SecureBoundRepository[Payload]``
        candidate = base.value if isinstance(base, ast.Subscript) else base
        name = candidate.id if isinstance(candidate, ast.Name) else getattr(candidate, "attr", "")
        if name == "SecureBoundRepository":
            return True
    return False


def test_every_bound_repository_consumes_the_registered_definition() -> None:
    """Every ``SecureBoundRepository`` subclass sources its metadata ClassVars off a definition."""
    bound_classes: list[str] = []
    violations: list[str] = []
    for label, tree in _production_modules():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not _is_secure_bound_subclass(node):
                continue
            bound_classes.append(f"{label}:{node.name}")
            for classvar in _BOUND_METADATA_CLASSVARS:
                value = _classvar_value(node, classvar)
                if value is None:
                    violations.append(f"{label}:{node.name} does not bind ClassVar '{classvar}'")
                elif not _is_definition_metadata_access(value):
                    violations.append(
                        f"{label}:{node.name}.{classvar} = {ast.unparse(value)} "
                        "is not sourced off a <NAME>_NAMESPACE definition attribute",
                    )
    assert len(bound_classes) >= 14, (
        f"expected the full SecureBoundRepository consumer surface, saw {len(bound_classes)}: {bound_classes}"
    )
    assert not violations, "SecureBoundRepository metadata must bind to a registered definition:\n" + "\n".join(
        violations,
    )


# ---------------------------------------------------------------------------
# 4. Non-vacuity — the detector flags an injected redeclaration and clears a clean one
# ---------------------------------------------------------------------------

_INJECTED_REDECLARATION_SOURCE = """
from typing import ClassVar

from cadrumo.core.classification import SensitivityClass


class _DriftedRepository(SecureBoundRepository[object]):
    namespace: ClassVar[str] = CALCULATION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.FINANCIAL
    schema_version: ClassVar[int] = 1


def _drifted_writer(objects) -> None:
    objects.save(
        namespace="cadrumo.calculations.observations",
        object_key="k",
        classification=SensitivityClass.FINANCIAL,
        schema_version=7,
        payload=b"{}",
    )
"""

_DEFINITION_SOURCED_SOURCE = """
from typing import ClassVar

from cadrumo.core.classification import SensitivityClass


class _CleanRepository(SecureBoundRepository[object]):
    namespace: ClassVar[str] = CALCULATION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = CALCULATION_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = CALCULATION_OBSERVATIONS_NAMESPACE.schema_version


def _clean_writer(objects, definition) -> None:
    objects.save(
        namespace=definition.namespace,
        object_key="k",
        classification=definition.sensitivity,
        schema_version=definition.schema_version,
        payload=b"{}",
    )
"""


def test_detector_flags_an_injected_redeclaration() -> None:
    """The detector is non-vacuous: a synthetic drift fragment is flagged.

    Without this proof the empty production result is meaningless — a stub
    detector would also return no findings on a truly-drifted tree.
    """
    tree = ast.parse(_INJECTED_REDECLARATION_SOURCE)
    findings = _find_redeclarations(tree, "synthetic.drift")
    rendered = [finding.render() for finding in findings]

    classvar_hits = [f for f in findings if f.site == "metadata-classvar"]
    save_hits = [f for f in findings if f.site == "secure-object-save"]
    assert classvar_hits, f"expected the raw sensitivity/schema_version ClassVars flagged, saw {rendered}"
    assert save_hits, f"expected the raw save-site metadata literals flagged, saw {rendered}"

    details = " ".join(rendered)
    assert "sensitivity ClassVar = SensitivityClass.FINANCIAL" in details
    assert "schema_version ClassVar = 1" in details
    assert "classification=SensitivityClass.FINANCIAL" in details
    assert "schema_version=7" in details


def test_detector_leaves_a_definition_sourced_fragment_clean() -> None:
    """The detector does not fire on correctly definition-sourced metadata.

    This is the negative control: it proves the detector distinguishes a
    redeclaration from the canonical single-sourced form rather than flagging
    every metadata site unconditionally.
    """
    tree = ast.parse(_DEFINITION_SOURCED_SOURCE)
    findings = _find_redeclarations(tree, "synthetic.clean")
    assert not findings, f"definition-sourced metadata must not be flagged, saw {[f.render() for f in findings]}"
