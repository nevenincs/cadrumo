"""Derive the source rows the unregistered bundled record designs are owed.

A file under ``corpus/aeat_official/disenos_registro/`` that no
``SourceReference`` names is invisible: it cannot be hash-pin verified, it
cannot be resolved by ``resolve_record_design_binary``, and no consumer of the
sources catalogue can see it exists. The standing worklist gate reports that
population; this module answers the next question, which is what closing it
would actually require.

The answer is: much less evidence work than the bare count suggests. The corpus
ingest harness already wrote a capture record for each artefact -- origin URL,
retrieval date, digest, length, and AEAT's own listing title -- so the fields a
``SourceReference`` needs are on disk and hash-verifiable, not lost. Enrolling
them is derivation from an existing record, not a fresh evidence acquisition.

THIS MODULE INSTALLS NOTHING. It reads the corpus and the catalogue and prints
a candidate. Authoring registry source rows changes what the product claims to
hold, and publication is a separate step again, so the boundary between "this
is derivable" and "this is now authority" stays where the registry flow puts
it: the operator reviews the candidate and decides.

TWO FIELDS ARE DELIBERATELY LEFT UNDECLARED.

``applies_from`` / ``applies_to`` and ``record_design_epoch`` are legal scope,
and the only thing on disk that suggests them is AEAT's listing title. A title
is a label; reading a temporal window out of one is the inference this project
refuses everywhere else. Both are optional on the model, so a row is authored
without them and a reviewer with the design open supplies the window when the
design itself states it.

The derived ``id`` does use the title's exercise, because an identifier is a
key rather than a claim -- nothing resolves law from it, and a reviewer renames
it freely before installing.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from cadrumo.core.resources.bundled_data import bundled_path

from ..compiler.loader import load_registry_tree

_DESIGN_ROOT_PARTS: Final = ("corpus", "aeat_official", "disenos_registro")
_DESIGN_SUFFIXES: Final = frozenset({".pdf", ".xls", ".xlsx", ".xlsm"})
_EXERCISE_IN_TITLE: Final = re.compile(r"ejercicio\s+(\d{4})", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DerivedSourceRow:
    """One candidate ``[sources."..."]`` row and where it would be authored."""

    source_id: str
    modelo_dir: str
    owning_toml: str
    corpus_path: str
    sha256: str
    bytes: int
    retrieved_at: str
    source_url: str
    title: str

    def as_toml(self) -> str:
        """Render the row exactly as it would be pasted into its owning file."""
        return "\n".join(
            (
                f'[sources."{self.source_id}"]',
                'evidence_tier = "layout_authority"',
                'authority = "aeat"',
                'kind = "record_design"',
                f'corpus_path = "{self.corpus_path}"',
                f'sha256 = "{self.sha256}"',
                f"bytes = {self.bytes}",
                f"retrieved_at = {self.retrieved_at}",
                f'source_url = "{self.source_url}"',
                'review_status = "pending_review"',
                f"# AEAT listing title: {self.title}",
                "# applies_from/applies_to/record_design_epoch intentionally undeclared:",
                "# supply them from the design's own stated scope, not from this title.",
            )
        )


def _capture_records(root: Path) -> Mapping[Path, Mapping[str, Any]]:
    """Index every per-modelo capture row by the artefact file it describes."""
    records: dict[Path, Mapping[str, Any]] = {}
    for manifest in root.rglob("manifest.json"):
        if manifest.parent == root:
            continue
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        for artefact in payload.get("artefacts", ()):
            records[(manifest.parent / artefact["stored_path"]).resolve()] = artefact
    return records


def _owning_toml_by_modelo_dir(registry_root: Path, registered: Mapping[str, str]) -> Mapping[str, str]:
    """Learn each modelo directory's sources home from where its rows already live.

    Derived rather than tabulated: the catalogue is organised by tax domain, not
    by modelo, and a hand-written table of that mapping would be a second home
    for a fact the tree already states.
    """
    declaring_file: dict[str, str] = {}
    for toml_path in registry_root.rglob("*.toml"):
        text = toml_path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r'\[sources\."([^"]+)"\]', text):
            declaring_file[match.group(1)] = toml_path.as_posix()
    homes: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    for source_id, corpus_path in registered.items():
        parts = corpus_path.split("/")
        if len(parts) < 4 or parts[2] != "disenos_registro":
            continue
        home = declaring_file.get(source_id)
        if home is not None:
            homes[parts[3]][home] += 1
    return {modelo_dir: max(counts, key=lambda key: counts[key]) for modelo_dir, counts in homes.items()}


def _derive_source_id(modelo_dir: str, title: str, stem: str, taken: set[str]) -> str:
    """Name the candidate row, preferring AEAT's own exercise over the stored stem."""
    modelo = modelo_dir.removeprefix("modelo_")
    exercise = _EXERCISE_IN_TITLE.search(title)
    if exercise is not None:
        candidate = f"aeat-dr-{modelo}-{exercise.group(1)}"
        if candidate not in taken:
            return candidate
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    candidate = f"aeat-dr-{modelo}-{slug}"
    suffix = 2
    while candidate in taken:
        candidate = f"aeat-dr-{modelo}-{slug}-{suffix}"
        suffix += 1
    return candidate


