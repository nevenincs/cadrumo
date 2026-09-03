from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import rtoml

from ..analysis import m200_2024_restoration_candidates as subject
from ..analysis.m200_semantic_casilla_candidates import M200CasillaDisposition
from ..pipeline._semantic_map import SemanticMap
from ..pipeline._semantic_map_loader import load_semantic_map as load_real_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REAL_MAP_PATH = Path(__file__).parents[1] / "mappings" / "modelo_200" / "2024"


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


@pytest.fixture(scope="module")
def real_semantic_map() -> SemanticMap:
    return load_real_semantic_map(_REAL_MAP_PATH)


@pytest.fixture(scope="module")
def real_target_fields(real_semantic_map: SemanticMap):
    return subject._load_target_field_index(real_semantic_map)


def _real_gap(
    real_semantic_map: SemanticMap,
    real_target_fields,
    *,
    export_field_id: str = "m200-2024.dp200012.f0013",
    source_ref: str | None = None,
    source_sha256: str | None = None,
) -> SimpleNamespace:
    target = real_target_fields[export_field_id]
    printed = subject._printed_number(target.normalized_description)
    assert printed is not None
    return SimpleNamespace(
        disposition=M200CasillaDisposition.REVISION_MISSING_DECLARATION,
        export_field_id=export_field_id,
        authored_token=printed,
        label=target.normalized_description,
        source_ref=source_ref or str(real_semantic_map.source_ref),
        source_sha256=source_sha256 or real_semantic_map.source_sha256,
        aeat_type=target.aeat_type,
        length=target.length,
    )


def _real_historic(real_semantic_map: SemanticMap, real_target_fields, *, export_field_id: str) -> dict[str, object]:
    entry = next(item for item in real_semantic_map.entries if str(item.export_field_id) == export_field_id)
    printed = subject._printed_number(real_target_fields[export_field_id].normalized_description)
    assert printed is not None
    return {
        **_historic(),
        "id": printed.lstrip("0"),
        "number": printed.lstrip("0"),
        "legal_refs": list(entry.legal_refs),
        "source_refs": list(entry.source_refs),
        "export_refs": [export_field_id],
    }


def test_build_returns_target_first_proposal_without_authority_writer(
    monkeypatch,
    real_semantic_map: SemanticMap,
    real_target_fields,
) -> None:
    export_field_id = "m200-2024.dp200012.f0013"
    gap = _real_gap(real_semantic_map, real_target_fields, export_field_id=export_field_id)
    historic = _real_historic(real_semantic_map, real_target_fields, export_field_id=export_field_id)
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (gap,))
    monkeypatch.setattr(subject, "load_semantic_map", lambda _path: real_semantic_map)
    monkeypatch.setattr(
        subject,
        "_historic_index",
        lambda: {export_field_id: (("z2024only-dp200012.toml", historic),)},
    )

    proposals, refusals = subject.build_bundled_restoration_proposals()

    assert not refusals
    assert proposals[0].id == "00093"
    assert proposals[0].export_field_id == export_field_id
    assert proposals[0].target_description == real_target_fields[export_field_id].normalized_description
    assert proposals[0].semantic_role == "is_correcciones_aumentos"
    assert not hasattr(subject, "render_apply_patch")
    assert not hasattr(subject, "_render_registry_fragment")


def test_legacy_candidate_aliases_are_not_exported() -> None:
    assert "RestorationCandidate" not in subject.__all__
    assert "build_bundled_restoration_candidates" not in subject.__all__
    assert not hasattr(subject, "RestorationCandidate")
    assert not hasattr(subject, "build_bundled_restoration_candidates")


def test_build_refuses_ambiguous_historic_export_identity(
    monkeypatch,
    real_semantic_map: SemanticMap,
    real_target_fields,
) -> None:
    export_field_id = "m200-2024.dp200012.f0013"
    gap = _real_gap(real_semantic_map, real_target_fields, export_field_id=export_field_id)
    historic = _real_historic(real_semantic_map, real_target_fields, export_field_id=export_field_id)
    match = ("z2024only-dp200012.toml", historic)
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (gap,))
    monkeypatch.setattr(subject, "load_semantic_map", lambda _path: real_semantic_map)
    monkeypatch.setattr(subject, "_historic_index", lambda: {export_field_id: (match, match)})

    proposals, refusals = subject.build_bundled_restoration_proposals()

    assert not proposals
    assert refusals[0].reason == "historic export match count is 2"


