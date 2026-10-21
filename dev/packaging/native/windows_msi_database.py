"""Read actual Windows Installer action sequencing without executing a package."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path


def _table_rows(artifact: Path, query: str, columns: int) -> list[tuple[str, ...]]:
    """Query the MSI database in read-only mode, closing every native handle."""
    if sys.platform != "win32":
        raise ValueError("MSI database verification requires a native Windows host")
    msi = ctypes.WinDLL("msi.dll", winmode=0x00000800)  # LOAD_LIBRARY_SEARCH_SYSTEM32
    handle = ctypes.c_uint32
    definitions = {
        "MsiOpenDatabaseW": ([ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.POINTER(handle)], handle),
        "MsiDatabaseOpenViewW": ([handle, ctypes.c_wchar_p, ctypes.POINTER(handle)], handle),
        "MsiViewExecute": ([handle, handle], handle),
        "MsiViewFetch": ([handle, ctypes.POINTER(handle)], handle),
        "MsiRecordGetStringW": ([handle, handle, ctypes.c_wchar_p, ctypes.POINTER(handle)], handle),
        "MsiRecordGetInteger": ([handle, handle], ctypes.c_int32),
        "MsiCloseHandle": ([handle], handle),
    }
    for name, (arguments, result) in definitions.items():
        function = getattr(msi, name)
        function.argtypes = arguments
        function.restype = result

    def check(status: int) -> None:
        if status:
            raise ValueError(f"Windows Installer read-only database query failed: {status}")

    database = handle()
    # MSIDBOPEN_READONLY is the null pointer; no install session is created.
    check(msi.MsiOpenDatabaseW(str(artifact.resolve(strict=True)), None, ctypes.byref(database)))
    try:
        view = handle()
        check(msi.MsiDatabaseOpenViewW(database, query, ctypes.byref(view)))
        try:
            check(msi.MsiViewExecute(view, 0))
            rows: list[tuple[str, ...]] = []
            while True:
                record = handle()
                status = msi.MsiViewFetch(view, ctypes.byref(record))
                if status == 259:  # ERROR_NO_MORE_ITEMS
                    return rows
                check(status)
                try:
                    values = []
                    for column in range(1, columns + 1):
                        size = handle(4096)
                        value = ctypes.create_unicode_buffer(size.value)
                        check(msi.MsiRecordGetStringW(record, column, value, ctypes.byref(size)))
                        values.append(value.value)
                    rows.append(tuple(values))
                finally:
                    msi.MsiCloseHandle(record)
        finally:
            msi.MsiCloseHandle(view)
    finally:
        msi.MsiCloseHandle(database)


def _sequence_rows(artifact: Path) -> dict[str, tuple[int, str]]:
    return {
        action: (int(sequence), condition)
        for action, sequence, condition in _table_rows(
            artifact, "SELECT `Action`, `Sequence`, `Condition` FROM `InstallExecuteSequence`", 3
        )
    }


def _verify_feature_rows(
    features: list[tuple[str, ...]], components: list[tuple[str, ...]], links: list[tuple[str, ...]]
) -> None:
    """Require complete, mandatory local feature ownership in the actual tables."""
    tree = {row[0]: row[1:] for row in features}
    owned = {row[0] for row in components}
    if not tree or len(tree) != len(features) or not owned or len(owned) != len(components):
        raise ValueError("MSI feature/component inventory is incomplete")
    counts = dict.fromkeys(tree, 0)
    enrolled: set[str] = set()
    for feature, component in links:
        if feature not in tree or component not in owned or component in enrolled:
            raise ValueError("MSI feature component ownership is unknown or repeated")
        enrolled.add(component)
        counts[feature] += 1
        if counts[feature] > 1600:
            raise ValueError("MSI feature exceeds 1600 components")
    if enrolled != owned:
        raise ValueError("MSI components are detached from mandatory features")
    combined = "VersionFiles" in tree and "SharedRegistration" in tree and "ProductFeature" not in tree
    for name, (parent, display, level, attributes) in tree.items():
        expected = ("10" if parent else "8") if combined else ("26" if parent else "24")
        if display not in {"", "0"} or level != "1" or attributes != expected:
            raise ValueError("MSI feature can be deselected or installed outside local storage")
        visited = {name}
        while parent:
            if parent not in tree or parent in visited or len(visited) >= 16:
                raise ValueError("MSI feature parent inventory is unknown or cyclic")
            visited.add(parent)
            parent = tree[parent][0]
        roots = {"VersionFiles", "SharedRegistration"} if combined else {"ProductFeature"}
        if not any(root in visited and not tree[root][0] for root in roots):
            raise ValueError("MSI feature is detached from the mandatory product root")


def _verify_component_rows(components: list[tuple[str, ...]], registry: list[tuple[str, ...]]) -> None:
    """Reserve one costing entry per registry keypath in addition to authored components."""
    keys = {row[0]: row[1:] for row in registry}
    if len(keys) != len(registry) or len({row[0] for row in components}) != len(components):
        raise ValueError("MSI component keypath inventory is repeated")
    costed = len(components)
    for component, attributes, keypath in components:
        if not attributes.isdigit() or int(attributes) > 65535:
            raise ValueError("MSI component attributes are invalid")
        if int(attributes) & 4:
            if (
                keypath not in keys
                or keys[keypath][1] != component
                or keys[keypath][0] not in {"-1", "0", "1", "2", "3"}
            ):
                raise ValueError("MSI component registry keypath ownership is invalid")
            costed += 1
    if costed > 65535:
        raise ValueError("MSI component costing budget exceeds 65535 entries")


def verify_feature_ownership(artifact: Path) -> None:
    """Reject oversized or unselected actual MSI features before publication."""
    components = _table_rows(artifact, "SELECT `Component`, `Attributes`, `KeyPath` FROM `Component`", 3)
    tables = {row[0] for row in _table_rows(artifact, "SELECT `Name` FROM `_Tables`", 1)}
    _verify_component_rows(
        components,
        _table_rows(artifact, "SELECT `Registry`, `Root`, `Component_` FROM `Registry`", 3)
        if "Registry" in tables
        else [],
    )
    _verify_feature_rows(
        _table_rows(artifact, "SELECT `Feature`, `Feature_Parent`, `Display`, `Level`, `Attributes` FROM `Feature`", 5),
        [(row[0],) for row in components],
        _table_rows(artifact, "SELECT `Feature_`, `Component_` FROM `FeatureComponents`", 2),
    )
    if "Condition" in tables and _table_rows(artifact, "SELECT `Feature_` FROM `Condition`", 1):
        raise ValueError("MSI mandatory feature selection can be changed by a condition")
    levels = _table_rows(artifact, "SELECT `Value` FROM `Property` WHERE `Property` = 'INSTALLLEVEL'", 1)
    if any(not row[0].isdigit() or int(row[0]) < 1 for row in levels):
        raise ValueError("MSI installation level disables mandatory features")


def action_sequence(artifact: Path) -> dict[str, int]:
    """Project the actual database's action ordering without executing installation."""
    return {name: row[0] for name, row in _sequence_rows(artifact).items()}


