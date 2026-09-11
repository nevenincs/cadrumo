"""Gates for the registry-backed RIRPF art. 95 retención rates.

The two rate figures are legal data, not Python constants. These gates pin the
chain the ``aeat-registry-authority-flow`` and
``aeat-calculation-grounding`` rules require:

    bundled BOE corpus excerpt → governed fact → typed record → the
    inference bound the transaction model actually applies.

The expected percentages are not recomputed from anything the loader does;
they are read out of the bundled BOE corpus excerpt for RD 439/2007 art. 95
and compared against the governed fact, so a drift in either the excerpt
or the fact reds the gate rather than agreeing with itself.

See Also:
    :mod:`domain.transactions.retencion_facts`
        The loader under test.
    :mod:`domain.iva.tests.test_legal_basis_rate_grounding`
        The sibling corpus → registry → substrate chain for IVA rates.
"""

from __future__ import annotations

import re
import tomllib
from datetime import date
from decimal import Decimal

import pytest
from test_support.registry_authoring import compile_registered_fact_providers

from ....core.directory_scan import scan_directory
from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.facts.resolution import ScalarFactQuery, resolve_governed_fact
from ....domain.calculations.registry.schema_base import DateAxis
from ..errors import TransactionValidationError
from ..retencion_facts import (
    RirpfArt95RetencionRates,
    load_retencion_actividades_rates,
    maximum_supported_activity_retencion_rate,
    retencion_effective_date,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_GENERAL_FACT_ID = "rirpf-art-95:retencion-actividades-profesionales-general"
_INICIO_FACT_ID = "rirpf-art-95:retencion-actividades-profesionales-inicio"
_LEGAL_REF = "rd-439-2007:art-95"
_CURRENT_EFFECTIVE_DATE = date(2026, 4, 1)


def _resolved_fact(fact_id: str):
    """Resolve one authored retención fact through the development compiler."""
    catalogue = compile_registered_fact_providers(bundled_path("registry", "aeat"))
    return resolve_governed_fact(
        catalogue,
        ScalarFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=_CURRENT_EFFECTIVE_DATE,
        ),
        authority_digest="0" * 64,
    )


def _corpus_text() -> str:
    path = bundled_path("corpus", "normatives", "html") / "rd-439-2007-art-95.html"
    raw = path.read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw.replace("\xa0", " ")))


def test_the_bundled_boe_excerpt_states_both_retencion_rates() -> None:
    """First link: the corpus excerpt carries the operative percentage strings."""
    text = _corpus_text()
    assert "15 por ciento sobre los ingresos íntegros satisfechos" in text
    assert "7 por ciento en el período impositivo de inicio de actividades" in text


def test_governed_facts_match_the_percentages_the_excerpt_states() -> None:
    """Second link: the fact values equal the BOE percentages as fractions."""
    assert _resolved_fact(_GENERAL_FACT_ID).payload.value == Decimal("15") / Decimal("100")
    assert _resolved_fact(_INICIO_FACT_ID).payload.value == Decimal("7") / Decimal("100")


@pytest.mark.parametrize(
    "fact_id",
    (_GENERAL_FACT_ID, _INICIO_FACT_ID),
    ids=("general", "inicio-actividad"),
)
def test_every_retencion_fact_cites_its_binding_provision(fact_id: str) -> None:
    """A regulatory value without its binding provision is ungrounded."""
    assert _LEGAL_REF in _resolved_fact(fact_id).legal_refs


def test_the_cited_provision_resolves_in_the_bundled_legal_catalogue() -> None:
    """The cited id must exist as a legal entry with a corpus_ref."""
    legal_root = bundled_path("registry", "aeat", "legal")
    entries: dict[str, object] = {}
    for path in scan_directory(legal_root, pattern="*.toml"):
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
        legal_table = payload.get("legal")
        if isinstance(legal_table, dict):
            entries.update(legal_table)
    entry = entries.get(_LEGAL_REF)
    assert isinstance(entry, dict), f"{_LEGAL_REF} is not declared in the legal catalogue"
    assert entry["corpus_ref"] == "corpus/normatives/html/rd-439-2007-art-95.html#a95"


