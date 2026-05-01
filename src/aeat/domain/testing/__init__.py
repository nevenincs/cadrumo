"""Synthetic filing-history fixtures loader.

The :mod:`aeat.domain.testing` subpackage owns the typed public API for
loading the hand-curated backlog of **synthetic** past filings that
lives under ``tests/fixtures/filing_history/``. It is the only
"test helper" code allowed in the source tree per issue #14 — every
other test helper stays under ``tests/``.

Synthetic-only invariant
------------------------

Every fixture file is marked synthetic in **two** ways, both
enforced by strict pydantic v2 validation (never by convention):

1. A top-level ``"synthetic": true`` key, typed as
   :class:`typing.Literal` ``True``. Any other value fails
   validation at load time.
2. A top-level ``"_comment"`` key carrying a non-empty warning
   string. A human opening the file sees the warning; the loader
   refuses any file missing it.

There is no code path that loads a fixture without both markers.
Anyone tempted to "borrow" a real filing as a fixture must instead
anonymise *and* perturb it into a freshly hand-curated synthetic
record.

Public API
----------

- :class:`FilingRecord` — one past filing, strict pydantic v2.
- :class:`FixtureCasilla` — one casilla on a record.
- :class:`FilingRecordPeriodKind`, :class:`FilingRecordScenario` —
  closed :class:`enum.StrEnum` catalogues.
- :data:`SYNTHETIC_FIXTURES_ROOT` — absolute path to
  ``tests/fixtures/filing_history/``.
- :func:`load_filing_history` — deterministic iterator yielding
  every fixture (optionally filtered by ``modelo`` or ``period``).
- :func:`compute_record_id` — content-addressed ID helper shared
  with fixture authoring.
- :func:`synthesize_filing_draft` — pure-construction factory that
  builds a strict-frozen :class:`aeat.application.filing.FilingDraft` from a
  casilla map. Used by the W1 P7 read-only reconcile path to feed
  ``aeat filing reconcile`` an APPROVED draft without running the
  full transactions/ruleset/formulas/validator pipeline.
- :func:`synthesize_filing_draft_from_decimals` — convenience
  wrapper that coerces decimal-as-string casilla values to
  :class:`Decimal` at the boundary.

Status reuses :class:`aeat.application.filing.FilingDraftStatus`; this
subpackage intentionally does **not** introduce a parallel status
enum.

How to add a new synthetic record
---------------------------------

1. Pick the modelo. Directories are
   ``tests/fixtures/filing_history/modelo_<id>/``.
2. Choose a filename: ``<period>-<scenario>.json``, e.g.
   ``2025q4-clean.json`` or ``2024-complementaria.json``.
3. Author the file. The **first** key must be ``"synthetic": true``
   and the **second** key must be ``"_comment"`` carrying a
   warning string. Subsequent keys follow the
   :class:`FilingRecord` field order.
4. Compute ``record_id`` via :func:`compute_record_id` (or let the
   existing corpus pattern guide you — the colocated test
   ``_test_record_ids_are_unique`` will catch collisions).
5. Status must be a valid :class:`aeat.application.filing.FilingDraftStatus`
   name (e.g. ``"ACKNOWLEDGED"``).
6. Run ``just test`` — the colocated suite loads every fixture
   through strict pydantic validation and asserts the invariants.

Example
-------

.. code-block:: python

    from . import load_filing_history

    for record in load_filing_history(modelo="130"):
        assert record.synthetic is True
        assert record.source == "synthetic"
        print(record.record_id, record.period, record.scenario)
"""

from __future__ import annotations

from ...core.errors import FilingFixtureError
from ._loader import SYNTHETIC_FIXTURES_ROOT, load_filing_history
from ._schema import (
    FilingRecord,
    FilingRecordPeriodKind,
    FilingRecordScenario,
    FixtureCasilla,
    FixtureScalar,
    compute_record_id,
)
from ._synthesize import (
    synthesize_filing_draft,
    synthesize_filing_draft_from_decimals,
)

__all__ = [
    "SYNTHETIC_FIXTURES_ROOT",
    "FilingFixtureError",
    "FilingRecord",
    "FilingRecordPeriodKind",
    "FilingRecordScenario",
    "FixtureCasilla",
    "FixtureScalar",
    "compute_record_id",
    "load_filing_history",
    "synthesize_filing_draft",
    "synthesize_filing_draft_from_decimals",
]
