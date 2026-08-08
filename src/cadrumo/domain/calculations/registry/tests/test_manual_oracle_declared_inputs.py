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

What a declaration proves, and what it does not
-----------------------------------------------

It does NOT prove the declared inputs are the manual's inputs. A wrong
transcription declared in a payload is still wrong — it is merely wrong in ONE
reviewable place, beside a per-input line reference, instead of scattered through a
fixture nobody diffs against the page. What it does buy mechanically is that a
consuming test which BUILDS its fixture from the declaration cannot drift away from
it, which is the specific failure that produced today's three instances.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from .....core.external_constants import UTF_8_ENCODING
from .....core.resources import bundled_path
from .. import ManualWorkedExamplePayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _payload_directory() -> Path:
    return Path(bundled_path("corpus", "manual_oracles"))


def _payload_names() -> tuple[str, ...]:
    """The manual worked-example payloads, globbed exactly as the grounding fold globs them.

    ``modelo-*.json`` rather than ``*.json``, and that is the production reader's own
    pattern rather than a convenience: the directory also holds oracles of other shapes
    that :class:`ManualWorkedExamplePayload` does not parse and the fold never reads. A
    gate that widened the glob would measure a different population than the contract it
    is gating, and would refuse a file no consumer of this model ever sees.
    """
    return tuple(sorted(path.name for path in _payload_directory().glob("modelo-*.json")))


def _payload(name: str) -> ManualWorkedExamplePayload:
    path = _payload_directory() / name
    return ManualWorkedExamplePayload.model_validate_json(path.read_text(encoding=UTF_8_ENCODING))


