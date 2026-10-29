//! The installation the component engine serves, resolved from the process's own image
//! and environment. The desktop builds its in-process engines from this resolution
//! ([`installation_config`]).
//!
//! The installation fixes everything but the local models: those are the person's
//! selection, which only the desktop knows, so the resolution reads no model from the
//! package or the environment.
//!
//! The image's package names the pins and the bundled browser driver; the storage root
//! and its relocatable members come from the package's storage rules, the same ones every
//! other process of the installation reads. The free space comes from the platform's
//! volume query, and the local AI server's fixed address from the package's contract.
//! The owner contains the process before the engine starts anything: a kill-on-close job
//! on Windows, and on Linux and macOS a process scope every browser check and hardware
//! query is created into, so whatever the engine starts ends with its owner.

use super::{
    browser::{self, DRIVER_PACKAGE, DriverManifest},
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

/// The location setting that relocates the local AI's models folder.
pub const MODELS_DIR_VARIABLE: &str = "CADRUMO_OLLAMA_MODELS_DIR";
/// The models folder under the storage root when no setting relocates it.
pub const MODELS_DEFAULT: &str = "models/ollama";
/// The location setting that relocates the local AI server's home.
pub const HOME_DIR_VARIABLE: &str = "CADRUMO_OLLAMA_HOME_DIR";
/// The server's home under the storage root when no setting relocates it.
pub const HOME_DEFAULT: &str = "components/ollama/home";

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

fn member(
    root: &Path,
    variable: &str,
    default: &str,
    lookup: &dyn Fn(&str) -> Option<OsString>,
) -> Result<PathBuf, Error> {
    storage::member_path(root, variable, default, lookup)
        .map_err(|refusal| Error::Invalid(format!("location refused: {}", refusal.code)))
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
    locations.browsers = browser::browsers_root(&root, &lookup)?;
    locations.models = member(&root, MODELS_DIR_VARIABLE, MODELS_DEFAULT, &lookup)?;
    locations.ollama_home = member(&root, HOME_DIR_VARIABLE, HOME_DEFAULT, &lookup)?;
    let scratch = member(
        &root,
        cadrumo_platform::TEMPORARY_ENV,
        cadrumo_platform::TEMPORARY_DEFAULT,
        &lookup,
    )?;
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
