"""Language-neutral vectors for the ``cadrumo-jcs-utf8-lf-v1`` contract."""

from __future__ import annotations

import json
from collections.abc import Mapping
from importlib.resources import files
from typing import Final, cast

from dev.docs.terminology._jcs import CANONICAL_JSON_CONTRACT

_VECTOR_FILE: Final[str] = "vectors.json"


def load_vectors() -> tuple[Mapping[str, object], ...]:
    """Load and structurally validate the committed cross-runtime vectors."""

    loaded = json.loads(files(__package__).joinpath(_VECTOR_FILE).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("JCS vector corpus must be a JSON object")
    payload = cast(dict[str, object], loaded)
    if payload.get("contract") != CANONICAL_JSON_CONTRACT:
        raise ValueError("JCS vector corpus contract mismatch")
    loaded_vectors = payload.get("vectors")
    if not isinstance(loaded_vectors, list) or not loaded_vectors:
        raise ValueError("JCS vector corpus must contain vectors")
    vectors = cast(list[object], loaded_vectors)
    checked: list[Mapping[str, object]] = []
    for loaded_vector in vectors:
        if not isinstance(loaded_vector, dict):
            raise ValueError("JCS vector entries must be JSON objects")
        vector = cast(dict[str, object], loaded_vector)
        if not isinstance(vector.get("id"), str):
            raise ValueError("JCS vector entries require a string id")
        has_expected = isinstance(vector.get("expected_utf8_hex"), str)
        has_error = vector.get("error") == "rejected"
        if has_expected == has_error:
            raise ValueError(f"JCS vector {vector['id']!r} needs one expected outcome")
        checked.append(vector)
    return tuple(checked)


__all__ = ["load_vectors"]
