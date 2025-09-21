# app.py — ג'ירף – איכויות מזון (דף פתיחה עם קוביות, מנה יומית, KPI, טופס ושאלות GPT)
from __future__ import annotations
import os, json, sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

import pandas as pd
import streamlit as st
import altair as alt

# ==== Google Sheets (אופציונלי) ====
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSHEETS_AVAILABLE = True
except Exception:
    GSHEETS_AVAILABLE = False

# ========= SETTINGS =========
st.set_page_config(page_title="ג'ירף – איכויות מזון", layout="wide")

BRANCHES: List[str] = [
    "חיפה", "ראשל״צ", "רמה״ח", "נס ציונה", "לנדמרק",
    "פתח תקווה", "הרצליה", "סביון"
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
    "לנדמרק": ["יו", "מא", "וואנג הואנבין", "וואנג ג'ינלאי", "ג'או", "אוליבר",
               "זאנג", "בי", "יאנג זימינג", "יאנג רונגשטן", "דונג", "וואנג פוקוואן"],
    # אליאס היסטורי
    "רמהח": ["ין", "סי", "ליו", "הואן", "פרנק", "זאנג", "זאו לי"],
}

DB_PATH = "food_quality.db"
MIN_CHEF_WEEK_M = 2
MIN_DISH_WEEK_M = 2

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

# ========= STYLE =========
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;600;800;900&display=swap');

:root{
  --ink:#111;
  --muted:#6b7280;
  --line:#dfe5ea;
  --bg:#fff;
  --amber:#FFF7C4;        /* צהוב בהיר לכותרת */
  --mint:#DDFBEA;         /* ירוק בהיר רקע */
  --mint-strong:#10b981;  /* ירוק קו */
}

html, body, .main, .block-container{direction:rtl;background:var(--bg);}
.main .block-container{font-family:"Rubik",system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}

