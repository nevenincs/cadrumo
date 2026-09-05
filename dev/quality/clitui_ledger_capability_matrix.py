"""The typed, freshness-bound Ledger backend/CLI/TUI capability matrix.

The matrix is a reviewed campaign ledger, not a collection of optimistic
statuses. It binds rows to accepted and current denominator censuses, keeps
applicability separate from implementation and proof, and admits evidence only
when its role and subject snapshot are current.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal, TypedDict, cast, override

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator
from pydantic_core import to_jsonable_python

from cadrumo.core.aggregation import LEDGER_BINDING_SOURCE_KINDS, BindingSourceKind
from cadrumo.core.transport_locus import TransportLocus, TransportRole, TransportShape
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.binding_targets import casillas_by_binding
from cadrumo.entrypoints.cli.command_spec import CommandSpec

SCHEMA_VERSION: Final[int] = 4
_DIGEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")
_CAPABILITY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^ledger(?:\.[a-z][a-z0-9_]*)(?:\.[a-z][a-z0-9_]*)*$")
_EVIDENCE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^evidence\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_FINDING_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^finding\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_SUBJECT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^subject\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_CENSUS_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^census\.ledger(?:\.[a-z][a-z0-9_]*)*$")
_ATTESTATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^attestation\.ledger(?:\.[a-z][a-z0-9_]*)*$")
_REVIEW_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^review\.ledger(?:\.[a-z][a-z0-9_]*)*$")
_PLACEHOLDER_TEXT: Final[frozenset[str]] = frozenset({"", "n/a", "na", "none", "tbd", "todo", "unknown", "unmeasured"})
ACCEPTED_LEDGER_PARITY_PLAN_OWNER: Final[str] = "clitui-ledger"
LEDGER_REGISTRY_ROUTE_CENSUS_SCHEMA_VERSION: Final[Literal[1]] = 1
LEDGER_REGISTRY_ROUTE_CENSUS_ROOT: Final[Literal["cadrumo.ledger_registry_route_census"]] = (
    "cadrumo.ledger_registry_route_census"
)
_LEDGER_REGISTRY_ROUTE_CENSUS_FRAME: Final[bytes] = b"cadrumo:ledger-registry-route-census:v1\x00"
_LEDGER_REGISTRY_SOURCE_SET_FRAME: Final[bytes] = b"cadrumo:ledger-registry-source-set:v1\x00"
LEDGER_TUI_SUPPORTED_SURFACE_CENSUS_SCHEMA_VERSION: Final[Literal[1]] = 1
LEDGER_TUI_SUPPORTED_SURFACE_CENSUS_ROOT: Final[Literal["cadrumo.ledger_tui_supported_surface_census"]] = (
    "cadrumo.ledger_tui_supported_surface_census"
)
_LEDGER_TUI_SUPPORTED_SURFACE_CENSUS_FRAME: Final[bytes] = b"cadrumo:ledger-tui-supported-surface-census:v1\x00"
LEDGER_UNION_DENOMINATOR_SCHEMA_VERSION: Final[Literal[4]] = 4
LEDGER_UNION_DENOMINATOR_ROOT: Final[Literal["cadrumo.ledger_union_denominator"]] = "cadrumo.ledger_union_denominator"
_LEDGER_UNION_DENOMINATOR_FRAME: Final[bytes] = b"cadrumo:ledger-union-denominator:v4\x00"
_LEDGER_MATRIX_CONTRACT_FRAME: Final[bytes] = b"cadrumo:ledger-capability-matrix-contract:v1\x00"
_LEDGER_TUI_SUPPORTED_SURFACE_SOURCE_SET_FRAME: Final[bytes] = b"cadrumo:ledger-tui-supported-surface-source-set:v1\x00"
_LEDGER_UNION_ROW_REVIEWED_AT: Final[datetime] = datetime.fromisoformat("2026-09-05T12:00:00+02:00")
_LEDGER_MESSAGE_TYPES: Final[tuple[str, ...]] = (
    "LedgerBackRequested",
    "LedgerEvidenceReviewRequested",
    "LedgerReviewRequested",
    "LedgerRouteRequested",
)
_LEDGER_MUTATION_DOORS: Final[tuple[str, ...]] = (
    "classification_submitter",
    "import_submitter",
    "link_submitter",
)


def _length_frame(value: bytes) -> bytes:
    """Frame one byte string without delimiter ambiguity."""
    return len(value).to_bytes(8, byteorder="big", signed=False) + value


def _canonical_json_text(value: object) -> str:
    """Normalize one registry value to the census' canonical JSON scalar text."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=False)
    return json.dumps(to_jsonable_python(value), ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _validated_selector_json(selector: BaseModel | Mapping[str, object]) -> str:
    """Serialize every typed selector field, retaining defaults and explicit nulls.

    Registry construction hydrates Ledger selectors to strict Pydantic models.
    ``source`` is loader-injected discriminator metadata rather than a selector
    axis, so it is the sole excluded field. A raw mapping is rejected to keep
    this evidence projection bound to the validated-model boundary.
    """
    if not isinstance(selector, BaseModel):
        raise TypeError("ledger registry census requires a validated selector model")
    return _canonical_json_text(
        selector.model_dump(
            mode="json",
            exclude={"source"},
            exclude_defaults=False,
            exclude_none=False,
            exclude_unset=False,
        )
    )


class LedgerRegistryRouteTargetV1(BaseModel):
    """One direct registry casilla target; an empty tuple means no direct target."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    casilla_id: str = Field(min_length=1)
    section: tuple[str, ...]


class LedgerRegistryRouteRowV1(BaseModel):
    """One ledger binding declaration projected from the validated authority."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    source: BindingSourceKind
    modelo_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    valid_from: date
    valid_to: date | None
    period_selector_json: str = Field(min_length=2)
    binding_id: str = Field(min_length=1)
    selector_json: str = Field(min_length=2)
    targets: tuple[LedgerRegistryRouteTargetV1, ...]

    @model_validator(mode="after")
    def _canonical_nested_values(self) -> LedgerRegistryRouteRowV1:
        for field_name in ("period_selector_json", "selector_json"):
            text = getattr(self, field_name)
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{field_name} must be valid JSON") from exc
            if text != _canonical_json_text(decoded):
                raise ValueError(f"{field_name} must use canonical JSON")
        target_keys = tuple((target.casilla_id, target.section) for target in self.targets)
        if target_keys != tuple(sorted(target_keys)):
            raise ValueError("targets must use canonical casilla/section order")
        if len(set(target_keys)) != len(target_keys):
            raise ValueError("targets must be unique")
        return self

    @property
    def sort_key(self) -> tuple[str, str, str, str]:
        """Return the complete deterministic declaration identity."""
        return self.source.value, self.modelo_id, self.revision_id, self.binding_id


class LedgerRegistryRouteCensusV1(BaseModel):
    """Versioned canonical projection; it contains no independent route facts."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    root: Literal["cadrumo.ledger_registry_route_census"]
    schema_version: Literal[1]
    source_set_digest: str
    rows: tuple[LedgerRegistryRouteRowV1, ...]

    @model_validator(mode="after")
    def _canonical_rows(self) -> LedgerRegistryRouteCensusV1:
        _require_digest(self.source_set_digest, field_name="source_set_digest")
        keys = tuple(row.sort_key for row in self.rows)
        if keys != tuple(sorted(keys)):
            raise ValueError("rows must use canonical source/modelo/revision/binding order")
        if len(set(keys)) != len(keys):
            raise ValueError("rows must have unique declaration identities")
        return self

    @property
    def calculated_digest(self) -> str:
        """Hash the domain-separated, length-framed canonical JSON bytes."""
        return ledger_registry_route_census_digest(self)


def ledger_registry_source_files(authority: ValidatedRegistryAuthority) -> tuple[Path, ...]:
    """Return exact TOML files declaring a member of the live seven-family set."""
    needles = tuple(f'source = "{source.value}"'.encode() for source in sorted(LEDGER_BINDING_SOURCE_KINDS))
    return tuple(
        path
        for path in sorted(
            authority.root.rglob("*.toml"), key=lambda item: item.relative_to(authority.source_root).as_posix()
        )
        if any(needle in path.read_bytes() for needle in needles)
    )


def ledger_registry_source_set_digest(
    authority: ValidatedRegistryAuthority,
    *,
    source_files: Iterable[Path] | None = None,
    source_records: Iterable[tuple[str, bytes]] | None = None,
) -> str:
    """Hash sorted source-root-relative paths and bytes with explicit framing."""
    if source_files is not None and source_records is not None:
        raise ValueError("provide source_files or source_records, not both")
    records: list[tuple[str, bytes]]
    if source_records is not None:
        records = list(source_records)
    else:
        files = tuple(source_files) if source_files is not None else ledger_registry_source_files(authority)
        records = []
        for path in files:
            relative = path.resolve().relative_to(authority.source_root.resolve()).as_posix()
            records.append((relative, path.read_bytes()))
    payload = bytearray(_LEDGER_REGISTRY_SOURCE_SET_FRAME)
    for relative, body in sorted(records):
        payload.extend(_length_frame(relative.encode("utf-8")))
        payload.extend(_length_frame(body))
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def build_ledger_registry_route_census(
    authority: ValidatedRegistryAuthority | None = None,
) -> LedgerRegistryRouteCensusV1:
    """Derive the canonical census only from the live validated registry authority."""
    authority = bundled_authority() if authority is None else authority
    authority.validate_registry()
    rows: list[LedgerRegistryRouteRowV1] = []
    for modelo in authority.modelos:
        for revision in modelo.revisions.values():
            target_ids = casillas_by_binding(revision)
            casillas = {casilla.id: casilla for casilla in revision.casillas}
            for binding in revision.bindings:
                if binding.source not in LEDGER_BINDING_SOURCE_KINDS:
                    continue
                targets = tuple(
                    sorted(
                        (
                            LedgerRegistryRouteTargetV1(casilla_id=casilla_id, section=casillas[casilla_id].section)
                            for casilla_id in target_ids.get(binding.id, ())
                        ),
                        key=lambda target: (target.casilla_id, target.section),
                    )
                )
                rows.append(
                    LedgerRegistryRouteRowV1(
                        source=binding.source,
                        modelo_id=modelo.id,
                        revision_id=revision.id,
                        valid_from=revision.valid_from,
                        valid_to=revision.valid_to,
                        period_selector_json=_canonical_json_text(revision.period_selector),
                        binding_id=binding.id,
                        selector_json=_validated_selector_json(binding.selector),
                        targets=targets,
                    )
                )
    return LedgerRegistryRouteCensusV1(
        root=LEDGER_REGISTRY_ROUTE_CENSUS_ROOT,
        schema_version=LEDGER_REGISTRY_ROUTE_CENSUS_SCHEMA_VERSION,
        source_set_digest=ledger_registry_source_set_digest(authority),
        rows=tuple(sorted(rows, key=lambda row: row.sort_key)),
    )


def ledger_registry_route_census_bytes(census: LedgerRegistryRouteCensusV1) -> bytes:
    """Serialize a validated census with explicit domain and payload framing."""
    canonical = LedgerRegistryRouteCensusV1.model_validate(census.model_dump(mode="python"))
    encoded = _canonical_json_text(canonical).encode("utf-8")
    return _LEDGER_REGISTRY_ROUTE_CENSUS_FRAME + _length_frame(encoded)


def ledger_registry_route_census_digest(census: LedgerRegistryRouteCensusV1) -> str:
    """Return the canonical route-census SHA-256 digest."""
    return f"sha256:{hashlib.sha256(ledger_registry_route_census_bytes(census)).hexdigest()}"


class LedgerTuiRouteRowV1(BaseModel):
    """One declared internal Ledger route and its production reachability."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    destination: str = Field(pattern=r"^ledger\.[a-z][a-z0-9_]*$")
    area: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    screen: str = Field(pattern=r"^Ledger[A-Za-z0-9]+Screen$")
    reachability: Literal["component_only", "installed"]


class LedgerTuiSupportedSurfaceCensusV1(BaseModel):
    """Canonical projection of live Ledger TUI declarations and composition."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    root: Literal["cadrumo.ledger_tui_supported_surface_census"]
    schema_version: Literal[1]
    source_set_digest: str
    routes: tuple[LedgerTuiRouteRowV1, ...]
    controller: str
    root_factory: str
    resolver: str
    installed_outer_destination: str
    initial_internal_destination: str
    message_consumers: tuple[str, ...]
    injected_read_action_ids: tuple[str, ...]
    installed_mutation_doors: tuple[str, ...]
    cli_tui_capabilities: tuple[tuple[str, str], ...]
    harness_files: tuple[str, ...]
    harness_test_functions: int = Field(ge=0)

    @model_validator(mode="after")
    def _canonical_projection(self) -> LedgerTuiSupportedSurfaceCensusV1:
        _require_digest(self.source_set_digest, field_name="source_set_digest")
        destinations = tuple(row.destination for row in self.routes)
        if destinations != tuple(sorted(destinations)) or len(set(destinations)) != len(destinations):
            raise ValueError("routes must have unique destinations in canonical order")
        for field_name in (
            "message_consumers",
            "injected_read_action_ids",
            "installed_mutation_doors",
            "harness_files",
        ):
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be unique and canonically ordered")
        if self.cli_tui_capabilities != tuple(sorted(set(self.cli_tui_capabilities))):
            raise ValueError("cli_tui_capabilities must be unique and canonically ordered")
        installed = tuple(row.destination for row in self.routes if row.reachability == "installed")
        if installed != (self.initial_internal_destination,):
            raise ValueError("the initial internal destination must be the sole installed route")
        return self

    @property
    def calculated_digest(self) -> str:
        """Hash the domain-separated, length-framed canonical projection."""
        return ledger_tui_supported_surface_census_digest(self)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ledger_tui_supported_surface_source_files(repo_root: Path | None = None) -> tuple[Path, ...]:
    """Return the structural Ledger closure and its installed-composition evidence.

    The census must move when Ledger screens, their concrete production entry
    points, or the installed workbench path changes.  It deliberately does
    not hash the unrelated TUI estate: that would reopen this Ledger-only
    denominator for an AEAT Sync or Modelo change with no selected row.
    """
    root = _repository_root() if repo_root is None else repo_root.resolve()
    tui_root = root / "src/cadrumo/entrypoints/tui"
    ledger_production = tuple(
        path
        for path in (tui_root / "ledger").rglob("*.py")
        if "tests" not in path.relative_to(tui_root / "ledger").parts
        and "__pycache__" not in path.parts
    )
    composition_sources = tuple(
        tui_root / name for name in ("app.py", "installed_session.py", "launcher.py")
    )
    ledger_tests = tuple((tui_root / "ledger/tests").glob("test_*.py"))
    composition_tests = tuple(
        tui_root / "tests" / name
        for name in (
            "test_installed_generation_composition.py",
            "test_installed_workbench.py",
            "test_launcher_entry_point.py",
        )
    )
    application_sources = tuple(
        root / relative
        for relative in (
            "src/cadrumo/application/ledger/workspace.py",
            "src/cadrumo/application/ledger/workspace_reader.py",
            "src/cadrumo/application/search/installed_workbench.py",
            "src/cadrumo/application/workbench_generation.py",
        )
    )
    cli_sources = tuple((root / "src/cadrumo/entrypoints/cli").glob("_app_ledger*_command_specs.py"))
    files = tuple(
        sorted(
            {
                *ledger_production,
                *composition_sources,
                *ledger_tests,
                *composition_tests,
                *application_sources,
                *cli_sources,
            }
        )
    )
    missing = tuple(path for path in files if not path.is_file())
    if missing:
        raise FileNotFoundError(f"Ledger TUI census source is unavailable: {missing[0]}")
    return files


def _source_records(
    files: Iterable[Path],
    *,
    repo_root: Path,
) -> tuple[tuple[str, bytes], ...]:
    return tuple(
        sorted((path.resolve().relative_to(repo_root.resolve()).as_posix(), path.read_bytes()) for path in files)
    )


def ledger_tui_supported_surface_source_set_digest(
    *,
    repo_root: Path | None = None,
    source_records: Iterable[tuple[str, bytes]] | None = None,
) -> str:
    """Hash sorted repository-relative paths and bodies with unsigned u64 frames."""
    root = _repository_root() if repo_root is None else repo_root.resolve()
    records = (
        tuple(source_records)
        if source_records is not None
        else _source_records(ledger_tui_supported_surface_source_files(root), repo_root=root)
    )
    ordered = tuple(sorted(records))
    if len({relative for relative, _body in ordered}) != len(ordered):
        raise ValueError("Ledger TUI census source paths must be unique")
    payload = bytearray(_LEDGER_TUI_SUPPORTED_SURFACE_SOURCE_SET_FRAME)
    for relative, body in ordered:
        payload.extend(_length_frame(relative.encode("utf-8")))
        payload.extend(_length_frame(body))
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _parsed_sources(records: Iterable[tuple[str, bytes]]) -> dict[str, ast.Module]:
    return {relative: ast.parse(body.decode("utf-8"), filename=relative) for relative, body in records}


def _named_function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = tuple(
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )
    if len(matches) != 1:
        raise ValueError(f"Ledger TUI census requires exactly one {name} function")
    return matches[0]


def _ledger_route_rows(tree: ast.Module) -> tuple[tuple[str, str, str], ...]:
    assignments = tuple(
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "LEDGER_ROUTES"
    )
    if len(assignments) != 1 or not isinstance(assignments[0].value, (ast.Tuple, ast.List)):
        raise ValueError("LEDGER_ROUTES must have one statically readable sequence assignment")
    rows: list[tuple[str, str, str]] = []
    for node in assignments[0].value.elts:
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "LedgerRouteV1":
            raise ValueError("LEDGER_ROUTES entries must be direct LedgerRouteV1 declarations")
        if len(node.args) != 3:
            raise ValueError("LedgerRouteV1 declarations must have three positional arguments")
        destination, area, screen = node.args
        if (
            not isinstance(destination, ast.Constant)
            or not isinstance(destination.value, str)
            or not isinstance(area, ast.Attribute)
            or not isinstance(screen, ast.Name)
        ):
            raise ValueError("Ledger route declaration is not statically census-readable")
        rows.append((destination.value, area.attr, screen.id))
    return tuple(sorted(rows))


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    values: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            for target in targets:
                if isinstance(target, ast.Name):
                    values[target.id] = value.value
    return values


def _call_named(node: ast.AST, name: str) -> tuple[ast.Call, ...]:
    return tuple(
        candidate
        for candidate in ast.walk(node)
        if isinstance(candidate, ast.Call) and isinstance(candidate.func, ast.Name) and candidate.func.id == name
    )


class _ReturnCollector(ast.NodeVisitor):
    """Collect returns in one function body without entering nested definitions."""

    def __init__(self) -> None:
        self.returns: list[ast.Return] = []

    @override
    def visit_Return(self, node: ast.Return) -> None:
        self.returns.append(node)

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    @override
    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return


def _function_returns(function: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[ast.Return, ...]:
    collector = _ReturnCollector()
    for statement in function.body:
        collector.visit(statement)
    return tuple(collector.returns)


@dataclass(frozen=True)
class _AliasDefinition:
    value: ast.expr
    target: ast.Name


class _BindingCollector(ast.NodeVisitor):
    """Collect same-scope writes without entering nested definitions."""

    def __init__(self) -> None:
        self.bindings: dict[str, list[ast.AST]] = {}

    def record(self, name: str, node: ast.AST) -> None:
        self.bindings.setdefault(name, []).append(node)

    def _visit_function_header(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in (*node.args.defaults, *(value for value in node.args.kw_defaults if value is not None)):
            self.visit(default)
        annotations = (
            *(argument.annotation for argument in node.args.posonlyargs if argument.annotation is not None),
            *(argument.annotation for argument in node.args.args if argument.annotation is not None),
            *(argument.annotation for argument in node.args.kwonlyargs if argument.annotation is not None),
        )
        for annotation in annotations:
            self.visit(annotation)
        if node.args.vararg is not None and node.args.vararg.annotation is not None:
            self.visit(node.args.vararg.annotation)
        if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
            self.visit(node.args.kwarg.annotation)
        if node.returns is not None:
            self.visit(node.returns)
        for type_parameter in getattr(node, "type_params", ()):
            self.visit(type_parameter)

    def _visit_comprehension(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> None:
        for generator in node.generators:
            self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)

    @override
    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.record(node.id, node)

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.record(node.name, node)
        self._visit_function_header(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.record(node.name, node)
        self._visit_function_header(node)

    @override
    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in (*node.args.defaults, *(value for value in node.args.kw_defaults if value is not None)):
            self.visit(default)

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.record(node.name, node)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)
        for type_parameter in getattr(node, "type_params", ()):
            self.visit(type_parameter)

    @override
    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node)

    @override
    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node)

    @override
    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node)

    @override
    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node)

    @override
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.record(alias.asname or alias.name.split(".", maxsplit=1)[0], node)

    @override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self.record(alias.asname or alias.name, node)

    @override
    def visit_Global(self, node: ast.Global) -> None:
        for name in node.names:
            self.record(name, node)

    @override
    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        for name in node.names:
            self.record(name, node)

    @override
    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self.record(node.name, node)
        self.generic_visit(node)

    @override
    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name is not None:
            self.record(node.name, node)
        self.generic_visit(node)

    @override
    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name is not None:
            self.record(node.name, node)

    @override
    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest is not None:
            self.record(node.rest, node)
        self.generic_visit(node)


def _simple_assignments(function: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, _AliasDefinition]:
    assignments: dict[str, _AliasDefinition] = {}
    for statement in function.body:
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            target = statement.targets[0]
            assignments[target.id] = _AliasDefinition(value=statement.value, target=target)
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.value is not None
        ):
            assignments[statement.target.id] = _AliasDefinition(value=statement.value, target=statement.target)
    return assignments


def _resolve_simple_alias(
    expression: ast.expr,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> ast.expr:
    assignments = _simple_assignments(function)
    collector = _BindingCollector()
    arguments = (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)
    for argument in arguments:
        collector.record(argument.arg, argument)
    if function.args.vararg is not None:
        collector.record(function.args.vararg.arg, function.args.vararg)
    if function.args.kwarg is not None:
        collector.record(function.args.kwarg.arg, function.args.kwarg)
    for statement in function.body:
        collector.visit(statement)
    seen: set[str] = set()
    while isinstance(expression, ast.Name) and expression.id in assignments:
        definition = assignments[expression.id]
        bindings = collector.bindings.get(expression.id, [])
        if bindings != [definition.target]:
            raise ValueError(f"Ledger TUI census alias {expression.id!r} is not uniquely and unconditionally defined")
        if definition.target.lineno >= expression.lineno:
            raise ValueError(f"Ledger TUI census alias {expression.id!r} is read before its definition")
        if expression.id in seen:
            raise ValueError("Ledger TUI census found a cyclic return alias")
        seen.add(expression.id)
        expression = definition.value
    return expression


def _single_effective_return(function: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.expr:
    returns = _function_returns(function)
    values = tuple(
        node.value
        for node in returns
        if node.value is not None and not (isinstance(node.value, ast.Constant) and node.value.value is None)
    )
    if len(values) != 1:
        raise ValueError(f"{function.name} must have exactly one non-null return dataflow")
    return _resolve_simple_alias(values[0], function)


def _returned_nested_function(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    expected_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    returned = _single_effective_return(function)
    if not isinstance(returned, ast.Name) or returned.id != expected_name:
        raise ValueError(f"{function.name} must return its exact nested {expected_name} factory")
    nested = tuple(
        node
        for node in function.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == expected_name
    )
    if len(nested) != 1:
        raise ValueError(f"{function.name} must define exactly one nested {expected_name} factory")
    return nested[0]


def _installed_action_ids(tree: ast.Module) -> tuple[str, ...]:
    function = _named_function(tree, "compose_authenticated_root_inputs_provider")
    constructors = _call_named(function, "InstalledWorkbenchFactoryDependenciesV1")
    if len(constructors) != 1:
        raise ValueError("installed Ledger dependencies constructor is not unique")
    constants = _module_string_constants(tree)
    values: list[str] = []
    for keyword in constructors[0].keywords:
        if keyword.arg not in {"ledger_review_action", "ledger_evidence_action"}:
            continue
        value = keyword.value
        if (
            not isinstance(value, ast.Call)
            or not isinstance(value.func, ast.Name)
            or value.func.id != "action"
            or len(value.args) != 1
            or not isinstance(value.args[0], ast.Name)
            or value.args[0].id not in constants
        ):
            raise ValueError("installed Ledger action reference is not statically census-readable")
        values.append(constants[value.args[0].id])
    return tuple(sorted(values))


def _installed_ledger_factory_call(tree: ast.Module) -> ast.Call:
    function = _named_function(tree, "_ledger_generation_factory")
    create = _returned_nested_function(function, "create")
    returned = _single_effective_return(create)
    if not isinstance(returned, ast.Call):
        raise ValueError("installed Ledger create factory must return a screen invocation")
    factory_expression = _resolve_simple_alias(returned.func, create)
    if (
        not isinstance(factory_expression, ast.Call)
        or not isinstance(factory_expression.func, ast.Name)
        or factory_expression.func.id != "ledger_screen_factory"
    ):
        raise ValueError("installed Ledger create return does not invoke ledger_screen_factory")
    return factory_expression


def _installed_outer_destination(tree: ast.Module) -> str:
    function = _named_function(tree, "compose_installed_workbench_generation_provider")
    enrolled = tuple(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and target.value.id == "factories"
            and isinstance(target.slice, ast.Constant)
            and target.slice.value == "workbench.ledger"
            for target in node.targets
        )
        and isinstance(node.value, ast.Name)
        and node.value.id == "ledger_factory"
    )
    destinations_calls = _call_named(function, "destinations")
    if len(enrolled) != 1 or not destinations_calls:
        raise ValueError("installed workbench does not enroll the Ledger outer factory")
    return "workbench.ledger"


def _initial_route_area(tree: ast.Module) -> str:
    function = _named_function(tree, "ledger_screen_factory")
    create = _returned_nested_function(function, "create")
    returned = _single_effective_return(create)
    if (
        not isinstance(returned, ast.Call)
        or not isinstance(returned.func, ast.Name)
        or returned.func.id != "resolve_ledger_screen"
        or len(returned.args) != 2
    ):
        raise ValueError("Ledger root create return does not resolve one screen")
    target = _resolve_simple_alias(returned.args[1], create)
    if (
        not isinstance(target, ast.Call)
        or not isinstance(target.func, ast.Attribute)
        or target.func.attr != "route_target"
        or len(target.args) != 1
    ):
        raise ValueError("Ledger root factory initial route is not statically census-readable")
    area = _resolve_simple_alias(target.args[0], create)
    if (
        not isinstance(area, ast.Attribute)
        or not isinstance(area.value, ast.Name)
        or area.value.id != "LedgerWorkspaceArea"
    ):
        raise ValueError("Ledger root factory initial route is not statically census-readable")
    return area.attr


def _reachable_recipient_classes(
    production_trees: Mapping[str, ast.Module],
    route_screens: set[str],
) -> tuple[ast.ClassDef, ...]:
    classes = {
        node.name: node for tree in production_trees.values() for node in tree.body if isinstance(node, ast.ClassDef)
    }
    pending = ["CadrumoTuiApp", *sorted(route_screens)]
    reachable: set[str] = set()
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        node = classes.get(name)
        if node is None:
            raise ValueError(f"installed Ledger recipient class is unavailable: {name}")
        reachable.add(name)
        pending.extend(base.id for base in node.bases if isinstance(base, ast.Name) and base.id in classes)
    return tuple(classes[name] for name in sorted(reachable))


def _message_consumers(classes: Iterable[ast.ClassDef]) -> tuple[str, ...]:
    conventional = {
        f"on_{re.sub(r'(?<!^)(?=[A-Z])', '_', message).lower()}": message for message in _LEDGER_MESSAGE_TYPES
    }
    found: set[str] = set()
    for class_node in classes:
        for method in class_node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if method.name in conventional:
                found.add(conventional[method.name])
            for decorator in method.decorator_list:
                if not isinstance(decorator, ast.Call) or not decorator.args:
                    continue
                decorator_name = (
                    decorator.func.id
                    if isinstance(decorator.func, ast.Name)
                    else decorator.func.attr
                    if isinstance(decorator.func, ast.Attribute)
                    else None
                )
                message_arg = decorator.args[0]
                if (
                    decorator_name == "on"
                    and isinstance(message_arg, ast.Name)
                    and message_arg.id in _LEDGER_MESSAGE_TYPES
                ):
                    found.add(message_arg.id)
    return tuple(sorted(found))


def build_ledger_tui_supported_surface_census(
    *,
    repo_root: Path | None = None,
    source_records: Iterable[tuple[str, bytes]] | None = None,
    cli_tui_capabilities: Iterable[tuple[str, str]] | None = None,
) -> LedgerTuiSupportedSurfaceCensusV1:
    """Derive the supported-surface census without importing the product TUI."""
    root = _repository_root() if repo_root is None else repo_root.resolve()
    records = (
        tuple(source_records)
        if source_records is not None
        else _source_records(ledger_tui_supported_surface_source_files(root), repo_root=root)
    )
    trees = _parsed_sources(records)
    routes_path = "src/cadrumo/entrypoints/tui/ledger/routes.py"
    launcher_path = "src/cadrumo/entrypoints/tui/launcher.py"
    installed_path = "src/cadrumo/entrypoints/tui/installed_session.py"
    for required in (routes_path, launcher_path, installed_path):
        if required not in trees:
            raise ValueError(f"Ledger TUI census source set is missing {required}")
    route_facts = _ledger_route_rows(trees[routes_path])
    if not route_facts:
        raise ValueError("Ledger TUI census found no internal routes")

    outer_destination = _installed_outer_destination(trees[launcher_path])
    installed_factory_call = _installed_ledger_factory_call(trees[launcher_path])
    initial_area = _initial_route_area(trees[routes_path])
    initial_destination = next(
        (destination for destination, area, _screen in route_facts if area == initial_area),
        None,
    )
    if initial_destination is None:
        raise ValueError("Ledger root factory initial area is absent from the route table")

    production_trees = {
        relative: tree
        for relative, tree in trees.items()
        if relative.startswith("src/cadrumo/entrypoints/tui/") and "/tests/" not in relative
    }
    route_screens = {screen for _destination, _area, screen in route_facts}
    defined_classes = {
        node.name for tree in production_trees.values() for node in tree.body if isinstance(node, ast.ClassDef)
    }
    if not route_screens <= defined_classes or "LedgerWorkspaceController" not in defined_classes:
        raise ValueError("Ledger TUI census route/controller class is unavailable")
    _named_function(trees[routes_path], "resolve_ledger_screen")
    initial_screen = next(screen for destination, _area, screen in route_facts if destination == initial_destination)
    recipient_classes = _reachable_recipient_classes(production_trees, {initial_screen})
    consumers = _message_consumers(recipient_classes)
    installed_keywords = {keyword.arg for keyword in installed_factory_call.keywords if keyword.arg is not None}
    installed_doors = tuple(sorted(installed_keywords & set(_LEDGER_MUTATION_DOORS)))
    read_actions = _installed_action_ids(trees[installed_path])

    if cli_tui_capabilities is None:
        from cadrumo.entrypoints.cli._app_ledger_command_specs import LEDGER_CLI_COMMAND_CENSUS

        cli_tui_capabilities = ((entry.command_key, entry.tui_capability.value) for entry in LEDGER_CLI_COMMAND_CENSUS)
    cli_statuses = tuple(sorted(cli_tui_capabilities))
    test_records = tuple((relative, tree) for relative, tree in trees.items() if "/tests/test_" in relative)
    harness_files = tuple(sorted(relative for relative, _tree in test_records))
    harness_test_functions = sum(
        1
        for _relative, tree in test_records
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    )
    return LedgerTuiSupportedSurfaceCensusV1(
        root=LEDGER_TUI_SUPPORTED_SURFACE_CENSUS_ROOT,
        schema_version=LEDGER_TUI_SUPPORTED_SURFACE_CENSUS_SCHEMA_VERSION,
        source_set_digest=ledger_tui_supported_surface_source_set_digest(source_records=records),
        routes=tuple(
            LedgerTuiRouteRowV1(
                destination=destination,
                area=area,
                screen=screen,
                reachability="installed" if destination == initial_destination else "component_only",
            )
            for destination, area, screen in route_facts
        ),
        controller="LedgerWorkspaceController",
        root_factory="ledger_screen_factory",
        resolver="resolve_ledger_screen",
        installed_outer_destination=outer_destination,
        initial_internal_destination=initial_destination,
        message_consumers=consumers,
        injected_read_action_ids=read_actions,
        installed_mutation_doors=installed_doors,
        cli_tui_capabilities=cli_statuses,
        harness_files=harness_files,
        harness_test_functions=harness_test_functions,
    )


def ledger_tui_supported_surface_census_bytes(census: LedgerTuiSupportedSurfaceCensusV1) -> bytes:
    """Serialize a validated census with explicit domain and payload framing."""
    canonical = LedgerTuiSupportedSurfaceCensusV1.model_validate(census.model_dump(mode="python"))
    encoded = _canonical_json_text(canonical).encode("utf-8")
    return _LEDGER_TUI_SUPPORTED_SURFACE_CENSUS_FRAME + _length_frame(encoded)


def ledger_tui_supported_surface_census_digest(census: LedgerTuiSupportedSurfaceCensusV1) -> str:
    """Return the canonical supported-surface SHA-256 digest."""
    return f"sha256:{hashlib.sha256(ledger_tui_supported_surface_census_bytes(census)).hexdigest()}"


class LedgerCapabilityAxis(StrEnum):
    """The independent backend, surface, and proof axes."""

    BACKEND = "backend"
    CLI = "cli"
    TUI = "tui"
    COMPOSITION = "composition"
    ARTIFACT = "artifact"
    PROVENANCE = "provenance"
    REGISTRY = "registry"
    PROOF = "proof"


class ApplicabilityState(StrEnum):
    """Whether one axis applies to a Ledger capability."""

    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"


class AxisProofState(StrEnum):
    """The evidence maturity of an applicable axis."""

    NOT_APPLICABLE = "not_applicable"
    UNPROVEN = "unproven"
    PARTIAL = "partial"
    PROVEN = "proven"


class SurfaceCapabilityState(StrEnum):
    """The observed implementation state of a surface axis."""

    NOT_APPLICABLE = "not_applicable"
    ABSENT = "absent"
    PARTIAL = "partial"
    PROVEN = "proven"


class CapabilityAnnotation(StrEnum):
    """Ownership and reachability facts that must not substitute for proof."""

    CLI_OWNED = "cli_owned"
    DELEGATING = "delegating"
    COMPONENT_ONLY = "component_only"
    INSTALLED = "installed"


class InitialCliOwnership(StrEnum):
    """Immutable ownership captured at the first denominator review."""

    NOT_CLI_OWNED = "not_cli_owned"
    CLI_OWNED = "cli_owned"


class LedgerGapClass(StrEnum):
    """The closed taxonomy of unresolved Ledger gaps."""

    AUTHORITY = "authority"
    PRODUCT = "product"
    COMPOSITION = "composition"
    PROOF = "proof"
    REACHABILITY = "reachability"
    ARTIFACT = "artifact"
    PROVENANCE = "provenance"
    REGISTRY = "registry"


class DenominatorSourceKind(StrEnum):
    """The mandatory input streams of the union denominator."""

    CLI_ENDPOINT = "cli_endpoint"
    CLI_SUBOPERATION = "cli_suboperation"
    BACKEND_ONLY = "backend_only"
    MISSING_PRODUCT = "missing_product"
    REGISTRY_ROUTE = "registry_route"
    ARTIFACT_PRODUCT = "artifact_product"
    SUPPORTED_SURFACE = "supported_surface"


class SemanticHomeStatus(StrEnum):
    """Whether an adjudicated canonical contract exists or is plan-owned."""

    EXISTING = "existing"
    PLANNED = "planned"


class LedgerCapabilityEffect(StrEnum):
    """The behavior distinction that prevents unlike denominator rows merging."""

    QUERY = "query"
    MUTATION = "mutation"
    PROPOSAL = "proposal"
    ARTIFACT = "artifact"
    ARTIFACT_QUERY = "artifact_query"
    REGISTRY_ROUTE = "registry_route"


class LedgerRegistryDestinationStatus(StrEnum):
    """How one reviewed row reaches the validated calculation registry."""

    NOT_APPLICABLE = "not_applicable"
    DIRECT = "direct"
    APPLICATION_SIDECAR = "application_sidecar"
    DESTINATIONLESS = "destinationless"


class LedgerUnionRowReviewRuling(StrEnum):
    """The bounded conclusion of the exhaustive denominator-row review."""

    COMPLETE_WITH_OPEN_GAPS = "complete_with_open_gaps"


class ReviewRuling(StrEnum):
    """The closed independent-review decision vocabulary."""

    ACCEPT = "accept"
    ACCEPT_WITH_REQUIRED_CHANGES = "accept_with_required_changes"
    REJECT = "reject"


class EvidenceKind(StrEnum):
    """The durable source form of a cited evidence coordinate."""

    CODE = "code"
    TEST = "test"
    COMMAND = "command"
    ARTIFACT = "artifact"
    REVIEW = "review"
    REFERENCE = "reference"


class EvidenceRole(StrEnum):
    """The precise conclusion evidence is allowed to support."""

    APPLICABILITY_REVIEW = "applicability_review"
    BASELINE = "baseline"
    DIRECT_BACKEND_BEHAVIOR = "direct_backend_behavior"
    ADAPTER_DETECTOR = "adapter_detector"
    CLI_SUCCESS = "cli_success"
    CLI_REFUSAL = "cli_refusal"
    CLI_ARTIFACT = "cli_artifact"
    TUI_PARITY = "tui_parity"
    TUI_REACHABILITY = "tui_reachability"
    MATRIX_PUBLICATION = "matrix_publication"
    INDEPENDENT_ENGINEERING_REVIEW = "independent_engineering_review"


class LedgerGate(StrEnum):
    """Ordered G0--G4 campaign gates."""

    G0_DENOMINATOR_AND_OWNERSHIP_FREEZE = "g0_denominator_and_ownership_freeze"
    G1_SEMANTIC_AUTHORITY_RECOVERY = "g1_semantic_authority_recovery"
    G2_BACKEND_PRODUCT_COMPLETENESS = "g2_backend_product_completeness"
    G3_CLI_CLEAN_BREAK_AND_COMPLETENESS = "g3_cli_clean_break_and_completeness"
    G4_TUI_ADMISSION_AND_PARITY = "g4_tui_admission_and_parity"


LEDGER_TUI_HOLD_UNTIL_GATE: Final[LedgerGate] = LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS
_GATE_ORDER: Final[tuple[LedgerGate, ...]] = tuple(LedgerGate)
_ALL_AXES: Final[frozenset[LedgerCapabilityAxis]] = frozenset(LedgerCapabilityAxis)
_SURFACE_AXES: Final[frozenset[LedgerCapabilityAxis]] = frozenset(
    {LedgerCapabilityAxis.BACKEND, LedgerCapabilityAxis.CLI, LedgerCapabilityAxis.TUI}
)
_G2_AXES: Final[frozenset[LedgerCapabilityAxis]] = frozenset(
    {
        LedgerCapabilityAxis.BACKEND,
        LedgerCapabilityAxis.COMPOSITION,
        LedgerCapabilityAxis.ARTIFACT,
        LedgerCapabilityAxis.PROVENANCE,
        LedgerCapabilityAxis.REGISTRY,
        LedgerCapabilityAxis.PROOF,
    }
)
_G2_GAP_CLASSES: Final[frozenset[LedgerGapClass]] = frozenset(
    {
        LedgerGapClass.PRODUCT,
        LedgerGapClass.COMPOSITION,
        LedgerGapClass.PROOF,
        LedgerGapClass.ARTIFACT,
        LedgerGapClass.PROVENANCE,
        LedgerGapClass.REGISTRY,
    }
)
_G3_GAP_CLASSES: Final[frozenset[LedgerGapClass]] = frozenset(
    {LedgerGapClass.AUTHORITY, LedgerGapClass.PRODUCT, LedgerGapClass.REACHABILITY, LedgerGapClass.ARTIFACT}
)


def _require_non_placeholder(value: str, *, field_name: str) -> str:
    if value.strip().lower() in _PLACEHOLDER_TEXT:
        raise ValueError(f"{field_name} must be bounded, not a placeholder")
    return value


def _require_identity(value: str, *, field_name: str, pattern: re.Pattern[str]) -> str:
    if not pattern.fullmatch(value):
        raise ValueError(f"{field_name} must be a stable dotted identity: {value!r}")
    return value


def _require_digest(value: str, *, field_name: str) -> str:
    if not _DIGEST_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a sha256 digest")
    return value


def _require_observed_at(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must carry an explicit timezone")
    return value


def _canonical_value(value: object) -> object:
    """Return a recursively stable JSON value for digest-bearing contracts."""
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="python"))
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        pairs = sorted(((str(key), item) for key, item in mapping.items()), key=lambda item: item[0])
        return {key: _canonical_value(item) for key, item in pairs}
    if isinstance(value, (frozenset, set)):
        values = cast(frozenset[object] | set[object], value)
        normalized = [_canonical_value(item) for item in values]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        )
    if isinstance(value, tuple | list):
        values = cast(tuple[object, ...] | list[object], value)
        return [_canonical_value(item) for item in values]
    return value


def _canonical_digest(payload: object) -> str:
    """Return the SHA-256 digest of the contract's canonical JSON payload."""
    encoded = json.dumps(_canonical_value(payload), ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class _EvidenceRoleContract:
    kinds: frozenset[EvidenceKind]
    axes: frozenset[LedgerCapabilityAxis] | None
    single_axis: bool = False


_EVIDENCE_ROLE_CONTRACTS: Final[Mapping[EvidenceRole, _EvidenceRoleContract]] = {
    EvidenceRole.APPLICABILITY_REVIEW: _EvidenceRoleContract(frozenset({EvidenceKind.REVIEW}), None, True),
    EvidenceRole.BASELINE: _EvidenceRoleContract(
        frozenset(
            {EvidenceKind.CODE, EvidenceKind.TEST, EvidenceKind.COMMAND, EvidenceKind.ARTIFACT, EvidenceKind.REFERENCE}
        ),
        None,
        True,
    ),
    EvidenceRole.DIRECT_BACKEND_BEHAVIOR: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}), frozenset({LedgerCapabilityAxis.BACKEND})
    ),
    EvidenceRole.ADAPTER_DETECTOR: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}), frozenset({LedgerCapabilityAxis.CLI})
    ),
    EvidenceRole.CLI_SUCCESS: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}), frozenset({LedgerCapabilityAxis.CLI})
    ),
    EvidenceRole.CLI_REFUSAL: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}), frozenset({LedgerCapabilityAxis.CLI})
    ),
    EvidenceRole.CLI_ARTIFACT: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST, EvidenceKind.ARTIFACT}),
        frozenset({LedgerCapabilityAxis.CLI, LedgerCapabilityAxis.ARTIFACT}),
    ),
    EvidenceRole.TUI_PARITY: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}),
        frozenset({LedgerCapabilityAxis.BACKEND, LedgerCapabilityAxis.CLI, LedgerCapabilityAxis.TUI}),
    ),
    EvidenceRole.TUI_REACHABILITY: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}), frozenset({LedgerCapabilityAxis.TUI})
    ),
    EvidenceRole.MATRIX_PUBLICATION: _EvidenceRoleContract(frozenset({EvidenceKind.REFERENCE}), _ALL_AXES),
    EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW: _EvidenceRoleContract(frozenset({EvidenceKind.REVIEW}), _ALL_AXES),
}


