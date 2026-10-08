//! Installer-owned publication outside immutable package inventories.
//! Native product admission and process liveness remain with the installer adapter.
use super::{DiscoveryContract, version};
use crate::{component::Cancellation, error::Error, filesystem, value::Sha256Digest};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    fs::{self, File},
    path::{Path, PathBuf},
};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Identity {
    pub application_id: String,
    pub channel: String,
    pub platform: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Phase {
    Pending,
    Ready,
    Removing,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Product {
    pub product_code: String,
    pub manifest_sha256: Sha256Digest,
    pub phase: Phase,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct State {
    schema: u32,
    identity: Identity,
    versions: BTreeMap<String, Product>,
    manager_anchor: Option<String>,
    desktop_anchor: Option<String>,
}

/// Closing a lease releases kernel ownership, including after process death.
#[derive(Debug)]
#[must_use = "hold the lease throughout the protected native operation"]
pub struct Lease(File);
impl Drop for Lease {
    fn drop(&mut self) {
        let _ = self.0.unlock();
    }
}

fn lock(path: &Path, shared: bool, create: bool) -> Result<Lease, Error> {
    filesystem::refuse_links(path)?;
    let file = File::options()
        .read(true)
        .write(!shared)
        .create(create)
        .truncate(false)
        .open(path)?;
    if !file.metadata()?.is_file() {
        return Err(Error::Invalid(
            "installation lock is not a regular file".into(),
        ));
    }
    let result = if shared {
        file.try_lock_shared()
    } else {
        file.try_lock()
    };
    result.map_err(|error| match error {
        std::fs::TryLockError::WouldBlock => Error::Busy,
        std::fs::TryLockError::Error(error) => Error::Io(error),
    })?;
    Ok(Lease(file))
}

/// The owner supplies the declared state directory and exact installation identity.
pub struct Store {
    root: PathBuf,
    identity: Identity,
    maximum_versions: usize,
}

impl Store {
    pub fn new(root: PathBuf, identity: Identity, maximum_versions: usize) -> Result<Self, Error> {
        filesystem::absolute_root(&root)?;
        if maximum_versions == 0
            || maximum_versions > 4096
            || [
                &identity.application_id,
                &identity.channel,
                &identity.platform,
            ]
            .iter()
            .any(|value| value.is_empty() || value.len() > 256)
        {
            return Err(Error::Invalid(
                "invalid installation state identity or bound".into(),
            ));
        }
        Ok(Self {
            root,
            identity,
            maximum_versions,
        })
    }

    /// Creation is explicit installer work; readers never create missing state.
    pub fn initialize(&self) -> Result<(), Error> {
        filesystem::absolute_root(&self.root)?;
        fs::create_dir_all(&self.root)?;
        let _writer = lock(&self.root.join("transaction.lock"), false, true)?;
        if self.root.join("state.json").exists() {
            self.read()?;
            return Ok(());
        }
        self.write(&State {
            schema: 1,
            identity: self.identity.clone(),
            versions: BTreeMap::new(),
            manager_anchor: None,
            desktop_anchor: None,
        })
    }

    fn read(&self) -> Result<State, Error> {
        let state: State = filesystem::json_file(&self.root.join("state.json"))?;
        if state.schema != 1
            || state.identity != self.identity
            || state.versions.len() > self.maximum_versions
        {
            return Err(Error::Incompatible(
                "installation publication identity differs".into(),
            ));
        }
        for (release, product) in &state.versions {
            version(release)?;
            validate_product(product)?;
        }
        for anchor in [&state.manager_anchor, &state.desktop_anchor]
            .into_iter()
            .flatten()
        {
            if !state
                .versions
                .get(anchor)
                .is_some_and(|product| product.phase == Phase::Ready)
            {
                return Err(Error::Integrity(
                    "installation anchor is not published".into(),
                ));
            }
        }
        Ok(state)
    }

    fn write(&self, state: &State) -> Result<(), Error> {
        let pending = self.root.join("state.pending.json");
        filesystem::refuse_links(&pending)?;
        if pending.exists() {
            fs::remove_file(&pending)?;
        }
        filesystem::write_json(&pending, state)?;
        filesystem::refuse_links(&self.root.join("state.json"))?;
        fs::rename(pending, self.root.join("state.json"))?;
        Ok(())
    }

    /// Reserve a release before native file installation. Different bytes never repair it.
    pub fn prepare(
        &self,
        release: &str,
        product_code: String,
        manifest_sha256: Sha256Digest,
    ) -> Result<Lease, Error> {
        version(release)?;
        let requested = Product {
            product_code,
            manifest_sha256,
            phase: Phase::Pending,
        };
        validate_product(&requested)?;
        let _writer = lock(&self.root.join("transaction.lock"), false, false)?;
        let mut state = self.read()?;
        if let Some(previous) = state.versions.get(release) {
            if previous.product_code != requested.product_code
                || previous.manifest_sha256 != requested.manifest_sha256
            {
                return Err(Error::Integrity(
                    "same version identifies different product or bytes".into(),
                ));
            }
            if previous.phase == Phase::Removing {
                return Err(Error::Busy);
            }
            return lock(&self.root.join(format!("{release}.lock")), false, false);
        }
        if state.versions.len() >= self.maximum_versions {
            return Err(Error::LimitExceeded);
        }
        let lease = lock(&self.root.join(format!("{release}.lock")), false, true)?;
        state.versions.insert(release.to_owned(), requested);
        self.write(&state)?;
        Ok(lease)
    }

    /// Publication verifies the actual complete package through the catalogue owner.
    pub fn publish(
        &self,
        release: &str,
        package: &Path,
        contract: &DiscoveryContract,
    ) -> Result<(), Error> {
        version(release)?;
        let _writer = lock(&self.root.join("transaction.lock"), false, false)?;
        let mut state = self.read()?;
        if self.identity.application_id != contract.installation_identity.application_id
            || self.identity.channel != contract.installation_identity.channel
            || self.identity.platform != contract.layout.platform
        {
            return Err(Error::Incompatible("publication contract differs".into()));
        }
        contract.inspect_package(package, release, &Cancellation::default())?;
        let observed_manifest = contract.manifest_digest(package, &Cancellation::default())?;
        let product = state
            .versions
            .get_mut(release)
            .ok_or_else(|| Error::Invalid("unreserved release".into()))?;
        if product.phase == Phase::Removing || product.manifest_sha256 != observed_manifest {
            return Err(Error::Integrity(
                "publication differs from reserved release".into(),
            ));
        }
        product.phase = Phase::Ready;
        self.write(&state)
    }

    /// Called only after shared registration commits. Old anchors remain until then.
    pub fn anchors(&self, manager: Option<&str>, desktop: Option<&str>) -> Result<(), Error> {
        let _writer = lock(&self.root.join("transaction.lock"), false, false)?;
        let mut state = self.read()?;
        for release in [manager, desktop].into_iter().flatten() {
            if !state
                .versions
                .get(release)
                .is_some_and(|product| product.phase == Phase::Ready)
            {
                return Err(Error::Integrity(
                    "cannot anchor an unpublished release".into(),
                ));
            }
        }
        state.manager_anchor = manager.map(str::to_owned);
        state.desktop_anchor = desktop.map(str::to_owned);
        self.write(&state)
    }

    /// Hold from catalogue verification through process use. Missing state is a refusal.
    pub fn acquire(&self, release: &str, manifest: &Sha256Digest) -> Result<Lease, Error> {
        version(release)?;
        let _reader = lock(&self.root.join("transaction.lock"), true, false)?;
        let state = self.read()?;
        let product = state
            .versions
            .get(release)
            .ok_or_else(|| Error::Integrity("release is not published".into()))?;
        if product.phase != Phase::Ready || &product.manifest_sha256 != manifest {
            return Err(Error::Integrity(
                "release is uncommitted, removing or altered".into(),
            ));
        }
        lock(&self.root.join(format!("{release}.lock")), true, false)
    }

    /// Fence new launches before the adapter checks all-session process use and invokes MSI.
    /// Dropping this guard leaves Removing durable; only explicit native recovery may restore it.
    pub fn begin_removal(&self, release: &str) -> Result<Lease, Error> {
        version(release)?;
        let _writer = lock(&self.root.join("transaction.lock"), false, false)?;
        let mut state = self.read()?;
        if state.manager_anchor.as_deref() == Some(release)
            || state.desktop_anchor.as_deref() == Some(release)
        {
            return Err(Error::Busy);
        }
        let product = state
            .versions
            .get_mut(release)
            .ok_or_else(|| Error::Invalid("unknown native release".into()))?;
        let lease = lock(&self.root.join(format!("{release}.lock")), false, false)?;
        product.phase = Phase::Removing;
        self.write(&state)?;
        Ok(lease)
    }
}

fn validate_product(product: &Product) -> Result<(), Error> {
    let value = product.product_code.as_bytes();
    if value.len() != 36
        || value.iter().enumerate().any(|(index, byte)| {
            if [8, 13, 18, 23].contains(&index) {
                *byte != b'-'
            } else {
                !byte.is_ascii_hexdigit()
            }
        })
    {
        return Err(Error::Invalid("invalid native product identity".into()));
    }
    Ok(())
}
