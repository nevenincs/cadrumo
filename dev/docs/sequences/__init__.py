"""The ``cli-sequence`` documentation execution engine (docs tooling).

This package is the one hermetic engine behind the ``cli-sequence`` MyST
directive: it parses a directive body into typed frames, executes each frame in a
per-sequence sandbox, compares the result against a committed golden, and drives
the refresh / check CLI. It lives under ``dev/docs`` (dev-only docs tooling,
kept separate from the shipped product) and imports the production ``cadrumo``
package from outside.

This module exposes the frame-grammar parser, the ``:seed:`` recipe loader,
the per-sequence hermetic sandbox runner with ``@capture`` threading, the
committed golden store, the golden comparison plus ``@expect`` evaluation
tier, the discovery/refresh/check engine functions behind
``python -m dev.docs.sequences`` — the one execution path the Sphinx build
hook and the pytest gate both wire — the build-time command-line tokeniser,
the static live-AEAT enrollment refusal (``refuse_live_frames`` /
``live_aeat_tokens``), and the ``@static`` blocked-reason taxonomy
(``StaticBlocker`` / ``BlockedReason``) that keeps a non-executed frame's
justification stated and cross-checkable.

Every symbol this package defines is imported from the module that defines it;
this initialiser is an inert namespace marker and forwards nothing.
"""
