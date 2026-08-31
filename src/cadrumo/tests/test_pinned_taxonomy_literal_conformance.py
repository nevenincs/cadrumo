"""``PINNED_TAXONOMY_LITERALS`` is a claim about the module body, and now a checked one.

Forty-plus test modules across the tree carry a docstring-adjacent declaration
of this shape::

    PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"buckets", "db"})
    \"\"\"Taxonomy-vocabulary literals this module deliberately pins.\"\"\"

The declaration exists to distinguish a deliberate independent oracle (a
hand-typed on-disk name asserted against what the real accessor resolves to,
so the test does not compare the taxonomy with itself) from an unmigrated
scaffold path that should route through the accessor instead. That
distinction is real and it is the whole reason the literal-corpus
burndown reads every hit by hand rather than bulk-migrating.

Until this gate, the set was prose: nothing checked that a declared literal
still appeared anywhere in its module, and nothing checked that every
taxonomy-vocabulary literal a module actually used was declared. Both gaps
are real, in different directions:

- **Stale declaration** (mode 1). A literal is declared pinned but the code
  that used it was rewritten or deleted. The module now claims to defend an
  on-disk name it no longer even mentions.
- **Undeclared pin** (mode 2). A taxonomy segment is hand-typed in a module
  that already opted in to declaring its pins, but this one was never added
  to the set. Either an unmigrated site hiding among legitimate pins, or a
  genuine pin nobody wrote down.

Why this is not the R14 tautology
----------------------------------
The failure mode the ``PINNED_TAXONOMY_LITERALS`` idea itself exists to avoid
is re-expressing an oracle through the accessor it should independently
check, so both sides move together and the assertion passes unconditionally.
This gate does not have that shape: the two sides it compares have
independent authors and independent reasons to change. The declaration is a
human's stated claim about intent, edited by hand. The literal usage is
whatever the module's test bodies actually contain, discovered by walking the
AST -- nobody edits it "to keep the gate green" without also changing what
the test asserts. A rename moves one side and not the other; that is
precisely the drift class the gate exists to catch, not a coincidence that
happens to make it pass. A synthetic counter-example is required and given
below, in the discrimination tests: seeded source that is stale in one
direction and under-declared in the other, proving the comparison rejects
both, with no seed left behind in the tree once this module is written.

Scope, by design
-----------------
Only modules that **already** declare ``PINNED_TAXONOMY_LITERALS`` are
scanned. The alternative -- inferring which bare tmp_path-rooted literal is a
deliberate pin versus an unrelated fixture root versus a different namespace
entirely -- is exactly the anchor-resolution problem the wider literal-corpus
census is still hardening, and duplicating it here would just be a second,
less careful copy of that resolver. Scoping to opted-in modules sidesteps the
anchor question outright: a module that declares the set has already told a
human it means to defend specific literals, so this gate only has to check
that the declaration and the module agree with each other.

What counts as "used"
----------------------
Any string constant, anywhere in the module (a bare ``/``-join operand, a
``joinpath``/``Path(...)`` argument, a dict value, a tuple element later
unpacked into a join -- deliberately not shape-restricted, because a first
pass that only matched ``/``-join chains missed the dominant real pattern: a
hand-maintained oracle table, such as ``core/tests/test_output_dir_state_root.py``'s
``DERIVED_OUTPUT_SUBPATHS``, stores its pinned literals as dict values and
tuple elements, never as a join chain at all) whose value exactly equals a
taxonomy vocabulary token. Two exclusions keep this from misfiring on prose:

- A constant containing a newline is a docstring or an embedded multi-line
  text/script blob, never a real path segment -- excluded outright.
- A constant longer than :data:`_MAX_TOKEN_LEN` cannot be a taxonomy token
  (the longest declared token is under 32 characters) -- excluded as a second,
  independent guard against a prose sentence that happens to contain no
  newline.

Both exclusions are themselves a structural blind spot, not just a
convenience: the newline exclusion means a literal that is genuinely pinned
but lives inside a multi-line embedded subprocess-script string (real,
observed once: :data:`EMBEDDED_LITERAL_EXCEPTIONS`) reads as unused. That is
accepted and named rather than chased with more heuristics that would
reopen the prose false-positive risk the exclusion exists to close.

Two more tables hold verified, human-read exceptions rather than silently
widening the detector's precision:

- :data:`HOMONYM_EXCEPTIONS` -- a taxonomy-vocabulary word used in a module
  that also pins taxonomy literals, but not to mean the storage taxonomy at
  all: a CLI verb (``registry`` in ``app registry inspect``), a *different*
  registry entirely (the calculation-registry TOML tree, already documented
  in the owning module's own docstring), a closed-enum axis's member value
  (``StorageGrouping``'s ``"logs"``), or an arbitrary settings-override probe
  value that happens to coincide with a directory name. Every entry states
  which.
- :data:`EMBEDDED_LITERAL_EXCEPTIONS` -- the inverse: a declared literal that
  is genuinely used, verified by reading the module, but only inside a
  multi-line text blob this AST scan cannot see into.

Neither table may hide a real gap -- the reconciliation tests at the bottom
assert every entry still describes what it claims: a homonym must still be
present and still undeclared (or the exception is dead weight), and an
embedded-literal exception must still be declared (or the declaration itself
went stale and the exception is now defending nothing).

:data:`PENDING_UNDECLARED` is different in kind from both: not a verified
exception but acknowledged debt in a module actively being edited by a
concurrent band of this same campaign at the time this gate was written
(``entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`` gained its
``PINNED_TAXONOMY_LITERALS`` declaration mid-edit, uncommitted, while this
gate was being built -- editing it further here would collide with live work
in the same file). Mirrors :data:`~cadrumo.tests.test_storage_provenance_gate.PENDING_ENROLLMENT`:
it may only shrink, and a reconciliation test asserts every entry is still
genuinely outstanding.
"""

