"""Every IVA registry table refuses to load over an ungrounded citation.

The tables under ``registry/aeat/iva/`` are regulatory values, and each row names
the provision establishing it. Until a loader resolves that name, the citation is
validated by nothing: an identifier naming a provision nobody defined parses
exactly like one naming a provision the BOE carries, and reads as grounded to
every later reader.

Three properties, in order of what they protect.

The citations SHIPPED today all resolve, checked by loading each table through
its real loader. That is a claim about the committed tree, and it is deliberately
made by calling the production loader rather than by re-walking the TOML: a test
that walks the files itself asserts a property of the bytes, while the thing that
matters is whether the code path callers use would have refused them.

The verifier REFUSES the three ways a citation goes wrong -- an identifier no
catalogue defines, a real identifier whose required text is absent from the law,
and a real identifier resolved at the wrong anchor. The anchor case is the one
worth naming: the required text is present in the consolidated document and
absent from the article the citation points at, so a file-scoped check passes it
and only an anchor-scoped one refuses. Losing that scoping would leave every
grounding check in the tree passing on any phrase occurring anywhere in six
hundred thousand characters of law.

The citation FIELD NAMES the tables use are not uniform, and that is a hazard
rather than a wart: the rate, recargo and territory tables write ``legal_refs``
while the place-of-supply table writes ``legal_references`` beside an
``establishing_reference``. A sweep discovering citations by searching for one
field name would have examined none of the place-of-supply table -- fifty-one of
the seventy-five citation occurrences in the tree -- and passed. Nothing here
discovers citations by field name; each loader hands over what it already parsed.

See Also:
    :func:`~domain.calculations.registry.verify_legal_reference`
        The registry's evidence validator, which every citation resolves through.
    :class:`~domain.iva.IvaTerritorialScope`
        The territorial classification whose table was the last to be routed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....core.resources import bundled_path
from ...calculations.registry.schema_references import LegalReference
from .._establishment import _excluded_territories_by_prefix
from .._grounding import registry_catalogues, verify_table_legal_refs
from .._place_of_supply import load_place_of_supply_table
from .._rates import load_iva_rate_table
from .._recargo_equivalencia import load_recargo_rate_table
from ..errors import IvaCatalogueError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: One provision per table, named so a rename or a dropped citation reds here
#: rather than letting a table pass with nothing left to check. Each is the
#: provision its table's values actually rest on, not an arbitrary member.
_ANCHOR_CITATIONS: dict[str, str] = {
    "rates.toml": "ley-37-1992:art-90",
    "recargo-rates.toml": "ley-37-1992:art-161",
    "place_of_supply.toml": "ley-37-1992:art-68",
    "territories.toml": "ley-37-1992:art-3.dos",
}


def _catalogue_entry(reference_id: str) -> LegalReference:
    legal, _sources, _root = registry_catalogues()
    entry = legal.get(reference_id)
    assert entry is not None, f"{reference_id} is absent from the legal catalogue, so this case cannot discriminate"
    return entry


# --------------------------------------------------------------------------
# The shipped tables load, which is the grounding claim made through the
# production path rather than about the bytes.
# --------------------------------------------------------------------------


def test_every_shipped_iva_table_loads_through_its_grounding_verifier() -> None:
    """Each loader resolves its own citations, so loading IS the grounding check.

    Loading four tables and asserting each returned something is a weak-looking
    case that is doing real work: every one of these loaders now refuses on an
    unresolvable citation, so a green here is the statement that no row in the
    committed tree cites a provision the bundled corpus does not carry at the
    anchor and with the wording the catalogue declares.
    """
    assert load_iva_rate_table(), "the rate table loaded no rows"
    assert load_recargo_rate_table(), "the recargo rate table loaded no rows"
    assert load_place_of_supply_table(), "the place-of-supply table loaded no rules"
    assert _excluded_territories_by_prefix(), "the territory table loaded no excluded prefix"


def test_each_table_still_cites_the_provision_its_values_rest_on() -> None:
    """Anchors for the case above, which would otherwise pass over emptied tables.

    A loader verifies the citations a table carries, and a table carrying none
    verifies nothing while loading perfectly. These four ids are the provisions
    the four tables are built on, so a table that quietly stopped citing its own
    foundation fails here instead of passing vacuously above.
    """
    root = bundled_path("registry", "aeat", "iva")
    for relative, reference_id in _ANCHOR_CITATIONS.items():
        text = (root / relative).read_text(encoding="utf-8")
        assert reference_id in text, f"{relative} no longer cites {reference_id}, which its values rest on"
        entry = _catalogue_entry(reference_id)
        assert entry.corpus_ref.partition("#")[2], f"{reference_id} names no anchor, so its check is file-scoped"
        assert entry.required_text, f"{reference_id} declares no required_text, so its corpus is never read"


# --------------------------------------------------------------------------
# The verifier refuses. Real catalogue entries, real corpus, real resolver.
# --------------------------------------------------------------------------


def test_an_identifier_no_catalogue_defines_is_refused() -> None:
    with pytest.raises(IvaCatalogueError, match="unknown legal_ref 'no-such-provision'"):
        verify_table_legal_refs("synthetic-table", [("row", ("no-such-provision",))])


def test_every_failure_is_reported_rather_than_only_the_first() -> None:
    """One load reports every ungrounded row, not one debugging round per row."""
    with pytest.raises(IvaCatalogueError) as caught:
        verify_table_legal_refs(
            "synthetic-table",
            [("first", ("no-such-provision",)), ("second", ("also-absent",))],
        )
    message = str(caught.value)
    assert "first: unknown legal_ref 'no-such-provision'" in message
    assert "second: unknown legal_ref 'also-absent'" in message


def _write_corpus(tmp_path: Path, *, filename: str, units: list[dict[str, str]]) -> Path:
    """Write a document plus the extracted sidecar the resolver actually reads."""
    document = tmp_path / "corpus" / "normatives" / "html" / filename
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text("<p>document body</p>", encoding="utf-8")
    document.with_name(document.name + ".extracted.json").write_text(
        json.dumps({"units": units}),
        encoding="utf-8",
    )
    return document


def _relocated(entry: LegalReference, *, corpus_ref: str, required_text: tuple[str, ...]) -> LegalReference:
    return entry.model_copy(update={"corpus_ref": corpus_ref, "required_text": required_text})


def test_a_citation_whose_required_text_the_law_lacks_is_refused(tmp_path: Path) -> None:
    """The wording check, driven against a real corpus that genuinely omits it.

    The entry is a real catalogue entry repointed at a corpus this test wrote,
    so the refusal comes from the production resolver reading real bytes rather
    than from a substituted verifier.
    """
    _write_corpus(tmp_path, filename="one-article.html", units=[{"anchor": "a90", "text": "text without the phrase"}])
    entry = _relocated(
        _catalogue_entry(_ANCHOR_CITATIONS["rates.toml"]),
        corpus_ref="corpus/normatives/html/one-article.html#a90",
        required_text=("21 por ciento",),
    )

    from ...calculations.registry.errors import RegistryValidationError
    from ...calculations.registry.legal import verify_legal_reference

    with pytest.raises(RegistryValidationError, match="missing required text"):
        verify_legal_reference(entry, source_root=tmp_path)


def test_a_citation_resolved_at_the_wrong_anchor_is_refused(tmp_path: Path) -> None:
    """The property a file-scoped check cannot have, pinned directly.

    Both articles live in one document and only the second carries the phrase.
    A check reading the file passes; a check reading the cited article refuses.
    The citation points at the first article, so a green here would mean the
    anchor stopped scoping and every grounding check in the tree weakened at
    once.
    """
    _write_corpus(
        tmp_path,
        filename="two-articles.html",
        units=[
            {"anchor": "a90", "text": "tipo impositivo general"},
            {"anchor": "a91", "text": "tipos impositivos reducidos 10 por ciento"},
        ],
    )
    entry = _relocated(
        _catalogue_entry(_ANCHOR_CITATIONS["rates.toml"]),
        corpus_ref="corpus/normatives/html/two-articles.html#a90",
        required_text=("tipos impositivos reducidos",),
    )

    from ...calculations.registry.errors import RegistryValidationError
    from ...calculations.registry.legal import verify_legal_reference

    with pytest.raises(RegistryValidationError):
        verify_legal_reference(entry, source_root=tmp_path)


def test_the_same_wording_verifies_at_the_anchor_that_carries_it(tmp_path: Path) -> None:
    """The positive control for the case above.

    Without it, the refusal proves only that something failed -- a resolver that
    refused every anchor would satisfy the wrong-anchor case just as well. Same
    document, same wording, correct anchor, and it passes.
    """
    _write_corpus(
        tmp_path,
        filename="two-articles.html",
        units=[
            {"anchor": "a90", "text": "tipo impositivo general"},
            {"anchor": "a91", "text": "tipos impositivos reducidos 10 por ciento"},
        ],
    )
    entry = _relocated(
        _catalogue_entry(_ANCHOR_CITATIONS["rates.toml"]),
        corpus_ref="corpus/normatives/html/two-articles.html#a91",
        required_text=("tipos impositivos reducidos",),
    )

    from ...calculations.registry.legal import verify_legal_reference

    assert verify_legal_reference(entry, source_root=tmp_path) is None


# --------------------------------------------------------------------------
# The loaders refuse, driven over real copies of the shipped tables.
# --------------------------------------------------------------------------


def test_the_recargo_loader_refuses_a_row_citing_an_undefined_provision(tmp_path: Path) -> None:
    """A real TOML copy with one citation broken, through the real loader."""
    source = bundled_path("registry", "aeat", "iva", "recargo-rates.toml")
    target = tmp_path / "recargo-rates.toml"
    target.write_text(
        source.read_text(encoding="utf-8").replace("ley-37-1992:art-161", "ley-37-1992:art-161-invented", 1),
        encoding="utf-8",
    )

    with pytest.raises(IvaCatalogueError, match="unknown legal_ref 'ley-37-1992:art-161-invented'"):
        load_recargo_rate_table(target)


def test_the_place_of_supply_loader_refuses_a_rule_citing_an_undefined_provision(tmp_path: Path) -> None:
    source = bundled_path("registry", "aeat", "iva", "place_of_supply.toml")
    target = tmp_path / "place_of_supply.toml"
    target.write_text(
        source.read_text(encoding="utf-8").replace("ley-37-1992:art-84", "ley-37-1992:art-84-invented"),
        encoding="utf-8",
    )

    with pytest.raises(IvaCatalogueError, match="unknown legal_ref 'ley-37-1992:art-84-invented'"):
        load_place_of_supply_table(target)
