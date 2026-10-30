//! Menu effects of an admitted manager package: open its desktop image or its log folder.
//!
//! Login start is not offered: no signed login registration exists, so the menu never
//! claims one and never changes the per-user sign-in preference.

use super::{Availability, Effects};
use crate::{preferences::Preferences, supervision::environment::ManagedLocations};
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
}

impl PackageEffects {
    pub fn new(locations: &ManagedLocations) -> io::Result<Self> {
        let contract: cadrumo_application::installation::DiscoveryContract =
            serde_json::from_str(crate::contract::INSTALLATION_CONTRACT)
                .map_err(io::Error::other)?;
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
        })
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
            sign_in: false,
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

    fn change_sign_in(&mut self, _enabled: bool) -> io::Result<Preferences> {
        Err(io::ErrorKind::Unsupported.into())
    }
}
