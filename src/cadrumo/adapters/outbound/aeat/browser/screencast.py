"""Screencast of the Sede view's page, acknowledged at once and drawn newest-first.

:class:`ViewScreencast` opens a Playwright-owned CDP session on the view's
own page and runs ``Page.startScreencast`` as JPEG, sized to the panel and
capped by a :class:`ScreencastProfile`. Chromium sends the next frame only
after the previous one is acknowledged, so every frame is acknowledged the
moment it arrives, whether or not anyone can draw it yet. Of the frames that
arrive, only the newest is retained.

Delivery is paced by credit, not by time. The consumer grants credit with
:meth:`ViewScreencast.grant_credit` after it drew an image, at most
:data:`~cadrumo_client.contracts.view_stream.VIEW_CREDIT_MAX_IMAGES` at a
time. A retained frame is handed to the sink only while credit remains and
consumes one credit. With no credit, frames stop reaching the sink; the
retained frame is replaced by each newer one, and the newest is handed over
when credit returns. Nothing else is buffered, so the sequence numbers the
sink sees skip the frames that were replaced.

Images are private taxpayer data. They live in memory only and are never
logged. Python copies of them cannot be wiped.

This module evaluates no script on the page. The only CDP methods it names
are ``Page.startScreencast``, ``Page.stopScreencast`` and
``Page.screencastFrameAck``.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Self

from pydantic import ValidationError

from cadrumo_client.contracts.view_stream import (
    VIEW_CREDIT_MAX_IMAGES,
    VIEW_IMAGE_MAX_BYTES,
    VIEW_MAX_CSS_EXTENT,
    VIEW_MAX_PIXEL_EXTENT,
    VIEW_MAX_SCALE,
    VIEW_MIN_SCALE,
    ViewImage,
    ViewResize,
)

from .....core.logging import get_logger
from .._playwright import BrowserContext, Page, PlaywrightError

if TYPE_CHECKING:
    from playwright.async_api import CDPSession

logger = get_logger(__name__)

#: Encoded size of the largest image, as base64 text; a longer frame is not decoded.
_BASE64_EXPANSION_NUMERATOR: Final[int] = 4
_BASE64_EXPANSION_DENOMINATOR: Final[int] = 3

#: JPEG segment markers that are start-of-frame headers (all but DHT, JPG and DAC).
_START_OF_FRAME_MARKERS: Final[frozenset[int]] = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
_START_OF_IMAGE: Final[bytes] = b"\xff\xd8"
_END_OF_IMAGE: Final[int] = 0xD9
_START_OF_SCAN: Final[int] = 0xDA
_TEMPORARY_MARKER: Final[int] = 0x01
_RESTART_MARKERS: Final[range] = range(0xD0, 0xD8)
_FILL_BYTE: Final[int] = 0xFF
_SEGMENT_HEADER_BYTES: Final[int] = 4
_FRAME_HEADER_BYTES: Final[int] = 9

#: How far the scale of an image may be clamped into the contract's range, to absorb pixel rounding.
_SCALE_TOLERANCE: Final[float] = 0.02


@dataclass(frozen=True, slots=True)
class ScreencastProfile:
    """How the screencast encodes and bounds its images.

    ``max_pixel_extent`` caps both image dimensions in device pixels, so a
    large panel is downscaled instead of growing the image. ``max_image_bytes``
    is the largest encoded image the view accepts; a larger frame is discarded.
    """

    quality: int = 70
    max_pixel_extent: int = 2560
    max_image_bytes: int = VIEW_IMAGE_MAX_BYTES

    def __post_init__(self) -> None:
        """Refuse a profile outside the contract's bounds."""
        if not 1 <= self.quality <= 100:
            raise ValueError("screencast quality is a JPEG quality between 1 and 100")
        if not 1 <= self.max_pixel_extent <= VIEW_MAX_PIXEL_EXTENT:
            raise ValueError("screencast pixel cap is within the contract's pixel extent")
        if not 1 <= self.max_image_bytes <= VIEW_IMAGE_MAX_BYTES:
            raise ValueError("screencast byte cap is within the contract's image size")


@dataclass(frozen=True, slots=True)
class ScreencastImage:
    """One encoded JPEG and the ``view.image`` announcement that precedes its chunks."""

    announcement: ViewImage
    data: bytes


type ScreencastSink = Callable[[ScreencastImage], Awaitable[None]]
"""Receives each image the credit allows; it completes once the image is written out."""


def image_matches_layout(pixel_width: int, pixel_height: int, css_width: int, css_height: int) -> bool:
    """Whether an image of ``pixel_width`` by ``pixel_height`` depicts a page laid out at the CSS size.

    A downscaled image keeps the page's aspect ratio to within the rounding of
    its two dimensions. Right after a resize Chromium can still send the
    previous layout's surface, fitted into the new size; that image does not
    match and is not announced as the new layout.
    """
    return abs(pixel_height * css_width - pixel_width * css_height) <= css_width + css_height


