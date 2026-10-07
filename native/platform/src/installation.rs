//! Read-only Windows installation discovery hints in both registration scopes.
use std::{
    ffi::{OsString, c_void},
    io,
    os::windows::ffi::OsStringExt,
    path::PathBuf,
    ptr,
};

#[link(name = "advapi32")]
unsafe extern "system" {
    fn RegGetValueW(
        key: *mut c_void,
        subkey: *const u16,
        value: *const u16,
        flags: u32,
        kind: *mut u32,
        data: *mut c_void,
        bytes: *mut u32,
    ) -> i32;
}

/// Registry values never authorize an image; consumers validate the shared catalogue.
pub fn manager_entry_points(application_id: &str) -> io::Result<Vec<PathBuf>> {
    if application_id.is_empty()
        || !application_id
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b".-_".contains(&c))
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid installation identity",
        ));
    }
    let key: Vec<u16> = format!("Software\\{application_id}")
        .encode_utf16()
        .chain([0])
        .collect();
    let value: Vec<u16> = "EntryPoint".encode_utf16().chain([0]).collect();
    let mut paths = Vec::new();
    // Win32 predefined HKEY values are sign-extended LONG_PTR constants, never closed.
    for root in [0x8000_0001u32, 0x8000_0002u32] {
        let mut data = vec![0u16; 32768];
        let mut bytes = (data.len() * 2) as u32;
        // SAFETY: terminated input strings and bounded writable output remain alive;
        // bytes describes the entire buffer. REG_SZ only, explicit 64-bit registry view.
        let result = unsafe {
            RegGetValueW(
                root as i32 as isize as *mut c_void,
                key.as_ptr(),
                value.as_ptr(),
                0x0000_0002 | 0x0001_0000 | 0x2000_0000,
                ptr::null_mut(),
                data.as_mut_ptr().cast(),
                &mut bytes,
            )
        };
        if matches!(result, 2 | 3) {
            continue;
        }
        if result != 0 {
            return Err(io::Error::from_raw_os_error(result));
        }
        if bytes < 2 || bytes as usize > data.len() * 2 || bytes % 2 != 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid entry point size",
            ));
        }
        let text = &data[..bytes as usize / 2];
        if text.last() != Some(&0)
            || text[..text.len() - 1].contains(&0)
            || String::from_utf16(&text[..text.len() - 1]).is_err()
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid entry point path",
            ));
        }
        let path = PathBuf::from(OsString::from_wide(&text[..text.len() - 1]));
        if !path.is_absolute()
            || path
                .components()
                .any(|c| matches!(c, std::path::Component::ParentDir))
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "entry point must be absolute",
            ));
        }
        paths.push(path);
    }
    Ok(paths)
}
