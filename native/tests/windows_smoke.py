"""Windows PE resources and public COM extension acceptance."""

import ctypes
import sys

from win32com.shell import shell


def require(condition, message):
    """Keep acceptance assertions active in optimized interpreters."""
    if not condition:
        raise AssertionError(message)


require(bool(shell.__file__), "COM extension did not load")
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.LoadLibraryExW.argtypes = (ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint)
kernel.LoadLibraryExW.restype = ctypes.c_void_p
kernel.FindResourceW.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
kernel.FindResourceW.restype = ctypes.c_void_p
kernel.FreeLibrary.argtypes = (ctypes.c_void_p,)
handle = kernel.LoadLibraryExW(sys.executable, None, 2)
require(bool(handle), "Cannot inspect PE resources")
try:
    require(bool(kernel.FindResourceW(handle, 1, 14)), "Missing executable icon")
    require(bool(kernel.FindResourceW(handle, 1, 16)), "Missing executable version resource")
finally:
    kernel.FreeLibrary(handle)
