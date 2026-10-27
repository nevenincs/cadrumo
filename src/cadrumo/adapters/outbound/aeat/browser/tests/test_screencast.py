"""The Sede view's screencast, proven against a real headless Chromium.

Every case drives the production :class:`ViewScreencast` on a real page and
reads the images it hands to its sink. Pixels are read back with Pillow, which
is independent of the adapter's own JPEG header reader.
"""

from __future__ import annotations

import asyncio
import io
from typing import Final

import pytest
from PIL import Image
from playwright.async_api import Error as PlaywrightError

from cadrumo_client.contracts.view_stream import (
    VIEW_CREDIT_MAX_IMAGES,
    ViewResize,
)

from ..screencast import ScreencastImage, ScreencastProfile, ViewScreencast, image_matches_layout, jpeg_pixel_size
from .view_page_support import EVENT_TIMEOUT_SECONDS, until, view_browser

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_VIEWPORT: Final[ViewResize] = ViewResize(css_width=400, css_height=300, scale=1.0)
_QUIET_SECONDS: Final[float] = 0.4
_RED: Final[tuple[int, int, int]] = (255, 0, 0)
_GREEN: Final[tuple[int, int, int]] = (0, 255, 0)
_BLUE: Final[tuple[int, int, int]] = (0, 0, 255)
_ANIMATED_PAGE: Final[str] = (
    "<style>@keyframes pulse{from{background:#f00}to{background:#00f}}"
    "body{margin:0;animation:pulse .1s infinite alternate}</style>"
)


class _Sink:
    """Collect the images the screencast hands over, as the lane to the window would."""

    def __init__(self) -> None:
        self.images: list[ScreencastImage] = []
        self._arrived = asyncio.Event()

    async def __call__(self, image: ScreencastImage) -> None:
        self.images.append(image)
        self._arrived.set()

    async def wait_for(self, count: int) -> None:
        async def arrived() -> None:
            while len(self.images) < count:
                self._arrived.clear()
                await self._arrived.wait()

        await asyncio.wait_for(arrived(), timeout=EVENT_TIMEOUT_SECONDS)


def _paint(color: tuple[int, int, int]) -> str:
    return f"<body style='margin:0;background:rgb{color}'></body>"


