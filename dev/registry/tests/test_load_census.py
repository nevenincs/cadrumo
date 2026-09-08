"""Detector-teeth tests for the mechanically derived registry load census."""

from __future__ import annotations

import pathlib

import pytest

from ..analysis.load_census import (
    REGISTRY_PACKAGE,
    build_reference_map,
    build_runtime_graph,
    census_universe,
    module_level_importers,
    registry_package_modules,
    static_load_closure,
    unreferenced_modules,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PLANTED = "cadrumo.domain.calculations.registry._module_that_does_not_exist"


def test_the_registry_package_is_covered_whether_or_not_the_load_imports_it() -> None:
    """A registry module outside the load closure is still in the universe.

    This is the case the census exists to catch. Deriving the universe from the
    closure alone would silently exempt exactly the modules a load never
    reaches, which is the population under investigation.
    """
    graph = build_runtime_graph()

    assert registry_package_modules() <= census_universe(graph)
    assert registry_package_modules() - static_load_closure(graph)


def test_every_registry_module_has_a_derived_reference_path() -> None:
    """The live graph reports no unreferenced registry module."""
    graph = build_runtime_graph()
    candidates = unreferenced_modules(graph, build_reference_map())

    assert candidates == frozenset()


def test_the_static_closure_matches_what_a_real_load_imports(
    registry_authority: object,
) -> None:
    """The closure is checked against reality, not trusted as a graph artefact.

    A closure computed from an import graph is a claim about the running
    program, and it is confronted with ``sys.modules`` after the session
    authority has loaded rather than trusted.

    The claim is not plain containment, and asserting that was wrong. The graph
    records function-scoped imports, which a real load never walks unless the
    function runs, so the closure is a statement about what a load can REACH and
    ``sys.modules`` is a statement about what it DID import. Demanding they match
    made the test unsatisfiable by a legitimate construct: ``_withholding_rows``
    imports ``withholding_bindings`` at module level and is imported back from
    inside a function, which is the standard way to break an import cycle and
    cannot be hoisted without restoring the cycle.

    So the difference is required to be exactly the deferred edges. Every module
    the graph reaches but the load did not import must have no module-level
    importer at all. A module that goes missing for any other reason - deleted,
    renamed, or dropped out of the load path - still fails here, which is the
    detection this test existed for.
    """
    import sys

    assert registry_authority is not None
    imported = {name for name in sys.modules if name == REGISTRY_PACKAGE or name.startswith(REGISTRY_PACKAGE + ".")}
    closure = {m for m in static_load_closure(build_runtime_graph()) if m.startswith(REGISTRY_PACKAGE)}

    eagerly_reachable = {module for module in closure - imported if module_level_importers(module)}
    assert eagerly_reachable == set(), (
        "the graph says a load imports these modules and the real load did not, "
        f"and each has a module-level importer so no deferred edge explains it: {sorted(eagerly_reachable)}"
    )


def test_no_registry_dynamic_import_site_is_left_unresolved() -> None:
    """The census must be able to follow the registry's own dynamic edges.

    A dynamic import the resolver cannot follow is dropped from the universe
    silently. The report has always recorded such sites and the CLI prints
    them, but nothing asserted on the field, so a resolver going blind produced
    no failure of its own - it surfaced one directory away, as classification
    rules that had apparently gone stale.

    That is what happened here. `_snapshot_internals` imports the cross-domain
    check modules from a tuple built out of another module's mapping values
    rather than from a literal, which the static resolver cannot read, so the
    renta package left the universe and the rule describing it started
    reporting as stale. The rule is correct; the resolver stopped seeing the
    edge it describes.

    Scoped to the registry package deliberately. Unresolved sites elsewhere in
    the tree are real too, but they belong to the surfaces that own them, and a
    gate that fails on all of them at once would say nothing about which one
    broke the census.
    """
    from ..analysis.load_census import run_census

    report = run_census()
    registry_sites = [
        f"{site.module}:{site.lineno}"
        for site in report.unresolved_dynamic_sites
        if site.module.startswith("cadrumo.domain.calculations.registry")
    ]

    assert not registry_sites, (
        "the census cannot follow a dynamic import inside the registry package, so whatever it "
        f"reaches is missing from the universe. Teach the resolver this shape: {registry_sites}"
    )


def test_the_evaluator_reads_a_constant_whatever_shape_it_is_built_from() -> None:
    """A name's value is the answer; how the value was written is not.

    The census followed a literal tuple and went blind when the same names were
    rebuilt from another module's mapping values. This resolves by asking the
    module, so both spellings answer identically - which is the property that
    stops the next construction from blinding it again.
    """
    from ..analysis.load_census import evaluated_string_sequence

    members = evaluated_string_sequence(
        "cadrumo.domain.calculations.registry._snapshot_internals",
        "_CROSS_DOMAIN_CHECK_MODULES",
    )

    assert members is not None, "the live non-literal construction must resolve"
    assert all(name.startswith("cadrumo.domain.renta.") for name in members)


def test_the_evaluator_returns_none_rather_than_guessing() -> None:
    """Every failure is a refusal, because a guessed target is worse than none.

    The caller records an unresolved site and a gate reads that record. A
    fallback that returned a partial or invented answer would fill the universe
    with modules nothing imports, and the census would look complete while
    describing a tree that does not exist.
    """
    from ..analysis.load_census import evaluated_string_sequence

    assert evaluated_string_sequence("cadrumo.module.that.does.not.exist", "ANY") is None
    assert evaluated_string_sequence("cadrumo.domain.calculations.registry._snapshot_internals", "NO_SUCH_NAME") is None
    assert (
        evaluated_string_sequence(
            "cadrumo.domain.calculations.registry._snapshot_internals",
            "_install_cross_domain_snapshot_checks",
        )
        is None
    ), "a callable is not a sequence of module names"


def test_an_unreadable_registry_module_is_announced_as_weakening_the_conclusion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An empty importer set MEANS every import of the module is deferred.

    A file that could not be read makes that conclusion easier to reach and
    wrong: a module-level importer sitting in the skipped file would have
    refuted it. The walk still continues, because one half-written file must
    not cost the census.
    """
    from ..analysis import load_census

    (tmp_path / "sound.py").write_text("from cadrumo.target import thing" + chr(10), encoding="utf-8")
    (tmp_path / "broken.py").write_text("def (:" + chr(10), encoding="utf-8")
    monkeypatch.setattr(load_census, "REGISTRY_DIR", tmp_path)

    load_census.module_level_importers("cadrumo.target")

    error = capsys.readouterr().err
    assert "would refute the deferred-import conclusion" in error
    assert "broken.py" in error


def test_a_readable_registry_tree_announces_nothing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A notice on every run would tell a reader nothing."""
    from ..analysis import load_census

    (tmp_path / "sound.py").write_text("VALUE = 1" + chr(10), encoding="utf-8")
    monkeypatch.setattr(load_census, "REGISTRY_DIR", tmp_path)

    load_census.module_level_importers("cadrumo.target")

    assert capsys.readouterr().err == ""


def test_an_unparsable_reference_scan_file_is_announced_not_dropped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The reference map must not silently lose a consumer to a syntax error.

    ``build_reference_map`` used to let an unparsable file vanish from the
    population with no notice at all, unlike its sibling
    ``module_level_importers``. A registry module whose only consumer lives in
    that file would then read as unreferenced and misclassify as a dead
    candidate, so the drop must be announced the same way.
    """
    from ..analysis import load_census

    root = tmp_path / "cadrumo"
    root.mkdir()
    (root / "sound_consumer.py").write_text(
        "from cadrumo.domain.calculations.registry.module_a import Thing" + chr(10),
        encoding="utf-8",
    )
    (root / "broken_consumer.py").write_text(
        "from cadrumo.domain.calculations.registry.module_b import Thing" + chr(10) + "def broken(" + chr(10),
        encoding="utf-8",
    )
    monkeypatch.setattr(load_census, "REFERENCE_SCAN_ROOTS", (root,))

    reference_map = load_census.build_reference_map()
    error = capsys.readouterr().err

    assert "cadrumo.domain.calculations.registry.module_a" in reference_map.production
    assert "cadrumo.domain.calculations.registry.module_b" not in reference_map.production
    assert "would be missing from the reference map" in error
    assert "broken_consumer.py" in error


def test_a_parsable_reference_scan_tree_announces_nothing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A clean reference scan must stay quiet, so the notice above means something."""
    from ..analysis import load_census

    root = tmp_path / "cadrumo"
    root.mkdir()
    (root / "sound_consumer.py").write_text(
        "from cadrumo.domain.calculations.registry.module_a import Thing" + chr(10),
        encoding="utf-8",
    )
    monkeypatch.setattr(load_census, "REFERENCE_SCAN_ROOTS", (root,))

    load_census.build_reference_map()

    assert capsys.readouterr().err == ""


def test_an_unparsable_dynamic_import_file_is_announced_not_dropped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A dynamic ``import_module`` call must not vanish because its file has a syntax error.

    ``dynamic_import_sites`` used to drop an unparsable file's call sites with
    no notice, so a real dynamic edge could go missing from the census the
    same way an unreadable registry module used to, silently.
    """
    from ..analysis import load_census

    root = tmp_path / "cadrumo"
    root.mkdir()
    (root / "sound_dynamic.py").write_text(
        "import importlib"
        + chr(10)
        + "importlib.import_module('cadrumo.domain.calculations.registry.module_c')"
        + chr(10),
        encoding="utf-8",
    )
    (root / "broken_dynamic.py").write_text(
        "import importlib"
        + chr(10)
        + "importlib.import_module('cadrumo.domain.calculations.registry.module_d')"
        + chr(10)
        + "def broken("
        + chr(10),
        encoding="utf-8",
    )
    monkeypatch.setattr(load_census, "REFERENCE_SCAN_ROOTS", (root,))

    sites = load_census.dynamic_import_sites(production_only=False)
    error = capsys.readouterr().err
    modules_seen = {site.module for site in sites}

    assert "cadrumo.sound_dynamic" in modules_seen
    assert "cadrumo.broken_dynamic" not in modules_seen
    assert "would be missing from the census" in error
    assert "broken_dynamic.py" in error


def test_a_parsable_dynamic_import_tree_announces_nothing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A clean dynamic-import scan must stay quiet, so the notice above means something."""
    from ..analysis import load_census

    root = tmp_path / "cadrumo"
    root.mkdir()
    (root / "sound_dynamic.py").write_text(
        "import importlib"
        + chr(10)
        + "importlib.import_module('cadrumo.domain.calculations.registry.module_c')"
        + chr(10),
        encoding="utf-8",
    )
    monkeypatch.setattr(load_census, "REFERENCE_SCAN_ROOTS", (root,))

    load_census.dynamic_import_sites(production_only=False)

    assert capsys.readouterr().err == ""


def test_the_clean_property_reads_every_field_it_claims_to() -> None:
    """The gate above asserts ``clean`` and never sees it answer False.

    ``clean`` is a conjunction over three fields, and the corpus satisfies all
    three, so a property that had stopped reading two of them would still
    answer True on every live run and the assertion above would still pass. The
    reports here are constructed because a False answer is not otherwise
    reachable from the working tree, and each one holds exactly one field the
    property must refuse on.
    """
    from ..analysis.load_census import CensusReport

    settled = {
        "universe": frozenset({_PLANTED}),
        "closure": frozenset(),
        "registry_modules": frozenset({_PLANTED}),
        "dead_candidates": frozenset(),
        "unresolved_dynamic_sites": (),
    }

    assert CensusReport(**settled).clean, "a report with nothing outstanding must read clean"

    assert not CensusReport(**{**settled, "dead_candidates": frozenset({_PLANTED})}).clean
