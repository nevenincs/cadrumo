"""The write-site census must discriminate, not merely match names.

Every assertion here pins a distinction whose absence produced a real wrong
number during the storage campaign: ``.save`` counted 138 secure-object writes
as file writes, and an attribute call named ``replace`` counted ``str.replace``
as ``Path.replace`` and reported 267 sites where roughly 99 existed. A census
that cannot tell those apart returns a confident figure about the wrong set, so
each discrimination is asserted in **both** directions -- the shape that must
count, and the lookalike that must not.
"""

from __future__ import annotations

import ast

import pytest

from dev.write_site_census import (
    WriteSite,
    _bindings,
    _is_constrained,
    _literal_tail,
    _module_signals_constraint_risk,
    _taxonomy_subpath_tokens,
    _top_level_div_chains,
    _trace,
    classify,
    origin_symbol,
    production_modules,
    write_target,
)

# Aliased on import: pytest collects any module-level name matching
# python_functions (default "test_*") -- including one merely imported, not
# defined here -- so a bare "test_modules" import would itself be collected
# and run as a (fixture-less, failing) test.
from dev.write_site_census import test_modules as _test_modules_lister

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _origin_at(source: str) -> str:
    """Trace the write-target origin of the first file-producing call in ``source``.

    Builds module-level bindings the same way :func:`census` does, so an
    aliased import in the fixture source is visible to the traced call.
    """
    tree = ast.parse(source)
    module_bindings = _bindings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            found = write_target(node)
            if found is not None:
                _primitive, path_expression = found
                return _trace(origin_symbol(path_expression), [module_bindings])
    raise AssertionError(f"no file-producing call in {source!r}")


def _call(source: str) -> ast.Call:
    """Return the first call expression in ``source``."""
    parsed = ast.parse(source)
    for node in ast.walk(parsed):
        if isinstance(node, ast.Call):
            return node
    raise AssertionError(f"no call expression in {source!r}")


def _constrained_at(source: str) -> bool:
    """Drive the real per-call pipeline for the first file-producing call in ``source``.

    Mirrors the sequencing :func:`census` runs -- bindings, trace, classify,
    then :func:`_is_constrained` -- without touching git, the same testing
    shape :func:`_origin_at` already uses for provenance. This calls the
    production functions in the production order; it does not re-derive
    their answer, so it cannot silently agree with a broken one of them.
    """
    tree = ast.parse(source)
    module_bindings = _bindings(tree)
    module_signals_risk = _module_signals_constraint_risk(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            found = write_target(node)
            if found is None:
                continue
            _primitive, path_expression = found
            origin = _trace(origin_symbol(path_expression), [module_bindings])
            provenance = classify(origin, local_params=set(), module_params=set())
            return _is_constrained(path_expression, provenance=provenance, module_signals_risk=module_signals_risk)
    raise AssertionError(f"no file-producing call in {source!r}")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("path.write_text('x')", "write_text"),
        ("path.write_bytes(b'x')", "write_bytes"),
        ("path.mkdir(parents=True)", "mkdir"),
        ("open(path, 'w')", "open"),
        ("open(path, mode='a')", "open"),
        ("shutil.copytree(source, destination)", "copytree"),
        ("os.makedirs(path)", "makedirs"),
        ("target.replace(destination)", "replace"),
        ("workbook.save(path)", "save"),
    ],
)
def test_a_real_file_producing_call_is_counted(source: str, expected: str) -> None:
    """Each shape that genuinely creates or replaces a filesystem object is matched."""
    found = write_target(_call(source))
    assert found is not None, f"{source!r} produces a file and must be counted"
    assert found[0] == expected


