"""AST-walking helpers for the typed-id placement enforcement test.

The helpers parse every Python module under :mod:`aeat` with the
standard-library :mod:`ast` module and surface structural violations of
the typed-id alias placement rule. Discovery is text-only: the helper
never imports application, domain, adapter, or entrypoint code so the
test surface cannot pull side effects from the modules it inspects.

The detectors expose ten checks, one per clause of the placement rule
(four inherited from the identity-primitives ADR, six new under
core-authority ADR Rule 11):

* :func:`find_sibling_domain_id_imports` — a ``domain.<a>`` module
  importing a name from ``domain.<b>._ids`` for ``a != b`` other than the
  registry-aliases exception.
* :func:`find_private_id_imports` — an adapter, application, or
  entrypoint module importing a leading-underscore name from any
  ``_ids.py`` module.
* :func:`find_misplaced_hex_length_constants` — an ``_HEX_*_LENGTH``
  module-level constant declared outside the owning ``_ids.py``.
* :func:`find_bare_str_typed_id_fields` — a pydantic-``BaseModel``
  subclass declaring a ``<owner>_id`` field as bare ``str`` (or
  ``str | None``) when a typed alias for that owner exists in the
  alias inventory.
* :func:`find_sibling_domain_enum_imports` — a ``domain.<a>`` module
  importing from ``domain.<b>._enums`` for ``a != b``.
* :func:`find_sibling_domain_constant_imports` — a ``domain.<a>``
  module importing from ``domain.<b>._constants`` for ``a != b``.
* :func:`find_sibling_domain_protocol_imports` — a ``domain.<a>``
  module importing from ``domain.<b>._protocols`` for ``a != b``.
* :func:`find_private_name_cross_package_imports` — any production
  module importing a ``_``-prefixed name (excluding dunders) from a
  cross-package module other than ``_ids.py``.
* :func:`find_same_name_constant_multi_declarations` — two or more
  production modules outside the protect list declaring an
  ``UPPER_SNAKE_CASE`` constant with the same name and the same
  literal value.
* :func:`find_bare_str_kind_status_state_fields` — a pydantic
  ``BaseModel`` subclass at a persisted or wire boundary declaring a
  ``<owner>_kind``, ``<owner>_status``, or ``<owner>_state`` field as
  bare ``str`` (or ``str | None``) when a typed alias for that owner
  exists.

Every detector returns a list of :class:`Finding` records; the test
surface asserts the list is empty. The detectors do not raise on
malformed source: a parse error becomes a finding so the test surface
reports a precise location rather than aborting at collection.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path

__all__ = (
    "AEAT_ROOT",
    "AliasInventory",
    "ConstraintShape",
    "Finding",
    "build_alias_inventory",
    "build_kind_status_state_alias_inventory",
    "find_bare_str_kind_status_state_fields",
    "find_bare_str_typed_id_fields",
    "find_misplaced_hex_length_constants",
    "find_private_id_imports",
    "find_private_name_cross_package_imports",
    "find_same_name_constant_multi_declarations",
    "find_sibling_domain_constant_imports",
    "find_sibling_domain_enum_imports",
    "find_sibling_domain_id_imports",
    "find_sibling_domain_protocol_imports",
    "iter_aeat_modules",
)

_CONSUMER_LAYER_ROOTS = ("aeat.adapters", "aeat.application", "aeat.entrypoints")

AEAT_ROOT = Path(__file__).resolve().parent.parent
"""Filesystem root of the :mod:`aeat` package (``src/aeat``)."""

_SKIP_DIR_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache"})

_HEX_LENGTH_CONSTANT_RE = re.compile(r"^_HEX_[A-Z0-9_]+_LENGTH$")


@dataclass(frozen=True)
class Finding:
    """One structural violation surfaced by an AST-walking detector."""

    path: Path
    line: int
    message: str

    def render(self) -> str:
        try:
            rel = self.path.relative_to(AEAT_ROOT.parent)
        except ValueError:
            rel = self.path
        return f"{rel.as_posix()}:{self.line}: {self.message}"


@dataclass(frozen=True)
class ConstraintShape:
    """A pydantic string-constraint shape extracted from AST.

    Attributes track the three substitutability-relevant facets: minimum
    length, maximum length, and regex pattern.  ``None`` means the facet
    was not declared at the source site (the comparator treats it as the
    permissive extreme: ``min_length=0``, ``max_length=inf``, no pattern).

    A separate ``pattern_unresolved`` flag distinguishes "no pattern
    declared" (``pattern is None and not pattern_unresolved``) from
    "pattern declared as a Name reference we could not resolve to a
    literal" (``pattern is None and pattern_unresolved``).  The
    comparator treats the unresolved case as "alias has a pattern
    requirement" so the missing literal does not silently downgrade the
    shape comparison.
    """

    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    pattern_unresolved: bool = False

    @property
    def has_pattern(self) -> bool:
        return self.pattern is not None or self.pattern_unresolved


@dataclass(frozen=True)
class AliasInventory:
    """Discovered typed-id alias inventory.

    ``aliases_by_owner`` maps the snake-case owner prefix (e.g.
    ``work_unit`` for ``WorkUnitId``) to the alias name. The mapping is
    used by the bare-string field detector to decide whether a
    ``<owner>_id`` field on a pydantic model has a typed alias it could
    consume instead of bare ``str``.

    ``alias_modules`` is the set of module dotted paths where any typed
    alias was discovered; the private-name import detector consults this
    set to recognise an ``_ids.py``-equivalent re-export module such as
    ``aeat.core.identity``.

    ``constraints_by_owner`` is the per-owner constraint shape derived
    from the alias's ``StringConstraints`` / ``Field`` metadata. Empty
    when the alias declaration could not be parsed (the substitutability
    comparator then treats the alias as unconstrained).
    """

    aliases_by_owner: dict[str, str]
    alias_modules: frozenset[str]
    constraints_by_owner: dict[str, ConstraintShape] = dataclass_field(default_factory=dict)


def iter_aeat_modules(root: Path = AEAT_ROOT) -> Iterator[Path]:
    """Yield every ``.py`` file under ``root`` excluding cache dirs."""
    for path in root.rglob("*.py"):
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def _module_dotted_path(path: Path, root: Path = AEAT_ROOT) -> str:
    """Return the ``<root.name>.<...>`` dotted path for ``path``.

    ``root`` defaults to the ``aeat`` package root; the helper accepts
    an alternate root so test fixtures rooted at a synthetic
    ``tmp_path/src/aeat`` layout resolve cleanly.
    """
    rel = path.relative_to(root.parent).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _parse(path: Path) -> tuple[ast.Module | None, Finding | None]:
    """Parse ``path`` into an AST, returning a finding on syntax error."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem error
        return None, Finding(path, 0, f"unreadable source: {exc}")
    try:
        return ast.parse(text, filename=str(path)), None
    except SyntaxError as exc:
        return None, Finding(path, exc.lineno or 0, f"syntax error: {exc.msg}")


