//! Stable entry dispatch precedes the session lock and runtime ownership.
use crate::supervision::environment::ManagedLocations;
use cadrumo_application::installation::{DiscoveryContract, RegistrationHints, Selection};
use std::{
    io,
    os::windows::process::CommandExt,
    path::Path,
    process::{Command, Stdio},
};

/// Admission belongs to this process and this selected manager image.
/// Its locations are available for diagnostics without exposing a new admission path.
pub struct CurrentInstallation {
    locations: ManagedLocations,
    pub(crate) lease: Option<std::sync::Arc<cadrumo_application::installation::maintenance::Lease>>,
}

impl CurrentInstallation {
    pub fn locations(&self) -> &ManagedLocations {
        &self.locations
    }

    pub(crate) fn into_parts(
        self,
    ) -> (
        ManagedLocations,
        Option<std::sync::Arc<cadrumo_application::installation::maintenance::Lease>>,
    ) {
        (self.locations, self.lease)
    }
}

pub enum DispatchOutcome {
    Dispatched,
    Current(CurrentInstallation),
}

pub fn select(image: &Path) -> io::Result<Selection> {
    let contract: DiscoveryContract =
        serde_json::from_str(crate::contract::INSTALLATION_CONTRACT).map_err(io::Error::other)?;
    let registered = cadrumo_platform::installation::manager_entry_points(
        &contract.installation_identity.application_id,
    )?;
    discover(
        &contract,
        image,
        &RegistrationHints {
            this_user: registered.this_user.as_deref(),
            all_users: registered.all_users.as_deref(),
        },
    )
}

fn discover(
    contract: &DiscoveryContract,
    image: &Path,
    registered: &RegistrationHints<'_>,
) -> io::Result<Selection> {
    #[cfg(test)]
    DISCOVERIES.with(|count| count.set(count.get() + 1));
    contract
        .discover(image, registered)
        .map_err(io::Error::other)
}

fn current_installation(
    image: &Path,
    selected: &Selection,
    locations: ManagedLocations,
) -> io::Result<Option<CurrentInstallation>> {
    if std::fs::canonicalize(locations.package_root())? != std::fs::canonicalize(&selected.package)?
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "managed package differs from selected installation",
        ));
    }
    if std::fs::canonicalize(image)? == std::fs::canonicalize(&selected.manager)? {
        Ok(Some(CurrentInstallation {
            locations,
            lease: selected.lease.clone(),
        }))
    } else {
        Ok(None)
    }
}

