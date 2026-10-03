#[cfg(not(target_os = "windows"))]
compile_error!("Only the Windows foundation has been implemented");

use std::os::windows::fs::MetadataExt;
use std::{
    env, fs,
    path::{Path, PathBuf},
    ptr,
};
include!(env!("CADRUMO_CONTRACT_RS"));

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
fn project_root(package: &Path) -> PathBuf {
    let working = env::current_dir().unwrap_or_else(|_| package.to_path_buf());
    for base in [package, working.as_path()] {
        for ancestor in base.ancestors() {
            if ancestor.join("pyproject.toml").is_file() {
                return ancestor.to_path_buf();
            }
        }
    }
    working
}
fn nonempty_environment_path(name: &str) -> Option<PathBuf> {
    env::var_os(name).and_then(|value| {
        if value.to_string_lossy().trim().is_empty() {
            None
        } else {
            Some(PathBuf::from(value))
        }
    })
}
fn rooted(path: PathBuf, root: &Path) -> PathBuf {
    if path.is_absolute() {
        path
    } else {
        root.join(path)
    }
}
fn context_storage_root(root: &Path) -> PathBuf {
    nonempty_environment_path(STORAGE_ENV)
        .or_else(|| nonempty_environment_path(STORAGE_ROOT_ENV))
        .map(|path| rooted(path, root))
        .unwrap_or_else(|| root.join(STORAGE_DEFAULT))
}
fn refined_storage_path(name: &str, root: &Path, default: &Path) -> PathBuf {
    nonempty_environment_path(name)
        .map(|path| rooted(path, root))
        .unwrap_or_else(|| default.to_path_buf())
}
fn context() -> Result<Context, String> {
    let exe = env::current_exe().map_err(|e| e.to_string())?;
    let package = exe
        .parent()
        .ok_or("Executable has no parent")?
        .to_path_buf();
    let root = project_root(&package);
    let user = context_storage_root(&root);
    let temporary = refined_storage_path(TEMPORARY_ENV, &user, &user.join(TEMPORARY_DEFAULT));
    let cache = refined_storage_path(TOOL_CACHE_ENV, &user, &user.join(TOOL_CACHE_DEFAULT));
    let paths = vec![
        package.clone(),
        user.clone(),
        exe,
        package.join(STDLIB),
        package.join(PACKAGES),
        package.join(NATIVE),
        package.join(AUTHORITY),
        user.clone(),
        temporary,
        cache,
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
fn prepare(ctx: &Context) -> Result<(), String> {
    for path in [&ctx.paths[1], &ctx.paths[8], &ctx.paths[9]] {
        refuse_links(path)?;
        fs::create_dir_all(path).map_err(|e| e.to_string())?;
        refuse_links(path)?;
    }
    // Environment mutation occurs once, before Python or application threads exist.
    let names: Vec<_> = env::vars_os().map(|(key, _)| key).collect();
    for name in names {
        let upper = name.to_string_lossy().to_ascii_uppercase();
        let allowed_storage_override = STORAGE_ENV_ALLOWLIST.contains(&upper.as_str())
            || PACKAGE_ENV_ALLOWLIST.contains(&upper.as_str());
        if upper.starts_with("PYTHON")
            || (upper.starts_with("CADRUMO_") && !allowed_storage_override)
            || (RESERVED_ENV.contains(&upper.as_str()) && !allowed_storage_override)
            || [
                "VIRTUAL_ENV",
                "CONDA_PREFIX",
                "CONDA_DEFAULT_ENV",
                "__PYVENV_LAUNCHER__",
            ]
            .contains(&upper.as_str())
        {
            unsafe {
                env::remove_var(name);
            }
        }
    }
    unsafe {
        env::set_var(STORAGE_ENV, &ctx.paths[7]);
        env::set_var(AUTHORITY_ENV, &ctx.paths[6]);
        for name in ["TEMP", "TMP", "TMPDIR"] {
            env::set_var(name, &ctx.paths[8]);
        }
        env::set_var("XDG_CACHE_HOME", &ctx.paths[9]);
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
