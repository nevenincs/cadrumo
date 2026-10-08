//! Exact anchored-install verification before any native transaction or mutation.
use super::*;
use cadrumo_application::installation::maintenance::Lease;
use cadrumo_application::installation::maintenance::Phase;

pub(super) struct Verified {
    _namespace: crate::publication::PublicationCustody,
    _state: Held<Vec<crate::custody::CachedCustody>>,
}

struct Held<C> {
    _maintenance: Lease,
    _version: Lease,
    _cache: C,
    _files: Vec<crate::custody::FileCustody>,
}

/// Only native observations are replaceable by isolated tests. Store locking,
/// publication checks and candidate byte verification use their real owners.
trait Observation {
    type Custody;
    fn bind(
        &mut self,
        plan: &Plan,
        admission: &Request,
        owner: &NativeOwner,
        registration: &NativeOwner,
    ) -> Result<(crate::registration::Description, Self::Custody), Error>;
    fn resources(
        &mut self,
        description: &crate::registration::Description,
        registration: &NativeOwner,
    ) -> Result<Vec<crate::custody::FileCustody>, Error>;
    fn recheck(
        &mut self,
        plan: &Plan,
        admission: &Request,
        owner: &NativeOwner,
        registration: &NativeOwner,
    ) -> Result<(), Error>;
}

struct NativeObservation;
impl Observation for NativeObservation {
    type Custody = Vec<crate::custody::CachedCustody>;
    fn bind(
        &mut self,
        plan: &Plan,
        admission: &Request,
        owner: &NativeOwner,
        registration: &NativeOwner,
    ) -> Result<(crate::registration::Description, Self::Custody), Error> {
        admission
            .admit(&windows::inventory(plan.scope).map_err(native_error)?)
            .map_err(native_error)?;
        if existing_native_registration(plan, admission, owner.context())?.as_ref()
            != Some(registration)
        {
            return Err(Error::Integrity("native registration differs".into()));
        }
        let version_cache =
            recovery::current_product(plan, admission, owner, crate::owner::Role::Version)?
                .ok_or_else(|| Error::Integrity("version native owner absent".into()))?;
        let registration_cache = recovery::current_product(
            plan,
            admission,
            registration,
            crate::owner::Role::Registration,
        )?
        .ok_or_else(|| Error::Integrity("registration native owner absent".into()))?;
        let incoming =
            windows::product_definition(&plan.registration_product.path).map_err(native_error)?;
        let (cached, cached_custody) = windows::cached_product(registration)?;
        let description = bound_description(
            plan,
            incoming.registration.as_ref(),
            cached.registration.as_ref(),
        )?;
        Ok((
            description.clone(),
            vec![version_cache, registration_cache, cached_custody],
        ))
    }
    fn resources(
        &mut self,
        description: &crate::registration::Description,
        registration: &NativeOwner,
    ) -> Result<Vec<crate::custody::FileCustody>, Error> {
        description.verify(registration).map_err(native_error)
    }
    fn recheck(
        &mut self,
        plan: &Plan,
        admission: &Request,
        owner: &NativeOwner,
        registration: &NativeOwner,
    ) -> Result<(), Error> {
        if MsiInventory.locate(owner)?.as_ref() != Some(owner)
            || MsiInventory.locate(registration)?.as_ref() != Some(registration)
        {
            return Err(Error::Integrity(
                "native owners changed during verification".into(),
            ));
        }
        admission
            .admit(&windows::inventory(plan.scope).map_err(native_error)?)
            .map_err(native_error)
    }
}

fn bound_description<'a>(
    plan: &Plan,
    incoming: Option<&'a crate::registration::Description>,
    cached: Option<&crate::registration::Description>,
) -> Result<&'a crate::registration::Description, Error> {
    let description =
        incoming.ok_or_else(|| Error::Integrity("registration description unavailable".into()))?;
    if cached != Some(description)
        || description.application_id != plan.contract.installation_identity.application_id
        || description.version != plan.version
        || description.scope != plan.scope
        || description.shortcuts.len() != usize::from(plan.desktop_present)
    {
        return Err(Error::Integrity("registration description differs".into()));
    }
    Ok(description)
}

