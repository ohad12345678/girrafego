# app.py — ג'ירף מטבחים · איכויות מזון
# הרצה: streamlit run app.py

from __future__ import annotations
import os, json, sqlite3
from datetime import datetime
from typing import List, Optional, Tuple

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
st.set_page_config(page_title="ג'ירף מטבחים – איכויות מזון", layout="wide")

# נתונים קבועים
BRANCHES: List[str] = ["חיפה", "ראשל״צ", "רמה״ח", "נס ציונה", "לנדמרק", "פתח תקווה", "הרצליה", "סביון"]
DISHES: List[str] = [
    "פאד תאי", "מלאזית", "פיליפינית", "אפגנית",
    "קארי דלעת", "סצ'ואן", "ביף רייס",
    "אורז מטוגן", "מאקי סלמון", "מאקי טונה",
    "ספייסי סלמון", "נודלס ילדים"
]
DB_PATH = "food_quality.db"
MIN_CHEF_TOP_M = 5
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

COLOR_NET = "#93C5FD"
COLOR_BRANCH = "#9AE6B4"

# =========================
# ---------- STYLES -------
# =========================
SPLASH_CSS = """
<style>
/* RTL + פונט */
@import url('https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;700;900&display=swap');
html, body, .main, .block-container{direction:rtl;}
.main .block-container{font-family:"Rubik",-apple-system,Segoe UI,Roboto,Arial,sans-serif;}
/* רקע חול */
html, body, .main, .block-container{background:#b79f73;}
/* מרכז אנכי/אופקי */
.splash-wrap{max-width:460px;margin:0 auto;padding:12vh 16px 10vh;text-align:center;}
.splash-title{color:#111; font-size:22px; font-weight:900; margin:0 0 18px;}
/* כפתורים כאריחים */
.stButton>button{
  width:100% !important; height:72px !important;
  background:transparent !important; color:#111 !important;
  border:2px solid #111 !important; border-radius:18px !important;
  font-weight:900 !important; font-size:20px !important;
  box-shadow:none !important;
}
.stButton>button:hover{filter:brightness(0.98);}
.tile-spacer{height:12px;}
</style>
"""

MAIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;700;900&display=swap');
:root{
  --bg:#f6efe6;         /* בז’ בהיר מאוד */
  --surface:#ffffff;
  --text:#1b1f24;
  --muted:#6b7280;
  --border:#e7ebf0;
  --primary:#11b5a3;    /* טורקיז עדין לפעולות */
  --primary-50:#eafff7;
}
html, body, .main, .block-container{direction:rtl; background:var(--bg);}
.main .block-container{font-family:"Rubik",-apple-system,Segoe UI,Roboto,Arial,sans-serif;}
/* מסגרת מובייל ממורכזת */
.mobile-frame{max-width:430px;margin:0 auto;padding:14px 14px 80px;}
/* כותרת נקייה */
.header-mobile{
  background:linear-gradient(180deg, var(--primary-50) 0%, #fff 92%);
  border:1px solid #d9f6ee; border-radius:18px;
  padding:18px 16px; text-align:center; box-shadow:0 10px 22px rgba(3,46,40,.06);
  margin:8px 0 16px;
}
.header-mobile .title{font-weight:900; font-size:22px; color:#0ea594; margin:0;}
/* כרטיסים */
.card{
  background:var(--surface); border:1px solid var(--border); border-radius:16px;
  padding:14px; box-shadow:0 6px 18px rgba(16,185,156,.05); margin-bottom:12px;
}
/* סטטוס */
.status-min{display:flex; justify-content:center; align-items:center; gap:8px;
  background:#fff; border:1px solid var(--border); border-radius:12px; padding:8px 10px;}
.chip{padding:4px 10px; border:1px solid #e6faf5; border-radius:999px;
  background:#f2fffb; color:#0ea594; font-weight:800; font-size:12px;}
/* קלטים נקיים (ללא placeholder) */
.stTextInput input, .stTextArea textarea{
  background:#f7fafc !important; color:var(--text) !important;
  border-radius:14px !important; border:1px solid var(--border) !important; padding:10px 12px !important;
}
.stTextArea textarea{min-height:96px !important;}
.stSelectbox div[data-baseweb="select"]{
  background:#f7fafc !important; color:var(--text) !important;
  border-radius:14px !important; border:1px solid var(--border) !important;
}
.stTextInput label, .stTextArea label, .stSelectbox label{color:#293241 !important; font-weight:800 !important;}
.stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox [data-baseweb="select"]:focus-within{
  outline:none !important; box-shadow:0 0 0 2px rgba(17,181,163,.18) !important; border-color:#11b5a3 !important;
}
/* כפתור פעולה ראשי */
.stButton>button{
  width:100% !important; background:#11b5a3 !important; color:#fff !important; border:0 !important;
  border-radius:16px !important; padding:12px 16px !important; font-weight:900 !important; font-size:16px !important;
  box-shadow:0 8px 20px rgba(17,181,163,.28) !important;
}
.stButton>button:hover{filter:brightness(1.03);}
.stAltairChart{border:1px solid var(--border); border-radius:14px; padding:8px; background:#fff;}
div[data-testid="stWidgetInstructions"]{display:none !important;}
</style>
"""

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
    return df

def _get_sheet_id() -> Optional[str]:
    sheet_id = st.secrets.get("GOOGLE_SHEET_ID") or os.getenv("GOOGLE_SHEET_ID")
    if sheet_id:
        return sheet_id
    sheet_url = st.secrets.get("GOOGLE_SHEET_URL") or os.getenv("GOOGLE_SHEET_URL")
    if sheet_url and "/spreadsheets/d/" in sheet_url:
        try:
            return sheet_url.split("/spreadsheets/d/")[1].split("/")[0]
        except Exception:
            return None
    return None

def _get_service_account_info() -> Optional[dict]:
    raw = (st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON")
           or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
           or st.secrets.get("google_service_account")
           or os.getenv("GOOGLE_SERVICE_ACCOUNT"))
    if not raw: return None
    if isinstance(raw, dict): return raw
    try:
        return json.loads(raw)
    except Exception:
        return None

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
    if not GSHEETS_AVAILABLE:
        return
    sheet_id = _get_sheet_id()
    creds_info = _get_service_account_info()
    if not (sheet_id and creds_info):
        return
    credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_key(sheet_id)
    ws = sh.sheet1
    ws.append_row([timestamp, branch, chef, dish, score, notes or ""])

def refresh_df():
    load_df.clear()

def score_hint(x: int) -> str:
    return "חלש" if x <= 3 else ("סביר" if x <= 6 else ("טוב" if x <= 8 else "מצוין"))

# KPI חישובים
def network_avg(df: pd.DataFrame) -> Optional[float]:
    return float(df["score"].mean()) if not df.empty else None

def branch_avg(df: pd.DataFrame, branch: str) -> Optional[float]:
    d = df[df["branch"] == branch]
    return float(d["score"].mean()) if not d.empty else None

def dish_avg_network(df: pd.DataFrame, dish: str) -> Optional[float]:
    d = df[df["dish_name"] == dish]
    return float(d["score"].mean()) if not d.empty else None

def dish_avg_branch(df: pd.DataFrame, branch: str, dish: str) -> Optional[float]:
    d = df[(df["branch"] == branch) & (df["dish_name"] == dish)]
    return float(d["score"].mean()) if not d.empty else None

def top_chef_network_with_branch(df: pd.DataFrame, min_n: int = MIN_CHEF_TOP_M) -> Tuple[Optional[str], Optional[str], Optional[float], int]:
    if df.empty:
        return None, None, None, 0
    g = df.groupby("chef_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
    g = g.sort_values(["n","avg"], ascending=[False, False])
    qual = g[g["n"] >= min_n]
    pick = qual.iloc[0] if not qual.empty else g.iloc[0]
    chef = str(pick["chef_name"])
    avg = float(pick["avg"])
    n = int(pick["n"])
    mode_branch = df[df["chef_name"] == chef]["branch"].value_counts().idxmax()
    return chef, mode_branch, avg, n

# =========================
# ------ AUTH & SPLASH ----
# =========================
def splash_screen():
    st.markdown(SPLASH_CSS, unsafe_allow_html=True)
    st.markdown('<div class="splash-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="splash-title">בחרו סביבה להתחלה</div>', unsafe_allow_html=True)

    # אריח "מטה"
    if st.button("מטה", key="tile_meta"):
        st.session_state.auth = {"role": "meta", "branch": None}
        st.rerun()

    st.markdown('<div class="tile-spacer"></div>', unsafe_allow_html=True)

    # אריחי סניפים - שתי עמודות
    for i in range(0, len(BRANCHES), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(BRANCHES):
                bname = BRANCHES[i + j]
                with cols[j]:
                    if st.button(bname, key=f"tile_{bname}"):
                        st.session_state.auth = {"role": "branch", "branch": bname}
                        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

def require_auth() -> dict:
    if "auth" not in st.session_state:
        st.session_state.auth = {"role": None, "branch": None}
    if not st.session_state.auth["role"]:
        splash_screen()
    return st.session_state.auth

auth = require_auth()

# =========================
# -------- MAIN UI --------
# =========================
st.markdown(MAIN_CSS, unsafe_allow_html=True)
st.markdown('<div class="mobile-frame">', unsafe_allow_html=True)

# Header
st.markdown('<div class="header-mobile"><p class="title">איכויות מזון</p></div>', unsafe_allow_html=True)

# Status
chip = auth["branch"] if auth["role"] == "branch" else "מטה"
st.markdown(f'<div class="status-min"><span class="chip">{chip}</span></div>', unsafe_allow_html=True)

# -------- FORM --------
st.markdown('<div class="card">', unsafe_allow_html=True)
with st.form("quality_form", clear_on_submit=False):
    colA, colB, colC = st.columns([1, 1, 1])

    if auth["role"] == "meta":
        with colA:
            selected_branch = st.selectbox("שם סניף *", options=BRANCHES, index=0)
    else:
        selected_branch = auth["branch"]
        with colA:
            st.text_input("שם סניף", value=selected_branch, disabled=True)

    with colB:
        chef = st.text_input("שם הטבח *", value="")  # ללא placeholder

    with colC:
        dish = st.selectbox("שם המנה *", options=DISHES, index=0)

    colD, colE = st.columns([1, 1])
    with colD:
        score = st.selectbox(
            "ציון איכות *",
            options=list(range(1, 11)),
            index=7,
            format_func=lambda x: f"{x} - {score_hint(x)}"
        )
    with colE:
        notes = st.text_area("הערות (לא חובה)", value="")  # ללא placeholder

    submitted = st.form_submit_button("שמור בדיקה")
st.markdown('</div>', unsafe_allow_html=True)

if submitted:
    if not selected_branch or not chef.strip() or not dish:
        st.error("חובה לבחור/להציג סניף, להזין שם טבח ולבחור מנה.")
    else:
        insert_record(selected_branch, chef, dish, score, notes, submitted_by=auth["role"])
        st.success(f"נשמר: {selected_branch} · {chef} · {dish} • ציון {score}")
        refresh_df()

# -------- KPI's --------
df = load_df()
st.markdown('<div class="card">', unsafe_allow_html=True)

def bar_compare(title: str, labels: list[str], values: list[float], colors: list[str]):
    df_chart = pd.DataFrame({"קטגוריה": labels, "ערך": values})
    ymax = max(values) * 1.25 if values and max(values) > 0 else 1
    base = alt.Chart(df_chart).encode(
        x=alt.X("קטגוריה:N", sort=labels, axis=alt.Axis(labelAngle=0, title=None)),
        y=alt.Y("ערך:Q", scale=alt.Scale(domain=(0, ymax)), axis=alt.Axis(title=None)),
    )
    bars = base.mark_bar(size=56).encode(color=alt.Color("קטגוריה:N", scale=alt.Scale(domain=labels, range=colors), legend=None))
    text = base.mark_text(dy=-8, fontWeight="bold").encode(text=alt.Text("ערך:Q", format=".2f"))
    st.markdown(f"**{title}**")
    st.altair_chart(bars + text, use_container_width=True)

if df.empty:
    st.info("אין נתונים להצגה עדיין.")
else:
    br = auth.get("branch") or BRANCHES[0]
    net_avg = network_avg(df)
    br_avg = branch_avg(df, br)
    pick_dish = df["dish_name"].iloc[0] if not df.empty else None
    net_dish_avg = dish_avg_network(df, pick_dish) if pick_dish else None
    br_dish_avg = dish_avg_branch(df, br, pick_dish) if pick_dish else None

    if net_avg is not None and br_avg is not None:
        bar_compare(f"ממוצע ציון — רשת מול {br}", ["רשת", br], [net_avg, br_avg], [COLOR_NET, COLOR_BRANCH])

    st.markdown("<hr style='border:none;border-top:1px solid #e6e8ef;margin:14px 0'/>", unsafe_allow_html=True)

    if net_dish_avg is not None and br_dish_avg is not None:
        bar_compare(f"ממוצע ציון למנה — רשת מול {br}",
                    ["רשת · מנה", f"{br} · מנה"], [net_dish_avg, br_dish_avg],
                    [COLOR_NET, COLOR_BRANCH])

    st.markdown("<hr style='border:none;border-top:1px solid #e6e8ef;margin:14px 0'/>", unsafe_allow_html=True)

    chef_name, chef_branch, chef_avg, chef_n = top_chef_network_with_branch(df, MIN_CHEF_TOP_M)
    title = "הטבח המצטיין ברשת"
    if chef_name:
        title += f" — {chef_name} · {chef_branch or ''}".strip()
    st.markdown(f'<div style="font-weight:900;margin:0 0 8px;">{title}</div>', unsafe_allow_html=True)
    st.markdown('<div class="card" style="text-align:center;"><div style="font-size:42px;font-weight:900;">{}</div></div>'.format(
        "—" if chef_avg is None else f"{chef_avg:.2f}"
    ), unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)  # סוף כרטיס KPI

# =========================
# ----- GPT SECTIONS ------
# =========================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### ניתוח עם GPT")

def df_to_csv_for_llm(df_in: pd.DataFrame, max_rows: int = 400) -> str:
    d = df_in.copy()
    if len(d) > max_rows:
        d = d.head(max_rows)
    return d.to_csv(index=False)

def call_openai(system_prompt: str, user_prompt: str) -> str:
    try:
        from openai import OpenAI
        api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        org_id = st.secrets.get("OPENAI_ORG") or os.getenv("OPENAI_ORG")
        project_id = st.secrets.get("OPENAI_PROJECT") or os.getenv("OPENAI_PROJECT")
        model = st.secrets.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        if not api_key:
            return "חסר מפתח OPENAI_API_KEY (ב-Secrets/Environment)."

        client_kwargs = {"api_key": api_key}
        if org_id: client_kwargs["organization"] = org_id
        if project_id: client_kwargs["project"] = project_id

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

# כרטיס 1 – כפתור הפעלה בלבד
if not df.empty:
    if st.button("הפעל ניתוח"):
        table_csv = df_to_csv_for_llm(df)
        up = f"הנה הטבלה בפורמט CSV:\n{table_csv}\n\nסכם מגמות, חריגים והמלצות קצרות לניהול."
        with st.spinner("מנתח..."):
            ans = call_openai("system", up)
        st.write(ans)
else:
    st.info("אין נתונים לניתוח עדיין.")

st.markdown('</div>', unsafe_allow_html=True)

# כרטיס 2 – שאל את אוהד
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### שאל את אוהד")
user_q = st.text_input("שאלה על הנתונים", value="")  # ללא placeholder
if st.button("שלח"):
    if not df.empty and user_q.strip():
        table_csv = df_to_csv_for_llm(df)
        up = f"שאלה: {user_q}\n\nהנה הטבלה בפורמט CSV (עד 400 שורות):\n{table_csv}\n\nענה בעברית ותן נימוק קצר לכל מסקנה."
        with st.spinner("מנתח..."):
            ans = call_openai("system", up)
        st.write(ans)
    elif df.empty:
        st.warning("אין נתונים לניתוח כרגע.")
    else:
        st.warning("נא להזין שאלה.")
st.markdown('</div>', unsafe_allow_html=True)

# =========================
# ----- ADMIN PANEL -------
# =========================
# מוצג רק כשמחוברים כ־"מטה"
if auth["role"] == "meta":
    admin_password = st.secrets.get("ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD", "admin123")

    st.markdown("---")
    st.markdown('<div class="card">', unsafe_allow_html=True)

    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False

    # התנתקות משתמש (בחירת סניף/מצב מחדש)
    c1, c2 = st.columns([4, 1])
    with c1:
        st.caption("לחזרה למסך כניסה: התנתק משתמש.")
    with c2:
        if st.button("התנתק משתמש"):
            st.session_state.auth = {"role": None, "branch": None}
            st.rerun()

    # כניסת מנהל
    if not st.session_state.admin_logged_in:
        st.write("כניסה למנהל")
        x1, x2, x3 = st.columns([2, 1, 2])
        with x2:
            pwd = st.text_input("סיסמת מנהל:", type="password", key="admin_password")
            if st.button("התחבר", use_container_width=True):
                if pwd == admin_password:
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.error("סיסמה שגויה")
    else:
        y1, y2 = st.columns([4, 1])
        with y1:
            st.success("מחובר כמנהל")
        with y2:
            if st.button("התנתק מנהל"):
                st.session_state.admin_logged_in = False
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # אזור מנהל — ייצוא ובדיקות
    if st.session_state.get("admin_logged_in", False):
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.write("ייצוא ומידע")

        df_all = load_df()
        csv_bytes = df_all.to_csv(index=False).encode("utf-8")
        st.download_button("הורדת CSV", data=csv_bytes, file_name="food_quality_export.csv", mime="text/csv")

        debug_info = []
        try:
            sheet_id = _get_sheet_id()
            creds_present = bool(_get_service_account_info())
            debug_info.append(f"gspread זמין: {GSHEETS_AVAILABLE}")
            debug_info.append(f"Service Account מוגדר: {creds_present}")
            debug_info.append(f"GOOGLE_SHEET_ID קיים: {bool(sheet_id)}")
            if creds_present:
                try:
                    creds = _get_service_account_info() or {}
                    debug_info.append(f"client_email: {creds.get('client_email','חסר')}")
                except Exception as e:
                    debug_info.append(f"שגיאה בקריאת JSON: {e}")
            sheets_ok = bool(GSHEETS_AVAILABLE and creds_present and sheet_id)
        except Exception as e:
            debug_info.append(f"שגיאת קונפיג: {e}")
            sheets_ok = False

        if sheets_ok:
            st.success("Google Sheets מחובר")
            st.markdown(f'https://docs.google.com/spreadsheets/d/{sheet_id}', unsafe_allow_html=True)
        else:
            st.error("Google Sheets לא מוגדר")

        with st.expander("מידע טכני"):
            for info in debug_info:
                st.text(info)
            with st.expander("הוראות הגדרה"):
                st.markdown("""
                1) צור/פתח Google Sheet  
                2) צור Service Account ב-Google Cloud והורד JSON  
                3) הוסף ל-Secrets/Environment:  
                   - GOOGLE_SHEET_ID=...  
                   - GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'  
                4) שתף את הגיליון עם ה-client_email בהרשאת Editor
                """)
        st.markdown('</div>', unsafe_allow_html=True)

# סיום מעטפת הדף
st.markdown('</div>', unsafe_allow_html=True)
