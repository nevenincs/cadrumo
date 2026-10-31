//! Menu effects of an admitted manager package: open its desktop image or its log folder,
//! and change the per-user login start.
//!
//! Login start is offered only where `login_start` admits registration: a bundle installed
//! in an Applications folder, on the default storage root, on a system with the agent
//! registration owner. Elsewhere the row stays disabled and the preference unchanged.

use super::{Availability, Effects};
use crate::{
    macos::login_start::{self, native::Agent},
    preferences::Preferences,
    supervision::environment::ManagedLocations,
};
use std::{
    io,
    os::unix::process::CommandExt,
    path::{Path, PathBuf},
    process::{Command, Stdio},
};

/// The system opener; it hands a folder to the Finder through LaunchServices.
const OPENER: &str = "/usr/bin/open";

pub struct PackageEffects {
    package: PathBuf,
    desktop: Option<PathBuf>,
    logs: PathBuf,
    storage: PathBuf,
    login: Option<Agent>,
}

/// The installed bundle's agent, when this package may register login start at all.
fn login_agent(
    locations: &ManagedLocations,
    contract: &serde_json::Value,
) -> io::Result<Option<Agent>> {
    if !locations.is_default_root() {
        return Ok(None);
    }
    let Some(payload) = contract["layout"]["application_bundle"]["payload"].as_str() else {
        return Ok(None);
    };
    let mut applications = vec![PathBuf::from("/Applications")];
    if let Some(home) = std::env::var_os("HOME").map(PathBuf::from)
        && home.is_absolute()
    {
        applications.push(home.join("Applications"));
    }
    let Some(bundle) =
        login_start::installed_bundle(locations.package_root(), Path::new(payload), &applications)
    else {
        return Ok(None);
    };
    Ok(login_start::bundled_agent(&bundle)?.and_then(Agent::new))
}

impl PackageEffects {
    pub fn new(locations: &ManagedLocations) -> io::Result<Self> {
        let contract: cadrumo_application::installation::DiscoveryContract =
            serde_json::from_str(crate::contract::INSTALLATION_CONTRACT)
                .map_err(io::Error::other)?;
        let login = login_agent(
            locations,
            &serde_json::from_str(crate::contract::INSTALLATION_CONTRACT)
                .map_err(io::Error::other)?,
        )?;
        let mut desktop = None;
        for image in contract
            .layout
            .application_images
            .iter()
            .filter(|image| image.target == "desktop-host-build")
        {
            let leaf = format!("{}{}", image.name, contract.layout.entrypoint_suffix);
            let member = cadrumo_application::value::RelativePath::new(if image.placement == "." {
                leaf
            } else {
                format!("{}/{leaf}", image.placement)
            })
            .map_err(io::Error::other)?;
            let path = member.under(locations.package_root());
            if path.is_file() {
                desktop = Some(path);
            }
        }
        let logs = cadrumo_application::value::RelativePath::new(crate::contract::MANAGER_LOG)
            .map_err(io::Error::other)?
            .under(locations.storage_root())
            .parent()
            .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidData))?
            .to_path_buf();
        Ok(Self {
            package: locations.package_root().to_path_buf(),
            desktop,
            logs,
            storage: locations.storage_root().to_path_buf(),
            login,
        })
    }

    /// Bring registration in line with the stored preference at startup. A refusal
    /// leaves registration as it was; the preference is never changed here.
    pub fn reconcile_login(&self, preferences: Preferences) -> io::Result<()> {
        match &self.login {
            Some(agent) => login_start::apply(agent, preferences.start_at_sign_in).map(|_| ()),
            None => Ok(()),
        }
    }
}

/// Start `command` in its own process group and reap it on a detached thread, so the
/// opened program neither receives the manager's terminal signals nor lingers as a zombie.
fn launch(command: &mut Command) -> io::Result<()> {
    let mut child = command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .process_group(0)
        .spawn()?;
    std::thread::Builder::new()
        .name("manager-open-reaper".into())
        .spawn(move || {
            let _ = child.wait();
        })?;
    Ok(())
}

impl Effects for PackageEffects {
    fn availability(&self) -> io::Result<Availability> {
        Ok(Availability {
            application: self.desktop.as_deref().is_some_and(Path::is_file),
            sign_in: self.login.is_some(),
            cutover_unsettled: false,
        })
    }

    fn open_application(&mut self) -> io::Result<()> {
        let desktop = self
            .desktop
            .as_deref()
            .filter(|path| path.is_file())
            .ok_or(io::ErrorKind::NotFound)?;
        launch(Command::new(desktop).current_dir(&self.package))
    }

    fn open_logs(&mut self) -> io::Result<()> {
        if !self.logs.is_dir() {
            return Err(io::ErrorKind::NotFound.into());
        }
        launch(Command::new(OPENER).arg(&self.logs))
    }

    /// Enabling registers before the preference is stored, so a refused registration
    /// changes nothing. Disabling stores the opt-out first: it alone stops a sign-in
    /// start, and the removal that follows only withdraws the item from the system list.
    fn change_sign_in(&mut self, enabled: bool) -> io::Result<Preferences> {
        let agent = self.login.as_ref().ok_or(io::ErrorKind::Unsupported)?;
        let mut preferences = Preferences::read(&self.storage)?;
        preferences.start_at_sign_in = enabled;
        if enabled {
            login_start::apply(agent, true)?;
            preferences.store(&self.storage)?;
        } else {
            preferences.store(&self.storage)?;
            // The stored opt-out is the commitment; a refused removal leaves only a
            // listed item whose sign-in start exits at once.
            let _ = login_start::apply(agent, false);
        }
        Ok(preferences)
    }
}
