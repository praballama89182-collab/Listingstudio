"""
Listing image builder — Amazon 2026 image rules.

Main image rules enforced here: pure white RGB(255,255,255), product fills ~85%
of the frame, no text or graphics, square, 2000 px, sRGB JPEG under 10 MB.
Secondary slots allow text, infographics and lifestyle backgrounds.
"""
from __future__ import annotations
import io, os, re, zipfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

CANVAS      = 2000          # Amazon's recommended 2000 x 2000
MAIN_FILL   = 0.85          # product must fill at least 85% of the main frame
MIN_SIDE    = 1000          # zoom threshold
MAX_SIDE    = 10000
MAX_BYTES   = 10 * 1024 * 1024
JPEG_Q      = 92

RED   = (227, 30, 42)
BLACK = (17, 17, 19)
WHITE = (255, 255, 255)
GREY  = (232, 234, 238)
DARK  = (28, 30, 34)

HERE = os.path.dirname(os.path.abspath(__file__))

def _font(name, size):
    """Robust font loader supporting custom files and reliable system fallbacks."""
    candidates = [
        os.path.join(HERE, "fonts", name),
        f"/usr/share/fonts/truetype/google-fonts/{name}",
        f"/usr/share/fonts/truetype/dejavu/{name}",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    # Fallback to default if nothing else is found
    try:
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()

def display(size):  return _font("Anton-Regular.ttf", size)          # headlines
def cond(size):     return _font("BarlowCondensed-Bold.ttf", size)   # sub-heads
def body(size):     return _font("Poppins-Regular.ttf", size)        # body copy
def body_b(size):   return _font("Poppins-Medium.ttf", size)

# ------------------------------------------------------------------ helpers
def to_rgb(im):
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, WHITE)
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert("RGB")

def cutout(im, tol=18):
    im = to_rgb(im)
    w, h = im.size
    px = im.load()
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    base = tuple(sum(c[i] for c in corners) // 4 for i in range(3))
    if min(base) < 200:                       # dark background: keep as-is
        out = im.convert("RGBA")
        return out, (0, 0, w, h)
    diff = ImageChops.difference(im, Image.new("RGB", im.size, base)).convert("L")
    mask = diff.point(lambda v: 255 if v > tol else 0).filter(ImageFilter.MedianFilter(3))
    bbox = mask.getbbox() or (0, 0, w, h)
    out = im.convert("RGBA")
    out.putalpha(mask)
    return out, bbox

def fit(im, box_w, box_h):
    r = min(box_w / im.width, box_h / im.height)
    return im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)

def wrap(draw, text, font, max_w):
    """Splits long attributes/headings into clean multi-line blocks."""
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        # Measure text width safely
        try:
            length = draw.textlength(t, font=font)
        except Exception:
            length = len(t) * (font.size if hasattr(font, 'size') else 12)
        
        if length <= max_w or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def draw_lines_with_shadow(draw, xy, lines, font, fill, shadow_fill=(10, 10, 10, 220), leading=1.15, shadow_offset=4):
    """Draws multi-line text with high-contrast drop shadows for absolute visibility."""
    x, y = xy
    try:
        asc = font.getbbox("Hg")[3] - font.getbbox("Hg")[1]
    except Exception:
        asc = 35
    for ln in lines:
        if shadow_fill:
            draw.text((x + shadow_offset, y + shadow_offset), ln, font=font, fill=shadow_fill)
        draw.text((x, y), ln, font=font, fill=fill)
        y += int(asc * leading) + 10
    return y