from __future__ import annotations

import ast
from functools import cache
from pathlib import PurePosixPath
from typing import Final

import pytest

from ..core.storage_taxonomy_locations import STORAGE_TAXONOMY
from ._inventory import aeat_relative, ast_for_path, package_python_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_DECLARATION_NAME: Final[str] = "PINNED_TAXONOMY_LITERALS"
_MAX_TOKEN_LEN: Final[int] = 48
"""Generous ceiling above the longest real taxonomy token (under 32 chars),
so a constant this long or longer cannot be one and is excluded from the
"used" scan without needing to check every candidate against the vocabulary
first."""


@cache
def _taxonomy_vocabulary() -> frozenset[str]:
    """Every taxonomy subpath's individual path segments, as bare strings.

    Deliberately the *parts*, not the joined subpath itself: a module states
    its pin as separate literals (``"financial"``, ``"invoices"``) far more
    often than as one slash-joined string, and decomposing lets a multi-part
    literal (``"financial/invoices"`` as one Python string, as the on-disk-name
    oracle in ``test_output_dir_state_root.py`` writes it) satisfy both parts
    at once without also having to register the whole joined spelling as its
    own separate token.
    """
    tokens: set[str] = set()
    for location in STORAGE_TAXONOMY.values():
        tokens.update(PurePosixPath(location.subpath).parts)
    return frozenset(tokens)


