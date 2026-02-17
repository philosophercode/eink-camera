#!/usr/bin/env python3
"""
Generate a printable HTML file with each enclosure panel at 1:1 scale
on separate letter-size pages. Print with "Actual size" (no scaling).

Run: python3 enclosure_print.py && open enclosure_print.html
"""

from enclosure import *

MARGIN = 25  # viewBox margin around each panel (mm) — room for dims + text


def h_dim(x1, x2, y, label, above=True):
    """Horizontal dimension line from x1 to x2 at y."""
    off = -6 if above else 6
    ty = y + off
    tly = ty - 2 if above else ty + 4
    # Extension lines
    ey1 = min(y, ty) - 1
    ey2 = max(y, ty) + 1
    return f'''<g class="dim">
      <line x1="{fmt(x1)}" y1="{fmt(ey1)}" x2="{fmt(x1)}" y2="{fmt(ey2)}"/>
      <line x1="{fmt(x2)}" y1="{fmt(ey1)}" x2="{fmt(x2)}" y2="{fmt(ey2)}"/>
      <line x1="{fmt(x1)}" y1="{fmt(ty)}" x2="{fmt(x2)}" y2="{fmt(ty)}" marker-start="url(#arr)" marker-end="url(#arr)"/>
      <text x="{fmt((x1+x2)/2)}" y="{fmt(tly)}" font-size="4" text-anchor="middle" font-family="sans-serif" fill="#333">{label}</text>
    </g>'''


def v_dim(x, y1, y2, label, left=True):
    """Vertical dimension line from y1 to y2 at x."""
    off = -6 if left else 6
    tx = x + off
    tlx = tx - 2 if left else tx + 4
    # Extension lines
    ex1 = min(x, tx) - 1
    ex2 = max(x, tx) + 1
    return f'''<g class="dim">
      <line x1="{fmt(ex1)}" y1="{fmt(y1)}" x2="{fmt(ex2)}" y2="{fmt(y1)}"/>
      <line x1="{fmt(ex1)}" y1="{fmt(y2)}" x2="{fmt(ex2)}" y2="{fmt(y2)}"/>
      <line x1="{fmt(tx)}" y1="{fmt(y1)}" x2="{fmt(tx)}" y2="{fmt(y2)}" marker-start="url(#arr)" marker-end="url(#arr)"/>
      <text x="{fmt(tlx)}" y="{fmt((y1+y2)/2)}" font-size="4" text-anchor="middle" font-family="sans-serif" fill="#333"
            transform="rotate(-90,{fmt(tlx)},{fmt((y1+y2)/2)})">{label}</text>
    </g>'''


def panel_page(title, draw_fn, pw, ph, extra_dims=""):
    """One panel as a full SVG with dimensions."""
    m = MARGIN
    vb_w = pw + 2 * m
    vb_h = ph + 2 * m
    ox, oy = m, m

    panel_el = draw_fn(ox, oy)

    # Standard width and height dimensions
    dims = h_dim(ox, ox + pw, oy, f"{pw:.4g}mm", above=True)
    dims += "\n    " + v_dim(ox, oy, oy + ph, f"{ph:.4g}mm", left=True)
    if extra_dims:
        dims += "\n    " + extra_dims

    return f'''<svg xmlns="http://www.w3.org/2000/svg"
         width="{fmt(vb_w)}mm" height="{fmt(vb_h)}mm"
         viewBox="0 0 {fmt(vb_w)} {fmt(vb_h)}"
         style="max-width:100%; max-height:250mm;" overflow="visible">
      <defs>
        <marker id="arr" markerWidth="3" markerHeight="3" refX="1.5" refY="1.5"
                orient="auto-start-reverse" markerUnits="strokeWidth">
          <path d="M0,0 L3,1.5 L0,3Z" fill="#333"/>
        </marker>
      </defs>
      <text x="{fmt(vb_w/2)}" y="{fmt(m/2)}" font-size="4.5" text-anchor="middle"
            font-family="sans-serif" font-weight="bold" fill="#333">{title}</text>
      <g fill="none" stroke="red" stroke-width="0.2">
        {panel_el}
      </g>
      {dims}
    </svg>'''


def generate_print_html():
    pages = []

    # 1. Front plate
    pages.append(panel_page(
        f"Front Plate  {OW:.0f} x {OH:.0f} mm",
        front_plate, OW, OH,
    ))

    # 2. Back plate
    pages.append(panel_page(
        f"Back Plate  {BACK_W:.1f} x {BACK_H:.1f} mm",
        back_plate, BACK_W, BACK_H,
    ))

    # 3. Top wall
    pages.append(panel_page(
        f"Top Wall  {OW:.0f} x {D:.0f} mm",
        top_wall, OW, D,
    ))

    # 4. Bottom wall
    pages.append(panel_page(
        f"Bottom Wall  {OW:.0f} x {D:.0f} mm  (USB-C cutout)",
        bottom_wall, OW, D,
    ))

    # 5. Left wall
    pages.append(panel_page(
        f"Left Wall  {OH:.0f} x {D:.0f} mm  (rail groove)",
        left_wall, OH, D,
    ))

    # 6. Right wall
    pages.append(panel_page(
        f"Right Wall  {OH:.0f} x {D:.0f} mm  (rail + button)",
        right_wall, OH, D,
    ))

    pages_html = "\n".join(
        f'<div class="page">\n{svg}\n</div>' for svg in pages
    )

    ref = '''<div class="page">
      <svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
        <text x="50" y="12" font-size="5" text-anchor="middle" font-family="sans-serif"
              font-weight="bold" fill="#333">Print Scale Check</text>
        <text x="50" y="19" font-size="3.5" text-anchor="middle" font-family="sans-serif" fill="#666">
          Measure this square with a ruler — it should be exactly 50mm
        </text>
        <rect x="25" y="25" width="50" height="50" fill="none" stroke="black" stroke-width="0.3"/>
        <text x="50" y="53" font-size="4" text-anchor="middle" font-family="sans-serif" fill="#333">50 x 50 mm</text>
        <text x="50" y="85" font-size="3" text-anchor="middle" font-family="sans-serif" fill="#999">
          If not 50mm, check print settings: use "Actual Size", not "Fit to Page"
        </text>
      </svg>
    </div>'''

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>E-ink Camera Enclosure — Print Template</title>
<style>
  @page {{ size: letter; margin: 10mm; }}
  body {{ margin: 0; padding: 0; font-family: sans-serif; }}
  .page {{
    page-break-after: always;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 260mm;
  }}
  .dim line, .dim path {{ stroke: #333; stroke-width: 0.2; fill: none; }}
  @media screen {{
    .page {{
      border-bottom: 2px dashed #ddd;
      padding: 10mm;
      margin-bottom: 5mm;
    }}
  }}
</style>
</head>
<body>
{ref}
{pages_html}
</body>
</html>'''


if __name__ == "__main__":
    html = generate_print_html()
    with open("enclosure_print.html", "w") as f:
        f.write(html)
    print("Generated enclosure_print.html")
    print("Print at 'Actual Size' (100%, no scaling) on letter paper.")
    print("Use the 50mm reference square on page 1 to verify scale.")
