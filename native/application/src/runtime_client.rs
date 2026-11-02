//! The application's own connection to the installed runtime.
//!
//! A runtime owns a storage root and serves it over one native endpoint. This
//! module derives that endpoint's name from the root, connects as the runtime's
//! verified same-account peer, completes the cohort handshake, and then runs
//! correlated exchanges on the connection while the runtime pushes events
//! between replies. It also reads the proof of a stored sign-in and makes the
//! sign-in, status, activity and sign-out requests a person's frontend makes.
//!
//! A desktop window once started a Python child for each of these: a session
//! hold, a session watch and short `config` commands, each paying an
//! interpreter start and the product's import graph before its first request.
//! The same exchanges run here in the window's own process.
//!
//! Frames are `kind || u32 length || payload`: `J` carries one JSON document,
//! `S` one secret the runtime has said it is ready for, `E` an event the
//! runtime pushes between replies. Every reply names the request it answers,
//! the runtime's boot and this connection; an answer naming another is
//! refused and the connection closed, as the runtime's Python clients do.
//! Nothing here starts, stops or supervises a runtime.

pub mod connection;
pub mod endpoint;
pub mod events;
pub mod framing;
pub mod handshake;
pub mod refusal;
pub mod session;
pub mod stored_proof;
pub mod timeout;

#[cfg(test)]
mod live_tests;
#[cfg(test)]
mod tests;
