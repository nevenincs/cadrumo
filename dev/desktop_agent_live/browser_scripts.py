"""Scripts used to observe and control the attached desktop shell."""

from typing import Final

SHELL_GRANT_COPIER: Final = """(() => {
    const shell = window.__CADRUMO_SHELL__;
    if (!shell) return;
    const token = shell.token;
    if (!token) return;
    Object.defineProperty(shell, "token", {configurable: true, get() { delete shell.token; return token; }});
    Object.defineProperty(window, "__CADRUMO_LANE_TOKEN__", {configurable: true, value: token});
})()"""


INVOKE: Final = """async ({command, args}) => {
    const token = window.__CADRUMO_LANE_TOKEN__;
    if (!token) throw new Error('desktop token unavailable');
    try {
        return {ok: await window.__TAURI_INTERNALS__.invoke(command, {...args, token})};
    } catch (error) {
        return {refused: error};
    }
}"""


STATUS_UNTIL: Final = """async ({command, until, boundMs}) => {
    const token = window.__CADRUMO_LANE_TOKEN__;
    if (!token) throw new Error('desktop token unavailable');
    const conditions = {
        sign_in_observed: (status) => Boolean(status && status.runtimeAvailable && status.state !== 'unknown'),
        signed_in: (status) => Boolean(status && status.state === 'present'),
        agent_ready: (status) => Boolean(status && status.state === 'ready'),
    };
    const holds = conditions[until];
    if (!holds) throw new Error(`unknown condition ${until}`);
    const bound = Date.now() + boundMs;
    let status = null;
    for (;;) {
        try { status = await window.__TAURI_INTERNALS__.invoke(command, {token}); }
        catch (error) { status = {unreadable: error}; }
        if (holds(status)) return {held: true, status};
        if (Date.now() >= bound) return {held: false, status};
        await new Promise((frame) => requestAnimationFrame(frame));
    }
}"""


CATALOG_SETTLED: Final = """async ({boundMs}) => {
    const token = window.__CADRUMO_LANE_TOKEN__;
    if (!token) throw new Error('desktop token unavailable');
    const bound = Date.now() + boundMs;
    for (;;) {
        try {
            return {ok: await window.__TAURI_INTERNALS__.invoke('agent_provider_catalog', {token})};
        } catch (error) {
            const busy = error && error.code === 'agent_service_busy';
            if (!busy || Date.now() >= bound) return {refused: error};
        }
        await new Promise((next) => requestAnimationFrame(next));
    }
}"""


SIGN_IN_OR_FAILURE: Final = """async ({boundMs, afterSequence}) => {
    const token = window.__CADRUMO_LANE_TOKEN__;
    if (!token) throw new Error('desktop token unavailable');
    const invoke = (command, args) => window.__TAURI_INTERNALS__.invoke(command, {...args, token});
    const bound = Date.now() + boundMs;
    let status = null;
    for (let frame = 0; ; frame++) {
        try { status = await invoke('sign_in_status', {}); } catch (error) { status = {unreadable: error}; }
        if (status && status.state === 'present') return {status, events: []};
        if (frame % 30 === 0) {
            let snapshot = null;
            try { snapshot = await invoke('diagnostics_snapshot', {after: 0}); } catch (error) { snapshot = null; }
            const events = ((snapshot && snapshot.events) || []).filter((event) => event.sequence > afterSequence);
            if (sign_in_failed(events)) return {status, events};
        }
        if (Date.now() >= bound) return {status, events: []};
        await new Promise((next) => requestAnimationFrame(next));
    }
    function sign_in_failed(events) {
        return events.some((event) => event.kind === 'helper_result' && event.failure
            && event.helperResult && event.helperResult.command === 'config.login');
    }
}"""


ENDED: Final = """({title, why, close}) => {
    const cover = document.createElement('div');
    cover.setAttribute('role', 'alertdialog');
    cover.setAttribute('aria-label', title);
    cover.style.cssText = 'position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;'
        + 'justify-content:center;background:rgba(0,0,0,.55);font:14px system-ui,sans-serif';
    const card = document.createElement('div');
    card.style.cssText = 'max-width:42rem;background:#fff;color:#111;padding:1.5rem;border-radius:.75rem';
    const heading = document.createElement('h2');
    heading.textContent = title;
    const text = document.createElement('p');
    text.style.whiteSpace = 'pre-wrap';
    text.textContent = why;
    const button = document.createElement('button');
    button.textContent = close;
    button.addEventListener('click', () => { window.__CADRUMO_LANE_ACKNOWLEDGED__ = true; });
    card.append(heading, text, button);
    cover.append(card);
    document.body.append(cover);
    button.focus();
}"""
