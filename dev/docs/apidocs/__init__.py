"""API-reference stub maintenance for the documentation toolchain.

Keeps the generated ``docs/api/*.rst`` stub tree in sync with the
``src/aeat/`` module tree. The CLI (``python -m dev.docs.apidocs``) exposes
``scaffold`` (regenerate every stub, creating missing ones and removing
orphans whose module is gone), ``scaffold --check`` (the drift gate), and
``audit`` (a stub-health report). The stubs are generated, never
hand-authored; regenerate them instead of editing.

Major declarations:

* :class:`ApiStubManager` — discovers modules and writes, checks, and
  audits the stub tree.
* :class:`ApiDocsError` — raised when the stub directory cannot be managed.
"""

from __future__ import annotations

from .manager import ApiDocsError, ApiStubManager

__all__ = ["ApiDocsError", "ApiStubManager"]
