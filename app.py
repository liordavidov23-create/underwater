"""מסך התכנון הראשי (SPEC סעיף 7). כל החישובים נעשים ב-nav_engine."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from nav_engine import (
    REFERENCE_LAYOUTS,
    Buoy,
    ErrorParams,
    Scenario,
    User,
    WorkArea,
    coverage,
    cycle_time_s,
    default_users,
    reference_buoys,
    solve,
    update_rate_hz,
)
from ui import theme
from ui.plots import planning_map

st.set_page_config(page_title="תכנון רשת מצופים", page_icon="🛟", layout="wide")
st.markdown(theme.CSS, unsafe_allow_html=True)

AREA = WorkArea()
STRIP_X_MAX = 65.0
WORLD_W, WORLD_H = 280.0, 240.0

LAYOUT_LABELS = {
    "west": "west: ארבעה מצופים ממערב",
    "around": "around: מצופים מסביב לשטח",
    "chal": "chal: שלושה מצופים ממערב",
    "solve": "solve: חמישה מצופים על קו הרצועה",
}
KIND_FROM_LABEL = {v: k for k, v in theme.KIND_LABELS.items()}

WIDGET_DEFAULTS = {
    "mode": "sync",
    "sigma_range": 0.30,
    "sound_pct": 0.20,
    "sigma_gnss": 0.50,
    "clock_us": 200,
    "depth": 15.0,
    "transducer_depth": 2.0,
    "mag": 12,
    "show_heat": True,
    "show_contour": True,
    "layout_choice": "west",
}

ss = st.session_state


# ---------- המרות בין טבלאות למודל ----------

def buoys_to_df(buoys: list[Buoy]) -> pd.DataFrame:
    return pd.DataFrame({"x": [float(b.x) for b in buoys], "y": [float(b.y) for b in buoys]})


def users_to_df(users: list[User]) -> pd.DataFrame:
    return pd.DataFrame({
        "id": [u.id for u in users],
        "kind": [theme.KIND_LABELS.get(u.kind, theme.KIND_LABELS["diver"]) for u in users],
        "x": [float(u.x) for u in users],
        "y": [float(u.y) for u in users],
    })


def df_to_buoys(df: pd.DataFrame) -> list[Buoy]:
    df = df.dropna(subset=["x", "y"])
    return [Buoy(x=float(r.x), y=float(r.y), name=f"B{i + 1}")
            for i, r in enumerate(df.itertuples(index=False))]


def df_to_users(df: pd.DataFrame) -> list[User]:
    df = df.dropna(subset=["x", "y"])
    users, seen = [], set()
    for i, r in enumerate(df.itertuples(index=False)):
        uid = str(r.id).strip() if isinstance(r.id, str) and r.id.strip() else f"U{i + 1}"
        base, n = uid, 2
        while uid in seen:  # שמות כפולים מקבלים סיומת
            uid, n = f"{base}-{n}", n + 1
        seen.add(uid)
        kind = KIND_FROM_LABEL.get(r.kind, "diver")
        users.append(User(id=uid, kind=kind, x=float(r.x), y=float(r.y)))
    return users


def params_from_widgets() -> ErrorParams:
    return ErrorParams(
        sigma_range=float(ss.sigma_range),
        sound_speed_frac=float(ss.sound_pct) / 100.0,
        sigma_gnss=float(ss.sigma_gnss),
        sigma_clock=float(ss.clock_us) * 1e-6,
        user_depth=float(ss.depth),
        transducer_depth=float(ss.transducer_depth),
        mode=ss.mode,
    )


def apply_scenario(sc: Scenario) -> None:
    p = sc.params
    ss.mode = p.mode
    ss.sigma_range = float(p.sigma_range)
    ss.sound_pct = float(p.sound_speed_frac) * 100.0
    ss.sigma_gnss = float(p.sigma_gnss)
    ss.clock_us = int(round(p.sigma_clock * 1e6))
    ss.depth = float(p.user_depth)
    ss.transducer_depth = float(p.transducer_depth)
    ss.buoys_df = buoys_to_df(sc.buoys)
    ss.users_df = users_to_df(sc.users)
    ss.editor_ver += 1


def load_layout() -> None:
    ss.buoys_df = buoys_to_df(reference_buoys(ss.layout_choice))
    ss.editor_ver += 1


def reset_users() -> None:
    ss.users_df = users_to_df(default_users())
    ss.editor_ver += 1


# ---------- מצב התחלתי ----------

for k, v in WIDGET_DEFAULTS.items():
    ss.setdefault(k, v)
if "buoys_df" not in ss:
    ss.buoys_df = buoys_to_df(reference_buoys("west"))
    ss.users_df = users_to_df(default_users())
    ss.editor_ver = 0

# העלאת תרחיש מטופלת לפני שהווידג'טים נוצרים, כדי שיקבלו את הערכים החדשים
_up = ss.get("upload")
if _up is not None and ss.get("upload_done") != _up.file_id:
    ss.upload_done = _up.file_id
    try:
        apply_scenario(Scenario.from_dict(json.loads(_up.getvalue().decode("utf-8"))))
        ss.upload_msg = ("ok", f"התרחיש \"{_up.name}\" נטען.")
    except Exception as exc:  # קובץ לא תקין לא מפיל את האפליקציה
        ss.upload_msg = ("err", f"לא הצלחתי לקרוא את הקובץ: {exc}")


# ---------- סרגל צד ----------

with st.sidebar:
    st.header("הגדרות")
    st.radio("שיטת מדידה", list(theme.MODE_LABELS), key="mode",
             format_func=theme.MODE_LABELS.get)

    st.subheader("מקורות שגיאה")
    st.slider("שגיאת מדידת טווח (מ')", 0.0, 2.0, step=0.05, key="sigma_range")
    st.slider("שגיאת מהירות הקול (%)", 0.0, 1.0, step=0.05, key="sound_pct")
    st.slider("שגיאת GNSS של המצוף (מ')", 0.0, 2.0, step=0.01, key="sigma_gnss")
    st.slider("שגיאת שעון (מיקרו-שניות)", 0, 1000, step=10, key="clock_us",
              help="משפיע רק במצב פסיבי מסונכרן. 200 מיקרו-שניות הן כ-0.3 מ' בטווח.")
    st.caption("ערכי ברירת המחדל הם הנחות טיפוסיות, לא נתוני יצרן.")

    st.subheader("עומק")
    st.slider("עומק המשתמשים (מ')", 3.0, 60.0, step=1.0, key="depth")
    st.slider("עומק המתמר במצוף (מ')", 0.5, 10.0, step=0.5, key="transducer_depth")

    st.subheader("פריסת ייחוס")
    st.selectbox("פריסה", list(REFERENCE_LAYOUTS), key="layout_choice",
                 format_func=lambda k: LAYOUT_LABELS.get(k, k))
    st.button("טען פריסה", on_click=load_layout, use_container_width=True)
    st.button("החזר משתמשים למיקום ההתחלתי", on_click=reset_users, use_container_width=True)

    st.subheader("תצוגה")
    st.slider("הגדלת האליפסות (פי)", 1, 40, key="mag")
    st.checkbox("מפת שגיאה בצבעים", key="show_heat")
    st.checkbox("קו גבול של מטר", key="show_contour")


# ---------- חישוב ----------

params = params_from_widgets()


def render_planning() -> None:
    col_edit, col_map = st.columns([1.2, 2.3], gap="medium")

    with col_edit:
        st.subheader("מצופים")
        bdf = st.data_editor(
            ss.buoys_df, key=f"buoys_editor_{ss.editor_ver}", num_rows="dynamic",
            hide_index=True, use_container_width=True,
            column_config={
                "x": st.column_config.NumberColumn("x מזרח (מ')", step=1.0, format="%.1f"),
                "y": st.column_config.NumberColumn("y צפון (מ')", step=1.0, format="%.1f"),
            },
        )
        buoys = df_to_buoys(bdf)
        outside = [b.name for b in buoys if b.x > STRIP_X_MAX]
        if outside:
            st.warning(f"מחוץ לרצועה המותרת (x גדול מ-{STRIP_X_MAX:g} מ'): {', '.join(outside)}. "
                       "החישוב ממשיך כרגיל.")
        st.caption("סדר השורות קובע את המספור B1, B2 וכן הלאה. להוספה: השורה הריקה בתחתית. "
                   "למחיקה: סמן שורה ולחץ על סמל הפח.")

        st.subheader("משתמשים")
        udf = st.data_editor(
            ss.users_df, key=f"users_editor_{ss.editor_ver}", num_rows="dynamic",
            hide_index=True, use_container_width=True,
            column_config={
                "id": st.column_config.TextColumn("שם"),
                "kind": st.column_config.SelectboxColumn(
                    "סוג", options=list(theme.KIND_LABELS.values()),
                    default=theme.KIND_LABELS["diver"]),
                "x": st.column_config.NumberColumn("x (מ')", step=1.0, format="%.1f"),
                "y": st.column_config.NumberColumn("y (מ')", step=1.0, format="%.1f"),
            },
        )
        users = df_to_users(udf)

    solutions = {u.id: solve(u.x, u.y, buoys, params) for u in users}
    worst = max(users, key=lambda u: solutions[u.id].rms if solutions[u.id] else float("inf"),
                default=None)
    cov = coverage(buoys, params, AREA)
    rate = update_rate_hz(buoys, users, params)
    cycle = cycle_time_s(buoys, users, params)

    with col_map:
        render_metrics(users, solutions, worst, cov, rate, cycle)
        fig = planning_map(buoys, users, solutions, worst.id if worst else None, params, AREA,
                           STRIP_X_MAX, WORLD_W, WORLD_H, mag=ss.mag,
                           show_heat=ss.show_heat, show_contour=ss.show_contour)
        st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
        st.caption(f"שיטה: {theme.MODE_LABELS[params.mode]}. אליפסות 95% מוגדלות פי {ss.mag}. "
                   "אזור כהה: אין פתרון. כל הערכים במפה: הערכה ממודל.")
        render_user_table(users, solutions)

    st.divider()
    render_scenario_io(buoys, users)


def card(label: str, value: str, sub: str = "", color: str = theme.TEXT, extra: str = "") -> str:
    return (f'<div class="metric-card"><div class="lbl">{label}</div>'
            f'<div class="val" style="color:{color}">{value}</div>'
            f'<div class="sub">{sub}</div>{extra}'
            f'<div class="note">{theme.MODEL_NOTE}</div></div>')


def render_metrics(users, solutions, worst, cov, rate, cycle) -> None:
    c1, c2, c3, c4 = st.columns(4)
    if not users:
        worst_html = card("המשתמש הגרוע", "אין", "אין משתמשים בטבלה")
        hdop_html = card("HDOP", "אין")
    elif solutions[worst.id] is None:
        chip = '<span class="chip bad">אין פתרון</span>'
        worst_html = card("שגיאה אופקית (1σ) של המשתמש הגרוע", "∞",
                          f"{worst.id}: אין מספיק מצופים או שהגאומטריה לא פתירה",
                          theme.WARNING, chip)
        hdop_html = card("HDOP", "∞", f"במיקום של {worst.id}", theme.WARNING)
    else:
        s = solutions[worst.id]
        ok = s.rms < 1.0
        chip = (f'<span class="chip {"good" if ok else "bad"}">'
                f'{"כולם מתחת למטר" if ok else "לא כולם מתחת למטר"}</span>')
        val = ">99" if s.rms > 99 else f"{s.rms:.2f} מ'"
        worst_html = card("שגיאה אופקית (1σ) של המשתמש הגרוע", val,
                          f"{worst.id}, הגרוע מבין {len(users)}", theme.error_color(s.rms), chip)
        hdop = "∞" if s.hdop == float("inf") else f"{s.hdop:.2f}"
        hdop_html = card("HDOP", hdop, f"במיקום של {worst.id}")
    c1.markdown(worst_html, unsafe_allow_html=True)
    c2.markdown(card("כיסוי שטח העבודה", f"{cov:.1f}%", "מהשטח עם שגיאה מתחת למטר",
                     theme.ACCENT), unsafe_allow_html=True)
    rate_sub = f"מחזור מדידה של {cycle:.2f} שניות" if cycle else "אין מצופים או משתמשים"
    c3.markdown(card("קצב עדכון למשתמש", f"{rate:.2f} Hz" if rate else "אין", rate_sub),
                unsafe_allow_html=True)
    c4.markdown(hdop_html, unsafe_allow_html=True)


def render_user_table(users, solutions) -> None:
    rows = []
    for u in users:
        s = solutions[u.id]
        if s is None:
            rows.append({"משתמש": u.id, "סוג": theme.KIND_LABELS.get(u.kind, u.kind),
                         "שגיאה 1σ (מ')": None, "ציר ארוך 95% (מ')": None,
                         "ציר קצר 95% (מ')": None, "HDOP": None, "מצב": "אין פתרון"})
            continue
        e = s.ellipse
        rows.append({"משתמש": u.id, "סוג": theme.KIND_LABELS.get(u.kind, u.kind),
                     "שגיאה 1σ (מ')": round(s.rms, 3),
                     "ציר ארוך 95% (מ')": round(e.semi_major, 2),
                     "ציר קצר 95% (מ')": round(e.semi_minor, 2),
                     "HDOP": round(s.hdop, 2) if s.hdop != float("inf") else None,
                     "מצב": "עומד ביעד" if s.rms < 1 else "לא עומד ביעד"})
    if rows:
        st.markdown("**שגיאה לכל משתמש** (הערכה ממודל)")
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_scenario_io(buoys, users) -> None:
    st.subheader("שמירה וטעינה של תרחיש")
    sc = Scenario(buoys=buoys, users=users, params=params, area=AREA,
                  strip_x_max=STRIP_X_MAX, world_w=WORLD_W, world_h=WORLD_H)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("הורדת התרחיש כקובץ JSON",
                           data=json.dumps(sc.to_dict(), ensure_ascii=False, indent=2),
                           file_name="scenario.json", mime="application/json",
                           use_container_width=True)
    with c2:
        st.file_uploader("העלאת תרחיש (JSON)", type=["json"], key="upload")
        msg = ss.get("upload_msg")
        if msg:
            (st.success if msg[0] == "ok" else st.error)(msg[1])


METHODOLOGY = """
### איך המודל עובד