def hex_pattern(canvas, colour=(255, 255, 255), alpha=16, step=120):
    lay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    r = step * 0.45
    for row, y in enumerate(range(-step, canvas.height + step, int(step * 0.86))):
        for x in range(-step, canvas.width + step, step):
            cx = x + (step // 2 if row % 2 else 0)
            pts = [(cx + r * __import__("math").cos(__import__("math").radians(60 * i)),
                    y + r * __import__("math").sin(__import__("math").radians(60 * i)))
                   for i in range(6)]
            d.polygon(pts, outline=colour + (alpha,))
    return Image.alpha_composite(canvas.convert("RGBA"), lay).convert("RGB")

def gradient(size, top, bottom, diagonal=False):
    w, h = size
    g = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    g = g.resize(size, Image.BILINEAR)
    if diagonal: g = g.rotate(12, resample=Image.BICUBIC, expand=False)
    return g

def shadow(canvas, prod, pos, blur=42, opacity=110):
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    a = prod.split()[-1].point(lambda v: min(opacity, v))
    solid = Image.new("RGBA", prod.size, (0, 0, 0, 255)); solid.putalpha(a)
    sh.paste(solid, (pos[0] + 14, pos[1] + 26), solid)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(canvas.convert("RGBA"), sh).convert("RGB")

def red_rule(d, x, y, w=240, h=14):
    d.rectangle([x, y, x + w, y + h], fill=RED)

# ------------------------------------------------------------------ templates
def main_image(src, size=CANVAS, fill=MAIN_FILL):
    prod, bbox = cutout(src)
    prod = prod.crop(bbox)
    target = int(size * fill)
    prod = fit(prod, target, target)
    canvas = Image.new("RGB", (size, size), WHITE)
    pos = ((size - prod.width) // 2, (size - prod.height) // 2)
    canvas = shadow(canvas, prod, pos, blur=30, opacity=55)
    canvas.paste(prod, pos, prod)
    d = ImageDraw.Draw(canvas)
    m = int(size * 0.012)
    for box in [(0, 0, size, m), (0, size - m, size, size),
                (0, 0, m, size), (size - m, 0, size, size)]:
        d.rectangle(box, fill=WHITE)
    return canvas

def hero(src, headline, accent, subline="", size=CANVAS, bg=None):
    """Large, bold, multi-line typography card layout with background compositing."""
    if bg is not None:
        canvas = fit(to_rgb(bg), size, size).resize((size, size), Image.LANCZOS)
        # Deep translucent dark veil to guarantee headline readability on any photo
        veil = Image.new("RGBA", (size, size), (15, 17, 23, 130))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), veil).convert("RGB")
    else:
        canvas = gradient((size, size), (44, 47, 54), (12, 13, 15))
        canvas = hex_pattern(canvas, alpha=13)

    # Product Cutout Scaling
    prod, bbox = cutout(src); prod = prod.crop(bbox)
    prod = fit(prod, int(size * 0.58), int(size * 0.62))
    pos = (size - prod.width - int(size * .04), int(size * .32))
    canvas = shadow(canvas, prod, pos, blur=55, opacity=140)
    canvas.paste(prod, pos, prod)

    # Large Typography Styling & Card Container
    d = ImageDraw.Draw(canvas)
    m = int(size * .06)
    f1 = display(int(size * .11))      # Large punchy headline size (~220px)
    fb = body_b(int(size * .035))     # Readable subline size (~70px)

    card_w = int(size * 0.58)
    
    # Semi-transparent backing card so text never blends into background scenery
    card_overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_overlay)
    cd.rounded_rectangle([m - 20, m - 20, m + card_w, int(size * 0.90)], radius=28, fill=(10, 12, 18, 180))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), card_overlay).convert("RGB")
    d = ImageDraw.Draw(canvas)

    y = m + 10
    if headline:
        hl_lines = wrap(d, headline.upper(), f1, card_w - 40)
        y = draw_lines_with_shadow(d, (m, y), hl_lines, f1, WHITE, leading=1.05)

    if accent:
        acc_lines = wrap(d, accent.upper(), f1, card_w - 40)
        y = draw_lines_with_shadow(d, (m, y), acc_lines, f1, RED, leading=1.05)

    red_rule(d, m, y + 14, int(size * .16), int(size * .009))
    y += int(size * .05)

    if subline:
        sub_lines = wrap(d, subline, fb, card_w - 40)
        draw_lines_with_shadow(d, (m, y), sub_lines[:3], fb, GREY, shadow_fill=(0,0,0,240), leading=1.3)

    return canvas

