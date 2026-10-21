//! A provider's browser hook hands one transient URL back to its login owner.

use serde::Deserialize;
use std::{
    ffi::OsString,
    io::{Read, Write},
    net::{Ipv4Addr, SocketAddr, TcpStream},
    time::{Duration, Instant},
};

const PORT: &str = "CADRUMO_AGENT_AUTH_BROWSER_PORT";
const NONCE: &str = "CADRUMO_AGENT_AUTH_BROWSER_NONCE";

/// Browser hooks accept an executable, but cannot supply a role argument.
/// Claim URL invocations before diagnostics, console attachment or GUI startup.
pub fn dispatch(arguments: &[OsString]) -> Option<i32> {
    let first = arguments.first()?.to_str()?;
    if !first.starts_with("https:") && !first.starts_with("http:") {
        return None;
    }
    Some(if arguments.len() == 1 && relay(first).is_some() {
        0
    } else {
        1
    })
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Acknowledgement {
    version: u8,
    nonce: String,
    accepted: bool,
}

fn relay(value: &str) -> Option<()> {
    // The login owner validates provider-specific origins. This bridge grants
    // no browser opening or credential access and never reports its inputs.
    if value.len() > 8192 || value.bytes().any(|byte| byte <= 32 || byte == 127) {
        return None;
    }
    let url = tauri::Url::parse(value).ok()?;
    if url.scheme() != "https"
        || url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.fragment().is_some()
    {
        return None;
    }
    let port = std::env::var(PORT).ok()?.parse::<u16>().ok()?;
    let nonce = std::env::var(NONCE).ok()?;
    if port == 0
        || nonce.len() < 32
        || nonce.len() > 128
        || !nonce
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_' || byte == b'-')
    {
        return None;
    }
    let timeout = Duration::from_secs(3);
    let deadline = Instant::now() + timeout;
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let mut stream = TcpStream::connect_timeout(&address, timeout).ok()?;
    stream
        .set_write_timeout(Some(deadline.checked_duration_since(Instant::now())?))
        .ok()?;
    let mut message = serde_json::to_vec(&serde_json::json!({
        "version": 1, "nonce": nonce, "url": value,
    }))
    .ok()?;
    message.push(b'\n');
    stream.write_all(&message).ok()?;
    let mut answer = Vec::new();
    while answer.len() <= 1024 {
        stream
            .set_read_timeout(Some(deadline.checked_duration_since(Instant::now())?))
            .ok()?;
        let mut byte = [0];
        stream.read_exact(&mut byte).ok()?;
        answer.push(byte[0]);
        if byte[0] == b'\n' {
            break;
        }
    }
    if answer.len() > 1024 || answer.last() != Some(&b'\n') {
        return None;
    }
    let ack: Acknowledgement = serde_json::from_slice(&answer).ok()?;
    (ack.version == 1 && ack.nonce == nonce && ack.accepted).then_some(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn browser_handoff_claims_urls_without_opening_a_desktop() {
        assert_eq!(dispatch(&["--role".into(), "runtime".into()]), None);
        assert_eq!(dispatch(&[]), None);
        assert_eq!(dispatch(&["http://example.invalid".into()]), Some(1));
        assert_eq!(
            dispatch(&["https://example.invalid".into(), "extra".into()]),
            Some(1)
        );
        assert_eq!(
            dispatch(&["https://user:secret@example.invalid".into()]),
            Some(1)
        );
    }
}