**המטרה.** לכל נקודה בשטח העבודה, הכלי מעריך כמה גדולה תהיה שגיאת המיקום האופקית של צוללן או רובוט שנמצא שם.
היעד: שגיאה קטנה ממטר אחד אצל כל המשתמשים.

**מדידות טווח.** כל מצוף יודע את מיקומו בעזרת GNSS ומשדר אות אקוסטי. המשתמש מודד את המרחק לכל מצוף לפי זמן ההגעה של האות.
לכל מדידה יש שגיאה, שמורכבת מארבעה חלקים:

- שגיאת המדידה עצמה (סליידר "שגיאת מדידת טווח").
- שגיאה במהירות הקול, שגדלה ככל שהמצוף רחוק יותר.
- שגיאת ה-GNSS של המצוף.
- שגיאת השעון, רק בשיטה הפסיבית המסונכרנת.

**שלוש שיטות.**

- **פסיבי מסונכרן:** המשתמש רק מקשיב, והשעונים מסונכרנים. מספיקים שני מצופים.
- **פסיבי ללא סנכרון:** המשתמש רק מקשיב, אבל לא יודע את הפער בין השעונים, ולכן צריך לנחש גם אותו. נדרשים לפחות שלושה מצופים, והדיוק יורד.
- **דו-כיווני:** המשתמש משדר ומקבל תשובה. אין צורך בשעון מסונכרן, אבל כל משתמש תופס זמן שידור, ולכן הקצב יורד ככל שיש יותר משתמשים.