def badge_card(src, headline, accent, badges, size=CANVAS, bg=None):
    if bg is not None:
        canvas = fit(to_rgb(bg), size, size).resize((size, size), Image.LANCZOS)
        veil = Image.new("RGBA", (size, size), (15, 17, 23, 110))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), veil).convert("RGB")
    else:
        canvas = gradient((size, size), (238, 240, 244), (203, 208, 215))

    d = ImageDraw.Draw(canvas)
    bar = int(size * .16)
    d.rectangle([0, 0, size, bar], fill=BLACK)
    d.polygon([(int(size * .62), bar), (size, bar), (size, bar + int(size * .028))], fill=RED)

    prod, bbox = cutout(src); prod = prod.crop(bbox)
    prod = fit(prod, int(size * .58), int(size * .58))
    pos = (size - prod.width - int(size * .04), int(size * .35))
    canvas = shadow(canvas, prod, pos, blur=50, opacity=120)
    canvas.paste(prod, pos, prod)

    d = ImageDraw.Draw(canvas)
    m = int(size * .045)
    f1 = display(int(size * .065))
    lines = wrap(d, headline.upper(), f1, size * .78)
    yy = int(bar * .18)

    for ln in lines[:1]:
        d.text((m, yy), ln, font=f1, fill=WHITE)
        try:
            wln = d.textlength(ln, font=f1)
        except Exception:
            wln = len(ln) * 25
        if accent: d.text((m + wln + 18, yy), accent.upper(), font=f1, fill=RED)

    y = int(size * .22)
    for label, sub in badges[:4]:
        h = int(size * .11)
        d.rounded_rectangle([m, y, m + int(size * .44), y + h], radius=int(h * .18), fill=DARK)
        d.rectangle([m + int(size * .44) - 10, y, m + int(size * .44), y + h], fill=RED)
        
        lbl_lines = wrap(d, label.upper(), cond(int(size * .038)), int(size * .38))
        d.text((m + int(size * .035), y + int(h * .12)), "\n".join(lbl_lines),
               font=cond(int(size * .038)), fill=WHITE)
        if sub:
            sub_lines = wrap(d, sub, body(int(size * .021)), int(size * .38))
            d.text((m + int(size * .035), y + int(h * .54)), "\n".join(sub_lines[:2]),
                   font=body(int(size * .021)), fill=(210, 214, 222))
        y += h + int(size * .025)
    return canvas