def _center_pixel(image: ScreencastImage) -> tuple[int, int, int]:
    decoded = Image.open(io.BytesIO(image.data)).convert("RGB")
    pixel = decoded.getpixel((decoded.width // 2, decoded.height // 2))
    assert isinstance(pixel, tuple)
    return pixel[0], pixel[1], pixel[2]


def _is_color(image: ScreencastImage, expected: tuple[int, int, int]) -> bool:
    return all(abs(actual - wanted) < 60 for actual, wanted in zip(_center_pixel(image), expected, strict=True))


@pytest.mark.asyncio
async def test_screencast_delivers_a_jpeg_sized_to_the_viewport() -> None:
    sink = _Sink()
    async with view_browser(width=800, height=600) as (context, page):
        await page.set_content(_paint(_RED))
        screencast = await ViewScreencast.start(context, page, _VIEWPORT, sink)
        try:
            assert page.viewport_size == {"width": 400, "height": 300}
            screencast.grant_credit(1)
            await sink.wait_for(1)
        finally:
            await screencast.stop()

    image = sink.images[0]
    decoded = Image.open(io.BytesIO(image.data))
    assert decoded.format == "JPEG"
    assert decoded.size == (400, 300)
    announcement = image.announcement
    assert (announcement.pixel_width, announcement.pixel_height) == (400, 300)
    assert (announcement.css_width, announcement.css_height) == (400, 300)
    assert announcement.scale == 1.0
    assert announcement.byte_length == len(image.data)
    assert _is_color(image, _RED)


@pytest.mark.asyncio
async def test_screencast_does_not_claim_a_scale_the_page_did_not_render() -> None:
    sink = _Sink()
    async with view_browser() as (context, page):
        await page.set_content(_paint(_RED))
        screencast = await ViewScreencast.start(
            context, page, ViewResize(css_width=400, css_height=300, scale=2.0), sink
        )
        try:
            screencast.grant_credit(1)
            await sink.wait_for(1)
        finally:
            await screencast.stop()

    announcement = sink.images[0].announcement
    assert (announcement.pixel_width, announcement.pixel_height) == (400, 300)
    assert announcement.scale == 1.0


@pytest.mark.asyncio
async def test_screencast_caps_the_image_below_the_viewport() -> None:
    sink = _Sink()
    async with view_browser() as (context, page):
        await page.set_content(_paint(_RED))
        screencast = await ViewScreencast.start(
            context, page, _VIEWPORT, sink, profile=ScreencastProfile(max_pixel_extent=200)
        )
        try:
            screencast.grant_credit(1)
            await sink.wait_for(1)
        finally:
            await screencast.stop()

    announcement = sink.images[0].announcement
    assert (announcement.pixel_width, announcement.pixel_height) == (200, 150)
    assert (announcement.css_width, announcement.css_height) == (400, 300)
    assert announcement.scale == 0.5
    assert Image.open(io.BytesIO(sink.images[0].data)).size == (200, 150)


@pytest.mark.asyncio
async def test_screencast_sends_no_image_without_credit_and_resumes_with_the_newest() -> None:
    sink = _Sink()
    async with view_browser() as (context, page):
        await page.set_content(_paint(_RED))
        screencast = await ViewScreencast.start(context, page, _VIEWPORT, sink)
        try:
            await until(lambda: screencast.received_frames >= 1)
            for color in (_GREEN, _BLUE):
                received = screencast.received_frames
                await page.set_content(_paint(color))
                await until(lambda received=received: screencast.received_frames > received)
            await asyncio.sleep(_QUIET_SECONDS)
            assert sink.images == []

            screencast.grant_credit(1)
            await sink.wait_for(1)
            assert _is_color(sink.images[0], _BLUE)

            received = screencast.received_frames
            await page.set_content(_paint(_RED))
            await until(lambda: screencast.received_frames > received)
            await asyncio.sleep(_QUIET_SECONDS)
            assert len(sink.images) == 1

            screencast.grant_credit(1)
            await sink.wait_for(2)
            assert _is_color(sink.images[1], _RED)
            assert sink.images[1].announcement.sequence > sink.images[0].announcement.sequence
        finally:
            await screencast.stop()


@pytest.mark.asyncio
async def test_screencast_acknowledges_every_frame_though_none_can_be_drawn() -> None:
    sink = _Sink()
    async with view_browser() as (context, page):
        await page.set_content(_ANIMATED_PAGE)
        screencast = await ViewScreencast.start(context, page, _VIEWPORT, sink)
        try:
            # Chromium stops sending after a few unacknowledged frames, so a count this high
            # shows each frame was acknowledged on arrival although the sink had no credit.
            await until(lambda: screencast.received_frames >= 8)
            assert sink.images == []

            received = screencast.received_frames
            screencast.grant_credit(1)
            await sink.wait_for(1)
            assert sink.images[0].announcement.sequence >= received - 1
        finally:
            await screencast.stop()


@pytest.mark.asyncio
async def test_screencast_credit_never_exceeds_two_outstanding_images() -> None:
    sink = _Sink()
    async with view_browser() as (context, page):
        await page.set_content(_ANIMATED_PAGE)
        screencast = await ViewScreencast.start(context, page, _VIEWPORT, sink)
        try:
            await until(lambda: screencast.received_frames >= 2)
            screencast.grant_credit(VIEW_CREDIT_MAX_IMAGES)
            screencast.grant_credit(VIEW_CREDIT_MAX_IMAGES)
            await sink.wait_for(VIEW_CREDIT_MAX_IMAGES)
            await asyncio.sleep(_QUIET_SECONDS)
            assert len(sink.images) == VIEW_CREDIT_MAX_IMAGES

            screencast.grant_credit(0)
            screencast.grant_credit(-1)
            await asyncio.sleep(_QUIET_SECONDS)
            assert len(sink.images) == VIEW_CREDIT_MAX_IMAGES
        finally:
            await screencast.stop()


@pytest.mark.asyncio
async def test_screencast_resize_lays_the_page_out_at_the_new_size() -> None:
    sink = _Sink()
    async with view_browser() as (context, page):
        await page.set_content(_paint(_RED))
        screencast = await ViewScreencast.start(context, page, _VIEWPORT, sink)
        try:
            await screencast.resize(ViewResize(css_width=600, css_height=200, scale=1.0))
            assert page.viewport_size == {"width": 600, "height": 200}

            async def resized() -> ScreencastImage:
                delivered = 0
                while True:
                    screencast.grant_credit(1)
                    delivered += 1
                    await sink.wait_for(delivered)
                    image = sink.images[-1]
                    if image.announcement.css_width == 600:
                        return image

            image = await asyncio.wait_for(resized(), timeout=EVENT_TIMEOUT_SECONDS)
        finally:
            await screencast.stop()

    # Chromium can still send the old layout's surface right after a resize; none may be announced as the new one.
    for delivered in sink.images:
        described = delivered.announcement
        assert image_matches_layout(
            described.pixel_width, described.pixel_height, described.css_width, described.css_height
        ), described
    announcement = image.announcement
    assert (announcement.css_width, announcement.css_height) == (600, 200)
    assert (announcement.pixel_width, announcement.pixel_height) == (600, 200)
    assert Image.open(io.BytesIO(image.data)).size == (600, 200)


@pytest.mark.asyncio
async def test_screencast_discards_an_image_scaled_below_the_contract_minimum() -> None:
    sink = _Sink()
    async with view_browser() as (context, page):
        await page.set_content(_paint(_RED))
        screencast = await ViewScreencast.start(
            context, page, _VIEWPORT, sink, profile=ScreencastProfile(max_pixel_extent=100)
        )
        try:
            screencast.grant_credit(1)
            await until(lambda: screencast.unusable_frames >= 1)
            assert sink.images == []
        finally:
            await screencast.stop()


@pytest.mark.asyncio
async def test_screencast_discards_an_image_over_its_byte_cap_and_keeps_acknowledging() -> None:
    sink = _Sink()
    async with view_browser() as (context, page):
        await page.set_content(_paint(_RED))
        screencast = await ViewScreencast.start(
            context, page, _VIEWPORT, sink, profile=ScreencastProfile(max_image_bytes=1)
        )
        try:
            screencast.grant_credit(1)
            await until(lambda: screencast.unusable_frames >= 1)
            assert sink.images == []
            await page.set_content(_paint(_BLUE))
            await until(lambda: screencast.received_frames >= 2)
        finally:
            await screencast.stop()


@pytest.mark.asyncio
async def test_screencast_stop_ends_delivery_and_is_repeatable() -> None:
    sink = _Sink()
    async with view_browser() as (context, page):
        await page.set_content(_ANIMATED_PAGE)
        screencast = await ViewScreencast.start(context, page, _VIEWPORT, sink)
        await until(lambda: screencast.received_frames >= 2)
        await screencast.stop()
        await screencast.stop()
        await screencast.wait_ended()
        received = screencast.received_frames

        screencast.grant_credit(2)
        await asyncio.sleep(_QUIET_SECONDS)
        assert sink.images == []
        assert screencast.received_frames == received
        await screencast.resize(ViewResize(css_width=500, css_height=500, scale=1.0))
        assert page.viewport_size == {"width": 400, "height": 300}


@pytest.mark.asyncio
async def test_screencast_reports_a_sink_failure_through_wait_ended() -> None:
    async def failing_sink(image: ScreencastImage) -> None:
        raise ConnectionResetError("lane closed")

    async with view_browser() as (context, page):
        await page.set_content(_paint(_RED))
        screencast = await ViewScreencast.start(context, page, _VIEWPORT, failing_sink)
        try:
            screencast.grant_credit(1)
            with pytest.raises(ConnectionResetError, match="lane closed"):
                await asyncio.wait_for(screencast.wait_ended(), timeout=EVENT_TIMEOUT_SECONDS)
        finally:
            await screencast.stop()


@pytest.mark.asyncio
async def test_screencast_start_on_a_closed_page_raises_and_leaves_nothing_open() -> None:
    sink = _Sink()
    async with view_browser() as (context, page):
        await page.close()
        with pytest.raises(PlaywrightError):
            await ViewScreencast.start(context, page, _VIEWPORT, sink)


@pytest.mark.parametrize(
    ("pixels", "css", "matches"),
    [
        ((400, 300), (400, 300), True),
        ((200, 150), (400, 300), True),
        ((199, 150), (400, 300), True),
        ((267, 200), (400, 300), True),
        ((400, 133), (600, 200), True),
        ((267, 200), (600, 200), False),
        ((400, 300), (600, 200), False),
        ((1000, 500), (500, 1000), False),
    ],
)
def test_image_matches_layout_tolerates_pixel_rounding_and_refuses_another_aspect(
    pixels: tuple[int, int], css: tuple[int, int], *, matches: bool
) -> None:
    assert image_matches_layout(pixels[0], pixels[1], css[0], css[1]) is matches


@pytest.mark.parametrize(
    ("size", "progressive"),
    [((1, 1), False), ((123, 45), False), ((640, 480), True), ((4097, 3), False)],
)
def test_jpeg_pixel_size_reads_the_frame_header_of_baseline_and_progressive_files(
    size: tuple[int, int], *, progressive: bool
) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 120, 200)).save(buffer, format="JPEG", progressive=progressive)

    assert jpeg_pixel_size(buffer.getvalue()) == size


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\xff\xd8",
        b"\x89PNG\r\n\x1a\n",
        b"\xff\xd8\xff\xe0\x00\x04",
        b"\xff\xd8\xff\xe0\x00\x01\x00",
        b"\xff\xd8\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00",
        b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x00\x00\x10\x01",
        b"\xff\xd8\x00\x00\x00\x00",
    ],
)
def test_jpeg_pixel_size_refuses_anything_without_a_readable_frame_header(data: bytes) -> None:
    assert jpeg_pixel_size(data) is None


@pytest.mark.parametrize(
    "profile",
    [
        {"quality": 0},
        {"quality": 101},
        {"max_pixel_extent": 0},
        {"max_pixel_extent": 8193},
        {"max_image_bytes": 0},
        {"max_image_bytes": 2 * 1024 * 1024 + 1},
    ],
)
def test_screencast_profile_refuses_values_outside_the_contract(profile: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="screencast"):
        ScreencastProfile(**profile)
