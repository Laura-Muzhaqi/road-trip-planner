"""
🚗 Road Trip Planner — Μινιμαλιστικός Σχεδιαστής Οδικών Ταξιδιών
Χρησιμοποιεί OSRM (OpenStreetMap Routing Machine) για δωρεάν δρομολόγηση.
Τρέξε με: streamlit run app.py
"""

import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

# ─────────────────────────────────────────────
# ΣΤΑΘΕΡΕΣ ΤΙΜΕΣ ΚΑΥΣΙΜΩΝ (€/λίτρο) — Ελλάδα, Μάρτιος 2026
# ─────────────────────────────────────────────
FUEL_PRICES = {
    "⛽ Βενζίνη (95 οκτ.)": 2.05,
    "🛢️ Πετρέλαιο Κίνησης": 2.12,
    "💨 Υγραέριο (LPG)": 0.95,
}

# ─────────────────────────────────────────────
# ΔΙΟΔΙΑ 2026 — Πραγματικές τιμές ανά αυτοκινητόδρομο (Ι.Χ. επιβατικό)
# Πηγή: Επίσημες ανακοινώσεις παραχωρησιούχων, Ιανουάριος 2026
# ─────────────────────────────────────────────
# Κάθε εγγραφή: (τμήμα_start, τμήμα_end, κόστος_€, χλμ)
# Χρησιμοποιείται για να βρούμε ποια διαδρομή ταιριάζει και να υπολογίσουμε
# ρεαλιστικό €/100χλμ. Αν δεν ταιριάζει καμία, χρησιμοποιείται fallback.

TOLL_SEGMENTS = [
    # Αυτοκινητόδρομος Αιγαίου (Αθήνα–Θεσσαλονίκη, ~500χλμ) → 18.20€
    {"keywords": ["αθήνα", "θεσσαλονίκη"], "cost": 18.20, "km": 500},
    # Ολυμπία Οδός (Πάτρα–Ελευσίνα/Αθήνα, ~220χλμ) → 13.80€
    {"keywords": ["πάτρα", "αθήνα"], "cost": 13.80, "km": 220},
    {"keywords": ["πάτρα", "ελευσίνα"], "cost": 13.80, "km": 220},
    # Ολυμπία Οδός (Πάτρα–Πύργος, ~100χλμ) → 5.70€
    {"keywords": ["πάτρα", "πύργος"], "cost": 5.70, "km": 100},
    # Ιόνια Οδός (Αντίρριο–Ιωάννινα, ~160χλμ) → 15.00€
    {"keywords": ["αντίρριο", "ιωάννινα"], "cost": 15.00, "km": 160},
    {"keywords": ["ιωάννινα", "αντίρριο"], "cost": 15.00, "km": 160},
    # Μορέας (Κόρινθος–Τρίπολη–Καλαμάτα, ~205χλμ) → 11.75€
    {"keywords": ["κόρινθος", "καλαμάτα"], "cost": 11.75, "km": 205},
    {"keywords": ["καλαμάτα", "κόρινθος"], "cost": 11.75, "km": 205},
    {"keywords": ["κόρινθος", "τρίπολη"], "cost": 7.50, "km": 120},
    # Εγνατία (Ηγουμενίτσα–Θεσσαλονίκη, ~560χλμ) → ~25€
    {"keywords": ["ηγουμενίτσα", "θεσσαλονίκη"], "cost": 25.00, "km": 560},
    {"keywords": ["θεσσαλονίκη", "ηγουμενίτσα"], "cost": 25.00, "km": 560},
]

# Fallback: μέσος ρεαλιστικός όρος αν δεν αναγνωριστεί διαδρομή
# Βασισμένος στα πραγματικά δεδομένα 2026 (~3.50€/100χλμ για αυτοκινητόδρομους)
TOLL_RATE_FALLBACK = 3.50  # €/100χλμ


