//! The closed line grammar between the manager and the runtime it launched.
//!
//! Each message is one JSON object on one ASCII line of at most [`MAX_LINE_BYTES`] including
//! its newline, discriminated by a closed `type` set, with no repeated, unknown or nested
//! member. The runtime's own Python grammar is the owner; the conformance vectors in
//! `tests/protocol_vectors.json` hold both sides to the same verdicts. Where the Python
//! models accept a non-canonical spelling the runtime never writes, this reader refuses it.

use super::exit::ExitReason;
use super::json::{FlatObject, canonical_uuid, is_hex64, text, unsigned};
use serde_json::Value;

/// Upper bound of one protocol line in either direction, including the newline.
pub const MAX_LINE_BYTES: usize = 512;

/// The largest sequence, count and pid value the grammar admits (2^53 - 1).
pub const MAX_PROTOCOL_INTEGER: u64 = (1 << 53) - 1;

const MAX_VERSION_CHARACTERS: usize = 64;

/// Which admission policy a runtime serves under.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Admission {
    Native,
    Development,
}

impl Admission {
    pub(crate) fn parse(value: &Value) -> Option<Self> {
        match value.as_str()? {
            "native" => Some(Self::Native),
            "development" => Some(Self::Development),
            _ => None,
        }
    }
}

/// The runtime owns its endpoint, published its boot record and accepts connections.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Ready {
    pub boot_id: String,
    pub pid: u64,
    pub version: String,
    pub storage_identity: String,
    pub admission: Admission,
}

/// Liveness evidence in reply to one ping.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Heartbeat {
    pub seq: u64,
    /// Milliseconds since the accept loop last turned; absent before the runtime serves.
    pub tick_age_ms: Option<u64>,
    pub frontends: u64,
    pub hosted_profiles: u64,
}

/// Why one line was refused; the line itself is never kept.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LineRefusal {
    Malformed,
    Oversized,
}

impl LineRefusal {
    fn parse(value: &Value) -> Option<Self> {
        match value.as_str()? {
            "malformed" => Some(Self::Malformed),
            "oversized" => Some(Self::Oversized),
            _ => None,
        }
    }
}

/// One runtime-to-manager message.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Announcement {
    Ready(Ready),
    Heartbeat(Heartbeat),
    /// The runtime is ending for this reason; the exit code remains authoritative.
    Stopping(ExitReason),
    /// A `stop-if-idle` found possible work; admissions stay open.
    Busy,
    /// The runtime refused one manager line.
    Refused(LineRefusal),
}

/// One manager-to-runtime message.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Command {
    Ping { seq: u64 },
    Stop,
    StopIfIdle,
    SessionEnd,
}

impl Command {
    /// The protocol line for this command, newline included.
    pub fn encode(self) -> Vec<u8> {
        let line = match self {
            Self::Ping { seq } => format!("{{\"type\":\"ping\",\"seq\":{seq}}}\n"),
            Self::Stop => "{\"type\":\"stop\"}\n".to_owned(),
            Self::StopIfIdle => "{\"type\":\"stop-if-idle\"}\n".to_owned(),
            Self::SessionEnd => "{\"type\":\"session-end\"}\n".to_owned(),
        };
        line.into_bytes()
    }
}

/// Parse one runtime line without its newline, refusing anything outside the grammar.
pub fn decode_announcement(line: &[u8]) -> Result<Announcement, LineRefusal> {
    if line.len() >= MAX_LINE_BYTES {
        return Err(LineRefusal::Oversized);
    }
    if !line.is_ascii() {
        return Err(LineRefusal::Malformed);
    }
    let mut object = FlatObject::parse(line).ok_or(LineRefusal::Malformed)?;
    let kind = object.take("type").ok_or(LineRefusal::Malformed)?;
    let announcement = match kind.as_str() {
        Some("ready") => ready(&mut object).map(Announcement::Ready),
        Some("heartbeat") => heartbeat(&mut object).map(Announcement::Heartbeat),
        Some("stopping") => object
            .take("reason")
            .and_then(|reason| reason.as_u64())
            .and_then(|code| u32::try_from(code).ok())
            .and_then(ExitReason::from_code)
            .map(Announcement::Stopping),
        Some("busy") => Some(Announcement::Busy),
        Some("refused") => object
            .take("code")
            .as_ref()
            .and_then(LineRefusal::parse)
            .map(Announcement::Refused),
        _ => None,
    };
    match announcement {
        Some(announcement) if object.is_exhausted() => Ok(announcement),
        _ => Err(LineRefusal::Malformed),
    }
}