HOMONYM_EXCEPTIONS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        (
            "domain/calculations/registry/tests/test_validation_verdict_location.py",
            "registry",
        ),
        (
            "domain/calculations/registry/tests/test_validation_verdict_shape_conformance.py",
            "registry",
        ),
        # Both above: the module's own docstring already names this --
        # ``tmp_path / "registry" / "aeat"`` is the calculation-registry's
        # bundled TOML authoring tree, an unrelated different-namespace
        # concept from the storage taxonomy's ``cache/registry`` member this
        # module otherwise pins (declared as ``"cache"``, plus
        # ``"registry-verdict"`` after this change).
        (
            "entrypoints/cli/tests/test_root_fallback_write_guard.py",
            "registry",
        ),
        # A CLI verb path element -- ``("app", "registry", "inspect")`` names
        # the ``aeat app registry inspect`` command group, not a directory.
        (
            "core/tests/test_storage_taxonomy.py",
            "logs",
        ),
        # ``_axis_members(StorageGrouping) == {"state", "logs", "cache",
        # "exports"}`` -- ``StorageGrouping`` is a closed presentation-axis
        # enum unrelated to on-disk directory names; ``"logs"`` here is one of
        # its members, not a pinned path segment.
        (
            "entrypoints/cli/tests/test_root_help_shape.py",
            "invoices",
        ),
        # An arbitrary settings-override probe value
        # (``setting_env("cadrumo_invoices_dir"): str(tmp_path / "invoices")``)
        # alongside sibling probes named "probe-tokens", "probe-runs", "txs" --
        # none of which are taxonomy tokens. The module's own docstring names
        # "logs" (in a different test) as the sole deliberate pin; this one
        # coincides with the vocabulary by accident of a natural variable name,
        # not by intent to defend the "invoices" on-disk name.
        (
            "entrypoints/cli/tests/test_config_custody_profile_lifecycle.py",
            "custody",
        ),
        # The operator-chosen profile LABEL passed to ``config profile create``
        # ("custody", named for what the test exercises), not the
        # ``custody`` capsule directory the taxonomy owns. It reaches the CLI
        # as an argv token and never addresses a path.
    },
)
"""Verified coincidental collisions with the taxonomy vocabulary: read, and confirmed not a pin.

Every entry is checked below by :func:`test_every_homonym_exception_is_still_a_live_collision`.
"""


EMBEDDED_LITERAL_EXCEPTIONS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        (
            "application/tests/test_config_reset_recovery.py",
            "secrets",
        ),
        # Read and confirmed genuinely used: the module's own docstring states
        # it outright ("The `"secrets"` literal in the crash-subprocess
        # settings preamble is deliberate, not injected"). It lives inside
        # ``_SETTINGS_PREAMBLE = dedent("""...""")``, a multi-line string that
        # is itself the *text* of a subprocess script
        # (``cadrumo_secret_store_dir=root.parent / "secrets"`` as characters,
        # not as this module's own AST) -- outside what a structural scan of
        # this module's own code can see, by the same reasoning
        # ``test_storage_provenance_gate.py`` gives for why a docstring naming
        # a field is invisible to an attribute walk.
    },
)
"""Verified declared-and-genuinely-used literals this AST scan cannot see (embedded text blobs).

Every entry is checked below by :func:`test_every_embedded_literal_exception_is_still_declared`.
"""


PENDING_UNDECLARED: Final[frozenset[tuple[str, str]]] = frozenset[tuple[str, str]](
    {
        # This module gained its PINNED_TAXONOMY_LITERALS declaration
        # mid-edit, uncommitted, by a concurrent band of this same campaign
        # while this gate was being written -- editing it further here would
        # collide with that live work rather than complete it. Genuinely
        # undeclared today; expected to be struck when that band's edit lands
        # a complete declaration. May only shrink -- see
        # :func:`test_pending_undeclared_only_shrinks`.
    },
)
"""Acknowledged debt in a module a concurrent band owns mid-edit. Must only shrink."""


def _declaration_node(tree: ast.AST) -> ast.AnnAssign | None:
    """Return the module-level ``PINNED_TAXONOMY_LITERALS`` declaration, if any."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == _DECLARATION_NAME
        ):
            return node
    return None


def _declared_literals(node: ast.AnnAssign) -> frozenset[str]:
    """Return the string literals inside ``frozenset({...})``, or empty if the shape does not match."""
    call = node.value
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "frozenset"):
        return frozenset[str]()
    if not call.args or not isinstance(call.args[0], ast.Set):
        return frozenset[str]()
    return frozenset(
        element.value
        for element in call.args[0].elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    )


def used_taxonomy_literals(tree: ast.AST, declaration: ast.AnnAssign) -> dict[str, tuple[int, ...]]:
    """Return every taxonomy-vocabulary literal used in ``tree``, mapped to its line numbers.

    Excludes the declaration statement's own lines (it names its pins, it does
    not "use" them), any multi-line constant (docstring or embedded text
    blob), and any constant too long to be a real token. See the module
    docstring's "What counts as 'used'" section for why the shape is
    deliberately this broad rather than restricted to ``/``-join chains.
    """
    vocabulary = _taxonomy_vocabulary()
    declaration_lines = set(range(declaration.lineno, (declaration.end_lineno or declaration.lineno) + 1))
    hits: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        value = node.value
        if node.lineno in declaration_lines or "\n" in value or len(value) > _MAX_TOKEN_LEN:
            continue
        candidates = set(PurePosixPath(value).parts) if "/" in value else {value}
        for candidate in candidates:
            if candidate in vocabulary:
                hits.setdefault(candidate, []).append(node.lineno)
    return {literal: tuple(lines) for literal, lines in hits.items()}


class _PinnedModule:
    """One module's declared pins, actual usage, and display path."""

    __slots__ = ("declared", "module", "used")

    def __init__(self, module: str, declared: frozenset[str], used: dict[str, tuple[int, ...]]) -> None:
        self.module = module
        self.declared = declared
        self.used = used


