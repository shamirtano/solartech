"""
generar_figuras_dashboard.py
============================
Genera las figuras finales del proyecto de análisis de potencial solar en Colombia.

DASHBOARD (HTML interactivo — Plotly):
  fig02_top15_interactivo.html   — Top 15 municipios por irradiancia con indicador UPME
  fig03_boxplot_region.html      — Boxplot de irradiancia por región natural
  fig07a_mw_region.html          — Capacidad MW solar UPME por región
  fig07b_fases_donut.html        — Distribución de proyectos por fase (donut)
  fig10_brecha_regional.html     — Recurso solar vs. capacidad planificada por región
  fig11_cuadrantes_brecha.html   — Cuadrante potencial vs. inversión UPME por municipio

ANEXO (PNG estático — Matplotlib):
  fig01_distribuciones_region.png — Distribución de irradiancia por región natural
  fig06_correlacion_nasa.png      — Matriz de correlación de variables climáticas NASA

Uso:
  cd scripts/
  python generar_figuras_dashboard.py

Requisitos:
  pip install pandas plotly matplotlib seaborn scipy
"""

import sqlite3
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import seaborn as sns
from scipy.stats import pearsonr

warnings.filterwarnings("ignore")

# ── Rutas ────────────────────────────────────────────────────────────────────
BASE    = Path(__file__).parent.parent          # raíz del proyecto
DB_PATH = BASE / "data" / "potencial_solar.db"
FIG_DIR = BASE / "docs" / "figuras"
FIG_DIR.mkdir(parents=True, exist_ok=True)

assert DB_PATH.exists(), f"No se encontró la BD en {DB_PATH}"