def verify_upgrade_order(artifact: Path, *, version_product: bool) -> None:
    """Require immutable versions and transactional registration upgrade ordering."""
    sequence = action_sequence(artifact)
    if version_product:
        if "RemoveExistingProducts" in sequence:
            raise ValueError("Version MSI schedules removal of another product")
    elif not (
        0
        < sequence.get("InstallExecute", 0)
        < sequence.get("RemoveExistingProducts", 0)
        < sequence.get("InstallFinalize", 0)
    ):
        raise ValueError(f"Registration MSI lost its transactional upgrade order: {sequence}")


def verify_admission_order(artifact: Path, *, owner_required: bool = False) -> None:
    """Prove scoped admission runs in the execute transaction before file ownership changes."""
    rows = _sequence_rows(artifact)
    sequence = {name: row[0] for name, row in rows.items()}
    if "CadrumoScopeAdmissionUser" in sequence:
        if not (
            0
            < sequence.get("CostFinalize", 0)
            < sequence.get("CadrumoPrepareAdmission", 0)
            < sequence.get("InstallInitialize", 0)
            < sequence.get("ProcessComponents", 0)
            < sequence.get("InstallFiles", 0)
        ):
            raise ValueError("Scope-aware MSI admission has unsafe action ordering")
        for suffix, condition in (("User", "NOT ALLUSERS"), ("Machine", 'ALLUSERS = "1"')):
            admission = "CadrumoScopeAdmission" + suffix
            if not sequence["InstallInitialize"] < sequence.get(admission, 0) < sequence["ProcessComponents"]:
                raise ValueError("Scope-aware MSI admission runs outside the transaction")
            if rows[admission][1] != f"({condition}) AND NOT REMOVE":
                raise ValueError("Scope-aware MSI admission has an unrecognized scope condition")
            if owner_required or "CadrumoAuthenticateOwner" + suffix in sequence:
                authenticate = "CadrumoAuthenticateOwner" + suffix
                if not (
                    sequence["CostFinalize"]
                    < sequence.get("CadrumoPrepareOwner", 0)
                    < sequence["CadrumoPrepareAdmission"]
                    and sequence[admission] < sequence.get(authenticate, 0) < sequence["ProcessComponents"]
                ):
                    raise ValueError("Scope-aware MSI owner authentication has unsafe ordering")
                if rows["CadrumoPrepareOwner"][1] or rows[authenticate][1] != condition:
                    raise ValueError("Scope-aware MSI owner authentication can be bypassed")
        return
    if not (
        0
        < sequence.get("CostFinalize", 0)
        < sequence.get("CadrumoPrepareAdmission", 0)
        < sequence.get("InstallInitialize", 0)
        < sequence.get("CadrumoScopeAdmission", 0)
        < sequence.get("ProcessComponents", 0)
        < sequence.get("InstallFiles", 0)
    ):
        raise ValueError(f"MSI native scope admission has unsafe action ordering: {sequence}")
    owner_required = owner_required or "CadrumoAuthenticateOwner" in sequence
    if owner_required and not (
        sequence["CostFinalize"] < sequence.get("CadrumoPrepareOwner", 0) < sequence["CadrumoPrepareAdmission"]
        and sequence["CadrumoScopeAdmission"]
        < sequence.get("CadrumoAuthenticateOwner", 0)
        < sequence["ProcessComponents"]
    ):
        raise ValueError(f"MSI native owner authentication has unsafe action ordering: {sequence}")
    if owner_required and any(
        rows.get(name, (0, "missing"))[1]
        for name in (
            "CadrumoPrepareOwner",
            "CadrumoAuthenticateOwner",
        )
    ):
        raise ValueError("MSI native owner authentication can be skipped by a condition")
