//! Remembers each window's size, position and maximized state between
//! launches, in the declared webview location.
//!
//! The record is host-only: no webview command reads or writes it. A missing
//! or unreadable record means the configured defaults, never a failure, and a
//! saved position is placed back onto a current monitor.
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    fs,
    io::Write,
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
};
use tauri::{PhysicalPosition, PhysicalSize, Runtime, Window, WindowEvent};

/// The record's file name inside the webview location.
pub const FILE: &str = "window-state.json";

/// One window's restorable geometry in physical pixels: the outer position
/// and inner size of its normal (not maximized) placement.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Placement {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
    pub maximized: bool,
}

/// A display area in physical pixels.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Area {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}

impl Area {
    fn overlap(&self, placement: &Placement) -> u64 {
        let span = |start: i32, length: u32, other: i32, other_length: u32| {
            let end = (i64::from(start) + i64::from(length))
                .min(i64::from(other) + i64::from(other_length));
            u64::try_from(end - i64::from(start.max(other))).unwrap_or(0)
        };
        span(self.x, self.width, placement.x, placement.width)
            * span(self.y, self.height, placement.y, placement.height)
    }
}

/// Reads the saved placements. A missing, unreadable or malformed record, and
/// any placement with an empty size, yield nothing for that window.
pub fn load(path: &Path) -> BTreeMap<String, Placement> {
    let Ok(bytes) = fs::read(path) else {
        return BTreeMap::new();
    };
    serde_json::from_slice::<BTreeMap<String, Placement>>(&bytes)
        .map(|placements| {
            placements
                .into_iter()
                .filter(|(_, p)| p.width > 0 && p.height > 0)
                .collect()
        })
        .unwrap_or_default()
}

/// Replaces the record atomically: the new content is written and flushed to
/// a temporary file in the same directory, then renamed over the record.
pub fn save(path: &Path, placements: &BTreeMap<String, Placement>) -> Result<()> {
    let failed = || ApplicationError::new(ErrorCode::WriteFailed, Operation::Webview);
    let directory = path.parent().ok_or_else(failed)?;
    let name = path.file_name().ok_or_else(failed)?;
    let mut temporary = name.to_owned();
    temporary.push(format!(".{}.tmp", std::process::id()));
    let temporary = directory.join(temporary);
    let bytes = serde_json::to_vec_pretty(placements).map_err(|e| failed().caused_by(e))?;
    let written = fs::create_dir_all(directory)
        .and_then(|()| {
            let mut file = fs::File::create(&temporary)?;
            file.write_all(&bytes)?;
            file.sync_all()
        })
        .and_then(|()| fs::rename(&temporary, path));
    if let Err(error) = written {
        let _ = fs::remove_file(&temporary);
        return Err(failed().caused_by(error));
    }
    Ok(())
}

/// Places a saved window onto the display it overlaps most, or onto the
/// first display when it overlaps none: the size shrinks to fit the display
/// and the position moves so the whole window lies on it.
pub fn fit(placement: Placement, displays: &[Area]) -> Option<Placement> {
    let display = displays
        .iter()
        .filter(|area| area.width > 0 && area.height > 0)
        .max_by_key(|area| area.overlap(&placement))?;
    let width = placement.width.min(display.width);
    let height = placement.height.min(display.height);
    let clamp = |start: i32, length: u32, area_start: i32, area_length: u32| {
        let last = i64::from(area_start) + i64::from(area_length) - i64::from(length);
        let value = i64::from(start).clamp(i64::from(area_start), last);
        i32::try_from(value).unwrap_or(area_start)
    };
    Some(Placement {
        x: clamp(placement.x, width, display.x, display.width),
        y: clamp(placement.y, height, display.y, display.height),
        width,
        height,
        maximized: placement.maximized,
    })
}

fn displays<R: Runtime>(window: &Window<R>) -> Vec<Area> {
    window
        .available_monitors()
        .unwrap_or_default()
        .iter()
        .map(|monitor| {
            let area = monitor.work_area();
            Area {
                x: area.position.x,
                y: area.position.y,
                width: area.size.width,
                height: area.size.height,
            }
        })
        .collect()
}

