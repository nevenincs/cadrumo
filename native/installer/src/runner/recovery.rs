//! Recovery authorizes another native transaction, never publication from inventory.
use super::*;
use cadrumo_application::installation::maintenance::{NativeRegistration, Phase, Product};
use std::os::windows::fs::MetadataExt;

/// A repair may start from damaged manifest bytes, so enumerate all existing
/// members under the already admitted namespace rather than trusting that manifest
/// to name every in-use image. The version lease is held before calling this.
pub(super) fn existing_package_files(root: &Path) -> Result<Vec<PathBuf>, Error> {
    let mut pending = vec![root.to_owned()];
    let mut files = Vec::new();
    let mut count = 0;
    while let Some(path) = pending.pop() {
        let metadata = match std::fs::symlink_metadata(&path) {
            Ok(metadata) => metadata,
            Err(error) if path == root && error.kind() == std::io::ErrorKind::NotFound => {
                return Ok(files);
            }
            Err(error) => return Err(error.into()),
        };
        count += 1;
        if count > 100_000 {
            return Err(Error::LimitExceeded);
        }
        if metadata.file_attributes() & 0x400 != 0 || (path == root && !metadata.is_dir()) {
            return Err(Error::Integrity(
                "repair inventory contains unsafe filesystem members".into(),
            ));
        }
        if metadata.is_dir() {
            for entry in std::fs::read_dir(&path)? {
                pending.push(entry?.path());
            }
            if pending.len() + count > 100_000 {
                return Err(Error::LimitExceeded);
            }
        } else if metadata.is_file() {
            files.push(path);
        } else {
            return Err(Error::Integrity(
                "repair inventory contains unsupported filesystem members".into(),
            ));
        }
    }
    Ok(files)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum RegistrationTransition {
    Consistent,
    ReconcilePending,
}

pub(super) fn registration_transition(
    published: Option<&NativeRegistration>,
    native: Option<&NativeOwner>,
    intended: &NativeOwner,
    pending: Option<&Product>,
    version_owner: &NativeOwner,
    manifest: &Sha256Digest,
) -> Result<RegistrationTransition, Error> {
    if published.is_some_and(|registration| registration.phase == RegistrationPhase::Removing) {
        return Err(Error::Busy);
    }
    let expected = published
        .filter(|registration| registration.phase == RegistrationPhase::Ready)
        .map(|registration| &registration.owner);
    if expected == native {
        return Ok(RegistrationTransition::Consistent);
    }
    // Complete native inventory may identify only this operation's intended
    // registration, or absence. Another product must never be adopted/replaced.
    if native.is_some_and(|owner| owner != intended)
        || !pending.is_some_and(|product| {
            product.phase == Phase::Pending
                && product.owner == *version_owner
                && product.manifest_sha256 == *manifest
        })
    {
        return Err(Error::Integrity(
            "interrupted native settlement differs from reservation".into(),
        ));
    }
    Ok(RegistrationTransition::ReconcilePending)
}

/// Existing products are repaired only after the native cached definition proves
/// the same exact role/version/payload and protocol identity as the incoming pair.
pub(super) fn current_product(
    plan: &Plan,
    admission: &Request,
    owner: &NativeOwner,
    role: crate::owner::Role,
) -> Result<Option<crate::custody::CachedCustody>, Error> {
    match MsiInventory.locate(owner)? {
        None => return Ok(None),
        Some(observed) if observed == *owner => {}
        Some(_) => {
            return Err(Error::Integrity(
                "installed product belongs to another native owner".into(),
            ));
        }
    }
    let (definition, custody) = windows::cached_product(owner)?;
    let metadata = definition
        .owner
        .as_ref()
        .ok_or_else(|| Error::Integrity("cached repair product has no owner protocol".into()))?;
    let family = usize::from(role == crate::owner::Role::Registration);
    if definition.family != admission.permitted_families[family]
        || definition.version != plan.version
        || definition.ownership
            != (windows::PackageOwnership {
                schema: 1,
                application_id: plan.contract.installation_identity.application_id.clone(),
                channel: plan.contract.installation_identity.channel.clone(),
                platform: plan.contract.layout.platform.clone(),
                version: plan.version.clone(),
                role: role.as_str().into(),
                manifest_sha256: plan.manifest_sha256.clone(),
            })
        || metadata.schema != 2
        || metadata.scope != plan.scope
        || metadata.product_code != definition.code
        || metadata.role != role
        || metadata.identity.application_id != definition.ownership.application_id
        || metadata.identity.channel != definition.ownership.channel
        || metadata.identity.platform != definition.ownership.platform
        || Some(&metadata.publication) != plan.contract.layout.installation.publication.as_ref()
        || definition.admission.scope != plan.scope
        || definition.admission.permitted_families != admission.permitted_families
        || definition.admission.conflicting_families != admission.conflicting_families
    {
        return Err(Error::Integrity(
            "cached repair product identity differs".into(),
        ));
    }
    Ok(Some(custody))
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::installation::maintenance::NativeContext;

    #[test]
    fn interrupted_settlement_requires_exact_pending_identity_and_does_not_resume_uninstall() {
        let root = tempfile::tempdir().unwrap();
        let owner = |code: &str| {
            NativeOwner::new(code.into(), NativeContext::Machine, root.path().to_owned()).unwrap()
        };
        let version = owner("10000000-0000-0000-0000-000000000001");
        let intended = owner("20000000-0000-0000-0000-000000000001");
        let old = owner("20000000-0000-0000-0000-000000000002");
        let digest = Sha256Digest::new("a".repeat(64)).unwrap();
        let mut pending = Product {
            owner: version.clone(),
            manifest_sha256: digest.clone(),
            phase: Phase::Pending,
        };
        let mut published = NativeRegistration {
            owner: old.clone(),
            phase: RegistrationPhase::Ready,
        };
        let decide = |published: Option<&NativeRegistration>,
                      native: Option<&NativeOwner>,
                      pending: Option<&Product>| {
            registration_transition(published, native, &intended, pending, &version, &digest)
        };
        assert_eq!(
            decide(None, None, None).unwrap(),
            RegistrationTransition::Consistent
        );
        assert_eq!(
            decide(Some(&published), Some(&old), None).unwrap(),
            RegistrationTransition::Consistent
        );
        for published in [None, Some(&published)] {
            assert_eq!(
                decide(published, Some(&intended), Some(&pending)).unwrap(),
                RegistrationTransition::ReconcilePending
            );
            assert!(decide(published, Some(&intended), None).is_err());
        }
        assert_eq!(
            decide(Some(&published), None, Some(&pending)).unwrap(),
            RegistrationTransition::ReconcilePending
        );
        assert!(decide(None, Some(&old), Some(&pending)).is_err());
        pending.phase = Phase::Ready;
        assert!(decide(None, Some(&intended), Some(&pending)).is_err());
        pending.phase = Phase::Removing;
        assert!(decide(None, Some(&intended), Some(&pending)).is_err());
        pending.phase = Phase::Pending;
        pending.manifest_sha256 = Sha256Digest::new("b".repeat(64)).unwrap();
        assert!(decide(None, Some(&intended), Some(&pending)).is_err());
        pending.manifest_sha256 = digest.clone();
        pending.owner = NativeOwner::new(
            version.product_code().into(),
            NativeContext::User {
                sid: "S-1-5-21-1000".into(),
            },
            root.path().to_owned(),
        )
        .unwrap();
        assert!(decide(None, Some(&intended), Some(&pending)).is_err());
        pending.owner = version.clone();
        published.phase = RegistrationPhase::Removing;
        assert!(decide(Some(&published), Some(&intended), Some(&pending)).is_err());
        published.phase = RegistrationPhase::Absent;
        assert_eq!(
            decide(Some(&published), Some(&intended), Some(&pending)).unwrap(),
            RegistrationTransition::ReconcilePending
        );
    }
}
#[test]
fn repair_liveness_inventory_includes_unmanifested_files_and_refuses_non_directory_roots() {
    let root = tempfile::tempdir().unwrap();
    assert!(
        existing_package_files(&root.path().join("absent"))
            .unwrap()
            .is_empty()
    );
    std::fs::create_dir(root.path().join("nested")).unwrap();
    let dll = root.path().join("nested/old-runtime.dll");
    let manifest = root.path().join("damaged-manifest.json");
    std::fs::write(&dll, b"still loaded independently").unwrap();
    std::fs::write(&manifest, b"not a usable inventory").unwrap();
    let files = existing_package_files(root.path()).unwrap();
    assert_eq!(files.len(), 2);
    assert!(files.contains(&dll) && files.contains(&manifest));
    assert!(existing_package_files(&manifest).is_err());
}