def _camel_to_snake(name: str) -> str:
    """Convert a CamelCase identifier to ``snake_case``."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


_CONSTRAINT_CALL_NAMES = frozenset({"StringConstraints", "Field"})


def _module_literal_string_assignments(tree: ast.Module) -> dict[str, str]:
    """Return module-level ``NAME = "literal"`` assignments.

    Used to resolve ``pattern=_HEX_64_PATTERN`` references back to the
    underlying regex literal when extracting a :class:`ConstraintShape`
    from an alias declaration.
    """
    out: dict[str, str] = {}
    for node in tree.body:
        target_name: str | None = None
        value_node: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            value_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            target_name = node.target.id
            value_node = node.value
        if target_name is None or value_node is None:
            continue
        if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
            out[target_name] = value_node.value
    return out


def _resolve_string_constant(
    node: ast.expr, literals: dict[str, str]
) -> tuple[str | None, bool]:
    """Return ``(literal, unresolved)`` for a regex-pattern AST expression.

    ``literal`` is the resolved string when the node is a string
    constant or a Name reference resolvable through ``literals``.
    ``unresolved`` is ``True`` when the node names a constraint
    (e.g. a Name we could not resolve, or a non-string expression) so
    the comparator can treat the alias as "has a pattern requirement"
    without knowing the exact pattern text.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, False
    if isinstance(node, ast.Name):
        if node.id in literals:
            return literals[node.id], False
        return None, True
    return None, True


def _extract_constraint_shape_from_call(
    call: ast.Call, literals: dict[str, str]
) -> ConstraintShape:
    """Extract a constraint shape from a ``StringConstraints`` or ``Field`` call."""
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    pattern_unresolved = False
    for kw in call.keywords:
        if kw.arg == "min_length" and isinstance(kw.value, ast.Constant) and isinstance(
            kw.value.value, int
        ):
            min_length = kw.value.value
        elif kw.arg == "max_length" and isinstance(kw.value, ast.Constant) and isinstance(
            kw.value.value, int
        ):
            max_length = kw.value.value
        elif kw.arg == "pattern":
            resolved, unresolved = _resolve_string_constant(kw.value, literals)
            pattern = resolved
            pattern_unresolved = unresolved
    return ConstraintShape(
        min_length=min_length,
        max_length=max_length,
        pattern=pattern,
        pattern_unresolved=pattern_unresolved,
    )


def _call_name(call: ast.Call) -> str | None:
    """Return the dotted-leaf name of ``call.func`` (``Field``, ``StringConstraints``)."""
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return None


def _extract_shape_from_annotated_value(
    value_node: ast.expr | None, literals: dict[str, str]
) -> ConstraintShape:
    """Extract a :class:`ConstraintShape` from an alias RHS expression.

    Accepts both ``Annotated[str, StringConstraints(...)]`` and
    ``Annotated[str, Field(...)]`` shapes; returns an empty
    :class:`ConstraintShape` when no constraint call is found.
    """
    if value_node is None:
        return ConstraintShape()
    if not isinstance(value_node, ast.Subscript):
        return ConstraintShape()
    slice_node = value_node.slice
    elements: list[ast.expr]
    if isinstance(slice_node, ast.Tuple):
        elements = list(slice_node.elts)
    else:
        elements = [slice_node]
    for element in elements:
        if isinstance(element, ast.Call) and _call_name(element) in _CONSTRAINT_CALL_NAMES:
            return _extract_constraint_shape_from_call(element, literals)
    return ConstraintShape()