@cache
def _pinned_modules() -> tuple[_PinnedModule, ...]:
    """Walk the package once, returning every module that declares ``PINNED_TAXONOMY_LITERALS``."""
    found: list[_PinnedModule] = []
    for path in package_python_files():
        tree = ast_for_path(path)
        if tree is None:
            continue
        declaration = _declaration_node(tree)
        if declaration is None:
            continue
        found.append(
            _PinnedModule(
                module=aeat_relative(path),
                declared=_declared_literals(declaration),
                used=used_taxonomy_literals(tree, declaration),
            ),
        )
    return tuple(sorted(found, key=lambda entry: entry.module))


def test_the_scanned_corpus_is_not_degenerate() -> None:
    """The gate must be reading real declarations, not finding nothing to check.

    A bound, not a count: an exact figure rots on the next module that opts
    in -- and, as this floor learned, on the next that legitimately opts OUT
    when its pinned literal genuinely leaves the module. ``PINNED_TAXONOMY_LITERALS``
    was declared in 41 modules when this gate was written and the floor was set
    six below that, close enough that one honest removal tripped it. The floor
    is set well clear of the live population instead: it exists to catch
    discovery COLLAPSING, not to ratchet the count.
    """
    modules = _pinned_modules()
    assert len(modules) >= 25, (
        f"found only {len(modules)} module(s) declaring {_DECLARATION_NAME}, expected at least 25. "
        "Discovery has likely broken (a shape change to the declaration, or to package_python_files), "
        "not that most modules stopped pinning anything"
    )
    total_hits = sum(len(entry.used) for entry in modules)
    assert total_hits >= 35, (
        f"found only {total_hits} used-literal hit(s) across the pinning modules; the used-literal scan "
        "has likely broken, since every pinning module is expected to use at least one of its own pins"
    )


def test_every_declared_literal_is_used_in_its_module() -> None:
    """Mode 1: a declared pin that no longer appears anywhere is a stale claim."""
    exceptions = EMBEDDED_LITERAL_EXCEPTIONS
    stale = sorted(
        f"{entry.module}: {literal!r}"
        for entry in _pinned_modules()
        for literal in entry.declared - set(entry.used)
        if (entry.module, literal) not in exceptions
    )
    assert not stale, (
        f"{_DECLARATION_NAME} declares a literal no longer used in its own module: {stale}. Either the "
        "literal is genuinely gone (strike it from the declaration) or it moved into a shape this scan "
        "cannot see (an embedded text blob) -- verify by reading the module, then add it to "
        "EMBEDDED_LITERAL_EXCEPTIONS with the reason, never silently"
    )


def test_every_taxonomy_literal_in_a_pinning_module_is_declared() -> None:
    """Mode 2: a taxonomy literal used in a module that already opted in, but never declared."""
    exceptions = HOMONYM_EXCEPTIONS | PENDING_UNDECLARED
    undeclared = sorted(
        f"{entry.module}: {literal!r} (line {entry.used[literal][0]})"
        for entry in _pinned_modules()
        for literal in set(entry.used) - entry.declared
        if (entry.module, literal) not in exceptions
    )
    assert not undeclared, (
        f"a taxonomy-vocabulary literal is used but not declared in {_DECLARATION_NAME}: {undeclared}. "
        "Either this is a genuine pin -- add it to the module's declared set -- or a coincidental homonym "
        "unrelated to the storage taxonomy -- verify by reading the module, then add it to "
        "HOMONYM_EXCEPTIONS with the reason, never silently"
    )


