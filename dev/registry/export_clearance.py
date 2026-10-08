"""Retire a pending export declaration after its generated source is installed."""

from dataclasses import dataclass
from pathlib import Path

import tomlkit
from tomlkit.items import Table

from cadrumo.core.atomic_write import hardened_staged_bytes_publication
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.cleared_families import ClearedFamilyCause, ClearedFamilyDeclaration
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .compiler.loader import load_modelo_directory


def remaining_export_clearances(revision: ModeloRevision) -> tuple[ClearedFamilyDeclaration, ...]:
    """Remove only the explicit pending-authoring marker, never a legal withdrawal."""
    return tuple(
        item
        for item in revision.cleared_families
        if not (item.family == "export_layouts" and item.cause is ClearedFamilyCause.NOT_AUTHORED_FOR_THIS_EDITION)
    )


@dataclass(frozen=True)
class ExportClearanceRetirement:
    """Exact source bytes for a separate, fail-closed manifest-owner write."""

    revision: str
    before: bytes
    after: bytes

    def install(self, modelo_root: Path) -> None:
        """Retire only the captured declaration after its export is present."""
        path = modelo_root / "revisions" / self.revision / "revision.toml"
        if is_link_like(path) or is_link_like(path.parent) or path.read_bytes() != self.before:
            raise RegistryValidationError("export clearance manifest changed before retirement")
        revision = load_modelo_directory(modelo_root).revisions[self.revision]
        if len(revision.export_layouts) != 1:
            raise RegistryValidationError("export clearance retirement requires the installed export")
        with hardened_staged_bytes_publication(path, self.after) as staged:
            if path.read_bytes() != self.before:
                raise RegistryValidationError("export clearance manifest changed during retirement")
            staged.publish()


def prepare_export_clearance_retirement(modelo_root: Path, revision_id: str) -> ExportClearanceRetirement | None:
    """Prepare a formatting-preserving edit without writing source or promoting authority."""
    revision = load_modelo_directory(modelo_root).revisions[revision_id]
    declarations = [item for item in revision.cleared_families if item.family == "export_layouts"]
    if not declarations:
        return None
    if any(item.cause is not ClearedFamilyCause.NOT_AUTHORED_FOR_THIS_EDITION for item in declarations):
        raise RegistryValidationError("cannot retire an official export withdrawal as pending authoring")
    path = modelo_root / "revisions" / revision_id / "revision.toml"
    before = path.read_bytes()
    document = tomlkit.parse(before.decode("utf-8"))
    revisions = document["revisions"]
    if not isinstance(revisions, Table) or not isinstance(table := revisions[revision_id], Table):
        raise RegistryValidationError("export clearance retirement requires a revision table")
    remaining = remaining_export_clearances(revision)
    if remaining:
        table["cleared_families"] = [item.model_dump(mode="json") for item in remaining]
    else:
        del table["cleared_families"]
    return ExportClearanceRetirement(revision_id, before, tomlkit.dumps(document).encode("utf-8"))