def _extract_field_constraint_shape(
    annotation: ast.expr, default_value: ast.expr | None, literals: dict[str, str]
) -> ConstraintShape:
    """Extract the effective constraint shape declared on a pydantic field.

    Two shapes contribute constraints:

    * The annotation itself when it is ``Annotated[str, ...]`` — the
      inner ``StringConstraints`` / ``Field`` call carries the
      constraints.
    * The default value when it is a ``Field(...)`` call with keyword
      arguments — bare-``str``-typed fields commonly declare their
      constraints inline through the default-value ``Field``.

    Both contributions are merged: the annotation shape's facets win
    where present, the default-value shape fills any remaining gaps.
    """
    ann_shape = _extract_shape_from_annotated_value(annotation, literals)
    default_shape = ConstraintShape()
    if isinstance(default_value, ast.Call) and _call_name(default_value) in _CONSTRAINT_CALL_NAMES:
        default_shape = _extract_constraint_shape_from_call(default_value, literals)
    return ConstraintShape(
        min_length=ann_shape.min_length if ann_shape.min_length is not None else default_shape.min_length,
        max_length=ann_shape.max_length if ann_shape.max_length is not None else default_shape.max_length,
        pattern=ann_shape.pattern if ann_shape.pattern is not None else default_shape.pattern,
        pattern_unresolved=ann_shape.pattern_unresolved or default_shape.pattern_unresolved,
    )


def _classify_promotion(
    candidate: ConstraintShape, alias: ConstraintShape
) -> tuple[bool, str]:
    """Return ``(compatible, rationale)`` for promoting ``candidate`` to ``alias``.

    Promotion is shape-compatible iff every constraint declared on
    ``alias`` is at least as permissive as the corresponding constraint
    declared on ``candidate`` -- i.e. every value accepted by the
    field's current constraints would also be accepted by the alias.
    The substitutability check follows the pre-filter required by the
    swarm-audit-cadence rule.

    The rationale string is empty when ``compatible`` is True and is a
    structured human-readable reason otherwise.
    """
    reasons: list[str] = []
    alias_min = alias.min_length if alias.min_length is not None else 0
    cand_min = candidate.min_length if candidate.min_length is not None else 0
    if alias_min > cand_min:
        reasons.append(
            f"alias requires min_length={alias.min_length} but field declares "
            f"min_length={candidate.min_length if candidate.min_length is not None else 0}"
        )
    alias_max = alias.max_length
    cand_max = candidate.max_length
    if alias_max is not None and (cand_max is None or cand_max > alias_max):
        reasons.append(
            f"alias requires max_length<={alias.max_length} but field declares "
            f"max_length={candidate.max_length if candidate.max_length is not None else 'unbounded'}"
        )
    if alias.has_pattern:
        if not candidate.has_pattern:
            reasons.append(
                f"alias requires pattern={alias.pattern!r} but field declares no pattern"
            )
        elif (
            alias.pattern is not None
            and candidate.pattern is not None
            and alias.pattern != candidate.pattern
        ):
            reasons.append(
                f"alias requires pattern={alias.pattern!r} but field declares "
                f"pattern={candidate.pattern!r}"
            )
    if reasons:
        return False, "; ".join(reasons)
    return True, ""


def _is_alias_module(path: Path) -> bool:
    """Return whether ``path`` is the alias-declaring module for a package.

    The ADR pattern places typed aliases in ``_ids.py``. The
    :mod:`aeat.core.identity` package aggregates aliases through its
    package ``__init__`` (re-exporting from ``_bucket.py``,
    ``_profile.py``, ``_snapshot.py``), so a package ``__init__`` that
    re-exports typed aliases is also recognised, as are the per-identity
    private modules within ``core/identity/`` themselves so the
    constraint-shape extractor sees the original ``StringConstraints``
    declaration rather than only the re-export.
    """
    name = path.name
    if name == "_ids.py":
        return True
    if path.parent.name == "identity":
        if name == "__init__.py":
            return True
        if name.startswith("_") and not name.startswith("__") and name.endswith(".py"):
            return True
    return False


def _iter_alias_definitions(
    tree: ast.Module,
) -> Iterator[tuple[str, ast.expr | None]]:
    """Yield ``(name, value_node)`` for module-level typed-id alias declarations.

    Re-export ``ImportFrom`` rows yield ``(name, None)`` because the
    value node lives in the imported module; the caller resolves the
    constraint shape from the underlying definition site instead.
    """
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield target.id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            yield node.target.id, node.value
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            yield node.name.id, getattr(node, "value", None)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                yield alias.asname or alias.name, None


