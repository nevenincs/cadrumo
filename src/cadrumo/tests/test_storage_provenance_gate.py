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

Scope, stated exactly
---------------------
The enforced property is **location production**, not readership. Reading the
root as the root -- handing it to a disk-usage walker, reporting it, scanning
beneath it -- produces no location and is not a finding; at the time of
writing 68 such reads exist and every one is legitimate. Joining onto the root
produces a location, and only the declared producers may do that.

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

from ..core import STORAGE_ROOT_SETTINGS_FIELD
from ._inventory import aeat_relative, ast_for_path, package_python_files

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


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
    reason: str


PERMITTED_PRODUCERS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        # The two accessors the enrollment contract names. Every enrolled site
        # resolves through one of them, so these are where the root becomes a
        # path on purpose.
        ("core/_storage_taxonomy.py", "storage_path"),
        ("core/_storage_taxonomy.py", "bucket_scoped_storage_path"),
        # Settings derivation: turns each root-derived member's declared
        # subpath into that field's default. It iterates the declaration
        # directly rather than carrying a table of its own.
        ("core/config.py", "Settings._resolve_output_dirs_under_storage_root"),
    },
)
"""Functions that may join onto the storage root, because producing a location is their job."""


PENDING_ENROLLMENT: Final[tuple[PendingSite, ...]] = (
    PendingSite(
        module="core/config.py",
        function="Settings._resolve_database_url_for_active_profile",
        site_count=2,
        reason=(
            "Builds the cold-start root-fallback database path and the per-bucket database path "
            "by joining module-local name constants onto the root. Both need declared members "
            "before they can resolve through the accessor -- the root-fallback database file, "
            "and the database file beneath the per-bucket db directory, which is a member while "
            "the file inside it is not."
        ),
    ),
    PendingSite(
        module="core/_config_storage_route.py",
        function="classify_storage_route_for_settings",
        site_count=1,
        reason=(
            "Re-derives the same root-fallback database path to classify the storage route. This "
            "is one of the duplicate copies the name unification exists to delete, and it goes "
            "when the root-fallback database becomes a declared member."
        ),
    ),
    PendingSite(
        module="adapters/persistence/storage/master_key/_master_key.py",
        function="refuse_unsecured_bucket_with_real_profile",
        site_count=1,
        reason=(
            "A third inline copy of the per-bucket database path, assembled from the adapter's "
            "own layout constants. It resolves through the bucket-scoped accessor once the "
            "database file beneath the bucket db directory is a declared member."
        ),
    ),
    PendingSite(
        module="core/tests/test_config_state_root.py",
        function="test_explicit_substrate_override_still_wins",
        site_count=2,
        reason=(
            "Pins that an explicit per-field substrate override beats root derivation, and "
            "spells the expected paths by joining the root. Re-expression must keep it defending "
            "that property -- asserting against the taxonomy's resolved value, not against the "
            "accessor equalling itself."
        ),
    ),
    *(
        PendingSite(
            module="adapters/persistence/storage/master_key/tests/test_master_key_file_fallback.py",
            function=f"TestFileFallbackProvider.{name}",
            site_count=count,
            reason=(
                "Reaches into a bucket's keystore by joining the root to assert the file-fallback "
                "provider's on-disk behaviour. These are pins-by-design: the keystore layout is "
                "what they exist to defend, so each must be re-expressed against the declared "
                "bucket- and keystore-scoped members rather than mechanically re-pointed."
            ),
        )
        for name, count in (
            ("test_bootstrap_activation_mints_distinct_persisted_bucket_dek", 1),
            ("test_tampered_bucket_dek_raises_localized_master_key_unavailable_without_path", 1),
            ("test_bucket_dek_manifest_without_dek_fails_closed", 1),
            ("test_fallback_bucket_id_does_not_authorize_dek_enrollment", 1),
            ("test_existing_dek_without_manifest_does_not_authorize_activation", 2),
        )
    ),
)
"""Pre-taxonomy join sites, each owned by a ruling. This table may only shrink."""


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


def root_join_sites(module: str, tree: ast.AST) -> tuple[JoinSite, ...]:
    """Return every place ``module`` joins onto the storage root.

    A pure function over a display name and a parsed tree, so the
    discrimination tests can hand it synthetic source and prove each shape
    fires or does not. The innermost enclosing function wins, so a join inside
    a closure is attributed to the closure rather than to its host.
    """
    spans = _function_spans(tree)
    sites: list[JoinSite] = []
    for lineno in sorted(_join_linenos(tree)):
        enclosing = [(start, name) for start, end, name in spans if start <= lineno <= end]
        function = max(enclosing)[1] if enclosing else "<module>"
        sites.append(JoinSite(module=module, function=function, lineno=lineno))
    return tuple(sites)


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


def test_discovery_finds_the_declared_producers() -> None:
    """A detector that finds nothing would satisfy every assertion below."""
    sites = _discovered_sites()
    assert sites, (
        "no storage-root join site found anywhere in the package. The resolvers must join onto "
        "the root -- that is how they produce a path -- so an empty result means the detector "
        "stopped working, not that the tree became clean"
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


def test_every_pending_entry_states_its_reason() -> None:
    """Debt with no stated owner is indistinguishable from permission."""
    for entry in PENDING_ENROLLMENT:
        assert entry.reason.strip(), f"{entry.module}::{entry.function} declares no reason"
        assert entry.site_count > 0, f"{entry.module}::{entry.function} declares no join sites"


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
