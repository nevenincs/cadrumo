//! Read-only discovery of complete immutable versions beneath an explicit install prefix.
//! Metadata and hashes establish package consistency, not publisher authenticity.
mod launch_guard;
pub mod maintenance;
use crate::{
    binary::{self, BinaryExpectation},
    component::Cancellation,
    error::Error,
    filesystem,
    package::{PackageManifest, Readiness},
    value::{RelativePath, Sha256Digest},
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Path, PathBuf},
    sync::Arc,
};

/// Bounded native installer diagnostics: no filesystem coordinates or error text.
#[derive(Debug, Serialize)]
pub struct CandidateRejection {
    stage: CandidateStage,
    kind: CandidateKind,
    #[serde(skip_serializing_if = "Option::is_none")]
    member_sha256: Option<String>,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
enum CandidateStage {
    Release,
    Root,
    Manifest,
    VersionIdentity,
    Inventory,
    Manager,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "snake_case")]
enum CandidateKind {
    Missing,
    Incompatible,
    NeedsUser,
    IoNotFound,
    IoPermissionDenied,
    IoOther,
    Json,
    Archive,
    Invalid,
    Integrity,
    Busy,
    Cancelled,
    LimitExceeded,
    Download,
    TimedOut,
    ProbeFailed,
}

struct CandidateFailure {
    error: Error,
    rejection: CandidateRejection,
}

impl CandidateFailure {
    fn new(error: Error, stage: CandidateStage) -> Self {
        let kind = match &error {
            Error::Io(error) => match error.kind() {
                std::io::ErrorKind::NotFound => CandidateKind::IoNotFound,
                std::io::ErrorKind::PermissionDenied => CandidateKind::IoPermissionDenied,
                _ => CandidateKind::IoOther,
            },
            Error::Json(_) => CandidateKind::Json,
            Error::Archive(_) => CandidateKind::Archive,
            Error::Invalid(_) => CandidateKind::Invalid,
            Error::Incompatible(_) => CandidateKind::Incompatible,
            Error::Integrity(_) => CandidateKind::Integrity,
            Error::Busy => CandidateKind::Busy,
            Error::Cancelled => CandidateKind::Cancelled,
            Error::LimitExceeded => CandidateKind::LimitExceeded,
            Error::Download => CandidateKind::Download,
            Error::TimedOut => CandidateKind::TimedOut,
            Error::ProbeFailed => CandidateKind::ProbeFailed,
        };
        Self {
            error,
            rejection: CandidateRejection {
                stage,
                kind,
                member_sha256: None,
            },
        }
    }

    fn readiness(readiness: &Readiness) -> Self {
        let (kind, member) = match readiness {
            Readiness::Missing(member) => (CandidateKind::Missing, Some(member.as_str())),
            Readiness::Incompatible(reason) if reason == "package target or ABI differs" => {
                (CandidateKind::Incompatible, None)
            }
            Readiness::Incompatible(member) => (
                CandidateKind::Incompatible,
                Some(member.strip_prefix("unexpected file: ").unwrap_or(member)),
            ),
            Readiness::NeedsUser(_) => (CandidateKind::NeedsUser, None),
            Readiness::Ready => (CandidateKind::Integrity, None),
        };
        let member_sha256 = member
            .and_then(|member| RelativePath::new(member).ok())
            .map(|member| format!("{:x}", Sha256::digest(member.as_str().as_bytes())));
        Self {
            error: Error::Integrity("incomplete installed version".into()),
            rejection: CandidateRejection {
                stage: CandidateStage::Inventory,
                kind,
                member_sha256,
            },
        }
    }
}

#[cfg(test)]
mod candidate_diagnostic_tests {
    use super::*;