def estimate_tolls(distance_km: float, waypoints: list) -> float:
    """
    Εκτιμά τα διόδια βάσει της διαδρομής.
    Αν αναγνωριστεί γνωστή διαδρομή → χρησιμοποιεί πραγματικές τιμές.
    Αλλιώς → χρησιμοποιεί fallback €/100χλμ.
    """
    # Κανονικοποίηση ονομάτων για αναζήτηση
    joined = " ".join(waypoints).lower()
    # Αφαίρεση "ελλάδα" και παρόμοιων γενικών λέξεων
    joined = joined.replace("ελλάδα", "").replace("greece", "").strip()

    for seg in TOLL_SEGMENTS:
        if all(kw in joined for kw in seg["keywords"]):
            # Βρέθηκε γνωστό τμήμα — κλιμάκωση βάσει πραγματικής απόστασης
            rate = seg["cost"] / seg["km"]
            return round(rate * distance_km, 2)

    # Fallback για άγνωστες διαδρομές
    return round((distance_km / 100) * TOLL_RATE_FALLBACK, 2)

# OSRM δημόσιο API endpoint
OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"

# Nominatim για geocoding
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Road Trip Planner 🚗",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CUSTOM CSS — Μινιμαλιστικό Design
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=Playfair+Display:wght@600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #F7F5F0;
    color: #1A1A1A;
}

h1 {
    font-family: 'Playfair Display', serif !important;
    font-size: 2.4rem !important;
    font-weight: 600 !important;
    color: #1A1A1A !important;
    letter-spacing: -0.5px;
    margin-bottom: 0.2rem !important;
}

.subtitle {
    color: #444;
    font-size: 0.95rem;
    font-weight: 400;
    margin-bottom: 2rem;
}

.result-card {
    background: #ffffff;
    border-radius: 18px;
    padding: 2rem;
    box-shadow: 0 4px 24px rgba(0,0,0,0.07);
    margin-bottom: 1.5rem;
    color: #1A1A1A;
}

.split-card {
    background: #ffffff;
    border-radius: 18px;
    padding: 1.8rem 2rem;
    box-shadow: 0 4px 24px rgba(0,0,0,0.07);
    margin-bottom: 1.5rem;
    border-left: 4px solid #1A1A1A;
    color: #1A1A1A;
}

.metric-row {
    display: flex;
    gap: 1.2rem;
    flex-wrap: wrap;
    margin-top: 1rem;
}

/* Ανοιχτό φόντο → μαύρα γράμματα */
.metric-box {
    flex: 1;
    min-width: 130px;
    background: #EDEAE3;
    border-radius: 14px;
    padding: 1.2rem 1.2rem;
    text-align: center;
    color: #1A1A1A;
}

.metric-value {
    font-size: 1.8rem;
    font-weight: 600;
    color: #1A1A1A;
    line-height: 1.1;
}

.metric-label {
    font-size: 0.75rem;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-top: 0.3rem;
    font-weight: 500;
}

.metric-icon {
    font-size: 1.3rem;
    margin-bottom: 0.3rem;
}

/* Labels ενότητας — σκούρο χρώμα για ευαναγνωσία */
.section-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #555;
    margin-bottom: 0.5rem;
    font-weight: 600;
}

.soft-divider {
    border: none;
    border-top: 1px solid #D8D5CF;
    margin: 1.5rem 0;
}

/* Sidebar — λευκό φόντο, μαύρα γράμματα */
section[data-testid="stSidebar"] {
    background: #fff;
    border-right: 1px solid #E8E5DF;
    color: #1A1A1A;
}

section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div {
    color: #1A1A1A !important;
}

/* Κουμπί — σκούρο φόντο, ασπρα γράμματα */
div.stButton > button {
    background: #1A1A1A;
    color: #ffffff !important;
    border: none;
    border-radius: 12px;
    padding: 0.75rem 2.5rem;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: 0.3px;
    cursor: pointer;
    transition: background 0.2s;
    width: 100%;
    margin-top: 0.5rem;
}

div.stButton > button:hover {
    background: #333;
    color: #ffffff !important;
}