def test_build_refuses_coordinated_map_and_gap_source_drift(
    monkeypatch,
    real_semantic_map: SemanticMap,
    real_target_fields,
) -> None:
    export_field_id = "m200-2024.dp200012.f0013"
    drifted_sha256 = "b" * 64
    drifted_map = real_semantic_map.model_copy(update={"source_sha256": drifted_sha256})
    gap = _real_gap(
        real_semantic_map,
        real_target_fields,
        export_field_id=export_field_id,
        source_sha256=drifted_sha256,
    )
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (gap,))
    monkeypatch.setattr(subject, "load_semantic_map", lambda _path: drifted_map)
    monkeypatch.setattr(
        subject,
        "_historic_index",
        lambda: pytest.fail("source drift must be refused before historic evidence is loaded"),
    )

    with pytest.raises(ValueError, match="source identity does not exactly match"):
        subject.build_bundled_restoration_proposals()


@pytest.mark.parametrize("identity_field", ("source_ref", "source_sha256"))
def test_target_design_source_identity_requires_exact_map_match(
    monkeypatch,
    real_semantic_map: SemanticMap,
    identity_field: str,
) -> None:
    parsed_source = SimpleNamespace(
        source_ref=real_semantic_map.source_ref,
        source_sha256=real_semantic_map.source_sha256,
    )
    if identity_field == "source_ref":
        parsed_source.source_ref = "aeat-dr-200-2024-other"
    else:
        parsed_source.source_sha256 = "b" * 64
    parsed_design = SimpleNamespace(source=parsed_source, sheets=())
    monkeypatch.setattr(subject, "load_catalogue_file", lambda _path: SimpleNamespace(sources={}))
    monkeypatch.setattr(subject, "load_record_design_intermediate", lambda *_args, **_kwargs: parsed_design)

    with pytest.raises(ValueError, match="source identity does not exactly match"):
        subject._load_target_field_index(real_semantic_map)


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


def test_cli_rejects_output_inside_canonical_registry_root(monkeypatch, tmp_path: Path) -> None:
    canonical_root = tmp_path / "src" / "cadrumo" / "_data" / "registry" / "aeat"
    canonical_root.mkdir(parents=True)
    monkeypatch.setattr(subject, "_CANONICAL_REGISTRY_ROOT", canonical_root)
    monkeypatch.setattr(
        subject,
        "build_bundled_restoration_proposals",
        lambda: pytest.fail("authority-root output must be rejected before loading evidence"),
    )

    for output in (
        canonical_root / "review.toml",
        canonical_root / "nested" / ".." / "review.toml",
    ):
        with pytest.raises(SystemExit) as error:
            subject.main(["--output", str(output)])
        assert error.value.code == 2


