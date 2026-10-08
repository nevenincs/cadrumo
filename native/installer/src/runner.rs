//! Ordered MSI transaction owner. There is no standalone-package gate bypass.
use crate::{
    admission::{Request, Scope},
    windows::{self, MsiInventory, Transaction},
};
use cadrumo_application::{
    error::Error,
    installation::{
        DiscoveryContract,
        maintenance::{Identity, NativeOwner, NativeProductInventory, RegistrationPhase, Store},
        version,
    },
    value::Sha256Digest,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    io::Read,
    path::{Path, PathBuf},
};

const PLAN_LIMIT: u64 = 64 * 1024;
const ARTIFACT_LIMIT: u64 = 16 * 1024 * 1024 * 1024;

mod recovery;
mod removal;
pub use removal::{remove_version, unregister};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Artifact {
    path: PathBuf,
    sha256: Sha256Digest,
    product_code: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Plan {
    schema: u32,
    scope: Scope,
    prefix: PathBuf,
    version: String,
    manifest_sha256: Sha256Digest,
    desktop_present: bool,
    contract: DiscoveryContract,
    version_product: Artifact,
    registration_product: Artifact,
}

#[derive(Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    Published,
    Removed,
    Unregistered,
    Refused,
    NativeRolledBack,
    NativeUnsettled,
    CommittedPublicationPending,
    RolledBackPublicationPending,
}

#[derive(Serialize)]
pub struct MaintenanceResult {
    schema: u32,
    outcome: Outcome,
    code: &'static str,
}
impl MaintenanceResult {
    pub fn succeeded(&self) -> bool {
        matches!(
            self.outcome,
            Outcome::Published | Outcome::Removed | Outcome::Unregistered
        )
    }
}

fn report(outcome: Outcome, code: &'static str) -> MaintenanceResult {
    MaintenanceResult {
        schema: 1,
        outcome,
        code,
    }
}

