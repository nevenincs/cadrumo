"""Gate: a contract disposition must name a declaration that still names it back.

``design_time_authority`` states a checkable property -- a dev tool reads the
module -- so it cannot quietly become false. "Staged capability landing soon"
cannot: it is a promise about the future, and a promise never fails loudly. The
``declared_by_contract`` kind is the verifiable form of that claim. The entry
must name the file whose declaration requires the module, and the loader
refuses it the moment that file stops mentioning it.

Without the check the mechanism would be an allowlist with prose attached: a
capability could be retired, its declaration dropped, and the disposition would
go on keeping a dead module quiet with a rationale describing a contract that
no longer exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..unreachable_module_ratchet import (
    BASELINE_PATH,
    IntentionalReachabilityKind,
    UnreachableBaseline,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODULE = "cadrumo.domain.example_package"


def _baseline(tmp_path: Path, body: str) -> Path:
    """Write a baseline at the real depth, so the repo root resolves as it does live."""
    root = tmp_path / "repo"
    (root / "dev" / "quality").mkdir(parents=True)
    path = root / "dev" / "quality" / "unreachable_module_ratchet.toml"
    path.write_text(f"allowed = []\nfrozen_prefixes = []\n{body}", encoding="utf-8")
    return path


def _declaration(tmp_path: Path, text: str) -> None:
    """Write the production file a disposition points at."""
    source = tmp_path / "repo" / "src" / "contract.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(text, encoding="utf-8")


_ENTRY = f"""
[[intentional]]
module = "{_MODULE}"
kind = "declared_by_contract"
declared_by = "src/contract.py"
rationale = "The error registry declares refusals against this package."
"""


def test_a_declaration_that_names_the_module_is_accepted(tmp_path: Path) -> None:
    """The normal case, so the gate is not merely always-red."""
    path = _baseline(tmp_path, _ENTRY)
    _declaration(tmp_path, f'ERRORS = ("{_MODULE}.errors.ShapeError",)\n')

    loaded = UnreachableBaseline.load(path)

    assert [d.module for d in loaded.intentional] == [_MODULE]
    assert loaded.intentional[0].kind is IntentionalReachabilityKind.DECLARED_BY_CONTRACT
    assert loaded.intentional[0].declared_by == "src/contract.py"


def test_a_declaration_that_stopped_naming_the_module_is_refused(tmp_path: Path) -> None:
    """Detector teeth: the contract moved on and the disposition did not."""
    path = _baseline(tmp_path, _ENTRY)
    _declaration(tmp_path, 'ERRORS = ("cadrumo.domain.something_else.errors.ShapeError",)\n')

    with pytest.raises(ValueError, match="no longer declares it"):
        UnreachableBaseline.load(path)


def test_a_declaration_file_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    """Detector teeth: a path that never resolved, or one deleted since."""
    path = _baseline(tmp_path, _ENTRY)

    with pytest.raises(ValueError, match="names no file"):
        UnreachableBaseline.load(path)


def test_the_kind_requires_its_declaration(tmp_path: Path) -> None:
    """A contract claim with nothing to check is the shape this kind exists to refuse."""
    path = _baseline(
        tmp_path,
        f'\n[[intentional]]\nmodule = "{_MODULE}"\nkind = "declared_by_contract"\nrationale = "Landing soon."\n',
    )

    with pytest.raises(ValueError, match="requires a declared_by path"):
        UnreachableBaseline.load(path)


def test_an_authority_entry_may_not_carry_a_declaration(tmp_path: Path) -> None:
    """The two kinds stay distinguishable; a mixed entry is refused rather than half-checked."""
    path = _baseline(
        tmp_path,
        f'\n[[intentional]]\nmodule = "{_MODULE}"\nkind = "design_time_authority"\n'
        'declared_by = "src/contract.py"\nrationale = "Read by a dev tool."\n',
    )

    with pytest.raises(ValueError, match="declared_by_contract entry only"):
        UnreachableBaseline.load(path)


def test_every_live_contract_disposition_still_verifies() -> None:
    """The committed baseline is subject to the same check, not only fixtures."""
    loaded = UnreachableBaseline.load(BASELINE_PATH)
    contract = [d for d in loaded.intentional if d.kind is IntentionalReachabilityKind.DECLARED_BY_CONTRACT]

    assert contract, (
        "no declared_by_contract disposition is recorded; this check would pass "
        "vacuously and the loader's verification would go unexercised on real data"
    )
    assert all(d.declared_by for d in contract)


def test_a_symbol_disposition_may_not_claim_a_contract(tmp_path: Path) -> None:
    """Detector teeth: the kind is shared, but only the module baseline can check it.

    Extending the enum for the module ratchet silently widened what the SYMBOL
    ratchet would accept, because both validate against the same closed set.
    A symbol entry carries no declared_by and nothing verifies it, so the kind
    is refused there rather than taken on trust.
    """
    from ..unused_symbol_ratchet import _intentional

    path = tmp_path / "unused_symbol_ratchet.toml"
    path.write_text(
        "
".join(
            (
                "[[intentional]]",
                'module = "cadrumo.example"',
                'symbol = "THING"',
                'kind = "declared_by_contract"',
                'rationale = "A contract declares it."',
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="design_time_authority only"):
        _intentional(path)
