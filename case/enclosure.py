#!/usr/bin/env python3
"""
Laser-cut enclosure generator for e-ink camera.

Boxes.py-inspired construction: burn compensation, corner relief,
finger joints on all mating edges, hinged back plate.

Run: python3 enclosure.py
Output: enclosure_YYYYMMDD_HHMMSS.svg (+ enclosure_latest.svg)
"""

import math
import os
from datetime import datetime

# ============================================================
# INPUTS — tweak these to change the enclosure
# ============================================================

# --- Material & Fabrication ---
T = 3.0           # material thickness (mm)
BURN = 0.1        # laser kerf compensation (mm) — holes shrink, tabs grow
RELIEF_R = 0.5    # corner relief radius (mm)
TAB_W = 12.0      # target finger joint tab width (mm)

# --- Box size (internal mm) ---
W = 144           # internal width  (panel 127.6 + 8.2mm border each side)
D = 29            # internal depth  (display + Pi stack + cables)

# --- Vertical layout (mm, top to bottom inside the box) ---
CAM_ZONE = 43     # space above display for camera module
BOTTOM_BORDER = 12.2  # border below display

# --- Display viewport (7.8" e-ink active area) ---
DISP_W = 119.0    # active area width in portrait + tolerance
DISP_H = 159.0    # active area height in portrait + tolerance
DISP_R = 2.0      # window corner radius

# --- Camera ---
CAM_D = 8.0       # hole diameter (lens barrel ~7mm + clearance)
CAM_CY = 14.0     # center distance from top internal edge

# --- Button (right wall) ---
BTN_D = 12.0      # panel hole diameter

# --- USB-C cutout (bottom wall) ---
USB_W = 12.0
USB_H = 7.0

# --- Pi 5 mounting (back plate) ---
PI_HOLE_D = 2.5       # M2.5 holes
PI_HOLE_SPACING_X = 58.0
PI_HOLE_SPACING_Y = 49.0
PI_HOLE_INSET_X = 3.5
PI_HOLE_INSET_Y = 3.5

# ============================================================
# DERIVED — computed from inputs above
# ============================================================

H = CAM_ZONE + DISP_H + BOTTOM_BORDER    # internal height
OW = W + 2 * T                            # outer width
OH = H + 2 * T                            # outer height
BACK_W = OW
BACK_H = OH

# Display window position (centered horizontally, below camera zone)
DISP_CX = W / 2
DISP_CY = CAM_ZONE + DISP_H / 2

# Camera position (centered horizontally)
CAM_CX = W / 2

# SVG layout
SPACING = 15


# ============================================================
# Utility functions
# ============================================================

def fmt(v):
    """Format a float for SVG, removing trailing zeros."""
    return f"{v:.3f}".rstrip('0').rstrip('.')


def burn_offset(nominal, is_hole):
    """Apply burn compensation. Holes shrink, tabs/outer features grow."""
    if is_hole:
        return nominal - 2 * BURN
    return nominal + 2 * BURN


def corner_relief(cx, cy):
    """SVG path for a corner relief semicircle at an inside corner."""
    r = RELIEF_R
    return (f"M{fmt(cx - r)},{fmt(cy)} "
            f"A{fmt(r)},{fmt(r)} 0 1,1 {fmt(cx + r)},{fmt(cy)} "
            f"A{fmt(r)},{fmt(r)} 0 1,1 {fmt(cx - r)},{fmt(cy)}Z")


def circle_path(cx, cy, d, is_hole=True):
    """SVG path for a circle. Apply burn compensation."""
    r = burn_offset(d, is_hole) / 2
    return (f"M{fmt(cx - r)},{fmt(cy)} "
            f"A{fmt(r)},{fmt(r)} 0 1,0 {fmt(cx + r)},{fmt(cy)} "
            f"A{fmt(r)},{fmt(r)} 0 1,0 {fmt(cx - r)},{fmt(cy)}Z")


