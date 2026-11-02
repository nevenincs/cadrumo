//! Windows Installer adapter.
#![allow(unsafe_code)]
pub mod destinations;
pub mod restart_manager;
use crate::admission::{
    MAX_DATA_BYTES, MAX_PRODUCTS, Product, Refusal, Request, Scope, canonical_guid,
};
use cadrumo_application::{
    error::Error,
    installation::maintenance::{
        NativeContext, NativeFeature, NativeOwner, NativeProductInventory,
    },
};
use std::{
    ffi::c_void,
    os::windows::{
        fs::MetadataExt,
        io::{FromRawHandle, OwnedHandle},
    },
    path::{Component, Path, Prefix},
};
use std::{path::PathBuf, ptr};

const ERROR_SUCCESS: u32 = 0;
const ERROR_NO_MORE_ITEMS: u32 = 259;
const ERROR_INSTALL_FAILURE: u32 = 1603;
const ERROR_UNKNOWN_PRODUCT: u32 = 1605;
const MACHINE: u32 = 4;
const ALL_CONTEXTS: u32 = 7;

#[link(name = "msi")]
unsafe extern "system" {
    fn MsiCloseHandle(handle: u32) -> u32;
    fn MsiGetActiveDatabase(install: u32) -> u32;
    fn MsiGetPropertyW(install: u32, name: *const u16, value: *mut u16, size: *mut u32) -> u32;
    fn MsiSetPropertyW(install: u32, name: *const u16, value: *const u16) -> u32;
    fn MsiOpenDatabaseW(path: *const u16, mode: *const u16, database: *mut u32) -> u32;
    #[cfg(test)]
    fn MsiDatabaseCommit(database: u32) -> u32;
    fn MsiDatabaseOpenViewW(database: u32, query: *const u16, view: *mut u32) -> u32;
    fn MsiViewExecute(view: u32, record: u32) -> u32;
    fn MsiViewFetch(view: u32, record: *mut u32) -> u32;
    fn MsiCreateRecord(fields: u32) -> u32;
    fn MsiRecordSetStringW(record: u32, field: u32, value: *const u16) -> u32;
    fn MsiRecordGetStringW(record: u32, field: u32, value: *mut u16, size: *mut u32) -> u32;
    fn MsiProcessMessage(install: u32, kind: u32, record: u32) -> i32;
    fn MsiEnumProductsExW(
        product: *const u16,
        sid: *const u16,
        contexts: u32,
        index: u32,
        code: *mut u16,
        context: *mut u32,
        owner: *mut u16,
        owner_size: *mut u32,
    ) -> u32;
    fn MsiGetProductInfoExW(
        product: *const u16,
        sid: *const u16,
        context: u32,
        property: *const u16,
        value: *mut u16,
        size: *mut u32,
    ) -> u32;
    fn MsiBeginTransactionW(
        name: *const u16,
        attributes: u32,
        transaction: *mut u32,
        owner_event: *mut *mut c_void,
    ) -> u32;
    fn MsiEndTransaction(state: u32) -> u32;
    fn MsiInstallProductW(package: *const u16, properties: *const u16) -> u32;
    fn MsiConfigureProductExW(
        product: *const u16,
        level: i32,
        state: i32,
        properties: *const u16,
    ) -> u32;
    fn MsiSetInternalUI(level: u32, window: *mut *mut c_void) -> u32;
    fn MsiQueryFeatureStateExW(
        product: *const u16,
        sid: *const u16,
        context: u32,
        feature: *const u16,
        state: *mut i32,
    ) -> u32;
    fn MsiGetFeatureStateW(
        install: u32,
        feature: *const u16,
        installed: *mut i32,
        action: *mut i32,
    ) -> u32;
}

#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetCurrentProcess() -> *mut c_void;
    fn CloseHandle(handle: *mut c_void) -> i32;
    fn LocalFree(memory: *mut c_void) -> *mut c_void;
}
#[link(name = "advapi32")]
unsafe extern "system" {
    fn OpenProcessToken(process: *mut c_void, access: u32, token: *mut *mut c_void) -> i32;
    fn GetTokenInformation(
        token: *mut c_void,
        class: u32,
        information: *mut c_void,
        size: u32,
        returned: *mut u32,
    ) -> i32;
    fn ConvertSidToStringSidW(sid: *mut c_void, value: *mut *mut u16) -> i32;
}
struct KernelHandle(*mut c_void);
impl Drop for KernelHandle {
    fn drop(&mut self) {
        // SAFETY: This wrapper owns a non-null handle returned by the native API.
        unsafe {
            CloseHandle(self.0);
        }
    }
}

static INSTALLER_UI: std::sync::Mutex<()> = std::sync::Mutex::new(());
struct InstallerUi {
    previous: u32,
    _exclusive: std::sync::MutexGuard<'static, ()>,
}
impl InstallerUi {
    fn quiet() -> Result<Self, Refusal> {
        let exclusive = INSTALLER_UI
            .try_lock()
            .map_err(|_| Refusal::NativeFailure)?;
        // SAFETY: process-global UI changes are serialized for this transaction's
        // entire lifetime. INSTALLUILEVEL_NONE prevents inherited dialogs, including
        // noninteractive service hosts; it never suppresses a native error result.
        let previous = unsafe { MsiSetInternalUI(2, ptr::null_mut()) };
        if previous == 0 {
            return Err(Refusal::NativeFailure);
        }
        Ok(Self {
            previous,
            _exclusive: exclusive,
        })
    }
}
impl Drop for InstallerUi {
    fn drop(&mut self) {
        // SAFETY: still holding the exclusive process UI guard, restore native state.
        unsafe {
            MsiSetInternalUI(self.previous, ptr::null_mut());
        }
    }
}

