//! The application's Dock icon on macOS.
//!
//! AppKit takes an application's icon from its main bundle. The installed desktop runs
//! as an image its bundle's launcher replaced itself with, outside the bundle's
//! executable directory, so AppKit finds no icon for it; nor does a desktop run on its
//! own. The desktop therefore sets the icon it was built with.

use objc2::AllocAnyThread;
use objc2_app_kit::{NSApplication, NSImage};
use objc2_foundation::{MainThreadMarker, NSData};

/// Sets the running application's icon from encoded image bytes (an ICNS or PNG file's
/// contents). Returns whether AppKit took it: off the main thread, or for bytes AppKit
/// cannot decode, the icon is left as it was.
pub fn set(image: &[u8]) -> bool {
    let Some(thread) = MainThreadMarker::new() else {
        return false;
    };
    let data = NSData::with_bytes(image);
    let Some(icon) = NSImage::initWithData(NSImage::alloc(), &data) else {
        return false;
    };
    let application = NSApplication::sharedApplication(thread);
    // SAFETY: the marker proves this is the main thread, where AppKit requires the
    // application object to be used, and the image is a valid, retained NSImage that
    // AppKit retains in turn.
    unsafe { application.setApplicationIconImage(Some(&icon)) };
    true
}
