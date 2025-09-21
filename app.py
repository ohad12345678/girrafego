# app.py — ג'ירף – איכויות מזון (Landing ענברי, קוביות 3×3, Daily Pick טרי, KPI; סיכום 60 יום; GPT מוגבל לסניף)
from __future__ import annotations
import os, json, sqlite3
from datetime import datetime
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

BRANCHES: List[str] = [
    "חיפה", "ראשל״צ", "רמה״ח", "נס ציונה", "לנדמרק", "פתח תקווה", "הרצליה", "סביון"
]

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
    "לנדמרק": [
        "יו", "מא", "וואנג הואנבין", "וואנג ג'ינלאי", "ג'או", "אוליבר", "זאנג", "בי",
        "יאנג זימינג", "יאנג רונגשטן", "דונג", "וואנג פוקוואן"
    ],
}

DB_PATH = "food_quality.db"
MIN_CHEF_TOP_M  = 5
MIN_CHEF_WEEK_M = 2      # משמש כסף מינימום גם בחישוב 60 יום
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
  --text:#0d0f12;
  --border:#e7ebf0;
  --green-50:#ecfdf5;
  --tile-green:#d7fde7;    /* ירוק בהיר חדש לקוביות */
  --green-100:#d1fae5;
  --green-500:#10b981;
  --amber:#FFE07A;         /* צהבהב-כתמתם לכותרת בעמוד הפתיחה */
}
html, body, .main, .block-container{direction:rtl; background:var(--bg);}
.main .block-container{font-family:"Rubik",-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
body{ border:4px solid #000; border-radius:16px; margin:10px; }

/* כותרות */
.header-min{
  background:var(--green-50);
  border:1px solid #000;
  border-radius:0;
  padding:16px;
  margin-bottom:14px;
  text-align:center;
  box-shadow:0 6px 22px rgba(0,0,0,.04);
}
.header-landing{ /* בעמוד הפתיחה בלבד – ענבר */
  background:var(--amber);
  border:1px solid #000;
  border-radius:0;
  padding:16px;
  margin-bottom:14px;
  text-align:center;
  box-shadow:0 6px 22px rgba(0,0,0,.04);
}
.header-min .title, .header-landing .title{font-size:26px; font-weight:900; color:#000; margin:0;}

/* "מנה יומית לבדיקה" */
.daily-pick-login{
  background:#fff; border:2px solid var(--green-500);
  border-radius:0; padding:12px 16px;
  display:inline-block; width:min(720px, 92vw); text-align:center;
}
.daily-pick-login .ttl{font-weight:900; color:#065f46; margin:0 0 6px;}
.daily-pick-login .dish{font-weight:900; font-size:18px;}
.daily-pick-login .avg{color:var(--green-500); font-weight:800;}

/* Grid 3×3 */
.branch-grid{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
@media (max-width:480px){ .branch-grid{ grid-template-columns:repeat(3,1fr);} }

a.branch-card, .branch-card:link, .branch-card:visited, .branch-card:hover, .branch-card:active{
  color:#000 !important; text-decoration:none !important;
}
.branch-card{
  display:flex; align-items:center; justify-content:center;
  background:var(--tile-green);
  border:2px solid #000; border-radius:12px; padding:18px 8px;
  font-weight:900; min-height:64px; user-select:none;
  box-shadow:0 4px 14px rgba(0,0,0,.06);
}

/* מצב נוכחי */
.status-min{display:flex; align-items:center; gap:10px; justify-content:center; background:#fff;
  border:1px solid var(--border); border-radius:14px; padding:10px 12px; margin:12px 0;}
.chip{padding:4px 10px; border:1px solid var(--green-100); border-radius:999px;
  font-weight:800; font-size:12px; color:#065f46; background:var(--green-50)}

.stTextInput input, .stTextArea textarea{
  background:#fff !important; color:#000 !important;
  border-radius:12px !important; border:1px solid var(--border) !important; padding:10px 12px !important;}
.stTextArea textarea{min-height:96px !important;}
.stSelectbox div[data-baseweb="select"]{background:#fff !important; color:#000 !important;
  border-radius:12px !important; border:1px solid var(--border) !important;}
.stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox [data-baseweb="select"]:focus-within{
  outline:none !important; box-shadow:0 0 0 2px rgba(16,185,129,.25) !important; border-color:var(--green-500) !important;}
.stRadio [data-baseweb="radio"] svg{ color:#000 !important; fill:#000 !important; }

/* לפתוח Select למטה */
.stSelectbox {overflow:visible !important;}
div[data-baseweb="select"] + div[role="listbox"]{ bottom:auto !important; top: calc(100% + 8px) !important; max-height:50vh !important; }

/* טבלאות */
table.small {width:100%; border-collapse:collapse;}
table.small thead tr{ background:var(--green-50); }
table.small th, table.small td {border-bottom:1px solid #f1f1f1; padding:8px; font-size:14px; text-align:center;}
table.small th {font-weight:900; color:#000;}
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

def load_df_fresh() -> pd.DataFrame:
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
    sid = st.secrets.get("GOOGLE_SHEET_ID") or os.getenv("GOOGLE_SHEET_ID")
    if sid: return sid
    url = st.secrets.get("GOOGLE_SHEET_URL") or os.getenv("GOOGLE_SHEET_URL")
    if url and "/spreadsheets/d/" in url:
        try: return url.split("/spreadsheets/d/")[1].split("/")[0]
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

# === 7 ימים אחרונים (ל-KPI הרשת) ===
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
# ------ QUERY PARAMS -----
# =========================
def qp_get(key: str) -> Optional[str]:
    try:
        return st.query_params.get(key)
    except Exception:
        q = st.experimental_get_query_params()
        vals = q.get(key, [])
        return vals[0] if vals else None

def qp_set(**kwargs):
    try:
        st.query_params.clear()
        st.query_params.update(kwargs)
    except Exception:
        st.experimental_set_query_params(**kwargs)

def qp_clear():
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()

def safe_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

# =========================
# ------ LANDING ----------
# =========================
def render_landing():
    # כותרת בעמוד פתיחה – ענבר
    st.markdown('<div class="header-landing"><p class="title">ג׳ירף – איכויות מזון</p></div>', unsafe_allow_html=True)

    # מנה יומית טרייה (לעקוף cache בכל כניסה)
    df_login = load_df_fresh()
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

    # קוביות 3×3
    items = ["מטה"] + BRANCHES
    links = "".join([f"<a class='branch-card' href='?select={item}'>{item}</a>" for item in items])
    st.markdown(f"<div class='branch-grid'>{links}</div>", unsafe_allow_html=True)

def consume_select_param():
    sel = qp_get("select")
    if not sel:
        return False
    if sel == "מטה":
        st.session_state.auth = {"role": "meta", "branch": None}
    elif sel in BRANCHES:
        st.session_state.auth = {"role": "branch", "branch": sel}
    qp_clear()
    safe_rerun()
    return True

def require_auth() -> dict:
    if "auth" not in st.session_state:
        st.session_state.auth = {"role": None, "branch": None}
    auth = st.session_state.auth

    if consume_select_param():
        st.stop()

    if not auth["role"]:
        render_landing()
        st.stop()
    return auth

auth = require_auth()

# =========================
# -------- MAIN UI --------
# =========================
st.markdown('<div class="header-min"><p class="title">ג׳ירף – איכויות מזון</p></div>', unsafe_allow_html=True)
chip = auth["branch"] if auth["role"] == "branch" else "מטה"
st.markdown(f'<div class="status-min"><span class="chip">{chip}</span></div>', unsafe_allow_html=True)

df = load_df()

# בחירת סניף להזנה (מטה)
if auth["role"] == "meta":
    st.markdown("#### בחירת סניף להזנה (מטה)")
    st.selectbox("בחר/י סניף להזנה", options=["— בחר —"] + BRANCHES, index=0, key="meta_branch_select")

# -------- FORM --------
st.markdown('<div class="card">', unsafe_allow_html=True)
with st.form("quality_form", clear_on_submit=False):
    if auth["role"] == "meta":
        selected_branch = st.session_state.get("meta_branch_select", "— בחר —")
    else:
        selected_branch = auth["branch"]

    col1, col2 = st.columns(2)

    with col1:
        chef_options = ["— בחר —"]
        if selected_branch and selected_branch != "— בחר —":
            chef_options += CHEFS_BY_BRANCH.get(selected_branch, [])
        chef_choice = st.selectbox("שם הטבח (מרשימה)", options=chef_options, index=0, key="chef_from_list")

    with col2:
        chef_manual = st.text_input("שם הטבח — הקלדה ידנית (לא חובה)", value="", key="chef_manual_input")

    colA, colB = st.columns(2)
    with colA:
        dish = st.selectbox("שם המנה *", options=["— בחר —"] + DISHES, index=0)
    with colB:
        score_choice = st.selectbox(
            "ציון איכות *",
            options=["— בחר —"] + list(range(1, 11)),
            index=0,
            format_func=lambda x: f"{x} - {score_hint(x)}" if isinstance(x, int) else x,
        )

    notes = st.text_area("הערות (לא חובה)", value="")
    submitted = st.form_submit_button("שמור בדיקה")
st.markdown('</div>', unsafe_allow_html=True)

if submitted:
    if auth["role"] == "meta" and (not selected_branch or selected_branch == "— בחר —"):
        st.error("נא לבחור סניף להזנה.")
    else:
        chef_final = chef_manual.strip() if chef_manual.strip() else (chef_choice if chef_choice != "— בחר —" else None)
        if not chef_final:
            st.error("נא לבחור שם טבח מהרשימה או להקליד ידנית.")
        elif not dish or dish == "— בחר —":
            st.error("נא לבחור שם מנה.")
        elif not isinstance(score_choice, int):
            st.error("נא לבחור ציון איכות.")
        else:
            insert_record(selected_branch, chef_final, dish, int(score_choice), notes, submitted_by=auth["role"])
            refresh_df()
            st.success("נשמר בהצלחה.")

# =========================
# ----- BRANCH SUMMARY (60 יום) -----
# =========================
def branch_60d_params(df: pd.DataFrame, branch: str,
                      min_chef: int = MIN_CHEF_WEEK_M,
                      min_dish: int = MIN_DISH_WEEK_M) -> Dict[str, Any]:
    """
    מחזיר מדדים עבור 60 הימים האחרונים (curr) לעומת 60 הימים שלפניהם (prev).
    """
    if df.empty:
        return {"avg": (None, None), "best_chef": ((None, None),(None, None)),
                "worst": (None, None), "best_dish_name": (None, None),
                "worst_dish_name": (None, None), "n_curr": 0, "n_prev": 0}

    d = df[df["branch"] == branch].copy()
    if d.empty:
        return {"avg": (None, None), "best_chef": ((None, None),(None, None)),
                "worst": (None, None), "best_dish_name": (None, None),
                "worst_dish_name": (None, None), "n_curr": 0, "n_prev": 0}

    now = pd.Timestamp.now(tz="UTC")
    curr_start, curr_end = now - pd.Timedelta(days=60), now
    prev_start, prev_end = now - pd.Timedelta(days=120), now - pd.Timedelta(days=60)

    dc = d[(d["created_at"] >= curr_start) & (d["created_at"] < curr_end)]
    dp = d[(d["created_at"] >= prev_start) & (d["created_at"] < prev_end)]

    avg_c  = float(dc["score"].mean())  if not dc.empty  else None
    avg_p  = float(dp["score"].mean())  if not dp.empty  else None

    def _chef_best_worst(frame: pd.DataFrame, min_count: int
                         ) -> Tuple[Tuple[Optional[str], Optional[float]], Tuple[Optional[str], Optional[float]]]:
        if frame.empty: return (None, None), (None, None)
        g = frame.groupby("chef_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
        g = g[g["n"] >= min_count]
        if g.empty: return (None, None), (None, None)
        best_row  = g.loc[g["avg"].idxmax()]
        worst_row = g.loc[g["avg"].idxmin()]
        return (str(best_row["chef_name"]), float(best_row["avg"])), (str(worst_row["chef_name"]), float(worst_row["avg"]))

    def _dish_best_worst(frame: pd.DataFrame, min_count: int) -> Tuple[Optional[str], Optional[str]]:
        if frame.empty: return None, None
        g = frame.groupby("dish_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
        g = g[g["n"] >= min_count]
        if g.empty: return None, None
        best_row  = g.loc[g["avg"].idxmax()]
        worst_row = g.loc[g["avg"].idxmin()]
        best, worst = str(best_row["dish_name"]), str(worst_row["dish_name"])
        if best == worst: return best, None
        return best, worst

    (best_name_c, best_avg_c), (best_name_p, best_avg_p) = _chef_best_worst(dc, min_chef)
    best_dish_name_c,  worst_dish_name_c  = _dish_best_worst(dc,  min_dish)
    best_dish_name_p,  worst_dish_name_p  = _dish_best_worst(dp,  min_dish)

    worst_c = float(dc.groupby("chef_name")["score"].mean().min()) if not dc.empty else None
    worst_p = float(dp.groupby("chef_name")["score"].mean().min()) if not dp.empty else None

    return {
        "avg": (avg_c, avg_p),
        "best_chef": ((best_name_c, best_avg_c), (best_name_p, best_avg_p)),
        "worst": (worst_c, worst_p),
        "best_dish_name": (best_dish_name_c, best_dish_name_p),
        "worst_dish_name": (worst_dish_name_c, worst_dish_name_p),
        "n_curr": int(len(dc)), "n_prev": int(len(dp)),
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

def render_branch_60d_table(df: pd.DataFrame, branch: str):
    m = branch_60d_params(df, branch, MIN_CHEF_WEEK_M, MIN_DISH_WEEK_M)
    avg_c,  avg_p  = m["avg"]
    (best_name_c, best_avg_c), (best_name_p, best_avg_p) = m["best_chef"]
    worst_c, worst_p = m["worst"]
    best_dish_c,  best_dish_p  = m["best_dish_name"]
    worst_dish_c, worst_dish_p = m["worst_dish_name"]
    if best_dish_c and worst_dish_c and best_dish_c == worst_dish_c:
        worst_dish_c = None
    if best_dish_p and worst_dish_p and best_dish_p == worst_dish_p:
        worst_dish_p = None

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
          <th>60 הימים האחרונים</th>
          <th>60 הימים שלפניהם</th>
          <th>Δ שינוי</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><b>ממוצע ציון כללי</b></td>
          <td>{fmt_num(avg_c)}</td>
          <td>{fmt_num(avg_p)}</td>
          <td>{wow_delta(avg_c, avg_p)}</td>
        </tr>
        <tr>
          <td><b>ממוצע טבח מוביל</b> <span class="small-muted">(מינ׳ {MIN_CHEF_WEEK_M})</span></td>
          <td>{fmt_avg_name(best_avg_c, best_name_c)}</td>
          <td>{fmt_avg_name(best_avg_p, best_name_p)}</td>
          <td>{wow_delta(best_avg_c, best_avg_p)}</td>
        </tr>
        <tr>
          <td><b>ממוצע טבח חלש</b> <span class="small-muted">(מינ׳ {MIN_CHEF_WEEK_M})</span></td>
          <td>{fmt_num(worst_c)}</td>
          <td>{fmt_num(worst_p)}</td>
          <td>{wow_delta(worst_c, worst_p)}</td>
        </tr>
        <tr>
          <td><b>מנה טובה</b></td>
          <td>{best_dish_c or '—'}</td>
          <td>{best_dish_p or '—'}</td>
          <td>—</td>
        </tr>
        <tr>
          <td><b>מנה לשיפור</b></td>
          <td>{worst_dish_c or '—'}</td>
          <td>{worst_dish_p or '—'}</td>
          <td>—</td>
        </tr>
      </tbody>
    </table>
    """
    st.markdown(html, unsafe_allow_html=True)

# --- META KPI + סיכומי 60 יום ---
if auth["role"] == "meta" and not df.empty:
    # KPI רשת (7 ימים) — ללא שינוי
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### KPI רשת – 7 ימים אחרונים")

    g = network_branch_avgs_last7(df)
    if not g.empty:
        light_palette = ["#cfe8ff", "#d7fde7", "#fde2f3", "#fff3bf",
                         "#e5e1ff", "#c9faf3", "#ffdede", "#eaf7e5"]
        x_axis = alt.Axis(labelAngle=0, labelPadding=6, labelColor='#111', title=None,
                          labelOverlap="greedy", labelLimit=300, labelFontSize=12)
        chart = (
            alt.Chart(g)
            .mark_bar(size=36)
            .encode(
                x=alt.X("branch:N", sort='-y', axis=x_axis),
                y=alt.Y("avg:Q", scale=alt.Scale(domain=(0, 10)), title=None),
                color=alt.Color("branch:N", legend=None, scale=alt.Scale(range=light_palette)),
                tooltip=[alt.Tooltip("branch:N", title="סניף"),
                         alt.Tooltip("avg:Q", title="ממוצע", format=".2f")],
            )
            .properties(height=260)
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("אין מספיק נתונים לגרף סניפים.")

    chef, chef_branch, chef_avg, chef_n = network_top_chef_last7(df, MIN_CHEF_WEEK_M)
    best_dish, worst_dish = network_best_worst_dish_last7(df, MIN_DISH_WEEK_M)

    def line(name, value):
        st.markdown(f"- **{name}:** {value}", unsafe_allow_html=True)

    line("ממוצע טבח מוביל",
         "—" if chef is None else f"{chef} · {chef_branch or ''} · <span class='num-green'>{chef_avg:.2f}</span>")
    line("ממוצע מנה הכי גבוה",
         "—" if not best_dish else f"{best_dish[0]} · <span class='num-green'>{best_dish[1]:.2f}</span> (N={best_dish[2]})")
    if worst_dish is not None:
        line("ממוצע מנה הכי נמוך",
             f"{worst_dish[0]} · <span class='num-green'>{worst_dish[1]:.2f}</span> (N={worst_dish[2]})")
    st.markdown('</div>', unsafe_allow_html=True)

    # סיכום לפי סניף — 60 יום
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### סיכום לפי סניף — 60 יום")
    for b in BRANCHES:
        with st.expander(b, expanded=False):
            render_branch_60d_table(df, b)
    st.markdown('</div>', unsafe_allow_html=True)

# --- BRANCH summary (60 יום) ---
if auth["role"] == "branch" and not df.empty:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"### סיכום 60 יום — {auth['branch']}")
    render_branch_60d_table(df, auth["branch"])
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# ----- GPT SECTIONS ------
# =========================
def df_to_csv_for_llm(df_in: pd.DataFrame, max_rows: int = 400) -> str:
    d = df_in.copy()
    if len(d) > max_rows: d = d.head(max_rows)
    return d.to_csv(index=False)

def call_openai(user_prompt: str) -> str:
    try:
        from openai import OpenAI
        api_key   = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        org_id    = st.secrets.get("OPENAI_ORG") or os.getenv("OPENAI_ORG")
        project   = st.secrets.get("OPENAI_PROJECT") or os.getenv("OPENAI_PROJECT")
        model     = st.secrets.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        if not api_key: return "חסר מפתח OPENAI_API_KEY (ב-Secrets/Environment)."
        client_kwargs = {"api_key": api_key}
        if org_id:  client_kwargs["organization"] = org_id
        if project: client_kwargs["project"] = project
        client = OpenAI(**client_kwargs)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content":
                 "אתה אנליסט דאטה דובר עברית. מוצגת לך טבלה עם העמודות: id, branch, chef_name, dish_name, score, notes, created_at. ענה בתמציתיות עם תובנות והמלצות קצרות."},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"שגיאה בקריאה ל-OpenAI: {e}"

# --- כרטיס ניתוח עם GPT ---
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### ניתוח עם GPT")

# הגבלת המידע לניתוח לסניף בלבד
if auth["role"] == "branch":
    df_ai = df[df["branch"] == auth["branch"]].copy()
    branch_for_ai = auth["branch"]
else:
    branch_for_ai = st.selectbox("בחר/י סניף לניתוח", options=["— בחר —"] + BRANCHES, index=0, key="ai_branch_pick")
    df_ai = df[df["branch"] == branch_for_ai].copy() if branch_for_ai and branch_for_ai != "— בחר —" else pd.DataFrame()

if not df_ai.empty and st.button("הפעל ניתוח"):
    table_csv = df_to_csv_for_llm(df_ai)
    up = (
        f"סניף לניתוח: {branch_for_ai}\n"
        f"הנה הטבלה בפורמט CSV (עד 400 שורות):\n{table_csv}\n\n"
        f"סכם מגמות, חריגים והמלצות קצרות לניהול הסניף בלבד."
    )
    with st.spinner("מנתח..."):
        ans = call_openai(up)
    st.write(ans)
elif auth["role"] == "meta" and (not branch_for_ai or branch_for_ai == "— בחר —"):
    st.info("בחר/י סניף כדי להפעיל ניתוח.")
elif df_ai.empty:
    st.info("אין נתונים לניתוח עבור הסניף שנבחר.")
st.markdown('</div>', unsafe_allow_html=True)

# --- כרטיס צ'אט אוהד ---
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### שאל את אוהד (על הסניף בלבד)")
user_q = st.text_input("שאלה על הנתונים", value="")
if st.button("שלח"):
    if not user_q.strip():
        st.warning("נא להזין שאלה.")
    elif df_ai.empty:
        st.warning("אין נתונים לסניף הזה כרגע.")
    else:
        table_csv = df_to_csv_for_llm(df_ai)
        up = (
            f"סניף מיקוד: {branch_for_ai}\n"
            f"שאלה: {user_q}\n\n"
            f"הנה טבלת הנתונים של הסניף (עד 400 שורות, CSV):\n{table_csv}\n\n"
            f"ענה בעברית, קצר ולעניין, והישאר ממוקד בסניף בלבד."
        )
        with st.spinner("מנתח..."):
            ans = call_openai(up)
        st.write(ans)
st.markdown('</div>', unsafe_allow_html=True)
