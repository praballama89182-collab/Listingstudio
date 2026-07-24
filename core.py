"""
Listing Studio — core rules engine (no Streamlit).
Amazon 2026 rules for title, item highlights, bullets and backend search terms.
"""
from __future__ import annotations
import html as _h, re, unicodedata
from dataclasses import dataclass, field

# ----------------------------------------------------------------- limits
TITLE_LIMIT        = 75
TITLE_LIMIT_MEDIA  = 200
HIGHLIGHT_LIMIT    = 125
BULLET_MIN         = 150     # Amazon-recommended floor
BULLET_MAX         = 200     # Amazon-recommended ceiling
BULLET_HARD        = 500     # absolute cap
BULLETS_TOTAL_MAX  = 1000    # cumulative across all five
DESCRIPTION_LIMIT  = 2000
BACKEND_BYTES      = 249     # strict; one byte over de-indexes the field
MAX_BULLETS        = 5

# ----------------------------------------------------------------- vocab
BANNED_TITLE_CHARS = set("!$?_~*#^|<>{}[]@=+;\"\\")

PROMO_TERMS = ["best seller","bestseller","best selling","#1","number one","top rated",
    "top selling","hottest","sale","on sale","discount","cheap","cheapest","free shipping",
    "free gift","money back","satisfaction guaranteed","guaranteed","world's best",
    "premium quality","amazing","perfect","flawless","miracle","must have","limited time",
    "buy now","order now","new arrival","brand new"]

# words that must never start or end a clause
CONJUNCTIONS = {"and","or","but","so","which","plus","also","then","while","whereas",
                "yet","nor","because","although","though","however"}
DANGLING_END = CONJUNCTIONS | {"the","a","an","with","for","of","in","on","to","at","from",
                               "as","by","that","this","its","your","our","is","are","be"}

BACKEND_STOP = CONJUNCTIONS | {"a","an","the","for","with","to","of","in","on","by","at",
    "from","as","is","it","this","that","these","those","your","our","you","we","they","its",
    "be","are","was","were","can","will","has","have","not","all","any","more","most","very",
    "just","also","than","when","how","what","buy","shop","sale","new","best","free","top",
    "great","good","nice","amazon","asin","com","de","la","el","los","las","del","para","con",
    "una","por","que","le","les","des","du","et","pour","avec","der","die","das","und","mit",
    "ein","il","lo","di","da","per"}

DISEASE_CLAIMS = ["cure","cures","treat","treats","prevent","prevents","heal","heals","remedy",
    "therapeutic","medicine","medicinal","arthritis","cancer","diabetes","infection","disease",
    "anti-inflammatory","antibiotic","fda approved","clinically proven","vet recommended"]

UNIT_ABBREV = {"ounces":"oz","ounce":"oz","pounds":"lb","pound":"lb","fluid ounces":"fl oz",
    "millilitres":"ml","milliliters":"ml","litres":"l","liters":"l",
    "grams":"g","kilograms":"kg","inches":"in","centimetres":"cm","centimeters":"cm","count":"ct"}

UNITS = (r"fl\.?\s?oz|ounces?|oz|millilit(?:er|re)s?|ml|lit(?:er|re)s?|ltr|gallons?|gal|"
         r"quarts?|qt|kilograms?|kgs?|milligrams?|mg|grams?|gm|pounds?|lbs?|inch(?:es)?|"
         r"cm|mm|feet|ft|watts?|volts?|mah|g|kg|lb|in|l|w|v|m")
SIZE_RE = re.compile(r"\b\d+(?:[\.,]\d+)?\s*(?:" + UNITS + r")\b", re.I)
PACK_RE = re.compile(r"\b(?:pack\s+of\s+\d+|set\s+of\s+\d+|box\s+of\s+\d+|"
                     r"\d+\s*[-\s]?(?:pack|pk|pcs?|pieces?|count|ct|units?))\b", re.I)
DIM_RE  = re.compile(r"\b\d+(?:\.\d+)?\s*(?:x|\u00D7)\s*\d+(?:\.\d+)?"
                     r"(?:\s*(?:x|\u00D7)\s*\d+(?:\.\d+)?)?\s*(?:cm|mm|inch(?:es)?|in|ft|m)?\b", re.I)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
                      "\u2190-\u21FF\u2B00-\u2BFF\uFE0F]")
