//! The linked manager image carries the version resource its projected names require,
//! read back through the operating system's own version-information parser.
#![cfg(windows)]

use cadrumo_manager::identity;
use std::path::Path;

const MANAGER: &str = env!("CARGO_BIN_EXE_cadrumo-manager");
const STRINGS: &str = r"\StringFileInfo\040904b0";
const VS_FFI_SIGNATURE: u32 = 0xFEEF_04BD;
const VFT_APP: u32 = 1;
const EN_US: u16 = 0x0409;
const UTF16: u16 = 1200;

fn text(info: &version_api::VersionInfo, name: &str) -> String {
    let units: Vec<u16> = info
        .query(&format!(r"{STRINGS}\{name}"), 2)
        .unwrap_or_else(|| panic!("the version resource names {name}"))
        .chunks_exact(2)
        .map(|pair| u16::from_le_bytes([pair[0], pair[1]]))
        .take_while(|&unit| unit != 0)
        .collect();
    String::from_utf16(&units).expect("UTF-16 version string")
}

fn dword(bytes: &[u8], index: usize) -> u32 {
    u32::from_le_bytes(
        bytes[index * 4..index * 4 + 4]
            .try_into()
            .expect("four bytes"),
    )
}

#[test]
fn strings_name_the_manager_product_and_version() {
    let info = version_api::VersionInfo::read(Path::new(MANAGER));
    let file_name = Path::new(MANAGER)
        .file_name()
        .and_then(|name| name.to_str())
        .expect("the manager image has a file name");
    assert_eq!(text(&info, "FileDescription"), identity::MANAGER_NAME);
    assert_eq!(text(&info, "ProductName"), identity::NAME);
    assert_eq!(text(&info, "FileVersion"), identity::VERSION);
    assert_eq!(text(&info, "ProductVersion"), identity::VERSION);
    assert_eq!(text(&info, "OriginalFilename"), file_name);
    assert_eq!(file_name, "cadrumo-manager.exe");
}

#[test]
fn fixed_version_matches_the_projected_release_version() {
    let info = version_api::VersionInfo::read(Path::new(MANAGER));
    let fixed = info.query("\\", 1).expect("the fixed file information");
    assert_eq!(fixed.len(), 52);
    assert_eq!(dword(fixed, 0), VS_FFI_SIGNATURE);
    let parts: Vec<u32> = identity::VERSION
        .split('.')
        .map(|part| part.parse().expect("numeric version part"))
        .collect();
    let expected = ((parts[0] << 16) | parts[1], parts[2] << 16);
    assert_eq!((dword(fixed, 2), dword(fixed, 3)), expected, "file version");
    assert_eq!(
        (dword(fixed, 4), dword(fixed, 5)),
        expected,
        "product version"
    );
    assert_eq!(dword(fixed, 7), 0, "a release image carries no file flags");
    assert_eq!(dword(fixed, 9), VFT_APP);
}

#[test]
fn translation_declares_the_string_table() {
    let info = version_api::VersionInfo::read(Path::new(MANAGER));
    let translation = info
        .query(r"\VarFileInfo\Translation", 1)
        .expect("the translation entry");
    assert_eq!(
        translation,
        [EN_US.to_le_bytes(), UTF16.to_le_bytes()].concat()
    );
}

/// Version-information reads through `version.dll`.
#[allow(unsafe_code)]
mod version_api {
    use std::{ffi::c_void, iter, os::windows::ffi::OsStrExt, path::Path, ptr};

    #[link(name = "version")]
    unsafe extern "system" {
        fn GetFileVersionInfoSizeW(filename: *const u16, handle: *mut u32) -> u32;
        fn GetFileVersionInfoW(
            filename: *const u16,
            handle: u32,
            length: u32,
            data: *mut c_void,
        ) -> i32;
        fn VerQueryValueW(
            block: *const c_void,
            sub_block: *const u16,
            buffer: *mut *mut c_void,
            length: *mut u32,
        ) -> i32;
    }

    /// A version-information block as `GetFileVersionInfoW` returned it.
    pub struct VersionInfo {
        // u64 storage keeps the block aligned for the UTF-16 and DWORD fields inside it.
        block: Vec<u64>,
        bytes: Vec<u8>,
    }

    fn wide(units: impl Iterator<Item = u16>) -> Vec<u16> {
        units.chain(iter::once(0)).collect()
    }

    impl VersionInfo {
        pub fn read(path: &Path) -> Self {
            let name = wide(path.as_os_str().encode_wide());
            let mut ignored = 0;
            // SAFETY: `name` is NUL-terminated and outlives the call; `ignored` is a valid
            // out-parameter.
            let size = unsafe { GetFileVersionInfoSizeW(name.as_ptr(), &raw mut ignored) };
            assert_ne!(size, 0, "{} has a version resource", path.display());
            let length = usize::try_from(size).expect("the block size fits usize");
            let mut block = vec![0_u64; length.div_ceil(8)];
            // SAFETY: `block` provides at least `size` writable, aligned bytes and `name` is
            // NUL-terminated; both outlive the call.
            let read =
                unsafe { GetFileVersionInfoW(name.as_ptr(), 0, size, block.as_mut_ptr().cast()) };
            assert_ne!(read, 0, "read the version resource of {}", path.display());
            let mut bytes: Vec<u8> = block.iter().flat_map(|word| word.to_ne_bytes()).collect();
            bytes.truncate(length);
            Self { block, bytes }
        }

        /// Return the value at `sub_block`, `unit` bytes per reported length unit, bounded
        /// by the block itself.
        pub fn query(&self, sub_block: &str, unit: usize) -> Option<&[u8]> {
            let path = wide(sub_block.encode_utf16());
            let mut value = ptr::null_mut();
            let mut length = 0_u32;
            // SAFETY: `block` is the initialized buffer `GetFileVersionInfoW` filled and is not
            // mutated; `path` is NUL-terminated; both out-parameters are valid. The returned
            // pointer is only compared by address, never dereferenced.
            let found = unsafe {
                VerQueryValueW(
                    self.block.as_ptr().cast(),
                    path.as_ptr(),
                    &raw mut value,
                    &raw mut length,
                )
            };
            if found == 0 || value.is_null() {
                return None;
            }
            let start = value.addr().checked_sub(self.block.as_ptr().addr())?;
            let end = start.checked_add(usize::try_from(length).ok()?.checked_mul(unit)?)?;
            self.bytes.get(start..end)
        }
    }
}
