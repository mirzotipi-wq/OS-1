#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Generate original, legally redistributable OS-1 visual assets.

Produces:
  1. Original 1920x1080 PNG wallpapers (`os1-horizon-light.png`, `os1-horizon-dark.png`)
     rendered deterministically with pure Python stdlib (no external image deps).
  2. Original OS-1 geometric logo SVG (`os1-logo.svg`) for the top-left OS-1 menu.
  3. Original KWin Aurorae window decoration SVG theme (`OS1Sequoia`) with
     left-aligned traffic-light window controls (close, minimize, maximize).

All generated artwork is 100% original OS-1 IP (zero third-party/Apple assets).
"""

import math
import os
import struct
import sys
import zlib


def write_png_rgb(path: str, width: int, height: int, rgb_bytes: bytes) -> None:
    def chunk(ctype: bytes, data: bytes) -> bytes:
        c = ctype + data
        return struct.pack("!I", len(data)) + c + struct.pack("!I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)
    stride = width * 3
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        rows.extend(rgb_bytes[y * stride : (y + 1) * stride])
    idat = zlib.compress(bytes(rows), level=6)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", idat))
        f.write(chunk(b"IEND", b""))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def render_horizon_wallpaper(path: str, dark: bool, width: int = 1920, height: int = 1080) -> None:
    """Render an original layered alpine horizon & sky gradient wallpaper."""
    # Precompute ridge profiles across x for speed
    ridge1 = [0.0] * width
    ridge2 = [0.0] * width
    ridge3 = [0.0] * width
    for x in range(width):
        nx = x / width
        ridge1[x] = 0.56 + 0.06 * math.sin(nx * 5.2 + 0.4) + 0.025 * math.sin(nx * 13.0)
        ridge2[x] = 0.67 + 0.05 * math.sin(nx * 6.8 + 2.1) + 0.02 * math.cos(nx * 17.0)
        ridge3[x] = 0.78 + 0.04 * math.sin(nx * 4.5 + 4.0) + 0.015 * math.sin(nx * 11.0)

    if not dark:
        # Sunlit Alpine Morning (OS-1 Light)
        sky_top = (42, 108, 186)
        sky_mid = (118, 178, 228)
        sky_bot = (242, 206, 178)
        r1_col = (74, 114, 158)
        r2_col = (48, 82, 122)
        r3_col = (28, 52, 84)
        sun_cx, sun_cy = 0.72, 0.34
        sun_col = (255, 240, 210)
    else:
        # Twilight Sequoia Aurora (OS-1 Dark)
        sky_top = (14, 22, 48)
        sky_mid = (36, 48, 92)
        sky_bot = (84, 58, 108)
        r1_col = (34, 44, 78)
        r2_col = (22, 30, 56)
        r3_col = (12, 18, 34)
        sun_cx, sun_cy = 0.32, 0.32
        sun_col = (80, 175, 220)

    buf = bytearray(width * height * 3)
    idx = 0
    for y in range(height):
        ny = y / height
        if ny < 0.55:
            t = ny / 0.55
            sr = lerp(sky_top[0], sky_mid[0], t)
            sg = lerp(sky_top[1], sky_mid[1], t)
            sb = lerp(sky_top[2], sky_mid[2], t)
        else:
            t = (ny - 0.55) / 0.45
            sr = lerp(sky_mid[0], sky_bot[0], t)
            sg = lerp(sky_mid[1], sky_bot[1], t)
            sb = lerp(sky_mid[2], sky_bot[2], t)

        dy = (ny - sun_cy) * (height / width)
        dy2 = dy * dy

        for x in range(width):
            if ny >= ridge3[x]:
                d = min(1.0, (ny - ridge3[x]) * 4.0)
                r = int(lerp(r3_col[0] + 10, r3_col[0], d))
                g = int(lerp(r3_col[1] + 10, r3_col[1], d))
                b = int(lerp(r3_col[2] + 12, r3_col[2], d))
            elif ny >= ridge2[x]:
                d = min(1.0, (ny - ridge2[x]) * 4.5)
                r = int(lerp(r2_col[0] + 12, r2_col[0], d))
                g = int(lerp(r2_col[1] + 12, r2_col[1], d))
                b = int(lerp(r2_col[2] + 14, r2_col[2], d))
            elif ny >= ridge1[x]:
                d = min(1.0, (ny - ridge1[x]) * 5.0)
                r = int(lerp(r1_col[0] + 14, r1_col[0], d))
                g = int(lerp(r1_col[1] + 14, r1_col[1], d))
                b = int(lerp(r1_col[2] + 16, r1_col[2], d))
            else:
                dx = (x / width) - sun_cx
                glow = math.exp(-(dx * dx + dy2) * 14.0) * 0.42
                r = int(min(255, lerp(sr, sun_col[0], glow)))
                g = int(min(255, lerp(sg, sun_col[1], glow)))
                b = int(min(255, lerp(sb, sun_col[2], glow)))

            buf[idx] = r
            buf[idx + 1] = g
            buf[idx + 2] = b
            idx += 3

    write_png_rgb(path, width, height, bytes(buf))


def write_os1_logo_svg(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="os1g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0A84FF"/>
      <stop offset="100%" stop-color="#5E5CE6"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="56" height="56" rx="16" fill="url(#os1g)"/>
  <circle cx="32" cy="32" r="18" fill="none" stroke="#FFFFFF" stroke-width="3.5" opacity="0.92"/>
  <path d="M32 20 L32 44 M27 25 L32 20" fill="none" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


def write_aurorae_theme(theme_dir: str) -> None:
    """Create original OS1Sequoia Aurorae KWin window decoration with left traffic lights."""
    os.makedirs(theme_dir, exist_ok=True)

    with open(os.path.join(theme_dir, "metadata.desktop"), "w", encoding="utf-8") as f:
        f.write(
            """[Desktop Entry]