def test_every_homonym_exception_is_still_a_live_collision() -> None:
    """A homonym exception that stopped colliding is dead weight hiding nothing -- or hiding a real gap.

    Two ways an entry can drift: the module was edited and the word no longer
    appears at all (strike the entry), or the module now *also* declares it
    (also strike it -- declaring a pin is always allowed even if this gate
    would not have required it). Either way the entry must be reconciled by
    hand, not left describing a module that moved on.
    """
    by_module = {entry.module: entry for entry in _pinned_modules()}
    drifted = []
    for module, literal in sorted(HOMONYM_EXCEPTIONS):
        entry = by_module.get(module)
        if entry is None:
            drifted.append(f"{module}: {literal!r} (module no longer declares {_DECLARATION_NAME})")
            continue
        if literal in entry.declared:
            drifted.append(f"{module}: {literal!r} (now declared -- the exception is no longer needed)")
        elif literal not in entry.used:
            drifted.append(f"{module}: {literal!r} (no longer used anywhere in the module)")
    assert not drifted, f"HOMONYM_EXCEPTIONS has drifted from the tree: {drifted}. Strike the stale entries"


def test_every_embedded_literal_exception_is_still_declared() -> None:
    """An embedded-literal exception whose declaration was struck is now defending nothing.

    The exception excuses this scan from *finding* the usage; it does not
    excuse the module from *declaring* the pin. If the declaration goes away,
    the exception has nothing left to explain and must go with it.
    """
    by_module = {entry.module: entry for entry in _pinned_modules()}
    drifted = []
    for module, literal in sorted(EMBEDDED_LITERAL_EXCEPTIONS):
        entry = by_module.get(module)
        if entry is None or literal not in entry.declared:
            drifted.append(f"{module}: {literal!r}")
    assert not drifted, (
        f"EMBEDDED_LITERAL_EXCEPTIONS names a literal no longer declared by its module: {drifted}. "
        "Strike the entry -- there is no declaration left for it to excuse"
    )


def test_pending_undeclared_only_shrinks() -> None:
    """A migrated pending entry must be struck, never left behind as a permanent excuse."""
    by_module = {entry.module: entry for entry in _pinned_modules()}
    drifted = []
    for module, literal in sorted(PENDING_UNDECLARED):
        entry = by_module.get(module)
        if entry is None:
            drifted.append(f"{module}: {literal!r} (module no longer declares {_DECLARATION_NAME})")
            continue
        if literal in entry.declared:
            drifted.append(f"{module}: {literal!r} (now declared -- strike the pending entry)")
        elif literal not in entry.used:
            drifted.append(f"{module}: {literal!r} (no longer used anywhere in the module)")
    assert not drifted, f"PENDING_UNDECLARED has drifted from the tree: {drifted}. Strike the stale entries"


def test_no_pair_is_both_homonym_and_pending() -> None:
    """A collision and acknowledged debt are different claims about the same pair."""
    overlap = sorted(HOMONYM_EXCEPTIONS & PENDING_UNDECLARED)
    assert not overlap, f"{overlap} appear in both HOMONYM_EXCEPTIONS and PENDING_UNDECLARED"


# --------------------------------------------------------------------- #
# Discrimination: the comparison fires on seeded drift, on synthetic     #
# in-memory source only -- no file in the tree is ever mutated to prove  #
# this, so there is no mutation window to clean up afterward.            #
# --------------------------------------------------------------------- #


def _synthetic_module(source: str) -> _PinnedModule:
    tree = ast.parse(source)
    declaration = _declaration_node(tree)
    assert declaration is not None, "synthetic fixture must declare PINNED_TAXONOMY_LITERALS"
    return _PinnedModule(
        module="synthetic.py",
        declared=_declared_literals(declaration),
        used=used_taxonomy_literals(tree, declaration),
    )


