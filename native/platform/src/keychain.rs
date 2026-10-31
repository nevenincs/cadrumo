//! Reads one generic password from this account's macOS keychain without ever asking the
//! person.
//!
//! The read forbids interaction: an item whose access list or partition does not admit
//! this program, or a locked keychain, answers with a refusal instead of a prompt. An
//! absent item is reported as absent. Security and CoreFoundation are loaded at run time,
//! so a host that links this library does not have to link the frameworks.

use std::{
    ffi::{CStr, c_void},
    io, ptr,
};

type CfType = *const c_void;

/// `errSecItemNotFound`: no item matches the query.
const ITEM_NOT_FOUND: i32 = -25300;
/// `kCFStringEncodingUTF8`.
const UTF8: u32 = 0x0800_0100;

struct Library(*mut c_void);

impl Library {
    fn open(path: &CStr) -> io::Result<Self> {
        // SAFETY: a terminated system framework path; the handle is retained by Self.
        let handle = unsafe { libc::dlopen(path.as_ptr(), libc::RTLD_NOW | libc::RTLD_LOCAL) };
        if handle.is_null() {
            return Err(io::ErrorKind::Unsupported.into());
        }
        Ok(Self(handle))
    }

    fn symbol(&self, name: &CStr) -> io::Result<*mut c_void> {
        // SAFETY: a terminated symbol name and a live handle.
        let symbol = unsafe { libc::dlsym(self.0, name.as_ptr()) };
        if symbol.is_null() {
            return Err(io::ErrorKind::Unsupported.into());
        }
        Ok(symbol)
    }

    /// The value of an exported constant object reference.
    fn constant(&self, name: &CStr) -> io::Result<CfType> {
        let address = self.symbol(name)?;
        // SAFETY: the framework exports this name as a constant object reference.
        let value = unsafe { *(address as *const CfType) };
        if value.is_null() {
            return Err(io::ErrorKind::Unsupported.into());
        }
        Ok(value)
    }
}

impl Drop for Library {
    fn drop(&mut self) {
        // SAFETY: no function pointer or object from this handle outlives Frameworks.
        unsafe {
            libc::dlclose(self.0);
        }
    }
}

type Release = unsafe extern "C" fn(CfType);
type CreateString = unsafe extern "C" fn(CfType, *const u8, isize, u32, u8) -> CfType;
type CreateDictionary = unsafe extern "C" fn(
    CfType,
    *const CfType,
    *const CfType,
    isize,
    *const c_void,
    *const c_void,
) -> CfType;
type InteractionQuery = unsafe extern "C" fn(*mut u8) -> i32;
type InteractionSet = unsafe extern "C" fn(u8) -> i32;

/// One owned CoreFoundation reference, released once.
struct Owned {
    value: CfType,
    release: Release,
}

impl Drop for Owned {
    fn drop(&mut self) {
        if !self.value.is_null() {
            // SAFETY: an owned reference this module created or was given.
            unsafe { (self.release)(self.value) }
        }
    }
}

/// The two frameworks, loaded for as long as the references made through them live.
struct Frameworks {
    security: Library,
    foundation: Library,
    release: Release,
    create_string: CreateString,
    create_dictionary: CreateDictionary,
}

impl Frameworks {
    fn open() -> io::Result<Self> {
        let foundation =
            Library::open(c"/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")?;
        let security = Library::open(c"/System/Library/Frameworks/Security.framework/Security")?;
        // SAFETY: each symbol has exactly the CoreFoundation ABI named by its type, and
        // the library stays loaded for as long as Self.
        let (release, create_string, create_dictionary) = unsafe {
            (
                std::mem::transmute::<*mut c_void, Release>(foundation.symbol(c"CFRelease")?),
                std::mem::transmute::<*mut c_void, CreateString>(
                    foundation.symbol(c"CFStringCreateWithBytes")?,
                ),
                std::mem::transmute::<*mut c_void, CreateDictionary>(
                    foundation.symbol(c"CFDictionaryCreate")?,
                ),
            )
        };
        Ok(Self {
            security,
            foundation,
            release,
            create_string,
            create_dictionary,
        })
    }

    /// Takes ownership of a reference a framework call returned.
    fn owned(&self, value: CfType) -> Owned {
        Owned {
            value,
            release: self.release,
        }
    }