/// Every successor repeats native admission, job escape and catalogue verification.
/// Dispatch acknowledgement conveys no runtime readiness or ownership.
pub fn dispatch_newest(image: &Path) -> io::Result<DispatchOutcome> {
    let selected = select(image)?;
    // Validate management eligibility before dispatch; never clear an override into eligibility.
    let locations = ManagedLocations::resolve(&selected.manager)?;
    if let Some(current) = current_installation(image, &selected, locations)? {
        return Ok(DispatchOutcome::Current(current));
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
    Ok(DispatchOutcome::Dispatched)
}

#[cfg(test)]
thread_local! {
    static DISCOVERIES: std::cell::Cell<usize> = const { std::cell::Cell::new(0) };
}

#[cfg(all(test, target_arch = "x86_64"))]
mod tests {
    use super::*;
    use cadrumo_application::diagnostics::lifecycle::InspectionRefusal;
    use serde_json::{Value, json};
    use sha2::{Digest, Sha256};
    use std::{
        fs,
        path::PathBuf,
        sync::atomic::{AtomicUsize, Ordering},
    };

    struct Fixture {
        root: PathBuf,
        contract: DiscoveryContract,
        package: PathBuf,
        manager: PathBuf,
        storage: PathBuf,
    }

    impl Fixture {
        fn new() -> Self {
            static NEXT: AtomicUsize = AtomicUsize::new(0);
            let root = std::env::temp_dir().join(format!(
                "manager-current-installation-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            fs::create_dir(&root).unwrap();
            let contract: DiscoveryContract =
                serde_json::from_str(crate::contract::INSTALLATION_CONTRACT).unwrap();
            let prefix = root.join("installed fixture ü space");
            let marker = contract.layout.installation.marker.under(&prefix);
            fs::create_dir_all(marker.parent().unwrap()).unwrap();
            fs::write(
                marker,
                serde_json::to_vec(&json!({
                    "schema": contract.layout.installation.schema,
                    "application_id": contract.installation_identity.application_id,
                    "channel": contract.installation_identity.channel,
                    "platform": contract.layout.platform,
                    "abi": contract.layout.abi,
                }))
                .unwrap(),
            )
            .unwrap();
            let package = contract
                .layout
                .installation
                .versions
                .under(&prefix)
                .join(crate::identity::VERSION);
            let manifest = contract.layout.files.package_manifest.under(&package);
            fs::create_dir_all(manifest.parent().unwrap()).unwrap();
            let member = contract.manager_member().unwrap();
            let manager = member.under(&package);
            // Discovery checks this host PE and its digest without executing it.
            let source =
                PathBuf::from(std::env::var_os("SystemRoot").unwrap()).join("System32/where.exe");
            let bytes = fs::read(source).unwrap();
            fs::write(&manager, &bytes).unwrap();
            fs::write(member.under(&prefix), &bytes).unwrap();
            let dependency = b"inventoried fixture dependency";
            fs::write(package.join("fixture-dependency.bin"), dependency).unwrap();
            fs::write(
                manifest,
                serde_json::to_vec(&json!({
                    "build": {
                        "application_id": contract.installation_identity.application_id,
                        "channel": contract.installation_identity.channel,
                        "version": crate::identity::VERSION,
                        "target": "windows-x86-64",
                    },
                    "layout": {"abi": contract.layout.abi, "platform": contract.layout.platform},
                    "python": "fixture", "distributions": {},
                    "files": {
                        (member.as_str()): format!("{:x}", Sha256::digest(bytes)),
                        "fixture-dependency.bin": format!("{:x}", Sha256::digest(dependency)),
                    },
                    "user_docs": {"directory": "docs/user", "bundled": false},
                }))
                .unwrap(),
            )
            .unwrap();
            let storage = root.join("storage");
            fs::create_dir(&storage).unwrap();
            Self {
                root,
                contract,
                package,
                manager,
                storage,
            }
        }

        fn locations(&self) -> ManagedLocations {
            ManagedLocations::fixture(self.package.clone(), self.storage.clone()).unwrap()
        }

        fn admit(&self) -> io::Result<CurrentInstallation> {
            let selected = discover(&self.contract, &self.manager, &RegistrationHints::default())?;
            current_installation(&self.manager, &selected, self.locations())?
                .ok_or_else(|| io::ErrorKind::InvalidData.into())
        }

        fn amend_manifest(&self, edit: impl FnOnce(&mut Value)) {
            let path = self
                .contract
                .layout
                .files
                .package_manifest
                .under(&self.package);
            let mut manifest = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
            edit(&mut manifest);
            fs::write(path, serde_json::to_vec(&manifest).unwrap()).unwrap();
        }
    }

    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.root);
        }
    }

    #[test]
    fn current_admission_verifies_once_and_preparation_does_not_reinspect_the_package() {
        let fixture = Fixture::new();
        let discoveries = DISCOVERIES.with(std::cell::Cell::get);
        let inspections = crate::installed::package_inspections();
        let admitted = fixture.admit().unwrap();
        assert_eq!(DISCOVERIES.with(std::cell::Cell::get), discoveries + 1);
        assert_eq!(admitted.locations(), &fixture.locations());
        // Only preparation now remains. Removing the manifest makes a repeated
        // inspection fail; the deliberately absent interpreter must still be probed.
        fs::remove_file(
            fixture
                .contract
                .layout
                .files
                .package_manifest
                .under(&fixture.package),
        )
        .unwrap();
        let failure = match crate::installed::InstalledRuntime::from_admitted(admitted) {
            Ok(_) => panic!("a missing fixture interpreter was accepted"),
            Err(failure) => failure,
        };
        assert_eq!(failure.refusal, InspectionRefusal::RuntimeProbeFailed);
        assert_eq!(crate::installed::package_inspections(), inspections);
        let failure = match crate::installed::InstalledRuntime::inspect(&fixture.locations()) {
            Ok(_) => panic!("an absent package manifest was accepted"),
            Err(failure) => failure,
        };
        assert_eq!(failure.refusal, InspectionRefusal::PackageUnavailable);
        assert_eq!(crate::installed::package_inspections(), inspections + 1);
    }

    #[test]
    fn current_admission_still_refuses_the_failed_version_marker_before_probing() {
        let fixture = Fixture::new();
        let admitted = fixture.admit().unwrap();
        let inspections = crate::installed::package_inspections();
        let marker = fixture
            .storage
            .join(".runtime/manager-failed-versions.json");
        fs::create_dir(marker.parent().unwrap()).unwrap();
        fs::write(marker, b"synthetic failed version").unwrap();
        let failure = match crate::installed::InstalledRuntime::from_admitted(admitted) {
            Ok(_) => panic!("a failed version marker was accepted"),
            Err(failure) => failure,
        };
        assert_eq!(failure.refusal, InspectionRefusal::FailedVersionMarker);
        assert_eq!(crate::installed::package_inspections(), inspections);
    }

    #[test]
    fn current_proof_requires_the_selected_image_and_matching_resolved_package() {
        let fixture = Fixture::new();
        let selected = discover(
            &fixture.contract,
            &fixture.manager,
            &RegistrationHints::default(),
        )
        .unwrap();
        let other_image = fixture.root.join("other-manager.exe");
        fs::copy(&fixture.manager, &other_image).unwrap();
        assert!(
            current_installation(&other_image, &selected, fixture.locations())
                .unwrap()
                .is_none()
        );
        assert!(
            current_installation(
                &fixture.root.join("absent-manager.exe"),
                &selected,
                fixture.locations(),
            )
            .is_err()
        );
        let other_package = fixture.root.join("other-package");
        fs::create_dir(&other_package).unwrap();
        let locations = ManagedLocations::fixture(other_package, fixture.storage.clone()).unwrap();
        assert!(matches!(
            current_installation(&fixture.manager, &selected, locations),
            Err(error) if error.kind() == io::ErrorKind::InvalidData
        ));
        let locations =
            ManagedLocations::fixture(fixture.root.join("absent-package"), fixture.storage.clone())
                .unwrap();
        assert!(current_installation(&fixture.manager, &selected, locations).is_err());
    }

    #[test]
    fn catalogue_admission_refuses_absent_damaged_and_foreign_packages() {
        let fixture = Fixture::new();
        let dependency = fixture.package.join("fixture-dependency.bin");
        fs::remove_file(&dependency).unwrap();
        assert!(fixture.admit().is_err());
        fs::write(&dependency, b"inventoried fixture dependency").unwrap();
        assert!(fixture.admit().is_ok());
        fs::write(&dependency, b"damaged fixture dependency").unwrap();
        assert!(fixture.admit().is_err());
        fs::write(&dependency, b"inventoried fixture dependency").unwrap();
        fixture.amend_manifest(|manifest| {
            manifest["build"]["application_id"] = json!("fixture.foreign");
        });
        assert!(fixture.admit().is_err());
    }
}
