"""Real-filesystem checks for the private-helper body census.

Mirrors `dev/quality/tests/test_fixture_census.py`'s own shape: the mechanism
is proven against real miniature repository trees under ``tmp_path``, never a
mock or a hand-built AST. The regression pin at the bottom follows
`dev/packaging/tests/test_hashing.py`'s ``_REHOMED_STREAMED_DIGEST_SITES``
precedent -- a small, reasoned, (path, function)-keyed allowlist checked for
staleness -- scoped to the four canonical homes the 2026-08-15 B16/B18/B24/B25
duplicate-helper burndown built this session.
"""

from __future__ import annotations

import ast
from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest

from ..fixture_census import FixtureCensusError
from ..helper_body_census import census

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_source(root: Path, relative_path: str, source: str) -> None:
    """Write one Python source file into a real miniature repository tree."""
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(source).lstrip(), encoding="utf-8")


def _scaffold(root: Path) -> None:
    """Create the minimal source universe `iter_source_files` requires."""
    _write_source(root, "conftest.py", "pass\n")
    (root / "dev").mkdir(exist_ok=True)
    (root / "packaging").mkdir(exist_ok=True)


# --------------------------------------------------------------------------
# Mechanism: the census bites on a real duplicate and clears on the fix
# --------------------------------------------------------------------------


def test_body_identical_helper_under_two_names_is_detected(tmp_path: Path) -> None:
    """A helper hand-copied under a fresh name in another file is caught.

    This is exactly the aliasing class a name-keyed search cannot find: `rg
    "_seed_ready_profile"` in one file reads as unique, and a reviewer would
    need to already know the other file's different name to notice.
    """
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        def _seed(tmp_path):
            record = {"a": 1, "b": 2}
            return record
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        def _prepare(tmp_path):
            record = {"a": 1, "b": 2}
            return record
        """,
    )

    result = census(tmp_path)

    assert result.aliased_behaviour_count == 1
    (behaviour,) = result.aliased_behaviours
    assert behaviour.function_names == ("_prepare", "_seed")
    assert len(behaviour.sites) == 2


def test_removing_the_duplicate_definition_clears_the_alias(tmp_path: Path) -> None:
    """Break it deliberately, confirm it reds, restore -- the gate reverses cleanly.

    Reuses the exact red fixture above, then rewrites the second file to
    delegate to the first instead of re-declaring the body, and re-censuses
    the same tmp_path tree. Nothing under the real repository's `src` is ever
    touched; the whole proof lives in a throwaway directory.
    """
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        def _seed(tmp_path):
            record = {"a": 1, "b": 2}
            return record
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        def _prepare(tmp_path):
            record = {"a": 1, "b": 2}
            return record
        """,
    )
    assert census(tmp_path).aliased_behaviour_count == 1, "precondition: the red state must actually be red"

    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        from .test_one import _seed as _prepare
        """,
    )

    assert census(tmp_path).aliased_behaviour_count == 0


def test_fixture_decorated_bodies_are_excluded(tmp_path: Path) -> None:
    """A `@pytest.fixture` duplicate is `fixture_census.py`'s population, not this one.

    Proves the two censuses are disjoint by construction rather than by
    convention: this module must never re-report what the fixture census
    already owns.
    """
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        import pytest

        @pytest.fixture
        def _bucket():
            return {"a": 1}
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        import pytest

        @pytest.fixture
        def _store():
            return {"a": 1}
        """,
    )

    result = census(tmp_path)

    assert result.helper_count == 0
    assert result.aliased_behaviour_count == 0


def test_symbol_origin_disambiguates_same_shaped_calls_to_different_functions(tmp_path: Path) -> None:
    """Same AST shape, different imported callee, is NOT one behaviour.

    Mirrors the false-positive `fixture_census.py`'s own docstring documents:
    two bodies can dump identically while calling entirely different
    functions, because the dump records the local NAME, not what it resolves
    to.
    """
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        from cadrumo.identity import census as identity_census

        def _run():
            return identity_census("HEAD")
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        from cadrumo.taxonomy import census as taxonomy_census

        def _go():
            return taxonomy_census("HEAD")
        """,
    )

    result = census(tmp_path)

    assert result.aliased_behaviour_count == 0


def test_performs_no_work_bodies_are_excluded_from_aliasing(tmp_path: Path) -> None:
    """A bare-name return is a per-module value binding, not a shared behaviour."""
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        _BUCKET_ID = "alpha"

        def _bucket_id():
            return _BUCKET_ID
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        _BUCKET_ID = "beta"

        def _bucket_id():
            return _BUCKET_ID
        """,
    )

    result = census(tmp_path)

    assert result.aliased_behaviour_count == 0


