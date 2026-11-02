use super::super::blocking;
use super::super::channel::RawFetch;
use super::super::relay::Result;
use super::super::user_profile::ProfileHost;
use super::protocol::{ChooserAnswered, DownloadAnswered, Opened, Sink, Size};
use super::runtime::start;
use super::transfer::NativeDialogs;
use super::{SedeViewHost, failure};
use cadrumo_application::view_stream::documents::{
    ViewClipboardAction, ViewInputEvent, ViewNavigateVerb,
};
use std::sync::Arc;
use tauri::Manager;
use tauri::ipc::{Channel, InvokeResponseBody};
use tauri::{AppHandle, State, Webview};

/// A view's messages on the window's channel. The images reach the page as
/// binary, which the page takes by name. It ends when the channel refuses a
/// message or the shell reports that one could not be delivered to the page.
pub(super) fn channel_sink<R: tauri::Runtime>(
    webview: Webview<R>,
    messages: Channel<InvokeResponseBody>,
) -> Sink {
    let fetch = RawFetch::new(webview, messages.id());
    Arc::new(move |body| messages.send(body).is_ok() && !fetch.failed())
}

/// Opens the Sede view for the signed-in profile at the panel's size and
/// relays it on `messages` until it ends. The answer comes before the browser
/// is open; `opened` follows on the channel.
///
/// Refuses `conflict` while the previous view has not ended, which includes the
/// time it takes to publish its session.
#[tauri::command]
pub(super) async fn sede_view_open<R: tauri::Runtime>(
    host: State<'_, Arc<SedeViewHost>>,
    profile: State<'_, Arc<ProfileHost>>,
    webview: Webview<R>,
    css_width: u32,
    css_height: u32,
    scale: f64,
    messages: Channel<InvokeResponseBody>,
) -> Result<Opened> {
    let size = Size::admit(css_width, css_height, scale)?;
    host.admit_open()?;
    let setup = webview
        .try_state::<Arc<super::super::setup::SetupHost>>()
        .ok_or_else(|| failure("unavailable"))?
        .inner()
        .clone();
    match setup.check_browser().await {
        Some(true) => {}
        Some(false) => {
            let view = host.component_not_ready(channel_sink(webview, messages))?;
            return Ok(Opened { view });
        }
        None => return Err(failure("unavailable")),
    }
    let started = start(&profile, &size)
        .await
        .inspect_err(|failure| host.submission_refused(failure))?;
    let sink = channel_sink(webview, messages);
    let owner = host.inner().clone();
    let view = blocking(move || Ok(owner.open_with(started, sink))).await??;
    Ok(Opened { view })
}

/// The person closed the page: the view publishes its session and settles.
/// `closing` and then `ended` follow on the channel.
#[tauri::command]
pub(super) async fn sede_view_close(host: State<'_, Arc<SedeViewHost>>, view: u32) -> Result<()> {
    let owner = host.inner().clone();
    blocking(move || Ok(owner.close_view(view))).await?
}

/// Forwards one input event: a pointer, wheel, key or text event of the person.
#[tauri::command]
pub(super) fn sede_view_input(
    host: State<'_, Arc<SedeViewHost>>,
    view: u32,
    event: ViewInputEvent,
) -> Result<()> {
    host.input(view, event)
}

/// Back, forward, reload or home. The window never names an address.
#[tauri::command]
pub(super) fn sede_view_navigate(
    host: State<'_, Arc<SedeViewHost>>,
    view: u32,
    verb: ViewNavigateVerb,
) -> Result<()> {
    host.navigate(view, verb)
}

/// The person explicitly copied or cut the focused page selection. Text stays
/// between the worker and the native clipboard, never in the webview channel.
#[tauri::command]
pub(super) async fn sede_view_clipboard<R: tauri::Runtime>(
    host: State<'_, Arc<SedeViewHost>>,
    app: AppHandle<R>,
    view: u32,
    action: ViewClipboardAction,
) -> Result<()> {
    let owner = host.inner().clone();
    tauri::async_runtime::spawn_blocking(move || owner.clipboard(view, action, &app))
        .await
        .map_err(|_| failure("unavailable"))?
}

#[tauri::command]
pub(super) fn sede_view_resize(
    host: State<'_, Arc<SedeViewHost>>,
    view: u32,
    css_width: u32,
    css_height: u32,
    scale: f64,
) -> Result<()> {
    host.resize(view, css_width, css_height, scale)
}

/// Grants the page one more image. Call it once for each `image` message
/// received, drawn or not: the host grants the first two itself.
#[tauri::command]
pub(super) fn sede_view_credit(host: State<'_, Arc<SedeViewHost>>, view: u32) -> Result<()> {
    host.credit(view)
}

/// The person's answer to a page dialog the view announced under `dialog_id`.
#[tauri::command]
pub(super) fn sede_view_dialog(
    host: State<'_, Arc<SedeViewHost>>,
    view: u32,
    dialog_id: u32,
    accept: bool,
    prompt_text: Option<String>,
) -> Result<()> {
    host.dialog(view, dialog_id, accept, prompt_text)
}

/// The person's answer to a download the view offered under `transfer_id`.
/// With `save`, the native save dialog asks where; a dialog closed unchosen
/// declines the download. The answer waits for the dialog. `download_ended`
/// follows on the channel when the bytes are written.
#[tauri::command]
pub(super) async fn sede_view_download_answer<R: tauri::Runtime>(
    host: State<'_, Arc<SedeViewHost>>,
    window: tauri::WebviewWindow<R>,
    view: u32,
    transfer_id: u32,
    save: bool,
) -> Result<DownloadAnswered> {
    let owner = host.inner().clone();
    blocking(move || Ok(owner.download_answer(view, transfer_id, save, &NativeDialogs(window))))
        .await?
}

/// The person's answer to a file chooser the page opened under `chooser_id`.
/// With `choose`, the native open dialog asks which files; a dialog closed
/// unchosen cancels the chooser. The answer waits for the dialog.
/// `upload_ended` follows on the channel for each file.
#[tauri::command]
pub(super) async fn sede_view_file_chooser_answer<R: tauri::Runtime>(
    host: State<'_, Arc<SedeViewHost>>,
    window: tauri::WebviewWindow<R>,
    view: u32,
    chooser_id: u32,
    choose: bool,
) -> Result<ChooserAnswered> {
    let owner = host.inner().clone();
    blocking(move || Ok(owner.chooser_answer(view, chooser_id, choose, &NativeDialogs(window))))
        .await?
}

/// Opens the page the person is on in the system browser. The window sends
/// no address.
#[tauri::command]
pub(super) async fn sede_view_open_external(
    host: State<'_, Arc<SedeViewHost>>,
    view: u32,
) -> Result<()> {
    let owner = host.inner().clone();
    blocking(move || Ok(owner.open_external(view))).await?
}

pub fn register<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        sede_view_open,
        sede_view_close,
        sede_view_input,
        sede_view_navigate,
        sede_view_clipboard,
        sede_view_resize,
        sede_view_credit,
        sede_view_dialog,
        sede_view_download_answer,
        sede_view_file_chooser_answer,
        sede_view_open_external
    ]
}
