"""
Listing image builder — Amazon 2026 image rules.

Optimized typography sizes, multi-line auto-wrapping, high-contrast dark visual cards, 
and progressive memory compression (keeping JPEGs compressed around ~300-500 KB).
"""
from __future__ import annotations
import io, os, re, zipfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

CANVAS      = 2000          # Amazon's recommended 2000 x 2000
MAIN_FILL   = 0.85          # product fills ~85% of frame
MIN_SIDE    = 1000
MAX_SIDE    = 10000
MAX_BYTES   = 10 * 1024 * 1024
JPEG_Q      = 86            # Optimized high quality compression (reduces MB size)

RED   = (227, 30, 42)
BLACK = (17, 17, 19)
WHITE = (255, 255, 255)
GREY  = (232, 234, 238)
DARK  = (28, 30, 34)

HERE = os.path.dirname(os.path.abspath(__file__))

def _font(name, size):
    """Robust scalable font finder across operating systems."""
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
    return ImageFont.load_default()

def display(size):  return _font("Anton-Regular.ttf", size)
def cond(size):     return _font("BarlowCondensed-Bold.ttf", size)
def body(size):     return _font("Poppins-Regular.ttf", size)
def body_b(size):   return _font("Poppins-Medium.ttf", size)

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
    if min(base) < 200:
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
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        try:
            length = draw.textlength(t, font=font)
        except Exception:
            length = len(t) * (font.size if hasattr(font, 'size') else 14)
        if length <= max_w or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def draw_lines_with_shadow(draw, xy, lines, font, fill, shadow_fill=(0, 0, 0, 240), leading=1.05, shadow_offset=5):
    x, y = xy
    try:
        asc = font.getbbox("Hg")[3] - font.getbbox("Hg")[1]
    except Exception:
        asc = int(font.size) if hasattr(font, 'size') else 40
    for ln in lines:
        if shadow_fill:
            draw.text((x + shadow_offset, y + shadow_offset), ln, font=font, fill=shadow_fill)
        draw.text((x, y), ln, font=font, fill=fill)
        y += int(asc * leading) + 12
    return y

def gradient(size, top, bottom):
    w, h = size
    g = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return g.resize(size, Image.BILINEAR)

def shadow(canvas, prod, pos, blur=45, opacity=120):
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    a = prod.split()[-1].point(lambda v: min(opacity, v))
    solid = Image.new("RGBA", prod.size, (0, 0, 0, 255)); solid.putalpha(a)
    sh.paste(solid, (pos[0] + 16, pos[1] + 28), solid)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(canvas.convert("RGBA"), sh).convert("RGB")

def red_rule(d, x, y, w=280, h=16):
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
    return canvas

def hero(src, headline, accent, subline="", size=CANVAS, bg=None):
    """Headline text sized extra large (~360px), stacked over high contrast background card."""
    if bg is not None:
        canvas = fit(to_rgb(bg), size, size).resize((size, size), Image.LANCZOS)
        veil = Image.new("RGBA", (size, size), (10, 12, 18, 145))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), veil).convert("RGB")
    else:
        canvas = gradient((size, size), (40, 43, 50), (12, 13, 15))

    # Scale Product Cutout
    prod, bbox = cutout(src); prod = prod.crop(bbox)
    prod = fit(prod, int(size * 0.60), int(size * 0.65))
    pos = (size - prod.width - int(size * .03), int(size * .28))
    canvas = shadow(canvas, prod, pos, blur=55, opacity=140)
    canvas.paste(prod, pos, prod)

    # Giant Typography Formatting
    d = ImageDraw.Draw(canvas)
    m = int(size * .055)
    f_headline = display(int(size * 0.18))  # ~360px Headline Size (Matches Product Prominence)
    f_sub = body_b(int(size * 0.042))      # ~84px Subline

    card_w = int(size * 0.58)

    # High Contrast Backing Box
    card_overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_overlay)
    cd.rounded_rectangle([m - 20, m - 20, m + card_w, int(size * 0.92)], radius=32, fill=(8, 10, 14, 195))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), card_overlay).convert("RGB")
    d = ImageDraw.Draw(canvas)

    y = m + 10
    if headline:
        hl_lines = wrap(d, headline.upper(), f_headline, card_w - 40)
        y = draw_lines_with_shadow(d, (m, y), hl_lines, f_headline, WHITE, leading=0.98)

    if accent:
        acc_lines = wrap(d, accent.upper(), f_headline, card_w - 40)
        y = draw_lines_with_shadow(d, (m, y), acc_lines, f_headline, RED, leading=0.98)

    red_rule(d, m, y + 16, int(size * .20), int(size * .012))
    y += int(size * .06)

    if subline:
        sub_lines = wrap(d, subline, f_sub, card_w - 40)
        draw_lines_with_shadow(d, (m, y), sub_lines[:3], f_sub, GREY, leading=1.25)

    return canvas

