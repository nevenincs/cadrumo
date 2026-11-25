//! Seats the system's window controls in the page's header row, as a macOS
//! window with a toolbar in its title bar seats them: centred on the row, as
//! far from the leading edge as from the top, with the header's first item the
//! same distance again after the last control.

use super::window_controls::NativeControls;
use tauri::LogicalPosition;

/// The header row's height: AppKit's compact unified toolbar.
pub const ROW_HEIGHT: f64 = 38.0;

/// AppKit's standard window controls, as macOS 26 lays them out in a titled,
/// full-size-content window.
struct Standard {
    /// Each control's square side.
    side: f64,
    /// Distance between the leading edges of neighbouring controls.
    pitch: f64,
    /// The control's offset from the bottom of its title bar container. Tauri
    /// grows the container to the control's side plus the inset it is given
    /// and the control keeps this offset, so its top lands at the inset less
    /// this offset.
    bottom: f64,
}

const STANDARD: Standard = Standard {
    side: 14.0,
    pitch: 23.0,
    bottom: 9.0,
};

/// Where the controls go and what the page reserves for them.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Placement {
    /// The inset Tauri applies to the controls when it builds the window.
    pub position: LogicalPosition<f64>,
    pub controls: NativeControls,
}

pub const fn placement() -> Placement {
    let margin = (ROW_HEIGHT - STANDARD.side) / 2.0;
    let last = margin + 2.0 * STANDARD.pitch + STANDARD.side;
    Placement {
        position: LogicalPosition {
            x: margin,
            y: margin + STANDARD.bottom,
        },
        controls: NativeControls {
            height: ROW_HEIGHT,
            inset: last + margin,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn controls_centre_on_the_row_and_the_header_clears_them_by_the_same_margin() {
        let placed = placement();
        // 12 above and 12 below a 14-point control on a 38-point row; the
        // control's top is the inset less its 9-point offset in the container.
        assert_eq!(placed.position, LogicalPosition::new(12.0, 21.0));
        // Close starts at 12, zoom ends at 12 + 46 + 14, then 12 more.
        assert_eq!(
            placed.controls,
            NativeControls {
                height: 38.0,
                inset: 84.0,
            }
        );
    }
}
