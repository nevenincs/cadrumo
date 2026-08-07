"""The territory table's citation resolves, and the statute says what it claims.

The table maps Spanish postal-code prefixes to IVA territories and cites Ley
37/1992 art. 3.Dos for the exclusions it enumerates. Two things can go wrong with
a citation like that and only one of them is visible from the table: the
identifier can name a provision nobody defined, and the provision can fail to say
what the row rests on. This module checks both against the bundled consolidated
text rather than against a literal typed beside the row, because an expectation
copied from the row would pass whatever the row said.

The Balears carry their own case deliberately. "Islands are outside the TAI" is
the plausible wrong generalisation -- Canarias is islands and is outside -- and
the table places the Balears inside by leaving prefix 07 out of the excluded set
rather than by naming them. Nothing in art. 3 names them either, so the case below
pins the mechanism that actually puts them inside: adjacency plus non-exclusion.

The prefix-to-province correspondence is administrative geography rather than tax
law, so no BOE text grounds it and none is checked here.

See Also:
    :class:`~domain.iva.IvaTerritorialScope`
        The closed territorial classification these rows resolve into.
"""

from __future__ import annotations

import tomllib

import pytest

from ....core import normalise_corpus_text
from ....core.resources import bundled_path
from .. import IvaTerritorialScope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The consolidated law, read once, as an anchor into the bundled whole-law file
# rather than a per-article extract -- the shape the grounding rule prefers over
# a hand-authored duplicate.
_LIVA = normalise_corpus_text(
    (bundled_path() / "corpus/normatives/html/ley-37-1992.html.extracted.md").read_text(
        encoding="utf-8",
        errors="replace",
    ),
)

# Every legal catalogue a territory row is allowed to cite into. Listed rather
# than globbed so a row citing a provision parked in some unrelated tree fails
# here instead of resolving by accident.
_CATALOGUE_FILES = (
    "registry/aeat/legal/tax-framework.toml",
    "registry/aeat/legal/iva.toml",
    "registry/aeat/legal/iva-flow.toml",
)


def _territory_records() -> list[dict[str, object]]:
    payload = tomllib.loads(
        bundled_path("registry", "aeat", "iva", "territories.toml").read_text(encoding="utf-8"),
    )
    records = payload["territory"]
    assert records, "the territory registry enumerates no excluded territory"
    return list(records)


def _string_list(record: dict[str, object], field: str) -> list[str]:
    """Return ``field`` as a list of strings, refusing anything else.

    TOML hands back ``object``, and narrowing it with a cast would assert the
    shape rather than check it. A malformed table is a real failure mode here --
    a prefix written as a bare integer would silently never match a string
    comparison -- so the shape is verified rather than declared.
    """
    value = record[field]

    assert isinstance(value, list), f"{field} is not a list: {value!r}"
    for item in value:
        assert isinstance(item, str), f"{field} carries a non-string entry: {item!r}"
    return list(value)


def _catalogue_text() -> str:
    return "".join((bundled_path() / name).read_text(encoding="utf-8", errors="replace") for name in _CATALOGUE_FILES)


def test_every_cited_provision_resolves_in_the_legal_catalogue() -> None:
    """A row citing an article nobody defined is ungrounded and must not ship.

    This is the property the table could not previously assert: the citation
    parsed as an identifier while no catalogue entry carried a ``corpus_ref``, so
    nothing checked it against the statute.
    """
    defined = _catalogue_text()
    cited = {ref for record in _territory_records() for ref in _string_list(record, "legal_refs")}

    assert cited, "no territory row cites a provision; this case would pass vacuously"
    for reference in cited:
        assert f'[legal."{reference}"]' in defined, (
            f"the territory table cites {reference}, which no legal catalogue entry defines"
        )


def test_the_cited_article_excludes_exactly_the_territories_the_table_enumerates() -> None:
    """Checked against the statute, not against the row.

    Art. 3.Dos.1.o excludes Ceuta y Melilla under letter a) and Canarias under
    letter b), on two different grounds -- outside the customs union, and outside
    turnover-tax harmonisation. Both limbs are asserted, so a table that kept one
    exclusion and dropped the other cannot pass.
    """
    assert (
        normalise_corpus_text(
            "en el Reino de España, Ceuta y Melilla y en la República Italiana, Livigno, "
            "en cuanto territorios no comprendidos en la Unión Aduanera",
        )
        in _LIVA
    )
    assert normalise_corpus_text("En el Reino de España, Canarias") in _LIVA

    scopes = {IvaTerritorialScope(str(record["scope"])) for record in _territory_records()}

    assert scopes == {IvaTerritorialScope.ES_CANARIAS, IvaTerritorialScope.ES_CEUTA_MELILLA}, (
        "the table excludes a territory the cited article does not, or drops one it does"
    )


def test_the_balears_are_inside_by_non_exclusion_and_the_statute_never_names_them() -> None:
    """The generalisation this table is shaped to refuse, pinned at both ends.

    The statute end: apartado Uno reaches the adjacent islands and apartado Dos
    excludes no Spanish territory beyond Canarias, Ceuta and Melilla, so nothing
    in art. 3 mentions the Balears at all. The table end: prefix 07 is absent from
    the excluded set, and absence is what places a prefix inside the TAI.

    Asserting the statute is SILENT is the load-bearing half. A future reader who
    finds no mention of the Balears has no way to tell a deliberate absence from
    an incomplete corpus, and would be one plausible edit away from "correcting"
    the table to put the islands outside.
    """
    assert normalise_corpus_text("incluyendo en él las islas adyacentes") in _LIVA
    assert normalise_corpus_text("Baleares") not in _LIVA
    assert normalise_corpus_text("Balears") not in _LIVA

    excluded_prefixes = {
        prefix for record in _territory_records() for prefix in _string_list(record, "postal_prefixes")
    }

    assert "07" not in excluded_prefixes, "the Balears are excluded from the TAI, which art. 3 does not do"