def rounded_rect_path(cx, cy, w, h, r, is_hole=True):
    """SVG path for a rounded rectangle centered at (cx, cy)."""
    if is_hole:
        w = w - 2 * BURN
        h = h - 2 * BURN
    else:
        w = w + 2 * BURN
        h = h + 2 * BURN
    r = max(0, min(r, w / 2, h / 2))
    x0, y0 = cx - w / 2, cy - h / 2
    x1, y1 = cx + w / 2, cy + h / 2
    return (f"M{fmt(x0 + r)},{fmt(y0)} "
            f"L{fmt(x1 - r)},{fmt(y0)} A{fmt(r)},{fmt(r)} 0 0,1 {fmt(x1)},{fmt(y0 + r)} "
            f"L{fmt(x1)},{fmt(y1 - r)} A{fmt(r)},{fmt(r)} 0 0,1 {fmt(x1 - r)},{fmt(y1)} "
            f"L{fmt(x0 + r)},{fmt(y1)} A{fmt(r)},{fmt(r)} 0 0,1 {fmt(x0)},{fmt(y1 - r)} "
            f"L{fmt(x0)},{fmt(y0 + r)} A{fmt(r)},{fmt(r)} 0 0,1 {fmt(x0 + r)},{fmt(y0)}Z")


def rect_cutout(cx, cy, w, h):
    """SVG path for a rectangular hole (burn-compensated inward)."""
    w = w - 2 * BURN
    h = h - 2 * BURN
    x, y = cx - w / 2, cy - h / 2
    return (f"M{fmt(x)},{fmt(y)} L{fmt(x + w)},{fmt(y)} "
            f"L{fmt(x + w)},{fmt(y + h)} L{fmt(x)},{fmt(y + h)}Z")


# ============================================================
# Finger joint generation
# ============================================================

def calc_fingers(length, tab_width=TAB_W):
    """Calculate number of fingers for an edge. Always odd count,
    starting and ending with a gap (no-tab) so corners stay solid."""
    n = max(3, round(length / tab_width))
    if n % 2 == 0:
        n += 1
    seg_w = length / n
    return n, seg_w


def finger_tab_edge(x1, y1, x2, y2):
    """Edge with tabs protruding outward (for walls mating into front plate slots).
    Tabs are at odd indices (1, 3, 5...). Even indices are gaps (baseline)."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    # Perpendicular pointing outward (for CW winding)
    px, py = dy / length, -dx / length

    n, seg_w = calc_fingers(length)
    b = BURN  # burn compensation

    segs = []
    for i in range(n):
        s_start = i * seg_w
        s_end = (i + 1) * seg_w

        sx = x1 + ux * s_start
        sy = y1 + uy * s_start
        ex = x1 + ux * s_end
        ey = y1 + uy * s_end

        if i % 2 == 1:
            # Tab: extend outward by T, widen by burn on each side
            tab_sx = sx[0] if isinstance(sx, tuple) else sx
            # Tab start: move back by burn along edge, then out by T
            tsx = sx - ux * b + px * T
            tsy = sy - uy * b + py * T
            tex = ex + ux * b + px * T
            tey = ey + uy * b + py * T
            ex2 = ex + ux * b
            ey2 = ey + uy * b
            sx2 = sx - ux * b
            sy2 = sy - uy * b

            segs.append(f"L{fmt(sx2)},{fmt(sy2)}")
            segs.append(f"L{fmt(tsx)},{fmt(tsy)}")
            segs.append(f"L{fmt(tex)},{fmt(tey)}")
            segs.append(f"L{fmt(ex2)},{fmt(ey2)}")
        else:
            segs.append(f"L{fmt(ex)},{fmt(ey)}")

    return " ".join(segs)


def finger_slot_edge(x1, y1, x2, y2):
    """Edge with slots cut inward (for front plate receiving wall tabs).
    Slots are at odd indices, matching tab positions on mating wall."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    px, py = dy / length, -dx / length

    n, seg_w = calc_fingers(length)
    b = BURN

    segs = []
    for i in range(n):
        s_start = i * seg_w
        s_end = (i + 1) * seg_w

        sx = x1 + ux * s_start
        sy = y1 + uy * s_start
        ex = x1 + ux * s_end
        ey = y1 + uy * s_end

        if i % 2 == 1:
            # Slot: cut inward by T, narrowed by burn on each side
            ssx = sx + ux * b - px * T
            ssy = sy + uy * b - py * T
            sex = ex - ux * b - px * T
            sey = ey - uy * b - py * T
            sx2 = sx + ux * b
            sy2 = sy + uy * b
            ex2 = ex - ux * b
            ey2 = ey - uy * b

            segs.append(f"L{fmt(sx2)},{fmt(sy2)}")
            segs.append(f"L{fmt(ssx)},{fmt(ssy)}")
            segs.append(f"L{fmt(sex)},{fmt(sey)}")
            segs.append(f"L{fmt(ex2)},{fmt(ey2)}")
        else:
            segs.append(f"L{fmt(ex)},{fmt(ey)}")

    return " ".join(segs)