class LedgerCapabilityIdentityV1(BaseModel):
    """Stable family, operation, and sub-operation identifiers."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    capability_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    suboperation_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_hierarchy(self) -> LedgerCapabilityIdentityV1:
        # Derived from the model for the same reason as the semantic home above.
        for field_name in type(self).model_fields:
            value = getattr(self, field_name)
            if isinstance(value, str):
                _require_identity(value, field_name=field_name, pattern=_CAPABILITY_ID_PATTERN)
        if self.operation_id != self.capability_id and not self.operation_id.startswith(f"{self.capability_id}."):
            raise ValueError("operation_id must equal capability_id or be its child")
        if self.suboperation_id != self.operation_id and not self.suboperation_id.startswith(f"{self.operation_id}."):
            raise ValueError("suboperation_id must equal operation_id or be its child")
        return self

    @property
    def row_id(self) -> str:
        """Return the unique row identity."""
        return self.suboperation_id


class CanonicalSemanticHomeV1(BaseModel):
    """Canonical frontend-neutral command owner and result contract."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    owner: str = Field(min_length=1)
    command_type: str = Field(min_length=1)
    result_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_values(self) -> CanonicalSemanticHomeV1:
        # Derived from the model, not listed: a field added here was silently
        # exempt from the placeholder check while the tuple went on naming three.
        for field_name in type(self).model_fields:
            value = getattr(self, field_name)
            if isinstance(value, str):
                _require_non_placeholder(value, field_name=field_name)
        return self


class LedgerAxisApplicabilityDecisionV1(BaseModel):
    """One reviewed axis decision with an explicit current proof state."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    axis: LedgerCapabilityAxis
    applicability: ApplicabilityState
    rationale: str = Field(min_length=1)
    proof: AxisProofState
    proof_requirement: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_decision(self) -> LedgerAxisApplicabilityDecisionV1:
        _require_non_placeholder(self.rationale, field_name="rationale")
        _require_non_placeholder(self.proof_requirement, field_name="proof_requirement")
        if self.applicability is ApplicabilityState.NOT_APPLICABLE:
            if self.proof is not AxisProofState.NOT_APPLICABLE:
                raise ValueError("a non-applicable reviewed union axis must have not_applicable proof")
        elif self.proof is AxisProofState.NOT_APPLICABLE:
            raise ValueError("an applicable reviewed union axis requires an operational proof state")
        return self


class LedgerUnionSourceObservationV1(BaseModel):
    """One raw census observation and the semantic rows it selects."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    source: DenominatorSourceKind
    observation_id: str = Field(min_length=1)
    capability_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_observation(self) -> LedgerUnionSourceObservationV1:
        _require_non_placeholder(self.observation_id, field_name="observation_id")
        if len(set(self.capability_ids)) != len(self.capability_ids):
            raise ValueError("a union source observation cannot select the same capability twice")
        for capability_id in self.capability_ids:
            _require_identity(capability_id, field_name="capability_id", pattern=_CAPABILITY_ID_PATTERN)
        return self


class LedgerUnionCapabilityRowV1(BaseModel):
    """One exhaustively reviewed semantic row selected by raw observations."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    capability_id: str = Field(min_length=1)
    sources: frozenset[DenominatorSourceKind] = Field(min_length=1)
    source_observation_ids: tuple[str, ...] = Field(min_length=1)
    semantic_home: CanonicalSemanticHomeV1
    semantic_home_status: SemanticHomeStatus
    effect: LedgerCapabilityEffect
    applicability: tuple[LedgerAxisApplicabilityDecisionV1, ...]
    gap_classes: frozenset[LedgerGapClass] = Field(min_length=1)
    primary_gap_class: LedgerGapClass
    secondary_gap_classes: tuple[LedgerGapClass, ...]
    proof_requirements: tuple[str, ...] = Field(min_length=1)
    blockers: tuple[str, ...] = Field(min_length=1)
    next_action: str = Field(min_length=1)
    tui_routes: tuple[str, ...] = ()
    tui_hold_until: LedgerGate | None = None
    registry_destination_status: LedgerRegistryDestinationStatus
    review_ruling: LedgerUnionRowReviewRuling
    review_digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_row(self) -> LedgerUnionCapabilityRowV1:
        _require_identity(self.capability_id, field_name="capability_id", pattern=_CAPABILITY_ID_PATTERN)
        if tuple(sorted(set(self.source_observation_ids))) != self.source_observation_ids:
            raise ValueError("union row source observation identities must be sorted and unique")
        axes = tuple(decision.axis for decision in self.applicability)
        if len(set(axes)) != len(axes) or frozenset(axes) != _ALL_AXES:
            raise ValueError("a union row must decide applicability for every axis exactly once")
        if tuple(sorted(self.applicability, key=lambda item: item.axis.value)) != self.applicability:
            raise ValueError("union row applicability decisions must use canonical axis order")
        for value in (*self.proof_requirements, *self.blockers, self.next_action, *self.tui_routes):
            _require_non_placeholder(value, field_name="union row text")
        if tuple(sorted(set(self.tui_routes))) != self.tui_routes:
            raise ValueError("union row TUI routes must be sorted and unique")
        if self.secondary_gap_classes != tuple(sorted(set(self.secondary_gap_classes), key=lambda item: item.value)):
            raise ValueError("secondary gap classes must be unique and canonically ordered")
        if (
            self.primary_gap_class in self.secondary_gap_classes
            or frozenset((self.primary_gap_class, *self.secondary_gap_classes)) != self.gap_classes
        ):
            raise ValueError("primary and secondary gap classes must exactly partition all row gaps")
        if self.review_ruling is not LedgerUnionRowReviewRuling.COMPLETE_WITH_OPEN_GAPS:
            raise ValueError("union rows must retain the reviewed-open ruling until their gaps close")
        _require_digest(self.review_digest, field_name="review_digest")
        tui_applicable = next(
            decision.applicability is ApplicabilityState.APPLICABLE
            for decision in self.applicability
            if decision.axis is LedgerCapabilityAxis.TUI
        )
        expected_hold = LEDGER_TUI_HOLD_UNTIL_GATE if tui_applicable else None
        if self.tui_hold_until is not expected_hold:
            state = "applicable" if tui_applicable else "not_applicable"
            raise ValueError(
                f"union row TUI hold must be {LEDGER_TUI_HOLD_UNTIL_GATE.value} for {state} TUI and absent otherwise"
            )
        return self

    @property
    def calculated_review_digest(self) -> str:
        """Bind every reviewed assertion without a self-reference."""
        payload = cast(dict[str, object], self.model_dump(mode="json", exclude={"review_digest"}))
        payload["sources"] = sorted(cast(list[str], payload["sources"]))
        payload["gap_classes"] = sorted(cast(list[str], payload["gap_classes"]))
        return _canonical_digest(payload)


class LedgerUnionSourceDigestV1(BaseModel):
    """One source stream digest bound into the S08 union."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    source: DenominatorSourceKind
    observation_count: int = Field(ge=1)
    digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_digest(self) -> LedgerUnionSourceDigestV1:
        _require_digest(self.digest, field_name="digest")
        return self


class LedgerUnionSelectionAccountingV1(BaseModel):
    """Exact observation/selection/join/split arithmetic for the union."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    observation_count: int = Field(ge=1)
    selected_edges: int = Field(ge=1)
    one_to_many_observations: int = Field(ge=0)
    one_to_many_extra_edges: int = Field(ge=0)
    multi_observation_rows: int = Field(ge=0)
    duplicate_selection_edges: int = Field(ge=0)
    final_rows: int = Field(ge=1)


class LedgerUnionRowReviewAttestationV1(BaseModel):
    """Digest-bound evidence that every denominator row received a bounded review."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    review_id: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    reviewed_at: datetime
    ruling: LedgerUnionRowReviewRuling
    reviewed_union_basis_digest: str = Field(min_length=1)
    row_review_digest: str = Field(min_length=1)
    reviewed_row_count: int = Field(ge=1)
    digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_attestation(self) -> LedgerUnionRowReviewAttestationV1:
        _require_identity(self.review_id, field_name="review_id", pattern=_REVIEW_ID_PATTERN)
        _require_non_placeholder(self.reviewer, field_name="reviewer")
        _require_observed_at(self.reviewed_at, field_name="reviewed_at")
        if self.ruling is not LedgerUnionRowReviewRuling.COMPLETE_WITH_OPEN_GAPS:
            raise ValueError("row-review attestation must retain open gaps")
        _require_digest(self.reviewed_union_basis_digest, field_name="reviewed_union_basis_digest")
        _require_digest(self.row_review_digest, field_name="row_review_digest")
        _require_digest(self.digest, field_name="digest")
        if self.digest != self.calculated_digest:
            raise ValueError("row-review attestation digest does not match its reviewed assertions")
        return self

    @property
    def calculated_digest(self) -> str:
        """Hash the complete row-review attestation without its digest field."""
        return _canonical_digest(self.model_dump(mode="json", exclude={"digest"}))


class LedgerUnionDenominatorV1(BaseModel):
    """Reproducible union with every raw observation and reviewed row decision."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    root: Literal["cadrumo.ledger_union_denominator"]
    schema_version: Literal[4]
    registry_census: LedgerRegistryRouteCensusV1
    tui_census: LedgerTuiSupportedSurfaceCensusV1
    source_digests: tuple[LedgerUnionSourceDigestV1, ...]
    observations: tuple[LedgerUnionSourceObservationV1, ...]
    rows: tuple[LedgerUnionCapabilityRowV1, ...]
    selection_accounting: LedgerUnionSelectionAccountingV1
    review_revision: str = Field(min_length=1)
    reviewed_row_count: int = Field(ge=1)
    row_review_digest: str = Field(min_length=1)
    row_review_attestation: LedgerUnionRowReviewAttestationV1
    digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_union(self) -> LedgerUnionDenominatorV1:
        _artifact_input_capabilities()
        _validate_supported_surface_route_selections(self.observations, self.rows)
        sources = tuple(item.source for item in self.source_digests)
        if len(set(sources)) != len(sources) or frozenset(sources) != frozenset(DenominatorSourceKind):
            raise ValueError("the union must bind every mandatory source digest exactly once")
        if tuple(sorted(self.source_digests, key=lambda item: item.source.value)) != self.source_digests:
            raise ValueError("union source digests must use canonical source order")
        observation_ids = tuple(item.observation_id for item in self.observations)
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("union source observation identities must be unique")
        _validate_non_registry_observation_adjudication(self.observations)
        _validate_registry_observation_projection(self.registry_census, self.observations)
        if (
            tuple(sorted(self.observations, key=lambda item: (item.source.value, item.observation_id)))
            != self.observations
        ):
            raise ValueError("union source observations must use canonical source order")
        counts = {source: 0 for source in DenominatorSourceKind}
        for observation in self.observations:
            counts[observation.source] += 1
        if any(item.observation_count != counts[item.source] for item in self.source_digests):
            raise ValueError("union source observation counts do not match their digests")
        expected_source_digests = tuple(
            LedgerUnionSourceDigestV1(
                source=source,
                observation_count=len(source_observations),
                digest=_union_source_digest(source, source_observations, self.registry_census, self.tui_census),
            )
            for source in sorted(DenominatorSourceKind, key=lambda item: item.value)
            if (source_observations := tuple(item for item in self.observations if item.source is source))
        )
        if self.source_digests != expected_source_digests:
            raise ValueError("union source counts or digests drifted from canonical projections")
        row_ids = tuple(row.capability_id for row in self.rows)
        if len(set(row_ids)) != len(row_ids) or tuple(sorted(row_ids)) != row_ids:
            raise ValueError("union rows must have unique canonically sorted identities")
        rows_by_id = {row.capability_id: row for row in self.rows}
        tui_reachability = {row.destination: row.reachability for row in self.tui_census.routes}
        _validate_tui_route_adjudication(
            _EXPLICIT_TUI_ROUTE_ADJUDICATION,
            known_routes=frozenset(tui_reachability),
        )
        registry_rows_by_capability = {_registry_union_capability_id(row): row for row in self.registry_census.rows}
        cli_ownership_by_capability: dict[str, set[str]] = {}
        from cadrumo.entrypoints.cli._app_ledger_command_specs import LEDGER_CLI_COMMAND_CENSUS

        for entry in LEDGER_CLI_COMMAND_CENSUS:
            for capability_id in _selection_for_observation(f"cli_endpoint:{entry.command_key}"):
                cli_ownership_by_capability.setdefault(capability_id, set()).add(entry.adapter_ownership.value)
            for suboperation_id in entry.suboperation_ids:
                for capability_id in _selection_for_observation(f"cli_suboperation:{suboperation_id}"):
                    cli_ownership_by_capability.setdefault(capability_id, set()).add(entry.adapter_ownership.value)
        selected: dict[str, set[DenominatorSourceKind]] = {}
        selecting_observations: dict[str, set[str]] = {}
        for observation in self.observations:
            for capability_id in observation.capability_ids:
                if capability_id not in rows_by_id:
                    raise ValueError(f"union observation selects an unavailable row: {capability_id}")
                selected.setdefault(capability_id, set()).add(observation.source)
                selecting_observations.setdefault(capability_id, set()).add(observation.observation_id)
        if set(selected) != set(rows_by_id):
            raise ValueError("every union row must be selected by a raw census observation")
        for capability_id, row in rows_by_id.items():
            if row.sources != frozenset(selected[capability_id]):
                raise ValueError(f"union row sources drifted from observations: {capability_id}")
            if row.source_observation_ids != tuple(sorted(selecting_observations[capability_id])):
                raise ValueError(f"union row observations drifted from census: {capability_id}")
            expected_effect = _effect_for(capability_id, row.sources)
            if row.effect is not expected_effect:
                raise ValueError(f"union row effect drifted from explicit adjudication: {capability_id}")
            expected_home, expected_status = _semantic_home_for(capability_id, expected_effect)
            if row.semantic_home != expected_home or row.semantic_home_status is not expected_status:
                raise ValueError(f"union row semantic home drifted from explicit adjudication: {capability_id}")
            expected_tui_routes = _tui_routes_for(capability_id, expected_effect)
            if row.tui_routes != expected_tui_routes:
                raise ValueError(f"union row TUI routes drifted from explicit adjudication: {capability_id}")
            expected_review = _reviewed_union_row_fields(
                capability_id=capability_id,
                sources=row.sources,
                semantic_home=expected_home,
                home_status=expected_status,
                effect=expected_effect,
                tui_routes=expected_tui_routes,
                tui_reachability=tui_reachability,
                cli_ownership=frozenset(cli_ownership_by_capability.get(capability_id, set())),
                registry_row=registry_rows_by_capability.get(capability_id),
            )
            for field_name, expected_value in expected_review.items():
                if getattr(row, field_name) != expected_value:
                    raise ValueError(f"union row {field_name} drifted from exhaustive review: {capability_id}")
            expected_tui_hold = (
                LEDGER_TUI_HOLD_UNTIL_GATE
                if next(
                    decision.applicability is ApplicabilityState.APPLICABLE
                    for decision in row.applicability
                    if decision.axis is LedgerCapabilityAxis.TUI
                )
                else None
            )
            if row.tui_hold_until is not expected_tui_hold:
                raise ValueError(f"union row TUI hold drifted from explicit adjudication: {capability_id}")
            if row.review_digest != row.calculated_review_digest:
                raise ValueError(f"union row review digest is stale: {capability_id}")
        selected_edges = sum(len(item.capability_ids) for item in self.observations)
        expected_accounting = LedgerUnionSelectionAccountingV1(
            observation_count=len(self.observations),
            selected_edges=selected_edges,
            one_to_many_observations=sum(len(item.capability_ids) > 1 for item in self.observations),
            one_to_many_extra_edges=sum(len(item.capability_ids) - 1 for item in self.observations),
            multi_observation_rows=sum(len(row.source_observation_ids) > 1 for row in self.rows),
            duplicate_selection_edges=selected_edges - len(self.rows),
            final_rows=len(self.rows),
        )
        if self.selection_accounting != expected_accounting:
            raise ValueError("union selection accounting drifted from observations and rows")
        _require_non_placeholder(self.review_revision, field_name="review_revision")
        if self.review_revision != "row-review-v1":
            raise ValueError("union row-review revision is unsupported")
        if self.reviewed_row_count != len(self.rows):
            raise ValueError("reviewed row coverage does not exactly equal the union denominator")
        _require_digest(self.row_review_digest, field_name="row_review_digest")
        if self.row_review_digest != self.calculated_row_review_digest:
            raise ValueError("aggregate row-review digest does not match every reviewed row")
        attestation = self.row_review_attestation
        if (
            attestation.reviewed_row_count != self.reviewed_row_count
            or attestation.row_review_digest != self.row_review_digest
            or attestation.reviewed_union_basis_digest != self.calculated_review_basis_digest
        ):
            raise ValueError("row-review attestation does not bind the complete reviewed union")
        _require_digest(self.digest, field_name="digest")
        if self.digest != self.calculated_digest:
            raise ValueError("union denominator digest does not match its adjudicated content")
        return self

    @property
    def calculated_digest(self) -> str:
        """Return the canonical digest excluding the self-referential digest field."""
        encoded = _canonical_json_text(_ledger_union_digest_payload(self)).encode("utf-8")
        return f"sha256:{hashlib.sha256(_LEDGER_UNION_DENOMINATOR_FRAME + _length_frame(encoded)).hexdigest()}"

    @property
    def calculated_row_review_digest(self) -> str:
        """Bind exact ordered coverage and each row's reviewed assertions."""
        return _canonical_digest(tuple((row.capability_id, row.review_digest) for row in self.rows))

    @property
    def calculated_review_basis_digest(self) -> str:
        """Bind the reviewed union without the self-referential attestation."""
        return _canonical_digest(_ledger_union_review_basis_payload(self))


