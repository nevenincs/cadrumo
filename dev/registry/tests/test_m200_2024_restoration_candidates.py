from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import rtoml

from ..analysis import m200_2024_restoration_candidates as subject
from ..analysis.m200_semantic_casilla_candidates import M200CasillaDisposition

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _gap(
    *,
    label: str = "Importe [00093]",
    source_sha256: str = "a" * 64,
    export_field_id: str = "m200-2024.dp200012.f0013",
    authored_token: str = "93",  # noqa: S107 - official casilla token
) -> SimpleNamespace:
    return SimpleNamespace(
        disposition=M200CasillaDisposition.REVISION_MISSING_DECLARATION,
        export_field_id=export_field_id,
        authored_token=authored_token,
        label=label,
        source_ref="aeat-dr-200-2024",
        source_sha256=source_sha256,
        aeat_type="Num",
        length=17,
    )


def _historic() -> dict[str, object]:
    return {
        "id": "93",
        "number": "93",
        "section": ["liquidacion_i"],
        "semantic_role": "is_correcciones_aumentos",
        "data_type": "money",
        "required": False,
        "input_kind": "manual",
        "legal_refs": ["ley-27-2014:art-41"],
        "source_refs": ["aeat-dr-200-2024"],
        "export_refs": ["m200-2024.dp200012.f0013"],
    }


def _proposal() -> subject.RestorationProposal:
    return subject.RestorationProposal(
        id="00093",
        number="00093",
        target_description="Importe [00093]",
        section=("liquidacion_i",),
        semantic_role="is_correcciones_aumentos",
        data_type="money",
        required=False,
        input_kind="manual",
        legal_refs=("ley-27-2014:art-41",),
        source_refs=("aeat-dr-200-2024",),
        export_field_id="m200-2024.dp200012.f0013",
        target_source_ref="aeat-dr-200-2024",
        target_source_sha256="a" * 64,
        historic_commit=subject.HISTORIC_COMMIT,
        historic_path="historic/z2024only-dp200012.toml",
    )


def _entry(*, legal_refs: tuple[str, ...] = ("ley-27-2014:art-41",)) -> SimpleNamespace:
    return SimpleNamespace(
        export_field_id="m200-2024.dp200012.f0013",
        source_refs=("aeat-dr-200-2024",),
        legal_refs=legal_refs,
    )


def test_build_returns_target_first_proposal_without_authority_writer(monkeypatch) -> None:
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (_gap(),))
    monkeypatch.setattr(subject, "load_semantic_map", lambda _path: SimpleNamespace(entries=(_entry(),)))
    monkeypatch.setattr(
        subject,
        "_historic_index",
        lambda: {"m200-2024.dp200012.f0013": (("z2024only-dp200012.toml", _historic()),)},
    )

    proposals, refusals = subject.build_bundled_restoration_proposals()

    assert not refusals
    assert proposals[0].id == "00093"
    assert proposals[0].export_field_id == "m200-2024.dp200012.f0013"
    assert proposals[0].target_description == "Importe [00093]"
    assert proposals[0].semantic_role == "is_correcciones_aumentos"
    assert not hasattr(subject, "render_apply_patch")
    assert not hasattr(subject, "_render_registry_fragment")


def test_build_refuses_ambiguous_historic_export_identity(monkeypatch) -> None:
    match = ("z2024only-dp200012.toml", _historic())
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (_gap(),))
    monkeypatch.setattr(subject, "load_semantic_map", lambda _path: SimpleNamespace(entries=(_entry(),)))
    monkeypatch.setattr(subject, "_historic_index", lambda: {"m200-2024.dp200012.f0013": (match, match)})

    proposals, refusals = subject.build_bundled_restoration_proposals()

    assert not proposals
    assert refusals[0].reason == "historic export match count is 2"


def test_render_review_toml_is_deterministic_and_cannot_be_registry_toml() -> None:
    refusal = subject.RestorationRefusal("m200-2024.dp200012.f0014", "ambiguous")

    rendered = subject.render_review_toml((_proposal(),), (refusal,))
    parsed = rtoml.loads(rendered)

    assert rendered == subject.render_review_toml((_proposal(),), (refusal,))
    assert parsed["authority_status"] == "proposal_only"
    assert parsed["historic_commit"] == subject.HISTORIC_COMMIT
    assert "revisions" not in parsed
    assert "restoration_proposal" in parsed
    assert "restoration_refusal" in parsed
    assert "[[revisions" not in rendered
    assert "*** Begin Patch" not in rendered