HTML_RE  = re.compile(r"<[^>]+>")
WS_RE    = re.compile(r"\s+")
CONTACT_RE = re.compile(r"(https?://\S+|www\.\S+|\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b|\+?\d[\d\s().-]{8,}\d)")
ACRONYMS = {"USB","LED","HD","UV","BPA","XL","XXL","XXXL","USA","PU","TPU","3D","4K","SPF",
            "ML","OZ","PCS","ABS","PVC","EVA","DHA","EPA","IPX7","ASTM","CPSC"}
NUM_WORDS = {1:"one",2:"two",3:"three",4:"four",5:"five",6:"six",7:"seven",8:"eight",9:"nine"}
BULLET_MARK_RE = re.compile(r"^\s*(?:[\u2022\u2023\u25CF\u25AA\u00B7\-\*\u2013\u2014]+|\(?\d{1,2}[\.\)])\s*")
SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

# ----------------------------------------------------------------- helpers
def plain(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"') \
         .replace("\u201d", '"').replace("\u2013", "-").replace("\u2014", "-") \
         .replace("\u00a0", " ").replace("\u200b", "")
    return s

def ws(s):  return WS_RE.sub(" ", plain(s).strip())
def n(s):   return ws(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()))
def nkw(s): return ws(re.sub(r"[^\w\s]", " ", (s or "").lower(), flags=re.UNICODE))
def clen(s):return len(s or "")
def blen(s):return len((s or "").encode("utf-8"))
def esc(s): return _h.escape(s or "")
def no_emoji(s): return EMOJI_RE.sub("", s or "")
def no_html(s):  return HTML_RE.sub("", s or "")

def strip_conjunctions(text):
    words = ws(text).split()
    while words and n(words[0]) in CONJUNCTIONS: words.pop(0)
    while words and n(words[-1]).strip(",;:") in DANGLING_END: words.pop()
    out = " ".join(words)
    out = re.sub(r"\s+([,;:.])", r"\1", out)
    out = re.sub(r"[,;:]+$", "", out)
    return ws(out)

def tidy(text):
    t = ws(text)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r"([,.;:!?])\s*(?=[,.;:!?])", "", t)
    t = re.sub(r"^[\s,.;:!?\-]+", "", t)
    t = re.sub(r"[\s,.;:\-]+$", "", t)
    return ws(t)

def number_units(text):
    t = re.sub(r"(\d)\s*(" + UNITS + r")\b", r"\1 \2", text or "", flags=re.I)
    def repl(m): return NUM_WORDS[int(m.group(1))]
    t = re.sub(r"(?<![\w.\-/])(?<!pack of )(?<!set of )(?<!box of )([1-9])"
               r"(?![\d\w.\-/])(?!\s*(?:" + UNITS + r")\b)", repl, t, flags=re.I)
    return ws(t)

def abbreviate_units(text):
    t = text or ""
    for long, short in UNIT_ABBREV.items():
        t = re.sub(r"(?i)(?<![a-z])" + re.escape(long) + r"(?![a-z])", short, t)
    return ws(t)

def drop_filler(text):
    t = re.sub(r"(?i)\s+\b(?:for|with)\b\s+", " ", text or "")
    return ws(t)

def strip_promo(text):
    t = text or ""
    for p in PROMO_TERMS:
        t = re.sub(r"(?i)(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", " ", t)
    return tidy(t)