class LedgerUnionReviewSnapshotV1(BaseModel):
    """The complete, independently reviewable union state a gate may freeze.

    This is deliberately a projection of a validated live union, rather than a
    second mutable review register.  It binds the outer union, exhaustive row
    coverage, and the reviewed attestation so a receipt cannot treat a fresh
    digest as proof that every row was actually reviewed.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    union_digest: str = Field(min_length=1)
    row_review_digest: str = Field(min_length=1)
    row_review_attestation_digest: str = Field(min_length=1)
    reviewed_row_count: int = Field(ge=1)
    review_revision: str = Field(min_length=1)
    review_id: str = Field(min_length=1)
    reviewed_at: datetime
    capability_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _check_snapshot(self) -> LedgerUnionReviewSnapshotV1:
        _require_digest(self.union_digest, field_name="union_digest")
        _require_digest(self.row_review_digest, field_name="row_review_digest")
        _require_digest(self.row_review_attestation_digest, field_name="row_review_attestation_digest")
        _require_non_placeholder(self.review_revision, field_name="review_revision")
        _require_identity(self.review_id, field_name="review_id", pattern=_REVIEW_ID_PATTERN)
        _require_observed_at(self.reviewed_at, field_name="reviewed_at")
        if not self.capability_ids or tuple(sorted(set(self.capability_ids))) != self.capability_ids:
            raise ValueError("reviewed union capability identities must be nonempty, sorted, and unique")
        for capability_id in self.capability_ids:
            _require_identity(capability_id, field_name="capability_id", pattern=_CAPABILITY_ID_PATTERN)
        return self

    @classmethod
    def from_union(cls, union: LedgerUnionDenominatorV1) -> LedgerUnionReviewSnapshotV1:
        """Project only a canonical, fully validated union into gate state."""
        canonical = LedgerUnionDenominatorV1.model_validate(_serialized_python_data(union))
        return cls(
            union_digest=canonical.digest,
            row_review_digest=canonical.row_review_digest,
            row_review_attestation_digest=canonical.row_review_attestation.digest,
            reviewed_row_count=canonical.reviewed_row_count,
            review_revision=canonical.review_revision,
            review_id=canonical.row_review_attestation.review_id,
            reviewed_at=canonical.row_review_attestation.reviewed_at,
            capability_ids=tuple(row.capability_id for row in canonical.rows),
        )


def _ledger_union_digest_payload(union: LedgerUnionDenominatorV1) -> dict[str, object]:
    """Return JSON data with every set-valued field in canonical order."""
    payload = cast(dict[str, object], union.model_dump(mode="json", exclude={"digest"}))
    rows = cast(list[dict[str, object]], payload["rows"])
    for row in rows:
        row["sources"] = sorted(cast(list[str], row["sources"]))
        row["gap_classes"] = sorted(cast(list[str], row["gap_classes"]))
    return payload


def _ledger_union_review_basis_payload(union: LedgerUnionDenominatorV1) -> dict[str, object]:
    """Return canonical reviewed content excluding outer and attestation digests."""
    payload = cast(
        dict[str, object],
        union.model_dump(mode="json", exclude={"digest", "row_review_attestation"}),
    )
    rows = cast(list[dict[str, object]], payload["rows"])
    for row in rows:
        row["sources"] = sorted(cast(list[str], row["sources"]))
        row["gap_classes"] = sorted(cast(list[str], row["gap_classes"]))
    return payload


@dataclass(frozen=True, slots=True)
class _BackendOperationDeclaration:
    capability_id: str
    owner: str
    command_type: str
    result_type: str
    status: SemanticHomeStatus


def _backend(
    capability_id: str,
    owner: str,
    command_type: str,
    result_type: str,
    *,
    existing_command: bool = False,
) -> _BackendOperationDeclaration:
    return _BackendOperationDeclaration(
        capability_id,
        owner,
        command_type,
        result_type,
        SemanticHomeStatus.EXISTING if existing_command else SemanticHomeStatus.PLANNED,
    )


# S05's 63-operation census, retained as typed-home decisions rather than a
# second implementation registry. ``planned`` means the callable exists but
# still accepts loose parameters; the named immutable request is the G1 home.
_LEDGER_BACKEND_OPERATION_DECLARATIONS: Final[tuple[_BackendOperationDeclaration, ...]] = (
    _backend(
        "ledger.classification.bulk_csv",
        "cadrumo.application.ledger.actions_classification:bulk_classify_from_csv",
        "LedgerBulkClassificationCommand",
        "BulkClassifyResult",
    ),
    _backend(
        "ledger.classification.rule_add",
        "cadrumo.application.ledger.actions_classification:add_classification_rule",
        "LedgerRuleAddCommand",
        "LedgerClassificationRule",
    ),
    _backend(
        "ledger.classification.rule_apply",
        "cadrumo.application.ledger.actions_classification:apply_classification_rules",
        "LedgerRuleApplyCommand",
        "ApplyRulesResult",
    ),
    _backend(
        "ledger.export.flat",
        "cadrumo.application.ledger.actions_export:export_ledger_transactions",
        "LedgerExportCommand",
        "LedgerExportResult",
        existing_command=True,
    ),
    _backend(
        "ledger.import.prepare",
        "cadrumo.application.ledger.import_preparation:prepare_ledger_import_command",
        "LedgerImportPreparationRequest",
        "LedgerSourceImportCommand",
    ),
    _backend(
        "ledger.import.parsed_rows",
        "cadrumo.application.ledger.actions_import:import_ledger_transactions",
        "LedgerParsedRowsImportCommand",
        "LedgerImportOperationResult",
    ),
    _backend(
        "ledger.import.source",
        "cadrumo.application.ledger.actions_import:import_ledger_source",
        "LedgerSourceImportCommand",
        "LedgerSourceImportResult",
        existing_command=True,
    ),
    _backend(
        "ledger.import.aggregate_results",
        "cadrumo.application.ledger.actions_import:aggregate_ledger_import_results",
        "LedgerImportAggregationQuery",
        "LedgerImportOperationResult",
    ),
    _backend(
        "ledger.lifecycle.archive",
        "cadrumo.application.ledger.actions_lifecycle:archive_manual_transaction",
        "LedgerArchiveCommand",
        "ManualLedgerTransactionResult",
    ),
    _backend(
        "ledger.lifecycle.stash",
        "cadrumo.application.ledger.actions_lifecycle:stash_manual_transaction",
        "LedgerStashCommand",
        "ManualLedgerTransactionResult",
    ),
    _backend(
        "ledger.lifecycle.restore",
        "cadrumo.application.ledger.actions_lifecycle:restore_manual_transaction",
        "LedgerRestoreCommand",
        "ManualLedgerTransactionResult",
    ),
    _backend(
        "ledger.lifecycle.reviewed_exclude",
        "cadrumo.application.ledger.actions_lifecycle:mark_transaction_reviewed_excluded",
        "LedgerReviewedExcludeCommand",
        "ManualLedgerTransactionResult",
    ),
    _backend(
        "ledger.lifecycle.remove",
        "cadrumo.application.ledger.actions_lifecycle:remove_manual_transaction",
        "LedgerRemoveCommand",
        "LedgerTransactionRemovalReport",
    ),
    _backend(
        "ledger.lifecycle.reset",
        "cadrumo.application.ledger.actions_lifecycle:reset_ledger_catalogue",
        "LedgerResetCommand",
        "LedgerCatalogueResetReport",
    ),
    _backend(
        "ledger.transaction.create",
        "cadrumo.application.ledger.actions_manual:create_manual_transaction",
        "ManualLedgerTransactionCommand",
        "ManualLedgerTransactionResult",
        existing_command=True,
    ),
    _backend(
        "ledger.transaction.attach",
        "cadrumo.application.ledger.actions_manual:attach_manual_transaction_evidence",
        "LedgerEvidenceAttachCommand",
        "ManualLedgerTransactionResult",
    ),
    _backend(
        "ledger.transaction.detach",
        "cadrumo.application.ledger.actions_manual:detach_manual_transaction_attachments",
        "LedgerEvidenceDetachCommand",
        "ManualLedgerTransactionResult",
    ),
    _backend(
        "ledger.transaction.invoice_link",
        "cadrumo.application.ledger.actions_manual:link_manual_transaction_invoice",
        "LedgerInvoiceLinkCommand",
        "InvoiceTransactionLinkResult",
    ),
    _backend(
        "ledger.transaction.get",
        "cadrumo.application.ledger.actions_manual:get_manual_transaction",
        "LedgerTransactionQuery",
        "Transaction",
    ),
    _backend(
        "ledger.transaction.list",
        "cadrumo.application.ledger.actions_manual:list_manual_transactions",
        "LedgerTransactionListQuery",
        "tuple[Transaction, ...]",
    ),
    _backend(
        "ledger.transaction.review_query",
        "cadrumo.application.ledger.actions_manual:query_ledger_review_rows",
        "LedgerReviewQuery",
        "LedgerReviewQueryResult",
        existing_command=True,
    ),
    _backend(
        "ledger.transaction.status_summary",
        "cadrumo.application.ledger.actions_manual:summarize_manual_transactions",
        "LedgerStatusQuery",
        "LedgerStatusReport",
    ),
    _backend(
        "ledger.transaction.update",
        "cadrumo.application.ledger.actions_manual:update_manual_transaction",
        "ManualLedgerTransactionCommand",
        "ManualLedgerTransactionResult",
    ),
    _backend(
        "ledger.transaction.update_fields",
        "cadrumo.application.ledger.actions_manual:update_manual_transaction_fields",
        "ManualLedgerTransactionPatch",
        "ManualLedgerTransactionResult",
    ),
    _backend(
        "ledger.transaction.split",
        "cadrumo.application.ledger.actions_split_merge:split_transaction",
        "LedgerSplitCommand",
        "SplitTransactionResult",
    ),
    _backend(
        "ledger.transaction.split_classified",
        "cadrumo.application.ledger.actions_split_merge:split_transaction_with_classified_children",
        "LedgerClassifiedSplitCommand",
        "SplitTransactionResult",
    ),
    _backend(
        "ledger.transaction.merge",
        "cadrumo.application.ledger.actions_split_merge:merge_transactions",
        "LedgerMergeCommand",
        "MergeTransactionsResult",
    ),
    _backend(
        "ledger.evidence.attachment_view",
        "cadrumo.application.ledger.attachment_review:get_attachment_review_item",
        "LedgerAttachmentViewQuery",
        "AttachmentReviewItem",
    ),
    _backend(
        "ledger.evidence.attachment_queue",
        "cadrumo.application.ledger.attachment_review:list_attachment_review_queue",
        "LedgerAttachmentQueueQuery",
        "tuple[AttachmentReviewItem, ...]",
    ),
    _backend(
        "ledger.evidence.add",
        "cadrumo.application.ledger.evidence:PurchaseInvoiceEvidenceService.add",
        "LedgerPurchaseEvidenceAddCommand",
        "PurchaseInvoiceEvidenceResult",
    ),
    _backend(
        "ledger.evidence.view",
        "cadrumo.application.ledger.evidence:PurchaseInvoiceEvidenceService.view",
        "LedgerPurchaseEvidenceViewQuery",
        "PurchaseInvoiceEvidence",
    ),
    _backend(
        "ledger.evidence.list",
        "cadrumo.application.ledger.evidence:PurchaseInvoiceEvidenceService.list_all",
        "LedgerPurchaseEvidenceListQuery",
        "tuple[PurchaseInvoiceEvidence, ...]",
    ),
    _backend(
        "ledger.evidence.update",
        "cadrumo.application.ledger.evidence:PurchaseInvoiceEvidenceService.update",
        "LedgerPurchaseEvidenceUpdateCommand",
        "PurchaseInvoiceEvidenceResult",
    ),
    _backend(
        "ledger.evidence.remove",
        "cadrumo.application.ledger.evidence:PurchaseInvoiceEvidenceService.remove",
        "LedgerPurchaseEvidenceRemoveCommand",
        "PurchaseInvoiceEvidenceResult",
    ),
    _backend(
        "ledger.evidence.batch",
        "cadrumo.application.ledger.batch_ingest:run_evidence_batch",
        "LedgerEvidenceBatchCommand",
        "BatchRunResult",
    ),
    _backend(
        "ledger.evidence.consent_survey",
        "cadrumo.application.ledger.consent_withdrawal:survey_cloud_consent",
        "LedgerConsentSurveyQuery",
        "ConsentWithdrawalSurvey",
    ),
    _backend(
        "ledger.evidence.consent_rederive",
        "cadrumo.application.ledger.consent_withdrawal:rederive_artefact_on_host",
        "LedgerConsentRederiveCommand",
        "LocalRederivation",
    ),
    _backend(
        "ledger.counterparty.record",
        "cadrumo.application.ledger.counterparty_establishment:record_confirmed_counterparty_facts",
        "LedgerCounterpartyRecordCommand",
        "ConfirmedCounterpartyFacts",
    ),
    _backend(
        "ledger.counterparty.forget",
        "cadrumo.application.ledger.counterparty_establishment:forget_confirmed_counterparty_facts",
        "LedgerCounterpartyForgetCommand",
        "bool",
    ),
    _backend(
        "ledger.counterparty.resolve",
        "cadrumo.application.ledger.counterparty_establishment:resolve_confirmed_counterparty_facts",
        "LedgerCounterpartyQuery",
        "ConfirmedCounterpartyResolution",
    ),
    _backend(
        "ledger.invoice.extract_draft",
        "cadrumo.application.ledger.invoice_draft_extraction:extract_invoice_draft_from_evidence",
        "LedgerInvoiceExtractCommand",
        "InvoiceDraft",
    ),
    _backend(
        "ledger.invoice.confirm_draft",
        "cadrumo.application.ledger.invoice_confirmation:confirm_invoice_draft_from_evidence",
        "LedgerInvoiceConfirmCommand",
        "InvoiceConfirmationResult",
    ),
    _backend(
        "ledger.llm.classify_with_evidence",
        "cadrumo.application.ledger.llm_classification:classify_with_evidence",
        "LedgerLlmEvidenceClassificationCommand",
        "LedgerClassificationSuggestion",
    ),
    _backend(
        "ledger.llm.suggest",
        "cadrumo.application.ledger.llm_classification:suggest_llm_classification",
        "LedgerLlmSuggestCommand",
        "LedgerClassificationSuggestion",
    ),
    _backend(
        "ledger.llm.apply",
        "cadrumo.application.ledger.llm_classification:apply_llm_classification",
        "LedgerLlmApplyCommand",
        "LedgerClassificationApplyResult",
    ),
    _backend(
        "ledger.llm.saturate",
        "cadrumo.application.ledger.llm_classification:saturate_llm_classification",
        "LedgerLlmSaturateCommand",
        "LedgerSaturationSuggestion",
    ),
    _backend(
        "ledger.llm.apply_saturated",
        "cadrumo.application.ledger.llm_classification:apply_saturated_llm_classification",
        "LedgerLlmSaturatedApplyCommand",
        "LedgerClassificationApplyResult",
    ),
    _backend(
        "ledger.llm.iva_derive",
        "cadrumo.application.ledger.llm_classification:derive_operator_iva_substrate",
        "LedgerLlmIvaDeriveCommand",
        "LedgerIvaSuggestion",
    ),
    _backend(
        "ledger.llm.suggest_split",
        "cadrumo.application.ledger.llm_classification:suggest_evidence_split",
        "LedgerLlmSplitSuggestCommand",
        "LedgerSplitSuggestion",
    ),
    _backend(
        "ledger.llm.apply_split",
        "cadrumo.application.ledger.llm_classification:apply_evidence_split",
        "LedgerLlmSplitApplyCommand",
        "SplitTransactionResult",
    ),
    _backend(
        "ledger.llm.apply_evidence_classification",
        "cadrumo.application.ledger.llm_classification:apply_evidence_classification",
        "LedgerLlmEvidenceApplyCommand",
        "LedgerClassificationApplyResult",
    ),
    _backend(
        "ledger.llm.reject",
        "cadrumo.application.ledger.llm_classification:reject_llm_suggestion",
        "LedgerLlmRejectCommand",
        "LedgerSuggestionRejectionResult",
    ),
    _backend(
        "ledger.llm.diagnostics",
        "cadrumo.application.ledger.llm_diagnostics:build_llm_diagnostics_report",
        "LedgerLlmDiagnosticsQuery",
        "LedgerLlmDiagnosticsReport",
    ),
    _backend(
        "ledger.llm.review_decision",
        "cadrumo.application.ledger.llm_review_workflow:execute_reviewed_decision",
        "LlmReviewRequest",
        "LlmReviewResult",
    ),
    _backend(
        "ledger.participation.get",
        "cadrumo.application.ledger.participation_read:get_transaction_participation",
        "LedgerParticipationQuery",
        "TransactionRevisionParticipationIndex",
    ),
    _backend(
        "ledger.preflight.readiness",
        "cadrumo.application.ledger.preflight:preflight_ledger_tax_readiness",
        "LedgerPreflightQuery",
        "LedgerPreflightReport",
    ),
    _backend(
        "ledger.preflight.catalogue",
        "cadrumo.application.ledger.preflight:preflight_transaction_catalogue",
        "LedgerCataloguePreflightQuery",
        "LedgerPreflightReport",
    ),
    _backend(
        "ledger.ratio.list",
        "cadrumo.application.ledger.ratios:list_eligible_ratios_for_bucket",
        "LedgerRatioListQuery",
        "tuple[UsageRatio, ...]",
    ),
    _backend(
        "ledger.ratio.validate",
        "cadrumo.application.ledger.ratios:validate_ratios_for_bucket",
        "LedgerRatioValidationQuery",
        "RatiosValidationReport",
    ),
    _backend(
        "ledger.ratio.set",
        "cadrumo.application.ledger.ratios:set_usage_ratio",
        "LedgerRatioSetCommand",
        "Decimal | None",
    ),
    _backend(
        "ledger.ratio.unset",
        "cadrumo.application.ledger.ratios:unset_usage_ratio",
        "LedgerRatioUnsetCommand",
        "Decimal | None",
    ),
    _backend(
        "ledger.workspace.affected_declarations",
        "cadrumo.application.ledger.workspace:project_affected_declaration_reconciliations",
        "LedgerAffectedDeclarationsQuery",
        "tuple[LedgerAffectedDeclarationRefV1, ...]",
    ),
    _backend(
        "ledger.workspace.project",
        "cadrumo.application.ledger.workspace:project_ledger_workspace",
        "LedgerWorkspaceProjectionQuery",
        "LedgerWorkspaceProjectionV1",
    ),
    _backend(
        "ledger.workspace.read",
        "cadrumo.application.ledger.workspace_reader:read_ledger_workspace_projection",
        "LedgerWorkspaceReadQuery",
        "LedgerWorkspaceProjectionV1",
    ),
)


_LEDGER_MISSING_PRODUCT_DECLARATIONS: Final[tuple[_BackendOperationDeclaration, ...]] = (
    _backend(
        "ledger.export.review_package",
        "cadrumo.application.ledger.review_exchange",
        "LedgerReviewExchangePlanCommand",
        "LedgerReviewExchangeResult",
    ),
    _backend(
        "ledger.export.google_transport",
        "cadrumo.application.ledger.review_exchange",
        "LedgerGoogleReviewExchangeCommand",
        "LedgerGoogleReviewExchangeResult",
    ),
    _backend(
        "ledger.export.restore_archive",
        "cadrumo.application.ledger.recovery_archive",
        "LedgerRecoveryArchiveCommand",
        "LedgerRecoveryArchiveResult",
    ),
    _backend(
        "ledger.export.provenance",
        "cadrumo.application.ledger.actions_export",
        "LedgerExportProvenanceQuery",
        "LedgerExportProvenanceResult",
    ),
    _backend(
        "ledger.evidence.download",
        "cadrumo.application.ledger.evidence_lifecycle",
        "LedgerEvidenceDownloadQuery",
        "LedgerEvidenceDownloadResult",
    ),
    _backend(
        "ledger.evidence.replace",
        "cadrumo.application.ledger.evidence_lifecycle",
        "LedgerEvidenceReplaceCommand",
        "LedgerEvidenceReplaceResult",
    ),
    _backend(
        "ledger.note.append", "cadrumo.application.ledger.notes", "LedgerNoteAppendCommand", "LedgerNoteAppendResult"
    ),
    _backend(
        "ledger.field_change.provenance",
        "cadrumo.domain.transactions.change_provenance",
        "LedgerFieldChangeQuery",
        "LedgerFieldChangeProvenance",
    ),
    _backend(
        "ledger.manual_override.provenance",
        "cadrumo.domain.transactions.change_provenance",
        "LedgerManualOverrideQuery",
        "LedgerManualOverrideProvenance",
    ),
    _backend(
        "ledger.import.normalization_provenance",
        "cadrumo.domain.transactions.change_provenance",
        "LedgerImportNormalizationQuery",
        "LedgerImportNormalizationProvenance",
    ),
    _backend(
        "ledger.fx.provenance",
        "cadrumo.domain.transactions.models",
        "LedgerFxProvenanceQuery",
        "LedgerFxProvenance",
    ),
    _backend(
        "ledger.transaction.batch_patch",
        "cadrumo.application.ledger.change_sets",
        "LedgerBatchPatchCommand",
        "LedgerBatchPatchResult",
    ),
    _backend(
        "ledger.list.page",
        "cadrumo.application.ledger.query_service",
        "LedgerPageQuery",
        "LedgerPageResult",
    ),
)

_LEDGER_MISSING_PRODUCT_OBSERVATIONS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("review_grade_workbook", ("ledger.export.review_package",)),
    ("restore_archive", ("ledger.export.restore_archive",)),
    ("google_ledger_export", ("ledger.export.google_transport",)),
    (
        "complete_export_provenance",
        (
            "ledger.export.provenance",
            "ledger.fx.provenance",
            "ledger.import.normalization_provenance",
            "ledger.manual_override.provenance",
        ),
    ),
    ("evidence_download", ("ledger.evidence.download",)),
    ("atomic_evidence_replace", ("ledger.evidence.replace",)),
    ("append_only_notes", ("ledger.note.append",)),
    ("changed_field_provenance", ("ledger.field_change.provenance",)),
    ("generic_batch_patch", ("ledger.transaction.batch_patch",)),
    ("application_paging", ("ledger.list.page",)),
)


_LEDGER_ARTIFACT_OBSERVATIONS: Final[tuple[tuple[str, str], ...]] = (
    ("flat.csv", "ledger.export.csv"),
    ("flat.jsonl", "ledger.export.jsonl"),
    ("flat.xlsx", "ledger.export.xlsx"),
    ("review.workbook_sidecar", "ledger.export.review_package"),
    ("review.google", "ledger.export.google_transport"),
    ("recovery.encrypted_archive", "ledger.export.restore_archive"),
)


_LEDGER_TUI_ROUTE_OBSERVATION_CAPABILITIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "ledger.overview": ("ledger.workspace.read",),
        "ledger.entries": ("ledger.transaction.list",),
        "ledger.review": ("ledger.transaction.review_query",),
        "ledger.import": ("ledger.import.source",),
        "ledger.classification": ("ledger.classify.direct",),
        "ledger.evidence": ("ledger.evidence.attachment_queue",),
        "ledger.reconciliation": ("ledger.transaction.invoice_link",),
    }
)


_EXPLICIT_NON_REGISTRY_OBSERVATION_SELECTIONS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "artifact_product:flat.csv": ("ledger.export.csv",),
        "artifact_product:flat.jsonl": ("ledger.export.jsonl",),
        "artifact_product:flat.xlsx": ("ledger.export.xlsx",),
        "artifact_product:recovery.encrypted_archive": ("ledger.export.restore_archive",),
        "artifact_product:review.google": ("ledger.export.google_transport",),
        "artifact_product:review.workbook_sidecar": ("ledger.export.review_package",),
        "backend_operation:ledger.classification.bulk_csv": ("ledger.classification.bulk_csv",),
        "backend_operation:ledger.classification.rule_add": ("ledger.classification.rule_add",),
        "backend_operation:ledger.classification.rule_apply": ("ledger.classification.rule_apply",),
        "backend_operation:ledger.counterparty.forget": ("ledger.counterparty.forget",),
        "backend_operation:ledger.counterparty.record": ("ledger.counterparty.record",),
        "backend_operation:ledger.counterparty.resolve": ("ledger.counterparty.resolve",),
        "backend_operation:ledger.evidence.add": ("ledger.evidence.add",),
        "backend_operation:ledger.evidence.attachment_queue": ("ledger.evidence.attachment_queue",),
        "backend_operation:ledger.evidence.attachment_view": ("ledger.evidence.attachment_view",),
        "backend_operation:ledger.evidence.batch": ("ledger.evidence.batch",),
        "backend_operation:ledger.evidence.consent_rederive": ("ledger.evidence.consent_rederive",),
        "backend_operation:ledger.evidence.consent_survey": ("ledger.evidence.consent_survey",),
        "backend_operation:ledger.evidence.list": ("ledger.evidence.list",),
        "backend_operation:ledger.evidence.remove": ("ledger.evidence.remove",),
        "backend_operation:ledger.evidence.update": ("ledger.evidence.update",),
        "backend_operation:ledger.evidence.view": ("ledger.evidence.view",),
        "backend_operation:ledger.export.flat": ("ledger.export.flat",),
        "backend_operation:ledger.import.aggregate_results": ("ledger.import.aggregate_results",),
        "backend_operation:ledger.import.prepare": ("ledger.import.prepare",),
        "backend_operation:ledger.import.parsed_rows": ("ledger.import.parsed_rows",),
        "backend_operation:ledger.import.source": ("ledger.import.source",),
        "backend_operation:ledger.invoice.confirm_draft": ("ledger.invoice.confirm_draft",),
        "backend_operation:ledger.invoice.extract_draft": ("ledger.invoice.extract_draft",),
        "backend_operation:ledger.lifecycle.archive": ("ledger.lifecycle.archive",),
        "backend_operation:ledger.lifecycle.remove": ("ledger.lifecycle.remove",),
        "backend_operation:ledger.lifecycle.reset": ("ledger.lifecycle.reset",),
        "backend_operation:ledger.lifecycle.restore": ("ledger.lifecycle.restore",),
        "backend_operation:ledger.lifecycle.reviewed_exclude": ("ledger.lifecycle.reviewed_exclude",),
        "backend_operation:ledger.lifecycle.stash": ("ledger.lifecycle.stash",),
        "backend_operation:ledger.llm.apply": ("ledger.llm.apply",),
        "backend_operation:ledger.llm.apply_evidence_classification": ("ledger.llm.apply_evidence_classification",),
        "backend_operation:ledger.llm.apply_saturated": ("ledger.llm.apply_saturated",),
        "backend_operation:ledger.llm.apply_split": ("ledger.llm.apply_split",),
        "backend_operation:ledger.llm.classify_with_evidence": ("ledger.llm.classify_with_evidence",),
        "backend_operation:ledger.llm.diagnostics": ("ledger.llm.diagnostics",),
        "backend_operation:ledger.llm.iva_derive": ("ledger.llm.iva_derive",),
        "backend_operation:ledger.llm.reject": ("ledger.llm.reject",),
        "backend_operation:ledger.llm.review_decision": ("ledger.llm.review_decision",),
        "backend_operation:ledger.llm.saturate": ("ledger.llm.saturate",),
        "backend_operation:ledger.llm.suggest": ("ledger.llm.suggest",),
        "backend_operation:ledger.llm.suggest_split": ("ledger.llm.suggest_split",),
        "backend_operation:ledger.participation.get": ("ledger.participation.get",),
        "backend_operation:ledger.preflight.catalogue": ("ledger.preflight.catalogue",),
        "backend_operation:ledger.preflight.readiness": ("ledger.preflight.readiness",),
        "backend_operation:ledger.ratio.list": ("ledger.ratio.list",),
        "backend_operation:ledger.ratio.set": ("ledger.ratio.set",),
        "backend_operation:ledger.ratio.unset": ("ledger.ratio.unset",),
        "backend_operation:ledger.ratio.validate": ("ledger.ratio.validate",),
        "backend_operation:ledger.transaction.attach": ("ledger.transaction.attach",),
        "backend_operation:ledger.transaction.create": ("ledger.transaction.create",),
        "backend_operation:ledger.transaction.detach": ("ledger.transaction.detach",),
        "backend_operation:ledger.transaction.get": ("ledger.transaction.get",),
        "backend_operation:ledger.transaction.invoice_link": ("ledger.transaction.invoice_link",),
        "backend_operation:ledger.transaction.list": ("ledger.transaction.list",),
        "backend_operation:ledger.transaction.merge": ("ledger.transaction.merge",),
        "backend_operation:ledger.transaction.review_query": ("ledger.transaction.review_query",),
        "backend_operation:ledger.transaction.split": ("ledger.transaction.split",),
        "backend_operation:ledger.transaction.split_classified": ("ledger.transaction.split_classified",),
        "backend_operation:ledger.transaction.status_summary": ("ledger.transaction.status_summary",),
        "backend_operation:ledger.transaction.update": ("ledger.transaction.update",),
        "backend_operation:ledger.transaction.update_fields": ("ledger.transaction.update_fields",),
        "backend_operation:ledger.workspace.affected_declarations": ("ledger.workspace.affected_declarations",),
        "backend_operation:ledger.workspace.project": ("ledger.workspace.project",),
        "backend_operation:ledger.workspace.read": ("ledger.workspace.read",),
        "cli_endpoint:app_ledger_add": ("ledger.transaction.create",),
        "cli_endpoint:app_ledger_allocate": ("ledger.allocate",),
        "cli_endpoint:app_ledger_archive": ("ledger.lifecycle.archive",),
        "cli_endpoint:app_ledger_attach": ("ledger.transaction.attach",),
        "cli_endpoint:app_ledger_bienes_inversion_declare": ("ledger.bienes_inversion.declare",),
        "cli_endpoint:app_ledger_bienes_inversion_list": ("ledger.bienes_inversion.list",),
        "cli_endpoint:app_ledger_categories": ("ledger.categories",),
        "cli_endpoint:app_ledger_check": ("ledger.check",),
        "cli_endpoint:app_ledger_classify": ("ledger.classify",),
        "cli_endpoint:app_ledger_counterparty_confirm": ("ledger.counterparty.record",),
        "cli_endpoint:app_ledger_counterparty_view": ("ledger.counterparty.resolve",),
        "cli_endpoint:app_ledger_counterparty_withdraw": ("ledger.counterparty.forget",),
        "cli_endpoint:app_ledger_detach": ("ledger.transaction.detach",),
        "cli_endpoint:app_ledger_evidence_add": ("ledger.evidence.add",),
        "cli_endpoint:app_ledger_evidence_attachment_queue": ("ledger.evidence.attachment_queue",),
        "cli_endpoint:app_ledger_evidence_attachment_view": ("ledger.evidence.attachment_view",),
        "cli_endpoint:app_ledger_evidence_batch": ("ledger.evidence.batch",),
        "cli_endpoint:app_ledger_evidence_confirm": ("ledger.evidence.confirm",),
        "cli_endpoint:app_ledger_evidence_consent_list": ("ledger.evidence.consent.list",),
        "cli_endpoint:app_ledger_evidence_consent_rederive": ("ledger.evidence.consent.rederive",),
        "cli_endpoint:app_ledger_evidence_extract": ("ledger.evidence.extract",),
        "cli_endpoint:app_ledger_evidence_list": ("ledger.evidence.list",),
        "cli_endpoint:app_ledger_evidence_pull": ("ledger.evidence.pull",),
        "cli_endpoint:app_ledger_evidence_pull_all": ("ledger.evidence.pull_all",),
        "cli_endpoint:app_ledger_evidence_remove": ("ledger.evidence.remove",),
        "cli_endpoint:app_ledger_evidence_review_list": ("ledger.evidence.review.list",),
        "cli_endpoint:app_ledger_evidence_review_view": ("ledger.evidence.review.view",),
        "cli_endpoint:app_ledger_evidence_update": ("ledger.evidence.update",),
        "cli_endpoint:app_ledger_evidence_view": ("ledger.evidence.view",),
        "cli_endpoint:app_ledger_exclude": ("ledger.lifecycle.reviewed_exclude",),
        "cli_endpoint:app_ledger_export": (
            "ledger.export.flat",
            "ledger.export.csv",
            "ledger.export.jsonl",
            "ledger.export.xlsx",
        ),
        "cli_endpoint:app_ledger_history": ("ledger.history",),
        "cli_endpoint:app_ledger_import": ("ledger.import",),
        "cli_endpoint:app_ledger_inventory_closing_authority_record": ("ledger.inventory.closing_authority.record",),
        "cli_endpoint:app_ledger_inventory_create": ("ledger.inventory.create",),
        "cli_endpoint:app_ledger_inventory_list": ("ledger.inventory.list",),
        "cli_endpoint:app_ledger_inventory_movement_add": ("ledger.inventory.movement.add",),
        "cli_endpoint:app_ledger_inventory_valuation_preview": ("ledger.inventory.valuation.preview",),
        "cli_endpoint:app_ledger_invoice_add": ("ledger.invoice.add",),
        "cli_endpoint:app_ledger_invoice_import": ("ledger.invoice.import",),
        "cli_endpoint:app_ledger_invoice_list": ("ledger.invoice.list",),
        "cli_endpoint:app_ledger_invoice_remove": ("ledger.invoice.remove",),
        "cli_endpoint:app_ledger_invoice_update": ("ledger.invoice.update",),
        "cli_endpoint:app_ledger_invoice_view": ("ledger.invoice.view",),
        "cli_endpoint:app_ledger_invoice_wizard": ("ledger.invoice.wizard",),
        "cli_endpoint:app_ledger_link": ("ledger.transaction.invoice_link",),
        "cli_endpoint:app_ledger_list": ("ledger.list",),
        "cli_endpoint:app_ledger_llm_diagnostics": ("ledger.llm.diagnostics",),
        "cli_endpoint:app_ledger_merge": ("ledger.transaction.merge",),
        "cli_endpoint:app_ledger_participation": ("ledger.participation.get",),
        "cli_endpoint:app_ledger_participation_rebuild": ("ledger.participation.rebuild",),
        "cli_endpoint:app_ledger_preflight": ("ledger.preflight.readiness",),
        "cli_endpoint:app_ledger_prorrata_declare_sector": ("ledger.prorrata.declare_sector",),
        "cli_endpoint:app_ledger_prorrata_elect_especial": ("ledger.prorrata.elect_especial",),
        "cli_endpoint:app_ledger_prorrata_elect_general": ("ledger.prorrata.elect_general",),
        "cli_endpoint:app_ledger_prorrata_list": ("ledger.prorrata.list",),
        "cli_endpoint:app_ledger_prorrata_revoke_especial": ("ledger.prorrata.revoke_especial",),
        "cli_endpoint:app_ledger_prorrata_seed": ("ledger.prorrata.seed",),
        "cli_endpoint:app_ledger_prorrata_seed_sector": ("ledger.prorrata.seed_sector",),
        "cli_endpoint:app_ledger_prorrata_settle_sector": ("ledger.prorrata.settle_sector",),
        "cli_endpoint:app_ledger_ratios_eligible": ("ledger.ratios.eligible",),
        "cli_endpoint:app_ledger_ratios_list": ("ledger.ratio.list",),
        "cli_endpoint:app_ledger_ratios_set": ("ledger.ratio.set",),
        "cli_endpoint:app_ledger_ratios_unset": ("ledger.ratio.unset",),
        "cli_endpoint:app_ledger_ratios_validate": ("ledger.ratio.validate",),
        "cli_endpoint:app_ledger_remove": ("ledger.lifecycle.remove",),
        "cli_endpoint:app_ledger_reset": ("ledger.lifecycle.reset",),
        "cli_endpoint:app_ledger_restore": ("ledger.lifecycle.restore",),
        "cli_endpoint:app_ledger_review": ("ledger.transaction.review_query",),
        "cli_endpoint:app_ledger_rule_add": ("ledger.classification.rule_add",),
        "cli_endpoint:app_ledger_rule_apply": ("ledger.rule.apply.preview", "ledger.classification.rule_apply"),
        "cli_endpoint:app_ledger_rule_list": ("ledger.rule.list",),
        "cli_endpoint:app_ledger_split": (
            "ledger.transaction.split",
            "ledger.llm.suggest_split",
            "ledger.llm.apply_split",
        ),
        "cli_endpoint:app_ledger_stash": ("ledger.lifecycle.stash",),
        "cli_endpoint:app_ledger_status": ("ledger.transaction.status_summary",),
        "cli_endpoint:app_ledger_track": ("ledger.track",),
        "cli_endpoint:app_ledger_update": ("ledger.transaction.update_fields",),
        "cli_endpoint:app_ledger_view": ("ledger.transaction.get",),
        "cli_suboperation:ledger.classify.auto_split.reject": ("ledger.llm.reject",),
        "cli_suboperation:ledger.classify.auto_split.single_apply": ("ledger.llm.apply",),
        "cli_suboperation:ledger.classify.auto_split.single_preview": ("ledger.llm.suggest",),
        "cli_suboperation:ledger.classify.auto_split.split_apply": ("ledger.llm.apply_split",),
        "cli_suboperation:ledger.classify.auto_split.split_preview": ("ledger.llm.suggest_split",),
        "cli_suboperation:ledger.classify.bulk_csv": ("ledger.classification.bulk_csv",),
        "cli_suboperation:ledger.classify.direct": ("ledger.classify.direct",),
        "cli_suboperation:ledger.classify.evidence_read": ("ledger.llm.classify_with_evidence",),
        "cli_suboperation:ledger.classify.iva_derive": ("ledger.llm.iva_derive",),
        "cli_suboperation:ledger.classify.llm_apply": ("ledger.llm.apply",),
        "cli_suboperation:ledger.classify.llm_preview": ("ledger.llm.suggest",),
        "cli_suboperation:ledger.classify.llm_reject": ("ledger.llm.reject",),
        "cli_suboperation:ledger.classify.llm_saturate_apply": ("ledger.llm.apply_saturated",),
        "cli_suboperation:ledger.classify.llm_saturate_preview": ("ledger.llm.saturate",),
        "cli_suboperation:ledger.classify.llm_saturate_reject": ("ledger.llm.reject",),
        "cli_suboperation:ledger.classify.m210": ("ledger.classify.m210",),
        "cli_suboperation:ledger.evidence.pull.drive": ("ledger.evidence.pull.drive",),
        "cli_suboperation:ledger.evidence.pull.gmail": ("ledger.evidence.pull.gmail",),
        "cli_suboperation:ledger.evidence.pull.url": ("ledger.evidence.pull.url",),
        "cli_suboperation:ledger.export.csv": ("ledger.export.csv",),
        "cli_suboperation:ledger.export.jsonl": ("ledger.export.jsonl",),
        "cli_suboperation:ledger.export.xlsx": ("ledger.export.xlsx",),
        "cli_suboperation:ledger.history.direct": ("ledger.history.direct",),
        "cli_suboperation:ledger.history.split_siblings": ("ledger.history.split_siblings",),
        "cli_suboperation:ledger.import.directory": ("ledger.import.directory",),
        "cli_suboperation:ledger.import.dry_run": ("ledger.import.dry_run",),
        "cli_suboperation:ledger.import.file": ("ledger.import.file",),
        "cli_suboperation:ledger.import.provider_auto": ("ledger.import.provider_auto",),
        "cli_suboperation:ledger.import.provider_csv": ("ledger.import.provider_csv",),
        "cli_suboperation:ledger.import.provider_n26": ("ledger.import.provider_n26",),
        "cli_suboperation:ledger.import.provider_ofx_qfx": ("ledger.import.provider_ofx_qfx",),
        "cli_suboperation:ledger.import.provider_pdf": ("ledger.import.provider_pdf",),
        "cli_suboperation:ledger.import.provider_pdf_n26": ("ledger.import.provider_pdf_n26",),
        "cli_suboperation:ledger.import.provider_xlsx_excel": ("ledger.import.provider_xlsx_excel",),
        "cli_suboperation:ledger.import.verify": ("ledger.import.verify",),
        "cli_suboperation:ledger.list.filter": ("ledger.list.filter",),
        "cli_suboperation:ledger.list.group": ("ledger.list.group",),
        "cli_suboperation:ledger.list.page": ("ledger.list.page",),
        "cli_suboperation:ledger.list.rejected_llm_filter": ("ledger.list.rejected_llm_filter",),
        "cli_suboperation:ledger.list.sort": ("ledger.list.sort",),
        "cli_suboperation:ledger.remove.commit": ("ledger.lifecycle.remove.commit",),
        "cli_suboperation:ledger.remove.preview": ("ledger.lifecycle.remove.preview",),
        "cli_suboperation:ledger.reset.commit": ("ledger.lifecycle.reset.commit",),
        "cli_suboperation:ledger.reset.preview": ("ledger.lifecycle.reset.preview",),
        "cli_suboperation:ledger.rule.apply.commit": ("ledger.classification.rule_apply",),
        "cli_suboperation:ledger.rule.apply.preview": ("ledger.rule.apply.preview",),
        "cli_suboperation:ledger.split.evidence_read": ("ledger.llm.classify_with_evidence",),
        "cli_suboperation:ledger.split.llm_apply": ("ledger.llm.apply_split",),
        "cli_suboperation:ledger.split.llm_preview": ("ledger.llm.suggest_split",),
        "cli_suboperation:ledger.split.manual": ("ledger.transaction.split",),
        "missing_product:append_only_notes": ("ledger.note.append",),
        "missing_product:application_paging": ("ledger.list.page",),
        "missing_product:atomic_evidence_replace": ("ledger.evidence.replace",),
        "missing_product:changed_field_provenance": ("ledger.field_change.provenance",),
        "missing_product:complete_export_provenance": (
            "ledger.export.provenance",
            "ledger.fx.provenance",
            "ledger.import.normalization_provenance",
            "ledger.manual_override.provenance",
        ),
        "missing_product:evidence_download": ("ledger.evidence.download",),
        "missing_product:generic_batch_patch": ("ledger.transaction.batch_patch",),
        "missing_product:google_ledger_export": ("ledger.export.google_transport",),
        "missing_product:restore_archive": ("ledger.export.restore_archive",),
        "missing_product:review_grade_workbook": ("ledger.export.review_package",),
        "supported_surface:ledger.classification:component_only": ("ledger.classify.direct",),
        "supported_surface:ledger.entries:component_only": ("ledger.transaction.list",),
        "supported_surface:ledger.evidence:component_only": ("ledger.evidence.attachment_queue",),
        "supported_surface:ledger.import:component_only": ("ledger.import.source",),
        "supported_surface:ledger.overview:installed": ("ledger.workspace.read",),
        "supported_surface:ledger.reconciliation:component_only": ("ledger.transaction.invoice_link",),
        "supported_surface:ledger.review:component_only": ("ledger.transaction.review_query",),
    }
)

_NON_REGISTRY_OBSERVATION_SOURCE_PREFIXES: Final[tuple[tuple[str, DenominatorSourceKind], ...]] = (
    ("artifact_product:", DenominatorSourceKind.ARTIFACT_PRODUCT),
    ("backend_operation:", DenominatorSourceKind.BACKEND_ONLY),
    ("cli_endpoint:", DenominatorSourceKind.CLI_ENDPOINT),
    ("cli_suboperation:", DenominatorSourceKind.CLI_SUBOPERATION),
    ("missing_product:", DenominatorSourceKind.MISSING_PRODUCT),
    ("supported_surface:", DenominatorSourceKind.SUPPORTED_SURFACE),
)


def _canonical_non_registry_observation_source(observation_id: str) -> DenominatorSourceKind:
    matches = tuple(
        source for prefix, source in _NON_REGISTRY_OBSERVATION_SOURCE_PREFIXES if observation_id.startswith(prefix)
    )
    if len(matches) != 1:
        raise ValueError(f"non-registry observation identity has no unique source authority: {observation_id}")
    return matches[0]


_EXPLICIT_NON_REGISTRY_OBSERVATION_AUTHORITIES: Final[Mapping[tuple[DenominatorSourceKind, str], tuple[str, ...]]] = (
    MappingProxyType(
        {
            (_canonical_non_registry_observation_source(observation_id), observation_id): capability_ids
            for observation_id, capability_ids in _EXPLICIT_NON_REGISTRY_OBSERVATION_SELECTIONS.items()
        }
    )
)


_BACKEND_DIRECT_PROOF_GAPS: Final[frozenset[str]] = frozenset(
    {
        "ledger.classification.rule_add",
        "ledger.classification.rule_apply",
        "ledger.import.aggregate_results",
        "ledger.evidence.attachment_view",
        "ledger.evidence.attachment_queue",
        "ledger.llm.diagnostics",
        "ledger.participation.get",
        "ledger.workspace.read",
    }
)

_LEDGER_BACKEND_OPERATION_SOURCE_PATHS: Final[tuple[str, ...]] = (
    "src/cadrumo/application/ledger/actions_classification.py",
    "src/cadrumo/application/ledger/actions_export.py",
    "src/cadrumo/application/ledger/actions_import.py",
    "src/cadrumo/application/ledger/import_preparation.py",
    "src/cadrumo/application/ledger/actions_lifecycle.py",
    "src/cadrumo/application/ledger/actions_manual.py",
    "src/cadrumo/application/ledger/actions_split_merge.py",
    "src/cadrumo/application/ledger/attachment_review.py",
    "src/cadrumo/application/ledger/batch_ingest.py",
    "src/cadrumo/application/ledger/consent_withdrawal.py",
    "src/cadrumo/application/ledger/counterparty_establishment.py",
    "src/cadrumo/application/ledger/evidence.py",
    "src/cadrumo/application/ledger/invoice_confirmation.py",
    "src/cadrumo/application/ledger/invoice_draft_extraction.py",
    "src/cadrumo/application/ledger/llm_classification.py",
    "src/cadrumo/application/ledger/llm_diagnostics.py",
    "src/cadrumo/application/ledger/llm_review_workflow.py",
    "src/cadrumo/application/ledger/participation_read.py",
    "src/cadrumo/application/ledger/preflight.py",
    "src/cadrumo/application/ledger/ratios.py",
    "src/cadrumo/application/ledger/workspace.py",
    "src/cadrumo/application/ledger/workspace_reader.py",
)

_REQUIRED_PUBLIC_BACKEND_OPERATIONS: Final[Mapping[str, tuple[str, str]]] = MappingProxyType(
    {
        "ledger.import.prepare": (
            "src/cadrumo/application/ledger/import_preparation.py",
            "prepare_ledger_import_command",
        ),
    }
)


def _validate_required_public_backend_operations() -> None:
    """Refuse a census that loses a public application operation or its source."""
    declarations = {item.capability_id: item for item in _LEDGER_BACKEND_OPERATION_DECLARATIONS}
    source_paths = frozenset(_LEDGER_BACKEND_OPERATION_SOURCE_PATHS)
    for capability_id, (source_path, symbol_name) in _REQUIRED_PUBLIC_BACKEND_OPERATIONS.items():
        if source_path not in source_paths:
            raise ValueError(f"public backend operation source is omitted: {source_path}")
        declaration = declarations.get(capability_id)
        if declaration is None:
            raise ValueError(f"public backend operation is omitted: {capability_id}")
        module_name, separator, declared_symbol = declaration.owner.partition(":")
        if not separator or declared_symbol != symbol_name:
            raise ValueError(f"public backend operation owner drifted: {capability_id}")
        if not callable(getattr(importlib.import_module(module_name), symbol_name, None)):
            raise ValueError(f"public backend operation symbol is unavailable: {capability_id}")


def _stable_segment(value: str) -> str:
    segment = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "value"
    return f"x_{segment}" if segment[0].isdigit() else segment


def _registry_union_capability_id(row: LedgerRegistryRouteRowV1) -> str:
    family = row.source.value.removeprefix("ledger_").removesuffix("_aggregation")
    identity_digest = hashlib.sha256(_canonical_json_text(row).encode("utf-8")).hexdigest()[:16]
    return ".".join(
        (
            "ledger",
            "registry_route",
            _stable_segment(family),
            _stable_segment(row.modelo_id),
            _stable_segment(row.revision_id),
            f"route_{identity_digest}",
        )
    )


def _selection_for_observation(observation_id: str) -> tuple[str, ...]:
    """Return the exact authored selection; new observations never self-admit."""
    try:
        return _EXPLICIT_NON_REGISTRY_OBSERVATION_SELECTIONS[observation_id]
    except KeyError as exc:
        raise ValueError(f"non-registry observation has no explicit adjudication: {observation_id}") from exc


def _pascal_identity(capability_id: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[._]", capability_id.removeprefix("ledger.")))


_EXPLICIT_QUERY_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {
        "ledger.bienes_inversion.list",
        "ledger.categories",
        "ledger.check",
        "ledger.counterparty.resolve",
        "ledger.evidence.attachment_queue",
        "ledger.evidence.attachment_view",
        "ledger.evidence.consent.list",
        "ledger.evidence.consent_survey",
        "ledger.evidence.list",
        "ledger.evidence.review.list",
        "ledger.evidence.review.view",
        "ledger.evidence.view",
        "ledger.export.provenance",
        "ledger.field_change.provenance",
        "ledger.fx.provenance",
        "ledger.history",
        "ledger.history.direct",
        "ledger.history.split_siblings",
        "ledger.import.aggregate_results",
        "ledger.import.prepare",
        "ledger.import.normalization_provenance",
        "ledger.inventory.list",
        "ledger.invoice.list",
        "ledger.invoice.view",
        "ledger.list",
        "ledger.list.filter",
        "ledger.list.group",
        "ledger.list.page",
        "ledger.list.rejected_llm_filter",
        "ledger.list.sort",
        "ledger.llm.diagnostics",
        "ledger.manual_override.provenance",
        "ledger.participation.get",
        "ledger.preflight.catalogue",
        "ledger.preflight.readiness",
        "ledger.prorrata.list",
        "ledger.ratio.list",
        "ledger.ratio.validate",
        "ledger.ratios.eligible",
        "ledger.rule.list",
        "ledger.track",
        "ledger.transaction.get",
        "ledger.transaction.list",
        "ledger.transaction.review_query",
        "ledger.transaction.status_summary",
        "ledger.workspace.affected_declarations",
        "ledger.workspace.project",
        "ledger.workspace.read",
    }
)


def _annotation_name(annotation: object) -> str:
    if isinstance(annotation, str):
        return annotation.strip("'")
    name = getattr(annotation, "__name__", None)
    return name if isinstance(name, str) else str(annotation)


def _validate_existing_semantic_home(
    declaration: _BackendOperationDeclaration, *, owner_callable: Callable[..., object] | None = None
) -> None:
    """Prove an existing request/result claim against the live callable boundary."""
    if declaration.status is not SemanticHomeStatus.EXISTING:
        return
    if owner_callable is None:
        module_name, separator, symbol_name = declaration.owner.partition(":")
        if not separator:
            raise ValueError(f"existing semantic home lacks a callable locator: {declaration.capability_id}")
        owner_callable = cast(Callable[..., object], getattr(importlib.import_module(module_name), symbol_name))
    signature = inspect.signature(owner_callable)
    parameters = tuple(signature.parameters.values())
    if not parameters or _annotation_name(parameters[0].annotation) != declaration.command_type:
        raise ValueError(f"existing semantic-home request signature drifted: {declaration.capability_id}")
    if any(parameter.default is inspect.Parameter.empty for parameter in parameters[1:]):
        raise ValueError(f"existing semantic home requires loose business parameters: {declaration.capability_id}")
    if _annotation_name(signature.return_annotation) != declaration.result_type:
        raise ValueError(f"existing semantic-home result signature drifted: {declaration.capability_id}")


_EXPLICIT_PROPOSAL_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {
        "ledger.inventory.valuation.preview",
        "ledger.lifecycle.remove.preview",
        "ledger.lifecycle.reset.preview",
        "ledger.llm.classify_with_evidence",
        "ledger.llm.iva_derive",
        "ledger.llm.saturate",
        "ledger.llm.suggest",
        "ledger.llm.suggest_split",
        "ledger.rule.apply.preview",
    }
)
_EXPLICIT_ARTIFACT_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {
        "ledger.export.csv",
        "ledger.export.flat",
        "ledger.export.google_transport",
        "ledger.export.jsonl",
        "ledger.export.restore_archive",
        "ledger.export.review_package",
        "ledger.export.xlsx",
    }
)
_EXPLICIT_ARTIFACT_QUERY_CAPABILITIES: Final[frozenset[str]] = frozenset({"ledger.evidence.download"})
_EXPLICIT_PROVENANCE_QUERY_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {
        "ledger.evidence.download",
        "ledger.export.provenance",
        "ledger.field_change.provenance",
        "ledger.fx.provenance",
        "ledger.import.normalization_provenance",
        "ledger.manual_override.provenance",
    }
)
_EXPLICIT_MUTATION_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {
        "ledger.allocate",
        "ledger.bienes_inversion.declare",
        "ledger.classification.bulk_csv",
        "ledger.classification.rule_add",
        "ledger.classification.rule_apply",
        "ledger.classify",
        "ledger.classify.direct",
        "ledger.classify.m210",
        "ledger.counterparty.forget",
        "ledger.counterparty.record",
        "ledger.evidence.add",
        "ledger.evidence.batch",
        "ledger.evidence.confirm",
        "ledger.evidence.consent.rederive",
        "ledger.evidence.consent_rederive",
        "ledger.evidence.extract",
        "ledger.evidence.pull",
        "ledger.evidence.pull.drive",
        "ledger.evidence.pull.gmail",
        "ledger.evidence.pull.url",
        "ledger.evidence.pull_all",
        "ledger.evidence.remove",
        "ledger.evidence.replace",
        "ledger.evidence.update",
        "ledger.import",
        "ledger.import.directory",
        "ledger.import.dry_run",
        "ledger.import.file",
        "ledger.import.parsed_rows",
        "ledger.import.provider_auto",
        "ledger.import.provider_csv",
        "ledger.import.provider_n26",
        "ledger.import.provider_ofx_qfx",
        "ledger.import.provider_pdf",
        "ledger.import.provider_pdf_n26",
        "ledger.import.provider_xlsx_excel",
        "ledger.import.source",
        "ledger.import.verify",
        "ledger.inventory.closing_authority.record",
        "ledger.inventory.create",
        "ledger.inventory.movement.add",
        "ledger.invoice.add",
        "ledger.invoice.confirm_draft",
        "ledger.invoice.extract_draft",
        "ledger.invoice.import",
        "ledger.invoice.remove",
        "ledger.invoice.update",
        "ledger.invoice.wizard",
        "ledger.lifecycle.archive",
        "ledger.lifecycle.remove",
        "ledger.lifecycle.remove.commit",
        "ledger.lifecycle.reset",
        "ledger.lifecycle.reset.commit",
        "ledger.lifecycle.restore",
        "ledger.lifecycle.reviewed_exclude",
        "ledger.lifecycle.stash",
        "ledger.llm.apply",
        "ledger.llm.apply_evidence_classification",
        "ledger.llm.apply_saturated",
        "ledger.llm.apply_split",
        "ledger.llm.reject",
        "ledger.llm.review_decision",
        "ledger.note.append",
        "ledger.participation.rebuild",
        "ledger.prorrata.declare_sector",
        "ledger.prorrata.elect_especial",
        "ledger.prorrata.elect_general",
        "ledger.prorrata.revoke_especial",
        "ledger.prorrata.seed",
        "ledger.prorrata.seed_sector",
        "ledger.prorrata.settle_sector",
        "ledger.ratio.set",
        "ledger.ratio.unset",
        "ledger.transaction.attach",
        "ledger.transaction.batch_patch",
        "ledger.transaction.create",
        "ledger.transaction.detach",
        "ledger.transaction.invoice_link",
        "ledger.transaction.merge",
        "ledger.transaction.split",
        "ledger.transaction.split_classified",
        "ledger.transaction.update",
        "ledger.transaction.update_fields",
    }
)

_EXPLICIT_EFFECTS: Final[Mapping[str, LedgerCapabilityEffect]] = MappingProxyType(
    {
        **{item: LedgerCapabilityEffect.QUERY for item in _EXPLICIT_QUERY_CAPABILITIES},
        **{item: LedgerCapabilityEffect.PROPOSAL for item in _EXPLICIT_PROPOSAL_CAPABILITIES},
        **{item: LedgerCapabilityEffect.ARTIFACT for item in _EXPLICIT_ARTIFACT_CAPABILITIES},
        **{item: LedgerCapabilityEffect.ARTIFACT_QUERY for item in _EXPLICIT_ARTIFACT_QUERY_CAPABILITIES},
        **{item: LedgerCapabilityEffect.MUTATION for item in _EXPLICIT_MUTATION_CAPABILITIES},
    }
)
_EXPLICIT_BACKEND_HELPER_ONLY_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {
        "ledger.evidence.consent_rederive",
        "ledger.evidence.consent_survey",
        "ledger.import.aggregate_results",
        "ledger.import.prepare",
        "ledger.import.parsed_rows",
        "ledger.invoice.confirm_draft",
        "ledger.invoice.extract_draft",
        "ledger.llm.apply_evidence_classification",
        "ledger.llm.review_decision",
        "ledger.preflight.catalogue",
        "ledger.transaction.split_classified",
        "ledger.transaction.update",
        "ledger.workspace.affected_declarations",
        "ledger.workspace.project",
    }
)


@dataclass(frozen=True, slots=True)
class LedgerCliArtifactInputObservation:
    """One live local-input declaration and every semantic row selected by its command."""

    command_key: str
    parameter_name: str
    shape: TransportShape
    role: TransportRole
    capability_ids: tuple[str, ...]


_EXPECTED_LEDGER_CLI_ARTIFACT_INPUT_OBSERVATIONS: Final[tuple[LedgerCliArtifactInputObservation, ...]] = (
    LedgerCliArtifactInputObservation(
        "app_ledger_classify",
        "file",
        TransportShape.FILE,
        TransportRole.PRIMARY,
        (
            "ledger.classification.bulk_csv",
            "ledger.classify",
            "ledger.classify.direct",
            "ledger.classify.m210",
            "ledger.llm.apply",
            "ledger.llm.apply_saturated",
            "ledger.llm.apply_split",
            "ledger.llm.classify_with_evidence",
            "ledger.llm.iva_derive",
            "ledger.llm.reject",
            "ledger.llm.saturate",
            "ledger.llm.suggest",
            "ledger.llm.suggest_split",
        ),
    ),
    LedgerCliArtifactInputObservation(
        "app_ledger_evidence_add",
        "source_path",
        TransportShape.FILE,
        TransportRole.PRIMARY,
        ("ledger.evidence.add",),
    ),
    LedgerCliArtifactInputObservation(
        "app_ledger_evidence_batch",
        "directory",
        TransportShape.DIRECTORY,
        TransportRole.PRIMARY,
        ("ledger.evidence.batch",),
    ),
    LedgerCliArtifactInputObservation(
        "app_ledger_evidence_batch",
        "file",
        TransportShape.FILE,
        TransportRole.PRIMARY,
        ("ledger.evidence.batch",),
    ),
    LedgerCliArtifactInputObservation(
        "app_ledger_import",
        "file",
        TransportShape.FILE,
        TransportRole.PRIMARY,
        (
            "ledger.import",
            "ledger.import.directory",
            "ledger.import.dry_run",
            "ledger.import.file",
            "ledger.import.provider_auto",
            "ledger.import.provider_csv",
            "ledger.import.provider_n26",
            "ledger.import.provider_ofx_qfx",
            "ledger.import.provider_pdf",
            "ledger.import.provider_pdf_n26",
            "ledger.import.provider_xlsx_excel",
            "ledger.import.verify",
        ),
    ),
    LedgerCliArtifactInputObservation(
        "app_ledger_import",
        "verify_source",
        TransportShape.FILE,
        TransportRole.AUXILIARY,
        (
            "ledger.import",
            "ledger.import.directory",
            "ledger.import.dry_run",
            "ledger.import.file",
            "ledger.import.provider_auto",
            "ledger.import.provider_csv",
            "ledger.import.provider_n26",
            "ledger.import.provider_ofx_qfx",
            "ledger.import.provider_pdf",
            "ledger.import.provider_pdf_n26",
            "ledger.import.provider_xlsx_excel",
            "ledger.import.verify",
        ),
    ),
    LedgerCliArtifactInputObservation(
        "app_ledger_inventory_closing_authority_record",
        "file",
        TransportShape.FILE,
        TransportRole.PRIMARY,
        ("ledger.inventory.closing_authority.record",),
    ),
    LedgerCliArtifactInputObservation(
        "app_ledger_invoice_import",
        "file",
        TransportShape.FILE,
        TransportRole.PRIMARY,
        ("ledger.invoice.import",),
    ),
)
_REVIEWED_ADDITIONAL_ARTIFACT_INPUT_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {
        "ledger.evidence.replace",
        "ledger.import.source",
    }
)

_EXPLICIT_TUI_ROUTE_GROUPS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "ledger.overview": frozenset({"ledger.workspace.read"}),
        "ledger.classification": frozenset(
            {
                "ledger.categories",
                "ledger.classification.bulk_csv",
                "ledger.classification.rule_add",
                "ledger.classification.rule_apply",
                "ledger.classify",
                "ledger.classify.direct",
                "ledger.classify.m210",
                "ledger.rule.apply.preview",
                "ledger.rule.list",
            }
        ),
        "ledger.evidence": frozenset(
            {
                "ledger.evidence.add",
                "ledger.evidence.attachment_queue",
                "ledger.evidence.attachment_view",
                "ledger.evidence.batch",
                "ledger.evidence.confirm",
                "ledger.evidence.consent.list",
                "ledger.evidence.consent.rederive",
                "ledger.evidence.download",
                "ledger.evidence.extract",
                "ledger.evidence.list",
                "ledger.evidence.pull",
                "ledger.evidence.pull.drive",
                "ledger.evidence.pull.gmail",
                "ledger.evidence.pull.url",
                "ledger.evidence.pull_all",
                "ledger.evidence.remove",
                "ledger.evidence.replace",
                "ledger.evidence.review.list",
                "ledger.evidence.review.view",
                "ledger.evidence.update",
                "ledger.evidence.view",
            }
        ),
        "ledger.import": frozenset(
            {
                "ledger.import",
                "ledger.import.directory",
                "ledger.import.dry_run",
                "ledger.import.file",
                "ledger.import.provider_auto",
                "ledger.import.provider_csv",
                "ledger.import.provider_n26",
                "ledger.import.provider_ofx_qfx",
                "ledger.import.provider_pdf",
                "ledger.import.provider_pdf_n26",
                "ledger.import.provider_xlsx_excel",
                "ledger.import.source",
                "ledger.import.verify",
            }
        ),
        "ledger.review": frozenset(
            {
                "ledger.field_change.provenance",
                "ledger.fx.provenance",
                "ledger.import.normalization_provenance",
                "ledger.list.rejected_llm_filter",
                "ledger.llm.apply",
                "ledger.llm.apply_saturated",
                "ledger.llm.apply_split",
                "ledger.llm.classify_with_evidence",
                "ledger.llm.diagnostics",
                "ledger.llm.iva_derive",
                "ledger.llm.reject",
                "ledger.llm.saturate",
                "ledger.llm.suggest",
                "ledger.llm.suggest_split",
                "ledger.manual_override.provenance",
                "ledger.note.append",
                "ledger.transaction.review_query",
            }
        ),
        "ledger.entries": frozenset(
            {
                "ledger.allocate",
                "ledger.check",
                "ledger.history",
                "ledger.history.direct",
                "ledger.history.split_siblings",
                "ledger.lifecycle.archive",
                "ledger.lifecycle.remove",
                "ledger.lifecycle.remove.commit",
                "ledger.lifecycle.remove.preview",
                "ledger.lifecycle.reset",
                "ledger.lifecycle.reset.commit",
                "ledger.lifecycle.reset.preview",
                "ledger.lifecycle.restore",
                "ledger.lifecycle.reviewed_exclude",
                "ledger.lifecycle.stash",
                "ledger.list",
                "ledger.list.filter",
                "ledger.list.group",
                "ledger.list.page",
                "ledger.list.sort",
                "ledger.track",
                "ledger.transaction.attach",
                "ledger.transaction.batch_patch",
                "ledger.transaction.create",
                "ledger.transaction.detach",
                "ledger.transaction.get",
                "ledger.transaction.list",
                "ledger.transaction.merge",
                "ledger.transaction.split",
                "ledger.transaction.status_summary",
                "ledger.transaction.update_fields",
            }
        ),
        "ledger.reconciliation": frozenset(
            {
                "ledger.bienes_inversion.declare",
                "ledger.bienes_inversion.list",
                "ledger.counterparty.forget",
                "ledger.counterparty.record",
                "ledger.counterparty.resolve",
                "ledger.export.csv",
                "ledger.export.flat",
                "ledger.export.google_transport",
                "ledger.export.jsonl",
                "ledger.export.provenance",
                "ledger.export.restore_archive",
                "ledger.export.review_package",
                "ledger.export.xlsx",
                "ledger.inventory.closing_authority.record",
                "ledger.inventory.create",
                "ledger.inventory.list",
                "ledger.inventory.movement.add",
                "ledger.inventory.valuation.preview",
                "ledger.invoice.add",
                "ledger.invoice.import",
                "ledger.invoice.list",
                "ledger.invoice.remove",
                "ledger.invoice.update",
                "ledger.invoice.view",
                "ledger.invoice.wizard",
                "ledger.participation.get",
                "ledger.participation.rebuild",
                "ledger.preflight.readiness",
                "ledger.prorrata.declare_sector",
                "ledger.prorrata.elect_especial",
                "ledger.prorrata.elect_general",
                "ledger.prorrata.list",
                "ledger.prorrata.revoke_especial",
                "ledger.prorrata.seed",
                "ledger.prorrata.seed_sector",
                "ledger.prorrata.settle_sector",
                "ledger.ratio.list",
                "ledger.ratio.set",
                "ledger.ratio.unset",
                "ledger.ratio.validate",
                "ledger.ratios.eligible",
                "ledger.transaction.invoice_link",
            }
        ),
    }
)

_EXPLICIT_TUI_ROUTE_ADJUDICATION: Final[tuple[tuple[str, tuple[str, ...]], ...]] = tuple(
    sorted(
        (capability_id, (route,))
        for route, capability_ids in _EXPLICIT_TUI_ROUTE_GROUPS.items()
        for capability_id in capability_ids
    )
)


def _derive_ledger_cli_artifact_input_observations(
    command_specs: tuple[CommandSpec, ...] | None = None,
    *,
    selection_for_observation: Callable[[str], tuple[str, ...]] = _selection_for_observation,
) -> tuple[LedgerCliArtifactInputObservation, ...]:
    """Project local file/directory input authority from the live Ledger CommandSpecs."""
    from cadrumo.entrypoints.cli._app_ledger_command_specs import (
        LEDGER_CLI_COMMAND_CENSUS,
        LEDGER_COMMAND_SPECS,
    )

    specs = LEDGER_COMMAND_SPECS if command_specs is None else command_specs
    census_by_key = {entry.command_key: entry for entry in LEDGER_CLI_COMMAND_CENSUS}
    observations: list[LedgerCliArtifactInputObservation] = []
    for spec in specs:
        local_inputs = tuple(
            parameter
            for parameter in spec.parameters
            if parameter.transport_locus is TransportLocus.LOCAL_IN
            and parameter.transport_shape in {TransportShape.FILE, TransportShape.DIRECTORY}
        )
        if not local_inputs:
            continue
        entry = census_by_key.get(spec.key)
        if entry is None:
            raise ValueError(f"Ledger local-input CommandSpec is not an invocable census member: {spec.key}")
        capability_ids = set(selection_for_observation(f"cli_endpoint:{entry.command_key}"))
        for suboperation_id in entry.suboperation_ids:
            capability_ids.update(selection_for_observation(f"cli_suboperation:{suboperation_id}"))
        canonical_capability_ids = tuple(sorted(capability_ids))
        if not canonical_capability_ids:
            raise ValueError(f"Ledger local-input CommandSpec selects no semantic capabilities: {spec.key}")
        observations.extend(
            LedgerCliArtifactInputObservation(
                command_key=spec.key,
                parameter_name=parameter.name,
                shape=parameter.transport_shape,
                role=parameter.transport_role,
                capability_ids=canonical_capability_ids,
            )
            for parameter in local_inputs
        )
    return tuple(sorted(observations, key=lambda item: (item.command_key, item.parameter_name)))


def _validate_artifact_input_capabilities(
    observations: tuple[LedgerCliArtifactInputObservation, ...],
) -> frozenset[str]:
    """Refuse transport metadata or semantic-selection drift and return its row authority."""
    if observations != _EXPECTED_LEDGER_CLI_ARTIFACT_INPUT_OBSERVATIONS:
        raise ValueError("artifact-input CommandSpec metadata or semantic mapping drifted")
    live_capabilities = frozenset(
        capability_id for observation in observations for capability_id in observation.capability_ids
    )
    capability_ids = live_capabilities | _REVIEWED_ADDITIONAL_ARTIFACT_INPUT_CAPABILITIES
    unknown = capability_ids - set(_EXPLICIT_EFFECTS)
    if unknown:
        raise ValueError(f"artifact-input adjudication names unknown capabilities: {sorted(unknown)!r}")
    return capability_ids


@cache
def _artifact_input_capabilities() -> frozenset[str]:
    """Return live CommandSpec-derived plus explicit reviewed planned artifact inputs."""
    return _validate_artifact_input_capabilities(_derive_ledger_cli_artifact_input_observations())


def _validate_tui_route_adjudication(
    adjudication: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    known_routes: frozenset[str] | None = None,
) -> None:
    """Refuse any drift from the exact reviewed non-registry route table."""
    if adjudication != tuple(sorted(adjudication, key=lambda item: item[0])):
        raise ValueError("TUI route adjudication must use canonical capability order")
    identities = tuple(capability_id for capability_id, _routes in adjudication)
    if len(set(identities)) != len(identities):
        raise ValueError("TUI route adjudication contains duplicate capability identities")
    expected = set(_EXPLICIT_EFFECTS) - set(_EXPLICIT_BACKEND_HELPER_ONLY_CAPABILITIES)
    actual = set(identities)
    if actual != expected:
        raise ValueError(
            "TUI route adjudication coverage drifted: "
            f"added={sorted(actual - expected)!r}; removed={sorted(expected - actual)!r}"
        )
    route_authority = frozenset(_EXPLICIT_TUI_ROUTE_GROUPS) if known_routes is None else known_routes
    for capability_id, routes in adjudication:
        if not routes or routes != tuple(sorted(set(routes))):
            raise ValueError(f"TUI routes must be nonempty, unique, and canonical: {capability_id}")
        unknown = set(routes) - set(route_authority)
        if unknown:
            raise ValueError(f"TUI route adjudication names unknown routes: {sorted(unknown)!r}")
    if adjudication != _EXPLICIT_TUI_ROUTE_ADJUDICATION:
        raise ValueError("TUI route adjudication drifted from the exhaustive reviewed mapping")


def _validate_supported_surface_route_selections(
    observations: tuple[LedgerUnionSourceObservationV1, ...],
    rows: tuple[LedgerUnionCapabilityRowV1, ...],
) -> None:
    """Require every supported-surface selection to name a row routed through that surface."""
    rows_by_id = {row.capability_id: row for row in rows}
    for observation in observations:
        if observation.source is not DenominatorSourceKind.SUPPORTED_SURFACE:
            continue
        parts = observation.observation_id.split(":")
        if len(parts) != 3 or parts[0] != "supported_surface":
            raise ValueError(f"supported-surface observation has an invalid identity: {observation.observation_id}")
        destination = parts[1]
        for capability_id in observation.capability_ids:
            row = rows_by_id.get(capability_id)
            if row is None:
                raise ValueError(f"supported-surface observation selects an unavailable row: {capability_id}")
            if destination not in row.tui_routes:
                raise ValueError(
                    "supported-surface observation destination is absent from selected row TUI routes: "
                    f"{observation.observation_id} -> {capability_id}"
                )


def _tui_routes_for(
    capability_id: str,
    effect: LedgerCapabilityEffect,
) -> tuple[str, ...]:
    """Return the exact reviewed route disposition for one semantic row."""
    if effect is LedgerCapabilityEffect.REGISTRY_ROUTE:
        return ("ledger.reconciliation",)
    routes = dict(_EXPLICIT_TUI_ROUTE_ADJUDICATION).get(capability_id)
    if capability_id in _EXPLICIT_BACKEND_HELPER_ONLY_CAPABILITIES:
        if routes is not None:
            raise ValueError(f"backend-helper-only capability cannot have a TUI route: {capability_id}")
        return ()
    if routes is None:
        raise ValueError(f"TUI-applicable capability has no reviewed route: {capability_id}")
    if "ledger.overview" in routes and effect is not LedgerCapabilityEffect.QUERY:
        raise ValueError("the installed Overview route is read-only and cannot host a non-query capability")
    return routes


def _effect_for(capability_id: str, sources: frozenset[DenominatorSourceKind]) -> LedgerCapabilityEffect:
    if DenominatorSourceKind.REGISTRY_ROUTE in sources:
        if not capability_id.startswith("ledger.registry_route."):
            raise ValueError(f"registry observation selected a non-registry identity: {capability_id}")
        return LedgerCapabilityEffect.REGISTRY_ROUTE
    try:
        return _EXPLICIT_EFFECTS[capability_id]
    except KeyError as exc:
        raise ValueError(f"unadjudicated non-registry capability identity: {capability_id}") from exc


def _validate_non_registry_decision_coverage(
    observations: tuple[LedgerUnionSourceObservationV1, ...],
) -> None:
    observed = {
        capability_id
        for observation in observations
        if observation.source is not DenominatorSourceKind.REGISTRY_ROUTE
        for capability_id in observation.capability_ids
    }
    if observed != set(_EXPLICIT_EFFECTS):
        missing = sorted(observed - set(_EXPLICIT_EFFECTS))
        removed = sorted(set(_EXPLICIT_EFFECTS) - observed)
        raise ValueError(f"non-registry semantic adjudication is stale; unadjudicated={missing}; removed={removed}")


def _validate_non_registry_observation_adjudication(
    observations: tuple[LedgerUnionSourceObservationV1, ...],
) -> None:
    non_registry = tuple(
        observation for observation in observations if observation.source is not DenominatorSourceKind.REGISTRY_ROUTE
    )
    identities = tuple(observation.observation_id for observation in non_registry)
    if len(set(identities)) != len(identities):
        raise ValueError("non-registry observation identities must be unique")
    actual = {
        (observation.source, observation.observation_id): observation.capability_ids for observation in non_registry
    }
    expected = dict(_EXPLICIT_NON_REGISTRY_OBSERVATION_AUTHORITIES)
    if actual != expected:
        added = sorted(set(actual) - set(expected))
        removed = sorted(set(expected) - set(actual))
        changed = sorted(identity for identity in set(actual) & set(expected) if actual[identity] != expected[identity])
        raise ValueError(
            "non-registry observation adjudication drifted; "
            f"added={added}; removed={removed}; changed_selections={changed}"
        )
    _validate_non_registry_decision_coverage(non_registry)


def _validate_registry_observation_projection(
    registry: LedgerRegistryRouteCensusV1,
    observations: tuple[LedgerUnionSourceObservationV1, ...],
) -> None:
    actual = {
        observation.observation_id: observation.capability_ids
        for observation in observations
        if observation.source is DenominatorSourceKind.REGISTRY_ROUTE
    }
    expected = {
        "registry_route:" + "|".join(map(str, row.sort_key)): (_registry_union_capability_id(row),)
        for row in registry.rows
    }
    if len(actual) != len(registry.rows) or actual != expected:
        raise ValueError("registry observation identities, count, or route selections drifted")


def _planned_owner(capability_id: str) -> str:
    if capability_id not in _EXPLICIT_EFFECTS:
        raise ValueError(f"union capability has no explicit semantic-home decision: {capability_id}")
    return "cadrumo.application.ledger.command_contracts"


def _semantic_home_for(
    capability_id: str,
    effect: LedgerCapabilityEffect,
) -> tuple[CanonicalSemanticHomeV1, SemanticHomeStatus]:
    declarations = {
        item.capability_id: item
        for item in (*_LEDGER_BACKEND_OPERATION_DECLARATIONS, *_LEDGER_MISSING_PRODUCT_DECLARATIONS)
    }
    declaration = declarations.get(capability_id)
    if declaration is not None:
        return (
            CanonicalSemanticHomeV1(
                owner=declaration.owner,
                command_type=declaration.command_type,
                result_type=declaration.result_type,
            ),
            declaration.status,
        )
    if effect is LedgerCapabilityEffect.REGISTRY_ROUTE:
        return (
            CanonicalSemanticHomeV1(
                owner="cadrumo.domain.calculations.registry.binding_targets:casillas_by_binding",
                command_type="LedgerBindingRouteQuery",
                result_type="LedgerBindingRouteResult",
            ),
            SemanticHomeStatus.PLANNED,
        )
    stem = f"Ledger{_pascal_identity(capability_id)}"
    if capability_id not in _EXPLICIT_EFFECTS:
        raise ValueError(f"union capability has no explicit planned contract decision: {capability_id}")
    request_suffix = (
        "Query" if effect in {LedgerCapabilityEffect.QUERY, LedgerCapabilityEffect.ARTIFACT_QUERY} else "Command"
    )
    return (
        CanonicalSemanticHomeV1(
            owner=_planned_owner(capability_id),
            command_type=f"{stem}{request_suffix}",
            result_type=f"{stem}Result",
        ),
        SemanticHomeStatus.PLANNED,
    )


def _axis_decisions(
    capability_id: str,
    sources: frozenset[DenominatorSourceKind],
    effect: LedgerCapabilityEffect,
) -> tuple[LedgerAxisApplicabilityDecisionV1, ...]:
    if effect is not LedgerCapabilityEffect.REGISTRY_ROUTE and capability_id not in _EXPLICIT_EFFECTS:
        raise ValueError(f"union capability has no explicit applicability decision: {capability_id}")
    backend_helper_only = capability_id in _EXPLICIT_BACKEND_HELPER_ONLY_CAPABILITIES
    if backend_helper_only != (
        sources == frozenset({DenominatorSourceKind.BACKEND_ONLY}) and capability_id != "ledger.workspace.read"
    ):
        raise ValueError(f"explicit backend-helper applicability drifted: {capability_id}")
    applicable = {
        LedgerCapabilityAxis.BACKEND: True,
        LedgerCapabilityAxis.CLI: not backend_helper_only,
        LedgerCapabilityAxis.TUI: not backend_helper_only,
        LedgerCapabilityAxis.COMPOSITION: effect
        in {
            LedgerCapabilityEffect.MUTATION,
            LedgerCapabilityEffect.PROPOSAL,
            LedgerCapabilityEffect.ARTIFACT,
            LedgerCapabilityEffect.ARTIFACT_QUERY,
            LedgerCapabilityEffect.REGISTRY_ROUTE,
        },
        LedgerCapabilityAxis.ARTIFACT: effect
        in {LedgerCapabilityEffect.ARTIFACT, LedgerCapabilityEffect.ARTIFACT_QUERY}
        or capability_id in _artifact_input_capabilities(),
        LedgerCapabilityAxis.PROVENANCE: effect
        in {
            LedgerCapabilityEffect.MUTATION,
            LedgerCapabilityEffect.PROPOSAL,
            LedgerCapabilityEffect.ARTIFACT,
            LedgerCapabilityEffect.REGISTRY_ROUTE,
        }
        or capability_id in _EXPLICIT_PROVENANCE_QUERY_CAPABILITIES,
        LedgerCapabilityAxis.REGISTRY: effect is LedgerCapabilityEffect.REGISTRY_ROUTE
        or capability_id in {"ledger.participation.get", "ledger.workspace.affected_declarations"},
        LedgerCapabilityAxis.PROOF: True,
    }
    rationales = {
        LedgerCapabilityAxis.BACKEND: "Every admitted behavior requires one frontend-neutral canonical owner.",
        LedgerCapabilityAxis.CLI: (
            "Operator or filing-route visibility is part of CLI parity."
            if applicable[LedgerCapabilityAxis.CLI]
            else "This is an internal backend composition, not a separately invocable CLI product."
        ),
        LedgerCapabilityAxis.TUI: (
            "The Ledger workbench must expose or faithfully summarize this operator capability."
            if applicable[LedgerCapabilityAxis.TUI]
            else "This internal backend composition is consumed through a higher-level TUI capability."
        ),
        LedgerCapabilityAxis.COMPOSITION: (
            "The behavior crosses state, provider, artifact, or registry boundaries."
            if applicable[LedgerCapabilityAxis.COMPOSITION]
            else "The query has no independent cross-boundary effect beyond its canonical read."
        ),
        LedgerCapabilityAxis.ARTIFACT: (
            "The capability emits or consumes an independently readable artifact."
            if applicable[LedgerCapabilityAxis.ARTIFACT]
            else "The capability has no independent file or archive product."
        ),
        LedgerCapabilityAxis.PROVENANCE: (
            "The effect must retain actor, source, revision, or route lineage."
            if applicable[LedgerCapabilityAxis.PROVENANCE]
            else "The read-only projection does not author independent provenance."
        ),
        LedgerCapabilityAxis.REGISTRY: (
            "The behavior resolves or presents a validated registry route."
            if applicable[LedgerCapabilityAxis.REGISTRY]
            else "The behavior does not consume a calculation-registry relationship directly."
        ),
        LedgerCapabilityAxis.PROOF: "Every admitted denominator row requires direct outcome and refusal evidence.",
    }
    proof_requirements = {
        LedgerCapabilityAxis.BACKEND: "Direct canonical-owner success and typed-refusal behavior evidence.",
        LedgerCapabilityAxis.CLI: "Live parser, delegation, result-schema, success, and refusal parity evidence.",
        LedgerCapabilityAxis.TUI: "Installed keyboard reachability plus canonical result and refusal parity evidence.",
        LedgerCapabilityAxis.COMPOSITION: "Real-boundary success, refusal, rollback, and fault behavior evidence.",
        LedgerCapabilityAxis.ARTIFACT: (
            "Independent readability, format/refusal, digest, destination, and custody/cleanup evidence."
        ),
        LedgerCapabilityAxis.PROVENANCE: (
            "Actor, source, operation, field, normalization, revision, and custody lineage evidence."
        ),
        LedgerCapabilityAxis.REGISTRY: (
            "Nonzero inclusion, exclusion, missing-versus-zero, and finish-line refusal evidence."
        ),
        LedgerCapabilityAxis.PROOF: "Current role-scoped evidence for every applicable operational claim.",
    }
    return tuple(
        LedgerAxisApplicabilityDecisionV1(
            axis=axis,
            applicability=ApplicabilityState.APPLICABLE if applicable[axis] else ApplicabilityState.NOT_APPLICABLE,
            rationale=rationales[axis],
            proof=AxisProofState.UNPROVEN if applicable[axis] else AxisProofState.NOT_APPLICABLE,
            proof_requirement=(
                proof_requirements[axis]
                if applicable[axis]
                else "No independent proof obligation applies because this axis is not applicable."
            ),
        )
        for axis in sorted(LedgerCapabilityAxis, key=lambda item: item.value)
    )


_PRIMARY_GAP_PRIORITY: Final[tuple[LedgerGapClass, ...]] = (
    LedgerGapClass.AUTHORITY,
    LedgerGapClass.REGISTRY,
    LedgerGapClass.PRODUCT,
    LedgerGapClass.ARTIFACT,
    LedgerGapClass.PROVENANCE,
    LedgerGapClass.COMPOSITION,
    LedgerGapClass.REACHABILITY,
    LedgerGapClass.PROOF,
)


class _ReviewedUnionRowFields(TypedDict):
    applicability: tuple[LedgerAxisApplicabilityDecisionV1, ...]
    gap_classes: frozenset[LedgerGapClass]
    primary_gap_class: LedgerGapClass
    secondary_gap_classes: tuple[LedgerGapClass, ...]
    proof_requirements: tuple[str, ...]
    blockers: tuple[str, ...]
    next_action: str
    registry_destination_status: LedgerRegistryDestinationStatus
    review_ruling: LedgerUnionRowReviewRuling


def _registry_destination_status(
    effect: LedgerCapabilityEffect,
    registry_row: LedgerRegistryRouteRowV1 | None,
) -> LedgerRegistryDestinationStatus:
    if effect is not LedgerCapabilityEffect.REGISTRY_ROUTE:
        if registry_row is not None:
            raise ValueError("a non-registry row cannot carry a registry declaration")
        return LedgerRegistryDestinationStatus.NOT_APPLICABLE
    if registry_row is None:
        raise ValueError("a registry row requires its exact declaration")
    if registry_row.targets:
        return LedgerRegistryDestinationStatus.DIRECT
    if registry_row.modelo_id == "210" or "retenciones" in registry_row.binding_id:
        return LedgerRegistryDestinationStatus.APPLICATION_SIDECAR
    return LedgerRegistryDestinationStatus.DESTINATIONLESS


def _reviewed_union_row_fields(
    *,
    capability_id: str,
    sources: frozenset[DenominatorSourceKind],
    semantic_home: CanonicalSemanticHomeV1,
    home_status: SemanticHomeStatus,
    effect: LedgerCapabilityEffect,
    tui_routes: tuple[str, ...],
    tui_reachability: Mapping[str, str],
    cli_ownership: frozenset[str],
    registry_row: LedgerRegistryRouteRowV1 | None,
) -> _ReviewedUnionRowFields:
    """Return the complete reproducible result of the exhaustive row review."""
    gaps = {LedgerGapClass.PROOF}
    if cli_ownership & {"mixed", "policy-bearing"}:
        gaps.add(LedgerGapClass.AUTHORITY)
    if home_status is SemanticHomeStatus.PLANNED:
        gaps.add(LedgerGapClass.PRODUCT)
    if effect in {
        LedgerCapabilityEffect.MUTATION,
        LedgerCapabilityEffect.PROPOSAL,
        LedgerCapabilityEffect.REGISTRY_ROUTE,
    }:
        gaps.add(LedgerGapClass.COMPOSITION)
    if (
        effect in {LedgerCapabilityEffect.ARTIFACT, LedgerCapabilityEffect.ARTIFACT_QUERY}
        or capability_id in _artifact_input_capabilities()
    ):
        gaps.add(LedgerGapClass.ARTIFACT)
    if effect is LedgerCapabilityEffect.REGISTRY_ROUTE:
        gaps.add(LedgerGapClass.REGISTRY)
    if (
        capability_id
        in {
            "ledger.evidence.download",
            "ledger.export.provenance",
            "ledger.field_change.provenance",
            "ledger.fx.provenance",
            "ledger.import.normalization_provenance",
            "ledger.manual_override.provenance",
            "ledger.llm.apply",
            "ledger.llm.apply_evidence_classification",
            "ledger.llm.apply_saturated",
            "ledger.llm.apply_split",
            "ledger.llm.classify_with_evidence",
            "ledger.llm.reject",
            "ledger.llm.review_decision",
            "ledger.llm.saturate",
            "ledger.llm.suggest",
            "ledger.llm.suggest_split",
        }
        or effect is LedgerCapabilityEffect.REGISTRY_ROUTE
    ):
        gaps.add(LedgerGapClass.PROVENANCE)
    component_only_routes = tuple(route for route in tui_routes if tui_reachability[route] == "component_only")
    if component_only_routes:
        gaps.add(LedgerGapClass.REACHABILITY)

    applicability = _axis_decisions(capability_id, sources, effect)
    proof_requirements = tuple(
        decision.proof_requirement
        for decision in applicability
        if decision.applicability is ApplicabilityState.APPLICABLE
    )
    blockers = ["Every applicable axis remains explicitly unproven in the reviewed baseline."]
    if LedgerGapClass.AUTHORITY in gaps:
        blockers.append("The current CLI observation carries policy-bearing or mixed ownership.")
    if home_status is SemanticHomeStatus.PLANNED:
        blockers.append("The named immutable application request/result contract is not yet implemented.")
    if component_only_routes:
        blockers.append("A TUI component exists without installed navigation or executable door reachability.")
    if capability_id in _BACKEND_DIRECT_PROOF_GAPS:
        blockers.append("No direct symbol-level backend behavior test was located for this public operation.")
    if capability_id in _artifact_input_capabilities():
        blockers.append("The local artifact input lacks complete readability, refusal, digest, and custody proof.")

    destination_status = _registry_destination_status(effect, registry_row)
    if destination_status is LedgerRegistryDestinationStatus.DIRECT:
        blockers.append("The direct registry destination lacks complete calculation and filing/export route proof.")
    elif destination_status is LedgerRegistryDestinationStatus.APPLICATION_SIDECAR:
        blockers.append("The application sidecar output identity is not represented by a registry edge.")
    elif destination_status is LedgerRegistryDestinationStatus.DESTINATIONLESS:
        blockers.append("The declaration has no registry destination or application output mapping.")

    primary_gap = next(gap for gap in _PRIMARY_GAP_PRIORITY if gap in gaps)
    secondary_gaps = tuple(sorted(gaps - {primary_gap}, key=lambda item: item.value))
    if primary_gap is LedgerGapClass.AUTHORITY:
        next_action = f"Move policy to {semantic_home.owner}, prove direct behavior, and prove thin CLI delegation."
    elif destination_status is LedgerRegistryDestinationStatus.APPLICATION_SIDECAR:
        next_action = "Move the sidecar output identity into a validated registry route, then prove the full route."
    elif destination_status is LedgerRegistryDestinationStatus.DESTINATIONLESS:
        next_action = (
            "Assign a typed registry destination or an explicit non-applicable disposition that cannot suppress a fact."
        )
    elif destination_status is LedgerRegistryDestinationStatus.DIRECT:
        next_action = (
            "Prove nonzero calculation, exclusions, missing-versus-zero behavior, "
            "and finish-line refusal for this route."
        )
    elif primary_gap is LedgerGapClass.PRODUCT:
        next_action = (
            f"Implement {semantic_home.command_type} and {semantic_home.result_type}, then prove every applicable axis."
        )
    elif primary_gap is LedgerGapClass.ARTIFACT:
        next_action = (
            "Prove artifact readability, format refusal, digest handling, and custody cleanup for the local input."
            if capability_id in _artifact_input_capabilities()
            else "Prove the artifact with an independent reader, declared-loss contract, and cleanup behavior."
        )
    else:
        next_action = "Attach current role-scoped success and refusal evidence for every applicable axis."

    return {
        "applicability": applicability,
        "gap_classes": frozenset(gaps),
        "primary_gap_class": primary_gap,
        "secondary_gap_classes": secondary_gaps,
        "proof_requirements": proof_requirements,
        "blockers": tuple(blockers),
        "next_action": next_action,
        "registry_destination_status": destination_status,
        "review_ruling": LedgerUnionRowReviewRuling.COMPLETE_WITH_OPEN_GAPS,
    }


def _union_observations(
    registry: LedgerRegistryRouteCensusV1,
    tui: LedgerTuiSupportedSurfaceCensusV1,
) -> tuple[LedgerUnionSourceObservationV1, ...]:
    from cadrumo.entrypoints.cli._app_ledger_command_specs import LEDGER_CLI_COMMAND_CENSUS

    declared_missing = {item.capability_id for item in _LEDGER_MISSING_PRODUCT_DECLARATIONS}
    observed_missing = {
        capability_id
        for _observation_id, capability_ids in _LEDGER_MISSING_PRODUCT_OBSERVATIONS
        for capability_id in capability_ids
    }
    if declared_missing != observed_missing:
        raise ValueError("missing-product observations and semantic declarations disagree")
    for item in _LEDGER_BACKEND_OPERATION_DECLARATIONS:
        observation_id = f"backend_operation:{item.capability_id}"
        if _selection_for_observation(observation_id) != (item.capability_id,):
            raise ValueError(f"backend observation selection drifted: {observation_id}")
    for observation_id, capability_ids in _LEDGER_MISSING_PRODUCT_OBSERVATIONS:
        if _selection_for_observation(f"missing_product:{observation_id}") != capability_ids:
            raise ValueError(f"missing-product observation selection drifted: {observation_id}")
    for observation_id, capability_id in _LEDGER_ARTIFACT_OBSERVATIONS:
        if _selection_for_observation(f"artifact_product:{observation_id}") != (capability_id,):
            raise ValueError(f"artifact observation selection drifted: {observation_id}")
    observations: list[LedgerUnionSourceObservationV1] = []
    for entry in LEDGER_CLI_COMMAND_CENSUS:
        observation_id = f"cli_endpoint:{entry.command_key}"
        observations.append(
            LedgerUnionSourceObservationV1(
                source=DenominatorSourceKind.CLI_ENDPOINT,
                observation_id=observation_id,
                capability_ids=_selection_for_observation(observation_id),
            )
        )
        observations.extend(
            LedgerUnionSourceObservationV1(
                source=DenominatorSourceKind.CLI_SUBOPERATION,
                observation_id=f"cli_suboperation:{suboperation_id}",
                capability_ids=_selection_for_observation(f"cli_suboperation:{suboperation_id}"),
            )
            for suboperation_id in entry.suboperation_ids
        )
    observations.extend(
        LedgerUnionSourceObservationV1(
            source=DenominatorSourceKind.BACKEND_ONLY,
            observation_id=f"backend_operation:{item.capability_id}",
            capability_ids=_selection_for_observation(f"backend_operation:{item.capability_id}"),
        )
        for item in _LEDGER_BACKEND_OPERATION_DECLARATIONS
    )
    observations.extend(
        LedgerUnionSourceObservationV1(
            source=DenominatorSourceKind.MISSING_PRODUCT,
            observation_id=f"missing_product:{observation_id}",
            capability_ids=_selection_for_observation(f"missing_product:{observation_id}"),
        )
        for observation_id, _capability_ids in _LEDGER_MISSING_PRODUCT_OBSERVATIONS
    )
    observations.extend(
        LedgerUnionSourceObservationV1(
            source=DenominatorSourceKind.REGISTRY_ROUTE,
            observation_id="registry_route:" + "|".join(map(str, row.sort_key)),
            capability_ids=(_registry_union_capability_id(row),),
        )
        for row in registry.rows
    )
    observations.extend(
        LedgerUnionSourceObservationV1(
            source=DenominatorSourceKind.ARTIFACT_PRODUCT,
            observation_id=f"artifact_product:{observation_id}",
            capability_ids=_selection_for_observation(f"artifact_product:{observation_id}"),
        )
        for observation_id, _capability_id in _LEDGER_ARTIFACT_OBSERVATIONS
    )
    route_rows = {row.destination: row for row in tui.routes}
    if set(route_rows) != set(_LEDGER_TUI_ROUTE_OBSERVATION_CAPABILITIES):
        raise ValueError("the TUI route-to-capability adjudication is stale")
    for destination, capability_ids in _LEDGER_TUI_ROUTE_OBSERVATION_CAPABILITIES.items():
        observation_id = f"supported_surface:{destination}:{route_rows[destination].reachability}"
        if _selection_for_observation(observation_id) != capability_ids:
            raise ValueError(f"TUI observation selection drifted: {observation_id}")
    observations.extend(
        LedgerUnionSourceObservationV1(
            source=DenominatorSourceKind.SUPPORTED_SURFACE,
            observation_id=f"supported_surface:{destination}:{route_rows[destination].reachability}",
            capability_ids=_selection_for_observation(
                f"supported_surface:{destination}:{route_rows[destination].reachability}"
            ),
        )
        for destination, _capability_ids in _LEDGER_TUI_ROUTE_OBSERVATION_CAPABILITIES.items()
    )
    canonical = tuple(sorted(observations, key=lambda item: (item.source.value, item.observation_id)))
    _validate_non_registry_observation_adjudication(canonical)
    _validate_registry_observation_projection(registry, canonical)
    return canonical


def _backend_operation_source_set_digest() -> str:
    root = Path(__file__).resolve().parents[2]
    payload = bytearray(b"cadrumo:ledger-backend-operation-source-set:v1\x00")
    for relative in _LEDGER_BACKEND_OPERATION_SOURCE_PATHS:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Ledger backend census source is unavailable: {relative}")
        payload.extend(_length_frame(relative.encode("utf-8")))
        payload.extend(_length_frame(path.read_bytes()))
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _union_source_digest(
    source: DenominatorSourceKind,
    observations: tuple[LedgerUnionSourceObservationV1, ...],
    registry: LedgerRegistryRouteCensusV1,
    tui: LedgerTuiSupportedSurfaceCensusV1,
) -> str:
    from cadrumo.entrypoints.cli._app_ledger_command_specs import LEDGER_CLI_COMMAND_CENSUS

    material: object = observations
    if source in {DenominatorSourceKind.CLI_ENDPOINT, DenominatorSourceKind.CLI_SUBOPERATION}:
        material = {
            "observations": observations,
            "command_census": tuple(
                {
                    "command_key": entry.command_key,
                    "path": entry.path,
                    "handler_identity": entry.handler_identity,
                    "result_schema_identity": entry.result_schema_identity,
                    "tui_capability": entry.tui_capability.value,
                    "adapter_ownership": entry.adapter_ownership.value,
                    "suboperation_ids": entry.suboperation_ids,
                }
                for entry in LEDGER_CLI_COMMAND_CENSUS
            ),
        }
    elif source is DenominatorSourceKind.BACKEND_ONLY:
        material = {
            "observations": observations,
            "declarations": tuple(
                {
                    "capability_id": item.capability_id,
                    "owner": item.owner,
                    "command_type": item.command_type,
                    "result_type": item.result_type,
                    "status": item.status.value,
                }
                for item in _LEDGER_BACKEND_OPERATION_DECLARATIONS
            ),
            "source_set_digest": _backend_operation_source_set_digest(),
        }
    elif source is DenominatorSourceKind.REGISTRY_ROUTE:
        material = {"observations": observations, "route_census_digest": registry.calculated_digest}
    elif source is DenominatorSourceKind.SUPPORTED_SURFACE:
        material = {"observations": observations, "surface_census_digest": tui.calculated_digest}
    return _canonical_digest(material)


def build_ledger_union_denominator(
    *,
    registry: LedgerRegistryRouteCensusV1 | None = None,
    tui: LedgerTuiSupportedSurfaceCensusV1 | None = None,
) -> LedgerUnionDenominatorV1:
    """Join all seven accepted S04--S07 streams into the S08 semantic union."""
    registry = build_ledger_registry_route_census() if registry is None else registry
    tui = build_ledger_tui_supported_surface_census() if tui is None else tui
    _validate_required_public_backend_operations()
    for declaration in _LEDGER_BACKEND_OPERATION_DECLARATIONS:
        _validate_existing_semantic_home(declaration)
    _artifact_input_capabilities()
    observations = _union_observations(registry, tui)
    effect_groups = (
        _EXPLICIT_QUERY_CAPABILITIES,
        _EXPLICIT_PROPOSAL_CAPABILITIES,
        _EXPLICIT_ARTIFACT_CAPABILITIES,
        _EXPLICIT_ARTIFACT_QUERY_CAPABILITIES,
        _EXPLICIT_MUTATION_CAPABILITIES,
    )
    if sum(map(len, effect_groups)) != len(_EXPLICIT_EFFECTS):
        raise ValueError("a non-registry capability has conflicting explicit effect decisions")
    _validate_non_registry_decision_coverage(observations)
    observations_by_capability: dict[str, list[LedgerUnionSourceObservationV1]] = {}
    for observation in observations:
        for capability_id in observation.capability_ids:
            observations_by_capability.setdefault(capability_id, []).append(observation)
    tui_reachability = {row.destination: row.reachability for row in tui.routes}
    _validate_tui_route_adjudication(
        _EXPLICIT_TUI_ROUTE_ADJUDICATION,
        known_routes=frozenset(tui_reachability),
    )
    registry_rows_by_capability = {_registry_union_capability_id(row): row for row in registry.rows}
    cli_ownership_by_capability: dict[str, set[str]] = {}
    from cadrumo.entrypoints.cli._app_ledger_command_specs import LEDGER_CLI_COMMAND_CENSUS

    for entry in LEDGER_CLI_COMMAND_CENSUS:
        for capability_id in _selection_for_observation(f"cli_endpoint:{entry.command_key}"):
            cli_ownership_by_capability.setdefault(capability_id, set()).add(entry.adapter_ownership.value)
        for suboperation_id in entry.suboperation_ids:
            for mapped in _selection_for_observation(f"cli_suboperation:{suboperation_id}"):
                cli_ownership_by_capability.setdefault(mapped, set()).add(entry.adapter_ownership.value)
    rows: list[LedgerUnionCapabilityRowV1] = []
    for capability_id, selecting in sorted(observations_by_capability.items()):
        sources = frozenset(item.source for item in selecting)
        effect = _effect_for(capability_id, sources)
        semantic_home, home_status = _semantic_home_for(capability_id, effect)
        tui_routes = _tui_routes_for(capability_id, effect)
        applicability = _axis_decisions(capability_id, sources, effect)
        reviewed_fields = _reviewed_union_row_fields(
            capability_id=capability_id,
            sources=sources,
            semantic_home=semantic_home,
            home_status=home_status,
            effect=effect,
            tui_routes=tui_routes,
            tui_reachability=tui_reachability,
            cli_ownership=frozenset(cli_ownership_by_capability.get(capability_id, set())),
            registry_row=registry_rows_by_capability.get(capability_id),
        )
        provisional_row = LedgerUnionCapabilityRowV1.model_construct(
            capability_id=capability_id,
            sources=sources,
            source_observation_ids=tuple(sorted(item.observation_id for item in selecting)),
            semantic_home=semantic_home,
            semantic_home_status=home_status,
            effect=effect,
            tui_routes=tui_routes,
            tui_hold_until=(
                LEDGER_TUI_HOLD_UNTIL_GATE
                if next(
                    decision.applicability is ApplicabilityState.APPLICABLE
                    for decision in applicability
                    if decision.axis is LedgerCapabilityAxis.TUI
                )
                else None
            ),
            review_digest="",
            **reviewed_fields,
        )
        rows.append(
            LedgerUnionCapabilityRowV1(
                **provisional_row.model_dump(mode="python", exclude={"review_digest"}),
                review_digest=provisional_row.calculated_review_digest,
            )
        )
    source_digests = tuple(
        LedgerUnionSourceDigestV1(
            source=source,
            observation_count=len(source_observations),
            digest=_union_source_digest(source, source_observations, registry, tui),
        )
        for source in sorted(DenominatorSourceKind, key=lambda item: item.value)
        if (source_observations := tuple(item for item in observations if item.source is source))
    )
    reviewed_row_count = len(rows)
    row_review_digest = _canonical_digest(tuple((row.capability_id, row.review_digest) for row in rows))
    placeholder_attestation = LedgerUnionRowReviewAttestationV1.model_construct(
        review_id="review.ledger.union_rows",
        reviewer="engineering-row-review",
        reviewed_at=_LEDGER_UNION_ROW_REVIEWED_AT,
        ruling=LedgerUnionRowReviewRuling.COMPLETE_WITH_OPEN_GAPS,
        reviewed_union_basis_digest="sha256:" + "0" * 64,
        row_review_digest=row_review_digest,
        reviewed_row_count=reviewed_row_count,
        digest="sha256:" + "0" * 64,
    )
    provisional = LedgerUnionDenominatorV1.model_construct(
        root=LEDGER_UNION_DENOMINATOR_ROOT,
        schema_version=LEDGER_UNION_DENOMINATOR_SCHEMA_VERSION,
        registry_census=registry,
        tui_census=tui,
        source_digests=source_digests,
        observations=observations,
        rows=tuple(rows),
        selection_accounting=LedgerUnionSelectionAccountingV1(
            observation_count=len(observations),
            selected_edges=sum(len(item.capability_ids) for item in observations),
            one_to_many_observations=sum(len(item.capability_ids) > 1 for item in observations),
            one_to_many_extra_edges=sum(len(item.capability_ids) - 1 for item in observations),
            multi_observation_rows=sum(len(row.source_observation_ids) > 1 for row in rows),
            duplicate_selection_edges=sum(len(item.capability_ids) for item in observations) - len(rows),
            final_rows=len(rows),
        ),
        review_revision="row-review-v1",
        reviewed_row_count=reviewed_row_count,
        row_review_digest=row_review_digest,
        row_review_attestation=placeholder_attestation,
        digest="",
    )
    provisional_attestation = LedgerUnionRowReviewAttestationV1.model_construct(
        review_id="review.ledger.union_rows",
        reviewer="engineering-row-review",
        reviewed_at=_LEDGER_UNION_ROW_REVIEWED_AT,
        ruling=LedgerUnionRowReviewRuling.COMPLETE_WITH_OPEN_GAPS,
        reviewed_union_basis_digest=provisional.calculated_review_basis_digest,
        row_review_digest=row_review_digest,
        reviewed_row_count=reviewed_row_count,
        digest="",
    )
    attestation = LedgerUnionRowReviewAttestationV1(
        **provisional_attestation.model_dump(mode="python", exclude={"digest"}),
        digest=provisional_attestation.calculated_digest,
    )
    provisional = provisional.model_copy(update={"row_review_attestation": attestation})
    return LedgerUnionDenominatorV1(
        **provisional.model_dump(mode="python", exclude={"digest"}), digest=provisional.calculated_digest
    )


def ledger_union_denominator_bytes(union: LedgerUnionDenominatorV1) -> bytes:
    """Serialize the canonical S08 union with domain and length framing."""
    canonical = LedgerUnionDenominatorV1.model_validate(union.model_dump(mode="python"))
    encoded = _canonical_json_text(_ledger_union_digest_payload(canonical)).encode("utf-8")
    return _LEDGER_UNION_DENOMINATOR_FRAME + _length_frame(encoded)


def ledger_union_denominator_digest(union: LedgerUnionDenominatorV1) -> str:
    """Return the framed serialized S08 union digest."""
    return f"sha256:{hashlib.sha256(ledger_union_denominator_bytes(union)).hexdigest()}"


class EvidenceSubjectSnapshotV1(BaseModel):
    """A current, independently observed subject used to freshness-check evidence."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    subject_id: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    digest: str = Field(min_length=1)
    observed_at: datetime

    @model_validator(mode="after")
    def _check_snapshot(self) -> EvidenceSubjectSnapshotV1:
        _require_identity(self.subject_id, field_name="subject_id", pattern=_SUBJECT_ID_PATTERN)
        _require_non_placeholder(self.locator, field_name="locator")
        _require_non_placeholder(self.revision, field_name="revision")
        _require_digest(self.digest, field_name="digest")
        _require_observed_at(self.observed_at, field_name="observed_at")
        return self


