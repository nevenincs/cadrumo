"""Architecture gate: production code never reaches another package's privates.

``aeat-architecture-boundaries`` states that leading-underscore modules "are
private to their package and are not cross-package APIs", and that a contract
required outside its package "must hard-move from an underscore-private module
to a public defining module". This gate is that rule, asserted at zero.

WHY THIS CARRIES NO ALLOWLIST, BASELINE OR EXEMPTION LEDGER
-----------------------------------------------------------
Its predecessor did. It had to: when the rule was first written the tree
carried 114 production violations, later 270 private modules reached from
1,586 consumer files, and a gate cannot assert zero against a number like
that. So the debt was grandfathered into a checked-in baseline and ratcheted
down.

A baseline is a hand-maintained list of names, and a hand-maintained list of
names is wrong in three ways this repository has now paid for. It goes stale on
every rename, and a stale entry is not inert -- it is an unused allowance a
future real violation can occupy, so the ratchet silently widens. It aborts the
whole run when an entry stops matching, which turns one dead name into every
boundary in the file going unenforced while the run still exits non-zero for an
unrelated-looking reason. And it lets a violation be recorded rather than
fixed, which is how 114 became 270.

The debt is now zero, so none of that is needed. The rule is derived from the
tree on every run: no names, nothing to maintain, nothing to go stale. A new
violation cannot be admitted by adding a line here, because there is no line to
add -- it has to be fixed, by moving the contract to a public defining module
the way the rule says.

The test-only population is reported, not asserted. Test modules reaching a
sibling package's internals is a weaker offence than production doing it, it
sits at 59, and pinning it here would reintroduce exactly the ledger this gate
exists without. It belongs to its own step.

See Also:
    :mod:`dev.quality.import_hygiene_scan`
        Owns the scan. This module only asserts on it, so the shape rule has
        one definition rather than two that can disagree.
"""

from __future__ import annotations

import pytest

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT
from ..quality.import_hygiene_scan import (
    PKG_ROOT,
    ImportSite,
    find_private_import_violations,
    walk_module_imports,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _all_import_sites() -> list[ImportSite]:
    """Every import site under ``src/cadrumo``, read from the working tree."""
    sites: list[ImportSite] = []
    for path in scan_directory(PKG_ROOT, pattern="*.py", recursive=True, prune_directories=("__pycache__",)):
        sites.extend(walk_module_imports(path))
    return sites


def test_no_production_module_imports_another_packages_privates() -> None:
    """Zero. Not a ceiling, not a baselined set -- zero, with no exemptions."""
    violations = [v for v in find_private_import_violations(_all_import_sites()) if not v.is_test]

    if violations:
        listing = "\n".join(
            f"  {v.importer_path}:{v.lineno}  {v.importer_mod} -> {v.target_mod}  {v.imported_names}"
            for v in sorted(violations, key=lambda v: (v.importer_path, v.lineno))
        )
        pytest.fail(
            f"{len(violations)} production cross-package private import(s).\n"
            "Move the contract to a public defining module in the package that owns it "
            "(a rename, not a re-export) and repoint the consumers. There is deliberately "
            "no exemption list to add to.\n" + listing,
        )


def test_the_detector_fires_on_a_planted_violation() -> None:
    """Anti-tautology control: the zero above must be a measurement, not a blind spot.

    The site is constructed rather than written to disk. Planting a real file
    to make a gate's point is a fleet hazard -- a concurrent agent hits an
    unattributable ImportError, a hard kill leaves the break behind, and a
    peer's pathspec commit can commit it -- and planting it outside the repo
    is not an option either, because the scan renders every violation as a
    repository-relative path.
    """
    reach = ImportSite(
        importer_mod="cadrumo.zzz_consumer.reaches",
        importer_path=REPO_ROOT / "src" / "cadrumo" / "zzz_consumer" / "reaches.py",
        lineno=1,
        target_mod="cadrumo.zzz_owner._secret",
        imported_names=["VALUE"],
        is_test=False,
        in_type_checking=False,
    )

    planted = find_private_import_violations([reach])

    assert [v.target_mod for v in planted] == ["cadrumo.zzz_owner._secret"], (
        "the detector did not see a cross-package private import, so the zero "
        "asserted above proves nothing"
    )


def test_the_gate_reads_a_real_population() -> None:
    """A scan that silently found nothing would also report zero violations."""
    sites = _all_import_sites()
    assert len(sites) > 10_000, f"only {len(sites)} import sites scanned; the scan is not reaching the tree"
