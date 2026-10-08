//! Native-owned deletion under publication exclusion; never recursive file removal.
use super::*;
use cadrumo_application::installation::maintenance::{Lease, RegistrationRemoval, Removal};

enum Guard<'a> {
    Version(Removal<'a>),
    Registration(RegistrationRemoval<'a>),
}
impl Guard<'_> {
    fn owner(&self) -> &NativeOwner {
        match self {
            Self::Version(guard) => guard.owner(),
            Self::Registration(guard) => guard.owner(),
        }
    }
    fn rollback(self, contract: &DiscoveryContract) -> Result<(), Error> {
        match self {
            Self::Version(guard) => guard.rollback(contract, &MsiInventory),
            Self::Registration(guard) => guard.rollback(contract, &MsiInventory),
        }
    }
    fn complete(self) -> Result<(), Error> {
        match self {
            Self::Version(guard) => guard.complete(&MsiInventory),
            Self::Registration(guard) => guard.complete(&MsiInventory),
        }
    }
}

/// Remove one unanchored release; publication leases exclude every live consumer.
pub fn remove_version(path: &Path, release: &str) -> MaintenanceResult {
    if version(release).is_err() {
        return report(Outcome::Refused, "invalid_release");
    }
    remove(path, Some(release))
}

/// Remove only the native registration product, retaining all version payloads.
pub fn unregister(path: &Path) -> MaintenanceResult {
    remove(path, None)
}

