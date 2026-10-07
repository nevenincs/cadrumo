//! Stable entry dispatch precedes the session lock and runtime ownership.
use crate::supervision::environment::ManagedLocations;
use cadrumo_application::installation::{DiscoveryContract, Selection};
use std::{
    io,
    os::windows::process::CommandExt,
    path::Path,
    process::{Command, Stdio},
};

pub fn select(image: &Path) -> io::Result<Selection> {
    let contract: DiscoveryContract =
        serde_json::from_str(crate::contract::INSTALLATION_CONTRACT).map_err(io::Error::other)?;
    let registered = cadrumo_platform::installation::manager_entry_points(
        &contract.installation_identity.application_id,
    )?;
    contract
        .discover(image, &registered)
        .map_err(io::Error::other)
}

/// Every successor repeats native admission, job escape and catalogue verification.
/// Dispatch acknowledgement conveys no runtime readiness or ownership.
pub fn dispatch_newest(image: &Path) -> io::Result<bool> {
    let selected = select(image)?;
    // Validate management eligibility before dispatch; never clear an override into eligibility.
    ManagedLocations::resolve(&selected.manager)?;
    if std::fs::canonicalize(image)? == std::fs::canonicalize(&selected.manager)? {
        return Ok(false);
    }
    Command::new(selected.manager)
        .env_clear()
        .envs(cadrumo_platform::storage::strict_host_environment(
            std::env::vars_os(),
        ))
        .current_dir(selected.package)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .creation_flags(0x0800_0000)
        .spawn()?;
    Ok(true)
}