def callouts(src, items, headline="", size=CANVAS):
    canvas = gradient((size, size), (243, 244, 246), (214, 217, 222))
    prod, bbox = cutout(src); prod = prod.crop(bbox)
    prod = fit(prod, int(size * .48), int(size * .48))
    pos = ((size - prod.width) // 2, (size - prod.height) // 2 + int(size * .03))
    canvas = shadow(canvas, prod, pos, blur=45, opacity=110)
    canvas.paste(prod, pos, prod)

    d = ImageDraw.Draw(canvas)
    if headline:
        f1 = display(int(size * .06))
        d.text((int(size * .05), int(size * .04)), headline.upper(), font=f1, fill=BLACK)
        red_rule(d, int(size * .05), int(size * .04) + int(size * .075), int(size * .12), 10)

    left = [i for n, i in enumerate(items) if n % 2 == 0][:3]
    right = [i for n, i in enumerate(items) if n % 2 == 1][:3]
    fh, fb = cond(int(size * .036)), body(int(size * .022))

    for col, side in ((left, "l"), (right, "r")):
        y = int(size * .20)
        for title, sub in col:
            x = int(size * .04) if side == "l" else int(size * .62)
            w = int(size * .34)

            d.rounded_rectangle([x - 10, y - 8, x + w + 10, y + int(size * .20)], radius=12,
                                fill=(255, 255, 255, 230), outline=(200, 204, 210), width=2)
            d.text((x, y), title.upper(), font=fh, fill=RED)
            ly = y + int(size * .045)
            
            sub_lines = wrap(d, sub, fb, w - 10)
            for ln in sub_lines[:3]:
                d.text((x, ly), ln, font=fb, fill=(30, 32, 38)); ly += int(size * .028)
            
            ax = x + w if side == "l" else x
            d.line([(ax, y + int(size * .02)),
                    (size // 2 - (int(size * .18) if side == "l" else -int(size * .18)),
                     y + int(size * .02))], fill=(150, 155, 163), width=3)
            d.ellipse([ax - 9, y + int(size * .02) - 9, ax + 9, y + int(size * .02) + 9], fill=RED)
            y += int(size * .24)
    return canvas

def angle_grid(images, labels=None, headline="360 view", accent="every angle covered", size=CANVAS):
    canvas = gradient((size, size), (245, 246, 248), (223, 226, 231))
    d = ImageDraw.Draw(canvas)
    f1 = display(int(size * .06))
    m = int(size * .045)
    d.text((m, int(size * .04)), headline.upper(), font=f1, fill=BLACK)
    try:
        wln = d.textlength(headline.upper(), font=f1)
    except Exception:
        wln = len(headline.upper()) * 25
    d.text((m + wln + 16, int(size * .04)), accent.upper(), font=f1, fill=RED)
    red_rule(d, m, int(size * .04) + int(size * .075), int(size * .12), 10)

    top = int(size * .18)
    cell = (size - m * 2 - int(size * .02)) // 2
    labels = labels or ["Front view", "Side view", "Top view", "Angled view"]

    for i, im in enumerate(images[:4]):
        cx = m + (i % 2) * (cell + int(size * .02))
        cy = top + (i // 2) * (cell + int(size * .02))
        d.rounded_rectangle([cx, cy, cx + cell, cy + cell], radius=18, fill=WHITE)
        p, bb = cutout(im); p = p.crop(bb)
        p = fit(p, int(cell * .78), int(cell * .70))
        px = cx + (cell - p.width) // 2
        py = cy + (cell - p.height) // 2 + int(cell * .05)
        canvas.paste(p, (px, py), p)
        d = ImageDraw.Draw(canvas)
        tag = labels[i] if i < len(labels) else ""
        try:
            tw = d.textlength(tag.upper(), font=cond(int(size * .026)))
        except Exception:
            tw = len(tag.upper()) * 15
        d.rectangle([cx + 16, cy + 16, cx + 45 + tw, cy + 16 + int(size * .048)], fill=BLACK)
        d.rectangle([cx + 16, cy + 16, cx + 24, cy + 16 + int(size * .048)], fill=RED)
        d.text((cx + 34, cy + 22), tag.upper(), font=cond(int(size * .026)), fill=WHITE)
    return canvas

def spec_card(src, headline, accent, stat, stat_label, chips=None, size=CANVAS, bg=None):
    if bg is not None:
        canvas = fit(to_rgb(bg), size, size).resize((size, size), Image.LANCZOS)
        veil = Image.new("RGBA", (size, size), (245, 246, 248, 170))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), veil).convert("RGB")
    else:
        canvas = gradient((size, size), (250, 250, 252), (219, 223, 229))

    d = ImageDraw.Draw(canvas)
    d.polygon([(0, 0), (int(size * .30), 0), (0, int(size * .30))], fill=BLACK)
    d.polygon([(0, 0), (int(size * .17), 0), (0, int(size * .17))], fill=RED)

    prod, bbox = cutout(src); prod = prod.crop(bbox)
    prod = fit(prod, int(size * .55), int(size * .50))
    pos = (size - prod.width - int(size * .05), int(size * .28))
    canvas = shadow(canvas, prod, pos, blur=48, opacity=115)
    canvas.paste(prod, pos, prod)

    d = ImageDraw.Draw(canvas)
    m = int(size * .055)
    f1 = display(int(size * .07))
    y = int(size * .10)
    
    if headline:
        hl_lines = wrap(d, headline.upper(), f1, int(size * 0.52))
        y = draw_lines_with_shadow(d, (m, y), hl_lines, f1, BLACK, shadow_fill=None)

    if accent:
        acc_lines = wrap(d, accent.upper(), f1, int(size * 0.52))
        y = draw_lines_with_shadow(d, (m, y), acc_lines, f1, RED, shadow_fill=None)

    red_rule(d, m, y + 10, int(size * .12), 10)

    if stat:
        fs = display(int(size * .16))
        d.text((m, int(size * .44)), str(stat), font=fs, fill=BLACK)
        try:
            w = d.textlength(str(stat), font=fs)
        except Exception:
            w = len(str(stat)) * 60
        d.text((m + w + 14, int(size * .52)), stat_label or "", font=cond(int(size * .045)), fill=RED)

    for i, (t, s2) in enumerate((chips or [])[:3]):
        cw = (size - m * 2) // 3
        x = m + i * cw
        yy = int(size * .82)
        d.rounded_rectangle([x, yy, x + cw - 18, yy + int(size * .12)], radius=14,
                            fill=WHITE, outline=(214, 218, 224), width=3)
        d.rectangle([x, yy, x + 10, yy + int(size * .12)], fill=RED)
        
        t_lines = wrap(d, t.upper(), cond(int(size * .03)), cw - 40)
        d.text((x + 22, yy + int(size * .015)), "\n".join(t_lines[:2]), font=cond(int(size * .03)), fill=BLACK)
        if s2:
            s2_lines = wrap(d, s2, body(int(size * .02)), cw - 40)
            d.text((x + 22, yy + int(size * .065)), "\n".join(s2_lines[:2]), font=body(int(size * .02)), fill=(90, 96, 106))
    return canvas