def test_cli_rejects_output_symlink_containment(monkeypatch, tmp_path: Path) -> None:
    canonical_root = tmp_path / "authority"
    canonical_root.mkdir()
    monkeypatch.setattr(subject, "_CANONICAL_REGISTRY_ROOT", canonical_root)
    monkeypatch.setattr(
        subject,
        "build_bundled_restoration_proposals",
        lambda: pytest.fail("authority-root output must be rejected before loading evidence"),
    )

    try:
        authority_alias = tmp_path / "authority-alias"
        authority_alias.symlink_to(canonical_root, target_is_directory=True)
        outside_link = tmp_path / "outside-link.toml"
        outside_link.symlink_to(canonical_root / "review.toml")
        authority_escape = canonical_root / "escape"
        authority_escape.symlink_to(tmp_path / "outside", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("the current platform does not permit test symlinks")

    for output in (
        authority_alias / "review.toml",
        outside_link,
        authority_escape / "review.toml",
    ):
        with pytest.raises(SystemExit) as error:
            subject.main(["--output", str(output)])
        assert error.value.code == 2


def test_cli_rejects_parent_swap_during_evidence_build(monkeypatch, tmp_path: Path) -> None:
    canonical_root = tmp_path / "authority"
    canonical_root.mkdir()
    canonical_output = canonical_root / "review.toml"
    canonical_output.write_text("authority sentinel\n", encoding="utf-8")
    output_parent = tmp_path / "review-output"
    output_parent.mkdir()
    output = output_parent / "review.toml"
    monkeypatch.setattr(subject, "_CANONICAL_REGISTRY_ROOT", canonical_root)

    def build_and_swap_parent():
        original_parent = tmp_path / "review-output-original"
        output_parent.rename(original_parent)
        output_parent.symlink_to(canonical_root, target_is_directory=True)
        return ((_proposal(),), ())

    monkeypatch.setattr(subject, "build_bundled_restoration_proposals", build_and_swap_parent)

    try:
        with pytest.raises(SystemExit) as error:
            subject.main(["--output", str(output)])
    except (OSError, NotImplementedError):
        pytest.skip("the current platform does not permit test symlinks")

    assert error.value.code == 2
    assert canonical_output.read_text(encoding="utf-8") == "authority sentinel\n"
    assert not (tmp_path / "review-output-original" / "review.toml").exists()


def test_cli_rejects_hardlink_alias_to_canonical_output(monkeypatch, tmp_path: Path) -> None:
    canonical_root = tmp_path / "authority"
    canonical_root.mkdir()
    canonical_output = canonical_root / "review.toml"
    canonical_output.write_text("authority sentinel\n", encoding="utf-8")
    outside_alias = tmp_path / "outside-review.toml"
    try:
        os.link(canonical_output, outside_alias)
    except (OSError, NotImplementedError):
        pytest.skip("the current platform does not permit test hardlinks")

    monkeypatch.setattr(subject, "_CANONICAL_REGISTRY_ROOT", canonical_root)
    monkeypatch.setattr(subject, "build_bundled_restoration_proposals", lambda: ((_proposal(),), ()))

    with pytest.raises(SystemExit) as error:
        subject.main(["--output", str(outside_alias)])

    assert error.value.code == 2
    assert canonical_output.read_text(encoding="utf-8") == "authority sentinel\n"


def test_cli_rejects_hardlink_added_after_initial_handle_check(monkeypatch, tmp_path: Path) -> None:
    canonical_root = tmp_path / "authority"
    canonical_root.mkdir()
    canonical_output = canonical_root / "review.toml"
    output = tmp_path / "outside-review.toml"
    output.write_text("outside sentinel\n", encoding="utf-8")
    try:
        os.link(output, canonical_output)
        canonical_output.unlink()
    except (OSError, NotImplementedError):
        pytest.skip("the current platform does not permit test hardlinks")

    monkeypatch.setattr(subject, "_CANONICAL_REGISTRY_ROOT", canonical_root)
    monkeypatch.setattr(subject, "build_bundled_restoration_proposals", lambda: ((_proposal(),), ()))
    real_assert = subject._assert_review_output_handle
    assertion_count = 0

    def assert_then_add_hardlink(path: Path, expected_path: Path, file_descriptor: int) -> None:
        nonlocal assertion_count
        assertion_count += 1
        real_assert(path, expected_path, file_descriptor)
        if assertion_count == 1:
            os.link(output, canonical_output)

    monkeypatch.setattr(subject, "_assert_review_output_handle", assert_then_add_hardlink)

    with pytest.raises(SystemExit) as error:
        subject.main(["--output", str(output)])

    assert error.value.code == 2
    assert assertion_count == 2
    assert output.read_text(encoding="utf-8") == "outside sentinel\n"
    assert canonical_output.read_text(encoding="utf-8") == "outside sentinel\n"


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


def test_f0014_proposal_keeps_current_printed_identity(
    monkeypatch,
    real_semantic_map: SemanticMap,
    real_target_fields,
) -> None:
    gap = _real_gap(real_semantic_map, real_target_fields, export_field_id="m200-2024.dp200012.f0014")
    historic = _real_historic(real_semantic_map, real_target_fields, export_field_id=gap.export_field_id)
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (gap,))
    monkeypatch.setattr(subject, "load_semantic_map", lambda _path: real_semantic_map)
    monkeypatch.setattr(subject, "_historic_index", lambda: {gap.export_field_id: (("historic.toml", historic),)})

    proposals, refusals = subject.build_bundled_restoration_proposals()

    assert not refusals
    assert proposals[0].id == "02971"
    assert proposals[0].number == "02971"
    assert "00355" not in proposals[0].target_description


def test_f0165_proposal_keeps_current_printed_identity(
    monkeypatch,
    real_semantic_map: SemanticMap,
    real_target_fields,
) -> None:
    gap = _real_gap(real_semantic_map, real_target_fields, export_field_id="m200-2024.dp200018.f0165")
    historic = _real_historic(real_semantic_map, real_target_fields, export_field_id=gap.export_field_id)
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (gap,))
    monkeypatch.setattr(subject, "load_semantic_map", lambda _path: real_semantic_map)
    monkeypatch.setattr(subject, "_historic_index", lambda: {gap.export_field_id: (("historic.toml", historic),)})

    proposals, refusals = subject.build_bundled_restoration_proposals()

    assert not refusals
    assert proposals[0].id == "01683"
    assert proposals[0].export_field_id == gap.export_field_id
