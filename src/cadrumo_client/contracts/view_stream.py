"""Closed control documents and bounds of the Sede view stream.

A view stream runs on its own verified connection on each leg: profile worker
to runtime host, and runtime host to window. On those connections ``J`` frames
carry exactly the documents declared here and ``B`` frames carry image chunks
whose 16-byte header the transport's view codec owns.

Downstream, toward the window: ``view.image`` announces the next image and is
immediately followed by all of that image's chunks, in order; ``view.state``,
``view.notice`` and ``view.closed`` report the page. Upstream, from the window:
``view.credit``, ``view.input``, ``view.navigate``, ``view.resize``,
``view.dialog`` and ``view.close``. Every set is closed: an unknown kind, member or value refuses
the frame, and a refused frame ends the view connection.

The window binds a view connection by asking on its person connection with
``view_attach`` for a single-use token, then presenting it with
``view_connect`` as the first request of a new connection from the same native
peer. The worker's own leg opens with ``view.bind``. ``ViewStreamSink`` is the
worker-side port a view operation's executor writes to.

Images, page titles, URLs, dialog text and input are private taxpayer data.
These documents live in memory only; they are never logged, persisted,
journaled or projected.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Final, Literal, Protocol, Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, Field, RootModel, model_validator

from cadrumo.application.operations.models import OperationId
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

if TYPE_CHECKING:
    from .view_transfer import (
        ViewDownload,
        ViewFileChooser,
        ViewTransferByteSource,
        ViewTransferCancel,
        ViewTransferEvent,
    )

VIEW_IMAGE_MAX_BYTES = 2 * 1024 * 1024
"""The largest encoded JPEG one image may carry."""

VIEW_CREDIT_MAX_IMAGES = 2
"""The most images a producer may have sent and not yet had credited back, per leg."""

VIEW_MAX_CSS_EXTENT = 4096
"""The largest panel width or height, in CSS pixels."""

VIEW_MAX_PIXEL_EXTENT = 8192
"""The largest image width or height, in device pixels."""

VIEW_MIN_SCALE = 0.5
VIEW_MAX_SCALE = 4.0
"""Bounds of the device pixel ratio the panel draws at."""

VIEW_MAX_SEQUENCE = 2**32 - 1
"""Image sequences and dialog ids are unsigned 32-bit numbers."""

VIEW_MAX_URL_LENGTH = 2048
VIEW_MAX_PATH_LENGTH = 2048
VIEW_MAX_TITLE_LENGTH = 1024
VIEW_MAX_DIALOG_MESSAGE_LENGTH = 2048
VIEW_MAX_PROMPT_TEXT_LENGTH = 1024
VIEW_MAX_TEXT_INPUT_LENGTH = 256
VIEW_MAX_KEY_LENGTH = 32
VIEW_MAX_WHEEL_DELTA = 10_000
VIEW_MAX_MODIFIERS = 15
"""Modifier bitmask as CDP spells it: Alt 1, Control 2, Meta 4, Shift 8."""

VIEW_MAX_CLICK_COUNT = 3

type _Extent = Annotated[int, Field(ge=1, le=VIEW_MAX_CSS_EXTENT)]
type _PixelExtent = Annotated[int, Field(ge=1, le=VIEW_MAX_PIXEL_EXTENT)]
type _Coordinate = Annotated[int, Field(ge=0, le=VIEW_MAX_CSS_EXTENT - 1)]
type _Scale = Annotated[float, Field(ge=VIEW_MIN_SCALE, le=VIEW_MAX_SCALE, allow_inf_nan=False)]
type _Modifiers = Annotated[int, Field(ge=0, le=VIEW_MAX_MODIFIERS)]
type _DialogId = Annotated[int, Field(ge=1, le=VIEW_MAX_SEQUENCE)]


def _has_control_character(value: str) -> bool:
    return any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)


def _is_address_of(address: str, origin: str) -> bool:
    """Whether ``address`` is a URL on exactly ``origin``, with no credentials, space or control character."""
    rest = address.removeprefix(origin)
    return (
        rest != address
        and rest[:1] in {"", "/", "?", "#"}
        and not _has_control_character(address)
        and " " not in address
    )


class ViewPhase(StrEnum):
    """Where the view's operation is: logging in, browsing, or publishing on close."""

    ACQUIRING = "acquiring"
    """A login runs in the view; the person's input still reaches the page and interrupts an assisted step."""
    BROWSING = "browsing"
    """The person browses; input reaches the page."""
    CLOSING = "closing"
    """The view captures, verifies and publishes its session; the panel is busy."""


