//! The Quit marker: the user quit, so no manager starts the runtime automatically.
//!
//! The marker is `.runtime/manager-quit.json`, an owner-only record beside the start
//! claim. It follows the runtime's record grammar: canonical JSON (sorted members, compact
//! separators, UTF-8), one flat object with no repeated member, at most
//! [`MAXIMUM_QUIT_MARKER_BYTES`] bytes, published by atomic replacement through the custody
//! primitives. `tests/session_record_vectors.json` holds the grammar's verdicts, which the
//! Python canonical-JSON owner confirms in
//! `dev/packaging/tests/test_native_manager_session_records.py`.
//!
//! Only a sign-in of the same user or a manual start clears the marker.

use crate::custody::{
    clear_local_record, ensure_local_directory, read_optional_local_record, write_local_record,
};
use crate::supervision::boot_record::BOOT_RECORD_LOCATION;
use crate::supervision::json::{FlatObject, unsigned};
use serde_json::Value;
use std::collections::BTreeMap;
use std::io;
use std::path::{Path, PathBuf};

/// Location of the marker below the storage root, beside the runtime's boot record.
pub const QUIT_MARKER_LOCATION: [&str; 2] = [BOOT_RECORD_LOCATION[0], "manager-quit.json"];

/// Upper bound of the encoded marker.
pub const MAXIMUM_QUIT_MARKER_BYTES: u64 = 4096;

const SCHEMA_VERSION: u64 = 1;
const MAXIMUM_USER_CHARACTERS: usize = 192;
const MAXIMUM_SESSION_CHARACTERS: usize = 64;
/// The largest integer every JSON reader on either side holds exactly.
const MAXIMUM_SET_AT_MS: u64 = (1 << 53) - 1;

/// Who quit, in which session, and when.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct QuitMarker {
    /// The user's security identifier on Windows, the effective uid on POSIX.
    pub user: String,
    /// The logon session the user quit in.
    pub session: String,
    /// When the user quit, in milliseconds since the Unix epoch.
    pub set_at_ms: u64,
}

/// What the storage root holds at the marker's location.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum QuitState {
    Absent,
    Present(QuitMarker),
    /// Something is there but it is not a valid marker, or it cannot be read.
    Unreadable,
}

/// The marker location under a storage root.
pub fn quit_marker_path(storage_root: &Path) -> PathBuf {
    QUIT_MARKER_LOCATION
        .iter()
        .fold(storage_root.to_path_buf(), |path, part| path.join(part))
}

/// A user or session identifier: ASCII letters, digits, `-` and `_`.
fn identifier(text: &str, maximum: usize) -> bool {
    (1..=maximum).contains(&text.len())
        && text
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
}

fn identifier_value(value: &Value, maximum: usize) -> Option<String> {
    value
        .as_str()
        .filter(|text| identifier(text, maximum))
        .map(str::to_owned)
}

/// The canonical bytes of `marker`, or `None` when a member is outside the grammar.
pub fn encode_quit_marker(marker: &QuitMarker) -> Option<Vec<u8>> {
    if !identifier(&marker.user, MAXIMUM_USER_CHARACTERS)
        || !identifier(&marker.session, MAXIMUM_SESSION_CHARACTERS)
        || !(1..=MAXIMUM_SET_AT_MS).contains(&marker.set_at_ms)
    {
        return None;
    }
    // A BTreeMap serializes its members in key order, which is the canonical order.
    let members = BTreeMap::from([
        ("schema_version", Value::from(SCHEMA_VERSION)),
        ("session", Value::from(marker.session.as_str())),
        ("set_at_ms", Value::from(marker.set_at_ms)),
        ("user", Value::from(marker.user.as_str())),
    ]);
    let encoded = serde_json::to_vec(&members).ok()?;
    (u64::try_from(encoded.len()).ok()? <= MAXIMUM_QUIT_MARKER_BYTES).then_some(encoded)
}

