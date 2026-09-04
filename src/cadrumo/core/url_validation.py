"""The canonical validator for an absolute HTTP URL.

Six modules each constructed their own ``TypeAdapter(AnyHttpUrl)`` under four
different names -- ``_ANY_HTTP_URL_ADAPTER``, ``_HTTP_URL_ADAPTER``,
``_URL_ADAPTER`` and ``_SITE_HEALTH_URL_ADAPTER``. The adapter is stateless and
identical wherever it is built, so each copy was a duplicate definition.

The four names mattered more than the six copies. ``_URL_ADAPTER`` is also the
name :mod:`cadrumo.domain.portals._entries.common` gives to a
``TypeAdapter(HttpUrl)``, which is a DIFFERENT type: ``HttpUrl`` constrains the
scheme to http or https, while ``AnyHttpUrl`` does not. One name meaning two
validators is how a caller ends up applying the weaker check believing it
applied the stronger one, so this module is named for the type it validates and
the portals adapter is deliberately left where it is.
"""

from __future__ import annotations

from typing import Final

from pydantic import AnyHttpUrl, TypeAdapter

ANY_HTTP_URL_ADAPTER: Final[TypeAdapter[AnyHttpUrl]] = TypeAdapter(AnyHttpUrl)
"""Validate a string as an absolute HTTP URL of any scheme pydantic accepts."""

__all__ = ["ANY_HTTP_URL_ADAPTER"]
