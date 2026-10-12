"""Live agent evaluation over a verified copy of the built Cadrumo package.

The lane runs a haiku agent, or a scripted client for the floor, over the
package's own ``cadrumo-mcp`` on a fresh storage root, with every storage step
done by the package's interpreter or command line. It is opt-in and reached
only from its recipes; nothing here is collected by pytest.

This initialiser is an inert namespace marker and forwards nothing.
"""