def test_context_manager_decorated_body_does_not_alias_with_a_bare_function(tmp_path: Path) -> None:
    """A `@contextlib.contextmanager` body and a bare function sharing statements run differently.

    Grouping them as one behaviour would be a false positive: consolidating
    them would silently strip the context-manager protocol from one call
    site. The decorator identity is part of the aliasing key, not an
    afterthought.
    """
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        import contextlib

        @contextlib.contextmanager
        def _guard():
            state = {"open": True}
            yield state
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        def _guard_plain():
            state = {"open": True}
            yield state
        """,
    )

    result = census(tmp_path)

    assert result.aliased_behaviour_count == 0


def test_non_underscore_export_from_a_private_support_module_is_a_candidate(tmp_path: Path) -> None:
    """A promoted export from a `_support.py`-style module is still in scope.

    B18's real regression: the canonical helper was renamed to
    `declared_live_write` (no leading underscore, since it is the module's
    public export) while a leftover copy elsewhere kept the private spelling
    `_declared_live_write`. Restricting candidacy to underscored NAMES only
    would have made this exact pair invisible again.
    """
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/_support.py",
        """
        import contextlib

        @contextlib.contextmanager
        def declared_thing(key):
            state = {"key": key}
            yield state
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_leftover.py",
        """
        import contextlib

        @contextlib.contextmanager
        def _declared_thing(key):
            state = {"key": key}
            yield state
        """,
    )

    result = census(tmp_path)

    assert result.aliased_behaviour_count == 1
    (behaviour,) = result.aliased_behaviours
    assert behaviour.function_names == ("_declared_thing", "declared_thing")


def test_closed_over_module_constant_is_labeled_and_still_reported(tmp_path: Path) -> None:
    """A body-identical group that closes over a same-named constant is FLAGGED, not silenced.

    A real-world proof: `_READY_PROFILE_FACTS` carried a
    different taxpayer surname per file, and `_WORKFLOW` pointed at a
    different CI YAML file per file, while both functions' bodies were
    genuinely identical. This is that shape in miniature -- two files declare
    a DIFFERENT `_SUBJECT` constant and a body-identical function that reads
    it. The group must still be reported (the shape really is duplicated),
    but labeled so a reviewer parameterises rather than deletes.
    """
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        _SUBJECT = "alpha"

        def _describe():
            return {"subject": _SUBJECT, "kind": "fixed"}
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        _SUBJECT = "beta"

        def _narrate():
            return {"subject": _SUBJECT, "kind": "fixed"}
        """,
    )

    result = census(tmp_path)

    assert result.aliased_behaviour_count == 1
    (behaviour,) = result.aliased_behaviours
    assert behaviour.function_names == ("_describe", "_narrate")
    assert behaviour.is_constant_dependent
    assert behaviour.closed_over_constants == ("_SUBJECT",)


def test_literal_only_duplicate_is_not_labeled_constant_dependent(tmp_path: Path) -> None:
    """A duplicate with no free module-level name is plain TRUE-DUPLICATION, not flagged."""
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        def _tax_id():
            return "X1234567L"
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        def _identifier():
            return "X1234567L"
        """,
    )

    result = census(tmp_path)

    assert result.aliased_behaviour_count == 1
    (behaviour,) = result.aliased_behaviours
    assert not behaviour.is_constant_dependent
    assert behaviour.closed_over_constants == ()


def test_a_local_variable_shadowing_a_module_constant_is_not_flagged(tmp_path: Path) -> None:
    """A same-named local variable shadows the module constant -- not a real reference.

    Without this, a module constant `_SUBJECT` sitting anywhere in the file
    would poison every unrelated helper that merely happens to assign a
    same-named local of its own.
    """
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        _SUBJECT = "unused-by-either-function"

        def _via_local_one():
            _SUBJECT = "irrelevant"
            return {"subject": _SUBJECT}
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        def _via_local_two():
            _SUBJECT = "irrelevant"
            return {"subject": _SUBJECT}
        """,
    )

    result = census(tmp_path)

    assert result.aliased_behaviour_count == 1
    (behaviour,) = result.aliased_behaviours
    assert not behaviour.is_constant_dependent
    assert behaviour.closed_over_constants == ()


def test_a_parameter_shadowing_a_module_constant_is_not_flagged(tmp_path: Path) -> None:
    """A same-named parameter shadows the module constant -- not a real reference."""
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        _SUBJECT = "unused-by-either-function"

        def _via_parameter_one(_SUBJECT):
            return {"subject": _SUBJECT}
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        def _via_parameter_two(_SUBJECT):
            return {"subject": _SUBJECT}
        """,
    )

    result = census(tmp_path)

    assert result.aliased_behaviour_count == 1
    (behaviour,) = result.aliased_behaviours
    assert not behaviour.is_constant_dependent
    assert behaviour.closed_over_constants == ()


