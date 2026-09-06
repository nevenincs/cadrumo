"""Byte-stable save flags for :mod:`dev.sanitizer`.

The default :meth:`pikepdf.Pdf.save` invocation is non-deterministic:
the trailer ``/ID`` array is timestamp-seeded, ``recompress_flate``
re-runs zlib at the system default level, and ``object_stream_mode=
generate`` shuffles object insertion order. This module wraps
``Pdf.save`` with a named flag set so the same input bytes round-trip
to the same output bytes across runs and processes.

The flags live as a :class:`DeterminismFlags` instance returned by
:func:`save_with_deterministic_flags` and embedded in every
:class:`SanitizationResult` so callers can audit which save shape
produced a given fixture.
"""

from __future__ import annotations

import io

from pikepdf import ObjectStreamMode, Pdf

from ._records import DeterminismFlags

# The canonical save flag set, kept as a module-level constant so
# the determinism contract is greppable from one place; tests may
# import this to assert the flags applied.
_DETERMINISM_FLAGS = DeterminismFlags(
    deterministic_id=True,
    static_id=False,
    object_stream_mode="preserve",
    linearize=False,
    recompress_flate=False,
    compress_streams=True,
)


def deterministic_save_flags() -> DeterminismFlags:
    """Return the canonical flag set used by :func:`save_with_deterministic_flags`.

    Exposed as a module-level helper so tests and audit reports can
    assert the exact flags without re-instantiating
    :class:`DeterminismFlags` from a literal — drift between the
    record and the actual save call would defeat the determinism
    contract.

    Returns:
        The single :class:`DeterminismFlags` instance applied during
        :func:`save_with_deterministic_flags`.
    """
    return _DETERMINISM_FLAGS


def save_with_deterministic_flags(pdf: Pdf) -> tuple[bytes, DeterminismFlags]:
    """Serialise ``pdf`` to bytes with the deterministic save flag set.

    Args:
        pdf: An open :class:`pikepdf.Pdf` instance ready to be
            saved. The caller retains ownership; this function does
            not close ``pdf``.

    Returns:
        A 2-tuple of ``(output_bytes, flags_applied)``. The bytes
        are byte-stable across repeated invocations on equivalent
        inputs; the :class:`DeterminismFlags` record matches the canonical set.
    """
    buffer = io.BytesIO()
    pdf.save(
        buffer,
        deterministic_id=_DETERMINISM_FLAGS.deterministic_id,
        static_id=_DETERMINISM_FLAGS.static_id,
        object_stream_mode=ObjectStreamMode[_DETERMINISM_FLAGS.object_stream_mode],
        linearize=_DETERMINISM_FLAGS.linearize,
        recompress_flate=_DETERMINISM_FLAGS.recompress_flate,
        compress_streams=_DETERMINISM_FLAGS.compress_streams,
    )
    return buffer.getvalue(), _DETERMINISM_FLAGS
