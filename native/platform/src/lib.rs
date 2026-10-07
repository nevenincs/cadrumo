#[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
compile_error!("Unsupported native platform");

#[cfg(windows)]
use std::os::windows::fs::MetadataExt;
use std::{
    env, fs,
    path::{Path, PathBuf},
    ptr,
};
include!(env!("CADRUMO_CONTRACT_RS"));
#[cfg(test)]
mod conformance_tests;
#[cfg(windows)]
pub mod desktop;
#[cfg(all(test, unix))]
mod posix_tests;
pub mod storage;

use storage::Profile;

#[repr(C)]
pub struct Buffer {
    data: *mut u8,
    len: u64,
}
pub struct Context {
    paths: Vec<PathBuf>,
}

fn buffer(s: String) -> Buffer {
    let bytes = s.into_bytes().into_boxed_slice();
    let len = bytes.len() as u64;
    Buffer {
        data: Box::into_raw(bytes) as *mut u8,
        len,
    }
}

fn context() -> Result<Context, String> {
    let exe = env::current_exe().map_err(|e| e.to_string())?;
    context_for(&exe, &|name| env::var_os(name))
}

fn context_for(
    exe: &Path,
    lookup: &dyn Fn(&str) -> Option<std::ffi::OsString>,
) -> Result<Context, String> {
    let evidence = storage::detect_mode(exe)?;
    let user = storage::resolve_storage_root_with(&evidence, lookup)
        .map_err(|refused| refused.to_string())?
        .root;
    let user = normalize_absolute_path(&user).map_err(|e| e.to_string())?;
    let temporary =
        storage::temporary_path(&user, lookup).map_err(|refused| refused.to_string())?;
    let temporary = normalize_absolute_path(&temporary).map_err(|e| e.to_string())?;
    let package = evidence.package;
    let authority = package.join(AUTHORITY);
    for field in HOST_INHERITED_FIELDS {
        storage::validate_inherited_pin(field, authority.as_os_str())
            .map_err(|refused| refused.to_string())?;
    }
    let paths = vec![
        package.clone(),
        user.clone(),
        exe.to_path_buf(),
        package.join(STDLIB),
        package.join(PACKAGES),
        package.join(NATIVE),
        authority,
        user,
        temporary,
    ];
    Ok(Context { paths })
}
pub(crate) fn refuse_links(path: &Path) -> Result<(), String> {
    for ancestor in path.ancestors() {
        match fs::symlink_metadata(ancestor) {
            Ok(meta) if is_link(&meta) => {
                return Err(format!(
                    "Symbolic link or reparse point is not permitted: {}",
                    ancestor.display()
                ));
            }
            Ok(meta) if ancestor != path && !meta.is_dir() => {
                return Err(format!(
                    "Storage path traverses a non-directory: {}",
                    ancestor.display()
                ));
            }
            Ok(_) => {}
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e.to_string()),
        }
    }
    Ok(())
}

fn is_link(meta: &fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        meta.file_attributes() & 0x400 != 0
    }
    #[cfg(unix)]
    {
        meta.file_type().is_symlink()
    }
}

pub(crate) fn create_private_directory(path: &Path) -> std::io::Result<()> {
    if !path.is_absolute() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "Storage path must be absolute",
        ));
    }
    refuse_links(path).map_err(std::io::Error::other)?;
    let mut builder = fs::DirBuilder::new();
    builder.recursive(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::DirBuilderExt;
        builder.mode(POSIX_DIRECTORY_MODE);
    }
    builder.create(path)?;
    refuse_links(path).map_err(std::io::Error::other)
}

pub(crate) fn normalize_absolute_path(path: &Path) -> std::io::Result<PathBuf> {
    storage::validated_absolute_path(path).map_err(std::io::Error::from)
}

/// Names a packaged host clears from itself, keeping the product and package allowlists.
fn cleared(name: &str) -> bool {
    storage::cleared(name, Profile::Operator, PACKAGE_ENV_ALLOWLIST)
}