class ViewNoticeCode(StrEnum):
    """Every notice the view may show; offer codes carry an external-browser offer."""

    DOWNLOAD_OFFERED = "download_offered"
    """A download, offered in the external browser."""
    FILE_CHOOSER_OFFERED = "file_chooser_offered"
    """A file upload, offered in the external browser."""
    DIALOG_OPENED = "dialog_opened"
    """The page opened a dialog the person answers with ``view.dialog``."""


VIEW_OFFER_NOTICE_CODES = frozenset({ViewNoticeCode.DOWNLOAD_OFFERED, ViewNoticeCode.FILE_CHOOSER_OFFERED})
"""The notice codes that carry an offer, and only they."""


class ViewDialogKind(StrEnum):
    """The page dialog kinds, spelled as CDP and Playwright spell them."""

    ALERT = "alert"
    CONFIRM = "confirm"
    PROMPT = "prompt"
    BEFOREUNLOAD = "beforeunload"


class ViewClosedReason(StrEnum):
    """Why a view connection ended; the operation's own result says how it settled."""

    CANCELLED = "cancelled"
    """The person closed the page or the window."""
    IDLE_EXPIRED = "idle_expired"
    """No person input arrived within the idle bound."""
    LIFETIME_EXPIRED = "lifetime_expired"
    """The view reached its absolute bound."""
    SESSION_RETIRED = "session_retired"
    """The window's person session was signed out, locked, expired or replaced."""
    OPERATION_ENDED = "operation_ended"
    """The view's operation settled for another reason."""
    REPLACED = "replaced"
    """A later attach bound a new view connection to the operation."""
    PROTOCOL_VIOLATION = "protocol_violation"
    """A peer sent a frame or document this contract refuses."""
    RUNTIME_STOPPING = "runtime_stopping"
    """The runtime is shutting down."""
    FAILED = "failed"
    """The view's browser failed."""


class ViewImage(BaseModel):
    """Announce the next image; its chunks follow at once, contiguous and in order.

    ``sequence`` strictly increases on a view connection and may skip values,
    because a producer without credit replaces its pending image.
    ``byte_length`` equals the image length in every chunk header.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.image"] = "view.image"
    sequence: int = Field(ge=0, le=VIEW_MAX_SEQUENCE)
    byte_length: int = Field(ge=1, le=VIEW_IMAGE_MAX_BYTES)
    pixel_width: _PixelExtent
    pixel_height: _PixelExtent
    css_width: _Extent
    css_height: _Extent
    scale: _Scale


class ViewState(BaseModel):
    """The page: origin and path for the toolbar, and the full address for the desktop host alone.

    ``origin`` and ``path`` never carry a query or fragment; they are what the
    window shows. ``address`` is the page's whole URL, query included, so that
    the person's "open in external browser" lands on the same page. The desktop
    host keeps it in memory and never relays it to the window; it is ``None``
    when the page's URL does not fit the contract.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.state"] = "view.state"
    origin: str = Field(min_length=1, max_length=VIEW_MAX_URL_LENGTH)
    path: str = Field(min_length=1, max_length=VIEW_MAX_PATH_LENGTH)
    address: str | None = Field(default=None, min_length=1, max_length=VIEW_MAX_URL_LENGTH)
    title: str = Field(max_length=VIEW_MAX_TITLE_LENGTH)
    can_go_back: bool
    can_go_forward: bool
    loading: bool
    phase: ViewPhase

    @model_validator(mode="after")
    def _origin_and_path_only(self) -> Self:
        parts = urlsplit(self.origin)
        if (
            parts.scheme != "https"
            or parts.hostname in {None, ""}
            or parts.username is not None
            or parts.password is not None
            or parts.path
            or parts.query
            or parts.fragment
            or self.origin != f"https://{parts.netloc}"
            or parts.netloc != parts.netloc.lower()
        ):
            raise ValueError("origin must be a lower-case https origin alone")
        if not self.path.startswith("/") or "?" in self.path or "#" in self.path:
            raise ValueError("path must be an absolute path without query or fragment")
        if _has_control_character(self.origin + self.path):
            raise ValueError("origin and path must not carry control characters")
        if self.address is not None and not _is_address_of(self.address, self.origin):
            raise ValueError("address must be a credential-free https URL on the stated origin")
        return self


