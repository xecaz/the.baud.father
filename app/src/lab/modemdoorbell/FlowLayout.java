package lab.modemdoorbell;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;

/** Children left to right, wrapping to the next line when the width runs out (the word buttons of the Say dialog). */
final class FlowLayout extends ViewGroup {
    private final int gap;

    FlowLayout(Context c, int gapPx) {
        super(c);
        gap = gapPx;
    }

    @Override
    protected void onMeasure(int widthSpec, int heightSpec) {
        final int width = MeasureSpec.getSize(widthSpec);
        final boolean bounded = MeasureSpec.getMode(widthSpec) != MeasureSpec.UNSPECIFIED;
        int x = 0, y = 0, line = 0, widest = 0;
        for (int i = 0; i < getChildCount(); i++) {
            View v = getChildAt(i);
            if (v.getVisibility() == GONE) continue;
            v.measure(bounded ? MeasureSpec.makeMeasureSpec(width, MeasureSpec.AT_MOST) : widthSpec,
                    MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED));
            if (bounded && x > 0 && x + v.getMeasuredWidth() > width) {
                x = 0;
                y += line + gap;
                line = 0;
            }
            x += v.getMeasuredWidth() + gap;
            line = Math.max(line, v.getMeasuredHeight());
            widest = Math.max(widest, x - gap);
        }
        setMeasuredDimension(bounded ? width : widest, resolveSize(y + line, heightSpec));
    }

    @Override
    protected void onLayout(boolean changed, int l, int t, int r, int b) {
        final int width = r - l;
        int x = 0, y = 0, line = 0;
        for (int i = 0; i < getChildCount(); i++) {
            View v = getChildAt(i);
            if (v.getVisibility() == GONE) continue;
            if (x > 0 && x + v.getMeasuredWidth() > width) {
                x = 0;
                y += line + gap;
                line = 0;
            }
            v.layout(x, y, x + v.getMeasuredWidth(), y + v.getMeasuredHeight());
            x += v.getMeasuredWidth() + gap;
            line = Math.max(line, v.getMeasuredHeight());
        }
    }
}
