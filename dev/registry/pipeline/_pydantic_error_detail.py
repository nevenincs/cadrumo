"""Render a pydantic ``ValidationError`` without its own leaking string form.

``str(ValidationError)`` composes itself from :meth:`ValidationError.errors`
and appends an ``input_value=`` fragment holding a length-truncated ``repr``
of the WHOLE validated payload, regardless of what the failing validator's own
message says. Measured (against a project TOML/JSON fragment payload carrying
a short and a long string field): the short value survives that truncation
whole into the composed string; the longer one happens to fall inside the
elided middle. Neither outcome is something this pipeline decided, and a
registry-fragment loader must never let a foreign renderer choose what a
refusal message shows.

Every caller in this package that catches :exc:`~pydantic.ValidationError`
therefore builds its message only from :func:`validation_error_detail`, never
from ``str(exc)`` or the exception's own ``args``.

The per-error ``loc`` tuple is included ahead of each ``msg``. ``loc`` is safe
to show: every model in this package validates a fixed, statically declared
schema -- no ``dict[str, ...]``-shaped field whose key could carry a caller's
string value -- so ``loc`` is always composed of field names and tuple/list
indices the schema itself declares, never payload content.
"""

from __future__ import annotations

from pydantic import ValidationError


def validation_error_detail(exc: ValidationError) -> str:
    """Return ``exc``'s own per-error locations and messages, and nothing else.

    Uses :meth:`ValidationError.errors` with ``include_url=False`` and
    ``include_input=False`` so the result carries only each error's ``loc``
    (a path of schema-declared field names and indices) and its ``msg`` (the
    text the failing validator composed on purpose to be shown) -- never the
    validated payload.
    """
    parts: list[str] = []
    for error in exc.errors(include_url=False, include_input=False):
        location = ".".join(str(segment) for segment in error["loc"])
        parts.append(f"{location}: {error['msg']}" if location else error["msg"])
    return "; ".join(parts)