pub(super) fn verify(
    plan: &Plan,
    admission: &Request,
    owner: &NativeOwner,
    registration: &NativeOwner,
    store: &Store,
) -> Result<Option<Verified>, Error> {
    let publication = plan
        .contract
        .layout
        .installation
        .publication
        .as_ref()
        .expect("validated plan")
        .under(&plan.prefix);
    match std::fs::symlink_metadata(&publication) {
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error.into()),
        Ok(_) => {}
    }
    let _namespace =
        crate::publication::admit_existing(&plan.prefix, &publication, owner.context())
            .map_err(native_error)?;
    Ok(verify_held(
        plan,
        admission,
        owner,
        registration,
        store,
        &mut NativeObservation,
    )?
    .map(|_state| Verified { _namespace, _state }))
}

fn verify_held<O: Observation>(
    plan: &Plan,
    admission: &Request,
    owner: &NativeOwner,
    registration: &NativeOwner,
    store: &Store,
    observation: &mut O,
) -> Result<Option<Held<O::Custody>>, Error> {
    let _maintenance = store.existing_exclusive_maintenance()?;
    let snapshot = store.snapshot()?;
    if snapshot.manager_anchor() != Some(plan.version.as_str())
        && snapshot.desktop_anchor() != Some(plan.version.as_str())
    {
        return Ok(None);
    }
    let product = snapshot
        .versions()
        .find(|(release, _)| *release == plan.version)
        .map(|(_, product)| product)
        .ok_or_else(|| Error::Integrity("anchored version missing".into()))?;
    if product.phase != Phase::Ready
        || product.owner != *owner
        || product.manifest_sha256 != plan.manifest_sha256
        || snapshot.manager_anchor() != Some(plan.version.as_str())
        || snapshot.desktop_anchor() != plan.desktop_present.then_some(plan.version.as_str())
        || !snapshot.registration().is_some_and(|entry| {
            entry.phase == RegistrationPhase::Ready && entry.owner == *registration
        })
    {
        return Err(Error::Integrity("existing publication differs".into()));
    }
    let _version = store.acquire(&plan.version, &plan.manifest_sha256)?;
    let (description, _cache) = observation.bind(plan, admission, owner, registration)?;
    // Existing-prefix recovery tolerates a missing marker; the resource contract below does not.
    admit_existing_prefix(plan, store, owner)?;
    let package = plan
        .contract
        .layout
        .installation
        .versions
        .under(&plan.prefix)
        .join(&plan.version);
    // Keep every existing package member immutable while the canonical inventory
    // owner verifies bytes, including delegated documentation inventories.
    let mut package_files = Vec::new();
    for path in recovery::existing_package_files(&package)? {
        package_files.push(crate::custody::file(&path).map_err(native_error)?);
    }
    plan.contract.verify_candidate(&package, &plan.version)?;
    let mut manifest =
        crate::custody::file(&plan.contract.layout.files.package_manifest.under(&package))
            .map_err(native_error)?;
    if crate::registration::file_digest(&mut manifest.file).map_err(native_error)?
        != plan.manifest_sha256
    {
        return Err(Error::Integrity("existing version bytes differ".into()));
    }
    let _resources = observation.resources(&description, registration)?;
    observation.recheck(plan, admission, owner, registration)?;
    // Repeat mutable registry/shortcut observations with the same file custody retained.
    let _rechecked = observation.resources(&description, registration)?;
    observation.recheck(plan, admission, owner, registration)?;
    let current = store.snapshot()?;
    if current.manager_anchor() != snapshot.manager_anchor()
        || current.desktop_anchor() != snapshot.desktop_anchor()
        || current.registration() != snapshot.registration()
        || current
            .versions()
            .find(|(release, _)| *release == plan.version)
            .map(|(_, entry)| entry)
            != Some(product)
    {
        return Err(Error::Integrity(
            "publication changed during verification".into(),
        ));
    }
    let mut files = _resources;
    files.extend(package_files);
    files.extend(_rechecked);
    files.push(manifest);
    Ok(Some(Held {
        _maintenance,
        _version,
        _cache,
        _files: files,
    }))
}

#[cfg(test)]
mod observation_tests;

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn already_verified_is_a_distinct_success_response() {
        let result = report(
            Outcome::AlreadyPublishedVerified,
            "already_published_verified",
        );
        assert!(result.succeeded());
        let value = serde_json::to_value(result).unwrap();
        assert_eq!(value["outcome"], "already_published_verified");
        assert_eq!(value["schema"], 1);
        assert!(!report(Outcome::Refused, "existing_registration_not_verified").succeeded());
    }
}
