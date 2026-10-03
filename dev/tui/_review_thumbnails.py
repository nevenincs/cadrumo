"""Produce and cache review thumbnails by their immutable PNG identities."""

from __future__ import annotations

import io
import threading
from collections import OrderedDict
from typing import Final

from PIL import Image

THUMBNAIL_WIDTH: Final[int] = 480


THUMBNAIL_CACHE_SIZE: Final[int] = 1024


def render_thumbnail(payload: bytes, *, width: int = THUMBNAIL_WIDTH) -> bytes:
    """A WebP reduction of a PNG frame, for the grid on a phone."""
    with Image.open(io.BytesIO(payload)) as source:
        image = source.convert("RGB")
    if image.width > width:
        height = max(1, round(image.height * width / image.width))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=82, method=4)
    return buffer.getvalue()


class ThumbnailCache:
    """Thumbnails by PNG digest, least recently used first out."""

    def __init__(self, capacity: int = THUMBNAIL_CACHE_SIZE) -> None:
        """Hold at most ``capacity`` thumbnails in memory."""
        self._capacity = capacity
        self._entries: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, digest: str) -> bytes | None:
        """The cached thumbnail for a PNG digest."""
        with self._lock:
            cached = self._entries.get(digest)
            if cached is not None:
                self._entries.move_to_end(digest)
            return cached

    def put(self, digest: str, thumbnail: bytes) -> None:
        """Keep a thumbnail, evicting the least recently used past capacity."""
        with self._lock:
            self._entries[digest] = thumbnail
            self._entries.move_to_end(digest)
            while len(self._entries) > self._capacity:
                self._entries.popitem(last=False)
