#!/usr/bin/env python3
"""Export the supplied hover GIF as two cropped SVG masks (local tool; Pillow).

Run after replacing the source animation. The committed masks are web assets;
the site build only copies them and does not need Pillow. Eight opacity levels
retain the source edges while allowing CSS to color the mark for either theme.
"""

from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/logo/animated/Logo - Hover_Mini.gif"
BOX = (116, 97, 186, 185)
FRAMES = 16


def main():
    source = Image.open(SOURCE)
    if source.size != (300, 300) or source.n_frames != FRAMES:
        raise ValueError("Review crop and playback timing for the new animation")
    width, height = BOX[2] - BOX[0], BOX[3] - BOX[1]
    layers = {"mark": [], "book": []}
    for index in range(FRAMES):
        source.seek(index)
        if source.info.get("duration") != 70:
            raise ValueError("Playback expects 70 ms per frame")
        pixels = source.convert("RGB")
        paths = {layer: {level: [] for level in range(1, 9)} for layer in layers}
        for y in range(height):
            row = []
            for x in range(width):
                r, g, b = pixels.getpixel((x + BOX[0], y + BOX[1]))
                # The source has charcoal lettering and gold pages on ivory.
                layer = "book" if r - b > 12 else "mark"
                background, foreground = (248, 27) if layer == "book" else (251, 30)
                value = b if layer == "book" else g
                alpha = max(0, min(1, (background - value) / (background - foreground)))
                row.append((layer, round(alpha * 8)))
            start = 0
            while start < width:
                layer, level = row[start]
                end = start + 1
                while end < width and row[end] == row[start]:
                    end += 1
                if level:
                    paths[layer][level].append(
                        f"M{start} {y + index * height}h{end-start}v1h-{end-start}z"
                    )
                start = end
        for layer in layers:
            for level, runs in paths[layer].items():
                if runs:
                    layers[layer].append(
                        f'<path opacity="{level/8:g}" d="{"".join(runs)}"/>'
                    )
    for layer, paths in layers.items():
        output = ROOT / f"assets/logo/hover-{layer}.svg"
        output.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height*FRAMES}">'
            + "".join(paths) + "</svg>\n", encoding="utf-8"
        )
        print(f"{output.relative_to(ROOT)}: {output.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
