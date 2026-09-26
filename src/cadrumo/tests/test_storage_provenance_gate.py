"""Provenance gate: a location is produced by the resolver, never by a join.

Where a byte lands used to be decided by four mutually unaware authorities, and
the gate written to prevent a fifth could not see any of them: it matched
slashed literals inside a ``Path(...)`` call, and every offending site instead
*built* its path by joining onto the storage root. A literal census
structurally cannot reach that class.

This gate reaches it, because it matches the join rather than the literal.
``settings.cadrumo_local_storage_root / _INDEX_SUBDIR`` is a ``BinOp`` whose
left operand is the attribute access, so the detector fires regardless of what
is joined on -- a constant, a module-local name, a computed segment, or a
chain. The same holds for ``joinpath``, ``glob``, ``rglob``, and ``iterdir``,
and through a ``Path(...)`` wrapper.

Being AST-structural also dissolves the false-positive class a name census
inherits, without an allowlist entry: ``core/auth_session_keys.py`` names
``Settings.cadrumo_token_dir`` inside its module docstring precisely to record
that the key is deliberately independent of it. A docstring is an
``ast.Constant``; an attribute walk cannot see it, so the gate cannot produce
that error at all.

Scope, stated exactly, including what this does NOT cover
---------------------------------------------------------
The enforced property is **location production**, not readership. Reading the
root as the root -- handing it to a disk-usage walker, reporting it, scanning
beneath it -- produces no location and is not a finding; at the time of
writing 68 such reads exist and every one is legitimate. Joining onto the root
produces a location, and only the declared producers may do that.

This is deliberately narrower than "the storage root has exactly one reader":
reading the root is legitimate, so that property would be false by design.

**A second, different property is not covered here at all**: that a module
must not hardcode a taxonomy-governed directory or file name. That is literal
vocabulary, not join provenance, and it lives in
:mod:`~core.tests.test_settings_lifecycle_gate`, which scans production code
and the test corpus alike. Neither gate subsumes the other -- a literal scan
cannot see a path built by joining, and this gate cannot see a name spelled
out in full.

Following a rebind
------------------
A receiver-only walk is evaded by one line, so the detector follows the root
through a function-local binding: a name assigned the root, then joined, is a
join. Scope is the function plus the scopes enclosing it, and no further --
chasing the root through parameters and returns is where a heuristic starts
flagging healthy code, and ``root`` is an ordinary variable name. A blind spot
in the detector would let a join pass unreported, which is worse than a missing
gate because it reads as proof.

:data:`PERMITTED_PRODUCERS`, keyed by module and enclosing function, names the
resolvers that exist to turn the root into a path. Every other join fails, and
an entry whose function stopped joining fails too, so the permission cannot
outlive the function that needed it.
"""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple

import pytest

from ..core.storage_taxonomy import STORAGE_ROOT_SETTINGS_FIELD
from .inventory import aeat_relative, ast_for_path, package_python_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.usefixtures("operation")]

if TYPE_CHECKING:
    from collections.abc import Sequence


_MODULE_SCOPE: Final[str] = "<module>"
"""Scope name for a join that sits outside any function."""


JOIN_METHODS: Final[frozenset[str]] = frozenset({"joinpath", "glob", "rglob", "iterdir"})
"""Path methods that derive a location from the receiver.

``/`` is the common shape; these are the method spellings of the same act. A
site that reaches beneath the root by any of them has produced a location.
"""


class JoinSite(NamedTuple):
    """One place the storage root is joined onto, and who owns it."""

    module: str
    function: str
    lineno: int

    @property
    def key(self) -> tuple[str, str]:
        """The declaration key: module and enclosing function."""
        return (self.module, self.function)


PERMITTED_PRODUCERS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        # The two accessors the enrollment contract names. Every enrolled site
        # resolves through one of them, so these are where the root becomes a
        # path on purpose.
        ("core/storage_taxonomy_locations.py", "storage_path"),
        ("core/storage_taxonomy_locations.py", "bucket_scoped_storage_path"),
        # Settings derivation: turns each root-derived member's declared
        # subpath into that field's default. It iterates the declaration
        # directly rather than carrying a table of its own.
        ("core/_config_validation.py", "resolve_output_dirs_under_storage_root"),
        # The on-disk-name pin. It must build the expected location from its own
        # oracle to measure the validator, and routing it through the accessor
        # would make it assert that the accessor equals itself -- deleting the
        # test's reason for existing while leaving it green. Joining the root is
        # not debt here; it is the measurement.
        ("core/tests/test_output_dir_state_root.py", "test_every_derived_output_dir_roots_under_storage_root"),
        # The TUI review harness gives each reviewer a private storage root for
        # its own session journal and SQLite bucket. That is development-only
        # harness state, not an application-chosen member of the taxonomy.
        ("entrypoints/tui/tests/fixture.py", "<module>"),
    },
)
"""Functions that may join onto the storage root, because producing a location is their job."""


