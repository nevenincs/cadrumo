"""Layer-3 write-guard for aeat.filing.reconciliation (#239).

Mirror of ``aeat.sede.test_no_write_surface``. Walks every ``.py``
source under the subpackage and fails if a forbidden call-context
verb appears. The reconciliation layer is a pure compare — it MUST
remain structurally free of any AEAT-mutation verb, English or
Spanish.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_RECON_ROOT = Path(__file__).resolve().parent
_FIXTURE = _RECON_ROOT / "_no_write_surface_fixture.txt"


def _load_forbidden_verbs() -> tuple[str, ...]:
    lines = _FIXTURE.read_text(encoding="utf-8").splitlines()
    return tuple(line.strip() for line in lines if line.strip() and not line.strip().startswith("#"))


def _iter_reconcile_sources() -> tuple[Path, ...]:
    return tuple(p for p in _RECON_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


class TestNoCallContextWriteVerbs:
    @pytest.mark.parametrize("verb", _load_forbidden_verbs())
    def test_verb_never_called(self, verb: str) -> None:
        pattern = re.compile(rf"\b{re.escape(verb)}\s*\(", re.IGNORECASE)
        offenders: list[str] = []
        for source in _iter_reconcile_sources():
            if source.name == Path(__file__).name:
                continue
            for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
                if pattern.search(line):
                    offenders.append(f"{source.relative_to(_RECON_ROOT)}:{line_no}: {line.strip()}")
        assert not offenders, (
            f"Forbidden write verb {verb!r} used as a call inside aeat.filing.reconciliation:\n" + "\n".join(offenders)
        )


class TestNoWriteModeLiteral:
    def test_no_write_mode_literal(self) -> None:
        mode_char = "w"
        forbidden = f'mode: Literal["{mode_char + "rite"}"]'
        for source in _iter_reconcile_sources():
            content = source.read_text(encoding="utf-8")
            assert forbidden not in content, (
                f"{source.relative_to(_RECON_ROOT)}: boundary-crossing record declares a non-read mode literal"
            )