/// The contract's pinned set plus the host-inherited authority pin, from resolved paths.
fn pinned(ctx: &Context) -> Vec<(&'static str, &Path)> {
    let mut values: Vec<(&'static str, &Path)> = PINNED_ENV
        .iter()
        .map(|&name| {
            let value = if name == ROOT_VARIABLE {
                &ctx.paths[7]
            } else {
                &ctx.paths[8]
            };
            (name, value.as_path())
        })
        .collect();
    values.extend(
        HOST_INHERITED_ENV
            .iter()
            .map(|&name| (name, ctx.paths[6].as_path())),
    );
    values
}

fn executable_search_path(
    ctx: &Context,
    lookup: &dyn Fn(&str) -> Option<std::ffi::OsString>,
) -> Result<std::ffi::OsString, String> {
    let mut search = vec![ctx.paths[0].clone()];
    if let Some(overrides) = lookup("CADRUMO_EXTERNAL_BIN_DIRS") {
        for directory in env::split_paths(&overrides) {
            if !directory.is_absolute() || !directory.is_dir() {
                return Err(
                    "CADRUMO_EXTERNAL_BIN_DIRS requires existing absolute directories".into(),
                );
            }
            search.push(directory);
        }
    }
    search.push(ctx.paths[5].clone());
    #[cfg(windows)]
    {
        let system = lookup("SystemRoot").ok_or("SystemRoot is missing")?;
        search.push(PathBuf::from(system).join("System32"));
    }
    #[cfg(unix)]
    search.extend([PathBuf::from("/usr/bin"), PathBuf::from("/bin")]);
    env::join_paths(search).map_err(|e| e.to_string())
}

fn prepare(ctx: &Context) -> Result<(), String> {
    let search = executable_search_path(ctx, &|name| env::var_os(name))?;
    for path in [&ctx.paths[1], &ctx.paths[8]] {
        create_private_directory(path).map_err(|e| e.to_string())?;
    }
    // Environment mutation occurs once, before Python or application threads exist.
    let names: Vec<_> = env::vars_os().map(|(key, _)| key).collect();
    for name in names {
        if cleared(&name.to_string_lossy()) {
            unsafe {
                env::remove_var(name);
            }
        }
    }
    unsafe {
        for (name, value) in pinned(ctx) {
            env::set_var(name, value);
        }
        env::set_var("PATH", search);
    }
    Ok(())
}

/// Prepare the same environment as the interpreter host without starting Python
/// or changing this process's environment. The caller verifies the executable.
pub fn prepared_environment(
    executable: &Path,
    ambient: &[(std::ffi::OsString, std::ffi::OsString)],
) -> Result<Vec<(std::ffi::OsString, std::ffi::OsString)>, String> {
    let matches = |key: &std::ffi::OsStr, name: &str| {
        if cfg!(windows) {
            key.to_string_lossy().eq_ignore_ascii_case(name)
        } else {
            key == name
        }
    };
    let lookup = |name: &str| {
        ambient
            .iter()
            .rev()
            .find(|(key, _)| matches(key, name))
            .map(|(_, value)| value.clone())
    };
    let ctx = context_for(executable, &lookup)?;
    let search = executable_search_path(&ctx, &lookup)?;
    for path in [&ctx.paths[1], &ctx.paths[8]] {
        create_private_directory(path).map_err(|e| e.to_string())?;
    }
    let pins = pinned(&ctx);
    let mut environment: Vec<_> = ambient
        .iter()
        .filter(|(key, _)| {
            !cleared(&key.to_string_lossy())
                && !matches(key, "PATH")
                && !pins.iter().any(|(name, _)| matches(key, name))
        })
        .cloned()
        .collect();
    environment.extend(
        pins.into_iter()
            .map(|(name, value)| (name.into(), value.as_os_str().to_owned())),
    );
    environment.push(("PATH".into(), search));
    #[cfg(windows)]
    for (key, _) in &mut environment {
        // CPython's Windows os.environ exposes case-insensitive names in
        // uppercase; preserve that representation for exact query parity.
        *key = key
            .to_str()
            .map(|name| name.to_uppercase().into())
            .unwrap_or_else(|| key.to_ascii_uppercase());
    }
    Ok(environment)
}

#[unsafe(no_mangle)]
pub extern "C" fn cadrumo_platform_abi() -> u32 {
    ABI
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_create(
    abi: u32,
    out: *mut *mut Context,
    error: *mut Buffer,
) -> u32 {
    if out.is_null() || error.is_null() {
        return 2;
    }
    unsafe {
        *out = ptr::null_mut();
        *error = Buffer {
            data: ptr::null_mut(),
            len: 0,
        };
    }
    if abi != ABI {
        unsafe {
            *error = buffer("Incompatible platform ABI".into());
        }
        return 1;
    }
    match context() {
        Ok(ctx) => {
            unsafe {
                *out = Box::into_raw(Box::new(ctx));
            }
            0
        }
        Err(e) => {
            unsafe {
                *error = buffer(e);
            }
            3
        }
    }
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_path(
    ctx: *mut Context,
    key: u32,
    out: *mut Buffer,
) -> u32 {
    if ctx.is_null() || out.is_null() {
        return 2;
    }
    unsafe {
        *out = Buffer {
            data: ptr::null_mut(),
            len: 0,
        };
    }
    match unsafe { &*ctx }.paths.get(key as usize) {
        Some(path) => match path.to_str() {
            Some(s) => {
                unsafe {
                    *out = buffer(s.into());
                }
                0
            }
            None => 3,
        },
        None => 2,
    }
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_prepare(ctx: *mut Context, error: *mut Buffer) -> u32 {
    if ctx.is_null() || error.is_null() {
        return 2;
    }
    unsafe {
        *error = Buffer {
            data: ptr::null_mut(),
            len: 0,
        };
    }
    match prepare(unsafe { &*ctx }) {
        Ok(()) => 0,
        Err(e) => {
            unsafe {
                *error = buffer(e);
            }
            3
        }
    }
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_release(b: *mut Buffer) {
    if b.is_null() {
        return;
    }
    let b = unsafe { &mut *b };
    if !b.data.is_null() {
        unsafe {
            drop(Box::from_raw(ptr::slice_from_raw_parts_mut(
                b.data,
                b.len as usize,
            )));
        }
    }
    b.data = ptr::null_mut();
    b.len = 0;
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_destroy(ctx: *mut Context) {
    if !ctx.is_null() {
        unsafe {
            drop(Box::from_raw(ctx));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn packaged_environment_pins_root_temporary_and_authority_and_clears_tool_and_cache_names() {
        let ctx = Context {
            paths: vec![
                PathBuf::from(r"C:\app"),
                PathBuf::from(r"C:\data"),
                PathBuf::from(r"C:\app\python.exe"),
                PathBuf::from(r"C:\app\python.zip"),
                PathBuf::from(r"C:\app\site"),
                PathBuf::from(r"C:\app\bin"),
                PathBuf::from(r"C:\app\data\authority"),
                PathBuf::from(r"C:\data"),
                PathBuf::from(r"C:\data\tmp"),
            ],
        };
        let set: Vec<_> = pinned(&ctx).into_iter().map(|(name, _)| name).collect();
        let mut expected: Vec<&str> = PINNED_ENV.to_vec();
        expected.extend(HOST_INHERITED_ENV);
        assert_eq!(set, expected);
        assert_eq!(set[0], ROOT_VARIABLE);
        assert!(!set.contains(&"XDG_CACHE_HOME"));
        assert!(
            pinned(&ctx)
                .iter()
                .any(|(name, value)| *name == ROOT_VARIABLE && *value == Path::new(r"C:\data"))
        );
        assert!(cleared("PYTHONPATH") && cleared("VIRTUAL_ENV"));
        assert!(cleared(&format!("{NAMESPACE_PREFIX}SECRET_PASSPHRASE")));
        assert!(!cleared(ROOT_VARIABLE));
        assert!(!cleared("SYSTEMROOT"));
        assert!(PRODUCT_ENV_ALLOWLIST.iter().all(|name| !cleared(name)));
        assert!(PACKAGE_ENV_ALLOWLIST.iter().all(|name| !cleared(name)));
    }
}
