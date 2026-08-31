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

This is deliberately narrower than "the storage root has exactly one reader",
which is a post-burndown property: it cannot hold until every ad-hoc site is
enrolled, and a gate red at HEAD by 68 legitimate reads gets allowlisted into
meaninglessness or deleted. The narrowing is recorded here rather than only in
a commit message because a gate that quietly covers less than its ruling
implies is how a campaign believes itself finished.

**A second, different property is not covered here at all**: that a test must
not hardcode a taxonomy-governed directory or file name. That is literal
vocabulary, not join provenance, and it lives in the settings-lifecycle gate,
which scans production modules only. Extending it across the test corpus is
its own burndown. Neither gate subsumes the other -- a literal scan cannot see
a path built by joining, and this gate cannot see a name spelled out in full.

Following a rebind
------------------
A receiver-only walk is evaded by one line, so the detector follows the root
through a function-local binding: a name assigned the root, then joined, is a
join. Scope is the function plus the scopes enclosing it, and no further --
chasing the root through parameters and returns is where a heuristic starts
flagging healthy code, and ``root`` is an ordinary variable name. That
undercount mattered beyond tidiness: this table's emptiness is a burndown
closure signal, so a blind spot in the detector is a false completion signal,
which is worse than a missing gate because it reads as proof.

Two tables, both keyed by module and enclosing function:

- :data:`PERMITTED_PRODUCERS` -- the resolvers that exist to turn the root into
  a path. Permanent.
- :data:`PENDING_ENROLLMENT` -- sites that predate the taxonomy and are owned
  by a named ruling. **This table may only shrink.**

The anti-rot teeth are what make a declared table acceptable here at all. Each
entry records how many join sites its function carries, and the gate re-runs
the detector against it: an entry whose function no longer joins, or joins a
different number of times, fails. So migrating a pending site reds the gate
until its entry is struck, and adding a join to an already-declared function
reds it too. The table cannot silently widen, and it cannot outlive the debt it
describes. A site count scoped to one named function is not a census of the
tree -- it moves only on the event being gated.
"""

from __future__ import annotations

import ast
from functools import cache
from typing import TYPE_CHECKING, Final, NamedTuple

import pytest

from ..core.storage_taxonomy import STORAGE_ROOT_SETTINGS_FIELD
from ._inventory import aeat_relative, ast_for_path, package_python_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


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


class PendingSite(NamedTuple):
    """A pre-taxonomy join site awaiting enrollment, with its owning ruling."""

    module: str
    function: str
    site_count: int
    disposition: str
    """Which burndown owns this entry -- see :data:`PENDING_DISPOSITIONS`.

    Production enrollment and test re-expression are different work with
    different rules: one routes a call site through the accessor, the other
    must keep a test defending the property it was written for. Recording
    which keeps a reader from mechanically re-pointing a pin and gutting it.
    """

    reason: str


PERMITTED_PRODUCERS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        # The two accessors the enrollment contract names. Every enrolled site
        # resolves through one of them, so these are where the root becomes a
        # path on purpose.
        ("core/_storage_taxonomy_locations.py", "storage_path"),
        ("core/_storage_taxonomy_locations.py", "bucket_scoped_storage_path"),
        # Settings derivation: turns each root-derived member's declared
        # subpath into that field's default. It iterates the declaration
        # directly rather than carrying a table of its own.
        ("core/config.py", "Settings._resolve_output_dirs_under_storage_root"),
        # The on-disk-name pin. It must build the expected location from its own
        # oracle to measure the validator, and routing it through the accessor
        # would make it assert that the accessor equals itself -- deleting the
        # test's reason for existing while leaving it green. Joining the root is
        # not debt here; it is the measurement.
        ("core/tests/test_output_dir_state_root.py", "test_every_derived_output_dir_roots_under_storage_root"),
    },
)
"""Functions that may join onto the storage root, because producing a location is their job."""


PRODUCTION_ENROLLMENT: Final[str] = "production enrollment"
"""Route the call site through the accessor, declaring a member if none exists."""

TEST_RE_EXPRESSION: Final[str] = "test re-expression"
"""Keep the test defending its property, against the taxonomy rather than a literal."""

PENDING_DISPOSITIONS: Final[frozenset[str]] = frozenset({PRODUCTION_ENROLLMENT, TEST_RE_EXPRESSION})


PENDING_ENROLLMENT: Final[tuple[PendingSite, ...]] = ()
"""Pre-taxonomy join sites, each owned by a ruling. This table may only shrink.

