"""ציור מפת התכנון ב-Plotly: מפת שגיאה, קו מטר, שטח עבודה, מצופים, משתמשים ואליפסות."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import plotly.graph_objects as go

from nav_engine import Buoy, ErrorParams, Solution, User, WorkArea, error_map
from . import theme

NO_SOLUTION_BG = "#181C30"


def _ellipse_xy(cx: float, cy: float, sol: Solution, mag: float, n: int = 73):
    e = sol.ellipse
    t = np.linspace(0, 2 * math.pi, n)
    a, b = e.semi_major * mag, e.semi_minor * mag
    c, s = math.cos(e.angle_rad), math.sin(e.angle_rad)
    x = cx + a * np.cos(t) * c - b * np.sin(t) * s
    y = cy + a * np.cos(t) * s + b * np.sin(t) * c
    return x, y


def _contour_label_point(xs, ys, rms, users: Sequence[User], x_min: float):
    """נקודה על גבול המטר, רחוקה ככל האפשר מהמשתמשים, לתווית."""
    good = np.nan_to_num(rms, nan=np.inf) < 1.0
    edge = np.zeros_like(good)
    edge[:, 1:] |= good[:, 1:] != good[:, :-1]
    edge[1:, :] |= good[1:, :] != good[:-1, :]
    X, Y = np.meshgrid(xs, ys)
    mask = edge & (X > x_min) & (Y > ys[0] + 15) & (Y < ys[-1] - 15)
    if not mask.any():
        return None
    px, py = X[mask], Y[mask]
    if users:
        ux = np.array([u.x for u in users])
        uy = np.array([u.y for u in users])
        d = np.min(np.hypot(px[:, None] - ux, py[:, None] - uy), axis=1)
        i = int(np.argmax(d))
    else:
        i = len(px) // 2
    return float(px[i]), float(py[i])


def planning_map(
    buoys: Sequence[Buoy],
    users: Sequence[User],
    solutions: dict[str, Solution | None],
    worst_id: str | None,
    params: ErrorParams,
    area: WorkArea,
    strip_x_max: float,
    world_w: float,
    world_h: float,
    mag: float = 12.0,
    show_heat: bool = True,
    show_contour: bool = True,
) -> go.Figure:
    fig = go.Figure()
    m = error_map(0, 0, world_w, world_h, buoys, params)

    if show_heat:
        z = np.minimum(m.rms, theme.ERROR_MAX)
        fig.add_trace(go.Heatmap(
            x=m.xs, y=m.ys, z=z, customdata=m.rms,
            zmin=0, zmax=theme.ERROR_MAX, colorscale=theme.plotly_colorscale(),
            opacity=0.72, zsmooth=False,
            colorbar=dict(
                title=dict(text="שגיאה, מטר", side="top"),
                tickvals=[0, 1, 2.5, 5], ticktext=["0", "1", "2.5", "5+"],
                thickness=12, len=0.6,
            ),
            hovertemplate="x %{x:.0f}, y %{y:.0f}<br>שגיאה: %{customdata:.2f} מטר<extra></extra>",
        ))

    if show_contour:
        zc = np.nan_to_num(m.rms, nan=999.0)
        for width, color in ((4, "white"), (2, theme.TEXT)):
            fig.add_trace(go.Contour(
                x=m.xs, y=m.ys, z=zc, showscale=False, hoverinfo="skip",
                contours=dict(start=1, end=1, size=1, coloring="none"),
                line=dict(width=width, color=color), showlegend=False,
            ))
        p = _contour_label_point(m.xs, m.ys, m.rms, users, strip_x_max + 25)
        if p:
            fig.add_annotation(x=p[0], y=p[1], text="<b>גבול 1 מטר</b>", showarrow=False,
                               bgcolor="white", bordercolor=theme.TEXT, borderwidth=1.5,
                               borderpad=3, font=dict(color=theme.TEXT, size=12))

    # רצועת הפריסה המותרת
    fig.add_shape(type="rect", x0=0, x1=strip_x_max, y0=0, y1=world_h, layer="below",
                  fillcolor=theme.STRIP_FILL, line=dict(width=0))
    fig.add_shape(type="line", x0=strip_x_max, x1=strip_x_max, y0=0, y1=world_h,
                  line=dict(color=theme.BUOY, width=2))
    fig.add_annotation(x=strip_x_max / 2, y=world_h / 2, text="<b>אזור מותר למצופים</b>",
                       textangle=-90, showarrow=False, font=dict(color=theme.TEXT, size=12))

    # שטח העבודה
    fig.add_shape(type="rect", x0=area.x0, x1=area.x1, y0=area.y0, y1=area.y1,
                  line=dict(color=theme.TEXT, width=1.5, dash="dash"))
    w, h = area.x1 - area.x0, area.y1 - area.y0
    fig.add_annotation(x=area.x1 - 4, y=area.y1 - 4, xanchor="right", yanchor="top",
                       text=f"<b>שטח העבודה {w:g}×{h:g} מטר</b>", showarrow=False,
                       font=dict(color=theme.TEXT, size=12))

    # אליפסות 95%
    for u in users:
        sol = solutions.get(u.id)
        if sol is None:
            continue
        ex, ey = _ellipse_xy(u.x, u.y, sol, mag)
        worst = u.id == worst_id
        fig.add_trace(go.Scatter(
            x=ex, y=ey, mode="lines", hoverinfo="skip", showlegend=False,
            line=dict(color=theme.TEXT, width=2.4 if worst else 1.4),
            opacity=1 if worst else 0.75,
        ))

    # משתמשים
    if users:
        fig.add_trace(go.Scatter(
            x=[u.x for u in users], y=[u.y for u in users], mode="markers", showlegend=False,
            marker=dict(
                symbol=["square" if u.kind == "robot" else "circle" for u in users],
                size=14, color=theme.TEXT, line=dict(color="white", width=2),
            ),
            customdata=[[u.id, theme.KIND_LABELS.get(u.kind, u.kind),
                         solutions[u.id].rms if solutions.get(u.id) else float("nan")]
                        for u in users],
            hovertemplate="%{customdata[0]} (%{customdata[1]})<br>שגיאה: %{customdata[2]:.2f} מטר"
                          "<extra></extra>",
        ))
        for u in users:
            sol = solutions.get(u.id)
            e = sol.rms if sol else None
            txt = "אין פתרון" if e is None else ("±>99" if e > 99 else f"±{e:.2f}")
            color = theme.error_color(e)
            fig.add_annotation(x=u.x, y=u.y, yshift=22, showarrow=False,
                               text=f"<b>{u.id}  {txt}</b>", bgcolor="white",
                               bordercolor=color, borderwidth=1.5, borderpad=2,
                               font=dict(color=color, size=11))
        wu = next((u for u in users if u.id == worst_id), None)
        if wu is not None:
            fig.add_trace(go.Scatter(
                x=[wu.x], y=[wu.y], mode="markers", hoverinfo="skip", showlegend=False,
                marker=dict(symbol="circle-open", size=26, color=theme.WARNING,
                            line=dict(width=2.5, color=theme.WARNING)),
            ))

    # מצופים
    if buoys:
        fig.add_trace(go.Scatter(
            x=[b.x for b in buoys], y=[b.y for b in buoys], mode="markers+text",
            showlegend=False, text=[b.name for b in buoys], textposition="middle center",
            textfont=dict(color=theme.TEXT, size=9, family="Heebo"),
            marker=dict(size=22, color=theme.BUOY, line=dict(color=theme.TEXT, width=2)),
            hovertemplate="%{text}<br>x %{x:.0f}, y %{y:.0f}<extra></extra>",
        ))

    fig.update_xaxes(range=[0, world_w], title="x: מזרח, מטר", showgrid=True,
                     gridcolor="rgba(255,255,255,0.25)", dtick=40, zeroline=False,
                     constrain="domain")
    fig.update_yaxes(range=[0, world_h], title="y: צפון, מטר", showgrid=True,
                     gridcolor="rgba(255,255,255,0.25)", dtick=40, zeroline=False,
                     scaleanchor="x", scaleratio=1, constrain="domain")
    fig.update_layout(
        height=640, showlegend=False, margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor=NO_SOLUTION_BG if show_heat else "#CFE0F5",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Heebo, system-ui, sans-serif", color=theme.TEXT),
        hoverlabel=dict(font_family="Heebo"),
    )
    return fig
