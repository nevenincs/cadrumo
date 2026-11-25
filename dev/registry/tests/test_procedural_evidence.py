"""Focused tests for procedural evidence backed by guidance or BOE clauses."""

from __future__ import annotations

from datetime import date
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions

from ..compiler.authority import compile_structural_authority
from ..compiler.validate_evidence import EvidenceValidator
from ..compiler.validate_registry_surfaces import validate_deadline_window_section

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Modelo 136's two authored editions: the older one is closed, the newer one open.
_M136_EARLY, _M136_LATE = authored_revisions("136")
_M136_EARLY_LAST = _M136_EARLY.valid_to
if _M136_EARLY_LAST is None:
    raise LookupError("modelo 136's older edition must be closed by its successor")
_YEAR_BEFORE_EARLY_END = date(_M136_EARLY_LAST.year - 1, 12, 31)


@cache
def _authority():
    return compile_structural_authority(bundled_path("registry", "aeat"), bundled_path())


def _catalogues():
    return _authority().catalogues


def _validator(*, legal_updates=None, source_updates=None) -> EvidenceValidator:
    catalogues = _catalogues()
    legal = dict(catalogues.legal)
    sources = dict(catalogues.sources)
    if legal_updates:
        legal.update(legal_updates)
    if source_updates:
        sources.update(source_updates)
    return EvidenceValidator(legal_refs=legal, source_refs=sources, source_root=bundled_path())


def _require(
    validator: EvidenceValidator,
    source_refs: tuple[str, ...],
    legal_refs: tuple[str, ...],
    *,
    valid_from: date = _M136_EARLY.valid_from,
    valid_to: date = _M136_EARLY_LAST,
) -> list[str]:
    return validator.require_procedural_evidence(
        "revision",
        "procedural-test",
        source_refs,
        legal_refs,
        valid_from=valid_from,
        valid_to=valid_to,
    )


def test_matching_boe_clause_in_cited_form_spec_passes() -> None:
    assert (
        _require(
            _validator(),
            ("boe-modelo-136-base-order",),
            ("orden-hap-70-2013:art-7",),
        )
        == []
    )


def test_clause_can_explicitly_govern_the_prior_information_year() -> None:
    governed_from = _catalogues().legal["orden-hfp-823-2022:art-4"].governs_periods_from
    assert governed_from is not None, "the clause declares the information year it governs"
    assert (
        _require(
            _validator(),
            ("boe-modelo-345-base-order",),
            ("orden-hfp-823-2022:art-4",),
            valid_from=governed_from,
            valid_to=date(governed_from.year, 12, 31),
        )
        == []
    )


@pytest.mark.parametrize("legal_refs", [(), ("orden-eha-3481-2008:art-5",)])
def test_missing_or_unrelated_boe_clause_fails(legal_refs: tuple[str, ...]) -> None:
    assert _require(_validator(), ("boe-modelo-136-base-order",), legal_refs)


def test_boe_source_without_explicit_start_fails() -> None:
    catalogues = _catalogues()
    source = catalogues.sources["boe-modelo-136-base-order"].model_copy(update={"applies_from": None})
    assert _require(
        _validator(source_updates={source.id: source}),
        (source.id,),
        ("orden-hap-70-2013:art-7",),
    )


@pytest.mark.parametrize("expired", ["source", "legal"])
def test_out_of_window_boe_source_or_clause_fails(expired: str) -> None:
    catalogues = _catalogues()
    source = catalogues.sources["boe-modelo-136-base-order"]
    legal = catalogues.legal["orden-hap-70-2013:art-7"]
    source_updates = (
        {source.id: source.model_copy(update={"applies_to": _YEAR_BEFORE_EARLY_END})} if expired == "source" else None
    )
    legal_updates = (
        {legal.id: legal.model_copy(update={"effective_to": _YEAR_BEFORE_EARLY_END})} if expired == "legal" else None
    )

    assert _require(
        _validator(legal_updates=legal_updates, source_updates=source_updates),
        (source.id,),
        (legal.id,),
    )


def test_existing_official_guidance_route_still_passes() -> None:
    assert (
        _require(
            _validator(),
            ("aeat-modelo-136-procedure",),
            (),
            valid_from=_M136_LATE.valid_from,
            valid_to=date(_M136_LATE.valid_from.year, 12, 31),
        )
        == []
    )


def test_deadline_section_accepts_matching_boe_deadline_clause() -> None:
    authority = _authority()
    modelo = next(item for item in authority.modelos if item.id == "136")
    revision = modelo.revisions[str(_M136_EARLY.id)]
    catalogues = authority.catalogues
    evidence = _validator()

    assert (
        validate_deadline_window_section(
            prefix=f"modelo 136 revision {_M136_EARLY.id}",
            revision=revision,
            legal_refs=catalogues.legal,
            source_refs=catalogues.sources,
            evidence=evidence,
        )
        == []
    )


def test_deadline_section_rejects_matching_boe_clause_without_deadline_text() -> None:
    authority = _authority()
    modelo = next(item for item in authority.modelos if item.id == "136")
    revision = modelo.revisions[str(_M136_EARLY.id)]
    catalogues = authority.catalogues
    legal = dict(catalogues.legal)
    anchor = legal["orden-hap-70-2013:art-7"]
    legal[anchor.id] = anchor.model_copy(update={"required_text": ("obligados tributarios",)})
    evidence = EvidenceValidator(legal_refs=legal, source_refs=catalogues.sources, source_root=bundled_path())

    failures = validate_deadline_window_section(
        prefix=f"modelo 136 revision {_M136_EARLY.id}",
        revision=revision,
        legal_refs=legal,
        source_refs=catalogues.sources,
        evidence=evidence,
    )
    assert any("BOE clauses without filing deadline text" in failure for failure in failures)


def test_deadline_section_rejects_an_unknown_official_modelo_210_code() -> None:
    """A tipo_renta scope naming no declared official code is refused, not silently accepted."""
    authority = _authority()
    catalogues = authority.catalogues
    modelo = next(item for item in authority.modelos if item.id == "210")
    revision = next(
        candidate
        for candidate in modelo.revisions.values()
        if any(window.tipo_renta_scope for window in candidate.deadline_windows)
    )
    windows = tuple(
        window.model_copy(update={"tipo_renta_scope": ("99",)}) if window.tipo_renta_scope else window
        for window in revision.deadline_windows
    )
    drifted = revision.model_copy(update={"deadline_windows": windows})

    with validating_governed_facts(
        CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years())
    ):
        failures = validate_deadline_window_section(
            prefix=f"modelo 210 revision {revision.id}",
            revision=drifted,
            legal_refs=catalogues.legal,
            source_refs=catalogues.sources,
            evidence=_validator(),
        )

    assert any("unknown official Modelo 210 codes ('99',)" in failure for failure in failures)
