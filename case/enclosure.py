#!/usr/bin/env python3
"""
Laser-cut enclosure generator for e-ink camera.

Boxes.py-inspired construction: burn compensation, corner relief,
finger joints on all mating edges, hinged back plate.

Run: python3 enclosure.py
Output: enclosure.svg
"""

import math

# === MATERIAL & FABRICATION ===
T = 3.0           # material thickness (mm)
BURN = 0.1        # laser kerf compensation (mm) — holes shrink, tabs grow
RELIEF_R = 0.5    # corner relief radius (mm)
TAB_W = 12.0      # target finger joint tab width (mm)

# === INTERNAL BOX DIMENSIONS (mm) ===
W = 140           # width: panel 127.6 + 6.2mm border each side
H = 212           # height: 28mm camera + 173.8mm display + 10.2mm bottom border
D = 30            # depth: display + Pi stack + cables

# === DISPLAY WINDOW ===
DISP_W = 127.6    # panel outline width (as measured)
DISP_H = 173.8    # panel outline height (as measured)
DISP_R = 2.0      # corner radius
# Window is centered horizontally; vertically offset down to leave room for camera
# Panel outline is 127.6 x 173.8, centered in 134 x 202 internal space
# Camera gets the top 28mm, display centered in remaining 174mm zone
DISP_CX = W / 2                          # centered horizontally
DISP_CY = 28 + 173.8 / 2                 # center of panel zone (below camera area)

# === CAMERA ===
CAM_D = 8.0       # hole diameter (lens barrel ~7mm + clearance)
CAM_CX = W / 2    # centered horizontally
CAM_CY = 14.0     # 14mm from top edge (centered in 28mm camera zone)

# === BUTTON (right wall) ===
BTN_D = 12.0      # panel hole diameter

# === USB-C CUTOUT (bottom wall, front edge) ===
USB_W = 12.0
USB_H = 7.0

# === PI 5 MOUNTING (back plate) ===
PI_HOLE_D = 2.5       # M2.5 holes
PI_HOLE_SPACING_X = 58.0
PI_HOLE_SPACING_Y = 49.0
PI_HOLE_INSET_X = 3.5   # from Pi board edge
PI_HOLE_INSET_Y = 3.5

# === OUTER DIMENSIONS ===
OW = W + 2 * T    # outer width: 140mm
OH = H + 2 * T    # outer height: 208mm

# === BACK PLATE ===
# Same outer dimensions as front plate — attaches with hinges
BACK_W = OW
BACK_H = OH

