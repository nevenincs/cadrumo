"""Owned Core Foundation Create/Copy values and strictly decoded native data."""

from __future__ import annotations

import ctypes
from collections.abc import Generator
from contextlib import contextmanager
from typing import cast

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
)
from .macos_keychain_contracts import CORE_FOUNDATION, MAX_SECRET_BYTES, UTF8, NativeKeychainFunction
from .macos_keychain_policy import keychain_refusal
from .zeroise import zeroise


class _DictionaryKeyCallbacks(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_long),
        ("retain", ctypes.c_void_p),
        ("release", ctypes.c_void_p),
        ("description", ctypes.c_void_p),
        ("equal", ctypes.c_void_p),
        ("hash", ctypes.c_void_p),
    ]


class _DictionaryValueCallbacks(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_long),
        ("retain", ctypes.c_void_p),
        ("release", ctypes.c_void_p),
        ("description", ctypes.c_void_p),
        ("equal", ctypes.c_void_p),
    ]


def bind_native_function(library: ctypes.CDLL, name: str, args: list[object], result: object) -> NativeKeychainFunction:
    """Bind one named native symbol with its exact argument and result ABI."""
    function = cast(NativeKeychainFunction, getattr(library, name))
    function.argtypes = args
    function.restype = result
    return function


def native_integer(value: int | None) -> int:
    """Require an integer native result before using it as status, length or pointer."""
    if value is None:
        raise keychain_refusal()
    return value