/* Input fields — λευκό φόντο, μαύρο κείμενο */
div[data-testid="stTextInput"] input {
    border-radius: 10px;
    border: 1px solid #C8C5BF;
    background: #fff;
    color: #1A1A1A !important;
    font-family: 'DM Sans', sans-serif;
    padding: 0.6rem 1rem;
    font-size: 0.95rem;
}

div[data-testid="stTextInput"] label {
    color: #1A1A1A !important;
    font-weight: 500;
}

/* Expander κείμενο */
details summary p, details summary span {
    color: #1A1A1A !important;
    font-weight: 500;
}

.error-msg {
    background: #FFF0F0;
    border-left: 3px solid #CC3333;
    border-radius: 8px;
    padding: 0.8rem 1.2rem;
    font-size: 0.88rem;
    color: #990000;
    font-weight: 500;
}

/* Ενδιάμεσες στάσεις tags — ανοιχτό φόντο, σκούρο κείμενο */
.stop-tag {
    display: inline-block;
    background: #E8E5DF;
    border-radius: 6px;
    padding: 0.15rem 0.6rem;
    font-size: 0.78rem;
    color: #333;
    font-weight: 500;
    margin-bottom: 0.3rem;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# ΒΟΗΘΗΤΙΚΕΣ ΣΥΝΑΡΤΗΣΕΙΣ
# ─────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def geocode(place: str):
    """Μετατρέπει τοποθεσία (string) σε συντεταγμένες (lat, lon) μέσω Nominatim."""
    try:
        params = {"q": place, "format": "json", "limit": 1}
        headers = {"User-Agent": "RoadTripPlannerGR/1.0"}
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=8)
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


@st.cache_data(show_spinner=False)
def get_route(coords: tuple):
    """
    Παίρνει διαδρομή από OSRM.
    coords: tuple of (lat, lon) tuples
    Επιστρέφει dict με distance_km, duration_min, geometry.
    """
    try:
        waypoints = ";".join(f"{lon},{lat}" for lat, lon in coords)
        url = f"{OSRM_BASE}/{waypoints}"
        params = {"overview": "full", "geometries": "geojson"}
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        if data.get("code") != "Ok":
            return None

        route = data["routes"][0]
        return {
            "distance_km": route["distance"] / 1000,
            "duration_min": route["duration"] / 60,
            "geometry": route["geometry"]["coordinates"],
        }
    except Exception:
        return None


def format_duration(minutes: float) -> str:
    """Μορφοποιεί λεπτά σε αναγνώσιμο format."""
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0:
        return f"{h}ω {m}λ"
    return f"{m} λεπτά"


def build_map(coords: list, geometry: list, labels: list) -> folium.Map:
    """Δημιουργεί Folium χάρτη με τη διαδρομή και markers."""
    avg_lat = sum(c[0] for c in coords) / len(coords)
    avg_lon = sum(c[1] for c in coords) / len(coords)

    m = folium.Map(
        location=[avg_lat, avg_lon],
        zoom_start=7,
        tiles="CartoDB Positron",
        prefer_canvas=True,
    )

    route_latlons = [[lat, lon] for lon, lat in geometry]
    folium.PolyLine(route_latlons, color="#1A1A1A", weight=3.5, opacity=0.85).add_to(m)

    colors = ["green"] + ["orange"] * (len(coords) - 2) + ["red"]
    for i, (coord, label) in enumerate(zip(coords, labels)):
        folium.Marker(
            location=[coord[0], coord[1]],
            popup=folium.Popup(label, max_width=200),
            tooltip=label,
            icon=folium.Icon(color=colors[i], icon="circle", prefix="fa"),
        ).add_to(m)

    return m