/// The owner, not a deferred custom action, holds this native transaction. A
/// successful commit return is the only operation that disables rollback on Drop.
pub struct Transaction {
    _transaction: Handle,
    ownership: crate::ownership::Ownership,
    active: bool,
    _ui: InstallerUi,
}
impl Transaction {
    pub fn begin(name: &str) -> Result<Self, Refusal> {
        let ui = InstallerUi::quiet()?;
        let name = wide(name)?;
        let mut transaction = 0;
        let mut event = ptr::null_mut();
        // SAFETY: All outputs and the terminated name remain live for this call.
        result(unsafe { MsiBeginTransactionW(name.as_ptr(), 0, &mut transaction, &mut event) })?;
        if event.is_null() || transaction == 0 {
            // SAFETY: The preceding successful call opened our transaction.
            unsafe {
                MsiEndTransaction(0);
            }
            if transaction != 0 {
                drop(Handle(transaction));
            }
            if !event.is_null() {
                drop(KernelHandle(event));
            }
            return Err(Refusal::NativeFailure);
        }
        Ok(Self {
            _transaction: Handle(transaction),
            // SAFETY: MsiBeginTransaction returned this newly owned event handle.
            ownership: crate::ownership::Ownership::new(unsafe {
                OwnedHandle::from_raw_handle(event)
            }),
            active: true,
            _ui: ui,
        })
    }
    pub fn ownership(&self) -> crate::ownership::Ownership {
        self.ownership.clone()
    }
    pub fn install(
        &self,
        package: &Path,
        owner: &NativeOwner,
        endpoint: &str,
    ) -> Result<(), Refusal> {
        self.ownership.current()?;
        local_regular_file(package)?;
        let package = wide(package.to_str().ok_or(Refusal::InvalidRequest)?)?;
        let observed = MsiInventory
            .locate(owner)
            .map_err(|_| Refusal::IncompleteInventory)?;
        let properties = wide(&installation_properties(
            owner,
            endpoint,
            observed.as_ref(),
        )?)?;
        // SAFETY: This process owns the transaction; terminated strings remain live.
        // Reboot-required and other nonzero results remain failures, never implicit success.
        let installed =
            result(unsafe { MsiInstallProductW(package.as_ptr(), properties.as_ptr()) });
        self.ownership.current()?;
        installed
    }
    pub fn commit(mut self) -> Result<(), Refusal> {
        self.ownership.current()?;
        // SAFETY: This object owns the active native transaction in this process.
        result(unsafe { MsiEndTransaction(1) })?;
        self.active = false;
        Ok(())
    }
    pub fn remove(&self, owner: &NativeOwner, endpoint: &str) -> Result<(), Refusal> {
        self.ownership.current()?;
        let product = wide(&format!("{{{}}}", owner.product_code()))?;
        let prefix = owner.prefix().to_str().ok_or(Refusal::InvalidRequest)?;
        if prefix.contains(['"', '\r', '\n', '\0']) || endpoint.contains(['"', '\r', '\n', '\0']) {
            return Err(Refusal::InvalidRequest);
        }
        let (remove, selection) = if let Some(feature) = owner.feature() {
            let other = match feature {
                NativeFeature::Version => NativeFeature::Registration,
                NativeFeature::Registration => NativeFeature::Version,
            };
            let other_present = MsiInventory
                .locate(&owner.clone().with_feature(other))
                .map_err(|_| Refusal::IncompleteInventory)?
                .is_some();
            (
                if other_present { feature.id() } else { "ALL" },
                format!(" CADRUMO_MSI_FEATURE={}", feature.id()),
            )
        } else {
            ("ALL", String::new())
        };
        let properties = wide(&format!(
            "REMOVE={remove} INSTALL_ROOT=\"{prefix}\" CADRUMO_MSI_OWNER=\"{endpoint}\" REBOOT=ReallySuppress MSIRESTARTMANAGERCONTROL=Disable{selection}"
        ))?;
        // SAFETY: exact native product was admitted by the caller; this transaction
        // owns settlement. INSTALLSTATE_ABSENT removes only Windows Installer-owned
        // resources. Nonzero reboot, in-use and failure statuses are never success.
        let removed = result(unsafe {
            MsiConfigureProductExW(
                product.as_ptr(),
                0,
                if remove == "ALL" { 2 } else { 5 },
                properties.as_ptr(),
            )
        });
        self.ownership.current()?;
        removed
    }
    pub fn rollback(mut self) -> Result<(), Refusal> {
        self.ownership.current()?;
        // SAFETY: This object owns the active native transaction in this process.
        result(unsafe { MsiEndTransaction(0) })?;
        self.active = false;
        Ok(())
    }
}

fn installation_properties(
    owner: &NativeOwner,
    endpoint: &str,
    observed: Option<&NativeOwner>,
) -> Result<String, Refusal> {
    let prefix = owner.prefix().to_str().ok_or(Refusal::InvalidRequest)?;
    if prefix.contains(['"', '\r', '\n', '\0'])
        || endpoint.contains(['"', '\r', '\n', '\0'])
        || observed.is_some_and(|native| native != owner)
    {
        return Err(Refusal::InvalidRequest);
    }
    // REINSTALL on an absent product performs no installation. Only exact native
    // presence enables forced file/registry/shortcut repair. No recache ('v') is
    // requested: the independently verified native cache remains authoritative.
    let repair = if observed.is_some() {
        format!(
            " REINSTALL={} REINSTALLMODE=amus",
            owner.feature().map_or("ALL", NativeFeature::id)
        )
    } else {
        String::new()
    };
    let feature = owner.feature().map_or_else(String::new, |feature| {
        format!(
            " INSTALLLEVEL=0 ADDLOCAL={0} CADRUMO_MSI_FEATURE={0}",
            feature.id()
        )
    });
    let scope = if owner.feature().is_some() {
        match owner.context() {
            NativeContext::Machine => " ALLUSERS=1 MSIINSTALLPERUSER=\"\"",
            NativeContext::User { .. } => " ALLUSERS=\"\" MSIINSTALLPERUSER=1",
        }
    } else {
        ""
    };
    Ok(format!(
        "INSTALL_ROOT=\"{prefix}\" CADRUMO_MSI_OWNER=\"{endpoint}\" REBOOT=ReallySuppress MSIRESTARTMANAGERCONTROL=Disable{scope}{feature}{repair}"
    ))
}
impl Drop for Transaction {
    fn drop(&mut self) {
        if self.active && self.ownership.current().is_ok() {
            // SAFETY: Only our still-active transaction is rolled back. Failure
            // leaves shared publication fenced; Drop never manufactures success.
            unsafe {
                MsiEndTransaction(0);
            }
        }
    }
}

