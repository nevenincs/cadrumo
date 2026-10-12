//! Bounded parallel descriptor/type/digest checks after namespace discovery.

use super::{Admission, Readiness, open_regular};
use crate::{
    component::Cancellation,
    error::Error,
    filesystem,
    value::{RelativePath, Sha256Digest},
};
use std::{
    io,
    path::PathBuf,
    sync::{Mutex, mpsc},
    thread,
};

const WORKERS: usize = 4;
const BATCH: usize = 32;

struct Task {
    index: usize,
    path: PathBuf,
    member: RelativePath,
    expected: Sha256Digest,
}

type Observation = Result<Option<Readiness>, Error>;

fn verify(task: &Task, cancellation: &Cancellation) -> Observation {
    cancellation.check()?;
    // Discovery may have queued this leaf behind other work. Re-observe its
    // own entry immediately before opening; never reuse stale link admission.
    let metadata = match std::fs::symlink_metadata(&task.path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => {
            return Ok(Some(Readiness::Missing(task.member.as_str().into())));
        }
        Err(error) => return Err(error.into()),
    };
    filesystem::refuse_metadata_links(&metadata)?;
    if !metadata.is_file() {
        return Ok(Some(Readiness::Incompatible(task.member.as_str().into())));
    }
    filesystem::refuse_links(&task.path)?;
    cancellation.check()?;
    let mut file = match open_regular(&task.path, &task.member)? {
        Admission::Admitted(file) => file,
        Admission::Refused(readiness) => return Ok(Some(readiness)),
    };
    if filesystem::digest_reader(&mut file, cancellation)? != task.expected {
        return Ok(Some(Readiness::Incompatible(task.member.as_str().into())));
    }
    Ok(None)
}

pub(super) struct Verifier {
    tasks: mpsc::SyncSender<Task>,
    results: mpsc::Receiver<(usize, Observation)>,
    pending: usize,
}

impl Verifier {
    pub(super) fn submit(
        &mut self,
        path: PathBuf,
        member: RelativePath,
        expected: Sha256Digest,
    ) -> Observation {
        self.tasks
            .send(Task {
                index: self.pending,
                path,
                member,
                expected,
            })
            .map_err(|_| Error::Io(io::ErrorKind::BrokenPipe.into()))?;
        self.pending += 1;
        if self.pending == BATCH {
            self.flush()
        } else {
            Ok(None)
        }
    }

    pub(super) fn flush(&mut self) -> Observation {
        let count = std::mem::take(&mut self.pending);
        let mut observations = Vec::with_capacity(count);
        for _ in 0..count {
            observations.push(
                self.results
                    .recv()
                    .map_err(|_| Error::Io(io::ErrorKind::BrokenPipe.into()))?,
            );
        }
        observations.sort_unstable_by_key(|(index, _)| *index);
        for (_, observation) in observations {
            if let Some(readiness) = observation? {
                return Ok(Some(readiness));
            }
        }
        Ok(None)
    }
}

pub(super) fn with_verifier<T>(
    cancellation: &Cancellation,
    inspect: impl FnOnce(&mut Verifier) -> Result<T, Error>,
) -> Result<T, Error> {
    with_verifier_using(cancellation, inspect, verify)
}

fn with_verifier_using<T>(
    cancellation: &Cancellation,
    inspect: impl FnOnce(&mut Verifier) -> Result<T, Error>,
    verify_task: impl Fn(&Task, &Cancellation) -> Observation + Sync,
) -> Result<T, Error> {
    let (tasks, queue) = mpsc::sync_channel::<Task>(BATCH);
    let queue = Mutex::new(queue);
    let (results, observations) = mpsc::sync_channel(BATCH);
    thread::scope(|scope| {
        let mut workers = Vec::with_capacity(WORKERS);
        for _ in 0..WORKERS {
            let queue = &queue;
            let observations = results.clone();
            let verify_task = &verify_task;
            let worker = thread::Builder::new()
                .name("package-verifier".into())
                .spawn_scoped(scope, move || {
                    loop {
                        let task = match queue.lock() {
                            Ok(queue) => queue.recv(),
                            Err(_) => return,
                        };
                        let Ok(task) = task else {
                            return;
                        };
                        // Dropping a receiver on an early namespace refusal must not
                        // leave a worker blocked while sending its observation.
                        let observation =
                            std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                                verify_task(&task, cancellation)
                            }))
                            .unwrap_or_else(|_| {
                                Err(Error::Io(io::Error::other(
                                    "package verifier worker failed",
                                )))
                            });
                        if observations.send((task.index, observation)).is_err() {
                            return;
                        }
                    }
                });
            match worker {
                Ok(worker) => workers.push(worker),
                Err(error) => {
                    drop(tasks);
                    drop(results);
                    for worker in workers {
                        let _ = worker.join();
                    }
                    return Err(error.into());
                }
            }
        }
        drop(results);
        let mut verifier = Verifier {
            tasks,
            results: observations,
            pending: 0,
        };
        let result = inspect(&mut verifier);
        // Both bounded endpoints are closed before joining, including when the
        // namespace traversal failed before draining its last partial batch.
        drop(verifier);
        let mut failed = false;
        for worker in workers {
            failed |= worker.join().is_err();
        }
        if failed && result.is_ok() {
            return Err(Error::Io(io::Error::other(
                "package verifier worker failed",
            )));
        }
        result
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cancelled_partial_batch_joins_before_releasing_file_custody() {
        let directory = tempfile::tempdir().unwrap();
        let file = directory.path().join("member.bin");
        std::fs::write(&file, vec![0_u8; 70_123]).unwrap();
        let cancellation = Cancellation::default();
        let outcome: Result<(), Error> = with_verifier(&cancellation, |verifier| {
            verifier.submit(
                file.clone(),
                RelativePath::new("member.bin").unwrap(),
                Sha256Digest::new("a".repeat(64)).unwrap(),
            )?;
            cancellation.cancel();
            cancellation.check()
        });
        assert!(matches!(outcome, Err(Error::Cancelled)));
        // Preserve immediate relocation functionality after a cancelled batch.
        // Worker settlement is the scoped join, not Windows delete sharing.
        std::fs::rename(file, directory.path().join("settled.bin")).unwrap();
    }

    #[test]
    fn panicking_popped_task_still_returns_an_indexed_failure_and_joins() {
        use std::sync::atomic::{AtomicUsize, Ordering};
        let observed = AtomicUsize::new(0);
        let outcome = with_verifier_using(
            &Cancellation::default(),
            |verifier| {
                for _ in 0..BATCH {
                    verifier.submit(
                        PathBuf::from("unused-test-member"),
                        RelativePath::new("member.bin").unwrap(),
                        Sha256Digest::new("a".repeat(64)).unwrap(),
                    )?;
                }
                Ok(())
            },
            |task, _| {
                observed.fetch_add(1, Ordering::Relaxed);
                if task.index == 0 {
                    panic!("synthetic private panic payload");
                }
                Ok(None)
            },
        );
        assert_eq!(observed.load(Ordering::Relaxed), BATCH);
        assert!(matches!(outcome, Err(Error::Io(error))
            if error.to_string() == "package verifier worker failed"));
    }
}
