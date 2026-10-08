"""Real input hashes fence documentation completion across producer and copy races."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .. import docs_build
from ..action_cache import current, fingerprint
from ..docs_stage import DocsPackagingError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("change", ["none", "source", "authority", "selection", "reuse"])
def test_source_and_authority_changes_refuse_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    build = tmp_path / "build"
    build.mkdir()
    source, authority = tmp_path / "page.md", tmp_path / "authority.json"
    source.write_text("original page", encoding="utf-8")
    authority.write_text("original authority", encoding="utf-8")
    selected = [authority]
    configuration = build / "build-paths.json"
    configuration.write_text(
        json.dumps({"paths": {"user_docs_build": "docs", "user_docs_work": "work"}}), encoding="utf-8"
    )
    inputs = build / "inputs.txt"
    inputs.write_text(f"{source}\n{configuration}\n", encoding="utf-8")
    destination, shared = build / "docs", tmp_path / "cache" / "docs"
    monkeypatch.setattr(docs_build, "selected_published_authority", lambda _root: tuple(selected))
    monkeypatch.setattr(docs_build, "dev_cache_dir", lambda _name: shared)
    monkeypatch.setattr(docs_build, "_index_site", lambda _root, _languages: None)

    def produce(root: Path, _work: Path, _languages: tuple[str, ...]) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "index.html").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        if change == "source":
            source.write_text("edited during compilation", encoding="utf-8")
        elif change == "authority":
            authority.write_text("republished during compilation", encoding="utf-8")
        elif change == "selection":
            successor = tmp_path / "successor.json"
            successor.write_bytes(authority.read_bytes())
            selected[:] = [successor]

    monkeypatch.setattr(docs_build, "_compile_roots", produce)
    original_receipt = b""
    if change in {"none", "reuse"}:
        docs_build.build_roots(build, inputs, target="windows-x86-64")
        assert current(destination, fingerprint(inputs, (authority,)))
        assert (shared / "ready").is_file()
        if change == "none":
            return
        original_receipt = (shared / "ready").read_bytes()
        (destination / "ready").unlink()
        copy = docs_build._copy_site

        def changed_copy(origin: Path, target: Path) -> None:
            copy(origin, target)
            source.write_text("edited while copying the shared site", encoding="utf-8")

        monkeypatch.setattr(docs_build, "_copy_site", changed_copy)

    with pytest.raises(DocsPackagingError, match="inputs changed"):
        docs_build.build_roots(build, inputs, target="windows-x86-64")
    assert not (destination / "ready").exists()
    if change == "reuse":
        assert (shared / "ready").read_bytes() == original_receipt
    else:
        assert not (shared / "ready").exists()