/// The saved placements and the record they persist to.
pub struct WindowStates {
    path: PathBuf,
    placements: Mutex<BTreeMap<String, Placement>>,
    diagnostics: Arc<Diagnostics>,
}

impl WindowStates {
    pub fn open(webview_location: &Path, diagnostics: Arc<Diagnostics>) -> Self {
        let path = webview_location.join(FILE);
        Self {
            placements: Mutex::new(load(&path)),
            path,
            diagnostics,
        }
    }

    fn lock(&self) -> std::sync::MutexGuard<'_, BTreeMap<String, Placement>> {
        self.placements.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Restores `window` from its saved placement, then follows its moves and
    /// resizes and saves the record when it is asked to close.
    pub fn attach<R: Runtime>(self: &Arc<Self>, window: &Window<R>) {
        let label = window.label().to_owned();
        let saved = self.lock().get(&label).copied();
        if let Some(placement) = saved.and_then(|p| fit(p, &displays(window))) {
            let restored = window
                .set_size(PhysicalSize::new(placement.width, placement.height))
                .and_then(|()| window.set_position(PhysicalPosition::new(placement.x, placement.y)))
                .and_then(|()| {
                    if placement.maximized {
                        window.maximize()
                    } else {
                        Ok(())
                    }
                });
            if let Err(error) = restored {
                self.diagnostics.failure(
                    ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview)
                        .caused_by(error),
                );
            }
        }
        let states = self.clone();
        let tracked = window.clone();
        window.on_window_event(move |event| match event {
            WindowEvent::Moved(_) | WindowEvent::Resized(_) => states.track(&tracked),
            WindowEvent::CloseRequested { .. } => states.close(&tracked),
            _ => {}
        });
    }

    /// Records the normal placement; a maximized or minimized window keeps
    /// the placement it had before.
    fn track<R: Runtime>(&self, window: &Window<R>) {
        if window.is_maximized().unwrap_or(true) || window.is_minimized().unwrap_or(true) {
            return;
        }
        let (Ok(position), Ok(size)) = (window.outer_position(), window.inner_size()) else {
            return;
        };
        let mut placements = self.lock();
        let maximized = placements.get(window.label()).is_some_and(|p| p.maximized);
        placements.insert(
            window.label().to_owned(),
            Placement {
                x: position.x,
                y: position.y,
                width: size.width,
                height: size.height,
                maximized,
            },
        );
    }

    fn close<R: Runtime>(&self, window: &Window<R>) {
        self.track(window);
        let maximized = window.is_maximized().unwrap_or(false);
        let snapshot = {
            let mut placements = self.lock();
            match placements.get_mut(window.label()) {
                Some(placement) => placement.maximized = maximized,
                // Never moved or resized while normal: save where it is now.
                None => {
                    let (Ok(position), Ok(size)) = (window.outer_position(), window.inner_size())
                    else {
                        return;
                    };
                    placements.insert(
                        window.label().to_owned(),
                        Placement {
                            x: position.x,
                            y: position.y,
                            width: size.width,
                            height: size.height,
                            maximized,
                        },
                    );
                }
            }
            placements.clone()
        };
        if let Err(error) = save(&self.path, &snapshot) {
            self.diagnostics.failure(error);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Scratch(PathBuf);
    impl Scratch {
        fn new(label: &str) -> Self {
            let path = std::env::temp_dir().join(format!(
                "cadrumo-window-state-{label}-{}-{}",
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
            Self(path)
        }
    }
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn placement(x: i32, y: i32, width: u32, height: u32) -> Placement {
        Placement {
            x,
            y,
            width,
            height,
            maximized: false,
        }
    }

    const PRIMARY: Area = Area {
        x: 0,
        y: 0,
        width: 1920,
        height: 1040,
    };
    const LEFT: Area = Area {
        x: -1280,
        y: 0,
        width: 1280,
        height: 984,
    };

    #[test]
    fn placements_round_trip_through_the_record_and_replace_it_atomically() {
        let scratch = Scratch::new("round-trip");
        // The webview location may not exist yet on a first launch.
        let path = scratch.0.join("webview").join(FILE);
        assert!(load(&path).is_empty());
        let mut first = BTreeMap::new();
        first.insert("main".to_owned(), placement(-1200, 40, 1440, 900));
        save(&path, &first).unwrap();
        assert_eq!(load(&path), first);
        let mut second = first.clone();
        second.insert(
            "main".to_owned(),
            Placement {
                maximized: true,
                ..placement(100, 80, 800, 600)
            },
        );
        save(&path, &second).unwrap();
        assert_eq!(load(&path), second);
        let left: Vec<_> = fs::read_dir(path.parent().unwrap())
            .unwrap()
            .map(|entry| entry.unwrap().file_name())
            .collect();
        assert_eq!(left, [FILE], "no temporary file is left behind");
    }

    #[test]
    fn a_corrupt_or_foreign_record_means_defaults() {
        let scratch = Scratch::new("corrupt");
        fs::create_dir_all(&scratch.0).unwrap();
        let path = scratch.0.join(FILE);
        for content in [
            &b"{\"main\": {\"x\": 1, \"y\""[..],
            b"\xff\xfe not json",
            b"[]",
            b"{\"main\": {\"x\": 1, \"y\": 2, \"width\": -5, \"height\": 4, \"maximized\": false}}",
            b"{\"main\": {\"x\": 1, \"y\": 2, \"width\": 5, \"height\": 4, \"maximized\": false, \"extra\": 1}}",
            b"",
        ] {
            fs::write(&path, content).unwrap();
            assert!(load(&path).is_empty(), "{:?}", String::from_utf8_lossy(content));
        }
        fs::write(
            &path,
            b"{\"main\": {\"x\": 1, \"y\": 2, \"width\": 0, \"height\": 4, \"maximized\": false},\
              \"other\": {\"x\": 1, \"y\": 2, \"width\": 5, \"height\": 4, \"maximized\": true}}",
        )
        .unwrap();
        assert_eq!(
            load(&path).into_keys().collect::<Vec<_>>(),
            ["other"],
            "an empty size drops only that window"
        );
    }

    #[test]
    fn a_window_on_a_current_display_keeps_its_placement() {
        let saved = placement(-1200, 40, 1000, 700);
        assert_eq!(fit(saved, &[PRIMARY, LEFT]), Some(saved));
        let saved = placement(200, 100, 1440, 900);
        assert_eq!(fit(saved, &[PRIMARY, LEFT]), Some(saved));
    }

    #[test]
    fn an_off_screen_window_is_brought_onto_a_display() {
        // Saved on a display that is gone: placed wholly on the first one.
        let fitted = fit(placement(-1200, 40, 1000, 700), &[PRIMARY]).unwrap();
        assert_eq!(fitted, placement(0, 40, 1000, 700));
        // Far away in every direction.
        for (x, y) in [(50_000, 50_000), (-50_000, -50_000), (i32::MAX, i32::MIN)] {
            let fitted = fit(placement(x, y, 800, 600), &[PRIMARY]).unwrap();
            assert!(PRIMARY.overlap(&fitted) == 800 * 600, "{fitted:?}");
        }
        // Partly off the edge: pulled in so the whole window shows.
        assert_eq!(
            fit(placement(1800, 900, 800, 600), &[PRIMARY]),
            Some(placement(1120, 440, 800, 600))
        );
        // Larger than the display: shrunk to it.
        let fitted = fit(
            Placement {
                maximized: true,
                ..placement(-10, -10, 4000, 3000)
            },
            &[LEFT],
        )
        .unwrap();
        assert_eq!(
            fitted,
            Placement {
                maximized: true,
                ..placement(-1280, 0, 1280, 984)
            }
        );
        // No display known: nothing to restore onto.
        assert_eq!(fit(placement(0, 0, 800, 600), &[]), None);
    }
}
