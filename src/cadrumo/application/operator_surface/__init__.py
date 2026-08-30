"""Public re-export boundary for the backend-owned operator surface.

The package collects the application-layer command-shape declarations from
:mod:`application.operator_surface.contract`,
:mod:`application.operator_surface.models`,
:mod:`application.operator_surface.help`,
:mod:`application.operator_surface.crud_contract`,
:mod:`application.operator_surface.crud_registry`, and
:mod:`application.operator_surface.errors`. Command adapters consume this
surface as data and render it; they do not define a second contract.

Root-surface declarations flow through :func:`get_operator_surface_contract`,
:data:`ACCEPTED_ROOTS`, :data:`MOUNTED_COMMAND_FAMILIES`, and
:class:`OperatorSurfaceContract`. Source-kind aliases remain parser-only
:class:`SourceKindAlias` records that resolve through
:func:`resolve_source_kind_alias` to canonical
:class:`core.BindingSourceKind` members. No operator-specific source-kind
taxonomy is introduced here.

The CRUD vocabulary is exposed through :class:`CrudVerb`,
:data:`CANONICAL_CRUD_VERBS`, :class:`MutatingNounGroupContract`,
:class:`CrudContractCatalogue`, and :func:`get_builtin_catalogue`. Help and
landing surfaces are exposed through :func:`build_help_document`,
:func:`build_root_landing_report`, :class:`HelpDocument`, and
:class:`RootLandingReport`. Refused surfaces use the registered
:class:`OperatorSurfaceContractError` path shared with
:func:`require_accepted_root`.

Consumer-specific projections of these protocol-neutral contracts belong to
the consuming distribution, not to the base application.

Consumers import from the owning module -- :mod:`contract`, :mod:`manifest`,
:mod:`models`, :mod:`crud_contract`, :mod:`help`, :mod:`help_models`,
:mod:`action_resolution`, :mod:`calculation_workflows`, :mod:`crud_registry`,
:mod:`errors` -- rather than from this package root, which is inert.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
"""Inert namespace: every contract is reached at the module that defines it."""