    #[test]
    fn readiness_rejection_retains_only_the_relative_member_digest() {
        let member = "cadrumo/private-member.json";
        let checksum = format!("{:x}", Sha256::digest(member.as_bytes()));
        for (readiness, kind) in [
            (Readiness::Missing(member.into()), "missing"),
            (Readiness::Incompatible(member.into()), "incompatible"),
            (
                Readiness::Incompatible(format!("unexpected file: {member}")),
                "incompatible",
            ),
        ] {
            let failure = CandidateFailure::readiness(&readiness);
            let value = serde_json::to_value(failure.rejection).unwrap();
            assert_eq!(value["stage"], "inventory");
            assert_eq!(value["kind"], kind);
            assert_eq!(value["member_sha256"], checksum);
            assert!(!value.to_string().contains(member));
        }
        for readiness in [
            Readiness::Incompatible("package target or ABI differs".into()),
            Readiness::Missing(r"C:\private\member.json".into()),
            Readiness::Missing("../private.json".into()),
            Readiness::NeedsUser("private arbitrary explanation".into()),
        ] {
            let value =
                serde_json::to_value(CandidateFailure::readiness(&readiness).rejection).unwrap();
            assert!(value.get("member_sha256").is_none());
            assert!(!value.to_string().contains("private"));
        }
    }

    #[test]
    fn native_error_projection_has_finite_kinds_without_error_display() {
        for (error, kind) in [
            (
                Error::Io(std::io::Error::new(
                    std::io::ErrorKind::NotFound,
                    "private missing path",
                )),
                "io_not_found",
            ),
            (
                Error::Io(std::io::Error::new(
                    std::io::ErrorKind::PermissionDenied,
                    "private permission detail",
                )),
                "io_permission_denied",
            ),
            (
                Error::Io(std::io::Error::other("private detail")),
                "io_other",
            ),
            (Error::Invalid("private input".into()), "invalid"),
            (Error::Integrity("private integrity".into()), "integrity"),
        ] {
            let failure = CandidateFailure::new(error, CandidateStage::Manifest);
            let value = serde_json::to_value(failure.rejection).unwrap();
            assert_eq!(value["stage"], "manifest");
            assert_eq!(value["kind"], kind);
            assert!(value.get("member_sha256").is_none());
            assert!(!value.to_string().contains("private"));
        }
    }
}

#[derive(Deserialize, Serialize)]
pub struct DiscoveryContract {
    pub layout: Layout,
    pub installation_identity: Identity,
}
#[derive(Deserialize, Serialize)]
pub struct Identity {
    pub application_id: String,
    pub channel: String,
}
#[derive(Deserialize, Serialize)]
pub struct Layout {
    pub abi: u32,
    pub platform: String,
    pub installation: Installation,
    pub files: Files,
    pub application_images: Vec<Image>,
    pub entrypoint_suffix: String,
}
#[derive(Deserialize, Serialize)]
pub struct Installation {
    pub schema: u32,
    pub marker: RelativePath,
    pub versions: RelativePath,
    pub maximum_versions: usize,
    #[serde(default)]
    pub publication: Option<RelativePath>,
    #[serde(default)]
    pub bootstrap: Option<Bootstrap>,
}

#[derive(Deserialize, Serialize)]
pub struct Bootstrap {
    pub directory: RelativePath,
    pub manifest: RelativePath,
}
#[derive(Deserialize, Serialize)]
pub struct Files {
    pub package_manifest: RelativePath,
}
#[derive(Deserialize, Serialize)]
pub struct Image {
    pub name: String,
    pub placement: String,
    pub target: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Marker {
    schema: u32,
    application_id: String,
    channel: String,
    platform: String,
    abi: u32,
    #[serde(default)]
    publication: Option<RelativePath>,
    #[serde(default)]
    launch_policy: Option<LaunchPolicy>,
}
#[derive(Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum LaunchPolicy {
    Portable,
    Native,
}
#[derive(Deserialize)]
struct VersionManifest {
    build: Build,
    #[serde(flatten)]
    package: PackageManifest,
}
#[derive(Deserialize)]
struct Build {
    application_id: String,
    version: String,
    channel: String,
    target: String,
}

