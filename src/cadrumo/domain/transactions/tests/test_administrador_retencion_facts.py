"""Gates for the registry-backed LIRPF art. 101.2 administrador retención rates.

The three figures (35 %, 19 %, the 100.000 € INCN threshold) are legal data,
not Python constants. These gates pin the chain the
``aeat-registry-authority-flow`` and ``aeat-calculation-grounding`` rules
require:

    bundled BOE corpus excerpt -> governed fact -> typed record -> the
    rate set the statutory-rate advisory actually compares withheld amounts
    against.

The expected figures are not recomputed from anything the loader does; they
are read out of the bundled BOE corpus excerpts for LIRPF art. 101 and RIRPF
art. 80 and compared against the governed facts, so a drift in either the
excerpt or the fact reds the gate rather than agreeing with itself.

See Also:
    :mod:`domain.transactions.retencion_facts`
        The loader under test.
    :mod:`domain.transactions.tests.test_retencion_facts`
        The sibling RIRPF art. 95 gate this module mirrors.
"""

from __future__ import annotations

import re
import tomllib
from datetime import date
from decimal import Decimal

import pytest

from ....core.directory_scan import scan_directory
from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.facts.resolution import ScalarFactQuery
from ....domain.calculations.registry.schema_base import DateAxis
from ...calculations.registry.authority import bundled_authority
from ..retencion_facts import (
    AdministradorRetencionRates,
    administrador_retencion_legal_refs,
    load_administrador_retencion_rates,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_GENERAL_FACT_ID = "lirpf-art-101:retencion-administrador-general"
_REDUCIDA_FACT_ID = "lirpf-art-101:retencion-administrador-reducida"
_UMBRAL_FACT_ID = "lirpf-art-101:retencion-administrador-incn-umbral-eur"
_LIRPF_REF = "ley-35-2006:art-101"
_RIRPF_REF = "rd-439-2007:art-80"
_CURRENT_EFFECTIVE_DATE = date(2026, 4, 1)


def _resolved_fact(fact_id: str):
    """Resolve one published administrator fact through the runtime authority."""
    return bundled_authority().resolve_governed_fact(
        ScalarFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=_CURRENT_EFFECTIVE_DATE,
        ),
    )


def _corpus_text(filename: str) -> str:
    path = bundled_path("corpus", "normatives", "html") / filename
    raw = path.read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw.replace("\xa0", " ")))


def test_the_bundled_lirpf_excerpt_states_every_administrador_figure() -> None:
    """First link: the LIRPF art. 101 excerpt carries all three operative figures."""
    text = _corpus_text("ley-35-2006-art-101.html")
    assert "35 por ciento" in text
    assert "19 por ciento" in text
    assert "100.000 euros" in text


def test_the_bundled_rirpf_excerpt_states_every_administrador_figure() -> None:
    """The RIRPF art. 80 excerpt states the same three figures, developing the LIRPF rate."""
    text = _corpus_text("rd-439-2007-art-80.html")
    assert "35 por ciento" in text
    assert "19 por ciento" in text
    assert "100.000 euros" in text


def test_governed_facts_match_the_percentages_the_excerpts_state() -> None:
    """Second link: the fact values equal the BOE percentages as fractions."""
    assert _resolved_fact(_GENERAL_FACT_ID).payload.value == Decimal("35") / Decimal("100")
    assert _resolved_fact(_REDUCIDA_FACT_ID).payload.value == Decimal("19") / Decimal("100")
    assert _resolved_fact(_UMBRAL_FACT_ID).payload.value == Decimal("100000")


@pytest.mark.parametrize(
    "fact_id",
    (_GENERAL_FACT_ID, _REDUCIDA_FACT_ID, _UMBRAL_FACT_ID),
    ids=("general", "reducida", "incn-umbral"),
)
def test_every_administrador_fact_cites_its_binding_provision(fact_id: str) -> None:
    """A regulatory value without its binding provision is ungrounded.

    The LIRPF establishing provision is retained directly on every resolved
    fact; the value does not rely on a retired provider declaration.
    """
    assert _LIRPF_REF in _resolved_fact(fact_id).legal_refs


