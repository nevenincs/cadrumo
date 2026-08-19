"""Every composing write is enumerated, so a new one cannot appear unnoticed.

This gate exists because the pattern-matching approach failed four times.

A singleton catalogue composed into a batch must carry the revision it was read
at, or the batch rewrites the whole row over whatever another caller committed
in between. Four successive detectors tried to FIND that mistake by its shape,
and each went green over live instances of it:

* a line-oriented ``grep`` missed calls spanning several lines;
* matching ``save(append_bucket_event(...))`` missed appends bound to a
  variable first;
* tracking ``ast.Assign`` missed ``catalogue: T = repo.load()``;
* tracking direct binding missed taint reaching the write through an
  intermediate (``updated = upsert(index, entry)``).

Each fix looked complete and was not, because a detector that hunts a shape can
only ever cover the shapes already imagined. So this gate does not hunt. It
ENUMERATES every composing write in the application and domain layers and
requires each to be either self-evidently guarded -- it passes
``expected_revision_id`` -- or listed below. A site in neither fails.

WHAT THE LIST IS, AND IS NOT. It is an inventory, not a clearance. Being listed
records that a site writes a document without asserting a revision; it does not
certify the site is safe. Three genuinely different situations are in here and
only the first is closed:

* the document was never read, so there is no revision to assert;
* the document arrives as a PARAMETER, so the revision belongs to whichever
  caller read it and closing the site means threading it down;
* the document is per-record rather than a singleton catalogue, which narrows
  the exposure to two writers touching the SAME record instead of any two
  writers at all.

Entries state which. Where a site has not been judged, it says so rather than
borrowing a neighbour's reason -- an inventory that quietly implies every line
was reviewed is worse than one that admits what it has not looked at.

Repository modules are excluded structurally: a repository's own ``save`` and
``to_secure_object_write`` write the document handed to them, which is the API
these call sites consume rather than an instance of the defect.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....tests import non_test_package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_COMPOSING_WRITES = frozenset({"to_secure_object_write", "save_with_secure_object_writes"})

#: Path fragments whose modules DEFINE these writes rather than compose them.
_REPOSITORY_LAYERS = ("/adapters/persistence/profile/", "/adapters/persistence/storage/")

#: Every ``(module, function)`` performing a composing write that asserts no
#: revision, with what is known about it. Keyed by function, never by line, so
#: an edit above it does not silently retarget the entry.
_WRITES_WITHOUT_A_REVISION: dict[tuple[str, str], str] = {
    (
        "src/cadrumo/application/calculations/_observations_repository.py",
        "save_decision",
    ): "builds a fresh decision envelope rather than deriving one from a read, so no revision exists to assert",
    (
        "src/cadrumo/application/workflow/_persistence.py",
        "save",
    ): "a repository-shaped save over its own parameter; the guarded path beside it composes with load_revisioned",
    (
        "src/cadrumo/application/modelo/_verification_actions.py",
        "_build_participation_writes",
    ): "per-TRANSACTION participation rows, not a singleton catalogue, so the exposure narrows to two writers "
    "touching the same transaction; unclassified beyond that",
    (
        "src/cadrumo/application/modelo/_revision_persistence.py",
        "_build_filed_participation_writes",
    ): "per-transaction participation rows, as above; unclassified beyond that",
    (
        "src/cadrumo/application/modelo/_verification_actions.py",
        "_persist_verified_revision_evidence",
    ): "the calculation catalogue arrives as a parameter read by its caller; closing it means threading the revision",
    (
        "src/cadrumo/application/modelo/_revision_persistence.py",
        "persist_calculation_revision",
    ): "the work-unit catalogue arrives as a parameter; its own calculation catalogue IS guarded here",
    (
        "src/cadrumo/application/modelo/_revision_persistence.py",
        "persist_filed_revision",
    ): "the work-unit and filing catalogues arrive as parameters; the calculation catalogue is guarded here",
    (
        "src/cadrumo/application/modelo/_external_import_actions.py",
        "import_external_filing_evidence",
    ): "the work-unit catalogue is read by _load_external_import_target; the two locally-read catalogues are guarded",
    (
        "src/cadrumo/application/invoices/_linking.py",
        "link_invoice_transaction_repositories",
    ): "the transaction store writes a row PER TRANSACTION rather than one singleton document, so its "
    "batch carries no whole-collection risk; the singleton invoice catalogue beside it IS guarded",
    (
        "src/cadrumo/application/invoices/_reconciliation.py",
        "reconcile_invoice_repositories",
    ): "per-transaction rows as above; the singleton invoice catalogue beside it IS guarded",
    (
        "src/cadrumo/application/ledger/_actions_common.py",
        "_save_transaction_catalogue_and_events",
    ): "the transaction catalogue arrives as a parameter; its EVENT side is guarded by _commit_with_guarded_events",
    (
        "src/cadrumo/application/ledger/_actions_common.py",
        "_save_transaction_catalogue_invoices_and_events",
    ): "transaction and invoice catalogues arrive as parameters; the event side is guarded",
    (
        "src/cadrumo/application/modelo/_amendment_actions.py",
        "_persist_amendment_side_effects",
    ): "all three catalogues -- calculation, filing and work-unit -- arrive as parameters, read by "
    "amend_calculation_revision at the top of the same call; closing it means threading three revisions",
    (
        "src/cadrumo/application/modelo/_m036_lifecycle.py",
        "record_m036_declaration",
    ): "the declaration result is freshly constructed rather than derived from a read, so no revision "
    "exists to assert; its event side goes through the guarded composer",
    (
        "src/cadrumo/application/modelo/_m145_communication_records.py",
        "_save_m145_record_with_event",
    ): "the communication record arrives as a parameter and is a per-record row rather than a catalogue; "
    "its event side goes through the guarded composer",
    (
        "src/cadrumo/application/modelo/_reconcile.py",
        "_finalise_reconciliation",
    ): "the reconciliation record is freshly built; the event catalogue beside it IS guarded",
    (
        "src/cadrumo/application/calculations/_iva_compensation_history.py",
        "persist_observation_envelope_and_iva_history",
    ): "the envelope arrives as a parameter and the history state is projected fresh from it, so neither "
    "write derives from a read this function performed",
    (
        "src/cadrumo/domain/buckets/_event_repository.py",
        "bucket_event_history_write",
    ): "the narrow-port fallback: the domain protocol promises only exists/load/save, so an injected "
    "alternative may offer no revisioned read",
}


def _bare_composing_sites() -> set[tuple[str, str]]:
    """Return every ``(module, function)`` composing a write with no revision."""
    found: set[tuple[str, str]] = set()
    for path in non_test_package_python_files():
        relative = repo_relative(path)
        if any(layer in relative for layer in _REPOSITORY_LAYERS):
            continue
        try:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparsable file is its own failure
            continue
        for scope in ast.walk(tree):
            if not isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for node in ast.walk(scope):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                if node.func.attr not in _COMPOSING_WRITES:
                    continue
                if any(keyword.arg == "expected_revision_id" for keyword in node.keywords):
                    continue
                found.add((relative, scope.name))
    return found


def test_every_composing_write_carries_a_revision_or_is_declared() -> None:
    """A new unguarded composition cannot appear without someone recording it."""
    undeclared = sorted(_bare_composing_sites() - set(_WRITES_WITHOUT_A_REVISION))

    assert not undeclared, (
        f"these functions compose a secure-object write without asserting a revision and are not "
        f"declared: {undeclared}. Pass expected_revision_id from load_revisioned() if the document "
        "was derived from a read, or add an entry saying why there is no revision to assert."
    )


def test_no_declaration_outlives_its_site() -> None:
    """The half that rots: an entry for a site that is now guarded, or gone.

    A stale entry reads as a known exposure that no longer exists, which
    inflates the inventory and hides real progress.
    """
    stale = sorted(set(_WRITES_WITHOUT_A_REVISION) - _bare_composing_sites())

    assert not stale, (
        f"these declarations no longer match an unguarded composing write: {stale}. Remove them; an "
        "entry that outlives its site claims an exposure that is not there."
    )


def test_every_declaration_states_something() -> None:
    """An entry with no reason is a silent exemption.

    ``unclassified`` is an acceptable reason and several entries use it. What is
    not acceptable is an empty one, which reads as reviewed while recording
    nothing.
    """
    empty = sorted(site for site, reason in _WRITES_WITHOUT_A_REVISION.items() if not reason.strip())

    assert not empty, f"declarations with no stated reason: {empty}"
