"""Developer tooling that writes the data the MCP harness and its agent workspace ship.

The harness answers an agent from documents written out of the production
registry and the recorded command table. This package writes them; the tests
that hold each document to its source live beside the source, because they
read the document and never write it.
"""
