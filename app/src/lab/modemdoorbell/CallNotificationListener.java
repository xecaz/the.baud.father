package lab.modemdoorbell;

import android.app.Notification;
import android.content.ComponentName;
import android.content.Context;
import android.app.NotificationManager;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.util.Log;

import java.util.HashSet;
import java.util.Set;

/**
 * Rings the doorbell for incoming calls from any app (WhatsApp, Signal, the dialer, ...), seen as
 * notifications with category "call". Internet calls do not change the phone state, so CallReceiver
 * never sees them.
 *
 * Also plays a ringtone for notifications from apps the user mapped (Ringtones), e.g. a spoken "WhatsApp message".
 *
 * Privacy: reads only the category, the flags, the CallStyle call type, whether there is a full-screen intent,
 * and the posting package name (logged). Never titles, text or caller names; nothing is stored.
 */
public class CallNotificationListener extends NotificationListenerService {
    static final String KEY_VOIP = "ring_on_internet_call";

    private final Set<String> rungKeys = new HashSet<>();

    static boolean enabled(Context c) {
        return CallReceiver.enabled(c) && c.getSharedPreferences(CallReceiver.PREFS, Context.MODE_PRIVATE)
                .getBoolean(KEY_VOIP, false);
    }

    static void setEnabled(Context c, boolean on) {
        c.getSharedPreferences(CallReceiver.PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY_VOIP, on).apply();
    }

    static boolean accessGranted(Context c) {
        return c.getSystemService(NotificationManager.class)
                .isNotificationListenerAccessGranted(new ComponentName(c, CallNotificationListener.class));
    }

    /** Incoming (ringing) call, as opposed to an ongoing or outgoing one. */
    private static boolean isIncomingCall(Notification n) {
        if (!Notification.CATEGORY_CALL.equals(n.category)) return false;
        int type = n.extras.getInt(Notification.EXTRA_CALL_TYPE, -1);
        if (type == Notification.CallStyle.CALL_TYPE_INCOMING) return true;
        if (type == Notification.CallStyle.CALL_TYPE_ONGOING
                || type == Notification.CallStyle.CALL_TYPE_SCREENING) return false;
        // No CallStyle: ringing calls show a full-screen ring screen, ongoing calls don't.
        return n.fullScreenIntent != null;
    }

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        Notification n = sbn.getNotification();
        if (n == null) return;
        if (!isIncomingCall(n)) {
            messageSound(sbn, n);
            return;
        }
        String key = sbn.getKey();
        if (!rungKeys.add(key)) return;   // same call, notification updated
        Log.i(RingSender.TAG, "incoming call notification from " + sbn.getPackageName());
        if (!enabled(this)) {
            Log.i(RingSender.TAG, "internet-call trigger is off");
            return;
        }
        // The phone app's own call notification is a regular call: plain ring. Anything else (WhatsApp,
        // Signal...) is an internet call: 0x03, the box plays the 56k clip.
        String dialer = getSystemService(android.telecom.TelecomManager.class).getDefaultDialerPackage();
        byte cmd = sbn.getPackageName().equals(dialer) ? MainActivity.CMD_RING : MainActivity.CMD_RING_NET;
        RingSender.send(this, "call notification " + sbn.getPackageName(), cmd, () -> { });
    }

    static final long APP_GAP_MS = 60000;   // one sound per app per minute (group chats, summaries, updates)
    private final java.util.Map<String, Long> lastByApp = new java.util.HashMap<>();

    /** A notification from an app that has a ringtone mapped (Ringtones). Reads flags, category and package only. */
    private void messageSound(StatusBarNotification sbn, Notification n) {
        String pkg = sbn.getPackageName();
        if (!Ringtones.onFor(this, pkg)) return;
        int tone = Ringtones.get(this, pkg);
        if (tone < 0) return;
        final int skip = Notification.FLAG_ONGOING_EVENT | Notification.FLAG_FOREGROUND_SERVICE | Notification.FLAG_GROUP_SUMMARY;
        if ((n.flags & skip) != 0) return;                       // sync/progress/service notices, group headers
        if (Notification.CATEGORY_CALL.equals(n.category) || Notification.CATEGORY_PROGRESS.equals(n.category)
                || Notification.CATEGORY_SERVICE.equals(n.category) || Notification.CATEGORY_TRANSPORT.equals(n.category)) return;
        long now = android.os.SystemClock.elapsedRealtime();
        Long last = lastByApp.get(pkg);
        if (last != null && now - last < APP_GAP_MS) return;     // quiet: bursts are normal
        if (getCurrentInterruptionFilter() != INTERRUPTION_FILTER_ALL) {
            Log.i(RingSender.TAG, "notification from " + pkg + ": Do Not Disturb is on, no sound");
            return;
        }
        if (Ringtones.quietNow(this)) {
            Log.i(RingSender.TAG, "notification from " + pkg + ": quiet hours, no sound");
            return;
        }
        lastByApp.put(pkg, now);
        if (tone == Ringtones.SAY) {                              // the app's own sentence, from the box's vocabulary
            String text = Ringtones.sentence(this, pkg);
            try {
                byte[] cmd = Vocab.command(this, Vocab.spell(this, text));
                Log.i(RingSender.TAG, "notification from " + pkg + ": say \"" + text + "\"");
                RingSender.send(this, "notification " + pkg, cmd, false, () -> { });
            } catch (Vocab.Unknown e) {
                Log.w(RingSender.TAG, "notification from " + pkg + ": sentence \"" + text + "\" not sent: " + e.getMessage());
            }
            return;
        }
        Log.i(RingSender.TAG, "notification from " + pkg + ": ringtone " + tone);
        RingSender.send(this, "notification " + pkg, Ringtones.cmd(tone), false, () -> { });
    }

    @Override
    public void onNotificationRemoved(StatusBarNotification sbn) {
        rungKeys.remove(sbn.getKey());
    }
}