/* פס מסגרת שחור כללי */
body { border: 2px solid #000; margin: 10px; }

/* כותרת צהבהבה במסגרת שחורה דקה */
.hero {
  background: var(--amber);
  border: 1px solid #000;
  padding: 14px 18px;
  margin: 8px 0 14px;
  text-align: center;
  border-radius: 4px;
  font-weight: 900;
  font-size: 28px;
  color: var(--ink);
}

/* קופסת מנה יומית לבדיקה */
.daily-pick {
  border: 2px solid var(--mint-strong);
  padding: 12px 16px;
  margin: 8px 0 18px;
  text-align: center;
  border-radius: 0;
}
.daily-pick .t1{font-weight:900;color:#065f46;margin-bottom:4px}
.daily-pick .dish{font-weight:900;font-size:18px}
.daily-pick .avg{color:#059669;font-weight:800}

/* רשת קוביות 3×3 */
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
@media (max-width: 480px){
  .grid{ grid-template-columns: repeat(3, 1fr); } /* גם במובייל 3 עמודות */
}
.branch-btn{
  display:block;
  width:100%;
  text-align:center;
  background: var(--mint);
  border: 2px solid #000;
  color: #000;             /* טקסט שחור */
  text-decoration:none !important;
  padding: 16px 10px;
  border-radius: 10px;
  font-weight: 800;
  cursor: pointer;
}
.branch-btn:hover{ filter:brightness(0.97); }

/* כרטיס */
.card{border:1px solid var(--line);border-radius:14px;padding:14px;margin:8px 0;}

/* שדות */
.stTextInput input, .stTextArea textarea{
  background:#fff !important; color:var(--ink) !important;
  border:1px solid var(--line) !important; border-radius:12px !important;
}
.stSelectbox div[data-baseweb="select"]{
  background:#fff !important; color:var(--ink) !important;
  border:1px solid var(--line) !important; border-radius:12px !important;
}
/* לפתוח את ה-select כלפי מטה */
.stSelectbox {overflow:visible !important;}
div[data-baseweb="select"] + div[role="listbox"]{
  top: calc(100% + 8px) !important; bottom:auto !important; max-height:50vh !important;
}

/* טבלת KPI */
.num { color:#10b981; font-weight:800; }
.small { color:var(--muted); font-size:12px; }
</style>
""", unsafe_allow_html=True)

# ========= DB =========
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
with conn() as c:
    c.execute(SCHEMA)

# ========= Helpers =========
@st.cache_data(ttl=20)
def load_df() -> pd.DataFrame:
    with conn() as c:
        df = pd.read_sql_query(
            "SELECT id, branch, chef_name, dish_name, score, notes, created_at "
            "FROM food_quality ORDER BY created_at DESC", c)
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    return df

def refresh_df():
    load_df.clear()

def score_hint(x:int)->str:
    return "חלש" if x<=3 else ("סביר" if x<=6 else ("טוב" if x<=8 else "מצוין"))

def last7(df:pd.DataFrame)->pd.DataFrame:
    if df.empty: return df
    start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)
    return df[df["created_at"] >= start].copy()

def worst_network_dish_last7(df:pd.DataFrame, min_n:int=MIN_DISH_WEEK_M
                             )->Tuple[Optional[str], Optional[float], int]:
    d = last7(df)
    if d.empty: return None, None, 0
    g = d.groupby("dish_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
    g = g[g["n"] >= min_n]
    if g.empty: return None, None, 0
    row = g.loc[g["avg"].idxmin()]
    return str(row["dish_name"]), float(row["avg"]), int(row["n"])

def branch_chefs(branch: Optional[str]) -> List[str]:
    if not branch: return []
    # אליאס
    if branch == "רמהח":
        branch = "רמה״ח"
    return CHEFS_BY_BRANCH.get(branch, [])

def save_row(branch:str, chef:str, dish:str, score:int, notes:str, who:str):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with conn() as c:
        c.execute(
            "INSERT INTO food_quality (branch, chef_name, dish_name, score, notes, created_at, submitted_by) "
            "VALUES (?,?,?,?,?,?,?)",
            (branch.strip(), chef.strip(), dish.strip(), int(score), (notes or "").strip(), ts, who)
        )
    # Google Sheets (אופציונלי)
    try:
        if GSHEETS_AVAILABLE:
            sheet_id = st.secrets.get("GOOGLE_SHEET_ID") or os.getenv("GOOGLE_SHEET_ID")
            svc = (st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON") or
                   os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
            if sheet_id and svc:
                info = json.loads(svc) if isinstance(svc, str) else svc
                creds = Credentials.from_service_account_info(info, scopes=SCOPES)
                gspread.authorize(creds).open_by_key(sheet_id).sheet1.append_row(
                    [ts, branch, chef, dish, score, notes or ""]
                )
    except Exception:
        pass

# ==== Weekly (rolling 7d) per branch ====
def weekly_branch_params(df:pd.DataFrame, branch:str,
                         min_chef:int=MIN_CHEF_WEEK_M,
                         min_dish:int=MIN_DISH_WEEK_M) -> Dict[str,Any]:
    d = last7(df)
    d = d[d["branch"] == branch]
    if d.empty:
        return {"avg":None, "best_chef":(None,None), "worst_chef_avg":None,
                "best_dish":None, "worst_dish":None}

    avg = float(d["score"].mean())

    g_chef = d.groupby("chef_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
    g_chef = g_chef[g_chef["n"]>=min_chef]
    if not g_chef.empty:
        r_best = g_chef.loc[g_chef["avg"].idxmax()]
        r_worst = g_chef.loc[g_chef["avg"].idxmin()]
        best_chef = (str(r_best["chef_name"]), float(r_best["avg"]))
        worst_avg = float(r_worst["avg"])
    else:
        best_chef, worst_avg = (None,None), None

    g_dish = d.groupby("dish_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
    g_dish = g_dish[g_dish["n"]>=min_dish]
    best_dish = worst_dish = None
    if not g_dish.empty:
        rb = g_dish.loc[g_dish["avg"].idxmax()]
        rw = g_dish.loc[g_dish["avg"].idxmin()]
        if str(rb["dish_name"]) != str(rw["dish_name"]):
            best_dish  = str(rb["dish_name"])
            worst_dish = str(rw["dish_name"])
        else:
            best_dish  = str(rb["dish_name"])
            worst_dish = None

    return {"avg":avg, "best_chef":best_chef, "worst_chef_avg":worst_avg,
            "best_dish":best_dish, "worst_dish":worst_dish}

# ========= AUTH / ENTRY =========
def landing():
    st.markdown('<div class="hero">ג׳ירף – איכויות מזון</div>', unsafe_allow_html=True)

    # מנה יומית לבדיקה
    df_login = load_df()
    name, avg, n = worst_network_dish_last7(df_login, MIN_DISH_WEEK_M)
    st.markdown('<div class="daily-pick">', unsafe_allow_html=True)
    st.markdown('<div class="t1">מנה יומית לבדיקה</div>', unsafe_allow_html=True)
    if name:
        st.markdown(f'<div class="dish">{name}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="avg">ממוצע רשת (7 ימים): <span class="num">{avg:.2f}</span> · N={n}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="dish">—</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # כפתורי סניפים + מטה (3×3)
    st.markdown('<div class="grid">', unsafe_allow_html=True)
    buttons = BRANCHES + ["מטה"]
    cols = st.columns(3, gap="small")
    for i, name in enumerate(buttons):
        with cols[i%3]:
            if st.button(name, key=f"pick_{name}", use_container_width=True):
                if name == "מטה":
                    st.session_state.auth = {"role":"meta", "branch":None}
                else:
                    st.session_state.auth = {"role":"branch", "branch":name}
                st.experimental_rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def require_auth()->dict:
    if "auth" not in st.session_state:
        st.session_state.auth = {"role":None, "branch":None}
    auth = st.session_state.auth
    if not auth["role"]:
        landing()
        st.stop()
    return auth

auth = require_auth()

# ========= HEADER AFTER LOGIN =========
header_title = "מטה" if auth["role"]=="meta" else auth["branch"]
st.markdown(f'<div class="hero">{header_title} — ג׳ירף איכויות מזון</div>', unsafe_allow_html=True)

df = load_df()

# ========= ENTRY FORM =========
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("#### הזנת בדיקה")
with st.form("quality_form", clear_on_submit=False):
    c1, c2, c3 = st.columns([1,1,1])

    # סניף להזנה
    if auth["role"]=="meta":
        with c1:
            branch_opt = ["— בחר —"] + BRANCHES
            selected_branch = st.selectbox("בחר/י סניף להזנה *", options=branch_opt, index=0)
    else:
        selected_branch = auth["branch"]
        with c1:
            st.text_input("סניף", value=selected_branch, disabled=True)

    # שם טבח – קודם גלילה לפי הסניף
    with c2:
        base_chefs = branch_chefs(selected_branch if selected_branch not in (None,"— בחר —") else None)
        chef_choice = st.selectbox("שם הטבח מהרשימה", options=base_chefs if base_chefs else ["—"], index=0 if base_chefs else 0)
    # שדה הקלדה ידנית – תמיד קיים למקרה שאין/רוצים חדש
    with c3:
        chef_manual = st.text_input("שם הטבח — הקלדה ידנית (לא חובה)", value="")

    c4, c5 = st.columns([1,1])
    with c4:
        dish = st.selectbox("שם המנה *", options=["— בחר —"]+DISHES, index=0)
    with c5:
        score_choice = st.selectbox(
            "ציון איכות *", options=["— בחר —"]+list(range(1,11)), index=0,
            format_func=lambda x: f"{x} - {score_hint(x)}" if isinstance(x,int) else x
        )

    notes = st.text_area("הערות (לא חובה)", value="")
    submitted = st.form_submit_button("שמור בדיקה")

st.markdown('</div>', unsafe_allow_html=True)

if submitted:
    if auth["role"]=="meta" and (not selected_branch or selected_branch=="— בחר —"):
        st.error("נא לבחור סניף להזנה.")
    elif dish=="— בחר —":
        st.error("נא לבחור שם מנה.")
    elif not isinstance(score_choice,int):
        st.error("נא לבחור ציון.")
    else:
        # בחירת שם טבח: ידני גובר על גלילה אם מולא
        chef_final = chef_manual.strip() if chef_manual.strip() else chef_choice
        if not chef_final or chef_final=="—":
            st.error("נא לבחור/להקליד שם טבח.")
        else:
            save_row(selected_branch, chef_final, dish, int(score_choice), notes, who=auth["role"])
            refresh_df()
            st.success("נשמר בהצלחה.")

# ========= KPI (META) =========
def network_kpi_ui(df:pd.DataFrame):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### KPI רשת – 7 ימים אחרונים")

    d7 = last7(df)
    if d7.empty:
        st.info("אין נתונים בשבעת הימים האחרונים.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # גרף ממוצע ציון לפי סניף (תוויות מאוזנות + צבעים פסטליים)
    g = d7.groupby("branch")["score"].mean().reset_index().rename(columns={"score":"avg"})
    g = g.sort_values("avg", ascending=False)
    palette = ["#cfe8ff","#d7fde7","#fde2f3","#fff3bf","#e5e1ff","#c9faf3","#ffdede","#eaf7e5"]
    x_axis = alt.Axis(labelAngle=0, labelPadding=6, labelColor='#111', title=None)
    chart = (alt.Chart(g)
             .mark_bar(size=36)
             .encode(
                 x=alt.X("branch:N", sort='-y', axis=x_axis),
                 y=alt.Y("avg:Q", scale=alt.Scale(domain=(0,10)), title=None),
                 color=alt.Color("branch:N", legend=None, scale=alt.Scale(range=palette)),
                 tooltip=[alt.Tooltip("branch:N", title="סניף"),
                          alt.Tooltip("avg:Q", title="ממוצע", format=".2f")]
             ).properties(height=260).configure_view(strokeWidth=0))
    st.altair_chart(chart, use_container_width=True)

    # טבח מוביל + מנה גבוהה/נמוכה
    gchef = d7.groupby("chef_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
    gchef = gchef[gchef["n"]>=MIN_CHEF_WEEK_M]
    top_line = "—"
    if not gchef.empty:
        r = gchef.loc[gchef["avg"].idxmax()]
        chef = str(r["chef_name"]); avg = float(r["avg"])
        try:
            b = d7[d7["chef_name"]==chef]["branch"].mode().iat[0]
        except Exception:
            b = ""
        top_line = f"{chef} · {b} · <span class='num'>{avg:.2f}</span>"

    gdish = d7.groupby("dish_name").agg(n=("id","count"), avg=("score","mean")).reset_index()
    gdish = gdish[gdish["n"]>=MIN_DISH_WEEK_M]
    best_line = worst_line = "—"
    if not gdish.empty:
        rb = gdish.loc[gdish["avg"].idxmax()]
        rw = gdish.loc[gdish["avg"].idxmin()]
        if str(rb["dish_name"]) != str(rw["dish_name"]):
            best_line  = f"{rb['dish_name']} · <span class='num'>{rb['avg']:.2f}</span> (N={int(rb['n'])})"
            worst_line = f"{rw['dish_name']} · <span class='num'>{rw['avg']:.2f}</span> (N={int(rw['n'])})"
        else:
            best_line  = f"{rb['dish_name']} · <span class='num'>{rb['avg']:.2f}</span> (N={int(rb['n'])})"

    st.markdown(f"- **ממוצע טבח מוביל:** {top_line}", unsafe_allow_html=True)
    st.markdown(f"- **ממוצע מנה הכי גבוה:** {best_line}", unsafe_allow_html=True)
    if worst_line != "—":
        st.markdown(f"- **ממוצע מנה הכי נמוך:** {worst_line}", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ========= WEEKLY SUMMARY (rolling 7d) =========
def weekly_ui(df:pd.DataFrame, branch:str):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"#### סיכום שבועי (7 ימים אחרונים) — {branch}")
    m = weekly_branch_params(df, branch)
    def num(x): return "—" if x is None else f"<span class='num'>{x:.2f}</span>"
    best_chef = "—" if m["best_chef"][0] is None else f"{m['best_chef'][0]} · {num(m['best_chef'][1])}"
    st.markdown(f"""
    - **ממוצע כלל הסניף:** {num(m['avg'])}  
    - **טבח מוביל:** {best_chef}  
    - **טבח חלש (ממוצע):** {num(m['worst_chef_avg'])}  
    - **מנה טובה:** {m['best_dish'] or '—'}  
    - **מנה לשיפור:** {m['worst_dish'] or '—'}
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ========= GPT =========
def df_to_csv_for_llm(df_in:pd.DataFrame, max_rows:int=400)->str:
    d = df_in.copy()
    if len(d) > max_rows:
        d = d.head(max_rows)
    return d.to_csv(index=False)

def call_openai(system_prompt:str, user_prompt:str)->str:
    try:
        from openai import OpenAI
        api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "חסר OPENAI_API_KEY."
        client = OpenAI(api_key=api_key)
        model = st.secrets.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system_prompt},
                      {"role":"user","content":user_prompt}],
            temperature=0.2
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"שגיאה בקריאה ל-OpenAI: {e}"

# ========= PAGE CONTENT =========
if auth["role"] == "meta":
    network_kpi_ui(df)
    # סיכומים שבועיים לכל סניף – מתחת ל-KPI
    for b in BRANCHES:
        weekly_ui(df, b)
else:
    # סיכום שבועי רק לסניף הנוכחי
    weekly_ui(df, auth["branch"])

# GPT – ניתוח
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("#### ניתוח עם GPT")
if auth["role"] == "meta":
    data_for_llm = df
    scope_note = "כל הסניפים"
else:
    data_for_llm = df[df["branch"] == auth["branch"]].copy()
    scope_note = f"סניף {auth['branch']}"
if data_for_llm.empty:
    st.info("אין נתונים לניתוח כרגע.")
else:
    if st.button("הפעל ניתוח"):
        csv = df_to_csv_for_llm(data_for_llm)
        up = f"הטווח: {scope_note}. להלן נתוני הבדיקות (CSV):\n{csv}\n\nסכם מגמות, חריגים והמלצות קצרות."
        with st.spinner("מנתח..."):
            ans = call_openai("אתה אנליסט דאטה דובר עברית.", up)
        st.write(ans)
st.markdown('</div>', unsafe_allow_html=True)

# GPT – שאל את אוהד
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("#### שאל את אוהד")
q = st.text_input("שאלה על הנתונים", value="")
if st.button("שלח שאלה"):
    if data_for_llm.empty or not q.strip():
        st.warning("אין נתונים או שאין שאלה.")
    else:
        csv = df_to_csv_for_llm(data_for_llm)
        up = f"שאלה: {q}\n\nהטווח: {scope_note}\n\nCSV נתונים:\n{csv}\n\nענה בעברית, תמציתי, עם בולטים."
        with st.spinner("מחשב תשובה..."):
            ans = call_openai("אתה אנליסט דובר עברית.", up)
        st.write(ans)
st.markdown('</div>', unsafe_allow_html=True)
