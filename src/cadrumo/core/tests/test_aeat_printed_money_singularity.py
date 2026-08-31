"""Singularity gate: one anchored AEAT printed-money grammar, tree-wide.

:func:`~core.decimal.is_aeat_printed_money` is the single production authority
on whether a token IS an AEAT-printed monetary amount. Two adapters on opposite
sides of the hexagon consult it — the inbound sanción/liquidación notification
reader and the outbound sede IVA compensation wallet reader — and neither may
carry its own copy.

The hazard is historical and concrete. The grammar shipped as a hand-copied
regex literal in both of those modules, byte-identical, and the notification
reader's own module docstring described it as "the house pattern, shared
verbatim with the IVA compensation wallet reader". It was not shared; it was
duplicated, and prose asserting otherwise is exactly what makes a duplicate
survive review. Nothing structural prevented a third copy.

What a drifting copy would cost is specific. The grammar's job is to mandate
AEAT's two-decimal comma tail, so that a template change to whole euros
(``1.843``) refuses instead of resolving to ``1843`` or ``1.843`` with nothing
in the token to choose by. A copy that relaxed the tail on one surface would
under- or over-state a figure a taxpayer pays or appeals against, on that
surface only, while the other surface kept refusing — the divergence invisible
from either side.

Three rules, recomputed from the real tree every run, with no stored baseline
and no per-violation allowlist:

1. The anchored grammar is DECLARED in exactly one production module, found by
   scanning source for an anchored two-decimal comma tail rather than by
   symbol name — a hand-copied literal bound to a fresh private name is the
   shape being caught, and a name-keyed sweep walks straight past it.
2. Every consumer resolves to the SAME function object. Rule 1 reads source
   text, so a copy assembled at runtime, or one spelled differently enough to
   miss the scan, would evade it; object identity cannot be evaded by
   spelling.
3. The canonical grammar still behaves as the anchored check it is named for.
   Without this, a rename or a loosened pattern would leave rules 1 and 2
   passing over a grammar that no longer mandates the tail — the gate green
   and the property gone.

Rule 3 is the fixture anchor for rules 1 and 2: it is what stops the detector
going vacuous rather than going red.

Separately from singularity: THREE grammars over this one convention ship
deliberately — the anchored validator in ``core``, the unanchored capture group
the PDF label readers embed, and the unanchored finder the sede wallet runs over
its aggregate line. They differ on anchoring, on the sign, and on the ungrouped
integer part, each difference earned by the job that grammar does. The
separator set is the one axis on which they may never differ, so it is asserted
across all three rather than left to each declaration's author. Reconciliation
covered only two of them once, and the omitted one was reading a compensación
carry a thousandfold low.
"""

from __future__ import annotations

import re

import pytest

from ...adapters.inbound.notificacion import _sancion
from ...adapters.inbound.pdf._label_regex import SPANISH_AMOUNT_GROUP
from ...adapters.outbound.aeat.sede import _iva_compensation_wallet_parsing
from ...tests import aeat_relative, production_python_files
from ..decimal.printed_money import AEAT_THOUSANDS_SEPARATORS, is_aeat_printed_money

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

CANONICAL_MODULE = "core/decimal/printed_money.py"
"""The one production module permitted to declare the anchored grammar."""

ANCHORED_TAIL_SIGNATURE = r",\d{2}$"
"""Source signature of an anchored mandatory two-decimal comma tail.

This is the invariant the grammar exists to enforce, written as it appears in
a regex literal. It deliberately does NOT match the unanchored *finders* that
locate an amount inside a longer printed line (the sede wallet aggregate
reader, the Renta WEB Open scraper, the ledger IVA evidence advisory): those
carry the same tail without the closing anchor, and they are a different
concept — find one inside a line, versus be one end to end.

The canonical module is therefore required to keep its explicit ``^``/``$``
anchoring rather than expressing the same language another way, so that this
scan stays able to see it. :func:`test_the_canonical_grammar_carries_the_signature_it_is_scanned_for`
pins that requirement instead of leaving it to prose.
"""


