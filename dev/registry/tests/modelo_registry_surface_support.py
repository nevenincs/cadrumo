"""Assertions shared by the per-modelo registry tests over the live-surface, extraction and link declarations."""

from __future__ import annotations

from collections.abc import Iterable

from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.tests.aeat_literal_fixtures import aeat_host

FORBIDDEN_REMOTE_ACTIONS = frozenset(
    [
        "server-side-save",
        "signing",
        "presentation",
        "payment",
        "amendment",
        "cancellation",
        "document-submission",
        "declaration-submission",
    ],
)


def assert_authenticated_read_surface_is_read_only(modelo: ModeloDefinition) -> None:
    for revision in modelo.revisions.values():
        decision = next(ref for ref in revision.live_cross_references if ref.surface == "authenticated_read_surface")
        assert decision.requires_authentication is True
        assert decision.requires_aeat_authorization is True
        assert decision.synthetic_data_allowed is False
        assert set(decision.allowed_methods) <= {"GET", "HEAD", "OPTIONS"}, revision.id
        assert set(decision.allowed_hosts) == {aeat_host("www1"), aeat_host("www6")}, revision.id
        assert FORBIDDEN_REMOTE_ACTIONS.issubset(decision.forbidden_actions), revision.id


def assert_declaration_pdf_profile_legal_refs(modelo: ModeloDefinition, expected_refs: Iterable[str]) -> None:
    expected = frozenset(expected_refs)
    for revision in modelo.revisions.values():
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        pdf_profiles = [profile for profile in revision.extraction_profiles if profile.surface == "declaracion_pdf"]
        assert pdf_profiles, revision.id
        for profile in pdf_profiles:
            target_refs = frozenset(
                legal_ref
                for target in profile.target_casillas
                for legal_ref in casillas_by_id[target.casilla_id].legal_refs
            )
            assert target_refs == expected
            assert frozenset(profile.legal_refs) == expected


def assert_review_surfaces_require_snapshot(modelo: ModeloDefinition) -> None:
    required_surfaces = {"review", "approval", "reconciliation", "workflow"}
    for revision in modelo.revisions.values():
        construct = revision.constructs[0]
        linked_by_surface = {link.surface: link for link in revision.application_links}
        assert required_surfaces <= set(linked_by_surface), revision.id
        for link in revision.application_links:
            if link.surface not in required_surfaces:
                continue
            assert link.requires_snapshot is True
            assert link.id in construct.application_links
