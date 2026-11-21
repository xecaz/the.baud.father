#!/usr/bin/env bash
# Build the Doorbell app with the Android SDK build-tools only: no Gradle, no dependencies.
# Output: app/build/doorbell.apk (signed with the standard debug key).
# Install: adb install -r app/build/doorbell.apk
set -euo pipefail

cd "$(dirname "$0")"
SDK="${ANDROID_HOME:-$HOME/Android/Sdk}"
BT="$SDK/build-tools/36.1.0"
JAR="$SDK/platforms/android-36/android.jar"
KS="${KEYSTORE:-$HOME/.android/debug.keystore}"
MIN_SDK=33      # Android 13: the newer BluetoothGatt write/read APIs
TARGET_SDK=36

rm -rf build
mkdir -p build/classes build/dex

echo "[1/5] icon, resources, manifest -> base apk"
# Launcher icon foreground from icon.svg: square background (no rounded corners), art at 66 % in the adaptive safe zone.
mkdir -p build/res/mipmap-xxxhdpi
cp -r res/. build/res/
python3 -I - <<'PYEOF'
import re
s = open("icon.svg").read()
cut = s.index("</defs>") + len("</defs>")
head, body = s[:cut], s[cut:s.rindex("</svg>")]
body = re.sub(r'<rect width="512" height="512" rx="96" fill="url\(#(bg|glow)\)"/>', "", body)
fg = (head + '<rect width="512" height="512" fill="url(#bg)"/><rect width="512" height="512" fill="url(#glow)"/>'
      '<g transform="translate(256 256) scale(0.66) translate(-256 -256)">' + body + "</g></svg>")
open("build/icon_fg.svg", "w").write(fg)
PYEOF
rsvg-convert -w 432 -h 432 -o build/res/mipmap-xxxhdpi/ic_launcher_fg.png build/icon_fg.svg
"$BT/aapt2" compile --dir build/res -o build/res.zip
# The box's vocabulary (tools/vocab.txt) as an asset: Vocab.java reads it, so the app and the box share one list.
mkdir -p build/assets
cp ../tools/vocab.txt build/assets/vocab.txt
"$BT/aapt2" link -o build/base.apk -I "$JAR" --manifest AndroidManifest.xml build/res.zip -A build/assets \
    --min-sdk-version "$MIN_SDK" --target-sdk-version "$TARGET_SDK"

echo "[2/5] javac"
javac --release 11 -Xlint:all -Xlint:-options -classpath "$JAR" -d build/classes \
    $(find src -name '*.java')

echo "[3/5] d8"
"$BT/d8" --release --min-api "$MIN_SDK" --lib "$JAR" --output build/dex \
    $(find build/classes -name '*.class')

echo "[4/5] add classes.dex, zipalign"
python3 -I - <<'EOF'
import shutil, zipfile
shutil.copy("build/base.apk", "build/unsigned.apk")
with zipfile.ZipFile("build/unsigned.apk", "a", zipfile.ZIP_DEFLATED) as z:
    z.write("build/dex/classes.dex", "classes.dex")
EOF
"$BT/zipalign" -p -f 4 build/unsigned.apk build/aligned.apk

echo "[5/5] sign"
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:android --ks-key-alias androiddebugkey \
    --key-pass pass:android --out build/doorbell.apk build/aligned.apk
"$BT/apksigner" verify build/doorbell.apk
echo "built: app/build/doorbell.apk"