pub fn local_regular_file(path: &Path) -> Result<(), Refusal> {
    if !path.is_absolute()
        || !matches!(path.components().next(), Some(Component::Prefix(prefix))
        if matches!(prefix.kind(), Prefix::Disk(_) | Prefix::VerbatimDisk(_)))
        || path
            .components()
            .any(|part| matches!(part, Component::ParentDir))
    {
        return Err(Refusal::InvalidRequest);
    }
    for ancestor in path.ancestors() {
        let metadata =
            std::fs::symlink_metadata(ancestor).map_err(|_| Refusal::IncompleteInventory)?;
        if metadata.file_attributes() & 0x400 != 0 {
            return Err(Refusal::InvalidRequest);
        }
    }
    if !path.is_file() {
        return Err(Refusal::InvalidRequest);
    }
    Ok(())
}

pub fn installation_context(scope: Scope) -> Result<NativeContext, Refusal> {
    let mut token = ptr::null_mut();
    // SAFETY: Pseudo process handle is borrowed; output is writable. TOKEN_QUERY only.
    if unsafe { OpenProcessToken(GetCurrentProcess(), 8, &mut token) } == 0 {
        return Err(Refusal::NativeFailure);
    }
    let token = KernelHandle(token);
    if scope == Scope::Machine {
        let mut elevation = 0_u32;
        let mut returned = 0;
        // SAFETY: TOKEN_ELEVATION is exactly one DWORD and the output size matches.
        if unsafe {
            GetTokenInformation(
                token.0,
                20,
                ptr::from_mut(&mut elevation).cast(),
                4,
                &mut returned,
            )
        } == 0
            || returned != 4
            || elevation == 0
        {
            return Err(Refusal::NativeFailure);
        }
        return Ok(NativeContext::Machine);
    }
    let mut returned = 0;
    // SAFETY: The initial size-only query deliberately supplies a null output.
    unsafe {
        GetTokenInformation(token.0, 1, ptr::null_mut(), 0, &mut returned);
    }
    if returned == 0 || returned > 65536 {
        return Err(Refusal::NativeFailure);
    }
    let mut storage = vec![0_usize; (returned as usize).div_ceil(size_of::<usize>())];
    // SAFETY: Aligned storage has at least returned bytes; TokenUser writes SID_AND_ATTRIBUTES.
    if unsafe {
        GetTokenInformation(
            token.0,
            1,
            storage.as_mut_ptr().cast(),
            returned,
            &mut returned,
        )
    } == 0
    {
        return Err(Refusal::NativeFailure);
    }
    // SAFETY: A successful TokenUser query starts with the SID pointer, pointer-aligned.
    let sid = unsafe { *storage.as_ptr().cast::<*mut c_void>() };
    let mut value = ptr::null_mut();
    // SAFETY: SID belongs to the live token-information buffer; API allocates terminated text.
    if unsafe { ConvertSidToStringSidW(sid, &mut value) } == 0 {
        return Err(Refusal::NativeFailure);
    }
    let mut size = 0;
    // SAFETY: The converted SID is terminated and documented textual SIDs fit 184 characters.
    while size < 184 && unsafe { *value.add(size) } != 0 {
        size += 1;
    }
    // SAFETY: The preceding scan bounds initialized UTF-16 text from this native allocation.
    let text = String::from_utf16(unsafe { std::slice::from_raw_parts(value, size) });
    // SAFETY: ConvertSidToStringSid allocated this memory for LocalFree.
    unsafe {
        LocalFree(value.cast());
    }
    if size == 184 {
        return Err(Refusal::InvalidRequest);
    }
    Ok(NativeContext::User {
        sid: text.map_err(|_| Refusal::InvalidRequest)?,
    })
}

pub struct ProductDefinition {
    pub code: String,
    pub family: String,
    pub version: String,
    pub admission: Request,
    pub ownership: PackageOwnership,
    pub owner: Option<OwnerMetadata>,
    pub registration: Option<crate::registration::Description>,
}

#[derive(Clone, Debug, PartialEq, Eq, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PackageOwnership {
    pub schema: u32,
    pub application_id: String,
    pub channel: String,
    pub platform: String,
    pub version: String,
    pub role: String,
    pub manifest_sha256: cadrumo_application::value::Sha256Digest,
}
fn database(path: &Path) -> Result<Handle, Refusal> {
    local_regular_file(path)?;
    let path = wide(path.to_str().ok_or(Refusal::InvalidRequest)?)?;
    let mut handle = 0;
    // SAFETY: Null persistence mode opens the local artifact read-only.
    result(unsafe { MsiOpenDatabaseW(path.as_ptr(), ptr::null(), &mut handle) })?;
    Handle::new(handle)
}

pub fn product_definition(path: &Path) -> Result<ProductDefinition, Refusal> {
    product_definition_for_scope(path, Scope::User)
}
pub fn product_definition_for_scope(
    path: &Path,
    scope: Scope,
) -> Result<ProductDefinition, Refusal> {
    let database = database(path)?;
    let required = |name| property(&database, name)?.ok_or(Refusal::InvalidRequest);
    let suffix = if scope == Scope::Machine {
        "Machine"
    } else {
        "User"
    };
    let admission = property(&database, &format!("CadrumoAdmission{suffix}"))?
        .or(property(&database, "CadrumoAdmission")?)
        .ok_or(Refusal::InvalidRequest)?;
    let registration = property(&database, &format!("CadrumoRegistration{suffix}"))?
        .or(property(&database, "CadrumoRegistration")?);
    Ok(ProductDefinition {
        code: canonical_guid(&required("ProductCode")?)?,
        family: canonical_guid(&required("UpgradeCode")?)?,
        version: required("ProductVersion")?,
        admission: Request::parse(&admission)?,
        ownership: serde_json::from_str(&required("CadrumoPackage")?)
            .map_err(|_| Refusal::InvalidRequest)?,
        owner: property(&database, "CadrumoOwner")?
            .map(|value| serde_json::from_str(&value).map_err(|_| Refusal::InvalidRequest))
            .transpose()?,
        registration: registration
            .map(|value| crate::registration::Description::parse(&value))
            .transpose()?,
    })
}
pub fn standalone_gate_present(path: &Path) -> Result<bool, Refusal> {
    let database = database(path)?;
    let query = wide("SELECT `Condition` FROM `LaunchCondition`")?;
    let mut view = 0;
    // SAFETY: Owned read-only database, terminated static SQL and writable output.
    result(unsafe { MsiDatabaseOpenViewW(database.0, query.as_ptr(), &mut view) })?;
    let view = Handle::new(view)?;
    // SAFETY: No parameters occur in the query.
    result(unsafe { MsiViewExecute(view.0, 0) })?;
    for _ in 0..256 {
        let mut row = 0;
        // SAFETY: The view is alive and output points to writable handle storage.
        let status = unsafe { MsiViewFetch(view.0, &mut row) };
        if status == ERROR_NO_MORE_ITEMS {
            return Ok(false);
        }
        result(status)?;
        let row = Handle::new(row)?;
        // SAFETY: The selected field exists and string supplies bounded writable storage.
        let value = string(|buffer, size| unsafe { MsiRecordGetStringW(row.0, 1, buffer, size) })?;
        if value.trim() == "0" {
            return Ok(true);
        }
    }
    Err(Refusal::IncompleteInventory)
}

