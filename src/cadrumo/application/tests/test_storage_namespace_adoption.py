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
   an ``Envelope(...)`` / ``SecureObjectWrite(...)`` construction, or a
   ``SecureBoundRepository`` metadata ClassVar) passing a *raw* namespace string,
   ``SensitivityClass.X`` member, or integer literal for the metadata instead of
   a definition-sourced value. This set is empty on the canonical tree; a
   re-hardcoded literal would repopulate it. The scan sees through two evasions:
   a value reached through a *module-level constant* (``sensitivity =
   _CLASSIFICATION`` where ``_CLASSIFICATION = SensitivityClass.FINANCIAL``) is
   resolved to its bound expression before the raw-literal predicates run, and a
   write call passing its metadata *positionally* is bound to parameter names
   before inspection.
3. **Consumption proof** — every ``SecureBoundRepository`` subclass in production
   binds its ``namespace`` / ``sensitivity`` / ``schema_version`` ClassVars to a
   ``<NAME>_NAMESPACE.<attr>`` attribute of a registered definition.

Constant resolution is deliberately *module-local*. A name that does not resolve
to a top-level assignment in the same module — an imported alias, a parameter, a
local — is left unresolved and therefore never flagged: the gate holds one module
tree at a time, and following an import through the package's ``__init__``
re-export chains would require an import graph this structural scan does not
build. That is sound rather than merely convenient, because an imported alias is
itself bound in some other production module, where this same scan applies to its
binding sites; the residual blind spot is a raw literal parked in a module that
declares no write site of its own and is re-exported purely to be consumed
elsewhere.

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

from ...adapters.persistence.storage._namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ...core.directory_scan import scan_directory

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
_REGISTRY_AUTHORING_MODULE = "_secure_object_namespaces.py"


def _package_root() -> Path:
    """Return the on-disk root of the ``cadrumo`` package.

    Derived from this test module's own location (``cadrumo/application/tests/``)
    rather than an absolute ``import cadrumo``, so the relative-imports gate stays
    satisfied.
    """
    return Path(__file__).resolve().parents[2]


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
    for path in scan_directory(root, pattern="*.py", recursive=True):
        if _is_test_path(path, root):
            continue
        if path.name == _REGISTRY_AUTHORING_MODULE:
            continue
        label = str(path.relative_to(root).as_posix())
        yield label, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# ---------------------------------------------------------------------------
# Module-level constant resolution
# ---------------------------------------------------------------------------


def _module_constants(tree: ast.Module) -> dict[str, ast.expr]:
    """Return every top-level ``NAME = <expr>`` binding in ``tree``.

    Only module-level statements are collected: these are the constants a write
    site can reach by bare name, and the indirection the raw-literal predicates
    must see through.
    """
    constants: dict[str, ast.expr] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            constants[stmt.target.id] = stmt.value
    return constants


def _resolve_constant(node: ast.expr, constants: dict[str, ast.expr]) -> ast.expr:
    """Follow a bare name through module-level constants to its bound expression.

    ``_CLASSIFICATION`` -> ``SensitivityClass.FINANCIAL`` collapses to the member
    access so the raw-literal predicates fire on it. A chain of aliases is
    followed transitively, guarding against a self-referential cycle. A name with
    no module-level binding (an import, a parameter, a local) resolves to itself
    and is therefore never treated as raw.
    """
    current = node
    seen: set[str] = set()
    while isinstance(current, ast.Name) and current.id in constants and current.id not in seen:
        seen.add(current.id)
        current = constants[current.id]
    return current


def _describe(original: ast.expr, resolved: ast.expr) -> str:
    """Render a metadata value, showing the indirection when there was one."""
    rendered = ast.unparse(original)
    if resolved is original:
        return rendered
    return f"{rendered} -> {ast.unparse(resolved)}"


# ---------------------------------------------------------------------------
# Raw-literal predicates
# ---------------------------------------------------------------------------


def _is_raw_sensitivity_literal(node: ast.expr) -> bool:
    """Return whether ``node`` is a raw ``SensitivityClass.<MEMBER>`` access.

    A definition-sourced value (``<def>.sensitivity`` / ``self.sensitivity``) is
    an attribute whose *attr* is ``sensitivity``; only a direct member of the
    ``SensitivityClass`` enum is a redeclaration. Callers pass the
    :func:`_resolve_constant` output, so a module constant bound to a member is
    caught as well.
    """
    if not isinstance(node, ast.Attribute):
        return False
    base = node.value
    return isinstance(base, ast.Name) and base.id.endswith("SensitivityClass")