def audit_image(im, is_main=False):
    out = []
    w, h = im.size
    longest = max(w, h)
    if longest < MIN_SIDE:
        out.append(("error", f"{w}x{h}. Under {MIN_SIDE} px on the longest side, so zoom is disabled."))
    elif longest < 1600:
        out.append(("warn", f"{w}x{h}. Works, but 2000 px is recommended."))
    if longest > MAX_SIDE:
        out.append(("error", f"Longest side {longest} px exceeds the {MAX_SIDE} px maximum."))
    if max(w, h) / max(1, min(w, h)) > 5:
        out.append(("error", "Aspect ratio wider than 5:1."))
    if is_main:
        rgb = to_rgb(im)
        px = rgb.load()
        pts = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
               (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]
        bad = [p for p in pts if px[p] != (255, 255, 255)]
        if bad:
            out.append(("error", f"Background is not pure white at {len(bad)} of {len(pts)} sampled edge points."))
        prod, bbox = cutout(rgb)
        fillpc = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / (w * h)
        if fillpc < 0.55:
            out.append(("warn", f"Product occupies roughly {fillpc*100:.0f}% of the frame. Amazon recommends 85%+ fill."))
        if w != h:
            out.append(("warn", "Not square. 1:1 is standard for main images."))
    if not out:
        out.append(("ok", f"{w}x{h}, compliant."))
    return out

def encode(im, quality=JPEG_Q):
    for q in (quality, 88, 82, 76, 70):
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=q, subsampling=0, optimize=True, dpi=(72, 72))
        if buf.tell() <= MAX_BYTES:
            return buf.getvalue()
    return buf.getvalue()

def safe_asin(s):
    s = re.sub(r"[^A-Za-z0-9]", "", s or "")
    return s.upper() or "PRODUCT"

def filename(asin, slot):
    return f"{safe_asin(asin)}.MAIN.jpg" if slot == 0 else f"{safe_asin(asin)}.PT{slot:02d}.jpg"

def build_zip(pairs):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in pairs:
            z.writestr(name, data)
    return buf.getvalue()

SLOT_PLAN = [
    (0,  "Main",            "Pure white, product only, 85% fill."),
    (1,  "Hero benefit",    "Headline and key benefit placed over the composited product cutout."),
    (2,  "Feature callouts","Annotated cards naming attributes and specs."),
    (3,  "Certification",   "Standards, testing, and compliance badges."),
    (4,  "Material or build","Materials and build highlight cards."),
    (5,  "Scale or spec",   "Sizing and key numerical statistics."),
    (6,  "Lifestyle in use","Product composited into a lifestyle background scene."),
    (7,  "Angle grid",      "Four key product angles in one multi-pane view."),
    (8,  "What is included","Box contents and bundle breakdown."),
]

TEMPLATES = {
    "Main — pure white":      "main",
    "Hero benefit":           "hero",
    "Feature callouts":       "callouts",
    "Certification badges":   "badge",
    "Spec or statistic":      "spec",
    "Angle grid":             "grid",
}

def render(kind, src, cfg, extras=None, bg=None, size=CANVAS):
    if kind == "main":
        return main_image(src, size)
    if kind == "hero":
        return hero(src, cfg.get("headline", ""), cfg.get("accent", ""),
                    cfg.get("subline", ""), size, bg=bg)
    if kind == "callouts":
        return callouts(src, cfg.get("items", []), cfg.get("headline", ""), size)
    if kind == "badge":
        return badge_card(src, cfg.get("headline", "Certified for"), cfg.get("accent", "safety"),
                          cfg.get("items", []), size, bg=bg)
    if kind == "spec":
        return spec_card(src, cfg.get("headline", ""), cfg.get("accent", ""),
                         cfg.get("stat", ""), cfg.get("stat_label", ""),
                         cfg.get("items", []), size, bg=bg)
    if kind == "grid":
        return angle_grid([src] + list(extras or []), cfg.get("labels"),
                          cfg.get("headline", "360 view"), cfg.get("accent", "every angle covered"),
                          size)
    return main_image(src, size)

