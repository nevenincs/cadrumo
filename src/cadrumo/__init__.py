"""Import-light root package for Cadrumo.

The package root exposes only the distribution ``__version__``. Concrete
capabilities live behind layer facades: :mod:`core` for shared primitives
and runtime context, :mod:`domain` for business authorities,
:mod:`application` for use-case orchestration, :mod:`adapters` for
inbound, outbound, and persistence infrastructure, and :mod:`entrypoints`
for operator transports such as the Typer CLI.

Importing ``cadrumo`` must not configure logging, load registries, open storage, or
materialise browser/PDF integrations. The ``pikepdf._core`` bridge logger is
silenced via the ``loggers`` block in
:func:`core.logging.configure_logging` rather than by bootstrap-time side
effects here, keeping logger policy in one auditable location.

See Also:
    :mod:`core.resources`
        Bundled registry and corpus resource boundary used after a concrete
        capability imports the relevant layer.
    :mod:`core.logging`
        Central logging configuration surface kept out of package import
        side effects.
    :mod:`application.operator_surface`
        Backend-owned capability contract for operator and automation surfaces.
"""

__version__ = "0.3.0"