def test_loader_returns_the_registry_values_as_a_typed_record() -> None:
    """Third link: the typed record carries exactly the resolved facts."""
    rates = load_retencion_actividades_rates(effective_date=_CURRENT_EFFECTIVE_DATE)

    assert isinstance(rates, RirpfArt95RetencionRates)
    assert rates.general_rate == _resolved_fact(_GENERAL_FACT_ID).payload.value
    assert rates.inicio_actividad_rate == _resolved_fact(_INICIO_FACT_ID).payload.value


def test_the_inference_bound_is_the_general_rate() -> None:
    """Fourth link: the bound the transaction model applies is the registry rate.

    The inicio-de-actividades rate is lower, so the general rate is the correct
    upper bound for a bounded inference that must not reject a legitimate 15 %
    withholding.
    """
    rates = load_retencion_actividades_rates(effective_date=_CURRENT_EFFECTIVE_DATE)
    assert maximum_supported_activity_retencion_rate(effective_date=_CURRENT_EFFECTIVE_DATE) == rates.general_rate
    assert rates.inicio_actividad_rate < rates.general_rate


def test_rate_selection_is_reproducible_across_the_2015_legal_change() -> None:
    """The caller's date, not the wall clock, chooses the settled legal rate."""
    before = load_retencion_actividades_rates(effective_date=date(2015, 7, 11))
    after = load_retencion_actividades_rates(effective_date=date(2015, 7, 12))

    assert before.general_rate == Decimal("0.18")
    assert after.general_rate == Decimal("0.15")


def test_unsupported_pre_source_date_refuses_instead_of_selecting_a_nearest_rate() -> None:
    """An uncovered coordinate has no fallback variant."""
    with pytest.raises(TransactionValidationError, match="failed to resolve retención fact"):
        load_retencion_actividades_rates(effective_date=date(2007, 3, 31))


def test_transaction_coordinate_prefers_value_date_and_refuses_when_absent() -> None:
    """Settlement evidence is explicit; neither a book date nor the clock is invented."""
    assert retencion_effective_date(value_date=date(2024, 2, 1), booked_date=date(2024, 2, 2)) == date(2024, 2, 1)
    assert retencion_effective_date(value_date=None, booked_date=date(2024, 2, 2)) == date(2024, 2, 2)
    with pytest.raises(TransactionValidationError, match="requires a transaction value or booked date"):
        retencion_effective_date(value_date=None, booked_date=None)


def test_no_feature_module_redeclares_the_retencion_rates_as_literals() -> None:
    """The literal this loader replaced must not reappear anywhere in the tree.

    ``aeat-registry-authority-flow`` bars inlined regulatory values; the retired
    ``_MAX_SUPPORTED_ACTIVITY_WITHHOLDING`` ``_RATE`` constant is the specific
    regression this guards.

    The retired name is assembled from fragments rather than written out, so
    this module does not match its own scan and the gate needs no self-exempting
    allowlist — an allowlist is how a scan quietly stops covering the thing it
    was written for.
    """
    retired_literal = "_MAX_SUPPORTED_ACTIVITY" + "_WITHHOLDING_RATE"
    package_root = bundled_path().parent
    scanned = scan_directory(package_root, pattern="*.py", recursive=True, require_root=True)
    # Floored because the assertion below is `offenders == []`: an empty walk
    # reports the same green as a package with no reintroduced literal, so a
    # moved package root would retire this gate without a word.
    assert scanned, (
        f"the retired-literal scan reached no module under {package_root}; "
        "a walk matching nothing cannot find a reintroduced retencion rate"
    )
    offenders = [
        str(path.relative_to(package_root)) for path in scanned if retired_literal in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"retired retención-rate literal reintroduced in: {offenders}"
