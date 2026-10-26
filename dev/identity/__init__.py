"""Working-tree identity canary.

The scan that answers "did a real Spanish taxpayer identity reach this
repository" lives in :mod:`dev.identity._tree_scan`. Detection itself belongs to
:mod:`dev.sanitizer`; this package owns the surface (a working tree) and the
scope decision. See :mod:`dev.identity._tree_scan` for both arguments in full,
including why there is no value allowlist.

Only that scan reaches for the sanitiser, and so only it carries the ``pikepdf``
dependency. The other probes here -- the hex-64 and identifier censuses -- are
declaration readers that parse source with :mod:`ast` and need no PDF support.
"""