Every entry here is currently a test re-expression: the production enrollments
this table opened with were migrated, and their entries went stale and were
struck by the route the shrink assertion forces. The count rose once, when the
detector learned to follow a rebind and a five-join site that had been evading
it surfaced -- an honest larger number replacing a flattering smaller one,
which is the only direction a census may legitimately grow. That site was then
re-expressed and struck too, by the same route.
"""


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
    location, so the binding has to be followed or the census undercounts --
    and an undercounting census makes an emptied burndown table read as proof
    the tree is enrolled when it is not.

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


@cache
def _discovered_sites() -> tuple[JoinSite, ...]:
    """Walk every packaged module, production and test alike.

    Cached because five assertions share one walk of the whole package and the
    tree does not change within a run.
    """
    sites: list[JoinSite] = []
    for path in package_python_files():
        tree = _tree_for(path)
        if tree is not None:
            sites.extend(root_join_sites(aeat_relative(path), tree))
    return tuple(sites)


def _tree_for(path: Path) -> ast.AST | None:
    return ast_for_path(path)


def _pending_by_key() -> dict[tuple[str, str], PendingSite]:
    return {(entry.module, entry.function): entry for entry in PENDING_ENROLLMENT}


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
    declared = PERMITTED_PRODUCERS | set(_pending_by_key())
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


def test_pending_enrollment_only_shrinks() -> None:
    """A migrated pending site must be struck, not left behind as permission."""
    counts: dict[tuple[str, str], int] = {}
    for site in _discovered_sites():
        counts[site.key] = counts.get(site.key, 0) + 1

    drifted: list[str] = []
    for key, entry in sorted(_pending_by_key().items()):
        observed = counts.get(key, 0)
        if observed != entry.site_count:
            drifted.append(
                f"{entry.module}::{entry.function} declares {entry.site_count} join site(s), found {observed}"
            )
    assert not drifted, (
        f"PENDING_ENROLLMENT has drifted from the tree: {drifted}. A count that fell means the "
        "site was migrated -- strike the entry. A count that rose means a new join was added to "
        "a function that already carried debt, which the enrollment contract forbids. This table "
        "may only shrink"
    )


def test_no_site_is_both_permitted_and_pending() -> None:
    """Permanent permission and temporary debt are different claims."""
    overlap = sorted(f"{module}::{function}" for module, function in PERMITTED_PRODUCERS & set(_pending_by_key()))
    assert not overlap, (
        f"{overlap} appear in both PERMITTED_PRODUCERS and PENDING_ENROLLMENT; a function either "
        "produces locations by design or carries debt awaiting enrollment"
    )


def test_every_pending_entry_states_its_reason_and_its_burndown() -> None:
    """Debt with no stated owner is indistinguishable from permission."""
    for entry in PENDING_ENROLLMENT:
        assert entry.reason.strip(), f"{entry.module}::{entry.function} declares no reason"
        assert entry.site_count > 0, f"{entry.module}::{entry.function} declares no join sites"
        assert entry.disposition in PENDING_DISPOSITIONS, (
            f"{entry.module}::{entry.function} declares disposition {entry.disposition!r}, which "
            f"is not one of {sorted(PENDING_DISPOSITIONS)}. Routing a call site through the "
            "accessor and re-expressing a pin are different work with different rules"
        )


# --------------------------------------------------------------------- #
# Discrimination: each shape fires, and each control does not            #
# --------------------------------------------------------------------- #


def _sites_in(source: str) -> tuple[JoinSite, ...]:
    return root_join_sites("synthetic.py", ast.parse(source))


@pytest.mark.parametrize(
    ("label", "source"),
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
    ],
)
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
    walk sees neither, so the census undercounts, and an undercounting census
    makes an emptied burndown table read as proof the tree is enrolled.
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
