# app.py — ג'ירף – איכויות מזון (בחירת סניף למטה מחוץ לטופס + גלילה לפי סניף + הקלדה ידנית)
from __future__ import annotations
import os, json, sqlite3
from typing import List, Optional, Tuple, Dict, Any

import pandas as pd
import streamlit as st
import altair as alt

# ===== Google Sheets (אופציונלי) =====
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSHEETS_AVAILABLE = True
except Exception:
    GSHEETS_AVAILABLE = False

# =========================
# ------- SETTINGS --------
# =========================
st.set_page_config(page_title="ג'ירף – איכויות מזון", layout="wide")

BRANCHES: List[str] = ["חיפה", "ראשל״צ", "רמה״ח", "נס ציונה", "לנדמרק", "פתח תקווה", "הרצליה", "סביון"]

DISHES: List[str] = [
    "פאד תאי", "מלאזית", "פיליפינית", "אפגנית",
    "קארי דלעת", "סצ'ואן", "ביף רייס",
    "אורז מטוגן", "מאקי סלמון", "מאקי טונה",
    "ספייסי סלמון", "נודלס ילדים",
    "סלט תאילנדי", "סלט בריאות", "סלט דג לבן", "אגרול", "גיוזה", "וון",
]

CHEFS_BY_BRANCH: Dict[str, List[str]] = {
    "פתח תקווה": ["שן", "זאנג", "דאי", "לי", "ין", "יו"],
    "הרצליה": ["יון", "שיגווה", "באו באו", "האו", "טו", "זאנג", "טאנג", "צונג"],
    "נס ציונה": ["לי פנג", "זאנג", "צ'ו", "פנג"],
    "סביון": ["בין בין", "וואנג", "וו", "סונג", "ג'או"],
    "ראשל״צ": ["ג'או", "זאנג", "צ'ה", "ליו", "מא", "רן"],
    "חיפה": ["סונג", "לי", "ליו", "ג'או"],
    "רמה״ח": ["ין", "סי", "ליו", "הואן", "פרנק", "זאנג", "זאו לי"],
    "רמהח":  ["ין", "סי", "ליו", "הואן", "פרנק", "זאנג", "זאו לי"],  # אליאס
    # לנדמרק – מעודכן
    "לנדמרק": ["יו", "מא", "וואנג הואנבין", "וואנג ג'ינלאי", "ג'או", "אוליבר",
               "זאנג", "בי", "יאנג זימינג", "יאנג רונגשטן", "דונג", "וואנג פוקוואן"],
}