def test_the_detector_fires_on_a_stale_declaration() -> None:
    """A declared literal absent from the rest of the module is caught."""
    source = (
        'from typing import Final\n\nPINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"buckets"})\n'
        "\ndef f(tmp_path):\n    return tmp_path\n"
    )
    entry = _synthetic_module(source)
    assert entry.declared - set(entry.used) == {"buckets"}


def test_the_detector_fires_on_an_undeclared_pin() -> None:
    """A taxonomy literal used but never declared is caught."""
    source = (
        'from typing import Final\n\nPINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"buckets"})\n'
        '\ndef f(tmp_path):\n    return tmp_path / "buckets" / "db"\n'
    )
    entry = _synthetic_module(source)
    assert set(entry.used) - entry.declared == {"db"}


def test_the_detector_stays_silent_when_declared_and_used_agree() -> None:
    """The clean case: nothing is flagged in either direction."""
    source = (
        'from typing import Final\n\nPINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"buckets", "db"})\n'
        '\ndef f(tmp_path):\n    return tmp_path / "buckets" / "db"\n'
    )
    entry = _synthetic_module(source)
    assert entry.declared - set(entry.used) == set()
    assert set(entry.used) - entry.declared == set()


def test_the_detector_catches_a_dict_value_and_a_tuple_element_not_only_a_join_chain() -> None:
    """The dominant real shape: an oracle table, not a ``/``-join.

    A first version of this scan only matched ``BinOp`` division chains and
    ``joinpath``/``Path(...)`` calls, and missed the on-disk-name oracle
    pattern entirely -- a dict literal's values and a tuple literal's elements,
    later joined by unpacking (``root.joinpath(*subpath.split("/"))``,
    ``tmp_path.joinpath(*relative_parts)``). Both shapes must be seen without
    following the unpack at all, because the literal is already a plain
    ``ast.Constant`` at the point it is declared.
    """
    source = (
        'from typing import Final\n\nPINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"buckets"})\n'
        '\nTABLE = {"a": "db", "b": ("blobs", "live-state")}\n'
    )
    entry = _synthetic_module(source)
    assert {"db", "blobs", "live-state"} <= set(entry.used)


@pytest.mark.parametrize(
    ("label", "source"),
    [
        (
            "a docstring mentioning a taxonomy word inside prose",
            "from typing import Final\n\n"
            '"""This module talks about the llm usage/telemetry/cache logical paths."""\n'
            "PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset(set())\n",
        ),
        (
            "a multi-line embedded text blob containing a slash-joined literal",
            "from typing import Final\nfrom textwrap import dedent\n\n"
            "PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset(set())\n"
            'SCRIPT = dedent("""\\nroot.parent / "secrets"\\n""")\n',
        ),
        (
            "an over-length string that happens to contain a taxonomy word",
            "from typing import Final\n\nPINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset(set())\n"
            'MESSAGE = "this failure message is unusually long and mentions a cache in passing here"\n',
        ),
    ],
)
def test_the_detector_stays_silent_on_each_control(label: str, source: str) -> None:
    """The positive controls: prose, embedded blobs, and long strings must not register as 'used'.

    The middle case is the specific, real, accepted blind spot the module
    docstring names: it proves *why* :data:`EMBEDDED_LITERAL_EXCEPTIONS` has
    to exist as a verified table rather than the scan simply reaching further.
    """
    entry = _synthetic_module(source)
    assert entry.used == {}, f"detector wrongly registered a hit for {label}: {entry.used}"


def test_a_module_with_no_declaration_is_out_of_scope() -> None:
    """A module that never opted in is not scanned at all -- confirmed against a real file."""
    non_pinning = next(path for path in package_python_files() if path.name == "test_storage_kind_parity_gate.py")
    tree = ast_for_path(non_pinning)
    assert tree is not None
    assert _declaration_node(tree) is None, (
        "fixture assumption broken: test_storage_kind_parity_gate.py now declares "
        f"{_DECLARATION_NAME}; pick a different non-pinning fixture module"
    )
