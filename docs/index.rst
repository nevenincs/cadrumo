aeat — Spanish Tax Authority automation
=======================================

``aeat`` is a Python toolkit for interacting with the Spanish tax authority
(`Agencia Estatal de Administración Tributaria
<https://sede.agenciatributaria.gob.es/>`_), modelling tax records, and
automating filing workflows for autónomos and small businesses.

The codebase follows a hexagonal layout: pure business records and rules
live under :mod:`aeat.domain`, inbound parsers and outbound integrations
live under :mod:`aeat.adapters`, use cases live under
:mod:`aeat.application`, and CLI / MCP entrypoints live under
:mod:`aeat.entrypoints`.

.. Getting Started and Architecture narrative pages are added separately;
   this toctree references only pages that currently exist.

.. toctree::
   :maxdepth: 2
   :caption: CLI Reference

   cli/index

.. toctree::
   :maxdepth: 3
   :caption: API Reference

   api/aeat

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