CERT_RE  = re.compile(r"certif|standard|dot\b|ece\b|astm|cpsc|iso\b|fmvss|tested|compliance", re.I)
STAT_RE  = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g|lb|lbs|oz|ml|l|litre|liter|cm|mm|inch|inches|hours?|hrs?)", re.I)
USE_RE   = re.compile(r"\bfor\b|use|ride|commut|travel|touring|daily|everyday", re.I)

def features_from_copy(title="", bullets=None, attributes=None):
    out, seen = [], set()
    for b in (bullets or []):
        b = re.sub(r"\s+", " ", str(b)).strip()
        if not b: continue
        head, _, body = b.partition(":")
        if not body: head, body = "", b
        detail = body.split(";")[0].strip()
        head = (head or " ".join(detail.split()[:2])).strip().title()
        k = head.lower()
        if head and detail and k not in seen:
            seen.add(k); out.append((head, detail))
    for a in (attributes or []):
        a = re.sub(r"\s+", " ", str(a)).strip()
        if not a: continue
        head, _, body = a.partition("|")
        head, detail = head.strip().title(), (body.strip() or a.strip())
        if head.lower() in seen: continue
        seen.add(head.lower()); out.append((head, detail))
    if not out and title:
        for seg in re.split(r"\s*[|,]\s*", title):
            seg = seg.strip()
            if len(seg.split()) >= 2 and seg.lower() not in seen:
                seen.add(seg.lower()); out.append((" ".join(seg.split()[:2]).title(), seg))
    return out

def plan_from_copy(title="", bullets=None, attributes=None, brand="", have_bg=False, n_extra=0, target=6):
    feats = features_from_copy(title, bullets, attributes)
    certs = [f for f in feats if CERT_RE.search(f[0] + " " + f[1])]
    stats = [f for f in feats if STAT_RE.search(f[0] + " " + f[1])]
    uses  = [f for f in feats if USE_RE.search(f[0] + " " + f[1])]
    lead  = feats[0] if feats else ("Built for the ride", "")

    plan = [{"kind": "main", "name": "Main — pure white", "cfg": {}}]

    plan.append({"kind": "hero", "name": "Hero benefit", "use_bg": have_bg, "cfg": {
        "headline": " ".join(lead[0].split()[:2]) or "Built for",
        "accent": " ".join(lead[0].split()[2:]) or "the ride",
        "subline": lead[1][:150]}})

    if feats:
        plan.append({"kind": "callouts", "name": "Feature callouts", "cfg": {
            "headline": "Engineered in detail", "items": feats[:6]}})

    if certs:
        plan.append({"kind": "badge", "name": "Certification", "cfg": {
            "headline": "Certified for", "accent": "safety",
            "items": [(c[0], c[1][:44]) for c in certs[:4]]}})

    if stats:
        m = STAT_RE.search(stats[0][0] + " " + stats[0][1])
        plan.append({"kind": "spec", "name": "Spec or statistic", "cfg": {
            "headline": stats[0][0], "accent": "", "stat": m.group(1),
            "stat_label": m.group(2), "items": [(f[0], f[1][:36]) for f in feats[1:4]]}})

    if have_bg:
        u = uses[0] if uses else lead
        plan.append({"kind": "hero", "name": "Lifestyle in use", "use_bg": True, "cfg": {
            "headline": "Ready for", "accent": "any road", "subline": u[1][:150]}})

    if n_extra:
        plan.append({"kind": "grid", "name": "Angle grid", "cfg": {
            "headline": "360 view", "accent": "every angle covered"}})

    if len(plan) < target and len(feats) > 3:
        plan.append({"kind": "callouts", "name": "More features", "cfg": {
            "headline": "More to know", "items": feats[3:9]}})

    return plan[:max(5, min(target, 9))]