# ============================================================
# Panel generators
# ============================================================

def front_plate(ox, oy):
    """Front plate (OW x OH): display window, camera hole.
    Finger joint SLOTS on all 4 edges. Top/bottom edges have T inset
    (solid corners where side walls sit), slots only in middle W portion."""
    w, h = OW, OH

    path = f"M{fmt(ox)},{fmt(oy)}"
    # Top edge (L to R): T solid + W slots + T solid
    path += f" L{fmt(ox + T)},{fmt(oy)}"
    path += " " + finger_slot_edge(ox + T, oy, ox + T + W, oy)
    path += f" L{fmt(ox + w)},{fmt(oy)}"
    # Right edge (top to bottom): full slots for side wall
    path += " " + finger_slot_edge(ox + w, oy, ox + w, oy + h)
    # Bottom edge (R to L): T solid + W slots + T solid
    path += f" L{fmt(ox + w - T)},{fmt(oy + h)}"
    path += " " + finger_slot_edge(ox + w - T, oy + h, ox + T, oy + h)
    path += f" L{fmt(ox)},{fmt(oy + h)}"
    # Left edge (bottom to top): full slots for side wall
    path += " " + finger_slot_edge(ox, oy + h, ox, oy)
    path += "Z"

    # Display window (centered in internal area, offset for front plate coords)
    win_cx = ox + T + DISP_CX
    win_cy = oy + T + DISP_CY
    window = rounded_rect_path(win_cx, win_cy, DISP_W, DISP_H, DISP_R, is_hole=True)

    # Camera hole
    cam_cx = ox + T + CAM_CX
    cam_cy = oy + T + CAM_CY
    camera = circle_path(cam_cx, cam_cy, CAM_D, is_hole=True)

    return f'<path d="{path} {window} {camera}" fill-rule="evenodd"/>'


def back_plate(ox, oy):
    """Back plate (OW x OH): finger joint slots on all 4 edges (mirrors front),
    attaches with hinges. Pi 5 mounting holes."""
    w, h = BACK_W, BACK_H

    # Outline with finger slots — top/bottom inset like front plate
    path = f"M{fmt(ox)},{fmt(oy)}"
    # Top edge: T solid + W slots + T solid
    path += f" L{fmt(ox + T)},{fmt(oy)}"
    path += " " + finger_slot_edge(ox + T, oy, ox + T + W, oy)
    path += f" L{fmt(ox + w)},{fmt(oy)}"
    # Right edge: full slots for side wall
    path += " " + finger_slot_edge(ox + w, oy, ox + w, oy + h)
    # Bottom edge: T solid + W slots + T solid
    path += f" L{fmt(ox + w - T)},{fmt(oy + h)}"
    path += " " + finger_slot_edge(ox + w - T, oy + h, ox + T, oy + h)
    path += f" L{fmt(ox)},{fmt(oy + h)}"
    # Left edge: full slots for side wall
    path += " " + finger_slot_edge(ox, oy + h, ox, oy)
    path += "Z"

    # Pi 5 mounting holes — centered in back plate
    pi_w = 85.0   # Pi board width
    pi_h = 56.0   # Pi board height
    pi_cx = ox + w / 2
    pi_cy = oy + w / 2 + 14  # offset down (below display center) to avoid camera zone

    holes = []
    for dx in [PI_HOLE_INSET_X, PI_HOLE_INSET_X + PI_HOLE_SPACING_X]:
        for dy in [PI_HOLE_INSET_Y, PI_HOLE_INSET_Y + PI_HOLE_SPACING_Y]:
            hx = pi_cx - pi_w / 2 + dx
            hy = pi_cy - pi_h / 2 + dy
            holes.append(circle_path(hx, hy, PI_HOLE_D, is_hole=True))

    cuts = " ".join(holes)
    return f'<path d="{path} {cuts}" fill-rule="evenodd"/>'


