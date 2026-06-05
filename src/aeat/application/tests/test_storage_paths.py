"""Real-behaviour tests for the shared storage_path helper.

Each parametrize case mirrors a remaining local ``storage_path`` consumer.
The tests assert:

1. The returned path has the expected stem and extension.
2. The parent directory is created by the helper (mkdir side-effect).
3. The path is writable (sanity that no extra segment is missing).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._storage_paths import storage_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    "sub_path, bucket_id, extension, expected_stem, expected_suffix",
    [
        # ledger/_business_operation_invoice.py: aeat_invoices_dir / kind.value
        (
            ("invoices", "payable"),
            "inv-payable-001",
            ".jsonl",
            "inv-payable-001",
            ".jsonl",
        ),
        # ledger/_evidence.py: aeat_purchase_invoice_evidence_dir (flat root)
        (
            ("purchase-invoice-evidence",),
            "bucket-evidence-01",
            ".jsonl",
            "bucket-evidence-01",
            ".jsonl",
        ),
    ],
    ids=[
        "invoices-kind",
        "purchase-invoice-evidence",
    ],
)
def test_storage_path_layout(
    tmp_path: Path,
    sub_path: tuple[str, ...],
    bucket_id: str,
    extension: str,
    expected_stem: str,
    expected_suffix: str,
) -> None:
    root = tmp_path.joinpath(*sub_path)
    # root must NOT pre-exist so we confirm the helper creates it
    assert not root.exists()

    result = storage_path(root, bucket_id, extension=extension)

    assert result.stem == expected_stem
    assert result.suffix == expected_suffix
    assert result.parent == root
    # mkdir side-effect
    assert root.is_dir(), "storage_path must create the root directory"
    # path is writable
    result.write_text("probe", encoding="utf-8")
    assert result.read_text(encoding="utf-8") == "probe"


def test_storage_path_default_extension(tmp_path: Path) -> None:
    """Default extension is .jsonl without requiring an explicit kwarg."""
    root = tmp_path / "some-domain"
    result = storage_path(root, "bkt-001")
    assert result.suffix == ".jsonl"
    assert result.name == "bkt-001.jsonl"


def test_storage_path_idempotent_mkdir(tmp_path: Path) -> None:
    """Calling the helper twice does not raise even though the dir exists."""
    root = tmp_path / "repeat"
    storage_path(root, "first")
    storage_path(root, "second")  # must not raise FileExistsError
    assert root.is_dir()


def test_storage_path_nested_root_created(tmp_path: Path) -> None:
    """Deep multi-level roots are fully created (parents=True)."""
    root = tmp_path / "a" / "b" / "c"
    result = storage_path(root, "deep")
    assert root.is_dir()
    assert result == root / "deep.jsonl"
