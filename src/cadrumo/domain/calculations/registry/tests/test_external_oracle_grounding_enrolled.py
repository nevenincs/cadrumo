"""Verification-power gate: every externally-oracle-grounded casilla is enrolled.

Enrollment (every computed casilla named in a `verification_expectation`) is a
ceiling; verification POWER is the count of casillas whose engine value is
reconciled against an AEAT-authoritative expected value. Two independent
per-casilla external oracle KINDS are bundled today, enumerated by
:class:`~cadrumo.core.ExternalOracleCorpus`:

* the Renta WEB Open open-simulator replay corpus
  (`corpus/parity_replays/renta_web_open/`), whose `expected_by_casilla_id`
  carries AEAT-computed figures captured from the live simulator; and
* the AEAT Manual practico worked-example oracle corpus
  (`corpus/manual_oracles/`), whose `expected_by_casilla_id` carries figures
  quoted verbatim from a bundled AEAT manual's own caso practico table (see
  `aeat-quality-gates` for the sibling PDF-fixture
  provenance discipline this mirrors).

This gate protects that hard-won grounding in both directions: every casilla
with an external oracle expected value MUST be computed and enrolled so the
oracle value is actually consumed by the verify gate rather than stranded, and
every casilla the registry DECLARES externally grounded MUST have a bundled
oracle behind it rather than a fabricated claim.

The fold itself is a library
(:func:`~domain.calculations.registry.audit_bundled_external_grounding`), not
test-local machinery: the same facts answer "how much of this registry is
independently checked" for governance tooling, and this module is the gate that
holds the relation at zero. It reads the compiled registry tree through the
non-validating loader so it survives concurrent peer registry churn per
`aeat-registry-authority-flow` and
`aeat-worktree-safety`.

Modelo-agnostic: every bundled oracle payload names its own modelo and filing
year, and the fold resolves the applicable revision for every modelo the
bundled oracles cover — not just M100.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.external_oracle_corpus import ExternalOracleCorpus
from .....core.directory_scan import scan_directory
from .....core.resources import bundled_path
from ..external_grounding import (
    audit_bundled_external_grounding,
    load_bundled_external_oracle_inventory,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

#: Bundled corpus directories, mirrored from the fold so this module can prove
#: the fold visits every payload on disk rather than trusting it to.
_CORPUS_DIRECTORIES = {
    ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY: ("corpus", "parity_replays", "renta_web_open"),
    ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE: ("corpus", "manual_oracles"),
}


def test_every_externally_grounded_casilla_is_computed_and_enrolled() -> None:
    audit = audit_bundled_external_grounding()

    assert audit.inventory.evidence, "no external oracle casilla ids are bundled (replay or manual worked example)"
    assert audit.rows, "the registry tree yielded no revisions to audit"
    assert audit.checked_revision_count, "no bundled oracle (modelo, filing year) matched a registry revision"

    stranded = audit.findings_of_kind("oracle_casilla_not_computed") + audit.findings_of_kind(
        "oracle_casilla_not_enrolled",
    )
    assert not stranded, "external oracle grounding is stranded (not enrolled/computed):\n" + "\n".join(
        finding.detail for finding in stranded
    )


def test_every_declared_externally_grounded_casilla_has_oracle_evidence() -> None:
    """Symmetric honesty gate: a registry grounding claim must be backed by evidence.

    A revision may DECLARE `externally_grounded_casilla_ids` on its verification
    expectations. This is the other direction of
    `test_every_externally_grounded_casilla_is_computed_and_enrolled`: every casilla
    the registry declares externally grounded MUST actually appear in a bundled
    oracle's `expected_by_casilla_id` for that revision's applicable filing year(s) -
    either a Renta WEB Open replay or a bundled AEAT-manual worked-example oracle. It
    fails loudly if a grounding tier is asserted with no independent AEAT oracle
    behind it - the guard against a fabricated grounding claim
    (`sensitive-financial-data-secure-storage-only`, `aeat-quality-gates`). Runs across
    every modelo in the registry tree, not just M100.
    """
    audit = audit_bundled_external_grounding()

    assert audit.declared_grounding_count, "no revision declared externally_grounded_casilla_ids to cross-check"

    unevidenced = audit.findings_of_kind("declared_grounding_without_oracle_evidence")
    assert not unevidenced, "declared external grounding lacks oracle evidence:\n" + "\n".join(
        finding.detail for finding in unevidenced
    )


def test_every_bundled_oracle_payload_is_accounted_for() -> None:
    """No bundled oracle payload may be dropped without saying so.

    A payload the fold skipped silently is indistinguishable from one it read
    and found clean, so its expected values would sit outside both honesty
    directions with nothing reporting their absence. Every file on disk must
    therefore surface either as attributed evidence or as an explicitly
    recorded attribution gap.

    Every bundled payload is attributed today, so the gap set is empty and this
    assertion currently proves only that no payload vanished. The recorded-gap
    half is not dead, but it is now narrower than it was: attribution reads a
    payload's declared modelo and filing year before falling back to its name,
    so a self-describing payload under a year-less name is attributed rather
    than recorded as a gap. What still lands here is a payload no reading can
    place — a Renta WEB Open replay, which declares neither axis, under a name
    that encodes neither — or one whose year resolves to no single revision.
    """
    inventory = load_bundled_external_oracle_inventory()

    on_disk = {
        payload_path.name
        for parts in _CORPUS_DIRECTORIES.values()
        for payload_path in scan_directory(Path(bundled_path(*parts)), pattern="modelo-*.json")
    }
    assert on_disk, "no bundled oracle payloads were discovered on disk"

    accounted = {item.payload_name for item in inventory.evidence} | {
        item.payload_name for item in inventory.unattributed_payloads
    }
    assert accounted == on_disk, (
        "bundled oracle payloads vanished from the fold without being recorded as attribution gaps: "
        f"{sorted(on_disk - accounted)}"
    )