DB_PATH = "food_quality.db"
MIN_CHEF_WEEK_M = 2
MIN_DISH_WEEK_M = 2
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# =========================
# ---------- STYLE --------
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;700;900&display=swap');
:root{ --bg:#fff; --surface:#fff; --text:#000; --border:#e7ebf0; --green-50:#ecfdf5; --green-100:#d1fae5; --green-500:#10b981; }
html, body, .main, .block-container{direction:rtl; background:var(--bg);}
.main .block-container{font-family:"Rubik",-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
body{ border:4px solid #000; border-radius:16px; margin:10px; }
.header-min{ background:var(--green-50); border:1px solid var(--green-100); border-radius:18px; padding:18px; box-shadow:0 6px 22px rgba(0,0,0,.04); margin-bottom:14px; text-align:center;}
.header-min .title{font-size:26px; font-weight:900; margin:0 0 12px;}
.daily-pick-login{ background:#fff; border:2px solid var(--green-500); border-radius:0; padding:12px 16px; display:inline-block; width:min(720px,92vw); text-align:center;}
.daily-pick-login .ttl{font-weight:900; color:#065f46; margin:0 0 6px;}
.daily-pick-login .dish{font-weight:900; font-size:18px;}
.daily-pick-login .avg{color:var(--green-500); font-weight:800;}
.card{background:var(--surface); border:1px solid var(--border); border-radius:16px; padding:16px; box-shadow:0 4px 18px rgba(10,20,40,.04); margin-bottom:12px;}
.status-min{display:flex; align-items:center; gap:10px; justify-content:center; background:#fff; border:1px solid var(--border); border-radius:14px; padding:10px 12px; margin-bottom:12px;}
.chip{padding:4px 10px; border:1px solid var(--green-100); border-radius:999px; font-weight:800; font-size:12px; color:#065f46; background:var(--green-50)}
.stTextInput input, .stTextArea textarea{ background:#fff !important; color:var(--text) !important; border-radius:12px !important; border:1px solid var(--border) !important; padding:10px 12px !important;}
.stTextArea textarea{min-height:96px !important;}
.stSelectbox div[data-baseweb="select"]{background:#fff !important; color:var(--text) !important; border-radius:12px !important; border:1px solid var(--border) !important;}
.stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox [data-baseweb="select"]:focus-within{ outline:none !important; box-shadow:0 0 0 2px rgba(16,185,129,.25) !important; border-color:var(--green-500) !important;}
.stRadio [data-baseweb="radio"] svg{ color:#000 !important; fill:#000 !important; }
.stSelectbox {overflow:visible !important;}
div[data-baseweb="select"] + div[role="listbox"]{ bottom:auto !important; top: calc(100% + 8px) !important; max-height:50vh !important; }
table.small {width:100%; border-collapse:collapse;}
table.small thead tr{ background:var(--green-50); }
table.small th, table.small td {border-bottom:1px solid #f1f1f1; padding:8px; font-size:14px; text-align:center;}
table.small th {font-weight:900;}
.num-green{color:var(--green-500); font-weight:700;}
div[data-testid="stWidgetInstructions"]{display:none !important;}
</style>
""", unsafe_allow_html=True)

# =========================
# ------- DATABASE --------
# =========================
def conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)

SCHEMA = """
CREATE TABLE IF NOT EXISTS food_quality (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  branch TEXT NOT NULL,
  chef_name TEXT NOT NULL,
  dish_name TEXT NOT NULL,
  score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 10),
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  submitted_by TEXT
);
"""
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_food_branch_time ON food_quality(branch, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_food_chef_dish_time ON food_quality(chef_name, dish_name, created_at)",
]
def init_db():
    c = conn(); cur = c.cursor()
    cur.execute(SCHEMA)
    for q in INDEXES: cur.execute(q)
    c.commit(); c.close()
init_db()

# =========================
# -------- HELPERS --------
# =========================
@st.cache_data(ttl=15)
def load_df() -> pd.DataFrame:
    c = conn()
    df = pd.read_sql_query(
        "SELECT id, branch, chef_name, dish_name, score, notes, created_at FROM food_quality ORDER BY created_at DESC",
        c,
    )
    c.close()
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    return df

def _get_sheet_id() -> Optional[str]:
    sheet_id = st.secrets.get("GOOGLE_SHEET_ID") or os.getenv("GOOGLE_SHEET_ID")
    if sheet_id: return sheet_id
    sheet_url = st.secrets.get("GOOGLE_SHEET_URL") or os.getenv("GOOGLE_SHEET_URL")
    if sheet_url and "/spreadsheets/d/" in sheet_url:
        try: return sheet_url.split("/spreadsheets/d/")[1].split("/")[0]
        except Exception: return None
    return None

def _get_service_account_info() -> Optional[dict]:
    raw = (st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON")
           or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
           or st.secrets.get("google_service_account")
           or os.getenv("GOOGLE_SERVICE_ACCOUNT"))
    if not raw: return None
    if isinstance(raw, dict): return raw
    try: return json.loads(raw)
    except Exception: return None

def save_to_google_sheets(branch: str, chef: str, dish: str, score: int, notes: str, ts: str):
    if not GSHEETS_AVAILABLE: return
    sheet_id = _get_sheet_id()
    creds_info = _get_service_account_info()
    if not (sheet_id and creds_info): return
    credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    gc = gspread.authorize(credentials)
    gc.open_by_key(sheet_id).sheet1.append_row([ts, branch, chef, dish, score, notes or ""])

def insert_record(branch: str, chef: str, dish: str, score: int, notes: str = "", submitted_by: Optional[str] = None):
    ts = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    c = conn(); cur = c.cursor()
    cur.execute(
        "INSERT INTO food_quality (branch, chef_name, dish_name, score, notes, created_at, submitted_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (branch.strip(), chef.strip(), dish.strip(), int(score), (notes or "").strip(), ts, submitted_by),
    )
    c.commit(); c.close()
    try: save_to_google_sheets(branch, chef, dish, score, notes, ts)
    except Exception as e: st.warning(f"נשמר מקומית, אך לא לגיליון: {e}")

def score_hint(x: int) -> str:
    return "חלש" if x <= 3 else ("סביר" if x <= 6 else ("טוב" if x <= 8 else "מצוין"))

# === 7 ימים אחרונים / רשת ===
def last7(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)
    return df[df["created_at"] >= start].copy()

def worst_network_dish_last7(df: pd.DataFrame, min_count: int = MIN_DISH_WEEK_M) -> Tuple[Optional[str], Optional[float], int]:
    d = last7(df)
    if d.empty: return None, None, 0
    g = d.groupby("dish_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
    g = g[g["n"] >= min_count]
    if g.empty: return None, None, 0
    row = g.loc[g["avg"].idxmin()]
    return str(row["dish_name"]), float(row["avg"]), int(row["n"])

def network_branch_avgs_last7(df: pd.DataFrame) -> pd.DataFrame:
    d = last7(df)
    if d.empty: return pd.DataFrame(columns=["branch","avg"])
    g = d.groupby("branch")["score"].mean().reset_index().rename(columns={"score":"avg"})
    return g.sort_values("avg", ascending=False)

def network_top_chef_last7(df: pd.DataFrame, min_n: int):
    d = last7(df)
    if d.empty: return None, None, None, 0
    g = d.groupby("chef_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
    g = g[g["n"] >= min_n]
    if g.empty: return None, None, None, 0
    row = g.loc[g["avg"].idxmax()]
    chef = str(row["chef_name"]); avg = float(row["avg"]); n = int(row["n"])
    try: branch_mode = d[d["chef_name"] == chef]["branch"].mode().iat[0]
    except Exception: branch_mode = None
    return chef, (None if branch_mode is None else str(branch_mode)), avg, n

def network_best_worst_dish_last7(df: pd.DataFrame, min_n: int):
    d = last7(df)
    if d.empty: return None, None
    g = d.groupby("dish_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
    g = g[g["n"] >= min_n]
    if g.empty: return None, None
    best = g.loc[g["avg"].idxmax()]
    worst = g.loc[g["avg"].idxmin()]
    best_t = (str(best["dish_name"]), float(best["avg"]), int(best["n"]))
    worst_t = (str(worst["dish_name"]), float(worst["avg"]), int(worst["n"]))
    if best_t[0] == worst_t[0]: return best_t, None
    return best_t, worst_t

# =========================
# ------ LOGIN / AUTH -----
# =========================
def require_auth() -> dict:
    if "auth" not in st.session_state: st.session_state.auth = {"role": None, "branch": None}
    auth = st.session_state.auth
    if not auth["role"]:
        st.markdown('<div class="header-min"><p class="title">ג׳ירף – איכויות מזון</p></div>', unsafe_allow_html=True)
        df_login = load_df()
        name, avg, n = worst_network_dish_last7(df_login, MIN_DISH_WEEK_M)
        box = f"<div class='daily-pick-login'><div class='ttl'>מנה יומית לבדיקה</div><div class='dish'>{name or '—'}</div>"
        if avg is not None: box += f"<div class='avg'>ממוצע רשת (7 ימים): {avg:.2f} · N={n}</div>"
        box += "</div>"
        st.markdown(box, unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.write("בחרו מצב עבודה:")
        role = st.radio("", options=["סניף", "מטה"], horizontal=True, index=0, label_visibility="collapsed")
        if role == "סניף":
            branch_opt = ["— בחר —"] + BRANCHES
            selected = st.selectbox("שם סניף *", options=branch_opt, index=0)
            if st.button("המשך"):
                if selected == "— בחר —": st.error("נא לבחור סניף.")
                else:
                    st.session_state.auth = {"role": "branch", "branch": selected}
                    st.rerun()
        else:
            if st.button("המשך כ'מטה'"):
                st.session_state.auth = {"role": "meta", "branch": None}
                # הגדרת סניף ברירת מחדל למטה
                st.session_state.setdefault("meta_branch", "— בחר —")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()
    return auth
auth = require_auth()

# =========================
# -------- HEADER ---------
# =========================
st.markdown('<div class="header-min"><p class="title">ג׳ירף – איכויות מזון</p></div>', unsafe_allow_html=True)
chip = auth["branch"] if auth["role"] == "branch" else "מטה"
st.markdown(f'<div class="status-min"><span class="chip">{chip}</span></div>', unsafe_allow_html=True)

df = load_df()

# =========================
# --- META: ACTIVE BRANCH SELECTOR (outside form) ---
# =========================
selected_branch: Optional[str]
if auth["role"] == "meta":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    # שומר מצב ב-session_state כדי שכל שינוי יגרום לריראנדר ומיד יעדכן את גלילת הטבחים
    current = st.session_state.get("meta_branch", "— בחר —")
    selected_branch = st.selectbox("בחר/י סניף להזנה *", ["— בחר —"] + BRANCHES,
                                   index=(0 if current not in BRANCHES else BRANCHES.index(current)+1),
                                   key="meta_branch")
    st.markdown('</div>', unsafe_allow_html=True)
    if selected_branch == "— בחר —":
        st.info("בחר/י סניף למטה כדי להתחיל להזין.")
        st.stop()
else:
    selected_branch = auth["branch"]

# =========================
# -------- FORM --------
# =========================
st.markdown('<div class="card">', unsafe_allow_html=True)
with st.form("quality_form", clear_on_submit=False):
    colA, colB, colC = st.columns([1, 1, 1])

    with colA:
        st.text_input("שם סניף", value=selected_branch, disabled=True)

    # גלילה לפי הסניף + שדה הקלדה ידנית נפרד
    with colB:
        names = CHEFS_BY_BRANCH.get(selected_branch, [])
        chef_choice = st.selectbox("שם הטבח מהרשימה", options=["— בחר —"] + names, index=0, key="chef_choice")
        chef_manual = st.text_input("שם הטבח — הקלדה ידנית (לא חובה)", value="", key="chef_manual")

    with colC:
        dish = st.selectbox("שם המנה *", options=["— בחר —"] + DISHES, index=0)

    colD, colE = st.columns([1, 1])
    with colD:
        score_choice = st.selectbox(
            "ציון איכות *",
            options=["— בחר —"] + list(range(1, 11)),
            index=0,
            format_func=lambda x: f"{x} - {score_hint(x)}" if isinstance(x, int) else x
        )
    with colE:
        notes = st.text_area("הערות (לא חובה)", value="")

    submitted = st.form_submit_button("שמור בדיקה")
st.markdown('</div>', unsafe_allow_html=True)

# ולידציה ושמירה
if submitted:
    chef_final = chef_manual.strip() if chef_manual.strip() else (chef_choice if chef_choice != "— בחר —" else "")
    if not chef_final:
        st.error("נא לבחור שם טבח מהרשימה או להקליד ידנית.")
    elif not dish or dish == "— בחר —":
        st.error("נא לבחור שם מנה.")
    elif not isinstance(score_choice, int):
        st.error("נא לבחור ציון איכות.")
    else:
        insert_record(selected_branch, chef_final, dish, int(score_choice), notes, submitted_by=auth["role"])
        load_df.clear()
        st.success("נשמר בהצלחה.")

# =========================
# --- WEEKLY / KPI (META) ---
# =========================
def fmt_num(v: Optional[float]) -> str:
    return "—" if v is None else f"<span class='num-green'>{v:.2f}</span>"

def network_branch_avgs_last7(df: pd.DataFrame) -> pd.DataFrame:
    d = last7(df)
    if d.empty: return pd.DataFrame(columns=["branch","avg"])
    g = d.groupby("branch")["score"].mean().reset_index().rename(columns={"score":"avg"})
    return g.sort_values("avg", ascending=False)

if auth["role"] == "meta" and not df.empty:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### KPI רשת – 7 ימים אחרונים")

    g = network_branch_avgs_last7(df)
    if not g.empty:
        light_palette = ["#cfe8ff","#d7fde7","#fde2f3","#fff3bf","#e5e1ff","#c9faf3","#ffdede","#eaf7e5"]
        x_axis = alt.Axis(labelAngle=0, labelPadding=6, labelColor='#111', title=None,
                          labelOverlap="greedy", labelLimit=300, labelFontSize=12)
        chart = (
            alt.Chart(g)
            .mark_bar(size=36)
            .encode(
                x=alt.X("branch:N", sort='-y', axis=x_axis),
                y=alt.Y("avg:Q", scale=alt.Scale(domain=(0, 10)), title=None),
                color=alt.Color("branch:N", legend=None, scale=alt.Scale(range=light_palette)),
                tooltip=[alt.Tooltip("branch:N", title="סניף"), alt.Tooltip("avg:Q", title="ממוצע", format=".2f")],
            )
            .properties(height=260)
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart, use_container_width=True)

    # טבח מוביל + מנות טובה/חלשה
    def network_top_chef_last7(df: pd.DataFrame, min_n: int):
        d = last7(df)
        if d.empty: return None, None, None, 0
        g = d.groupby("chef_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
        g = g[g["n"] >= min_n]
        if g.empty: return None, None, None, 0
        row = g.loc[g["avg"].idxmax()]
        chef = str(row["chef_name"]); avg = float(row["avg"]); n = int(row["n"])
        try: branch_mode = d[d["chef_name"] == chef]["branch"].mode().iat[0]
        except Exception: branch_mode = None
        return chef, (None if branch_mode is None else str(branch_mode)), avg, n

    def network_best_worst_dish_last7(df: pd.DataFrame, min_n: int):
        d = last7(df)
        if d.empty: return None, None
        g = d.groupby("dish_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
        g = g[g["n"] >= min_n]
        if g.empty: return None, None
        best = g.loc[g["avg"].idxmax()]
        worst = g.loc[g["avg"].idxmin()]
        best_t = (str(best["dish_name"]), float(best["avg"]), int(best["n"]))
        worst_t = (str(worst["dish_name"]), float(worst["avg"]), int(worst["n"]))
        if best_t[0] == worst_t[0]: return best_t, None
        return best_t, worst_t

    def line(name, value): st.markdown(f"- **{name}:** {value}", unsafe_allow_html=True)

    chef, chef_branch, chef_avg, chef_n = network_top_chef_last7(df, MIN_CHEF_WEEK_M)
    best_dish, worst_dish = network_best_worst_dish_last7(df, MIN_DISH_WEEK_M)
    line("ממוצע טבח מוביל", "—" if chef is None else f"{chef} · {chef_branch or ''} · <span class='num-green'>{chef_avg:.2f}</span>")
    line("ממוצע מנה הכי גבוה", "—" if not best_dish else f"{best_dish[0]} · <span class='num-green'>{best_dish[1]:.2f}</span> (N={best_dish[2]})")
    if worst_dish is not None:
        line("ממוצע מנה הכי נמוך", f"{worst_dish[0]} · <span class='num-green'>{worst_dish[1]:.2f}</span> (N={worst_dish[2]})")
    st.markdown('</div>', unsafe_allow_html=True)
