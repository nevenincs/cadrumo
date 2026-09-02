"""Re-render one modelo revision from its authored inputs and compare it to the shipped tree.

The generation pipeline can render, validate, publish and check, but until now
only tests assembled the inputs for a real modelo, and they did it with isolated
fixtures. There was no supported way to ask whether the shipped export tree of a
given revision still matches what its authored inputs produce, which meant a
change to a semantic map or a render profile could not be verified without
hand-driving the generator.

That gap is not academic. A monetary field in a revision currently in force is
emitted at the wrong magnitude, its root cause is proven and its corrected value
is stated in the official design, and the correction is still unmade because
nothing regenerates one revision from its inputs.

This module closes the read-only half of that gap. It renders into a temporary
directory and compares bytes against the committed tree. It never writes into
the registry, so it is safe to run against filing data: publishing remains the
pipeline's own concern and is deliberately not exposed here.

Everything the renderer needs is derived from the validated authority rather than
declared in a table: the layout and its transport shape from the revision's own
export layout, the record design and its epoch from the revision's sources, and
the filing year from the window the revision declares. A revision that carries no
generated layout is refused by name rather than guessed at.

Both outcomes are trustworthy, and that was established rather than assumed. The
derivation was run across every published generated tree and its verdict compared
with the reference implementation the test suite drives: twenty-one reproduce
exactly, four differ only in their provenance attestation, and two differ in a
record file. The two verdicts agree on all twenty-seven.

An earlier revision of this module warned that a difference was inconclusive,
because a modelo whose records repeat over binding rows re-rendered without that
repeat and the loss was read as this module's incompleteness. The sweep showed
otherwise: that modelo is the only one exhibiting it, the reference
implementation reports the same record file, and the official design says the
record must repeat. The missing repeat is a real defect in what the current
inputs produce, not a gap in this comparison, and the caveat was excusing it.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.ids import SourceRefId
from cadrumo.domain.calculations.registry.static_inspection import GeneratedArtifactSource, RegistryRevisionInspection

from ._export_tree import ExportTreeTransportProfile, render_complete_export_tree
from ._record_design_ir import load_record_design_intermediate
from ._render_profile import load_render_profile, load_render_profile_source_evidence
from ._semantic_map_join import join_record_design_semantics
from ._semantic_map_loader import load_semantic_map

__all__ = ["RenderComparison", "compare_revision_against_committed"]

_SERIALIZER_CONVENTION = "rtoml-pretty-v1"

#: The generation manifest attests which inputs produced the tree, so it changes
#: whenever an input or the generator does. A tree differing ONLY here ships
#: correct records with a stale attestation; a tree differing in a record file
#: ships bytes its inputs no longer produce. The two need different remedies and
#: are reported separately.
_PROVENANCE_MANIFEST = "_generation.provenance.json"
_AUTHORED_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class RenderComparison:
    """The outcome of re-rendering one revision and diffing it against the shipped tree."""

    modelo: str
    revision: str
    layout_id: str
    files_compared: int
    differing: tuple[str, ...]
    only_committed: tuple[str, ...]
    only_rendered: tuple[str, ...]
    serialization_only: tuple[str, ...] = ()

    @property
    def byte_differing(self) -> tuple[str, ...]:
        """Every file whose bytes differ, whatever the difference means."""
        return self.differing

    @property
    def record_differing(self) -> tuple[str, ...]:
        """Records whose parsed meaning differs, not merely their spelling.

        A file whose bytes changed but whose parsed content did not is excluded.
        The serializer decides quoting, key order and whitespace, and none of
        those reach the emitted filing bytes; treating them as drift fills the
        class that exists to stop an unsafe republication with members that are
        perfectly safe, which is how a real one stops being noticed.
        """
        excluded = {_PROVENANCE_MANIFEST, *self.serialization_only}
        return tuple(name for name in self.differing if name not in excluded)

    @property
    def provenance_only(self) -> bool:
        """Whether the tree differs solely in its generation manifest.

        True only when the manifest is the single differing file. A tree whose
        records differ in spelling alone is also safe to republish, but it is
        not in this state and saying so would misreport which file moved; ask
        ``semantically_reproduced`` for that question.
        """
        return tuple(self.differing) == (_PROVENANCE_MANIFEST,) and not (self.only_committed or self.only_rendered)

    @property
    def semantically_reproduced(self) -> bool:
        """Whether every shipped record still means what its inputs produce.

        Weaker than ``reproduced`` and deliberately so: it tolerates a
        serializer change, which cannot reach the emitted filing bytes, while
        still refusing a changed value.
        """
        return not (self.record_differing or self.only_committed or self.only_rendered)

    @property
    def disposition_class(self) -> str | None:
        """Which explained state this tree is in, or ``None`` when it needs no row.

        Three outcomes, and the third is why this exists. A record that means
        something its inputs no longer produce is ``record_drift`` and is unsafe
        to republish. A stale attestation over correct records is
        ``provenance_only`` and is safe. A tree differing only in how the
        serializer spells a value is in neither state: nothing about it is
        unexplained, and demanding a written disposition for it would bury the
        rows that describe a real condition.
        """
        if self.record_differing or self.only_committed or self.only_rendered:
            return "record_drift"
        if _PROVENANCE_MANIFEST in self.differing:
            return "provenance_only"
        return None

    @property
    def reproduced(self) -> bool:
        """Whether the shipped tree is exactly what this derivation re-renders.

        True is conclusive: the tree matches its authored inputs. False is not,
        because this derivation is known to be incomplete for some revisions,
        so it means unreproduced rather than drifted.
        """
        return not (self.differing or self.only_committed or self.only_rendered)


def _parsed(name: str, raw: bytes) -> object | None:
    """Return the parsed content of a tree file, or ``None`` when it does not parse.

    Returning ``None`` matters: an unparseable file must never compare equal to
    another, or a corrupted record would be excused as a spelling change.
    """
    try:
        text = raw.decode("utf-8")
        if name.endswith(".toml"):
            return rtoml.loads(text)
        if name.endswith(".json"):
            return json.loads(text)
    except (UnicodeDecodeError, ValueError):
        return None
    return None


def _tree_bytes(root: Path) -> dict[str, bytes]:
    """Return every file under ``root`` keyed by its path relative to it."""
    return {
        str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def compare_revision_against_committed(
    authority: ValidatedRegistryAuthority, *, modelo: str, revision: str
) -> RenderComparison:
    """Re-render one revision from its authored inputs and diff it against the shipped tree.

    Raises:
        ValueError: If the revision declares no generated export layout, or no
            record-design source, or its authored inputs are absent. Each is
            reported by name rather than substituted, because a silent fallback
            would compare the wrong thing and report a match.
    """
    definition = authority.modelo(modelo)
    if revision not in definition.revisions:
        raise ValueError(f"modelo {modelo} declares no revision {revision!r}")
    selected = definition.revisions[revision]
    if not selected.export_layouts:
        raise ValueError(f"{modelo}/{revision} declares no export layout to render")
    layout = selected.export_layouts[0]

    sources = authority.catalogues.sources
    design_refs = [
        ref
        for ref in selected.source_refs
        if (source := sources.get(ref)) is not None
        and source.kind == "record_design"
        and source.record_design_epoch is not None
    ]
    if not design_refs:
        raise ValueError(f"{modelo}/{revision} cites no record-design source to render from")
    source_ref = design_refs[0]
    epoch = sources[source_ref].record_design_epoch
    if epoch is None:  # pragma: no cover - filtered above, restated for the type checker
        raise ValueError(f"source {source_ref} declares no design epoch")

    semantic_root = _AUTHORED_ROOT / "mappings" / f"modelo_{modelo}" / epoch
    profile_root = _AUTHORED_ROOT / "render_profiles" / f"modelo_{modelo}" / epoch
    for root in (semantic_root, profile_root):
        if not root.is_dir():
            raise ValueError(f"{modelo}/{revision} has no authored inputs at {root}")

    semantic_map = load_semantic_map(semantic_root)
    render_profile = load_render_profile(profile_root)
    # Each SourceReference satisfies the GeneratedArtifactSource protocol the
    # loader declares; only Mapping invariance blocks passing the catalogue
    # directly, so the boundary is rebuilt rather than cast.
    design_sources: Mapping[SourceRefId, GeneratedArtifactSource] = dict(sources)
    intermediate = load_record_design_intermediate(
        bundled_path(),
        design_sources,
        source_ref=source_ref,
        filing_year=selected.valid_from.year,
        design_epoch=epoch,
    )
    inspection = RegistryRevisionInspection.from_revision(
        modelo=definition,
        revision=selected,
        source_root=bundled_path(),
        sources=sources,
        legal_ref_ids=frozenset(authority.catalogues.legal),
    )
    joined = join_record_design_semantics(semantic_map, intermediate, inspection)
    evidence = load_render_profile_source_evidence(bundled_path() / sources[source_ref].corpus_path, render_profile)
    transport = ExportTreeTransportProfile(
        modelo=modelo,
        design_epoch=epoch,
        source_ref=source_ref,
        source_sha256=intermediate.source.source_sha256,
        layout_id=str(layout.id),
        format="fixed_width",
        encoding=ExportEncoding.ISO_8859_1,
        line_ending=layout.records[0].line_ending,
        serializer_convention=_SERIALIZER_CONVENTION,
    )

    committed_root = bundled_path("registry", "aeat", "modelos", modelo, "revisions", revision, "export")
    committed = _tree_bytes(committed_root)
    with tempfile.TemporaryDirectory(prefix="cadrumo-render-check-") as scratch:
        target = Path(scratch) / "export"
        render_complete_export_tree(
            target,
            revision_id=selected.id,
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=transport,
            render_profile=render_profile,
            render_profile_source_evidence=evidence,
        )
        rendered = _tree_bytes(target)

    shared = sorted(set(committed) & set(rendered))
    differing = tuple(name for name in shared if committed[name] != rendered[name])
    serialization_only = tuple(
        name
        for name in differing
        if name != _PROVENANCE_MANIFEST
        and (parsed := _parsed(name, committed[name])) is not None
        and parsed == _parsed(name, rendered[name])
    )
    return RenderComparison(
        modelo=modelo,
        revision=revision,
        layout_id=str(layout.id),
        files_compared=len(shared),
        differing=differing,
        serialization_only=serialization_only,
        only_committed=tuple(sorted(set(committed) - set(rendered))),
        only_rendered=tuple(sorted(set(rendered) - set(committed))),
    )


def main(argv: list[str] | None = None) -> int:
    """Compare one revision and report; exit non-zero only under ``--check``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("modelo")
    parser.add_argument("revision")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when the shipped tree is not reproduced (a difference is inconclusive)",
    )
    args = parser.parse_args(argv)

    comparison = compare_revision_against_committed(bundled_authority(), modelo=args.modelo, revision=args.revision)
    for name in comparison.differing:
        sys.stdout.write(f"render_check differs file={name}\n")
    for name in comparison.only_committed:
        sys.stdout.write(f"render_check only_committed file={name}\n")
    for name in comparison.only_rendered:
        sys.stdout.write(f"render_check only_rendered file={name}\n")
    sys.stdout.write(
        f"summary modelo={comparison.modelo} revision={comparison.revision} "
        f"layout={comparison.layout_id} compared={comparison.files_compared} "
        f"reproduced={comparison.reproduced} "
        f"record_drift={len(comparison.record_differing)} "
        f"serialization_only={len(comparison.serialization_only)} "
        f"semantically_reproduced={comparison.semantically_reproduced} "
        f"provenance_only={comparison.provenance_only} "
        f"note='record_drift means a record now MEANS what its inputs do not produce'\n"
    )
    return 1 if args.check and not comparison.reproduced else 0


if __name__ == "__main__":
    raise SystemExit(main())
