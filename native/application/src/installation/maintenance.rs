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
    pub owner: NativeOwner,
    pub manifest_sha256: Sha256Digest,
    pub phase: Phase,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RegistrationPhase {
    Ready,
    Removing,
    Absent,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NativeRegistration {
    pub owner: NativeOwner,
    pub phase: RegistrationPhase,
}

#[must_use = "retain registration exclusion until native settlement"]
pub struct RegistrationRemoval<'a> {
    store: &'a Store,
    owner: NativeOwner,
    _lease: Lease,
}

impl RegistrationRemoval<'_> {
    pub fn owner(&self) -> &NativeOwner {
        &self.owner
    }

    /// The native transaction must have committed before this positive absence
    /// evidence is recorded. Dropping an unsettled guard preserves Removing.
    pub fn complete(self, inventory: &impl NativeProductInventory) -> Result<(), Error> {
        self.store
            .complete_registration_removal(&self.owner, inventory)
    }
}

/// Native product context is separate from the account running an installer action.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "scope", rename_all = "snake_case", deny_unknown_fields)]
pub enum NativeContext {
    Machine,
    User { sid: String },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NativeOwner {
    product_code: String,
    context: NativeContext,
    prefix: PathBuf,
}

impl NativeOwner {
    pub fn new(
        product_code: String,
        context: NativeContext,
        prefix: PathBuf,
    ) -> Result<Self, Error> {
        let owner = Self {
            product_code: product_code.to_ascii_uppercase(),
            context,
            prefix,
        };
        owner.validate()?;
        Ok(owner)
    }
    pub fn product_code(&self) -> &str {
        &self.product_code
    }
    pub fn context(&self) -> &NativeContext {
        &self.context
    }
    pub fn prefix(&self) -> &Path {
        &self.prefix
    }

    fn validate(&self) -> Result<(), Error> {
        validate_product_code(&self.product_code)?;
        filesystem::absolute_root(&self.prefix)?;
        if let NativeContext::User { sid } = &self.context {
            let fields: Vec<_> = sid.split('-').collect();
            if matches!(
                sid.as_str(),
                "S-1-1-0" | "S-1-5-18" | "S-1-5-19" | "S-1-5-20"
            ) || !(4..=18).contains(&fields.len())
                || fields[0] != "S"
                || fields[1] != "1"
                || fields[2]
                    .parse::<u64>()
                    .ok()
                    .is_none_or(|value| value >= (1_u64 << 48))
                || fields[2..].iter().any(|field| {
                    field.is_empty()
                        || !field.bytes().all(|c| c.is_ascii_digit())
                        || (field.len() > 1 && field.starts_with('0'))
                })
                || fields[3..]
                    .iter()
                    .any(|field| field.parse::<u32>().is_err())
            {
                return Err(Error::Invalid("invalid native product account SID".into()));
            }
        }
        Ok(())
    }
}

/// Effect port implemented by the native installer adapter. Implementations must
/// query the exact product and account context; unknown/inaccessible evidence is
/// an error. None means a completed native query proved that product absent.
pub trait NativeProductInventory {
    fn locate(&self, owner: &NativeOwner) -> Result<Option<NativeOwner>, Error>;
}

/// A removal operation owns exclusion and the exact persisted product snapshot.
/// Dropping it never makes the version eligible or removes files.
#[must_use = "complete or roll back native removal, or retain the durable removing fence"]
pub struct Removal<'a> {
    store: &'a Store,
    release: String,
    product: Product,
    _lease: Lease,
}