class ViewOffer(BaseModel):
    """A URL the person may open in the external browser, never a session.

    ``offer_id`` is 32 lower-case hex characters minted by the worker. The
    desktop host keeps ``url`` and gives the page only ``offer_id``; opening
    sends the id back and the host revalidates the URL before handing it to
    the system browser.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    offer_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    url: str = Field(min_length=1, max_length=VIEW_MAX_URL_LENGTH)

    @model_validator(mode="after")
    def _web_url(self) -> Self:
        parts = urlsplit(self.url)
        if (
            parts.scheme not in {"https", "http"}
            or parts.hostname in {None, ""}
            or parts.username is not None
            or parts.password is not None
            or _has_control_character(self.url)
            or " " in self.url
        ):
            raise ValueError("offer url must be a credential-free http or https URL")
        return self


class ViewDialogPrompt(BaseModel):
    """A page dialog waiting for the person's answer under its ``dialog_id``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    dialog_id: _DialogId
    dialog_kind: ViewDialogKind
    message: str = Field(max_length=VIEW_MAX_DIALOG_MESSAGE_LENGTH)
    default_prompt: str | None = Field(default=None, max_length=VIEW_MAX_PROMPT_TEXT_LENGTH)

    @model_validator(mode="after")
    def _prompt_default_only_for_prompts(self) -> Self:
        if self.default_prompt is not None and self.dialog_kind is not ViewDialogKind.PROMPT:
            raise ValueError("only a prompt dialog carries a default answer")
        return self


class ViewNotice(BaseModel):
    """One closed notice; an offer code carries exactly one offer, ``dialog_opened`` one dialog."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.notice"] = "view.notice"
    code: ViewNoticeCode
    offer: ViewOffer | None = None
    dialog: ViewDialogPrompt | None = None

    @model_validator(mode="after")
    def _members_follow_code(self) -> Self:
        if (self.offer is not None) != (self.code in VIEW_OFFER_NOTICE_CODES):
            raise ValueError("an offer accompanies exactly the offer codes")
        if (self.dialog is not None) != (self.code is ViewNoticeCode.DIALOG_OPENED):
            raise ValueError("a dialog accompanies exactly dialog_opened")
        return self


class ViewClosed(BaseModel):
    """The last document on a view connection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.closed"] = "view.closed"
    reason: ViewClosedReason


class ViewCredit(BaseModel):
    """Grant the producer more images after drawing; outstanding credit never exceeds two.

    A view connection starts with no credit, so the window grants its first
    credit after attaching.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.credit"] = "view.credit"
    images: int = Field(ge=1, le=VIEW_CREDIT_MAX_IMAGES)


class PointerAction(StrEnum):
    """Pointer actions, translated to CDP ``mousePressed``, ``mouseReleased`` and ``mouseMoved``."""

    DOWN = "down"
    UP = "up"
    MOVE = "move"


class PointerButton(StrEnum):
    """Pointer buttons as CDP spells them."""

    NONE = "none"
    LEFT = "left"
    MIDDLE = "middle"
    RIGHT = "right"


class KeyAction(StrEnum):
    """Key actions, translated to CDP ``keyDown`` and ``keyUp``."""

    DOWN = "down"
    UP = "up"


class PointerInput(BaseModel):
    """A pointer event at CSS pixel coordinates within the panel."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    type: Literal["pointer"] = "pointer"
    action: PointerAction
    x: _Coordinate
    y: _Coordinate
    button: PointerButton
    click_count: int = Field(ge=0, le=VIEW_MAX_CLICK_COUNT)
    modifiers: _Modifiers

    @model_validator(mode="after")
    def _press_names_a_button(self) -> Self:
        if self.action is PointerAction.MOVE:
            if self.click_count != 0:
                raise ValueError("a move carries no click count")
        elif self.button is PointerButton.NONE or self.click_count < 1:
            raise ValueError("a press or release names a button and a click count")
        return self


class WheelInput(BaseModel):
    """A wheel scroll at CSS pixel coordinates, with deltas in CSS pixels."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    type: Literal["wheel"] = "wheel"
    x: _Coordinate
    y: _Coordinate
    delta_x: int = Field(ge=-VIEW_MAX_WHEEL_DELTA, le=VIEW_MAX_WHEEL_DELTA)
    delta_y: int = Field(ge=-VIEW_MAX_WHEEL_DELTA, le=VIEW_MAX_WHEEL_DELTA)
    modifiers: _Modifiers


class KeyInput(BaseModel):
    """A key event with its DOM ``key`` and ``code`` values; printable text arrives as text input."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    type: Literal["key"] = "key"
    action: KeyAction
    key: str = Field(min_length=1, max_length=VIEW_MAX_KEY_LENGTH)
    code: str = Field(max_length=VIEW_MAX_KEY_LENGTH)
    modifiers: _Modifiers

    @model_validator(mode="after")
    def _printable_names(self) -> Self:
        if _has_control_character(self.key + self.code):
            raise ValueError("key names carry no control characters")
        return self


