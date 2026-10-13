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
#[cfg(windows)]
pub mod installation;
pub mod launch;
#[cfg(all(test, unix))]
mod posix_tests;
pub mod storage;
#[cfg(target_os = "macos")]
pub mod transport;

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

/// The image a packaged executable is, from its declared file name in the package.
fn executable_image(executable: &Path) -> Option<&'static str> {
    let name = executable.file_name()?.to_str()?;
    if storage::filename_matches(name, EXECUTABLE) {
        return Some("python");
    }
    let suffix = Path::new(EXECUTABLE)
        .extension()
        .map(|extension| format!(".{}", extension.to_string_lossy()))
        .unwrap_or_default();
    LAUNCH_IMAGES
        .iter()
        .copied()
        .find(|image| storage::filename_matches(name, &format!("{image}{suffix}")))
}

/// Define the environment `executable`'s default profile gives a caller holding `ambient`.
fn define_for(
    executable: &Path,
    ambient: &[(std::ffi::OsString, std::ffi::OsString)],
) -> Result<launch::Defined, String> {
    let image = executable_image(executable)
        .ok_or_else(|| format!("{} is not a declared package image", executable.display()))?;
    let evidence = storage::detect_mode(executable)?;
    let profile = launch::select(image, &[]).map_err(describe)?;
    launch::define_environment(profile, ambient, &evidence.package.clone(), &|lookup| {
        storage::resolve_storage_root_with(&evidence, lookup).map(|resolved| resolved.root)
    })
    .map_err(describe)
}

fn describe(error: launch::DefineError) -> String {
    match error {
        launch::DefineError::Refused(refusal) => refusal.line(),
        launch::DefineError::Failed(message) => message,
    }
}

fn prepare(ctx: &Context) -> Result<(), String> {
    let ambient: Vec<_> = env::vars_os().collect();
    let defined = define_for(&ctx.paths[2], &ambient)?;
    // Environment mutation occurs once, before Python or application threads exist.
    unsafe { launch::apply(&defined) }.map_err(describe)
}

/// Define the environment `executable` gives a caller holding `ambient`, without starting
/// Python or changing this process's environment. Its pinned directories are created.
/// The caller verifies the executable.
pub fn prepared_environment(
    executable: &Path,
    ambient: &[(std::ffi::OsString, std::ffi::OsString)],
) -> Result<Vec<(std::ffi::OsString, std::ffi::OsString)>, String> {
    // Match the native interpreter's current_exe path representation even when
    // callers supply a Windows executable using forward slashes.
    let executable = normalize_absolute_path(executable).map_err(|error| error.to_string())?;
    let defined = define_for(&executable, ambient)?;
    for directory in &defined.directories {
        create_private_directory(directory).map_err(|e| e.to_string())?;
    }
    Ok(defined.environment)
}

#[unsafe(no_mangle)]
pub extern "C" fn cadrumo_platform_abi() -> u32 {
    ABI
}
/// # Safety
/// Non-null outputs must be aligned, writable and non-overlapping. Release a
/// returned error buffer and destroy a returned context using this library.
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
/// # Safety
/// A non-null context must be live and created by this library. A non-null output
/// must be aligned and writable without aliasing the context. Release returned
/// buffers using this library before reusing their output storage.
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
/// # Safety
/// A non-null context must be live and created by this library. A non-null error
/// output must be aligned, writable and not alias the context. The caller must
/// exclude concurrent environment access while this operation changes it.
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
/// The native character of this platform's process arguments.
#[cfg(windows)]
pub type NativeChar = u16;
#[cfg(unix)]
pub type NativeChar = std::ffi::c_char;

/// # Safety
/// `argument` must be a non-null, terminated native string.
unsafe fn native_argument(argument: *const NativeChar) -> std::ffi::OsString {
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStringExt;
        let length = (0..)
            .take_while(|&index| unsafe { *argument.add(index) } != 0)
            .count();
        std::ffi::OsString::from_wide(unsafe { std::slice::from_raw_parts(argument, length) })
    }
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStringExt;
        std::ffi::OsString::from_vec(
            unsafe { std::ffi::CStr::from_ptr(argument) }
                .to_bytes()
                .to_vec(),
        )
    }
}

/// Select the launch profile for `image` and this invocation, then define the process
/// environment from it.
///
/// Returns 0 on success, 2 on an invalid argument, 3 on a platform failure with an
/// error message, and 4 on a launch-profile refusal, when `error` holds the one
/// refusal line the host writes before exiting. A refusal changes nothing.
///
/// # Safety
/// A non-null context must be live and created by this library. `image` must be a
/// terminated UTF-8 string. `argv` must hold `argc` terminated native strings: the
/// arguments after the image's own path. The error output must be aligned and
/// writable. The caller must exclude concurrent environment access while this
/// operation changes it.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_define(
    ctx: *mut Context,
    image: *const std::ffi::c_char,
    argc: u32,
    argv: *const *const NativeChar,
    error: *mut Buffer,
) -> u32 {
    if ctx.is_null() || image.is_null() || error.is_null() || (argc > 0 && argv.is_null()) {
        return 2;
    }
    unsafe {
        *error = Buffer {
            data: ptr::null_mut(),
            len: 0,
        };
    }
    let Ok(image) = unsafe { std::ffi::CStr::from_ptr(image) }.to_str() else {
        return 2;
    };
    let mut arguments = Vec::with_capacity(argc as usize);
    for index in 0..argc as usize {
        let argument = unsafe { *argv.add(index) };
        if argument.is_null() {
            return 2;
        }
        arguments.push(unsafe { native_argument(argument) });
    }
    let package = unsafe { &*ctx }.paths[0].clone();
    let outcome = launch::select(image, &arguments).and_then(|profile| {
        let exe = env::current_exe().map_err(|e| launch::DefineError::Failed(e.to_string()))?;
        let evidence = storage::detect_mode(&exe).map_err(launch::DefineError::Failed)?;
        let ambient: Vec<_> = env::vars_os().collect();
        let defined = launch::define_environment(profile, &ambient, &package, &|lookup| {
            storage::resolve_storage_root_with(&evidence, lookup).map(|resolved| resolved.root)
        })?;
        // Environment mutation occurs once, before Python or application threads exist.
        unsafe { launch::apply(&defined) }
    });
    match outcome {
        Ok(()) => 0,
        Err(launch::DefineError::Refused(refusal)) => {
            unsafe {
                *error = buffer(refusal.line());
            }
            4
        }
        Err(launch::DefineError::Failed(message)) => {
            unsafe {
                *error = buffer(message);
            }
            3
        }
    }
}

/// # Safety
/// A non-null pointer must exclusively reference an aligned, writable buffer
/// returned by this library (or an empty buffer). Its data and length must be
/// unchanged, and its allocation must not already have been released.
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
/// # Safety
/// A non-null pointer must be an exclusively owned live context returned by this
/// library. No further access or destruction is permitted after this call.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_destroy(ctx: *mut Context) {
    if !ctx.is_null() {
        unsafe {
            drop(Box::from_raw(ctx));
        }
    }
}