def _is_raw_int_literal(node: ast.expr) -> bool:
    """Return whether ``node`` is a bare integer literal (a schema-version restatement)."""
    return isinstance(node, ast.Constant) and type(node.value) is int


def _is_raw_namespace_literal(node: ast.expr) -> bool:
    """Return whether ``node`` is a bare string literal (a namespace restatement)."""
    return isinstance(node, ast.Constant) and type(node.value) is str


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


def _func_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


# Positional parameter order of every recognised secure-object write callable.
# The canonical writers are keyword-only today, so positional binding is defence
# in depth: it keeps the gate honest if a write helper ever accepts positionals,
# and it closes the "pass the literal positionally" evasion outright.
_WRITE_CALL_POSITIONAL_PARAMS: dict[str, tuple[str, ...]] = {
    "save": ("namespace", "object_key", "classification", "schema_version", "written_at", "payload"),
    "save_with_raw_key": (
        "namespace",
        "hashed_object_key",
        "classification",
        "schema_version",
        "written_at",
        "payload",
    ),
    "SecureObjectWrite": ("namespace", "object_key", "classification", "schema_version", "written_at", "payload"),
    "Envelope": ("schema_version", "written_at", "classification", "payload"),
}

# A positional call is only read as a secure-object write when it carries at
# least this many positional arguments, so an unrelated one-argument ``save(row)``
# on some other repository is never misread as the six-parameter write shape.
_MIN_POSITIONAL_WRITE_ARITY = 3


def _positional_param_order(call: ast.Call) -> tuple[str, ...]:
    name = _func_name(call)
    if name.endswith("Envelope"):
        return _WRITE_CALL_POSITIONAL_PARAMS["Envelope"]
    return _WRITE_CALL_POSITIONAL_PARAMS.get(name, ())


def _bound_write_arguments(call: ast.Call) -> dict[str, ast.expr]:
    """Bind a write call's arguments to parameter names, positionals included."""
    bound: dict[str, ast.expr] = {}
    order = _positional_param_order(call)
    if order and len(call.args) >= _MIN_POSITIONAL_WRITE_ARITY:
        for name, arg in zip(order, call.args, strict=False):
            if not isinstance(arg, ast.Starred):
                bound[name] = arg
    for keyword in call.keywords:
        if keyword.arg is not None:
            bound[keyword.arg] = keyword.value
    return bound


def _inspect_write_call(call: ast.Call, module: str, constants: dict[str, ast.expr]) -> Iterator[_Redeclaration]:
    """Flag raw metadata literals passed to a secure-object write call.

    A secure-object write is recognised structurally as either a ``save(...)``
    carrying both ``namespace`` and ``classification`` (the
    :meth:`SecureObjectRepository.save` shape), or an ``Envelope(...)`` /
    ``SecureObjectWrite(...)`` construction carrying ``classification``. Arguments
    are matched whether they are passed by keyword or positionally, and each
    metadata value is resolved through module-level constants before the
    raw-literal predicates run.
    """
    bound = _bound_write_arguments(call)
    classification = bound.get("classification")
    if classification is None:
        return
    func_name = _func_name(call)
    is_envelope_ctor = func_name.endswith("Envelope")
    namespace = bound.get("namespace")
    if namespace is None and not is_envelope_ctor:
        return
    site = "envelope-construction" if is_envelope_ctor else "secure-object-save"

    if namespace is not None:
        resolved_namespace = _resolve_constant(namespace, constants)
        if _is_raw_namespace_literal(resolved_namespace):
            yield _Redeclaration(
                module=module,
                line=namespace.lineno,
                site=site,
                detail=(
                    f"namespace={_describe(namespace, resolved_namespace)} "
                    "restated instead of sourced off the namespace definition"
                ),
            )

    resolved_classification = _resolve_constant(classification, constants)
    if _is_raw_sensitivity_literal(resolved_classification):
        yield _Redeclaration(
            module=module,
            line=classification.lineno,
            site=site,
            detail=(
                f"classification={_describe(classification, resolved_classification)} "
                "restated instead of sourced off the namespace definition"
            ),
        )
    schema = bound.get("schema_version")
    if schema is not None:
        resolved_schema = _resolve_constant(schema, constants)
        if _is_raw_int_literal(resolved_schema):
            yield _Redeclaration(
                module=module,
                line=schema.lineno,
                site=site,
                detail=(
                    f"schema_version={_describe(schema, resolved_schema)} "
                    "restated instead of sourced off the namespace definition"
                ),
            )


