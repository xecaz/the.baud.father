package lab.modemdoorbell;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.BluetoothStatusCodes;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanFilter;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.graphics.Insets;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelUuid;
import android.view.Gravity;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

/**
 * Remote for the Baudfather (modem.doorbell): finds the box over BLE, bonds, and writes the trigger.
 * GATT contract: notes/ble.md (mirrors firmware/main/ble.h).
 */
public class MainActivity extends Activity {
    static final UUID SERVICE = UUID.fromString("2139d581-b04a-4808-8e1f-f08bb13d8de6");
    static final UUID TRIGGER = UUID.fromString("2139d582-b04a-4808-8e1f-f08bb13d8de6");
    static final UUID STATUS = UUID.fromString("2139d583-b04a-4808-8e1f-f08bb13d8de6");
    static final UUID CCCD = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
    static final byte CMD_RING = 0x01;
    static final byte CMD_IDENTIFY = 0x02;
    static final byte CMD_RING_NET = 0x03;   // internet call (WhatsApp etc.): the box plays the 56k clip
    static final String[] STATUS_NAMES = {"Ready", "Calling…", "Resting between calls", "Pairing window open"};
    static final String DEVICE_NAME = "doorbell";
    static final long SCAN_TIMEOUT_MS = 15000;

    private final Handler ui = new Handler(Looper.getMainLooper());
    private BluetoothAdapter adapter;
    private BluetoothLeScanner scanner;
    private BluetoothDevice device;
    private BluetoothGatt gatt;
    private BluetoothGattCharacteristic triggerChar, statusChar;
    private boolean scanning, ready, busy;
    private volatile int boxStatus = -1;   // last value from the Status characteristic

    private TextView stateText, statusText, logText;
    private Button ringBtn, blinkBtn, connectBtn, demoBtn, tryBtn;
    private Button sayBtn;
    static final int DEMO_RINGTONE = 6;
    private Switch callSwitch, voipSwitch, msgSwitch, miscSwitch, quietSwitch;
    private LinearLayout msgBox, soundsBox;
    private final ArrayDeque<String> logLines = new ArrayDeque<>();

    // ---------------------------------------------------------------- UI

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private TextView text(float sp, boolean bold) {
        TextView t = new TextView(this);
        t.setTextSize(sp);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setPadding(0, dp(6), 0, dp(6));
        return t;
    }

