//! Registered operations and the profile language for a person session this
//! process holds on its own runtime connection.
//!
//! A desktop window once carried these through its Python session-hold child.
//! The relay names no definition, subject or wording: the window names a
//! definition, a subject and a typed request, and the runtime's registered
//! operation validation decides whether the session may submit it. The relay
//! then passes back what the runtime publishes: an operation's observation,
//! its settled result or refusal document (or, for a refused or failed one
//! whose definition declares no refusal document, the detail its executor
//! recorded of why it stopped), a pending review with the digest of
//! exactly what it showed, an answer bound to that digest, and a cancellation
//! at the observed revision. Documents pass unchanged, so the product that
//! registered an operation owns its meaning and its words.
//!
//! The language read and set run the registered `user-profile.view` and
//! `user-profile.field-mutation` operations to settlement, observing again on
//! the runtime's `operation_changed` cue for the held session instead of on a
//! timer.
//!
//! A definition whose contract requires an ephemeral secret is submitted only
//! by `operation_secret_submit`. The relay describes the definition first and
//! refuses unless its contract asks for a secret, submits the request without
//! the secret, and requires the receipt's secret requirement to name exactly
//! the operation, definition and subject it submitted. The secret then
//! travels only on the runtime's secret frame, once the runtime has said it is
//! ready for it, and the operation starts only after the runtime acknowledges
//! it. The secret is the exact text of that frame, which the operation's
//! executor parses; the relay never parses, copies, logs or answers it. A
//! plain submission whose receipt asks for a secret is refused, since nothing
//! would ever deliver it.
//!
//! Requests, reply checks and refusal codes follow the Python client. That
//! client validated each reply against the product's typed models; here the
//! fields the client relies on and their cross-checks are verified, and a
//! definition contract must reproduce its own digest. Digests use the
//! product's canonical JSON: sorted keys, compact separators, unescaped UTF-8
//! and Python's spelling of numbers.

pub mod failure;
mod lifecycle;
pub mod profile_language;
pub mod protocol;
pub mod relay;
pub mod sensitive;
mod timestamps;
mod transport;

#[cfg(test)]
mod tests;
