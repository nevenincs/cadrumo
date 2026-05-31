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
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

__all__ = (
    "AEAT_ROOT",
    "AliasInventory",
    "Finding",
    "PROMOTE001_PROTECT_LIST",
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
    """

    aliases_by_owner: dict[str, str]
    alias_modules: frozenset[str]


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


def _module_alias_names(tree: ast.Module) -> list[str]:
    """Return module-level identifiers that name a typed-id alias.

    A typed alias may appear as a bare ``Assign`` (``WorkUnitId =
    Annotated[...]``), an ``AnnAssign`` with a type annotation, a PEP 695
    ``TypeAlias`` statement (``type CasillaId = Annotated[...]``), or as
    an ``ImportFrom`` re-export (``from ._bucket import BucketId``).
    The detector accepts any module-level name ending in ``Id`` whose
    first character is uppercase, mirroring the ADR Rule 4 naming
    convention.
    """
    names: list[str] = []
    for node in tree.body:
        candidates: list[str] = []
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    candidates.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            candidates.append(node.target.id)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            candidates.append(node.name.id)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported = alias.asname or alias.name
                candidates.append(imported)
        for candidate in candidates:
            if (
                candidate.endswith("Id")
                and candidate[:1].isupper()
                and not candidate.startswith("_")
            ):
                names.append(candidate)
    return names


def _is_alias_module(path: Path) -> bool:
    """Return whether ``path`` is the alias-declaring module for a package.

    The ADR pattern places typed aliases in ``_ids.py``. The
    :mod:`aeat.core.identity` package aggregates aliases through its
    package ``__init__`` (re-exporting from ``_bucket.py``,
    ``_profile.py``, ``_snapshot.py``), so a package ``__init__`` that
    re-exports typed aliases is also recognised.
    """
    name = path.name
    if name == "_ids.py":
        return True
    if name == "__init__.py" and path.parent.name == "identity":
        return True
    return False


def build_alias_inventory(root: Path = AEAT_ROOT) -> AliasInventory:
    """Discover typed-id aliases declared under ``root``."""
    by_owner: dict[str, str] = {}
    alias_modules: set[str] = set()
    for path in iter_aeat_modules(root):
        if not _is_alias_module(path):
            continue
        tree, _err = _parse(path)
        if tree is None:
            continue
        names = _module_alias_names(tree)
        if not names:
            continue
        alias_modules.add(_module_dotted_path(path, root))
        for alias in names:
            owner = _camel_to_snake(alias[:-2])  # strip trailing ``Id``
            by_owner.setdefault(owner, alias)
    return AliasInventory(
        aliases_by_owner=dict(sorted(by_owner.items())),
        alias_modules=frozenset(alias_modules),
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
    """Detect ``domain.<a>`` importing from ``domain.<b>._ids`` for ``a != b``."""
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
    """Detect ``_HEX_*_LENGTH`` constants declared outside an ``_ids.py``."""
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

#: Sites excluded from the Clause 4 bare-str ``_id`` detector.
#:
#: Each entry is a ``(dotted_module, class_name, field_name)`` triple.
#: A site is excluded when the alias constraint shape is stricter than the
#: field's declared constraint, so promoting the bare ``str`` to the typed alias
#: would cause runtime validation failures on existing data.
#:
#: Rationale codes:
#:   HEX64   — alias requires a 64-char hex digest; field accepts arbitrary strings.
#:   MINLEN  — alias requires min_length=1; field has an empty-string default.
#:   PATTERN — alias has a character-class pattern that rejects existing values.
#:   NODOC   — field documents a non-hex-64 shape in its module docstring; alias is hex-64.
#:   TRANSIT — field carries values from an external transit format that doesn't
#:             match the alias constraint (e.g. 3-digit modelo codes, registry kebab refs).
PROMOTE001_PROTECT_LIST: frozenset[tuple[str, str, str]] = frozenset(
    {
        # HEX64 — TransactionId requires hex-64; these fields accept any str
        ("aeat.application.aggregation._iva_ledger", "IvaLedgerAggregationIssue", "transaction_id"),
        ("aeat.application.aggregation._iva_ledger", "ProrrataLedgerReference", "transaction_id"),
        ("aeat.application.aggregation._renta_income_ledger", "RentaIncomeLedgerAggregationIssue", "transaction_id"),
        ("aeat.application.aggregation._renta_income_ledger", "RentaIncomeObservation", "transaction_id"),
        ("aeat.application.aggregation._renta_ledger", "RentaLedgerAggregationIssue", "transaction_id"),
        ("aeat.application.invoices._linking", "InvoiceTransactionLinkResult", "transaction_id"),
        ("aeat.application.invoices._reconciliation", "ReconciliationSkippedSuggestion", "transaction_id"),
        ("aeat.application.ledger._models", "LedgerReviewQuery", "transaction_id"),
        ("aeat.application.ledger._models", "BulkClassifyRow", "transaction_id"),
        ("aeat.application.ledger._models", "BulkClassifyFailure", "transaction_id"),
        ("aeat.application.ledger._models", "ApplyRulesAppliedRow", "transaction_id"),
        ("aeat.application.ledger._preflight", "LedgerPreflightIssue", "transaction_id"),
        ("aeat.application.review._models", "LedgerReviewRecord", "transaction_id"),
        ("aeat.domain.transactions._models", "TransactionEvidenceProvenanceEntry", "evidence_id"),
        ("aeat.domain.transactions._models", "Transaction", "invoice_id"),
        ("aeat.domain.transactions._raw_transaction", "RawTransaction", "transaction_id"),
        # HEX64 — EvidenceId is hex-64; these fields accept arbitrary strings
        ("aeat.application.ledger._evidence", "PurchaseInvoiceEvidence", "evidence_id"),
        # HEX64 — InvoiceId likely hex-64; these fields accept arbitrary strings
        ("aeat.application.invoices._linking", "InvoiceTransactionLinkResult", "invoice_id"),
        ("aeat.application.invoices._queries", "InvoiceListRow", "invoice_id"),
        ("aeat.application.invoices._reconciliation", "ReconciliationSkippedSuggestion", "invoice_id"),
        ("aeat.application.ledger._business_operation_invoice", "BusinessOperationInvoice", "invoice_id"),
        ("aeat.application.review._models", "InvoiceReviewRecord", "invoice_id"),
        ("aeat.domain.invoices._service", "ReconciliationSuggestion", "invoice_id"),
        ("aeat.domain.invoices._service", "LinkInconsistency", "invoice_id"),
        ("aeat.domain.calculations.registry._bindings", "InvoiceObservation", "invoice_id"),
        # HEX64/NODOC — SnapshotId is hex-64; snapshot_id fields use non-hex-64 shape
        ("aeat.application.live.test_snapshot_base", "ProbeSnapshot", "snapshot_id"),
        ("aeat.application.live._borrador_100", "Borrador100Snapshot", "snapshot_id"),
        ("aeat.application.live._censo", "CensoSnapshot", "snapshot_id"),
        ("aeat.application.user_profile._censo_sync", "CensoProfileComparison", "snapshot_id"),
        ("aeat.application.user_profile._censo_sync", "CensoApplyResult", "snapshot_id"),
        ("aeat.application.user_profile", "ProfileSnapshot", "snapshot_id"),
        ("aeat.application.user_profile", "ProfileStaleCheckReport", "snapshot_id"),
        # MINLEN — BucketId has min_length=1; these fields have empty-string defaults
        ("aeat.adapters.persistence.storage.runtime", "StorageRuntime", "bucket_id"),
        ("aeat.application.live.test_snapshot_base", "ProbeSnapshot", "bucket_id"),
        ("aeat.core._bucket_pointer", "BucketPointer", "bucket_id"),
        ("aeat.core.config", "StorageRouteClassification", "bucket_id"),
        ("aeat.application.live._censo", "CensoSnapshot", "profile_id"),
        # HEX64 — RevisionId constraint incompatible with these fields
        ("aeat.application.state_projection", "ModeloReadinessRequest", "revision_id"),
        ("aeat.application.state_projection", "ProjectionModeloReadiness", "revision_id"),
        ("aeat.application.user_profile", "ProfilePreflightReport", "revision_id"),
        ("aeat.application.user_profile", "ProfileSnapshotRequest", "revision_id"),
        ("aeat.application.user_profile", "ProfileSnapshot", "revision_id"),
        ("aeat.domain.user_profile._registry_contract", "UserProfileRegistryContractIssue", "revision_id"),
        ("aeat.adapters.persistence.storage.sql.secure_objects", "SecureObjectRawRow", "revision_id"),
        # TRANSIT — ModeloId requires ^\d{3}$; these carry arbitrary model identifiers in transit
        ("aeat.adapters.outbound.google._calc_sheets_pull", "PullMetadata", "modelo_id"),
        ("aeat.application.storage.calc_sheets._parity_harness", "ParityReport", "modelo_id"),
        ("aeat.application.storage.calc_sheets._records", "SheetExportMetadata", "modelo_id"),
        ("aeat.domain.user_profile._registry_contract", "UserProfileRegistryContractIssue", "modelo_id"),
        # PATTERN — ProfileId has character-class pattern; field values may not match
        ("aeat.application.state_projection", "ProjectionActiveProfile", "profile_id"),
        # TRANSIT — ConstructId; registry construct identifiers use different shape
        ("aeat.domain.user_profile._registry_contract", "UserProfileRegistryContractIssue", "construct_id"),
        # TRANSIT — BindingId/CasillaId; registry ref shapes differ from hex-64
        ("aeat.application.aggregation._source_mesh", "CalculationSourceDiagnostic", "binding_id"),
        ("aeat.application.aggregation._source_mesh", "CalculationSourceDiagnostic", "casilla_id"),
    }
)


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
    protect_list: frozenset[tuple[str, str, str]] | None = None,
) -> list[Finding]:
    """Detect bare-``str`` ``<owner>_id`` fields on pydantic models.

    For every pydantic ``BaseModel`` subclass declared under ``root``,
    inspect every ``AnnAssign`` field whose target name matches
    ``<owner>_id``. If ``<owner>`` is in the alias inventory and the
    annotation is bare ``str`` (or ``str | None``), the field is flagged
    — the typed alias for that identity exists and is the contract the
    field should consume.

    Sites in ``protect_list`` (default: :data:`PROMOTE001_PROTECT_LIST`) are
    excluded from the findings.  Each protect-list entry is a
    ``(dotted_module, class_name, field_name)`` triple documenting a site
    where the alias constraint shape is incompatible with the field's existing
    data contract, making promotion without a broader data-migration unsafe.
    """
    if inventory is None:
        inventory = build_alias_inventory(root)
    if protect_list is None:
        protect_list = PROMOTE001_PROTECT_LIST
    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        if _is_alias_declaration_module(path):
            continue
        dotted = _module_dotted_path(path, root)
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
                name = target.id
                if not name.endswith("_id"):
                    continue
                owner = name[:-3]
                if owner not in inventory.aliases_by_owner:
                    continue
                if not _annotation_is_bare_str(field.annotation):
                    continue
                if (dotted, class_node.name, name) in protect_list:
                    continue
                alias = inventory.aliases_by_owner[owner]
                findings.append(
                    Finding(
                        path,
                        field.lineno,
                        (
                            f"bare-str typed-id field {class_node.name}.{name}: a typed "
                            f"alias {alias!r} exists for owner {owner!r}; consume it"
                        ),
                    )
                )
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
        if isinstance(node.operand, ast.Constant):
            return -node.operand.value  # type: ignore[operator]
    return _MISSING


def find_same_name_constant_multi_declarations(
    root: Path = AEAT_ROOT,
) -> list[Finding]:
    """Detect ``UPPER_SNAKE_CASE`` constants with the same name and value in multiple modules.

    Only module-level assignments whose right-hand side is a simple literal
    (int, float, str, bytes, bool, or unary-negated number) are considered.
    Test modules and protect-list modules are excluded.
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
