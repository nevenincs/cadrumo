//! Completed native registration removal, distinct from update/rollback gaps.
use cadrumo_application::installation::{
    DiscoveryContract, Selection,
    maintenance::{Identity, NativeOwner, NativeRegistration, RegistrationPhase, Store},
};
use std::{
    io,
    path::PathBuf,
    time::{Duration, Instant},
};

pub struct InstallationWatch {
    entrypoint: PathBuf,
    application_id: String,
    owner: Option<NativeOwner>,
    store: Option<Store>,
    next: Instant,
}
impl InstallationWatch {
    pub fn new(selected: &Selection) -> io::Result<Self> {
        let contract: DiscoveryContract =
            serde_json::from_str(crate::contract::INSTALLATION_CONTRACT)
                .map_err(io::Error::other)?;
        let prefix = selected
            .entrypoint
            .parent()
            .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidData))?;
        let store = contract
            .layout
            .installation
            .publication
            .as_ref()
            .map(|path| {
                Store::new(
                    path.under(prefix),
                    Identity {
                        application_id: contract.installation_identity.application_id.clone(),
                        channel: contract.installation_identity.channel,
                        platform: contract.layout.platform,
                    },
                    contract.layout.installation.maximum_versions,
                )
            })
            .transpose()
            .map_err(io::Error::other)?;
        Ok(Self {
            entrypoint: selected.entrypoint.clone(),
            application_id: contract.installation_identity.application_id,
            owner: selected.registration.clone(),
            store,
            next: Instant::now(),
        })
    }
    pub fn removed(&mut self) -> bool {
        if Instant::now() < self.next {
            return false;
        }
        self.next = Instant::now() + Duration::from_secs(2);
        self.observe().unwrap_or(false)
    }
    fn observe(&mut self) -> io::Result<bool> {
        let Some(store) = &self.store else {
            return Ok(false);
        };
        let snapshot = store.snapshot().map_err(io::Error::other)?;
        let hints = cadrumo_platform::installation::manager_entry_points(&self.application_id)?;
        let registered = [&hints.this_user, &hints.all_users]
            .into_iter()
            .flatten()
            .any(|path| crate::ipc::windows::same_image(path, &self.entrypoint));
        let file_absent = match std::fs::symlink_metadata(&self.entrypoint) {
            Err(error) if error.kind() == io::ErrorKind::NotFound => true,
            Ok(metadata) if metadata.is_file() && !metadata.file_type().is_symlink() => false,
            _ => return Ok(false),
        };
        if snapshot
            .registration()
            .is_some_and(|record| record.phase == RegistrationPhase::Absent)
            && (snapshot.manager_anchor().is_some() || snapshot.desktop_anchor().is_some())
        {
            return Ok(false);
        }
        Ok(completed(
            &mut self.owner,
            snapshot.registration(),
            !registered,
            file_absent,
        ))
    }
}
fn completed(
    expected: &mut Option<NativeOwner>,
    observed: Option<&NativeRegistration>,
    registration_absent: bool,
    entry_absent: bool,
) -> bool {
    let (Some(expected), Some(observed)) = (expected.as_mut(), observed) else {
        return false;
    };
    if observed.phase == RegistrationPhase::Ready
        && !registration_absent
        && !entry_absent
        && observed.owner.context() == expected.context()
        && observed.owner.prefix() == expected.prefix()
    {
        // Follow committed ProductCode changes only within an intact admitted scope.
        *expected = observed.owner.clone();
        return false;
    }
    // The authenticated publication store is authoritative for this prefix and
    // scope. Polling may skip a committed ProductCode update before its removal.
    observed.phase == RegistrationPhase::Absent
        && observed.owner.context() == expected.context()
        && observed.owner.prefix() == expected.prefix()
        && registration_absent
        && entry_absent
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::installation::maintenance::NativeContext;
    #[test]
    fn transient_anchor_or_registration_gaps_never_trigger_uninstall() {
        let owner = NativeOwner::new(
            "11111111-1111-4111-8111-111111111111".into(),
            NativeContext::Machine,
            std::env::temp_dir(),
        )
        .unwrap();
        let mut expected = Some(owner.clone());
        assert!(!completed(&mut expected, None, true, true));
        for phase in [RegistrationPhase::Ready, RegistrationPhase::Removing] {
            assert!(!completed(
                &mut expected,
                Some(&NativeRegistration {
                    owner: owner.clone(),
                    phase
                }),
                true,
                true
            ));
        }
        let removed = NativeRegistration {
            owner: owner.clone(),
            phase: RegistrationPhase::Absent,
        };
        assert!(!completed(&mut expected, Some(&removed), true, false));
        assert!(!completed(&mut expected, Some(&removed), false, true));
        assert!(completed(&mut expected, Some(&removed), true, true));
        let changed = NativeOwner::new(
            "22222222-2222-4222-8222-222222222222".into(),
            NativeContext::Machine,
            std::env::temp_dir(),
        )
        .unwrap();
        assert!(completed(
            &mut expected,
            Some(&NativeRegistration {
                owner: changed.clone(),
                phase: RegistrationPhase::Absent
            }),
            true,
            true
        ));
        let foreign = NativeOwner::new(
            "33333333-3333-4333-8333-333333333333".into(),
            NativeContext::Machine,
            std::env::temp_dir().join("different-prefix"),
        )
        .unwrap();
        assert!(!completed(
            &mut expected,
            Some(&NativeRegistration {
                owner: foreign,
                phase: RegistrationPhase::Absent
            }),
            true,
            true
        ));
        assert!(!completed(
            &mut expected,
            Some(&NativeRegistration {
                owner: changed.clone(),
                phase: RegistrationPhase::Ready
            }),
            false,
            false
        ));
        assert!(completed(&mut expected, Some(&removed), true, true));
        assert!(completed(
            &mut expected,
            Some(&NativeRegistration {
                owner: changed,
                phase: RegistrationPhase::Absent
            }),
            true,
            true
        ));
    }
}
