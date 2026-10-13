//! The development direct start: cadrumo-agent's gateway run from its own
//! project environment, without the launcher, for a build compiled with the
//! `agent-direct-start` feature. No distributed build has the feature.
//!
//! The packaged interpreter clears every `CADRUMO_` variable it does not know
//! before Python runs, and cadrumo-agent reads its settings and its key only
//! from `CADRUMO_AGENT_` variables, so the packaged copy cannot be configured
//! this way. The agent's own project environment, named by
//! `CADRUMO_AGENT_SOURCE_DIR`, runs it instead. The key comes from this
//! process's own `CADRUMO_AGENT_ANTHROPIC_API_KEY`, and is handed to the agent
//! in its environment only.
//!
//! The agent's files live under `<storage root>/agent/<profile>/`. It serves
//! one workspace, `workspaces/main`, which every run starts in.

use super::supervisor::{Direct, Launch, Prepared};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::{
    ffi::OsString,
    net::{Ipv4Addr, TcpListener},
    path::{Path, PathBuf},
    process::Command,
    sync::Arc,
};

/// The key's variable, in this process and in the agent's.
pub const KEY_VARIABLE: &str = "CADRUMO_AGENT_ANTHROPIC_API_KEY";
/// The cadrumo-agent project directory, as the package build names it.
pub const SOURCE_VARIABLE: &str = "CADRUMO_AGENT_SOURCE_DIR";

/// Values the interpreter and the operating system need; none carries a
/// credential.
const PASSED: &[&str] = &[
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "PATH",
    "PATHEXT",
    "COMSPEC",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "OS",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "USERNAME",
    "USERDOMAIN",
    "LOCALAPPDATA",
    "APPDATA",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "HOME",
    "LANG",
];

fn failure(code: ErrorCode) -> ApplicationError {
    ApplicationError::new(code, Operation::Cli)
}

/// A directory name for a profile label: its 64-bit FNV-1a digest in hex,
/// since a label may hold any character.
pub fn profile_directory(label: &str) -> String {
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    for byte in label.as_bytes() {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
    format!("{hash:016x}")
}

fn free_port() -> Result<u16> {
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0))
        .map_err(|cause| failure(ErrorCode::SpawnFailed).caused_by(cause))?;
    listener
        .local_addr()
        .map(|address| address.port())
        .map_err(|cause| failure(ErrorCode::SpawnFailed).caused_by(cause))
}

fn interpreter(source: &Path) -> PathBuf {
    if cfg!(windows) {
        source.join(".venv").join("Scripts").join("python.exe")
    } else {
        source.join(".venv").join("bin").join("python")
    }
}

/// The direct start, when this process names both the key and the agent's
/// project directory.
pub fn launch(storage: PathBuf) -> Option<Launch> {
    std::env::var_os(KEY_VARIABLE).filter(|key| !key.is_empty())?;
    let source = std::env::var_os(SOURCE_VARIABLE)
        .map(PathBuf::from)
        .filter(|source| source.is_absolute())?;
    Some(Arc::new(move |bearer: &str, profile: &str| {
        // Read at each start, so a key set for this process is the one used.
        let key = std::env::var_os(KEY_VARIABLE)
            .filter(|key| !key.is_empty())
            .ok_or_else(|| failure(ErrorCode::EnvironmentFailed))?;
        prepare(&source, &storage, key, bearer, profile)
    }))
}

