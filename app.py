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

    # Pre-populate session state if keywords change, allowing user manual override
    if "backend_edit" not in st.session_state or st.session_state.get("last_auto_backend") != computed_backend:
        st.session_state["backend_edit"] = computed_backend
        st.session_state["last_auto_backend"] = computed_backend

    st.markdown("---")
    st.markdown("### Backend Search Terms (Editable Output)")
    st.caption("Extracted unique single words from selected keywords. Edit directly below before copying.")

    # Editable text area
    edited_terms = st.text_area(
        "Backend Terms Output", 
        key="backend_edit", 
        height=100, 
        label_visibility="collapsed"
    )

    # Live Byte Count Audit
    current_bytes = C.blen(edited_terms)
    label("Backend Search Terms", current_bytes, C.BACKEND_BYTES, unit="bytes")
    
    copy_button(edited_terms, "backend_copy")
