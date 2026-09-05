"""Write-surface checks for cadrumo.adapters.outbound.aeat.sede.

The sede adapter is a read-only boundary. These checks reject mutation
verbs in call contexts and reject non-read boundary record modes while
allowing browser events used to open selectors and read document links.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ......core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_SEDE_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = _SEDE_ROOT / "_no_write_surface_fixture.txt"


def _load_forbidden_verbs() -> tuple[str, ...]:
    """Return the forbidden-verb list with comments + blanks stripped."""
    lines = _FIXTURE.read_text(encoding="utf-8").splitlines()
    return tuple(line.strip() for line in lines if line.strip() and not line.strip().startswith("#"))


def _iter_sede_sources() -> tuple[Path, ...]:
    """Every .py file under cadrumo.adapters.outbound.aeat.sede (includes this test module)."""
    return tuple(p for p in scan_directory(_SEDE_ROOT, pattern="*.py", recursive=True) if "__pycache__" not in p.parts)


def _iter_sede_production_sources() -> tuple[Path, ...]:
    """Every production .py file under the sede boundary, excluding tests."""
    return tuple(source for source in _iter_sede_sources() if "tests" not in source.parts)


def _local_persistence_is_allowed(source_name: str, line: str) -> bool:
    """Whether ``line`` is the one sanctioned local-persistence call shape.

    Local encrypted observation persistence is allowed; this guard exists for
    REMOTE Sede mutation verbs. The exemption is deliberately scoped to
    :mod:`observation_store` and to named accessors -- the legacy raw
    ``SecureObjectRepository`` handles and the current
    ``SecureBoundRepository``-backed properties, which persist to the same
    local encrypted namespaces.

    Kept as a named predicate rather than inline so
    :class:`TestTheGuardCanActuallyFire` can prove both that it excuses what it
    is meant to and that it excuses nothing else.
    """
    if source_name != "observation_store.py":
        return False
    return (
        "self._objects.save(" in line
        or "self._repository.save(" in line
        or "self._observations.save(" in line
        or "self._wallet_observations.save(" in line
    )


def _line_offends(source_name: str, line: str, verb: str) -> bool:
    """Whether ``line`` in ``source_name`` is a forbidden call of ``verb``."""
    if _local_persistence_is_allowed(source_name, line):
        return False
    return bool(re.compile(rf"\b{re.escape(verb)}\s*\(", re.IGNORECASE).search(line))


class TestNoCallContextWriteVerbs:
    """Forbidden verbs must never appear as a call-site in cadrumo.adapters.outbound.aeat.sede."""

    @pytest.mark.parametrize("verb", _load_forbidden_verbs())
    def test_verb_never_called(self, verb: str) -> None:
        offenders: list[str] = []
        for source in _iter_sede_sources():
            if source.name == Path(__file__).name:
                # The guard test references the verbs as fixture strings,
                # not as calls — skip its own body.
                continue
            for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
                if _line_offends(source.name, line, verb):
                    offenders.append(f"{source.relative_to(_SEDE_ROOT)}:{line_no}: {line.strip()}")
        assert not offenders, (
            f"Forbidden write verb {verb!r} used in a call context inside cadrumo.adapters.outbound.aeat.sede:\n"
            + "\n".join(offenders)
        )


class TestNoWriteModeLiteral:
    """No boundary-crossing record may declare a mode other than 'read'."""

    def test_no_write_mode_literal(self) -> None:
        # Compose the forbidden literal at runtime so neither this test
        # file nor any source matching the fixture path trips the guard.
        mode_char = "w"
        forbidden = f'mode: Literal["{mode_char + "rite"}"]'
        for source in _iter_sede_sources():
            content = source.read_text(encoding="utf-8")
            assert forbidden not in content, (
                f"{source.relative_to(_SEDE_ROOT)}: boundary-crossing record declares a non-read mode literal"
            )


class TestReadPostCanary:
    """The only raw POST is the legally guarded already-read document retrieval."""

    def test_only_the_guarded_notification_detail_post_exists(self) -> None:
        post_sites: list[tuple[Path, int]] = []
        sources: dict[Path, str] = {}
        for source in _iter_sede_production_sources():
            content = source.read_text(encoding="utf-8")
            sources[source] = content
            for line_number, line in enumerate(content.splitlines(), start=1):
                if re.search(r"\.post\s*\(", line):
                    post_sites.append((source, line_number))

        assert len(post_sites) == 1, f"unexpected raw POST call sites: {post_sites}"
        source, _ = post_sites[0]
        assert source.name == "notifications.py"

        content = sources[source]
        function_start = content.index("async def fetch_notification_document")
        function_end = content.index("\n\nasync def fetch_notifications_query", function_start)
        function = content[function_start:function_end]
        post_index = function.index(".post(")

        assert function.count(".post(") == 1
        assert function.index("assert_notification_content_readable(row)") < post_index
        assert function.index('_assert_read_http("GET", url)') < post_index
        assert function.index('assert_read_http_for(READ_GUARD_POLICY, "POST", url)') < post_index


class TestTheGuardCanActuallyFire:
    """Prove this guard is armed, not merely green.

    A scan that matches nothing passes identically whether the tree is clean or
    the matcher is broken, and this guard was briefly disarmed in exactly that
    way: a rewrite added ``save(...)`` call sites, main went red, and the fix
    was to WIDEN the exemption. Widening is the direction that silently turns a
    guard into decoration, so the exemption now has to prove it still refuses.

    These cases assert against :func:`_line_offends` -- the same predicate the
    real scan uses -- on synthetic lines, so they never depend on the tree
    containing a violation.
    """

    @pytest.mark.parametrize("verb", _load_forbidden_verbs())
    def test_a_remote_call_of_every_forbidden_verb_is_caught(self, verb: str) -> None:
        """Every verb in the fixture must be detected in a call context."""
        assert _line_offends("_declarations_fetch.py", f"    self._client.{verb}(url, data=payload)", verb), (
            f"the guard did not detect a call to forbidden verb {verb!r}"
        )

    def test_the_local_persistence_exemption_applies_where_it_should(self) -> None:
        """The sanctioned local-persistence shapes stay allowed in their own module."""
        for accessor in ("_objects", "_repository", "_observations", "_wallet_observations"):
            line = f"        self.{accessor}.save(record)"
            assert not _line_offends("observation_store.py", line, "save"), (
                f"self.{accessor}.save(...) must remain allowed in _observation_store.py"
            )

    def test_the_exemption_does_not_leak_to_other_modules(self) -> None:
        """The identical line in any other module must still be refused.

        The exemption is scoped to one file on purpose. If it were keyed on the
        accessor name alone, adding that name elsewhere would silently buy a
        remote write surface.
        """
        line = "        self._observations.save(record)"
        assert _line_offends("_declarations_fetch.py", line, "save")
        assert _line_offends("iva_compensation_wallet.py", line, "save")

    def test_the_exemption_does_not_excuse_a_different_verb(self) -> None:
        """Only ``save`` is exempted on those accessors, not every mutation verb."""
        assert _line_offends("observation_store.py", "        self._observations.submit(record)", "submit")