class TextInput(BaseModel):
    """Text inserted at the focus, translated to CDP ``Input.insertText``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    type: Literal["text"] = "text"
    text: str = Field(min_length=1, max_length=VIEW_MAX_TEXT_INPUT_LENGTH)

    @model_validator(mode="after")
    def _printable_text(self) -> Self:
        if _has_control_character(self.text):
            raise ValueError("text input carries no control characters")
        return self


type ViewInputEvent = Annotated[PointerInput | WheelInput | KeyInput | TextInput, Field(discriminator="type")]


class ViewInput(BaseModel):
    """One person input event for the view's page."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.input"] = "view.input"
    event: ViewInputEvent


class ViewNavigateVerb(StrEnum):
    """The toolbar's navigation verbs; ``home`` opens the Sede start page."""

    BACK = "back"
    FORWARD = "forward"
    RELOAD = "reload"
    HOME = "home"


class ViewNavigate(BaseModel):
    """A toolbar navigation; the view never accepts a URL from the window."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.navigate"] = "view.navigate"
    verb: ViewNavigateVerb


class ViewResize(BaseModel):
    """The panel's new CSS size and device pixel ratio."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.resize"] = "view.resize"
    css_width: _Extent
    css_height: _Extent
    scale: _Scale


class ViewDialog(BaseModel):
    """The person's answer to the dialog announced under ``dialog_id``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.dialog"] = "view.dialog"
    dialog_id: _DialogId
    accept: bool
    prompt_text: str | None = Field(default=None, max_length=VIEW_MAX_PROMPT_TEXT_LENGTH)

    @model_validator(mode="after")
    def _text_only_when_accepting(self) -> Self:
        if self.prompt_text is not None and not self.accept:
            raise ValueError("a dismissed dialog carries no answer text")
        return self


class ViewClose(BaseModel):
    """The person closed the page or the window: end the view and publish its session.

    Closing is not a cancellation. The view stops taking input, publishes its
    session through the canonical custody path and settles; a view connection
    that drops without this document is closed the same way.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.close"] = "view.close"


type ViewDownstreamDocument = ViewImage | ViewState | ViewNotice | ViewClosed
type ViewUpstreamDocument = ViewCredit | ViewInput | ViewNavigate | ViewResize | ViewDialog | ViewClose


class ViewDownstreamFrame(RootModel[Annotated[ViewDownstreamDocument, Field(discriminator="kind")]]):
    """The closed set of control documents sent toward the window."""


class ViewUpstreamFrame(RootModel[Annotated[ViewUpstreamDocument, Field(discriminator="kind")]]):
    """The closed set of control documents sent from the window."""


SEDE_VIEW_DEFINITION_ID: Final = "live.sede.view"
"""The one registered operation whose worker may open a view stream."""

VIEW_ATTACH_TOKEN_BYTES = 32
"""CSPRNG bytes in one attach token; it travels as 64 lower-case hex characters."""

VIEW_ATTACH_TOKEN_SECONDS: Final = 10
"""How long an attach token stays presentable after it is issued."""

type _AttachToken = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ViewAttachRequest(BaseModel):
    """Ask, on the window's person connection, to attach a view connection to a running view.

    The runtime grants it only to the admitted desktop session that submitted
    the ``live.sede.view`` operation named here, on the same profile and
    native peer, and only while that operation's worker holds its view open.
    The reply is ``view_attach_granted`` or an ``access_refusal``.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["view_attach"] = "view_attach"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    operation_id: OperationId


class ViewAttachGranted(BaseModel):
    """A single-use attach token for one new view connection.

    The token is bound to the exact session, profile, native peer, runtime
    boot and operation of the request. It is spent by its first presentation,
    accepted or not, and refused after ``expires_in_seconds``. It is never
    logged, journaled or persisted.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view_attach_granted"] = "view_attach_granted"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    operation_id: OperationId
    attach_token: _AttachToken
    expires_in_seconds: Literal[10] = VIEW_ATTACH_TOKEN_SECONDS


