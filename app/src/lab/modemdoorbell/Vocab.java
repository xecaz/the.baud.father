package lab.modemdoorbell;

import android.content.Context;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The box's vocabulary: words it can say in any order (notes/ble.md "Say"). The list is tools/vocab.txt, packed into
 * the app as an asset by build.sh; a word's number is its position there. Same rules as tools/vocab.py.
 * The app sends 0x40 followed by the word numbers.
 */
final class Vocab {
    static final byte CMD_SAY = 0x40;
    static final int MAX_WORDS = 16;   // SAY_MAX_WORDS in firmware/main/config.h

    private static final String[] ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
            + "fourteen fifteen sixteen seventeen eighteen nineteen").split(" ");
    private static final String[] TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split(" ");
    private static final Pattern NUMBER = Pattern.compile("(-?)(\\d{1,6})(?:\\.(\\d+))?(%?)");

    private static List<String> names;            // index = word number
    private static Map<String, Integer> index;

    private Vocab() {}

    /** A sentence that cannot be said; the message is for the user. */
    static final class Unknown extends Exception {
        private static final long serialVersionUID = 1;

        Unknown(String msg) {
            super(msg);
        }
    }

    private static synchronized void load(Context c) {
        if (names != null) return;
        List<String> list = new ArrayList<>();
        Map<String, Integer> map = new HashMap<>();
        try (BufferedReader r = new BufferedReader(
                new InputStreamReader(c.getAssets().open("vocab.txt"), StandardCharsets.UTF_8))) {
            for (String line; (line = r.readLine()) != null; ) {
                int hash = line.indexOf('#');
                if (hash >= 0) line = line.substring(0, hash);
                int eq = line.indexOf('=');
                if (eq < 0) continue;
                String name = line.substring(0, eq).trim();
                if (name.isEmpty()) continue;
                map.put(name, list.size());
                list.add(name);
            }
        } catch (IOException e) {
            android.util.Log.w(RingSender.TAG, "vocabulary not readable: " + e);
        }
        names = list;
        index = map;
    }

    /** The words, in the box's order, without the pause. */
    static String words(Context c) {
        load(c);
        StringBuilder b = new StringBuilder();
        for (String n : names) {
            if (n.equals("pause")) continue;
            if (b.length() > 0) b.append("  ");
            b.append(n);
        }
        return b.toString();
    }

    private static void number(int n, List<String> out) {
        if (n < 20) {
            out.add(ONES[n]);
        } else if (n < 100) {
            out.add(TENS[n / 10 - 2]);
            if (n % 10 != 0) out.add(ONES[n % 10]);
        } else if (n < 1000) {
            out.add(ONES[n / 100]);
            out.add("hundred");
            if (n % 100 != 0) number(n % 100, out);
        } else {
            number(n / 1000, out);
            out.add("thousand");
            if (n % 1000 != 0) number(n % 1000, out);
        }
    }

    private static String alias(String tok) {
        switch (tok) {
            case "%": return "percent";
            case "e-mail": return "email";
            case "o'clock": return "oclock";
            case "okay": return "ok";
            case ",": return "pause";
            case "-": return "minus";
            default: return tok;
        }
    }

    /** "3 new messages" -> the words as the box will say them ("three new messages"). */
    static List<String> spell(Context c, String text) throws Unknown {
        load(c);
        List<String> out = new ArrayList<>();
        for (String tok : text.toLowerCase(java.util.Locale.ROOT).replace(",", " , ").trim().split("\\s+")) {
            if (tok.isEmpty()) continue;
            tok = alias(tok);
            Matcher m = NUMBER.matcher(tok);
            if (m.matches()) {
                if (!m.group(1).isEmpty()) out.add("minus");
                number(Integer.parseInt(m.group(2)), out);
                if (m.group(3) != null) {
                    out.add("point");
                    for (char d : m.group(3).toCharArray()) out.add(ONES[d - '0']);
                }
                if (!m.group(4).isEmpty()) out.add("percent");
            } else {
                out.add(tok.replaceAll("[.!?]+$", ""));
            }
        }
        StringBuilder missing = new StringBuilder();
        for (String w : out) {
            if (!index.containsKey(w) && missing.indexOf("\"" + w + "\"") < 0) {
                missing.append(missing.length() > 0 ? ", " : "").append('"').append(w).append('"');
            }
        }
        if (missing.length() > 0) throw new Unknown("The box does not know " + missing);
        if (out.isEmpty()) throw new Unknown("Nothing to say");
        if (out.size() > MAX_WORDS) throw new Unknown(out.size() + " words: the box takes " + MAX_WORDS + " at a time");
        return out;
    }

    /** The bytes to write to the trigger: 0x40, then one byte per word. */
    static byte[] command(Context c, List<String> words) {
        load(c);
        byte[] b = new byte[1 + words.size()];
        b[0] = CMD_SAY;
        for (int i = 0; i < words.size(); i++) b[1 + i] = (byte) (int) index.get(words.get(i));
        return b;
    }
}
