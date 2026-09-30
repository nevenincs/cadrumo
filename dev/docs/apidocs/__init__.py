"""API-reference stub generation for the documentation toolchain.

Writes the ``docs/api/*.rst`` automodule stubs from the ``src/cadrumo/``
module tree. A full-scope documentation build generates them at
``builder-inited`` into the source tree it reads, so they are build output
and never committed.

``ApiStubManager`` and ``ApiDocsError`` are defined in and imported from
:mod:`dev.docs.apidocs.manager`; this initialiser forwards nothing.
"""