struct Handle(u32);
impl Handle {
    fn new(value: u32) -> Result<Self, Refusal> {
        if value == 0 {
            Err(Refusal::NativeFailure)
        } else {
            Ok(Self(value))
        }
    }
}
impl Drop for Handle {
    fn drop(&mut self) {
        // SAFETY: Each wrapper owns one MSI handle returned by a successful API call.
        unsafe {
            MsiCloseHandle(self.0);
        }
    }
}
fn wide(value: &str) -> Result<Vec<u16>, Refusal> {
    if value.contains('\0') || value.len() > MAX_DATA_BYTES {
        return Err(Refusal::InvalidRequest);
    }
    Ok(value.encode_utf16().chain(Some(0)).collect())
}
fn result(code: u32) -> Result<(), Refusal> {
    if code == ERROR_SUCCESS {
        Ok(())
    } else {
        Err(Refusal::NativeFailure)
    }
}
fn string(call: impl FnOnce(*mut u16, *mut u32) -> u32) -> Result<String, Refusal> {
    let mut buffer = vec![0; MAX_DATA_BYTES + 1];
    let mut size = buffer.len() as u32;
    result(call(buffer.as_mut_ptr(), &mut size))?;
    if size as usize > MAX_DATA_BYTES {
        return Err(Refusal::InvalidRequest);
    }
    let value =
        String::from_utf16(&buffer[..size as usize]).map_err(|_| Refusal::InvalidRequest)?;
    if value.len() > MAX_DATA_BYTES || value.contains('\0') {
        return Err(Refusal::InvalidRequest);
    }
    Ok(value)
}

fn property(database: &Handle, name: &str) -> Result<Option<String>, Refusal> {
    let query = wide("SELECT `Value` FROM `Property` WHERE `Property` = ?")?;
    let mut view = 0;
    // SAFETY: Database is owned, query is terminated, output points to a live u32.
    result(unsafe { MsiDatabaseOpenViewW(database.0, query.as_ptr(), &mut view) })?;
    let view = Handle::new(view)?;
    // SAFETY: Allocates a one-field record, subsequently owned by Handle.
    let record = Handle::new(unsafe { MsiCreateRecord(1) })?;
    let name = wide(name)?;
    // SAFETY: Record and view remain alive; the one bound field is a terminated string.
    result(unsafe { MsiRecordSetStringW(record.0, 1, name.as_ptr()) })?;
    // SAFETY: The query has exactly one parameter and the record has that field.
    result(unsafe { MsiViewExecute(view.0, record.0) })?;
    let mut row = 0;
    // SAFETY: The executed view is alive and the output pointer is writable.
    let status = unsafe { MsiViewFetch(view.0, &mut row) };
    if status == ERROR_NO_MORE_ITEMS {
        return Ok(None);
    }
    result(status)?;
    let row = Handle::new(row)?;
    // SAFETY: The selected field exists; string supplies a bounded writable buffer.
    let value = string(|buffer, size| unsafe { MsiRecordGetStringW(row.0, 1, buffer, size) })?;
    // Property is a primary key, so multiple values indicate an invalid database.
    let mut extra = 0;
    // SAFETY: Same owned view, writable output; any unexpected handle is closed.
    let status = unsafe { MsiViewFetch(view.0, &mut extra) };
    if extra != 0 {
        drop(Handle::new(extra)?);
    }
    if status != ERROR_NO_MORE_ITEMS {
        return Err(Refusal::AmbiguousOwnership);
    }
    Ok(Some(value))
}

fn session_property(install: u32, name: &str) -> Result<String, Refusal> {
    let name = wide(name)?;
    // SAFETY: MSI owns the borrowed install handle. Name and output buffers are live.
    string(|buffer, size| unsafe { MsiGetPropertyW(install, name.as_ptr(), buffer, size) })
}

fn cached_family(code: &[u16], context: u32, sid: &[u16]) -> Result<Option<String>, Refusal> {
    let sid = if context == MACHINE {
        ptr::null()
    } else {
        sid.as_ptr()
    };
    let local_package = wide("LocalPackage")?;
    // SAFETY: Values come from native enumeration; all input/output buffers are live.
    let cache = string(|buffer, size| unsafe {
        MsiGetProductInfoExW(
            code.as_ptr(),
            sid,
            context,
            local_package.as_ptr(),
            buffer,
            size,
        )
    })
    .map_err(|_| Refusal::IncompleteInventory)?;
    if cache.is_empty() {
        return Err(Refusal::IncompleteInventory);
    }
    let _cache_custody = crate::custody::file(Path::new(&cache))?;
    let cache = wide(&cache)?;
    let mut database = 0;
    // SAFETY: Null mode is MSIDBOPEN_READONLY; this never runs cached package actions.
    result(unsafe { MsiOpenDatabaseW(cache.as_ptr(), ptr::null(), &mut database) })
        .map_err(|_| Refusal::IncompleteInventory)?;
    let database = Handle::new(database)?;
    let cached_code = property(&database, "ProductCode")?.ok_or(Refusal::IncompleteInventory)?;
    let native_code = String::from_utf16(&code[..38]).map_err(|_| Refusal::AmbiguousOwnership)?;
    if canonical_guid(&cached_code)? != canonical_guid(&native_code)? {
        return Err(Refusal::AmbiguousOwnership);
    }
    property(&database, "UpgradeCode")
}