# ─────────────────────────────────────────────
# SIDEBAR — Παράμετροι Οχήματος & Παρέας
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🚗 Παράμετροι Οχήματος")
    st.markdown("<hr style='border-top:1px solid #E8E5DF;margin:0.5rem 0 1.2rem'>", unsafe_allow_html=True)

    fuel_type = st.selectbox(
        "Τύπος Καυσίμου",
        options=list(FUEL_PRICES.keys()),
        index=0,
    )

    consumption = st.slider(
        "Κατανάλωση (λίτρα / 100 χλμ.)",
        min_value=4.0,
        max_value=20.0,
        value=7.5,
        step=0.5,
        format="%.1f L",
    )

    include_tolls = st.checkbox("Συμπερίληψη εκτίμησης διοδίων", value=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 👥 Διαχωρισμός Κόστους")
    st.markdown("<hr style='border-top:1px solid #E8E5DF;margin:0.5rem 0 1.2rem'>", unsafe_allow_html=True)

    split_cost = st.checkbox("Χώρισε το κόστος με παρέα", value=False)

    num_people = 1
    if split_cost:
        num_people = st.number_input(
            "Αριθμός ατόμων",
            min_value=2,
            max_value=20,
            value=4,
            step=1,
            help="Το συνολικό κόστος θα διαιρεθεί ισόποσα.",
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:#F7F5F0;border-radius:10px;padding:0.9rem 1rem;font-size:0.82rem;color:#888'>"
        f"<b>Τιμή καυσίμου:</b> {FUEL_PRICES[fuel_type]:.2f} €/λίτρο<br>"
        f"<span style='font-size:0.75rem'>Μέσος όρος Ελλάδας, Μάρτιος 2026</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
# ΚΥΡΙΟ ΠΕΡΙΕΧΟΜΕΝΟ
# ─────────────────────────────────────────────
st.markdown("# Road Trip Planner")
st.markdown('<p class="subtitle">Σχεδίασε το ταξίδι σου — απλά, έξυπνα, με κάθε λεπτομέρεια.</p>', unsafe_allow_html=True)
st.markdown("<hr class='soft-divider'>", unsafe_allow_html=True)

# ── Αφετηρία & Προορισμός ──
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown('<p class="section-label">Αφετηρία</p>', unsafe_allow_html=True)
    origin = st.text_input(
        "origin",
        placeholder="π.χ. Αθήνα, Ελλάδα",
        label_visibility="collapsed",
    )

with col2:
    st.markdown('<p class="section-label">Τελικός Προορισμός</p>', unsafe_allow_html=True)
    destination = st.text_input(
        "destination",
        placeholder="π.χ. Θεσσαλονίκη, Ελλάδα",
        label_visibility="collapsed",
    )

# ── Ενδιάμεσες Στάσεις — Δυναμικές, χωρίς όριο ──
st.markdown("<br>", unsafe_allow_html=True)

# Αρχικοποίηση session state για τον αριθμό στάσεων
if "num_stops" not in st.session_state:
    st.session_state.num_stops = 0

with st.expander("➕  Ενδιάμεσες στάσεις (προαιρετικό)"):

    col_add, col_remove, _ = st.columns([1.2, 1.4, 4])
    with col_add:
        if st.button("＋ Προσθήκη"):
            st.session_state.num_stops += 1
    with col_remove:
        if st.button("－ Αφαίρεση") and st.session_state.num_stops > 0:
            st.session_state.num_stops -= 1

    # Δυναμικά input fields για κάθε στάση
    stops = []
    for i in range(st.session_state.num_stops):
        val = st.text_input(
            f"Στάση {i + 1}",
            placeholder=f"π.χ. πόλη ή χωριό, Ελλάδα",
            key=f"stop_{i}",
        )
        stops.append(val)

    if st.session_state.num_stops == 0:
        st.markdown(
            "<div style='color:#ccc;font-size:0.85rem;padding:0.5rem 0;'>"
            "Πάτα «＋ Προσθήκη» για να προσθέσεις ενδιάμεσα σημεία — όσα θέλεις!"
            "</div>",
            unsafe_allow_html=True,
        )

# ── Κουμπί Υπολογισμού ──
st.markdown("<br>", unsafe_allow_html=True)
calculate = st.button("🗺️  Υπολογισμός Ταξιδιού")

# ─────────────────────────────────────────────
# ΛΟΓΙΚΗ ΥΠΟΛΟΓΙΣΜΟΥ
# ─────────────────────────────────────────────
if calculate:

    # Συλλογή σημείων: αφετηρία + ενδιάμεσες + προορισμός
    raw_points = [origin.strip()] + [s.strip() for s in stops] + [destination.strip()]
    waypoints_labels = [p for p in raw_points if p]

    if len(waypoints_labels) < 2:
        st.markdown(
            '<div class="error-msg">⚠️ Παρακαλώ συμπλήρωσε τουλάχιστον <b>Αφετηρία</b> και <b>Τελικό Προορισμό</b>.</div>',
            unsafe_allow_html=True,
        )
    else:
        with st.spinner("Αναζήτηση τοποθεσιών και υπολογισμός διαδρομής…"):

            coords = []
            failed = []
            for label in waypoints_labels:
                result = geocode(label)
                if result:
                    coords.append(result)
                else:
                    failed.append(label)

            if failed:
                st.markdown(
                    f'<div class="error-msg">⚠️ Δεν βρέθηκαν: <b>{", ".join(failed)}</b>. '
                    f"Δοκίμασε πιο αναλυτικά (π.χ. «Λαμία, Ελλάδα»).</div>",
                    unsafe_allow_html=True,
                )
            elif len(coords) < 2:
                st.markdown('<div class="error-msg">⚠️ Δεν ήταν δυνατός ο εντοπισμός των τοποθεσιών.</div>', unsafe_allow_html=True)
            else:
                route_data = get_route(tuple(coords))

                if not route_data:
                    st.markdown(
                        '<div class="error-msg">⚠️ Αποτυχία σύνδεσης με το routing API. Έλεγξε τη σύνδεσή σου και δοκίμασε ξανά.</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    distance_km = route_data["distance_km"]
                    duration_min = route_data["duration_min"]

                    # Υπολογισμός καυσίμων
                    fuel_needed = (distance_km / 100) * consumption
                    fuel_cost = fuel_needed * FUEL_PRICES[fuel_type]

                    # Εκτίμηση διοδίων — βάσει πραγματικών τιμών 2026
                    toll_cost = estimate_tolls(distance_km, waypoints_labels) if include_tolls else 0

                    total_cost = fuel_cost + toll_cost

                    # Κόστος ανά άτομο (αν ενεργοποιηθεί)
                    cost_per_person = total_cost / num_people if split_cost else None

                    # ── ΚΑΡΤΑ ΑΠΟΤΕΛΕΣΜΑΤΩΝ ──
                    stops_html = ""
                    if len(waypoints_labels) > 2:
                        stops_html = "".join(
                            f'<span class="stop-tag">⬤ {s}</span> '
                            for s in waypoints_labels[1:-1]
                        )

                    toll_box_html = ""
                    if include_tolls:
                        toll_box_html = (
                            f'<div class="metric-box">'
                            f'<div class="metric-icon">🛣️</div>'
                            f'<div class="metric-value">{toll_cost:.1f}€</div>'
                            f'<div class="metric-label">Εκτίμηση Διοδίων</div>'
                            f'</div>'
                        )

                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown(
                        f"""
                        <div class="result-card">
                            <div style="font-family:'Playfair Display',serif;font-size:1.25rem;font-weight:600;margin-bottom:0.3rem;">
                                📍 {waypoints_labels[0]} → {waypoints_labels[-1]}
                            </div>
                            <div style="margin-bottom:0.5rem;">{stops_html}</div>
                            <div class="metric-row">
                                <div class="metric-box">
                                    <div class="metric-icon">📏</div>
                                    <div class="metric-value">{distance_km:,.0f}</div>
                                    <div class="metric-label">Χιλιόμετρα</div>
                                </div>
                                <div class="metric-box">
                                    <div class="metric-icon">⏱️</div>
                                    <div class="metric-value">{format_duration(duration_min)}</div>
                                    <div class="metric-label">Χρόνος Ταξιδιού</div>
                                </div>
                                <div class="metric-box">
                                    <div class="metric-icon">⛽</div>
                                    <div class="metric-value">{fuel_cost:.1f}€</div>
                                    <div class="metric-label">Κόστος Καυσίμων</div>
                                </div>
                                {toll_box_html}
                                <div class="metric-box" style="background:#1A1A1A;color:#fff;">
                                    <div class="metric-icon">💰</div>
                                    <div class="metric-value" style="color:#fff;">{total_cost:.1f}€</div>
                                    <div class="metric-label" style="color:#aaa;">Συνολικό Κόστος</div>
                                </div>
                            </div>
                            <hr class="soft-divider" style="margin-top:1.5rem">
                            <div style="font-size:0.78rem;color:#bbb;">
                                🔢 Κατανάλωση: {consumption} L/100χλμ &nbsp;·&nbsp;
                                Καύσιμο: {fuel_type} @ {FUEL_PRICES[fuel_type]:.2f}€/L &nbsp;·&nbsp;
                                Ποσότητα: {fuel_needed:.1f} L
                                {'&nbsp;·&nbsp; Διόδια: εκτίμηση βάσει τιμών 2026' if include_tolls else ''}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # ── ΚΑΡΤΑ ΔΙΑΧΩΡΙΣΜΟΥ ΚΟΣΤΟΥΣ ──
                    if split_cost and cost_per_person is not None:
                        # Boxes για κάθε άτομο (μέχρι 8 για να μην γεμίσει η οθόνη)
                        display_count = min(int(num_people), 8)
                        people_boxes = "".join(
                            f'<div style="background:#F7F5F0;border-radius:10px;padding:0.8rem 1rem;text-align:center;min-width:80px;">'
                            f'<div style="font-size:0.7rem;color:#bbb;margin-bottom:0.2rem;">Άτομο {j+1}</div>'
                            f'<div style="font-size:1.5rem;font-weight:600;color:#1A1A1A;">{cost_per_person:.2f}€</div>'
                            f'</div>'
                            for j in range(display_count)
                        )
                        extra_note = (
                            f"<div style='font-size:0.8rem;color:#bbb;margin-top:0.5rem;'>+ {int(num_people) - display_count} ακόμα άτομα × {cost_per_person:.2f}€</div>"
                            if int(num_people) > display_count else ""
                        )

                        st.markdown(
                            f"""
                            <div class="split-card">
                                <div style="font-family:'Playfair Display',serif;font-size:1.1rem;font-weight:600;margin-bottom:0.4rem;">
                                    👥 Διαχωρισμός για {int(num_people)} άτομα
                                </div>
                                <div style="font-size:0.83rem;color:#aaa;margin-bottom:1.2rem;">
                                    {total_cost:.2f}€ συνολικό κόστος ÷ {int(num_people)} άτομα
                                </div>
                                <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.2rem;">
                                    <div style="background:#1A1A1A;color:#fff;border-radius:14px;padding:1.2rem 2rem;text-align:center;">
                                        <div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;color:#aaa;margin-bottom:0.3rem;">Ο καθένας πληρώνει</div>
                                        <div style="font-size:2.6rem;font-weight:700;line-height:1;">{cost_per_person:.2f}€</div>
                                    </div>
                                </div>
                                <div style="display:flex;gap:0.6rem;flex-wrap:wrap;">
                                    {people_boxes}
                                </div>
                                {extra_note}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    # ── ΧΑΡΤΗΣ ──
                    st.markdown('<p class="section-label" style="margin-top:1.5rem">Χάρτης Διαδρομής</p>', unsafe_allow_html=True)
                    route_map = build_map(coords, route_data["geometry"], waypoints_labels)
                    st_folium(route_map, width="100%", height=460, returned_objects=[])

                    st.markdown(
                        "<div style='font-size:0.75rem;color:#ccc;margin-top:0.5rem;text-align:center'>"
                        "Δεδομένα χαρτών: © OpenStreetMap contributors | Δρομολόγηση: OSRM"
                        "</div>",
                        unsafe_allow_html=True,
                    )

# ── Footer ──
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:center;font-size:0.75rem;color:#ccc;'>"
    "Road Trip Planner · Φτιαγμένο με ❤️ · Δεδομένα από OpenStreetMap"
    "</div>",
    unsafe_allow_html=True,
)