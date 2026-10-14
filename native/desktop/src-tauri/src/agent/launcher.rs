//! The launcher's line protocol: distinct authority secrets in, JSON event lines out.

use serde::Deserialize;
use zeroize::Zeroizing;

/// The longest event line the launcher may write; a longer one is a fault.
pub const LINE_LIMIT: usize = 4096;
/// The longest agent version the column is asked to show.
const VERSION_LIMIT: usize = 128;
/// `MAX_WORKSPACE_ROOT_LENGTH`: the longest workspace root a run may name.
const WORKSPACE_LIMIT: usize = 4096;

/// One event the launcher reports on its standard output.
#[derive(Debug, PartialEq, Eq)]
pub enum Event {
    ServiceReady {
        admin_port: u16,
        runtime_boot_id: String,
        connection_id: String,
        profile_id: String,
        service_id: String,
    },
    Ready {
        gateway_port: u16,
        agent_version: String,
        /// The profile's one agent workspace, which the launcher created:
        /// every run starts in it and the catalog is read for it.
        workspace_root: String,
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

/// The private admin and gateway frame: one JSON line followed by an open stream.
pub fn bearer_frame(bearer: &str, gateway_bearer: &str) -> Zeroizing<Vec<u8>> {
    #[derive(serde::Serialize)]
    struct Frame<'a> {
        bearer: &'a str,
        gateway_bearer: &'a str,
    }
    let mut encoded = Zeroizing::new(Vec::with_capacity(bearer.len() + gateway_bearer.len() + 64));
    // Writing to a vector cannot fail, and a string serializes infallibly.
    if serde_json::to_writer(
        &mut *encoded,
        &Frame {
            bearer,
            gateway_bearer,
        },
    )
    .is_ok()
    {
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

/// Absolute under either convention, as cadrumo-agent's own workspace check
/// reads a root: a POSIX root, a drive root or a UNC share.
fn absolute(path: &str) -> bool {
    let bytes = path.as_bytes();
    path.starts_with('/')
        || path.starts_with(r"\\")
        || (bytes.len() > 2
            && bytes[0].is_ascii_alphabetic()
            && bytes[1] == b':'
            && matches!(bytes[2], b'\\' | b'/'))
}

/// Reads one event line, without its terminator.
pub fn decode(line: &[u8]) -> Result<Event, Violation> {
    #[derive(Deserialize)]
    #[serde(tag = "event", deny_unknown_fields)]
    enum Wire {
        #[serde(rename = "service_ready")]
        ServiceReady {
            protocol: u64,
            admin_port: u16,
            runtime_boot_id: String,
            connection_id: String,
            profile_id: String,
            service_id: String,
        },
        #[serde(rename = "agent_ready")]
        Ready {
            gateway_port: u64,
            agent_version: String,
            hosting_contract: u64,
            workspace_root: String,
        },
        #[serde(rename = "refused", alias = "agent_refused")]
        Refused { code: String },
        #[serde(rename = "stopped", alias = "agent_stopped")]
        Stopped {
            #[serde(default, alias = "code")]
            reason: String,
        },
    }
    if line.len() > LINE_LIMIT {
        return Err(Violation);
    }
    let line = line.strip_suffix(b"\r").unwrap_or(line);
    match serde_json::from_slice::<Wire>(line).map_err(|_| Violation)? {
        Wire::ServiceReady {
            protocol,
            admin_port,
            runtime_boot_id,
            connection_id,
            profile_id,
            service_id,
        } if protocol == 1
            && admin_port != 0
            && service_id == "cadrumo-agent-service"
            && [&runtime_boot_id, &connection_id, &profile_id]
                .iter()
                .all(|id| crate::shell::agent_access::wire::is_uuid(id)) =>
        {
            Ok(Event::ServiceReady {
                admin_port,
                runtime_boot_id,
                connection_id,
                profile_id,
                service_id,
            })
        }
        Wire::Ready {
            gateway_port,
            agent_version,
            hosting_contract,
            workspace_root,
        } => {
            let gateway_port = u16::try_from(gateway_port).map_err(|_| Violation)?;
            if gateway_port == 0
                || hosting_contract != 1
                || agent_version.is_empty()
                || agent_version.chars().count() > VERSION_LIMIT
                || agent_version.chars().any(char::is_control)
                || !absolute(&workspace_root)
                || workspace_root.chars().count() > WORKSPACE_LIMIT
                || workspace_root.chars().any(char::is_control)
            {
                return Err(Violation);
            }
            Ok(Event::Ready {
                gateway_port,
                agent_version,
                workspace_root,
            })
        }
        Wire::Refused { code: refused } if code(&refused) => Ok(Event::Refused { code: refused }),
        Wire::Stopped { reason } if reason.is_empty() || code(&reason) => {
            Ok(Event::Stopped { reason })
        }
        _ => Err(Violation),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_bearer_is_one_json_line() {
        let frame = bearer_frame("ab\"c", "gateway-secret");
        assert_eq!(
            &*frame,
            b"{\"bearer\":\"ab\\\"c\",\"gateway_bearer\":\"gateway-secret\"}\n"
        );
    }

    #[test]
    fn each_event_the_protocol_declares_is_read() {
        assert_eq!(
            decode(br#"{"event": "agent_ready", "gateway_port": 49213, "agent_version": "0.4.1", "hosting_contract": 1, "workspace_root": "C:\\lane\\agent\\p\\workspace"}"#),
            Ok(Event::Ready {
                gateway_port: 49213,
                agent_version: "0.4.1".into(),
                workspace_root: r"C:\lane\agent\p\workspace".into()
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
            br#"{"event":"agent_ready","gateway_port":0,"agent_version":"1","hosting_contract":1,"workspace_root":"C:\\ws"}"#,
            br#"{"event":"agent_ready","gateway_port":65536,"agent_version":"1","hosting_contract":1,"workspace_root":"C:\\ws"}"#,
            br#"{"event":"agent_ready","gateway_port":-1,"agent_version":"1","hosting_contract":1,"workspace_root":"C:\\ws"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"1","hosting_contract":1,"lane":"production","workspace_root":"C:\\ws"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"1","hosting_contract":2,"workspace_root":"C:\\ws"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"1","workspace_root":"C:\\ws"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"","hosting_contract":1,"workspace_root":"C:\\ws"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"1\n","hosting_contract":1,"workspace_root":"C:\\ws"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"hosting_contract":1,"workspace_root":"C:\\ws"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"1","hosting_contract":1,"workspace_root":"C:\\ws","token":"x"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"1","hosting_contract":1 }"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"1","hosting_contract":1,"workspace_root":"relative\\ws"}"#,
            br#"{"event":"agent_ready","gateway_port":4000,"agent_version":"1","hosting_contract":1,"workspace_root":"C:\\w\n"}"#,
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
