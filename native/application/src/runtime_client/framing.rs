use super::endpoint::RuntimeChannel;
use super::refusal::Refusal;
use crate::value::Sha256Digest;
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use std::sync::atomic::{AtomicU64, Ordering};
use std::thread;
use std::time::{Duration, Instant, SystemTime};

/// The largest frame the runtime connection reads or writes in one piece; a
/// larger document travels streamed.
pub const MAXIMUM_FRAME_BYTES: usize = 64 * 1024;

/// The longest secret one secret frame carries, and so the longest the runtime takes.
pub const MAXIMUM_SECRET_BYTES: usize = 64 * 1024;

/// The runtime stages a streamed submission in chunks of exactly this many
/// bytes, the last one excepted.
pub(super) const SUBMISSION_PAYLOAD_CHUNK_BYTES: usize = 16_384;

pub(super) const DOCUMENT_FRAME: u8 = b'J';

pub(super) const SECRET_FRAME: u8 = b'S';

pub(super) const EVENT_FRAME: u8 = b'E';

/// Last-resort protection against a peer that leaves an incomplete frame open.
pub(super) const FRAME_BUDGET: Duration =
    Duration::from_secs(cadrumo_platform::DEFAULT_ORCHESTRATION_TIMEOUT_SECONDS);

pub(super) const TRANSFER_CHUNK_BYTES: usize = 16_384;

pub(super) const TRANSFER_LIMIT_BYTES: usize = 1_048_576;

pub(super) fn sha256_hex(bytes: &[u8]) -> String {
    Sha256Digest::of(bytes).to_string()
}

pub(crate) fn is_uuid(text: &str) -> bool {
    let bytes = text.as_bytes();
    bytes.len() == 36
        && bytes.iter().enumerate().all(|(index, byte)| match index {
            8 | 13 | 18 | 23 => *byte == b'-',
            _ => byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase(),
        })
}

static REQUEST_COUNTER: AtomicU64 = AtomicU64::new(0);

/// A fresh request id in UUID spelling. Replies are correlated by it on one
/// verified connection, so it needs to be distinct, not unguessable.
pub fn request_id() -> String {
    let nanos = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map_or(0, |elapsed| elapsed.as_nanos());
    let counter = REQUEST_COUNTER.fetch_add(1, Ordering::Relaxed);
    let mut hasher = Sha256::new();
    hasher.update(std::process::id().to_le_bytes());
    hasher.update(nanos.to_le_bytes());
    hasher.update(counter.to_le_bytes());
    hasher.update(format!("{:?}", thread::current().id()).as_bytes());
    let digest = hasher.finalize();
    let mut bytes = [0u8; 16];
    bytes.copy_from_slice(&digest[..16]);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    let hex: String = bytes.iter().map(|byte| format!("{byte:02x}")).collect();
    format!(
        "{}-{}-{}-{}-{}",
        &hex[..8],
        &hex[8..12],
        &hex[12..16],
        &hex[16..20],
        &hex[20..]
    )
}

pub(crate) fn frame(kind: u8, payload: &[u8]) -> Result<Vec<u8>, Refusal> {
    let limit = if kind == SECRET_FRAME {
        MAXIMUM_SECRET_BYTES
    } else {
        MAXIMUM_FRAME_BYTES
    };
    if payload.is_empty() || payload.len() > limit {
        return Err(Refusal::InvalidFrame);
    }
    let mut framed = Vec::with_capacity(5 + payload.len());
    framed.push(kind);
    framed.extend_from_slice(&(payload.len() as u32).to_be_bytes());
    framed.extend_from_slice(payload);
    Ok(framed)
}

pub(super) fn frame_header(header: &[u8; 5]) -> Result<(u8, usize), Refusal> {
    let size = u32::from_be_bytes([header[1], header[2], header[3], header[4]]) as usize;
    if !matches!(header[0], DOCUMENT_FRAME | EVENT_FRAME) || size == 0 || size > MAXIMUM_FRAME_BYTES
    {
        return Err(Refusal::InvalidFrame);
    }
    Ok((header[0], size))
}

/// Reads one frame before the caller's deadline, allowing at most
/// [`FRAME_BUDGET`] for the payload after its header.
pub(crate) fn read_frame(
    pipe: &RuntimeChannel,
    header_deadline: Instant,
) -> Result<(u8, Vec<u8>), Refusal> {
    let mut header = [0u8; 5];
    pipe.read_exact(&mut header, header_deadline)?;
    let (kind, size) = frame_header(&header)?;
    let mut payload = vec![0u8; size];
    pipe.read_exact(
        &mut payload,
        header_deadline.min(Instant::now() + FRAME_BUDGET),
    )?;
    Ok((kind, payload))
}

pub(super) fn read_idle_frame(pipe: &RuntimeChannel) -> Result<(u8, Vec<u8>), Refusal> {
    let mut header = [0u8; 5];
    pipe.read_idle_byte(&mut header[0])?;
    let deadline = Instant::now() + FRAME_BUDGET;
    pipe.read_exact(&mut header[1..], deadline)?;
    let (kind, size) = frame_header(&header)?;
    let mut payload = vec![0u8; size];
    pipe.read_exact(&mut payload, deadline)?;
    Ok((kind, payload))
}

pub(crate) fn document(payload: &[u8]) -> Result<Map<String, Value>, Refusal> {
    match serde_json::from_slice::<Value>(payload) {
        Ok(Value::Object(object)) => Ok(object),
        _ => Err(Refusal::InvalidFrame),
    }
}

pub(crate) fn text<'a>(document: &'a Map<String, Value>, key: &str) -> Option<&'a str> {
    document.get(key).and_then(Value::as_str)
}

/// Decodes standard base64 with padding, refusing anything but the one
/// canonical spelling of the bytes.
pub fn base64_decode(encoded: &str) -> Option<Vec<u8>> {
    fn value(byte: u8) -> Option<u32> {
        Some(match byte {
            b'A'..=b'Z' => u32::from(byte - b'A'),
            b'a'..=b'z' => u32::from(byte - b'a') + 26,
            b'0'..=b'9' => u32::from(byte - b'0') + 52,
            b'+' => 62,
            b'/' => 63,
            _ => return None,
        })
    }
    let bytes = encoded.as_bytes();
    if bytes.is_empty() || !bytes.len().is_multiple_of(4) {
        return None;
    }
    let padding = bytes.iter().rev().take_while(|&&byte| byte == b'=').count();
    if padding > 2 || bytes[..bytes.len() - padding].contains(&b'=') {
        return None;
    }
    let mut decoded = Vec::with_capacity(bytes.len() / 4 * 3);
    for group in bytes.chunks(4) {
        let mut bits = 0u32;
        let mut count = 0;
        for &byte in group {
            if byte == b'=' {
                break;
            }
            bits = (bits << 6) | value(byte)?;
            count += 1;
        }
        let kept = match count {
            4 => 3,
            3 => 2,
            2 => 1,
            _ => return None,
        };
        bits <<= 6 * (4 - count);
        let octets = bits.to_be_bytes();
        // The bits a canonical encoding leaves unused are zero.
        if octets[1 + kept..].iter().any(|&byte| byte != 0) {
            return None;
        }
        decoded.extend_from_slice(&octets[1..1 + kept]);
    }
    Some(decoded)
}
