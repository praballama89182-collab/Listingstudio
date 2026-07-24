"""
Listing Studio — Amazon title, item highlights, bullets and search terms (2026 rules).
Rules engine lives in core.py. This file is presentation only.
"""
import json, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import streamlit.components.v1 as components
import core as C
import images as IMG
from PIL import Image

# Custom Embedded Tab Icon (Studio Sparkle + Edit Pencil SVG)
FAVICON = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 128 128'><rect width='128' height='128' rx='32' fill='%237B6CFF'/><path d='M36 92 L80 48 L92 60 L48 104 L28 104 Z' fill='%23FFFFFF'/><path d='M80 32 L96 48' stroke='%23FFE29A' stroke-width='8'/></svg>"

st.set_page_config(page_title="Listing Studio", page_icon=FAVICON, layout="wide")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Archivo:wght@600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');
.stApp{background:#fff}
html,body,[class*="css"]{font-family:'Atkinson Hyperlegible','Inter',system-ui,sans-serif;
 color:#0f1419;font-size:16px;line-height:1.55}
h1,h2,h3,h4,h5{font-family:'Archivo',sans-serif;color:#0b0f14;letter-spacing:-.015em}
.stMarkdown p,label,li{font-size:15.5px;color:#26303c}
.stCodeBlock code,pre code{font-family:'JetBrains Mono',monospace!important;font-size:15px!important;
 line-height:1.6!important;color:#0f1419!important}
.stCodeBlock{border:1px solid #d7dce4!important;border-radius:10px!important;background:#fbfcfe!important}
input,textarea{font-size:15.5px!important;color:#0f1419!important}
.block-container{padding-top:1.3rem;max-width:1380px}
.hero{background:linear-gradient(115deg,#ffe29a,#ff9a8b 38%,#ff6fa5 68%,#7b6cff);
 border-radius:18px;padding:20px 24px;margin-bottom:16px;box-shadow:0 10px 26px rgba(123,108,255,.2)}
.hero h1{font-size:25px;font-weight:800;margin:0;color:#20142e}
.hero p{margin:6px 0 0;font-size:13px;color:#3a2440;font-weight:500;max-width:840px}
.lbl{display:flex;justify-content:space-between;align-items:baseline;margin:14px 0 2px}
.lbl b{font-size:15px;font-weight:700;color:#0b0f14}
.lbl span{font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:700;
 padding:3px 10px;border-radius:999px}
.ok{background:#dcfce7;color:#0b7a46;border:1px solid #86efac}
.warn{background:#fef3c7;color:#96690b;border:1px solid #fcd34d}
.bad{background:#ffe4e6;color:#b4143c;border:1px solid #fda4af}
.sc{display:flex;align-items:center;gap:18px;background:#fff;border:1px solid #e7eaf3;
 border-left:8px solid var(--c,#22c55e);border-radius:14px;padding:14px 20px;margin:8px 0 14px;
 box-shadow:0 4px 14px rgba(20,26,41,.06)}
.sc .n{font-family:'JetBrains Mono',monospace;font-size:38px;font-weight:700;line-height:1}
.sc .m{font-size:12.5px;color:#6b7391}
.iss{font-size:14px;padding:7px 12px;border-radius:999px;margin:4px 0;background:#f7f9fc;
 border-left:4px solid #cbd5e1;color:#3a4256}
.iss.error{background:#fff1f2;border-left-color:#f43f5e}
.iss.warn{background:#fffbeb;border-left-color:#f59e0b}
.iss.ok{background:#f0fdf4;border-left-color:#22c55e}
.chip{display:inline-block;font-size:12px;font-weight:600;padding:4px 10px;margin:3px;
 border-radius:999px;border:1px solid}
.stTabs [data-baseweb="tab-list"]{gap:6px}
[data-baseweb="tab"]{font-weight:700;font-family:'Archivo',sans-serif;font-size:16px}
div.stButton>button[kind="primary"]{background:#7b6cff;border:0;font-weight:700;border-radius:10px}
</style>""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>Listing Studio</h1><p>Amazon title, item highlights, bullets '
 'and backend search terms, built to the 2026 rules. Everything updates as you type — there is no '
 'button to press.</p></div>', unsafe_allow_html=True)

# --------------------------------------------------------------- helpers
def cls(count, limit):
    return "bad" if count > limit else "warn" if count > limit * .9 else "ok"

def copy_button(text, key, caption=""):
    payload = json.dumps(text or "")
    components.html(f"""
      <div style="display:flex;align-items:center;gap:10px;font-family:'Atkinson Hyperlegible',
                  system-ui,sans-serif">
        <button id="cb{key}" style="background:#7b6cff;color:#fff;border:0;border-radius:8px;
          padding:7px 16px;font-size:14px;font-weight:700;cursor:pointer">Copy</button>
        <span style="font-size:13px;color:#5b6472">{C.esc(caption)}</span>
      </div>
      <script>
        const t{key} = {payload};
        const b{key} = document.getElementById("cb{key}");
        b{key}.onclick = async () => {{
          try {{ await navigator.clipboard.writeText(t{key}); }}
          catch (e) {{
            const ta = document.createElement('textarea');
            ta.value = t{key}; ta.style.position='fixed'; ta.style.opacity='0';
            document.body.appendChild(ta); ta.select();
            try {{ document.execCommand('copy'); }} catch (err) {{}}
            document.body.removeChild(ta);
          }}
          b{key}.textContent = 'Copied'; b{key}.style.background = '#22c55e';
          setTimeout(() => {{ b{key}.textContent='Copy'; b{key}.style.background='#7b6cff'; }}, 1400);
        }};
      </script>""", height=44)

def label(text, count=None, limit=None, unit="characters"):
    right = f'<span class="{cls(count,limit)}">{count} / {limit} {unit}</span>' if limit else ""
    st.markdown(f'<div class="lbl"><b>{C.esc(text)}</b>{right}</div>', unsafe_allow_html=True)

def issues(a):
    for i in a.issues:
        tag = {"error": "Fix", "warn": "Check", "ok": "OK"}[i.severity]
        st.markdown(f'<div class="iss {i.severity}"><b>{tag}</b> &nbsp;{C.esc(i.message)}</div>',
                    unsafe_allow_html=True)

def scorecard(audits):
    s, g = C.score(audits)
    col = "#22c55e" if s >= 80 else "#f59e0b" if s >= 55 else "#f43f5e"
    e = sum(len(a.errors) for a in audits); w = sum(len(a.warns) for a in audits)
    st.markdown(f'<div class="sc" style="--c:{col}"><div class="n" style="color:{col}">{s}</div>'
                f'<div><b style="color:{col}">Grade {g}</b><div class="m">{e} blocking · {w} to check'
                f'</div></div></div>', unsafe_allow_html=True)

def copy_out(title, high, bullets, backend="", desc="", key="x"):
    live = [b for b in bullets if b]
    st.markdown("#### Copy each field")
    label("Title", C.clen(title), C.TITLE_LIMIT)
    copy_button(title, f"t{key}"); st.code(title or "", language=None)

    label("Item Highlights", C.clen(high), C.HIGHLIGHT_LIMIT)
    copy_button(high, f"h{key}"); st.code(high or "", language=None)

    for i, b in enumerate(live, 1):
        label(f"Bullet {i}", C.clen(b), C.BULLET_MAX)
        copy_button(b, f"b{key}{i}"); st.code(b, language=None)

    label(f"All {len(live)} bullets, one per line",
          sum(C.clen(b) for b in live), C.BULLETS_TOTAL_MAX)
    copy_button("\n".join(live), f"all{key}", "one bullet per line")
    st.code("\n".join(live), language=None)

    if backend:
        label("Backend search terms", C.blen(backend), C.BACKEND_BYTES, "bytes")
        copy_button(backend, f"k{key}"); st.code(backend, language=None)

def copy_raw(pairs, key="r"):
    with st.expander("Copy the original details you pasted"):
        for name, val in pairs:
            if C.ws(val):
                label(name, C.clen(val), None)
                st.code(val, language=None)

# --------------------------------------------------------------- sidebar
with st.sidebar:
    st.subheader("Settings")
    vendor = st.radio("Account", ["Seller — 5 bullets", "Vendor — 10 bullets"], index=0)
    maxb = 10 if vendor.startswith("Vendor") else 5
    media = st.checkbox("Media category (200-character titles)", value=False)
    lim = C.TITLE_LIMIT_MEDIA if media else C.TITLE_LIMIT
    st.caption(f"Title limit in use: **{lim} characters**")
    st.markdown("---")
    st.caption("**Field limits**  \nTitle 75 · Highlights 125 · Bullets 150–200 each, "
               "1000 total · Search terms 249 bytes")

# Tabs placed in requested sequence
tabs = st.tabs(["Build a listing", "Improve a listing", "Keyword research", "Rules", "Listing images", "AI generation"])

# ================================================================ BUILD (Tab 0)
with tabs[0]:
    st.markdown("### Product details")
    st.caption("Fields are read in priority order: Brand -> Model Name -> Attribute 1 -> Attribute 2 -> Type -> USP. "
               "Whatever doesn't fit the title cascades down into Highlights and Bullets.")

    def clear_build():
        for k in ("f_brand","f_model","f_type","f_a1","f_a2","f_a3","f_a4","f_usp","f_size","f_use","f_feat"):
            if k in st.session_state:
                st.session_state[k] = ""

    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    with r1c1:
        st.markdown('<div class="lbl"><b>1 · Brand name</b></div>', unsafe_allow_html=True)
        brand = st.text_input("br", key="f_brand", label_visibility="collapsed", placeholder="Rider")
    with r1c2:
        st.markdown('<div class="lbl"><b>2 · Model Name</b></div>', unsafe_allow_html=True)
        model_name = st.text_input("mo", key="f_model", label_visibility="collapsed", placeholder="AeroX 500")
    with r1c3:
        st.markdown('<div class="lbl"><b>3 · Attribute 1</b></div>', unsafe_allow_html=True)
        a1 = st.text_input("a1", key="f_a1", label_visibility="collapsed", placeholder="Real Carbon Fibre")
    with r1c4:
        st.markdown('<div class="lbl"><b>4 · Attribute 2</b></div>', unsafe_allow_html=True)
        a2 = st.text_input("a2", key="f_a2", label_visibility="collapsed", placeholder="Dual Visor")

    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1:
        st.markdown('<div class="lbl"><b>5 · Product Type</b></div>', unsafe_allow_html=True)
        ptype = st.text_input("pt", key="f_type", label_visibility="collapsed", placeholder="Modular Motorcycle Helmet")
    with r2c2:
        st.markdown('<div class="lbl"><b>6 · USP</b></div>', unsafe_allow_html=True)
        usp = st.text_input("up", key="f_usp", label_visibility="collapsed", placeholder="1.48 kg Lightweight")
    with r2c3:
        st.markdown('<div class="lbl"><b>7 · Size or Gender</b></div>', unsafe_allow_html=True)
        size = st.text_input("sz", key="f_size", label_visibility="collapsed", placeholder="Medium, 500 ML or Men's")

    r3c1, r3c2 = st.columns(2)
    with r3c1:
        st.markdown('<div class="lbl"><b>8 · Attribute 3 (Highlight Focus)</b></div>', unsafe_allow_html=True)
        a3 = st.text_input("a3", key="f_a3", label_visibility="collapsed", placeholder="DOT and ECE Certified")
    with r3c2:
        st.markdown('<div class="lbl"><b>9 · Attribute 4 (Highlight Focus)</b></div>', unsafe_allow_html=True)
        a4 = st.text_input("a4", key="f_a4", label_visibility="collapsed", placeholder="Flip Up Chin Bar")

    st.markdown('<div class="lbl"><b>Features — one per line</b></div>', unsafe_allow_html=True)
    feat_raw = st.text_area("ft", key="f_feat", height=140, label_visibility="collapsed",
        placeholder="Superior Ventilation System: top and rear vents keep air moving\n"
                    "Retractable sun visor cuts glare without swapping shields")
    st.button("Clear all boxes", key="f_clear", on_click=clear_build)

    feats, fmode = C.parse_bullets(feat_raw, maxb)

    if C.ws(brand) and C.ws(ptype):
        facts = C.Facts(brand=brand, model_name=model_name, product_type=ptype, attr1=a1, attr2=a2, attr3=a3, attr4=a4,
                        usp=usp, size_gender=size, features=feats)
        res = C.compose(facts, media, max_bullets=maxb)
        title, high, bullets = res["title"], res["highlights"], res["bullets"]

        au = [C.audit_title(title, brand, media), C.audit_highlights(high)]
        au += [C.audit_bullet(b, i + 1) for i, b in enumerate(bullets)]
        au.append(C.audit_bullets_total(bullets))

        st.markdown("---")
        scorecard(au)

        h1, h2 = st.columns(2)
        with h1:
            st.markdown("**Moved down to Item Highlights**")
            st.markdown("".join(f'<span class="chip ok">{C.esc(x)}</span>'
                                for x in res["to_highlights"]) or "_none_", unsafe_allow_html=True)
        with h2:
            st.markdown("**Moved down to Bullets**")
            st.markdown("".join(f'<span class="chip warn">{C.esc(x)}</span>'
                                for x in res["to_bullets"]) or "_none_", unsafe_allow_html=True)

        copy_out(title, high, bullets, key="b")
        st.session_state["listing"] = {"title": title, "high": high, "bullets": bullets, "brand": brand, "features": feats}
    else:
        st.info("Enter a brand name and a product type to see the listing.")

# ================================================================ IMPROVE (Tab 1)
with tabs[1]:
    st.markdown("### Paste your current listing")
    st.caption("Attribute 1 & Attribute 2 are prioritized in the title after Model Name. "
               "Overflow parts from Title cascade into Highlights, and rest into Bullets without word duplication.")

    def clear_imp():
        for k in ("i_brand","i_model","i_title","i_bul","i_a1","i_a2","i_a3","i_a4","i_size","i_gender"):
            if k in st.session_state:
                st.session_state[k] = ""

    ic1, ic2, ic3 = st.columns([1, 1, 2])
    with ic1:
        st.markdown('<div class="lbl"><b>Brand name</b></div>', unsafe_allow_html=True)
        ibrand = st.text_input("ib", key="i_brand", label_visibility="collapsed", placeholder="Rider")
    with ic2:
        st.markdown('<div class="lbl"><b>Model Name</b></div>', unsafe_allow_html=True)
        imodel = st.text_input("imo", key="i_model", label_visibility="collapsed", placeholder="AeroX 500")
    with ic3:
        st.markdown('<div class="lbl"><b>Current title</b></div>', unsafe_allow_html=True)
        iraw = st.text_area("it", key="i_title", height=80, label_visibility="collapsed",
                            placeholder="Rider ABS Scooter Helmet for Kids | 11 Vents | Pack of 2")
    if iraw:
        label("Length of what you pasted", C.clen(iraw), lim)

    mined = C.mine_title(iraw, ibrand) if C.ws(iraw) else None

    # Row 1: Title Priority
    jc1, jc2, jc3, jc4 = st.columns(4)
    with jc1:
        st.markdown('<div class="lbl"><b>Attribute 1 (Priority 1)</b></div>', unsafe_allow_html=True)
        ia1 = st.text_input("ia1", key="i_a1", label_visibility="collapsed", placeholder="ABS Shell")
    with jc2:
        st.markdown('<div class="lbl"><b>Attribute 2 (Priority 2)</b></div>', unsafe_allow_html=True)
        ia2 = st.text_input("ia2", key="i_a2", label_visibility="collapsed", placeholder="Matte Black")
    with jc3:
        st.markdown('<div class="lbl"><b>Size (Tail)</b></div>', unsafe_allow_html=True)
        isize = st.text_input("isz", key="i_size", label_visibility="collapsed", placeholder="Medium")
    with jc4:
        st.markdown('<div class="lbl"><b>Gender (Last Priority)</b></div>', unsafe_allow_html=True)
        igender = st.text_input("ign", key="i_gender", label_visibility="collapsed", placeholder="Kids / Unisex")

    # Row 2: Highlights Priority
    hc1, hc2 = st.columns(2)
    with hc1:
        st.markdown('<div class="lbl"><b>Attribute 3 (Highlight Focus)</b></div>', unsafe_allow_html=True)
        ia3 = st.text_input("ia3", key="i_a3", label_visibility="collapsed", placeholder="CPSC & DOT Certified")
    with hc2:
        st.markdown('<div class="lbl"><b>Attribute 4 (Highlight Focus)</b></div>', unsafe_allow_html=True)
        ia4 = st.text_input("ia4", key="i_a4", label_visibility="collapsed", placeholder="11 Air Vents Ventilation")

    st.markdown('<div class="lbl"><b>Current bullets — one per line</b></div>', unsafe_allow_html=True)
    ibul = st.text_area("ibl", key="i_bul", height=150, label_visibility="collapsed", placeholder="Vented shell\nAdjustable dial fit")
    st.button("Clear all boxes", key="i_clear", on_click=clear_imp)

    if mined and C.ws(iraw):
        tail_spec = ", ".join([x for x in [isize or mined["size"], igender] if C.ws(x)])
        facts = C.Facts(
            brand=ibrand,
            model_name=imodel,
            product_type=mined["product_type"],
            attr1=ia1 or (mined["features"][0] if mined["features"] else ""),
            attr2=ia2 or (mined["features"][1] if len(mined["features"]) > 1 else ""),
            attr3=ia3,
            attr4=ia4,
            size_gender=tail_spec,
            features=mined["features"]
        )

        _res = C.compose(facts, media, extra=mined["features"], max_bullets=maxb)
        title, high, bullets = _res["title"], _res["highlights"], _res["bullets"]

        au = [C.audit_title(title, ibrand, media), C.audit_highlights(high)]
        au += [C.audit_bullet(b, i + 1) for i, b in enumerate(bullets)]
        au.append(C.audit_bullets_total(bullets))

        st.markdown("---")
        scorecard(au)
        copy_out(title, high, bullets, key="i")
        st.session_state["listing"] = {"title": title, "high": high, "bullets": bullets, "brand": ibrand, "features": mined["features"]}

# ================================================================ KEYWORDS & BACKEND (Tab 2)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
MARKETS = {"amazon.com (US)": "ATVPDKIKX0DER", "amazon.co.uk (UK)": "A1F83G8C2ARO7P",
           "amazon.de (DE)": "A1PA6795UKMFR9", "amazon.ca (CA)": "A2EUQ1WTGCTBG2",
           "amazon.in (IN)": "A21TJRUUN4KGV"}

def _get(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def _google(seed):
    d = _get("https://suggestqueries.google.com/complete/search?client=firefox&q=" + urllib.parse.quote(seed))
    return [str(x) for x in d[1]] if isinstance(d, list) and len(d) > 1 else []

def _amazon(seed, mid):
    d = _get("https://completion.amazon.com/api/2017/suggestions?mid=" + mid + "&alias=aps&limit=11&prefix=" + urllib.parse.quote(seed))
    return [s.get("value", "") for s in d.get("suggestions", []) if s.get("value")] if isinstance(d, dict) else []

@st.cache_data(ttl=3600, show_spinner=False)
def fetch(seed, source, mid, expand):
    seed = C.ws(seed)
    if not seed: return [], "Enter a seed keyword."
    seeds = [seed] + ([f"{seed} {c}" for c in "abcdefghijklmnopqrstuvwxyz"] if expand else [])
    fn = (lambda s: _google(s)) if source == "Google" else (lambda s: _amazon(s, mid))
    rank, freq, disp = {}, {}, {}
    try:
        with ThreadPoolExecutor(max_workers=8) as p:
            for got in p.map(fn, seeds):
                for i, term in enumerate(got):
                    t = C.ws(term); k = t.lower()
                    if not t: continue
                    disp.setdefault(k, t); freq[k] = freq.get(k, 0) + 1
                    rank[k] = min(rank.get(k, 99), i)
    except Exception as e:
        return [], f"Could not reach {source}: {e}"
    rows = [{"term": disp[k], "rank": rank[k], "freq": freq[k], "score": C.kw_score(rank[k], freq[k], source)} for k in disp]
    rows.sort(key=lambda r: (-r["score"], r["rank"]))
    return rows, ""

with tabs[2]:
    st.markdown("### Find keywords")
    k1, k2, k3 = st.columns([2, 1, 1])
    with k1:
        seed = st.text_input("Seed keyword", key="k_seed", placeholder="kids scooter helmet")
    with k2:
        src = st.selectbox("Source", ["Amazon", "Google"], key="k_src")
    with k3:
        mkt = st.selectbox("Marketplace", list(MARKETS), key="k_mkt", disabled=(src != "Amazon"))
    expand = st.checkbox("Expand A to Z for long-tail terms", value=True)

    if st.button("Fetch keywords", type="primary", key="k_go"):
        with st.spinner(f"Asking {src}…"):
            rows, err = fetch(seed, src, MARKETS[mkt], expand)
        st.session_state["k_rows"], st.session_state["k_err"] = rows, err

    rows = st.session_state.get("k_rows", [])

    if rows:
        st.caption(f"Showing all {len(rows)} discovered keywords ordered by score:")
        st.markdown("".join(
            f'<span class="chip" style="background:{C.volume_colour(r["score"])[0]};'
            f'color:{C.volume_colour(r["score"])[1]};border-color:{C.volume_colour(r["score"])[2]}">'
            f'{C.esc(r["term"])} <b>{r["score"]}</b></span>' for r in rows),
            unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Select & Route Keywords")
    manual = st.text_area("Your custom keywords — one per line", key="k_man", height=90)
    pool = list(dict.fromkeys([r["term"] for r in rows] + C.parse_lines(manual)))

    a1_, a2_, a3_ = st.columns(3)
    with a1_:
        sel_t = st.multiselect("Into Title", pool, key="k_t")
    with a2_:
        sel_b = st.multiselect("Into Bullets", pool, key="k_b")
    with a3_:
        sel_s = st.multiselect("Into Search Terms", pool, key="k_s")

    L = st.session_state.get("listing", {})
    all_selected = list(dict.fromkeys(sel_t + sel_b + sel_s))

    # Dynamic Unique Terms Extraction Engine
    computed_backend = C.build_backend(
        all_selected, 
        exclude_text=f"{L.get('title', '')} {L.get('high', '')}", 
        brand=L.get('brand', '')
    )["terms"]

    # Pre-update session state safely before rendering text_area
    if st.session_state.get("last_auto_backend") != computed_backend:
        st.session_state["backend_edit"] = computed_backend
        st.session_state["last_auto_backend"] = computed_backend

    st.markdown("---")
    st.markdown("### Backend Search Terms (Editable Output)")
    st.caption("Extracted unique single words from selected keywords. Edit directly below before copying.")

    edited_terms = st.text_area(
        "Backend Terms Output", 
        key="backend_edit", 
        height=100, 
        label_visibility="collapsed"
    )

    current_bytes = C.blen(edited_terms)
    label("Backend Search Terms", current_bytes, C.BACKEND_BYTES, unit="bytes")
    
    copy_button(edited_terms, "backend_copy")

# ================================================================ RULES (Tab 3)
with tabs[3]:
    st.markdown("### The rules this tool enforces")
    st.markdown(f"""
**Title — {C.TITLE_LIMIT} characters**
`[Brand] + [Model Name] + [Attribute 1] + [Attribute 2] + [Product Type], [USP], [Size / Gender]`

**Item Highlights — {C.HIGHLIGHT_LIMIT} characters**
Focused on Attribute 3, Attribute 4, and overflow parts from Attribute 1 & 2.

**Bullets — {C.BULLET_MIN} to {C.BULLET_MAX} characters each**
Contains remaining feature details and unplaced attributes across all fields.

**Backend search terms — {C.BACKEND_BYTES} bytes**
Unique single words, all lowercase, single spaces. Max 249 bytes.
""")

# ================================================================ IMAGES (Tab 4)
def _show_gallery(built, asin, keyprefix):
    files = []
    for i, (name, im, is_main) in enumerate(built):
        data = IMG.encode(im)
        fname = IMG.filename(asin, 0 if is_main else i)
        files.append((fname, data))
        st.markdown(f"#### {i+1}. {name}")
        st.image(im, use_container_width=True)
        st.download_button(f"Download {fname}", data, fname, "image/jpeg", key=f"{keyprefix}dl{i}")
    return files

with tabs[4]:
    st.markdown("### Build each image yourself")
    up = st.file_uploader("Product photo on a plain background", type=["jpg", "jpeg", "png", "webp"], key="m_main")
    extras_up = st.file_uploader("More angles", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key="m_extra")
    m_asin = st.text_input("ASIN or SKU", key="m_asin", placeholder="B0XXXXXXXX")
    n_slots = st.number_input("How many images", 1, 9, 5, key="m_n")

    tmpl_names = list(IMG.TEMPLATES.keys())
    defaults = ["Main — pure white", "Hero benefit", "Feature callouts", "Certification badges", "Spec or statistic"]
    slots = []
    for i in range(int(n_slots)):
        with st.expander(f"Image {i+1}", expanded=(i < 2)):
            kind_label = st.selectbox("Template", tmpl_names, key=f"m_k{i}", index=tmpl_names.index(defaults[i % len(defaults)]))
            kind = IMG.TEMPLATES[kind_label]
            bgf = None
            cfg = {}
            if kind != "main":
                c1, c2 = st.columns(2)
                with c1: cfg["headline"] = st.text_input("Headline", key=f"m_h{i}")
                with c2: cfg["accent"] = st.text_input("Accent, shown in red", key=f"m_a{i}")
                if kind in ("hero",): cfg["subline"] = st.text_area("Sub-line", key=f"m_s{i}", height=70)
                bgf = st.file_uploader("Background photo, optional", type=["jpg", "jpeg", "png", "webp"], key=f"m_bg{i}")
            slots.append((kind_label, kind, cfg, bgf))

    if up is not None:
        try:
            src = Image.open(up)
            others = [Image.open(f) for f in (extras_up or [])]
            built = []
            with st.spinner("Rendering…"):
                for label_, kind, cfg, bgf in slots:
                    bg = Image.open(bgf) if bgf else None
                    built.append((label_, IMG.render(kind, src, cfg, extras=others, bg=bg), kind == "main"))
            _show_gallery(built, m_asin, "man")
        except Exception as e:
            st.error(f"Could not render: {e}")

# ================================================================ AI GENERATION (Tab 5)
with tabs[5]:
    st.markdown("### Generate the set automatically")
    a_up = st.file_uploader("Product photo", type=["jpg", "jpeg", "png", "webp"], key="a_main")
    a_bg = st.file_uploader("Background photo", type=["jpg", "jpeg", "png", "webp"], key="a_bg")
    a_extra = st.file_uploader("More angles", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key="a_extra")

    L = st.session_state.get("listing", {})
    a_asin = st.text_input("ASIN or SKU", key="a_asin", placeholder="B0XXXXXXXX")
    a_title = st.text_input("Title", key="a_title", value=L.get("title", ""))
    a_bul = st.text_area("Bullets", key="a_bul", height=150, value="\n".join(L.get("bullets", [])))

    if a_up is not None:
        try:
            src = Image.open(a_up)
            bg = Image.open(a_bg) if a_bg else None
            others = [Image.open(f) for f in (a_extra or [])]
            bullets = C.parse_lines(a_bul)
            plan = IMG.plan_from_copy(a_title, bullets, have_bg=bg is not None, n_extra=len(others))

            built = []
            with st.spinner("Rendering gallery…"):
                for p in plan:
                    use_bg = bg if p.get("use_bg") else None
                    built.append((p["name"], IMG.render(p["kind"], src, p["cfg"], extras=others, bg=use_bg), p["kind"] == "main"))
            _show_gallery(built, a_asin, "ai")
        except Exception as e:
            st.error(f"Could not generate: {e}")
