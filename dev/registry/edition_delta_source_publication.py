"""Publish a registry modelo only after the complete source proof has passed."""

from __future__ import annotations

from pathlib import Path

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_workdir as _edition_delta_workdir

__all__ = ()


def _assert_proof_inputs_unchanged(*, live_root: Path, captured_root: Path, modelo_id: str) -> None:
    """Refuse apply when any dependency captured by the proof has changed."""
    from .source_tree_installation import fingerprint

    captured_modelos = captured_root / _edition_delta_fields._MODELOS
    for captured_modelo in captured_modelos.iterdir():
        if not captured_modelo.is_dir() or captured_modelo.name == modelo_id:
            continue
        live_modelo = live_root / _edition_delta_fields._MODELOS / captured_modelo.name
        if not live_modelo.is_dir() or fingerprint(live_modelo) != fingerprint(captured_modelo):
            raise _edition_delta_errors.MigrationRefusedError(
                f"dependency modelo {captured_modelo.name!r} changed after the source proof; apply refused"
            )


def _apply_proven_modelo(*, target: Path, staged: Path, original: Path) -> None:
    """Install one proven source tree with the shared recoverable publisher."""
    from .source_tree_installation import fingerprint, install_proven_tree

    install_proven_tree(target, staged, original, fingerprint(original))


def _validate_staged_modelo(*, staged_root: Path, modelo_id: str) -> None:
    """Hydrate the complete staged modelo immediately before live replacement."""
    _edition_delta_workdir._load(staged_root, modelo_id)
