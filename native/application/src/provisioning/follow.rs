//! What a setup that follows another engine's setup waits on.
//!
//! A follower reads the item's activity record again whenever something may have changed,
//! and learns that the writer is gone, finished or dead, when it can take the item's lock
//! shared. Three things end its wait: a change in the activity folder, the lock's release,
//! and the follower's own cancellation. Nothing is looked at on a timer where the
//! platform reports changes: with the platform layer, the folder's change notification
//! wakes the wait on Windows; elsewhere, and in a build without the platform layer, the
//! wait ends within [`OBSERVATION`] so the record is observed on that interval, as the
//! platform layer itself does for a folder it cannot watch. The release is a blocking
//! shared lock taken on a thread of its own, which wakes the wait when the kernel grants
//! it; a follower that stops first leaves that thread waiting until the writer lets go.

use super::activity;
use crate::component::CancelWake;
use std::{path::PathBuf, time::Duration};

/// The longest wait where no change notification is available.
pub const OBSERVATION: Duration = Duration::from_millis(100);

/// The changes of one folder a follower waits on.
pub struct Changes {
    inner: imp::Changes,
}

impl Changes {
    pub fn new(folder: PathBuf) -> Self {
        Self {
            inner: imp::Changes::new(folder),
        }
    }

    /// Ends the current or next wait from any thread.
    pub fn waker(&self) -> CancelWake {
        self.inner.waker()
    }

    /// Waits until something in the folder may have changed or the waker is called, and
    /// at most `bound` when one is given.
    pub fn wait(&mut self, bound: Option<Duration>) {
        self.inner.wait(bound);
    }
}

/// Calls `wake` once no writer holds the lock at `lock`. `false` when no thread could be
/// started for the wait, so the caller must bound its own waits instead.
pub fn wake_on_release(lock: PathBuf, wake: CancelWake) -> bool {
    std::thread::Builder::new()
        .name("cadrumo-components-follow".into())
        .spawn(move || {
            activity::wait_released(&lock);
            wake();
        })
        .is_ok()
}

#[cfg(feature = "platform")]
mod imp {
    use super::CancelWake;
    use cadrumo_platform::file_changes::FileChanges;
    use std::{path::PathBuf, sync::Arc, time::Duration};

    pub struct Changes(FileChanges);

    impl Changes {
        pub fn new(folder: PathBuf) -> Self {
            Self(FileChanges::new(vec![folder]))
        }

        pub fn waker(&self) -> CancelWake {
            let waker = self.0.waker();
            Arc::new(move || waker.wake())
        }

        pub fn wait(&mut self, bound: Option<Duration>) {
            self.0.wait(bound);
        }
    }
}

#[cfg(not(feature = "platform"))]
mod imp {
    use super::{CancelWake, OBSERVATION};
    use std::{
        path::PathBuf,
        sync::{Arc, Condvar, Mutex},
        time::Duration,
    };

    type Signal = Arc<(Mutex<bool>, Condvar)>;

    pub struct Changes(Signal);

    impl Changes {
        pub fn new(_folder: PathBuf) -> Self {
            Self(Arc::new((Mutex::new(false), Condvar::new())))
        }

        pub fn waker(&self) -> CancelWake {
            let signal = self.0.clone();
            Arc::new(move || {
                let (woken, wake) = &*signal;
                *woken
                    .lock()
                    .unwrap_or_else(|poisoned| poisoned.into_inner()) = true;
                wake.notify_all();
            })
        }

        pub fn wait(&mut self, bound: Option<Duration>) {
            let limit = bound.map_or(OBSERVATION, |bound| bound.min(OBSERVATION));
            let (woken, wake) = &*self.0;
            let guard = woken
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            let (mut guard, _) = wake
                .wait_timeout_while(guard, limit, |woken| !*woken)
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            *guard = false;
        }
    }
}