def test_delegating_wrapper_closing_over_a_constant_is_not_counted_as_duplication(tmp_path: Path) -> None:
    """A real-tree finding, in miniature: a thin per-file wrapper is the SOLUTION.

    `_write_modelo`/`_load_revision` in `domain/calculations/registry/tests/`
    were reported as CONSTANT-DEPENDENT duplication until this test's
    counterpart shipped -- each was a one-line forward of its own per-file
    constant into a single shared implementation, which is composition, not
    debt. Two files here do the same shape: call a function imported from a
    real shared module, passing along a per-file constant.
    """
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/_shared_writer.py",
        """
        def write_record(value):
            return {"value": value}
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        from ._shared_writer import write_record

        _VALUE = "alpha"

        def _write():
            return write_record(_VALUE)
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        from ._shared_writer import write_record

        _VALUE = "beta"

        def _write():
            return write_record(_VALUE)
        """,
    )

    result = census(tmp_path)

    assert result.aliased_behaviour_count == 0
    assert result.delegating_wrapper_count == 2
    delegates_to = {record.delegates_to for record in result.delegating_wrappers}
    assert delegates_to == {"cadrumo.tests._shared_writer.write_record"}


def test_real_work_closing_over_a_constant_still_counts_as_duplication(tmp_path: Path) -> None:
    """A body that does more than forward one call stays in the duplicate bucket.

    Contrast with the delegating-wrapper case above: this body constructs a
    dict of two entries itself rather than handing everything to one
    imported call, so it is real duplicated logic, not composition, and must
    still be reported (and still labeled CONSTANT-DEPENDENT).
    """
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        _VALUE = "alpha"

        def _build():
            return {"value": _VALUE, "kind": "fixed"}
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        _VALUE = "beta"

        def _assemble():
            return {"value": _VALUE, "kind": "fixed"}
        """,
    )

    result = census(tmp_path)

    assert result.delegating_wrapper_count == 0
    assert result.aliased_behaviour_count == 1
    (behaviour,) = result.aliased_behaviours
    assert behaviour.is_constant_dependent
    assert behaviour.closed_over_constants == ("_VALUE",)


def test_a_call_reached_through_attribute_access_is_not_guessed_as_a_wrapper(tmp_path: Path) -> None:
    """The callee must be a bare imported NAME -- an attribute call is left alone, never guessed at."""
    _scaffold(tmp_path)
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_one.py",
        """
        import subprocess

        def _run():
            return subprocess.run(["true"])
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/tests/test_two.py",
        """
        import subprocess

        def _execute():
            return subprocess.run(["true"])
        """,
    )

    result = census(tmp_path)

    assert result.delegating_wrapper_count == 0
    assert result.aliased_behaviour_count == 1


# --------------------------------------------------------------------------
# Regression pin: the real canonical homes this session's burndown built
# --------------------------------------------------------------------------

#: Every entry states WHY the duplicate survives, and is keyed by
#: (path, qualname) -- never by line number, per `aeat-quality-gates`'s
#: allowlist discipline. `test_allowlist_entries_are_not_stale` fails the
#: moment a site here stops existing or stops aliasing anything, so a fix
#: that resolves an entry cannot leave a dead exemption behind unnoticed.
#:
#: Empty today. A future genuinely-forced duplicate (a different helper, a
#: different boundary) is declared here, never by weakening
#: `test_canonical_homes_carry_no_unallowlisted_duplicate` itself.
_ALLOWED_DUPLICATE_SITES: Final[dict[tuple[str, str], str]] = {}

#: Every (path, qualname) the B16/B18/B24/B25 burndown consolidated to one
#: canonical home this session. A NEW body-identical copy of any of these,
#: anywhere in the tree, is either declared above with a reason or a
#: regression.
_CANONICAL_HOMES: Final[tuple[tuple[str, str], ...]] = (
    ("dev/packaging/_hashing.py", "sha256_path"),
    ("src/cadrumo/tests/declared_command_risk.py", "declared_live_write"),
    ("src/cadrumo/adapters/persistence/storage/sql/tests/_secure_objects_support.py", "_ephemeral_secure_repo"),
    ("dev/docs/terminology_handbook/tests/_support.py", "write_concept_fragment"),
)