# ── Paleta de colores ─────────────────────────────────────────────────────────
PALETTE = {
    "Caribe":    "#F4A020",
    "Andina":    "#3A86FF",
    "Orinoquia": "#06D6A0",
    "Amazonia":  "#8338EC",
    "Pacifica":  "#FF006E",
}
SOLAR_ORANGE = "#F4A020"
UPME_BLUE    = "#3A86FF"
GAP_RED      = "#EF233C"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. CARGA DE DATOS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def cargar_datos():
    conn = sqlite3.connect(DB_PATH)

    # Mediciones NASA con región
    df_nasa = pd.read_sql("""
        SELECT n.irradiancia_global, n.temperatura_2m, n.humedad_relativa,
               n.velocidad_viento, n.precipitacion,
               n.id_municipio, m.nombre municipio, m.latitud, m.longitud,
               d.nombre departamento, d.region_natural
        FROM mediciones_nasa n
        JOIN municipios m ON n.id_municipio = m.id_municipio
        JOIN departamentos d ON m.id_departamento = d.id_departamento
    """, conn)

    # Proyectos UPME solares
    df_solar = pd.read_sql("""
        SELECT p.capacidad_mw, p.id_municipio, ep.nombre estado,
               m.nombre municipio, d.nombre departamento, d.region_natural
        FROM proyectos_upme p
        JOIN estados_proyecto ep ON p.id_estado = ep.id_estado
        JOIN recursos r          ON p.id_recurso = r.id_recurso
        JOIN municipios m        ON p.id_municipio = m.id_municipio
        JOIN departamentos d     ON m.id_departamento = d.id_departamento
        WHERE r.nombre = 'SOLAR'
    """, conn)

    conn.close()
    return df_nasa, df_solar


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ANEXO — fig01: Distribución de irradiancia por región (PNG)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fig01_distribuciones_region(df_nasa):
    regiones = [r for r in ["Caribe", "Andina", "Orinoquia", "Amazonia", "Pacifica"]
                if r in df_nasa.region_natural.unique()]

    sns.set_theme(style="whitegrid", font_scale=1.05)
    fig, axes = plt.subplots(1, len(regiones), figsize=(18, 4), sharey=False)
    fig.suptitle(
        "Distribución de irradiancia solar por región natural (kWh/m²/día · 2024–2026)",
        fontsize=13, fontweight="bold", y=1.02,
    )

    for ax, region in zip(axes, regiones):
        data  = df_nasa.loc[df_nasa.region_natural == region, "irradiancia_global"].dropna()
        color = PALETTE.get(region, "#888888")
        ax.hist(data, bins=55, color=color, alpha=0.75, edgecolor="white", linewidth=0.3)
        ax.axvline(data.mean(),   color="#333", lw=1.5, ls="--",
                   label=f"Media: {data.mean():.2f}")
        ax.axvline(data.median(), color="#777", lw=1.2, ls=":",
                   label=f"Mediana: {data.median():.2f}")
        ax.set_title(region, fontweight="bold", color=color)
        ax.set_xlabel("kWh/m²/día")
        ax.set_ylabel("Frecuencia")
        ax.legend(fontsize=8)
        ax.text(0.97, 0.95,
                f"n={len(data):,}\nasim={data.skew():.2f}",
                transform=ax.transAxes, ha="right", va="top", fontsize=8,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color, alpha=0.7))

    plt.tight_layout()
    out = FIG_DIR / "fig01_distribuciones_region.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [ANEXO]     fig01 → {out.name}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DASHBOARD — fig02: Top 15 municipios por irradiancia con indicador UPME (HTML)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fig02_top15_interactivo(df_nasa, df_solar):
    # Irradiancia media por municipio
    irr_muni = (
        df_nasa.groupby(["id_municipio", "municipio", "departamento", "region_natural"])
        ["irradiancia_global"]
        .agg(irr_media="mean", irr_std="std")
        .reset_index()
        .sort_values("irr_media", ascending=False)
        .head(15)
    )

    # Municipios con proyecto UPME solar
    upme_ids = set(df_solar.id_municipio.unique())
    irr_muni["tiene_upme"] = irr_muni.id_municipio.isin(upme_ids)
    irr_muni["cv_pct"]     = (irr_muni.irr_std / irr_muni.irr_media * 100).round(1)

    colores   = [PALETTE.get(r, "#888") for r in irr_muni.region_natural]
    bordes    = ["#000000" if t else "white" for t in irr_muni.tiene_upme]
    etiquetas = [f"{m.title()} ★" if t else m.title()
                 for m, t in zip(irr_muni.municipio, irr_muni.tiene_upme)]

    fig = go.Figure(go.Bar(
        x=irr_muni.irr_media,
        y=etiquetas,
        orientation="h",
        marker=dict(color=colores, line=dict(color=bordes, width=2)),
        customdata=list(zip(
            irr_muni.municipio.str.title(),
            irr_muni.departamento.str.title(),
            irr_muni.region_natural,
            irr_muni.cv_pct,
            irr_muni.tiene_upme.map({True: "Sí", False: "No"}),
        )),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "%{customdata[1]} · %{customdata[2]}<br>"
            "Irradiancia media: <b>%{x:.3f} kWh/m²/día</b><br>"
            "Variabilidad (CV): %{customdata[3]}%<br>"
            "Proyecto UPME solar: <b>%{customdata[4]}</b>"
            "<extra></extra>"
        ),
    ))

    # Leyenda manual de regiones
    for region, color in PALETTE.items():
        if region in irr_muni.region_natural.values:
            fig.add_trace(go.Bar(
                x=[None], y=[None], name=region,
                marker_color=color, showlegend=True,
            ))
    fig.add_trace(go.Bar(
        x=[None], y=[None], name="★ Con proyecto UPME",
        marker=dict(color="white", line=dict(color="black", width=2)),
        showlegend=True,
    ))

    fig.update_layout(
        title=dict(
            text="<b>Top 15 municipios por irradiancia solar media (2024–2026)</b><br>"
                 "<sup>★ indica presencia de proyecto UPME solar registrado</sup>",
            x=0.5, xanchor="center", font=dict(size=14),
        ),
        xaxis=dict(title="Irradiancia media diaria (kWh/m²/día)", gridcolor="#eeeeee"),
        yaxis=dict(autorange="reversed"),
        barmode="overlay",
        plot_bgcolor="white", paper_bgcolor="white",
        height=520, width=820,
        margin=dict(l=180, r=30, t=90, b=60),
        legend=dict(orientation="v", x=1.01, y=1, font=dict(size=10)),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )

    out = FIG_DIR / "fig02_top15_interactivo.html"
    fig.write_html(str(out), include_plotlyjs="cdn")
    print(f"  [DASHBOARD] fig02 → {out.name}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DASHBOARD — fig03: Boxplot de irradiancia por región (HTML)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fig03_boxplot_region(df_nasa):
    # Orden por mediana descendente
    orden = (
        df_nasa.groupby("region_natural")["irradiancia_global"]
        .median()
        .sort_values(ascending=False)
        .index.tolist()
    )

    fig = go.Figure()
    for region in orden:
        data = df_nasa.loc[df_nasa.region_natural == region, "irradiancia_global"].dropna()
        fig.add_trace(go.Box(
            y=data,
            name=region,
            marker_color=PALETTE.get(region, "#888"),
            line_color=PALETTE.get(region, "#888"),
            boxmean=False,
            hovertemplate=(
                f"<b>{region}</b><br>"
                "Irradiancia: <b>%{y:.3f} kWh/m²/día</b>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        title=dict(
            text="<b>Distribución de irradiancia solar por región natural (2024–2026)</b><br>"
                 "<sup>Ordenado por mediana descendente · cada punto es una medición diaria</sup>",
            x=0.5, xanchor="center", font=dict(size=14),
        ),
        yaxis=dict(title="Irradiancia global diaria (kWh/m²/día)", gridcolor="#eeeeee"),
        xaxis=dict(title="Región natural"),
        plot_bgcolor="white", paper_bgcolor="white",
        height=480, width=800,
        margin=dict(l=70, r=30, t=90, b=60),
        showlegend=False,
        hoverlabel=dict(bgcolor="white", font_size=12),
    )

    out = FIG_DIR / "fig03_boxplot_region.html"
    fig.write_html(str(out), include_plotlyjs="cdn")
    print(f"  [DASHBOARD] fig03 → {out.name}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ANEXO — fig06: Matriz de correlación de variables NASA (PNG)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fig06_correlacion_nasa(df_nasa):
    vars_nasa = ["irradiancia_global", "temperatura_2m", "humedad_relativa",
                 "velocidad_viento", "precipitacion"]
    labels    = ["Irradiancia\n(kWh/m²/d)", "Temperatura\n(°C)", "Humedad\n(%)",
                 "Viento\n(m/s)", "Precipitación\n(mm/d)"]

    sample = df_nasa[vars_nasa].dropna().sample(min(20_000, len(df_nasa)), random_state=42)
    corr   = sample.corr(method="pearson")
    corr.columns = labels
    corr.index   = labels

    sns.set_theme(style="white", font_scale=1.05)
    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdYlGn",
                center=0, vmin=-1, vmax=1,
                linewidths=0.5, ax=ax, square=True)
    ax.set_title("Matriz de correlación de Pearson — Variables climáticas NASA\n"
                 "(muestra aleatoria 20 000 registros, 2024–2026)",
                 fontweight="bold")
    plt.tight_layout()
    out = FIG_DIR / "fig06_correlacion_nasa.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [ANEXO]     fig06 → {out.name}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DASHBOARD — fig07a: MW solar UPME por región (HTML)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fig07a_mw_region(df_solar):
    resumen = (
        df_solar.groupby("region_natural")
        .agg(mw_total=("capacidad_mw", "sum"),
             n_proyectos=("capacidad_mw", "count"),
             mw_promedio=("capacidad_mw", "mean"))
        .reset_index()
        .sort_values("mw_total", ascending=True)
    )

    fig = go.Figure(go.Bar(
        x=resumen.mw_total,
        y=resumen.region_natural,
        orientation="h",
        marker_color=[PALETTE.get(r, "#888") for r in resumen.region_natural],
        marker_line=dict(color="white", width=1),
        customdata=list(zip(resumen.n_proyectos, resumen.mw_promedio)),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Capacidad total: <b>%{x:,.0f} MW</b><br>"
            "N° proyectos: %{customdata[0]}<br>"
            "Promedio por proyecto: %{customdata[1]:,.0f} MW"
            "<extra></extra>"
        ),
        text=[f"{v:,.0f} MW" for v in resumen.mw_total],
        textposition="outside",
        textfont=dict(size=11),
    ))

    fig.update_layout(
        title=dict(
            text="<b>Capacidad solar planificada UPME por región natural</b><br>"
                 "<sup>Proyectos fotovoltaicos registrados 2024–2026 · Total: "
                 f"{resumen.mw_total.sum():,.0f} MW</sup>",
            x=0.5, xanchor="center", font=dict(size=14),
        ),
        xaxis=dict(title="MW totales planificados", gridcolor="#eeeeee",
                   range=[0, resumen.mw_total.max() * 1.18]),
        yaxis=dict(title=""),
        plot_bgcolor="white", paper_bgcolor="white",
        height=380, width=720,
        margin=dict(l=110, r=60, t=90, b=60),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )

    out = FIG_DIR / "fig07a_mw_region.html"
    fig.write_html(str(out), include_plotlyjs="cdn")
    print(f"  [DASHBOARD] fig07a → {out.name}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DASHBOARD — fig07b: Distribución de proyectos por fase — donut (HTML)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fig07b_fases_donut(df_solar):
    fases = (
        df_solar.groupby("estado")
        .agg(mw=("capacidad_mw", "sum"), n=("capacidad_mw", "count"))
        .reset_index()
        .sort_values("mw", ascending=False)
    )

    total_mw = fases.mw.sum()
    colores_fase = {
        "FASE 1": "#06D6A0",
        "FASE 2": SOLAR_ORANGE,
        "FASE 3": GAP_RED,
    }

    fig = go.Figure(go.Pie(
        labels=fases.estado,
        values=fases.mw,
        hole=0.55,
        marker=dict(
            colors=[colores_fase.get(e, "#BBBBBB") for e in fases.estado],
            line=dict(color="white", width=2),
        ),
        textinfo="label+percent",
        textfont=dict(size=13),
        customdata=list(zip(fases.n, fases.mw)),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Capacidad: <b>%{customdata[1]:,.0f} MW</b><br>"
            "Participación: <b>%{percent}</b><br>"
            "N° proyectos: %{customdata[0]}"
            "<extra></extra>"
        ),
    ))

    fig.add_annotation(
        text=f"<b>{total_mw:,.0f}</b><br>MW totales",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16),
        xanchor="center", yanchor="middle",
    )

    fig.update_layout(
        title=dict(
            text="<b>Proyectos solares UPME por fase de madurez</b><br>"
                 "<sup>Fase 3 = listo para operar · Fase 2 = en desarrollo · Fase 1 = inscrito</sup>",
            x=0.5, xanchor="center", font=dict(size=14),
        ),
        plot_bgcolor="white", paper_bgcolor="white",
        height=430, width=600,
        margin=dict(l=30, r=30, t=90, b=40),
        showlegend=True,
        legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center"),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )

    out = FIG_DIR / "fig07b_fases_donut.html"
    fig.write_html(str(out), include_plotlyjs="cdn")
    print(f"  [DASHBOARD] fig07b → {out.name}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DASHBOARD — fig10: Recurso solar vs. capacidad planificada por región (HTML)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fig10_brecha_regional(df_nasa, df_solar):
    irr = (
        df_nasa[df_nasa.region_natural != "Insular"]
        .groupby("region_natural")["irradiancia_global"]
        .mean()
        .reset_index()
        .rename(columns={"irradiancia_global": "irr_media"})
    )
    mw = (
        df_solar[df_solar.region_natural != "Insular"]
        .groupby("region_natural")
        .agg(mw_total=("capacidad_mw", "sum"), n_proy=("capacidad_mw", "count"))
        .reset_index()
    )
    panel = irr.merge(mw, on="region_natural", how="left").fillna(0)
    panel = panel.sort_values("irr_media", ascending=False)

    def clasificar(r):
        if r.mw_total == 0:
            return ("Sin prioridad", "#BBBBBB")
        if r.irr_media >= 4.7 and r.mw_total < 1000:
            return ("Brecha critica", "#EF233C")
        if r.mw_total > 2000 and r.irr_media < 4.7:
            return ("Sobreplanificada", "#3A86FF")
        return ("Bien aprovechada", "#06D6A0")

    panel[["clasificacion", "color"]] = panel.apply(
        clasificar, axis=1, result_type="expand"
    )

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x=panel.region_natural, y=panel.irr_media,
        name="Irradiancia media (kWh/m²/día)",
        marker_color=SOLAR_ORANGE, opacity=0.85,
        width=0.4, offset=-0.22,
        hovertemplate="<b>%{x}</b><br>Irradiancia: <b>%{y:.2f} kWh/m²/día</b><extra></extra>",
    ), secondary_y=False)

    fig.add_trace(go.Bar(
        x=panel.region_natural, y=panel.mw_total,
        name="Capacidad UPME solar (MW)",
        marker_color=UPME_BLUE, opacity=0.75,
        width=0.4, offset=0.22,
        hovertemplate=[
            f"<b>{r.region_natural}</b><br>"
            f"Capacidad planificada: <b>{r.mw_total:,.0f} MW</b><br>"
            f"N° proyectos: {int(r.n_proy)}<extra></extra>"
            for _, r in panel.iterrows()
        ],
    ), secondary_y=True)

    for _, r in panel.iterrows():
        fig.add_annotation(
            x=r.region_natural, y=r.irr_media, yref="y",
            text=f"<b>{r.clasificacion}</b>",
            font=dict(size=11, color=r.color),
            showarrow=False, yshift=12, xanchor="center",
        )

    fig.update_layout(
        title=dict(
            text="<b>Recurso solar disponible vs. Capacidad planificada UPME por región</b><br>"
                 "<sup>Barras naranjas: irradiancia media 2024–2026 (eje izquierdo)  ·  "
                 "Barras azules: MW solares UPME (eje derecho)  ·  Insular excluida</sup>",
            x=0.5, xanchor="center", font=dict(size=14),
        ),
        barmode="overlay",
        plot_bgcolor="white", paper_bgcolor="white",
        height=480, width=850,
        margin=dict(l=70, r=70, t=100, b=60),
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    fig.update_yaxes(title_text="Irradiancia media diaria (kWh/m²/día)",
                     secondary_y=False, gridcolor="#eeeeee", range=[3.5, 6.2])
    fig.update_yaxes(title_text="Capacidad solar planificada UPME (MW)",
                     secondary_y=True, gridcolor="#eeeeee", range=[0, 4800])

    out = FIG_DIR / "fig10_brecha_regional.html"
    fig.write_html(str(out), include_plotlyjs="cdn")
    print(f"  [DASHBOARD] fig10 → {out.name}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DASHBOARD — fig11: Cuadrante potencial vs. inversión UPME por municipio (HTML)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fig11_cuadrantes_brecha(df_nasa, df_solar):
    irr_muni = (
        df_nasa.groupby(["id_municipio", "municipio", "departamento", "region_natural"])
        ["irradiancia_global"].mean()
        .reset_index()
        .rename(columns={"irradiancia_global": "irr_media"})
    )
    upme_muni = (
        df_solar.groupby("id_municipio")
        .agg(mw_solar=("capacidad_mw", "sum"), n_proy=("capacidad_mw", "count"))
        .reset_index()
    )
    pm = irr_muni.merge(upme_muni, on="id_municipio", how="left").fillna(0)

    med_irr = pm.irr_media.median()
    med_mw  = pm[pm.mw_solar > 0].mw_solar.median()   # umbral: mediana de los que tienen proyecto

    def quadrant(r):
        hi_irr = r.irr_media >= med_irr
        hi_mw  = r.mw_solar  >= med_mw
        if hi_irr and not hi_mw:      return "Brecha critica"
        if hi_irr and hi_mw:          return "Bien aprovechado"
        if not hi_irr and hi_mw:      return "Sobreplanificado"
        return "Sin prioridad"

    pm["quad"] = pm.apply(quadrant, axis=1)

    # Jitter visual para municipios con mw = 0
    rng = np.random.default_rng(42)
    pm["mw_plot"]  = pm.mw_solar.astype(float)
    pm["irr_plot"] = pm.irr_media.astype(float)
    mask0 = pm.mw_solar == 0
    n0    = mask0.sum()
    pm.loc[mask0, "mw_plot"]  = rng.uniform(1, 65, n0)
    pm.loc[mask0, "irr_plot"] = pm.loc[mask0, "irr_media"] + rng.uniform(-0.025, 0.025, n0)

    QUAD_CFG = {
        "Brecha critica":   {"color": GAP_RED,      "symbol": "circle-open", "size": 10, "lcolor": "#c00020"},
        "Bien aprovechado": {"color": "#06D6A0",    "symbol": "circle",      "size": 9,  "lcolor": "#007a50"},
        "Sobreplanificado": {"color": UPME_BLUE,    "symbol": "diamond",     "size": 9,  "lcolor": "#1a3fa0"},
        "Sin prioridad":    {"color": "#BBBBBB",    "symbol": "circle",      "size": 7,  "lcolor": "#888888"},
    }

    xmin = pm.irr_media.min() - 0.06
    xmax = pm.irr_media.max() + 0.06
    ymax = pm.mw_solar.max() * 1.2

    fig = go.Figure()

    # Fondos de cuadrante
    for coords, fc in [
        (dict(x0=med_irr, x1=xmax,    y0=0.5,    y1=med_mw), "rgba(239,35,60,0.06)"),
        (dict(x0=med_irr, x1=xmax,    y0=med_mw, y1=ymax),   "rgba(6,214,160,0.06)"),
        (dict(x0=xmin,    x1=med_irr, y0=med_mw, y1=ymax),   "rgba(58,134,255,0.06)"),
        (dict(x0=xmin,    x1=med_irr, y0=0.5,    y1=med_mw), "rgba(187,187,187,0.07)"),
    ]:
        fig.add_shape(type="rect", layer="below", fillcolor=fc, line_width=0, **coords)

    # Líneas y anotaciones de referencia
    fig.add_vline(x=med_irr, line_dash="dash", line_color="#aaa", line_width=1.2)
    fig.add_hline(y=med_mw,  line_dash="dash", line_color="#aaa", line_width=1.2)
    fig.add_annotation(x=med_irr, y=1200, xanchor="right",
        text=f"Mediana irr. {med_irr:.2f} kWh/m²/d",
        showarrow=False, font=dict(size=9, color="#888"), xshift=-5)
    fig.add_annotation(x=xmin + 0.01, y=med_mw * 1.15, yanchor="bottom",
        text=f"Umbral {med_mw:.0f} MW",
        showarrow=False, font=dict(size=9, color="#888"), xanchor="left")

    # Etiquetas de cuadrante
    fig.add_annotation(x=xmax - 0.01, y=15,       xanchor="right", yanchor="middle",
        text="<b>Brecha critica</b>",   showarrow=False, font=dict(size=12, color="#c00020"))
    fig.add_annotation(x=xmax - 0.01, y=1000,     xanchor="right", yanchor="top",
        text="<b>Bien aprovechado</b>", showarrow=False, font=dict(size=12, color="#007a50"))
    fig.add_annotation(x=xmin + 0.01, y=1000,     xanchor="left",  yanchor="top",
        text="<b>Sobreplanificado</b>", showarrow=False, font=dict(size=12, color="#1a3fa0"))
    fig.add_annotation(x=xmin + 0.01, y=15,       xanchor="left",  yanchor="middle",
        text="<b>Sin prioridad</b>",    showarrow=False, font=dict(size=12, color="#888888"))

    # Trazas
    for quad, cfg in QUAD_CFG.items():
        sub = pm[pm.quad == quad]
        fig.add_trace(go.Scatter(
            x=sub.irr_plot, y=sub.mw_plot,
            mode="markers", name=quad,
            marker=dict(color=cfg["color"], symbol=cfg["symbol"],
                        size=cfg["size"], line=dict(color="white", width=1), opacity=0.85),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}<br>"
                "Irradiancia: <b>%{customdata[5]:.3f} kWh/m²/día</b><br>"
                "Capacidad UPME: <b>%{customdata[3]:,.0f} MW</b><br>"
                "N° proyectos: %{customdata[4]}<extra></extra>"
            ),
            customdata=list(zip(
                sub.municipio.str.title(), sub.departamento.str.title(),
                sub.region_natural, sub.mw_solar, sub.n_proy, sub.irr_media,
            )),
        ))

    # Etiquetas municipios clave
    for _, r in pm[pm.quad == "Brecha critica"].nlargest(8, "irr_media").iterrows():
        fig.add_annotation(x=r.irr_plot, y=r.mw_plot, text=f"  {r.municipio.title()}",
            showarrow=False, xanchor="left", yanchor="middle",
            font=dict(size=9, color="#EF233C"))
    for _, r in pm[pm.quad == "Bien aprovechado"].nlargest(5, "mw_solar").iterrows():
        fig.add_annotation(x=r.irr_plot, y=r.mw_plot, text=f"  {r.municipio.title()}",
            showarrow=False, xanchor="left", yanchor="middle",
            font=dict(size=9, color="#007a50"))

    fig.add_annotation(
        x=0.5, y=-0.17, xref="paper", yref="paper",
        text="Municipios sin proyecto UPME (MW = 0) se muestran con desplazamiento vertical para mayor legibilidad. El valor real es 0 MW.",
        showarrow=False, font=dict(size=9, color="#aaa"), xanchor="center",
    )

    fig.update_layout(
        title=dict(
            text="<b>Potencial solar vs. Inversión UPME por municipio</b><br>"
                 "<sup>88 municipios del panel NASA · "
                 "Ejes de referencia: mediana nacional de irradiancia y umbral 100 MW</sup>",
            x=0.5, xanchor="center", font=dict(size=14),
        ),
        xaxis=dict(title="Irradiancia media diaria (kWh/m²/día)",
                   gridcolor="#f0f0f0", range=[xmin, xmax]),
        yaxis=dict(
            title="Capacidad UPME solar planificada (MW)",
            type="log", gridcolor="#f0f0f0",
            tickvals=[1, 5, 10, 50, 100, 250, 500, 1000],
            ticktext=["<1", "5", "10", "50", "100", "250", "500", "1000"],
            range=[0, np.log10(ymax)],
        ),
        legend=dict(orientation="h", y=-0.13, x=0.5, xanchor="center", font=dict(size=10)),
        plot_bgcolor="white", paper_bgcolor="white",
        height=570, width=860,
        margin=dict(l=70, r=30, t=100, b=120),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )

    out = FIG_DIR / "fig11_cuadrantes_brecha.html"
    fig.write_html(str(out), include_plotlyjs="cdn")
    print(f"  [DASHBOARD] fig11 → {out.name}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    print(f"\nBase de datos: {DB_PATH}")
    print(f"Salida:        {FIG_DIR}\n")

    print("Cargando datos...")
    df_nasa, df_solar = cargar_datos()
    print(f"  NASA: {len(df_nasa):,} mediciones  |  UPME solar: {len(df_solar)} proyectos\n")

    print("Generando figuras...")
    fig01_distribuciones_region(df_nasa)
    fig02_top15_interactivo(df_nasa, df_solar)
    fig03_boxplot_region(df_nasa)
    fig06_correlacion_nasa(df_nasa)
    fig07a_mw_region(df_solar)
    fig07b_fases_donut(df_solar)
    fig10_brecha_regional(df_nasa, df_solar)
    fig11_cuadrantes_brecha(df_nasa, df_solar)

    print(f"\nListo. 8 figuras guardadas en {FIG_DIR}")
    print("  Anexo (PNG):      fig01, fig06")
    print("  Dashboard (HTML): fig02, fig03, fig07a, fig07b, fig10, fig11")
