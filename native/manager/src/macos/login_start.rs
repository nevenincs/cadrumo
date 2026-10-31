//! Login start through the bundle's own Aqua agent, registered for the current user
//! only by the platform's service-management owner.
//!
//! Registration is admitted only for a bundle installed in an Applications folder that
//! runs against the default storage root, so development, test and CI images never
//! register. The per-user preference stays authoritative: a sign-in start that finds the
//! opt-out exits before it supervises anything, and a user who disables the item in the
//! system settings is never re-registered behind their back.

use std::{
    ffi::OsStr,
    io,
    path::{Path, PathBuf},
};

/// The bundle's agent declarations, beside the main executable's `Contents`.
const AGENT_DIRECTORY: &str = "Contents/Library/LaunchAgents";

/// Registration state as the service-management owner reports it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    NotRegistered,
    Enabled,
    /// Registered, but held off until the user approves it, or disabled by the user.
    RequiresApproval,
    /// The owner cannot find the declared agent.
    NotFound,
}

impl Status {
    pub fn from_raw(value: isize) -> io::Result<Self> {
        match value {
            0 => Ok(Self::NotRegistered),
            1 => Ok(Self::Enabled),
            2 => Ok(Self::RequiresApproval),
            3 => Ok(Self::NotFound),
            _ => Err(io::ErrorKind::InvalidData.into()),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Change {
    Register,
    Unregister,
}

/// The single change that brings registration in line with the per-user preference.
/// A pending or user-disabled item is left to the user while start is wanted.
pub fn reconcile(start_at_sign_in: bool, status: Status) -> Option<Change> {
    match (start_at_sign_in, status) {
        (true, Status::NotRegistered) => Some(Change::Register),
        (false, Status::Enabled | Status::RequiresApproval) => Some(Change::Unregister),
        _ => None,
    }
}

/// Native registration port; tests substitute it and never reach the real owner.
pub trait Registrar {
    fn status(&self) -> io::Result<Status>;
    fn register(&self) -> io::Result<()>;
    fn unregister(&self) -> io::Result<()>;
}

/// Apply the reconciled change, reporting what was done.
pub fn apply(registrar: &dyn Registrar, start_at_sign_in: bool) -> io::Result<Option<Change>> {
    let change = reconcile(start_at_sign_in, registrar.status()?);
    match change {
        Some(Change::Register) => registrar.register()?,
        Some(Change::Unregister) => registrar.unregister()?,
        None => {}
    }
    Ok(change)
}

/// The bundle that holds `package` at its declared `payload` placement, when that bundle
/// lies directly in one of the `applications` folders.
pub fn installed_bundle(
    package: &Path,
    payload: &Path,
    applications: &[PathBuf],
) -> Option<PathBuf> {
    if !package.is_absolute() || payload.is_absolute() || payload.as_os_str().is_empty() {
        return None;
    }
    let mut bundle = package;
    for _ in payload.components() {
        bundle = bundle.parent()?;
    }
    if bundle.join(payload) != package || bundle.extension() != Some(OsStr::new("app")) {
        return None;
    }
    let folder = bundle.parent()?;
    applications
        .iter()
        .any(|candidate| candidate.is_absolute() && candidate == folder)
        .then(|| bundle.to_path_buf())
}

/// The file name of the bundle's one agent declaration. Anything else there, or more
/// than one declaration, leaves login start unavailable rather than guessing.
pub fn bundled_agent(bundle: &Path) -> io::Result<Option<String>> {
    let entries = match std::fs::read_dir(bundle.join(AGENT_DIRECTORY)) {
        Ok(entries) => entries,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error),
    };
    let mut found = None;
    for entry in entries {
        let entry = entry?;
        let name = entry.file_name();
        let name = name.to_str().ok_or(io::ErrorKind::InvalidData)?;
        if !entry.file_type()?.is_file() || !name.ends_with(".plist") || found.is_some() {
            return Ok(None);
        }
        found = Some(name.to_owned());
    }
    Ok(found)
}

#[cfg(target_os = "macos")]
pub mod native {
    #![allow(unsafe_code)]

    use super::{Registrar, Status};
    use objc2::{msg_send, rc::Retained, runtime::AnyClass, runtime::AnyObject};
    use objc2_foundation::{NSError, NSString};
    use std::io;

    #[link(name = "ServiceManagement", kind = "framework")]
    unsafe extern "C" {}

    /// One bundled agent, named by its declaration's file name. The service object is
    /// looked up per call so no Objective-C object outlives the call that needs it.
    pub struct Agent {
        plist: String,
    }

    impl Agent {
        /// `None` when the running system has no agent registration owner.
        pub fn new(plist: String) -> Option<Self> {
            AnyClass::get(c"SMAppService").map(|_| Self { plist })
        }

        fn service(&self) -> io::Result<Retained<AnyObject>> {
            let class = AnyClass::get(c"SMAppService").ok_or(io::ErrorKind::Unsupported)?;
            let name = NSString::from_str(&self.plist);
            // SAFETY: `agentServiceWithPlistName:` takes one NSString and returns an
            // autoreleased service object or nil; the retained result owns it.
            let service: Option<Retained<AnyObject>> =
                unsafe { msg_send![class, agentServiceWithPlistName: &*name] };
            service.ok_or_else(|| io::ErrorKind::NotFound.into())
        }
    }

    fn refused(error: &NSError) -> io::Error {
        io::Error::other(format!("login_registration_refused:{}", error.code()))
    }

    impl Registrar for Agent {
        fn status(&self) -> io::Result<Status> {
            let service = self.service()?;
            // SAFETY: `status` is a read-only NSInteger property of the service.
            let value: isize = unsafe { msg_send![&*service, status] };
            Status::from_raw(value)
        }

        fn register(&self) -> io::Result<()> {
            let service = self.service()?;
            // SAFETY: `registerAndReturnError:` returns BOOL and fills the error out
            // parameter only on failure, which objc2 converts into the `Err` value.
            let result: Result<(), Retained<NSError>> =
                unsafe { msg_send![&*service, registerAndReturnError: _] };
            result.map_err(|error| refused(&error))
        }

        fn unregister(&self) -> io::Result<()> {
            let service = self.service()?;
            // SAFETY: as for registration, with the synchronous removal selector.
            let result: Result<(), Retained<NSError>> =
                unsafe { msg_send![&*service, unregisterAndReturnError: _] };
            result.map_err(|error| refused(&error))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    use std::time::{SystemTime, UNIX_EPOCH};

    struct Recorded {
        status: Status,
        calls: RefCell<Vec<&'static str>>,
    }
    impl Registrar for Recorded {
        fn status(&self) -> io::Result<Status> {
            Ok(self.status)
        }
        fn register(&self) -> io::Result<()> {
            self.calls.borrow_mut().push("register");
            Ok(())
        }
        fn unregister(&self) -> io::Result<()> {
            self.calls.borrow_mut().push("unregister");
            Ok(())
        }
    }

    #[test]
    fn registration_follows_the_preference_and_leaves_user_held_items_alone() {
        use Status::*;
        assert_eq!(reconcile(true, NotRegistered), Some(Change::Register));
        assert_eq!(reconcile(true, Enabled), None);
        assert_eq!(reconcile(true, RequiresApproval), None);
        assert_eq!(reconcile(true, NotFound), None);
        assert_eq!(reconcile(false, Enabled), Some(Change::Unregister));
        assert_eq!(reconcile(false, RequiresApproval), Some(Change::Unregister));
        assert_eq!(reconcile(false, NotRegistered), None);
        assert_eq!(reconcile(false, NotFound), None);
        for (raw, status) in [
            (0, NotRegistered),
            (1, Enabled),
            (2, RequiresApproval),
            (3, NotFound),
        ] {
            assert_eq!(Status::from_raw(raw).unwrap(), status);
        }
        assert!(Status::from_raw(4).is_err());
        assert!(Status::from_raw(-1).is_err());
    }

    #[test]
    fn apply_performs_only_the_reconciled_change() {
        for (preference, status, expected) in [
            (true, Status::NotRegistered, vec!["register"]),
            (true, Status::RequiresApproval, vec![]),
            (false, Status::Enabled, vec!["unregister"]),
            (false, Status::NotRegistered, vec![]),
        ] {
            let registrar = Recorded {
                status,
                calls: RefCell::new(Vec::new()),
            };
            apply(&registrar, preference).unwrap();
            assert_eq!(*registrar.calls.borrow(), expected);
        }
    }

    #[test]
    fn only_a_bundle_directly_in_an_applications_folder_is_installed() {
        let payload = Path::new("Contents/Resources/app");
        let applications = [
            PathBuf::from("/Applications"),
            PathBuf::from("/Users/u/Applications"),
        ];
        assert_eq!(
            installed_bundle(
                Path::new("/Applications/Cadrumo.app/Contents/Resources/app"),
                payload,
                &applications
            ),
            Some(PathBuf::from("/Applications/Cadrumo.app"))
        );
        assert_eq!(
            installed_bundle(
                Path::new("/Users/u/Applications/Cadrumo Preview.app/Contents/Resources/app"),
                payload,
                &applications
            ),
            Some(PathBuf::from("/Users/u/Applications/Cadrumo Preview.app"))
        );
        for refused in [
            "/Users/u/build/macos-arm64/stage/Cadrumo.app/Contents/Resources/app",
            "/Applications/Tools/Cadrumo.app/Contents/Resources/app",
            "/Volumes/Cadrumo/Cadrumo.app/Contents/Resources/app",
            "/Applications/Cadrumo/Contents/Resources/app",
            "/Applications/Cadrumo.app/Contents/Resources/other",
            "Applications/Cadrumo.app/Contents/Resources/app",
            "/Contents/Resources/app",
        ] {
            assert_eq!(
                installed_bundle(Path::new(refused), payload, &applications),
                None,
                "{refused}"
            );
        }
        let relative = [PathBuf::from("Applications")];
        assert_eq!(
            installed_bundle(
                Path::new("/Applications/Cadrumo.app/Contents/Resources/app"),
                payload,
                &relative
            ),
            None
        );
        assert_eq!(
            installed_bundle(
                Path::new("/Applications/Cadrumo.app/Contents/Resources/app"),
                Path::new(""),
                &applications
            ),
            None
        );
    }

    #[test]
    fn exactly_one_regular_agent_declaration_is_admitted() {
        let bundle = std::env::temp_dir().join(format!(
            "manager-login-start-{}-{}.app",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        assert_eq!(bundled_agent(&bundle).unwrap(), None);
        let agents = bundle.join(AGENT_DIRECTORY);
        std::fs::create_dir_all(&agents).unwrap();
        assert_eq!(bundled_agent(&bundle).unwrap(), None);
        std::fs::write(agents.join("md.neve.cadrumo.manager.plist"), b"<plist/>").unwrap();
        assert_eq!(
            bundled_agent(&bundle).unwrap().as_deref(),
            Some("md.neve.cadrumo.manager.plist")
        );
        std::fs::write(agents.join("second.plist"), b"<plist/>").unwrap();
        assert_eq!(bundled_agent(&bundle).unwrap(), None);
        std::fs::remove_file(agents.join("second.plist")).unwrap();
        std::fs::create_dir(agents.join("nested.plist")).unwrap();
        assert_eq!(bundled_agent(&bundle).unwrap(), None);
        std::fs::remove_dir(agents.join("nested.plist")).unwrap();
        std::fs::write(agents.join("notes.txt"), b"").unwrap();
        assert_eq!(bundled_agent(&bundle).unwrap(), None);
        std::fs::remove_dir_all(bundle).unwrap();
    }
}
