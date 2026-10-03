"""Load the declared support scope and deterministic raw binding inventory."""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from dev.first_party_source import PRODUCT_PACKAGE
from dev.registry.compiler.export_fragment_grammar import revision_section_for_directory

from .common import load_toml, relative, revision_table, rows
from .models import RawInventory, SignalInputs, SupportScope

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import (
        ModeloDefinition,
        ModeloRevision,
        RegistryCatalogues,
        SupportedFilingYearsCatalogue,
    )


class _RawRevisionRecord(TypedDict):
    """The raw family rows and source locations for one declared revision."""

    metadata: dict[str, object]
    families: dict[str, list[dict[str, object]]]
    locations: dict[str, list[dict[str, object]]]


@dataclass(frozen=True, slots=True)
class _Location:
    """Stable authored-fragment coordinate for one declaration row."""

    path: str
    family: str
    ordinal: int


def collect_inputs(root: Path) -> SignalInputs:
    """Load enrollment, compiler, runtime, and raw-source inventory inputs."""
    registry_root = root / PRODUCT_PACKAGE / "_data" / "registry" / "aeat" / "modelos"
    registrations, registration_limits = _registration_inventory(root)
    compiled, support_scope, loader_limits = _compiled_revisions(root, registry_root.parent)
    runtime_resolvers, resolver_limits = _runtime_resolver_inventory(root)
    limitations = [*registration_limits, *loader_limits, *resolver_limits]
    binding_consumers = _load_binding_consumers(limitations)
    raw = _collect_raw_inventory(root, registry_root, support_scope)
    return SignalInputs(
        root=root,
        registry_root=registry_root,
        registrations=registrations,
        compiled=compiled,
        support_scope=support_scope,
        runtime_resolvers=runtime_resolvers,
        binding_consumers=binding_consumers,
        limitations=limitations,
        raw=raw,
    )


def _load_binding_consumers(limitations: list[dict[str, object]]):
    try:
        from cadrumo.domain.calculations.registry.binding_targets import binding_consumers
    except Exception as exc:
        limitations.append(
            {
                "code": "CANONICAL_CONSUMER_PROJECTION_IMPORT_FAILED",
                "message": f"{type(exc).__name__}: {exc}",
            }
        )
        return None
    return binding_consumers


def _collect_raw_inventory(
    root: Path,
    registry_root: Path,
    support_scope: SupportScope | None,
) -> RawInventory:
    inventory = RawInventory({}, set(), [], [], [], Counter(), Counter())
    below_floor = support_scope.below_floor if support_scope is not None else frozenset()
    for modelo_dir in sorted(path for path in registry_root.iterdir() if path.is_dir()):
        revisions_dir = modelo_dir / "revisions"
        if not revisions_dir.is_dir():
            inventory.modelos_without_revisions.append(relative(modelo_dir, root))
            continue
        _collect_modelo_revisions(root, modelo_dir, revisions_dir, below_floor, inventory)
    return inventory


def _collect_modelo_revisions(
    root: Path,
    modelo_dir: Path,
    revisions_dir: Path,
    below_floor: frozenset[tuple[str, str]],
    inventory: RawInventory,
) -> None:
    for revision_dir in sorted(path for path in revisions_dir.iterdir() if path.is_dir()):
        coordinate = (modelo_dir.name, revision_dir.name)
        inventory.declared_coordinates.add(coordinate)
        if coordinate in below_floor:
            inventory.revisions_below_floor.append(f"{coordinate[0]}/{coordinate[1]}")
            continue
        inventory.revisions[coordinate] = _collect_revision(root, revision_dir, inventory)


def _collect_revision(root: Path, revision_dir: Path, inventory: RawInventory) -> _RawRevisionRecord:
    record: _RawRevisionRecord = {"metadata": {}, "families": {}, "locations": {}}
    revision_file = revision_dir / "revision.toml"
    revision_data, error = load_toml(revision_file)
    if error:
        inventory.parse_failures.append({"path": relative(revision_file, root), "error": error})
    elif revision_data is not None:
        record["metadata"] = dict(revision_table(revision_data, revision_dir.name))
    _collect_revision_families(root, revision_dir, record, inventory)
    return record


def _collect_revision_families(
    root: Path,
    revision_dir: Path,
    record: _RawRevisionRecord,
    inventory: RawInventory,
) -> None:
    for family_dir in sorted(path for path in revision_dir.iterdir() if path.is_dir()):
        family = revision_section_for_directory(family_dir.name)
        for fragment in sorted(family_dir.glob("*.toml")):
            inventory.family_file_counts[family] += 1
            data, error = load_toml(fragment)
            if error:
                inventory.parse_failures.append({"path": relative(fragment, root), "error": error})
                continue
            if data is None:
                inventory.parse_failures.append(
                    {
                        "path": relative(fragment, root),
                        "error": "TOML loader returned no data and no diagnostic",
                    }
                )
                continue
            rows_for_family = rows(revision_table(data, revision_dir.name).get(family))
            inventory.family_row_counts[family] += len(rows_for_family)
            _record_family_rows(record, family, rows_for_family, relative(fragment, root))


def _record_family_rows(
    record: _RawRevisionRecord,
    family: str,
    rows_for_family: Sequence[object],
    path: str,
) -> None:
    for ordinal, row in enumerate(rows_for_family, 1):
        if not isinstance(row, Mapping):
            continue
        record["families"].setdefault(family, []).append(dict(row))
        record["locations"].setdefault(family, []).append(asdict(_Location(path, family, ordinal)))