/// Exact-context native ownership observation for shared removal recovery.
pub struct MsiInventory;

/// Bind cached metadata to an exact installed product, scope, account and prefix.
/// Retain the cache and its namespace while admitting nested native removal.
pub fn cached_product(
    owner: &NativeOwner,
) -> Result<(ProductDefinition, crate::custody::CachedCustody), Error> {
    if MsiInventory.locate(owner)?.as_ref() != Some(owner) {
        return Err(Error::Integrity(
            "cached product has no exact native owner".into(),
        ));
    }
    let code = wide(&format!("{{{}}}", owner.product_code())).map_err(application_error)?;
    let sid = match owner.context() {
        NativeContext::Machine => None,
        NativeContext::User { sid } => Some(wide(sid).map_err(application_error)?),
    };
    let contexts: &[u32] = if sid.is_none() { &[MACHINE] } else { &[1, 2] };
    let mut cache = None;
    for context in contexts {
        if native_product_property(&code, sid.as_deref(), *context, "State")?.is_some() {
            if cache.is_some() {
                return Err(Error::Integrity("ambiguous cached product".into()));
            }
            cache = native_product_property(&code, sid.as_deref(), *context, "LocalPackage")?;
        }
    }
    let path = PathBuf::from(
        cache.ok_or_else(|| Error::Integrity("missing native cached product".into()))?,
    );
    let custody =
        crate::custody::native_cache(&path, owner.context()).map_err(application_error)?;
    let definition = product_definition_for_scope(
        &path,
        match owner.context() {
            NativeContext::Machine => Scope::Machine,
            NativeContext::User { .. } => Scope::User,
        },
    )
    .map_err(application_error)?;
    if definition.code != owner.product_code() {
        return Err(Error::Integrity("cached product identity mismatch".into()));
    }
    Ok((definition, custody))
}

impl NativeProductInventory for MsiInventory {
    fn locate(&self, owner: &NativeOwner) -> Result<Option<NativeOwner>, Error> {
        let code = wide(&format!("{{{}}}", owner.product_code())).map_err(application_error)?;
        let sid = match owner.context() {
            NativeContext::Machine => None,
            NativeContext::User { sid } => Some(wide(sid).map_err(application_error)?),
        };
        let contexts: &[u32] = if sid.is_none() { &[MACHINE] } else { &[1, 2] };
        let mut found = None;
        let mut product_seen = false;
        for context in contexts {
            let state = native_product_property(&code, sid.as_deref(), *context, "State")?;
            let Some(state) = state else {
                continue;
            };
            // INSTALLSTATE_DEFAULT (5) is installed. Advertised, broken or other
            // transitional state cannot prove either committed presence or absence.
            if state != "5" || product_seen {
                return Err(Error::Integrity(
                    "native product has ambiguous installation state".into(),
                ));
            }
            product_seen = true;
            let location =
                native_product_property(&code, sid.as_deref(), *context, "InstallLocation")?
                    .filter(|value| !value.is_empty())
                    .ok_or_else(|| {
                        Error::Integrity("native product install location is unavailable".into())
                    })?;
            if owner.feature().is_some() && Path::new(&location) != owner.prefix() {
                return Err(Error::Integrity(
                    "native feature belongs to another prefix".into(),
                ));
            }
            if let Some(feature) = owner.feature() {
                let feature = wide(feature.id()).map_err(application_error)?;
                let mut installed = 0;
                // SAFETY: exact native product/account/context and bounded, owned
                // feature name; observation never opens an installation session.
                result(unsafe {
                    MsiQueryFeatureStateExW(
                        code.as_ptr(),
                        sid.as_ref().map_or(ptr::null(), |sid| sid.as_ptr()),
                        *context,
                        feature.as_ptr(),
                        &mut installed,
                    )
                })
                .map_err(application_error)?;
                if installed == 2 {
                    continue;
                }
                if installed != 3 {
                    return Err(Error::Integrity("native feature state is not local".into()));
                }
            }
            let mut observed = NativeOwner::new(
                owner.product_code().into(),
                owner.context().clone(),
                PathBuf::from(location),
            )?;
            if let Some(feature) = owner.feature() {
                observed = observed.with_feature(feature);
            }
            found = Some(observed);
        }
        Ok(found)
    }
}

fn application_error(refusal: Refusal) -> Error {
    Error::Integrity(refusal.message().into())
}

fn native_product_property(
    code: &[u16],
    sid: Option<&[u16]>,
    context: u32,
    property: &str,
) -> Result<Option<String>, Error> {
    let name = wide(property).map_err(application_error)?;
    let mut status = ERROR_SUCCESS;
    let value = string(|buffer, size| {
        // SAFETY: Product, context and exact account are owned validated strings;
        // the native query is read-only and output storage is bounded by string().
        status = unsafe {
            MsiGetProductInfoExW(
                code.as_ptr(),
                sid.map_or(ptr::null(), |sid| sid.as_ptr()),
                context,
                name.as_ptr(),
                buffer,
                size,
            )
        };
        status
    });
    if status == ERROR_UNKNOWN_PRODUCT {
        return Ok(None);
    }
    value.map(Some).map_err(application_error)
}

