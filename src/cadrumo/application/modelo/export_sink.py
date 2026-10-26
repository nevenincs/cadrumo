"""The local-file sink every modelo export artefact is published through.

A modelo artefact -- the fichero-BOE, the calculation workbook, a calculation
report -- is rendered by exactly one producer per family; what differs between
them is where the bytes go. This module owns the local-file case once: the
operator's path is checked before any cleartext financial byte is written, the
bytes are staged beside it under an unguessable name that is discarded on every
exit that does not publish, and publication refuses to replace an existing file
unless the operator chose to.

The sink is deliberately a different word from the screen routes the terminal
interface calls destinations, which name pages rather than places bytes land.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel, NonNegativeInt

from ...core.atomic_write import StagedPublication, hardened_staged_publication
from ...core.hashing import sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.modelos.errors import ModeloExportError


class ModeloExportOutputPathError(ModeloExportError):
    """Raised when the operator-supplied output path cannot receive the artefact.

    Validated up front, before any artefact bytes are written, so an unusable
    destination (empty path, an existing directory, an existing file the
    operator did not choose to replace, a missing or unwritable parent
    directory) is refused with a typed, operator-facing message instead of
    surfacing a raw ``OSError`` traceback from the staged write -- and
    crucially before any cleartext financial bytes touch disk.
    """


class LocalFileExportReceipt(BaseModel):
    """The published file and the facts that identify its bytes."""

    model_config = STRICT_FROZEN_CONFIG

    path: Path
    byte_size: NonNegativeInt
    sha256: ContentDigest


class LocalFileExportSink(BaseModel):
    """An operator-chosen file an export artefact is published to.

    ``replace_existing`` is the operator's explicit choice to replace a file
    already at ``path``; without it an existing file is refused, both when the
    sink is checked and again, atomically, at publication.
    """

    model_config = STRICT_FROZEN_CONFIG

    path: Path
    replace_existing: bool = False

    def require_writable(self) -> None:
        """Refuse an unusable path before any artefact byte is written.

        Raises:
            ModeloExportOutputPathError: When the path is empty, names an
                existing directory, names an existing file the operator did not
                choose to replace, or its parent directory is missing or not a
                directory.
        """
        raw = str(self.path).strip()
        if not raw or raw == ".":
            raise _path_refusal(raw or "(empty)", "path is empty")
        if self.path.is_dir():
            raise _path_refusal(str(self.path), "path is an existing directory")
        if self.path.exists() and not self.replace_existing:
            raise _path_refusal(str(self.path), "path is an existing file")
        parent = self.path.parent
        if not parent.exists():
            raise _path_refusal(str(self.path), "parent directory does not exist")
        if not parent.is_dir():
            raise _path_refusal(str(self.path), "parent path is not a directory")

    @contextmanager
    def staged(self) -> Generator[StagedPublication]:
        """Check the path, then reserve the staging file a producer writes into.

        The staged file is discarded on every exit that does not reach
        :meth:`publish`, so a refusal or interrupt between the write and the
        publication never strands cleartext bytes beside the chosen path.
        """
        self.require_writable()
        with hardened_staged_publication(self.path) as staged:
            yield staged

    def publish(self, staged: StagedPublication) -> None:
        """Move the staged bytes onto the path, honouring the replace choice.

        A file that appeared after :meth:`require_writable` ran, or a
        publication that fails for any other reason, is translated into the
        same typed refusal the up-front check raises.

        Raises:
            ModeloExportOutputPathError: When the path became occupied or the
                publication failed.
        """
        try:
            staged.publish(replace_existing=self.replace_existing)
        except FileExistsError as exc:
            raise _path_refusal(str(self.path), "path is an existing file") from exc
        except OSError as exc:
            raise _path_refusal(str(self.path), str(exc)) from exc

    def write(self, payload: bytes) -> LocalFileExportReceipt:
        """Publish an in-memory artefact and return the facts of the landed file."""
        with self.staged() as staged:
            with staged.path.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            self.publish(staged)
        return LocalFileExportReceipt(
            path=self.path,
            byte_size=len(payload),
            sha256=sha256_hex(payload),
        )


def _path_refusal(output_path: str, reason: str) -> ModeloExportOutputPathError:
    return ModeloExportOutputPathError(
        translated_message="application.modelo.errors.export_output_path_invalid",
        context={"output_path": output_path, "reason": reason},
    )


__all__ = ["LocalFileExportReceipt", "LocalFileExportSink", "ModeloExportOutputPathError"]
