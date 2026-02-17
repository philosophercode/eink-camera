#!/usr/bin/env python3
"""
Laser-cut wood enclosure generator for e-ink camera.
Generates SVG with all panels laid out for cutting.

Adjust PARAMETERS below to match your components.
Run: python3 enclosure_v1.py
Output: enclosure_v1.svg
"""

import math

# === PARAMETERS (measure your components, adjust these) ===
T = 3.0          # material thickness (mm)
TAB_W = 12.0     # target finger joint tab width

# Internal box dimensions (space for components + clearance)
# 7.8" panel outline: 173.8 x 127.6mm
# Pi 5: 85 x 56 x ~20mm
W = 184          # internal width  - panel 173.8mm + 10mm margin
H = 158          # internal height - panel 127.6mm + 30mm for camera above
D = 40           # internal depth  - Pi 5 (~20mm) + display (<1mm) + cables

# Display window (active area: 158.2 x 118.6mm)
DISP_W = 159     # slightly larger than active area for tolerance
DISP_H = 119     # slightly larger than active area for tolerance
DISP_Y_OFF = 12  # shift window down from center (room for camera above)

# Camera hole
CAM_D = 10       # diameter
CAM_Y = 18       # center distance from top of front plate

# Button hole (centered on top wall)
BTN_D = 12

# USB-C power cutout (on right wall)
USB_W = 12
USB_H = 7
USB_POS = 0.7    # position along wall (0=bottom, 1=top of box)

# Screw holes (M3) for front/back plates
SCREW_D = 3.2
SCREW_INSET = 10

# === DERIVED ===
OW = W + 2 * T   # outer width
OH = H + 2 * T   # outer height
SPACING = 15      # gap between panels in SVG layout


def finger_edge(x1, y1, x2, y2, tabs_out=True):
    """Generate SVG path segments for a finger-jointed edge.

    Edge goes from (x1,y1) to (x2,y2). For CW-traced panels,
    tabs_out=True extends tabs outward from the panel.
    Corners are always gaps (baseline) so corner material is preserved.
    """
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length       # unit direction
    px, py = dy / length, -dx / length      # outward perpendicular (CW)

    sign = 1 if tabs_out else -1
    tx, ty = sign * px * T, sign * py * T   # tab offset vector

    # Odd number of segments >= 5; corners (even indices) are gaps
    n = max(5, round(length / TAB_W))
    if n % 2 == 0:
        n += 1
    w = length / n

    segs = []
    for i in range(n):
        ex = x1 + ux * (i + 1) * w
        ey = y1 + uy * (i + 1) * w
        if i % 2 == 1:  # active (tab or slot) at odd indices
            sx = x1 + ux * i * w
            sy = y1 + uy * i * w
            segs.append(f"L{sx+tx:.2f},{sy+ty:.2f}")
            segs.append(f"L{ex+tx:.2f},{ey+ty:.2f}")
            segs.append(f"L{ex:.2f},{ey:.2f}")
        else:  # gap at even indices
            segs.append(f"L{ex:.2f},{ey:.2f}")
    return ' '.join(segs)


def circle_path(cx, cy, d):
    """SVG path for a circle (two arcs)."""
    r = d / 2
    return (f"M{cx-r:.2f},{cy:.2f} "
            f"A{r:.2f},{r:.2f} 0 1,0 {cx+r:.2f},{cy:.2f} "
            f"A{r:.2f},{r:.2f} 0 1,0 {cx-r:.2f},{cy:.2f}Z")


def rect_path(cx, cy, w, h):
    """SVG path for a rectangle centered at (cx, cy)."""
    x, y = cx - w / 2, cy - h / 2
    return (f"M{x:.2f},{y:.2f} L{x+w:.2f},{y:.2f} "
            f"L{x+w:.2f},{y+h:.2f} L{x:.2f},{y+h:.2f}Z")


def screw_holes(ox, oy, w, h):
    """Four corner screw holes."""
    si = SCREW_INSET
    return ' '.join([
        circle_path(ox + si, oy + si, SCREW_D),
        circle_path(ox + w - si, oy + si, SCREW_D),
        circle_path(ox + w - si, oy + h - si, SCREW_D),
        circle_path(ox + si, oy + h - si, SCREW_D),
    ])


# === PANEL GENERATORS ===
# Each returns an SVG <path> element string.
# Panels are drawn at position (ox, oy) in SVG coordinates.
# Convention: SVG top edge = assembly back edge for wall panels.

def front_plate(ox, oy):
    """Front plate: plain rectangle with display window, camera hole, screws."""
    w, h = OW, OH

    outline = (f"M{ox:.2f},{oy:.2f} L{ox+w:.2f},{oy:.2f} "
               f"L{ox+w:.2f},{oy+h:.2f} L{ox:.2f},{oy+h:.2f}Z")

    dcx, dcy = ox + w / 2, oy + h / 2 + DISP_Y_OFF
    cuts = ' '.join([
        rect_path(dcx, dcy, DISP_W, DISP_H),
        circle_path(ox + w / 2, oy + CAM_Y, CAM_D),
        screw_holes(ox, oy, w, h),
    ])

    return f'<path d="{outline} {cuts}" fill-rule="evenodd"/>'


