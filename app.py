# app.py — ג'ירף – איכויות מזון (תיקון הקלדה ידנית + צבעי גרף בהירים ותוויות מאוזנות)
from __future__ import annotations
import os, json, sqlite3
from datetime import datetime, timedelta
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
    # תוספות
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
    "לנדמרק": [
        "יו", "מא", "וואנג הואנבין", "וואנג ג'ינלאי", "ג'או", "אוליבר",
        "זאנג", "בי", "יאנג זימינג", "יאנג רונגשטן", "דונג", "וואנג פוקוואן",
    ],
}

DB_PATH = "food_quality.db"
MIN_CHEF_TOP_M  = 5
MIN_CHEF_WEEK_M = 2
MIN_DISH_WEEK_M = 2

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# =========================
# ---------- STYLE --------
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;700;900&display=swap');

:root{
  --bg:#ffffff;
  --surface:#ffffff;
  --text:#000000;
  --muted:#6b7280;
  --border:#e7ebf0;
  --green-50:#ecfdf5;
  --green-100:#d1fae5;
  --green-500:#10b981;
}

html, body, .main, .block-container{direction:rtl; background:var(--bg);}
.main .block-container{font-family:"Rubik",-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
/* מסגרת שחורה עבה סביב כל הדף */
body{ border:4px solid #000; border-radius:16px; margin:10px; }

/* כותרת עליונה */
.header-min{
  background:var(--green-50);
  border:1px solid var(--green-100);
  border-radius:18px; padding:18px;
  box-shadow:0 6px 22px rgba(0,0,0,.04);
  margin-bottom:14px; text-align:center;
}
.header-min .title{font-size:26px; font-weight:900; color:var(--text); margin:0 0 12px;}

/* קופסת "מנה יומית לבדיקה" בדף הכניסה — מרובעת וממורכזת */
.daily-pick-login{
  background:#fff; border:2px solid var(--green-500);
  border-radius:0; padding:12px 16px;
  display:inline-block; width:min(720px, 92vw); text-align:center;
}
.daily-pick-login .ttl{font-weight:900; color:#065f46; margin:0 0 6px;}
.daily-pick-login .dish{font-weight:900; font-size:18px;}
.daily-pick-login .avg{color:var(--green-500); font-weight:800;}

.card{background:var(--surface); border:1px solid var(--border); border-radius:16px;
  padding:16px; box-shadow:0 4px 18px rgba(10,20,40,.04); margin-bottom:12px;}

.status-min{display:flex; align-items:center; gap:10px; justify-content:center; background:#fff;
  border:1px solid var(--border); border-radius:14px; padding:10px 12px; margin-bottom:12px;}
.chip{padding:4px 10px; border:1px solid var(--green-100); border-radius:999px;
  font-weight:800; font-size:12px; color:#065f46; background:var(--green-50)}

.stTextInput input, .stTextArea textarea{
  background:#fff !important; color:var(--text) !important;
  border-radius:12px !important; border:1px solid var(--border) !important; padding:10px 12px !important;}
.stTextArea textarea{min-height:96px !important;}
.stSelectbox div[data-baseweb="select"]{background:#fff !important; color:var(--text) !important;
  border-radius:12px !important; border:1px solid var(--border) !important;}
.stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox [data-baseweb="select"]:focus-within{
  outline:none !important; box-shadow:0 0 0 2px rgba(16,185,129,.25) !important; border-color:var(--green-500) !important;}
.stRadio [data-baseweb="radio"] svg{ color:#000 !important; fill:#000 !important; }

/* פתיחת ה-select למטה */
.stSelectbox {overflow:visible !important;}
div[data-baseweb="select"] + div[role="listbox"]{ bottom:auto !important; top: calc(100% + 8px) !important; max-height:50vh !important; }

/* טבלאות */
table.small {width:100%; border-collapse:collapse;}
table.small thead tr{ background:var(--green-50); }
table.small th, table.small td {border-bottom:1px solid #f1f1f1; padding:8px; font-size:14px; text-align:center;}
table.small th {font-weight:900; color:var(--text);}
.num-green{color:var(--green-500); font-weight:700;}

/* הסתרת “Press Enter to apply” */
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

def insert_record(branch: str, chef: str, dish: str, score: int, notes: str = "", submitted_by: Optional[str] = None):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    c = conn(); cur = c.cursor()
    cur.execute(
        "INSERT INTO food_quality (branch, chef_name, dish_name, score, notes, created_at, submitted_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (branch.strip(), chef.strip(), dish.strip(), int(score), (notes or "").strip(), timestamp, submitted_by),
    )
    c.commit(); c.close()
    try:
        save_to_google_sheets(branch, chef, dish, score, notes, timestamp)
    except Exception as e:
        st.warning(f"נשמר מקומית, אך לא לגיליון: {e}")

def save_to_google_sheets(branch: str, chef: str, dish: str, score: int, notes: str, timestamp: str):
    if not GSHEETS_AVAILABLE: return
    sheet_id = _get_sheet_id()
    creds_info = _get_service_account_info()
    if not (sheet_id and creds_info): return
    credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    gc = gspread.authorize(credentials)
    gc.open_by_key(sheet_id).sheet1.append_row([timestamp, branch, chef, dish, score, notes or ""])

def refresh_df():
    load_df.clear()

def score_hint(x: int) -> str:
    return "חלש" if x <= 3 else ("סביר" if x <= 6 else ("טוב" if x <= 8 else "מצוין"))


# === רשת 7 ימים ===
def last7(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)
    return df[df["created_at"] >= start].copy()

def worst_network_dish_last7(df: pd.DataFrame, min_count: int = MIN_DISH_WEEK_M
                             ) -> Tuple[Optional[str], Optional[float], int]:
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

def network_top_chef_last7(df: pd.DataFrame, min_n: int) -> Tuple[Optional[str], Optional[str], Optional[float], int]:
    d = last7(df)
    if d.empty: return None, None, None, 0
    g = d.groupby("chef_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
    g = g[g["n"] >= min_n]
    if g.empty: return None, None, None, 0
    row = g.loc[g["avg"].idxmax()]
    chef = str(row["chef_name"]); avg = float(row["avg"]); n = int(row["n"])
    try:
        branch_mode = d[d["chef_name"] == chef]["branch"].mode().iat[0]
    except Exception:
        branch_mode = None
    return chef, (None if branch_mode is None else str(branch_mode)), avg, n

def network_best_worst_dish_last7(df: pd.DataFrame, min_n: int
                                  ) -> Tuple[Optional[Tuple[str,float,int]], Optional[Tuple[str,float,int]]]:
    d = last7(df)
    if d.empty: return None, None
    g = d.groupby("dish_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
    g = g[g["n"] >= min_n]
    if g.empty: return None, None
    best = g.loc[g["avg"].idxmax()]
    worst = g.loc[g["avg"].idxmin()]
    best_t = (str(best["dish_name"]), float(best["avg"]), int(best["n"]))
    worst_t = (str(worst["dish_name"]), float(worst["avg"]), int(worst["n"]))
    if best_t[0] == worst_t[0]:
        return best_t, None
    return best_t, worst_t

# =========================
# ------ LOGIN / AUTH -----
# =========================
def require_auth() -> dict:
    if "auth" not in st.session_state:
        st.session_state.auth = {"role": None, "branch": None}
    auth = st.session_state.auth

    if not auth["role"]:
        st.markdown('<div class="header-min">', unsafe_allow_html=True)
        st.markdown('<p class="title">ג׳ירף – איכויות מזון</p>', unsafe_allow_html=True)
        # מנה יומית בדף הכניסה
        df_login = load_df()
        name, avg, n = worst_network_dish_last7(df_login, MIN_DISH_WEEK_M)
        if name:
            st.markdown(
                f"<div class='daily-pick-login'><div class='ttl'>מנה יומית לבדיקה</div>"
                f"<div class='dish'>{name}</div>"
                f"<div class='avg'>ממוצע רשת (7 ימים): {avg:.2f} · N={n}</div></div>",
                unsafe_allow_html=True)
        else:
            st.markdown("<div class='daily-pick-login'><div class='ttl'>מנה יומית לבדיקה</div><div class='dish'>—</div></div>",
                        unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.write("בחרו מצב עבודה:")
        role = st.radio("", options=["סניף", "מטה"], horizontal=True, index=0, label_visibility="collapsed")

        if role == "סניף":
            branch_opt = ["— בחר —"] + BRANCHES
            selected = st.selectbox("שם סניף *", options=branch_opt, index=0)
            if st.button("המשך"):
                if selected == "— בחר —":
                    st.error("נא לבחור סניף.")
                else:
                    st.session_state.auth = {"role": "branch", "branch": selected}
                    st.rerun()
        else:
            if st.button("המשך כ'מטה'"):
                st.session_state.auth = {"role": "meta", "branch": None}
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()
    return auth

auth = require_auth()

# =========================
# ---- CHEF MANUAL MODE ---
# =========================
CHEF_MANUAL_OPTION = "הקלדה ידנית…"
if "chef_mode" not in st.session_state:
    st.session_state.chef_mode = "list"   # "list" | "manual"
if "chef_manual" not in st.session_state:
    st.session_state.chef_manual = ""

def _chef_select_changed():
    """עוברים למצב הקלדה כשהאופציה נבחרת, סוגרים את הדרופדאון ע"י reset + rerun (חשוב לנייד)."""
    sel = st.session_state.get("chef_select")
    if sel == CHEF_MANUAL_OPTION:
        st.session_state.chef_mode = "manual"
        st.session_state.chef_select = "— בחר —"  # סוגר את הדרופדאון
        st.rerun()

def _chef_back_to_list():
    st.session_state.chef_mode = "list"

# =========================
# -------- MAIN UI --------
# =========================
st.markdown('<div class="header-min"><p class="title">ג׳ירף – איכויות מזון</p></div>', unsafe_allow_html=True)
chip = auth["branch"] if auth["role"] == "branch" else "מטה"
st.markdown(f'<div class="status-min"><span class="chip">{chip}</span></div>', unsafe_allow_html=True)

df = load_df()

# -------- FORM --------
st.markdown('<div class="card">', unsafe_allow_html=True)
with st.form("quality_form", clear_on_submit=False):
    colA, colB, colC = st.columns([1, 1, 1])

    if auth["role"] == "meta":
        with colA:
            branch_opt = ["— בחר —"] + BRANCHES
            selected_branch = st.selectbox("שם סניף *", options=branch_opt, index=0)
    else:
        selected_branch = auth["branch"]
        with colA:
            st.text_input("שם סניף", value=selected_branch, disabled=True)

    with colB:
        # רשימת טבחים לסניף + האופציה להקלדה ידנית (תמיד זמינה)
        chef_options = ["— בחר —"]
        if selected_branch and selected_branch != "— בחר —":
            chef_options += CHEFS_BY_BRANCH.get(selected_branch, [])
        chef_options += [CHEF_MANUAL_OPTION]

        st.selectbox(
            "שם הטבח *",
            options=chef_options,
            index=0,
            key="chef_select",
            on_change=_chef_select_changed,
            help="בחר/י מהרשימה או בחר/י 'הקלדה ידנית…' כדי להקליד שם חדש"
        )

        if st.session_state.chef_mode == "manual":
            st.text_input(
                "שם הטבח — הקלדה ידנית *",
                key="chef_manual",
                placeholder="הקלד/י כאן את שם הטבח",
            )
            st.button("חזרה לרשימה", on_click=_chef_back_to_list)

    with colC:
        dish_options = ["— בחר —"] + DISHES
        dish = st.selectbox("שם המנה *", options=dish_options, index=0)

    colD, colE = st.columns([1, 1])
    with colD:
        score_options = ["— בחר —"] + list(range(1, 11))
        score_choice = st.selectbox(
            "ציון איכות *",
            options=score_options,
            index=0,
            format_func=lambda x: f"{x} - {score_hint(x)}" if isinstance(x, int) else x
        )
    with colE:
        notes = st.text_area("הערות (לא חובה)", value="")

    submitted = st.form_submit_button("שמור בדיקה")
st.markdown('</div>', unsafe_allow_html=True)

# ולידציה ושמירה
if submitted:
    if auth["role"] == "meta" and (not selected_branch or selected_branch == "— בחר —"):
        st.error("נא לבחור סניף.")
    else:
        # קביעת שם הטבח
        if st.session_state.chef_mode == "manual":
            chef_final = (st.session_state.get("chef_manual") or "").strip()
        else:
            sel = st.session_state.get("chef_select")
            chef_final = sel if sel and sel not in ("— בחר —", CHEF_MANUAL_OPTION) else ""

        if not chef_final:
            st.error("נא לבחור שם טבח או להקליד ידנית.")
        elif not dish or dish == "— בחר —":
            st.error("נא לבחור שם מנה.")
        elif not isinstance(score_choice, int):
            st.error("נא לבחור ציון איכות.")
        else:
            insert_record(selected_branch, chef_final, dish, int(score_choice), notes, submitted_by=auth["role"])
            refresh_df()
            st.success("נשמר בהצלחה.")

# =========================
# --- WEEKLY BY BRANCH ----
# =========================
def weekly_branch_params(df: pd.DataFrame, branch: str,
                         min_chef: int = MIN_CHEF_WEEK_M,
                         min_dish: int = MIN_DISH_WEEK_M) -> Dict[str, Any]:
    if df.empty:
        return {"avg": (None, None), "best_chef": ((None, None),(None, None)),
                "worst": (None, None), "best_dish_name": (None, None),
                "worst_dish_name": (None, None), "n_week": 0, "n_last": 0}
    d = df[df["branch"] == branch].copy()
    if d.empty:
        return {"avg": (None, None), "best_chef": ((None, None),(None, None)),
                "worst": (None, None), "best_dish_name": (None, None),
                "worst_dish_name": (None, None), "n_week": 0, "n_last": 0}

    now = pd.Timestamp.now(tz="UTC")
    w_start = (now - pd.Timedelta(days=int(now.dayofweek))).normalize()
    w_end = w_start + pd.Timedelta(days=7)
    lw_start = w_start - pd.Timedelta(days=7)
    lw_end = w_start

    sw  = d[(d["created_at"] >= w_start)  & (d["created_at"] < w_end)]
    slw = d[(d["created_at"] >= lw_start) & (d["created_at"] < lw_end)]

    avg_w  = float(sw["score"].mean())  if not sw.empty  else None
    avg_lw = float(slw["score"].mean()) if not slw.empty else None

    def _chef_best_worst(frame: pd.DataFrame, min_count: int
                         ) -> Tuple[Tuple[Optional[str], Optional[float]], Tuple[Optional[str], Optional[float]]]:
        if frame.empty: return (None, None), (None, None)
        g = frame.groupby("chef_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
        g = g[g["n"] >= min_count]
        if g.empty: return (None, None), (None, None)
        best_row  = g.loc[g["avg"].idxmax()]
        worst_row = g.loc[g["avg"].idxmin()]
        return (str(best_row["chef_name"]), float(best_row["avg"])), (str(worst_row["chef_name"]), float(worst_row["avg"]))

    def _dish_best_worst(frame: pd.DataFrame, min_count: int
                         ) -> Tuple[Optional[str], Optional[str]]:
        if frame.empty: return None, None
        g = frame.groupby("dish_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
        g = g[g["n"] >= min_count]
        if g.empty: return None, None
        best_row  = g.loc[g["avg"].idxmax()]
        worst_row = g.loc[g["avg"].idxmin()]
        best, worst = str(best_row["dish_name"]), str(worst_row["dish_name"])
        if best == worst: return best, None
        return best, worst

    (best_name_w, best_avg_w), (best_name_lw, best_avg_lw) = _chef_best_worst(sw,  MIN_CHEF_WEEK_M)
    best_dish_name_w,  worst_dish_name_w  = _dish_best_worst(sw,  MIN_DISH_WEEK_M)
    best_dish_name_lw, worst_dish_name_lw = _dish_best_worst(slw, MIN_DISH_WEEK_M)

    worst_w = float(sw.groupby("chef_name")["score"].mean().min()) if not sw.empty else None
    worst_lw = float(slw.groupby("chef_name")["score"].mean().min()) if not slw.empty else None

    return {
        "avg": (avg_w, avg_lw),
        "best_chef": ((best_name_w, best_avg_w), (best_name_lw, best_avg_lw)),
        "worst": (worst_w, worst_lw),
        "best_dish_name": (best_dish_name_w, best_dish_name_lw),
        "worst_dish_name": (worst_dish_name_w, worst_dish_name_lw),
        "n_week": int(len(sw)), "n_last": int(len(slw)),
    }

def wow_delta(curr: Optional[float], prev: Optional[float]) -> str:
    if curr is None and prev is None: return "—"
    if curr is None: return "↓ —"
    if prev is None: return "↑ —"
    diff = curr - prev
    sign = "↑" if diff >= 0 else "↓"
    return f"{sign} {diff:+.2f}"

def fmt_num(v: Optional[float]) -> str:
    return "—" if v is None else f"<span class='num-green'>{v:.2f}</span>"

# =========================
# --- NETWORK KPI (META) ---
# =========================
if auth["role"] == "meta" and not df.empty:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### KPI רשת – 7 ימים אחרונים")

    # 1) גרף עמודות ממוצע ציון לפי סניף — תוויות מאוזנות וצבעים בהירים מאוד
    g = network_branch_avgs_last7(df)
    if not g.empty:
        light_palette = [
            "#cfe8ff",  # כחול בהיר מאד
            "#d7fde7",  # ירוק-מנטה בהיר
            "#fde2f3",  # ורוד בהיר מאד
            "#fff3bf",  # צהוב-ונילה
            "#e5e1ff",  # סגול בהיר מאד
            "#c9faf3",  # טיל בהיר מאד
            "#ffdede",  # אדמדם בהיר מאד
            "#eaf7e5",  # ירקרק בהיר מאד
        ]
        x_axis = alt.Axis(
            labelAngle=0,
            labelPadding=6,
            labelColor='#111',
            title=None,
            labelOverlap="greedy",
            labelLimit=500,
            labelFontSize=12,
        )
        chart = (
            alt.Chart(g)
            .mark_bar(size=36)
            .encode(
                x=alt.X("branch:N", sort='-y', axis=x_axis),
                y=alt.Y("avg:Q", scale=alt.Scale(domain=(0, 10)), title=None),
                color=alt.Color("branch:N", legend=None, scale=alt.Scale(range=light_palette)),
                tooltip=[
                    alt.Tooltip("branch:N", title="סניף"),
                    alt.Tooltip("avg:Q", title="ממוצע", format=".2f"),
                ],
            )
            .properties(height=260)
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("אין מספיק נתונים לגרף סניפים.")

    # 2) טבח מוביל
    chef, chef_branch, chef_avg, chef_n = network_top_chef_last7(df, MIN_CHEF_WEEK_M)

    # 3-4) מנה טובה/לשיפור
    best_dish, worst_dish = network_best_worst_dish_last7(df, MIN_DISH_WEEK_M)

    def line(name, value):
        st.markdown(f"- **{name}:** {value}", unsafe_allow_html=True)

    line("ממוצע טבח מוביל", "—" if chef is None else f"{chef} · {chef_branch or ''} · <span class='num-green'>{chef_avg:.2f}</span>")
    line("ממוצע מנה הכי גבוה", "—" if not best_dish else f"{best_dish[0]} · <span class='num-green'>{best_dish[1]:.2f}</span> (N={best_dish[2]})")
    if worst_dish is not None:
        line("ממוצע מנה הכי נמוך", f"{worst_dish[0]} · <span class='num-green'>{worst_dish[1]:.2f}</span> (N={worst_dish[2]})")

    st.markdown('</div>', unsafe_allow_html=True)

    # סיכום שבועי לפי סניף (מתחת ל-KPI)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### סיכום שבועי לפי סניף")
    for b in BRANCHES:
        with st.expander(b, expanded=False):
            m = weekly_branch_params(df, b, MIN_CHEF_WEEK_M, MIN_DISH_WEEK_M)
            avg_w,  avg_lw  = m["avg"]
            (best_name_w, best_avg_w), (best_name_lw, best_avg_lw) = m["best_chef"]
            worst_w, worst_lw = m["worst"]
            best_dish_w,  best_dish_lw  = m["best_dish_name"]
            worst_dish_w, worst_dish_lw = m["worst_dish_name"]

            if best_dish_w and worst_dish_w and best_dish_w == worst_dish_w:
                worst_dish_w = None
            if best_dish_lw and worst_dish_lw and best_dish_lw == worst_dish_lw:
                worst_dish_lw = None

            def fmt_avg_name(avg: Optional[float], name: Optional[str]) -> str:
                if avg is None and not name: return "—"
                if avg is None: return f"{name}"
                if not name: return f"<span class='num-green'>{avg:.2f}</span>"
                return f"<span class='num-green'>{avg:.2f}</span> · {name}"

            html = f"""
            <table class="small">
              <thead>
                <tr>
                  <th>פרמטר</th>
                  <th>השבוע</th>
                  <th>שבוע שעבר</th>
                  <th>Δ שינוי</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><b>ממוצע ציון כללי</b></td>
                  <td>{fmt_num(avg_w)}</td>
                  <td>{fmt_num(avg_lw)}</td>
                  <td>{wow_delta(avg_w, avg_lw)}</td>
                </tr>
                <tr>
                  <td><b>ממוצע טבח מוביל</b> <span class="small-muted">(מינ׳ {MIN_CHEF_WEEK_M})</span></td>
                  <td>{fmt_avg_name(best_avg_w, best_name_w)}</td>
                  <td>{fmt_avg_name(best_avg_lw, best_name_lw)}</td>
                  <td>{wow_delta(best_avg_w, best_avg_lw)}</td>
                </tr>
                <tr>
                  <td><b>ממוצע טבח חלש</b> <span class="small-muted">(מינ׳ {MIN_CHEF_WEEK_M})</span></td>
                  <td>{fmt_num(worst_w)}</td>
                  <td>{fmt_num(worst_lw)}</td>
                  <td>{wow_delta(worst_w, worst_lw)}</td>
                </tr>
                <tr>
                  <td><b>מנה טובה</b></td>
                  <td>{best_dish_w or '—'}</td>
                  <td>{best_dish_lw or '—'}</td>
                  <td>—</td>
                </tr>
                <tr>
                  <td><b>מנה לשיפור</b></td>
                  <td>{worst_dish_w or '—'}</td>
                  <td>{worst_dish_lw or '—'}</td>
                  <td>—</td>
                </tr>
              </tbody>
            </table>
            """
            st.markdown(html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