@pytest.mark.parametrize(
    ("source", "why"),
    [
        ("repository.save(record)", "a secure-object save writes an encrypted SQL row, not a file"),
        ("buffer.save(stream)", "an in-memory buffer save touches no filesystem"),
        ("text.replace('a', 'b')", "str.replace takes two arguments; Path.replace takes one"),
        (
            "repository.rename(profile_id, new_label=label)",
            "a domain rename passes a bare positional-arity test; Path.rename takes no keywords",
        ),
        ("open(path, 'r')", "a read-mode open produces nothing"),
        ("open(path)", "the default mode is read"),
        ("path.exists()", "a predicate is not a write"),
        ("path.read_text()", "a read is not a write"),
    ],
)
def test_a_lookalike_is_not_counted(source: str, why: str) -> None:
    """Each shape that shares a method name with a writer, but writes nothing, is refused."""
    assert write_target(_call(source)) is None, f"{source!r} must not be counted: {why}"


def test_the_two_directions_disagree_on_the_same_method_name() -> None:
    """The discriminations are real, not an artefact of separate name lists.

    ``save`` and ``replace`` each appear in both directions above. If the
    selector keyed on the bare method name, one of the two directions would be
    wrong for each, so asserting them together is what proves the receiver and
    the arity are actually consulted.
    """
    assert write_target(_call("workbook.save(path)")) is not None
    assert write_target(_call("repository.save(record)")) is None
    assert write_target(_call("target.replace(destination)")) is not None
    assert write_target(_call("text.replace('a', 'b')")) is None


@pytest.mark.parametrize(
    ("origin", "local_params", "expected"),
    [
        ("storage_path", set(), "taxonomy"),
        ("cadrumo_audit_dir", set(), "taxonomy"),
        ("destination", {"destination"}, "pass_through"),
        ("self", set(), "pass_through"),
        ("self._root", set(), "pass_through"),
        ("<literal 'buckets'>", set(), "literal"),
        ("tmp_dir", set(), "temporary"),
        ("<Subscript>", set(), "unresolved"),
        ("computed", set(), "local"),
        ("FIXTURES_DIR", set(), "fixture"),
        ("bundled_path", set(), "fixture"),
    ],
)
def test_provenance_classification(origin: str, local_params: set[str], expected: str) -> None:
    """Each origin shape lands in the bucket that describes where the path came from."""
    assert classify(origin, local_params=local_params, module_params=set()) == expected


def test_a_fixture_named_local_is_not_a_fixture_marker() -> None:
    """FIXTURE_MARKERS is an exact set, not a substring match on 'fixture'.

    A local carrying the word without being one of the two real marker
    symbols is exactly as unclassified as any other hand-rolled local -- the
    same discipline TAXONOMY_MARKERS already applies (``cadrumo_x`` matches by
    prefix, but nothing merely resembling a taxonomy name does).
    """
    assert classify("fixture_root", local_params=set(), module_params=set()) == "local"
    assert classify("_my_fixtures", local_params=set(), module_params=set()) == "local"


def test_an_aliased_fixture_import_still_resolves_to_the_real_marker() -> None:
    """``from X import FIXTURES_DIR as Y`` must trace back through the rename.

    The test tree's own convention (``from .....tests import FIXTURES_DIR as
    _FIXTURES_ROOT``) is exactly this shape. Without following the import
    alias, the aliased name resolves to nothing and the fixture-corpus split
    silently fails on the codebase's own style.
    """
    source = (
        "from cadrumo.tests import FIXTURES_DIR as _FIXTURES_ROOT\n\n"
        "def build():\n"
        '    target = _FIXTURES_ROOT / "justificantes" / "130.pdf"\n'
        "    target.write_bytes(b'x')\n"
    )
    assert _origin_at(source) == "FIXTURES_DIR"


def test_a_bundled_path_call_resolves_through_a_local_alias() -> None:
    """``_DATA_ROOT = bundled_path()`` then a join off ``_DATA_ROOT`` traces to ``bundled_path``.

    The registry corpus tests' own shape (``_DATA_ROOT = bundled_path()``,
    ``_JUSTIFICANTE_CORPUS_ROOT = _DATA_ROOT.parent / "fixtures" /
    "justificantes"``) chains a plain assignment through an attribute access;
    the existing rebind-following must still land on the real accessor.
    """
    source = (
        "def build():\n"
        "    _data_root = bundled_path()\n"
        '    corpus_root = _data_root.parent / "fixtures" / "justificantes"\n'
        "    target = corpus_root / \"130.pdf\"\n"
        "    target.write_bytes(b'x')\n"
    )
    assert _origin_at(source) == "bundled_path"