def badge_card(src, headline, accent, badges, size=CANVAS, bg=None):
    if bg is not None:
        canvas = fit(to_rgb(bg), size, size).resize((size, size), Image.LANCZOS)
    else:
        canvas = gradient((size, size), (238, 240, 244), (203, 208, 215))

    d = ImageDraw.Draw(canvas)
    bar = int(size * .16)
    d.rectangle([0, 0, size, bar], fill=BLACK)

    prod, bbox = cutout(src); prod = prod.crop(bbox)
    prod = fit(prod, int(size * .58), int(size * .58))
    pos = (size - prod.width - int(size * .04), int(size * .35))
    canvas = shadow(canvas, prod, pos, blur=50, opacity=120)
    canvas.paste(prod, pos, prod)

    d = ImageDraw.Draw(canvas)
    m = int(size * .045)
    f1 = display(int(size * .08))
    lines = wrap(d, headline.upper(), f1, size * .78)
    yy = int(bar * .15)

    for ln in lines[:1]:
        d.text((m, yy), ln, font=f1, fill=WHITE)
        try:
            wln = d.textlength(ln, font=f1)
        except Exception:
            wln = len(ln) * 30
        if accent: d.text((m + wln + 18, yy), accent.upper(), font=f1, fill=RED)

    y = int(size * .22)
    for label, sub in badges[:4]:
        h = int(size * .12)
        d.rounded_rectangle([m, y, m + int(size * .44), y + h], radius=16, fill=DARK)
        d.rectangle([m + int(size * .44) - 10, y, m + int(size * .44), y + h], fill=RED)
        
        lbl_lines = wrap(d, label.upper(), cond(int(size * .04)), int(size * .38))
        d.text((m + int(size * .035), y + int(h * .12)), "\n".join(lbl_lines), font=cond(int(size * .04)), fill=WHITE)
        if sub:
            sub_lines = wrap(d, sub, body(int(size * .022)), int(size * .38))
            d.text((m + int(size * .035), y + int(h * .55)), "\n".join(sub_lines[:2]), font=body(int(size * .022)), fill=(210, 214, 222))
        y += h + int(size * .028)
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
        f1 = display(int(size * .07))
        d.text((int(size * .05), int(size * .04)), headline.upper(), font=f1, fill=BLACK)

    left = [i for n, i in enumerate(items) if n % 2 == 0][:3]
    right = [i for n, i in enumerate(items) if n % 2 == 1][:3]
    fh, fb = cond(int(size * .04)), body(int(size * .024))

    for col, side in ((left, "l"), (right, "r")):
        y = int(size * .20)
        for title, sub in col:
            x = int(size * .04) if side == "l" else int(size * .62)
            w = int(size * .34)

            d.rounded_rectangle([x - 10, y - 8, x + w + 10, y + int(size * .20)], radius=12,
                                fill=(255, 255, 255, 235), outline=(200, 204, 210), width=2)
            d.text((x, y), title.upper(), font=fh, fill=RED)
            ly = y + int(size * .048)
            sub_lines = wrap(d, sub, fb, w - 10)
            for ln in sub_lines[:3]:
                d.text((x, ly), ln, font=fb, fill=(30, 32, 38)); ly += int(size * .03)
            y += int(size * .24)
    return canvas

