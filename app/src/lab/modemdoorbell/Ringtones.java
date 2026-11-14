package lab.modemdoorbell;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.Calendar;
import java.util.Map;
import java.util.TreeMap;

/**
 * The box's ringtones (firmware config.h RINGTONES, append-only: the numbers are stored here) and the
 * per-app mapping "notification from this app -> ringtone n". The app sends 0x10 + n; the box knows the sound.
 */
final class Ringtones {
    /** Index = ringtone number on the box. Keep in step with firmware/main/config.h. */
    static final String[] NAMES = {
            "Call: real 33.6k handshake",
            "Call: recorded 56k handshake",
            "Voice: \"WhatsApp message\"",
            "Voice: \"Signal message\"",
            "Failed negotiation, redial, connect (long)",
            "Voice: \"Incoming e-mail\"",
            "Demo: call, connect, \"Signal message\", \"WhatsApp message\"",
    };

    private static final String PREFS = "doorbell_sounds";
    private static final String APP = "app:";
    private static final String KEY_ON = "message_sounds";
    private static final String KEY_MISC_ON = "misc_sounds";
    private static final String KEY_QUIET = "quiet_hours";
    /** The "Messages" category; every other mapped app is "Misc". */
    static final String[] MESSENGERS = {"com.whatsapp", "org.thoughtcrime.securesms"};
    private static final String KEY_SEEDED = "seeded";
    static final int QUIET_FROM = 22, QUIET_TO = 7;   // 22:00-07:00

    private Ringtones() {}

    static byte cmd(int n) {
        return (byte) (0x10 + n);
    }

    static String name(int n) {
        return n >= 0 && n < NAMES.length ? NAMES[n] : "Ringtone " + n;
    }

    private static SharedPreferences prefs(Context c) {
        SharedPreferences p = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        if (!p.getBoolean(KEY_SEEDED, false)) {   // first run: the two the box already has voices for
            p.edit().putInt(APP + "com.whatsapp", 2).putInt(APP + "org.thoughtcrime.securesms", 3)
                    .putBoolean(KEY_SEEDED, true).apply();
        }
        return p;
    }

    static boolean isMessenger(String pkg) {
        for (String m : MESSENGERS) if (m.equals(pkg)) return true;
        return false;
    }

    static boolean miscOn(Context c) {
        return prefs(c).getBoolean(KEY_MISC_ON, false);
    }

    static void setMiscOn(Context c, boolean on) {
        prefs(c).edit().putBoolean(KEY_MISC_ON, on).apply();
    }

    /** Is the category this app belongs to switched on? */
    static boolean onFor(Context c, String pkg) {
        return isMessenger(pkg) ? on(c) : miscOn(c);
    }

    static boolean on(Context c) {
        return prefs(c).getBoolean(KEY_ON, false);
    }

    static void setOn(Context c, boolean on) {
        prefs(c).edit().putBoolean(KEY_ON, on).apply();
    }

    static boolean quiet(Context c) {
        return prefs(c).getBoolean(KEY_QUIET, false);
    }

    static void setQuiet(Context c, boolean on) {
        prefs(c).edit().putBoolean(KEY_QUIET, on).apply();
    }

    static boolean quietNow(Context c) {
        if (!quiet(c)) return false;
        int h = Calendar.getInstance().get(Calendar.HOUR_OF_DAY);
        return h >= QUIET_FROM || h < QUIET_TO;
    }

    /** Ringtone for a package, or -1. */
    static int get(Context c, String pkg) {
        return prefs(c).getInt(APP + pkg, -1);
    }

    static void set(Context c, String pkg, int n) {
        SharedPreferences.Editor e = prefs(c).edit();
        if (n < 0) e.remove(APP + pkg);
        else e.putInt(APP + pkg, n);
        e.apply();
    }

    /** package -> ringtone, sorted by package. */
    static Map<String, Integer> all(Context c) {
        Map<String, Integer> m = new TreeMap<>();
        for (Map.Entry<String, ?> e : prefs(c).getAll().entrySet()) {
            if (e.getKey().startsWith(APP) && e.getValue() instanceof Integer) {
                m.put(e.getKey().substring(APP.length()), (Integer) e.getValue());
            }
        }
        return m;
    }
}
