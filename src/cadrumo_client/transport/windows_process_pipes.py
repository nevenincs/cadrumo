"""Private standard pipes for contained Windows child processes."""

from __future__ import annotations

import os
import sys
from typing import BinaryIO, cast

from ..contracts.contracts import RefusalCode, RefusalError
from .windows_native_io import NativeWindowsHandle, native_windows_call, owned_windows_handle


def _pipe_ends(attributes: object) -> tuple[NativeWindowsHandle, NativeWindowsHandle]:
    """Retain both native pipe handles and release the first if the second is refused."""
    import win32pipe

    values = native_windows_call(win32pipe, "CreatePipe", attributes, 0)
    if not isinstance(values, tuple):
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    values = cast("tuple[object, ...]", values)
    if len(values) != 2:
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    read = owned_windows_handle(values[0])
    try:
        write = owned_windows_handle(values[1])
    except BaseException:
        read.Close()
        raise
    return read, write


def windows_standard_pipes() -> tuple[tuple[NativeWindowsHandle, ...], tuple[NativeWindowsHandle, ...]]:
    """Create inheritable child ends and private parent ends for a launch.

    Return the child's standard input, output and error ends, then the
    parent's write end of standard input and read ends of standard output and
    standard error.
    """
    if sys.platform != "win32":
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    import pywintypes
    import win32api

    attributes = pywintypes.SECURITY_ATTRIBUTES()
    attributes.bInheritHandle = True
    created: list[NativeWindowsHandle] = []
    try:
        input_read, input_write = _pipe_ends(attributes)
        created.extend((input_read, input_write))
        output_read, output_write = _pipe_ends(attributes)
        created.extend((output_read, output_write))
        error_read, error_write = _pipe_ends(attributes)
        created.extend((error_read, error_write))
        for parent_end in (input_write, output_read, error_read):
            # HANDLE_FLAG_INHERIT cleared: the parent ends never reach any child.
            win32api.SetHandleInformation(int(parent_end), 1, 0)
    except BaseException:
        for handle in created:
            handle.Close()
        raise
    return (input_read, output_write, error_write), (input_write, output_read, error_read)


def windows_parent_streams(parent_ends: tuple[NativeWindowsHandle, ...]) -> tuple[BinaryIO, BinaryIO, BinaryIO]:
    """Turn the parent's standard-input, output and error ends into streams, releasing every end on failure."""
    streams: list[BinaryIO] = []
    try:
        for end, mode in zip(parent_ends, ("wb", "rb", "rb"), strict=True):
            streams.append(_python_stream(end, mode))
    except BaseException:
        for stream in streams:
            stream.close()
        for end in parent_ends[len(streams) :]:
            end.Close()
        raise
    standard_input, standard_output, standard_error = streams
    return standard_input, standard_output, standard_error


def _python_stream(handle: NativeWindowsHandle, mode: str) -> BinaryIO:
    """Transfer one native pipe end into an unbuffered Python binary stream."""
    if sys.platform != "win32":
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    import msvcrt

    import win32api

    flags = os.O_WRONLY if "w" in mode else os.O_RDONLY
    detached = native_windows_call(handle, "Detach")
    if type(detached) is not int or detached <= 0:
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    try:
        descriptor = msvcrt.open_osfhandle(detached, flags | os.O_BINARY)
    except BaseException:
        win32api.CloseHandle(detached)
        raise
    try:
        return cast("BinaryIO", os.fdopen(descriptor, mode, buffering=0))
    except BaseException:
        os.close(descriptor)
        raise
