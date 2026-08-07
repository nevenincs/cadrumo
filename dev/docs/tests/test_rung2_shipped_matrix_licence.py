"""Licence gate for the shipped Rung-2 semantic matrix.

``shipped-search-licence-clean`` permits exactly one embedding artefact to reach
a reader: a bounded, provenance-stamped, reviewable plain-data matrix computed on
the dev box by a **pinned, named model under MIT or Apache-2.0** over
project-authored or project-bundled vocabulary. Everything else in that rule is a
prohibition; this is the single carve-out, so it is the one place a licence claim
has to be mechanically checked rather than asserted in prose.

Nothing else validates it. The compiler asserts its own internal invariants and
the browser reader re-validates the *bundle* it is handed at runtime, but neither
answers the question this gate exists for: **is the artefact we commit one the
licence rule actually permits?** A model swap, a revision bump, an
unbounded-growth regression, or a quantization change would each keep the
compiler green and the browser happy while breaking the rule's terms.

The bound and the pins are read from the shipped reader
(``docs/_static/cadrumo-docs.js``) rather than duplicated here. Restating them
would create a second authority that could drift from the one the browser
enforces, and a gate whose constant disagrees with production silently stops
testing production.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# Reads two committed artefacts and nothing else: no build, no browser, no model.
pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = REPO_ROOT / "dev" / "docs" / "terminology" / "evaluation" / "rung2-matrix.json"
READER_PATH = REPO_ROOT / "docs" / "_static" / "cadrumo-docs.js"

# The rule names these two licences and no others.
PERMITTED_SPDX_LICENCES = frozenset({"MIT", "Apache-2.0"})

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _reader_constant(name: str) -> str:
    """Return a ``var NAME = "value";`` literal from the shipped reader."""
    source = READER_PATH.read_text(encoding="utf-8")
    match = re.search(rf'^\s*var {re.escape(name)} = "([^"]*)";', source, re.M)
    if match is None:
        pytest.fail(f"{name} is not declared in {READER_PATH.name}; the pin moved or was removed")
    return match.group(1)


def _reader_number(name: str) -> int:
    source = READER_PATH.read_text(encoding="utf-8")
    match = re.search(rf"^\s*var {re.escape(name)} = (\d+);", source, re.M)
    if match is None:
        pytest.fail(f"{name} is not declared in {READER_PATH.name}; the pin moved or was removed")
    return int(match.group(1))


@pytest.fixture(scope="module")
def matrix() -> dict[str, object]:
    if not MATRIX_PATH.exists():
        pytest.fail(
            f"{MATRIX_PATH} is absent. The shipped matrix is a committed measurement input; "
            "if it was intentionally retired, retire this gate in the same change.",
        )
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _model(matrix: dict[str, object]) -> dict[str, object]:
    model = matrix.get("model")
    assert isinstance(model, dict), "matrix.model must be an object carrying the provenance stamp"
    return model


def test_matrix_declares_a_permitted_spdx_licence(matrix: dict[str, object]) -> None:
    """The licence is the whole basis of the carve-out, so it is checked first."""
    licence = _model(matrix).get("spdx_license")
    assert licence in PERMITTED_SPDX_LICENCES, (
        f"the shipped matrix declares spdx_license={licence!r}; "
        f"shipped-search-licence-clean permits only {sorted(PERMITTED_SPDX_LICENCES)}"
    )


def test_matrix_model_matches_the_pin_the_browser_enforces(matrix: dict[str, object]) -> None:
    """A model or revision swap must fail here, not surface as changed recall."""
    model = _model(matrix)
    assert model.get("repository") == _reader_constant("RUNG2_MODEL_REPOSITORY")
    assert model.get("revision") == _reader_constant("RUNG2_MODEL_REVISION")
    assert model.get("spdx_license") == _reader_constant("RUNG2_MODEL_LICENSE")


def test_matrix_provenance_stamp_is_complete(matrix: dict[str, object]) -> None:
    """The rule requires model, revision, licence, vocabulary fingerprint and size.

    A stamp missing any one of those is unreviewable, which is the condition the
    carve-out is granted against.
    """
    model = _model(matrix)
    for field in ("repository", "revision", "spdx_license", "model_snapshot_sha256"):
        assert model.get(field), f"matrix.model.{field} is required by the provenance stamp"

    for field in ("vocabulary_sha256", "query_token_sha256", "artifact_sha256"):
        value = matrix.get(field)
        assert isinstance(value, str) and _HEX64.match(value), (
            f"matrix.{field} must be a sha256 hex digest; the stamp is not reviewable without it"
        )

    assert isinstance(matrix.get("serialized_bytes"), int), (
        "matrix.serialized_bytes is required: the rule bounds the artefact by size"
    )


def test_matrix_stays_inside_the_declared_size_bound(matrix: dict[str, object]) -> None:
    """3 MB is the upper bound of the governing 1-3 MB envelope."""
    declared = matrix["serialized_bytes"]
    limit = _reader_number("RUNG2_MAX_PAYLOAD_BYTES")
    assert isinstance(declared, int) and 0 < declared <= limit, (
        f"the shipped matrix declares {declared} bytes against a {limit}-byte bound"
    )


def test_declared_size_matches_the_bytes_actually_committed(matrix: dict[str, object]) -> None:
    """A self-declared size nothing cross-checks is an honour-system bound.

    The declaration is what the browser enforces its bound against, so it has to
    agree with the artefact on disk or the bound measures a number rather than a
    payload.
    """
    on_disk = MATRIX_PATH.stat().st_size
    assert matrix["serialized_bytes"] == on_disk, (
        f"matrix declares serialized_bytes={matrix['serialized_bytes']} "
        f"but the committed file is {on_disk} bytes"
    )


def test_matrix_is_reviewable_plain_data(matrix: dict[str, object]) -> None:
    """"Reviewable plain data" is a term of the carve-out, not a description.

    Rows carry an explicit term, an int8 vector and a scalar, so a human can read
    what shipped. An opaque blob would satisfy every other assertion here.
    """
    assert matrix.get("quantization_algorithm") == _reader_constant("RUNG2_QUANTIZATION")
    assert matrix.get("row_order") == _reader_constant("RUNG2_ROW_ORDER")
    assert matrix.get("dimension") == _reader_number("RUNG2_DIMENSION")

    rows = matrix.get("rows")
    assert isinstance(rows, list) and rows, "matrix.rows must carry the reviewable vocabulary rows"
    assert len(rows) == matrix.get("vocabulary_count"), (
        "matrix.vocabulary_count must equal the rows actually shipped"
    )

    first = rows[0]
    assert isinstance(first, dict), "each row must be a readable object, not a packed blob"
    assert isinstance(first.get("term"), str) and first["term"], "each row must name its term"
    values = first.get("values")
    assert isinstance(values, list) and len(values) == matrix["dimension"]
    assert all(isinstance(v, int) and -128 <= v <= 127 for v in values), (
        "row values must be plain int8 integers; a float or packed encoding is not reviewable"
    )


def test_vocabulary_is_project_authored(matrix: dict[str, object]) -> None:
    """The carve-out covers project-authored or project-bundled vocabulary only.

    Terms are asserted to come from the committed terminology corpus rather than
    from the model's own vocabulary, which is what keeps this an embedding *of our
    words* rather than a redistribution of the upstream model.
    """
    rows = matrix["rows"]
    assert isinstance(rows, list)
    terms = [row["term"] for row in rows if isinstance(row, dict)]
    assert terms, "no terms shipped"
    assert len(set(terms)) == len(terms), "the shipped vocabulary contains duplicate terms"
    assert all(term == term.strip() and term.lower() == term for term in terms), (
        "terms must be normalised as the pinned algorithm emits them"
    )
