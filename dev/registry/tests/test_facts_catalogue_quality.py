"""Detector-teeth tests for facts-only catalogue structural gates."""

from __future__ import annotations

import ast
import tomllib
from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.facts.resolution import ScalarFactQuery, resolve_governed_fact
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue
from dev.registry.compiler.fact_providers import FactProviderRegistration

from ..analysis.facts_catalogue_quality import (
    FactQualityKind,
    facts_catalogue_findings,
    live_facts_catalogue_findings,
    main,
    migration_retirement_findings,
    resolved_fact_provenance_findings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _provider(provider_id: str, directory: str) -> FactProviderRegistration:
    return FactProviderRegistration(
        provider_id=provider_id,
        owned_directories=(directory,),
        compile=lambda registry_root: (),
        collect_fingerprints=lambda _root: (),
        reset=lambda: None,
    )


def _fact(fact_id: str, *variants: dict[str, object]) -> GovernedFact:
    return GovernedFact.model_validate({"fact_id": fact_id, "family": "scalar", "variants": variants})


def _variant(
    variant_id: str,
    start: date,
    end: date | None = None,
    *,
    precedence_over: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = ("aeat-source",),
    citation_refs: tuple[str, ...] = ("aeat-source",),
) -> dict[str, object]:
    return {
        "variant_id": variant_id,
        "date_axis": "transaction_date",
        "valid_from": start,
        "valid_to": end,
        "payload": {"kind": "scalar", "value": 21, "unit": "percent"},
        "legal_refs": ("ley:art-1",),
        "source_refs": source_refs,
        "source_citations": tuple({"source_ref": ref, "required_text": ("Tipo general",)} for ref in citation_refs),
        "review_status": "pending_review",
        "ownership": "authored",
        "precedence_over": precedence_over,
    }


def test_clean_facts_provider_catalogue_has_no_findings() -> None:
    provider = _provider("authored", "facts")
    fact = _fact("iva-rate", _variant("ordinary", date(2025, 1, 1)))

    assert facts_catalogue_findings((provider,), {"authored": (fact,)}, ("facts",)) == ()


def test_complete_legal_only_and_source_only_provenance_lanes_are_accepted() -> None:
    provider = _provider("authored", "facts")
    legal_only = _fact(
        "legal-only",
        _variant("legal", date(2025, 1, 1), source_refs=(), citation_refs=()),
    )
    source_only_variant = (
        _fact("source-only", _variant("source", date(2025, 1, 1)))
        .variants[0]
        .model_copy(
            update={"legal_refs": ()},
        )
    )
    source_only = _fact("source-only", _variant("source", date(2025, 1, 1))).model_copy(
        update={"variants": (source_only_variant,)},
    )

    assert (
        facts_catalogue_findings(
            (provider,),
            {"authored": (legal_only, source_only)},
            ("facts",),
        )
        == ()
    )


def test_neither_partial_and_mismatched_provenance_lanes_are_rejected() -> None:
    provider = _provider("authored", "facts")
    base = _fact("broken", _variant("broken", date(2025, 1, 1)))
    variant = base.variants[0]
    neither = base.model_copy(
        update={
            "variants": (variant.model_copy(update={"legal_refs": (), "source_refs": (), "source_citations": ()}),),
        },
    )
    partial = _fact(
        "partial",
        _variant("partial", date(2025, 1, 1), source_refs=("aeat-source",), citation_refs=()),
    )
    mismatched = base.model_copy(
        update={
            "fact_id": "mismatched",
            "variants": (variant.model_copy(update={"variant_id": "mismatched", "source_refs": ("other",)}),),
        },
    )

    findings = facts_catalogue_findings(
        (provider,),
        {"authored": (neither, partial, mismatched)},
        ("facts",),
    )

    assert len(findings) == 3
    assert {finding.kind for finding in findings} == {FactQualityKind.MISSING_PROVENANCE}


def test_provider_ownership_and_compilation_identity_bite() -> None:
    provider = _provider("authored", "facts")
    findings = facts_catalogue_findings((provider,), {"adapter": ()}, ("facts", "iva"))

    assert {finding.kind for finding in findings} == {
        FactQualityKind.INVALID_PROVIDER,
        FactQualityKind.UNOWNED_DIRECTORY,
    }


def test_fact_and_variant_identity_are_global_across_providers() -> None:
    first = _provider("first", "facts/a")
    second = _provider("second", "facts/b")
    left = _fact("same-fact", _variant("same-variant", date(2025, 1, 1)))
    right = _fact("same-fact", _variant("same-variant", date(2026, 1, 1)))

    findings = facts_catalogue_findings((first, second), {"first": (left,), "second": (right,)}, ("facts/a", "facts/b"))

    assert {finding.kind for finding in findings} == {
        FactQualityKind.DUPLICATE_FACT_ID,
        FactQualityKind.DUPLICATE_VARIANT_ID,
    }


def test_overlapping_same_coordinate_requires_explicit_acyclic_precedence() -> None:
    provider = _provider("authored", "facts")
    ambiguous = _fact(
        "iva-rate",
        _variant("ordinary", date(2025, 1, 1)),
        _variant("override", date(2025, 6, 1), date(2025, 6, 30)),
    )
    ordered = _fact(
        "iva-rate",
        _variant("ordinary", date(2025, 1, 1)),
        _variant("override", date(2025, 6, 1), date(2025, 6, 30), precedence_over=("ordinary",)),
    )

    assert {item.kind for item in facts_catalogue_findings((provider,), {"authored": (ambiguous,)}, ("facts",))} == {
        FactQualityKind.TEMPORAL_AMBIGUITY
    }
    assert facts_catalogue_findings((provider,), {"authored": (ordered,)}, ("facts",)) == ()


def test_cycles_and_precedence_between_disjoint_windows_are_rejected() -> None:
    provider = _provider("authored", "facts")
    fact = _fact(
        "iva-rate",
        _variant("old", date(2024, 1, 1), date(2024, 12, 31), precedence_over=("new",)),
        _variant("new", date(2025, 1, 1), precedence_over=("old",)),
    )

    findings = facts_catalogue_findings((provider,), {"authored": (fact,)}, ("facts",))

    assert {finding.kind for finding in findings} == {FactQualityKind.INVALID_PRECEDENCE}


def test_every_declared_source_requires_a_citation() -> None:
    provider = _provider("authored", "facts")
    fact = _fact(
        "iva-rate",
        _variant("ordinary", date(2025, 1, 1), source_refs=("aeat-source", "aeat-uncited")),
    )

    findings = facts_catalogue_findings((provider,), {"authored": (fact,)}, ("facts",))

    assert {finding.kind for finding in findings} == {FactQualityKind.MISSING_PROVENANCE}


def test_applicable_resolved_fact_without_provenance_is_rejected() -> None:
    fact = _fact("iva-rate", _variant("ordinary", date(2025, 1, 1)))
    resolved = resolve_governed_fact(
        GovernedFactCatalogue(facts={fact.fact_id: fact}),
        ScalarFactQuery(fact_id=fact.fact_id, date_axis="transaction_date", effective_date=date(2025, 1, 1)),
        authority_digest="a" * 64,
    ).model_copy(update={"legal_refs": (), "source_refs": (), "source_citations": ()})

    findings = resolved_fact_provenance_findings((resolved,))

    assert {finding.kind for finding in findings} == {FactQualityKind.PROVENANCE_FREE_RESULT}


def _live_iva_retirement_ledger() -> dict[str, object]:
    return tomllib.loads(
        (Path(__file__).parents[1] / "analysis" / "facts_iva_retirement.toml").read_text(encoding="utf-8"),
    )


def test_only_named_open_s80_s85_holds_are_admitted() -> None:
    ledger = _live_iva_retirement_ledger()
    open_steps = {"W04.P15.S81", "W04.P15.S82", "W04.P15.S83", "W04.P15.S84", "W04.P17.S85"}

    assert migration_retirement_findings(ledger, open_steps=open_steps) == ()


def test_unowned_or_stale_retirement_hold_bites() -> None:
    ledger = _live_iva_retirement_ledger()
    tables = ledger["remaining_structured_tables"]
    assert isinstance(tables, list)
    tables.append(
        {
            "data_path": "src/cadrumo/_data/registry/aeat/iva/unowned.toml",
            "classification": "needs_typed_schema_and_fact_migration",
            "decision": "retain_until_lossless_replacement",
            "direct_readers": ["src/cadrumo/domain/iva/unowned.py:load"],
            "safe_next_scope": "invent a migration",
        },
    )

    findings = migration_retirement_findings(
        ledger,
        open_steps={"W04.P15.S82", "W04.P15.S83", "W04.P15.S84", "W04.P17.S85"},
    )

    assert {finding.kind for finding in findings} == {
        FactQualityKind.UNAPPROVED_MIGRATION_HOLD,
        FactQualityKind.STALE_MIGRATION_HOLD,
    }


def test_closed_s80_s85_holds_must_be_removed_but_need_not_remain_in_the_ledger() -> None:
    ledger = _live_iva_retirement_ledger()
    tables = ledger["remaining_structured_tables"]
    lanes = ledger["lanes"]
    assert isinstance(tables, list)
    assert isinstance(lanes, list)
    ledger["remaining_structured_tables"] = [
        table for table in tables if table["data_path"] != "src/cadrumo/_data/registry/aeat/iva/catalogues.toml"
    ]
    ledger["lanes"] = [lane for lane in lanes if lane["lane_id"] != "iva-local-grounding"]

    assert (
        migration_retirement_findings(
            ledger,
            open_steps={"W04.P15.S82", "W04.P15.S83", "W04.P15.S84"},
        )
        == ()
    )


def test_live_gate_resolves_registered_modelo_projections_with_actual_modelos(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projected = _fact("modelo-projection", _variant("projected", date(2025, 1, 1)))
    provider = FactProviderRegistration(
        provider_id="projection-provider",
        owned_directories=(),
        compile=lambda _root: (),
        collect_fingerprints=lambda _root: (),
        reset=lambda: None,
        project_modelos=lambda _modelos: (),
        inherited_identity_domains=("modelos",),
    )
    marker = object()
    calls: list[tuple[Path, tuple[object, ...]]] = []
    monkeypatch.setattr(
        "dev.registry.analysis.facts_catalogue_quality.load_registry_tree",
        lambda root: ((marker,), object()),
    )
    monkeypatch.setattr(
        "dev.registry.analysis.facts_catalogue_quality.compile_registered_fact_providers",
        lambda root, *, modelos: (
            calls.append((root, tuple(modelos))) or GovernedFactCatalogue(facts={projected.fact_id: projected})
        ),
    )

    assert live_facts_catalogue_findings(tmp_path, (provider,)) == ()
    assert calls == [(tmp_path, (marker,))]


def test_gate_imports_no_modelo_denominator() -> None:
    source = (Path(__file__).parents[1] / "analysis/facts_catalogue_quality.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }

    assert not {name for name in imports if "modelo" in name.lower()}


def test_live_gate_compiles_every_registered_provider_and_uses_its_directory_denominator(tmp_path: Path) -> None:
    calls: list[Path] = []

    def compile_provider(registry_root: Path) -> tuple[GovernedFact, ...]:
        calls.append(registry_root)
        return (_fact("iva-rate", _variant("ordinary", date(2025, 1, 1))),)

    provider = FactProviderRegistration(
        provider_id="live-provider",
        owned_directories=("facts/iva",),
        compile=compile_provider,
        collect_fingerprints=lambda _root: (),
        reset=lambda: None,
    )

    assert live_facts_catalogue_findings(tmp_path, (provider,)) == ()
    assert calls == [tmp_path]


def test_live_gate_reports_provider_compile_failure_and_main_blocks_on_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_compile(registry_root: Path) -> tuple[GovernedFact, ...]:
        raise ValueError("broken catalogue")

    provider = FactProviderRegistration(
        provider_id="broken-provider",
        owned_directories=("facts",),
        compile=broken_compile,
        collect_fingerprints=lambda _root: (),
        reset=lambda: None,
    )
    findings = live_facts_catalogue_findings(tmp_path, (provider,))
    assert {finding.kind for finding in findings} == {FactQualityKind.INVALID_PROVIDER}

    monkeypatch.setattr(
        "dev.registry.analysis.facts_catalogue_quality.live_facts_catalogue_findings",
        lambda _root: findings,
    )
    assert main(["--registry-root", str(tmp_path)]) == 1