#[derive(Clone, Debug)]
pub struct Selection {
    pub entrypoint: PathBuf,
    pub package: PathBuf,
    pub manager: PathBuf,
    pub version: [u32; 3],
    pub lease: Option<Arc<maintenance::Lease>>,
    pub registration: Option<maintenance::NativeOwner>,
}

/// Scoped native registrations are hints, verified through the same package catalogue.
#[derive(Default)]
pub struct RegistrationHints<'a> {
    pub this_user: Option<&'a Path>,
    pub all_users: Option<&'a Path>,
}

/// Distribution identity permits only a canonical numeric release triple.
pub fn version(value: &str) -> Result<[u32; 3], Error> {
    let parts: Vec<_> = value.split('.').collect();
    if parts.len() != 3
        || parts.iter().any(|p| {
            p.is_empty()
                || !p.bytes().all(|c| c.is_ascii_digit())
                || (p.len() > 1 && p.starts_with('0'))
        })
    {
        return Err(Error::Invalid("noncanonical installed version".into()));
    }
    let mut result = [0; 3];
    for (slot, part) in result.iter_mut().zip(parts) {
        *slot = part
            .parse()
            .map_err(|_| Error::Invalid("installed version overflows".into()))?;
    }
    Ok(result)
}

impl DiscoveryContract {
    pub fn manager_member(&self) -> Result<RelativePath, Error> {
        let mut images = self
            .layout
            .application_images
            .iter()
            .filter(|image| image.target == "rust_manager");
        let image = images
            .next()
            .ok_or_else(|| Error::Invalid("manager image is not declared".into()))?;
        if images.next().is_some() || image.placement != "." {
            return Err(Error::Invalid("manager must be a unique root image".into()));
        }
        let member = RelativePath::new(format!("{}{}", image.name, self.layout.entrypoint_suffix))?;
        if member.as_str().contains('/') {
            return Err(Error::Invalid("manager image is not root-level".into()));
        }
        Ok(member)
    }

    /// A package contributes only its structurally declared versioned prefix.
    /// A stable entry image contributes its own directory. No cwd or sibling guessing.
    pub fn local_prefix(&self, image: &Path) -> Option<PathBuf> {
        let directory = image.parent()?;
        if self.layout.installation.marker.under(directory).is_file() {
            return Some(directory.to_path_buf());
        }
        version(directory.file_name()?.to_str()?).ok()?;
        let versions = directory.parent()?;
        let prefix = versions.parent()?;
        (self.layout.installation.versions.under(prefix) == versions).then(|| prefix.to_path_buf())
    }

    /// Registered entry points are hints; every prefix, complete package and executable
    /// is verified before it can be returned. A complete this-user registration wins
    /// before version comparison across the local and all-users fallback prefixes.
    pub fn discover(
        &self,
        image: &Path,
        registered: &RegistrationHints<'_>,
    ) -> Result<Selection, Error> {
        self.discover_cancellable(image, registered, &Cancellation::default())
    }

    /// Cancellation is fatal through prefix and version fallback, not a damaged candidate.
    pub fn discover_cancellable(
        &self,
        image: &Path,
        registered: &RegistrationHints<'_>,
        cancellation: &Cancellation,
    ) -> Result<Selection, Error> {
        cancellation.check()?;
        let member = self.manager_member()?;
        let mut prefixes: Vec<(PathBuf, bool)> = self
            .local_prefix(image)
            .into_iter()
            .map(|prefix| (prefix, false))
            .collect();
        for (hint, this_user) in [(registered.this_user, true), (registered.all_users, false)] {
            cancellation.check()?;
            let Some(entry) = hint else { continue };
            if entry.file_name() == Some(Path::new(member.as_str()).as_os_str())
                && let Some(prefix) = entry.parent()
            {
                if let Some((_, preferred)) = prefixes.iter_mut().find(|(p, _)| p == prefix) {
                    *preferred |= this_user;
                } else {
                    prefixes.push((prefix.to_path_buf(), this_user));
                }
            }
        }
        let mut preferred: Option<Selection> = None;
        let mut newest: Option<Selection> = None;
        for (prefix, this_user) in prefixes {
            cancellation.check()?;
            let inspected = self.select_for_launch_cancellable(&prefix, cancellation);
            cancellation.check()?;
            if matches!(inspected, Err(Error::Cancelled)) {
                return Err(Error::Cancelled);
            }
            if let Ok(candidate) = inspected {
                let winner = if this_user {
                    &mut preferred
                } else {
                    &mut newest
                };
                if winner
                    .as_ref()
                    .is_none_or(|old| candidate.version > old.version)
                {
                    *winner = Some(candidate);
                }
            }
        }
        cancellation.check()?;
        preferred.or(newest).ok_or_else(|| {
            Error::Incompatible("no complete compatible manager installation".into())
        })
    }