def _annassign_target_name(node: ast.AnnAssign) -> str | None:
    return node.target.id if isinstance(node.target, ast.Name) else None


_CLASSVAR_RAW_PREDICATES = {
    "namespace": _is_raw_namespace_literal,
    "sensitivity": _is_raw_sensitivity_literal,
    "schema_version": _is_raw_int_literal,
}


def _inspect_metadata_classvar(
    node: ast.AnnAssign,
    module: str,
    constants: dict[str, ast.expr],
) -> Iterator[_Redeclaration]:
    """Flag a ``namespace``/``sensitivity``/``schema_version`` ClassVar bound to a raw literal."""
    name = _annassign_target_name(node)
    if name is None or name not in _CLASSVAR_RAW_PREDICATES:
        return
    value = node.value
    if value is None:  # bare annotation on the base class — no binding to check
        return
    resolved = _resolve_constant(value, constants)
    if _CLASSVAR_RAW_PREDICATES[name](resolved):
        yield _Redeclaration(
            module=module,
            line=value.lineno,
            site="metadata-classvar",
            detail=(
                f"{name} ClassVar = {_describe(value, resolved)} "
                "restated instead of sourced off the namespace definition"
            ),
        )


def _find_redeclarations(tree: ast.Module, module: str) -> list[_Redeclaration]:
    """Return every raw-metadata redeclaration at a secure-object binding site in ``tree``.

    Two site kinds are scanned. Secure-object *write calls* are matched
    structurally across the whole module (the ``namespace=``+``classification=``
    / ``Envelope(classification=...)`` shape is itself the scope). *Metadata
    ClassVars* are scanned only inside :class:`SecureBoundRepository` subclass
    bodies, so an unrelated ``schema_version`` field on some other record model
    is not misread as a namespace-metadata restatement. Both site kinds resolve
    their values through the module's top-level constants first, so an
    indirection through a module constant is flagged like a direct literal.
    """
    constants = _module_constants(tree)
    findings: list[_Redeclaration] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            findings.extend(_inspect_write_call(node, module, constants))
        elif isinstance(node, ast.ClassDef) and _is_secure_bound_subclass(node):
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign):
                    findings.extend(_inspect_metadata_classvar(stmt, module, constants))
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

_ARTEFACT_CLASSIFICATION = SensitivityClass.FINANCIAL
_ENVELOPE_VERSION = 1
_ARTEFACT_NAMESPACE = "cadrumo.calculations.observations"


class _DriftedRepository(SecureBoundRepository[object]):
    namespace: ClassVar[str] = CALCULATION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.FINANCIAL
    schema_version: ClassVar[int] = 1


class _IndirectlyDriftedRepository(SecureBoundRepository[object]):
    namespace: ClassVar[str] = _ARTEFACT_NAMESPACE
    sensitivity: ClassVar[SensitivityClass] = _ARTEFACT_CLASSIFICATION
    schema_version: ClassVar[int] = _ENVELOPE_VERSION


def _drifted_writer(objects) -> None:
    objects.save(
        namespace="cadrumo.calculations.observations",
        object_key="k",
        classification=SensitivityClass.FINANCIAL,
        schema_version=7,
        payload=b"{}",
    )


def _indirectly_drifted_writer(objects) -> None:
    objects.save(
        namespace=_ARTEFACT_NAMESPACE,
        object_key="k",
        classification=_ARTEFACT_CLASSIFICATION,
        schema_version=_ENVELOPE_VERSION,
        payload=b"{}",
    )


def _positional_drifted_writer(objects, written_at) -> None:
    objects.save(
        "cadrumo.calculations.observations",
        "k",
        SensitivityClass.FINANCIAL,
        9,
        written_at,
        b"{}",
    )
"""

_DEFINITION_SOURCED_SOURCE = """
from typing import ClassVar

from cadrumo.core.classification import SensitivityClass

_OBSERVATION_NAMESPACE = CALCULATION_OBSERVATIONS_NAMESPACE.namespace
_OBSERVATION_CLASSIFICATION = CALCULATION_OBSERVATIONS_NAMESPACE.sensitivity
_OBSERVATION_ENVELOPE_VERSION = CALCULATION_OBSERVATIONS_NAMESPACE.schema_version