def find_promo(text):
    low = f" {(text or '').lower()} "
    return sorted({p for p in PROMO_TERMS if re.search(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", low)})

def find_claims(text):
    low = f" {(text or '').lower()} "
    return sorted({c for c in DISEASE_CLAIMS if re.search(r"(?<![a-z0-9])" + re.escape(c) + r"(?![a-z0-9])", low)})

def find_banned(text, allow=""):
    a = set(allow or "")
    return sorted({c for c in (text or "") if c in BANNED_TITLE_CHARS and c not in a})

def shouting(w):
    core = re.sub(r"[-/]", "", w or "")
    if not core.isalpha() or len(core) < 4 or not w.isupper(): return False
    return not all(p.upper() in ACRONYMS or len(p) <= 2 for p in re.split(r"[-/]", w) if p)

def trim_to(s, limit):
    s = ws(s)
    if clen(s) <= limit: return s, ""
    cut = s[:limit]
    if " " in cut: cut = cut.rsplit(" ", 1)[0]
    return tidy(cut), tidy(s[len(cut):])

def parse_lines(text):
    out = []
    for raw in (text or "").splitlines():
        line = ws(BULLET_MARK_RE.sub("", raw))
        if line: out.append(line)
    return out

# ================================================================= AUDITS
SEV_E, SEV_W, SEV_OK = "error", "warn", "ok"

@dataclass
class Issue:
    severity: str
    message: str

@dataclass
class Audit:
    field: str; value: str; count: int; limit: int
    issues: list = field(default_factory=list)
    @property
    def errors(self): return [i for i in self.issues if i.severity == SEV_E]
    @property
    def warns(self):  return [i for i in self.issues if i.severity == SEV_W]

def audit_title(t, brand="", media=False):
    t = t or ""; lim = TITLE_LIMIT_MEDIA if media else TITLE_LIMIT
    a = Audit("Title", t, clen(t), lim)
    if not t.strip():
        a.issues.append(Issue(SEV_E, "Title is empty.")); return a
    if a.count > lim:
        a.issues.append(Issue(SEV_E, f"{a.count - lim} characters over limit."))
    b = find_banned(t, brand)
    if b: a.issues.append(Issue(SEV_E, "Characters not allowed outside brand: " + " ".join(b)))
    if no_emoji(t) != t: a.issues.append(Issue(SEV_E, "Emoji are not allowed."))
    p = find_promo(t)
    if p: a.issues.append(Issue(SEV_E, "Promotional claims: " + ", ".join(p[:5])))
    if not a.errors and not a.warns:
        a.issues.append(Issue(SEV_OK, "Compliant."))
    return a

def audit_highlights(t):
    t = t or ""; a = Audit("Item Highlights", t, clen(t), HIGHLIGHT_LIMIT)
    if not t.strip():
        a.issues.append(Issue(SEV_W, "Empty."))
        return a
    if a.count > HIGHLIGHT_LIMIT:
        a.issues.append(Issue(SEV_E, f"{a.count - HIGHLIGHT_LIMIT} characters over limit."))
    if not a.errors and not a.warns: a.issues.append(Issue(SEV_OK, "Compliant."))
    return a

def audit_bullet(t, idx):
    t = t or ""; a = Audit(f"Bullet {idx}", t, clen(t), BULLET_HARD)
    if not t.strip():
        a.issues.append(Issue(SEV_W, "Empty bullet.")); return a
    if a.count > BULLET_HARD:
        a.issues.append(Issue(SEV_E, f"Over {BULLET_HARD} character cap."))
    if not a.errors and not a.warns: a.issues.append(Issue(SEV_OK, "Compliant."))
    return a

def audit_bullets_total(bullets):
    total = sum(clen(b) for b in bullets or [])
    a = Audit("All bullets", "", total, BULLETS_TOTAL_MAX)
    if total > BULLETS_TOTAL_MAX:
        a.issues.append(Issue(SEV_W, f"{total} total characters across bullets."))
    else:
        a.issues.append(Issue(SEV_OK, f"{total}/{BULLETS_TOTAL_MAX} characters."))
    return a

def audit_backend(terms):
    t = terms or ""; a = Audit("Search terms", t, blen(t), BACKEND_BYTES)
    if not t.strip():
        a.issues.append(Issue(SEV_W, "Empty.")); return a
    if a.count > BACKEND_BYTES:
        a.issues.append(Issue(SEV_E, f"{a.count} bytes. Over {BACKEND_BYTES} limit."))
    if not a.errors and not a.warns: a.issues.append(Issue(SEV_OK, "Compliant."))
    return a

def score(audits):
    s = 100
    for a in audits: s -= 18 * len(a.errors) + 5 * len(a.warns)
    s = max(0, min(100, s))
    g = "A" if s >= 90 else "B" if s >= 80 else "C" if s >= 70 else "D" if s >= 55 else "F"
    return s, g

# ================================================================= FACTS
@dataclass
class Facts:
    brand: str = ""
    product_type: str = ""
    attr1: str = ""          # Priority 1
    attr2: str = ""          # Priority 2
    attr3: str = ""
    attr4: str = ""
    usp: str = ""            
    size_gender: str = ""    # Appended at tail end
    features: list = field(default_factory=list)
    use_case: str = ""

    @property
    def size(self): return self.size_gender

    def ordered(self):
        return [("brand", self.brand), ("attr1", self.attr1),
                ("product_type", self.product_type), ("attr2", self.attr2),
                ("usp", self.usp), ("size_gender", self.size_gender),
                ("attr3", self.attr3), ("attr4", self.attr4)]

# ================================================================= TITLE
def fix_title(t, brand="", media=False):
    lim = TITLE_LIMIT_MEDIA if media else TITLE_LIMIT
    t = ws(no_emoji(no_html(t)))
    t = "".join(c for c in t if c not in BANNED_TITLE_CHARS)
    t = tidy(strip_promo(ws(t)))
    return trim_to(ws(t), lim)

def brand_first(title, brand):
    brand, title = ws(brand), ws(title)
    if not brand: return title
    if n(title).startswith(n(brand) + " ") or n(title) == n(brand): return title
    rest = tidy(re.sub(r"(?i)(?<![a-z0-9])" + re.escape(brand) + r"(?![a-z0-9])", " ", title))
    return ws(f"{brand} {rest}") if rest else brand

def _title_pass(f: Facts, media=False):
    """
    Title Assembly Priority Rules:
    1. Brand
    2. Attribute 1 (Strongest feature qualifier)
    3. Product Type
    4. Attribute 2
    5. USP
    6. Size & Gender (Appended at tail end)
    """
    lim = TITLE_LIMIT_MEDIA if media else TITLE_LIMIT
    size_gen = abbreviate_units(ws(f.size_gender))
    tail = f", {size_gen}" if size_gen else ""
    budget = max(0, lim - clen(tail))

    head, used = "", set()
    priority_fields = [
        ("brand", f.brand),
        ("attr1", f.attr1),
        ("product_type", f.product_type),
        ("attr2", f.attr2),
        ("usp", f.usp)
    ]

    for key, val in priority_fields:
        v = drop_filler(ws(val)) if key in ("attr1", "product_type", "attr2", "usp") else ws(val)
        if not v: continue
        cand = ws(f"{head} {v}") if head else v
        if clen(cand) <= budget and n(v) not in n(head):
            head = cand
            used.add(key)

    if size_gen:
        used.add("size_gender")

    title = ws(head + tail) if head else ws(tail.lstrip(", "))
    title = brand_first(title, f.brand)
    return fix_title(title, f.brand, media)[0], used

# ================================================================= HIGHLIGHTS
def _highlights_pass(f: Facts, title, used, extra=None):
    """
    Pulls leftovers from facts and extra mined keywords that didn't fit into the title.
    """
    spec_side = [ws(f.attr1), abbreviate_units(ws(f.size_gender))]
    left, seen = "", set()
    for sp in [x for x in spec_side if x]:
        k = n(sp)
        if not k or k in seen: continue
        cand = f"{left}, {sp}" if left else sp
        if clen(cand) <= HIGHLIGHT_LIMIT // 2:
            seen.add(k); left = cand

    leftovers = [v for key, v in f.ordered() if key not in used and ws(v)]
    use_pool = leftovers + [ws(f.usp), ws(f.use_case)] + \
               [ws(x) for x in (f.features or [])] + list(extra or [])
    right, placed = "", set()
    for u in use_pool:
        if not u: continue
        k = n(u)
        if not k or k in seen: continue
        seen.add(k)
        cand = f"{right}, {u}" if right else u
        whole = f"{left}; {cand}" if left else cand
        if clen(whole) <= HIGHLIGHT_LIMIT:
            right = cand; placed.add(k)

    out = f"{left}; {right}" if (left and right) else (left or right)
    out = strip_conjunctions(tidy(no_emoji(no_html(out))))
    out = trim_to(out, HIGHLIGHT_LIMIT)[0]
    unplaced = [u for u in use_pool if ws(u) and n(u) not in placed and n(u) not in n(out)]
    return out, unplaced

# ================================================================= BULLETS
BENEFIT = {
 "stainless":"resists rust and wipes clean in seconds","glass":"will not stain or hold onto smells",
 "abs":"absorbs impact without cracking","eps":"absorbs impact energy on contact",
 "vented":"moves air across the head so it stays cooler","certified":"meets published safety standard",
}

HEADER_MAP = [
 ("AIRFLOW", r"vent|airflow|breathab|mesh|cool"),
 ("ADJUSTABLE FIT", r"adjust|dial|strap|fit\b|sizing"),
 ("SAFETY CERTIFIED", r"cpsc|astm|ce\b|certif|standard|tested"),
 ("IMPACT PROTECTION", r"impact|shell|abs|eps|absorb|protect"),
]

def short_header(phrase, used):
    low = n(phrase)
    for name, pat in HEADER_MAP:
        if re.search(pat, low) and name not in used:
            return name
    return "KEY FEATURE"

def make_bullet(header, benefit, detail=""):
    body = f"{benefit}; {detail}" if detail else benefit
    body = number_units(body)
    return f"{header.upper()}: {body}"

def build_bullets(f: Facts, max_bullets=MAX_BULLETS):
    feats = [ws(x) for x in (f.features or []) if ws(x)]
    out = []
    used_h = set()
    for row in feats[:max_bullets]:
        hdr = short_header(row, used_h)
        used_h.add(hdr)
        out.append(make_bullet(hdr, row))
    return out

def is_paragraph(text):
    return clen(ws(text)) > 160 and len(re.findall(r"[.!?]", text or "")) >= 2

def parse_bullets(text, max_bullets=MAX_BULLETS):
    return parse_lines(text), "lines"

def rewrite_bullet(b, pool, used, used_headers=None, header_hint=""):
    return make_bullet("FEATURE", b)

# ================================================================= BACKEND
def build_backend(keywords, exclude_text="", brand="", limit=BACKEND_BYTES):
    exclude = set(nkw(exclude_text).split()) | set(nkw(brand).split())
    kept, seen = [], set()
    dropped_visible, dropped_dupe, dropped_stop = [], [], []
    for kw in keywords or []:
        for w in nkw(kw).split():
            if len(w) < 2 or w in BACKEND_STOP:
                dropped_stop.append(w); continue
            if w in exclude:
                dropped_visible.append(w); continue
            if w in seen:
                dropped_dupe.append(w); continue
            seen.add(w); kept.append(w)
    out, overflow = "", []
    for w in kept:
        cand = f"{out} {w}" if out else w
        if blen(cand) > limit: overflow.append(w); continue
        out = cand
    return {"terms": out, "bytes": blen(out), "limit": limit,
            "dropped_visible": sorted(set(dropped_visible)),
            "dropped_dupe": sorted(set(dropped_dupe)),
            "dropped_stop": sorted(set(dropped_stop)), "overflow": overflow}

# ================================================================= MINING
def detect_type(text):
    w = ws(text).split()
    return (" ".join(w[-2:]) if len(w) >= 2 else (w[0] if w else "")), "guess"

def mine_title(raw, brand=""):
    t = ws(no_html(no_emoji(raw)))
    size = ""
    m = PACK_RE.search(t)
    pack = ws(m.group(0)) if m else ""
    ms = SIZE_RE.search(t)
    if ms: size = ws(ms.group(0))
    ptype, conf = detect_type(t)
    segs = [ws(x) for x in re.split(r"\s*[|,\u2013\u2014]\s*", t) if ws(x)]
    feats = [s for s in segs if len(s.split()) >= 2]
    return {"product_type": ptype, "type_confidence": conf, "size": size,
            "pack": pack, "features": feats}

def kw_score(rank, freq, source):
    return int(round(min(100, max(0, 10 - min(rank, 10)) / 10 * 60 + min(freq, 5) / 5 * 25)))

def volume_colour(s):
    hue = int(max(0, min(100, s)) * 1.2)
    return f"hsl({hue},72%,90%)", f"hsl({hue},70%,26%)", f"hsl({hue},60%,72%)"

def force_into_title(title, keywords, brand, limit=TITLE_LIMIT, media=False):
    return title, [], [], keywords

def force_into_bullets(bullets, keywords, pool=None, max_bullets=MAX_BULLETS):
    return bullets or [], [], [], keywords

def compose(f: Facts, media=False, extra=None, max_bullets=MAX_BULLETS):
    title, used = _title_pass(f, media)
    highlights, unplaced = _highlights_pass(f, title, used, extra)
    bullets = build_bullets(f, max_bullets)
    return {"title": title, "highlights": highlights, "bullets": bullets,
            "in_title": sorted(used), "to_highlights": unplaced,
            "to_bullets": [], "logic": {}}