def _unwrap_path_call(node: ast.expr) -> ast.expr:
    """Strip ``Path(...)`` wrappers so ``Path(root) / x`` reads like ``root / x``."""
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Path" and node.args:
        node = node.args[0]
    return node


def _is_root_access(node: ast.expr) -> bool:
    """Whether ``node`` loads the storage-root attribute off anything."""
    unwrapped = _unwrap_path_call(node)
    return isinstance(unwrapped, ast.Attribute) and unwrapped.attr == STORAGE_ROOT_SETTINGS_FIELD


def _join_linenos(tree: ast.AST) -> set[int]:
    """Return the lines on which the storage root has something joined onto it."""
    found: set[int] = set()
    for node in ast.walk(tree):
        target: ast.expr | None = None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            target = node.left
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in JOIN_METHODS:
            target = node.func.value
        if target is not None and _is_root_access(target):
            found.add(_unwrap_path_call(target).lineno)
    return found


def _function_spans(tree: ast.AST) -> list[tuple[int, int, str]]:
    """Return ``(start, end, dotted name)`` for every function, nested ones included."""
    spans: list[tuple[int, int, str]] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                name = f"{prefix}{child.name}"
                if not isinstance(child, ast.ClassDef):
                    spans.append((child.lineno, child.end_lineno or child.lineno, name))
                walk(child, f"{name}.")
            else:
                walk(child, prefix)

    walk(tree, "")
    return spans


def _enclosing_scope(lineno: int, spans: list[tuple[int, int, str]]) -> str:
    """Return the innermost function containing ``lineno``, or the module scope."""
    enclosing = [(start, name) for start, end, name in spans if start <= lineno <= end]
    return max(enclosing)[1] if enclosing else _MODULE_SCOPE


def _root_bound_names(tree: ast.AST, spans: list[tuple[int, int, str]]) -> dict[str, list[tuple[str, int]]]:
    """Return, per scope, the local names assigned the storage root and where.

    A one-line rebind is the obvious way around a receiver-only walk::

        root = settings.cadrumo_local_storage_root   # a plain read
        target = root / "buckets" / bucket_id        # a join the walk cannot see

    Both statements are individually unremarkable and together they produce a
    location, so the binding has to be followed or the gate passes a join it
    never saw.

    Scope is deliberately the whole of a function (plus the scopes enclosing
    it, since a closure genuinely sees its host's names) and no further.
    Chasing the root through parameters and return values is where a heuristic
    starts flagging healthy code, and a gate that flags healthy code gets
    weakened or deleted.
    """
    bound: dict[str, list[tuple[str, int]]] = {}
    for node in ast.walk(tree):
        targets: Sequence[ast.expr]
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = (node.target,)
        else:
            continue
        if node.value is None or not _is_root_access(node.value):
            continue
        scope = _enclosing_scope(node.lineno, spans)
        for target in targets:
            if isinstance(target, ast.Name):
                bound.setdefault(scope, []).append((target.id, node.lineno))
    return bound


def _binds_root(
    name: str,
    scope: str,
    lineno: int,
    bound: dict[str, list[tuple[str, int]]],
) -> bool:
    """Whether ``name`` holds the storage root at ``lineno`` within ``scope``.

    Visible scopes are the scope itself and every scope enclosing it, so a
    closure joining a name its host bound is caught. Only bindings *above* the
    use count, which keeps an unrelated same-named local in an earlier sibling
    function from reaching across.
    """
    parts = scope.split(".")
    visible = [".".join(parts[:depth]) for depth in range(1, len(parts) + 1)] + [_MODULE_SCOPE]
    return any(
        bound_name == name and bound_lineno < lineno
        for candidate in visible
        for bound_name, bound_lineno in bound.get(candidate, ())
    )


