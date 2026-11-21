package lab.modemdoorbell;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.BluetoothStatusCodes;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import java.util.concurrent.atomic.AtomicBoolean;

/**
 * One-shot "ring" from the background: connect to the bonded box, write 0x01 (or 0x03 for internet calls) to
 * Trigger, disconnect.
 * No scan (the box is already bonded, found by name among bonded devices), no UI.
 */
final class RingSender {
    static final String TAG = "Doorbell";
    static final long TIMEOUT_MS = 9000;   // stay inside the ~10 s a goAsync() receiver gets

    static final long DEDUPE_MS = 20000;   // a regular call fires both detectors; ring once
    private static long lastRingMs;

    private RingSender() {}

    static BluetoothDevice findBondedBox(BluetoothAdapter adapter) {
        for (BluetoothDevice d : adapter.getBondedDevices()) {
            if (MainActivity.DEVICE_NAME.equals(d.getName())) return d;
        }
        return null;
    }

    /** Sends one ring; calls done exactly once (on the main thread) when finished or timed out. */
    static void send(Context ctx, String reason, Runnable done) {
        send(ctx, reason, MainActivity.CMD_RING, done);
    }

    static void send(Context ctx, String reason, byte cmd, Runnable done) {
        send(ctx, reason, cmd, true, done);
    }

    static final long MESSAGE_GAP_MS = 1000;   // message sounds at least this far apart (the box queues them; it drops writes of one link < 250 ms apart)
    private static long lastAnyMs;

    /** call = a call ring (deduped against other call rings only); otherwise a message sound (dropped only if something was sent within the last second: the box queues the rest). */
    static void send(Context ctx, String reason, byte cmd, boolean call, Runnable done) {
        send(ctx, reason, new byte[]{cmd}, call, done);
    }

    /** cmd: the whole trigger write (one command byte, or 0x40 and the words of a sentence). */
    static void send(Context ctx, String reason, byte[] cmd, boolean call, Runnable done) {
        Context app = ctx.getApplicationContext();
        if (app.checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            Log.w(TAG, "ring (" + reason + "): no BLUETOOTH_CONNECT permission");
            done.run();
            return;
        }
        BluetoothAdapter adapter = app.getSystemService(BluetoothManager.class).getAdapter();
        if (adapter == null || !adapter.isEnabled()) {
            Log.w(TAG, "ring (" + reason + "): Bluetooth is off");
            done.run();
            return;
        }
        BluetoothDevice box = findBondedBox(adapter);
        if (box == null) {
            Log.w(TAG, "ring (" + reason + "): no bonded \"" + MainActivity.DEVICE_NAME + "\"");
            done.run();
            return;
        }

        long now = android.os.SystemClock.elapsedRealtime();
        synchronized (RingSender.class) {
            long last = call ? lastRingMs : lastAnyMs;
            if (last != 0 && now - last < (call ? DEDUPE_MS : MESSAGE_GAP_MS)) {
                Log.i(TAG, "ring (" + reason + "): skipped, rang " + (now - last) / 1000 + " s ago");
                done.run();
                return;
            }
            if (call) lastRingMs = now;
            lastAnyMs = now;
        }
        Handler main = new Handler(Looper.getMainLooper());
        AtomicBoolean finished = new AtomicBoolean(false);
        BluetoothGatt[] gatt = new BluetoothGatt[1];
        Runnable finish = () -> main.post(() -> {
            if (!finished.compareAndSet(false, true)) return;
            main.removeCallbacksAndMessages(null);
            if (gatt[0] != null) {
                gatt[0].disconnect();
                gatt[0].close();
            }
            done.run();
        });
        main.postDelayed(() -> {
            Log.w(TAG, "ring (" + reason + "): timed out");
            finish.run();
        }, TIMEOUT_MS);

        Log.i(TAG, "ring (" + reason + "): connecting to " + box.getAddress());
        gatt[0] = box.connectGatt(app, false, new BluetoothGattCallback() {
            @Override
            public void onConnectionStateChange(BluetoothGatt g, int status, int newState) {
                if (newState == BluetoothProfile.STATE_CONNECTED) {
                    g.discoverServices();
                } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                    Log.i(TAG, "ring (" + reason + "): disconnected (status " + status + ")");
                    finish.run();
                }
            }

            @Override
            public void onServicesDiscovered(BluetoothGatt g, int status) {
                BluetoothGattService svc = g.getService(MainActivity.SERVICE);
                BluetoothGattCharacteristic trig = svc == null ? null : svc.getCharacteristic(MainActivity.TRIGGER);
                if (trig == null) {
                    Log.w(TAG, "ring (" + reason + "): doorbell service not found");
                    finish.run();
                    return;
                }
                int r = g.writeCharacteristic(trig, cmd,
                        BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
                if (r != BluetoothStatusCodes.SUCCESS) {
                    Log.w(TAG, "ring (" + reason + "): write refused (" + r + ")");
                    finish.run();
                }
            }

            @Override
            public void onCharacteristicWrite(BluetoothGatt g, BluetoothGattCharacteristic ch, int status) {
                Log.i(TAG, "ring (" + reason + "): " + (status == BluetoothGatt.GATT_SUCCESS ? "sent" : "write failed " + status));
                finish.run();
            }
        }, BluetoothDevice.TRANSPORT_LE);
    }
}
