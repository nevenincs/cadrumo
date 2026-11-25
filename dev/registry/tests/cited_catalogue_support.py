"""Install the legal and source catalogue entries an isolated registry tree cites."""

from __future__ import annotations

import shutil
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import freeze_toml, render_toml

from ..compiler.authority import compiled_bundled_authority
from ..compiler.corpus_catalogue import record_design_manifest_path


def install_cited_catalogue_entries(root: Path) -> None:
    """Carry the legal and source entries the installed inputs cite, with their corpus files.

    The closure is read from the installed files themselves, so an input that
    starts citing another provision brings that provision along instead of
    this helper restating a list.
    """
    catalogues = compiled_bundled_authority().catalogues
    installed_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "registry").rglob("*.toml") if path.is_file()
    )
    legal = {key: entry for key, entry in catalogues.legal.items() if f'"{key}"' in installed_text}
    sources = {key: entry for key, entry in catalogues.sources.items() if f'"{key}"' in installed_text}
    document: dict[str, object] = {
        "legal": {key: entry.model_dump(exclude_none=True, exclude={"id"}) for key, entry in legal.items()},
        "sources": {key: entry.model_dump(exclude_none=True, exclude={"id"}) for key, entry in sources.items()},
    }
    legal_dir = root / "registry" / "aeat" / "legal"
    legal_dir.mkdir(parents=True, exist_ok=True)
    (legal_dir / "cited-inputs.toml").write_text(render_toml(freeze_toml(document)), encoding="utf-8")
    corpus_paths = {entry.corpus_ref.split("#", 1)[0] for entry in legal.values() if entry.corpus_ref}
    corpus_paths.update(entry.corpus_path for entry in sources.values() if entry.corpus_path)
    # A record design's identity is checked against its modelo's acquisition manifest, which the compiler reads.
    corpus_paths.update(
        str(manifest)
        for entry in sources.values()
        if entry.corpus_path and (manifest := record_design_manifest_path(entry.corpus_path)) is not None
    )
    for corpus_path in corpus_paths:
        bundled_file = bundled_path(*corpus_path.split("/"))
        for sibling in bundled_file.parent.glob(f"{bundled_file.name}*"):
            target = root.joinpath(*corpus_path.split("/")).with_name(sibling.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sibling, target)
