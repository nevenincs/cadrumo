"""Conceptual topic catalogue for ``aeat app registry citations``.

A tax-naive operator hitting the CLI for the first time needs
plain-language explanations of concepts (``iva-regime``, ``casilla``,
``pago-fraccionado`` …) without having to leave the terminal. The
CLI exposes:

- ``aeat app registry citations`` -> list every registered slug + one-line summary.
- ``aeat app registry citations <slug>`` -> render the topic body + see_also
  pointers + legal references.

Topics live as TOML files under ``registry/aeat/topics/<slug>.toml``;
title and body text live in the i18n catalogue under ``topic.<slug>.*``
so translations follow the project's locale pipeline rather than
hardcoded multiline strings.

The :class:`Topic` records are core-level resources: they depend only
on core primitives and the bundled registry path. They are loaded into
a :class:`TopicCatalogue` by :func:`load_topic_catalogue` and consumed
through the
:class:`core.resources._repos.topics.TopicCatalogueRepository`
singleton, keeping ``core`` free of any import into the application
layer.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
