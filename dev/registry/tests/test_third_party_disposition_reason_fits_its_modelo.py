"""A disposition reason claiming "third-party data" must fit the modelo it sits on.

A family disposition explains why a schema family is inapplicable, and the
explanation is operator-facing grounding rather than decoration: it is the only
record of WHY a family that could have carried content carries none.

One sentence -- "an informational declaration reporting third-party data to
AEAT" -- was pasted verbatim onto ten revisions. Checked against each modelo's
official name, it is accurate on four and wrong on the rest, because those
declarants report their OWN facts:

* Modelo 145 is not filed with AEAT at all; the perceptor hands it to the
  PAGADOR, declaring their own personal and family circumstances.
* Modelo 232 reports the declarant's own operaciones vinculadas.
* Modelo 720 reports the declarant's own bienes y derechos en el extranjero.
* Modelo 840 reports the declarant's own actividad economica.

The conclusion those dispositions reach -- no formula family -- was right in
every case, which is exactly why the wrong reason survived: nothing downstream
reads the prose, so only a reader would catch it, and modelo 840's own reviewer
note recorded it and left it standing.

This pins the sentence to the modelos it actually describes. It is an allowlist
because the judgement is a reading of each modelo's nature and cannot be derived
from the tree; every entry states the official name that justifies it, and an
entry that stops matching fails rather than passing quietly.
"""

from __future__ import annotations

import pytest

from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The claim under test, matched on its distinctive phrase rather than the whole
#: sentence so a reworded copy still has to justify itself here.
_THIRD_PARTY_CLAIM = "third-party data"

#: Modelos whose declarant genuinely reports OTHER people's data, with the
#: official name that settles it. A financial entity or declarant files these
#: about its clients, partícipes or counterparties, never about itself.
_REPORTS_OTHERS: dict[str, str] = {
    "189": "Declaracion informativa anual acerca de valores, seguros y rentas",
    "280": "Declaracion informativa anual de Planes de Ahorro a Largo Plazo",
    "345": "Declaracion informativa anual de planes y fondos de pensiones, participes, aportaciones y contribuciones",
    "347": "Operaciones con terceras personas (informativa anual)",
}

#: Modelos corrected away from the claim, with the fact each reports instead.
#: Kept here so a re-paste onto one of them is caught by name.
_REPORTS_OWN_FACTS: dict[str, str] = {
    "145": "the perceptor's own personal and family circumstances, handed to the pagador",
    "232": "the declarant's own operaciones vinculadas y paraisos fiscales",
    "720": "the declarant's own bienes y derechos situados en el extranjero",
    "840": "the declarant's own actividad economica",
}


def _dispositions_claiming_third_party() -> dict[str, list[str]]:
    """Return ``modelo id -> revision ids`` whose disposition reasons make the claim."""
    modelos, _catalogues = _committed_registry_tree()
    found: dict[str, list[str]] = {}
    for modelo in modelos:
        for revision_id, revision in modelo.revisions.items():
            for disposition in revision.family_dispositions.values():
                if _THIRD_PARTY_CLAIM in (disposition.reason or ""):
                    found.setdefault(modelo.id, []).append(revision_id)
                    break
    return found


def test_the_third_party_claim_sits_only_on_modelos_that_report_others() -> None:
    claiming = _dispositions_claiming_third_party()

    assert claiming, (
        "no disposition claims to report third-party data any more, so this gate is "
        "proven by nothing; retire it or re-anchor on the sentence that replaced it"
    )
    assert set(claiming) == set(_REPORTS_OTHERS), {
        "claiming_but_not_allowed": sorted(set(claiming) - set(_REPORTS_OTHERS)),
        "allowed_but_not_claiming": sorted(set(_REPORTS_OTHERS) - set(claiming)),
    }


def test_a_modelo_reporting_its_own_facts_never_makes_the_claim() -> None:
    """Stated separately from its sibling so the failure names the modelo.

    The sibling would also catch a re-paste, but only as a set difference. This
    one says which modelo took a sentence about somebody else's data.
    """
    claiming = _dispositions_claiming_third_party()

    for modelo_id, own_fact in _REPORTS_OWN_FACTS.items():
        assert modelo_id not in claiming, (
            f"modelo {modelo_id} claims to report third-party data, but it reports {own_fact}"
        )


def test_every_allowlisted_modelo_still_carries_the_official_name_that_justifies_it() -> None:
    """The allowlist entries are judgements about a name; the name must still hold.

    Without this the allowlist could outlive the modelo it was written for -- a
    renamed or re-scoped modelo would keep its exemption on the strength of a
    reading nobody re-checked.
    """
    modelos, _catalogues = _committed_registry_tree()
    by_id = {modelo.id: modelo for modelo in modelos}

    for modelo_id, expected_name in _REPORTS_OTHERS.items():
        modelo = by_id.get(modelo_id)
        assert modelo is not None, f"modelo {modelo_id} is allowlisted but no longer in the tree"
        actual = modelo.get_title("es")
        assert actual == expected_name, (
            f"modelo {modelo_id} is now titled {actual!r}, not {expected_name!r}; re-read whether "
            "it still reports other people's data before leaving it allowlisted"
        )


def test_the_corrected_modelos_say_what_they_do_report() -> None:
    """A correction that only deleted the wrong claim would leave no grounding.

    Each corrected disposition has to state the declarant's own subject, so the
    operator reading it learns why the family is empty rather than merely that
    it is.
    """
    modelos, _catalogues = _committed_registry_tree()
    by_id = {modelo.id: modelo for modelo in modelos}

    for modelo_id in _REPORTS_OWN_FACTS:
        modelo = by_id[modelo_id]
        reasons = [
            disposition.reason or ""
            for revision in modelo.revisions.values()
            for disposition in revision.family_dispositions.values()
        ]
        assert reasons, f"modelo {modelo_id} declares no family disposition to check"
        assert any("OWN" in reason or "own" in reason for reason in reasons), (
            f"modelo {modelo_id} no longer states whose facts it reports in any disposition reason"
        )
