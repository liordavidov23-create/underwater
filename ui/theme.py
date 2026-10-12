"""שפה חזותית (SPEC סעיף 8): צבעים, סקאלת שגיאה, RTL ופונט."""

TEXT = "#0C2347"
BACKGROUND = "#E9F0FB"
ACCENT = "#1C5FD1"
WARNING = "#946A00"
BUOY = "#F5C518"
OK = "#1C5FD1"      # כחול: עומד ביעד
CARD = "#FFFFFF"
STRIP_FILL = "rgba(245, 197, 24, 0.22)"

# סקאלת מפת השגיאה במטרים. המעבר בין 0.99 ל-1.0 חד בכוונה.
ERROR_STOPS = [
    (0.0, "#0A308C"),
    (0.99, "#60ACF2"),
    (1.0, "#FFE246"),
    (2.5, "#F2B81C"),
    (5.0, "#966400"),
]
ERROR_MAX = 5.0

MODE_LABELS = {
    "sync": "פסיבי מסונכרן",
    "unsync": "פסיבי ללא סנכרון",
    "active": "דו-כיווני",
}
KIND_LABELS = {"diver": "צוללן", "robot": "רובוט"}
MODEL_NOTE = "הערכה ממודל"


def plotly_colorscale() -> list[list]:
    """סקאלת Plotly מנורמלת לטווח 0 עד ERROR_MAX."""
    return [[v / ERROR_MAX, c] for v, c in ERROR_STOPS]


def error_color(e: float | None) -> str:
    """כחול אם עומד ביעד (מתחת למטר), אחרת צבע אזהרה."""
    return OK if e is not None and e < 1.0 else WARNING


CSS = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>
html, body, .stApp, [class*="st-"], button, input, textarea, select {{
  font-family: 'Heebo', system-ui, sans-serif;
}}
.stApp, [data-testid="stSidebar"], [data-testid="stMarkdownContainer"] {{
  direction: rtl;
  text-align: right;
}}
/* גרפים, טבלאות וסליידרים נשארים משמאל לימין: מערב משמאל */
[data-testid="stPlotlyChart"], .js-plotly-plot,
[data-testid="stDataFrame"], [data-testid="stDataFrameResizable"],
[data-testid="stSlider"] > div:not([data-testid="stWidgetLabel"]) {{
  direction: ltr;
}}
[data-testid="stWidgetLabel"] {{ direction: rtl; text-align: right; }}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ font-weight: 500; }}
.metric-card {{
  background: {CARD};
  border-radius: 12px;
  padding: 12px 16px;
  border: 1px solid rgba(12, 35, 71, 0.10);
  height: 100%;
}}
.metric-card .lbl {{ font-size: 0.85rem; color: {TEXT}; opacity: 0.8; }}
.metric-card .val {{ font-size: 2rem; font-weight: 800; line-height: 1.2; direction: ltr; text-align: right; }}
.metric-card .sub {{ font-size: 0.85rem; color: {TEXT}; }}
.metric-card .note {{ font-size: 0.72rem; color: {TEXT}; opacity: 0.6; margin-top: 2px; }}
.chip {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 700; }}
.chip.good {{ background: rgba(28, 95, 209, 0.12); color: {OK}; }}
.chip.bad {{ background: rgba(148, 106, 0, 0.14); color: {WARNING}; }}
</style>
"""
