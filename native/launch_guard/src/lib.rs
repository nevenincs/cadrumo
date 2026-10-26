//! Small C boundary over the application's single native-publication owner.
use cadrumo_application::installation::{DiscoveryContract, maintenance::Lease};
use std::{
    panic::{AssertUnwindSafe, catch_unwind},
    path::Path,
    sync::Arc,
};

/// Opaque process-lifetime publication lease. C callers never dereference this.
pub struct LaunchGuard {
    _lease: Arc<Lease>,
}

/// Acquire exact-own-package removal exclusion before loading package code.
///
/// # Safety
/// `out` must point to writable aligned pointer storage. `package` must identify
/// `length` readable bytes for this call. Neither region may overlap. The caller
/// retains the resulting handle until all package use ends, then releases once.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_launch_guard_acquire(
    package: *const u8,
    length: usize,
    out: *mut *mut LaunchGuard,
) -> u32 {
    if out.is_null() {
        return 1;
    }
    // SAFETY: the C boundary requires writable aligned out storage.
    unsafe {
        *out = std::ptr::null_mut();
    }
    if package.is_null() || length == 0 || length > 131_072 {
        return 1;
    }
    let admitted = catch_unwind(|| -> Result<Option<Arc<Lease>>, ()> {
        // SAFETY: caller supplies length readable bytes for the duration of this call.
        let bytes = unsafe { std::slice::from_raw_parts(package, length) };
        let path = std::str::from_utf8(bytes).map_err(|_| ())?;
        if path.contains('\0') {
            return Err(());
        }
        let contract: DiscoveryContract =
            serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
                .map_err(|_| ())?;
        contract.acquire_package(Path::new(path)).map_err(|_| ())
    });
    match admitted {
        Ok(Ok(lease)) => {
            if let Some(lease) = lease {
                // SAFETY: same caller-owned output storage; the box transfers to C.
                unsafe {
                    *out = Box::into_raw(Box::new(LaunchGuard { _lease: lease }));
                }
            }
            0
        }
        Ok(Err(())) => 2,
        Err(_) => 3,
    }
}

/// Release one completed process's lease; null is a no-op.
///
/// # Safety
/// A non-null pointer must be returned by acquire and not previously released.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_launch_guard_release(guard: *mut LaunchGuard) {
    if guard.is_null() {
        return;
    }
    let _ = catch_unwind(AssertUnwindSafe(|| {
        // SAFETY: caller transfers the unique live allocation back exactly once.
        drop(unsafe { Box::from_raw(guard) });
    }));
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn invalid_inputs_refuse_and_clear_output() {
        let mut output = std::ptr::dangling_mut::<LaunchGuard>();
        // SAFETY: valid output storage; null input is refused before dereference.
        assert_ne!(
            unsafe { cadrumo_launch_guard_acquire(std::ptr::null(), 1, &mut output) },
            0
        );
        assert!(output.is_null());
        let bytes = [0xff];
        // SAFETY: input bytes and output storage are valid for the call.
        assert_ne!(
            unsafe { cadrumo_launch_guard_acquire(bytes.as_ptr(), bytes.len(), &mut output) },
            0
        );
        assert!(output.is_null());
        // SAFETY: null release is explicitly permitted.
        unsafe {
            cadrumo_launch_guard_release(output);
        }
    }

    #[test]
    fn standalone_package_returns_explicit_null_guard_and_relative_path_refuses() {
        let package = env!("CARGO_MANIFEST_DIR").as_bytes();
        let mut output = std::ptr::null_mut();
        // SAFETY: compile-time path bytes and aligned output storage are live.
        assert_eq!(
            unsafe { cadrumo_launch_guard_acquire(package.as_ptr(), package.len(), &mut output) },
            0
        );
        assert!(output.is_null());
        let relative = b"relative-package";
        // SAFETY: valid borrowed input and output storage for this call.
        assert_ne!(
            unsafe { cadrumo_launch_guard_acquire(relative.as_ptr(), relative.len(), &mut output) },
            0
        );
        assert!(output.is_null());
    }
}