/// Machine admission enumerates Everyone, including managed/unmanaged user products.
/// User admission enumerates the invoking account and machine products. It never
/// substitutes the elevated installer's HKCU for all account contexts.
pub fn inventory(scope: Scope) -> Result<Vec<Product>, Refusal> {
    let everyone = wide("S-1-1-0")?;
    let sid = if scope == Scope::Machine {
        everyone.as_ptr()
    } else {
        ptr::null()
    };
    let mut products = Vec::new();
    for index in 0..=MAX_PRODUCTS {
        let mut code = [0; 39];
        let mut owner = [0; 185];
        let mut owner_size = owner.len() as u32;
        let mut context = 0;
        // SAFETY: The native API gets its documented fixed GUID and bounded SID buffers.
        let status = unsafe {
            MsiEnumProductsExW(
                ptr::null(),
                sid,
                ALL_CONTEXTS,
                index as u32,
                code.as_mut_ptr(),
                &mut context,
                owner.as_mut_ptr(),
                &mut owner_size,
            )
        };
        if status == ERROR_NO_MORE_ITEMS {
            return Ok(products);
        }
        if status != ERROR_SUCCESS || index == MAX_PRODUCTS || owner_size as usize >= owner.len() {
            return Err(Refusal::IncompleteInventory);
        }
        let scope = match context {
            MACHINE => Scope::Machine,
            1 | 2 => Scope::User,
            _ => return Err(Refusal::AmbiguousOwnership),
        };
        let family = cached_family(&code, context, &owner)?;
        products.push(Product {
            code: String::from_utf16(&code[..38]).map_err(|_| Refusal::AmbiguousOwnership)?,
            family,
            scope,
            sid: if scope == Scope::Machine {
                None
            } else {
                Some(
                    String::from_utf16(&owner[..owner_size as usize])
                        .map_err(|_| Refusal::AmbiguousOwnership)?,
                )
            },
        });
    }
    Err(Refusal::IncompleteInventory)
}

fn prepare(install: u32) -> Result<(), Refusal> {
    // SAFETY: MSI returns an owned database handle for the borrowed session handle.
    let database = Handle::new(unsafe { MsiGetActiveDatabase(install) })?;
    // Read the authored database, not an overridable public MSI property.
    let all_users = session_property(install, "ALLUSERS")?;
    let suffix = if all_users == "1" {
        "Machine"
    } else if all_users.is_empty() {
        "User"
    } else {
        return Err(Refusal::AmbiguousOwnership);
    };
    let scoped = property(&database, &format!("CadrumoAdmission{suffix}"))?;
    let combined = scoped.is_some();
    let value = scoped
        .or(property(&database, "CadrumoAdmission")?)
        .ok_or(Refusal::InvalidRequest)?;
    let request = Request::parse(&value)?;
    if (request.scope == Scope::Machine && all_users != "1")
        || (request.scope == Scope::User && !all_users.is_empty())
    {
        return Err(Refusal::AmbiguousOwnership);
    }
    let name = wide(&format!(
        "CadrumoScopeAdmission{}",
        if combined { suffix } else { "" }
    ))?;
    let value = wide(&serde_json::to_string(&request).map_err(|_| Refusal::InvalidRequest)?)?;
    // SAFETY: The strings are terminated. Windows Installer copies the deferred data.
    result(unsafe { MsiSetPropertyW(install, name.as_ptr(), value.as_ptr()) })
}