class EvidenceCoordinateV1(BaseModel):
    """A role-bound evidence claim tied to one exact current subject snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1)
    kind: EvidenceKind
    role: EvidenceRole
    axes: frozenset[LedgerCapabilityAxis] = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    subject_revision: str = Field(min_length=1)
    subject_digest: str = Field(min_length=1)
    observed_at: datetime
    locator: str = Field(min_length=1)
    claim: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_role_contract(self) -> EvidenceCoordinateV1:
        _require_identity(self.evidence_id, field_name="evidence_id", pattern=_EVIDENCE_ID_PATTERN)
        _require_identity(self.subject_id, field_name="subject_id", pattern=_SUBJECT_ID_PATTERN)
        _require_non_placeholder(self.subject_revision, field_name="subject_revision")
        _require_digest(self.subject_digest, field_name="subject_digest")
        _require_observed_at(self.observed_at, field_name="observed_at")
        _require_non_placeholder(self.locator, field_name="locator")
        _require_non_placeholder(self.claim, field_name="claim")
        contract = _EVIDENCE_ROLE_CONTRACTS[self.role]
        if self.kind not in contract.kinds:
            raise ValueError(f"{self.role.value} evidence has an invalid kind: {self.kind.value}")
        if contract.axes is not None and self.axes != contract.axes:
            raise ValueError(
                f"{self.role.value} evidence must prove exactly {sorted(axis.value for axis in contract.axes)}"
            )
        if contract.single_axis and len(self.axes) != 1:
            raise ValueError(f"{self.role.value} evidence must name exactly one axis")
        return self

    def is_current_against(self, subject: EvidenceSubjectSnapshotV1) -> bool:
        """Return whether this claim matches the exact current subject snapshot."""
        return (
            self.subject_id == subject.subject_id
            and self.subject_revision == subject.revision
            and self.subject_digest == subject.digest
            and self.observed_at == subject.observed_at
            and self.locator == subject.locator
        )


class DenominatorEntryV1(BaseModel):
    """One identity in the complete union census and each selecting source stream."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    capability_id: str = Field(min_length=1)
    sources: frozenset[DenominatorSourceKind] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_entry(self) -> DenominatorEntryV1:
        _require_identity(self.capability_id, field_name="capability_id", pattern=_CAPABILITY_ID_PATTERN)
        return self