class CoreFoundation:
    """Small typed CF bridge with ownership explicit at each Create/Copy."""

    def __init__(self) -> None:
        """Bind the owned Core Foundation bridge and canonical runtime type identifiers."""
        self.library = ctypes.CDLL(CORE_FOUNDATION)
        pointer = ctypes.c_void_p
        index = ctypes.c_long
        self.release = bind_native_function(self.library, "CFRelease", [pointer], None)
        self.type_id = bind_native_function(self.library, "CFGetTypeID", [pointer], ctypes.c_ulong)
        self.string_type = bind_native_function(self.library, "CFStringGetTypeID", [], ctypes.c_ulong)
        self.array_type = bind_native_function(self.library, "CFArrayGetTypeID", [], ctypes.c_ulong)
        self.data_type = bind_native_function(self.library, "CFDataGetTypeID", [], ctypes.c_ulong)
        self.dictionary_type = bind_native_function(self.library, "CFDictionaryGetTypeID", [], ctypes.c_ulong)
        self.number_type = bind_native_function(self.library, "CFNumberGetTypeID", [], ctypes.c_ulong)
        self.boolean_type = bind_native_function(self.library, "CFBooleanGetTypeID", [], ctypes.c_ulong)
        self.string_create = bind_native_function(
            self.library, "CFStringCreateWithBytes", [pointer, pointer, index, ctypes.c_uint32, ctypes.c_ubyte], pointer
        )
        self.string_length = bind_native_function(self.library, "CFStringGetLength", [pointer], index)
        self.string_get = bind_native_function(
            self.library, "CFStringGetCString", [pointer, pointer, index, ctypes.c_uint32], ctypes.c_ubyte
        )
        self.array_count = bind_native_function(self.library, "CFArrayGetCount", [pointer], index)
        self.array_get = bind_native_function(self.library, "CFArrayGetValueAtIndex", [pointer, index], pointer)
        self.array_create = bind_native_function(
            self.library, "CFArrayCreate", [pointer, pointer, index, pointer], pointer
        )
        self.dictionary_create = bind_native_function(
            self.library, "CFDictionaryCreateMutable", [pointer, index, pointer, pointer], pointer
        )
        self.dictionary_set = bind_native_function(
            self.library, "CFDictionarySetValue", [pointer, pointer, pointer], None
        )
        self.dictionary_get = bind_native_function(self.library, "CFDictionaryGetValue", [pointer, pointer], pointer)
        self.data_create = bind_native_function(self.library, "CFDataCreate", [pointer, pointer, index], pointer)
        self.data_length = bind_native_function(self.library, "CFDataGetLength", [pointer], index)
        self.data_pointer = bind_native_function(self.library, "CFDataGetBytePtr", [pointer], pointer)
        self.number_get = bind_native_function(
            self.library, "CFNumberGetValue", [pointer, ctypes.c_int, pointer], ctypes.c_ubyte
        )
        self.boolean_get = bind_native_function(self.library, "CFBooleanGetValue", [pointer], ctypes.c_ubyte)
        self.equal = bind_native_function(self.library, "CFEqual", [pointer, pointer], ctypes.c_ubyte)
        self.true = self.constant(self.library, "kCFBooleanTrue")
        self.false = self.constant(self.library, "kCFBooleanFalse")
        self.key_callbacks = _DictionaryKeyCallbacks.in_dll(self.library, "kCFTypeDictionaryKeyCallBacks")
        self.value_callbacks = _DictionaryValueCallbacks.in_dll(self.library, "kCFTypeDictionaryValueCallBacks")

    @staticmethod
    def constant(library: ctypes.CDLL, name: str) -> int:
        """Read one published nonnull native Core Foundation constant."""
        pointer = ctypes.c_void_p.in_dll(library, name).value
        if not pointer:
            raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)
        return pointer

    def require_type(self, pointer: int | None, expected: NativeKeychainFunction) -> int:
        """Admit a nonnull pointer only when its native type matches the expected identifier."""
        if not pointer or self.type_id(pointer) != expected():
            raise keychain_refusal()
        return pointer

    @contextmanager
    def string(self, value: str) -> Generator[int]:
        """Own one UTF-8 Core Foundation string until the calling scope settles."""
        encoded = value.encode("utf-8")
        pointer = native_integer(self.string_create(None, encoded, len(encoded), UTF8, 0))
        if not pointer:
            raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)
        try:
            yield pointer
        finally:
            self.release(pointer)

    def text(self, pointer: int | None) -> str:
        """Decode one bounded typed native string with exact UTF-8 round-trip meaning."""
        pointer = self.require_type(pointer, self.string_type)
        length = native_integer(self.string_length(pointer))
        if not 0 <= length <= 1024:
            raise keychain_refusal()
        buffer = ctypes.create_string_buffer(length * 4 + 1)
        if not self.string_get(pointer, buffer, len(buffer), UTF8):
            raise keychain_refusal()
        raw: object = buffer.value
        if not isinstance(raw, bytes):
            raise keychain_refusal()
        try:
            value = raw.decode("utf-8", errors="strict")
            # CFStringGetCString permits embedded NULs. Never accept a truncated
            # service/account as an exact identity match.
            if len(value.encode("utf-16-le")) // 2 != length:
                raise keychain_refusal()
            return value
        except UnicodeError:
            raise keychain_refusal() from None

    def strings(self, pointer: int | None) -> tuple[str, ...]:
        """Read all strings in one typed native array without dropping elements."""
        pointer = self.require_type(pointer, self.array_type)
        count = native_integer(self.array_count(pointer))
        if not 0 < count <= 32:
            raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)
        return tuple(self.text(self.array_get(pointer, index)) for index in range(count))

    def field(self, dictionary: int, key: int) -> int | None:
        """Read one borrowed typed dictionary member without taking its ownership."""
        self.require_type(dictionary, self.dictionary_type)
        return self.dictionary_get(dictionary, key)

    @contextmanager
    def array(self, values: tuple[int, ...]) -> Generator[int]:
        """Own an array while its already-owned native elements remain live."""
        elements = (ctypes.c_void_p * len(values))(*values)
        pointer = native_integer(self.array_create(None, elements, len(values), None))
        if not pointer:
            raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)
        try:
            yield pointer
        finally:
            self.release(pointer)

    def number(self, pointer: int | None) -> int:
        """Read one typed native number without changing its integer meaning."""
        pointer = self.require_type(pointer, self.number_type)
        value = ctypes.c_int64()
        if not self.number_get(pointer, 4, ctypes.byref(value)):
            raise keychain_refusal()
        return value.value

    def boolean(self, pointer: int | None) -> bool:
        """Read one typed native boolean and refuse any other value."""
        pointer = self.require_type(pointer, self.boolean_type)
        return bool(self.boolean_get(pointer))

    @contextmanager
    def dictionary(self) -> Generator[int]:
        """Own a fresh mutable native dictionary for this exact query or update."""
        pointer = native_integer(
            self.dictionary_create(None, 0, ctypes.byref(self.key_callbacks), ctypes.byref(self.value_callbacks))
        )
        if not pointer:
            raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)
        try:
            yield pointer
        finally:
            self.release(pointer)

    @contextmanager
    def data(self, raw: bytes) -> Generator[int]:
        """Own bounded native byte data and wipe its mutable staging copy on exit."""
        staging = bytearray(raw)
        array = (ctypes.c_ubyte * len(staging)).from_buffer(staging)
        try:
            pointer = native_integer(self.data_create(None, array, len(staging)))
            if not pointer:
                raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)
            try:
                yield pointer
            finally:
                self.release(pointer)
        finally:
            zeroise(staging)

    def read_data(self, pointer: int | None) -> bytes:
        """Read bytes only from a typed bounded native data object."""
        pointer = self.require_type(pointer, self.data_type)
        length = native_integer(self.data_length(pointer))
        address = self.data_pointer(pointer)
        if not 0 < length <= MAX_SECRET_BYTES or not address:
            raise keychain_refusal()
        return ctypes.string_at(address, length)