def root_join_sites(module: str, tree: ast.AST) -> tuple[JoinSite, ...]:
    """Return every place ``module`` joins onto the storage root.

    A pure function over a display name and a parsed tree, so the
    discrimination tests can hand it synthetic source and prove each shape
    fires or does not. The innermost enclosing function wins, so a join inside
    a closure is attributed to the closure rather than to its host.
    """
    spans = _function_spans(tree)
    bound = _root_bound_names(tree, spans)
    linenos: set[int] = set(_join_linenos(tree))

    for node in ast.walk(tree):
        target: ast.expr | None = None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            target = node.left
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in JOIN_METHODS:
            target = node.func.value
        if target is None:
            continue
        receiver = _unwrap_path_call(target)
        if isinstance(receiver, ast.Name) and _binds_root(
            receiver.id, _enclosing_scope(receiver.lineno, spans), receiver.lineno, bound
        ):
            linenos.add(receiver.lineno)

    return tuple(
        JoinSite(module=module, function=_enclosing_scope(lineno, spans), lineno=lineno) for lineno in sorted(linenos)
    )


_ROOT_FIELD_BYTES: Final = STORAGE_ROOT_SETTINGS_FIELD.encode("utf-8")


def _may_join_onto_root(path: Path) -> bool:
    """Whether ``path`` could possibly hold a join site, decided from its bytes alone.

    Every site :func:`root_join_sites` can report is anchored on an
    ``ast.Attribute`` whose attribute name is
    :data:`STORAGE_ROOT_SETTINGS_FIELD` -- directly, or through a local name
    that the SAME tree assigned from such an attribute, since binding is
    resolved per tree and never across modules. The identifier therefore appears
    verbatim in the source of any module that has a site, and a module whose
    bytes do not contain it cannot produce one.

    This is a pre-filter on cost, not on meaning: the corpus the non-vacuity
    gate measures is still every packaged module, and any module that passes
    this check is analysed exactly as before. It matters because
    :func:`root_join_sites` makes four full traversals of a module's tree, and
    it was making them for all 5,485 packaged modules to find 7 sites -- 33 s
    of walking, essentially all of it over modules that never mention the root.

    An unreadable file answers ``True`` rather than being skipped quietly; the
    parse path below is what owns reporting it.
    """
    try:
        return _ROOT_FIELD_BYTES in path.read_bytes()
    except OSError:
        return True


@cache
def _discovered_sites() -> tuple[JoinSite, ...]:
    """Walk every packaged module, production and test alike.

    Cached because five assertions share one walk of the whole package and the
    tree does not change within a run.
    """
    sites: list[JoinSite] = []
    for path in package_python_files():
        if not _may_join_onto_root(path):
            continue
        tree = _tree_for(path)
        if tree is not None:
            sites.extend(root_join_sites(aeat_relative(path), tree))
    return tuple(sites)


def _tree_for(path: Path) -> ast.AST | None:
    return ast_for_path(path)


def test_the_scanned_corpus_and_its_findings_are_both_non_degenerate() -> None:
    """The gate must be looking at the real tree, not at nothing.

    A detector proved correct on synthetic input still measures nothing if it
    is fed the wrong subject. Two ways that happens here, and both are refused:
    the module walk yields an empty corpus, so no violation is reported for the
    wrong reason; or the walk works but finds no join at all, which cannot be
    true while the resolvers exist -- turning the root into a path is what they
    are for.

    Bounds, not counts: an exact figure rots on the next ordinary module.
    """
    corpus = package_python_files()
    assert len(corpus) >= 500, (
        f"the provenance scan walked only {len(corpus)} module(s). The package is far larger "
        "than that, so discovery has collapsed and every assertion below would report a clean "
        "tree it never actually read"
    )

    sites = _discovered_sites()
    assert len(sites) >= len(PERMITTED_PRODUCERS), (
        f"found {len(sites)} storage-root join site(s) across {len(corpus)} modules, fewer than "
        f"the {len(PERMITTED_PRODUCERS)} declared producers. The resolvers must join onto the "
        "root -- that is how they produce a path -- so this means the detector stopped working, "
        "not that the tree became clean"
    )


def test_only_declared_producers_join_onto_the_storage_root() -> None:
    """Building a location from the root outside a declared producer fails here."""
    declared = PERMITTED_PRODUCERS
    undeclared = sorted(
        f"{site.module}:{site.lineno} in {site.function}" for site in _discovered_sites() if site.key not in declared
    )
    assert not undeclared, (
        f"storage-root join site(s) outside every declared producer: {undeclared}. Resolve the "
        "location through storage_path(category) -- or bucket_scoped_storage_path(category, "
        "bucket_id) for a per-bucket member -- rather than joining onto "
        f"{STORAGE_ROOT_SETTINGS_FIELD}. If the location has no member yet, declare one: the "
        "taxonomy governs every application-chosen segment, not only the top of each category"
    )