fn remove(path: &Path, release: Option<&str>) -> MaintenanceResult {
    let plan = match read_plan(path) {
        Ok(plan) => plan,
        Err(_) => return report(Outcome::Refused, "invalid_plan"),
    };
    let context = match windows::installation_context(plan.scope) {
        Ok(context) => context,
        Err(_) => return report(Outcome::Refused, "installer_authority_unavailable"),
    };
    let admitted = (|| -> Result<_, Error> {
        let runner = runner_digest()?;
        let (request, version_file) = artifact(&plan.version_product, &plan, "version", &runner)?;
        let (registration, registration_file) =
            artifact(&plan.registration_product, &plan, "registration", &runner)?;
        if request.permitted_families != registration.permitted_families
            || request.conflicting_families != registration.conflicting_families
        {
            return Err(Error::Integrity(
                "MSI roles have inconsistent ownership".into(),
            ));
        }
        let publication = plan
            .contract
            .layout
            .installation
            .publication
            .as_ref()
            .unwrap();
        let store = Store::new(
            publication.under(&plan.prefix),
            Identity {
                application_id: plan.contract.installation_identity.application_id.clone(),
                channel: plan.contract.installation_identity.channel.clone(),
                platform: plan.contract.layout.platform.clone(),
            },
            plan.contract.layout.installation.maximum_versions,
        )?;
        Ok((request, store, version_file, registration_file))
    })();
    let (request, store, _version_file, _registration_file) = match admitted {
        Ok(value) => value,
        Err(_) => return report(Outcome::Refused, "artifact_or_owner_refused"),
    };
    if windows::standalone_gate_present(&plan.version_product.path).unwrap_or(true)
        || windows::standalone_gate_present(&plan.registration_product.path).unwrap_or(true)
    {
        return report(Outcome::Refused, "native_owner_protocol_not_admitted");
    }
    let transaction = match Transaction::begin(&plan.contract.installation_identity.application_id)
    {
        Ok(transaction) => transaction,
        Err(_) => return report(Outcome::Refused, "native_transaction_unavailable"),
    };
    let namespace = (|| -> Result<_, Error> {
        existing_native_registration(&plan, &request, &context)?;
        crate::publication::admit_existing(
            &plan.prefix,
            &plan
                .contract
                .layout
                .installation
                .publication
                .as_ref()
                .unwrap()
                .under(&plan.prefix),
            &context,
        )
        .map_err(native_error)
    })();
    let _namespace = match namespace {
        Ok(namespace) => namespace,
        Err(_) => return rollback(transaction, "native_removal_admission_refused"),
    };
    // RegistrationRemoval owns this same lease itself. Version removal also
    // retains global maintenance exclusion so registration cannot change anchors.
    let _maintenance: Option<Lease> = if release.is_some() {
        match store.exclusive_maintenance() {
            Ok(lease) => Some(lease),
            Err(_) => return rollback(transaction, "native_maintenance_busy"),
        }
    } else {
        None
    };
    let reservation = match release {
        Some(release) => store.begin_removal(release).map(Guard::Version),
        None => store.snapshot().and_then(|snapshot| {
            let registration = snapshot
                .registration()
                .ok_or_else(|| Error::Invalid("registration owner is unknown".into()))?;
            store
                .begin_registration_removal(&registration.owner)
                .map(Guard::Registration)
        }),
    };
    let guard = match reservation {
        Ok(guard) => guard,
        Err(_) => return rollback(transaction, "native_removal_busy_or_unavailable"),
    };
    let prepared = (|| -> Result<_, Error> {
        let owner = guard.owner();
        if owner.context() != &context || owner.prefix() != plan.prefix {
            return Err(Error::Integrity("removal owner differs".into()));
        }
        let (definition, custody) = windows::cached_product(owner)?;
        let snapshot = store.snapshot()?;
        let selected = release
            .or_else(|| snapshot.manager_anchor())
            .ok_or_else(|| Error::Integrity("registration has no anchor".into()))?;
        let product = snapshot
            .versions()
            .find(|(name, _)| *name == selected)
            .map(|(_, product)| product)
            .ok_or_else(|| Error::Integrity("removal publication is missing".into()))?;
        let role = if release.is_some() {
            crate::owner::Role::Version
        } else {
            crate::owner::Role::Registration
        };
        let metadata = definition
            .owner
            .as_ref()
            .ok_or_else(|| Error::Integrity("cached product has no owner protocol".into()))?;
        let index = usize::from(release.is_none());
        if definition.family != request.permitted_families[index]
            || definition.version != selected
            || definition.ownership.version != selected
            || definition.ownership.role != role.as_str()
            || definition.ownership.schema != 1
            || definition.ownership.manifest_sha256 != product.manifest_sha256
            || definition.ownership.application_id
                != plan.contract.installation_identity.application_id
            || definition.ownership.channel != plan.contract.installation_identity.channel
            || definition.ownership.platform != plan.contract.layout.platform
            || metadata.schema != 2
            || metadata.scope != plan.scope
            || metadata.product_code != definition.code
            || metadata.role != role
            || metadata.identity.application_id != definition.ownership.application_id
            || metadata.identity.channel != definition.ownership.channel
            || metadata.identity.platform != definition.ownership.platform
            || Some(&metadata.publication) != plan.contract.layout.installation.publication.as_ref()
            || definition.admission.permitted_families != request.permitted_families
            || definition.admission.conflicting_families != request.conflicting_families
        {
            return Err(Error::Integrity("cached removal identity differs".into()));
        }
        let package = plan
            .contract
            .layout
            .installation
            .versions
            .under(&plan.prefix)
            .join(selected);
        plan.contract.verify_candidate(&package, selected)?;
        let manifest_path = &plan.contract.layout.files.package_manifest;
        let manifest_file =
            crate::custody::file(&manifest_path.under(&package)).map_err(native_error)?;
        let mut bytes = Vec::new();
        manifest_file
            .file
            .take(16 * 1024 * 1024 + 1)
            .read_to_end(&mut bytes)?;
        if bytes.len() > 16 * 1024 * 1024
            || Sha256Digest::new(format!("{:x}", Sha256::digest(&bytes)))?
                != product.manifest_sha256
        {
            return Err(Error::Integrity("removal package bytes differ".into()));
        }
        let manifest: cadrumo_application::package::PackageManifest =
            serde_json::from_slice(&bytes)?;
        let files = if release.is_some() {
            manifest
                .files
                .keys()
                .map(|member| member.under(&package))
                .collect::<Vec<_>>()
        } else {
            vec![plan.contract.manager_member()?.under(&plan.prefix)]
        };
        for batch in files.chunks(256) {
            if !windows::file_users(batch).map_err(native_error)?.is_empty() {
                return Err(Error::Busy);
            }
        }
        let broker = crate::owner::Broker::bind(
            context.clone(),
            transaction.ownership(),
            metadata.identity.clone(),
            plan.prefix.clone(),
            metadata.publication.clone(),
        )
        .map_err(native_error)?;
        Ok((custody, role, broker))
    })();
    let (_cache, role, broker) = match prepared {
        Ok(prepared) => prepared,
        Err(_) => {
            return rollback_removal(transaction, guard, &plan.contract, "native_removal_refused");
        }
    };
    let removed = (|| {
        let _active = broker.activate(crate::owner::Claim {
            product_code: guard.owner().product_code().into(),
            scope: plan.scope,
            prefix: plan.prefix.clone(),
            operation: crate::owner::Operation::Remove,
            role,
        })?;
        transaction.remove(guard.owner(), broker.endpoint())
    })();
    if removed.is_err() {
        return rollback_removal(transaction, guard, &plan.contract, "native_removal_failed");
    }
    if transaction.commit().is_err() {
        return report(Outcome::NativeUnsettled, "native_commit_failed");
    }
    if guard.complete().is_err() {
        return report(
            Outcome::CommittedPublicationPending,
            "native_removal_publication_incomplete",
        );
    }
    if release.is_some() {
        report(Outcome::Removed, "version_removed")
    } else {
        report(Outcome::Unregistered, "registration_absent")
    }
}

fn rollback_removal(
    transaction: Transaction,
    guard: Guard<'_>,
    contract: &DiscoveryContract,
    code: &'static str,
) -> MaintenanceResult {
    if transaction.rollback().is_err() {
        return report(Outcome::NativeUnsettled, "native_rollback_unsettled");
    }
    if guard.rollback(contract).is_err() {
        return report(
            Outcome::RolledBackPublicationPending,
            "rollback_publication_fenced",
        );
    }
    report(Outcome::NativeRolledBack, code)
}