fn ready(object: &mut FlatObject) -> Option<Ready> {
    let boot_id = canonical_uuid(&object.take("boot_id")?)?.to_owned();
    let pid = unsigned(&object.take("pid")?, 1, MAX_PROTOCOL_INTEGER)?;
    let version = text(&object.take("version")?, MAX_VERSION_CHARACTERS)?.to_owned();
    let storage_identity = object.take("storage_identity")?;
    let storage_identity = storage_identity.as_str().filter(|text| is_hex64(text))?;
    let admission = Admission::parse(&object.take("admission")?)?;
    Some(Ready {
        boot_id,
        pid,
        version,
        storage_identity: storage_identity.to_owned(),
        admission,
    })
}

fn heartbeat(object: &mut FlatObject) -> Option<Heartbeat> {
    let count = |value: Value| unsigned(&value, 0, MAX_PROTOCOL_INTEGER);
    let seq = count(object.take("seq")?)?;
    let tick_age_ms = match object.take("tick_age_ms")? {
        Value::Null => None,
        value => Some(count(value)?),
    };
    Some(Heartbeat {
        seq,
        tick_age_ms,
        frontends: count(object.take("frontends")?)?,
        hosted_profiles: count(object.take("hosted_profiles")?)?,
    })
}

/// Split runtime bytes into lines while holding at most one bounded line.
///
/// A line longer than the bound is discarded through its newline and reported once as
/// oversized, so memory stays bounded whatever the runtime writes.
#[derive(Debug, Default)]
pub struct LineFraming {
    buffer: Vec<u8>,
    discarding: bool,
}

impl LineFraming {
    /// Return each complete line, or a refusal in its place, in arrival order.
    pub fn feed(&mut self, chunk: &[u8]) -> Vec<Result<Vec<u8>, LineRefusal>> {
        let mut framed = Vec::new();
        self.buffer.extend_from_slice(chunk);
        while let Some(end) = self.buffer.iter().position(|&byte| byte == b'\n') {
            let mut line: Vec<u8> = self.buffer.drain(..=end).collect();
            line.pop();
            if self.discarding || end + 1 > MAX_LINE_BYTES {
                self.discarding = false;
                framed.push(Err(LineRefusal::Oversized));
            } else {
                framed.push(Ok(line));
            }
        }
        if self.buffer.len() >= MAX_LINE_BYTES {
            self.buffer.clear();
            self.discarding = true;
        }
        framed
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const BUSY: &[u8] = b"{\"type\":\"busy\"}";

    #[test]
    fn framing_joins_split_lines() {
        let mut framing = LineFraming::default();
        assert_eq!(
            framing.feed(b"{\"type\":\"busy\"}\n{\"ty"),
            [Ok(BUSY.to_vec())]
        );
        assert_eq!(framing.feed(b"pe\":\"busy\"}\n"), [Ok(BUSY.to_vec())]);
    }

    #[test]
    fn framing_bounds_memory_and_reports_one_oversized_line() {
        let mut framing = LineFraming::default();
        assert!(framing.feed(&vec![b'x'; MAX_LINE_BYTES * 3]).is_empty());
        assert!(framing.buffer.len() < MAX_LINE_BYTES);
        assert_eq!(framing.feed(b"tail\n"), [Err(LineRefusal::Oversized)]);
        assert_eq!(framing.feed(b"{\"type\":\"busy\"}\n"), [Ok(BUSY.to_vec())]);
    }

    #[test]
    fn framing_admits_a_line_of_exactly_the_bound() {
        let mut framing = LineFraming::default();
        let mut exact = vec![b' '; MAX_LINE_BYTES - 1];
        exact.push(b'\n');
        assert_eq!(framing.feed(&exact), [Ok(vec![b' '; MAX_LINE_BYTES - 1])]);
        let mut over = vec![b' '; MAX_LINE_BYTES];
        over.push(b'\n');
        assert_eq!(framing.feed(&over), [Err(LineRefusal::Oversized)]);
    }

    #[test]
    fn commands_encode_one_bounded_ascii_line() {
        for command in [
            Command::Ping {
                seq: MAX_PROTOCOL_INTEGER,
            },
            Command::Stop,
            Command::StopIfIdle,
            Command::SessionEnd,
        ] {
            let line = command.encode();
            assert!(line.is_ascii() && line.len() <= MAX_LINE_BYTES);
            assert_eq!(line.iter().filter(|&&byte| byte == b'\n').count(), 1);
            assert_eq!(line.last(), Some(&b'\n'));
        }
    }
}