def test_an_unrelated_import_alias_is_not_mistaken_for_a_fixture() -> None:
    """Following import aliases must not manufacture a fixture classification out of nothing.

    The positive control for the two tests above: an aliased import of an
    ordinary name resolves to that ordinary name, not to a marker.
    """
    source = (
        "from somewhere import storage_root as _root\n\n"
        "def build():\n"
        '    target = _root / "scratch.bin"\n'
        "    target.write_bytes(b'x')\n"
    )
    assert _origin_at(source) == "storage_root"


def test_production_modules_and_test_modules_are_a_disjoint_partition_at_head() -> None:
    """The two real listers, driven for real, put a known production file and a known test file on opposite sides.

    Reads actual committed HEAD through the real ``git ls-tree`` call both
    functions make -- not a re-derivation of the filter predicate, which
    would only prove the predicate agrees with itself. ``core/paths.py`` and
    ``core/tests/test_paths.py`` are both long-lived, so the assertion is
    stable rather than tied to a file likely to move.
    """
    production = set(production_modules("HEAD"))
    tests = set(_test_modules_lister("HEAD"))

    assert "src/cadrumo/core/paths.py" in production
    assert "src/cadrumo/core/paths.py" not in tests
    assert "src/cadrumo/core/tests/test_paths.py" in tests
    assert "src/cadrumo/core/tests/test_paths.py" not in production
    assert production.isdisjoint(tests), "a module must not be counted in both scopes"


def test_a_caller_supplied_path_is_pass_through_not_unenrolled() -> None:
    """The distinction the whole census exists to make.

    A site handed its path has no enrollment answer of its own -- the answer is
    "wherever the caller said". Classifying it as unenrolled would manufacture a
    finding; classifying it as enrolled would manufacture coverage. It is
    neither, and the third label is what lets the count mean something.
    """
    assert classify("output_dir", local_params={"output_dir"}, module_params=set()) == "pass_through"
    assert classify("output_dir", local_params=set(), module_params={"output_dir"}) == "pass_through"
    assert classify("output_dir", local_params=set(), module_params=set()) == "local"


def test_ambiguity_is_reported_rather_than_silently_trusted() -> None:
    """A site on a duck-typed name must announce that it needs a human read."""
    ambiguous = WriteSite(module="m.py", line=1, primitive="touch", origin="session", provenance="local")
    unambiguous = WriteSite(module="m.py", line=2, primitive="mkdir", origin="target", provenance="local")
    assert ambiguous.ambiguous
    assert not unambiguous.ambiguous


# ---------------------------------------------------------------------------
# injected-but-constrained: a literal that coincides with a declared taxonomy
# subpath, in a module that also references a real accessor or spawns a
# subprocess -- the shape three renamed "free" ``secrets`` literals actually
# were, breaking a cross-process fixture handoff nobody had marked as shared.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('tmp_path / "secrets"', ("secrets",)),
        ('root / bucket_id / "db"', ("db",)),
        ("tmp_path / bucket_id", ()),
        ("tmp_path", ()),
    ],
)
def test_literal_tail_returns_the_trailing_contiguous_string_literal_run(
    source: str, expected: tuple[str, ...]
) -> None:
    """The walk stops at the first non-literal segment met walking backward from the tail."""
    node = ast.parse(source, mode="eval").body
    assert _literal_tail(node) == expected


def test_literal_tail_is_empty_for_an_expression_with_no_division_at_all() -> None:
    """A bare name (no ``/`` join at all) has no literal tail to report."""
    node = ast.parse("tmp_path", mode="eval").body
    assert _literal_tail(node) == ()