fn admit(install: u32) -> Result<(), Refusal> {
    let request = Request::parse(&session_property(install, "CustomActionData")?)?;
    request.admit(&inventory(request.scope)?)
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OwnerMetadata {
    pub schema: u32,
    #[serde(default)]
    pub scope: Option<Scope>,
    pub product_code: String,
    pub role: crate::owner::Role,
    pub runner_sha256: cadrumo_application::value::Sha256Digest,
    pub identity: cadrumo_application::installation::maintenance::Identity,
    pub publication: cadrumo_application::value::RelativePath,
}

impl OwnerMetadata {
    pub fn admits_role(&self, scope: Scope, role: crate::owner::Role) -> bool {
        (self.schema == 2 && self.scope == Some(scope) && self.role == role)
            || (self.schema == 3
                && self.scope.is_none()
                && self.role == crate::owner::Role::Application
                && role != crate::owner::Role::Application)
    }
}

fn prepare_owner(install: u32) -> Result<(), Refusal> {
    // SAFETY: MSI returns an owned database handle for this borrowed session.
    let database = Handle::new(unsafe { MsiGetActiveDatabase(install) })?;
    let metadata = property(&database, "CadrumoOwner")?.ok_or(Refusal::InvalidRequest)?;
    let metadata: OwnerMetadata =
        serde_json::from_str(&metadata).map_err(|_| Refusal::InvalidRequest)?;
    let product = property(&database, "ProductCode")?.ok_or(Refusal::InvalidRequest)?;
    let combined = metadata.schema == 3
        && metadata.role == crate::owner::Role::Application
        && metadata.scope.is_none();
    if (!combined && metadata.schema != 2) || canonical_guid(&product)? != metadata.product_code {
        return Err(Refusal::InvalidRequest);
    }
    let all_users = session_property(install, "ALLUSERS")?;
    let scope = if all_users == "1" {
        Scope::Machine
    } else if all_users.is_empty() {
        Scope::User
    } else {
        return Err(Refusal::AmbiguousOwnership);
    };
    let (role, operation) = if combined {
        selected_feature(install)?
    } else {
        if metadata.scope != Some(scope) {
            return Err(Refusal::AmbiguousOwnership);
        }
        (
            metadata.role,
            if session_property(install, "REMOVE")?.is_empty() {
                crate::owner::Operation::Install
            } else {
                crate::owner::Operation::Remove
            },
        )
    };
    let callback = crate::owner::Callback {
        schema: 2,
        identity: metadata.identity,
        publication: metadata.publication,
        claim: crate::owner::Claim {
            product_code: metadata.product_code,
            scope,
            prefix: PathBuf::from(session_property(install, "INSTALL_ROOT")?),
            operation,
            role,
        },
    };
    let bytes = serde_json::to_vec(&callback).map_err(|_| Refusal::InvalidRequest)?;
    crate::owner::Callback::parse(&bytes)?;
    let name = wide(&format!(
        "CadrumoAuthenticateOwner{}",
        if combined {
            if scope == Scope::Machine {
                "Machine"
            } else {
                "User"
            }
        } else {
            ""
        }
    ))?;
    let value = wide(std::str::from_utf8(&bytes).map_err(|_| Refusal::InvalidRequest)?)?;
    // SAFETY: MSI copies the bounded strings for the deferred action.
    result(unsafe { MsiSetPropertyW(install, name.as_ptr(), value.as_ptr()) })
}

fn feature_states(install: u32, feature: NativeFeature) -> Result<(i32, i32), Refusal> {
    let feature = wide(feature.id())?;
    let mut installed = 0;
    let mut action = 0;
    // SAFETY: borrowed native session, immutable authored feature name and live outputs.
    result(unsafe { MsiGetFeatureStateW(install, feature.as_ptr(), &mut installed, &mut action) })?;
    Ok((installed, action))
}

fn selected_feature(
    install: u32,
) -> Result<(crate::owner::Role, crate::owner::Operation), Refusal> {
    let (feature, other, role) = match session_property(install, "CADRUMO_MSI_FEATURE")?.as_str() {
        "VersionFiles" => (
            NativeFeature::Version,
            NativeFeature::Registration,
            crate::owner::Role::Version,
        ),
        "SharedRegistration" => (
            NativeFeature::Registration,
            NativeFeature::Version,
            crate::owner::Role::Registration,
        ),
        _ => return Err(Refusal::InvalidRequest),
    };
    for property in [
        "ADVERTISE",
        "ADDDEFAULT",
        "ADDSOURCE",
        "COMPADDLOCAL",
        "COMPADDSOURCE",
        "FILEADDLOCAL",
        "FILEADDSOURCE",
    ] {
        if !session_property(install, property)?.is_empty() {
            return Err(Refusal::InvalidRequest);
        }
    }
    let remove = session_property(install, "REMOVE")?;
    let add = session_property(install, "ADDLOCAL")?;
    let reinstall = session_property(install, "REINSTALL")?;
    let (_, target_action) = feature_states(install, feature)?;
    let other_states = feature_states(install, other)?;
    let operation = feature_operation(
        feature,
        target_action,
        other_states,
        (&remove, &add, &reinstall),
    )?;
    Ok((role, operation))
}

fn feature_operation(
    feature: NativeFeature,
    target_action: i32,
    other_states: (i32, i32),
    selectors: (&str, &str, &str),
) -> Result<crate::owner::Operation, Refusal> {
    let (other_installed, other_action) = other_states;
    let (remove, add, reinstall) = selectors;
    if !matches!(other_installed, -1 | 2 | 3)
        || (other_installed == 3 && other_action != 3)
        || (other_installed != 3 && !matches!(other_action, -1 | 2))
    {
        return Err(Refusal::InvalidRequest);
    }
    let operation = if remove.is_empty() {
        if add != feature.id()
            || (!reinstall.is_empty() && reinstall != feature.id())
            || target_action != 3
        {
            return Err(Refusal::InvalidRequest);
        }
        crate::owner::Operation::Install
    } else {
        if (!add.is_empty())
            || !reinstall.is_empty()
            || target_action != 2
            || !(remove == feature.id() || (remove == "ALL" && other_installed != 3))
        {
            return Err(Refusal::InvalidRequest);
        }
        crate::owner::Operation::Remove
    };
    Ok(operation)
}

fn authenticate_owner(install: u32) -> Result<(), Refusal> {
    let data = session_property(install, "CustomActionData")?;
    let callback = crate::owner::Callback::parse(data.as_bytes())?;
    // Deferred actions can read ProductCode; bind the request to their actual native product.
    if canonical_guid(&session_property(install, "ProductCode")?)? != callback.claim.product_code {
        return Err(Refusal::InvalidRequest);
    }
    crate::owner::authenticate(&callback)
}

fn boundary(install: u32, operation: fn(u32) -> Result<(), Refusal>) -> u32 {
    let outcome =
        std::panic::catch_unwind(|| operation(install)).unwrap_or(Err(Refusal::NativeFailure));
    if let Err(refusal) = outcome {
        // No paths, SIDs, process details or property values enter MSI logs.
        // SAFETY: CreateRecord returns owned MSI storage or zero on failure.
        if let Ok(record) = Handle::new(unsafe { MsiCreateRecord(0) })
            && let Ok(message) = wide(refusal.message())
        {
            // SAFETY: Field zero is the MSI message template; all handles remain live.
            unsafe {
                MsiRecordSetStringW(record.0, 0, message.as_ptr());
                MsiProcessMessage(install, 0x0100_0000, record.0);
            }
        }
        ERROR_INSTALL_FAILURE
    } else {
        ERROR_SUCCESS
    }
}

/// Prepare a bounded request from immutable MSI database metadata.
#[unsafe(no_mangle)]
pub extern "system" fn CadrumoPrepareAdmission(install: u32) -> u32 {
    boundary(install, prepare)
}
/// Deferred, checked custom action; per-machine authoring must disable impersonation.
#[unsafe(no_mangle)]
pub extern "system" fn CadrumoScopeAdmission(install: u32) -> u32 {
    boundary(install, admit)
}

#[unsafe(no_mangle)]
pub extern "system" fn CadrumoPrepareOwner(install: u32) -> u32 {
    boundary(install, prepare_owner)
}
#[unsafe(no_mangle)]
pub extern "system" fn CadrumoAuthenticateOwner(install: u32) -> u32 {
    boundary(install, authenticate_owner)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selective_feature_actions_preserve_other_role_and_refuse_wider_mutation() {
        use crate::owner::Operation::{Install, Remove};
        use NativeFeature::{Registration, Version};
        for (feature, action, other, selectors, expected) in [
            (Version, 3, (-1, -1), ("", "VersionFiles", ""), Ok(Install)),
            (
                Version,
                3,
                (3, 3),
                ("", "VersionFiles", "VersionFiles"),
                Ok(Install),
            ),
            (
                Registration,
                3,
                (3, 3),
                ("", "SharedRegistration", ""),
                Ok(Install),
            ),
            (Version, 2, (3, 3), ("VersionFiles", "", ""), Ok(Remove)),
            (Registration, 2, (2, 2), ("ALL", "", ""), Ok(Remove)),
            (
                Version,
                2,
                (3, 3),
                ("ALL", "", ""),
                Err(Refusal::InvalidRequest),
            ),
            (
                Version,
                2,
                (3, 2),
                ("VersionFiles", "", ""),
                Err(Refusal::InvalidRequest),
            ),
            (
                Version,
                3,
                (2, 3),
                ("", "VersionFiles", ""),
                Err(Refusal::InvalidRequest),
            ),
            (
                Version,
                3,
                (3, 3),
                ("", "VersionFiles", "ALL"),
                Err(Refusal::InvalidRequest),
            ),
            (
                Version,
                3,
                (3, 3),
                ("", "SharedRegistration", ""),
                Err(Refusal::InvalidRequest),
            ),
            (
                Version,
                2,
                (2, 2),
                ("VersionFiles", "SharedRegistration", ""),
                Err(Refusal::InvalidRequest),
            ),
            (
                Version,
                0,
                (2, 2),
                ("", "VersionFiles", ""),
                Err(Refusal::InvalidRequest),
            ),
        ] {
            assert_eq!(
                feature_operation(feature, action, other, selectors),
                expected
            );
        }
    }

    #[test]
    fn invalid_session_handles_fail_closed_at_both_exported_boundaries() {
        assert_eq!(CadrumoPrepareAdmission(0), ERROR_INSTALL_FAILURE);
        assert_eq!(CadrumoScopeAdmission(0), ERROR_INSTALL_FAILURE);
        assert_eq!(CadrumoPrepareOwner(0), ERROR_INSTALL_FAILURE);
        assert_eq!(CadrumoAuthenticateOwner(0), ERROR_INSTALL_FAILURE);
    }

    #[test]
    fn native_exact_product_inventory_distinguishes_absence_without_installing() {
        let directory = tempfile::tempdir().unwrap();
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let digits = format!("{unique:032X}");
        let code = format!(
            "{}-{}-{}-{}-{}",
            &digits[..8],
            &digits[8..12],
            &digits[12..16],
            &digits[16..20],
            &digits[20..]
        );
        let owner =
            NativeOwner::new(code, NativeContext::Machine, directory.path().to_owned()).unwrap();
        assert_eq!(MsiInventory.locate(&owner).unwrap(), None);
        assert!(directory.path().is_dir());
    }

    #[test]
    fn native_database_properties_are_parameter_bound_and_missing_is_distinct() {
        let directory = tempfile::tempdir().unwrap();
        let path = wide(directory.path().join("fixture.msi").to_str().unwrap()).unwrap();
        let mut database = 0;
        // SAFETY: MSIDBOPEN_CREATE is the documented integer mode 3. The path and
        // output are live and this creates only an isolated empty test database.
        result(unsafe { MsiOpenDatabaseW(path.as_ptr(), 3_usize as *const u16, &mut database) })
            .unwrap();
        let database = Handle::new(database).unwrap();
        for statement in [
            "CREATE TABLE `Property` (`Property` CHAR(72) NOT NULL, `Value` CHAR(0) LOCALIZABLE PRIMARY KEY `Property`)",
            "INSERT INTO `Property` (`Property`, `Value`) VALUES ('ProductCode', '{A0000000-0000-0000-0000-000000000000}')",
            "INSERT INTO `Property` (`Property`, `Value`) VALUES ('CadrumoAdmission', 'immutable authored data')",
        ] {
            let statement = wide(statement).unwrap();
            let mut view = 0;
            // SAFETY: Owned isolated database, terminated static SQL, writable output.
            result(unsafe { MsiDatabaseOpenViewW(database.0, statement.as_ptr(), &mut view) })
                .unwrap();
            let view = Handle::new(view).unwrap();
            // SAFETY: These statements contain no parameters.
            result(unsafe { MsiViewExecute(view.0, 0) }).unwrap();
        }
        assert_eq!(
            property(&database, "CadrumoAdmission").unwrap().as_deref(),
            Some("immutable authored data")
        );
        assert_eq!(property(&database, "UnknownProperty").unwrap(), None);
        assert_eq!(property(&database, "' OR '1' = '1").unwrap(), None);
    }
    #[test]
    fn native_installer_ui_is_quiet_serialized_and_restored() {
        // Native UI requests may normalize to NONE on a Session 0 host. Capture
        // the observed prior level; this test does not claim interactive UI proof.
        // SAFETY: changes this test process's UI only; no installation is invoked.
        let initial = unsafe { MsiSetInternalUI(3, ptr::null_mut()) };
        // SAFETY: INSTALLUILEVEL_NOCHANGE observes the actual native level.
        let prior = unsafe { MsiSetInternalUI(0, ptr::null_mut()) };
        let ui = InstallerUi::quiet().unwrap();
        let previous = ui.previous;
        assert_eq!(previous, prior);
        // SAFETY: INSTALLUILEVEL_NOCHANGE queries this process's current UI level.
        assert_eq!(unsafe { MsiSetInternalUI(0, ptr::null_mut()) }, 2);
        assert!(InstallerUi::quiet().is_err());
        drop(ui);
        // SAFETY: Read-only query after the RAII guard restored native process state.
        assert_eq!(unsafe { MsiSetInternalUI(0, ptr::null_mut()) }, previous);
        // SAFETY: restore the test process's original choice after verification.
        unsafe {
            MsiSetInternalUI(initial, ptr::null_mut());
        }
    }
}
#[test]
fn reinstall_properties_require_exact_native_presence_and_never_skip_fresh_install() {
    let root = tempfile::tempdir().unwrap();
    let owner = NativeOwner::new(
        "12345678-1234-1234-1234-123456789ABC".into(),
        NativeContext::Machine,
        root.path().to_owned(),
    )
    .unwrap();
    let fresh = installation_properties(&owner, "endpoint", None).unwrap();
    assert!(!fresh.contains("REINSTALL"));
    assert!(fresh.contains("REBOOT=ReallySuppress"));
    let repair = installation_properties(&owner, "endpoint", Some(&owner)).unwrap();
    assert!(repair.ends_with(" REINSTALL=ALL REINSTALLMODE=amus"));
    let foreign = NativeOwner::new(
        owner.product_code().into(),
        NativeContext::Machine,
        root.path().join("other-prefix"),
    )
    .unwrap();
    assert_eq!(
        installation_properties(&owner, "endpoint", Some(&foreign)),
        Err(Refusal::InvalidRequest)
    );
    assert_eq!(
        installation_properties(&owner, "endpoint\" REINSTALL=ALL", None),
        Err(Refusal::InvalidRequest)
    );
}