    fn string(&self, text: &str) -> io::Result<Owned> {
        let length = isize::try_from(text.len()).map_err(|_| io::ErrorKind::InvalidInput)?;
        // SAFETY: the bytes are valid for `length` and copied by CoreFoundation.
        let value = unsafe { (self.create_string)(ptr::null(), text.as_ptr(), length, UTF8, 0) };
        if value.is_null() {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        Ok(self.owned(value))
    }

    fn dictionary(&self, entries: &[(CfType, CfType)]) -> io::Result<Owned> {
        let keys: Vec<CfType> = entries.iter().map(|entry| entry.0).collect();
        let values: Vec<CfType> = entries.iter().map(|entry| entry.1).collect();
        let key_callbacks = self.foundation.symbol(c"kCFTypeDictionaryKeyCallBacks")?;
        let value_callbacks = self.foundation.symbol(c"kCFTypeDictionaryValueCallBacks")?;
        // SAFETY: two arrays of equal, stated length of live objects; the callback records
        // are the framework's own, which retain what the dictionary holds.
        let value = unsafe {
            (self.create_dictionary)(
                ptr::null(),
                keys.as_ptr(),
                values.as_ptr(),
                keys.len() as isize,
                key_callbacks,
                value_callbacks,
            )
        };
        if value.is_null() {
            return Err(io::ErrorKind::OutOfMemory.into());
        }
        Ok(self.owned(value))
    }

    /// The query entries naming one generic password.
    fn item(&self, service: &Owned, account: &Owned) -> io::Result<Vec<(CfType, CfType)>> {
        Ok(vec![
            (
                self.security.constant(c"kSecClass")?,
                self.security.constant(c"kSecClassGenericPassword")?,
            ),
            (self.security.constant(c"kSecAttrService")?, service.value),
            (self.security.constant(c"kSecAttrAccount")?, account.value),
        ])
    }
}

/// File-based keychains decide on prompting from process-wide state rather than from the
/// query, so interaction is switched off for the read and the prior state restored after.
struct Quiet {
    set: InteractionSet,
    prior: u8,
}

impl Quiet {
    fn begin(frameworks: &Frameworks) -> io::Result<Self> {
        // SAFETY: exact Security ABI for these two calls; the library outlives Self.
        let (query, set) = unsafe {
            (
                std::mem::transmute::<*mut c_void, InteractionQuery>(
                    frameworks
                        .security
                        .symbol(c"SecKeychainGetUserInteractionAllowed")?,
                ),
                std::mem::transmute::<*mut c_void, InteractionSet>(
                    frameworks
                        .security
                        .symbol(c"SecKeychainSetUserInteractionAllowed")?,
                ),
            )
        };
        let mut prior = 0u8;
        // SAFETY: one writable boolean output, then a by-value boolean.
        if unsafe { query(&mut prior) } != 0 || unsafe { set(0) } != 0 {
            return Err(io::Error::other("keychain interaction state unavailable"));
        }
        Ok(Self { set, prior })
    }
}

impl Drop for Quiet {
    fn drop(&mut self) {
        // SAFETY: restores the boolean read in `begin`.
        unsafe {
            (self.set)(self.prior);
        }
    }
}

/// Reads the password stored under `service` and `account`. `Ok(None)` means no such
/// item; any other failure, including an item this program may not read without asking,
/// is an error.
pub fn read_generic_password(service: &str, account: &str) -> io::Result<Option<Vec<u8>>> {
    let frameworks = Frameworks::open()?;
    // SAFETY: each symbol has exactly the CoreFoundation or Security ABI named here, and
    // both libraries stay loaded while `frameworks` lives.
    let (data_length, data_bytes, type_of, data_type, copy_matching) = unsafe {
        (
            std::mem::transmute::<*mut c_void, unsafe extern "C" fn(CfType) -> isize>(
                frameworks.foundation.symbol(c"CFDataGetLength")?,
            ),
            std::mem::transmute::<*mut c_void, unsafe extern "C" fn(CfType) -> *const u8>(
                frameworks.foundation.symbol(c"CFDataGetBytePtr")?,
            ),
            std::mem::transmute::<*mut c_void, unsafe extern "C" fn(CfType) -> usize>(
                frameworks.foundation.symbol(c"CFGetTypeID")?,
            ),
            std::mem::transmute::<*mut c_void, unsafe extern "C" fn() -> usize>(
                frameworks.foundation.symbol(c"CFDataGetTypeID")?,
            ),
            std::mem::transmute::<*mut c_void, unsafe extern "C" fn(CfType, *mut CfType) -> i32>(
                frameworks.security.symbol(c"SecItemCopyMatching")?,
            ),
        )
    };
    let service = frameworks.string(service)?;
    let account = frameworks.string(account)?;
    let mut entries = frameworks.item(&service, &account)?;
    entries.extend([
        (
            frameworks.security.constant(c"kSecReturnData")?,
            frameworks.foundation.constant(c"kCFBooleanTrue")?,
        ),
        (
            frameworks.security.constant(c"kSecMatchLimit")?,
            frameworks.security.constant(c"kSecMatchLimitOne")?,
        ),
        (
            frameworks.security.constant(c"kSecUseAuthenticationUI")?,
            frameworks
                .security
                .constant(c"kSecUseAuthenticationUIFail")?,
        ),
    ]);
    let query = frameworks.dictionary(&entries)?;
    let mut result: CfType = ptr::null();
    let status = {
        let _quiet = Quiet::begin(&frameworks)?;
        // SAFETY: a live query and a writable result the call fills with an owned reference.
        unsafe { copy_matching(query.value, &mut result) }
    };
    let result = frameworks.owned(result);
    match status {
        0 => {}
        ITEM_NOT_FOUND => return Ok(None),
        code => return Err(io::Error::other(format!("keychain status {code}"))),
    }
    // SAFETY: a live object; its type is checked before it is read as data.
    if result.value.is_null() || unsafe { type_of(result.value) != data_type() } {
        return Err(io::ErrorKind::InvalidData.into());
    }
    // SAFETY: a live data object whose bytes stay valid while `result` is held.
    let bytes = unsafe {
        let length =
            usize::try_from(data_length(result.value)).map_err(|_| io::ErrorKind::InvalidData)?;
        let start = data_bytes(result.value);
        if length == 0 {
            Vec::new()
        } else if start.is_null() {
            return Err(io::ErrorKind::InvalidData.into());
        } else {
            std::slice::from_raw_parts(start, length).to_vec()
        }
    };
    Ok(Some(bytes))
}

#[cfg(test)]
mod tests;
