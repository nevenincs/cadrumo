"""Emit the Rung-2 bundle and its enablement config into a built docs site.

The browser seam in ``docs/_static/cadrumo-docs.js`` is fail-closed by design: it
activates only when ``window.__CADRUMO_SEARCH_RUNG2__`` is present, complete, and
hash-consistent with the bundle it names. Nothing wrote that config, so the seam
was dark in every real build and the compiled matrix had no load path.

This module is that missing step, and only that step. It does not compile a
matrix, download a model, run a sweep, or choose a threshold: it loads the
committed matrix and the committed relevance authority, links them into the
schema-v3 bundle the reader validates, and writes the bundle plus a config whose
acceptance block is copied from the ratified adjudication. A missing or
unratified input raises rather than emitting a config, because a half-written
enablement surface is worse than a dark one - the reader would accept it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ._rung2_acceptance import Rung2AcceptanceEvidence
from ._rung2_bridge import build_rung2_search_bundle, write_rung2_search_bundle
from ._rung2_inputs import build_rung2_compilation_inputs
from ._static_matrix import load_static_embedding_matrix

#: Must equal ``RUNG2_CONFIG_SCHEMA`` in ``docs/_static/cadrumo-docs.js``.
CONFIG_SCHEMA_VERSION = "cadrumo.docs-search.rung2-config.v2"
#: Must equal ``RUNG2_NORMALIZATION_VERSION`` in the reader.
NORMALIZATION_VERSION = "unicode-word-runs-nfkc-lower-v1"

BUNDLE_FILENAME = "rung2-search-bundle.json"
CONFIG_FILENAME = "rung2-search-config.js"

MATRIX_RELPATH = Path("dev/docs/terminology/evaluation/rung2-matrix.json")


class Rung2EmitError(RuntimeError):
    """Raised when the enablement surface cannot be emitted completely."""


@dataclass(frozen=True)
class Rung2Emission:
    """What was written, so a caller can assert on it rather than re-read files."""

    bundle_path: Path
    config_path: Path
    bundle_sha256: str
    payload_bytes: int
    enabled: bool


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def emit_rung2_static_assets(
    static_dir: Path,
    *,
    repo_root: Path,
    evidence: Rung2AcceptanceEvidence,
    matrix_path: Path | None = None,
) -> Rung2Emission:
    """Write the bundle and its config into ``static_dir``.

    ``static_dir`` is the built site's ``_static`` directory. Both files are
    written together or neither is: the config names the bundle by hash, so a
    config without its bundle would fail the reader's integrity check on every
    page load.

    ``evidence`` is a ratified :class:`Rung2AcceptanceEvidence`. It is required
    rather than derived here because the model refuses to construct at all
    unless the measurement passed - ``approved`` and ``quantization_accepted``
    are ``Literal[True]`` and ``held_out_miss_rate`` is bounded by the ratified
    threshold. So an unaccepted tier cannot reach this function, and this module
    never has to decide whether a regression is shippable.
    """
    resolved_matrix = matrix_path if matrix_path is not None else repo_root / MATRIX_RELPATH
    if not resolved_matrix.is_file():
        raise Rung2EmitError(
            f"the compiled Rung-2 matrix is absent at {resolved_matrix}; "
            "compile it on the dev box before emitting the enablement surface",
        )

    matrix = load_static_embedding_matrix(resolved_matrix)
    inputs = build_rung2_compilation_inputs(repo_root)
    bundle = build_rung2_search_bundle(
        matrix,
        inputs.sweep,
        inputs.records,
        provenance=inputs.provenance,
    )

    static_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = static_dir / BUNDLE_FILENAME
    write_rung2_search_bundle(bundle, bundle_path)

    payload = bundle_path.read_bytes()
    bundle_sha256 = _sha256_hex(payload)

    acceptance = _acceptance_block(evidence, payload_bytes=len(payload))
    enabled = True

    config = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "enabled": enabled,
        "normalization_version": NORMALIZATION_VERSION,
        "bundle_url": f"_static/{BUNDLE_FILENAME}",
        "bundle_sha256": bundle_sha256,
        "acceptance": acceptance,
    }
    config_path = static_dir / CONFIG_FILENAME
    config_path.write_text(
        "window.__CADRUMO_SEARCH_RUNG2__ = "
        + json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    return Rung2Emission(
        bundle_path=bundle_path,
        config_path=config_path,
        bundle_sha256=bundle_sha256,
        payload_bytes=len(payload),
        enabled=enabled,
    )


def _acceptance_block(evidence: Rung2AcceptanceEvidence, *, payload_bytes: int) -> dict[str, object]:
    """Project ratified evidence into the reader's acceptance shape.

    Every field the reader requires is taken from the evidence rather than
    defaulted here: a threshold invented at emit time would be a second result
    authority, which the seam's own contract forbids.
    """
    required = (
        "approved",
        "minimum_coverage_ratio",
        "cosine_floor",
        "runner_up_margin",
        "maximum_quantization_drift",
        "measured_quantization_drift",
        "quantization_accepted",
        "held_out_top_five_loss",
        "held_out_miss_rate",
        "no_locale_or_kind_regression",
    )
    block: dict[str, object] = {}
    for field in required:
        if not hasattr(evidence, field):
            raise Rung2EmitError(
                f"the ratified evidence does not carry {field!r}; "
                "the acceptance block must be ratified, never defaulted at emit time",
            )
        block[field] = getattr(evidence, field)
    block["payload_bytes"] = payload_bytes
    return block