def build_alias_inventory(root: Path = AEAT_ROOT) -> AliasInventory:
    """Discover typed-id aliases declared under ``root``.

    Each discovered alias contributes its constraint shape to
    ``constraints_by_owner`` so the bare-string field detector can
    decide promotion compatibility from the alias's actual
    ``StringConstraints`` / ``Field`` metadata.

    Returns:
        An :class:`AliasInventory` mapping owner prefixes to alias names,
        with per-owner constraint shapes extracted from the declarations.
    """
    by_owner: dict[str, str] = {}
    alias_modules: set[str] = set()
    constraints_by_owner: dict[str, ConstraintShape] = {}
    for path in iter_aeat_modules(root):
        if not _is_alias_module(path):
            continue
        tree, _err = _parse(path)
        if tree is None:
            continue
        literals = _module_literal_string_assignments(tree)
        recorded_in_module = False
        for name, value_node in _iter_alias_definitions(tree):
            if not (name.endswith("Id") and name[:1].isupper() and not name.startswith("_")):
                continue
            recorded_in_module = True
            owner = _camel_to_snake(name[:-2])
            by_owner.setdefault(owner, name)
            if owner in constraints_by_owner:
                continue
            if value_node is None:
                continue
            shape = _extract_shape_from_annotated_value(value_node, literals)
            if shape != ConstraintShape():
                constraints_by_owner[owner] = shape
        if recorded_in_module:
            alias_modules.add(_module_dotted_path(path, root))
    return AliasInventory(
        aliases_by_owner=dict(sorted(by_owner.items())),
        alias_modules=frozenset(alias_modules),
        constraints_by_owner=dict(sorted(constraints_by_owner.items())),
    )


# --- Clause 1: sibling-domain ``_ids`` import -----------------------------


_REGISTRY_IDS_MODULE = "aeat.domain.calculations.registry._ids"


def _domain_root(dotted: str) -> str | None:
    """Return the ``domain.<root>`` segment for ``dotted`` if any."""
    parts = dotted.split(".")
    if len(parts) >= 3 and parts[0] == "aeat" and parts[1] == "domain":
        return parts[2]
    return None


def _resolve_relative_import(consumer: str, module: str | None, level: int) -> str | None:
    """Resolve a ``from .x import y`` style module to an absolute path."""
    if level == 0:
        return module
    consumer_parts = consumer.split(".")
    if level > len(consumer_parts):
        return None
    base = consumer_parts[:-level]
    if module:
        base.extend(module.split("."))
    return ".".join(base) if base else None


def _iter_import_from(tree: ast.Module) -> Iterator[ast.ImportFrom]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            yield node


def find_sibling_domain_id_imports(root: Path = AEAT_ROOT) -> list[Finding]:
    """Detect ``domain.<a>`` importing from ``domain.<b>._ids`` for ``a != b``.

    Returns:
        A list of :class:`Finding` records for each sibling-domain id import.
    """
    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        dotted = _module_dotted_path(path, root)
        consumer_domain = _domain_root(dotted)
        if consumer_domain is None:
            continue
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        for node in _iter_import_from(tree):
            target = _resolve_relative_import(dotted, node.module, node.level)
            if target is None:
                continue
            if target == _REGISTRY_IDS_MODULE:
                continue
            target_domain = _domain_root(target)
            if target_domain is None or target_domain == consumer_domain:
                continue
            if not (target.endswith("._ids") or target.split(".")[-1] == "_ids"):
                continue
            imported = ", ".join(alias.name for alias in node.names)
            findings.append(
                Finding(
                    path,
                    node.lineno,
                    (
                        f"sibling-domain _ids import: aeat.domain.{consumer_domain} "
                        f"imports {imported!r} from {target}"
                    ),
                )
            )
    return findings


# --- Clause 2: private-name import from any ``_ids.py`` -------------------


def _is_consumer_layer(dotted: str) -> bool:
    return any(dotted == root or dotted.startswith(root + ".") for root in _CONSUMER_LAYER_ROOTS)


def find_private_id_imports(root: Path = AEAT_ROOT) -> list[Finding]:
    """Detect leading-underscore imports from any ``_ids.py`` module.

    An adapter, application, or entrypoint module may consume the public
    typed-id aliases exported by an ``_ids.py`` module. It MUST NOT
    reach into the underlying regex constants, length constants, or
    private re-aliases that the ``_ids.py`` module uses to construct
    them. The public alias names are the cross-layer contract; the
    private constants are an implementation detail.

    Returns:
        A list of :class:`Finding` records for each private-name import.
    """
    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        dotted = _module_dotted_path(path, root)
        if not _is_consumer_layer(dotted):
            continue
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        for node in _iter_import_from(tree):
            target = _resolve_relative_import(dotted, node.module, node.level)
            if target is None:
                continue
            if not target.endswith("._ids"):
                continue
            for alias in node.names:
                if alias.name.startswith("_"):
                    findings.append(
                        Finding(
                            path,
                            node.lineno,
                            (
                                f"private-name import from {target}: {alias.name!r} "
                                f"is an internal constant; consume the public alias instead"
                            ),
                        )
                    )
    return findings


# --- Clause 3: ``_HEX_*_LENGTH`` constant outside owning ``_ids.py`` ------


