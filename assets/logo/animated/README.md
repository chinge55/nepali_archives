# Source logo animations

The original GIF exports are preserved here. They include opening and closing
sequences, plus the small hover sequence used by the site header.

The header uses `../hover-mark.svg` and `../hover-book.svg`: two transparent,
cropped SVG frame strips derived from `Logo - Hover_Mini.gif`. Each strip contains
16 frames, 70 × 88 source pixels per frame. CSS colors the letter and pages for
light and dark themes. The playback controller uses the original 70 ms frame
duration, plays once on mouse hover or keyboard focus, and restores frame zero.
Reduced-motion preferences and JavaScript-free reading use the still first frame.

To regenerate the masks after changing the source, run
`python3 pipeline/prepare_logo.py` from the repository root with Pillow installed.
If frame dimensions or timing change, review the crop, CSS sizing and controller
together. This is a local asset preparation step; deployment copies the committed
SVG files and does not require Pillow.

The opening and closing GIFs are retained as source artwork and are not loaded by
the reader. The existing PNGs remain the fallback for browsers without CSS masks
and supply the favicons.
