"""Exercise refusal and syntax preservation before touching repository callers."""

import ast
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("remediate", Path(__file__).with_name("remediate.py"))
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def diagnostic(line=2, column=9, method="run"):
    return {
        "description": f"missing-override-decorator: Method `{method}` overrides `Base.{method}` "
        "but is not decorated with `@override`",
        "location": {"positions": {"begin": {"line": line, "column": column}}},
    }


def test_preserves_crlf_comments_and_future_import():
    source = b'"""Keep me."""\r\nfrom __future__ import annotations\r\n\r\nclass Child(Base):\r\n    # Keep this too.\r\n    def run(self):\r\n        pass\r\n'
    after, count = MODULE.transform_overrides(source, [diagnostic(6)])
    assert count == 1
    assert b"# Keep this too.\r\n    @override\r\n" in after
    assert b"\n" not in after.replace(b"\r\n", b"")
    tree = ast.parse(after)
    assert tree.body[1].module == "__future__"


def test_override_is_inside_classmethod_decorator():
    source = b"class Child(Base):\n    @classmethod\n    def run(cls):\n        pass\n"
    after, _ = MODULE.transform_overrides(source, [diagnostic(3)])
    assert b"@classmethod\n    @override\n    def run" in after


def test_shadowed_override_uses_fresh_alias():
    source = b"override = False\nclass Child(Base):\n    def run(self):\n        pass\n"
    after, _ = MODULE.transform_overrides(source, [diagnostic(3)])
    assert b"from typing import override as typing_override" in after
    assert b"@typing_override" in after


def test_existing_import_is_not_duplicated():
    source = b"from typing import override\nclass Child(Base):\n    def run(self):\n        pass\n"
    after, _ = MODULE.transform_overrides(source, [diagnostic(3)])
    assert after.count(b"from typing import override") == 1


def test_stale_location_is_refused():
    with pytest.raises(ValueError, match="unmatched"):
        MODULE.transform_overrides(b"class Child(Base):\n    def run(self):\n        pass\n", [diagnostic(3)])


def test_nested_function_is_refused():
    source = b"def outer():\n    def run():\n        pass\n"
    with pytest.raises(ValueError, match="direct class method"):
        MODULE.transform_overrides(source, [diagnostic()])


def test_apply_refuses_entire_stale_batch_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    directory = tmp_path / "src"
    directory.mkdir()
    before = b"value = 1\n"
    after = b"value = 2\n"
    edits = []
    for name in ("one.py", "two.py"):
        (directory / name).write_bytes(before)
        edits.append(
            {
                "path": f"src/{name}",
                "before_sha256": MODULE.digest(before),
                "after_sha256": MODULE.digest(after),
                "after_hex": after.hex(),
            }
        )
    plan = tmp_path / "preview.json"
    patch = b"reviewed patch\n"
    plan.with_suffix(".patch").write_bytes(patch)
    raw = MODULE.json_bytes(
        {"schema": 1, "transform": "override", "edits": edits, "patch_sha256": MODULE.digest(patch)}
    )
    plan.write_bytes(raw)
    (directory / "two.py").write_bytes(b"concurrent = True\n")
    with pytest.raises(ValueError, match="no edits applied"):
        MODULE.apply(plan, MODULE.digest(raw))
    assert (directory / "one.py").read_bytes() == before
    (directory / "two.py").write_bytes(before)
    MODULE.apply(plan, MODULE.digest(raw))
    MODULE.apply(plan, MODULE.digest(raw))
    assert all((directory / name).read_bytes() == after for name in ("one.py", "two.py"))


def test_apply_refuses_unreviewed_plan(tmp_path):
    plan = tmp_path / "preview.json"
    plan.write_text(json.dumps({"schema": 1}))
    with pytest.raises(ValueError, match="reviewed dry run"):
        MODULE.apply(plan, "0" * 64)


def confirmation_sources():
    fields = MODULE.CONFIRMATION_FIELDS
    callee = (
        "def confirm_invoice_draft_from_evidence(*, "
        + ", ".join(f"{key}: {value}" for key, value in fields.items())
        + "):\n    pass\n"
    )
    returned = "{" + ", ".join(f"{key!r}: {key}" for key in fields) + "}"
    helper = "from __future__ import annotations\nfrom typing import Mapping\n\n"
    for name in sorted(MODULE.CONFIRMATION_HELPERS):
        helper += f"def {name}(*, bucket_id: str) -> Mapping[str, object]:\n    return {returned}\n\n"
    return helper.encode(), callee.encode()


def test_confirmation_preserves_bodies_and_emits_exact_required_keys():
    before, callee = confirmation_sources()
    after = MODULE.transform_confirmation_kwargs(before, callee)
    tree = ast.parse(after)
    declaration = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    fields = {n.target.id: ast.unparse(n.annotation) for n in declaration.body if isinstance(n, ast.AnnAssign)}
    assert fields == MODULE.CONFIRMATION_FIELDS
    assert b"Mapping[str, object]" not in after


def test_confirmation_refuses_changed_callee():
    before, callee = confirmation_sources()
    with pytest.raises(ValueError, match="parameter types changed"):
        MODULE.transform_confirmation_kwargs(before, callee.replace(b"CatalogueCreationPorts", b"object"))


def test_confirmation_refuses_unknown_dictionary_keys():
    before, callee = confirmation_sources()
    with pytest.raises(ValueError, match="unexpected helper keys"):
        MODULE.transform_confirmation_kwargs(before.replace(b"'evidence_ports':", b"'unreviewed':"), callee)


def test_work_lifecycle_bundles_existing_values_and_preserves_alias():
    before = b"from cadrumo.application.modelo.work_lifecycle import create_work_unit as create\ncreate(bucket_id=bucket, repository=work, bucket_event_repository=events, clock=now)\n"
    after, count, refusals = MODULE.transform_work_lifecycle(before)
    assert count == 1 and not refusals
    call = ast.parse(after).body[-1].value
    assert call.func.id == "create"
    assert [kw.arg for kw in call.keywords] == ["bucket_id", "ports", "clock"]
    assert [kw.value.id for kw in call.keywords[1].value.keywords] == ["work", "events"]


@pytest.mark.parametrize(
    "arguments",
    [
        "repository=work",
        "repository=build_work(), bucket_event_repository=events",
        "repository=work, clock=now, bucket_event_repository=events",
        "repository=work, bucket_event_repository=events, **extras",
    ],
)
def test_work_lifecycle_refuses_missing_or_reordered_evaluation(arguments):
    before = (
        "from cadrumo.application.modelo.work_lifecycle import create_work_unit\n" + f"create_work_unit({arguments})\n"
    ).encode()
    after, count, refusals = MODULE.transform_work_lifecycle(before)
    assert after == before and count == 0 and len(refusals) == 1


def test_work_lifecycle_ignores_unrelated_same_named_callable():
    before = b"from different.module import create_work_unit\ncreate_work_unit(repository=work, bucket_event_repository=events)\n"
    after, count, _ = MODULE.transform_work_lifecycle(before)
    assert after == before and count == 0


def test_work_lifecycle_ignores_shadowed_import():
    before = b"from cadrumo.application.modelo.work_lifecycle import create_work_unit\ndef example(create_work_unit):\n    create_work_unit(repository=work, bucket_event_repository=events)\n"
    after, count, _ = MODULE.transform_work_lifecycle(before)
    assert after == before and count == 0