class _CleanRepository(SecureBoundRepository[object]):
    namespace: ClassVar[str] = CALCULATION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = CALCULATION_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = CALCULATION_OBSERVATIONS_NAMESPACE.schema_version


class _CleanConstantSourcedRepository(SecureBoundRepository[object]):
    namespace: ClassVar[str] = _OBSERVATION_NAMESPACE
    sensitivity: ClassVar[SensitivityClass] = _OBSERVATION_CLASSIFICATION
    schema_version: ClassVar[int] = _OBSERVATION_ENVELOPE_VERSION


def _clean_writer(objects, definition) -> None:
    objects.save(
        namespace=definition.namespace,
        object_key="k",
        classification=definition.sensitivity,
        schema_version=definition.schema_version,
        payload=b"{}",
    )


def _clean_constant_writer(objects) -> None:
    objects.save(
        namespace=_OBSERVATION_NAMESPACE,
        object_key="k",
        classification=_OBSERVATION_CLASSIFICATION,
        schema_version=_OBSERVATION_ENVELOPE_VERSION,
        payload=b"{}",
    )


def _clean_imported_constant_writer(objects) -> None:
    objects.save(
        namespace=IMPORTED_NAMESPACE_STRING,
        object_key="k",
        classification=IMPORTED_CLASSIFICATION,
        schema_version=IMPORTED_ENVELOPE_VERSION,
        payload=b"{}",
    )


def _unrelated_single_argument_save(repository, record) -> None:
    repository.save(record)
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

    # A raw namespace string is metadata restatement too: the definition is the
    # single authority for the namespace value, not only for its two siblings.
    assert 'namespace="cadrumo.calculations.observations"' in details.replace("'", '"'), (
        f"expected the raw namespace string flagged, saw {rendered}"
    )


def test_detector_flags_metadata_reached_through_a_module_constant() -> None:
    """A raw literal parked in a module constant and referenced is still a redeclaration.

    This is the indirection evasion: the binding site reads as an ``ast.Name``,
    so a predicate that only matches a direct ``SensitivityClass.X`` attribute or
    a bare ``ast.Constant`` sees nothing. The detector must resolve the constant
    to its bound expression first.
    """
    tree = ast.parse(_INJECTED_REDECLARATION_SOURCE)
    findings = _find_redeclarations(tree, "synthetic.drift")
    indirect = [finding for finding in findings if "->" in finding.detail]
    rendered = [finding.render() for finding in indirect]
    details = " ".join(rendered)

    assert indirect, (
        f"expected the module-constant indirection flagged, saw only {[finding.render() for finding in findings]}"
    )
    assert "_ARTEFACT_CLASSIFICATION -> SensitivityClass.FINANCIAL" in details, rendered
    assert "_ENVELOPE_VERSION -> 1" in details, rendered
    assert "_ARTEFACT_NAMESPACE ->" in details, rendered
    assert any(finding.site == "metadata-classvar" for finding in indirect), rendered
    assert any(finding.site == "secure-object-save" for finding in indirect), rendered


def test_detector_flags_metadata_passed_positionally() -> None:
    """A write call passing its metadata positionally does not escape the scan.

    The canonical writers are keyword-only, so this is defence in depth against a
    future write helper that accepts positionals — and it proves the argument
    binding is by parameter name, not by keyword presence alone.
    """
    tree = ast.parse(_INJECTED_REDECLARATION_SOURCE)
    findings = _find_redeclarations(tree, "synthetic.drift")
    positional = [f for f in findings if "schema_version=9" in f.detail]
    assert positional, f"expected the positional save-site metadata flagged, saw {[f.render() for f in findings]}"


def test_detector_leaves_a_definition_sourced_fragment_clean() -> None:
    """The detector does not fire on correctly definition-sourced metadata.

    This is the negative control: it proves the detector distinguishes a
    redeclaration from the canonical single-sourced form rather than flagging
    every metadata site unconditionally. It covers the three shapes the
    resolution and positional-binding passes could each turn into a false
    positive: a module constant that resolves to a *definition* attribute, an
    imported name that resolves to nothing module-local, and an unrelated
    one-argument ``repository.save(record)``.
    """
    tree = ast.parse(_DEFINITION_SOURCED_SOURCE)
    findings = _find_redeclarations(tree, "synthetic.clean")
    assert not findings, f"definition-sourced metadata must not be flagged, saw {[f.render() for f in findings]}"
