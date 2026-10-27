"""Closed control documents of the Sede view stream's file transfers.

A download carries a file from the page toward the window, an upload carries
the file the person chose toward the page. Both travel on the view connection
that carries the images: a ``J`` document announces and closes each transfer,
and ``B`` chunks, whose framing the transport's view codec owns, carry its
bytes. The sender of the bytes allocates the transfer id; ids strictly
increase per direction on a connection and may skip values.

Downstream, toward the window: ``view.download`` offers a download and
``view.file_chooser`` asks for the files the page wants. Upstream, from the
window: ``view.download_answer`` accepts, refuses or cancels an offer,
``view.file_chooser_answer`` supplies files or cancels, and ``view.upload``
describes each supplied file. ``view.transfer_complete`` closes a transfer
after its last chunk, ``view.transfer_credit`` lets the receiver of the bytes
admit more chunks, and ``view.transfer_cancel`` stops a transfer from either
end, in either direction; they travel both ways. Every set is closed: an
unknown kind, member or value refuses the frame, and a refused frame ends the
view connection.

A transfer has its own credit, counted in chunks, so a file never waits on an
image and an image never waits behind more than one credit window of file
bytes. Credit bounds only what is in flight. It never limits how much a person
downloads or uploads: no document here caps a file's size, a file count or a
rate. The bounds below keep a frame well formed.

File names, sizes and bytes are private taxpayer data. These documents live
in memory only; they are never logged, persisted, journaled or projected.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, Field, RootModel, model_validator

from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

from .view_stream import ViewDownstreamDocument, ViewUpstreamDocument

VIEW_TRANSFER_CREDIT_MAX_CHUNKS = 32
"""The most chunks a receiver may have admitted and not yet seen, per transfer.

At 65,520 bytes a chunk this is about 2 MiB in flight, the size of one image.
"""

VIEW_MAX_TRANSFER_ID = 2**32 - 1
"""Transfer and file chooser ids are unsigned 32-bit numbers."""

VIEW_MAX_TRANSFER_SIZE = 2**64 - 1
"""A transfer's size is an unsigned 64-bit number of bytes."""

VIEW_MAX_FILENAME_LENGTH = 255
VIEW_MAX_MIME_LENGTH = 255
VIEW_MAX_ACCEPT_ENTRIES = 128


def _plain_filename(name: str) -> str:
    if name in {".", ".."}:
        raise ValueError("a file name names a file, not a directory entry")
    return name


type _TransferId = Annotated[int, Field(ge=1, le=VIEW_MAX_TRANSFER_ID)]
type _TransferSize = Annotated[int, Field(ge=0, le=VIEW_MAX_TRANSFER_SIZE)]
type _Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type _Filename = Annotated[
    str,
    Field(min_length=1, max_length=VIEW_MAX_FILENAME_LENGTH, pattern=r"^[^\x00-\x1f\x7f/\\]+$"),
    AfterValidator(_plain_filename),
]
type _MimeType = Annotated[
    str,
    Field(
        min_length=3,
        max_length=VIEW_MAX_MIME_LENGTH,
        pattern=r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$",
    ),
]
type _AcceptToken = Annotated[
    str, Field(min_length=1, max_length=VIEW_MAX_MIME_LENGTH, pattern=r"^[A-Za-z0-9!#$&^_.+*/-]+$")
]


class ViewTransferDirection(StrEnum):
    """Which way a transfer's bytes travel."""

    DOWNLOAD = "download"
    """From the page toward the window."""
    UPLOAD = "upload"
    """From the window toward the page."""


class ViewDownloadOutcome(StrEnum):
    """The window's answer to a download offer."""

    ACCEPTED = "accepted"
    """The person chose a path in the native save dialog; the bytes may flow once credit arrives."""
    REFUSED = "refused"
    """The host declined the file; no bytes will be sent."""
    CANCELLED = "cancelled"
    """The person closed the save dialog; no bytes will be sent."""


class ViewFileChooserOutcome(StrEnum):
    """The window's answer to a file chooser request."""

    SUPPLIED = "supplied"
    """The person chose files; one ``view.upload`` per file follows."""
    CANCELLED = "cancelled"
    """The person closed the open dialog."""