class CensusStreamObservationV1(BaseModel):
    """One independently readable mandatory source stream in a live census."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    source: DenominatorSourceKind
    revision: str = Field(min_length=1)
    observed_at: datetime
    scan_succeeded: bool
    readable: bool
    complete: bool
    ambiguous: bool
    reviewed_zero: bool
    capability_ids: tuple[str, ...] = ()
    digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_stream(self) -> CensusStreamObservationV1:
        _require_non_placeholder(self.revision, field_name="revision")
        _require_observed_at(self.observed_at, field_name="observed_at")
        identities = self.capability_ids
        if len(set(identities)) != len(identities):
            raise ValueError(f"{self.source.value} census stream has duplicate capability identities")
        for capability_id in identities:
            _require_identity(capability_id, field_name="capability_id", pattern=_CAPABILITY_ID_PATTERN)
        if identities and self.reviewed_zero:
            raise ValueError("a nonempty census stream cannot be declared reviewed zero")
        if not identities and not self.reviewed_zero:
            raise ValueError("an empty census stream requires an explicit reviewed zero")
        _require_digest(self.digest, field_name="digest")
        if self.digest != self.calculated_digest:
            raise ValueError(f"{self.source.value} census stream digest does not match its observation")
        return self

    @property
    def calculated_digest(self) -> str:
        """Return the canonical digest of every scan result and declared zero."""
        return _canonical_digest(
            {
                "source": self.source,
                "revision": self.revision,
                "observed_at": self.observed_at,
                "scan_succeeded": self.scan_succeeded,
                "readable": self.readable,
                "complete": self.complete,
                "ambiguous": self.ambiguous,
                "reviewed_zero": self.reviewed_zero,
                "capability_ids": tuple(sorted(self.capability_ids)),
            }
        )

    @property
    def readiness_errors(self) -> tuple[str, ...]:
        """Return fail-closed diagnostics for an unavailable source stream."""
        errors: list[str] = []
        if not self.scan_succeeded:
            errors.append(f"{self.source.value} census stream did not scan successfully")
        if not self.readable:
            errors.append(f"{self.source.value} census stream is unreadable")
        if not self.complete:
            errors.append(f"{self.source.value} census stream is partial")
        if self.ambiguous:
            errors.append(f"{self.source.value} census stream is ambiguous")
        return tuple(errors)


class LedgerLiveCensusReportV1(BaseModel):
    """A complete external observation of every denominator source stream."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    census_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    observed_at: datetime
    streams: tuple[CensusStreamObservationV1, ...]
    digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_report(self) -> LedgerLiveCensusReportV1:
        _require_identity(self.census_id, field_name="census_id", pattern=_CENSUS_ID_PATTERN)
        _require_non_placeholder(self.revision, field_name="revision")
        _require_observed_at(self.observed_at, field_name="observed_at")
        sources = tuple(stream.source for stream in self.streams)
        if len(set(sources)) != len(sources) or frozenset(sources) != frozenset(DenominatorSourceKind):
            raise ValueError("a live census report must account for every mandatory source stream exactly once")
        if not self.capability_ids:
            raise ValueError("a complete live census report cannot be empty")
        _require_digest(self.digest, field_name="digest")
        if self.digest != self.calculated_digest:
            raise ValueError("live census report digest does not match its complete stream observations")
        return self

    @property
    def capability_ids(self) -> frozenset[str]:
        """Return the union of identities selected by all successful streams."""
        return frozenset(capability_id for stream in self.streams for capability_id in stream.capability_ids)

    @property
    def denominator_entries(self) -> tuple[DenominatorEntryV1, ...]:
        """Project source-stream observations into the complete union denominator."""
        sources_by_capability: dict[str, set[DenominatorSourceKind]] = {}
        for stream in self.streams:
            for capability_id in stream.capability_ids:
                sources_by_capability.setdefault(capability_id, set()).add(stream.source)
        return tuple(
            DenominatorEntryV1(capability_id=capability_id, sources=frozenset(sources))
            for capability_id, sources in sorted(sources_by_capability.items())
        )

    @property
    def calculated_digest(self) -> str:
        """Return the canonical digest of the full source-stream observation."""
        return _canonical_digest(
            {
                "census_id": self.census_id,
                "revision": self.revision,
                "observed_at": self.observed_at,
                "streams": tuple(sorted(self.streams, key=lambda stream: stream.source.value)),
            }
        )

    @property
    def readiness_errors(self) -> tuple[str, ...]:
        """Return the complete fail-closed diagnostics for this live census."""
        errors = [error for stream in self.streams for error in stream.readiness_errors]
        if not self.capability_ids:
            errors.append("the complete live census report is empty")
        return tuple(errors)