def test_every_permitted_producer_still_produces() -> None:
    """A permitted entry whose function stopped joining is a widened permission."""
    joining = {site.key for site in _discovered_sites()}
    stale = sorted(f"{module}::{function}" for module, function in PERMITTED_PRODUCERS - joining)
    assert not stale, (
        f"PERMITTED_PRODUCERS names {stale}, which no longer joins onto the storage root; strike "
        "the entry in the same change that moves the resolution, so the permission cannot outlive "
        "the function that needed it"
    )


# --------------------------------------------------------------------- #
# Discrimination: each shape fires, and each control does not            #
# --------------------------------------------------------------------- #


def _sites_in(source: str) -> tuple[JoinSite, ...]:
    return root_join_sites("synthetic.py", ast.parse(source))


LOCATION_PRODUCING_SOURCES: Final[tuple[tuple[str, str], ...]] = tuple(
    [
        (
            "operator join onto a literal",
            'def make():\n    return settings.cadrumo_local_storage_root / "scratch"\n',
        ),
        (
            "operator join onto a module-local constant",
            "def make():\n    return settings.cadrumo_local_storage_root / _INDEX_SUBDIR\n",
        ),
        (
            "chained join",
            'def make():\n    return settings.cadrumo_local_storage_root / "a" / "b" / "c"\n',
        ),
        (
            "joinpath spelling",
            'def make():\n    return settings.cadrumo_local_storage_root.joinpath("scratch")\n',
        ),
        (
            "glob beneath the root",
            'def make():\n    return list(settings.cadrumo_local_storage_root.glob("*.db"))\n',
        ),
        (
            "wrapped in Path()",
            'def make():\n    return Path(settings.cadrumo_local_storage_root) / "scratch"\n',
        ),
        (
            "reached through self",
            'def make(self):\n    return self.cadrumo_local_storage_root / "scratch"\n',
        ),
        (
            "reached through a call result",
            'def make():\n    return load_settings().cadrumo_local_storage_root / "scratch"\n',
        ),
    ]
)
"""Every spelling of "build a path from the root" that the detector must fire on.

Held as a constant rather than inlined into one parametrize, because two tests
need the same corpus of shapes: the detector must fire on each, and the byte
pre-filter in :func:`_may_join_onto_root` must admit each.
"""


@pytest.mark.parametrize(("label", "source"), LOCATION_PRODUCING_SOURCES)
def test_the_detector_fires_on_each_location_producing_shape(label: str, source: str) -> None:
    """Every spelling of "build a path from the root" is caught.

    Parametrised rather than folded into one module because a single combined
    fixture proves only that *something* fired; these prove each shape does.
    """
    assert len(_sites_in(source)) == 1, f"detector missed the {label} shape"


@pytest.mark.parametrize(
    ("label", "source"),
    [
        (
            "a docstring naming the field",
            '"""This key is deliberately independent of cadrumo_local_storage_root."""\n',
        ),
        (
            "a plain read passed to a walker",
            "def measure():\n    return directory_byte_total(settings.cadrumo_local_storage_root)\n",
        ),
        (
            "a plain read returned as the root",
            "def show():\n    return settings.cadrumo_local_storage_root\n",
        ),
        (
            "an override keyword, not an attribute load",
            "def isolate(tmp):\n    return override_settings(cadrumo_local_storage_root=tmp)\n",
        ),
        (
            "a join onto a category, not the root",
            'def make():\n    return settings.cadrumo_runs_dir / "trace.json"\n',
        ),
        (
            "the accessor doing its job elsewhere",
            "def make():\n    return storage_path(StorageCategory.RUNS) / trace_id\n",
        ),
    ],
)
def test_the_detector_stays_silent_on_each_control(label: str, source: str) -> None:
    """The positive controls, and the reason the gate is not a name census.

    The docstring case is the specific historical false positive: a module
    naming the field precisely to say it does not use it. The category-join
    case is the one that matters at scale -- without it a gate on "any settings
    path read" would flag hundreds of legitimate single-field consumers and be
    switched off within a week.
    """
    assert _sites_in(source) == (), f"detector wrongly fired on {label}"


