//! The manager's status record: a cue that its status changed, for a desktop observing it.
//!
//! The record is `.runtime/manager-status/<session>.json`, an owner-only record a manager
//! rewrites only when the status it reports changes, and clears when it ends. It names
//! the publishing process and grants nothing: an observer watches the directory and
//! re-reads the status through the manager's authenticated `status` request. A record
//! that is absent, unreadable or names a process no longer running means the owner
//! publishes no cue, as an older manager does.

use crate::custody::{
    clear_local_record, ensure_local_directory, read_optional_local_record, write_local_record,
};
use crate::supervision::boot_record::BOOT_RECORD_LOCATION;
use crate::supervision::process::open_process;
use serde::{Deserialize, Serialize};
use std::io;
use std::path::{Path, PathBuf};

const MAXIMUM_STATUS_RECORD_BYTES: u64 = 512;
const SCHEMA_VERSION: u32 = 2;

#[derive(Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
struct StatusRecord {
    schema_version: u32,
    pid: u32,
    /// The publisher's creation stamp, so a record a crashed manager left behind does not
    /// name whichever process later reuses its pid.
    process_created: u64,
    status: String,
}

/// The directory every session's status record lives in, under `storage_root`.
pub fn status_cue_directory(storage_root: &Path) -> PathBuf {
    storage_root
        .join(BOOT_RECORD_LOCATION[0])
        .join("manager-status")
}

fn record_path(storage_root: &Path, session: &str) -> io::Result<PathBuf> {
    if session.is_empty()
        || session.len() > 64
        || !session
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
    {
        return Err(io::ErrorKind::InvalidInput.into());
    }
    Ok(status_cue_directory(storage_root).join(format!("{session}.json")))
}

/// Rewrites this session's record whenever the published status changes.
pub struct StatusPublisher {
    path: PathBuf,
    created: u64,
    published: Option<&'static str>,
}

impl StatusPublisher {
    pub fn new(storage_root: &Path, session: &str) -> io::Result<Self> {
        if !storage_root.is_absolute() {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        let path = record_path(storage_root, session)?;
        // Without its own creation stamp a manager could not be told from a pid's reuser.
        let created = open_process(std::process::id())
            .map_err(|error| io::Error::other(format!("{error:?}")))?
            .identity
            .created;
        ensure_local_directory(&storage_root.join(BOOT_RECORD_LOCATION[0]))?;
        ensure_local_directory(&status_cue_directory(storage_root))?;
        Ok(Self {
            path,
            created,
            published: None,
        })
    }

    /// Record `status` if it differs from the last one recorded. A failed write
    /// is retried at the next change of status or the next call after it.
    pub fn publish(&mut self, status: &'static str) {
        if self.published == Some(status) {
            return;
        }
        let record = StatusRecord {
            schema_version: SCHEMA_VERSION,
            pid: std::process::id(),
            process_created: self.created,
            status: status.to_owned(),
        };
        let written = serde_json::to_vec(&record)
            .map_err(io::Error::other)
            .and_then(|payload| {
                write_local_record(&self.path, &payload, MAXIMUM_STATUS_RECORD_BYTES)
            });
        self.published = written.is_ok().then_some(status);
    }
}

impl Drop for StatusPublisher {
    fn drop(&mut self) {
        let _ = clear_local_record(&self.path);
    }
}

/// Whether the owner of this session publishes status changes: its record is
/// present and names a running process created when the publisher was.
pub fn owner_publishes(storage_root: &Path, session: &str) -> bool {
    let Ok(path) = record_path(storage_root, session) else {
        return false;
    };
    let Ok(Some(raw)) = read_optional_local_record(&path, MAXIMUM_STATUS_RECORD_BYTES) else {
        return false;
    };
    let Ok(record) = serde_json::from_slice::<StatusRecord>(&raw) else {
        return false;
    };
    record.schema_version == SCHEMA_VERSION
        && record.pid != 0
        && open_process(record.pid)
            .is_ok_and(|opened| opened.identity.created == record.process_created)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch(label: &str) -> PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "manager-status-cue-{label}-{}-{nanos}",
            std::process::id()
        ));
        crate::custody::ensure_local_directory(&root).unwrap();
        root
    }

    #[test]
    fn a_record_is_written_on_each_change_only_and_cleared_when_the_publisher_ends() {
        let root = scratch("publish");
        assert!(!owner_publishes(&root, "1"));
        let path = record_path(&root, "1").unwrap();
        let mut publisher = StatusPublisher::new(&root, "1").unwrap();
        publisher.publish("starting");
        assert!(owner_publishes(&root, "1"));
        let first = std::fs::metadata(&path).unwrap().modified().unwrap();
        std::thread::sleep(std::time::Duration::from_millis(20));
        publisher.publish("starting");
        assert_eq!(std::fs::metadata(&path).unwrap().modified().unwrap(), first);
        publisher.publish("running");
        let record: StatusRecord = serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        assert_eq!(record.status, "running");
        assert_eq!(record.pid, std::process::id());
        assert_eq!(
            record.process_created,
            open_process(std::process::id()).unwrap().identity.created
        );
        // Another session's observer finds no publisher of its own.
        assert!(!owner_publishes(&root, "2"));
        drop(publisher);
        assert!(!path.exists());
        assert!(!owner_publishes(&root, "1"));
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_record_naming_no_running_process_or_outside_the_grammar_is_no_publisher() {
        let root = scratch("stale");
        let path = record_path(&root, "1").unwrap();
        drop(StatusPublisher::new(&root, "1").unwrap());
        let pid = std::process::id();
        let created = open_process(pid).unwrap().identity.created;
        for payload in [
            r#"{"schema_version":2,"pid":4294967295,"process_created":0,"status":"running"}"#
                .to_owned(),
            // A running process that reused a crashed publisher's pid.
            format!(
                r#"{{"schema_version":2,"pid":{pid},"process_created":{},"status":"running"}}"#,
                created ^ 1
            ),
            // A record from before the creation stamp.
            format!(r#"{{"schema_version":1,"pid":{pid},"status":"running"}}"#),
            format!(
                r#"{{"schema_version":3,"pid":{pid},"process_created":{created},"status":"running"}}"#
            ),
            format!(
                r#"{{"schema_version":2,"pid":{pid},"process_created":{created},"status":"running","extra":0}}"#
            ),
            "not json".to_owned(),
        ] {
            write_local_record(&path, payload.as_bytes(), MAXIMUM_STATUS_RECORD_BYTES).unwrap();
            assert!(!owner_publishes(&root, "1"), "{payload}");
        }
        // The same record with the publisher's own stamp does name it.
        let current = format!(
            r#"{{"schema_version":2,"pid":{pid},"process_created":{created},"status":"running"}}"#
        );
        write_local_record(&path, current.as_bytes(), MAXIMUM_STATUS_RECORD_BYTES).unwrap();
        assert!(owner_publishes(&root, "1"));
        assert!(record_path(&root, "..\\x").is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
}