def test_cli_writes_then_checks_explicit_review_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subject, "build_bundled_restoration_proposals", lambda: ((_proposal(),), ()))
    output = tmp_path / "review.toml"

    assert subject.main(["--output", str(output)]) == 0
    assert subject.main(["--output", str(output), "--check"]) == 0


def test_cli_rejects_retired_patch_switch() -> None:
    with pytest.raises(SystemExit):
        subject.main(["--emit-patch"])


def test_target_description_mutation_is_refused() -> None:
    reason = subject._refusal_reason(
        _gap(label="Changed official description [00093]"),
        _entry(),
        _historic(),
        expected_target_description="Importe [00093]",
        expected_source_ref="aeat-dr-200-2024",
        expected_source_sha256="a" * 64,
    )

    assert reason == "current target description differs from the pinned official design"


def test_semantic_role_mutation_is_refused_against_pinned_historic_blob(monkeypatch) -> None:
    path = f"{subject.HISTORIC_ROOT}/z2024only-dp200012.toml"
    document = {"revisions": {"2024": {"casillas": [_historic()]}}}
    monkeypatch.setattr(subject, "_git", lambda *_args: rtoml.dumps(document))

    mutated = {**_historic(), "semantic_role": "is_mutated_role"}

    assert not subject._historic_payload_is_pinned(path, _gap().export_field_id, mutated)


def test_legal_reference_mutation_is_refused() -> None:
    mutated = {**_historic(), "legal_refs": ["ley-27-2014:art-99"]}

    assert subject._refusal_reason(_gap(), _entry(), mutated) == (
        "historic semantic legal payload disagrees with current reviewed map"
    )


def test_source_sha_mutation_is_refused() -> None:
    reason = subject._refusal_reason(
        _gap(source_sha256="b" * 64),
        _entry(),
        _historic(),
        expected_target_description="Importe [00093]",
        expected_source_ref="aeat-dr-200-2024",
        expected_source_sha256="a" * 64,
    )

    assert reason == "current target source SHA-256 differs from the semantic map"


def test_source_sha_malformed_value_is_refused() -> None:
    assert subject._refusal_reason(_gap(source_sha256="not-a-sha"), _entry(), _historic()) == (
        "current target source SHA-256 is malformed"
    )


def test_f0014_proposal_keeps_current_printed_identity(monkeypatch) -> None:
    gap = _gap(
        label="Importe [02971]",
        export_field_id="m200-2024.dp200012.f0014",
        authored_token="2971",  # noqa: S106 - official casilla token
    )
    historic = {**_historic(), "id": "2971", "number": "2971", "export_refs": [gap.export_field_id]}
    entry = SimpleNamespace(
        export_field_id=gap.export_field_id,
        source_refs=(gap.source_ref,),
        legal_refs=("ley-27-2014:art-41",),
    )
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (gap,))
    monkeypatch.setattr(subject, "load_semantic_map", lambda _path: SimpleNamespace(entries=(entry,)))
    monkeypatch.setattr(subject, "_historic_index", lambda: {gap.export_field_id: (("historic.toml", historic),)})

    proposals, refusals = subject.build_bundled_restoration_proposals()

    assert not refusals
    assert proposals[0].id == "02971"
    assert proposals[0].number == "02971"
    assert "00355" not in proposals[0].target_description


def test_f0165_proposal_keeps_current_printed_identity(monkeypatch) -> None:
    gap = _gap(
        label="Importe [01683]",
        export_field_id="m200-2024.dp200018.f0165",
        authored_token="1683",  # noqa: S106 - official casilla token
    )
    historic = {**_historic(), "id": "1683", "number": "1683", "export_refs": [gap.export_field_id]}
    entry = SimpleNamespace(
        export_field_id=gap.export_field_id,
        source_refs=(gap.source_ref,),
        legal_refs=("ley-27-2014:art-41",),
    )
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (gap,))
    monkeypatch.setattr(subject, "load_semantic_map", lambda _path: SimpleNamespace(entries=(entry,)))
    monkeypatch.setattr(subject, "_historic_index", lambda: {gap.export_field_id: (("historic.toml", historic),)})

    proposals, refusals = subject.build_bundled_restoration_proposals()

    assert not refusals
    assert proposals[0].id == "01683"
    assert proposals[0].export_field_id == gap.export_field_id