def jpeg_pixel_size(data: bytes) -> tuple[int, int] | None:
    """Return ``(width, height)`` from a JPEG's first frame header, or ``None``.

    Only the segment headers are read; no pixel is decoded. Anything that is
    not a JPEG with a well-formed frame header before its first scan yields
    ``None``.
    """
    if data[:2] != _START_OF_IMAGE:
        return None
    position = 2
    while position + 2 <= len(data):
        if data[position] != _FILL_BYTE:
            return None
        marker = data[position + 1]
        if marker == _FILL_BYTE:
            position += 1
            continue
        if marker == _TEMPORARY_MARKER or marker in _RESTART_MARKERS:
            position += 2
            continue
        if marker in {_END_OF_IMAGE, _START_OF_SCAN}:
            return None
        if position + _SEGMENT_HEADER_BYTES > len(data):
            return None
        length = int.from_bytes(data[position + 2 : position + 4], "big")
        if length < 2:
            return None
        if marker in _START_OF_FRAME_MARKERS:
            if position + _FRAME_HEADER_BYTES > len(data):
                return None
            height = int.from_bytes(data[position + 5 : position + 7], "big")
            width = int.from_bytes(data[position + 7 : position + 9], "big")
            return (width, height) if width > 0 and height > 0 else None
        position += 2 + length
    return None


@dataclass(slots=True)
class _RetainedFrame:
    """The newest frame Chromium sent, still as the base64 text it arrived in."""

    sequence: int
    encoded: str
    css_width: int
    css_height: int