def _registration_inventory(root: Path) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    limitations: list[dict[str, object]] = []
    _add_import_root(root)
    try:
        from cadrumo.domain.calculations.registry.binding_provider_registration import (
            BINDING_PROVIDER_REGISTRATIONS,
        )
    except Exception as exc:
        limitations.append({"code": "PROVIDER_REGISTRATION_IMPORT_FAILED", "message": f"{type(exc).__name__}: {exc}"})
        return {}, limitations

    result: dict[str, dict[str, object]] = {}
    for kind, registration in BINDING_PROVIDER_REGISTRATIONS.items():
        kind_value = str(getattr(kind, "value", kind))
        result[kind_value] = _registration_row(kind_value, registration)
    return result, limitations


def _registration_row(kind_value: str, registration: Any) -> dict[str, object]:
    route = registration.route
    provider_model = registration.provider_model
    return {
        "kind": kind_value,
        "provider_model": f"{provider_model.__module__}.{provider_model.__name__}",
        "validator": _qualified_callable_name(registration.validator),
        "disposition": registration.disposition,
        "output": registration.output,
        "permitted_value_channels": sorted(item.value for item in registration.permitted_value_channels),
        "permitted_aggregation_ops": sorted(item.value for item in registration.permitted_aggregation_ops),
        "permitted_terminal_origins": sorted(item.value for item in registration.permitted_terminal_origins),
        "row_grouping": getattr(registration.row_grouping, "value", registration.row_grouping),
        "route": {
            "type": type(route).__name__,
            "resolver_id": getattr(route, "resolver_id", None),
            "stage": getattr(route, "stage", None),
            "owner": getattr(route, "owner", None),
            "reason": getattr(route, "reason", None),
        },
    }


def _qualified_callable_name(value: object) -> str | None:
    from types import FunctionType

    if isinstance(value, FunctionType):
        return f"{value.__module__}.{value.__name__}"
    return None


def _add_import_root(root: Path) -> None:
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def _revision_is_entirely_below_floor(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    support: SupportedFilingYearsCatalogue,
) -> bool:
    """Return whether no supported filing coordinate can reach ``revision``."""
    from cadrumo.domain.calculations.registry.errors import (
        AmbiguousRevisionSelectionError,
        RegistrySnapshotError,
        RegistryValidationError,
    )
    from cadrumo.domain.calculations.registry.temporal import select_revision
    from dev.registry.maintenance_support import revision_selection_coordinates

    try:
        if revision_selection_coordinates(
            revision,
            assessment_horizon=support.horizon,
            assessment_floor=support.floor,
        ):
            return False
    except RegistryValidationError:
        return False
    return not _supported_coordinates_select_revision(
        modelo,
        revision,
        support,
        select_revision,
        AmbiguousRevisionSelectionError,
        RegistrySnapshotError,
        RegistryValidationError,
    )


def _supported_coordinates_select_revision(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    support: SupportedFilingYearsCatalogue,
    select_revision: Callable[..., Any],
    ambiguous_error: type[Exception],
    snapshot_error: type[Exception],
    validation_error: type[Exception],
) -> bool:
    for filing_year in support.years:
        for period in revision.period_selector.declared_periods:
            try:
                selected = select_revision(modelo, filing_year=filing_year, period=period, support=support)
            except ambiguous_error:
                return True
            except (snapshot_error, validation_error):
                continue
            if selected.id == revision.id:
                return True
    return False


def _support_scope(
    modelos: Sequence[ModeloDefinition],
    catalogues: RegistryCatalogues,
) -> SupportScope | None:
    support = catalogues.supported_filing_years
    if support is None:
        return None
    below_floor = frozenset(
        (str(modelo.id), str(revision_id))
        for modelo in modelos
        for revision_id, revision in modelo.revisions.items()
        if _revision_is_entirely_below_floor(modelo, revision, support)
    )
    return SupportScope(support.floor, support.horizon, support.hard_ceiling, below_floor)


def _compiled_revisions(
    root: Path,
    authored_registry_root: Path,
) -> tuple[dict[tuple[str, str], ModeloRevision], SupportScope | None, list[dict[str, object]]]:
    limitations: list[dict[str, object]] = []
    _add_import_root(root)
    try:
        from dev.registry.compiler.loader import load_registry_tree

        modelos, catalogues = load_registry_tree(authored_registry_root)
        scope = _support_scope(modelos, catalogues)
    except Exception as exc:
        limitations.append({"code": "REGISTRY_LOADER_FAILED", "message": f"{type(exc).__name__}: {exc}"})
        return {}, None, limitations
    if scope is None:
        limitations.append(
            {
                "code": "SUPPORT_ENVELOPE_UNAVAILABLE",
                "message": "registry catalogues declare no supported filing years; no revision is scoped out",
            }
        )
    result = {
        (str(modelo.id), str(revision_id)): revision
        for modelo in modelos
        for revision_id, revision in modelo.revisions.items()
    }
    return result, scope, limitations


def _runtime_resolver_inventory(
    root: Path,
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    limitations: list[dict[str, object]] = []
    _add_import_root(root)
    try:
        from cadrumo.application.modelo.calculation_route import CALCULATION_ROUTE_RESOLVER_OWNERSHIP
    except Exception as exc:
        limitations.append(
            {"code": "RUNTIME_RESOLVER_INVENTORY_IMPORT_FAILED", "message": f"{type(exc).__name__}: {exc}"}
        )
        return {}, limitations
    result: dict[str, dict[str, object]] = {}
    for row in CALCULATION_ROUTE_RESOLVER_OWNERSHIP:
        resolver_id = str(row.resolver_id)
        resolver_type = row.resolver_type
        result[resolver_id] = {
            "resolver_id": resolver_id,
            "stage": row.stage,
            "resolver_type": (
                f"{resolver_type.__module__}.{resolver_type.__name__}" if resolver_type is not None else None
            ),
            "owned_sources": sorted(str(getattr(item, "value", item)) for item in row.owned_sources),
        }
    return result, limitations
