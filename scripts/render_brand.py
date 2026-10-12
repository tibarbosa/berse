"""Render the integration's small vector mark into Home Assistant PNG assets."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components" / "barbs_erse" / "brand"
SIZE = 1024
SCALE = SIZE // 512


def scaled(points):
    return [(round(x * SCALE), round(y * SCALE)) for x, y in points]


def render(size: int) -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    dark = "#10263D"
    teal = "#62DEC8"
    gold = "#FFC857"
    white = "#F4FAFF"
    draw.ellipse((32 * SCALE, 32 * SCALE, 480 * SCALE, 480 * SCALE), fill=dark)
    draw.ellipse((32 * SCALE, 32 * SCALE, 480 * SCALE, 480 * SCALE), outline=teal, width=18 * SCALE)
    draw.polygon(
        scaled([(256, 79), (155, 267), (232, 267), (203, 433), (357, 208), (276, 208), (315, 79)]),
        fill=gold,
    )
    for x, y, width, height in ((94, 347, 42, 56), (153, 319, 42, 84), (212, 293, 42, 110)):
        draw.rounded_rectangle(
            (x * SCALE, y * SCALE, (x + width) * SCALE, (y + height) * SCALE),
            radius=9 * SCALE,
            fill=white,
        )
    draw.line(scaled([(302, 403), (421, 403)]), fill=teal, width=15 * SCALE)
    image = image.resize((size, size), Image.Resampling.LANCZOS)
    return image


def main() -> None:
    BRAND.mkdir(parents=True, exist_ok=True)
    render(256).save(BRAND / "icon.png", optimize=True)
    render(512).save(BRAND / "icon@2x.png", optimize=True)


if __name__ == "__main__":
    main()