    private Button button(String label, int heightDp, float sp) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(sp);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(heightDp));
        lp.topMargin = dp(8);
        b.setLayoutParams(lp);
        b.setAllCaps(false);
        return b;
    }

    /** A titled card; title and description may be null. Returns the card to add controls to. */
    private LinearLayout section(LinearLayout root, String title, String desc) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), dp(12), dp(16), dp(14));
        android.graphics.drawable.GradientDrawable bg = new android.graphics.drawable.GradientDrawable();
        bg.setColor(0x16FFFFFF);
        bg.setCornerRadius(dp(14));
        box.setBackground(bg);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(14);
        box.setLayoutParams(lp);
        if (title != null) {
            TextView h = text(20, true);
            h.setText(title);
            box.addView(h);
        }
        if (desc != null) box.addView(note(desc));
        root.addView(box);
        return box;
    }

    private TextView note(String s) {
        TextView t = text(14, false);
        t.setText(s);
        t.setAlpha(0.75f);
        return t;
    }

    private Switch toggle(String label) {
        Switch sw = new Switch(this);
        sw.setText(label);
        sw.setTextSize(17);
        sw.setPadding(0, dp(12), 0, dp(12));
        return sw;
    }

    /** Two buttons side by side, equal width. */
    private LinearLayout row(Button a, Button b) {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.HORIZONTAL);
        for (Button x : new Button[]{a, b}) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, x.getLayoutParams().height, 1f);
            lp.topMargin = dp(8);
            if (x == b) lp.leftMargin = dp(8);
            x.setLayoutParams(lp);
            r.addView(x);
        }
        return r;
    }

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        final int pad = dp(16);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setOnApplyWindowInsetsListener((v, in) -> {
            Insets i = in.getInsets(WindowInsets.Type.systemBars());
            v.setPadding(pad + i.left, pad + i.top, pad + i.right, pad + i.bottom);
            return WindowInsets.CONSUMED;
        });

        // Header: res/drawable-nodpi/header.png (the user's logo, cream background) as a rounded card.
        android.widget.ImageView title = new android.widget.ImageView(this);
        title.setImageResource(getResources().getIdentifier("header", "drawable", getPackageName()));
        title.setAdjustViewBounds(true);
        title.setContentDescription("The Baud Father");
        android.graphics.drawable.GradientDrawable card = new android.graphics.drawable.GradientDrawable();
        card.setColor(0xFFFBF6EC);
        card.setCornerRadius(dp(14));
        title.setBackground(card);
        title.setClipToOutline(true);
        LinearLayout.LayoutParams hl = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        hl.bottomMargin = dp(10);
        title.setLayoutParams(hl);
        root.addView(title);

        // Connection
        LinearLayout conn = section(root, null, null);
        statusText = text(18, true);
        stateText = text(14, false);
        stateText.setAlpha(0.75f);
        connectBtn = button("Connect", 52, 16);
        conn.addView(statusText);
        conn.addView(stateText);
        conn.addView(connectBtn);

        // Ring it now
        LinearLayout now = section(root, "Ring it now", "Place a call between the two modems.");
        ringBtn = button("RING", 96, 28);
        demoBtn = button("Demo", 52, 16);
        tryBtn = button("Play a ringtone…", 52, 16);
        blinkBtn = button("Blink the LED", 52, 16);
        now.addView(ringBtn);
        now.addView(row(demoBtn, tryBtn));
        sayBtn = button("Say…", 52, 16);
        now.addView(row(sayBtn, blinkBtn));

        // Incoming calls
        LinearLayout calls = section(root, "Incoming calls", "Make The Baud Father ring when your phone receives a call.");
        callSwitch = toggle("Phone calls");
        callSwitch.setChecked(CallReceiver.enabled(this)
                && checkSelfPermission(Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED);
        voipSwitch = toggle("Internet calls (WhatsApp, Signal …)");
        calls.addView(callSwitch);
        calls.addView(voipSwitch);
        calls.addView(note("Internet calls need notification access. A phone call plays the long failed "
                + "negotiation and redial; an internet call connects at 33.6k."));

        // Messages
        LinearLayout msgs = section(root, "Messages", "Announce new messages from your chat apps.");
        msgSwitch = toggle("Message sounds");
        msgBox = new LinearLayout(this);
        msgBox.setOrientation(LinearLayout.VERTICAL);
        msgs.addView(msgSwitch);
        msgs.addView(msgBox);

        // Misc
        LinearLayout misc = section(root, "Misc", "Pick any other app and a sound for its notifications.");
        miscSwitch = toggle("Other app sounds");
        soundsBox = new LinearLayout(this);
        soundsBox.setOrientation(LinearLayout.VERTICAL);
        misc.addView(miscSwitch);
        misc.addView(soundsBox);
        misc.addView(note("Messages and Misc: at most one sound per app per minute. Both need notification "
                + "access; only the app's name is read, never the content."));

        // Quiet time
        LinearLayout quiet = section(root, "Quiet time", "Do Not Disturb always silences message sounds. Calls still ring.");
        quietSwitch = toggle("Also quiet from " + Ringtones.QUIET_FROM + ":00 to 0" + Ringtones.QUIET_TO + ":00");
        quietSwitch.setChecked(Ringtones.quiet(this));
        quiet.addView(quietSwitch);

        // Activity
        LinearLayout act = section(root, "Activity", null);
        logText = text(12, false);
        logText.setTypeface(Typeface.MONOSPACE);
        act.addView(logText);

        android.widget.ScrollView scroll = new android.widget.ScrollView(this);
        scroll.addView(root);
        setContentView(scroll);

        ringBtn.setOnClickListener(v -> send(CMD_RING, "ring"));
        sayBtn.setOnClickListener(v -> askSentence());
        tryBtn.setOnClickListener(v ->
                pickRingtone("Play a ringtone", false, n -> {
                    if (n == Ringtones.SAY) askSentence();
                    else send(Ringtones.cmd(n), Ringtones.name(n));
                }));
        msgSwitch.setOnCheckedChangeListener((v, on) -> {
            if (syncingSwitches) return;
            Ringtones.setOn(this, on);
            if (on && !CallNotificationListener.accessGranted(this)) {
                log("Allow \"The Baud Father\" under notification access, then come back");
                startActivity(new Intent(android.provider.Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS));
                return;
            }
            log(on ? "Message sounds on" : "Message sounds off");
        });
        miscSwitch.setOnCheckedChangeListener((v, on) -> {
            if (syncingSwitches) return;
            Ringtones.setMiscOn(this, on);
            if (on && !CallNotificationListener.accessGranted(this)) {
                log("Allow \"The Baud Father\" under notification access, then come back");
                startActivity(new Intent(android.provider.Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS));
                return;
            }
            log(on ? "Other app sounds on" : "Other app sounds off");
        });
        quietSwitch.setOnCheckedChangeListener((v, on) -> Ringtones.setQuiet(this, on));
        blinkBtn.setOnClickListener(v -> send(CMD_IDENTIFY, "blink"));
        demoBtn.setOnClickListener(v -> send(Ringtones.cmd(DEMO_RINGTONE), "demo"));
        connectBtn.setOnClickListener(v -> start());
        callSwitch.setOnCheckedChangeListener((v, on) -> {
            if (on && checkSelfPermission(Manifest.permission.READ_PHONE_STATE) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.READ_PHONE_STATE}, 2);
                return;   // saved once the permission is granted
            }
            CallReceiver.setEnabled(this, on);
            log(on ? "Call trigger on" : "Call trigger off");
            refreshSwitches();
        });
        voipSwitch.setOnCheckedChangeListener((v, on) -> {
            if (syncingSwitches) return;
            CallNotificationListener.setEnabled(this, on);
            if (on && !CallNotificationListener.accessGranted(this)) {
                log("Allow \"The Baud Father\" under notification access, then come back");
                startActivity(new Intent(android.provider.Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS));
                return;
            }
            log(on ? "Internet-call trigger on" : "Internet-call trigger off");
        });

        adapter = getSystemService(BluetoothManager.class).getAdapter();
        registerReceiver(bondReceiver, new IntentFilter(BluetoothDevice.ACTION_BOND_STATE_CHANGED),
                Context.RECEIVER_EXPORTED);
        updateButtons();

        if (hasPermissions()) start();
        else requestPermissions(new String[]{Manifest.permission.BLUETOOTH_SCAN,
                Manifest.permission.BLUETOOTH_CONNECT}, 1);
    }

    private boolean syncingSwitches;

    /** Show the saved choices, but only as "on" when Android actually grants what they need. */
    private void refreshSwitches() {
        syncingSwitches = true;
        boolean callOn = CallReceiver.enabled(this)
                && checkSelfPermission(Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED;
        voipSwitch.setEnabled(callOn);
        voipSwitch.setChecked(callOn && CallNotificationListener.enabled(this)
                && CallNotificationListener.accessGranted(this));
        msgSwitch.setChecked(Ringtones.on(this) && CallNotificationListener.accessGranted(this));
        miscSwitch.setChecked(Ringtones.miscOn(this) && CallNotificationListener.accessGranted(this));
        refreshSounds();
        syncingSwitches = false;
    }

    // ---------------------------------------------------------------- say (sentences from the box's vocabulary)

    private String lastSentence = "";

    private interface TextPick { void picked(String text); }

    private void askSentence() {
        askSentence("Say", "Say it", lastSentence, this::say);
    }

    /** A word button of the Say dialog. */
    private TextView chip(String label, android.widget.EditText in, String adds) {
        TextView t = new TextView(this);
        t.setText(label);
        t.setTextSize(15);
        t.setPadding(dp(11), dp(7), dp(11), dp(7));
        android.graphics.drawable.GradientDrawable bg = new android.graphics.drawable.GradientDrawable();
        bg.setColor(0x33888888);
        bg.setCornerRadius(dp(16));
        t.setBackground(bg);
        t.setOnClickListener(v -> {
            String cur = in.getText().toString().trim();
            String next = cur.isEmpty() ? adds : adds.equals(",") ? cur + "," : cur + " " + adds;
            in.setText(next);
            in.setSelection(next.length());
        });
        return t;
    }

    /** Dialog: build a sentence by tapping the box's words (grouped as in tools/vocab.txt) or by typing. then gets
     *  a sentence the box can say; one it cannot is reported and dropped. */
    private void askSentence(String title, String ok, String initial, TextPick then) {
        android.widget.EditText in = new android.widget.EditText(this);
        in.setHint("Tap words, or type: 3 new messages");
        in.setSingleLine(true);
        in.setText(initial);
        in.setSelection(initial.length());
        Button back = new Button(this);
        back.setText("⌫");
        back.setTextSize(18);
        back.setOnClickListener(v -> {                       // remove the last word (or pause)
            String cur = in.getText().toString().trim();
            int cut = cur.endsWith(",") ? cur.length() - 1 : Math.max(cur.lastIndexOf(' '), 0);
            String next = cur.substring(0, cut).trim();
            in.setText(next);
            in.setSelection(next.length());
        });
        back.setOnLongClickListener(v -> {
            in.setText("");
            return true;
        });
        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.addView(in, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        top.addView(back, new LinearLayout.LayoutParams(dp(56), LinearLayout.LayoutParams.WRAP_CONTENT));

        LinearLayout words = new LinearLayout(this);
        words.setOrientation(LinearLayout.VERTICAL);
        words.addView(note("Numbers can be typed as digits. Up to " + Vocab.MAX_WORDS + " words. ⌫ removes the last "
                + "word, held: all."));
        List<String> titles = Vocab.groupTitles(this);
        for (int g = 0; g < titles.size(); g++) {
            TextView h = text(13, true);
            h.setText(titles.get(g).toUpperCase(Locale.ROOT));
            h.setAlpha(0.6f);
            h.setPadding(0, dp(12), 0, dp(4));
            words.addView(h);
            FlowLayout flow = new FlowLayout(this, dp(6));
            if (g == 0) flow.addView(chip("pause ,", in, ","));
            for (String w : Vocab.groupWords(this, g)) flow.addView(chip(w, in, w));
            words.addView(flow);
        }
        android.widget.ScrollView sc = new android.widget.ScrollView(this);
        sc.addView(words);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(8), dp(20), 0);
        box.setFocusableInTouchMode(true);                   // the field does not take focus: no keyboard over the words
        box.addView(top);
        box.addView(sc);
        new android.app.AlertDialog.Builder(this).setTitle(title)
                .setView(box)
                .setPositiveButton(ok, (d, which) -> {
                    String text = in.getText().toString().trim();
                    try {
                        Vocab.spell(this, text);
                        then.picked(text);
                    } catch (Vocab.Unknown e) {
                        log(e.getMessage());
                        android.widget.Toast.makeText(this, e.getMessage(), android.widget.Toast.LENGTH_LONG).show();
                    }
                })
                .setNegativeButton("Cancel", null).show();
    }

    private void say(String text) {
        lastSentence = text.trim();
        try {
            List<String> w = Vocab.spell(this, text);
            send(Vocab.command(this, w), "\"" + String.join(" ", w) + "\"");
        } catch (Vocab.Unknown e) {
            log(e.getMessage());
            android.widget.Toast.makeText(this, e.getMessage(), android.widget.Toast.LENGTH_LONG).show();
        }
    }

    // ---------------------------------------------------------------- message sounds (app -> ringtone)

    private interface IntPick { void picked(int n); }

    /** Dialog with the box's ringtones, then "Say a sentence…" (reports Ringtones.SAY); withNone adds "No sound"
     *  (reports -1). */
    private void pickRingtone(String title, boolean withNone, IntPick then) {
        final int n = Ringtones.NAMES.length;
        String[] items = new String[n + 1 + (withNone ? 1 : 0)];
        System.arraycopy(Ringtones.NAMES, 0, items, 0, n);
        items[n] = "Say a sentence…";
        if (withNone) items[n + 1] = "No sound";
        new android.app.AlertDialog.Builder(this).setTitle(title)
                .setItems(items, (d, which) -> then.picked(which < n ? which : which == n ? Ringtones.SAY : -1))
                .setNegativeButton("Cancel", null).show();
    }

    /** What the user picked for an app: store it and play it once. A sentence is asked for first. */
    private void mapApp(String pkg, int n) {
        if (n == Ringtones.SAY) {
            askSentence(appLabel(pkg), "Save", Ringtones.sentence(this, pkg), text -> {
                Ringtones.setSentence(this, pkg, text);
                say(text);
                refreshSounds();
            });
            return;
        }
        Ringtones.set(this, pkg, n);
        if (n >= 0) send(Ringtones.cmd(n), Ringtones.name(n));   // hear it (if connected and idle)
        refreshSounds();
    }

    private String appLabel(String pkg) {
        try {
            PackageManager pm = getPackageManager();
            return pm.getApplicationLabel(pm.getApplicationInfo(pkg, 0)).toString();
        } catch (PackageManager.NameNotFoundException e) {
            return pkg + " (not installed)";
        }
    }

    /** One app's row: "App  →  sound"; tap to change, silence or (Misc only) remove, and hear the choice. */
    private Button soundRow(String pkg, int tone, boolean messenger) {
        Button b = button(appLabel(pkg) + "  →  " + Ringtones.label(this, pkg, tone), 56, 14);
        b.setOnClickListener(v -> pickRingtone(appLabel(pkg), true, n -> mapApp(pkg, n)));
        return b;
    }

    /** Messages: the known chat apps (always listed). Misc: every other mapped app, then "Add an app". */
    private void refreshSounds() {
        msgBox.removeAllViews();
        for (String pkg : Ringtones.MESSENGERS) msgBox.addView(soundRow(pkg, Ringtones.get(this, pkg), true));
        soundsBox.removeAllViews();
        for (java.util.Map.Entry<String, Integer> e : Ringtones.all(this).entrySet()) {
            if (!Ringtones.isMessenger(e.getKey())) soundsBox.addView(soundRow(e.getKey(), e.getValue(), false));
        }
        Button add = button("Add an app…", 56, 14);
        add.setOnClickListener(v -> pickApp());
        soundsBox.addView(add);
    }

    /** Installed apps that have a launcher icon, by name. */
    private void pickApp() {
        PackageManager pm = getPackageManager();
        Intent launcher = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        java.util.TreeMap<String, String> byLabel = new java.util.TreeMap<>(String.CASE_INSENSITIVE_ORDER);
        for (android.content.pm.ResolveInfo r : pm.queryIntentActivities(launcher, 0)) {
            String pkg = r.activityInfo.packageName;
            if (pkg.equals(getPackageName()) || Ringtones.isMessenger(pkg)) continue;
            byLabel.put(r.loadLabel(pm) + "  (" + pkg + ")", pkg);
        }
        String[] labels = byLabel.keySet().toArray(new String[0]);
        new android.app.AlertDialog.Builder(this).setTitle("Which app?")
                .setItems(labels, (d, which) -> {
                    String pkg = byLabel.get(labels[which]);
                    pickRingtone(appLabel(pkg), false, n -> mapApp(pkg, n));
                })
                .setNegativeButton("Cancel", null).show();
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshSwitches();   // e.g. back from the notification-access settings
    }

    @Override
    protected void onDestroy() {
        unregisterReceiver(bondReceiver);
        stopScan();
        if (gatt != null) {
            gatt.disconnect();
            gatt.close();
            gatt = null;
        }
        super.onDestroy();
    }

    private void setState(String s) {
        ui.post(() -> stateText.setText(s));
    }

    private void log(String s) {
        String line = new SimpleDateFormat("HH:mm:ss", Locale.ROOT).format(new Date()) + "  " + s;
        ui.post(() -> {
            logLines.addLast(line);
            while (logLines.size() > 10) logLines.removeFirst();
            logText.setText(String.join("\n", logLines));
        });
    }

    private void updateButtons() {
        ui.post(() -> {
            // RING only when the box would act on it: idle (0) or pairing window (3).
            ringBtn.setEnabled(ready && !busy && (boxStatus == 0 || boxStatus == 3));
            demoBtn.setEnabled(ringBtn.isEnabled());
            tryBtn.setEnabled(ringBtn.isEnabled());
            sayBtn.setEnabled(ready && !busy);   // sentences queue on the box, also during a ring
            blinkBtn.setEnabled(ready && !busy);
            connectBtn.setEnabled(!ready && !scanning);
            connectBtn.setVisibility(ready ? android.view.View.GONE : android.view.View.VISIBLE);
            if (!ready) statusText.setText(scanning ? "Searching…" : "Not connected");
        });
    }

    private void showStatus(byte[] value) {
        if (value == null || value.length < 1) return;
        int s = value[0] & 0xff;
        boxStatus = s;
        updateButtons();
        String name = s < STATUS_NAMES.length ? STATUS_NAMES[s] : ("Unknown (" + s + ")");
        ui.post(() -> statusText.setText(name));
    }

    // ---------------------------------------------------------------- permissions

    private boolean hasPermissions() {
        return checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED
                && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        if (code == 2) {
            boolean ok = checkSelfPermission(Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED;
            CallReceiver.setEnabled(this, ok);
            callSwitch.setChecked(ok);
            refreshSwitches();
            log(ok ? "Call trigger on" : "Phone permission denied: call trigger off");
            return;
        }
        if (hasPermissions()) start();
        else setState("Bluetooth permissions are needed. Allow them in the app settings.");
    }

    // ---------------------------------------------------------------- find, bond, connect

    private void start() {
        if (!hasPermissions()) {
            requestPermissions(new String[]{Manifest.permission.BLUETOOTH_SCAN,
                    Manifest.permission.BLUETOOTH_CONNECT}, 1);
            return;
        }
        if (adapter == null || !adapter.isEnabled()) {
            setState("Bluetooth is off. Turn it on and tap Connect.");
            return;
        }
        for (BluetoothDevice d : adapter.getBondedDevices()) {
            if (DEVICE_NAME.equals(d.getName())) {
                device = d;
                log("Using paired box " + d.getAddress());
                connect();
                return;
            }
        }
        scan();
    }

    private void scan() {
        scanner = adapter.getBluetoothLeScanner();
        if (scanner == null) {
            setState("BLE scanner not available.");
            return;
        }
        ScanFilter filter = new ScanFilter.Builder().setServiceUuid(new ParcelUuid(SERVICE)).build();
        ScanSettings settings = new ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build();
        scanning = true;
        updateButtons();
        setState("Searching for The Baud Father…");
        scanner.startScan(List.of(filter), settings, scanCallback);
        ui.postDelayed(scanTimeout, SCAN_TIMEOUT_MS);
    }

    private final Runnable scanTimeout = () -> {
        if (!scanning) return;
        stopScan();
        setState("The Baud Father was not found. Is it powered and in range? Tap Connect to retry.");
    };

    private void stopScan() {
        ui.removeCallbacks(scanTimeout);
        if (scanning && scanner != null) scanner.stopScan(scanCallback);
        scanning = false;
        updateButtons();
    }

    private final ScanCallback scanCallback = new ScanCallback() {
        @Override
        public void onScanResult(int type, ScanResult r) {
            if (!scanning) return;
            stopScan();
            device = r.getDevice();
            log("Found " + device.getAddress() + " (RSSI " + r.getRssi() + ")");
            if (device.getBondState() == BluetoothDevice.BOND_BONDED) connect();
            else pair();
        }

        @Override
        public void onScanFailed(int err) {
            scanning = false;
            updateButtons();
            setState("Scan failed (" + err + "). Tap Connect to retry.");
        }
    };

    private void pair() {
        setState("Pairing… The box accepts this only while its LED blinks "
                + "(hold RING or BOOT for 3 s).");
        if (!device.createBond()) log("createBond() refused");
    }

    private final BroadcastReceiver bondReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context c, Intent i) {
            BluetoothDevice d = i.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice.class);
            if (device == null || d == null || !d.getAddress().equals(device.getAddress())) return;
            int state = i.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE, BluetoothDevice.BOND_NONE);
            int prev = i.getIntExtra(BluetoothDevice.EXTRA_PREVIOUS_BOND_STATE, BluetoothDevice.BOND_NONE);
            if (state == BluetoothDevice.BOND_BONDED) {
                log("Paired");
                connect();
            } else if (state == BluetoothDevice.BOND_NONE && prev == BluetoothDevice.BOND_BONDING) {
                log("Pairing failed or rejected");
                setState("Pairing rejected. Hold RING or BOOT on the box for 3 s until the LED blinks, "
                        + "then tap Connect within 60 s.");
                updateButtons();
            }
        }
    };

    private void connect() {
        if (gatt != null) {
            gatt.close();
            gatt = null;
        }
        setState("Connecting…");
        gatt = device.connectGatt(this, false, gattCallback, BluetoothDevice.TRANSPORT_LE);
    }

    private final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {
        @Override
        public void onConnectionStateChange(BluetoothGatt g, int status, int newState) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                setState("Connected, reading the box…");
                g.discoverServices();
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                ready = false;
                busy = false;
                g.close();
                if (g == gatt) gatt = null;
                log("Disconnected (status " + status + ")");
                setState("Disconnected. Tap Connect.");
                updateButtons();
            }
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt g, int status) {
            BluetoothGattService svc = g.getService(SERVICE);
            if (status != BluetoothGatt.GATT_SUCCESS || svc == null) {
                setState("This device is not a Baud Father.");
                g.disconnect();
                return;
            }
            triggerChar = svc.getCharacteristic(TRIGGER);
            statusChar = svc.getCharacteristic(STATUS);
            g.setCharacteristicNotification(statusChar, true);
            BluetoothGattDescriptor ccc = statusChar.getDescriptor(CCCD);
            g.writeDescriptor(ccc, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
        }

        @Override
        public void onDescriptorWrite(BluetoothGatt g, BluetoothGattDescriptor d, int status) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                log("Enabling status updates failed (" + status + ")");
                setState("The box refused the link. If it was reset (bonds forgotten), remove "
                        + "\"doorbell\" in Android Bluetooth settings and connect again.");
                return;
            }
            g.readCharacteristic(statusChar);
        }

        @Override
        public void onCharacteristicRead(BluetoothGatt g, BluetoothGattCharacteristic ch, byte[] value, int status) {
            if (status == BluetoothGatt.GATT_SUCCESS) showStatus(value);
            ready = true;
            setState("Connected to " + g.getDevice().getAddress());
            log("Ready");
            updateButtons();
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic ch, byte[] value) {
            if (STATUS.equals(ch.getUuid())) showStatus(value);
        }

        @Override
        public void onCharacteristicWrite(BluetoothGatt g, BluetoothGattCharacteristic ch, int status) {
            busy = false;
            log(status == BluetoothGatt.GATT_SUCCESS ? "Sent" : "Send failed (" + status + ")");
            updateButtons();
        }
    };

    private void send(byte cmd, String what) {
        send(new byte[]{cmd}, what);
    }

    private void send(byte[] cmd, String what) {
        if (!ready || busy || gatt == null) return;
        busy = true;
        updateButtons();
        int r = gatt.writeCharacteristic(triggerChar, cmd,
                BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
        if (r != BluetoothStatusCodes.SUCCESS) {
            busy = false;
            log("Could not send " + what + " (" + r + ")");
            updateButtons();
        } else {
            log("Sending " + what);
        }
    }
}