def derive_enrollment_candidate(
    registry_root: Path, *, bundle_root: Path
) -> tuple[tuple[DerivedSourceRow, ...], tuple[str, ...]]:
    """Return the derivable candidate rows, and the files no capture record covers.

    The second element is not a smaller version of the first. A design file with
    no ingest row was never captured by the harness that fills this corpus, so
    its origin is unknown to the repository; enrolling it would mean asserting a
    retrieval nobody recorded. It is reported separately so it cannot be swept
    into the same batch.
    """
    _, catalogues = load_registry_tree(registry_root)
    registered_paths = {source.corpus_path for source in catalogues.sources.values()}
    registered_by_id = {source.id: source.corpus_path for source in catalogues.sources.values()}
    taken = set(catalogues.sources)

    design_root = bundle_root / Path(*_DESIGN_ROOT_PARTS)
    records = _capture_records(design_root)
    homes = _owning_toml_by_modelo_dir(registry_root, registered_by_id)

    rows: list[DerivedSourceRow] = []
    uncaptured: list[str] = []
    for path in sorted(design_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _DESIGN_SUFFIXES:
            continue
        corpus_path = path.relative_to(bundle_root).as_posix()
        if corpus_path in registered_paths:
            continue
        captured = records.get(path.resolve())
        if captured is None:
            uncaptured.append(corpus_path)
            continue
        modelo_dir = corpus_path.split("/")[3]
        source_id = _derive_source_id(modelo_dir, captured.get("title", ""), path.stem, taken)
        taken.add(source_id)
        rows.append(
            DerivedSourceRow(
                source_id=source_id,
                modelo_dir=modelo_dir,
                owning_toml=homes.get(modelo_dir, "<no existing sources row for this modelo>"),
                corpus_path=corpus_path,
                sha256=captured["sha256"],
                bytes=captured["bytes"],
                retrieved_at=captured["retrieved_at"],
                source_url=captured["url"],
                title=captured.get("title", ""),
            )
        )
    return tuple(rows), tuple(uncaptured)


def _render_report(rows: Sequence[DerivedSourceRow], uncaptured: Sequence[str]) -> str:
    grouped: dict[str, list[DerivedSourceRow]] = defaultdict(list)
    for row in rows:
        grouped[row.owning_toml].append(row)
    lines = [
        f"{len(rows)} unregistered record design(s) are derivable from their capture record.",
        f"{len(uncaptured)} have no capture record and must NOT be enrolled from this data.",
        "",
    ]
    for toml_path in sorted(grouped):
        lines.append(f"# ---- {toml_path} ({len(grouped[toml_path])} row(s)) ----")
        lines.extend(row.as_toml() + "\n" for row in grouped[toml_path])
    if uncaptured:
        lines.append("# ---- no capture record: origin unknown to this repository ----")
        lines.extend(f"# {path}" for path in uncaptured)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Print the enrollment candidate. Writes nothing to the registry."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable rows instead of TOML")
    args = parser.parse_args(argv)
    bundle_root = bundled_path()
    rows, uncaptured = derive_enrollment_candidate(bundle_root / "registry" / "aeat", bundle_root=bundle_root)
    if args.json:
        print(
            json.dumps(
                {"derivable": [asdict(row) for row in rows], "uncaptured": list(uncaptured)},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(_render_report(rows, uncaptured))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