#: Payloads that have not yet declared their scenario inputs, each with its reason.
#:
#: A reason states WHERE the scenario facts currently live, because that is what a
#: migration has to move. Some payloads are named by no test's source at all — they
#: are reached through a constructed filename — and for those, locating the consuming
#: fixture is itself the first step of migrating them; their reasons say so. No count
#: is stated here for the same reason none is asserted: it would be wrong the moment a
#: payload migrates, and the entries themselves are the inventory.
_UNMIGRATED_PAYLOADS: Mapping[str, str] = {
    "modelo-100-2024-capital-inmobiliario-arrendamiento-vivienda-tensionada.json": (
        "scenario facts still hand-written in "
        "test_m100_2024_capital_inmobiliario_arrendamiento_vivienda_manual_worked_example.py"
    ),
    "modelo-100-2024-ganancias-patrimoniales-transmision-inmueble.json": (
        "scenario facts still hand-written in "
        "test_m100_2024_ganancias_patrimoniales_transmision_inmueble_manual_worked_example.py"
    ),
    "modelo-100-2024-integracion-compensacion-ganancias-patrimoniales.json": (
        "scenario facts still hand-written in "
        "test_m100_2024_integracion_compensacion_ganancias_patrimoniales_manual_worked_example.py"
    ),
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
    "modelo-200-2024-ejemplo1-tributacion-minima-empresa-grande.json": (
        "scenario facts still hand-written in test_modelo_200_2024_ejemplo1_tributacion_minima_manual_worked_example.py"
    ),
    "modelo-202-2025-primer-pago-modalidad-40-2.json": (
        "scenario facts still hand-written in test_modelo_202_2025_pago_fraccionado_manual_worked_example.py"
    ),
    "modelo-303-2024-regimen-general-recargo-intracomunitaria-importacion.json": (
        "the IVA manual ships as source.pdf with NO extracted text -- unlike the renta manuals, which carry source.pdf.extracted.md -- so a per-input line locator cannot be constructed at all, only the page reference this payload already holds as raw_evidence_locator. DeclaredScenarioInputs requires locator_by_casilla_id, and a locator that cannot point at the figure it claims would assert a reviewability that is not there. Blocked on extracting the IVA corpus, not on this contract's design. Separately, test_m303_2024_regimen_general_manual_worked_example.py drives the registry through constructed IvaLedgerObservation rows the manual does not print; it states only the outcome aggregates, which are already this payload's expected_by_casilla_id, so there is no printed INPUT to declare"
    ),
    "modelo-303-2025-prorrata-general-regularizacion.json": (
        "the IVA manual ships as source.pdf with NO extracted text -- unlike the renta manuals, which carry source.pdf.extracted.md -- so a per-input line locator cannot be constructed at all, only the page reference this payload already holds as raw_evidence_locator. DeclaredScenarioInputs requires locator_by_casilla_id, and a locator that cannot point at the figure it claims would assert a reviewability that is not there. Blocked on extracting the IVA corpus, not on this contract's design. Its two consumers, test_prorrata_regularizacion_oracle.py and test_prorrata_regularizacion_source_resolver.py, are not ledger-driven and would migrate cleanly once the corpus is extracted; they must move together"
    ),
    "modelo-322-2024-grupo-entidades-delta.json": (
        "the IVA manual ships as source.pdf with NO extracted text -- unlike the renta manuals, which carry source.pdf.extracted.md -- so a per-input line locator cannot be constructed at all, only the page reference this payload already holds as raw_evidence_locator. DeclaredScenarioInputs requires locator_by_casilla_id, and a locator that cannot point at the figure it claims would assert a reviewability that is not there. Blocked on extracting the IVA corpus, not on this contract's design. Separately, test_m322_2024_grupo_entidades_manual_worked_example.py drives the registry through constructed IvaLedgerObservation rows the manual does not print; it states only the outcome aggregates, which are already this payload's expected_by_casilla_id, so there is no printed INPUT to declare"
    ),
    "modelo-322-2024-grupo-entidades-omega.json": (
        "the IVA manual ships as source.pdf with NO extracted text -- unlike the renta manuals, which carry source.pdf.extracted.md -- so a per-input line locator cannot be constructed at all, only the page reference this payload already holds as raw_evidence_locator. DeclaredScenarioInputs requires locator_by_casilla_id, and a locator that cannot point at the figure it claims would assert a reviewability that is not there. Blocked on extracting the IVA corpus, not on this contract's design. Separately, test_m322_2024_grupo_entidades_manual_worked_example.py drives the registry through constructed IvaLedgerObservation rows the manual does not print; it states only the outcome aggregates, which are already this payload's expected_by_casilla_id, so there is no printed INPUT to declare"
    ),
    "modelo-353-2024-grupo-entidades-agregado.json": (
        "the IVA manual ships as source.pdf with NO extracted text -- unlike the renta manuals, which carry source.pdf.extracted.md -- so a per-input line locator cannot be constructed at all, only the page reference this payload already holds as raw_evidence_locator. DeclaredScenarioInputs requires locator_by_casilla_id, and a locator that cannot point at the figure it claims would assert a reviewability that is not there. Blocked on extracting the IVA corpus, not on this contract's design. Separately, test_m353_2024_grupo_entidades_manual_worked_example.py drives the registry through constructed IvaLedgerObservation rows the manual does not print; it states only the outcome aggregates, which are already this payload's expected_by_casilla_id, so there is no printed INPUT to declare"
    ),
    "modelo-390-2024-resumen-anual-cuatro-trimestres.json": (
        "the IVA manual ships as source.pdf with NO extracted text -- unlike the renta manuals, which carry source.pdf.extracted.md -- so a per-input line locator cannot be constructed at all, only the page reference this payload already holds as raw_evidence_locator. DeclaredScenarioInputs requires locator_by_casilla_id, and a locator that cannot point at the figure it claims would assert a reviewability that is not there. Blocked on extracting the IVA corpus, not on this contract's design. Separately, test_m390_2024_annual_manual_worked_example.py drives the registry through constructed IvaLedgerObservation rows the manual does not print; it states only the outcome aggregates, which are already this payload's expected_by_casilla_id, so there is no printed INPUT to declare"
    ),
}


def test_every_payload_either_declares_inputs_or_states_why_not() -> None:
    """A new oracle must decide, at authoring time, whether it declares its scenario.

    The refusal this exists for is a payload arriving with neither — which is how the
    corpus reached 22 payloads that all pinned outputs and none pinned inputs, with no
    surface anywhere recording that as a gap.
    """
    undecided = sorted(
        name for name in _payload_names() if _payload(name).declared_inputs is None and name not in _UNMIGRATED_PAYLOADS
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
        name for name in _UNMIGRATED_PAYLOADS if name in names and _payload(name).declared_inputs is not None
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
        payload = _payload(name)
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
        declared = _payload(name).declared_inputs
        assert (declared is not None) == ("declared_inputs" in raw), (
            f"{name}: declared_inputs presence disagrees between the raw file and the parsed model"
        )
        if declared is not None:
            assert set(declared.by_casilla_id) == set(declared.locator_by_casilla_id), name
