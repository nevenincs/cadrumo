"""Gate: a persistence surface a product command reads must have a production writer.

Wires :mod:`dev.audit.write_path_coverage` into the pytest/CI surface.

The defect this protects against is invisible to every other gate in the
repository, including the reachability audit it is built on. A snapshot store
whose last producer was deleted is still perfectly *reachable*: the service
class, its payload models, its storage namespace, and the CLI commands that
read it all remain imported, typed, and tested. What is gone is the DATA path,
and the product ships list/show/latest commands over a namespace nothing can
fill. That has happened twice here.

Because the failure mode of such a gate is silence, the detector's teeth are
proven in the same run as its normal path. The synthetic tree below plants one
service with a reachable reader and no production writer and asserts it is
reported; the control adds the writer to the SAME tree and asserts the report
goes empty. A third case plants an unrelated class with an identically named
``capture`` method and asserts it does NOT clear the stranded surface, which is
the false-clear this audit's two-sided caller binding exists to prevent.

The plants are built in a throwaway ``tmp_path`` tree from outside the
repository. No production module is monkeypatched and the contributor's working
tree is never mutated, so a crashed run leaves no residue.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..audit.unreachable_code import EntryPoint, ShippedTreeSpec
from ..audit.write_path_coverage import (
    PersistenceSurfaceSpec,
    WritePathOutcome,
    run_write_path_scan,
    scan_write_path_coverage,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_EXCLUDES = ("src/pkg/tests", "src/pkg/tests/**", "src/pkg/**/tests", "src/pkg/**/tests/**")

_SURFACE = PersistenceSurfaceSpec(base_module="pkg.snapshot_base", base_classes=("SnapshotService",))

_BASE = '''"""Lifecycle base for bucket-scoped snapshot services."""

from __future__ import annotations


class SnapshotService:
    """Template base: the write half persists, the read half consumes."""

    def __init__(self, repository: object) -> None:
        self._repository = repository

    def _capture_with_lifecycle(self, payload: object) -> object:
        self._repository.save(payload)
        return payload

    def list_snapshots(self) -> tuple[object, ...]:
        return self._repository.list_snapshots()

    def resolve_snapshot(self, snapshot_id: str) -> object:
        return self._repository.resolve(snapshot_id)
'''

_SERVICE = '''"""The persistence surface under audit."""

from __future__ import annotations

from .snapshot_base import SnapshotService


class LedgerService(SnapshotService):
    """Reads through list/show; fills the store through capture."""

    def capture(self, payload: object) -> object:
        return self._capture_with_lifecycle(payload)

    def show(self, snapshot_id: str) -> object:
        return self.resolve_snapshot(snapshot_id)
'''

_READER = '''"""A product command that reads the store."""

from __future__ import annotations

from .store import LedgerService


def ledger_list(repository: object) -> tuple[object, ...]:
    return LedgerService(repository).list_snapshots()


def ledger_show(repository: object, snapshot_id: str) -> object:
    return LedgerService(repository).show(snapshot_id)
'''

_WRITER = '''"""The producer that fills the store."""

from __future__ import annotations

from .store import LedgerService


def ledger_import(repository: object, payload: object) -> object:
    return LedgerService(repository).capture(payload)
'''

#: An unrelated class whose method happens to be spelled ``capture`` too. A
#: detector that searched the tree for the verb alone would clear the stranded
#: surface on the strength of this module.
_NAMESAKE = '''"""A different subject that also has a capture verb."""

from __future__ import annotations


class TelemetrySink:
    def capture(self, event: object) -> None:
        self._events = event


def record(event: object) -> None:
    TelemetrySink().capture(event)
'''


def _write(root: Path, relative: str, text: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _planted_tree(root: Path, *, with_writer: bool, with_namesake: bool = False) -> ShippedTreeSpec:
    """A package whose console script reaches the reader, and the writer only on request."""
    imports = ["from . import reader"]
    if with_writer:
        imports.append("from . import writer")
    if with_namesake:
        imports.append("from . import telemetry")
    _write(root, "src/pkg/__init__.py")
    _write(root, "src/pkg/cli.py", "\n".join(imports) + "\n\n\ndef main() -> None:\n    del reader\n")
    _write(root, "src/pkg/snapshot_base.py", _BASE)
    _write(root, "src/pkg/store.py", _SERVICE)
    _write(root, "src/pkg/reader.py", _READER)
    if with_writer:
        _write(root, "src/pkg/writer.py", _WRITER)
    if with_namesake:
        _write(root, "src/pkg/telemetry.py", _NAMESAKE)
    return ShippedTreeSpec(
        repo_root=root,
        src_root=root / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.cli", "main"),),
        exclude_globs=_EXCLUDES,
    )


def test_a_readable_surface_with_no_production_writer_is_reported(tmp_path: Path) -> None:
    """The teeth. A store the CLI reads and nothing fills is named, with its verbs."""
    spec = _planted_tree(tmp_path, with_writer=False)

    result = scan_write_path_coverage(spec, _SURFACE)

    assert result.outcome is WritePathOutcome.FINDINGS, result.headline()
    assert [finding.id for finding in result.findings] == ["write-path:pkg.store:LedgerService"]
    finding = result.findings[0]
    assert finding.write_verbs == ("capture",)
    assert "list_snapshots" in finding.read_verbs
    assert finding.read_callers == ("pkg.reader",)


def test_the_same_surface_with_a_production_writer_is_not_reported(tmp_path: Path) -> None:
    """The control. One module calling ``capture`` clears the identical surface.

    Without this, the assertion above would pass just as happily if the audit
    reported every surface it could see.
    """
    spec = _planted_tree(tmp_path, with_writer=True)

    result = scan_write_path_coverage(spec, _SURFACE)

    assert result.is_green, result.headline()
    assert result.findings == ()
    assert "pkg.store:LedgerService" in result.surfaces_examined


def test_an_unrelated_namesake_verb_does_not_clear_the_stranded_surface(tmp_path: Path) -> None:
    """The precision case: ``capture`` elsewhere is not a writer for THIS store.

    A detector that matched the verb name alone would report the tree clean
    here, which is exactly how such a gate becomes a rubber stamp.
    """
    spec = _planted_tree(tmp_path, with_writer=False, with_namesake=True)

    result = scan_write_path_coverage(spec, _SURFACE)

    assert [finding.id for finding in result.findings] == ["write-path:pkg.store:LedgerService"]


def test_a_writer_named_only_in_prose_does_not_clear_the_surface(tmp_path: Path) -> None:
    """A docstring describing ``capture`` is documentation, not a data path."""
    spec = _planted_tree(tmp_path, with_writer=False)
    _write(
        spec.repo_root,
        "src/pkg/writer.py",
        '"""Historical note: this module used to call LedgerService.capture."""\n\n'
        "from __future__ import annotations\n\n"
        "from .store import LedgerService\n\n\n"
        "def unused(repository: object) -> object:\n    return LedgerService(repository)\n",
    )

    result = scan_write_path_coverage(spec, _SURFACE)

    assert [finding.id for finding in result.findings] == ["write-path:pkg.store:LedgerService"]


def test_a_surface_nobody_reads_is_left_to_the_reachability_audit(tmp_path: Path) -> None:
    """No reader, no finding: an unread store is dead code, not a broken data path."""
    spec = _planted_tree(tmp_path, with_writer=False)
    _write(spec.repo_root, "src/pkg/cli.py", "def main() -> None:\n    return None\n")

    result = scan_write_path_coverage(spec, _SURFACE)

    assert result.is_green, result.headline()


def test_a_lost_anchor_refuses_rather_than_reporting_clean(tmp_path: Path) -> None:
    """Renaming the lifecycle base must fail loudly, not empty the scan silently.

    The dangerous failure for this audit is not a crash but a false all-clear:
    if a missing anchor produced zero surfaces, the gate would report every
    data path healthy at the moment it stopped being able to see any of them.
    """
    spec = _planted_tree(tmp_path, with_writer=False)

    result = scan_write_path_coverage(spec, PersistenceSurfaceSpec(spec.package + ".snapshot_base", ("Renamed",)))

    assert result.outcome is WritePathOutcome.ERROR
    assert not result.is_green
    assert "Renamed" in result.reason


def test_the_live_shipped_tree_write_path_coverage_is_reported_truthfully() -> None:
    """The real scan. It must produce a trustworthy verdict, never an error.

    The verdict itself is asserted against the committed backlog in
    :mod:`dev.quality.write_path_backlog`; here the only claim is that the
    scan can still see the tree, so a silent breakage of the anchor or of the
    import graph cannot masquerade as a clean data path.
    """
    result = run_write_path_scan()

    assert result.outcome is not WritePathOutcome.ERROR, result.reason
    assert result.surfaces_examined