Name=OS1Sequoia
Comment=Original OS-1 window decoration with left-aligned traffic-light controls
X-KDE-PluginInfo-Author=OS-1 Project
X-KDE-PluginInfo-License=GPL-2.0-only
X-KDE-PluginInfo-Name=OS1Sequoia
X-KDE-PluginInfo-Version=1.0
"""
        )

    with open(os.path.join(theme_dir, "OS1Sequoiarc"), "w", encoding="utf-8") as f:
        f.write(
            """[General]
TitleAlignment=Center
TitleVerticalAlignment=Center
TitleEdgeTop=6
TitleEdgeBottom=4
TitleEdgeLeft=10
TitleEdgeRight=10
TitleHeight=28
ButtonWidth=16
ButtonHeight=16
ButtonSpacing=8
ButtonMarginTop=6
ExplicitButtonSpacer=8
PaddingTop=0
PaddingBottom=0
PaddingLeft=0
PaddingRight=0
BorderLeft=1
BorderRight=1
BorderBottom=1
BorderTop=28
Shadow=true
ActiveTextColor=29,29,31
InactiveTextColor=110,110,115
"""
        )

    def button_svg(filename: str, fill: str, stroke: str, glyph: str) -> None:
        svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="80" height="16" viewBox="0 0 80 16">
  <g id="active-center" transform="translate(0,0)">
    <circle cx="8" cy="8" r="6" fill="{fill}" stroke="{stroke}" stroke-width="0.8"/>
  </g>
  <g id="hover-center" transform="translate(16,0)">
    <circle cx="8" cy="8" r="6" fill="{fill}" stroke="{stroke}" stroke-width="0.8"/>
    {glyph}
  </g>
  <g id="pressed-center" transform="translate(32,0)">
    <circle cx="8" cy="8" r="6" fill="{stroke}" stroke="{stroke}" stroke-width="0.8"/>
    {glyph}
  </g>
  <g id="inactive-center" transform="translate(48,0)">
    <circle cx="8" cy="8" r="6" fill="#C7C7CC" stroke="#AEAEB2" stroke-width="0.8"/>
  </g>
  <g id="deactivated-center" transform="translate(64,0)">
    <circle cx="8" cy="8" r="6" fill="#C7C7CC" stroke="#AEAEB2" stroke-width="0.8"/>
  </g>
</svg>
"""
        with open(os.path.join(theme_dir, filename), "w", encoding="utf-8") as f:
            f.write(svg)

    button_svg(
        "close.svg",
        "#FF5F57",
        "#E0443E",
        '<path d="M5.5 5.5 L10.5 10.5 M10.5 5.5 L5.5 10.5" stroke="#4D0000" stroke-width="1.3" stroke-linecap="round"/>',
    )
    button_svg(
        "minimize.svg",
        "#FEBC2E",
        "#D89E24",
        '<path d="M5 8 L11 8" stroke="#6B4400" stroke-width="1.4" stroke-linecap="round"/>',
    )
    button_svg(
        "maximize.svg",
        "#28C840",
        "#1AAB29",
        '<path d="M5.5 10.5 L10.5 5.5 M7 5.5 L10.5 5.5 L10.5 9" fill="none" stroke="#004D0E" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    )
    button_svg(
        "restore.svg",
        "#28C840",
        "#1AAB29",
        '<path d="M5.5 10.5 L10.5 5.5" stroke="#004D0E" stroke-width="1.2" stroke-linecap="round"/>',
    )

    decoration_svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
  <rect id="decoration-center" x="10" y="28" width="100" height="82" fill="#F5F5F7"/>
  <path id="decoration-topleft" d="M0,10 Q0,0 10,0 L10,28 L0,28 Z" fill="#ECECEE"/>
  <rect id="decoration-top" x="10" y="0" width="100" height="28" fill="#ECECEE"/>
  <path id="decoration-topright" d="M110,0 Q120,0 120,10 L120,28 L110,28 Z" fill="#ECECEE"/>
  <rect id="decoration-left" x="0" y="28" width="10" height="82" fill="#D1D1D6"/>
  <rect id="decoration-right" x="110" y="28" width="10" height="82" fill="#D1D1D6"/>
  <rect id="decoration-bottomleft" x="0" y="110" width="10" height="10" fill="#D1D1D6"/>
  <rect id="decoration-bottom" x="10" y="110" width="100" height="10" fill="#D1D1D6"/>
  <rect id="decoration-bottomright" x="110" y="110" width="10" height="10" fill="#D1D1D6"/>
</svg>
"""
    with open(os.path.join(theme_dir, "decoration.svg"), "w", encoding="utf-8") as f:
        f.write(decoration_svg)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <target-rootfs-usr-share-dir>", file=sys.stderr)
        return 2
    usr_share = sys.argv[1]

    wp_dir = os.path.join(usr_share, "wallpapers", "OS1Horizon", "contents", "images")
    render_horizon_wallpaper(os.path.join(wp_dir, "1920x1080.png"), dark=False)
    render_horizon_wallpaper(os.path.join(wp_dir, "1920x1080-dark.png"), dark=True)

    os.makedirs(os.path.join(usr_share, "wallpapers", "OS1Horizon"), exist_ok=True)
    with open(os.path.join(usr_share, "wallpapers", "OS1Horizon", "metadata.json"), "w", encoding="utf-8") as f:
        f.write(
            """{
  "KPlugin": {
    "Id": "OS1Horizon",
    "Name": "OS-1 Horizon",
    "License": "GPL-2.0-only",
    "Authors": [{ "Name": "OS-1 Project" }]
  }
}
"""
        )

    write_os1_logo_svg(os.path.join(usr_share, "icons", "hicolor", "scalable", "apps", "os1-logo.svg"))
    write_os1_logo_svg(os.path.join(usr_share, "pixmaps", "os1-logo.svg"))
    write_aurorae_theme(os.path.join(usr_share, "aurorae", "themes", "OS1Sequoia"))

    print(f"[os1-branding] Generated OS-1 wallpapers, logo SVG, and OS1Sequoia Aurorae theme in {usr_share}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
