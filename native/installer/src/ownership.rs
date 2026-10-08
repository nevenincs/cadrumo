//! Sticky observation of Windows Installer's change-of-owner event.
#![allow(unsafe_code)]
use crate::admission::Refusal;
use std::{
    os::windows::io::{AsRawHandle, OwnedHandle},
    sync::{Arc, Mutex},
};
use windows_sys::Win32::{Foundation::WAIT_TIMEOUT, System::Threading::WaitForSingleObject};

#[derive(Clone)]
pub struct Ownership(Arc<Mutex<State>>);
struct State {
    event: OwnedHandle,
    lost: bool,
}
impl Ownership {
    pub(crate) fn new(event: OwnedHandle) -> Self {
        Self(Arc::new(Mutex::new(State { event, lost: false })))
    }
    /// A signal, wait failure, or poisoned observer permanently revokes authority.
    /// Serialize polling so an auto-reset event cannot be consumed independently
    /// by the broker and transaction threads with different conclusions.
    pub fn current(&self) -> Result<(), Refusal> {
        let mut state = self.0.lock().map_err(|_| Refusal::NativeFailure)?;
        // SAFETY: State owns the event throughout this nonblocking wait.
        if !state.lost
            && unsafe { WaitForSingleObject(state.event.as_raw_handle(), 0) } != WAIT_TIMEOUT
        {
            state.lost = true;
        }
        if state.lost {
            Err(Refusal::NativeFailure)
        } else {
            Ok(())
        }
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use std::{os::windows::io::FromRawHandle, ptr};
    use windows_sys::Win32::System::Threading::{CreateEventW, SetEvent};

    pub(crate) fn unsignaled() -> Ownership {
        // SAFETY: An unnamed auto-reset event, initially unsignaled, with no inheritance.
        let event = unsafe { CreateEventW(ptr::null(), 0, 0, ptr::null()) };
        assert!(!event.is_null());
        // SAFETY: The successful creation transferred ownership to this test.
        Ownership::new(unsafe { OwnedHandle::from_raw_handle(event) })
    }
    #[test]
    fn owner_loss_is_sticky_across_observers_after_auto_reset() {
        let owner = unsignaled();
        let broker = owner.clone();
        assert!(owner.current().is_ok());
        {
            let state = owner.0.lock().unwrap();
            // SAFETY: Event remains owned by the locked state.
            assert_ne!(unsafe { SetEvent(state.event.as_raw_handle()) }, 0);
        }
        assert!(broker.current().is_err());
        assert!(owner.current().is_err());
        assert!(broker.current().is_err());
    }
}
