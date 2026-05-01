"""Top-level package for the AEAT (Agencia Estatal de Administración Tributaria) toolkit.

Exposes the :data:`__version__` of the distribution and silences the
``pikepdf._core`` bridge logger at package import time so the CLI's
machine-readable stderr envelope is never contaminated by pikepdf's
INFO-level initialisation message. Subpackages provide the layered
architecture: :mod:`aeat.adapters` (inbound / outbound integrations),
:mod:`aeat.application` (use-cases), :mod:`aeat.domain` (pure rules),
:mod:`aeat.entrypoints` (CLI / scripts), and :mod:`aeat.core`
(cross-cutting infrastructure).
"""

import logging as _logging

# Silence pikepdf's C++-to-Python logger bridge INFO message that
# fires at first pikepdf import. Without this, the bridge init line
# ("pikepdf C++ to Python logger bridge initialized") lands on
# stderr before the CLI's JSON output contract takes over,
# contaminating any pipeline that asserts a clean JSON envelope on
# stderr. Configuring the logger here — at the package root, before
# any submodule (and therefore any pikepdf transitive import) loads
# — guarantees the level is set before the bridge fires. Does not
# touch pikepdf's WARNING/ERROR levels; real pikepdf failures still
# log normally.
_logging.getLogger("pikepdf._core").setLevel(_logging.WARNING)

__version__ = "0.1.0"