class ViewDownload(BaseModel):
    """Offer a download to the person; its bytes flow only after the window accepts.

    ``filename`` is a hint for the native save dialog and never a path.
    ``size`` is the byte count when the browser knows it up front and is only
    a hint for progress; the completion document carries the size that counts.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.download"] = "view.download"
    transfer_id: _TransferId
    filename: _Filename
    size: _TransferSize | None = None
    mime: _MimeType | None = None


class ViewFileChooser(BaseModel):
    """The page asks for files; the window answers under ``chooser_id``.

    ``accept`` lists the page's accepted types, extensions such as ``.pdf`` or
    media types such as ``image/*``, and is empty when the page names none.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.file_chooser"] = "view.file_chooser"
    chooser_id: _TransferId
    accept: tuple[_AcceptToken, ...] = Field(max_length=VIEW_MAX_ACCEPT_ENTRIES)
    multiple: bool


class ViewDownloadAnswer(BaseModel):
    """Accept, refuse or cancel the download offered under ``transfer_id``.

    It is the first and only answer to an offer. Stopping an accepted
    download in flight is ``view.transfer_cancel``.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.download_answer"] = "view.download_answer"
    transfer_id: _TransferId
    outcome: ViewDownloadOutcome


class ViewFileChooserAnswer(BaseModel):
    """Supply files for the chooser, or cancel it.

    A supplied answer names how many files follow, at least one and exactly
    one when the chooser was not ``multiple``; each file then travels as a
    ``view.upload`` and its chunks. A cancelled answer supplies none.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.file_chooser_answer"] = "view.file_chooser_answer"
    chooser_id: _TransferId
    outcome: ViewFileChooserOutcome
    file_count: int = Field(ge=0, le=VIEW_MAX_TRANSFER_ID)

    @model_validator(mode="after")
    def _count_follows_outcome(self) -> Self:
        if (self.outcome is ViewFileChooserOutcome.SUPPLIED) != (self.file_count > 0):
            raise ValueError("a supplied answer names at least one file and a cancelled one none")
        return self


class ViewUpload(BaseModel):
    """Describe one file supplied for the chooser; its chunks and completion follow.

    ``size`` is the file's exact byte count; the receiver refuses an upload
    whose bytes differ from it.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.upload"] = "view.upload"
    chooser_id: _TransferId
    transfer_id: _TransferId
    name: _Filename
    size: _TransferSize
    mime: _MimeType | None = None


class ViewTransferComplete(BaseModel):
    """The sender's close of a transfer: the exact size and sha256 of every byte it sent.

    The receiver refuses the transfer unless both equal what it received.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.transfer_complete"] = "view.transfer_complete"
    transfer_id: _TransferId
    size: _TransferSize
    sha256: _Sha256


class ViewTransferCredit(BaseModel):
    """Admit more chunks of a transfer; outstanding credit never exceeds the window.

    A transfer starts with no credit, so the receiver grants its first credit
    once it can take the bytes.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.transfer_credit"] = "view.transfer_credit"
    transfer_id: _TransferId
    chunks: int = Field(ge=1, le=VIEW_TRANSFER_CREDIT_MAX_CHUNKS)


class ViewTransferCancel(BaseModel):
    """Stop a transfer, from either end.

    ``direction`` says which way the transfer's bytes travel, because the two
    ends allocate ids independently. The sender of the bytes cancels to stop
    sending. The receiver cancels to stop receiving, and the sender answers
    with its own cancel unless it already sent ``view.transfer_complete``;
    chunks that cross the cancel are discarded.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["view.transfer_cancel"] = "view.transfer_cancel"
    direction: ViewTransferDirection
    transfer_id: _TransferId


type ViewTransferDownstreamDocument = (
    ViewDownload | ViewFileChooser | ViewTransferComplete | ViewTransferCredit | ViewTransferCancel
)
type ViewTransferUpstreamDocument = (
    ViewDownloadAnswer
    | ViewFileChooserAnswer
    | ViewUpload
    | ViewTransferComplete
    | ViewTransferCredit
    | ViewTransferCancel
)

type ViewConnectionDownstreamDocument = ViewDownstreamDocument | ViewTransferDownstreamDocument
type ViewConnectionUpstreamDocument = ViewUpstreamDocument | ViewTransferUpstreamDocument


class ViewConnectionDownstreamFrame(
    RootModel[Annotated[ViewConnectionDownstreamDocument, Field(discriminator="kind")]]
):
    """Everything a view connection that carries transfers sends toward the window."""


class ViewConnectionUpstreamFrame(RootModel[Annotated[ViewConnectionUpstreamDocument, Field(discriminator="kind")]]):
    """Everything a view connection that carries transfers sends from the window."""
