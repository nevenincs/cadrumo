"""AEAT - Spanish Tax Authority automation tools.

Tools for interacting with the Agencia Estatal de Administracion Tributaria (AEAT),
managing tax information, and automating tax filing workflows.
"""

import logging as _logging

# Silence pikepdf's C++-to-Python logger bridge INFO message that
# fires at first pikepdf import. Without this, the bridge init line
# ("pikepdf C++ to Python logger bridge initialized") lands on
# stderr before the CLI's JSON output contract (#399) takes over,
# contaminating any pipeline that asserts a clean JSON envelope on
# stderr. Configuring the logger here — at the package root, before
# any submodule (and therefore any pikepdf transitive import) loads
# — guarantees the level is set before the bridge fires. Does not
# touch pikepdf's WARNING/ERROR levels; real pikepdf failures still
# log normally.
_logging.getLogger("pikepdf._core").setLevel(_logging.WARNING)

__version__ = "0.1.0"