class ViewConnect(BaseModel):
    """The first request on a new runtime connection, turning it into a view connection.

    It is refused anywhere but first. The connection must come from the same
    native peer as the person connection that asked for the token. The reply
    is ``view_connected``, after which the connection carries only the view
    stream: ``view.*`` documents in ``J`` frames and image chunks in ``B``
    frames toward the window, and upstream ``view.*`` documents from it. Any
    refusal is an ``access_refusal`` followed by the connection's close.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["view_connect"] = "view_connect"
    request_id: UUID
    operation_id: OperationId
    attach_token: _AttachToken


class ViewConnected(BaseModel):
    """The view connection is bound to its operation; the stream follows with no credit granted."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view_connected"] = "view_connected"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    operation_id: OperationId


class ViewWorkerBind(BaseModel):
    """The profile worker's first document on its view channel, naming the one view it serves.

    The worker listens for its view channel only while a ``live.sede.view``
    operation it owns runs. The runtime host connects when a window first
    attaches, verifies the worker process natively, and reads this document
    to learn which operation and submitting session the channel serves.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.bind"] = "view.bind"
    definition_id: Literal["live.sede.view"] = SEDE_VIEW_DEFINITION_ID
    operation_id: OperationId
    session_id: UUID


type ViewPersonInput = ViewInput | ViewNavigate | ViewResize | ViewDialog | ViewClose
"""Upstream documents the view's executor acts on; credit is consumed by the sink itself."""

type ViewSinkInput = ViewPersonInput | ViewTransferEvent
"""Everything ``ViewStreamSink.receive`` returns: person input and the window's transfer answers."""


class ViewStreamSink(Protocol):
    """The worker-side port through which a ``live.sede.view`` executor reaches its view stream.

    The worker's operation host composes one sink per view into the
    operation context; the tax application never sees the channel behind it.
    Every method is thread-safe and none blocks on the window: ``offer_image``
    keeps only the newest image not yet sent and sends it when the window has
    credit, ``send`` drops a document once its small bounded queue is full,
    and ``receive`` returns person input or ``None`` when ``timeout`` passes.
    Images, documents and input are private taxpayer data and stay in memory.

    ``connected`` says whether the runtime host holds the view channel now; it
    connects when a window attaches. ``ended`` turns true once the host closed
    the channel, which it does when the submitting session is retired or
    locked, the runtime stops, or a protocol violation occurs; the executor
    must then end the view without publishing. A window that closes the view
    sends ``view.close``, which ``receive`` returns; the host sends the same
    document when the window's view connection drops without it.

    Transfers travel on the same channel. ``send`` also carries the
    ``view.download`` and ``view.file_chooser`` requests; ``receive`` returns
    the window's answers, the files it supplied, received whole and checked
    against their digest, and its cancels. ``send_download`` streams one
    accepted download under the window's transfer credit, and
    ``cancel_download`` stops it from the worker side. ``close`` ends the view from the worker side: it
    sends ``view.closed`` with ``reason`` and returns only after the host has
    unbound the window, or after a short bound when the host does not answer,
    so the operation settles only after unbinding.
    """

    @property
    def connected(self) -> bool:
        """Whether the runtime host holds the view channel."""
        ...

    @property
    def ended(self) -> bool:
        """Whether the view channel ended; the view must then end."""
        ...

    def offer_image(self, announcement: ViewImage, image: bytes) -> None:
        """Make this the newest pending image, replacing any older one not yet sent."""
        ...

    def send(self, document: ViewState | ViewNotice | ViewDownload | ViewFileChooser | ViewTransferCancel) -> None:
        """Queue one page document, or one transfer request or cancel, for the window."""
        ...

    def receive(self, *, timeout: float) -> ViewSinkInput | None:
        """Return the next person input or transfer event, or ``None`` after ``timeout`` seconds or once ended."""
        ...

    def send_download(self, transfer_id: int, source: ViewTransferByteSource) -> bool:
        """Stream an accepted download's bytes, blocking until its completion is sent.

        Returns ``False`` when the window cancels the transfer, the worker
        cancels it with :meth:`cancel_download`, or the view ends first. One
        download streams at a time; a second call waits its turn.
        """
        ...

    def cancel_download(self, transfer_id: int) -> None:
        """Stop the download ``transfer_id`` from the worker side and tell the window.

        A ``send_download`` streaming it, or waiting its turn to, returns
        ``False`` promptly, so its caller can release the source. A later call
        for the same transfer returns ``False`` at once.
        """
        ...

    def close(self, reason: ViewClosedReason) -> None:
        """End the view stream and wait for the host to unbind it."""
        ...


class ViewStreamSinks(Protocol):
    """Open the one view stream a worker may hold at a time, for its running view operation."""

    def open_view(self, *, operation_id: OperationId, session_id: UUID) -> ViewStreamSink:
        """Start listening for the host's view channel for this operation and session."""
        ...
