"""Vacuity floor for the committed cli-sequence corpus.

The goldens gate (``dev/docs/tests/test_sequence_goldens.py``) and the Sphinx
build gate both assert that :func:`~dev.docs.sequences.checks.check_sequences`
returns no problems. Over an enrolment of zero directives that engine returns
no problems, so both surfaces read a corpus that has silently stopped being
discovered exactly as they read a fully enrolled one that passes. The refresh
CLI has the same blind spot: it prints "nothing to refresh" and exits 0.

The engine itself must stay neutral -- it legitimately runs over freshly
scaffolded and tmp docs trees that carry no directives yet -- so the claim
that the *committed* corpus is enrolled belongs here, once, rather than
restated at each scanning gate. This mirrors the same discipline applied to
the markdown corpus in ``dev/docs/tests/test_docs.py``.

The floor is two-dimensional for the reason a single total is not enough: one
documentation subtree dropping out of discovery leaves the sequence total high
enough to pass while nothing in that subtree is read.
"""

from __future__ import annotations

import pytest

from ..checks import discover_sequences

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

#: Enrolled sequences the committed corpus currently carries, with headroom for
#: ordinary authoring churn. Raise it only alongside a deliberate expansion.
_MINIMUM_ENROLLED_SEQUENCES = 190

#: Distinct docs pages the enrolled sequences currently span.
_MINIMUM_ENROLLED_PAGES = 24


def test_the_committed_corpus_is_discovered_and_parses_clean() -> None:
    """Unscoped discovery over the committed docs tree reports no problems."""
    _, problems = discover_sequences()

    assert problems == (), "committed cli-sequence corpus does not parse:\n" + "\n".join(problems)


def test_committed_enrolment_stays_above_its_vacuity_floor() -> None:
    """Discovery must find the committed corpus, not an empty set read as clean."""
    discovered, _ = discover_sequences()
    pages = {item.page for item in discovered}

    assert len(discovered) >= _MINIMUM_ENROLLED_SEQUENCES, (
        f"only {len(discovered)} cli-sequence(s) discovered under the committed docs tree; "
        "the goldens gate and the Sphinx build gate report an empty problem list over a "
        "collapsed enrolment exactly as they do over a clean one"
    )
    assert len(pages) >= _MINIMUM_ENROLLED_PAGES, (
        f"the enrolled corpus spans only {len(pages)} page(s) ({sorted(pages)[:8]}...); "
        "one documentation subtree dropping out of discovery leaves the sequence total "
        "high enough to pass while nothing in that subtree is read"
    )
