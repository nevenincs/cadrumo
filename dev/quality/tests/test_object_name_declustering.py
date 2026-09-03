"""Detector teeth for the safe object-name declustering command boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest

from ...audit.object_names import scan
from .. import object_name_declustering as cli
from .. import object_name_graph as graph_module
from .. import object_name_rehearsal as rehearsal_module
from ..object_name_rehearsal import ObjectNameRehearsalReceipt
from ..object_name_replay import ObjectNameReplayResult
from .test_object_name_rehearsal import _TEST_MANDATORY_GATES, _fixture, _live_bytes
from .test_object_name_replay import _case, _generated_case

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(autouse=True)
def _bind_disposable_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "cadrumo", raising=False)
    monkeypatch.delitem(sys.modules, "dev", raising=False)
    monkeypatch.setattr(graph_module, "_FIRST_PARTY_ROOTS", ("example",))
    monkeypatch.setattr(rehearsal_module, "MANDATORY_OBJECT_NAME_GATES", _TEST_MANDATORY_GATES)


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "dev").mkdir()
    return root


def _context_case(tmp_path: Path) -> tuple[Path, Any, Any, Any]:
    root = tmp_path / "repo"
    inventory, manifest, component = _fixture(root)
    return root, inventory, manifest, component


def _write_manifest(path: Path, manifest: Any) -> None:
    def quoted(value: str) -> str:
        return json.dumps(value)

    def strings(values: Any) -> str:
        return "[" + ", ".join(quoted(value) for value in values) + "]"

    rows = [f"schema_version = {manifest.schema_version}", f"inventory_digest = {quoted(manifest.inventory_digest)}"]
    for operation in manifest.operations:
        rows.extend(
            (
                "",
                "[[operations]]",
                f"operation_id = {quoted(operation.operation_id)}",
                f"finding_id = {quoted(operation.finding_id)}",
                f"operation_kind = {quoted(operation.operation_kind)}",
                f"disposition = {quoted(operation.disposition)}",
                f"lifecycle = {quoted(operation.lifecycle)}",
                f"old_locator = {quoted(operation.old_locator)}",
                f"old_path = {quoted(operation.old_path)}",
                f"new_locator = {quoted(operation.new_locator)}",
                f"new_path = {quoted(operation.new_path)}",
                f"owner = {quoted(operation.owner)}",
                f"rationale = {quoted(operation.rationale)}",
                "preconditions = ["
                + ", ".join(
                    f"{{ path = {quoted(item.path)}, sha256 = {quoted(item.sha256)} }}"
                    for item in operation.preconditions
                )
                + "]",
                f"expected_reference_classes = {strings(operation.expected_reference_classes)}",
                "moves = ["
                + ", ".join(
                    f"{{ source = {quoted(item.source)}, target = {quoted(item.target)} }}" for item in operation.moves
                )
                + "]",
                f"changed_paths = {strings(operation.changed_paths)}",
                "generator_commands = ["
                + ", ".join(strings(command) for command in operation.generator_commands)
                + "]",
                "focused_gates = [" + ", ".join(strings(command) for command in operation.focused_gates) + "]",
            )
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_receipt(path: Path, receipt: ObjectNameRehearsalReceipt) -> None:
    path.write_text(json.dumps(asdict(receipt), sort_keys=True), encoding="utf-8")


def test_parser_defaults_to_rehearsal_and_lists_every_explicit_mode() -> None:
    parser = cli._parser()

    assert parser.parse_args([]).mode == "rehearse"
    assert [parser.parse_args([mode]).mode for mode in cli._MODES] == list(cli._MODES)

    with pytest.raises(SystemExit) as raised:
        parser.parse_args(["rename-now"])
    assert raised.value.code == 2


def test_default_mode_rehearses_and_cannot_replay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, inventory, manifest, component, receipt = _case(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setattr(cli, "_manifest_path", lambda *_args: root / "manifest.toml")
    monkeypatch.setattr(cli, "_context", lambda *_args: (inventory, manifest, component))
    monkeypatch.setattr(cli, "scan", lambda *_args: inventory)
    monkeypatch.setattr(cli, "load_validated_object_name_manifest", lambda *_args, **_kwargs: manifest)
    monkeypatch.setattr(cli, "rehearse_object_name_component", lambda *_args, **_kwargs: receipt)
    monkeypatch.setattr(
        cli,
        "replay_object_name_component",
        lambda *_args, **_kwargs: pytest.fail("default command reached live replay"),
    )

    assert cli.main([]) == 0


@pytest.mark.parametrize("mode", ["inventory", "plan", "verify", "rehearse"])
@pytest.mark.parametrize("argument", ["--receipt=receipt.json", "--receipt-id=sha256:nope"])
def test_receipt_arguments_are_apply_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
    argument: str,
) -> None:
    monkeypatch.chdir(_repository(tmp_path))

    assert cli.main([mode, argument]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "receipt arguments are valid only in apply mode" in captured.err


@pytest.mark.parametrize(
    "arguments",
    [[], ["--receipt=receipt.json"], ["--receipt-id=sha256:nope"]],
)
def test_apply_requires_both_receipt_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
) -> None:
    monkeypatch.chdir(_repository(tmp_path))

    assert cli.main(["apply", *arguments]) == 2
    assert capsys.readouterr().out == ""


def test_apply_refuses_invalid_receipt_before_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repository(tmp_path)
    receipt = root / "receipt.json"
    receipt.write_text('{"receipt_id":"sha256:invented"}', encoding="utf-8")
    monkeypatch.chdir(root)
    monkeypatch.setattr(cli, "_context", lambda *_args: pytest.fail("context built before receipt refusal"))

    assert cli.main(["apply", f"--receipt={receipt}", "--receipt-id=sha256:invented"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "receipt" in captured.err


def test_apply_refuses_explicit_identity_mismatch_before_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _inventory, _manifest, _component, receipt = _case(tmp_path)
    receipt_path = root / "receipt.json"
    _write_receipt(receipt_path, receipt)
    monkeypatch.chdir(root)
    monkeypatch.setattr(cli, "_context", lambda *_args: pytest.fail("context built before identity refusal"))

    assert cli.main(["apply", f"--receipt={receipt_path}", "--receipt-id=sha256:wrong"]) == 2


@pytest.mark.parametrize(
    "payload",
    [b"not-json", b"[]", b"{}", b'{"unexpected":true}', b"\xff"],
    ids=("invalid-json", "non-object", "missing-fields", "extra-fields", "invalid-utf8"),
)
def test_receipt_loader_refuses_malformed_payloads(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "receipt.json"
    path.write_bytes(payload)

    with pytest.raises(cli.ObjectNameDeclusteringCliError):
        cli._receipt(path)


def test_receipt_loader_refuses_failed_or_retagged_evidence(tmp_path: Path) -> None:
    _root, _inventory, _manifest, _component, receipt = _case(tmp_path)
    path = tmp_path / "receipt.json"
    payload = asdict(receipt)
    payload["source_tree_unchanged"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(cli.ObjectNameDeclusteringCliError, match="receipt file is invalid"):
        cli._receipt(path)


def test_receipt_loader_refuses_linked_file(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "receipt.json"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"file links unavailable: {exc}")

    with pytest.raises(cli.ObjectNameDeclusteringCliError, match="regular file"):
        cli._receipt(link)


@pytest.mark.parametrize("supplied", [Path("../manifest.toml"), Path(".git/manifest.toml")])
def test_manifest_path_refuses_lexical_escape_and_metadata(tmp_path: Path, supplied: Path) -> None:
    root = _repository(tmp_path)

    with pytest.raises(cli.ObjectNameDeclusteringCliError, match="repository-relative"):
        cli._manifest_path(root, supplied)


def test_manifest_path_refuses_absolute_missing_and_linked_paths(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    external = tmp_path / "manifest.toml"
    external.write_text("schema_version = 1\n", encoding="utf-8")
    with pytest.raises(cli.ObjectNameDeclusteringCliError, match="repository-relative"):
        cli._manifest_path(root, external)
    with pytest.raises(cli.ObjectNameDeclusteringCliError, match="regular file"):
        cli._manifest_path(root, Path("missing.toml"))
    target = root / "real"
    target.mkdir()
    try:
        (root / "linked").symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory links unavailable: {exc}")
    with pytest.raises(cli.ObjectNameDeclusteringCliError, match="link-like"):
        cli._manifest_path(root, Path("linked/manifest.toml"))


def test_inventory_and_verify_are_manifest_independent_and_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repository(tmp_path)
    source = root / "src/example.py"
    source.write_bytes(b"class Widgets:\n    pass\n")
    before = _live_bytes(root)
    monkeypatch.chdir(root)
    monkeypatch.setattr(cli, "_context", lambda *_args: pytest.fail("read-only mode loaded a manifest"))
    monkeypatch.setattr(cli, "rehearse_object_name_component", lambda *_args, **_kwargs: pytest.fail("rehearsed"))
    monkeypatch.setattr(cli, "replay_object_name_component", lambda *_args, **_kwargs: pytest.fail("replayed"))

    assert cli.main(["inventory", "--manifest=missing.toml", "--json"]) == 0
    inventory_output = json.loads(capsys.readouterr().out)
    assert inventory_output["summary"]["enforced_findings"] == 1
    assert cli.main(["verify", "--manifest=missing.toml", "--json"]) == 1
    verify_output = json.loads(capsys.readouterr().out)
    assert verify_output["mode"] == "verify"
    assert verify_output["inventory"]["summary"]["enforced_findings"] == 1
    assert _live_bytes(root) == before


def test_plan_uses_real_manifest_context_without_writing_live_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _inventory, manifest, _component = _context_case(tmp_path)
    manifest_path = root / "dev/quality/object_name_rename_manifest.toml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _write_manifest(manifest_path, manifest)
    before = _live_bytes(root)
    monkeypatch.chdir(root)
    monkeypatch.setattr(cli, "rehearse_object_name_component", lambda *_args, **_kwargs: pytest.fail("rehearsed"))
    monkeypatch.setattr(cli, "replay_object_name_component", lambda *_args, **_kwargs: pytest.fail("replayed"))

    assert cli.main(["plan", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "plan"
    assert _live_bytes(root) == before


def test_generator_backed_plan_and_rehearsal_use_canonical_cli_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, inventory, manifest, _component, _receipt = _generated_case(tmp_path)
    operation = manifest.operations[0].model_copy(
        update={
            "changed_paths": tuple(sorted(manifest.operations[0].changed_paths)),
            "preconditions": tuple(sorted(manifest.operations[0].preconditions, key=lambda item: item.path)),
        }
    )
    manifest = manifest.model_copy(update={"operations": (operation,)})
    component = cli.canonical_object_name_component_set(manifest, inventory=inventory, repo_root=root)[0]
    manifest_path = root / "manifest.toml"
    _write_manifest(manifest_path, manifest)
    before = _live_bytes(root)
    monkeypatch.chdir(root)

    assert cli.main(["plan", "--manifest=manifest.toml", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "component": json.loads(json.dumps(asdict(component))),
        "mode": "plan",
    }

    real_rehearse = cli.rehearse_object_name_component
    captured_receipts: list[ObjectNameRehearsalReceipt] = []

    def capture_rehearsal(*args: Any, **kwargs: Any) -> ObjectNameRehearsalReceipt:
        result = real_rehearse(*args, **kwargs)
        captured_receipts.append(result)
        return result

    monkeypatch.setattr(cli, "rehearse_object_name_component", capture_rehearsal)
    assert cli.main(["rehearse", "--manifest=manifest.toml", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "mode": "rehearse",
        "receipt": json.loads(json.dumps(asdict(captured_receipts[0]))),
    }
    assert payload["receipt"]["generator_outcomes"][0]["argv"] == list(manifest.operations[0].generator_commands[0])
    assert _live_bytes(root) == before


def test_context_refuses_manifest_with_two_independent_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, inventory, manifest, _component = _context_case(tmp_path)
    second_path = root / "src/example/reports.py"
    second_path.write_bytes(b"class Reports:\n    pass\n")
    inventory = scan((root / "src", root / "dev"), root)
    declaration = next(item for item in inventory.declarations if item.name == "Reports")
    finding = next(item for item in inventory.findings if item.name == "Reports")
    second = manifest.operations[0].model_copy(
        update={
            "operation_id": "rename-reports",
            "finding_id": finding.id,
            "old_locator": declaration.qualified_locator,
            "old_path": declaration.path,
            "new_locator": replace(declaration, name="Report").qualified_locator,
            "new_path": declaration.path,
            "preconditions": (
                manifest.operations[0]
                .preconditions[0]
                .model_copy(update={"path": declaration.path, "sha256": declaration.source_hash}),
            ),
            "changed_paths": (declaration.path,),
        }
    )
    manifest = manifest.model_copy(
        update={
            "inventory_digest": cli.to_json(inventory)["inventory_digest"],
            "operations": tuple(sorted((manifest.operations[0], second), key=lambda item: item.operation_id)),
        }
    )
    manifest_path = root / "manifest.toml"
    _write_manifest(manifest_path, manifest)
    monkeypatch.chdir(root)

    assert cli.main(["plan", "--manifest=manifest.toml", "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "manifest must select exactly one complete component; found 2" in captured.err


def test_plan_refuses_malformed_manifest_without_rehearsal_or_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repository(tmp_path)
    manifest = root / "dev/quality/object_name_rename_manifest.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("not valid toml = [", encoding="utf-8")
    monkeypatch.chdir(root)
    monkeypatch.setattr(cli, "rehearse_object_name_component", lambda *_args, **_kwargs: pytest.fail("rehearsed"))
    monkeypatch.setattr(cli, "replay_object_name_component", lambda *_args, **_kwargs: pytest.fail("replayed"))

    assert cli.main(["plan", "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "object-name declustering refused" in captured.err


def test_mode_dispatches_only_to_its_owned_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, inventory, manifest, component, receipt = _case(tmp_path)
    receipt_path = root / "receipt.json"
    _write_receipt(receipt_path, receipt)
    monkeypatch.chdir(root)
    monkeypatch.setattr(cli, "_manifest_path", lambda *_args: root / "manifest.toml")
    monkeypatch.setattr(cli, "_context", lambda *_args: (inventory, manifest, component))
    monkeypatch.setattr(cli, "scan", lambda *_args: inventory)
    monkeypatch.setattr(cli, "load_validated_object_name_manifest", lambda *_args, **_kwargs: manifest)
    calls: list[str] = []

    def rehearse(*_args: Any, **_kwargs: Any) -> ObjectNameRehearsalReceipt:
        assert _kwargs["component"] is None
        calls.append("rehearse")
        return receipt

    def replay(*_args: Any, **_kwargs: Any) -> ObjectNameReplayResult:
        calls.append("apply")
        return ObjectNameReplayResult(receipt.receipt_id, receipt.changed_paths, "sha256:post", (), ())

    monkeypatch.setattr(cli, "rehearse_object_name_component", rehearse)
    monkeypatch.setattr(cli, "replay_object_name_component", replay)

    assert cli.main(["rehearse", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "rehearse"
    assert calls == ["rehearse"]
    calls.clear()
    assert cli.main(["apply", f"--receipt={receipt_path}", f"--receipt-id={receipt.receipt_id}", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "apply"
    assert calls == ["apply"]


def test_apply_uses_real_replay_and_emits_exact_result_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _inventory, manifest, _component, receipt = _case(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setattr(cli, "_manifest_path", lambda *_args: root / "manifest.toml")
    monkeypatch.setattr(cli, "_receipt", lambda *_args: receipt)
    monkeypatch.setattr(cli, "_context", lambda *_args: (_inventory, manifest, _component))

    assert (
        cli.main(
            [
                "apply",
                "--manifest=manifest.toml",
                "--receipt=receipt.json",
                f"--receipt-id={receipt.receipt_id}",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    expected = ObjectNameReplayResult(
        receipt_id=receipt.receipt_id,
        changed_paths=receipt.changed_paths,
        post_tree_digest=payload["result"]["post_tree_digest"],
        generator_outcomes=receipt.generator_outcomes,
        gate_outcomes=receipt.gate_outcomes,
    )
    assert payload == {"mode": "apply", "result": json.loads(json.dumps(asdict(expected)))}
    assert (root / "src/example/contracts.py").read_bytes() == b"class Widget:\n    pass\n"


def test_json_and_human_output_keep_stdout_clean_and_deterministic(
    capfd: pytest.CaptureFixture[str],
) -> None:
    payload = {"z": [2, 1], "a": "value"}

    cli._emit(payload, as_json=True)
    first = capfd.readouterr()
    cli._emit(payload, as_json=True)
    second = capfd.readouterr()
    assert first.out == second.out == '{"a":"value","z":[2,1]}\n'
    assert first.err == second.err == ""

    cli._emit(payload, as_json=False)
    human = capfd.readouterr()
    assert human.out == "z: [2, 1]\na: value\n"
    assert human.err == ""


def test_expected_refusal_is_stderr_only_and_exit_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(_repository(tmp_path))
    monkeypatch.setattr(cli, "scan", lambda *_args: (_ for _ in ()).throw(OSError("refused read")))

    assert cli.main(["inventory", "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "object-name declustering refused: refused read" in captured.err


def test_unexpected_programming_defect_propagates_with_subprocess_traceback(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    project = Path(__file__).parents[3]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(project / "src"), str(project)))
    script = (
        "from dev.quality import object_name_declustering as cli; "
        "cli.scan=lambda *_args: (_ for _ in ()).throw(RuntimeError('programming defect')); "
        "raise SystemExit(cli.main(['inventory']))"
    )

    result = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned program.
        [sys.executable, "-c", script],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Traceback" in result.stderr
    assert "RuntimeError: programming defect" in result.stderr


def test_raw_link_like_repository_root_is_refused(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    link = tmp_path / "linked-repo"
    try:
        link.symlink_to(root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory links unavailable: {exc}")

    with pytest.raises(cli.ObjectNameDeclusteringCliError, match="link-like"):
        cli._repo_root(link)


def test_rehearsal_changes_only_disposable_temporary_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, inventory, manifest, component = _context_case(tmp_path)
    manifest_path = root / "dev/quality/object_name_rename_manifest.toml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _write_manifest(manifest_path, manifest)
    before = _live_bytes(root)
    monkeypatch.chdir(root)
    monkeypatch.setattr(cli, "_context", lambda *_args: (inventory, manifest, component))
    monkeypatch.setattr(
        cli,
        "replay_object_name_component",
        lambda *_args, **_kwargs: pytest.fail("rehearsal reached live replay"),
    )

    assert cli.main(["rehearse", "--json"]) == 0
    assert _live_bytes(root) == before


def test_inventory_success_with_advisory_or_enforced_findings_is_informational(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / "src/widgets.py").write_bytes(b"class Widgets:\n    pass\n")
    result = scan((root / "src", root / "dev"), root)

    assert result.enforced_findings


def test_verify_returns_zero_for_clean_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repository(tmp_path)
    (root / "src/example.py").write_bytes(b"class Widget:\n    pass\n")
    monkeypatch.chdir(root)

    assert cli.main(["verify", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "verify"
    assert payload["inventory"]["summary"]["enforced_findings"] == 0
