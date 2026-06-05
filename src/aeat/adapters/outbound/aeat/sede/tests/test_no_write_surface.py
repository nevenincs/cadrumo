"""Write-surface checks for aeat.adapters.outbound.aeat.sede.

The sede adapter is a read-only boundary. These checks reject mutation
verbs in call contexts and reject non-read boundary record modes while
allowing browser events used to open selectors and read document links.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_SEDE_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = _SEDE_ROOT / "_no_write_surface_fixture.txt"


def _load_forbidden_verbs() -> tuple[str, ...]:
    """Return the forbidden-verb list with comments + blanks stripped."""
    lines = _FIXTURE.read_text(encoding="utf-8").splitlines()
    return tuple(line.strip() for line in lines if line.strip() and not line.strip().startswith("#"))


def _iter_sede_sources() -> tuple[Path, ...]:
    """Every .py file under aeat.adapters.outbound.aeat.sede (includes this test module)."""
    return tuple(p for p in _SEDE_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


class TestNoCallContextWriteVerbs:
    """Forbidden verbs must never appear as a call-site in aeat.adapters.outbound.aeat.sede."""

    @pytest.mark.parametrize("verb", _load_forbidden_verbs())
    def test_verb_never_called(self, verb: str) -> None:
        pattern = re.compile(rf"\b{re.escape(verb)}\s*\(", re.IGNORECASE)
        offenders: list[str] = []
        for source in _iter_sede_sources():
            if source.name == Path(__file__).name:
                # The guard test references the verbs as fixture strings,
                # not as calls — skip its own body.
                continue
            for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
                if source.name == "_observation_store.py" and (
                    "self._objects.save(" in line or "self._repository.save(" in line
                ):
                    # Local encrypted observation persistence is allowed;
                    # this guard is for remote Sede mutation verbs.
                    # Accepts both the legacy ``self._objects`` direct attr
                    # and the current ``self._repository`` property accessor.
                    continue
                if pattern.search(line):
                    offenders.append(f"{source.relative_to(_SEDE_ROOT)}:{line_no}: {line.strip()}")
        assert not offenders, (
            f"Forbidden write verb {verb!r} used in a call context inside aeat.adapters.outbound.aeat.sede:\n"
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