    pub fn inspect(&self, prefix: &Path) -> Result<Selection, Error> {
        self.inspect_cancellable(prefix, &Cancellation::default())
    }

    pub fn inspect_cancellable(
        &self,
        prefix: &Path,
        cancellation: &Cancellation,
    ) -> Result<Selection, Error> {
        self.read_catalogue(prefix, cancellation, false, true)?
            .into_iter()
            .next()
            .ok_or_else(|| Error::Incompatible("no complete compatible installed version".into()))
    }

    /// The installed version a start runs. It reads each candidate's manifest and verifies its
    /// manager executable, but never hashes the package: that is the installer's work, done
    /// once when the version is published, not on every manager or desktop start.
    pub fn select_for_launch_cancellable(
        &self,
        prefix: &Path,
        cancellation: &Cancellation,
    ) -> Result<Selection, Error> {
        self.read_catalogue(prefix, cancellation, false, false)?
            .into_iter()
            .next()
            .ok_or_else(|| Error::Incompatible("no complete compatible installed version".into()))
    }

    /// Complete versions ordered newest first. Every returned selection retains its
    /// publication lease; callers must keep that lease while the version is in use.
    /// The stable anchor is verified against this same admitted inventory.
    pub fn catalogue_cancellable(
        &self,
        prefix: &Path,
        cancellation: &Cancellation,
    ) -> Result<Vec<Selection>, Error> {
        self.read_catalogue(prefix, cancellation, true, true)
    }

