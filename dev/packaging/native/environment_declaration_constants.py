"""Schema constants for application environment declarations."""

import re

SCHEMA = 1

NAME_KINDS = frozenset(
    {
        "text",
        "language",
        "boolean",
        "integer",
        "number",
        "directory",
        "file",
        "directory_list",
        "port",
        "executable",
        "descriptor",
    }
)
NAME_ROLES = frozenset({"location", "operator", "package", "pin", "fixed", "slot", "pass"})
NUMERIC_ARGUMENT_KINDS = frozenset({"handle", "descriptor"})
ARGUMENT_KINDS = NUMERIC_ARGUMENT_KINDS | {"revision", "identifier"}
OPTION_KINDS = frozenset({"revision"})
BASE_GROUPS = ("system", "session", "terminal", "display", "network")
PLATFORMS = ("windows", "posix")
PATH_ENTRIES = frozenset({"executable", "external", "native", "external_defaults", "system"})
PIN_KINDS = ("root", "temporary", "authority")

# Declared names reach C and Rust string literals and process environments unescaped.
_NAME = re.compile(r"[A-Z][A-Z0-9_]*")
# Operating-system names keep their platform spelling, such as PROGRAMFILES(X86) or http_proxy.
_BASE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\([A-Za-z0-9]+\))?")
_PROFILE = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)*")
_SLOT = re.compile(r"[a-z][a-z0-9_]*")
# Literal arguments become C and Rust string literals; keep them printable ASCII without quotes.
_LITERAL = re.compile(r"[A-Za-z0-9_.:/=+-]+")
_OPTION = re.compile(r"--[a-z][a-z0-9]*(-[a-z0-9]+)*")
# An opaque revision is bounded printable ASCII that cannot be read as an option or a path.
_REVISION = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,63}")
_PATH_COMPONENT = re.compile(r"[A-Za-z0-9._-]+")
