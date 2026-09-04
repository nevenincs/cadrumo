"""API-reference stub maintenance for the documentation toolchain.

Keeps the generated ``docs/api/*.rst`` stub tree in sync with the
``src/cadrumo/`` module tree. The CLI (``python -m dev.docs.apidocs``) exposes
``scaffold`` (regenerate every stub, creating missing ones and removing
orphans whose module is gone), ``scaffold --check`` (the drift gate), and
``audit`` (a stub-health report). The stubs are generated, never
hand-authored; regenerate them instead of editing.

``ApiStubManager`` and ``ApiDocsError`` are defined in and imported from
:mod:`dev.docs.apidocs.manager`; this initialiser forwards nothing.
"""
