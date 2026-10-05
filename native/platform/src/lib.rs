#[cfg(not(target_os = "windows"))]
compile_error!("Only the Windows foundation has been implemented");

use std::os::windows::fs::MetadataExt;
use std::{
    env, fs,
    path::{Path, PathBuf},
    ptr,
};
include!(env!("CADRUMO_CONTRACT_RS"));
pub mod desktop;
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
    let evidence = storage::detect_mode(&exe)?;
    let user = storage::resolve_storage_root(&evidence)
        .map_err(|refused| refused.message)?
        .root;
    let temporary = storage::temporary_path(&user, &storage::environment_value);
    let package = evidence.package;
    let paths = vec![
        package.clone(),
        user.clone(),
        exe,
        package.join(STDLIB),
        package.join(PACKAGES),
        package.join(NATIVE),
        package.join(AUTHORITY),
        user,
        temporary,
    ];
    Ok(Context { paths })
}
fn refuse_links(path: &Path) -> Result<(), String> {
    for ancestor in path.ancestors() {
        match fs::symlink_metadata(ancestor) {
            Ok(meta) if meta.file_attributes() & 0x400 != 0 => {
                return Err(format!(
                    "Reparse point is not permitted: {}",
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

fn prepare(ctx: &Context) -> Result<(), String> {
    for path in [&ctx.paths[1], &ctx.paths[8]] {
        refuse_links(path)?;
        fs::create_dir_all(path).map_err(|e| e.to_string())?;
        refuse_links(path)?;
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
        let system = env::var_os("SystemRoot").ok_or("SystemRoot is missing")?;
        let mut search = vec![ctx.paths[0].clone()];
        if let Some(overrides) = env::var_os("CADRUMO_EXTERNAL_BIN_DIRS") {
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
        search.push(PathBuf::from(system).join("System32"));
        let path = env::join_paths(search).map_err(|e| e.to_string())?;
        env::set_var("PATH", path);
    }
    Ok(())
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