    fn read_catalogue(
        &self,
        prefix: &Path,
        cancellation: &Cancellation,
        all: bool,
        full: bool,
    ) -> Result<Vec<Selection>, Error> {
        cancellation.check()?;
        filesystem::absolute_root(prefix)?;
        let layout = &self.layout;
        let marker: Marker = filesystem::json_file_cancellable(
            &layout.installation.marker.under(prefix),
            cancellation,
        )?;
        if marker.schema != layout.installation.schema
            || marker.application_id != self.installation_identity.application_id
            || marker.channel != self.installation_identity.channel
            || marker.platform != layout.platform
            || marker.abi != layout.abi
        {
            return Err(Error::Incompatible("installation identity differs".into()));
        }
        let versions = layout.installation.versions.under(prefix);
        let publication = match marker.publication.as_ref() {
            Some(path) if Some(path) == layout.installation.publication.as_ref() => {
                Some(maintenance::Store::new(
                    path.under(prefix),
                    maintenance::Identity {
                        application_id: marker.application_id.clone(),
                        channel: marker.channel.clone(),
                        platform: marker.platform.clone(),
                    },
                    layout.installation.maximum_versions,
                )?)
            }
            Some(_) => {
                return Err(Error::Invalid(
                    "undeclared installation publication path".into(),
                ));
            }
            None => None,
        };
        let registration = publication
            .as_ref()
            .map(|store| store.snapshot())
            .transpose()?
            .and_then(|snapshot| {
                snapshot
                    .registration()
                    .filter(|registration| {
                        registration.phase == maintenance::RegistrationPhase::Ready
                    })
                    .map(|registration| registration.owner.clone())
            });
        filesystem::absolute_root(&versions)?;
        let member = self.manager_member()?;
        let entrypoint = member.under(prefix);
        let expected = BinaryExpectation::host()?;
        let mut complete = Vec::new();
        let mut entry_verified = false;
        let mut candidates = Vec::new();
        for (count, entry) in fs::read_dir(&versions)?.enumerate() {
            cancellation.check()?;
            if count >= layout.installation.maximum_versions {
                return Err(Error::LimitExceeded);
            }
            let entry = entry?;
            let Some(name) = entry.file_name().to_str().map(str::to_owned) else {
                continue;
            };
            let Ok(number) = version(&name) else { continue };
            candidates.push((number, name, entry.path()));
        }
        // Enumeration is bounded before selection: invalid names and entries after
        // a ready candidate still count toward the installation's version limit.
        candidates.sort_unstable_by_key(|candidate| std::cmp::Reverse(candidate.0));
        for (number, name, package) in candidates {
            cancellation.check()?;
            let inspect = || -> Result<_, Error> {
                let lease = publication
                    .as_ref()
                    .map(|store| {
                        let manifest = self.manifest_digest(&package, cancellation)?;
                        store.acquire(&name, &manifest).map(Arc::new)
                    })
                    .transpose()?;
                let (manager, digest) = self
                    .inspect_package_diagnostic(&package, &name, full, cancellation)
                    .map_err(|failure| failure.error)?;
                Ok((manager, digest, lease))
            };
            let inspected = inspect();
            cancellation.check()?;
            if matches!(inspected, Err(Error::Cancelled)) {
                return Err(Error::Cancelled);
            }
            let Ok((manager, digest, lease)) = inspected else {
                continue;
            };
            // A stable entry can still contain an older manager's bytes. It must match
            // a complete version; its startup redirects before claiming runtime ownership.
            if !entry_verified {
                cancellation.check()?;
                entry_verified = binary::verify(&entrypoint, &digest, expected).is_ok();
                cancellation.check()?;
            }
            if all || complete.is_empty() {
                complete.push(Selection {
                    entrypoint: entrypoint.clone(),
                    package,
                    manager,
                    version: number,
                    lease,
                    registration: registration.clone(),
                });
            }
            if !all && entry_verified {
                break;
            }
        }
        if !entry_verified {
            cancellation.check()?;
            return Err(Error::Integrity(
                "stable manager entry point is missing or modified".into(),
            ));
        }
        cancellation.check()?;
        Ok(complete)
    }

    /// Select an exact still-complete version only for a verified rollback or
    /// held-child designation. Ordinary launchers continue to choose the newest.
    pub fn inspect_version_cancellable(
        &self,
        prefix: &Path,
        release: &str,
        cancellation: &Cancellation,
    ) -> Result<Selection, Error> {
        let requested = version(release)?;
        self.catalogue_cancellable(prefix, cancellation)?
            .into_iter()
            .find(|candidate| candidate.version == requested)
            .ok_or_else(|| Error::Incompatible("requested version is not complete".into()))
    }

    /// Verify candidate inventory before native transaction publication. This
    /// grants neither discovery eligibility nor a process-use lease.
    pub fn verify_candidate(&self, package: &Path, release: &str) -> Result<(), Error> {
        version(release)?;
        self.inspect_package(package, release, &Cancellation::default())
            .map(|_| ())
    }

    /// Same candidate inspection, projected without arbitrary error or path text.
    pub fn verify_candidate_diagnostic(
        &self,
        package: &Path,
        release: &str,
    ) -> Result<(), CandidateRejection> {
        version(release)
            .map_err(|error| CandidateFailure::new(error, CandidateStage::Release).rejection)?;
        self.inspect_package_diagnostic(package, release, true, &Cancellation::default())
            .map(|_| ())
            .map_err(|failure| failure.rejection)
    }

