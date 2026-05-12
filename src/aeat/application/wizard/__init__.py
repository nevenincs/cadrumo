"""Schema-driven wizard subpackage.

The wizard descriptor catalogue is the single source of truth for every
operator-facing configuration question. A ``WizardFlow`` declares the
sections, questions, widgets, conditional branches, and answer model;
the runtime walks that descriptor against a ``Prompter`` implementation
to collect canonical-token answers, runs per-widget validation, parses
the typed projection, and persists the result through the standard
profile workflow. The descriptor also projects onto the legacy
``PROFILE_KEYS`` registry via ``compile_profile_keys``, keeping the
catalogue and the validation registry in lockstep.
"""
