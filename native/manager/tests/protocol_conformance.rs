//! The manager's protocol and boot-record readers against the shared conformance vectors.
//!
//! `protocol_vectors.json` holds lines and records whose verdicts the Python owners confirm
//! in `dev/packaging/tests/test_native_manager_protocol.py`. Every line the manager accepts
//! is one the runtime's grammar accepts; `refused_by_manager_only` lists spellings the Python
//! models also accept but the runtime never writes, which this reader refuses.

use cadrumo_manager::supervision::boot_record::{
    BOOT_RECORD_LOCATION, BootRecord, decode_boot_record,
};
use cadrumo_manager::supervision::exit::ExitReason;
use cadrumo_manager::supervision::protocol::{
    Admission, Announcement, Command, Heartbeat, LineRefusal, MAX_LINE_BYTES, Ready,
    decode_announcement,
};
use serde_json::Value;
use std::path::PathBuf;

fn vectors() -> Value {
    serde_json::from_str(include_str!("protocol_vectors.json")).expect("vectors JSON")
}

fn strings<'a>(value: &'a Value, group: &str, kind: &str) -> Vec<&'a str> {
    value[group][kind]
        .as_array()
        .unwrap_or_else(|| panic!("{group}.{kind}"))
        .iter()
        .map(|item| item.as_str().expect("vector string"))
        .collect()
}

fn admission(value: &Value) -> Admission {
    match value.as_str() {
        Some("native") => Admission::Native,
        Some("development") => Admission::Development,
        other => panic!("admission {other:?}"),
    }
}

/// The announcement a vector line spells, read field by field without the grammar's checks.
fn spelled(line: &str) -> Announcement {
    let value: Value = serde_json::from_str(line).expect("vector JSON");
    let number = |name: &str| value[name].as_u64().expect(name);
    match value["type"].as_str().expect("type") {
        "ready" => Announcement::Ready(Ready {
            boot_id: value["boot_id"].as_str().expect("boot_id").into(),
            pid: number("pid"),
            version: value["version"].as_str().expect("version").into(),
            storage_identity: value["storage_identity"].as_str().expect("identity").into(),
            admission: admission(&value["admission"]),
        }),
        "heartbeat" => Announcement::Heartbeat(Heartbeat {
            seq: number("seq"),
            tick_age_ms: value["tick_age_ms"].as_u64(),
            frontends: number("frontends"),
            hosted_profiles: number("hosted_profiles"),
        }),
        "stopping" => Announcement::Stopping(
            ExitReason::from_code(u32::try_from(number("reason")).expect("u32"))
                .expect("a contract reason"),
        ),
        "busy" => Announcement::Busy,
        "refused" => Announcement::Refused(match value["code"].as_str() {
            Some("malformed") => LineRefusal::Malformed,
            Some("oversized") => LineRefusal::Oversized,
            other => panic!("code {other:?}"),
        }),
        other => panic!("type {other}"),
    }
}

#[test]
fn the_line_bound_and_record_location_match_the_owners() {
    let vectors = vectors();
    assert_eq!(
        vectors["max_line_bytes"].as_u64(),
        Some(MAX_LINE_BYTES as u64)
    );
    assert_eq!(
        vectors["boot_record_location"].as_str(),
        Some(BOOT_RECORD_LOCATION.join("/").as_str())
    );
}

#[test]
fn commands_encode_exactly_the_lines_the_runtime_decodes() {
    for vector in vectors()["commands"].as_array().expect("commands") {
        let command = match vector["type"].as_str().expect("type") {
            "ping" => Command::Ping {
                seq: vector["seq"].as_u64().expect("seq"),
            },
            "stop" => Command::Stop,
            "stop-if-idle" => Command::StopIfIdle,
            "session-end" => Command::SessionEnd,
            other => panic!("command {other}"),
        };
        let line = vector["line"].as_str().expect("line");
        assert_eq!(command.encode(), format!("{line}\n").into_bytes());
    }
}

#[test]
fn runtime_announcements_are_accepted_with_their_meaning() {
    let vectors = vectors();
    let canonical = strings(&vectors, "announcements", "canonical");
    let accepted = strings(&vectors, "announcements", "accepted");
    assert!(!canonical.is_empty() && !accepted.is_empty());
    for line in canonical.into_iter().chain(accepted) {
        assert_eq!(
            decode_announcement(line.as_bytes()),
            Ok(spelled(line)),
            "{line}"
        );
    }
}

#[test]
fn every_contract_stop_reason_has_a_canonical_vector() {
    let vectors = vectors();
    let reasons: Vec<ExitReason> = strings(&vectors, "announcements", "canonical")
        .into_iter()
        .filter_map(|line| match spelled(line) {
            Announcement::Stopping(reason) => Some(reason),
            _ => None,
        })
        .collect();
    assert_eq!(reasons, ExitReason::ALL);
}

#[test]
fn lines_outside_the_grammar_are_refused() {
    let vectors = vectors();
    let refused = strings(&vectors, "announcements", "refused");
    let manager_only = strings(&vectors, "announcements", "refused_by_manager_only");
    assert!(!refused.is_empty() && !manager_only.is_empty());
    for line in refused.into_iter().chain(manager_only) {
        assert!(decode_announcement(line.as_bytes()).is_err(), "{line}");
    }
}

fn record_of(raw: &str) -> BootRecord {
    let value: Value = serde_json::from_str(raw).expect("record JSON");
    BootRecord {
        boot_id: value["boot_id"].as_str().expect("boot_id").into(),
        pid: u32::try_from(value["pid"].as_u64().expect("pid")).expect("u32 pid"),
        process_created: value["process_created"].as_u64().expect("created"),
        version: value["version"].as_str().expect("version").into(),
        package_directory: value["package_directory"].as_str().map(PathBuf::from),
        admission: admission(&value["admission"]),
    }
}

#[test]
fn boot_records_the_runtime_writes_are_read_with_their_meaning() {
    let vectors = vectors();
    for raw in strings(&vectors, "boot_records", "canonical")
        .into_iter()
        .chain(strings(&vectors, "boot_records", "accepted"))
    {
        assert_eq!(
            decode_boot_record(raw.as_bytes()),
            Some(record_of(raw)),
            "{raw}"
        );
    }
}

#[test]
fn malformed_boot_records_are_refused() {
    let vectors = vectors();
    for raw in strings(&vectors, "boot_records", "refused")
        .into_iter()
        .chain(strings(&vectors, "boot_records", "refused_by_manager_only"))
    {
        assert_eq!(decode_boot_record(raw.as_bytes()), None, "{raw}");
    }
}
