//! The `components` role's host: resolves this installation for the engine from the
//! process's own image and environment, then serves the role's protocol on standard
//! input and output.
//!
//! The image's package names the pins and the bundled browser driver; the storage root
//! and its relocatable members come from the package's storage rules, the same ones every
//! other process of the installation reads. The free space comes from the platform's
//! volume query, and the local AI server's fixed address from the package's contract. The
//! owner contains the process: the role runs inside a kill-on-close job on Windows, so a
//! browser check the engine starts ends with it.

use super::{
    browser::{self, DRIVER_PACKAGE, DriverManifest},
    connection::Network,
    engine::{Engine, EngineConfig},
    items::Locations,
    pins::{ComponentPins, Platform},
    protocol,
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

/// Serves the command `arguments` name on standard input and output and returns the
/// process's exit status.
pub fn run(arguments: &[OsString]) -> i32 {
    protocol::serve(arguments, std::io::stdin(), std::io::stdout(), engine)
}

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

/// The engine for this process's installation.
fn engine() -> Result<Engine, Error> {
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
    Engine::new(EngineConfig {
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
