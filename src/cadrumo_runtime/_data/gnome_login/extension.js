// Read-only compositor observations. No login labels, credentials or lock actions.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const NAME = 'org.cadrumo.Runtime.LoginObservation1';
const PATH = '/org/cadrumo/Runtime/LoginObservation1';
const XML = `<node>
  <interface name="org.cadrumo.Runtime.LoginObservation1">
    <method name="GetState">
      <arg name="version" type="u" direction="out"/>
      <arg name="epoch" type="s" direction="out"/>
      <arg name="sequence" type="u" direction="out"/>
      <arg name="lockGeneration" type="u" direction="out"/>
      <arg name="locked" type="b" direction="out"/>
      <arg name="active" type="b" direction="out"/>
      <arg name="mode" type="s" direction="out"/>
    </method>
    <signal name="StateChanged"><arg name="sequence" type="u"/></signal>
  </interface>
</node>`;

export default class CadrumoLoginObservation extends Extension {
    enable() {
        this._ready = false;
        this._epoch = GLib.uuid_string_random();
        this._sequence = 1;
        this._shield = Main.screenShield;
        this._signals = [];
        if (!this._shield || typeof this._shield.locked !== 'boolean' ||
            typeof this._shield.active !== 'boolean')
            return;
        this._lockGeneration = this._shield.locked ? 1 : 0;
        this._object = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._object.export(Gio.DBus.session, PATH);
        this._signals.push([this._shield,
            this._shield.connect('locked-changed', () => {
                if (this._shield.locked) {
                    if (this._lockGeneration === 0xffffffff) {
                        this._epoch = GLib.uuid_string_random();
                        this._lockGeneration = 0;
                    }
                    this._lockGeneration++;
                }
                this._changed();
            })]);
        this._signals.push([this._shield,
            this._shield.connect('active-changed', () => this._changed())]);
        this._signals.push([Main.sessionMode,
            Main.sessionMode.connect('updated', () => this._changed())]);
        // Never replace another owner or queue a latent observer after a conflict.
        this._owner = Gio.bus_own_name_on_connection(Gio.DBus.session, NAME,
            Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
            () => { this._ready = true; },
            () => { this._ready = false; });
    }

    _changed() {
        if (this._sequence === 0xffffffff) {
            // Wrap must invalidate retained bindings rather than reuse an epoch.
            this._epoch = GLib.uuid_string_random();
            this._sequence = 1;
        } else {
            this._sequence++;
        }
        if (this._ready)
            this._object.emit_signal('StateChanged', new GLib.Variant('(u)', [this._sequence]));
    }

    GetState() {
        const mode = Main.sessionMode.currentMode;
        if (!this._ready || !this._shield ||
            typeof this._shield.locked !== 'boolean' ||
            typeof this._shield.active !== 'boolean' ||
            !['user', 'unlock-dialog'].includes(mode))
            throw new Error('Native login observation unavailable');
        // Read directly on Shell's main loop; no cached hint or asynchronous proxy.
        return [1, this._epoch, this._sequence, this._lockGeneration,
            this._shield.locked, this._shield.active, mode];
    }

    disable() {
        this._ready = false;
        if (this._owner)
            Gio.bus_unown_name(this._owner);
        this._owner = 0;
        for (const [object, signal] of this._signals ?? [])
            object.disconnect(signal);
        this._signals = [];
        this._object?.unexport();
        this._object = null;
        this._shield = null;
        this._epoch = null;
    }
}
