//! The launcher's line protocol: one bearer frame in, JSON event lines out.

use serde::Deserialize;
use zeroize::Zeroizing;

/// The longest event line the launcher may write; a longer one is a fault.
pub const LINE_LIMIT: usize = 4096;
/// The longest agent version the column is asked to show.
const VERSION_LIMIT: usize = 128;

/// One event the launcher reports on its standard output.
#[derive(Debug, PartialEq, Eq)]
pub enum Event {
    Ready {
        gateway_port: u16,
        agent_version: String,
    },
    Refused {
        code: String,
    },
    Stopped {
        reason: String,
    },
}

/// A line that is not one of the protocol's events.
#[derive(Debug, PartialEq, Eq)]
pub struct Violation;

/// The bearer frame: one JSON line, written once, followed by an open stream.
pub fn bearer_frame(bearer: &str) -> Zeroizing<Vec<u8>> {
    #[derive(serde::Serialize)]
    struct Frame<'a> {
        bearer: &'a str,
    }
    let mut encoded = Zeroizing::new(Vec::with_capacity(bearer.len() + 16));
    // Writing to a vector cannot fail, and a string serializes infallibly.
    if serde_json::to_writer(&mut *encoded, &Frame { bearer }).is_ok() {
        encoded.push(b'\n');
    }
    encoded
}

/// A stable code as the protocol spells one.
fn code(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 64
        && value
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
}

/// Reads one event line, without its terminator.
pub fn decode(line: &[u8]) -> Result<Event, Violation> {
    #[derive(Deserialize)]
    #[serde(tag = "event", deny_unknown_fields)]
    enum Wire {
        #[serde(rename = "agent_ready")]
        Ready {
            gateway_port: u64,
            agent_version: String,
            lane: String,
        },
        #[serde(rename = "agent_refused")]
        Refused { code: String },
        #[serde(rename = "agent_stopped")]
        Stopped { reason: String },
    }
    if line.len() > LINE_LIMIT {
        return Err(Violation);
    }
    let line = line.strip_suffix(b"\r").unwrap_or(line);
    match serde_json::from_slice::<Wire>(line).map_err(|_| Violation)? {
        Wire::Ready {
            gateway_port,
            agent_version,
            lane,
        } => {
            let gateway_port = u16::try_from(gateway_port).map_err(|_| Violation)?;
            if gateway_port == 0
                || lane != "development"
                || agent_version.is_empty()
                || agent_version.chars().count() > VERSION_LIMIT
                || agent_version.chars().any(char::is_control)
            {
                return Err(Violation);
            }
            Ok(Event::Ready {
                gateway_port,
                agent_version,
            })
        }
        Wire::Refused { code: refused } if code(&refused) => Ok(Event::Refused { code: refused }),
        Wire::Stopped { reason } if code(&reason) => Ok(Event::Stopped { reason }),
        _ => Err(Violation),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_bearer_is_one_json_line() {
        let frame = bearer_frame("ab\"c");
        assert_eq!(&*frame, b"{\"bearer\":\"ab\\\"c\"}\n");
    }

    #[test]
    fn each_event_the_protocol_declares_is_read() {
        assert_eq!(
            decode(br#"{"event": "agent_ready", "gateway_port": 49213, "agent_version": "0.4.1", "lane": "development"}"#),
            Ok(Event::Ready {
                gateway_port: 49213,
                agent_version: "0.4.1".into()
            })
        );
        assert_eq!(
            decode(b"{\"event\":\"agent_refused\",\"code\":\"agent_root_unmarked\"}\r"),
            Ok(Event::Refused {
                code: "agent_root_unmarked".into()
            })
        );
        assert_eq!(
            decode(br#"{"event":"agent_stopped","reason":"agent_signed_out"}"#),
            Ok(Event::Stopped {
                reason: "agent_signed_out".into()
            })
        );
    }

    #[test]
    fn anything_else_is_a_violation() {
        let long = format!(
            r#"{{"event":"agent_refused","code":"{}"}}"#,
            "x".repeat(LINE_LIMIT)
        );
        for line in [
            &b""[..],
            b"agent_ready",
            br#"{"event":"agent_ready","gateway_port":0,"agent_version":"1","lane":"development"}"#,
            br#"{"event":"agent_ready","gateway_port":65536,"agent_version":"1","lane":"development"}"#,
            br#"{"event":"agent_ready","gateway_port":-1,"agent_version":"1","lane":"development"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"1","lane":"production"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"","lane":"development"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"1\n","lane":"development"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"lane":"development"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"1","lane":"development","token":"x"}"#,
            br#"{"event":"agent_refused","code":"Agent Failed"}"#,
            br#"{"event":"agent_refused","code":""}"#,
            br#"{"event":"agent_stopped","reason":"sk-ant-\u0000"}"#,
            br#"{"event":"agent_started"}"#,
            long.as_bytes(),
        ] {
            assert_eq!(decode(line), Err(Violation), "{}", String::from_utf8_lossy(line));
        }
    }
}
