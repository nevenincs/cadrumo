//! Ordered MSI transaction owner. There is no standalone-package gate bypass.
use crate::{
    admission::{Request, Scope},
    windows::{self, MsiInventory, Transaction},
};
use cadrumo_application::{
    error::Error,
    installation::{
        DiscoveryContract,
        maintenance::{Identity, NativeOwner, NativeProductInventory, Store},
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
    Refused,
    NativeRolledBack,
    NativeUnsettled,
    CommittedPublicationPending,
}

#[derive(Serialize)]
pub struct MaintenanceResult {
    schema: u32,
    outcome: Outcome,
    code: &'static str,
}
impl MaintenanceResult {
    pub fn succeeded(&self) -> bool {
        matches!(self.outcome, Outcome::Published)
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

fn artifact(
    artifact: &Artifact,
    plan: &Plan,
    role: &str,
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
        || !definition
            .admission
            .permitted_families
            .contains(&definition.family)
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
        let (admission, version_file) = artifact(&plan.version_product, &plan, "version")?;
        let (registration, registration_file) =
            artifact(&plan.registration_product, &plan, "registration")?;
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
    // Until authenticated owner callbacks and protected publication-directory
    // creation are integrated, real artifacts contain an unconditional Launch
    // gate. Refuse before creating state or starting a native transaction.
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
        admission
            .admit(&windows::inventory(plan.scope).map_err(native_error)?)
            .map_err(native_error)?;
        store.initialize()?;
        let maintenance = store.exclusive_maintenance()?;
        let version = store.prepare(&plan.version, owner.clone(), plan.manifest_sha256.clone())?;
        Ok((maintenance, version))
    })();
    let (_maintenance, _version) = match prepared {
        Ok(guards) => guards,
        Err(_) => return rollback(transaction, "native_preparation_refused"),
    };
    let broker = match crate::owner::Broker::bind(owner.context().clone()) {
        Ok(broker) => broker,
        Err(_) => return rollback(transaction, "native_owner_unavailable"),
    };
    let install = |artifact: &Artifact| {
        let _active = broker.activate(crate::owner::Claim {
            product_code: artifact.product_code.to_ascii_uppercase(),
            scope: plan.scope,
            prefix: plan.prefix.clone(),
        })?;
        transaction.install(&artifact.path, &plan.prefix, broker.endpoint())
    };
    if install(&plan.version_product).is_err() {
        return rollback(transaction, "version_installation_failed");
    }
    let package = plan
        .contract
        .layout
        .installation
        .versions
        .under(&plan.prefix)
        .join(&plan.version);
    // Verify while Pending. Publication is deliberately deferred until commit.
    if plan
        .contract
        .verify_candidate(&package, &plan.version)
        .is_err()
    {
        return rollback(transaction, "version_inventory_failed");
    }
    if install(&plan.registration_product).is_err() {
        return rollback(transaction, "registration_installation_failed");
    }
    if transaction.commit().is_err() {
        return report(Outcome::NativeUnsettled, "native_commit_failed");
    }
    let published = (|| -> Result<(), Error> {
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
        report(Outcome::Published, "installation_published")
    }
}

fn rollback(transaction: Transaction, code: &'static str) -> MaintenanceResult {
    if transaction.rollback().is_ok() {
        report(Outcome::NativeRolledBack, code)
    } else {
        report(Outcome::NativeUnsettled, "native_rollback_unsettled")
    }
}
