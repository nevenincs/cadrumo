"""The R2 client signs exactly as the S3 protocol specifies and publishes the whole tree.

The signing oracle is independent of this implementation: the expected
signatures are the worked examples AWS publishes for Signature Version 4 on S3
("Authenticating Requests: Using the Authorization Header", examples "GET
Object" and "GET Bucket (List Objects)"), with their published example key.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import pytest

from ..r2_objects import R2Bucket, content_type_for, files_to_publish, signed_headers

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The signing material AWS publishes alongside the worked examples.
_PUBLISHED_EXAMPLE_KEY_MATERIAL = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
_EXAMPLE_KEY = R2Bucket(
    account_id="unused",
    name="examplebucket",
    access_key_id="AKIAIOSFODNN7EXAMPLE",
    secret_access_key=_PUBLISHED_EXAMPLE_KEY_MATERIAL,
)
_EXAMPLE_HOST = "examplebucket.s3.amazonaws.com"
_EXAMPLE_INSTANT = datetime(2013, 5, 24, tzinfo=UTC)
_EMPTY_PAYLOAD = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _signature(headers: dict[str, str]) -> str:
    return headers["authorization"].rsplit("Signature=", 1)[1]


def test_get_object_matches_the_published_example() -> None:
    headers = signed_headers(
        _EXAMPLE_KEY,
        host=_EXAMPLE_HOST,
        region="us-east-1",
        method="GET",
        path="/test.txt",
        query={},
        payload_hash=_EMPTY_PAYLOAD,
        extra_headers={"Range": "bytes=0-9"},
        now=_EXAMPLE_INSTANT,
    )
    assert "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date," in headers["authorization"]
    assert _signature(headers) == "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"


def test_list_objects_matches_the_published_example() -> None:
    """The query string is part of the signature, canonically sorted and encoded."""
    headers = signed_headers(
        _EXAMPLE_KEY,
        host=_EXAMPLE_HOST,
        region="us-east-1",
        method="GET",
        path="/",
        query={"prefix": "J", "max-keys": "2"},
        payload_hash=_EMPTY_PAYLOAD,
        extra_headers={},
        now=_EXAMPLE_INSTANT,
    )
    assert _signature(headers) == "34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7"


class _CommonSigningArgs(TypedDict):
    host: str
    method: str
    path: str
    query: dict[str, str]
    extra_headers: dict[str, str]
    now: datetime


def test_a_changed_body_changes_the_signature() -> None:
    """Teeth for the examples: the signature is bound to what is sent."""
    common: _CommonSigningArgs = {
        "host": _EXAMPLE_HOST,
        "method": "PUT",
        "path": "/a.html",
        "query": {},
        "extra_headers": {"content-type": "text/html; charset=utf-8"},
        "now": _EXAMPLE_INSTANT,
    }
    first = signed_headers(_EXAMPLE_KEY, payload_hash="0" * 64, **common)
    second = signed_headers(_EXAMPLE_KEY, payload_hash="1" * 64, **common)
    assert _signature(first) != _signature(second)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("index.html", "text/html; charset=utf-8"),
        ("pagefind.js", "text/javascript; charset=utf-8"),
        ("pagefind-ui.css", "text/css; charset=utf-8"),
        ("pagefind-entry.json", "application/json"),
        ("sitemap.xml", "application/xml"),
        ("wasm.en.pagefind", "application/octet-stream"),
        ("en_4f2a.pf_index", "application/octet-stream"),
    ],
)
def test_content_types_do_not_depend_on_the_host_registry(name: str, expected: str) -> None:
    assert content_type_for(Path(name)) == expected


def test_the_published_tree_is_every_file_except_the_excluded(tmp_path: Path) -> None:
    for relative in ("index.html", "es/index.html", "pagefind/pagefind.js", ".doctrees/env.pickle", "es/.doctrees/x"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")
    files = files_to_publish(tmp_path, excludes=(".doctrees/*", "*/.doctrees/*"))
    assert set(files) == {"index.html", "es/index.html", "pagefind/pagefind.js"}