def back_plate(ox, oy):
    """Back plate: finger joint slots on all 4 edges, screw holes."""
    w, h = OW, OH

    path = f"M{ox:.2f},{oy:.2f}"
    # Top edge: slots (receive top wall tabs)
    path += ' ' + finger_edge(ox, oy, ox + w, oy, tabs_out=False)
    # Right edge: plain T, then slots for right wall, then plain T
    path += f" L{ox+w:.2f},{oy+T:.2f}"
    path += ' ' + finger_edge(ox + w, oy + T, ox + w, oy + T + H, tabs_out=False)
    path += f" L{ox+w:.2f},{oy+h:.2f}"
    # Bottom edge: slots (receive bottom wall tabs)
    path += ' ' + finger_edge(ox + w, oy + h, ox, oy + h, tabs_out=False)
    # Left edge: plain T, slots for left wall, plain T (going up)
    path += f" L{ox:.2f},{oy+T+H:.2f}"
    path += ' ' + finger_edge(ox, oy + T + H, ox, oy + T, tabs_out=False)
    path += f" L{ox:.2f},{oy:.2f}"
    path += "Z"

    cuts = screw_holes(ox, oy, w, h)
    return f'<path d="{path} {cuts}" fill-rule="evenodd"/>'


def top_wall(ox, oy):
    """Top wall (OW x D): tabs on back edge, button hole."""
    w, h = OW, D

    path = f"M{ox:.2f},{oy:.2f}"
    # Top edge (= back in assembly): tabs
    path += ' ' + finger_edge(ox, oy, ox + w, oy, tabs_out=True)
    # Right, bottom, left: plain
    path += f" L{ox+w:.2f},{oy+h:.2f}"
    path += f" L{ox:.2f},{oy+h:.2f}"
    path += f" L{ox:.2f},{oy:.2f}Z"

    btn = circle_path(ox + w / 2, oy + h / 2, BTN_D)
    return f'<path d="{path} {btn}" fill-rule="evenodd"/>'


def bottom_wall(ox, oy):
    """Bottom wall (OW x D): tabs on back edge."""
    w, h = OW, D

    path = f"M{ox:.2f},{oy:.2f}"
    path += ' ' + finger_edge(ox, oy, ox + w, oy, tabs_out=True)
    path += f" L{ox+w:.2f},{oy+h:.2f}"
    path += f" L{ox:.2f},{oy+h:.2f}"
    path += f" L{ox:.2f},{oy:.2f}Z"

    return f'<path d="{path}"/>'


def left_wall(ox, oy):
    """Left wall (H x D): tabs on back edge."""
    w, h = H, D

    path = f"M{ox:.2f},{oy:.2f}"
    path += ' ' + finger_edge(ox, oy, ox + w, oy, tabs_out=True)
    path += f" L{ox+w:.2f},{oy+h:.2f}"
    path += f" L{ox:.2f},{oy+h:.2f}"
    path += f" L{ox:.2f},{oy:.2f}Z"

    return f'<path d="{path}"/>'


def right_wall(ox, oy):
    """Right wall (H x D): tabs on back edge, USB-C cutout."""
    w, h = H, D

    path = f"M{ox:.2f},{oy:.2f}"
    path += ' ' + finger_edge(ox, oy, ox + w, oy, tabs_out=True)
    path += f" L{ox+w:.2f},{oy+h:.2f}"
    path += f" L{ox:.2f},{oy+h:.2f}"
    path += f" L{ox:.2f},{oy:.2f}Z"

    # USB-C cutout on front edge (SVG bottom), position adjustable
    usb_cx = ox + w * USB_POS
    usb_cy = oy + h - USB_H / 2  # flush with front edge
    usb = rect_path(usb_cx, usb_cy, USB_W, USB_H)

    return f'<path d="{path} {usb}" fill-rule="evenodd"/>'


def generate_svg():
    """Lay out all panels and generate SVG."""
    sp = SPACING

    # Row 1: Front plate + Back plate
    r1_y = sp

    # Row 2: Top wall + Bottom wall
    r2_y = r1_y + OH + sp

    # Row 3: Left wall + Right wall
    r3_y = r2_y + D + sp

    total_w = sp + OW + sp + OW + sp
    total_h = r3_y + D + sp

    parts = [
        f'<!-- Front Plate {OW:.0f}x{OH:.0f}mm -->',
        front_plate(sp, r1_y),

        f'<!-- Back Plate {OW:.0f}x{OH:.0f}mm -->',
        back_plate(sp + OW + sp, r1_y),

        f'<!-- Top Wall {OW:.0f}x{D:.0f}mm -->',
        top_wall(sp, r2_y),

        f'<!-- Bottom Wall {OW:.0f}x{D:.0f}mm -->',
        bottom_wall(sp + OW + sp, r2_y),

        f'<!-- Left Wall {H:.0f}x{D:.0f}mm -->',
        left_wall(sp, r3_y),

        f'<!-- Right Wall {H:.0f}x{D:.0f}mm (USB cutout) -->',
        right_wall(sp + H + sp, r3_y),
    ]

    content = '\n    '.join(parts)

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{total_w:.2f}mm" height="{total_h:.2f}mm"
     viewBox="0 0 {total_w:.2f} {total_h:.2f}">
  <!-- Red stroke = cut lines for laser cutter -->
  <!-- Units: mm. Material: {T}mm wood/plywood -->
  <g fill="none" stroke="red" stroke-width="0.1">
    {content}
  </g>
</svg>'''


if __name__ == '__main__':
    svg = generate_svg()
    with open('enclosure_v1.svg', 'w') as f:
        f.write(svg)
    print(f"Generated enclosure_v1.svg")
    print(f"Outer box: {OW:.0f} x {OH:.0f} x {D + 2*T:.0f} mm")
    print(f"Internal:  {W} x {H} x {D} mm")
    print(f"Material:  {T}mm")
    print(f"\nPanels:")
    print(f"  Front/Back plate: {OW:.0f} x {OH:.0f} mm")
    print(f"  Top/Bottom wall:  {OW:.0f} x {D:.0f} mm")
    print(f"  Left/Right wall:  {H} x {D} mm")