def test_taxonomy_subpath_tokens_contains_both_whole_subpaths_and_their_path_components() -> None:
    """A leaf-only injection (``"secrets"``) must match, not only an exact full multi-segment subpath."""
    tokens = _taxonomy_subpath_tokens()
    assert "secrets" in tokens  # SECRETS' own whole declared subpath
    assert "master.key" in tokens  # a path component of SECRETS_MASTER_KEY's "secrets/master.key"


def test_taxonomy_subpath_tokens_does_not_contain_an_unrelated_word() -> None:
    """The positive control's negative: a plausible-looking directory name with no taxonomy referent."""
    assert "fallback-store" not in _taxonomy_subpath_tokens()


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import subprocess\ndef f():\n    subprocess.run(['x'])\n", True),
        ("from subprocess import Popen\ndef f():\n    Popen(['x'])\n", True),
        ("def f():\n    CliRunner().invoke(app)\n", True),
        ("def f():\n    storage_path(StorageCategory.SECRETS)\n", True),
        ("def f():\n    return 1 + 1\n", False),
        ("def f():\n    subprocess_like_name()\n", False),
    ],
)
def test_module_signals_constraint_risk(source: str, expected: bool) -> None:
    """Any of the three named spawners, or a taxonomy-accessor reference, signals risk -- nothing else does."""
    assert _module_signals_constraint_risk(ast.parse(source)) is expected


@pytest.mark.parametrize(
    ("path_source", "provenance", "module_signals_risk", "expected"),
    [
        # The real incident, minimal: a temporary-scoped literal matching a
        # declared taxonomy subpath, in a module that signals risk.
        ('tmp_path / "secrets"', "temporary", True, True),
        # Same coincidence, but nothing in the module suggests a shared
        # derivation -- not enough on its own.
        ('tmp_path / "secrets"', "temporary", False, False),
        # Risk signal present, but the literal has no taxonomy referent.
        ('tmp_path / "fallback-store"', "temporary", True, False),
        # Already has a real enrollment answer (or an unresolved one) that
        # this refinement does not touch.
        ('tmp_path / "secrets"', "taxonomy", True, False),
        ('tmp_path / "secrets"', "local", True, False),
        ('tmp_path / "secrets"', "literal", True, False),
        # pass_through is the other provenance this check applies to.
        ('output_dir / "secrets"', "pass_through", True, True),
    ],
)
def test_is_constrained(path_source: str, provenance: str, module_signals_risk: bool, expected: bool) -> None:
    """Only a temporary/pass_through site, in a risk-signalling module, on a taxonomy-coincident tail is constrained."""
    node = ast.parse(path_source, mode="eval").body
    assert _is_constrained(node, provenance=provenance, module_signals_risk=module_signals_risk) is expected


def test_is_constrained_is_false_when_the_path_expression_is_absent() -> None:
    """A write primitive with no path argument (e.g. a bare ``mkdir()``) has nothing to check."""
    assert _is_constrained(None, provenance="temporary", module_signals_risk=True) is False


def test_top_level_div_chains_counts_a_multi_segment_join_once() -> None:
    """``a / "b" / "c"`` parses as nested BinOp nodes; only the outermost is a chain."""
    tree = ast.parse('root = a / "b" / "c"\n')
    chains = _top_level_div_chains(tree)
    assert len(chains) == 1
    assert isinstance(chains[0].right, ast.Constant)
    assert chains[0].right.value == "c"


def test_top_level_div_chains_counts_two_independent_joins_separately() -> None:
    """Two unrelated joins in the same scope are two chains, not folded together."""
    tree = ast.parse('x = a / "b"\ny = c / "d"\n')
    assert len(_top_level_div_chains(tree)) == 2


def test_top_level_div_chains_is_empty_for_an_expression_with_no_division() -> None:
    """A module with no ``/``-join at all reports zero chains."""
    assert _top_level_div_chains(ast.parse("x = a\n")) == []