# === SVG LAYOUT ===
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
    Finger joint SLOTS on all 4 edges to receive wall tabs."""
    w, h = OW, OH

    # Outline with finger slots on all 4 edges
    path = f"M{fmt(ox)},{fmt(oy)}"
    # Top edge (L to R)
    path += " " + finger_slot_edge(ox, oy, ox + w, oy)
    # Right edge (top to bottom)
    path += " " + finger_slot_edge(ox + w, oy, ox + w, oy + h)
    # Bottom edge (R to L)
    path += " " + finger_slot_edge(ox + w, oy + h, ox, oy + h)
    # Left edge (bottom to top)
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
    """Back plate (OW x OH): finger joint slots on all 4 edges (same as front),
    attaches with hinges. Pi 5 mounting holes."""
    w, h = BACK_W, BACK_H

    # Outline with finger slots on all 4 edges (mirrors front plate)
    path = f"M{fmt(ox)},{fmt(oy)}"
    path += " " + finger_slot_edge(ox, oy, ox + w, oy)
    path += " " + finger_slot_edge(ox + w, oy, ox + w, oy + h)
    path += " " + finger_slot_edge(ox + w, oy + h, ox, oy + h)
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
    """Top wall (OW x D): finger tabs on all 4 edges."""
    w, h = OW, D

    path = f"M{fmt(ox)},{fmt(oy)}"
    # Back edge (top in SVG): tabs (mates with back plate slots)
    path += " " + finger_tab_edge(ox, oy, ox + w, oy)
    # Right edge: tabs
    path += " " + finger_tab_edge(ox + w, oy, ox + w, oy + h)
    # Front edge (bottom in SVG): tabs
    path += " " + finger_tab_edge(ox + w, oy + h, ox, oy + h)
    # Left edge: tabs
    path += " " + finger_tab_edge(ox, oy + h, ox, oy)
    path += "Z"

    return f'<path d="{path}"/>'


def bottom_wall(ox, oy):
    """Bottom wall (OW x D): finger tabs on all 4 edges + USB-C cutout."""
    w, h = OW, D

    path = f"M{fmt(ox)},{fmt(oy)}"
    # Back edge: tabs
    path += " " + finger_tab_edge(ox, oy, ox + w, oy)
    # Right edge: tabs
    path += " " + finger_tab_edge(ox + w, oy, ox + w, oy + h)
    # Front edge: tabs
    path += " " + finger_tab_edge(ox + w, oy + h, ox, oy + h)
    # Left edge: tabs
    path += " " + finger_tab_edge(ox, oy + h, ox, oy)
    path += "Z"

    # USB-C cutout centered horizontally, centered in wall depth
    usb_cx = ox + w / 2
    usb_cy = oy + h / 2
    usb = rect_cutout(usb_cx, usb_cy, USB_W, USB_H)

    return f'<path d="{path} {usb}" fill-rule="evenodd"/>'


def side_wall_path(ox, oy, button=False):
    """Side wall (OH x D): finger tabs on all 4 edges. Optional button hole."""
    w, h = OH, D

    path = f"M{fmt(ox)},{fmt(oy)}"
    # Back edge (top in SVG): tabs (mates with back plate slots)
    path += " " + finger_tab_edge(ox, oy, ox + w, oy)
    # Bottom-of-box edge (right in SVG, going down): tabs
    path += " " + finger_tab_edge(ox + w, oy, ox + w, oy + h)
    # Front edge (bottom in SVG, R to L): tabs
    path += " " + finger_tab_edge(ox + w, oy + h, ox, oy + h)
    # Top-of-box edge (left in SVG, going up): tabs
    path += " " + finger_tab_edge(ox, oy + h, ox, oy)
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
# SVG generation
# ============================================================

def generate_svg():
    """Lay out all 6 panels and generate SVG."""
    sp = SPACING
    margin = T + 1  # extra margin for protruding finger tabs

    # Row 1: Front plate + Back plate
    r1_y = sp + margin

    # Row 2: Top wall + Bottom wall
    r2_y = r1_y + OH + margin + sp + margin

    # Row 3: Left wall + Right wall
    r3_y = r2_y + D + margin + sp + margin

    # Width must fit the widest row (row 3 has two OH-wide side walls)
    r1_w = margin + OW + sp + BACK_W + margin
    r2_w = margin + OW + sp + OW + margin
    r3_w = margin + OH + sp + OH + margin
    total_w = max(r1_w, r2_w, r3_w) + 2 * sp
    total_h = r3_y + D + margin + sp

    # X offsets: center each row, or just use consistent left margin
    x0 = sp + margin

    parts = [
        f'<!-- Front Plate {OW:.0f}x{OH:.0f}mm (slots on all edges) -->',
        front_plate(x0, r1_y),

        f'<!-- Back Plate {BACK_W:.0f}x{BACK_H:.0f}mm (hinged, Pi mount) -->',
        back_plate(x0 + OW + sp, r1_y),

        f'<!-- Top Wall {OW:.0f}x{D:.0f}mm (tabs all edges) -->',
        top_wall(x0, r2_y),

        f'<!-- Bottom Wall {OW:.0f}x{D:.0f}mm (tabs + USB-C cutout) -->',
        bottom_wall(x0 + OW + sp, r2_y),

        f'<!-- Left Wall {OH:.0f}x{D:.0f}mm (tabs all edges) -->',
        left_wall(x0, r3_y),

        f'<!-- Right Wall {OH:.0f}x{D:.0f}mm (tabs + button) -->',
        right_wall(x0 + OH + sp, r3_y),
    ]

    content = "\n    ".join(parts)

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
</svg>'''


if __name__ == "__main__":
    svg = generate_svg()
    with open("enclosure.svg", "w") as f:
        f.write(svg)
    print(f"Generated enclosure.svg")
    print(f"\nBox dimensions:")
    print(f"  Outer:    {OW:.0f} x {OH:.0f} x {D + 2*T:.0f} mm")
    print(f"  Internal: {W} x {H} x {D} mm")
    print(f"  Material: {T}mm plywood, burn comp: {BURN}mm")
    print(f"\nPanels:")
    print(f"  Front plate:  {OW:.0f} x {OH:.0f} mm (finger slots, display window, camera hole)")
    print(f"  Back plate:   {BACK_W:.0f} x {BACK_H:.0f} mm (finger slots, hinged, Pi 5 mount)")
    print(f"  Top wall:     {OW:.0f} x {D:.0f} mm (finger tabs all edges)")
    print(f"  Bottom wall:  {OW:.0f} x {D:.0f} mm (finger tabs, USB-C cutout)")
    print(f"  Left wall:    {OH:.0f} x {D:.0f} mm (finger tabs all edges)")
    print(f"  Right wall:   {OH:.0f} x {D:.0f} mm (finger tabs, button hole)")
    print(f"\nFeatures:")
    print(f"  Display window: {DISP_W}x{DISP_H}mm, {DISP_R}mm corners")
    print(f"  Camera hole:    {CAM_D}mm dia")
    print(f"  Button hole:    {BTN_D}mm dia (right wall)")
    print(f"  USB-C cutout:   {USB_W}x{USB_H}mm (bottom wall)")