class ViewScreencast:
    """The running screencast of one view page; build it with :meth:`start`."""

    def __init__(
        self,
        *,
        page: Page,
        session: CDPSession,
        sink: ScreencastSink,
        profile: ScreencastProfile,
    ) -> None:
        """Hold the page and its CDP session; nothing runs until :meth:`start` begins the screencast."""
        self._page = page
        self._session = session
        self._sink = sink
        self._profile = profile
        self._credit = 0
        self._pending: _RetainedFrame | None = None
        self._next_sequence = 0
        self._unusable_frames = 0
        self._ready = asyncio.Event()
        self._lock = asyncio.Lock()
        self._stopped = False
        self._acknowledgements: set[asyncio.Task[None]] = set()
        self._pump: asyncio.Task[None] | None = None

    @classmethod
    async def start(
        cls,
        context: BrowserContext,
        page: Page,
        viewport: ViewResize,
        sink: ScreencastSink,
        *,
        profile: ScreencastProfile | None = None,
    ) -> Self:
        """Size ``page`` to ``viewport`` and start its screencast.

        A new view connection starts with no credit; no image reaches ``sink``
        before :meth:`grant_credit`. A Playwright failure while starting
        propagates after the CDP session is released.
        """
        session = await context.new_cdp_session(page)
        screencast = cls(page=page, session=session, sink=sink, profile=profile or ScreencastProfile())
        try:
            await screencast._begin(viewport)
        except BaseException:
            await screencast.stop()
            raise
        return screencast

    @property
    def received_frames(self) -> int:
        """How many frames Chromium has sent, each acknowledged on arrival."""
        return self._next_sequence

    @property
    def unusable_frames(self) -> int:
        """How many frames were discarded instead of announced.

        A frame is discarded when it exceeds the byte cap, is not a readable
        JPEG, depicts a layout other than the page's current CSS size, or was
        scaled below the contract's smallest scale.
        """
        return self._unusable_frames

    def grant_credit(self, images: int) -> None:
        """Allow ``images`` more images, never more than two outstanding at once.

        The window grants credit after drawing. A grant that would take the
        outstanding credit past the contract's bound is cut to the bound.
        """
        if self._stopped or images < 1:
            return
        self._credit = min(self._credit + images, VIEW_CREDIT_MAX_IMAGES)
        self._ready.set()

    async def resize(self, viewport: ViewResize) -> None:
        """Lay the page out at the panel's new size and restart the screencast at the new cap."""
        async with self._lock:
            if self._stopped:
                return
            await self._page.set_viewport_size({"width": viewport.css_width, "height": viewport.css_height})
            await self._session.send("Page.stopScreencast")
            await self._session.send("Page.startScreencast", self._screencast_parameters(viewport))

    async def wait_ended(self) -> None:
        """Return when the screencast has stopped, or raise what the sink raised.

        The owner awaits this beside its other work to learn that the lane to
        the window failed. A stopped screencast returns normally.
        """
        pump = self._pump
        if pump is None:
            return
        try:
            # Shielded, so cancelling the waiter never cancels the delivery itself.
            await asyncio.shield(pump)
        except asyncio.CancelledError:
            if not pump.cancelled():
                raise

    async def stop(self) -> None:
        """Stop the screencast, drop the retained frame and release the CDP session.

        An image being written to the sink is abandoned; the owner closes the
        lane to the window afterwards. A page or browser that is already gone
        is not an error.
        """
        async with self._lock:
            if self._stopped:
                return
            self._stopped = True
        self._pending = None
        try:
            await self._session.send("Page.stopScreencast")
        except PlaywrightError as exc:
            logger.debug("aeat view screencast stop skipped exc_type=%s", type(exc).__name__)
        if self._pump is not None:
            self._pump.cancel()
            await asyncio.gather(self._pump, return_exceptions=True)
        for acknowledgement in tuple(self._acknowledgements):
            acknowledgement.cancel()
        await asyncio.gather(*self._acknowledgements, return_exceptions=True)
        try:
            await self._session.detach()
        except PlaywrightError as exc:
            logger.debug("aeat view screencast detach skipped exc_type=%s", type(exc).__name__)

    async def _begin(self, viewport: ViewResize) -> None:
        await self._page.set_viewport_size({"width": viewport.css_width, "height": viewport.css_height})
        self._session.on("Page.screencastFrame", self._on_frame)
        self._pump = asyncio.get_running_loop().create_task(self._deliver())
        await self._session.send("Page.startScreencast", self._screencast_parameters(viewport))

    def _screencast_parameters(self, viewport: ViewResize) -> dict[str, object]:
        cap = self._profile.max_pixel_extent
        return {
            "format": "jpeg",
            "quality": self._profile.quality,
            "maxWidth": min(max(round(viewport.css_width * viewport.scale), 1), cap),
            "maxHeight": min(max(round(viewport.css_height * viewport.scale), 1), cap),
            "everyNthFrame": 1,
        }

    def _on_frame(self, parameters: dict[str, object]) -> None:
        session_id = parameters.get("sessionId")
        if isinstance(session_id, int):
            # First, so Chromium's next frame is never held back by anything below.
            task = asyncio.get_running_loop().create_task(self._acknowledge(session_id))
            self._acknowledgements.add(task)
            task.add_done_callback(self._acknowledgements.discard)
        if self._stopped:
            return
        encoded = parameters.get("data")
        metadata = parameters.get("metadata")
        sequence = self._next_sequence
        self._next_sequence += 1
        css_size = _css_size(metadata)
        if not isinstance(encoded, str) or css_size is None:
            self._unusable_frames += 1
            return
        self._pending = _RetainedFrame(sequence, encoded, css_size[0], css_size[1])
        self._ready.set()

    async def _acknowledge(self, session_id: int) -> None:
        try:
            await self._session.send("Page.screencastFrameAck", {"sessionId": session_id})
        except PlaywrightError as exc:
            logger.debug("aeat view screencast ack skipped exc_type=%s", type(exc).__name__)

    async def _deliver(self) -> None:
        while True:
            await self._ready.wait()
            self._ready.clear()
            while self._credit > 0 and self._pending is not None:
                frame = self._pending
                self._pending = None
                image = self._announce(frame)
                if image is None:
                    self._unusable_frames += 1
                    continue
                self._credit -= 1
                await self._sink(image)

    def _announce(self, frame: _RetainedFrame) -> ScreencastImage | None:
        limit = self._profile.max_image_bytes
        if len(frame.encoded) > limit * _BASE64_EXPANSION_NUMERATOR // _BASE64_EXPANSION_DENOMINATOR + 4:
            return None
        try:
            data = base64.b64decode(frame.encoded, validate=True)
        except (binascii.Error, ValueError):
            return None
        pixel_size = jpeg_pixel_size(data)
        if pixel_size is None or len(data) > limit:
            return None
        if not image_matches_layout(pixel_size[0], pixel_size[1], frame.css_width, frame.css_height):
            return None
        exact_scale = pixel_size[0] / frame.css_width
        scale = min(max(exact_scale, VIEW_MIN_SCALE), VIEW_MAX_SCALE)
        if abs(scale - exact_scale) > _SCALE_TOLERANCE:
            return None
        try:
            announcement = ViewImage(
                sequence=frame.sequence,
                byte_length=len(data),
                pixel_width=pixel_size[0],
                pixel_height=pixel_size[1],
                css_width=frame.css_width,
                css_height=frame.css_height,
                scale=round(scale, 4),
            )
        except ValidationError:
            return None
        return ScreencastImage(announcement=announcement, data=data)


def _css_size(metadata: object) -> tuple[int, int] | None:
    """Read the page's CSS size from a frame's metadata, within the contract's extent."""
    if not isinstance(metadata, dict):
        return None
    width: object = metadata.get("deviceWidth")
    height: object = metadata.get("deviceHeight")
    if not isinstance(width, int | float) or not isinstance(height, int | float):
        return None
    css_width, css_height = round(width), round(height)
    if not (1 <= css_width <= VIEW_MAX_CSS_EXTENT and 1 <= css_height <= VIEW_MAX_CSS_EXTENT):
        return None
    return css_width, css_height