def _modules_declaring_an_anchored_money_grammar() -> list[str]:
    """Return every production module whose source declares the anchored tail."""
    found: list[str] = []
    for path in production_python_files():
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:  # pragma: no cover - unreadable file in a scanned tree
            continue
        for line_no, line in enumerate(source.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            if ANCHORED_TAIL_SIGNATURE in line:
                found.append(f"{aeat_relative(path)}:{line_no}")
    return found


def test_the_anchored_money_grammar_is_declared_in_exactly_one_module() -> None:
    """No production module outside ``core.decimal`` may declare the anchored grammar."""
    declarations = _modules_declaring_an_anchored_money_grammar()
    modules = sorted({site.rsplit(":", 1)[0] for site in declarations})

    assert modules == [CANONICAL_MODULE], (
        f"the anchored AEAT printed-money grammar must be declared only in {CANONICAL_MODULE}; "
        f"found declarations at {declarations}. Import is_aeat_printed_money from cadrumo.core.decimal "
        "instead of re-declaring the pattern."
    )


def test_the_canonical_grammar_carries_the_signature_it_is_scanned_for() -> None:
    """The canonical module must remain visible to the scan above.

    Rule 1 keys on source text, so a canonical module that stopped carrying the
    signature would make the scan report nothing and pass by finding no
    duplicates rather than by there being none. This asserts the anchor exists,
    which turns that silence into a failure.
    """
    declarations = _modules_declaring_an_anchored_money_grammar()

    assert declarations, (
        f"{CANONICAL_MODULE} no longer carries {ANCHORED_TAIL_SIGNATURE!r}. Rule 1 now scans for a "
        "signature nothing matches and cannot fail, so restore the explicit anchoring or re-key the scan."
    )


def test_every_consumer_resolves_to_the_one_grammar_object() -> None:
    """Both adapter consumers must reference the identical function object.

    Identity, not equality of behaviour: a faithful re-implementation would
    satisfy a behavioural comparison while still being the second copy this
    gate exists to forbid.
    """
    assert _sancion.is_aeat_printed_money is is_aeat_printed_money
    assert _iva_compensation_wallet_parsing.is_aeat_printed_money is is_aeat_printed_money


@pytest.mark.parametrize("separator", list(AEAT_THOUSANDS_SEPARATORS))
def test_every_grammar_reads_the_same_thousands_separators(separator: str) -> None:
    """The three grammars over this convention must not diverge on the separator set.

    They differ on anchoring, on the optional sign, and on whether an ungrouped
    four-or-more-digit integer part is admitted — all deliberate, all a
    consequence of the job each does. They must NOT differ on which code points
    AEAT prints between thousand groups: a separator one accepts and another
    rejects means the same printed document reads as two different figures
    depending on which surface received it.

    The wallet finder is asserted through ``findall``, not only ``fullmatch``,
    because losing a group is how the divergence actually presented rather than
    a flat refusal. Its separator class was a dot and nothing else, so
    ``1\\xa0234,56`` yielded the fragment ``234,56`` — which then passed the
    anchored check cleanly, because a fragment of the shape IS the shape. The
    aggregate it reads is the IVA compensación carry a taxpayer claims, so that
    silent thousandfold under-read over-paid.

    Sharing :data:`~core.decimal.AEAT_THOUSANDS_SEPARATORS` is what makes the
    parity true structurally; this asserts the sharing actually reaches the
    compiled behaviour rather than merely the source.
    """
    printed = f"1{separator}234,56"

    assert is_aeat_printed_money(printed), f"anchored grammar rejects {printed!r}"
    match = re.fullmatch(SPANISH_AMOUNT_GROUP, printed)
    assert match is not None and match.group(1) == printed, f"capture group rejects {printed!r}"
    found = _iva_compensation_wallet_parsing._SPANISH_AMOUNT_RE.findall(printed)
    assert found == [printed], f"wallet aggregate finder read {found!r} out of {printed!r}"


@pytest.mark.parametrize("separator", [" ", "\t"])
def test_no_grammar_treats_column_whitespace_as_a_thousands_separator(separator: str) -> None:
    """ASCII space and tab separate AEAT's COLUMNS, so none may group thousands.

    This is the half that must never be widened. A grammar that grouped across
    ordinary whitespace could bridge a label-to-value gap and fuse two adjacent
    printed numbers into one figure.

    The wallet finder is unanchored and scans a whole labelled line, so the
    assertion for it is that the spanning figure is not among what it found —
    it legitimately still finds the trailing ``234,56`` on that line, which is
    a value in its own right and precisely what a column gap should leave.
    """
    printed = f"1{separator}234,56"

    assert not is_aeat_printed_money(printed)
    assert re.fullmatch(SPANISH_AMOUNT_GROUP, printed) is None
    assert printed not in _iva_compensation_wallet_parsing._SPANISH_AMOUNT_RE.findall(printed)


@pytest.mark.parametrize(
    "printed",
    [
        "3.687,12",
        "1234,56",
        "-1.234,56",
        "0,00",
        "999.999.999,99",
    ],
)
def test_the_canonical_grammar_accepts_aeat_printed_amounts(printed: str) -> None:
    """Grouped and ungrouped AEAT renderings, signed or not, are the accepted shape."""
    assert is_aeat_printed_money(printed)


@pytest.mark.parametrize(
    "refused",
    [
        "1.843",
        "1843",
        "3.687,1",
        "3.687,123",
        "total 3.687,12 euros",
        "3.687,12euros",
        "3.687,12\n",
        "",
        "-",
    ],
)
def test_the_canonical_grammar_refuses_anything_that_is_not_the_shape(refused: str) -> None:
    """A missing tail, a wrong tail width, or a token carrying anything else refuses.

    ``1.843`` is the case the whole grammar exists for: read permissively it is
    either ``1843`` or ``1.843``, and the token holds no evidence to choose by.

    The trailing-newline case pins the ``fullmatch`` the grammar is evaluated
    with: ``$`` alone also matches immediately before a final newline, so a
    ``match`` would call ``"3.687,12\\n"`` a well-formed amount.
    """
    assert not is_aeat_printed_money(refused)