class LedgerDenominatorSnapshotV1(BaseModel):
    """A digested and dated complete denominator snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    census_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    observed_at: datetime
    entries: tuple[DenominatorEntryV1, ...]
    source_report_digest: str = Field(min_length=1)
    source_report_revision: str = Field(min_length=1)
    source_report_observed_at: datetime
    digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_snapshot(self) -> LedgerDenominatorSnapshotV1:
        _require_identity(self.census_id, field_name="census_id", pattern=_CENSUS_ID_PATTERN)
        _require_non_placeholder(self.revision, field_name="revision")
        _require_observed_at(self.observed_at, field_name="observed_at")
        _require_digest(self.source_report_digest, field_name="source_report_digest")
        _require_non_placeholder(self.source_report_revision, field_name="source_report_revision")
        _require_observed_at(self.source_report_observed_at, field_name="source_report_observed_at")
        if not self.entries:
            raise ValueError("a denominator census cannot be content-free")
        identities = tuple(entry.capability_id for entry in self.entries)
        if len(set(identities)) != len(identities):
            raise ValueError("a denominator census contains duplicate capability identities")
        _require_digest(self.digest, field_name="digest")
        if self.digest != self.calculated_digest:
            raise ValueError("denominator digest does not match its complete observed entries")
        return self

    @property
    def capability_ids(self) -> frozenset[str]:
        """Return the stable identities selected by this census."""
        return frozenset(entry.capability_id for entry in self.entries)

    @property
    def calculated_digest(self) -> str:
        """Return the canonical digest of identities and source categories."""
        return _canonical_digest(
            {
                "census_id": self.census_id,
                "revision": self.revision,
                "observed_at": self.observed_at,
                "entries": tuple(sorted(self.entries, key=lambda entry: entry.capability_id)),
                "source_report_digest": self.source_report_digest,
                "source_report_revision": self.source_report_revision,
                "source_report_observed_at": self.source_report_observed_at,
            }
        )

    @classmethod
    def from_live_report(cls, report: LedgerLiveCensusReportV1) -> LedgerDenominatorSnapshotV1:
        """Freeze a denominator snapshot that remains bound to its live report."""
        provisional = cls.model_construct(
            census_id=report.census_id,
            revision=report.revision,
            observed_at=report.observed_at,
            entries=report.denominator_entries,
            source_report_digest=report.digest,
            source_report_revision=report.revision,
            source_report_observed_at=report.observed_at,
            digest="",
        )
        return cls(**provisional.model_dump(exclude={"digest"}), digest=provisional.calculated_digest)


class AxisAssessmentV1(BaseModel):
    """One per-axis reviewed applicability decision and independent proof state."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    axis: LedgerCapabilityAxis
    applicability: ApplicabilityState
    applicability_rationale: str = Field(min_length=1)
    applicability_review_evidence: EvidenceCoordinateV1
    proof: AxisProofState
    surface_state: SurfaceCapabilityState | None = None
    evidence: tuple[EvidenceCoordinateV1, ...] = ()

    @model_validator(mode="after")
    def _check_assessment(self) -> AxisAssessmentV1:
        _require_non_placeholder(self.applicability_rationale, field_name="applicability_rationale")
        review = self.applicability_review_evidence
        if review.role is not EvidenceRole.APPLICABILITY_REVIEW or review.axes != frozenset({self.axis}):
            raise ValueError("each axis requires its own applicability-review evidence")
        if self.axis in _SURFACE_AXES and self.surface_state is None:
            raise ValueError(f"{self.axis.value} requires a surface_state")
        if self.axis not in _SURFACE_AXES and self.surface_state is not None:
            raise ValueError(f"{self.axis.value} must not carry a surface_state")
        if self.applicability is ApplicabilityState.NOT_APPLICABLE:
            if self.proof is not AxisProofState.NOT_APPLICABLE or self.evidence:
                raise ValueError("a non-applicable axis has no operational proof or evidence")
            if self.surface_state not in {None, SurfaceCapabilityState.NOT_APPLICABLE}:
                raise ValueError("a non-applicable surface must have not_applicable state")
        else:
            if self.proof is AxisProofState.NOT_APPLICABLE:
                raise ValueError("an applicable axis requires unproven, partial, or proven proof")
            if self.surface_state is SurfaceCapabilityState.NOT_APPLICABLE:
                raise ValueError("an applicable surface cannot be not_applicable")
        if any(self.axis not in coordinate.axes for coordinate in self.evidence):
            raise ValueError("operational evidence must name the assessment axis")
        if any(coordinate.role is EvidenceRole.APPLICABILITY_REVIEW for coordinate in self.evidence):
            raise ValueError("applicability review evidence belongs in its dedicated coordinate")
        if len({coordinate.evidence_id for coordinate in self.evidence}) != len(self.evidence):
            raise ValueError("assessment has duplicate operational evidence identities")
        return self

    @property
    def needs_finding(self) -> bool:
        """Return whether an applicable incomplete state needs a closure finding."""
        return self.applicability is ApplicabilityState.APPLICABLE and (
            self.proof is not AxisProofState.PROVEN
            or self.surface_state in {SurfaceCapabilityState.ABSENT, SurfaceCapabilityState.PARTIAL}
        )


class CapabilityFindingV1(BaseModel):
    """An unresolved axis-scoped gap and its bounded next action."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    finding_id: str = Field(min_length=1)
    gap_class: LedgerGapClass
    affected_axes: frozenset[LedgerCapabilityAxis] = Field(min_length=1)
    description: str = Field(min_length=1)
    next_closure_action: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_finding(self) -> CapabilityFindingV1:
        _require_identity(self.finding_id, field_name="finding_id", pattern=_FINDING_ID_PATTERN)
        _require_non_placeholder(self.description, field_name="description")
        _require_non_placeholder(self.next_closure_action, field_name="next_closure_action")
        return self


class AuthorityMigrationHistoryV1(BaseModel):
    """Monotonic G1 ownership history; it cannot be erased after cutover."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    initial_cli_ownership: InitialCliOwnership
    migration_completed: bool


class AuthorityDispositionEntryV1(BaseModel):
    """The initial CLI authority fact for one stable denominator row."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    row_id: str = Field(min_length=1)
    initial_cli_ownership: InitialCliOwnership

    @model_validator(mode="after")
    def _check_entry(self) -> AuthorityDispositionEntryV1:
        _require_identity(self.row_id, field_name="row_id", pattern=_CAPABILITY_ID_PATTERN)
        return self


class AuthorityDispositionSnapshotV1(BaseModel):
    """Digested immutable initial-ownership dispositions across matrix revisions."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    census_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    observed_at: datetime
    entries: tuple[AuthorityDispositionEntryV1, ...]
    digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_snapshot(self) -> AuthorityDispositionSnapshotV1:
        _require_identity(self.census_id, field_name="census_id", pattern=_CENSUS_ID_PATTERN)
        _require_non_placeholder(self.revision, field_name="revision")
        _require_observed_at(self.observed_at, field_name="observed_at")
        row_ids = tuple(entry.row_id for entry in self.entries)
        if not row_ids or len(set(row_ids)) != len(row_ids):
            raise ValueError("authority disposition snapshots require unique nonempty row identities")
        _require_digest(self.digest, field_name="digest")
        if self.digest != self.calculated_digest:
            raise ValueError("authority disposition snapshot digest does not match its entries")
        return self

    @property
    def dispositions(self) -> Mapping[str, InitialCliOwnership]:
        """Return initial ownership keyed by stable row identity."""
        return {entry.row_id: entry.initial_cli_ownership for entry in self.entries}

    @property
    def calculated_digest(self) -> str:
        """Return the canonical digest of immutable initial ownership facts."""
        return _canonical_digest(
            {
                "census_id": self.census_id,
                "revision": self.revision,
                "observed_at": self.observed_at,
                "entries": tuple(sorted(self.entries, key=lambda entry: entry.row_id)),
            }
        )


class LedgerCapabilityRowV1(BaseModel):
    """One complete reviewed row bound to the union denominator."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    identity: LedgerCapabilityIdentityV1
    semantic_home: CanonicalSemanticHomeV1
    assessments: tuple[AxisAssessmentV1, ...]
    annotations: frozenset[CapabilityAnnotation] = frozenset()
    findings: tuple[CapabilityFindingV1, ...] = ()
    authority_migration: AuthorityMigrationHistoryV1
    cli_delegates_to_canonical: bool
    tui_hold_until: LedgerGate | None = None

    @model_validator(mode="after")
    def _check_complete_row(self) -> LedgerCapabilityRowV1:
        has_all_axes = frozenset(assessment.axis for assessment in self.assessments) == _ALL_AXES
        if not has_all_axes or len(self.assessments) != len(_ALL_AXES):
            raise ValueError("rows require exactly one reviewed assessment for every axis")
        if not any(assessment.applicability is ApplicabilityState.APPLICABLE for assessment in self.assessments):
            raise ValueError("a capability row cannot be content-free or all not_applicable")
        if len({finding.finding_id for finding in self.findings}) != len(self.findings):
            raise ValueError("rows contain duplicate finding identities")
        for assessment in self.assessments:
            if assessment.needs_finding and not any(
                assessment.axis in finding.affected_axes for finding in self.findings
            ):
                raise ValueError(f"{assessment.axis.value} is unresolved but has no affected-axis finding")
        cli = self.assessment(LedgerCapabilityAxis.CLI)
        tui = self.assessment(LedgerCapabilityAxis.TUI)
        if self.cli_delegates_to_canonical != (CapabilityAnnotation.DELEGATING in self.annotations):
            raise ValueError("cli_delegates_to_canonical must exactly match delegating")
        if CapabilityAnnotation.CLI_OWNED in self.annotations and (
            cli.applicability is not ApplicabilityState.APPLICABLE or self.cli_delegates_to_canonical
        ):
            raise ValueError("cli_owned requires applicable non-delegating CLI")
        if self.cli_delegates_to_canonical and cli.applicability is not ApplicabilityState.APPLICABLE:
            raise ValueError("delegating requires applicable CLI")
        history = self.authority_migration
        if history.initial_cli_ownership is InitialCliOwnership.CLI_OWNED:
            if history.migration_completed != self.cli_delegates_to_canonical:
                raise ValueError("CLI-owned rows require matching migration and delegation state")
            if not history.migration_completed and CapabilityAnnotation.CLI_OWNED not in self.annotations:
                raise ValueError("uncut CLI-owned rows retain cli_owned")
            if not history.migration_completed and not any(
                finding.gap_class is LedgerGapClass.AUTHORITY and LedgerCapabilityAxis.CLI in finding.affected_axes
                for finding in self.findings
            ):
                raise ValueError(
                    "an incomplete CLI-owned migration requires an authority finding and next closure action"
                )
        elif CapabilityAnnotation.CLI_OWNED in self.annotations:
            raise ValueError("cli_owned contradicts immutable initial ownership")
        if (
            CapabilityAnnotation.COMPONENT_ONLY in self.annotations
            and tui.applicability is not ApplicabilityState.APPLICABLE
        ):
            raise ValueError("component_only requires applicable TUI")
        if (
            CapabilityAnnotation.INSTALLED in self.annotations
            and tui.applicability is not ApplicabilityState.APPLICABLE
        ):
            raise ValueError("installed requires applicable TUI")
        if (
            CapabilityAnnotation.COMPONENT_ONLY in self.annotations
            and CapabilityAnnotation.INSTALLED in self.annotations
        ):
            raise ValueError("a TUI capability cannot be component_only and installed")
        expected_tui_hold = LEDGER_TUI_HOLD_UNTIL_GATE if tui.applicability is ApplicabilityState.APPLICABLE else None
        if self.tui_hold_until is not expected_tui_hold:
            state = "applicable" if tui.applicability is ApplicabilityState.APPLICABLE else "not_applicable"
            raise ValueError(
                f"matrix row TUI hold must be {LEDGER_TUI_HOLD_UNTIL_GATE.value} for {state} TUI and absent otherwise"
            )
        return self

    def assessment(self, axis: LedgerCapabilityAxis) -> AxisAssessmentV1:
        """Return the one validated assessment for an axis."""
        return next(assessment for assessment in self.assessments if assessment.axis is axis)

    def evidence_with_role(self, role: EvidenceRole, *, axis: LedgerCapabilityAxis | None = None) -> bool:
        """Return whether the row has an operational coordinate of a role."""
        assessments: Iterable[AxisAssessmentV1] = self.assessments if axis is None else (self.assessment(axis),)
        return any(coordinate.role is role for assessment in assessments for coordinate in assessment.evidence)

    def has_gap(self, gap_class: LedgerGapClass, *, axis: LedgerCapabilityAxis | None = None) -> bool:
        """Return whether a gap class affects the optional requested axis."""
        return any(
            finding.gap_class is gap_class and (axis is None or axis in finding.affected_axes)
            for finding in self.findings
        )


class LedgerCampaignControlsV1(BaseModel):
    """Singular-plan ownership and TUI-hold facts required by gate ordering."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    sole_ledger_parity_plan_owner: str = Field(min_length=1)
    tui_implementation_hold_recorded: bool
    tui_implementation_hold_active: bool

    @model_validator(mode="after")
    def _check_owner(self) -> LedgerCampaignControlsV1:
        if self.sole_ledger_parity_plan_owner != ACCEPTED_LEDGER_PARITY_PLAN_OWNER:
            raise ValueError("sole_ledger_parity_plan_owner must be the accepted clitui-ledger plan identity")
        return self


class LedgerMatrixAcceptanceAttestationV1(BaseModel):
    """An independent ACCEPT ruling for one exact frozen matrix state."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    attestation_id: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    ruling: ReviewRuling
    plan_owner: str = Field(min_length=1)
    matrix_digest: str = Field(min_length=1)
    denominator_digest: str = Field(min_length=1)
    denominator_revision: str = Field(min_length=1)
    union_review: LedgerUnionReviewSnapshotV1
    review_subject_id: str = Field(min_length=1)
    review_subject_revision: str = Field(min_length=1)
    review_subject_digest: str = Field(min_length=1)
    review_subject_observed_at: datetime
    attested_at: datetime
    closure_receipt_set_digest: str | None = None

    @model_validator(mode="after")
    def _check_attestation(self) -> LedgerMatrixAcceptanceAttestationV1:
        _require_identity(self.attestation_id, field_name="attestation_id", pattern=_ATTESTATION_ID_PATTERN)
        _require_non_placeholder(self.reviewer, field_name="reviewer")
        if self.plan_owner != ACCEPTED_LEDGER_PARITY_PLAN_OWNER:
            raise ValueError("acceptance attestation must name the accepted clitui-ledger plan identity")
        _require_digest(self.matrix_digest, field_name="matrix_digest")
        _require_digest(self.denominator_digest, field_name="denominator_digest")
        _require_non_placeholder(self.denominator_revision, field_name="denominator_revision")
        _require_identity(self.review_subject_id, field_name="review_subject_id", pattern=_SUBJECT_ID_PATTERN)
        _require_non_placeholder(self.review_subject_revision, field_name="review_subject_revision")
        _require_digest(self.review_subject_digest, field_name="review_subject_digest")
        _require_observed_at(self.review_subject_observed_at, field_name="review_subject_observed_at")
        _require_observed_at(self.attested_at, field_name="attested_at")
        if self.closure_receipt_set_digest is not None:
            _require_digest(self.closure_receipt_set_digest, field_name="closure_receipt_set_digest")
        return self

    @property
    def calculated_digest(self) -> str:
        """Hash every independently reviewed assertion without a self-reference."""
        return _canonical_digest(self)


def ledger_gate_closure_receipt_id(gate: LedgerGate) -> str:
    """Return the sole accepted receipt identity for one pre-TUI gate."""
    if gate not in _GATE_ORDER[:-1]:
        raise ValueError("only G0 through G3 have gate closure receipt identities")
    return f"receipt.ledger.{gate.value}"


class LedgerGateClosureReceiptV1(BaseModel):
    """An independently accepted, current closure of one ordered pre-TUI gate.

    The receipt binds the gate-relevant matrix projection, rather than the full
    matrix digest, so the one authorized transition from an active to inactive
    TUI hold does not erase accepted G0--G3 history.  Every other matrix change
    remains part of the projection and invalidates the receipt.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    receipt_id: str = Field(min_length=1)
    gate: LedgerGate
    matrix_closure_basis_digest: str = Field(min_length=1)
    acceptance_attestation_digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_receipt(self) -> LedgerGateClosureReceiptV1:
        if self.gate not in _GATE_ORDER[:-1]:
            raise ValueError("gate closure receipts are limited to G0 through G3")
        if self.receipt_id != ledger_gate_closure_receipt_id(self.gate):
            raise ValueError("gate closure receipt identity must be the exact gate-derived receipt identity")
        _require_digest(self.matrix_closure_basis_digest, field_name="matrix_closure_basis_digest")
        _require_digest(self.acceptance_attestation_digest, field_name="acceptance_attestation_digest")
        return self


