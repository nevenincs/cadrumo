//! The window's end of the Sede view stream.
//!
//! A profile worker's own Chromium page is streamed to the desktop as JPEG
//! images, and the person's input, downloads and uploads travel back. The
//! Python side of the contract is `cadrumo_client.transport.view_stream`,
//! `cadrumo_client.contracts.view_stream` and `...view_transfer`; this module
//! reads and writes exactly that wire format, and its tests run the shared
//! vectors those modules are tested against.
//!
//! The window binds the stream in three steps. On its person connection it
//! asks with `view_attach` for a single-use token ([`attach::view_attach`]).
//! It then opens a new runtime connection from the same process, with the
//! same peer verification as every other connection, and presents the token
//! as `view_connect`, the connection's first request ([`attach::connect_view`]).
//! From then on that connection carries only the stream, which [`lane::ViewLane`]
//! reads and writes.
//!
//! A stream frame is `kind || u32 length || payload`. `J` carries one JSON
//! document from the closed sets in [`documents`]; `B` carries one chunk of an
//! image or of a file transfer, whose 16-byte header [`chunks`] owns. `S` and
//! `E` never appear. The reader refuses what the Python reader refuses, and a
//! refusal ends the connection.
//!
//! Images, page titles, URLs, dialog text, input, file names and file bytes
//! are private taxpayer data. They live in memory only: buffers that hold
//! image or transfer bytes are zeroed when dropped, nothing is logged, and the
//! types that carry private members print no content.

pub mod chunks;
pub mod decoder;
pub mod documents;
pub mod transfer;

#[cfg(feature = "platform")]
pub mod attach;
#[cfg(feature = "platform")]
pub mod lane;

#[cfg(test)]
mod vectors;

/// A rule of the stream contract that a frame, header or document broke.
///
/// `0` names the rule with the diagnostic name the Python codec gives it. It
/// is a closed name, never content, so it is safe to log.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Violation(pub &'static str);

impl Violation {
    pub fn check(self) -> &'static str {
        self.0
    }
}

impl std::fmt::Display for Violation {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(self.0)
    }
}

impl std::error::Error for Violation {}