    pub(crate) fn manifest_digest(
        &self,
        package: &Path,
        cancellation: &Cancellation,
    ) -> Result<Sha256Digest, Error> {
        cancellation.check()?;
        let bytes = filesystem::json_bytes(&self.layout.files.package_manifest.under(package))?;
        filesystem::digest_reader(&mut bytes.as_slice(), cancellation)
    }

    pub(crate) fn inspect_package(
        &self,
        package: &Path,
        name: &str,
        cancellation: &Cancellation,
    ) -> Result<(PathBuf, Sha256Digest), Error> {
        self.inspect_package_diagnostic(package, name, true, cancellation)
            .map_err(|failure| failure.error)
    }

    /// ``full`` hashes every package file, for installation, repair and rollback; a launch passes
    /// ``false`` and checks only the version's identity, target and manager executable.
    fn inspect_package_diagnostic(
        &self,
        package: &Path,
        name: &str,
        full: bool,
        cancellation: &Cancellation,
    ) -> Result<(PathBuf, Sha256Digest), CandidateFailure> {
        filesystem::absolute_root(package)
            .map_err(|error| CandidateFailure::new(error, CandidateStage::Root))?;
        let layout = &self.layout;
        let manifest: VersionManifest = filesystem::json_file_cancellable(
            &layout.files.package_manifest.under(package),
            cancellation,
        )
        .map_err(|error| CandidateFailure::new(error, CandidateStage::Manifest))?;
        let target = if layout.platform == "windows-x64" {
            "windows-x86-64"
        } else {
            &layout.platform
        };
        if manifest.build.application_id != self.installation_identity.application_id
            || manifest.build.channel != self.installation_identity.channel
            || manifest.build.version != name
            || manifest.build.target != target
        {
            return Err(CandidateFailure::new(
                Error::Incompatible("version identity differs".into()),
                CandidateStage::VersionIdentity,
            ));
        }
        let files = if full {
            let inspected = manifest
                .package
                .inspect_cancellable(
                    package,
                    &layout.files.package_manifest,
                    &layout.platform,
                    layout.abi,
                    cancellation,
                )
                .map_err(|error| CandidateFailure::new(error, CandidateStage::Inventory))?;
            if inspected.readiness != Readiness::Ready {
                return Err(CandidateFailure::readiness(&inspected.readiness));
            }
            inspected.manifest.files
        } else {
            // A launch trusts the installer's publication of a complete version: it checks the
            // version's target and the manager it is about to run, never every package file.
            if manifest.package.layout.platform != layout.platform
                || manifest.package.layout.abi != layout.abi
            {
                return Err(CandidateFailure::readiness(&Readiness::Incompatible(
                    "package target or ABI differs".into(),
                )));
            }
            // An interrupted or damaged version missing a file every start needs is passed over.
            for critical in &manifest.package.startup_files {
                let present = fs::symlink_metadata(critical.under(package))
                    .is_ok_and(|metadata| metadata.is_file());
                if !present {
                    return Err(CandidateFailure::readiness(&Readiness::Missing(
                        critical.as_str().into(),
                    )));
                }
            }
            manifest.package.files
        };
        let member = self
            .manager_member()
            .map_err(|error| CandidateFailure::new(error, CandidateStage::Manager))?;
        let digest = files
            .get(&member)
            .ok_or_else(|| {
                CandidateFailure::new(
                    Error::Invalid("manager absent from inventory".into()),
                    CandidateStage::Manager,
                )
            })?
            .clone();
        let manager = member.under(package);
        cancellation
            .check()
            .map_err(|error| CandidateFailure::new(error, CandidateStage::Manager))?;
        let expected = BinaryExpectation::host()
            .map_err(|error| CandidateFailure::new(error, CandidateStage::Manager))?;
        binary::verify(&manager, &digest, expected)
            .map_err(|error| CandidateFailure::new(error, CandidateStage::Manager))?;
        cancellation
            .check()
            .map_err(|error| CandidateFailure::new(error, CandidateStage::Manager))?;
        Ok((manager, digest))
    }
}
