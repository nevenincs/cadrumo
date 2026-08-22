"""The standing worklist of modelos this application cannot yet file.

THIS TEST IS EXPECTED TO FAIL, AND MUST NOT BE MADE TO PASS BY NARROWING IT.

A permanently-failing test is normally forbidden by this project's quality rules.
This one is sanctioned by explicit operator directive, and it exists because the
previous arrangement was worse: every modelo that could not emit a filing artifact
carried a decision record declaring its layout withdrawn, each individually
grounded and defensible, and nothing ever summed them. The tree stayed green while
the application quietly could not file IVA, sociedades or retenciones. Converting
"we cannot file this" into a declared, gate-satisfying state is precisely what let
that go unnoticed for the whole of the project's history.

So the absence is now loud instead of ratified. The failure message below is the
capability worklist: every modelo and revision that cannot produce a filing
artifact, sorted and counted. It goes green when, and only when, every revision in
the registry can emit -- at which point the list is empty and this test passes on
its own, with no edit.

Forbidden, without exception:

* Do not skip, xfail, or mark this test.
* Do not narrow it to a subset of modelos, add an allowlist, or excuse
  "informative" modelos.
* Do not hardcode the expected list. It is derived from the registry on every run,
  so a modelo that gains a layout leaves the list automatically and one that loses
  a layout rejoins it. A hardcoded tally would rot into a stale claim, which is the
  same failure mode in a new costume.

The one legitimate way to change this test's result is to build an export layout.

See Also:
    :func:`cadrumo.domain.calculations.registry.bundled_authority`
        Loads the registry this worklist is derived from.
    :class:`cadrumo.domain.calculations.registry.ModeloRevision`
        The revision whose ``export_layouts`` decide filing capability.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from .._export import derive_export_layouts_from_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _revisions_that_cannot_emit() -> tuple[tuple[str, str, str], ...]:
    """Return every ``(modelo, revision)`` that can produce no filing artifact.

    Capability is read exactly as the filing boundary reads it: layouts are derived
    from bindings first, so a revision declaring none inline but deriving one counts
    as capable and never appears here. That keeps this worklist and the refusal in
    :mod:`.._snapshot` from ever disagreeing about who is on the list.

    The tree is read through the compiler rather than the validated authority on
    purpose. A worklist that can only be produced when the registry is healthy is
    useless precisely when it is needed: any unrelated validation failure anywhere
    in the tree would replace this enumeration with someone else's error, and the
    list of modelos that cannot file would silently stop being reported.
    """
    modelos, catalogues = bundled_registry_tree()
    return tuple(
        sorted(
            (str(modelo.id), str(revision.id), _blocker(modelo, revision, catalogues.sources))
            for modelo in modelos
            for revision in modelo.revisions.values()
            if not derive_export_layouts_from_bindings(revision)
        ),
    )


def _bundled_designs(modelo_id: str) -> tuple[str, ...]:
    """Return the record-design files the corpus holds for one modelo."""
    directory = bundled_path("corpus", "aeat_official", "disenos_registro", f"modelo_{modelo_id}", "files")
    if not directory.is_dir():
        return ()
    return tuple(
        sorted(path.name for path in directory.iterdir() if path.suffix.lower() in {".pdf", ".xls", ".xlsx"})
    )


def _blocker(modelo: object, revision: object, sources: object) -> str:
    """Return what this revision actually needs before a layout can be authored.

    Derived on every run, never listed. The bare worklist said only "no export
    layout" for every line, which reads as one backlog of one kind of work. It
    is three. A revision whose modelo has no bundled design cannot be authored
    at all until the corpus carries one. A revision whose designs are bundled
    but unregistered needs the era each governs grounded first, and that is not
    mechanical: a design may state no orden, no BOE reference and no ejercicio
    anywhere in its text, leaving only AEAT's update date, which this campaign
    has twice had to undo reading as a governed period. A revision whose modelo
    HAS registered designs but cites none of them is waiting on the design for
    its own window, which is modelo 185's 2003-2025 case: the one bundled design
    governs 2026 onward and correctly grounds its sibling revision instead. A
    revision already citing a registered design is authorable now.

    Sequencing the remaining work needs that distinction, and deriving it costs
    one directory listing per line.
    """
    modelo_id = str(modelo.id)
    designs = _bundled_designs(modelo_id)
    registered = tuple(
        ref
        for ref, source in sources.items()
        if getattr(source, "kind", None) == "record_design"
        and source.corpus_path
        and f"modelo_{modelo_id}/" in str(source.corpus_path).replace("\\", "/")
    )
    cited = tuple(
        str(ref)
        for ref in (revision.source_refs or ())
        if (source := sources.get(str(ref))) is not None
        and getattr(source, "kind", None) == "record_design"
    )
    if not designs:
        return "BLOCKED on corpus: no record design is bundled for this modelo"
    if not registered:
        return (
            f"BLOCKED on grounding: {len(designs)} design(s) bundled, none registered -- the era each "
            "governs must be grounded before it can become a source_ref"
        )
    if not cited:
        return (
            f"BLOCKED on era: {len(registered)} registered design(s) for this modelo, none cited by this "
            "revision -- the design governing THIS window is not among them"
        )
    return (
        f"AUTHORABLE: cites {cited[0]}, {len(revision.casillas or ())} casilla(s) declared "
        "-- needs its semantic map and layout"
    )


def test_every_registry_revision_can_produce_a_filing_artifact() -> None:
    """Fail with the list of revisions that cannot emit, until that list is empty."""
    unable = _revisions_that_cannot_emit()

    assert not unable, (
        f"{len(unable)} registry revision(s) across "
        f"{len({modelo for modelo, _revision, _blocked in unable})} modelo(s) declare no export layout, so this "
        "application cannot file them. This is the capability worklist, not a defect to suppress: each "
        "line needs its fixed-width export layout authored before the modelo can be filed, and each states what it is waiting on.\n"
        + "\n".join(
            f"  modelo {modelo} revision {revision}: no export layout -- {blocked}"
            for modelo, revision, blocked in unable
        )
    )