fn read_plan(path: &Path) -> Result<Plan, Error> {
    let source = crate::custody::file(path).map_err(native_error)?;
    let mut bytes = Vec::new();
    source.file.take(PLAN_LIMIT + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > PLAN_LIMIT {
        return Err(Error::LimitExceeded);
    }
    let plan: Plan = serde_json::from_slice(&bytes)?;
    version(&plan.version)?;
    if plan.schema != 1
        || plan.contract.layout.platform != "windows-x64"
        || plan.contract.layout.installation.publication.is_none()
        || !plan.prefix.is_absolute()
        || plan
            .prefix
            .components()
            .any(|part| matches!(part, std::path::Component::ParentDir))
        || plan
            .prefix
            .as_os_str()
            .to_string_lossy()
            .contains(['"', '\r', '\n', '\0'])
    {
        return Err(Error::Invalid("invalid Windows maintenance plan".into()));
    }
    Ok(plan)
}

fn native_error(error: crate::admission::Refusal) -> Error {
    Error::Integrity(error.message().into())
}

fn runner_digest() -> Result<Sha256Digest, Error> {
    let mut image = crate::custody::file(&std::env::current_exe()?).map_err(native_error)?;
    let mut digest = Sha256::new();
    let mut buffer = [0; 65536];
    loop {
        let size = image.file.read(&mut buffer)?;
        if size == 0 {
            break;
        }
        digest.update(&buffer[..size]);
    }
    Sha256Digest::new(format!("{:x}", digest.finalize()))
}

fn existing_native_registration(
    plan: &Plan,
    admission: &Request,
    context: &cadrumo_application::installation::maintenance::NativeContext,
) -> Result<Option<NativeOwner>, Error> {
    let inventory = windows::inventory(plan.scope).map_err(native_error)?;
    admission.admit(&inventory).map_err(native_error)?;
    let mut registration = None;
    for product in inventory {
        let Some(family) = product.family else {
            continue;
        };
        if !admission.permitted_families.contains(&family) {
            continue;
        }
        if match context {
            cadrumo_application::installation::maintenance::NativeContext::Machine => {
                product.scope != Scope::Machine || product.sid.is_some()
            }
            cadrumo_application::installation::maintenance::NativeContext::User { sid } => {
                product.scope != Scope::User || product.sid.as_ref() != Some(sid)
            }
        } {
            return Err(Error::Integrity(
                "native family belongs to another account".into(),
            ));
        }
        let owner = NativeOwner::new(product.code, context.clone(), plan.prefix.clone())?;
        if MsiInventory.locate(&owner)?.as_ref() != Some(&owner) {
            return Err(Error::Integrity(
                "native family belongs to another prefix or context".into(),
            ));
        }
        if family == admission.permitted_families[1] && registration.replace(owner).is_some() {
            return Err(Error::Integrity(
                "multiple native registration owners".into(),
            ));
        }
    }
    Ok(registration)
}

fn previous_registration(
    plan: &Plan,
    admission: &Request,
    store: &Store,
    native: Option<NativeOwner>,
) -> Result<Option<(crate::owner::Claim, crate::custody::CachedCustody)>, Error> {
    let snapshot = store.snapshot()?;
    let Some(registration) = snapshot.registration() else {
        if native.is_some() {
            return Err(Error::Integrity(
                "unpublished native registration owner".into(),
            ));
        }
        return Ok(None);
    };
    if registration.phase == RegistrationPhase::Absent && native.is_none() {
        return Ok(None);
    }
    if registration.phase != RegistrationPhase::Ready
        || native.as_ref() != Some(&registration.owner)
    {
        return Err(Error::Integrity(
            "registration publication differs from native owner".into(),
        ));
    }
    let (definition, custody) = windows::cached_product(&registration.owner)?;
    let metadata = definition
        .owner
        .as_ref()
        .ok_or_else(|| Error::Integrity("cached registration has no owner protocol".into()))?;
    let anchor = snapshot
        .manager_anchor()
        .ok_or_else(|| Error::Integrity("registration has no manager anchor".into()))?;
    let product = snapshot
        .versions()
        .find(|(release, _)| *release == anchor)
        .map(|(_, product)| product)
        .ok_or_else(|| Error::Integrity("registration anchor has no product".into()))?;
    if definition.family != admission.permitted_families[1]
        || definition.version != anchor
        || definition.ownership.version != anchor
        || definition.ownership.role != "registration"
        || metadata.role != crate::owner::Role::Registration
        || definition.ownership.manifest_sha256 != product.manifest_sha256
        || definition.ownership.application_id != plan.contract.installation_identity.application_id
        || definition.ownership.channel != plan.contract.installation_identity.channel
        || definition.ownership.platform != plan.contract.layout.platform
        || metadata.schema != 2
        || metadata.scope != plan.scope
        || metadata.product_code != definition.code
        || metadata.identity.application_id != definition.ownership.application_id
        || metadata.identity.channel != definition.ownership.channel
        || metadata.identity.platform != definition.ownership.platform
        || Some(&metadata.publication) != plan.contract.layout.installation.publication.as_ref()
        || definition.admission.permitted_families != admission.permitted_families
        || definition.admission.conflicting_families != admission.conflicting_families
    {
        return Err(Error::Integrity(
            "cached registration ownership mismatch".into(),
        ));
    }
    Ok(Some((
        crate::owner::Claim {
            product_code: definition.code,
            scope: plan.scope,
            prefix: plan.prefix.clone(),
            operation: crate::owner::Operation::Remove,
            role: crate::owner::Role::Registration,
        },
        custody,
    )))
}

fn admit_existing_prefix(plan: &Plan, store: &Store, owner: &NativeOwner) -> Result<(), Error> {
    if !plan.prefix.try_exists()?
        || std::fs::read_dir(&plan.prefix)?
            .next()
            .transpose()?
            .is_none()
    {
        return Ok(());
    }
    let marker = plan.contract.layout.installation.marker.under(&plan.prefix);
    if marker.try_exists()? {
        let source = crate::custody::file(&marker).map_err(native_error)?;
        let mut bytes = Vec::new();
        source.file.take(16385).read_to_end(&mut bytes)?;
        if bytes.len() > 16384 {
            return Err(Error::LimitExceeded);
        }
        let observed: serde_json::Value = serde_json::from_slice(&bytes)?;
        let expected = serde_json::json!({
            "schema": plan.contract.layout.installation.schema,
            "application_id": plan.contract.installation_identity.application_id,
            "channel": plan.contract.installation_identity.channel,
            "platform": plan.contract.layout.platform,
            "abi": plan.contract.layout.abi,
            "publication": plan.contract.layout.installation.publication,
            "launch_policy": "native",
        });
        if observed != expected {
            return Err(Error::Integrity(
                "existing prefix is not the same native installation".into(),
            ));
        }
    }
    // Missing stable marker can be an interrupted first install. Recovery still
    // requires a prior durable exact product reservation, never an arbitrary folder.
    let snapshot = store.snapshot()?;
    if !snapshot
        .versions()
        .any(|(release, product)| release == plan.version && product.owner == *owner)
        && !marker.try_exists()?
    {
        return Err(Error::Integrity(
            "existing prefix has no native maintenance owner".into(),
        ));
    }
    Ok(())
}

fn artifact(
    artifact: &Artifact,
    plan: &Plan,
    role: &str,
    runner: &Sha256Digest,
) -> Result<(Request, crate::custody::FileCustody), Error> {
    // Retain the source handle through native installation; another writer cannot
    // replace or modify the admitted MSI while Windows Installer consumes it.
    let mut custody = crate::custody::file(&artifact.path).map_err(native_error)?;
    let file = &mut custody.file;
    if file.metadata()?.len() > ARTIFACT_LIMIT {
        return Err(Error::LimitExceeded);
    }
    let mut digest = Sha256::new();
    let mut buffer = [0; 65536];
    loop {
        let size = file.read(&mut buffer)?;
        if size == 0 {
            break;
        }
        digest.update(&buffer[..size]);
    }
    if Sha256Digest::new(format!("{:x}", digest.finalize()))? != artifact.sha256 {
        return Err(Error::Integrity("native MSI artifact hash changed".into()));
    }
    let definition = windows::product_definition(&artifact.path).map_err(native_error)?;
    let family_index = match role {
        "version" => 0,
        "registration" => 1,
        _ => return Err(Error::Integrity("unknown native MSI role".into())),
    };
    let owner = definition
        .owner
        .as_ref()
        .ok_or_else(|| Error::Integrity("MSI has no authenticated native owner".into()))?;
    if owner.schema != 2
        || owner.scope != plan.scope
        || owner.product_code != definition.code
        || owner.role.as_str() != role
        || &owner.runner_sha256 != runner
        || Some(&owner.publication) != plan.contract.layout.installation.publication.as_ref()
        || owner.identity.application_id != plan.contract.installation_identity.application_id
        || owner.identity.channel != plan.contract.installation_identity.channel
        || owner.identity.platform != plan.contract.layout.platform
    {
        return Err(Error::Integrity(
            "MSI belongs to another native maintenance owner".into(),
        ));
    }
    if definition.code
        != crate::admission::canonical_guid(&artifact.product_code).map_err(native_error)?
        || definition.version != plan.version
        || definition.admission.scope != plan.scope
        || definition.ownership
            != (windows::PackageOwnership {
                schema: 1,
                application_id: plan.contract.installation_identity.application_id.clone(),
                channel: plan.contract.installation_identity.channel.clone(),
                platform: plan.contract.layout.platform.clone(),
                version: plan.version.clone(),
                role: role.into(),
                manifest_sha256: plan.manifest_sha256.clone(),
            })
        || definition.family != definition.admission.permitted_families[family_index]
    {
        return Err(Error::Integrity(
            "native MSI identity differs from maintenance plan".into(),
        ));
    }
    Ok((definition.admission, custody))
}

/// A successful native commit is irreversible; any later publication failure is
/// reported as committed-but-pending and never represented as a native rollback.
pub fn install(path: &Path) -> MaintenanceResult {
    let plan = match read_plan(path) {
        Ok(plan) => plan,
        Err(_) => return report(Outcome::Refused, "invalid_plan"),
    };
    let context = match windows::installation_context(plan.scope) {
        Ok(context) => context,
        Err(_) => return report(Outcome::Refused, "installer_authority_unavailable"),
    };
    let prepared = (|| -> Result<_, Error> {
        let runner = runner_digest()?;
        let (admission, version_file) = artifact(&plan.version_product, &plan, "version", &runner)?;
        let (registration, registration_file) =
            artifact(&plan.registration_product, &plan, "registration", &runner)?;
        if admission.permitted_families != registration.permitted_families
            || admission.conflicting_families != registration.conflicting_families
            || plan.version_product.product_code == plan.registration_product.product_code
        {
            return Err(Error::Integrity(
                "MSI roles have inconsistent ownership".into(),
            ));
        }
        let owner = NativeOwner::new(
            plan.version_product.product_code.clone(),
            context.clone(),
            plan.prefix.clone(),
        )?;
        let registration_owner = NativeOwner::new(
            plan.registration_product.product_code.clone(),
            context,
            plan.prefix.clone(),
        )?;
        let publication = plan
            .contract
            .layout
            .installation
            .publication
            .as_ref()
            .expect("read_plan checked publication");
        let store = Store::new(
            publication.under(&plan.prefix),
            Identity {
                application_id: plan.contract.installation_identity.application_id.clone(),
                channel: plan.contract.installation_identity.channel.clone(),
                platform: plan.contract.layout.platform.clone(),
            },
            plan.contract.layout.installation.maximum_versions,
        )?;
        Ok((
            admission,
            owner,
            registration_owner,
            store,
            version_file,
            registration_file,
        ))
    })();
    let (admission, owner, registration_owner, store, _version_file, _registration_file) =
        match prepared {
            Ok(value) => value,
            Err(_) => return report(Outcome::Refused, "artifact_or_owner_refused"),
        };
    // Native lifecycle protections must pass disposable-host acceptance before
    // the unconditional MSI Launch gate can open. Refuse before creating state
    // or starting a native transaction; implemented source is not that evidence.
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
    let prepared = (|| -> Result<_, Error> {
        let native_registration = existing_native_registration(&plan, &admission, owner.context())?;
        admit_existing_prefix(&plan, &store, &owner)?;
        let publication = plan
            .contract
            .layout
            .installation
            .publication
            .as_ref()
            .expect("validated publication")
            .under(&plan.prefix);
        let namespace = crate::publication::prepare(&plan.prefix, &publication, owner.context())
            .map_err(native_error)?;
        store.initialize()?;
        let maintenance = store.exclusive_maintenance()?;
        let snapshot = store.snapshot()?;
        let pending = snapshot
            .versions()
            .find(|(release, _)| *release == plan.version)
            .map(|(_, product)| product);
        let transition = recovery::registration_transition(
            snapshot.registration(),
            native_registration.as_ref(),
            &registration_owner,
            pending,
            &owner,
            &plan.manifest_sha256,
        )?;
        let previous = if transition == recovery::RegistrationTransition::Consistent {
            previous_registration(&plan, &admission, &store, native_registration)?
        } else {
            if let Some(published) = snapshot.registration()
                && published.owner != registration_owner
                && MsiInventory.locate(&published.owner)?.is_some()
            {
                return Err(Error::Integrity(
                    "interrupted registration still has another native owner".into(),
                ));
            }
            None
        };
        let version_cache =
            recovery::current_product(&plan, &admission, &owner, crate::owner::Role::Version)?;
        let registration_cache = recovery::current_product(
            &plan,
            &admission,
            &registration_owner,
            crate::owner::Role::Registration,
        )?;
        let version = store.prepare_transaction(
            &plan.version,
            owner.clone(),
            plan.manifest_sha256.clone(),
        )?;
        Ok((
            maintenance,
            version,
            namespace,
            previous,
            version_cache,
            registration_cache,
            transition,
        ))
    })();
    let (
        _maintenance,
        reservation,
        _namespace,
        previous,
        _version_cache,
        _registration_cache,
        transition,
    ) = match prepared {
        Ok(guards) => guards,
        Err(_) => return rollback(transaction, "native_preparation_refused"),
    };
    let broker = match crate::owner::Broker::bind(
        owner.context().clone(),
        transaction.ownership(),
        Identity {
            application_id: plan.contract.installation_identity.application_id.clone(),
            channel: plan.contract.installation_identity.channel.clone(),
            platform: plan.contract.layout.platform.clone(),
        },
        plan.prefix.clone(),
        plan.contract
            .layout
            .installation
            .publication
            .clone()
            .expect("read_plan checked publication"),
    ) {
        Ok(broker) => broker,
        Err(_) => {
            return rollback_prepared(
                transaction,
                reservation,
                &plan.contract,
                "native_owner_unavailable",
            );
        }
    };
    let install = |artifact: &Artifact, role| {
        let mut claims = vec![crate::owner::Claim {
            product_code: artifact.product_code.to_ascii_uppercase(),
            scope: plan.scope,
            prefix: plan.prefix.clone(),
            operation: crate::owner::Operation::Install,
            role,
        }];
        if role == crate::owner::Role::Registration
            && let Some((claim, _custody)) = &previous
        {
            claims.push(claim.clone());
        }
        let _active = broker.activate_claims(claims)?;
        let product_owner = if role == crate::owner::Role::Version {
            &owner
        } else {
            &registration_owner
        };
        transaction.install(&artifact.path, product_owner, broker.endpoint())
    };
    let package = plan
        .contract
        .layout
        .installation
        .versions
        .under(&plan.prefix)
        .join(&plan.version);
    let idle = (|| -> Result<(), Error> {
        for files in recovery::existing_package_files(&package)?.chunks(256) {
            if !windows::file_users(files).map_err(native_error)?.is_empty() {
                return Err(Error::Busy);
            }
        }
        Ok(())
    })();
    if idle.is_err() {
        return rollback_prepared(
            transaction,
            reservation,
            &plan.contract,
            "version_in_use_or_unknown",
        );
    }
    if install(&plan.version_product, crate::owner::Role::Version).is_err() {
        return rollback_prepared(
            transaction,
            reservation,
            &plan.contract,
            "version_installation_failed",
        );
    }
    // Verify while Pending. Publication is deliberately deferred until commit.
    if plan
        .contract
        .verify_candidate(&package, &plan.version)
        .is_err()
    {
        return rollback_prepared(
            transaction,
            reservation,
            &plan.contract,
            "version_inventory_failed",
        );
    }
    let stable_manager = match plan.contract.manager_member() {
        Ok(member) => member.under(&plan.prefix),
        Err(_) => {
            return rollback_prepared(
                transaction,
                reservation,
                &plan.contract,
                "registration_entrypoint_invalid",
            );
        }
    };
    let stable_available = (|| -> Result<bool, Error> {
        if !stable_manager.try_exists()? {
            return Ok(true);
        }
        Ok(windows::file_users(std::slice::from_ref(&stable_manager))
            .map_err(native_error)?
            .is_empty())
    })();
    if !matches!(stable_available, Ok(true)) {
        return rollback_prepared(
            transaction,
            reservation,
            &plan.contract,
            "shared_registration_in_use_or_unknown",
        );
    }
    if install(&plan.registration_product, crate::owner::Role::Registration).is_err() {
        return rollback_prepared(
            transaction,
            reservation,
            &plan.contract,
            "registration_installation_failed",
        );
    }
    if transaction.commit().is_err() {
        return report(Outcome::NativeUnsettled, "native_commit_failed");
    }
    let published = (|| -> Result<(), Error> {
        // Native file creation must preserve the admitted inherited ACLs. A
        // committed product with unsafe new permissions remains unpublished.
        let publication = plan
            .contract
            .layout
            .installation
            .publication
            .as_ref()
            .expect("validated publication")
            .under(&plan.prefix);
        let _postinstall_namespace =
            crate::publication::prepare(&plan.prefix, &publication, owner.context())
                .map_err(native_error)?;
        if MsiInventory.locate(&owner)?.as_ref() != Some(&owner)
            || MsiInventory.locate(&registration_owner)?.as_ref() != Some(&registration_owner)
        {
            return Err(Error::Integrity(
                "committed native ownership differs".into(),
            ));
        }
        store.publish_registered(
            &plan.version,
            &package,
            &plan.contract,
            plan.desktop_present,
            registration_owner,
        )
    })();
    if published.is_err() {
        report(
            Outcome::CommittedPublicationPending,
            "native_publication_incomplete",
        )
    } else {
        report(
            Outcome::Published,
            if transition == recovery::RegistrationTransition::ReconcilePending {
                "installation_recovered"
            } else {
                "installation_published"
            },
        )
    }
}

fn rollback(transaction: Transaction, code: &'static str) -> MaintenanceResult {
    if transaction.rollback().is_ok() {
        report(Outcome::NativeRolledBack, code)
    } else {
        report(Outcome::NativeUnsettled, "native_rollback_unsettled")
    }
}

fn rollback_prepared(
    transaction: Transaction,
    reservation: cadrumo_application::installation::maintenance::Preparation<'_>,
    contract: &DiscoveryContract,
    code: &'static str,
) -> MaintenanceResult {
    if transaction.rollback().is_err() {
        return report(Outcome::NativeUnsettled, "native_rollback_unsettled");
    }
    if matches!(
        reservation.rollback(contract, &MsiInventory),
        Err(_) | Ok(cadrumo_application::installation::maintenance::RollbackPublication::PendingRetained)
    ) {
        return report(
            Outcome::RolledBackPublicationPending,
            "rollback_publication_fenced",
        );
    }
    report(Outcome::NativeRolledBack, code)
}