def top_wall(ox, oy):
    """Top wall (W x D): fits between side walls. Tabs on all edges —
    long edges into front/back plates, short edges into side wall slots."""
    w, h = W, D

    path = f"M{fmt(ox)},{fmt(oy)}"
    # Back edge (top in SVG): tabs (mates with back plate slots)
    path += " " + finger_tab_edge(ox, oy, ox + w, oy)
    # Right edge: tabs (into right side wall slots)
    path += " " + finger_tab_edge(ox + w, oy, ox + w, oy + h)
    # Front edge (bottom in SVG): tabs (mates with front plate slots)
    path += " " + finger_tab_edge(ox + w, oy + h, ox, oy + h)
    # Left edge: tabs (into left side wall slots)
    path += " " + finger_tab_edge(ox, oy + h, ox, oy)
    path += "Z"

    return f'<path d="{path}"/>'


def bottom_wall(ox, oy):
    """Bottom wall (W x D): fits between side walls. Tabs on all edges —
    long edges into front/back plates, short edges into side wall slots + USB-C cutout."""
    w, h = W, D

    path = f"M{fmt(ox)},{fmt(oy)}"
    # Back edge: tabs (mates with back plate slots)
    path += " " + finger_tab_edge(ox, oy, ox + w, oy)
    # Right edge: tabs (into right side wall slots)
    path += " " + finger_tab_edge(ox + w, oy, ox + w, oy + h)
    # Front edge: tabs (mates with front plate slots)
    path += " " + finger_tab_edge(ox + w, oy + h, ox, oy + h)
    # Left edge: tabs (into left side wall slots)
    path += " " + finger_tab_edge(ox, oy + h, ox, oy)
    path += "Z"

    # USB-C cutout centered horizontally, centered in wall depth
    usb_cx = ox + w / 2
    usb_cy = oy + h / 2
    usb = rect_cutout(usb_cx, usb_cy, USB_W, USB_H)

    return f'<path d="{path} {usb}" fill-rule="evenodd"/>'


def side_wall_path(ox, oy, button=False):
    """Side wall (OH x D): tabs on long edges (front/back plates),
    slots on short edges (receive top/bottom wall tabs). Optional button hole."""
    w, h = OH, D

    path = f"M{fmt(ox)},{fmt(oy)}"
    # Back edge (top in SVG): tabs (mates with back plate slots)
    path += " " + finger_tab_edge(ox, oy, ox + w, oy)
    # Bottom-of-box edge (right in SVG): slots (receive bottom wall tabs)
    path += " " + finger_slot_edge(ox + w, oy, ox + w, oy + h)
    # Front edge (bottom in SVG, R to L): tabs (mates with front plate slots)
    path += " " + finger_tab_edge(ox + w, oy + h, ox, oy + h)
    # Top-of-box edge (left in SVG): slots (receive top wall tabs)
    path += " " + finger_slot_edge(ox, oy + h, ox, oy)
    path += "Z"

    if button:
        btn_cx = ox + w / 2   # centered vertically (along height)
        btn_cy = oy + h / 2   # centered in depth
        btn = circle_path(btn_cx, btn_cy, BTN_D, is_hole=True)
        return f'<path d="{path} {btn}" fill-rule="evenodd"/>'
    return f'<path d="{path}"/>'


def left_wall(ox, oy):
    """Left wall, no button."""
    return side_wall_path(ox, oy, button=False)


def right_wall(ox, oy):
    """Right wall with button hole."""
    return side_wall_path(ox, oy, button=True)


# ============================================================
# Dimension legend
# ============================================================

def dimension_legend(ox, oy):
    """Generate SVG text block showing all dimensions."""
    lines = [
        f"E-INK CAMERA ENCLOSURE",
        f"",
        f"Box (outer):  {OW:.1f} x {OH:.1f} x {D + 2*T:.1f} mm  "
            f"({OW/25.4:.2f} x {OH/25.4:.2f} x {(D+2*T)/25.4:.2f} in)  "
            f"({OW/10:.1f} x {OH/10:.1f} x {(D+2*T)/10:.1f} cm)",
        f"Box (inner):  {W:.1f} x {H:.1f} x {D:.1f} mm",
        f"Material:     {T:.1f}mm plywood, burn comp: {BURN}mm",
        f"",
        f"PANELS",
        f"  Front plate:   {OW:.1f} x {OH:.1f} mm",
        f"  Back plate:    {BACK_W:.1f} x {BACK_H:.1f} mm",
        f"  Top wall:      {W:.1f} x {D:.1f} mm  (fits between side walls)",
        f"  Bottom wall:   {W:.1f} x {D:.1f} mm  (fits between side walls)",
        f"  Left wall:     {OH:.1f} x {D:.1f} mm",
        f"  Right wall:    {OH:.1f} x {D:.1f} mm",
        f"",
        f"FEATURES",
        f"  Display window:  {DISP_W} x {DISP_H} mm  (r={DISP_R}mm)",
        f"  Camera hole:     {CAM_D}mm dia  ({CAM_CY}mm from top)",
        f"  Camera zone:     {CAM_ZONE}mm above display",
        f"  Button hole:     {BTN_D}mm dia  (right wall)",
        f"  USB-C cutout:    {USB_W} x {USB_H} mm  (bottom wall)",
    ]

    text_elements = []
    line_h = 5  # mm line height
    for i, line in enumerate(lines):
        y = oy + i * line_h
        weight = 'font-weight="bold"' if line and not line.startswith(" ") else ""
        text_elements.append(
            f'<text x="{fmt(ox)}" y="{fmt(y)}" {weight}>{line}</text>'
        )

    return "\n    ".join(text_elements)