class LedgerAcceptanceRecordAnchorV1(BaseModel):
    """An external, current evidence record that freezes one ACCEPT attestation.

    This object is intentionally not a matrix field.  Its coordinate is checked
    against an independently supplied ``EvidenceSubjectSnapshotV1`` at gate
    evaluation time, so replacing every digest inside a mutable matrix cannot
    remint acceptance authority.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    coordinate: EvidenceCoordinateV1
    acceptance_attestation_digest: str = Field(min_length=1)
    attestation_id: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    attested_at: datetime
    matrix_basis_digest: str = Field(min_length=1)
    denominator_digest: str = Field(min_length=1)
    denominator_revision: str = Field(min_length=1)
    union_review: LedgerUnionReviewSnapshotV1
    review_subject_id: str = Field(min_length=1)
    review_subject_revision: str = Field(min_length=1)
    review_subject_digest: str = Field(min_length=1)
    review_subject_observed_at: datetime

    @model_validator(mode="after")
    def _check_anchor(self) -> LedgerAcceptanceRecordAnchorV1:
        if self.coordinate.role is not EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW:
            raise ValueError("acceptance record anchor must use independent_engineering_review evidence")
        _require_digest(self.acceptance_attestation_digest, field_name="acceptance_attestation_digest")
        _require_identity(self.attestation_id, field_name="attestation_id", pattern=_ATTESTATION_ID_PATTERN)
        _require_non_placeholder(self.reviewer, field_name="reviewer")
        _require_observed_at(self.attested_at, field_name="attested_at")
        _require_digest(self.matrix_basis_digest, field_name="matrix_basis_digest")
        _require_digest(self.denominator_digest, field_name="denominator_digest")
        _require_non_placeholder(self.denominator_revision, field_name="denominator_revision")
        _require_identity(self.review_subject_id, field_name="review_subject_id", pattern=_SUBJECT_ID_PATTERN)
        _require_non_placeholder(self.review_subject_revision, field_name="review_subject_revision")
        _require_digest(self.review_subject_digest, field_name="review_subject_digest")
        _require_observed_at(self.review_subject_observed_at, field_name="review_subject_observed_at")
        if self.coordinate.subject_digest != self.calculated_subject_digest:
            raise ValueError("acceptance record anchor coordinate does not bind its canonical record content")
        return self

    @property
    def calculated_subject_digest(self) -> str:
        """Return the external record content digest without its snapshot binding.

        The coordinate's snapshot fields are deliberately excluded to avoid a
        self-reference: the independently observed subject supplies those
        fields and its digest must equal this frozen record content digest.
        """
        return _canonical_digest(
            {
                "acceptance_attestation_digest": self.acceptance_attestation_digest,
                "attestation_id": self.attestation_id,
                "reviewer": self.reviewer,
                "attested_at": self.attested_at,
                "matrix_basis_digest": self.matrix_basis_digest,
                "denominator_digest": self.denominator_digest,
                "denominator_revision": self.denominator_revision,
                "union_review": self.union_review,
                "review_subject_id": self.review_subject_id,
                "review_subject_revision": self.review_subject_revision,
                "review_subject_digest": self.review_subject_digest,
                "review_subject_observed_at": self.review_subject_observed_at,
                "coordinate": {
                    "evidence_id": self.coordinate.evidence_id,
                    "kind": self.coordinate.kind,
                    "role": self.coordinate.role,
                    "axes": self.coordinate.axes,
                    "locator": self.coordinate.locator,
                    "claim": self.coordinate.claim,
                },
            }
        )


class LedgerCapabilityMatrixV1(BaseModel):
    """Accepted/current census and current evidence subjects bind every matrix row."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    schema_version: int = Field(ge=1)
    controls: LedgerCampaignControlsV1
    accepted_denominator: LedgerDenominatorSnapshotV1
    current_denominator: LedgerDenominatorSnapshotV1
    accepted_union_review: LedgerUnionReviewSnapshotV1
    current_union_review: LedgerUnionReviewSnapshotV1
    live_union: LedgerUnionDenominatorV1 | None = None
    accepted_authority_dispositions: AuthorityDispositionSnapshotV1
    current_authority_dispositions: AuthorityDispositionSnapshotV1
    current_subjects: tuple[EvidenceSubjectSnapshotV1, ...]
    rows: tuple[LedgerCapabilityRowV1, ...]
    campaign_evidence: tuple[EvidenceCoordinateV1, ...] = ()
    accepted_gate_closure_receipts: tuple[LedgerGateClosureReceiptV1, ...] = ()
    matrix_digest: str = Field(min_length=1)
    acceptance_attestation: LedgerMatrixAcceptanceAttestationV1

    @model_validator(mode="after")
    def _check_matrix(self) -> LedgerCapabilityMatrixV1:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported Ledger capability matrix schema version: {self.schema_version}")
        if not self.current_subjects:
            raise ValueError("matrix requires current evidence-subject snapshots")
        subject_ids = tuple(subject.subject_id for subject in self.current_subjects)
        if len(set(subject_ids)) != len(subject_ids):
            raise ValueError("current subject snapshots contain duplicate identities")
        row_ids = tuple(row.identity.row_id for row in self.rows)
        if len(set(row_ids)) != len(row_ids):
            raise ValueError("matrix contains duplicate row identities")
        if frozenset(row_ids) != self.current_denominator.capability_ids:
            raise ValueError("matrix rows must exactly equal current complete denominator")
        if self.live_union is not None:
            canonical_union = LedgerUnionDenominatorV1.model_validate(_serialized_python_data(self.live_union))
            if LedgerUnionReviewSnapshotV1.from_union(canonical_union) != self.current_union_review:
                raise ValueError("matrix reviewed union snapshot is stale against the supplied live union")
            live_union_ids = frozenset(row.capability_id for row in canonical_union.rows)
            if frozenset(row_ids) != live_union_ids:
                raise ValueError("matrix rows must exactly equal supplied live union identities")
            if self.current_denominator.capability_ids != live_union_ids:
                raise ValueError("current denominator must exactly equal supplied live union identities")
        if frozenset(self.accepted_authority_dispositions.dispositions) != self.accepted_denominator.capability_ids:
            raise ValueError("accepted authority dispositions must exactly equal the accepted denominator")
        if self.accepted_authority_dispositions.census_id != self.accepted_denominator.census_id:
            raise ValueError("accepted authority dispositions must bind the accepted denominator census")
        if frozenset(row_ids) != frozenset(self.current_authority_dispositions.dispositions):
            raise ValueError("current authority dispositions must exactly equal matrix rows")
        if self.current_authority_dispositions.census_id != self.current_denominator.census_id:
            raise ValueError("current authority dispositions must bind the current denominator census")
        current_dispositions = self.current_authority_dispositions.dispositions
        for row in self.rows:
            if current_dispositions[row.identity.row_id] is not row.authority_migration.initial_cli_ownership:
                raise ValueError("current authority disposition contradicts immutable row history")
        evidence = tuple(self.iter_evidence())
        evidence_ids = tuple(coordinate.evidence_id for coordinate in evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence identities must be globally unique")
        subjects = {subject.subject_id: subject for subject in self.current_subjects}
        for coordinate in evidence:
            subject = subjects.get(coordinate.subject_id)
            if subject is None or not coordinate.is_current_against(subject):
                raise ValueError(f"evidence {coordinate.evidence_id!r} is stale or absent from current subjects")
        _require_digest(self.matrix_digest, field_name="matrix_digest")
        if self.matrix_digest != self.calculated_matrix_digest:
            raise ValueError("matrix digest does not bind the current campaign state")
        attestation = self.acceptance_attestation
        if attestation.plan_owner != self.controls.sole_ledger_parity_plan_owner:
            raise ValueError("acceptance attestation plan owner differs from campaign controls")
        if attestation.matrix_digest != self.attestation_matrix_basis_digest:
            raise ValueError("acceptance attestation is not bound to the frozen pre-receipt matrix basis")
        if (
            attestation.denominator_digest != self.current_denominator.digest
            or attestation.denominator_revision != self.current_denominator.revision
        ):
            raise ValueError("acceptance attestation is not bound to this exact denominator revision")
        if attestation.union_review != self.current_union_review:
            raise ValueError("acceptance attestation is not bound to this exact reviewed union")
        review_subject = subjects.get(attestation.review_subject_id)
        if review_subject is None or (
            attestation.review_subject_revision != review_subject.revision
            or attestation.review_subject_digest != review_subject.digest
            or attestation.review_subject_observed_at != review_subject.observed_at
        ):
            raise ValueError("acceptance attestation review subject is stale or absent")
        self._validate_gate_closure_receipts()
        return self

    def _validate_gate_closure_receipts(self) -> None:
        """Require a unique ordered prefix of current independently accepted receipts."""
        expected_gates = _GATE_ORDER[: len(self.accepted_gate_closure_receipts)]
        actual_gates = tuple(receipt.gate for receipt in self.accepted_gate_closure_receipts)
        if actual_gates != expected_gates:
            raise ValueError("gate closure receipts must form the ordered G0-through-G3 prefix exactly once")
        if len({receipt.receipt_id for receipt in self.accepted_gate_closure_receipts}) != len(
            self.accepted_gate_closure_receipts
        ):
            raise ValueError("gate closure receipts contain duplicate identities")
        attestation = self.acceptance_attestation
        expected_receipt_set_digest = (
            self.gate_closure_receipt_set_digest if self.accepted_gate_closure_receipts else None
        )
        if attestation.closure_receipt_set_digest != expected_receipt_set_digest:
            raise ValueError("acceptance attestation is not bound to the exact gate closure receipt identity set")
        if self.accepted_gate_closure_receipts and attestation.ruling is not ReviewRuling.ACCEPT:
            raise ValueError("gate closure receipts require a current ACCEPT acceptance attestation")
        for receipt in self.accepted_gate_closure_receipts:
            if receipt.matrix_closure_basis_digest != self.gate_closure_basis_digest(receipt.gate):
                raise ValueError("gate closure receipt is stale or not bound to the current matrix closure basis")
            if receipt.acceptance_attestation_digest != attestation.calculated_digest:
                raise ValueError("gate closure receipt is not bound to the current independent acceptance attestation")

    def accepted_gate_closure_receipt(self, gate: LedgerGate) -> LedgerGateClosureReceiptV1 | None:
        """Return the current accepted receipt for one pre-TUI gate, if recorded."""
        return next((receipt for receipt in self.accepted_gate_closure_receipts if receipt.gate is gate), None)

    @property
    def gate_closure_receipt_set_digest(self) -> str:
        """Hash the frozen receipt identities and gates that the attestation authorizes."""
        return self.calculate_gate_closure_receipt_set_digest(
            tuple((receipt.receipt_id, receipt.gate) for receipt in self.accepted_gate_closure_receipts)
        )

    @classmethod
    def calculate_gate_closure_receipt_set_digest(cls, identities: tuple[tuple[str, LedgerGate], ...]) -> str:
        """Calculate the noncircular receipt-set binding before receipt attestation digests exist."""
        return _canonical_digest({"gate_closure_receipt_identities": tuple(sorted(identities))})

    def iter_evidence(self) -> Iterable[EvidenceCoordinateV1]:
        """Yield every coordinate whose identity and freshness are globally checked."""
        for row in self.rows:
            for assessment in row.assessments:
                yield assessment.applicability_review_evidence
                yield from assessment.evidence
        yield from self.campaign_evidence

    def has_campaign_evidence(self, role: EvidenceRole) -> bool:
        """Return whether a current campaign-wide coordinate has a role."""
        return any(coordinate.role is role for coordinate in self.campaign_evidence)

    @property
    def attestation_matrix_basis_digest(self) -> str:
        """Return the noncircular exact matrix basis independently reviewed before receipts.

        Receipt publication and the sole authorized active-hold transition are
        excluded.  The acceptance attestation itself is omitted only here to
        avoid a hash cycle; the gate closure basis below includes its complete
        canonical content.
        """
        return self.calculate_attestation_matrix_basis_digest(
            schema_version=self.schema_version,
            controls=self.controls,
            accepted_denominator=self.accepted_denominator,
            current_denominator=self.current_denominator,
            accepted_union_review=self.accepted_union_review,
            current_union_review=self.current_union_review,
            accepted_authority_dispositions=self.accepted_authority_dispositions,
            current_authority_dispositions=self.current_authority_dispositions,
            current_subjects=self.current_subjects,
            rows=self.rows,
            campaign_evidence=self.campaign_evidence,
        )

    @classmethod
    def calculate_attestation_matrix_basis_digest(
        cls,
        *,
        schema_version: int,
        controls: LedgerCampaignControlsV1,
        accepted_denominator: LedgerDenominatorSnapshotV1,
        current_denominator: LedgerDenominatorSnapshotV1,
        accepted_union_review: LedgerUnionReviewSnapshotV1,
        current_union_review: LedgerUnionReviewSnapshotV1,
        accepted_authority_dispositions: AuthorityDispositionSnapshotV1,
        current_authority_dispositions: AuthorityDispositionSnapshotV1,
        current_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
        rows: tuple[LedgerCapabilityRowV1, ...],
        campaign_evidence: tuple[EvidenceCoordinateV1, ...],
    ) -> str:
        """Calculate the acceptance basis without constructing a cyclic matrix."""
        normalized_controls = {
            "sole_ledger_parity_plan_owner": controls.sole_ledger_parity_plan_owner,
            "tui_implementation_hold_recorded": controls.tui_implementation_hold_recorded,
        }
        return _canonical_digest(
            {
                "schema_version": schema_version,
                "controls": normalized_controls,
                "accepted_denominator": accepted_denominator,
                "current_denominator": current_denominator,
                "accepted_union_review": accepted_union_review,
                "current_union_review": current_union_review,
                "accepted_authority_dispositions": accepted_authority_dispositions,
                "current_authority_dispositions": current_authority_dispositions,
                "current_subjects": tuple(sorted(current_subjects, key=lambda subject: subject.subject_id)),
                "rows": tuple(sorted(rows, key=lambda row: row.identity.row_id)),
                "campaign_evidence": tuple(sorted(campaign_evidence, key=lambda coordinate: coordinate.evidence_id)),
            }
        )

    @property
    def calculated_matrix_digest(self) -> str:
        """Return the digest of all mutable semantic and proof-bearing campaign facts."""
        return self.calculate_digest(
            schema_version=self.schema_version,
            controls=self.controls,
            accepted_denominator=self.accepted_denominator,
            current_denominator=self.current_denominator,
            accepted_union_review=self.accepted_union_review,
            current_union_review=self.current_union_review,
            accepted_authority_dispositions=self.accepted_authority_dispositions,
            current_authority_dispositions=self.current_authority_dispositions,
            current_subjects=self.current_subjects,
            rows=self.rows,
            campaign_evidence=self.campaign_evidence,
            accepted_gate_closure_receipts=self.accepted_gate_closure_receipts,
        )

    def gate_closure_basis_digest(self, gate: LedgerGate) -> str:
        """Hash the frozen matrix state that a G0--G3 receipt is allowed to carry.

        The current full matrix digest includes the active-hold control and the
        receipt collection.  Neither belongs in a historical closure basis:
        lifting the hold is the authorized G3-to-G4 transition, and a receipt
        cannot cryptographically contain itself.  All other matrix facts remain
        bound, including every row and current evidence subject.
        """
        if gate not in _GATE_ORDER[:-1]:
            raise ValueError("only G0 through G3 have closure receipt bases")
        controls = {
            "sole_ledger_parity_plan_owner": self.controls.sole_ledger_parity_plan_owner,
            "tui_implementation_hold_recorded": self.controls.tui_implementation_hold_recorded,
        }
        return _canonical_digest(
            {
                "gate": gate,
                "schema_version": self.schema_version,
                "controls": controls,
                "accepted_denominator": self.accepted_denominator,
                "current_denominator": self.current_denominator,
                "accepted_union_review": self.accepted_union_review,
                "current_union_review": self.current_union_review,
                "accepted_authority_dispositions": self.accepted_authority_dispositions,
                "current_authority_dispositions": self.current_authority_dispositions,
                "current_subjects": tuple(sorted(self.current_subjects, key=lambda subject: subject.subject_id)),
                "rows": tuple(sorted(self.rows, key=lambda row: row.identity.row_id)),
                "campaign_evidence": tuple(
                    sorted(self.campaign_evidence, key=lambda coordinate: coordinate.evidence_id)
                ),
                "acceptance_attestation": self.acceptance_attestation,
            }
        )

    @classmethod
    def calculate_digest(
        cls,
        *,
        schema_version: int,
        controls: LedgerCampaignControlsV1,
        accepted_denominator: LedgerDenominatorSnapshotV1,
        current_denominator: LedgerDenominatorSnapshotV1,
        accepted_union_review: LedgerUnionReviewSnapshotV1,
        current_union_review: LedgerUnionReviewSnapshotV1,
        accepted_authority_dispositions: AuthorityDispositionSnapshotV1,
        current_authority_dispositions: AuthorityDispositionSnapshotV1,
        current_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
        rows: tuple[LedgerCapabilityRowV1, ...],
        campaign_evidence: tuple[EvidenceCoordinateV1, ...],
        accepted_gate_closure_receipts: tuple[LedgerGateClosureReceiptV1, ...] = (),
    ) -> str:
        """Calculate the pre-attestation digest without constructing an invalid matrix."""
        return _canonical_digest(
            {
                "schema_version": schema_version,
                "controls": controls,
                "accepted_denominator": accepted_denominator,
                "current_denominator": current_denominator,
                "accepted_union_review": accepted_union_review,
                "current_union_review": current_union_review,
                "accepted_authority_dispositions": accepted_authority_dispositions,
                "current_authority_dispositions": current_authority_dispositions,
                "current_subjects": tuple(sorted(current_subjects, key=lambda subject: subject.subject_id)),
                "rows": tuple(sorted(rows, key=lambda row: row.identity.row_id)),
                "campaign_evidence": tuple(sorted(campaign_evidence, key=lambda coordinate: coordinate.evidence_id)),
                "accepted_gate_closure_receipts": tuple(
                    sorted(accepted_gate_closure_receipts, key=lambda receipt: receipt.gate)
                ),
            }
        )


def ledger_capability_matrix_source_digest(path: Path | None = None) -> str:
    """Hash the matrix contract bytes after newline normalization.

    A source coordinate must not drift merely because a checkout translates
    CRLF.  The framed payload still changes for every semantic byte change.
    """
    source = Path(__file__) if path is None else path
    normalized = source.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return f"sha256:{hashlib.sha256(_LEDGER_MATRIX_CONTRACT_FRAME + _length_frame(normalized)).hexdigest()}"


def _matrix_subject(union: LedgerUnionDenominatorV1) -> EvidenceSubjectSnapshotV1:
    return EvidenceSubjectSnapshotV1(
        subject_id="subject.ledger.matrix_contract",
        locator="dev/quality/clitui_ledger_capability_matrix.py",
        revision="matrix-contract-v1",
        digest=ledger_capability_matrix_source_digest(),
        observed_at=union.row_review_attestation.reviewed_at,
    )


def _matrix_coordinate(
    subject: EvidenceSubjectSnapshotV1,
    *,
    evidence_id: str,
    kind: EvidenceKind,
    role: EvidenceRole,
    axes: frozenset[LedgerCapabilityAxis],
    claim: str,
) -> EvidenceCoordinateV1:
    return EvidenceCoordinateV1(
        evidence_id=evidence_id,
        kind=kind,
        role=role,
        axes=axes,
        subject_id=subject.subject_id,
        subject_revision=subject.revision,
        subject_digest=subject.digest,
        observed_at=subject.observed_at,
        locator=subject.locator,
        claim=claim,
    )


def _matrix_live_report(union: LedgerUnionDenominatorV1) -> LedgerLiveCensusReportV1:
    streams: list[CensusStreamObservationV1] = []
    for source in DenominatorSourceKind:
        capability_ids = tuple(row.capability_id for row in union.rows if source in row.sources)
        provisional = CensusStreamObservationV1.model_construct(
            source=source,
            revision=union.review_revision,
            observed_at=union.row_review_attestation.reviewed_at,
            scan_succeeded=True,
            readable=True,
            complete=True,
            ambiguous=False,
            reviewed_zero=not capability_ids,
            capability_ids=capability_ids,
            digest="",
        )
        streams.append(provisional.model_copy(update={"digest": provisional.calculated_digest}))
    provisional_report = LedgerLiveCensusReportV1.model_construct(
        census_id="census.ledger.matrix_union",
        revision=union.review_revision,
        observed_at=union.row_review_attestation.reviewed_at,
        streams=tuple(streams),
        digest="",
    )
    return provisional_report.model_copy(update={"digest": provisional_report.calculated_digest})


def _matrix_authority_snapshot(
    denominator: LedgerDenominatorSnapshotV1,
    rows: tuple[LedgerCapabilityRowV1, ...],
) -> AuthorityDispositionSnapshotV1:
    entries = tuple(
        AuthorityDispositionEntryV1(
            row_id=row.identity.row_id,
            initial_cli_ownership=row.authority_migration.initial_cli_ownership,
        )
        for row in rows
    )
    provisional = AuthorityDispositionSnapshotV1.model_construct(
        census_id=denominator.census_id,
        revision=denominator.revision,
        observed_at=denominator.observed_at,
        entries=entries,
        digest="",
    )
    return provisional.model_copy(update={"digest": provisional.calculated_digest})


def _matrix_gap_axes(
    row: LedgerUnionCapabilityRowV1,
    gap_class: LedgerGapClass,
    applicable_axes: frozenset[LedgerCapabilityAxis],
) -> frozenset[LedgerCapabilityAxis]:
    """Map each authoritative reviewed gap to its owning matrix axis set."""
    axis_by_gap = {
        LedgerGapClass.AUTHORITY: frozenset({LedgerCapabilityAxis.CLI}),
        LedgerGapClass.PRODUCT: frozenset({LedgerCapabilityAxis.BACKEND}),
        LedgerGapClass.COMPOSITION: frozenset({LedgerCapabilityAxis.COMPOSITION}),
        LedgerGapClass.ARTIFACT: frozenset({LedgerCapabilityAxis.ARTIFACT}),
        LedgerGapClass.PROVENANCE: frozenset({LedgerCapabilityAxis.PROVENANCE}),
        LedgerGapClass.REGISTRY: frozenset({LedgerCapabilityAxis.REGISTRY}),
        LedgerGapClass.REACHABILITY: frozenset({LedgerCapabilityAxis.TUI}),
        LedgerGapClass.PROOF: applicable_axes,
    }
    axes = axis_by_gap[gap_class] & applicable_axes
    if not axes:
        raise ValueError(f"reviewed {gap_class.value} finding has no applicable matrix axis: {row.capability_id}")
    return axes


def _matrix_row_from_union(
    row: LedgerUnionCapabilityRowV1, subject: EvidenceSubjectSnapshotV1
) -> LedgerCapabilityRowV1:
    """Project one reviewed union row without inventing a second baseline.

    The matrix is a gate-oriented projection, not a replacement review
    register.  Its annotations, surface state and findings therefore preserve
    the row-review cohorts instead of inferring ownership from mere CLI
    applicability or reachability from every mapped TUI route.
    """
    identity = LedgerCapabilityIdentityV1(
        capability_id=row.capability_id,
        operation_id=row.capability_id,
        suboperation_id=row.capability_id,
    )
    assessments: list[AxisAssessmentV1] = []
    applicable_axes = frozenset(
        decision.axis for decision in row.applicability if decision.applicability is ApplicabilityState.APPLICABLE
    )
    cli_applicable = LedgerCapabilityAxis.CLI in applicable_axes
    tui_applicable = LedgerCapabilityAxis.TUI in applicable_axes
    cli_observed = bool(row.sources & {DenominatorSourceKind.CLI_ENDPOINT, DenominatorSourceKind.CLI_SUBOPERATION})
    tui_observed = bool(row.tui_routes)
    for decision in row.applicability:
        applicable = decision.applicability is ApplicabilityState.APPLICABLE
        if not applicable:
            surface_state = SurfaceCapabilityState.NOT_APPLICABLE if decision.axis in _SURFACE_AXES else None
        elif decision.axis is LedgerCapabilityAxis.BACKEND:
            surface_state = (
                SurfaceCapabilityState.ABSENT
                if row.semantic_home_status is SemanticHomeStatus.PLANNED
                else SurfaceCapabilityState.PARTIAL
            )
        elif decision.axis is LedgerCapabilityAxis.CLI:
            surface_state = SurfaceCapabilityState.PARTIAL if cli_observed else SurfaceCapabilityState.ABSENT
        elif decision.axis is LedgerCapabilityAxis.TUI:
            surface_state = SurfaceCapabilityState.PARTIAL if tui_observed else SurfaceCapabilityState.ABSENT
        else:
            surface_state = None
        assessments.append(
            AxisAssessmentV1(
                axis=decision.axis,
                applicability=decision.applicability,
                applicability_rationale=decision.rationale,
                applicability_review_evidence=_matrix_coordinate(
                    subject,
                    evidence_id=f"evidence.{row.capability_id.removeprefix('ledger.')}.applicability.{decision.axis.value}",
                    kind=EvidenceKind.REVIEW,
                    role=EvidenceRole.APPLICABILITY_REVIEW,
                    axes=frozenset({decision.axis}),
                    claim="The exhaustive union review records this axis applicability decision.",
                ),
                proof=(AxisProofState.UNPROVEN if applicable else AxisProofState.NOT_APPLICABLE),
                surface_state=surface_state,
            )
        )
    findings = [
        CapabilityFindingV1(
            finding_id=f"finding.{row.capability_id.removeprefix('ledger.')}.{gap_class.value}",
            gap_class=gap_class,
            affected_axes=_matrix_gap_axes(row, gap_class, applicable_axes),
            description=" ".join(row.blockers),
            next_closure_action=row.next_action,
        )
        for gap_class in sorted(row.gap_classes, key=lambda item: item.value)
    ]
    annotations: set[CapabilityAnnotation] = set()
    initial_ownership = InitialCliOwnership.NOT_CLI_OWNED
    if LedgerGapClass.AUTHORITY in row.gap_classes:
        if not cli_applicable:
            raise ValueError("an authority review finding requires an applicable CLI axis")
        initial_ownership = InitialCliOwnership.CLI_OWNED
        annotations.add(CapabilityAnnotation.CLI_OWNED)
    if tui_applicable:
        if LedgerGapClass.REACHABILITY in row.gap_classes:
            annotations.add(CapabilityAnnotation.COMPONENT_ONLY)
        elif row.tui_routes == ("ledger.overview",):
            annotations.add(CapabilityAnnotation.INSTALLED)
    return LedgerCapabilityRowV1(
        identity=identity,
        semantic_home=row.semantic_home,
        assessments=tuple(assessments),
        annotations=frozenset(annotations),
        findings=tuple(findings),
        authority_migration=AuthorityMigrationHistoryV1(
            initial_cli_ownership=initial_ownership,
            migration_completed=False,
        ),
        cli_delegates_to_canonical=False,
        tui_hold_until=LEDGER_TUI_HOLD_UNTIL_GATE if tui_applicable else None,
    )


@cache
def build_ledger_capability_matrix() -> LedgerCapabilityMatrixV1:
    """Build the sole deterministic 693-row pre-acceptance Ledger candidate."""
    union = build_ledger_union_denominator()
    subject = _matrix_subject(union)
    rows = tuple(_matrix_row_from_union(row, subject) for row in union.rows)
    report = _matrix_live_report(union)
    denominator = LedgerDenominatorSnapshotV1.from_live_report(report)
    union_review = LedgerUnionReviewSnapshotV1.from_union(union)
    authority = _matrix_authority_snapshot(denominator, rows)
    controls = LedgerCampaignControlsV1(
        sole_ledger_parity_plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
        tui_implementation_hold_recorded=True,
        tui_implementation_hold_active=True,
    )
    campaign_evidence = (
        _matrix_coordinate(
            subject,
            evidence_id="evidence.ledger.matrix.publication",
            kind=EvidenceKind.REFERENCE,
            role=EvidenceRole.MATRIX_PUBLICATION,
            axes=_ALL_AXES,
            claim="This coordinate binds the canonical matrix contract source under newline-normalized framing.",
        ),
    )
    matrix_digest = LedgerCapabilityMatrixV1.calculate_digest(
        schema_version=SCHEMA_VERSION,
        controls=controls,
        accepted_denominator=denominator,
        current_denominator=denominator,
        accepted_union_review=union_review,
        current_union_review=union_review,
        accepted_authority_dispositions=authority,
        current_authority_dispositions=authority,
        current_subjects=(subject,),
        rows=rows,
        campaign_evidence=campaign_evidence,
    )
    basis = LedgerCapabilityMatrixV1.calculate_attestation_matrix_basis_digest(
        schema_version=SCHEMA_VERSION,
        controls=controls,
        accepted_denominator=denominator,
        current_denominator=denominator,
        accepted_union_review=union_review,
        current_union_review=union_review,
        accepted_authority_dispositions=authority,
        current_authority_dispositions=authority,
        current_subjects=(subject,),
        rows=rows,
        campaign_evidence=campaign_evidence,
    )
    attestation = LedgerMatrixAcceptanceAttestationV1(
        attestation_id="attestation.ledger.preacceptance",
        reviewer="independent-review-pending",
        ruling=ReviewRuling.REJECT,
        plan_owner=ACCEPTED_LEDGER_PARITY_PLAN_OWNER,
        matrix_digest=basis,
        denominator_digest=denominator.digest,
        denominator_revision=denominator.revision,
        union_review=union_review,
        review_subject_id=subject.subject_id,
        review_subject_revision=subject.revision,
        review_subject_digest=subject.digest,
        review_subject_observed_at=subject.observed_at,
        attested_at=subject.observed_at,
    )
    return LedgerCapabilityMatrixV1(
        schema_version=SCHEMA_VERSION,
        controls=controls,
        accepted_denominator=denominator,
        current_denominator=denominator,
        accepted_union_review=union_review,
        current_union_review=union_review,
        live_union=union,
        accepted_authority_dispositions=authority,
        current_authority_dispositions=authority,
        current_subjects=(subject,),
        rows=rows,
        campaign_evidence=campaign_evidence,
        matrix_digest=matrix_digest,
        acceptance_attestation=attestation,
    )


class GateAssessmentV1(BaseModel):
    """The deterministic open/closed result for one gate predicate."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    gate: LedgerGate
    closed: bool
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check_shape(self) -> GateAssessmentV1:
        if self.closed and self.blockers:
            raise ValueError("a closed gate cannot carry blockers")
        if not self.closed and not self.blockers:
            raise ValueError("an open gate must name blockers")
        return self


def _denominator_drift(accepted: LedgerDenominatorSnapshotV1, current: LedgerDenominatorSnapshotV1) -> tuple[str, ...]:
    if accepted.census_id != current.census_id:
        return ("accepted and current denominator census identities differ",)
    accepted_entries = {entry.capability_id: entry.sources for entry in accepted.entries}
    current_entries = {entry.capability_id: entry.sources for entry in current.entries}
    drift: list[str] = []
    for identity in sorted(current_entries.keys() - accepted_entries.keys()):
        drift.append(f"new live denominator capability: {identity}")
    for identity in sorted(accepted_entries.keys() - current_entries.keys()):
        drift.append(f"accepted denominator capability missing from current census: {identity}")
    for identity in sorted(accepted_entries.keys() & current_entries.keys()):
        if accepted_entries[identity] != current_entries[identity]:
            drift.append(f"denominator source classification drifted: {identity}")
    if accepted.revision != current.revision:
        drift.append("denominator revision drifted")
    if accepted.observed_at != current.observed_at:
        drift.append("denominator observation time drifted")
    if accepted.source_report_revision != current.source_report_revision:
        drift.append("denominator source-report revision drifted")
    if accepted.source_report_observed_at != current.source_report_observed_at:
        drift.append("denominator source-report observation time drifted")
    if accepted.source_report_digest != current.source_report_digest:
        drift.append("denominator source-report digest drifted")
    if accepted.digest != current.digest and not drift:
        drift.append("denominator digest drifted without an entry-level explanation")
    return tuple(drift)


def _union_review_drift(accepted: LedgerUnionReviewSnapshotV1, current: LedgerUnionReviewSnapshotV1) -> tuple[str, ...]:
    """Name every reviewed-union change that invalidates the G0 freeze."""
    labels = (
        ("union_digest", "reviewed union digest drifted"),
        ("row_review_digest", "union row-review digest drifted"),
        ("row_review_attestation_digest", "union row-review attestation digest drifted"),
        ("reviewed_row_count", "union reviewed-row coverage drifted"),
        ("review_revision", "union review revision drifted"),
        ("review_id", "union review identity drifted"),
        ("reviewed_at", "union review observation time drifted"),
    )
    return tuple(label for field_name, label in labels if getattr(accepted, field_name) != getattr(current, field_name))


def _authority_disposition_drift(
    accepted: AuthorityDispositionSnapshotV1, current: AuthorityDispositionSnapshotV1
) -> tuple[str, ...]:
    """Detect erased or changed immutable initial CLI ownership across revisions."""
    if accepted.census_id != current.census_id:
        return ("accepted and current authority disposition census identities differ",)
    accepted_entries = accepted.dispositions
    current_entries = current.dispositions
    drift: list[str] = []
    for row_id in sorted(current_entries.keys() - accepted_entries.keys()):
        drift.append(f"new authority disposition row: {row_id}")
    for row_id in sorted(accepted_entries.keys() - current_entries.keys()):
        drift.append(f"accepted authority disposition missing from current snapshot: {row_id}")
    for row_id in sorted(accepted_entries.keys() & current_entries.keys()):
        if accepted_entries[row_id] is not current_entries[row_id]:
            drift.append(f"immutable initial CLI ownership drifted: {row_id}")
    if accepted.revision != current.revision:
        drift.append("authority disposition revision drifted")
    if accepted.observed_at != current.observed_at:
        drift.append("authority disposition observation time drifted")
    if accepted.digest != current.digest and not drift:
        drift.append("authority disposition digest drifted without an entry-level explanation")
    return tuple(drift)


def _live_census_report_errors(report: LedgerLiveCensusReportV1) -> list[str]:
    """Recheck a supplied report so model-copy construction cannot bypass G0."""
    errors: list[str] = []
    sources = tuple(stream.source for stream in report.streams)
    if len(set(sources)) != len(sources) or frozenset(sources) != frozenset(DenominatorSourceKind):
        errors.append("live census report does not account for every mandatory source stream exactly once")
    if report.digest != report.calculated_digest:
        errors.append("live census report digest is stale or does not match its stream observations")
    for stream in report.streams:
        if stream.digest != stream.calculated_digest:
            errors.append(f"{stream.source.value} census stream digest is stale or does not match its observation")
        if len(set(stream.capability_ids)) != len(stream.capability_ids):
            errors.append(f"{stream.source.value} census stream has duplicate capability identities")
        if stream.capability_ids and stream.reviewed_zero:
            errors.append(f"{stream.source.value} census stream has entries but is declared reviewed zero")
        if not stream.capability_ids and not stream.reviewed_zero:
            errors.append(f"{stream.source.value} census stream is empty without an explicit reviewed zero")
        errors.extend(stream.readiness_errors)
    if not report.capability_ids:
        errors.append("the complete live census report is empty")
    return errors


def _matrix_acceptance_errors(matrix: LedgerCapabilityMatrixV1) -> list[str]:
    """Recheck digest-bound G0 acceptance before trusting a supplied matrix."""
    errors: list[str] = []
    if matrix.controls.sole_ledger_parity_plan_owner != ACCEPTED_LEDGER_PARITY_PLAN_OWNER:
        errors.append("campaign controls do not name the accepted clitui-ledger plan identity")
    if matrix.matrix_digest != matrix.calculated_matrix_digest:
        errors.append("matrix digest is stale or does not bind the current campaign state")
    source_subject = next(
        (subject for subject in matrix.current_subjects if subject.subject_id == "subject.ledger.matrix_contract"), None
    )
    if source_subject is not None and source_subject.digest != ledger_capability_matrix_source_digest():
        errors.append("matrix-contract evidence source digest drifted")
    attestation = matrix.acceptance_attestation
    if attestation.plan_owner != matrix.controls.sole_ledger_parity_plan_owner:
        errors.append("acceptance attestation plan owner differs from campaign controls")
    if attestation.matrix_digest != matrix.attestation_matrix_basis_digest:
        errors.append("acceptance attestation is not bound to the frozen pre-receipt matrix basis")
    if (
        attestation.denominator_digest != matrix.current_denominator.digest
        or attestation.denominator_revision != matrix.current_denominator.revision
    ):
        errors.append("acceptance attestation is not bound to this exact denominator revision")
    if attestation.union_review != matrix.current_union_review:
        errors.append("acceptance attestation is not bound to this exact reviewed union")
    subjects = {subject.subject_id: subject for subject in matrix.current_subjects}
    review_subject = subjects.get(attestation.review_subject_id)
    if review_subject is None or (
        attestation.review_subject_revision != review_subject.revision
        or attestation.review_subject_digest != review_subject.digest
        or attestation.review_subject_observed_at != review_subject.observed_at
    ):
        errors.append("acceptance attestation review subject is stale or absent")
    return errors


def validate_ledger_matrix_currentness(
    matrix: LedgerCapabilityMatrixV1,
    *,
    observed_census: LedgerLiveCensusReportV1,
    observed_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
    observed_union: LedgerUnionDenominatorV1 | None = None,
) -> list[str]:
    """Compare persisted state to mandatory live census, union, and evidence.

    A matrix can be serialized as a historical review artifact without its
    live-union payload, but no currentness or gate evaluation may accept that
    artifact.  The live union is the sole reviewed denominator authority and
    must agree exactly with the matrix rows, denominator, review snapshot, and
    independently observed union supplied at the evaluation boundary.
    """
    canonical_matrix, canonical_census, canonical_subjects, validation_blockers = _canonical_gate_inputs(
        matrix, observed_census, observed_subjects
    )
    if validation_blockers:
        return validation_blockers
    if canonical_matrix is None or canonical_census is None or canonical_subjects is None:
        return ["gate input validation failed at <root>: incomplete_canonical_result"]
    matrix = canonical_matrix
    observed_census = canonical_census
    observed_subjects = canonical_subjects
    errors = _live_census_report_errors(observed_census)
    observed_denominator = LedgerDenominatorSnapshotV1.from_live_report(observed_census)
    errors.extend(_denominator_drift(matrix.current_denominator, observed_denominator))
    if observed_union is None:
        errors.append("live reviewed union observation is missing")
    else:
        try:
            canonical_observed_union = LedgerUnionDenominatorV1.model_validate(_serialized_python_data(observed_union))
        except ValidationError as error:
            errors.extend(_validation_blockers("live reviewed union", error))
        except (TypeError, ValueError):
            errors.append("live reviewed union validation failed at <root>: invalid_serialized_data")
        else:
            observed_review = LedgerUnionReviewSnapshotV1.from_union(canonical_observed_union)
            errors.extend(_union_review_drift(matrix.current_union_review, observed_review))
            observed_ids = frozenset(row.capability_id for row in canonical_observed_union.rows)
            matrix_ids = frozenset(row.identity.row_id for row in matrix.rows)
            if matrix_ids != observed_ids:
                errors.append("matrix row identities do not exactly equal the observed live reviewed union")
            if matrix.current_denominator.capability_ids != observed_ids:
                errors.append("matrix denominator identities do not exactly equal the observed live reviewed union")
            if frozenset(matrix.current_union_review.capability_ids) != observed_ids:
                errors.append("matrix reviewed-union identities do not exactly equal the observed live reviewed union")
            if matrix.live_union is None:
                errors.append("matrix live reviewed union is missing")
            else:
                try:
                    canonical_matrix_union = LedgerUnionDenominatorV1.model_validate(
                        _serialized_python_data(matrix.live_union)
                    )
                except ValidationError as error:
                    errors.extend(_validation_blockers("matrix live reviewed union", error))
                except (TypeError, ValueError):
                    errors.append("matrix live reviewed union validation failed at <root>: invalid_serialized_data")
                else:
                    if canonical_matrix_union != canonical_observed_union:
                        errors.append("matrix live reviewed union differs from the observed live reviewed union")
                    matrix_union_ids = frozenset(row.capability_id for row in canonical_matrix_union.rows)
                    if matrix_ids != matrix_union_ids:
                        errors.append("matrix row identities do not exactly equal its live reviewed union")
                    if matrix.current_denominator.capability_ids != matrix_union_ids:
                        errors.append("matrix denominator identities do not exactly equal its live reviewed union")
                    if matrix.current_union_review != LedgerUnionReviewSnapshotV1.from_union(canonical_matrix_union):
                        errors.append("matrix reviewed union snapshot differs from its live reviewed union")
    if not observed_subjects:
        errors.append("live evidence-subject observation is empty")
    expected = {subject.subject_id: subject for subject in matrix.current_subjects}
    observed = {subject.subject_id: subject for subject in observed_subjects}
    if len(observed) != len(observed_subjects):
        errors.append("live evidence-subject observation contains duplicate identities")
    for subject_id in sorted(observed.keys() - expected.keys()):
        errors.append(f"new evidence subject absent from matrix snapshot: {subject_id}")
    for subject_id in sorted(expected.keys() - observed.keys()):
        errors.append(f"matrix evidence subject no longer observed: {subject_id}")
    for subject_id in sorted(expected.keys() & observed.keys()):
        if expected[subject_id] != observed[subject_id]:
            errors.append(f"evidence subject freshness drifted: {subject_id}")
    return errors


def _gate_assessment(gate: LedgerGate, blockers: list[str]) -> GateAssessmentV1:
    return GateAssessmentV1(gate=gate, closed=not blockers, blockers=tuple(blockers))


def _serialized_python_data(value: object) -> object:
    """Detach a supplied model from model-copy state before revalidation."""
    return value.model_dump(mode="python") if isinstance(value, BaseModel) else value


def _validation_blockers(scope: str, error: ValidationError) -> list[str]:
    """Render canonical, stable fail-closed blockers without exposing values."""
    return [
        f"{scope} validation failed at {'.'.join(str(part) for part in item['loc']) or '<root>'}: {item['type']}"
        for item in sorted(error.errors(include_url=False), key=lambda item: (item["loc"], item["type"]))
    ]


def _canonical_gate_inputs(
    matrix: LedgerCapabilityMatrixV1,
    observed_census: LedgerLiveCensusReportV1,
    observed_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
) -> tuple[
    LedgerCapabilityMatrixV1 | None,
    LedgerLiveCensusReportV1 | None,
    tuple[EvidenceSubjectSnapshotV1, ...] | None,
    list[str],
]:
    """Exhaustively revalidate every supplied gate object from serialized data."""
    blockers: list[str] = []
    canonical_matrix: LedgerCapabilityMatrixV1 | None = None
    canonical_census: LedgerLiveCensusReportV1 | None = None
    canonical_subjects: tuple[EvidenceSubjectSnapshotV1, ...] | None = None
    try:
        canonical_matrix = LedgerCapabilityMatrixV1.model_validate(_serialized_python_data(matrix))
    except ValidationError as error:
        blockers.extend(_validation_blockers("matrix", error))
    except (TypeError, ValueError):
        blockers.append("matrix validation failed at <root>: invalid_serialized_data")
    try:
        canonical_census = LedgerLiveCensusReportV1.model_validate(_serialized_python_data(observed_census))
    except ValidationError as error:
        blockers.extend(_validation_blockers("live census", error))
    except (TypeError, ValueError):
        blockers.append("live census validation failed at <root>: invalid_serialized_data")
    try:
        canonical_subjects = TypeAdapter(tuple[EvidenceSubjectSnapshotV1, ...]).validate_python(
            _serialized_python_data(observed_subjects)
        )
    except ValidationError as error:
        blockers.extend(_validation_blockers("observed subjects", error))
    except (TypeError, ValueError):
        blockers.append("observed subjects validation failed at <root>: invalid_serialized_data")
    return canonical_matrix, canonical_census, canonical_subjects, blockers


def _acceptance_record_anchor_errors(
    matrix: LedgerCapabilityMatrixV1,
    acceptance_record_anchor: LedgerAcceptanceRecordAnchorV1 | None,
    observed_acceptance_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
) -> list[str]:
    """Require an immutable, independently observed record for receipt authority."""
    if acceptance_record_anchor is None:
        return ["accepted G3 closure requires a current external acceptance record anchor"]
    try:
        anchor = LedgerAcceptanceRecordAnchorV1.model_validate(_serialized_python_data(acceptance_record_anchor))
    except ValidationError as error:
        return _validation_blockers("acceptance record anchor", error)
    except (TypeError, ValueError):
        return ["acceptance record anchor validation failed at <root>: invalid_serialized_data"]
    try:
        subjects = TypeAdapter(tuple[EvidenceSubjectSnapshotV1, ...]).validate_python(
            _serialized_python_data(observed_acceptance_subjects)
        )
    except ValidationError as error:
        return _validation_blockers("observed acceptance subjects", error)
    except (TypeError, ValueError):
        return ["observed acceptance subjects validation failed at <root>: invalid_serialized_data"]
    subject_ids = tuple(subject.subject_id for subject in subjects)
    if len(set(subject_ids)) != len(subject_ids):
        return ["observed acceptance subjects contain duplicate identities"]
    matches = tuple(subject for subject in subjects if subject.subject_id == anchor.coordinate.subject_id)
    if len(matches) != 1:
        return ["acceptance record anchor subject is absent from independently observed acceptance subjects"]
    if not anchor.coordinate.is_current_against(matches[0]):
        return ["acceptance record anchor coordinate is stale against independently observed acceptance subject"]
    attestation = matrix.acceptance_attestation
    expected = {
        "acceptance_attestation_digest": attestation.calculated_digest,
        "attestation_id": attestation.attestation_id,
        "reviewer": attestation.reviewer,
        "attested_at": attestation.attested_at,
        "matrix_basis_digest": attestation.matrix_digest,
        "denominator_digest": attestation.denominator_digest,
        "denominator_revision": attestation.denominator_revision,
        "union_review": attestation.union_review,
        "review_subject_id": attestation.review_subject_id,
        "review_subject_revision": attestation.review_subject_revision,
        "review_subject_digest": attestation.review_subject_digest,
        "review_subject_observed_at": attestation.review_subject_observed_at,
    }
    if any(getattr(anchor, field_name) != value for field_name, value in expected.items()):
        return ["acceptance record anchor does not bind the current acceptance attestation"]
    return []


def _gate_reopening_blockers(
    matrix: LedgerCapabilityMatrixV1,
    *,
    observed_census: LedgerLiveCensusReportV1,
    observed_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
    observed_union: LedgerUnionDenominatorV1 | None,
    acceptance_record_anchor: LedgerAcceptanceRecordAnchorV1 | None,
    observed_acceptance_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
) -> list[str]:
    """Return currentness defects that relock every accepted gate dependency.

    The union, matrix acceptance, and receipt anchor are separate inputs.  No
    digest inside the mutable matrix can substitute for a fresh union review or
    its independently observed acceptance record.
    """
    blockers = validate_ledger_matrix_currentness(
        matrix,
        observed_census=observed_census,
        observed_subjects=observed_subjects,
        observed_union=observed_union,
    )
    if observed_union is None:
        blockers.append("live reviewed union observation is missing")
    blockers.extend(_denominator_drift(matrix.accepted_denominator, matrix.current_denominator))
    blockers.extend(_union_review_drift(matrix.accepted_union_review, matrix.current_union_review))
    blockers.extend(
        _authority_disposition_drift(matrix.accepted_authority_dispositions, matrix.current_authority_dispositions)
    )
    blockers.extend(_matrix_acceptance_errors(matrix))
    if matrix.accepted_gate_closure_receipts:
        blockers.extend(
            _acceptance_record_anchor_errors(matrix, acceptance_record_anchor, observed_acceptance_subjects)
        )
    return list(dict.fromkeys(blockers))


def reopened_gates_for_currentness(
    matrix: LedgerCapabilityMatrixV1,
    *,
    observed_census: LedgerLiveCensusReportV1,
    observed_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
    observed_union: LedgerUnionDenominatorV1 | None,
    acceptance_record_anchor: LedgerAcceptanceRecordAnchorV1 | None = None,
    observed_acceptance_subjects: tuple[EvidenceSubjectSnapshotV1, ...] = (),
) -> frozenset[LedgerGate]:
    """Fail closed: any reviewed-state drift relocks G0 and every later gate."""
    canonical_matrix, canonical_census, canonical_subjects, validation_blockers = _canonical_gate_inputs(
        matrix, observed_census, observed_subjects
    )
    if validation_blockers or canonical_matrix is None or canonical_census is None or canonical_subjects is None:
        return frozenset(_GATE_ORDER)
    blockers = _gate_reopening_blockers(
        canonical_matrix,
        observed_census=canonical_census,
        observed_subjects=canonical_subjects,
        observed_union=observed_union,
        acceptance_record_anchor=acceptance_record_anchor,
        observed_acceptance_subjects=observed_acceptance_subjects,
    )
    return frozenset(_GATE_ORDER) if blockers else frozenset[LedgerGate]()


def evaluate_ledger_capability_gate(
    matrix: LedgerCapabilityMatrixV1,
    gate: LedgerGate,
    *,
    observed_census: LedgerLiveCensusReportV1,
    observed_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
    observed_union: LedgerUnionDenominatorV1 | None = None,
    acceptance_record_anchor: LedgerAcceptanceRecordAnchorV1 | None = None,
    observed_acceptance_subjects: tuple[EvidenceSubjectSnapshotV1, ...] = (),
) -> GateAssessmentV1:
    """Evaluate the exact G0--G4 predicate against typed current evidence."""
    canonical_matrix, canonical_census, canonical_subjects, validation_blockers = _canonical_gate_inputs(
        matrix, observed_census, observed_subjects
    )
    if validation_blockers:
        return _gate_assessment(gate, validation_blockers)
    if canonical_matrix is None or canonical_census is None or canonical_subjects is None:
        return _gate_assessment(gate, ["gate input validation failed at <root>: incomplete_canonical_result"])
    matrix = canonical_matrix
    observed_census = canonical_census
    observed_subjects = canonical_subjects
    blockers = _gate_reopening_blockers(
        matrix,
        observed_census=observed_census,
        observed_subjects=observed_subjects,
        observed_union=observed_union,
        acceptance_record_anchor=acceptance_record_anchor,
        observed_acceptance_subjects=observed_acceptance_subjects,
    )
    if gate is LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE:
        if not matrix.controls.tui_implementation_hold_recorded or not matrix.controls.tui_implementation_hold_active:
            blockers.append("the Ledger TUI implementation hold is not recorded and active")
        if matrix.acceptance_attestation.ruling is not ReviewRuling.ACCEPT:
            blockers.append("independent review has not issued an ACCEPT attestation for the frozen matrix")
        if not matrix.accepted_gate_closure_receipts:
            blockers.extend(
                _acceptance_record_anchor_errors(matrix, acceptance_record_anchor, observed_acceptance_subjects)
            )
        for row in matrix.rows:
            for assessment in row.assessments:
                if (
                    assessment.applicability is ApplicabilityState.APPLICABLE
                    and assessment.proof is not AxisProofState.UNPROVEN
                    and not row.evidence_with_role(EvidenceRole.BASELINE, axis=assessment.axis)
                ):
                    blockers.append(f"{row.identity.row_id}: {assessment.axis.value} lacks exact baseline evidence")
        return _gate_assessment(gate, blockers)
    if gate is LedgerGate.G1_SEMANTIC_AUTHORITY_RECOVERY:
        for row in matrix.rows:
            backend = row.assessment(LedgerCapabilityAxis.BACKEND)
            if row.has_gap(LedgerGapClass.AUTHORITY):
                blockers.append(f"{row.identity.row_id}: an authority finding remains")
            if CapabilityAnnotation.CLI_OWNED in row.annotations:
                blockers.append(f"{row.identity.row_id}: cli_owned annotation remains")
            if (
                backend.applicability is ApplicabilityState.APPLICABLE
                and backend.surface_state is SurfaceCapabilityState.ABSENT
            ):
                blockers.append(f"{row.identity.row_id}: applicable backend owner is absent")
            if row.authority_migration.initial_cli_ownership is InitialCliOwnership.CLI_OWNED:
                if not row.authority_migration.migration_completed:
                    blockers.append(f"{row.identity.row_id}: immutable CLI-owned migration is incomplete")
                if not row.evidence_with_role(EvidenceRole.DIRECT_BACKEND_BEHAVIOR, axis=LedgerCapabilityAxis.BACKEND):
                    blockers.append(f"{row.identity.row_id}: migrated authority lacks direct backend behavior evidence")
                if not row.evidence_with_role(EvidenceRole.ADAPTER_DETECTOR, axis=LedgerCapabilityAxis.CLI):
                    blockers.append(f"{row.identity.row_id}: migrated authority lacks an adapter detector")
        return _gate_assessment(gate, blockers)
    if gate is LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS:
        for row in matrix.rows:
            backend = row.assessment(LedgerCapabilityAxis.BACKEND)
            if backend.applicability is ApplicabilityState.APPLICABLE:
                if (
                    backend.surface_state is not SurfaceCapabilityState.PROVEN
                    or backend.proof is not AxisProofState.PROVEN
                ):
                    blockers.append(f"{row.identity.row_id}: backend is not implemented and proven")
                if not row.evidence_with_role(EvidenceRole.DIRECT_BACKEND_BEHAVIOR, axis=LedgerCapabilityAxis.BACKEND):
                    blockers.append(f"{row.identity.row_id}: backend lacks direct behavior evidence")
            for axis in _G2_AXES - {LedgerCapabilityAxis.BACKEND}:
                assessment = row.assessment(axis)
                if (
                    assessment.applicability is ApplicabilityState.APPLICABLE
                    and assessment.proof is not AxisProofState.PROVEN
                ):
                    blockers.append(f"{row.identity.row_id}: applicable {axis.value} axis is not proven")
            for gap_class in _G2_GAP_CLASSES:
                if row.has_gap(gap_class):
                    blockers.append(f"{row.identity.row_id}: {gap_class.value} finding remains")
        return _gate_assessment(gate, blockers)
    if gate is LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS:
        for row in matrix.rows:
            cli = row.assessment(LedgerCapabilityAxis.CLI)
            if cli.applicability is not ApplicabilityState.APPLICABLE:
                continue
            if cli.proof is not AxisProofState.PROVEN or cli.surface_state is not SurfaceCapabilityState.PROVEN:
                blockers.append(f"{row.identity.row_id}: CLI is not proven through a stable interface contract")
            if not row.cli_delegates_to_canonical:
                blockers.append(f"{row.identity.row_id}: CLI does not delegate to the canonical owner")
            if not row.evidence_with_role(EvidenceRole.CLI_SUCCESS, axis=LedgerCapabilityAxis.CLI):
                blockers.append(f"{row.identity.row_id}: CLI success behavior is not evidenced")
            if not row.evidence_with_role(EvidenceRole.CLI_REFUSAL, axis=LedgerCapabilityAxis.CLI):
                blockers.append(f"{row.identity.row_id}: CLI refusal behavior is not evidenced")
            if row.assessment(
                LedgerCapabilityAxis.ARTIFACT
            ).applicability is ApplicabilityState.APPLICABLE and not row.evidence_with_role(
                EvidenceRole.CLI_ARTIFACT, axis=LedgerCapabilityAxis.CLI
            ):
                blockers.append(f"{row.identity.row_id}: CLI artifact behavior is not evidenced")
            for gap_class in _G3_GAP_CLASSES:
                if row.has_gap(gap_class, axis=LedgerCapabilityAxis.CLI):
                    blockers.append(f"{row.identity.row_id}: CLI {gap_class.value} finding remains")
        return _gate_assessment(gate, blockers)
    if gate is LedgerGate.G4_TUI_ADMISSION_AND_PARITY:
        if matrix.controls.tui_implementation_hold_active:
            blockers.append("the Ledger TUI implementation hold remains active")
        elif matrix.accepted_gate_closure_receipt(LEDGER_TUI_HOLD_UNTIL_GATE) is None:
            blockers.append("the Ledger TUI implementation hold lacks a current accepted G3 closure receipt")
        else:
            for anchor_error in _acceptance_record_anchor_errors(
                matrix, acceptance_record_anchor, observed_acceptance_subjects
            ):
                if anchor_error not in blockers:
                    blockers.append(anchor_error)
        for row in matrix.rows:
            tui = row.assessment(LedgerCapabilityAxis.TUI)
            if tui.applicability is ApplicabilityState.APPLICABLE:
                if tui.proof is not AxisProofState.PROVEN or tui.surface_state is not SurfaceCapabilityState.PROVEN:
                    blockers.append(f"{row.identity.row_id}: TUI is not proven and installed")
                if CapabilityAnnotation.INSTALLED not in row.annotations:
                    blockers.append(f"{row.identity.row_id}: TUI is not marked installed")
            for finding in row.findings:
                if any(
                    row.assessment(axis).applicability is ApplicabilityState.APPLICABLE
                    for axis in finding.affected_axes
                ):
                    blockers.append(f"{row.identity.row_id}: blocking {finding.gap_class.value} finding remains")
        for role in (EvidenceRole.TUI_PARITY, EvidenceRole.TUI_REACHABILITY, EvidenceRole.MATRIX_PUBLICATION):
            if not matrix.has_campaign_evidence(role):
                blockers.append(f"campaign-wide {role.value} evidence is missing")
        return _gate_assessment(gate, blockers)
    raise ValueError(f"unsupported Ledger gate: {gate}")


def evaluate_ledger_capability_gates(
    matrix: LedgerCapabilityMatrixV1,
    *,
    observed_census: LedgerLiveCensusReportV1,
    observed_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
    observed_union: LedgerUnionDenominatorV1 | None = None,
    acceptance_record_anchor: LedgerAcceptanceRecordAnchorV1 | None = None,
    observed_acceptance_subjects: tuple[EvidenceSubjectSnapshotV1, ...] = (),
) -> tuple[GateAssessmentV1, ...]:
    """Evaluate ordered gates without allowing a later false closure.

    A current externally anchored G0 receipt preserves the historical
    active-hold closure across the one authorized post-G3 hold lift. It never
    suppresses census, matrix, receipt, or external-anchor currentness failures.
    """
    canonical_matrix, canonical_census, canonical_subjects, validation_blockers = _canonical_gate_inputs(
        matrix, observed_census, observed_subjects
    )
    if validation_blockers:
        return tuple(_gate_assessment(gate, validation_blockers) for gate in _GATE_ORDER)
    if canonical_matrix is None or canonical_census is None or canonical_subjects is None:
        incomplete = ["gate input validation failed at <root>: incomplete_canonical_result"]
        return tuple(_gate_assessment(gate, incomplete) for gate in _GATE_ORDER)

    # Ordered evaluation must not inspect an unvalidated caller-owned model for
    # the post-G3 historical-receipt exception.  A model_copy/model_construct
    # mutation can otherwise make this evaluator raise before it can relock.
    matrix = canonical_matrix
    observed_census = canonical_census
    observed_subjects = canonical_subjects
    assessments: list[GateAssessmentV1] = []
    prior_open = False
    for gate in _GATE_ORDER:
        assessment = evaluate_ledger_capability_gate(
            matrix,
            gate,
            observed_census=observed_census,
            observed_subjects=observed_subjects,
            observed_union=observed_union,
            acceptance_record_anchor=acceptance_record_anchor,
            observed_acceptance_subjects=observed_acceptance_subjects,
        )
        if (
            gate is LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE
            and matrix.accepted_gate_closure_receipt(gate) is not None
            and not matrix.controls.tui_implementation_hold_active
            and assessment.blockers == ("the Ledger TUI implementation hold is not recorded and active",)
        ):
            anchor_errors = _acceptance_record_anchor_errors(
                matrix, acceptance_record_anchor, observed_acceptance_subjects
            )
            assessment = (
                GateAssessmentV1(gate=gate, closed=True)
                if not anchor_errors
                else GateAssessmentV1(gate=gate, closed=False, blockers=tuple(anchor_errors))
            )
        if prior_open and assessment.closed:
            assessment = GateAssessmentV1(
                gate=gate, closed=False, blockers=(f"{gate.value} cannot close while an earlier gate remains open",)
            )
        assessments.append(assessment)
        prior_open = prior_open or not assessment.closed
    return tuple(assessments)


def reopened_gates_for_denominator_drift(
    accepted: LedgerDenominatorSnapshotV1, current: LedgerDenominatorSnapshotV1
) -> frozenset[LedgerGate]:
    """A changed live census reopens G0 and all potentially affected later gates."""
    try:
        canonical_accepted = LedgerDenominatorSnapshotV1.model_validate(_serialized_python_data(accepted))
        canonical_current = LedgerDenominatorSnapshotV1.model_validate(_serialized_python_data(current))
    except (TypeError, ValueError, ValidationError):
        # This legacy return shape has no blocker channel; reopening every gate
        # is the deterministic fail-closed refusal for invalid serialized data.
        return frozenset(_GATE_ORDER)
    return (
        frozenset(_GATE_ORDER) if _denominator_drift(canonical_accepted, canonical_current) else frozenset[LedgerGate]()
    )


__all__ = [
    "ACCEPTED_LEDGER_PARITY_PLAN_OWNER",
    "LEDGER_REGISTRY_ROUTE_CENSUS_ROOT",
    "LEDGER_REGISTRY_ROUTE_CENSUS_SCHEMA_VERSION",
    "LEDGER_TUI_HOLD_UNTIL_GATE",
    "LEDGER_TUI_SUPPORTED_SURFACE_CENSUS_ROOT",
    "LEDGER_TUI_SUPPORTED_SURFACE_CENSUS_SCHEMA_VERSION",
    "LEDGER_UNION_DENOMINATOR_ROOT",
    "LEDGER_UNION_DENOMINATOR_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "ApplicabilityState",
    "AuthorityDispositionEntryV1",
    "AuthorityDispositionSnapshotV1",
    "AuthorityMigrationHistoryV1",
    "AxisAssessmentV1",
    "AxisProofState",
    "CanonicalSemanticHomeV1",
    "CapabilityAnnotation",
    "CapabilityFindingV1",
    "CensusStreamObservationV1",
    "DenominatorEntryV1",
    "DenominatorSourceKind",
    "EvidenceCoordinateV1",
    "EvidenceKind",
    "EvidenceRole",
    "EvidenceSubjectSnapshotV1",
    "GateAssessmentV1",
    "InitialCliOwnership",
    "LedgerAcceptanceRecordAnchorV1",
    "LedgerAxisApplicabilityDecisionV1",
    "LedgerCampaignControlsV1",
    "LedgerCapabilityAxis",
    "LedgerCapabilityEffect",
    "LedgerCapabilityIdentityV1",
    "LedgerCapabilityMatrixV1",
    "LedgerCapabilityRowV1",
    "LedgerDenominatorSnapshotV1",
    "LedgerGapClass",
    "LedgerGate",
    "LedgerGateClosureReceiptV1",
    "LedgerLiveCensusReportV1",
    "LedgerMatrixAcceptanceAttestationV1",
    "LedgerRegistryDestinationStatus",
    "LedgerRegistryRouteCensusV1",
    "LedgerRegistryRouteRowV1",
    "LedgerRegistryRouteTargetV1",
    "LedgerTuiRouteRowV1",
    "LedgerTuiSupportedSurfaceCensusV1",
    "LedgerUnionCapabilityRowV1",
    "LedgerUnionDenominatorV1",
    "LedgerUnionReviewSnapshotV1",
    "LedgerUnionRowReviewAttestationV1",
    "LedgerUnionRowReviewRuling",
    "LedgerUnionSelectionAccountingV1",
    "LedgerUnionSourceDigestV1",
    "LedgerUnionSourceObservationV1",
    "ReviewRuling",
    "SemanticHomeStatus",
    "SurfaceCapabilityState",
    "build_ledger_capability_matrix",
    "build_ledger_registry_route_census",
    "build_ledger_tui_supported_surface_census",
    "build_ledger_union_denominator",
    "evaluate_ledger_capability_gate",
    "evaluate_ledger_capability_gates",
    "ledger_capability_matrix_source_digest",
    "ledger_gate_closure_receipt_id",
    "ledger_registry_route_census_bytes",
    "ledger_registry_route_census_digest",
    "ledger_registry_source_files",
    "ledger_registry_source_set_digest",
    "ledger_tui_supported_surface_census_bytes",
    "ledger_tui_supported_surface_census_digest",
    "ledger_tui_supported_surface_source_files",
    "ledger_tui_supported_surface_source_set_digest",
    "ledger_union_denominator_bytes",
    "ledger_union_denominator_digest",
    "reopened_gates_for_currentness",
    "reopened_gates_for_denominator_drift",
    "validate_ledger_matrix_currentness",
]
