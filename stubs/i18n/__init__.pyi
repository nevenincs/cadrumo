# Stub for `python-i18n`, which ships no `py.typed` and has no `types-*`
# distribution on PyPI. Only the three names `core/i18n/render.py` actually
# uses are declared: an over-broad stub would assert a surface nobody verified.
#
# `load_path` is the mutable search-path list the backend appends locale
# directories to; `set` writes one backend setting; `t` resolves a key,
# falling back to the configured fallback locale and finally to the key
# itself, so it always returns a string.

load_path: list[str]

def set(key: str, value: object) -> None: ...
# `t` returns the translated string, or the key itself when nothing matches --
# but it also returns `kwargs['default']` verbatim when that is supplied, and
# a caller may pass any object as the default. `str` was too narrow: it made
# the caller's own isinstance guard read as dead code.
def t(key: str, **kwargs: object) -> object: ...