def angle_grid(images, labels=None, headline="360 view", accent="every angle covered", size=CANVAS):
    canvas = gradient((size, size), (245, 246, 248), (223, 226, 231))
    d = ImageDraw.Draw(canvas)
    f1 = display(int(size * .07))
    m = int(size * .045)
    d.text((m, int(size * .04)), headline.upper(), font=f1, fill=BLACK)

    top = int(size * .18)
    cell = (size - m * 2 - int(size * .02)) // 2
    labels = labels or ["Front view", "Side view", "Top view", "Angled view"]

    for i, im in enumerate(images[:4]):
        cx = m + (i % 2) * (cell + int(size * .02))
        cy = top + (i // 2) * (cell + int(size * .02))
        d.rounded_rectangle([cx, cy, cx + cell, cy + cell], radius=18, fill=WHITE)
        p, bb = cutout(im); p = p.crop(bb)
        p = fit(p, int(cell * .78), int(cell * .70))
        canvas.paste(p, (cx + (cell - p.width) // 2, cy + (cell - p.height) // 2 + 20), p)
    return canvas

def spec_card(src, headline, accent, stat, stat_label, chips=None, size=CANVAS, bg=None):
    canvas = gradient((size, size), (250, 250, 252), (219, 223, 229))
    prod, bbox = cutout(src); prod = prod.crop(bbox)
    prod = fit(prod, int(size * .55), int(size * .50))
    pos = (size - prod.width - int(size * .05), int(size * .28))
    canvas = shadow(canvas, prod, pos, blur=48, opacity=115)
    canvas.paste(prod, pos, prod)

    d = ImageDraw.Draw(canvas)
    m = int(size * .055)
    f1 = display(int(size * .08))
    y = int(size * .10)
    
    if headline:
        hl_lines = wrap(d, headline.upper(), f1, int(size * 0.52))
        y = draw_lines_with_shadow(d, (m, y), hl_lines, f1, BLACK, shadow_fill=None)

    if stat:
        fs = display(int(size * .18))
        d.text((m, int(size * .44)), str(stat), font=fs, fill=BLACK)
    return canvas

def audit_image(im, is_main=False):
    out = []
    w, h = im.size
    longest = max(w, h)
    if longest < MIN_SIDE:
        out.append(("error", f"{w}x{h}. Under {MIN_SIDE} px on longest side."))
    if not out:
        out.append(("ok", f"{w}x{h}, compliant."))
    return out

def encode(im, quality=JPEG_Q):
    """Encodes compressed sRGB JPEG images (Target ~300KB-500KB per file)."""
    buf = io.BytesIO()
    im.convert("RGB").save(
        buf, 
        "JPEG", 
        quality=quality, 
        optimize=True, 
        progressive=True, 
        subsampling=1
    )
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
    (0,  "Main",            "Pure white, product only."),
    (1,  "Hero benefit",    "Headline and key benefit placed over background scene."),
    (2,  "Feature callouts","Annotated cards naming attributes and specs."),
    (3,  "Certification",   "Compliance badges."),
    (4,  "Material or build","Materials highlight cards."),
    (5,  "Scale or spec",   "Sizing and key statistics."),
    (6,  "Lifestyle in use","Product composited into scene."),
    (7,  "Angle grid",      "Four key product angles."),
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
    return out

def plan_from_copy(title="", bullets=None, attributes=None, brand="", have_bg=False, n_extra=0, target=6):
    feats = features_from_copy(title, bullets, attributes)
    lead  = feats[0] if feats else ("Built for the ride", "")

    plan = [{"kind": "main", "name": "Main — pure white", "cfg": {}}]
    plan.append({"kind": "hero", "name": "Hero benefit", "use_bg": have_bg, "cfg": {
        "headline": " ".join(lead[0].split()[:2]) or "Built for",
        "accent": " ".join(lead[0].split()[2:]) or "the ride",
        "subline": lead[1][:150]}})

    if feats:
        plan.append({"kind": "callouts", "name": "Feature callouts", "cfg": {
            "headline": "Engineered in detail", "items": feats[:6]}})

    return plan[:max(5, min(target, 9))]
