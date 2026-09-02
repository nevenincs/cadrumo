"""Ratchet: every manual worked-example oracle declares its inputs, or says why not.

The AEAT manual worked-example contract pinned only the OUTPUT — a locator and
``expected_by_casilla_id``. The taxpayer facts that make a worked example *that*
example lived solely in hand-written fixtures, with nothing cross-checking them
against the printed page, so a fixture could reach the manual's figure from a
scenario the manual never states and still read as AEAT-grounded. Three tests did
exactly that in one evening. The sibling replay corpus had already closed this:
:class:`~domain.calculations.registry.RentaWebOpenReplayPayload` carries
``profile_overrides`` while the manual corpus carried nothing.

:class:`~domain.calculations.registry.DeclaredScenarioInputs` closes it here. The
field is optional at the MODEL boundary because the corpus cannot migrate in one
change — and optional-and-unenumerated would be the worse outcome, leaving the hole
open while the contract *appeared* to cover inputs, which is harder to see than
today's uniform absence. So the un-migrated payloads are named here, each with the
reason it has not moved, and this module refuses any payload that is neither
migrated nor named.

The registry shrinks as payloads migrate. **No count is asserted anywhere**: a
tally would encode this moment, train everyone to edit the constant, and then
detect nothing. The property is what is gated — every payload is in exactly one of
the two states, and every entry here names a payload that really exists and really
has not migrated.

**Not every entry is pending work.** Some are ruled permanently out of scope, and
their reasons say so — see :data:`_NO_PRINTED_CASILLA_INPUT`, which covers the six
whose consumed figures never reach a casilla. Read an entry's reason before
treating it as a backlog item: the map holds both "not yet" and "not ever", and
the difference is the whole reason each entry carries prose rather than a flag.

What a declaration proves, and what it does not
-----------------------------------------------

It does NOT prove the declared inputs are the manual's inputs. A wrong
transcription declared in a payload is still wrong — it is merely wrong in ONE
reviewable place, beside a per-input line reference, instead of scattered through a
fixture nobody diffs against the page. What it does buy mechanically is that a
consuming test which BUILDS its fixture from the declaration cannot drift away from
it, which is the specific failure that produced today's three instances.

Migrating a payload: what to declare
-------------------------------------

**A declared input is a fact the scenario CONSUMES.** Not a fact the manual prints
prominently, and not a fact the scenario derives from. Four cases have come up, and
they look alike from a distance.

**Read this one first — it is the only one that fails SILENTLY.**

* The corpus prints the ANTECEDENT, not the figure. The example opens with raw
  facts — a retention certificate, a book of ingresos and gastos — and its solución
  works them into the figures the casillas actually take. Declare the worked figure
  and cite the solución line. Citing the raw one instead looks entirely reasonable,
  sits on the manual's headline lines, passes every check, and points a reviewer at
  a number that does not match the declaration: 10.100 cited for a declared input of
  20.300. The cases below fail visibly, by a missing figure or a refused collision.
  This one succeeds and is wrong.

The rest:

* The corpus does not print it. Scenario scaffolding the engine needs and the
  manual never states — component boxes under a stated total, neutral zeros, a
  marked-X flag whose encoding is ours rather than the page's. Keep it local and
  labelled. Declaring it would attach a locator to a figure the corpus does not
  carry.
* The corpus prints it, as an ANSWER. A stated total that is an expected OUTPUT of
  this same scenario. Declaring it as an input makes the oracle assert what it was
  handed, which :func:`test_no_declared_input_is_also_an_expected_output` refuses.
* One casilla COMBINES several printed items. The registry lumps intereses and
  reparación into a single box; the declared figure is their sum, so the locator
  spans every item it is made of rather than whichever appears first. This one
  arises from the REGISTRY's shape, not the extraction's — the page-break case
  below looks identical and is an artefact of how the corpus was extracted, so a
  reader who has met only that one will expect a contiguous range and miss this.

Migrating a payload: where the locator points
----------------------------------------------

**At what ESTABLISHES the figure, which is not always where the figure is
printed.** Same rule as grounding a casilla on the provision that fixes its value
rather than the framework article, one layer down:

* Where a nota adjusts a line item so the scenario's figure differs from the
  printed one — 18.900 on the line, 1.200 removed by the nota, 17.700 supplied —
  cite BOTH. Citing only the line item sends a reviewer to a number that does not
  match the declaration.
* An input stated only in a nota cites the nota, not the block a faster read
  reaches for.
* Sometimes NOTHING on the page displays the figure as a figure. The amortizaciones
  deducted from an acquisition value appear only inside the arithmetic of a total —
  ``(90.000+8.000-1.620)`` — so 1.620 never stands on its own anywhere. Cite the
  arithmetic line AND the nota establishing how it arose. The pull here is toward
  declaring the TOTAL instead, because the total is printed cleanly and the
  component is not; resist it, because the total is not what the scenario consumes.
* A component set spanning a page break in the extraction carries the ranges its
  components actually fall in, never one span that quietly includes the lines
  between them.

Read every locator off the year's OWN manual. Sibling years state the same caso
práctico at different lines, so copying a sibling's references is the mistake this
is most likely to invite — and no case above would fail a test if got wrong. That
is what the declaration is for: not catching a wrong locator, but putting it in one
reviewable place beside the figure it claims.

Why any of this matters
------------------------

**A literal that happens to match the oracle is not the oracle.** Everything above
is that one sentence in different clothes. A fixture reaching the printed figure
because a different term of a ``min`` binds; a child two years younger than the
manual's, routed through a branch the real case never takes; a scenario whose
literals are identical to the manual's and which is nonetheless a deliberate
departure. In each the VALUE was right and its PROVENANCE was not, and provenance
is the only thing that makes a number evidence rather than a coincidence.

So when a scenario departs from the printed case on purpose, let it depart
visibly — take the manual's figures from the declaration and pass arguments only
for the departure. Three copies of one figure, one of which means something
different, cannot be told apart by reading.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....core.external_constants import UTF_8_ENCODING
from .....core.resources.bundled_data import bundled_path
from .manual_oracle_support import read_manual_worked_example

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _payload_directory() -> Path:
    return Path(bundled_path("corpus", "manual_oracles"))


def _payload_names() -> tuple[str, ...]:
    """The manual worked-example payloads, globbed exactly as the grounding fold globs them.

    ``modelo-*.json`` rather than ``*.json``, and that is the production reader's own
    pattern rather than a convenience: the directory also holds oracles of other shapes
    that :class:`ManualWorkedExamplePayload` does not parse and the fold never reads. A
    gate that widened the pattern would measure a different population than the contract
    it is gating, and would refuse a file no consumer of this model ever sees.
    """
    return tuple(sorted(path.name for path in scan_directory(_payload_directory(), pattern="modelo-*.json")))


#: Payloads that have not yet declared their scenario inputs, each with its reason.
#:
#: A reason states WHERE the scenario facts currently live, because that is what a
#: migration has to move. Some payloads are named by no test's source at all — they
#: are reached through a constructed filename — and for those, locating the consuming
#: fixture is itself the first step of migrating them; their reasons say so. No count
#: is stated here for the same reason none is asserted: it would be wrong the moment a
#: payload migrates, and the entries themselves are the inventory.
#: The one reason six payloads are excluded, ruled once rather than six times.
#:
#: BY DESIGN, NOT A GAP. These payloads' consumed figures never reach a casilla: five
#: drive the registry through IvaLedgerObservation rows the manual does not print, and
#: the M202 scenario's figure arrives as a binding value. The manual states only the
#: outcome aggregates, which are already those payloads' own expected_by_casilla_id, so
#: declaring them would trip
#: :func:`test_no_declared_input_is_also_an_expected_output` -- correctly.
#:
#: :class:`DeclaredScenarioInputs` was NOT widened to admit them, and that is the
#: decision rather than an omission. The contract's whole guarantee is reviewability
#: against a printed page: a locator lets a reviewer hold the declaration beside the
#: manual and check it. A ledger row the manual never prints has nothing to point at,
#: and neither does a binding value. Admitting them would mean declarations carrying no
#: locator, or one aimed at the aggregate they roll into -- a reference that looks
#: reviewable and is not. That would not extend the guarantee to six more payloads; it
#: would weaken it for all twenty-one, because a reader could no longer assume a
#: declared input is a printed fact. The contract meaning one thing is worth more than
#: the coverage.
#:
#: WHAT THIS RULING DOES NOT SETTLE: these six still have the two-independent-
#: transcriptions problem -- test and payload as separate copies of one truth with
#: nothing checking they agree. That risk is real and is explicitly NOT addressed for
#: them. Closing it needs a mechanism other than a locator-bearing declaration, which
#: is a separate question and not a reason to reopen this one.
#:
#: The boundary is a property of individual INPUTS, not of whole payloads: the 2025
#: prorrata payload migrated with two casilla-keyed givens declared while its
#: prior-year volumes, which reach a domain function directly, stayed local.
_NO_PRINTED_CASILLA_INPUT = (
    "ruled out of scope by design, not pending: its consumed figures never reach a "
    "casilla, so there is no printed input DeclaredScenarioInputs.by_casilla_id can key "
    "and no page a locator could point at. Consumed by {test}. See "
    "_NO_PRINTED_CASILLA_INPUT for the full rationale and for what this ruling does not "
    "settle"
)

_UNMIGRATED_PAYLOADS: Mapping[str, str] = {
    "modelo-100-2024-minimo-descendientes-adopcion-mayor-de-tres-rioja.json": (
        "scenario facts still hand-written in test_minimo_descendientes_manual_oracles.py; that surface is "
        "under independent verification after the meses_madre_trabajo month-set migration and must not be "
        "perturbed mid-verification"
    ),
    "modelo-100-2024-minimo-descendientes-declaracion-propia-valenciana.json": (
        "scenario facts still hand-written in test_minimo_descendientes_manual_oracles.py; same "
        "mid-verification hold as the Rioja payload"
    ),
    "modelo-100-2024-minimo-descendientes-prorrateo-asturias.json": (
        "scenario facts still hand-written in test_minimo_descendientes_manual_oracles.py; same "
        "mid-verification hold as the Rioja payload"
    ),
    "modelo-202-2025-primer-pago-modalidad-40-2.json": (
        _NO_PRINTED_CASILLA_INPUT.format(test="test_modelo_202_2025_pago_fraccionado_manual_worked_example.py")
    ),
    "modelo-303-2024-regimen-general-recargo-intracomunitaria-importacion.json": (
        _NO_PRINTED_CASILLA_INPUT.format(test="test_m303_2024_regimen_general_manual_worked_example.py")
    ),
    "modelo-322-2024-grupo-entidades-delta.json": (
        _NO_PRINTED_CASILLA_INPUT.format(test="test_m322_2024_grupo_entidades_manual_worked_example.py")
    ),
    "modelo-322-2024-grupo-entidades-omega.json": (
        _NO_PRINTED_CASILLA_INPUT.format(test="test_m322_2024_grupo_entidades_manual_worked_example.py")
    ),
    "modelo-353-2024-grupo-entidades-agregado.json": (
        _NO_PRINTED_CASILLA_INPUT.format(test="test_m353_2024_grupo_entidades_manual_worked_example.py")
    ),
    "modelo-390-2024-resumen-anual-cuatro-trimestres.json": (
        _NO_PRINTED_CASILLA_INPUT.format(test="test_m390_2024_annual_manual_worked_example.py")
    ),
}


def test_every_payload_either_declares_inputs_or_states_why_not() -> None:
    """A new oracle must decide, at authoring time, whether it declares its scenario.

    The refusal this exists for is a payload arriving with neither — which is how the
    corpus reached 22 payloads that all pinned outputs and none pinned inputs, with no
    surface anywhere recording that as a gap.
    """
    undecided = sorted(
        name
        for name in _payload_names()
        if read_manual_worked_example(name).declared_inputs is None and name not in _UNMIGRATED_PAYLOADS
    )
    if undecided:
        listed = "\n  ".join(undecided)
        raise AssertionError(
            f"{len(undecided)} manual oracle payload(s) neither declare inputs nor are enrolled as "
            f"un-migrated:\n  {listed}\n\n"
            "Declare the scenario's inputs in the payload's 'declared_inputs' block (with a "
            "per-input line reference), and build the consuming test's fixture from it. If the "
            "migration cannot happen in this change, add the payload to _UNMIGRATED_PAYLOADS with "
            "the reason and the location its scenario facts currently live in.",
        )


def test_no_unmigrated_entry_outlives_its_payload() -> None:
    """An entry must name a payload that exists and has genuinely not migrated.

    Both stale shapes hide the same thing. An entry for a deleted payload inflates the
    apparent remaining work; an entry for a payload that HAS since migrated reports a
    gap that is closed, and the registry stops being a truthful account of what is
    left — which is the only reason to keep it.
    """
    names = set(_payload_names())
    vanished = sorted(name for name in _UNMIGRATED_PAYLOADS if name not in names)
    already_migrated = sorted(
        name
        for name in _UNMIGRATED_PAYLOADS
        if name in names and read_manual_worked_example(name).declared_inputs is not None
    )
    problems = [f"{name}: payload no longer exists" for name in vanished]
    problems += [f"{name}: payload now declares inputs, so the entry is stale" for name in already_migrated]
    if problems:
        listed = "\n  ".join(problems)
        raise AssertionError(f"stale _UNMIGRATED_PAYLOADS entries:\n  {listed}\n\nRemove each entry.")


def test_every_unmigrated_entry_states_a_reason() -> None:
    """A bare enrolment is an allowlist; the reason is what makes it reviewable."""
    unreasoned = sorted(name for name, reason in _UNMIGRATED_PAYLOADS.items() if len(reason.strip()) < 20)
    assert not unreasoned, (
        f"_UNMIGRATED_PAYLOADS entries without a substantive reason: {unreasoned}. "
        "State where the scenario facts currently live, which is what a migration has to move."
    )


def test_no_declared_input_is_also_an_expected_output() -> None:
    """An oracle must not hand the engine the very casilla it then claims to check.

    A casilla appearing on both sides is a tautology wearing an AEAT-branded name: the
    assertion would pass by echoing its own input, no matter what the formula chain
    did. This is cheap to state and impossible to see by reading a payload, because
    the two mappings are far apart in the file.
    """
    offenders: dict[str, list[str]] = {}
    for name in _payload_names():
        payload = read_manual_worked_example(name)
        if payload.declared_inputs is None:
            continue
        both = sorted(set(payload.declared_inputs.by_casilla_id) & set(payload.expected_by_casilla_id))
        if both:
            offenders[name] = both
    assert not offenders, (
        f"casilla(s) declared as INPUT and asserted as EXPECTED OUTPUT in the same oracle: {offenders}. "
        "The expected figure would be echoing the supplied one; assert a casilla the engine derives."
    )


def test_declared_inputs_survive_the_strict_payload_model() -> None:
    """The declaration is read through the same strict model the grounding fold uses.

    Reading it here with a local ``json.loads`` would let this module accept a shape the
    fold refuses, so the gate could pass on a payload the production reader rejects.
    """
    for name in _payload_names():
        raw = json.loads((_payload_directory() / name).read_text(encoding=UTF_8_ENCODING))
        declared = read_manual_worked_example(name).declared_inputs
        assert (declared is not None) == ("declared_inputs" in raw), (
            f"{name}: declared_inputs presence disagrees between the raw file and the parsed model"
        )
        if declared is not None:
            assert set(declared.by_casilla_id) == set(declared.locator_by_casilla_id), name