impl Removal<'_> {
    pub fn owner(&self) -> &NativeOwner {
        &self.product.owner
    }

    /// Restore discoverability only after native rollback and complete inventory
    /// verification at this product's canonical installed path.
    pub fn rollback(
        self,
        contract: &DiscoveryContract,
        inventory: &impl NativeProductInventory,
    ) -> Result<(), Error> {
        let _writer = lock(&self.store.root.join("transaction.lock"), false, false)?;
        let mut state = self.store.read()?;
        self.current(&state)?;
        if inventory.locate(&self.product.owner)?.as_ref() != Some(&self.product.owner) {
            return Err(Error::Integrity(
                "native rollback did not restore exact product ownership".into(),
            ));
        }
        let package = self
            .store
            .package(&self.release, &self.product.owner, contract)?;
        contract.inspect_package(&package, &self.release, &Cancellation::default())?;
        if contract.manifest_digest(&package, &Cancellation::default())?
            != self.product.manifest_sha256
        {
            return Err(Error::Integrity(
                "native rollback restored different bytes".into(),
            ));
        }
        state
            .versions
            .get_mut(&self.release)
            .expect("current checked product")
            .phase = Phase::Ready;
        self.store.write(&state)
    }

    /// Forget publication only after the native adapter proves this exact product
    /// absent. Windows Installer owns file removal; this method deletes no files.
    pub fn complete(self, inventory: &impl NativeProductInventory) -> Result<(), Error> {
        let _writer = lock(&self.store.root.join("transaction.lock"), false, false)?;
        let mut state = self.store.read()?;
        self.current(&state)?;
        if inventory.locate(&self.product.owner)?.is_some() {
            return Err(Error::Busy);
        }
        state.versions.remove(&self.release);
        self.store.write(&state)
    }

    fn current(&self, state: &State) -> Result<(), Error> {
        if state.versions.get(&self.release) != Some(&self.product) {
            return Err(Error::Integrity(
                "native maintenance product changed during removal".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct State {
    schema: u32,
    identity: Identity,
    versions: BTreeMap<String, Product>,
    manager_anchor: Option<String>,
    desktop_anchor: Option<String>,
    #[serde(default)]
    registration: Option<NativeRegistration>,
}

/// A validated observation, not authority to start or remove a product. Consumers
/// re-acquire a version lease before acting on any version in this snapshot.
#[derive(Clone, Debug)]
pub struct Snapshot {
    versions: BTreeMap<String, Product>,
    manager_anchor: Option<String>,
    desktop_anchor: Option<String>,
    registration: Option<NativeRegistration>,
}

impl Snapshot {
    pub fn registration(&self) -> Option<&NativeRegistration> {
        self.registration.as_ref()
    }
    pub fn versions(&self) -> impl Iterator<Item = (&str, &Product)> {
        self.versions
            .iter()
            .map(|(release, product)| (release.as_str(), product))
    }
    pub fn manager_anchor(&self) -> Option<&str> {
        self.manager_anchor.as_deref()
    }
    pub fn desktop_anchor(&self) -> Option<&str> {
        self.desktop_anchor.as_deref()
    }
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
            schema: 2,
            identity: self.identity.clone(),
            versions: BTreeMap::new(),
            manager_anchor: None,
            desktop_anchor: None,
            registration: None,
        })
    }

    pub fn snapshot(&self) -> Result<Snapshot, Error> {
        let _reader = lock(&self.root.join("transaction.lock"), true, false)?;
        let state = self.read()?;
        Ok(Snapshot {
            versions: state.versions,
            manager_anchor: state.manager_anchor,
            desktop_anchor: state.desktop_anchor,
            registration: state.registration,
        })
    }

    /// Serialize native maintenance for this prefix while ordinary readers keep
    /// using already-published versions. This is distinct from the brief state lock.
    pub fn exclusive_maintenance(&self) -> Result<Lease, Error> {
        lock(&self.root.join("maintenance.lock"), false, true)
    }

    fn read(&self) -> Result<State, Error> {
        let state: State = filesystem::json_file(&self.root.join("state.json"))?;
        if state.schema != 2
            || state.identity != self.identity
            || state.versions.len() > self.maximum_versions
        {
            return Err(Error::Incompatible(
                "installation publication identity differs".into(),
            ));
        }
        let first_owner = state.versions.values().next().map(|product| &product.owner);
        if let Some(registration) = &state.registration {
            self.validate_owner(&registration.owner)?;
            if first_owner.is_some_and(|owner| {
                owner.context != registration.owner.context
                    || owner.prefix != registration.owner.prefix
            }) || (registration.phase == RegistrationPhase::Absent
                && (state.manager_anchor.is_some() || state.desktop_anchor.is_some()))
                || (registration.phase == RegistrationPhase::Ready
                    && state.manager_anchor.is_none())
            {
                return Err(Error::Integrity(
                    "registration publication is inconsistent".into(),
                ));
            }
        }
        for (release, product) in &state.versions {
            version(release)?;
            self.validate_owner(&product.owner)?;
            if first_owner.is_some_and(|owner| {
                owner.context != product.owner.context || owner.prefix != product.owner.prefix
            }) {
                return Err(Error::Integrity(
                    "installation has conflicting native owners".into(),
                ));
            }
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
        owner: NativeOwner,
        manifest_sha256: Sha256Digest,
    ) -> Result<Lease, Error> {
        version(release)?;
        let requested = Product {
            owner,
            manifest_sha256,
            phase: Phase::Pending,
        };
        self.validate_owner(&requested.owner)?;
        let _writer = lock(&self.root.join("transaction.lock"), false, false)?;
        let mut state = self.read()?;
        if let Some(previous) = state.versions.get(release) {
            if previous.owner != requested.owner
                || previous.manifest_sha256 != requested.manifest_sha256
            {
                return Err(Error::Integrity(
                    "same version identifies different product or bytes".into(),
                ));
            }
            if previous.phase == Phase::Removing {
                return Err(Error::Busy);
            }
            // Repair cannot temporarily invalidate an anchor. Advancing shared
            // registration is a separate native operation, never an implicit fix.
            if state.manager_anchor.as_deref() == Some(release)
                || state.desktop_anchor.as_deref() == Some(release)
            {
                return Err(Error::Busy);
            }
            let lease = lock(&self.root.join(format!("{release}.lock")), false, false)?;
            state
                .versions
                .get_mut(release)
                .expect("existing product")
                .phase = Phase::Pending;
            self.write(&state)?;
            return Ok(lease);
        }
        if state.registration.as_ref().is_some_and(|registration| {
            registration.owner.context != requested.owner.context
                || registration.owner.prefix != requested.owner.prefix
        }) || state.versions.values().any(|product| {
            product.owner.context != requested.owner.context
                || product.owner.prefix != requested.owner.prefix
        }) {
            return Err(Error::Integrity(
                "new release has conflicting native ownership".into(),
            ));
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
        self.mark_ready(&mut state, release, package, contract)?;
        self.write(&state)
    }

    /// The native transaction owner calls this only after irrevocable commit and
    /// exact product revalidation. Readers see readiness and both anchors together.
    pub fn publish_registered(
        &self,
        release: &str,
        package: &Path,
        contract: &DiscoveryContract,
        desktop_present: bool,
        registration_owner: NativeOwner,
    ) -> Result<(), Error> {
        version(release)?;
        let _writer = lock(&self.root.join("transaction.lock"), false, false)?;
        let mut state = self.read()?;
        self.validate_owner(&registration_owner)?;
        let product = state
            .versions
            .get(release)
            .ok_or_else(|| Error::Invalid("unreserved release".into()))?;
        if product.owner.context != registration_owner.context
            || product.owner.prefix != registration_owner.prefix
            || product.owner.product_code == registration_owner.product_code
        {
            return Err(Error::Integrity(
                "registration owner differs from version ownership".into(),
            ));
        }
        self.mark_ready(&mut state, release, package, contract)?;
        state.manager_anchor = Some(release.to_owned());
        state.desktop_anchor = desktop_present.then(|| release.to_owned());
        state.registration = Some(NativeRegistration {
            owner: registration_owner,
            phase: RegistrationPhase::Ready,
        });
        self.write(&state)
    }

    /// Fence registration before invoking native uninstall. Anchors remain until
    /// committed absence is proved; interruption therefore cannot signal uninstall.
    pub fn begin_registration_removal(
        &self,
        owner: &NativeOwner,
    ) -> Result<RegistrationRemoval<'_>, Error> {
        let lease = self.exclusive_maintenance()?;
        let _writer = lock(&self.root.join("transaction.lock"), false, false)?;
        let mut state = self.read()?;
        let registration = state
            .registration
            .as_mut()
            .ok_or_else(|| Error::Invalid("registration owner is unknown".into()))?;
        if &registration.owner != owner || registration.phase == RegistrationPhase::Absent {
            return Err(Error::Integrity(
                "registration removal owner differs".into(),
            ));
        }
        registration.phase = RegistrationPhase::Removing;
        self.write(&state)?;
        Ok(RegistrationRemoval {
            store: self,
            owner: owner.clone(),
            _lease: lease,
        })
    }

    /// Call only after native commit, retaining the maintenance lease. A positive
    /// exact-context absence query and the durable Removing record are mandatory.
    fn complete_registration_removal(
        &self,
        owner: &NativeOwner,
        inventory: &impl NativeProductInventory,
    ) -> Result<(), Error> {
        let _writer = lock(&self.root.join("transaction.lock"), false, false)?;
        let mut state = self.read()?;
        let registration = state
            .registration
            .as_mut()
            .ok_or_else(|| Error::Invalid("registration owner is unknown".into()))?;
        if &registration.owner != owner || registration.phase != RegistrationPhase::Removing {
            return Err(Error::Integrity(
                "registration removal is not pending for this owner".into(),
            ));
        }
        if inventory.locate(owner)?.is_some() {
            return Err(Error::Busy);
        }
        registration.phase = RegistrationPhase::Absent;
        state.manager_anchor = None;
        state.desktop_anchor = None;
        self.write(&state)
    }

    fn mark_ready(
        &self,
        state: &mut State,
        release: &str,
        package: &Path,
        contract: &DiscoveryContract,
    ) -> Result<(), Error> {
        let product = state
            .versions
            .get_mut(release)
            .ok_or_else(|| Error::Invalid("unreserved release".into()))?;
        if self.package(release, &product.owner, contract)? != package {
            return Err(Error::Integrity(
                "publication package differs from native product prefix".into(),
            ));
        }
        contract.inspect_package(package, release, &Cancellation::default())?;
        let observed_manifest = contract.manifest_digest(package, &Cancellation::default())?;
        if product.phase == Phase::Removing || product.manifest_sha256 != observed_manifest {
            return Err(Error::Integrity(
                "publication differs from reserved release".into(),
            ));
        }
        product.phase = Phase::Ready;
        Ok(())
    }

    /// Called only after shared registration commits. Old anchors remain until then.
    pub fn anchors(&self, manager: Option<&str>, desktop: Option<&str>) -> Result<(), Error> {
        let _writer = lock(&self.root.join("transaction.lock"), false, false)?;
        let mut state = self.read()?;
        if state
            .registration
            .as_ref()
            .is_some_and(|registration| match registration.phase {
                RegistrationPhase::Ready => manager.is_none(),
                RegistrationPhase::Absent => manager.is_some() || desktop.is_some(),
                RegistrationPhase::Removing => true,
            })
        {
            return Err(Error::Busy);
        }
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
    pub fn begin_removal(&self, release: &str) -> Result<Removal<'_>, Error> {
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
        if product.phase == Phase::Pending {
            return Err(Error::Integrity(
                "uncommitted installation needs native install recovery".into(),
            ));
        }
        let lease = lock(&self.root.join(format!("{release}.lock")), false, false)?;
        product.phase = Phase::Removing;
        let product = product.clone();
        self.write(&state)?;
        Ok(Removal {
            store: self,
            release: release.to_owned(),
            product,
            _lease: lease,
        })
    }

    fn validate_owner(&self, owner: &NativeOwner) -> Result<(), Error> {
        owner.validate()?;
        if self.root == owner.prefix || !self.root.starts_with(&owner.prefix) {
            return Err(Error::Integrity(
                "native product prefix does not contain publication state".into(),
            ));
        }
        Ok(())
    }

    fn package(
        &self,
        release: &str,
        owner: &NativeOwner,
        contract: &DiscoveryContract,
    ) -> Result<PathBuf, Error> {
        if self.identity.application_id != contract.installation_identity.application_id
            || self.identity.channel != contract.installation_identity.channel
            || self.identity.platform != contract.layout.platform
        {
            return Err(Error::Incompatible("publication contract differs".into()));
        }
        let publication = contract
            .layout
            .installation
            .publication
            .as_ref()
            .ok_or_else(|| Error::Invalid("native publication is not declared".into()))?;
        if publication.under(&owner.prefix) != self.root {
            return Err(Error::Integrity(
                "native publication path differs from contract".into(),
            ));
        }
        let package = contract
            .layout
            .installation
            .versions
            .under(&owner.prefix)
            .join(release);
        filesystem::absolute_root(&package)?;
        Ok(package)
    }
}

fn validate_product_code(code: &str) -> Result<(), Error> {
    let value = code.as_bytes();
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
