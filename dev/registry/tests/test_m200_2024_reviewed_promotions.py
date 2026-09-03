"""Contract tests for the invocation-owned M200/2024 promotion snapshot."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..analysis import m200_2024_reviewed_promotions as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_snapshot_compiles_each_receipt_once_and_rechecks_all_canonical_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The explicit snapshot removes replay without replacing any authority check."""
    audits = (SimpleNamespace(casilla_id="audit"),)
    template = SimpleNamespace(adjudications=(SimpleNamespace(casilla_id="s12"),))
    blocker = SimpleNamespace(adjudications=(SimpleNamespace(casilla_id="s14"),))
    unique = SimpleNamespace(adjudications=(SimpleNamespace(casilla_id="s13"),))
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(subject, "audit_bundled_restorations", lambda: audits)
    monkeypatch.setattr(
        subject,
        "compile_m200_2024_same_template_authority",
        lambda *, audits: calls.append(("template", audits)) or template,
    )
    monkeypatch.setattr(
        subject,
        "build_worklist",
        lambda *, audits: calls.append(("worklist", audits)) or {"member": ()},
    )
    monkeypatch.setattr(
        subject,
        "compile_m200_2024_blocker_authority",
        lambda *, audits, worklist, same_template_authority: (
            calls.append(("blocker", (audits, worklist, same_template_authority))) or blocker
        ),
    )
    monkeypatch.setattr(
        subject,
        "compile_m200_2024_unique_authority",
        lambda *, audits: calls.append(("unique", audits)) or unique,
    )
    for verifier in (
        "verify_template_canonical_declarations",
        "verify_blocker_canonical_declarations",
        "verify_unique_canonical_declarations",
    ):
        monkeypatch.setattr(
            subject,
            verifier,
            lambda authority, *, casillas_root: calls.append(("verify", authority)),
        )

    snapshot = subject.build_m200_2024_reviewed_promotion_snapshot()
    assert subject.verified_promoted_candidate_ids(snapshot=snapshot) == {"s12", "s13", "s14"}
    assert [name for name, _value in calls] == [
        "template",
        "worklist",
        "blocker",
        "unique",
        "verify",
        "verify",
        "verify",
    ]
    assert calls[2][1] == (audits, {"member": ()}, template)


def test_snapshot_refuses_overlap_before_canonical_byte_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    overlapping = subject.M200ReviewedPromotionSnapshot(
        audits=(),
        template_authority=SimpleNamespace(adjudications=(SimpleNamespace(casilla_id="same"),)),
        blocker_authority=SimpleNamespace(adjudications=(SimpleNamespace(casilla_id="same"),)),
        unique_authority=SimpleNamespace(adjudications=()),
    )
    monkeypatch.setattr(subject, "verify_template_canonical_declarations", lambda *_args, **_kwargs: pytest.fail())

    with pytest.raises(RegistryValidationError, match="cohorts overlap"):
        subject.verified_promoted_candidate_ids(snapshot=overlapping)
