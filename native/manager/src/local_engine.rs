//! Per-user local engine selection: which engine serves the local models and where it runs
//! them. The desktop writes the record and the manager reads it; installers never mutate it.
//!
//! An absent record means the defaults, Ollama with automatic placement, and nothing else
//! does: a record that cannot be read, or that this reader does not know, never reads as
//! the defaults, since the manager would then run an engine the person may not have chosen.

use crate::{
    contract::LOCAL_ENGINE_SELECTION,
    custody::{ensure_local_directory, read_optional_local_record, write_local_record},
};
use cadrumo_application::provisioning::local_ai::{LocalEngine, Placement};
use serde::{Deserialize, Serialize};
use std::{io, path::Path};

/// The longest record the manager reads.
const RECORD_BYTES: u64 = 4096;

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct LocalEngineSelection {
    schema: u32,
    pub engine: LocalEngine,
    pub placement: Placement,
}

/// What the selection record holds.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Recorded {
    /// No record: the person chose nothing, and the defaults apply.
    Absent,
    Selected(LocalEngineSelection),
    /// A record is there and cannot be read: corrupt, of another schema, with a member this
    /// reader does not know, or refused by custody.
    Unreadable,
}

impl Default for LocalEngineSelection {
    fn default() -> Self {
        Self::new(LocalEngine::default(), Placement::default())
    }
}

impl LocalEngineSelection {
    pub fn new(engine: LocalEngine, placement: Placement) -> Self {
        Self {
            schema: 1,
            engine,
            placement,
        }
    }

    pub fn read(root: &Path) -> Recorded {
        let bytes =
            match read_optional_local_record(&root.join(LOCAL_ENGINE_SELECTION), RECORD_BYTES) {
                Ok(Some(bytes)) => bytes,
                Ok(None) => return Recorded::Absent,
                // A storage root that does not exist yet holds no record.
                Err(error) if error.kind() == io::ErrorKind::NotFound => return Recorded::Absent,
                Err(_) => return Recorded::Unreadable,
            };
        match serde_json::from_slice::<Self>(&bytes) {
            Ok(selection) if selection.schema == 1 => Recorded::Selected(selection),
            _ => Recorded::Unreadable,
        }
    }

    pub fn store(&self, root: &Path) -> io::Result<()> {
        if !root.is_absolute() || self.schema != 1 {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        ensure_local_directory(root)?;
        let bytes = serde_json::to_vec(self).map_err(io::Error::other)?;
        write_local_record(&root.join(LOCAL_ENGINE_SELECTION), &bytes, RECORD_BYTES)
    }
}

impl Recorded {
    /// The selection the manager runs: the defaults for an absent record, and none for an
    /// unreadable one.
    pub fn selection(self) -> Option<LocalEngineSelection> {
        match self {
            Self::Absent => Some(LocalEngineSelection::default()),
            Self::Selected(selection) => Some(selection),
            Self::Unreadable => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn scratch_root() -> std::path::PathBuf {
        std::env::temp_dir().join(format!(
            "manager-local-engine-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ))
    }

    #[test]
    fn a_stored_selection_reads_back_whole_and_a_rewrite_replaces_it() {
        let root = scratch_root();
        let selection = LocalEngineSelection::new(LocalEngine::LlamaCpp, Placement::CpuOnly);
        selection.store(&root).unwrap();
        assert_eq!(
            LocalEngineSelection::read(&root),
            Recorded::Selected(selection)
        );
        let bytes = std::fs::read(root.join(LOCAL_ENGINE_SELECTION)).unwrap();
        assert_eq!(
            String::from_utf8(bytes).unwrap(),
            r#"{"schema":1,"engine":"llamacpp","placement":"cpu_only"}"#
        );
        let rewritten = LocalEngineSelection::new(LocalEngine::Ollama, Placement::Auto);
        rewritten.store(&root).unwrap();
        assert_eq!(
            LocalEngineSelection::read(&root),
            Recorded::Selected(rewritten)
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn an_absent_record_is_the_defaults_and_only_an_absent_one() {
        let root = scratch_root();
        // No storage root yet, and a root with no record.
        assert_eq!(LocalEngineSelection::read(&root), Recorded::Absent);
        std::fs::create_dir_all(&root).unwrap();
        let absent = LocalEngineSelection::read(&root);
        assert_eq!(absent, Recorded::Absent);
        assert_eq!(
            absent.selection(),
            Some(LocalEngineSelection::new(
                LocalEngine::Ollama,
                Placement::Auto
            ))
        );
        assert_eq!(Recorded::Unreadable.selection(), None);
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_record_that_cannot_be_read_is_unreadable_and_never_the_defaults() {
        let root = scratch_root();
        LocalEngineSelection::default().store(&root).unwrap();
        for bytes in [
            // Corrupt, and not JSON at all.
            b"{".as_slice(),
            b"ollama",
            // Another schema.
            br#"{"schema":2,"engine":"ollama","placement":"auto"}"#,
            br#"{"schema":0,"engine":"ollama","placement":"auto"}"#,
            // A member this reader does not know, and one missing.
            br#"{"schema":1,"engine":"ollama","placement":"auto","extra":0}"#,
            br#"{"schema":1,"engine":"ollama"}"#,
            // Values outside the closed sets, among them the spelling `llama_cpp`.
            br#"{"schema":1,"engine":"llama_cpp","placement":"auto"}"#,
            br#"{"schema":1,"engine":"ollama","placement":"gpu"}"#,
            // A repeated member.
            br#"{"schema":1,"engine":"ollama","engine":"llamacpp","placement":"auto"}"#,
        ] {
            write_local_record(&root.join(LOCAL_ENGINE_SELECTION), bytes, RECORD_BYTES).unwrap();
            assert_eq!(
                LocalEngineSelection::read(&root),
                Recorded::Unreadable,
                "{}",
                String::from_utf8_lossy(bytes)
            );
        }
        // A record above its bound is refused by custody, and reads unreadable too.
        let oversized = vec![b' '; RECORD_BYTES as usize + 1];
        write_local_record(
            &root.join(LOCAL_ENGINE_SELECTION),
            &oversized,
            RECORD_BYTES + 1,
        )
        .unwrap();
        assert_eq!(LocalEngineSelection::read(&root), Recorded::Unreadable);
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_selection_is_stored_only_under_an_absolute_root() {
        let relative = Path::new("relative-root");
        assert!(LocalEngineSelection::default().store(relative).is_err());
        assert!(!relative.exists());
    }
}
