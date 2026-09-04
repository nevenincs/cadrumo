"""Gate: catalogue revision segments and registry revision ids stay in lock-step.

Modelo casilla keys embed the revision id they belong to, and that id is
registry data, not authored text. So a revision RENAME -- ``347``'s
``2008-2024`` becoming ``2011-2024`` -- or a SPLIT -- ``322``'s ``2008-2023``
becoming ``2023`` plus ``2008-2022`` -- silently invalidates every catalogue
key under the old id while the registry side compiles clean. Nothing raises:
the labels simply resolve to nothing, and the operator reads a raw key.

Three such changes landed unnoticed, because the drift report could only
describe them as unrelated missing and extra keys among thousands of others.
This gate asks the question directly and in both directions: no catalogue may
reference a revision the registry does not declare, and no casilla-bearing
registry revision may be missing from the catalogues.

The assertions are structural. They never assert what a key resolves to --
that is the translation gates' job -- only that the revision ids on the two
sides name the same set. Coverage of individual keys within a revision stays
with the parity gate, so a newly declared casilla is a missing key there and
not a false rename here.
"""

from __future__ import annotations

import pytest

from .._paths import LOCALES_DIR, SRC_DIR
from .._registry_scanner import scan_modelo_schema_keys
from .._revision_drift import classify_revision_moves, classify_revision_parity
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")


@pytest.fixture(scope="module")
def registry_keys() -> frozenset[str]:
    """Return every Modelo schema key the committed registry derives."""
    return frozenset(scan_modelo_schema_keys())


@pytest.fixture(scope="module")
def catalogue_keys() -> dict[str, frozenset[str]]:
    """Return each shipped catalogue's key set, read through the manager."""
    manager = LocaleManager(SRC_DIR, LOCALES_DIR)
    return {locale: frozenset(manager.get_yaml_keys(manager.load_locale(LOCALES_DIR / locale))) for locale in _LOCALES}


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_catalogue_references_an_undeclared_revision(
    locale: str,
    registry_keys: frozenset[str],
    catalogue_keys: dict[str, frozenset[str]],
) -> None:
    """No catalogue key names a revision id the registry does not declare."""
    findings = classify_revision_parity(registry_keys, catalogue_keys[locale])
    assert not findings.stale, (
        f"the {locale} catalogue carries keys under revision id(s) the registry does not declare: "
        f"{[f'{modelo}/{revision}' for modelo, revision in findings.stale]}. A renamed or split revision "
        f"moves its keys: `python -m dev.locales move-revision <modelo> <old> <new>`."
    )


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_casilla_bearing_revision_has_catalogue_keys(
    locale: str,
    registry_keys: frozenset[str],
    catalogue_keys: dict[str, frozenset[str]],
) -> None:
    """Every registry revision carrying casillas is present in every catalogue."""
    findings = classify_revision_parity(registry_keys, catalogue_keys[locale])
    assert not findings.absent, (
        f"the registry declares casillas for revision(s) the {locale} catalogue holds no key for at all: "
        f"{[f'{modelo}/{revision}' for modelo, revision in findings.absent]}. If the revision was renamed, "
        f"carry its keys with `python -m dev.locales move-revision <modelo> <old> <new>` rather than "
        f"scaffolding empty slots."
    )


def _rename_revision(keys: frozenset[str], modelo: str, old: str, new: str) -> frozenset[str]:
    """Return ``keys`` with one revision segment rewritten, as a registry rename does."""
    old_prefix = f"modelo.schema.{modelo}.revision.{old}."
    new_prefix = f"modelo.schema.{modelo}.revision.{new}."
    return frozenset(f"{new_prefix}{key[len(old_prefix) :]}" if key.startswith(old_prefix) else key for key in keys)


def test_an_unmoved_rename_is_reported_in_both_directions(
    registry_keys: frozenset[str],
    catalogue_keys: dict[str, frozenset[str]],
) -> None:
    """A registry rename with no catalogue move reds this gate, by construction.

    The rename is applied to a COPY of the real registry key set and compared
    against the real catalogue, which is exactly the state the tree is in the
    moment a revision id changes and nothing carries the keys across. Proving
    it here rather than by editing the registry keeps the tree untouched while
    exercising the same function the two gates above call.
    """
    modelo, old_revision = "303", "2023"
    renamed = _rename_revision(registry_keys, modelo, old_revision, "2023-renamed")
    assert renamed != registry_keys, f"{modelo}/{old_revision} must exist for this proof to mean anything"

    findings = classify_revision_parity(renamed, catalogue_keys["es"])
    assert (modelo, old_revision) in findings.stale
    assert (modelo, "2023-renamed") in findings.absent


def test_an_unmoved_rename_is_reported_as_a_move_with_its_invocation(
    registry_keys: frozenset[str],
    catalogue_keys: dict[str, frozenset[str]],
) -> None:
    """The drift report describes an unmoved rename as one move, not as two piles.

    This is the reading that would have caught the three splits: the same key
    on both sides of the report, recognised as one relocation and printed with
    the verb that performs it.
    """
    modelo, old_revision, new_revision = "303", "2023", "2023-renamed"
    renamed = _rename_revision(registry_keys, modelo, old_revision, new_revision)
    catalogue = catalogue_keys["es"]

    report = classify_revision_moves("es.yml", renamed - catalogue, catalogue - renamed)
    candidates = [
        candidate
        for candidate in report.candidates
        if candidate.modelo == modelo and candidate.source_revision == old_revision
    ]
    assert len(candidates) == 1, f"expected exactly one move candidate for {modelo}/{old_revision}: {candidates}"
    (candidate,) = candidates
    assert candidate.destination_revisions == (new_revision,)
    assert candidate.key_count > 0
    assert candidate.invocation == f"python -m dev.locales move-revision {modelo} {old_revision} {new_revision}"
    assert report.accounted_extra, "the moved keys must be accounted for rather than reported as removals"
