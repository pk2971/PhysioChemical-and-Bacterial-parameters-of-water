import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import unicodedata

st.set_page_config(
    page_title="Tirupati Water Quality Dashboard",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background: #f0f4f8; }
  [data-testid="stHeader"] { background: transparent; }
  .main-title {
    font-size: 2rem; font-weight: 700; color: #1a3a5c;
    border-bottom: 3px solid #2196F3; padding-bottom: 8px; margin-bottom: 4px;
  }
  .subtitle { color: #546e7a; font-size: 0.95rem; margin-bottom: 20px; }
  .metric-card {
    background: white; border-radius: 12px; padding: 16px 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;
  }
  .metric-value { font-size: 2rem; font-weight: 700; }
  .metric-label { font-size: 0.8rem; color: #78909c; text-transform: uppercase; letter-spacing: 0.5px; }
  .section-header {
    font-size: 1.1rem; font-weight: 600; color: #1a3a5c;
    margin: 16px 0 10px 0; border-left: 4px solid #2196F3; padding-left: 10px;
  }
  .loc-detail-box {
    background: white; border-radius: 12px; padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 12px;
  }
  .pass-badge  { background:#e8f5e9; color:#2e7d32; border-radius:6px; padding:2px 8px; font-size:0.78rem; font-weight:600; }
  .fail-badge  { background:#ffebee; color:#c62828; border-radius:6px; padding:2px 8px; font-size:0.78rem; font-weight:600; }
  .warn-badge  { background:#fff8e1; color:#e65100; border-radius:6px; padding:2px 8px; font-size:0.78rem; font-weight:600; }
  .na-badge    { background:#eceff1; color:#546e7a; border-radius:6px; padding:2px 8px; font-size:0.78rem; font-weight:600; }
  div[data-testid="stTabs"] button { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_excel("dashboard/data.xlsx", sheet_name="water quality")

    # Source category
    def categorise(s):
        s = str(s).lower()
        if "ground" in s: return "Groundwater"
        if "bottled" in s: return "Bottled RO"
        if "domestic" in s: return "Domestic RO"
        if "commercial" in s: return "Commercial RO"
        if "dam" in s or "tuda" in s: return "Surface / Municipal"
        if "fall" in s: return "Natural Water Body"
        return "Other"

    df["Source Category"] = df["Type of water source with code"].apply(categorise)

    # Parse DMS coordinates
    def parse_dms(geo):
        if not isinstance(geo, str): return None, None
        geo = unicodedata.normalize("NFKD", geo)
        for ch in ["\u0361","\u0300","\u0301","\u030e","\u031d"]: geo = geo.replace(ch,"")
        nm = re.search(r"N\s*[-–]?\s*(\d+)[^\d]+([\d]+)[^\d]+([\d.,]+)", geo)
        em = re.search(r"E\s*[-–]?\s*(\d+)[^\d]+([\d]+)[^\d]+([\d.,]+)", geo)
        if nm and em:
            try:
                lat = float(nm.group(1)) + float(nm.group(2))/60 + float(nm.group(3).replace(",","."))/3600
                lon = float(em.group(1)) + float(em.group(2))/60 + float(em.group(3).replace(",","."))/3600
                # sanity check – Tirupati is ~13-14°N, 79°E
                if 12 < lat < 15 and 78 < lon < 81:
                    return round(lat,6), round(lon,6)
            except: pass
        return None, None

    df[["lat","lon"]] = df["Geographical location"].apply(lambda g: pd.Series(parse_dms(g)))

    # Bacterial load – coerce to numeric
    def clean_bact(v):
        try: return float(v)
        except:
            s = str(v).lower()
            if "too many" in s or "tntc" in s: return 10000
            if "not det" in s or "nd" in s or v in [0,"0"]: return 0
            return np.nan
    df["Bacterial_num"] = df["Baterial load -Total viable count (CFU/100 ml)"].apply(clean_bact)

    # E.coli normalise
    df["Ecoli_pos"] = df["E.coli"].str.lower().str.strip() == "positive"

    return df

# ── BIS limits ────────────────────────────────────────────────────────────────
ACCEPTABLE = {
    "pH": (6.5, 8.5), "Alkalinity": (None, 200), "TDS": (None, 500),
    "Hardness": (None, 200), "CalciumCa": (None, 75), "Magnesium Mg": (None, 30),
    "Fluoride F": (None, 1.0), "Aluminium Al": (None, 0.03), "Chromium Cr": (None, 0.05),
    "Manganese Mn": (None, 0.1), "Nickel  Ni": (None, 0.02), "Copper Cu": (None, 0.05),
    "Arsenic As": (None, 0.01), "Selenium Se": (None, 0.01), "Molybden Mo": (None, 0.07),
    "Silver  Ag": (None, 0.1), "Cadmium Cd": (None, 0.003), "Barium Ba": (None, 0.7),
    "Mercury Hg": (None, 0.001), "Lead Pb": (None, 0.01), "Uranium U": (None, 0.03),
}
PERMISSIBLE = {
    "Alkalinity": 600, "TDS": 2000, "Hardness": 600, "CalciumCa": 200,
    "Magnesium Mg": 100, "Fluoride F": 1.5, "Aluminium Al": 0.2,
    "Manganese Mn": 0.3, "Copper Cu": 1.5, "Arsenic As": 0.05,
    "Cadmium Cd": None, "Barium Ba": None,
}
PARAM_UNITS = {
    "pH":"","Alkalinity":"mg/L","TDS":"mg/L","Hardness":"mg/L",
    "Electrical conductivity":"µS/cm","Resistance":"Ω",
    "CalciumCa":"mg/L","Magnesium Mg":"mg/L","Fluoride F":"mg/L",
    "Aluminium Al":"mg/L","Chromium Cr":"mg/L","Manganese Mn":"mg/L",
    "Nickel  Ni":"mg/L","Copper Cu":"mg/L","Arsenic As":"mg/L",
    "Selenium Se":"mg/L","Molybden Mo":"mg/L","Silver  Ag":"mg/L",
    "Cadmium Cd":"mg/L","Barium Ba":"mg/L","Mercury Hg":"mg/L",
    "Lead Pb":"mg/L","Uranium U":"mg/L",
    "Bacterial_num":"CFU/100ml",
}
NUMERIC_PARAMS = list(ACCEPTABLE.keys())
ALL_NUMERIC = NUMERIC_PARAMS + ["Electrical conductivity","Resistance","Bacterial_num"]

METAL_PARAMS = ["Aluminium Al","Chromium Cr","Manganese Mn","Nickel  Ni","Copper Cu",
                "Arsenic As","Selenium Se","Molybden Mo","Silver  Ag","Cadmium Cd",
                "Barium Ba","Mercury Hg","Lead Pb","Uranium U"]

CAT_SOURCE_COLORS = {
    "Groundwater":"#1565C0","Domestic RO":"#2E7D32","Commercial RO":"#6A1B9A",
    "Bottled RO":"#E65100","Surface / Municipal":"#00838F","Natural Water Body":"#558B2F","Other":"#78909C"
}

def compliance_status(row):
    fails, warns = 0, 0
    for param, (lo, hi) in ACCEPTABLE.items():
        v = row.get(param)
        if pd.isna(v): continue
        if lo and v < lo: fails += 1
        elif hi and v > hi:
            perm = PERMISSIBLE.get(param)
            if perm and v <= perm: warns += 1
            else: fails += 1
    if row.get("Ecoli_pos"): fails += 1
    bact = row.get("Bacterial_num", 0)
    if pd.notna(bact) and bact > 0: fails += 1
    return fails, warns

@st.cache_data
def compute_wqi(df):
    weights = {
        "pH":0.122,"TDS":0.122,"Hardness":0.08,"Alkalinity":0.05,"CalciumCa":0.05,
        "Magnesium Mg":0.05,"Fluoride F":0.08,"Arsenic As":0.12,"Lead Pb":0.1,
        "Mercury Hg":0.1,"Cadmium Cd":0.08,"Bacterial_num":0.15,
    }
    ideal = {"pH":7.0,"TDS":0,"Hardness":0,"Alkalinity":0,"CalciumCa":0,
             "Magnesium Mg":0,"Fluoride F":0,"Arsenic As":0,"Lead Pb":0,
             "Mercury Hg":0,"Cadmium Cd":0,"Bacterial_num":0}
    standards = {"pH":8.5,"TDS":500,"Hardness":200,"Alkalinity":200,"CalciumCa":75,
                 "Magnesium Mg":30,"Fluoride F":1.0,"Arsenic As":0.01,"Lead Pb":0.01,
                 "Mercury Hg":0.001,"Cadmium Cd":0.003,"Bacterial_num":0}
    wqi = []
    for _, row in df.iterrows():
        score = 0
        for p, w in weights.items():
            v = row.get(p, np.nan)
            if pd.isna(v): v = 0
            s = standards[p]
            i = ideal[p]
            if s == i: continue
            qi = abs(v - i) / abs(s - i) * 100
            score += w * qi
        wqi.append(min(score, 300))
    return wqi

def wqi_label(s):
    if s < 25: return "Excellent", "#1B5E20"
    if s < 50: return "Good",      "#388E3C"
    if s < 75: return "Poor",      "#F57F17"
    if s < 100:return "Very Poor", "#E65100"
    return "Unsuitable", "#B71C1C"

# ── Load ──────────────────────────────────────────────────────────────────────
df = load_data()
df["WQI"] = compute_wqi(df)
df["WQI_label"] = df["WQI"].apply(lambda s: wqi_label(s)[0])
df["WQI_color"] = df["WQI"].apply(lambda s: wqi_label(s)[1])
df[["Fails","Warns"]] = df.apply(lambda r: pd.Series(compliance_status(r)), axis=1)

# Map valid coords
df_map = df[df["lat"].notna() & df["lon"].notna()].copy()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">💧 Tirupati Water Quality Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Physicochemical & Bacterial Analysis · BIS Standards Compliance</div>', unsafe_allow_html=True)

# ── KPI row ───────────────────────────────────────────────────────────────────
total = len(df)
ecoli_pos = df["Ecoli_pos"].sum()
fail_any = (df["Fails"] > 0).sum()
avg_wqi = df["WQI"].mean()

c1,c2,c3,c4,c5 = st.columns(5)
with c1:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#1565C0">{total}</div><div class="metric-label">Locations Sampled</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#2E7D32">{len(df_map)}</div><div class="metric-label">Mapped Locations</div></div>', unsafe_allow_html=True)
with c3:
    wc, col = wqi_label(avg_wqi)
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:{col}">{avg_wqi:.0f}</div><div class="metric-label">Avg WQI Score</div></div>', unsafe_allow_html=True)
with c4:
    pct = fail_any/total*100
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#E65100">{fail_any} <span style="font-size:1rem">({pct:.0f}%)</span></div><div class="metric-label">Locations Exceeding Limits</div></div>', unsafe_allow_html=True)
with c5:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#B71C1C">{ecoli_pos}</div><div class="metric-label">E. coli Positive</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗺️ Map", "📍 Location Detail", "🔬 Parameter Explorer",
    "📊 Overview", "🔗 Correlations"
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 – MAP
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    col_ctrl, col_map = st.columns([1, 3])

    with col_ctrl:
        st.markdown('<div class="section-header">Map Controls</div>', unsafe_allow_html=True)
        colour_by = st.selectbox("Colour markers by",
            ["WQI Score","Source Category","E.coli Status","TDS","pH","Hardness","Fluoride F","Arsenic As","Lead Pb"],
            key="map_colour")
        show_ecoli = st.checkbox("Highlight E.coli positive", value=True)

        st.markdown('<div class="section-header">Legend</div>', unsafe_allow_html=True)
        if colour_by == "WQI Score":
            for lbl, col in [("Excellent (<25)","#1B5E20"),("Good (25-50)","#388E3C"),
                              ("Poor (50-75)","#F57F17"),("Very Poor (75-100)","#E65100"),
                              ("Unsuitable (>100)","#B71C1C")]:
                st.markdown(f'<span style="color:{col}">⬤</span> {lbl}', unsafe_allow_html=True)
        elif colour_by == "Source Category":
            for cat, col in CAT_SOURCE_COLORS.items():
                if cat in df["Source Category"].values:
                    st.markdown(f'<span style="color:{col}">⬤</span> {cat}', unsafe_allow_html=True)
        else:
            st.markdown("🔵 Low &nbsp;&nbsp; 🟡 Mid &nbsp;&nbsp; 🔴 High", unsafe_allow_html=True)

        st.markdown('<div class="section-header">Click a marker</div>', unsafe_allow_html=True)
        st.info("Click any map marker, then go to the **Location Detail** tab to see the full analysis.")

    with col_map:
        m = folium.Map(location=[13.62, 79.42], zoom_start=12,
                       tiles="CartoDB positron")

        # Compute marker colors
        if colour_by == "WQI Score":
            df_map["_mc"] = df_map["WQI"].apply(lambda s: wqi_label(s)[1])
        elif colour_by == "Source Category":
            df_map["_mc"] = df_map["Source Category"].map(CAT_SOURCE_COLORS).fillna("#78909C")
        elif colour_by == "E.coli Status":
            df_map["_mc"] = df_map["Ecoli_pos"].map({True:"#B71C1C", False:"#1B5E20"})
        else:
            param = colour_by
            mn, mx = df_map[param].min(), df_map[param].max()
            def pcolor(v):
                if pd.isna(v) or mx == mn: return "#78909C"
                r = (v - mn) / (mx - mn)
                if r < 0.5:
                    g = int(255 * (1 - 2*r) * 0.8 + 50)
                    return f"#1565{g:02X}"
                else:
                    r2 = (r - 0.5) * 2
                    red = int(180 + 75*r2)
                    return f"#{red:02X}2020"
            df_map["_mc"] = df_map[param].apply(pcolor)

        for _, row in df_map.iterrows():
            wlbl, _ = wqi_label(row["WQI"])
            bact_val = row["Bacterial_num"]
            bact_str = "Too many to count" if bact_val >= 10000 else f"{int(bact_val) if not pd.isna(bact_val) else 'N/A'} CFU/100ml"
            ecoli_str = "🔴 Positive" if row["Ecoli_pos"] else "🟢 Negative"

            popup_html = f"""
            <div style='font-family:sans-serif;min-width:200px'>
              <b style='font-size:13px;color:#1a3a5c'>{row['Location in Tirupati']}</b><br>
              <span style='color:#546e7a;font-size:11px'>{row['Type of water source with code']}</span><hr style='margin:6px 0'>
              <b>WQI:</b> {row['WQI']:.1f} ({wlbl})<br>
              <b>TDS:</b> {row['TDS']} mg/L &nbsp; <b>pH:</b> {row['pH']}<br>
              <b>Hardness:</b> {row['Hardness']} mg/L<br>
              <b>E.coli:</b> {ecoli_str}<br>
              <b>Bacterial load:</b> {bact_str}<br>
              <b>Violations:</b> {row['Fails']} param(s)
            </div>"""

            color = row["_mc"]
            border = "#FF1744" if (show_ecoli and row["Ecoli_pos"]) else color

            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=9, color=border, weight=3,
                fill=True, fill_color=color, fill_opacity=0.85,
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=row["Location in Tirupati"]
            ).add_to(m)

        map_data = st_folium(m, width=None, height=520, use_container_width=True, key="main_map")

        # Save clicked location
        if map_data and map_data.get("last_object_clicked_tooltip"):
            st.session_state["selected_location"] = map_data["last_object_clicked_tooltip"]

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 – LOCATION DETAIL
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    loc_names = df["Location in Tirupati"].tolist()
    default_idx = 0
    if "selected_location" in st.session_state:
        try:
            default_idx = loc_names.index(st.session_state["selected_location"])
        except: pass

    sel_loc = st.selectbox("Select a location", loc_names, index=default_idx, key="detail_loc")
    row = df[df["Location in Tirupati"] == sel_loc].iloc[0]
    wlbl, wcol = wqi_label(row["WQI"])

    # Header cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:{wcol}">{row["WQI"]:.0f}</div><div class="metric-label">WQI Score · {wlbl}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#1a3a5c">{row["Source Category"]}</div><div class="metric-label">Water Source</div></div>', unsafe_allow_html=True)
    with c3:
        fc = "#B71C1C" if row["Fails"] > 0 else "#1B5E20"
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:{fc}">{row["Fails"]}</div><div class="metric-label">Parameters Exceeding Limits</div></div>', unsafe_allow_html=True)
    with c4:
        ec = "#B71C1C" if row["Ecoli_pos"] else "#1B5E20"
        ecstr = "Positive ⚠️" if row["Ecoli_pos"] else "Negative ✓"
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:{ec};font-size:1.4rem">{ecstr}</div><div class="metric-label">E. coli</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        st.markdown('<div class="section-header">Parameter Compliance Table</div>', unsafe_allow_html=True)

        table_rows = []
        for param, (lo, hi) in ACCEPTABLE.items():
            v = row.get(param)
            unit = PARAM_UNITS.get(param, "")
            if pd.isna(v):
                badge = '<span class="na-badge">N/A</span>'
                status = "N/A"
            else:
                acc_limit = hi if hi else f"{lo}–"
                perm = PERMISSIBLE.get(param)
                if lo and v < lo:
                    badge = '<span class="fail-badge">FAIL</span>'
                    status = "Below minimum"
                elif hi and v > hi:
                    if perm and v <= perm:
                        badge = '<span class="warn-badge">WARN</span>'
                        status = "Exceeds acceptable, within permissible"
                    else:
                        badge = '<span class="fail-badge">FAIL</span>'
                        status = "Exceeds permissible limit"
                else:
                    badge = '<span class="pass-badge">PASS</span>'
                    status = "Within acceptable limit"

            table_rows.append({
                "Parameter": param.strip(),
                "Value": f"{v:.4g} {unit}" if not pd.isna(v) else "N/A",
                "BIS Acceptable": f"≤{hi}" if hi and not lo else (f"{lo}–{hi}" if lo and hi else "—"),
                "Status": badge
            })

        # Bacterial
        bact = row["Bacterial_num"]
        if bact >= 10000:
            bact_str = "TNTC (>10000)"
            bbadge = '<span class="fail-badge">FAIL</span>'
        elif bact > 0:
            bact_str = f"{int(bact)} CFU/100ml"
            bbadge = '<span class="fail-badge">FAIL</span>'
        else:
            bact_str = "0 CFU/100ml"
            bbadge = '<span class="pass-badge">PASS</span>'
        table_rows.append({"Parameter":"Bacterial Load","Value":bact_str,"BIS Acceptable":"Not detectable","Status":bbadge})

        table_html = """<table style='width:100%;border-collapse:collapse;font-size:0.85rem'>
        <tr style='background:#e3f2fd;font-weight:600'>
          <td style='padding:6px 8px'>Parameter</td>
          <td style='padding:6px 8px'>Value</td>
          <td style='padding:6px 8px'>BIS Limit</td>
          <td style='padding:6px 8px'>Status</td>
        </tr>"""
        for i, tr in enumerate(table_rows):
            bg = "#fafafa" if i%2==0 else "white"
            table_html += f"<tr style='background:{bg}'><td style='padding:5px 8px'>{tr['Parameter']}</td><td style='padding:5px 8px'>{tr['Value']}</td><td style='padding:5px 8px'>{tr['BIS Acceptable']}</td><td style='padding:5px 8px'>{tr['Status']}</td></tr>"
        table_html += "</table>"
        st.markdown(table_html, unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="section-header">Radar Chart – Key Parameters</div>', unsafe_allow_html=True)
        radar_params = ["pH","TDS","Hardness","Fluoride F","Arsenic As","Lead Pb","Manganese Mn","CalciumCa"]
        radar_labels, radar_vals, radar_limits = [], [], []
        for p in radar_params:
            hi = ACCEPTABLE[p][1]
            if hi and not pd.isna(row[p]):
                radar_labels.append(p.strip())
                radar_vals.append(min(row[p] / hi, 3.0))
                radar_limits.append(1.0)
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=radar_vals + [radar_vals[0]], theta=radar_labels + [radar_labels[0]],
            fill="toself", name="Sample", line_color="#1565C0", fillcolor="rgba(21,101,192,0.2)"
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=radar_limits + [radar_limits[0]], theta=radar_labels + [radar_labels[0]],
            fill="toself", name="BIS Limit", line_color="#E53935", line_dash="dot",
            fillcolor="rgba(229,57,53,0.05)"
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, max(max(radar_vals)*1.2, 1.5)])),
            showlegend=True, margin=dict(t=20,b=20,l=20,r=20), height=300,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        st.markdown('<div class="section-header">Heavy Metals Profile</div>', unsafe_allow_html=True)
        metal_vals = [row[m] for m in METAL_PARAMS if not pd.isna(row.get(m))]
        metal_names = [m.split()[0] for m in METAL_PARAMS if not pd.isna(row.get(m))]
        metal_limits = [ACCEPTABLE.get(m, (None,None))[1] for m in METAL_PARAMS if not pd.isna(row.get(m))]
        pct_limit = [v/l*100 if l and l>0 else 0 for v,l in zip(metal_vals, metal_limits)]
        bar_colors = ["#B71C1C" if p>100 else "#F57F17" if p>70 else "#1565C0" for p in pct_limit]
        fig_metals = go.Figure(go.Bar(
            x=metal_names, y=pct_limit, marker_color=bar_colors,
            text=[f"{p:.1f}%" for p in pct_limit], textposition="outside"
        ))
        fig_metals.add_hline(y=100, line_color="red", line_dash="dash", annotation_text="BIS Limit")
        fig_metals.update_layout(
            yaxis_title="% of BIS Limit", xaxis_title="",
            margin=dict(t=10,b=30,l=40,r=10), height=220,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_metals, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 – PARAMETER EXPLORER
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        sel_param = st.selectbox("Select parameter", ALL_NUMERIC, key="explorer_param")
    with ctrl2:
        source_filter = st.multiselect("Filter by source type",
            df["Source Category"].unique().tolist(),
            default=df["Source Category"].unique().tolist(), key="explorer_src")
    with ctrl3:
        chart_type = st.selectbox("Chart type", ["Box plot by source","Histogram","Scatter vs parameter"], key="chart_type")

    df_filt = df[df["Source Category"].isin(source_filter)].copy()

    limit_val = ACCEPTABLE.get(sel_param, (None,None))[1]

    if chart_type == "Box plot by source":
        fig = px.box(df_filt, x="Source Category", y=sel_param,
                     color="Source Category", color_discrete_map=CAT_SOURCE_COLORS,
                     points="all", hover_data=["Location in Tirupati"],
                     title=f"{sel_param} ({PARAM_UNITS.get(sel_param,'')}) by Source Type")
        if limit_val:
            fig.add_hline(y=limit_val, line_dash="dash", line_color="red",
                          annotation_text=f"BIS Acceptable: {limit_val}")
        fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "Histogram":
        fig = px.histogram(df_filt, x=sel_param, color="Source Category",
                           color_discrete_map=CAT_SOURCE_COLORS, nbins=20,
                           title=f"Distribution of {sel_param} ({PARAM_UNITS.get(sel_param,'')})")
        if limit_val:
            fig.add_vline(x=limit_val, line_dash="dash", line_color="red",
                          annotation_text=f"BIS: {limit_val}")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    else:
        sel_param2 = st.selectbox("Y-axis parameter", [p for p in ALL_NUMERIC if p != sel_param], key="scatter_y")
        fig = px.scatter(df_filt, x=sel_param, y=sel_param2,
                         color="Source Category", color_discrete_map=CAT_SOURCE_COLORS,
                         hover_data=["Location in Tirupati"],
                         title=f"{sel_param} vs {sel_param2}")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    # Stats table
    st.markdown('<div class="section-header">Summary Statistics</div>', unsafe_allow_html=True)
    stats = df_filt[sel_param].describe().round(4)
    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    for col, (lbl, key) in zip([sc1,sc2,sc3,sc4,sc5],
        [("Count","count"),("Mean","mean"),("Std Dev","std"),("Min","min"),("Max","max")]):
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#1a3a5c;font-size:1.5rem">{stats[key]:.3g}</div><div class="metric-label">{lbl}</div></div>', unsafe_allow_html=True)

    if limit_val:
        exc = (df_filt[sel_param] > limit_val).sum()
        st.markdown(f"<br>⚠️ **{exc} locations ({exc/len(df_filt)*100:.1f}%)** exceed the BIS acceptable limit of **{limit_val} {PARAM_UNITS.get(sel_param,'')}**", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 – OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="section-header">Exceedance Count per Parameter</div>', unsafe_allow_html=True)
        exc_counts = {}
        for param, (lo, hi) in ACCEPTABLE.items():
            if hi:
                exc_counts[param.strip()] = (df[param] > hi).sum()
        exc_df = pd.DataFrame({"Parameter": list(exc_counts.keys()), "Locations Exceeding BIS": list(exc_counts.values())})
        exc_df = exc_df[exc_df["Locations Exceeding BIS"] > 0].sort_values("Locations Exceeding BIS", ascending=True)
        fig_exc = px.bar(exc_df, x="Locations Exceeding BIS", y="Parameter", orientation="h",
                         color="Locations Exceeding BIS", color_continuous_scale=["#81D4FA","#E53935"],
                         title="")
        fig_exc.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                               coloraxis_showscale=False, margin=dict(t=10))
        st.plotly_chart(fig_exc, use_container_width=True)

    with col_b:
        st.markdown('<div class="section-header">WQI Distribution by Source Type</div>', unsafe_allow_html=True)
        fig_wqi = px.box(df, x="Source Category", y="WQI",
                         color="Source Category", color_discrete_map=CAT_SOURCE_COLORS,
                         points="all", hover_data=["Location in Tirupati"])
        fig_wqi.add_hline(y=50, line_dash="dash", line_color="orange", annotation_text="Good/Poor threshold")
        fig_wqi.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_wqi, use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        st.markdown('<div class="section-header">Source Type Distribution</div>', unsafe_allow_html=True)
        src_counts = df["Source Category"].value_counts().reset_index()
        src_counts.columns = ["Source","Count"]
        fig_pie = px.pie(src_counts, values="Count", names="Source",
                         color="Source", color_discrete_map=CAT_SOURCE_COLORS,
                         hole=0.4)
        fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_d:
        st.markdown('<div class="section-header">Compliance Heatmap (locations × parameters)</div>', unsafe_allow_html=True)
        heat_params = [p for p in ACCEPTABLE if ACCEPTABLE[p][1]]
        heat_df = df[["Location in Tirupati"] + heat_params].set_index("Location in Tirupati")
        norm_df = pd.DataFrame(index=heat_df.index)
        for p in heat_params:
            hi = ACCEPTABLE[p][1]
            norm_df[p.strip()] = (heat_df[p] / hi).clip(0, 3)
        fig_heat = px.imshow(norm_df.T, aspect="auto",
                             color_continuous_scale=["#E8F5E9","#FFF9C4","#FFCDD2","#B71C1C"],
                             zmin=0, zmax=2,
                             labels={"color":"Ratio to BIS limit"})
        fig_heat.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                                xaxis=dict(tickfont=dict(size=7)),
                                margin=dict(t=10))
        st.plotly_chart(fig_heat, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 – CORRELATIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<div class="section-header">Correlation Heatmap – All Numeric Parameters</div>', unsafe_allow_html=True)
    corr_params = [p for p in ALL_NUMERIC if p in df.columns]
    corr = df[corr_params].corr().round(2)
    fig_corr = px.imshow(corr, text_auto=".2f", aspect="auto",
                         color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
                         title="Pearson Correlation Matrix")
    fig_corr.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=600,
                            xaxis=dict(tickfont=dict(size=9)),
                            yaxis=dict(tickfont=dict(size=9)))
    st.plotly_chart(fig_corr, use_container_width=True)

    st.markdown('<div class="section-header">Top Correlations with WQI</div>', unsafe_allow_html=True)
    wqi_corr = df[corr_params + ["WQI"]].corr()["WQI"].drop("WQI").abs().sort_values(ascending=False)
    top_corr = wqi_corr.head(10).reset_index()
    top_corr.columns = ["Parameter", "|Correlation with WQI|"]
    fig_topcorr = px.bar(top_corr, x="|Correlation with WQI|", y="Parameter",
                         orientation="h", color="|Correlation with WQI|",
                         color_continuous_scale=["#90CAF9","#1565C0"])
    fig_topcorr.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                               coloraxis_showscale=False, margin=dict(t=10))
    st.plotly_chart(fig_topcorr, use_container_width=True)

# Footer
st.markdown("---")
st.markdown('<div style="text-align:center;color:#90a4ae;font-size:0.8rem">Data source: Physicochemical & Bacterial analysis of water sources, Tirupati · BIS IS 10500:2012 drinking water standards</div>', unsafe_allow_html=True)