fn prepare(
    source: &Path,
    storage: &Path,
    key: OsString,
    bearer: &str,
    profile: &str,
) -> Result<Prepared> {
    let python = interpreter(source);
    if !python.is_file() {
        return Err(failure(ErrorCode::PackageUnavailable));
    }
    let root = storage.join("agent").join(profile_directory(profile));
    let home = root.join("home");
    let workspaces = root.join("workspaces");
    let main = workspaces.join("main");
    let temporary = root.join("tmp");
    for directory in [&home, &main, &temporary] {
        std::fs::create_dir_all(directory)
            .map_err(|cause| failure(ErrorCode::EnvironmentFailed).caused_by(cause))?;
    }
    let workspace_root = main
        .to_str()
        .ok_or_else(|| failure(ErrorCode::EnvironmentFailed))?
        .to_owned();
    let gateway_port = free_port()?;
    let mut worker_port = free_port()?;
    while worker_port == gateway_port {
        worker_port = free_port()?;
    }
    let mut command = Command::new(&python);
    command
        .args(["-m", "cadrumo_agent.cli.main", "serve"])
        .current_dir(&root)
        .env_clear();
    for (name, value) in std::env::vars_os() {
        let known = name.to_str().is_some_and(|name| {
            PASSED
                .iter()
                .any(|passed| passed.eq_ignore_ascii_case(name))
        });
        if known {
            command.env(name, value);
        }
    }
    command
        .env("TEMP", &temporary)
        .env("TMP", &temporary)
        .env(KEY_VARIABLE, key)
        .env("CADRUMO_AGENT_GATEWAY_TOKEN", bearer)
        .env("CADRUMO_AGENT_PROJECT_ROOT", &root)
        .env("CADRUMO_AGENT_HOME", &home)
        .env("CADRUMO_AGENT_WORKSPACE_ROOT", &workspaces)
        .env("CADRUMO_AGENT_HOST", "127.0.0.1")
        .env("CADRUMO_AGENT_PORT", gateway_port.to_string())
        .env("CADRUMO_AGENT_WORKER_PORT", worker_port.to_string());
    Ok(Prepared {
        command,
        direct: Some(Direct {
            gateway_port,
            workspace_root,
        }),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_profile_names_one_stable_directory() {
        assert_eq!(profile_directory("Perfil á"), profile_directory("Perfil á"));
        assert_ne!(profile_directory("A"), profile_directory("B"));
        assert_eq!(profile_directory("").len(), 16);
        assert!(
            profile_directory("x/../y")
                .bytes()
                .all(|b| b.is_ascii_hexdigit())
        );
    }

    #[test]
    fn the_agent_is_started_in_its_profile_root_with_its_own_settings() {
        let source = std::env::temp_dir().join(format!("agent-direct-{}", std::process::id()));
        let python = interpreter(&source);
        std::fs::create_dir_all(python.parent().unwrap()).unwrap();
        std::fs::write(&python, b"").unwrap();
        let storage = source.join("storage");
        let prepared = prepare(
            &source,
            &storage,
            "test-key-not-real".into(),
            "b".repeat(64).as_str(),
            "Perfil",
        )
        .unwrap();
        let root = storage.join("agent").join(profile_directory("Perfil"));
        let direct = prepared.direct.unwrap();
        assert_eq!(
            PathBuf::from(&direct.workspace_root),
            root.join("workspaces").join("main")
        );
        assert!(root.join("workspaces").join("main").is_dir());
        let environment: std::collections::BTreeMap<_, _> = prepared
            .command
            .get_envs()
            .map(|(name, value)| {
                (
                    name.to_string_lossy().into_owned(),
                    value.map(|v| v.to_owned()),
                )
            })
            .collect();
        assert_eq!(
            environment["CADRUMO_AGENT_PORT"],
            Some(direct.gateway_port.to_string().into())
        );
        assert_eq!(
            environment["CADRUMO_AGENT_WORKSPACE_ROOT"],
            Some(root.join("workspaces").into_os_string())
        );
        assert!(
            environment
                .keys()
                .all(|name| !name.starts_with("CADRUMO_") || name.starts_with("CADRUMO_AGENT_"))
        );
        assert_eq!(environment[KEY_VARIABLE], Some("test-key-not-real".into()));
        assert_eq!(prepared.command.get_current_dir(), Some(root.as_path()));
        // Without the agent's project environment nothing starts.
        assert_eq!(
            prepare(&storage, &storage, "k".into(), "b", "Perfil")
                .err()
                .unwrap()
                .code,
            ErrorCode::PackageUnavailable
        );
        let _ = std::fs::remove_dir_all(&source);
    }
}
