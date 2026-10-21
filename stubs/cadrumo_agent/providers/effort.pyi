"""Translate a lane's declared efforts into its provider-native control."""

from .gateways import AnthropicGateway
from .provider_catalog import NativeControl

def gateway_effort_control(gateway: AnthropicGateway) -> NativeControl | None: ...
