"""Minimal stub for the one symbol `google-api-python-client-stubs` references.

`googleapiclient-stubs/discovery.pyi` annotates every `build` overload's
`credentials` parameter as `oauth2client.Credentials | google.auth.credentials.Credentials | None`
and imports `oauth2client` under `# type: ignore[import-not-found]`, because
oauth2client is a deprecated package this project does not install. Without a
resolvable `oauth2client.Credentials` the whole overload set resolves as
partially unknown, which erases the return type of every `build(...)` call and,
with it, the type of every Drive and Sheets resource downstream.

This declares only the attribute the stubs name. The project passes
`google.auth.credentials.Credentials`; nothing here is imported at runtime.
"""

class Credentials: ...