def _iter_module_assignments(tree: ast.Module) -> Iterator[tuple[str, int]]:
    """Yield ``(name, lineno)`` for every module-level name assignment."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield target.id, node.lineno
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            yield node.target.id, node.lineno


def find_misplaced_hex_length_constants(root: Path = AEAT_ROOT) -> list[Finding]:
    """Detect ``_HEX_*_LENGTH`` constants declared outside an ``_ids.py``.

    Returns:
        A list of :class:`Finding` records for each misplaced constant.
    """
    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        if path.name == "_ids.py":
            continue
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        for name, lineno in _iter_module_assignments(tree):
            if _HEX_LENGTH_CONSTANT_RE.match(name):
                findings.append(
                    Finding(
                        path,
                        lineno,
                        (
                            f"misplaced shape constant {name!r}: hex-length constants "
                            f"belong only in the owning _ids.py module"
                        ),
                    )
                )
    return findings


# --- Clause 4: bare-``str`` ``<owner>_id`` BaseModel field ----------------


def _is_basemodel_subclass(node: ast.ClassDef) -> bool:
    """Return whether ``node`` textually inherits from ``BaseModel``.

    The walker inspects each base name as a plain attribute or name
    expression. A class is recognised as a pydantic model when any base
    spells ``BaseModel`` (the canonical pydantic import name) — the
    project does not subclass under an aliased name, so a textual match
    is sufficient. Generic-parameterised bases (e.g. ``BaseModel[T]``)
    are unwrapped through the ``ast.Subscript`` value.
    """
    for base in node.bases:
        target = base
        if isinstance(target, ast.Subscript):
            target = target.value
        if isinstance(target, ast.Name) and target.id == "BaseModel":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "BaseModel":
            return True
    return False


def _annotation_is_bare_str(annotation: ast.expr) -> bool:
    """Return whether ``annotation`` is ``str`` or ``str | None``.

    A typed alias (``WorkUnitId``, ``ProfileId``) is an ``ast.Name``
    other than ``str``; an inline ``Annotated[str, ...]`` is an
    ``ast.Subscript``; either form passes the detector. The detector
    only flags the two bare shapes that drop the typed contract.
    """
    if isinstance(annotation, ast.Name) and annotation.id == "str":
        return True
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        left = annotation.left
        right = annotation.right
        if _annotation_is_bare_str(left) and _expr_is_none(right):
            return True
        if _annotation_is_bare_str(right) and _expr_is_none(left):
            return True
    return False


def _expr_is_none(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _is_alias_declaration_module(path: Path) -> bool:
    """Return whether ``path`` declares typed-id aliases (skip in detector)."""
    return _is_alias_module(path)


def find_bare_str_typed_id_fields(
    root: Path = AEAT_ROOT,
    inventory: AliasInventory | None = None,
) -> list[Finding]:
    """Detect bare-``str`` ``<owner>_id`` fields on pydantic models.

    For every pydantic ``BaseModel`` subclass declared under ``root``,
    inspect every ``AnnAssign`` field whose target name matches
    ``<owner>_id``. If ``<owner>`` is in the alias inventory and the
    annotation is bare ``str`` (or ``str | None``), the field is
    classified against the alias's introspected constraint shape:

    * **Shape-compatible** — every value the field accepts today would
      also be accepted by the alias. The detector emits a promotion
      candidate finding so the migration pressure stays on without
      requiring an allowlist of pre-approved sites.
    * **Shape-incompatible** — the alias is stricter than the field's
      declared constraints. The detector emits a structured rationale
      derived from the introspected constraint deltas (``min_length``,
      ``max_length``, ``pattern``) so the operator can see why
      promotion would reject values the field currently accepts.

    The classification follows the substitutability pre-filter from the
    swarm-audit-cadence rule and consults ``inventory.constraints_by_owner``
    directly; there is no protect list.

    Returns:
        A list of :class:`Finding` records, one per flagged field.
    """
    if inventory is None:
        inventory = build_alias_inventory(root)
    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        if _is_alias_declaration_module(path):
            continue
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        literals = _module_literal_string_assignments(tree)
        for class_node in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            if not _is_basemodel_subclass(class_node):
                continue
            for field in class_node.body:
                if not isinstance(field, ast.AnnAssign):
                    continue
                target = field.target
                if not isinstance(target, ast.Name):
                    continue
                name = target.id
                if not name.endswith("_id"):
                    continue
                owner = name[:-3]
                if owner not in inventory.aliases_by_owner:
                    continue
                if not _annotation_is_bare_str(field.annotation):
                    continue
                alias = inventory.aliases_by_owner[owner]
                alias_shape = inventory.constraints_by_owner.get(owner, ConstraintShape())
                candidate_shape = _extract_field_constraint_shape(
                    field.annotation, field.value, literals
                )
                compatible, rationale = _classify_promotion(candidate_shape, alias_shape)
                if compatible:
                    message = (
                        f"bare-str typed-id field {class_node.name}.{name}: "
                        f"shape-compatible promotion candidate; alias {alias!r} "
                        f"accepts every value the field accepts"
                    )
                else:
                    message = (
                        f"bare-str typed-id field {class_node.name}.{name}: "
                        f"shape-incompatible with alias {alias!r}; {rationale}"
                    )
                findings.append(Finding(path, field.lineno, message))
    return findings


# --- Clause 5: sibling-domain ``_enums`` import ----------------------------


def _is_named_domain_subpackage(domain_segment: str) -> bool:
    """Return whether ``domain_segment`` identifies a named subpackage.

    A named subpackage starts with a letter, not an underscore.  Module-level
    ``_enums.py`` / ``_constants.py`` / ``_protocols.py`` placed directly under
    ``domain/`` have ``parts[2] == '_enums'`` etc. and are NOT sibling
    subpackages — they are the root domain package's own internal modules.
    """
    return bool(domain_segment) and domain_segment[0].isalpha()


def find_sibling_domain_enum_imports(root: Path = AEAT_ROOT) -> list[Finding]:
    """Detect ``domain.<a>`` importing from ``domain.<b>._enums`` for ``a != b``.

    Only named subpackages (those whose name starts with a letter) are
    considered sibling domains.  Root-level ``domain/_enums.py`` is not a
    sibling subpackage and imports from it are not flagged by this clause.

    Returns:
        A list of :class:`Finding` records for each sibling-domain enum import.
    """
    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        dotted = _module_dotted_path(path, root)
        consumer_domain = _domain_root(dotted)
        if consumer_domain is None or not _is_named_domain_subpackage(consumer_domain):
            continue
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        for node in _iter_import_from(tree):
            target = _resolve_relative_import(dotted, node.module, node.level)
            if target is None:
                continue
            target_domain = _domain_root(target)
            if (
                target_domain is None
                or target_domain == consumer_domain
                or not _is_named_domain_subpackage(target_domain)
            ):
                continue
            seg = target.split(".")
            if seg[-1] != "_enums":
                continue
            imported = ", ".join(alias.name for alias in node.names)
            findings.append(
                Finding(
                    path,
                    node.lineno,
                    (
                        f"sibling-domain _enums import: aeat.domain.{consumer_domain} "
                        f"imports {imported!r} from {target}"
                    ),
                )
            )
    return findings


# --- Clause 6: sibling-domain ``_constants`` import ------------------------


def find_sibling_domain_constant_imports(root: Path = AEAT_ROOT) -> list[Finding]:
    """Detect ``domain.<a>`` importing from ``domain.<b>._constants`` for ``a != b``.

    Only named subpackages (those whose name starts with a letter) are
    considered sibling domains.

    Returns:
        A list of :class:`Finding` records for each sibling-domain constant import.
    """
    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        dotted = _module_dotted_path(path, root)
        consumer_domain = _domain_root(dotted)
        if consumer_domain is None or not _is_named_domain_subpackage(consumer_domain):
            continue
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        for node in _iter_import_from(tree):
            target = _resolve_relative_import(dotted, node.module, node.level)
            if target is None:
                continue
            target_domain = _domain_root(target)
            if (
                target_domain is None
                or target_domain == consumer_domain
                or not _is_named_domain_subpackage(target_domain)
            ):
                continue
            seg = target.split(".")
            if seg[-1] != "_constants":
                continue
            imported = ", ".join(alias.name for alias in node.names)
            findings.append(
                Finding(
                    path,
                    node.lineno,
                    (
                        f"sibling-domain _constants import: aeat.domain.{consumer_domain} "
                        f"imports {imported!r} from {target}"
                    ),
                )
            )
    return findings


# --- Clause 7: sibling-domain ``_protocols`` import ------------------------


def find_sibling_domain_protocol_imports(root: Path = AEAT_ROOT) -> list[Finding]:
    """Detect ``domain.<a>`` importing from ``domain.<b>._protocols`` for ``a != b``.

    Only named subpackages (those whose name starts with a letter) are
    considered sibling domains.

    Returns:
        A list of :class:`Finding` records for each sibling-domain protocol import.
    """
    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        dotted = _module_dotted_path(path, root)
        consumer_domain = _domain_root(dotted)
        if consumer_domain is None or not _is_named_domain_subpackage(consumer_domain):
            continue
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        for node in _iter_import_from(tree):
            target = _resolve_relative_import(dotted, node.module, node.level)
            if target is None:
                continue
            target_domain = _domain_root(target)
            if (
                target_domain is None
                or target_domain == consumer_domain
                or not _is_named_domain_subpackage(target_domain)
            ):
                continue
            seg = target.split(".")
            if seg[-1] != "_protocols":
                continue
            imported = ", ".join(alias.name for alias in node.names)
            findings.append(
                Finding(
                    path,
                    node.lineno,
                    (
                        f"sibling-domain _protocols import: aeat.domain.{consumer_domain} "
                        f"imports {imported!r} from {target}"
                    ),
                )
            )
    return findings


# --- Clause 8: private-name cross-package import (non-``_ids.py``) ---------

#: Dotted module prefixes that are exempt from the private-name cross-package rule.
#: These correspond to the 13 protect-list sites from the core-authority ADR.
_CLAUSE8_PROTECT_MODULES: frozenset[str] = frozenset(
    {
        "aeat.core.identity",
        "aeat.adapters.persistence.storage",
        "aeat.application.auth",
    }
)


def _is_same_package(consumer_dotted: str, imported_dotted: str) -> bool:
    """Return whether ``consumer_dotted`` and ``imported_dotted`` share an immediate package.

    Two modules share a package when their parent dotted paths are identical
    (e.g. ``aeat.core.errors._registry`` and ``aeat.core.errors._base``
    both live in ``aeat.core.errors``).
    """

    def _parent(dotted: str) -> str:
        parts = dotted.rsplit(".", 1)
        return parts[0] if len(parts) > 1 else ""

    return _parent(consumer_dotted) == _parent(imported_dotted)


def find_private_name_cross_package_imports(root: Path = AEAT_ROOT) -> list[Finding]:
    """Detect cross-package imports of ``_``-prefixed names from non-``_ids.py`` modules.

    Only production modules are considered: test modules (``test_*.py`` or
    ``*_test.py``) are excluded because they legitimately reach into private
    helpers to exercise internal behaviour. Dunder names (``__version__``,
    ``__all__``, etc.) are excluded because they are a Python convention and
    not private API. Relative imports are within-package by definition and are
    excluded. Imports from modules on the ADR protect list are excluded.

    Returns:
        A list of :class:`Finding` records for each violating import.
    """
    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        if path.name.startswith("test_") or path.stem.endswith("_test"):
            continue
        # files inside test-infrastructure directories are not production modules
        if "tests" in path.parts:
            continue
        dotted = _module_dotted_path(path, root)
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        for node in _iter_import_from(tree):
            if node.level > 0:
                # relative import — within the same package by definition
                continue
            mod = node.module or ""
            if not mod:
                continue
            if mod.endswith("._ids") or mod.split(".")[-1] == "_ids":
                # covered by clause 2
                continue
            if any(
                mod == protect or mod.startswith(protect + ".")
                for protect in _CLAUSE8_PROTECT_MODULES
            ):
                continue
            if _is_same_package(dotted, mod):
                continue
            for alias in node.names:
                name = alias.name
                if not name.startswith("_"):
                    continue
                if name.startswith("__") and name.endswith("__"):
                    # dunder — not a private API name
                    continue
                findings.append(
                    Finding(
                        path,
                        node.lineno,
                        (
                            f"private-name cross-package import: {name!r} imported from "
                            f"{mod} is a private implementation detail; expose a public API"
                        ),
                    )
                )
    return findings


# --- Clause 9: same-name ``UPPER_SNAKE_CASE`` multi-declaration ------------

_UPPER_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9_]+$")

#: Dotted module prefixes exempt from the same-name constant rule (protect list).
_CLAUSE9_PROTECT_MODULES: frozenset[str] = frozenset(
    {
        "aeat.core.identity",
        "aeat.adapters.persistence.storage",
        "aeat.application.auth",
    }
)


def _literal_constant_value(node: ast.expr) -> object:
    """Return the literal value of ``node`` if it is a simple constant, else sentinel."""
    _MISSING = object()
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
            return -node.operand.value
    return _MISSING


def find_same_name_constant_multi_declarations(
    root: Path = AEAT_ROOT,
) -> list[Finding]:
    """Detect ``UPPER_SNAKE_CASE`` constants with the same name and value in multiple modules.

    Only module-level assignments whose right-hand side is a simple literal
    (int, float, str, bytes, bool, or unary-negated number) are considered.
    Test modules and protect-list modules are excluded.

    Returns:
        A list of :class:`Finding` records, one per duplicated constant site.
    """
    _MISSING = object()
    # name -> list of (dotted_module, literal_value, path, lineno)
    registry: dict[str, list[tuple[str, object, Path, int]]] = {}

    for path in iter_aeat_modules(root):
        if path.name.startswith("test_") or "test_" in path.stem:
            continue
        dotted = _module_dotted_path(path, root)
        if any(
            dotted == protect or dotted.startswith(protect + ".")
            for protect in _CLAUSE9_PROTECT_MODULES
        ):
            continue
        tree, err = _parse(path)
        if err is not None:
            continue
        assert tree is not None
        for name, lineno in _iter_module_assignments(tree):
            if not _UPPER_SNAKE_RE.match(name):
                continue
            # find the corresponding value node
            val = _MISSING
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name) and tgt.id == name and node.lineno == lineno:
                            val = _literal_constant_value(node.value)
                elif (
                    isinstance(node, ast.AnnAssign)
                    and isinstance(node.target, ast.Name)
                    and node.target.id == name
                    and node.lineno == lineno
                    and node.value is not None
                ):
                    val = _literal_constant_value(node.value)
            if val is _MISSING:
                continue
            registry.setdefault(name, []).append((dotted, val, path, lineno))

    findings: list[Finding] = []
    for const_name, sites in registry.items():
        # group by value
        by_value: dict[object, list[tuple[str, object, Path, int]]] = {}
        for site in sites:
            _val = site[1]
            # use repr as dict key to handle unhashable types safely
            key = repr(_val)
            by_value.setdefault(key, []).append(site)
        for _val_repr, same_value_sites in by_value.items():
            if len(same_value_sites) < 2:
                continue
            modules = {s[0] for s in same_value_sites}
            if len(modules) < 2:
                continue
            for dotted, _v, path, lineno in same_value_sites:
                findings.append(
                    Finding(
                        path,
                        lineno,
                        (
                            f"same-name constant multi-declaration: {const_name!r} "
                            f"declared in {len(same_value_sites)} modules with the same "
                            f"literal value; import from the canonical site instead"
                        ),
                    )
                )
    return findings


# --- Clause 10: bare-``str`` ``<owner>_kind/_status/_state`` BaseModel field --

_KIND_STATUS_STATE_SUFFIXES: tuple[tuple[str, int], ...] = (
    ("_kind", 5),
    ("_status", 7),
    ("_state", 6),
)


def _is_string_alias_value(value_node: ast.expr) -> bool:
    """Return whether ``value_node`` represents a string-backed typed alias.

    A string-backed alias is one whose value is a ``Literal[...]`` or
    an ``Annotated[str, ...]``.  Enum class bodies and integer Literals
    are excluded.  This guards the clause-10 inventory against false
    positives from enum classes and integer constants that happen to
    share the ``Kind``/``Status``/``State`` naming suffix.
    """
    if not isinstance(value_node, ast.Subscript):
        return False
    outer = value_node.value
    if isinstance(outer, ast.Name):
        outer_name = outer.id
    elif isinstance(outer, ast.Attribute):
        outer_name = outer.attr
    else:
        return False
    if outer_name == "Literal":
        return True
    if outer_name == "Annotated":
        # first type arg must be str
        slice_node = value_node.slice
        if isinstance(slice_node, ast.Tuple) and slice_node.elts:
            first = slice_node.elts[0]
            if isinstance(first, ast.Name) and first.id == "str":
                return True
    return False


def build_kind_status_state_alias_inventory(root: Path = AEAT_ROOT) -> AliasInventory:
    """Discover string-backed typed aliases for ``<owner>Kind``, ``<owner>Status``, ``<owner>State``.

    Only ``Literal[...]`` and ``Annotated[str, ...]`` aliases are
    considered.  Enum classes and non-string type aliases sharing the
    ``Kind``/``Status``/``State`` naming suffix are excluded so the
    inventory does not generate false-positive clause-10 violations.

    Returns:
        An :class:`AliasInventory` mapping owner prefixes to kind, status,
        and state alias names.
    """
    by_owner: dict[str, str] = {}
    alias_modules: set[str] = set()
    for path in iter_aeat_modules(root):
        tree, _err = _parse(path)
        if tree is None:
            continue
        for node in tree.body:
            name: str | None = None
            value_node: ast.expr | None = None
            if isinstance(node, ast.Assign):
                if node.targets and isinstance(node.targets[0], ast.Name):
                    name = node.targets[0].id
                    value_node = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                name = node.target.id
                value_node = node.value
            elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
                name = node.name.id
                value_node = getattr(node, "value", None)
            if not name or not name[0].isupper() or name.startswith("_"):
                continue
            if value_node is None or not _is_string_alias_value(value_node):
                continue
            for suffix, strip in _KIND_STATUS_STATE_SUFFIXES:
                camel_suffix = suffix.lstrip("_").capitalize()
                if name.endswith(camel_suffix):
                    snake = _camel_to_snake(name)
                    owner = snake[: -strip]
                    by_owner.setdefault(owner, name)
                    alias_modules.add(_module_dotted_path(path, root))
                    break
    return AliasInventory(
        aliases_by_owner=dict(sorted(by_owner.items())),
        alias_modules=frozenset(alias_modules),
    )


def find_bare_str_kind_status_state_fields(
    root: Path = AEAT_ROOT,
    inventory: AliasInventory | None = None,
) -> list[Finding]:
    """Detect bare-``str`` ``<owner>_kind/_status/_state`` fields on pydantic models.

    For every pydantic ``BaseModel`` subclass declared under ``root``,
    inspect every ``AnnAssign`` field whose target name ends in
    ``_kind``, ``_status``, or ``_state``. If a typed alias for that
    owner exists in the inventory and the annotation is bare ``str`` (or
    ``str | None``), the field is flagged.

    Returns:
        A list of :class:`Finding` records, one per flagged field.
    """
    if inventory is None:
        inventory = build_kind_status_state_alias_inventory(root)
    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        for class_node in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            if not _is_basemodel_subclass(class_node):
                continue
            for field in class_node.body:
                if not isinstance(field, ast.AnnAssign):
                    continue
                target = field.target
                if not isinstance(target, ast.Name):
                    continue
                fname = target.id
                matched_owner: str | None = None
                matched_alias: str | None = None
                for suffix, strip in _KIND_STATUS_STATE_SUFFIXES:
                    if fname.endswith(suffix):
                        owner = fname[: -strip]
                        if owner in inventory.aliases_by_owner:
                            matched_owner = owner
                            matched_alias = inventory.aliases_by_owner[owner]
                            break
                if matched_owner is None or matched_alias is None:
                    continue
                if not _annotation_is_bare_str(field.annotation):
                    continue
                findings.append(
                    Finding(
                        path,
                        field.lineno,
                        (
                            f"bare-str typed field {class_node.name}.{fname}: a typed "
                            f"alias {matched_alias!r} exists for owner {matched_owner!r}; "
                            f"consume it"
                        ),
                    )
                )
    return findings
