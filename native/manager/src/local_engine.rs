//! Per-user local engine selection: which engine serves the local models and where it runs
//! them. The desktop writes the record and the manager reads it; installers never mutate it.
//!
//! An absent record means the defaults, and nothing else does: automatic placement, and the
//! engine [`package_default_engine`] derives from the package, which is llama.cpp where the
//! package carries the llama-server and Ollama otherwise. A record that cannot be read, or
//! that this reader does not know, never reads as the defaults, since the manager would then
//! run an engine the person may not have chosen. A stored choice is kept whatever the
//! package carries.

use crate::{
    contract::LOCAL_ENGINE_SELECTION,
    custody::{ensure_local_directory, read_optional_local_record, write_local_record},
};
use cadrumo_application::provisioning::local_ai::{LocalEngine, Placement, package_default_engine};
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
    /// No record: the person chose nothing, and the defaults the package derives apply.
    Absent,
    Selected(LocalEngineSelection),
    /// A record is there and cannot be read: corrupt, of another schema, with a member this
    /// reader does not know, or refused by custody.
    Unreadable,
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
    /// The selection the manager runs from the package at `package_root`: the defaults the
    /// package derives for an absent record, the stored choice as it is, and none for an
    /// unreadable record.
    pub fn selection(self, package_root: &Path) -> Option<LocalEngineSelection> {
        match self {
            Self::Absent => Some(LocalEngineSelection::new(
                package_default_engine(package_root),
                Placement::default(),
            )),
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

    #[cfg(windows)]
    const LLAMA_SERVER_EXECUTABLE: &str = "llama-server.exe";
    #[cfg(not(windows))]
    const LLAMA_SERVER_EXECUTABLE: &str = "llama-server";

    /// A package at `package` that carries the llama-server program.
    fn carrying_llama_server(package: &Path) {
        let folder = package.join(crate::contract::LLAMA_SERVER);
        std::fs::create_dir_all(&folder).unwrap();
        let program = folder.join(LLAMA_SERVER_EXECUTABLE);
        std::fs::write(&program, b"#!/bin/sh\nexit 3\n").unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&program, std::fs::Permissions::from_mode(0o755)).unwrap();
        }
    }

    #[test]
    fn an_absent_record_is_the_defaults_the_package_derives_and_only_an_absent_one() {
        let root = scratch_root();
        let (with, without) = (root.join("with-llama-server"), root.join("without"));
        // No storage root yet, and a root with no record.
        assert_eq!(LocalEngineSelection::read(&root), Recorded::Absent);
        std::fs::create_dir_all(&root).unwrap();
        carrying_llama_server(&with);
        std::fs::create_dir_all(&without).unwrap();
        let absent = LocalEngineSelection::read(&root);
        assert_eq!(absent, Recorded::Absent);
        assert_eq!(
            absent.selection(&with),
            Some(LocalEngineSelection::new(
                LocalEngine::LlamaCpp,
                Placement::Auto
            )),
            "a package that carries the llama-server serves with it"
        );
        assert_eq!(
            absent.selection(&without),
            Some(LocalEngineSelection::new(
                LocalEngine::Ollama,
                Placement::Auto
            )),
            "a package without it serves with Ollama"
        );
        for folder in [&with, &without] {
            assert_eq!(Recorded::Unreadable.selection(folder), None);
        }
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_stored_choice_is_kept_whatever_the_package_carries() {
        let root = scratch_root();
        let (with, without) = (root.join("with-llama-server"), root.join("without"));
        carrying_llama_server(&with);
        std::fs::create_dir_all(&without).unwrap();
        for engine in [LocalEngine::Ollama, LocalEngine::LlamaCpp] {
            let chosen = LocalEngineSelection::new(engine, Placement::CpuOnly);
            chosen.store(&root).unwrap();
            let recorded = LocalEngineSelection::read(&root);
            // llama.cpp chosen on a package without it stays the choice, and Ollama chosen
            // beside a packaged llama-server stays Ollama.
            assert_eq!(recorded.selection(&with), Some(chosen));
            assert_eq!(recorded.selection(&without), Some(chosen));
        }
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_record_that_cannot_be_read_is_unreadable_and_never_the_defaults() {
        let root = scratch_root();
        LocalEngineSelection::new(LocalEngine::Ollama, Placement::Auto)
            .store(&root)
            .unwrap();
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
        let selection = LocalEngineSelection::new(LocalEngine::LlamaCpp, Placement::Auto);
        assert!(selection.store(relative).is_err());
        assert!(!relative.exists());
    }
}