def _constrained_bare_chain_at(source: str) -> bool:
    """Drive the real bare-``/``-chain pipeline census runs under ``scope="tests"``.

    The incident this feature exists to catch (``{"CADRUMO_SECRET_STORE_DIR":
    str(tmp_path / "secrets")}``, a dict value handed to an env-var override)
    is a chain no write primitive ever consumes -- :func:`write_target` never
    sees it, only :func:`_top_level_div_chains` does. This mirrors that half
    of :func:`census`, the same shape :func:`_constrained_at` mirrors for the
    write-primitive half.
    """
    tree = ast.parse(source)
    module_bindings = _bindings(tree)
    module_signals_risk = _module_signals_constraint_risk(tree)
    chains = _top_level_div_chains(tree)
    if not chains:
        raise AssertionError(f"no / -join chain in {source!r}")
    chain = chains[0]
    origin = _trace(origin_symbol(chain), [module_bindings])
    provenance = classify(origin, local_params=set(), module_params=set())
    return _is_constrained(chain, provenance=provenance, module_signals_risk=module_signals_risk)


def test_a_literal_matching_a_taxonomy_subpath_is_constrained_when_the_module_spawns_a_subprocess() -> None:
    """The exact incident this feature exists to catch, minimised.

    Three sites of the shape ``str(tmp_path / "secrets")``, injected as an
    env-var override value, were renamed to a seemingly-free literal and
    broke -- a spawned child process independently derived the same
    location from the real accessor while the site under test read as free.
    No write primitive ever consumes this expression; only the bare-chain
    walk sees it.
    """
    source = (
        "import subprocess\n\n"
        "def build(tmp_path):\n"
        '    overrides = {"CADRUMO_SECRET_STORE_DIR": str(tmp_path / "secrets")}\n'
        "    subprocess.run(['aeat', 'config'], env=overrides)\n"
    )
    assert _constrained_bare_chain_at(source)


def test_the_same_literal_is_not_constrained_without_a_co_located_risk_signal() -> None:
    """A taxonomy-coincident literal alone is not enough -- nothing in the module suggests a shared derivation.

    No accessor/subprocess/CliRunner name and, deliberately, no CADRUMO_*
    string constant either -- the env-var-key dict form belongs to the
    positive-control test above; this is the genuine risk-free negative.
    """
    source = 'def build(tmp_path):\n    target = tmp_path / "secrets"\n    return str(target)\n'
    assert not _constrained_bare_chain_at(source)


def test_a_risk_signal_alone_does_not_constrain_an_unrelated_literal() -> None:
    """The positive control's negative: a subprocess call plus a literal with no taxonomy referent."""
    source = (
        "import subprocess\n\n"
        "def build(tmp_path):\n"
        '    overrides = {"CADRUMO_FALLBACK_DIR": str(tmp_path / "fallback-store")}\n'
        "    subprocess.run(['aeat', 'config'], env=overrides)\n"
    )
    assert not _constrained_bare_chain_at(source)


def test_a_taxonomy_accessor_reference_also_signals_risk_not_only_a_spawned_process() -> None:
    """CONSTRAINT_RISK_SIGNALS includes the taxonomy accessor markers too, not only subprocess/Popen/CliRunner."""
    source = (
        "def build(tmp_path):\n"
        '    overrides = {"CADRUMO_SECRET_STORE_DIR": str(tmp_path / "secrets")}\n'
        "    other = storage_path(StorageCategory.SECRETS)\n"
    )
    assert _constrained_bare_chain_at(source)


def test_a_write_primitive_called_directly_on_the_chain_is_also_caught() -> None:
    """The write-primitive half catches the same coincidence when the chain feeds a real write call inline.

    ``_is_constrained`` receives whatever :func:`write_target` calls the
    "path expression" for a given primitive shape; for a receiver primitive
    (``.mkdir()``) that is the receiver expression itself. Inlining the
    chain as the receiver, rather than assigning it to a local first, is
    what lets :func:`_literal_tail` see the join -- proving the write-call
    half of the wiring independently of the bare-chain half above.
    """
    source = (
        "import subprocess\n\n"
        "def build(tmp_path):\n"
        '    (tmp_path / "secrets").mkdir(parents=True)\n'
        "    subprocess.run(['aeat', 'config'])\n"
    )
    assert _constrained_at(source)
