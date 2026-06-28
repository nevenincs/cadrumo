"""Outbound adapter layer.

Hosts adapters that drive external systems on behalf of the domain.
Submodules group adapters by external counterpart, currently
:mod:`aeat.adapters.outbound.aeat` for the Spanish tax administration
portal.

This module uses ``AeatSession``, ``AuthProvider``,
``BrowserSessionFactory``, and ``GoogleService`` for external integration.
"""
