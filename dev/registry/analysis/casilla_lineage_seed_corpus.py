"""Compile lineage-seeding input one modelo at a time and preserve local failures."""

from __future__ import annotations

from collections.abc import Iterable

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.loader import load_modelo_directory
from ..compiler.loader_cache import ModeloSource
from .casilla_lineage_seed_paths import _REPO_ROOT
from .casilla_lineage_seed_types import ModeloLoadFailure

_RECORDED_REASON_LIMIT = 512


def load_corpus(
    sources: Iterable[ModeloSource],
) -> tuple[dict[str, ModeloDefinition], tuple[ModeloLoadFailure, ...]]:
    """Compile each modelo on its own, so one that cannot load stops only itself.

    The whole-corpus authority refuses the entire corpus when any single modelo
    fails, which would stop seeding all fifty-eight modelos for a defect in one
    -- including a modelo this seeder is excluded from writing and never reads
    a chain from. Loading per directory keeps the blast radius at the modelo:
    the one that fails is returned as a :class:`ModeloLoadFailure` and every
    other modelo is planned exactly as before.

    Only :class:`RegistryLoadError` is caught. It is the loader's own boundary
    type: a malformed manifest, an unreadable fragment, a schema violation and
    an ambiguous delta-edition merge all arrive as one. Anything else is a
    defect in this tooling and must not be recorded as a data failure.
    """
    loaded: dict[str, ModeloDefinition] = {}
    failures: list[ModeloLoadFailure] = []
    for source in sources:
        try:
            loaded[source.modelo_id] = load_modelo_directory(source.path)
        except RegistryLoadError as error:
            failures.append(ModeloLoadFailure(source.modelo_id, _recorded_reason(str(error))))
    return loaded, tuple(failures)


def _recorded_reason(message: str) -> str:
    """The first line of a loader message, made fit to commit in the ledger.

    The loader names the directory it refused by resolved absolute path, which
    would put one machine's checkout location into a shared artifact and make
    the ledger differ per machine. The repository prefix is dropped and the
    remaining separators are written the one way, so two checkouts of the same
    tree record the same reason. The result is bounded like any other recorded
    reason.
    """
    text = next((line.strip() for line in message.splitlines() if line.strip()), "")
    root = str(_REPO_ROOT.resolve())
    for prefix in (f"{root}\\", f"{root}/", root):
        text = text.replace(prefix, "")
    text = text.replace("\\", "/")
    return text if len(text) <= _RECORDED_REASON_LIMIT else text[: _RECORDED_REASON_LIMIT - 3] + "..."