**גאומטריה.** כשהמצופים "נראים" מכיוונים שונים, השגיאות מבטלות זו את זו. כשכולם באותו צד, השגיאה גדלה בכיוון הניצב להם.
זו הסיבה שהאליפסות מתארכות מצפון לדרום כשכל המצופים ממערב. HDOP הוא מדד לאיכות הגאומטריה בלבד: ככל שהוא קטן יותר, הגאומטריה טובה יותר.

**כיסוי.** הכלי בודק נקודות כל 2 מטר בתוך שטח העבודה, ומדווח באיזה אחוז מהן השגיאה קטנה ממטר.

**קצב עדכון.** הערכה גסה: כל מצוף משדר בתורו (או כל משתמש, בשיטה הדו-כיוונית), עם הפסקה קצרה בין שידורים.

### מה המודל לא כולל

- הקול נע בקו ישר ובמהירות קבועה.
- אין הדים מהקרקעית ומפני המים.
- השגיאות נחשבות בלתי תלויות זו בזו, אף שבפועל שגיאת מהירות הקול משותפת לכל המצופים.
- עומק המשתמש ידוע במדויק.

לכן כל מספר בכלי הוא **הערכה ממודל** לצורך תכנון והשוואה בין פריסות, ולא הבטחה לדיוק בשטח.
"""


st.title("תכנון רשת מצופים לניווט תת-ימי")
tab_plan, tab_method = st.tabs(["תכנון", "מתודולוגיה"])
with tab_plan:
    render_planning()
with tab_method:
    st.markdown(METHODOLOGY)