_SECURE_OBJECTS_SUPPORT_PATH = "src/cadrumo/adapters/persistence/storage/sql/tests/_secure_objects_support.py"
_EPHEMERAL_SECURE_REPO_CONSUMERS: Final[dict[str, frozenset[str]]] = {
    "src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_object_write_batching.py": frozenset(
        {"_ephemeral_secure_repo"},
    ),
    "src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py": frozenset(
        {"_ephemeral_secure_repo", "_ephemeral_secure_repo_at"},
    ),
}


def _module_imports(relative_path: str) -> frozenset[str]:
    """Return names imported directly from the canonical secure-object support module."""
    repository_root = Path(__file__).resolve().parents[3]
    tree = ast.parse((repository_root / relative_path).read_text(encoding="utf-8"))
    return frozenset(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module == "_secure_objects_support"
        for alias in node.names
    )


def test_ephemeral_secure_repo_has_one_shared_definition_and_direct_consumers() -> None:
    """The secure-object helpers have one owner; callers import rather than re-declare them."""
    result = census()
    definitions = {
        (record.path, record.qualname)
        for record in result.helpers
        if record.qualname in {"_ephemeral_secure_repo", "_ephemeral_secure_repo_at"}
    }

    assert definitions == {
        (_SECURE_OBJECTS_SUPPORT_PATH, "_ephemeral_secure_repo"),
        (_SECURE_OBJECTS_SUPPORT_PATH, "_ephemeral_secure_repo_at"),
    }
    for path, expected_names in _EPHEMERAL_SECURE_REPO_CONSUMERS.items():
        assert expected_names <= _module_imports(path)


def _site_key(site: str) -> tuple[str, str]:
    """Recover a body-agnostic (path, qualname) key from one census site string."""
    path, _line, qualname = site.split(":", 2)
    return (path, qualname)


def test_canonical_homes_carry_no_unallowlisted_duplicate() -> None:
    """A body-identical copy of a canonical home, anywhere else, must be declared.

    This is the property `2026-08-14-test-harness-sanity-semantic-test-corpus-
    drift-audit` found nothing could catch by name: a renamed or re-pasted
    twin of `sha256_path`, `declared_live_write`, `_ephemeral_secure_repo`, or
    `write_concept_fragment` reads as unique to a search for that one name.
    Gated on the PROPERTY (every flagged site touching a canonical home is
    allowlisted with a reason), never a tally -- the real tree's total
    aliased-behaviour count is not asserted here at all, because a module
    count trains everyone to update the constant and then detects nothing.
    """
    try:
        result = census()
    except FixtureCensusError as exc:
        pytest.fail(f"helper census could not read the tracked source tree: {exc}")

    homes = set(_CANONICAL_HOMES)
    violations: list[str] = []
    for behaviour in result.aliased_behaviours:
        keys = {_site_key(site) for site in behaviour.sites}
        if not (keys & homes):
            continue
        unresolved = sorted(key for key in keys if key not in _ALLOWED_DUPLICATE_SITES)
        if unresolved:
            violations.append(f"{behaviour.function_names}: {unresolved}")

    assert not violations, "unallowlisted duplicate(s) of a canonical helper home:\n" + "\n".join(violations)


def test_allowlist_entries_are_not_stale() -> None:
    """Every allowlisted site must still exist and still actually alias something.

    A resolved duplicate (the local copy deleted, the site renamed) leaves a
    dead entry behind if nothing checks it. This is the ratchet: the entry
    stops being evidence and starts being a stale exemption the moment either
    condition breaks.
    """
    try:
        result = census()
    except FixtureCensusError as exc:
        pytest.fail(f"helper census could not read the tracked source tree: {exc}")

    existing_sites = {(record.path, record.qualname) for record in result.helpers}
    aliased_sites = {_site_key(site) for behaviour in result.aliased_behaviours for site in behaviour.sites}

    stale = [
        f"{key}: {'site no longer exists' if key not in existing_sites else 'no longer aliases anything'}"
        for key in _ALLOWED_DUPLICATE_SITES
        if key not in existing_sites or key not in aliased_sites
    ]

    assert not stale, "stale allowlist entries:\n" + "\n".join(stale)