def test_the_fact_cited_provision_resolves_in_the_bundled_legal_catalogue() -> None:
    """The fact's establishing legal id exists with an exact corpus reference."""
    legal_root = bundled_path("registry", "aeat", "legal")
    entries: dict[str, object] = {}
    for path in scan_directory(legal_root, pattern="*.toml"):
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
        legal_table = payload.get("legal")
        if isinstance(legal_table, dict):
            entries.update(legal_table)

    lirpf_entry = entries.get(_LIRPF_REF)
    assert isinstance(lirpf_entry, dict), f"{_LIRPF_REF} is not declared in the legal catalogue"
    assert lirpf_entry["corpus_ref"] == "corpus/normatives/html/ley-35-2006-art-101.html#a101"


def test_loader_returns_the_registry_values_as_a_typed_record() -> None:
    """Third link: the typed record carries exactly the resolved facts."""
    rates = load_administrador_retencion_rates(effective_date=_CURRENT_EFFECTIVE_DATE)

    assert isinstance(rates, AdministradorRetencionRates)
    assert rates.general_rate == _resolved_fact(_GENERAL_FACT_ID).payload.value
    assert rates.reduced_rate == _resolved_fact(_REDUCIDA_FACT_ID).payload.value
    assert rates.reduced_incn_threshold_eur == _resolved_fact(_UMBRAL_FACT_ID).payload.value


def test_the_reduced_rate_is_strictly_below_the_general_rate() -> None:
    """A sanity ordering: the INCN-conditioned rate is the LOWER of the two."""
    rates = load_administrador_retencion_rates(effective_date=_CURRENT_EFFECTIVE_DATE)
    assert rates.reduced_rate < rates.general_rate


def test_administrador_legal_refs_names_the_fact_provision() -> None:
    """Fourth link: the grounding function returns the fact's legal basis."""
    refs = administrador_retencion_legal_refs(effective_date=_CURRENT_EFFECTIVE_DATE)
    assert _LIRPF_REF in refs


def test_no_feature_module_redeclares_the_administrador_rates_as_literals() -> None:
    """The literals this loader replaced must not reappear anywhere in the tree.

    ``aeat-registry-authority-flow`` bars inlined regulatory values; the
    retired ``core.aggregation`` constants are the specific regression this
    guards.

    The retired names are assembled from fragments rather than written out, so
    this module does not match its own scan and the gate needs no
    self-exempting allowlist -- an allowlist is how a scan quietly stops
    covering the thing it was written for.
    """
    # Whole-identifier boundaries: a bare substring match would false-fire on
    # the still-live ``ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND`` diagnostic
    # kind, which legitimately shares the retired constant's prefix.
    retired_patterns = tuple(
        re.compile(r"(?<![A-Za-z0-9_])" + re.escape(literal) + r"(?![A-Za-z0-9_])")
        for literal in (
            "ADMINISTRADOR_RETENCION" + "_RATE",
            "ADMINISTRADOR_RETENCION_REDUCED" + "_RATE",
            "ADMINISTRADOR_RETENCION_REDUCED_INCN" + "_THRESHOLD_EUR",
        )
    )
    package_root = bundled_path().parent
    scanned = scan_directory(package_root, pattern="*.py", recursive=True, require_root=True)
    # Floored for the same reason as the sibling retencion gate: the assertion
    # below is `offenders == []`, so an empty walk reports the same green as a
    # package carrying no reintroduced literal.
    assert scanned, (
        f"the retired-literal scan reached no module under {package_root}; "
        "a walk matching nothing cannot find a reintroduced administrador retencion rate"
    )
    offenders: list[str] = []
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        offenders.extend(str(path.relative_to(package_root)) for pattern in retired_patterns if pattern.search(text))
    assert offenders == [], f"retired administrador retención-rate literal reintroduced in: {offenders}"
