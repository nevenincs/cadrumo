//! Recovery of this transaction's fresh rejected candidate, never ordinary removal.
use super::*;
use cadrumo_application::installation::maintenance::Preparation;

const CAUSE: &str = "version_inventory_failed";

pub(super) fn rollback(
    transaction: Transaction,
    broker: crate::owner::Broker,
    reservation: Preparation<'_>,
    plan: &Plan,
    admission: &Request,
    held: &mut [crate::registration::service::RestartGuard],
) -> MaintenanceResult {
    let settled = transaction.rollback();
    // End the old transaction's authority and settle its server before publishing
    // another owner.json for the private compensating transaction.
    drop(broker);
    if settled.is_err() {
        let mut result = report(Outcome::NativeUnsettled, "native_rollback_unsettled");
        result.cause = Some(CAUSE);
        return result.restore_services(held);
    }
    let recovered = (|| -> Result<(), Error> {
        let Some(owner) = reservation.fresh_rollback_owner()? else {
            // Existing Ready/Pending repair retains the original restoration rules.
            return Ok(());
        };
        let package = plan
            .contract
            .layout
            .installation
            .versions
            .under(&plan.prefix)
            .join(&plan.version);
        match MsiInventory.locate(&owner)? {
            None => require_absent_directory(&package)?,
            Some(observed) if observed == owner => {
                compensate(plan, admission, &reservation, &owner, &package)?;
            }
            Some(_) => return Err(Error::Integrity("rollback native owner differs".into())),
        }
        Ok(())
    })();
    if recovered.is_err() {
        let mut result = report(
            Outcome::RolledBackPublicationPending,
            "rollback_publication_fenced",
        );
        result.cause = Some(CAUSE);
        return result.restore_services(held);
    }
    rollback_publication(reservation, &plan.contract, held, CAUSE)
}

fn compensate(
    plan: &Plan,
    admission: &Request,
    reservation: &Preparation<'_>,
    owner: &NativeOwner,
    package: &Path,
) -> Result<(), Error> {
    // The outer source custodians, maintenance lease and reservation remain held.
    let _cached =
        recovery::current_product(plan, admission, owner, crate::owner::Role::Version)?
            .ok_or_else(|| Error::Integrity("rollback cached ownership disappeared".into()))?;
    let inventory = windows::inventory(plan.scope).map_err(native_error)?;
    admission
        .admit_removal(&inventory, owner)
        .map_err(native_error)?;
    let publication = plan
        .contract
        .layout
        .installation
        .publication
        .as_ref()
        .expect("read_plan checked publication");
    let _namespace = crate::publication::admit_existing(
        &plan.prefix,
        &publication.under(&plan.prefix),
        owner.context(),
    )
    .map_err(native_error)?;
    for batch in recovery::existing_package_files(package)?.chunks(256) {
        if !windows::file_users(batch).map_err(native_error)?.is_empty() {
            return Err(Error::Busy);
        }
    }
    if reservation.fresh_rollback_owner()?.as_ref() != Some(owner) {
        return Err(Error::Integrity("rollback reservation differs".into()));
    }
    let transaction = Transaction::begin(&plan.contract.installation_identity.application_id)
        .map_err(native_error)?;
    let broker = match crate::owner::Broker::bind(
        owner.context().clone(),
        transaction.ownership(),
        Identity {
            application_id: plan.contract.installation_identity.application_id.clone(),
            channel: plan.contract.installation_identity.channel.clone(),
            platform: plan.contract.layout.platform.clone(),
        },
        plan.prefix.clone(),
        publication.clone(),
    ) {
        Ok(broker) => broker,
        Err(error) => {
            // No removal was admitted, but settle the newly opened transaction.
            let _ = transaction.rollback();
            return Err(native_error(error));
        }
    };
    let active = match broker.activate(crate::owner::Claim {
        product_code: owner.product_code().into(),
        scope: plan.scope,
        prefix: plan.prefix.clone(),
        operation: crate::owner::Operation::Remove,
        role: crate::owner::Role::Version,
    }) {
        Ok(active) => active,
        Err(error) => {
            let _ = transaction.rollback();
            return Err(native_error(error));
        }
    };
    if let Err(error) = transaction.remove(owner, broker.endpoint()) {
        // Rollback may invoke the cached package: keep its authenticated claim
        // and server alive until the transaction's rollback/Drop has settled.
        let _ = transaction.rollback();
        drop(active);
        drop(broker);
        return Err(native_error(error));
    }
    // commit consumes the transaction; its failed-commit Drop also runs while
    // both the authenticated claim and its server are still retained.
    let committed = transaction.commit();
    drop(active);
    drop(broker);
    committed.map_err(native_error)?;
    if MsiInventory.locate(owner)?.is_some() {
        return Err(Error::Integrity("rollback native product remains".into()));
    }
    require_absent_directory(package)
}

fn require_absent_directory(package: &Path) -> Result<(), Error> {
    match std::fs::symlink_metadata(package) {
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(error.into()),
        Ok(_) => Err(Error::Integrity(
            "rollback candidate namespace remains".into(),
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn directory_absence_requires_actual_absence_not_an_empty_or_foreign_member() {
        let root = tempfile::tempdir().unwrap();
        let package = root.path().join("candidate");
        assert!(require_absent_directory(&package).is_ok());
        std::fs::create_dir(&package).unwrap();
        assert!(require_absent_directory(&package).is_err());
        std::fs::remove_dir(&package).unwrap();
        std::fs::write(&package, b"foreign").unwrap();
        assert!(require_absent_directory(&package).is_err());
    }
}