def test_the_detector_follows_the_root_through_a_local_rebind() -> None:
    """A one-line rebind must not launder a join past the gate.

    Both statements are unremarkable alone -- a plain read, then a join on an
    ordinary local -- and together they produce a location. A receiver-only
    walk sees neither, so the gate would pass a join it never saw.
    """
    source = (
        "def build(settings, bucket_id):\n"
        "    root = settings.cadrumo_local_storage_root\n"
        '    return root / "buckets" / bucket_id / "db"\n'
    )
    sites = _sites_in(source)
    assert len(sites) == 1, "the rebound join was not detected"
    assert sites[0].function == "build"


def test_the_detector_follows_a_rebind_into_a_closure() -> None:
    """A closure genuinely sees its host's names, so the binding reaches it."""
    source = (
        "def outer(settings):\n"
        "    root = settings.cadrumo_local_storage_root\n"
        "    def inner():\n"
        '        return root / "scratch"\n'
        "    return inner\n"
    )
    (site,) = _sites_in(source)
    assert site.function == "outer.inner"


@pytest.mark.parametrize(
    ("label", "source"),
    [
        (
            "a local bound from a fixture, not the root",
            'def build(tmp_path):\n    root = tmp_path / "state"\n    return root / "buckets"\n',
        ),
        (
            "a local bound from a category, not the root",
            'def build(settings):\n    root = settings.cadrumo_runs_dir\n    return root / "trace.json"\n',
        ),
        (
            "a same-named local in a sibling function",
            "def bind(settings):\n"
            "    root = settings.cadrumo_local_storage_root\n"
            "    return root\n"
            "\n"
            "def unrelated(tmp_path):\n"
            "    root = tmp_path\n"
            '    return root / "scratch"\n',
        ),
        (
            "a join on a name bound after it",
            'def build(tmp_path, settings):\n    target = tmp_path / "a"\n    root = settings.cadrumo_local_storage_root\n    return target\n',
        ),
    ],
)
def test_the_rebind_tracking_does_not_flag_an_unrelated_local(label: str, source: str) -> None:
    """The control on the binding tracker itself.

    ``root`` is an ordinary variable name and most of its uses have nothing to
    do with storage. A tracker that flagged any local called ``root``, or that
    let one function's binding reach another's, would fire on healthy code --
    and a gate that fires on healthy code is one somebody weakens or deletes.
    Only a name bound *from the root*, used *after* that binding, in that scope
    or one it encloses, counts.
    """
    assert _sites_in(source) == (), f"the rebind tracker wrongly fired on {label}"


def test_the_detector_attributes_a_site_to_its_innermost_function() -> None:
    """Declaration keys must name the function that actually joins."""
    source = (
        "def outer():\n"
        "    def inner():\n"
        '        return settings.cadrumo_local_storage_root / "scratch"\n'
        "    return inner\n"
    )
    (site,) = _sites_in(source)
    assert site.function == "outer.inner"


def test_the_byte_prefilter_admits_every_shape_the_detector_fires_on(tmp_path: Path) -> None:
    """Teeth for the pre-filter: a module the detector would flag is never skipped.

    :func:`_may_join_onto_root` decides from bytes whether a module is worth
    parsing at all, so a firing shape it rejected would be a site that silently
    stops being reported -- a gate going green by not looking, which is this
    instrument's worst failure mode. Driven from the same corpus of shapes as
    the detector's own discrimination tests, so a newly supported spelling
    cannot be added to one without facing the other.
    """
    for label, source in LOCATION_PRODUCING_SOURCES:
        assert _sites_in(source), f"sanity: the detector must fire on {label!r}"
        module = tmp_path / "candidate.py"
        module.write_text(source, encoding="utf-8")
        assert _may_join_onto_root(module), (
            f"the pre-filter rejected {label!r}, so a real module of that shape would be skipped "
            "unparsed and its join site would never be reported"
        )


def test_the_byte_prefilter_rejects_a_module_that_cannot_hold_a_site(tmp_path: Path) -> None:
    """The filter must actually filter, or it buys nothing.

    Paired with the admission test above: together they state that the filter
    separates the two populations rather than answering the same way for both.
    """
    module = tmp_path / "unrelated.py"
    module.write_text('def make():\n    return settings.some_other_dir / "scratch"\n', encoding="utf-8")
    assert not _may_join_onto_root(module)
    assert not _sites_in(module.read_text(encoding="utf-8")), "sanity: this shape must not be a site"
