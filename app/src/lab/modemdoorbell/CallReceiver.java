package lab.modemdoorbell;

import android.Manifest;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.telephony.TelephonyManager;
import android.util.Log;

/**
 * Rings the doorbell when the phone starts ringing. ACTION_PHONE_STATE_CHANGED is on Android's list of
 * implicit broadcasts still delivered to manifest receivers, so this works while the app is closed
 * (not after "Force stop", until the app is opened again).
 * Only the call state is used; the caller's number needs READ_CALL_LOG, which this app does not request.
 */
public class CallReceiver extends BroadcastReceiver {
    static final String PREFS = "doorbell";
    static final String KEY_CALL_TRIGGER = "ring_on_incoming_call";

    static boolean enabled(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY_CALL_TRIGGER, false);
    }

    static void setEnabled(Context c, boolean on) {
        c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY_CALL_TRIGGER, on).apply();
    }

    @Override
    public void onReceive(Context c, Intent i) {
        if (!TelephonyManager.ACTION_PHONE_STATE_CHANGED.equals(i.getAction())) return;
        String state = i.getStringExtra(TelephonyManager.EXTRA_STATE);
        Log.i(RingSender.TAG, "phone state: " + state);
        if (!TelephonyManager.EXTRA_STATE_RINGING.equals(state)) return;
        if (!enabled(c)) {
            Log.i(RingSender.TAG, "incoming call, call trigger is off");
            return;
        }
        if (c.checkSelfPermission(Manifest.permission.READ_PHONE_STATE) != PackageManager.PERMISSION_GRANTED) return;
        PendingResult pending = goAsync();
        RingSender.send(c, "incoming call", pending::finish);
    }
}