# ============================================================
# SVG generation
# ============================================================

def generate_svg():
    """Lay out all 6 panels + dimension legend and generate SVG."""
    sp = SPACING
    margin = T + 1  # extra margin for protruding finger tabs

    # Row 1: Front plate + Back plate
    r1_y = sp + margin

    # Row 2: Top wall + Bottom wall
    r2_y = r1_y + OH + margin + sp + margin

    # Row 3: Left wall + Right wall
    r3_y = r2_y + D + margin + sp + margin

    # Legend below panels
    legend_y = r3_y + D + margin + sp + 10

    # Width must fit the widest row (row 3 has two OH-wide side walls)
    r1_w = margin + OW + sp + BACK_W + margin
    r2_w = margin + W + sp + W + margin
    r3_w = margin + OH + sp + OH + margin
    total_w = max(r1_w, r2_w, r3_w) + 2 * sp
    total_h = legend_y + 20 * 5 + sp  # 20 lines of legend

    # X offsets: center each row, or just use consistent left margin
    x0 = sp + margin

    parts = [
        f'<!-- Front Plate {OW:.0f}x{OH:.0f}mm -->',
        front_plate(x0, r1_y),

        f'<!-- Back Plate {BACK_W:.0f}x{BACK_H:.0f}mm -->',
        back_plate(x0 + OW + sp, r1_y),

        f'<!-- Top Wall {W:.0f}x{D:.0f}mm -->',
        top_wall(x0, r2_y),

        f'<!-- Bottom Wall {W:.0f}x{D:.0f}mm -->',
        bottom_wall(x0 + W + sp, r2_y),

        f'<!-- Left Wall {OH:.0f}x{D:.0f}mm -->',
        left_wall(x0, r3_y),

        f'<!-- Right Wall {OH:.0f}x{D:.0f}mm -->',
        right_wall(x0 + OH + sp, r3_y),
    ]

    content = "\n    ".join(parts)
    legend = dimension_legend(x0, legend_y)

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{fmt(total_w)}mm" height="{fmt(total_h)}mm"
     viewBox="0 0 {fmt(total_w)} {fmt(total_h)}">
  <!-- Laser-cut enclosure for e-ink camera -->
  <!-- Red = cut, Blue = engrave/score -->
  <!-- Units: mm. Material: {T}mm plywood. Burn: {BURN}mm -->
  <g fill="none" stroke="red" stroke-width="0.1">
    {content}
  </g>
  <g fill="#444" stroke="none" font-family="monospace" font-size="3.5">
    {legend}
  </g>
</svg>'''


if __name__ == "__main__":
    svg = generate_svg()

    # Versioned output
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    versioned = f"enclosure_{ts}.svg"
    with open(versioned, "w") as f:
        f.write(svg)

    # Latest symlink
    latest = "enclosure_latest.svg"
    if os.path.islink(latest) or os.path.exists(latest):
        os.remove(latest)
    os.symlink(versioned, latest)

    print(f"Generated {versioned}")
    print(f"Linked   {latest} -> {versioned}")
    print(f"\nBox: {OW/10:.1f} x {OH/10:.1f} x {(D+2*T)/10:.1f} cm "
          f"({OW:.0f} x {OH:.0f} x {D+2*T:.0f} mm)")
    print(f"Internal: {W} x {H:.1f} x {D} mm")