/// Parse marker bytes strictly: one flat object, no repeated or unknown member.
pub fn decode_quit_marker(raw: &[u8]) -> Option<QuitMarker> {
    if u64::try_from(raw.len()).ok()? > MAXIMUM_QUIT_MARKER_BYTES {
        return None;
    }
    let mut object = FlatObject::parse(raw)?;
    unsigned(
        &object.take("schema_version")?,
        SCHEMA_VERSION,
        SCHEMA_VERSION,
    )?;
    let user = identifier_value(&object.take("user")?, MAXIMUM_USER_CHARACTERS)?;
    let session = identifier_value(&object.take("session")?, MAXIMUM_SESSION_CHARACTERS)?;
    let set_at_ms = unsigned(&object.take("set_at_ms")?, 1, MAXIMUM_SET_AT_MS)?;
    if !object.is_exhausted() {
        return None;
    }
    Some(QuitMarker {
        user,
        session,
        set_at_ms,
    })
}

/// Read the marker without creating anything.
///
/// A missing storage root, `.runtime` directory or marker is absent. Anything else that
/// cannot be read as a valid marker, including a link or an oversized record, is
/// unreadable.
pub fn read_quit_marker(storage_root: &Path) -> QuitState {
    match read_optional_local_record(&quit_marker_path(storage_root), MAXIMUM_QUIT_MARKER_BYTES) {
        Ok(Some(raw)) => decode_quit_marker(&raw).map_or(QuitState::Unreadable, QuitState::Present),
        Ok(None) => QuitState::Absent,
        Err(error) if error.kind() == io::ErrorKind::NotFound => QuitState::Absent,
        Err(_) => QuitState::Unreadable,
    }
}

/// Publish `marker`, replacing any earlier one.
pub fn record_quit(storage_root: &Path, marker: &QuitMarker) -> io::Result<()> {
    let payload = encode_quit_marker(marker).ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "the quit marker is outside its grammar",
        )
    })?;
    if !storage_root.is_absolute() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "the storage root must be absolute",
        ));
    }
    ensure_local_directory(&storage_root.join(QUIT_MARKER_LOCATION[0]))?;
    write_local_record(
        &quit_marker_path(storage_root),
        &payload,
        MAXIMUM_QUIT_MARKER_BYTES,
    )
}

/// Remove the marker; an absent marker or `.runtime` directory is already clear.
pub fn clear_quit(storage_root: &Path) -> io::Result<()> {
    match clear_local_record(&quit_marker_path(storage_root)) {
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(()),
        result => result,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn marker() -> QuitMarker {
        QuitMarker {
            user: "S-1-5-21-1004336348-1177238915-682003330-1001".into(),
            session: "1".into(),
            set_at_ms: 1_790_000_000_000,
        }
    }

    #[test]
    fn encoding_is_canonical_and_round_trips() {
        let encoded = encode_quit_marker(&marker()).expect("valid");
        assert_eq!(
            encoded,
            br#"{"schema_version":1,"session":"1","set_at_ms":1790000000000,"user":"S-1-5-21-1004336348-1177238915-682003330-1001"}"#
        );
        assert_eq!(decode_quit_marker(&encoded), Some(marker()));
    }

    #[test]
    fn markers_outside_the_grammar_are_not_written() {
        for invalid in [
            QuitMarker {
                user: String::new(),
                ..marker()
            },
            QuitMarker {
                session: "a b".into(),
                ..marker()
            },
            QuitMarker {
                user: "é".into(),
                ..marker()
            },
            QuitMarker {
                set_at_ms: 0,
                ..marker()
            },
            QuitMarker {
                set_at_ms: MAXIMUM_SET_AT_MS + 1,
                ..marker()
            },
            QuitMarker {
                session: "s".repeat(MAXIMUM_SESSION_CHARACTERS + 1),
                ..marker()
            },
        ] {
            assert_eq!(encode_quit_marker(&invalid), None, "{invalid:?}");
        }
    }

    #[test]
    fn the_marker_sits_beside_the_start_claim() {
        let root = std::env::temp_dir();
        assert_eq!(
            quit_marker_path(&root).parent(),
            super::super::claim::start_claim_path(&root).parent()
        );
        assert_eq!(
            quit_marker_path(&root),
            root.join(".runtime").join("manager-quit.json")
        );
    }
}
