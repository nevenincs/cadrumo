//! The installation the component engine serves, resolved from the process's own image
//! and environment. The desktop builds its in-process engines from this resolution
//! ([`installation_config`]).
//!
//! The installation fixes everything but the local models: those are the person's
//! selection, which only the desktop knows, so the resolution reads no model from the
//! package or the environment.
//!
//! The image's package names the pins and the bundled browser driver; the storage root
//! comes from the package's storage rules, the same ones every other process of the
//! installation reads, and every component location is a fixed path beneath it. The free space comes from the platform's
//! volume query, and the local AI server's fixed address from the package's contract.
//! The owner contains the process before the engine starts anything: a kill-on-close job
//! on Windows, and on Linux and macOS a process scope every browser check and hardware
//! query is created into, so whatever the engine starts ends with its owner.

use super::{
    browser::{DRIVER_PACKAGE, DriverManifest},
    connection::Network,
    engine::EngineConfig,
    items::Locations,
    pins::{ComponentPins, Platform},
    proxy::ProxySettings,
    transfer::RetryPolicy,
};
use crate::error::Error;
use cadrumo_platform::storage;
use std::{
    collections::BTreeMap,
    ffi::OsString,
    path::{Path, PathBuf},
};

/// The operating system settings a browser check passes on from the engine's own
/// environment; its temporary folders are the owner's.
const BROWSER_PASSED_THROUGH: &[&str] = &[
    "SystemRoot",
    "SystemDrive",
    "windir",
    "ComSpec",
    "PATH",
    "PATHEXT",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "HOME",
    "LANG",
    "LC_ALL",
];

fn package_path(package: &Path, relative: &str) -> PathBuf {
    relative
        .split('/')
        .filter(|part| !part.is_empty() && *part != ".")
        .fold(package.to_path_buf(), |path, part| path.join(part))
}

fn refused(refusal: storage::Refusal) -> Error {
    Error::Invalid(format!("location refused: {}", refusal.code))
}

/// What the engine of this process's installation is built from, for an owner that
/// keeps facts across engines, such as a window that measures the hardware once.
pub fn installation_config() -> Result<EngineConfig, Error> {
    let lookup = |name: &str| std::env::var_os(name);
    let text = |name: &str| std::env::var(name).ok();
    let executable = std::env::current_exe()?;
    let evidence = storage::detect_mode(&executable).map_err(Error::Invalid)?;
    let root = storage::resolve_storage_root_with(&evidence, &lookup)
        .map_err(|refusal| Error::Invalid(format!("storage root refused: {}", refusal.code)))?
        .root;
    let mut locations = Locations::under(&root);
    for member in [
        &mut locations.browsers,
        &mut locations.models,
        &mut locations.ollama_home,
    ] {
        *member = storage::validated_absolute_path(member).map_err(refused)?;
    }
    let scratch =
        storage::member_path(&root, cadrumo_platform::TEMPORARY_MEMBER).map_err(refused)?;
    let package = evidence.package;
    let pins = ComponentPins::load(&package_path(&package, cadrumo_platform::COMPONENT_PINS))?;
    let driver = DriverManifest::read(
        &package_path(&package, cadrumo_platform::PACKAGES).join(DRIVER_PACKAGE),
    )
    .ok();
    let mut browser_environment: BTreeMap<OsString, OsString> = BROWSER_PASSED_THROUGH
        .iter()
        .filter_map(|name| Some((OsString::from(name), lookup(name)?)))
        .collect();
    for name in ["TEMP", "TMP", "TMPDIR"] {
        browser_environment.insert(name.into(), scratch.clone().into_os_string());
    }
    Ok(EngineConfig {
        storage_root: root,
        locations,
        pins,
        driver,
        platform: Platform::current(),
        network: Network::new(ProxySettings::from_settings(text)?),
        ambient: Box::new(lookup),
        local_ai_address: cadrumo_platform::LOCAL_AI_ADDRESS
            .parse()
            .map_err(|_| Error::Invalid("local AI address".into()))?,
        browser_environment,
        scratch,
        free_space: Box::new(|path| cadrumo_platform::volume::available_bytes(path).ok()),
        hardware: None,
        policy: RetryPolicy::default(),
    })
}
