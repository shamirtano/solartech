"""
app.py  —  SolarTech Colombia: Dashboard Integrado
==================================================
Una sola app Streamlit con tres pestañas:

  1. Explorador Solar Nacional  — Supabase + NASA POWER en tiempo real
  2. Análisis de Brecha         — 88 municipios · SQLite · 6 figuras Plotly
  3. Anexo Técnico              — figuras PNG para el informe académico

Uso local:
  pip install -r requirements.txt
  streamlit run app.py

Credenciales (archivo .streamlit/secrets.toml o variables de entorno):
  DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
"""

from datetime import datetime
from io import BytesIO
import os
import sqlite3
import time
import unicodedata
import warnings
from pathlib import Path

import emoji
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

warnings.filterwarnings("ignore")
load_dotenv()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RUTAS Y CONSTANTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BASE    = Path(__file__).parent
DB_LITE = BASE / "data" / "potencial_solar.db"
FIG_DIR = BASE / "docs" / "figuras"

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

NASA_BG_URL = (
    "https://images-assets.nasa.gov/image/iss065e066456/iss065e066456~large.jpg"
)
HERO_IMG_URL = (
    "https://static.vecteezy.com/system/resources/thumbnails/007/449/150/small/"
    "hand-holding-tree-growing-on-globe-with-solar-cell-and-turbine-concept-"
    "clean-energy-for-save-world-elements-of-this-image-furnished-nasa-free-photo.jpg"
)

UPME_TABLE_NAME = "proyectos_upme"
UPME_TEMPLATE_COLUMNS = [
    "codigo_proyecto", "marco_normativo_aplicable", "fecha_inscripcion_proyecto",
    "fecha_limite_validez", "nombre_proyecto", "estado", "recurso", "tipo",
    "tecnologia", "capacidad_mw", "departamento", "municipio",
    "fecha_inicio_construccion", "fecha_estimada_operacion",
    "codigo_dane_municipio", "latitud", "longitud", "id_municipio", "observaciones",
]
UPME_REQUIRED_COLUMNS = {"codigo_proyecto", "nombre_proyecto", "departamento", "municipio"}
UPME_COLUMN_DEFINITIONS = {
    "codigo_proyecto": "TEXT", "marco_normativo_aplicable": "TEXT",
    "fecha_inscripcion_proyecto": "DATE", "fecha_limite_validez": "DATE",
    "nombre_proyecto": "TEXT", "estado": "TEXT", "recurso": "TEXT",
    "tipo": "TEXT", "tecnologia": "TEXT", "capacidad_mw": "NUMERIC",
    "departamento": "TEXT", "municipio": "TEXT",
    "fecha_inicio_construccion": "DATE", "fecha_estimada_operacion": "DATE",
    "codigo_dane_municipio": "TEXT", "observaciones": "TEXT",
    "id_municipio": "INTEGER", "latitud": "NUMERIC", "longitud": "NUMERIC",
    "fecha_cargue": "TIMESTAMP",
}
UPME_COLUMN_ALIASES = {
    "codigo_proyecto": "codigo_proyecto", "codigo_del_proyecto": "codigo_proyecto",
    "codigo_upme": "codigo_proyecto", "marco_normativo_aplicable": "marco_normativo_aplicable",
    "fecha_inscripcion_proyecto": "fecha_inscripcion_proyecto",
    "fecha_de_inscripcion_proyecto": "fecha_inscripcion_proyecto",
    "fecha_limite_de_validez": "fecha_limite_validez", "fecha_limite_validez": "fecha_limite_validez",
    "nombre_del_proyecto": "nombre_proyecto", "nombre_proyecto": "nombre_proyecto",
    "estado": "estado", "recurso": "recurso", "tipo": "tipo", "tecnologia": "tecnologia",
    "capacidad_[mw]": "capacidad_mw", "capacidad_mw": "capacidad_mw",
    "departamento": "departamento", "municipio": "municipio",
    "fecha_de_inicio_de_construccion": "fecha_inicio_construccion",
    "fecha_inicio_construccion": "fecha_inicio_construccion",
    "fecha_de_entrada_en_operacion": "fecha_estimada_operacion",
    "fecha_entrada_operacion": "fecha_estimada_operacion",
    "fecha_estimada_operacion": "fecha_estimada_operacion",
}
MAPEO_VARIABLES = {
    emoji.emojize(":sun: Irradiancia Global (kWh/m2/dia)"): {
        "nasa": "ALLSKY_SFC_SW_DWN", "col_bd": "irradiancia",
        "unidad": " kWh/m²/día",
    },
    emoji.emojize(":thermometer: Temperatura Ambiente (C)"): {
        "nasa": "T2M", "col_bd": "temperatura", "unidad": " °C",
    },
    emoji.emojize(":droplet: Humedad Relativa (%)"): {
        "nasa": "RH2M", "col_bd": "humedad", "unidad": " %",
    },
    emoji.emojize(":dashing_away: Velocidad del Viento (m/s)"): {
        "nasa": "WS2M", "col_bd": "viento", "unidad": " m/s",
    },
    emoji.emojize(":cloud_with_rain: Precipitacion (mm/dia)"): {
        "nasa": "PRECTOTCORR", "col_bd": "precipitacion", "unidad": " mm/día",
    },
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PÁGINA Y ESTILOS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(
    page_title="SolarTech Colombia",
    page_icon=emoji.emojize(":sun:"),
    layout="wide",
)


def aplicar_estilos():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                linear-gradient(120deg, rgba(6,13,30,0.92), rgba(8,30,45,0.82)),
                url("{NASA_BG_URL}");
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
            color: #000;
        }}
        .stApp, .stApp p, .stApp span, .stApp label, .stApp div, .stApp li,
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        [data-testid="stMarkdownContainer"],
        [data-testid="stWidgetLabel"],
        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"] {{ color: #f5f7fb; }}
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li {{ color: #d9e7ef; }}
        .stApp a {{ color: #8fd4ff; }}
        .stApp a:hover {{ color: #ffd166; }}
        [data-testid="stSidebar"] {{
            background: rgba(2,10,24,0.88);
            border-right: 1px solid rgba(255,255,255,0.12);
        }}
        [data-testid="stSidebar"] *, [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p {{ color: #f5f7fb; }}
        [data-testid="stHeader"] {{ background: rgba(2,10,24,0); }}
        .block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; }}
        .solar-hero {{
            border: 1px solid rgba(255,255,255,0.16);
            background:
                linear-gradient(90deg,rgba(3,12,28,0.92) 0%,rgba(8,35,48,0.78) 48%,rgba(8,35,48,0.38) 100%),
                url("{HERO_IMG_URL}");
            background-size: cover; background-position: center right;
            border-radius: 8px; min-height: 180px; padding: 1.4rem 1.6rem;
            margin-bottom: 1rem; box-shadow: 0 20px 50px rgba(0,0,0,0.25);
            display: flex; flex-direction: column; justify-content: center;
        }}
        .solar-hero h1, .solar-hero h2 {{
            margin: 0; max-width: 720px; font-size: 2.1rem; line-height: 1.1;
            color: #ffffff; text-shadow: 0 2px 14px rgba(0,0,0,0.55);
        }}
        .solar-hero p {{
            margin: 0.5rem 0 0; max-width: 680px; color: #e6f4f7;
            font-size: 0.97rem; text-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }}
        .metric-band {{
            display: grid; grid-template-columns: repeat(3, minmax(0,1fr));
            gap: 0.8rem; margin: 0.8rem 0 1.2rem;
        }}
        .metric-tile {{
            border: 1px solid rgba(255,255,255,0.14);
            background: rgba(255,255,255,0.08);
            border-radius: 8px; padding: 0.9rem 1rem;
        }}
        .metric-tile span {{ color: #a8d8ff; font-size: 0.78rem; text-transform: uppercase; }}
        .metric-tile strong {{ display: block; margin-top: 0.25rem; font-size: 1.2rem; color: #ffffff; }}
        .kpi-band {{
            display: grid; grid-template-columns: repeat(4, minmax(0,1fr));
            gap: 0.8rem; margin: 0.8rem 0 1.4rem;
        }}
        .kpi-tile {{
            border: 1px solid rgba(255,255,255,0.14);
            background: rgba(255,255,255,0.07);
            border-radius: 8px; padding: 0.85rem 1rem; text-align: center;
        }}
        .kpi-tile .kpi-num {{ font-size: 1.7rem; font-weight: 700; color: #ffd166; }}
        .kpi-tile .kpi-lbl {{ font-size: 0.78rem; color: #a8d8ff; margin-top: 0.2rem; }}
        .section-label {{
            font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
            color: #8fd4ff; margin: 1.6rem 0 0.4rem;
        }}
        div[data-testid="stMetric"] {{
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 8px; padding: 0.8rem;
        }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 0.35rem; }}
        .stTabs [data-baseweb="tab"] {{
            background: rgba(255,255,255,0.08);
            border-radius: 8px 8px 0 0; padding: 0.5rem 1rem; color: #f5f7fb;
        }}
        .stTabs [data-baseweb="tab"] p {{ color: #f5f7fb; font-weight: 600; }}
        .stTabs [data-baseweb="tab"]:hover {{ background: rgba(255,209,102,0.18); }}
        .stTabs [aria-selected="true"] {{
            background: rgba(143,212,255,0.22);
            border-bottom: 2px solid #ffd166;
        }}
        [data-baseweb="select"] > div, [data-baseweb="input"] > div,
        [data-baseweb="textarea"] textarea, [data-testid="stDateInput"] input {{
            background: rgba(255,255,255,0.94); color: #081627;
            border-color: rgba(143,212,255,0.55);
        }}
        [data-baseweb="select"] span, [data-baseweb="select"] div,
        [data-baseweb="input"] input, [data-testid="stDateInput"] input {{ color: #081627; }}
        [data-baseweb="popover"] *, [role="listbox"] *, [role="option"] {{ color: #081627; }}
        [role="option"]:hover {{ background: rgba(255,209,102,0.24); color: #081627; }}
        .stButton > button,
        .stButton > button[kind="primary"],
        .stDownloadButton > button,
        [data-testid="stFileUploaderDropzone"] {{
            background: rgba(255,255,255,0.92);
            color: #081627 !important;
            border: 1px solid rgba(143,212,255,0.7);
            border-radius: 8px;
        }}
        .stButton > button *,
        .stButton > button[kind="primary"] *,
        .stDownloadButton > button *,
        .stButton > button [data-testid="stMarkdownContainer"],
        .stButton > button[kind="primary"] [data-testid="stMarkdownContainer"],
        .stDownloadButton > button [data-testid="stMarkdownContainer"] {{
            color: #081627 !important;
        }}
        .stButton > button:hover,
        .stButton > button[kind="primary"]:hover,
        .stDownloadButton > button:hover {{
            background: #ffd166;
            color: #081627 !important;
            border-color: #ffd166;
        }}
        .stButton > button:hover *,
        .stButton > button[kind="primary"]:hover *,
        .stDownloadButton > button:hover * {{
            color: #081627 !important;
        }}
        [data-testid="stDataFrame"] {{
            background: rgba(255,255,255,0.96); border-radius: 8px; padding: 0.25rem;
        }}
        [data-testid="stDataFrame"] * {{ color: #081627; }}
        [data-testid="stExpander"] {{
            background: rgba(4,16,34,0.86);
            border: 1px solid rgba(143,212,255,0.28); border-radius: 8px;
        }}
        [data-testid="stExpander"] summary {{
            background: rgba(255,255,255,0.08); border-radius: 8px 8px 0 0; color: #f5f7fb;
        }}
        [data-testid="stExpander"] summary:hover {{ background: rgba(255,209,102,0.18); }}
        [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] [data-testid="stMarkdownContainer"] *,
        [data-testid="stExpander"] div {{ color: #f5f7fb; }}
        /* ── Sección titulo con acento amarillo ── */
        .seccion-titulo {{
            font-size: 1.12rem;
            font-weight: 700;
            color: #ffffff;
            border-left: 4px solid #ffd166;
            padding: 0.35rem 0 0.35rem 1rem;
            margin: 2.2rem 0 0.9rem;
            letter-spacing: 0.01em;
        }}
        /* ── Callout pregunta central ── */
        .pregunta-card {{
            background: linear-gradient(135deg, rgba(255,209,102,0.10), rgba(255,209,102,0.03));
            border: 1px solid rgba(255,209,102,0.35);
            border-left: 4px solid #ffd166;
            border-radius: 8px;
            padding: 1.2rem 1.5rem;
            margin: 0.8rem 0 1.8rem;
        }}
        .pregunta-card .pq-label {{
            font-size: 0.68rem;
            text-transform: uppercase;
            letter-spacing: 0.11em;
            color: #ffd166;
            margin-bottom: 0.5rem;
            font-weight: 600;
        }}
        .pregunta-card p {{
            color: #f0f4f8 !important;
            font-size: 1rem;
            font-style: italic;
            line-height: 1.6;
            margin: 0;
        }}
        /* ── Callout insight / hallazgo ── */
        .insight-card {{
            background: rgba(143,212,255,0.06);
            border: 1px solid rgba(143,212,255,0.18);
            border-left: 4px solid #8fd4ff;
            border-radius: 0 8px 8px 0;
            padding: 0.9rem 1.3rem;
            margin: 0.3rem 0 2rem;
        }}
        .insight-card .ins-label {{
            font-size: 0.67rem;
            text-transform: uppercase;
            letter-spacing: 0.11em;
            color: #8fd4ff;
            margin-bottom: 0.35rem;
            font-weight: 600;
        }}
        .insight-card p {{
            color: #d9e7ef !important;
            font-size: 0.92rem;
            line-height: 1.55;
            margin: 0;
        }}
        /* ── Caption de figura ── */
        .fig-caption {{
            font-size: 0.8rem;
            color: #8a9eb5;
            margin: -0.3rem 0 0.6rem;
            font-style: italic;
        }}
        @media (max-width: 760px) {{
            .solar-hero h1, .solar-hero h2 {{ font-size: 1.5rem; }}
            .metric-band, .kpi-band {{ grid-template-columns: 1fr 1fr; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


aplicar_estilos()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONEXIÓN SUPABASE (Tab 1)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_secret(key: str, default=None):
    return st.secrets.get(key, os.getenv(key, default))


@st.cache_resource
def obtener_engine():
    url_conexion = URL.create(
        drivername="postgresql+psycopg2",
        username=get_secret("DB_USER"),
        password=get_secret("DB_PASSWORD"),
        host=get_secret("DB_HOST"),
        port=int(get_secret("DB_PORT", 5432)),
        database=get_secret("DB_NAME"),
    )
    return create_engine(url_conexion, pool_pre_ping=True)


@st.cache_data(ttl=600)
def cargar_parametros_geograficos():
    try:
        query = """
            SELECT mun.id AS id_municipio, mun.nombre AS municipio,
                   mun.latitud, mun.longitud, mun.codigo_dane,
                   dep.nombre AS departamento
            FROM municipios mun
            JOIN departamentos dep ON mun.id_departamento = dep.id;
        """
        return pd.read_sql(query, con=obtener_engine())
    except Exception as exc:
        st.sidebar.error(f"Error conectando con Supabase: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=120)
def cargar_proyectos_upme():
    try:
        asegurar_tabla_upme()
        query = f"""
            SELECT codigo_proyecto, marco_normativo_aplicable,
                   fecha_inscripcion_proyecto, fecha_limite_validez,
                   nombre_proyecto, estado, recurso, tipo, tecnologia,
                   capacidad_mw, departamento, municipio,
                   fecha_inicio_construccion, fecha_estimada_operacion,
                   codigo_dane_municipio, latitud, longitud,
                   id_municipio, observaciones, fecha_cargue
            FROM {UPME_TABLE_NAME}
            ORDER BY fecha_cargue DESC NULLS LAST, nombre_proyecto ASC;
        """
        return pd.read_sql(query, con=obtener_engine())
    except Exception as exc:
        st.error(f"No fue posible leer proyectos UPME: {exc}")
        return pd.DataFrame()


# ── Helpers UPME ──────────────────────────────────────────────────────────────
def normalizar_texto(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.replace("_", " ").replace("-", " ").split())


def normalizar_nombre_columna(col):
    return normalizar_texto(col).replace(" ", "_")


def homologar_columnas_upme(df):
    df = df.copy()
    df.columns = [
        UPME_COLUMN_ALIASES.get(normalizar_nombre_columna(c), normalizar_nombre_columna(c))
        for c in df.columns
    ]
    return df.loc[:, ~df.columns.duplicated()]


def asegurar_tabla_upme():
    ddl = f"CREATE TABLE IF NOT EXISTS {UPME_TABLE_NAME} (id BIGSERIAL PRIMARY KEY);"
    with obtener_engine().begin() as conn:
        conn.execute(text(ddl))
        for col, tipo in UPME_COLUMN_DEFINITIONS.items():
            conn.execute(text(
                f"ALTER TABLE {UPME_TABLE_NAME} ADD COLUMN IF NOT EXISTS {col} {tipo};"
            ))


def guardar_upme_en_bd(df_upme):
    asegurar_tabla_upme()
    engine = obtener_engine()
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {UPME_TABLE_NAME} RESTART IDENTITY CASCADE;"))
    df_upme.to_sql(UPME_TABLE_NAME, con=engine, if_exists="append", index=False)
    cargar_proyectos_upme.clear()


def preparar_dataframe_upme(archivo, df_geo):
    df = pd.read_excel(archivo)
    if df.empty:
        raise ValueError("El archivo no contiene registros para cargar.")
    df = homologar_columnas_upme(df)
    faltantes = sorted(UPME_REQUIRED_COLUMNS - set(df.columns))
    if faltantes:
        raise ValueError("Faltan columnas obligatorias: " + ", ".join(faltantes))
    for col in UPME_TEMPLATE_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    df = df[UPME_TEMPLATE_COLUMNS].copy()
    df["capacidad_mw"] = pd.to_numeric(df["capacidad_mw"], errors="coerce")
    df["latitud"]      = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"]     = pd.to_numeric(df["longitud"], errors="coerce")
    df["id_municipio"] = pd.to_numeric(df["id_municipio"], errors="coerce")
    for col_f in ["fecha_inscripcion_proyecto", "fecha_limite_validez",
                  "fecha_inicio_construccion", "fecha_estimada_operacion"]:
        df[col_f] = pd.to_datetime(df[col_f], errors="coerce", dayfirst=True).dt.date
    df["codigo_dane_municipio"] = (
        df["codigo_dane_municipio"].astype("string")
        .str.replace(r"\.0$", "", regex=True).str.strip()
    )
    df.loc[df["codigo_dane_municipio"].isin(["", "<NA>", "nan", "None"]),
           "codigo_dane_municipio"] = pd.NA
    df["codigo_dane_municipio"] = df["codigo_dane_municipio"].str.zfill(5)
    if not df_geo.empty:
        geo = df_geo.copy()
        geo["codigo_dane_municipio"] = geo["codigo_dane"].astype("string").str.zfill(5)
        geo["departamento_norm"] = geo["departamento"].map(normalizar_texto)
        geo["municipio_norm"]    = geo["municipio"].map(normalizar_texto)
        geo = geo.rename(columns={"id_municipio": "geo_id", "latitud": "geo_lat", "longitud": "geo_lon"})
        df["departamento_norm"] = df["departamento"].map(normalizar_texto)
        df["municipio_norm"]    = df["municipio"].map(normalizar_texto)
        por_codigo = geo[["codigo_dane_municipio", "geo_id", "geo_lat", "geo_lon"]].drop_duplicates("codigo_dane_municipio")
        df = df.merge(por_codigo, on="codigo_dane_municipio", how="left")
        df["id_municipio"] = df["id_municipio"].fillna(df["geo_id"])
        df["latitud"]      = df["latitud"].fillna(df["geo_lat"])
        df["longitud"]     = df["longitud"].fillna(df["geo_lon"])
        pendientes = df["id_municipio"].isna()
        if pendientes.any():
            por_nombre = geo[["departamento_norm", "municipio_norm", "codigo_dane_municipio",
                              "geo_id", "geo_lat", "geo_lon"]].drop_duplicates()
            res = df.loc[pendientes].merge(por_nombre, on=["departamento_norm", "municipio_norm"],
                                           how="left", suffixes=("", "_n"))
            df.loc[pendientes, "id_municipio"] = res["geo_id_n"].values
            df.loc[pendientes, "codigo_dane_municipio"] = res["codigo_dane_municipio_n"].values
            df.loc[pendientes, "latitud"]  = res["geo_lat_n"].values
            df.loc[pendientes, "longitud"] = res["geo_lon_n"].values
        df = df.drop(columns=["departamento_norm", "municipio_norm", "geo_id", "geo_lat", "geo_lon"], errors="ignore")
    df["fecha_cargue"] = datetime.now()
    return df


def crear_plantilla_upme():
    ejemplo = pd.DataFrame([{
        "codigo_proyecto": "3880", "marco_normativo_aplicable": "Resolucion UPME No. 749 de 2025",
        "fecha_inscripcion_proyecto": "27/02/2026", "fecha_limite_validez": "23/09/2027",
        "nombre_proyecto": "PARQUE SOLAR CORDOBA 200MW", "estado": "FASE 2",
        "recurso": "SOLAR", "tipo": "SOL", "tecnologia": "FOTOVOLTAICO",
        "capacidad_mw": 200.0, "departamento": "CORDOBA", "municipio": "PUEBLO NUEVO",
        "fecha_inicio_construccion": "23/09/2027", "fecha_estimada_operacion": "31/10/2029",
        "codigo_dane_municipio": "", "latitud": "", "longitud": "", "id_municipio": "",
        "observaciones": "Columnas geograficas se completan con la base si hay cruce.",
    }], columns=UPME_TEMPLATE_COLUMNS)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        ejemplo.to_excel(w, sheet_name="Plantilla_UPME", index=False)
    buf.seek(0)
    return buf


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATOS SQLITE (Tab 2)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@st.cache_data(ttl=3600, show_spinner="Cargando datos del análisis de brecha...")
def cargar_datos_brecha():
    if not DB_LITE.exists():
        return None, None
    conn = sqlite3.connect(DB_LITE)
    df_nasa = pd.read_sql("""
        SELECT n.irradiancia_global, n.temperatura_2m, n.humedad_relativa,
               n.velocidad_viento, n.precipitacion,
               n.id_municipio, m.nombre municipio, m.latitud, m.longitud,
               d.nombre departamento, d.region_natural
        FROM mediciones_nasa n
        JOIN municipios m ON n.id_municipio = m.id_municipio
        JOIN departamentos d ON m.id_departamento = d.id_departamento
    """, conn)
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIGURAS PLOTLY (Tab 2)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _dark_layout(fig):
    """Aplica tema oscuro consistente a cualquier figura Plotly."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.04)",
        font=dict(color="#e0e8f0"),
        title=dict(font=dict(color="#ffffff", size=14)),
        legend=dict(
            bgcolor="rgba(20,35,55,0.85)",
            bordercolor="rgba(255,255,255,0.12)",
            borderwidth=1,
            font=dict(color="#d8e8f5"),
        ),
        hoverlabel=dict(
            bgcolor="#1a2d45", font_size=12,
            font_color="#ffffff", bordercolor="#3a5070",
        ),
    )
    fig.update_xaxes(
        gridcolor="rgba(255,255,255,0.08)",
        linecolor="rgba(255,255,255,0.18)",
        tickfont=dict(color="#c5d5e5"),
        title_font=dict(color="#d0dde8"),
    )
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.08)",
        linecolor="rgba(255,255,255,0.18)",
        tickfont=dict(color="#c5d5e5"),
        title_font=dict(color="#d0dde8"),
    )


def build_fig02(df_nasa, df_solar):
    """Top 15 municipios por irradiancia con indicador UPME."""
    irr_muni = (
        df_nasa.groupby(["id_municipio", "municipio", "departamento", "region_natural"])
        ["irradiancia_global"]
        .agg(irr_media="mean", irr_std="std")
        .reset_index()
        .sort_values("irr_media", ascending=False)
        .head(15)
    )
    upme_ids = set(df_solar.id_municipio.unique())
    irr_muni["tiene_upme"] = irr_muni.id_municipio.isin(upme_ids)
    irr_muni["cv_pct"]     = (irr_muni.irr_std / irr_muni.irr_media * 100).round(1)
    colores   = [PALETTE.get(r, "#888") for r in irr_muni.region_natural]
    bordes    = ["#000000" if t else "white" for t in irr_muni.tiene_upme]
    etiquetas = [f"{m.title()} ★" if t else m.title()
                 for m, t in zip(irr_muni.municipio, irr_muni.tiene_upme)]
    fig = go.Figure(go.Bar(
        x=irr_muni.irr_media, y=etiquetas, orientation="h",
        showlegend=False,
        marker=dict(color=colores, line=dict(color=bordes, width=2)),
        customdata=list(zip(
            irr_muni.municipio.str.title(), irr_muni.departamento.str.title(),
            irr_muni.region_natural, irr_muni.cv_pct,
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
    for region, color in PALETTE.items():
        if region in irr_muni.region_natural.values:
            fig.add_trace(go.Bar(x=[None], y=[None], name=region,
                                 marker_color=color, showlegend=True))
    fig.add_trace(go.Bar(x=[None], y=[None], name="★ Con proyecto UPME",
                         marker=dict(color="white", line=dict(color="black", width=2)),
                         showlegend=True))
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
        height=500, margin=dict(l=180, r=30, t=90, b=60),
        legend=dict(orientation="v", x=1.01, y=1, font=dict(size=10)),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    _dark_layout(fig)
    return fig


def build_fig03(df_nasa):
    """Boxplot de irradiancia por región natural."""
    orden = (
        df_nasa.groupby("region_natural")["irradiancia_global"]
        .median().sort_values(ascending=False).index.tolist()
    )
    fig = go.Figure()
    for region in orden:
        data = df_nasa.loc[df_nasa.region_natural == region, "irradiancia_global"].dropna()
        fig.add_trace(go.Box(
            y=data, name=region,
            marker_color=PALETTE.get(region, "#888"),
            line_color=PALETTE.get(region, "#888"),
            boxmean=False,
            hovertemplate=f"<b>{region}</b><br>Irradiancia: <b>%{{y:.3f}} kWh/m²/día</b><extra></extra>",
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
        height=460, margin=dict(l=70, r=30, t=90, b=60),
        showlegend=False, hoverlabel=dict(bgcolor="white", font_size=12),
    )
    _dark_layout(fig)
    return fig


def build_fig07a(df_solar):
    """MW solar UPME por región."""
    resumen = (
        df_solar.groupby("region_natural")
        .agg(mw_total=("capacidad_mw", "sum"),
             n_proyectos=("capacidad_mw", "count"),
             mw_promedio=("capacidad_mw", "mean"))
        .reset_index().sort_values("mw_total", ascending=True)
    )
    fig = go.Figure(go.Bar(
        x=resumen.mw_total, y=resumen.region_natural, orientation="h",
        marker_color=[PALETTE.get(r, "#888") for r in resumen.region_natural],
        marker_line=dict(color="white", width=1),
        customdata=list(zip(resumen.n_proyectos, resumen.mw_promedio)),
        hovertemplate=(
            "<b>%{y}</b><br>Capacidad total: <b>%{x:,.0f} MW</b><br>"
            "N° proyectos: %{customdata[0]}<br>"
            "Promedio por proyecto: %{customdata[1]:,.0f} MW<extra></extra>"
        ),
        text=[f"{v:,.0f} MW" for v in resumen.mw_total],
        textposition="outside", textfont=dict(size=11, color="#e0e8f0"),
    ))
    fig.update_layout(
        title=dict(
            text="<b>Capacidad solar planificada UPME por región natural</b><br>"
                 f"<sup>Proyectos fotovoltaicos registrados 2024–2026 · Total: {resumen.mw_total.sum():,.0f} MW</sup>",
            x=0.5, xanchor="center", font=dict(size=14),
        ),
        xaxis=dict(title="MW totales planificados", gridcolor="#eeeeee",
                   range=[0, resumen.mw_total.max() * 1.18]),
        yaxis=dict(title=""),
        plot_bgcolor="white", paper_bgcolor="white",
        height=360, margin=dict(l=110, r=60, t=90, b=60),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    _dark_layout(fig)
    return fig


def build_fig07b(df_solar):
    """Donut de proyectos solares UPME por fase."""
    GAP_RED_LOCAL = "#EF233C"
    fases = (
        df_solar.groupby("estado")
        .agg(mw=("capacidad_mw", "sum"), n=("capacidad_mw", "count"))
        .reset_index().sort_values("mw", ascending=False)
    )
    total_mw = fases.mw.sum()
    colores_fase = {"FASE 1": "#06D6A0", "FASE 2": SOLAR_ORANGE, "FASE 3": GAP_RED_LOCAL}
    fig = go.Figure(go.Pie(
        labels=fases.estado, values=fases.mw, hole=0.55,
        marker=dict(
            colors=[colores_fase.get(e, "#BBBBBB") for e in fases.estado],
            line=dict(color="white", width=2),
        ),
        textinfo="label+percent", textfont=dict(size=13),
        customdata=fases.n.astype(int).tolist(),
        hovertemplate=(
            "<b>%{label}</b><br>Capacidad: <b>%{value:,.0f} MW</b><br>"
            "Participación: <b>%{percent}</b><br>N° proyectos: %{customdata}<extra></extra>"
        ),
    ))
    fig.add_annotation(
        text=f"<b>{total_mw:,.0f}</b><br>MW totales",
        x=0.5, y=0.5, showarrow=False, font=dict(size=15, color="#ffffff"),
        xanchor="center", yanchor="middle",
    )
    fig.update_layout(
        title=dict(
            text="<b>Proyectos solares UPME por fase de madurez</b><br>"
                 "<sup>Fase 3 = listo para operar · Fase 2 = en desarrollo · Fase 1 = inscrito</sup>",
            x=0.5, xanchor="center", font=dict(size=14),
        ),
        plot_bgcolor="white", paper_bgcolor="white",
        height=420, margin=dict(l=30, r=30, t=90, b=40),
        showlegend=True,
        legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center"),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    _dark_layout(fig)
    return fig


def build_fig10(df_nasa, df_solar):
    """Brecha regional: recurso solar vs. capacidad planificada."""
    irr = (
        df_nasa[df_nasa.region_natural != "Insular"]
        .groupby("region_natural")["irradiancia_global"]
        .mean().reset_index().rename(columns={"irradiancia_global": "irr_media"})
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
        if r.mw_total == 0:           return ("Sin prioridad",    "#BBBBBB")
        if r.irr_media >= 4.7 and r.mw_total < 1000:
                                       return ("Brecha critica",   "#EF233C")
        if r.mw_total > 2000 and r.irr_media < 4.7:
                                       return ("Sobreplanificada", "#3A86FF")
        return ("Bien aprovechada", "#06D6A0")

    panel[["clasificacion", "color"]] = panel.apply(clasificar, axis=1, result_type="expand")
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
        customdata=list(zip(panel.n_proy.fillna(0).astype(int))),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Capacidad planificada: <b>%{y:,.0f} MW</b><br>"
            "N° proyectos: %{customdata[0]}"
            "<extra></extra>"
        ),
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
                 "<sup>Barras naranjas: irradiancia media 2024–2026 (eje izq.)  ·  "
                 "Barras azules: MW UPME (eje der.)  ·  Insular excluida</sup>",
            x=0.5, xanchor="center", font=dict(size=14),
        ),
        barmode="overlay", plot_bgcolor="white", paper_bgcolor="white",
        height=460, margin=dict(l=70, r=70, t=100, b=60),
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    fig.update_yaxes(title_text="Irradiancia media diaria (kWh/m²/día)",
                     secondary_y=False, gridcolor="#eeeeee", range=[3.5, 6.2])
    fig.update_yaxes(title_text="Capacidad solar planificada UPME (MW)",
                     secondary_y=True, gridcolor="#eeeeee", range=[0, 4800])
    _dark_layout(fig)
    return fig


def build_fig11(df_nasa, df_solar):
    """Cuadrante potencial solar vs. inversión UPME por municipio."""
    irr_muni = (
        df_nasa.groupby(["id_municipio", "municipio", "departamento", "region_natural"])
        ["irradiancia_global"].mean().reset_index()
        .rename(columns={"irradiancia_global": "irr_media"})
    )
    upme_muni = (
        df_solar.groupby("id_municipio")
        .agg(mw_solar=("capacidad_mw", "sum"), n_proy=("capacidad_mw", "count"))
        .reset_index()
    )
    pm = irr_muni.merge(upme_muni, on="id_municipio", how="left").fillna(0)
    med_irr = pm.irr_media.median()
    med_mw  = pm[pm.mw_solar > 0].mw_solar.median()

    def quadrant(r):
        hi_irr = r.irr_media >= med_irr
        hi_mw  = r.mw_solar  >= med_mw
        if hi_irr and not hi_mw:  return "Brecha critica"
        if hi_irr and hi_mw:      return "Bien aprovechado"
        if not hi_irr and hi_mw:  return "Sobreplanificado"
        return "Sin prioridad"

    pm["quad"] = pm.apply(quadrant, axis=1)
    rng = np.random.default_rng(42)
    pm["mw_plot"]  = pm.mw_solar.astype(float)
    pm["irr_plot"] = pm.irr_media.astype(float)
    mask0 = pm.mw_solar == 0
    n0    = mask0.sum()
    pm.loc[mask0, "mw_plot"]  = rng.uniform(1, 65, n0)
    pm.loc[mask0, "irr_plot"] = pm.loc[mask0, "irr_media"] + rng.uniform(-0.025, 0.025, n0)

    QUAD_CFG = {
        "Brecha critica":   {"color": GAP_RED,   "symbol": "circle-open", "size": 10, "lcolor": "#c00020"},
        "Bien aprovechado": {"color": "#06D6A0", "symbol": "circle",      "size": 9,  "lcolor": "#007a50"},
        "Sobreplanificado": {"color": UPME_BLUE, "symbol": "diamond",     "size": 9,  "lcolor": "#1a3fa0"},
        "Sin prioridad":    {"color": "#BBBBBB", "symbol": "circle",      "size": 7,  "lcolor": "#888888"},
    }
    xmin = pm.irr_media.min() - 0.06
    xmax = pm.irr_media.max() + 0.06
    ymax = pm.mw_solar.max() * 1.2

    fig = go.Figure()
    for coords, fc in [
        (dict(x0=med_irr, x1=xmax,    y0=0.5,    y1=med_mw), "rgba(239,35,60,0.06)"),
        (dict(x0=med_irr, x1=xmax,    y0=med_mw, y1=ymax),   "rgba(6,214,160,0.06)"),
        (dict(x0=xmin,    x1=med_irr, y0=med_mw, y1=ymax),   "rgba(58,134,255,0.06)"),
        (dict(x0=xmin,    x1=med_irr, y0=0.5,    y1=med_mw), "rgba(187,187,187,0.07)"),
    ]:
        fig.add_shape(type="rect", layer="below", fillcolor=fc, line_width=0, **coords)

    fig.add_vline(x=med_irr, line_dash="dash", line_color="#aaa", line_width=1.2)
    fig.add_hline(y=med_mw,  line_dash="dash", line_color="#aaa", line_width=1.2)
    fig.add_annotation(x=med_irr, y=1200, xanchor="right",
        text=f"Mediana irr. {med_irr:.2f} kWh/m²/d",
        showarrow=False, font=dict(size=9, color="#888"), xshift=-5)
    fig.add_annotation(x=xmin + 0.01, y=med_mw * 1.15, yanchor="bottom",
        text=f"Umbral {med_mw:.0f} MW",
        showarrow=False, font=dict(size=9, color="#888"), xanchor="left")
    fig.add_annotation(x=xmax - 0.01, y=15, xanchor="right", yanchor="middle",
        text="<b>Brecha critica</b>", showarrow=False, font=dict(size=12, color="#ff6b7a"))
    fig.add_annotation(x=xmax - 0.01, y=1000, xanchor="right", yanchor="top",
        text="<b>Bien aprovechado</b>", showarrow=False, font=dict(size=12, color="#06D6A0"))
    fig.add_annotation(x=xmin + 0.01, y=1000, xanchor="left", yanchor="top",
        text="<b>Sobreplanificado</b>", showarrow=False, font=dict(size=12, color="#7aaeff"))
    fig.add_annotation(x=xmin + 0.01, y=15, xanchor="left", yanchor="middle",
        text="<b>Sin prioridad</b>", showarrow=False, font=dict(size=12, color="#b0b8c8"))

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

    for _, r in pm[pm.quad == "Brecha critica"].nlargest(8, "irr_media").iterrows():
        fig.add_annotation(x=r.irr_plot, y=r.mw_plot, text=f"  {r.municipio.title()}",
            showarrow=False, xanchor="left", yanchor="middle",
            font=dict(size=9, color="#ff6b7a"))
    for _, r in pm[pm.quad == "Bien aprovechado"].nlargest(5, "mw_solar").iterrows():
        fig.add_annotation(x=r.irr_plot, y=r.mw_plot, text=f"  {r.municipio.title()}",
            showarrow=False, xanchor="left", yanchor="middle",
            font=dict(size=9, color="#06D6A0"))

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
        height=560, margin=dict(l=70, r=30, t=100, b=80),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    _dark_layout(fig)
    return fig


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CABECERA HERO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown(
    """
    <section class="solar-hero">
        <h2>SolarTech Colombia — Análisis de Potencial Solar</h2>
        <p>
            Exploración territorial del recurso solar, análisis de brecha entre
            potencial NASA y proyectos UPME, y cargue operativo de datos en tiempo real.
        </p>
    </section>
    """,
    unsafe_allow_html=True,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PESTAÑAS PRINCIPALES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TAB_EXPLORADOR, TAB_BRECHA, TAB_ANEXO = st.tabs([
    "Explorador Solar Nacional",
    "Análisis de Brecha",
    "Anexo Técnico",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — EXPLORADOR SOLAR NACIONAL
# ════════════════════════════════════════════════════════════════════════════
with TAB_EXPLORADOR:
    # ── Barra lateral ──────────────────────────────────────────────────────
    df_geo = cargar_parametros_geograficos()
    st.sidebar.markdown("### Filtros de ubicacion")

    if not df_geo.empty:
        lista_deps = sorted(df_geo["departamento"].dropna().unique())
        dep_sel = st.sidebar.selectbox("Departamento", lista_deps)
        df_muns = df_geo[df_geo["departamento"] == dep_sel]
        lista_muns = sorted(df_muns["municipio"].dropna().unique())
        mun_sel = st.sidebar.selectbox("Municipio / Ciudad", lista_muns)
        datos_mun = df_muns[df_muns["municipio"] == mun_sel].iloc[0]
        lat_mun, lon_mun = float(datos_mun["latitud"]), float(datos_mun["longitud"])
        id_municipio_sel = int(datos_mun["id_municipio"])
    else:
        lat_mun, lon_mun, dep_sel, mun_sel, id_municipio_sel = 6.2442, -75.5812, "Antioquia", "Medellin", None

    st.sidebar.markdown("### Rango de fechas")
    fecha_desde = st.sidebar.date_input("Desde", datetime(2026, 1, 1), format="DD/MM/YYYY")
    fecha_hasta = st.sidebar.date_input("Hasta", datetime(2026, 3, 31), format="DD/MM/YYYY")

    st.sidebar.markdown("### Parametros de consulta")
    variables_sel = st.sidebar.multiselect(
        "Variables analiticas", options=list(MAPEO_VARIABLES.keys()),
        default=list(MAPEO_VARIABLES.keys())[:2],
    )
    st.sidebar.markdown("---")
    btn_sincronizar = st.sidebar.button("Sincronizar y analizar", use_container_width=True, type="primary")

    # ── Sub-pestañas del explorador ─────────────────────────────────────────
    sub_analisis, sub_proyectos, sub_upme = st.tabs([
        "Análisis NASA POWER",
        "Proyectos actuales según UPME",
        "Cargue proyectos UPME XLSX",
    ])

    # ── Sub-tab: Análisis NASA POWER ────────────────────────────────────────
    with sub_analisis:
        st.markdown(
            f"""
            <div class="metric-band">
                <div class="metric-tile"><span>Departamento</span><strong>{dep_sel}</strong></div>
                <div class="metric-tile"><span>Municipio</span><strong>{mun_sel}</strong></div>
                <div class="metric-tile"><span>Coordenadas</span><strong>{lat_mun:.4f}, {lon_mun:.4f}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        df_mapa = pd.DataFrame({"lat": [lat_mun], "lon": [lon_mun]})
        st.map(df_mapa, zoom=11, use_container_width=True)

        if btn_sincronizar:
            st.markdown("---")
            st.subheader(f"Resultados del análisis en {mun_sel}, {dep_sel}")
            if not variables_sel:
                st.warning("Selecciona al menos una variable en el panel lateral.")
            elif fecha_desde > fecha_hasta:
                st.warning("La fecha inicial no puede ser posterior a la fecha final.")
            else:
                codigos_nasa = [MAPEO_VARIABLES[l]["nasa"] for l in variables_sel]
                url_api = (
                    "https://power.larc.nasa.gov/api/temporal/daily/point"
                    f"?parameters={','.join(codigos_nasa)}&community=RE"
                    f"&longitude={lon_mun}&latitude={lat_mun}"
                    f"&start={fecha_desde.strftime('%Y%m%d')}&end={fecha_hasta.strftime('%Y%m%d')}&format=JSON"
                )
                try:
                    with st.spinner("Sincronizando con la grilla satelital de NASA POWER...", show_time=True):
                        time.sleep(0.2)
                        response = requests.get(url_api, timeout=45)
                        response.raise_for_status()
                        json_data = response.json()

                    props  = json_data["properties"]["parameter"]
                    fechas = list(props[codigos_nasa[0]].keys())
                    rows = []
                    for f in fechas:
                        row = {"id_municipio": id_municipio_sel,
                               "fecha": pd.to_datetime(f, format="%Y%m%d").date()}
                        for lbl in variables_sel:
                            cod = MAPEO_VARIABLES[lbl]["nasa"]
                            col = MAPEO_VARIABLES[lbl]["col_bd"]
                            val = props[cod][f]
                            row[col] = val if val >= 0 else np.nan
                        rows.append(row)
                    df_res = pd.DataFrame(rows)

                    st.markdown("#### Valores promedio del periodo")
                    cols = st.columns(len(variables_sel))
                    for i, lbl in enumerate(variables_sel):
                        col = MAPEO_VARIABLES[lbl]["col_bd"]
                        uni = MAPEO_VARIABLES[lbl]["unidad"]
                        prom = df_res[col].mean()
                        with cols[i]:
                            st.metric(lbl, "No disp." if pd.isna(prom) else round(prom, 2), delta=uni)

                    st.markdown("#### Análisis y Comportamiento Temporal")
                    with st.container(border=True):
                        st.markdown("**Vista Comparativa**")
                        st.caption("Identifica correlaciones entre múltiples variables en un mismo eje de tiempo.")
                        cols_graf = [MAPEO_VARIABLES[l]["col_bd"] for l in variables_sel]
                        st.line_chart(df_res.set_index("fecha")[cols_graf],
                                      x_label="Fecha", y_label="Valor General")
                    st.write("")
                    with st.container(border=True):
                        st.markdown("**Vista Individual por variable**")
                        st.caption("Tendencia aislada de cada variable respetando su escala y unidad.")
                        pestanas = st.tabs(variables_sel)
                        for i, lbl in enumerate(variables_sel):
                            col = MAPEO_VARIABLES[lbl]["col_bd"]
                            with pestanas[i]:
                                st.line_chart(data=df_res, x="fecha", y=col,
                                              use_container_width=True)

                    st.markdown("---")
                    st.subheader("Conclusión técnica de viabilidad solar")
                    col_irr = MAPEO_VARIABLES[emoji.emojize(":sun: Irradiancia Global (kWh/m2/dia)")]["col_bd"]
                    irr_media = df_res[col_irr].mean() if col_irr in df_res.columns else np.nan
                    with st.expander("Ver reporte de viabilidad detallado", expanded=True):
                        irr_fmt = round(irr_media, 2)
                        if pd.isna(irr_media) or irr_media <= 0:
                            st.error("No se registran mediciones válidas de irradiancia para el periodo seleccionado.")
                        elif irr_media >= 5.5:
                            st.success(f"**VIABILIDAD EXCEPCIONAL** — {irr_fmt} kWh/m²/día. Zona de clase mundial, ideal para centrales fotovoltaicas de gran escala.")
                        elif irr_media >= 4.5:
                            st.success(f"**VIABILIDAD ALTA** — {irr_fmt} kWh/m²/día. Recurso altamente competitivo y estable para autogeneración comercial e industrial.")
                        elif irr_media >= 3.8:
                            st.info(f"**VIABILIDAD MODERADA-ALTA** — {irr_fmt} kWh/m²/día. Viable para sistemas fotovoltaicos conectados a red en hogares y comercios.")
                        elif irr_media >= 3.0:
                            st.warning(f"**VIABILIDAD MODERADA** — {irr_fmt} kWh/m²/día. Recomendable usar paneles de alta eficiencia y realizar análisis de sombras.")
                        else:
                            st.error(f"**VIABILIDAD BAJA** — {irr_fmt} kWh/m²/día. Recurso limitado; considerar sistemas híbridos como complemento.")
                except Exception as exc:
                    st.error(f"Error de enlace con NASA POWER: {exc}")

    # ── Sub-tab: Proyectos UPME ─────────────────────────────────────────────
    with sub_proyectos:
        st.subheader("Proyectos UPME cargados en la base de datos")
        with st.spinner("Consultando proyectos UPME...", show_time=True):
            df_proy = cargar_proyectos_upme()
        tiene_datos = not df_proy.empty

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Actualizar datos UPME", use_container_width=True):
                cargar_proyectos_upme.clear()
                st.rerun()
        with c2:
            if st.button("Insertar datos de prueba", use_container_width=True, disabled=tiene_datos):
                st.info("Carga un archivo XLSX en la pestaña 'Cargue proyectos UPME XLSX' para poblar la tabla.")

        if df_proy.empty:
            st.info("La tabla UPME existe pero aún no tiene registros. Carga un XLSX en la pestaña de cargue.")
        else:
            df_v = df_proy.copy()
            df_v["capacidad_mw"] = pd.to_numeric(df_v["capacidad_mw"], errors="coerce")
            cf1, cf2, cf3 = st.columns(3)
            with cf1:
                deps = sorted(df_v["departamento"].dropna().unique())
                deps_s = st.multiselect("Departamento", deps, default=deps)
            with cf2:
                ests = sorted(df_v["estado"].dropna().unique())
                ests_s = st.multiselect("Estado", ests, default=ests)
            with cf3:
                recs = sorted(df_v["recurso"].dropna().unique())
                recs_s = st.multiselect("Recurso", recs, default=recs)
            if deps_s: df_v = df_v[df_v["departamento"].isin(deps_s)]
            if ests_s: df_v = df_v[df_v["estado"].isin(ests_s)]
            if recs_s: df_v = df_v[df_v["recurso"].isin(recs_s)]
            cap = df_v["capacidad_mw"].sum(min_count=1)
            st.markdown(
                f"""
                <div class="metric-band">
                    <div class="metric-tile"><span>Proyectos visibles</span><strong>{len(df_v)}</strong></div>
                    <div class="metric-tile"><span>Capacidad total</span><strong>{0 if pd.isna(cap) else round(cap,2)} MW</strong></div>
                    <div class="metric-tile"><span>Municipios</span><strong>{df_v["municipio"].nunique()}</strong></div>
                </div>
                """, unsafe_allow_html=True,
            )
            cols_tabla = ["codigo_proyecto", "nombre_proyecto", "estado", "recurso",
                          "capacidad_mw", "departamento", "municipio",
                          "fecha_inicio_construccion", "fecha_estimada_operacion"]
            st.dataframe(df_v[[c for c in cols_tabla if c in df_v.columns]],
                         use_container_width=True, hide_index=True)
            df_mapa_u = df_v.dropna(subset=["latitud","longitud"]).copy()
            if not df_mapa_u.empty:
                df_mapa_u["lat"] = pd.to_numeric(df_mapa_u["latitud"], errors="coerce")
                df_mapa_u["lon"] = pd.to_numeric(df_mapa_u["longitud"], errors="coerce")
                df_mapa_u = df_mapa_u.dropna(subset=["lat","lon"])
                if not df_mapa_u.empty:
                    st.markdown("#### Ubicación de proyectos con coordenadas")
                    st.map(df_mapa_u[["lat","lon"]], zoom=5, use_container_width=True)

    # ── Sub-tab: Cargue XLSX ─────────────────────────────────────────────────
    with sub_upme:
        st.subheader("Cargue de proyectos UPME desde XLSX")
        st.write("Descarga la plantilla, completa los registros y sube el archivo para validar el contenido antes de enviarlo.")
        st.download_button(
            "Descargar plantilla XLSX", data=crear_plantilla_upme(),
            file_name="plantilla_cargue_upme.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.markdown("<p>Examinar archivo XLSX</p>", unsafe_allow_html=True)
        archivo_upme = st.file_uploader("", type=["xlsx"]   , label_visibility="collapsed")
        if archivo_upme is not None:
            try:
                with st.spinner("Validando estructura UPME...", show_time=True):
                    df_orig = pd.read_excel(archivo_upme)
                    df_upme = preparar_dataframe_upme(archivo_upme, df_geo)
                    df_upme.index = df_orig.index
                st.success(f"Archivo válido: {len(df_upme)} registros listos para cargar.")
                sin_mun = df_upme["id_municipio"].isna().sum()
                if sin_mun:
                    st.warning(f"{sin_mun} registros no pudieron asociarse a un municipio. Se cargarán con id_municipio vacío.")
                else:
                    st.success("Todos los registros se asociaron geográficamente.")
                st.markdown("### Vista previa:")
                st.dataframe(df_upme.head(50), use_container_width=True, hide_index=True)
                if st.button("Guardar registros UPME en la base de datos", use_container_width=True):
                    with st.spinner("Cargando en Supabase...", show_time=True):
                        guardar_upme_en_bd(df_upme)
                    st.success(f"Cargue completado: {len(df_upme)} registros insertados.")
                    time.sleep(1); st.rerun()
            except Exception as exc:
                st.error(f"No fue posible procesar el archivo: {exc}")


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — ANÁLISIS DE BRECHA
# ════════════════════════════════════════════════════════════════════════════
with TAB_BRECHA:
    df_nasa, df_solar = cargar_datos_brecha()

    if df_nasa is None:
        st.error(
            "No se encontró la base de datos local en `data/potencial_solar.db`. "
            "Asegúrate de incluir el archivo en el repositorio."
        )
    else:
        # ════════════════════════════════════════════════════════════════
        # CONTEXTO
        # ════════════════════════════════════════════════════════════════
        st.markdown('<p class="seccion-titulo">Contexto</p>', unsafe_allow_html=True)
        st.markdown("""
        Colombia ha dependido históricamente de la generación hidráulica, que representa el **63,7%** de
        su capacidad instalada total (20.763 MW). Esta dependencia hace que el sistema sea vulnerable a
        fenómenos como El Niño, que reducen los caudales y la capacidad de generación durante períodos
        prolongados. En respuesta, la energía solar fotovoltaica emergió como alternativa estratégica:
        de apenas **277 MW** operativos en enero de 2023, Colombia superó **1 GW instalado** en julio de
        2024, alcanzando 1.193 MW — un crecimiento del 330% en 18 meses.

        Este dinamismo responde al **Plan 6GW+** del Gobierno del Cambio y al **Plan de Expansión
        2023–2037** de la UPME, que contempla entre 7,4 y 11,4 GW de capacidad solar para 2037. Sin
        embargo, el crecimiento no ha sido homogéneo: la geografía colombiana genera condiciones de
        irradiancia muy distintas entre regiones, y la planificación de proyectos no siempre sigue al
        recurso disponible.
        """)

        st.markdown("""
        <div class="pregunta-card">
            <div class="pq-label">Pregunta central del proyecto</div>
            <p>¿Existe correspondencia entre las zonas de mayor potencial de irradiancia solar histórica
            en Colombia (2024–2026) y la distribución geográfica de los proyectos fotovoltaicos
            registrados ante la UPME? ¿Qué regiones presentan la mayor brecha entre el recurso
            disponible y la planificación actual?</p>
        </div>
        """, unsafe_allow_html=True)

        # ════════════════════════════════════════════════════════════════
        # LOS DATOS
        # ════════════════════════════════════════════════════════════════
        st.markdown('<p class="seccion-titulo">Los datos del análisis</p>', unsafe_allow_html=True)

        n_muns      = df_nasa["id_municipio"].nunique()
        n_deps      = df_nasa["departamento"].nunique()
        n_medic     = len(df_nasa)
        n_proy      = len(df_solar)
        mw_total    = df_solar["capacidad_mw"].sum()

        st.markdown(
            f"""
            <div class="kpi-band">
                <div class="kpi-tile">
                    <div class="kpi-num">{n_deps}</div>
                    <div class="kpi-lbl">Departamentos</div>
                </div>
                <div class="kpi-tile">
                    <div class="kpi-num">{n_muns}</div>
                    <div class="kpi-lbl">Municipios analizados</div>
                </div>
                <div class="kpi-tile">
                    <div class="kpi-num">{n_medic:,}</div>
                    <div class="kpi-lbl">Mediciones NASA POWER</div>
                </div>
                <div class="kpi-tile">
                    <div class="kpi-num">{n_proy}</div>
                    <div class="kpi-lbl">Proyectos UPME · {mw_total:,.0f} MW</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("Ver metodología de recolección de datos"):
            st.markdown("""
            **Fuente primaria — NASA POWER**

            Los datos provienen del endpoint `temporal/daily/point` de la API NASA POWER (comunidad
            Renewable Energy). La resolución espacial es de 0,5° × 0,5° (~55 km × 55 km): municipios
            separados por menos de esta distancia comparten el mismo valor de irradiancia (mismo
            "píxel"). Los 88 municipios del panel se agrupan en **63 píxeles únicos**, cada uno
            consultado una sola vez para garantizar eficiencia y consistencia.

            - **Período**: 2024-01-01 al 2026-05-09 (860 días) · Completitud: 99,9%
            - **Variables**: Irradiancia (ALLSKY_SFC_SW_DWN), Temperatura (T2M), Humedad (RH2M),
              Viento (WS2M), Precipitación (PRECTOTCORR)

            **Fuente secundaria — UPME**

            Informe de Registros Activos de Proyectos de Generación Eléctrica (corte marzo 2026).
            72 proyectos solares fotovoltaicos con capacidad nominal de 7.155,55 MW en 18 departamentos.
            Esta cifra representa la **cartera registrada**, no la capacidad operativa efectiva
            (~1.193 MW a julio de 2024). La base de datos SQLite integra ambas fuentes en un modelo
            relacional de 7 tablas.
            """)

        st.divider()

        # ════════════════════════════════════════════════════════════════
        # SECCIÓN 1: EL RECURSO SOLAR
        # ════════════════════════════════════════════════════════════════
        st.markdown('<p class="seccion-titulo">El recurso solar en Colombia</p>', unsafe_allow_html=True)
        st.markdown("""
        El primer paso es caracterizar la disponibilidad del recurso solar en el territorio. Con
        74.984 mediciones diarias, el promedio nacional es de **4,808 kWh/m²/día** (rango: 0,299 – 7,67).
        La distribución no es homogénea: la geografía y el clima generan diferencias marcadas entre
        regiones que son determinantes para identificar dónde tiene sentido desarrollar proyectos
        solares a gran escala.
        """)

        st.markdown("**Figura 1 — Distribución de irradiancia por región natural (2024–2026)**")
        st.markdown(
            '<p class="fig-caption">El ancho de cada caja muestra la dispersión de mediciones diarias; '
            'la línea central es la mediana. Mayor caja = mayor variabilidad climática en esa región.</p>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(build_fig03(df_nasa), use_container_width=True)

        st.markdown("""
        <div class="insight-card">
            <div class="ins-label">Análisis</div>
            <p>La región <strong>Caribe</strong> tiene la irradiancia mediana más alta (~5,2 kWh/m²/día)
            y la menor variabilidad relativa, lo que la hace ideal para proyectos de gran escala con
            alta predictibilidad de generación. La región <strong>Pacífica</strong> muestra los valores
            más bajos (~4,1 kWh/m²/día) con alta dispersión, consecuencia de su régimen intenso de
            lluvias. La región <strong>Andina</strong>, donde se concentra la mayor parte de la demanda
            energética del país, tiene un recurso moderado pero completamente viable para proyectos
            fotovoltaicos conectados a red.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Figura 2 — Top 15 municipios por irradiancia media (2024–2026)**")
        st.markdown(
            '<p class="fig-caption">Los municipios con ★ tienen al menos un proyecto fotovoltaico '
            'registrado ante la UPME. El color indica la región natural del municipio.</p>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(build_fig02(df_nasa, df_solar), use_container_width=True)

        st.markdown("""
        <div class="insight-card">
            <div class="ins-label">Análisis</div>
            <p>Los 15 municipios con mayor irradiancia pertenecen casi exclusivamente a la región Caribe.
            <strong>Santa Marta</strong> (5,76 kWh/m²/día) y <strong>Riohacha</strong> (5,61 kWh/m²/día)
            lideran el ranking nacional. Varios de los municipios con mayor recurso no tienen proyectos
            UPME registrados (sin ★), lo que anticipa la brecha que se analiza en la Sección 3.
            Barranquilla, Tubará y varios municipios del Magdalena comparten el mismo valor de
            irradiancia por estar dentro del mismo píxel NASA de 0,5°.</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ════════════════════════════════════════════════════════════════
        # SECCIÓN 2: LOS PROYECTOS UPME
        # ════════════════════════════════════════════════════════════════
        st.markdown('<p class="seccion-titulo">Los proyectos solares UPME registrados</p>', unsafe_allow_html=True)
        st.markdown("""
        La UPME registra proyectos fotovoltaicos en tres fases del ciclo de desarrollo:
        Fase 1 (inscripción inicial), Fase 2 (con resolución de conexión) y Fase 3 (avanzada hacia
        operación). La cartera analizada —corte marzo 2026— contiene **72 proyectos solares** con
        una capacidad nominal agregada de **7.155,55 MW** en 18 departamentos. Es crucial distinguir
        esta cifra de la capacidad efectivamente operativa (~1.193 MW): la cartera es en su mayor parte
        **prospectiva**, no instalada.
        """)

        # ── Top 10 departamentos ─────────────────────────────────────────
        top_dep = (
            df_solar.groupby("departamento")
            .agg(
                Proyectos=("capacidad_mw", "count"),
                mw=("capacidad_mw", "sum"),
                Región=("region_natural", "first"),
            )
            .reset_index()
            .sort_values("mw", ascending=False)
            .head(10)
        )
        top_dep["Capacidad (MW)"] = top_dep["mw"].apply(lambda x: f"{x:,.2f}")
        top_dep = top_dep.rename(columns={"departamento": "Departamento"})
        top_dep["Departamento"] = top_dep["Departamento"].str.title()
        top_dep["Región"]       = top_dep["Región"].str.title()
        top_dep = top_dep[["Departamento", "Región", "Proyectos", "Capacidad (MW)"]]

        st.markdown("**Tabla 1 — Top 10 departamentos por capacidad solar registrada (UPME, marzo 2026)**")
        st.dataframe(top_dep, use_container_width=True, hide_index=True)

        st.markdown("")
        st.markdown("**Figura 3 — Capacidad solar planificada UPME por región natural**")
        st.markdown(
            '<p class="fig-caption">Pasa el cursor sobre cada barra para ver número de proyectos '
            'y capacidad media por proyecto.</p>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(build_fig07a(df_solar), use_container_width=True)

        st.markdown("**Figura 4 — Proyectos solares UPME por fase de madurez**")
        st.markdown(
            '<p class="fig-caption">Fase 3 = avanzada hacia operación · '
            'Fase 2 = resolución de conexión aprobada · Fase 1 = inscripción inicial</p>',
            unsafe_allow_html=True,
        )
        col_izq, col_centro, col_der = st.columns([1, 2, 1])
        with col_centro:
            st.plotly_chart(build_fig07b(df_solar), use_container_width=True)

        st.markdown("""
        <div class="insight-card">
            <div class="ins-label">Análisis</div>
            <p><strong>Córdoba</strong> concentra el 28% de toda la capacidad solar registrada (2.017 MW
            en 18 proyectos), seguido de <strong>La Guajira</strong> (835 MW) y <strong>Tolima</strong>
            (739 MW). El <strong>80% de los MW están en Fase 2</strong> — con resolución de conexión
            pero sin fecha de construcción confirmada. Solo 4 proyectos del total están en Fase 3
            (avanzada hacia operación), acumulando 309 MW. Esto confirma que la cartera analizada es
            fundamentalmente una apuesta de inversión, no capacidad instalada.</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ════════════════════════════════════════════════════════════════
        # SECCIÓN 3: LA BRECHA
        # ════════════════════════════════════════════════════════════════
        st.markdown('<p class="seccion-titulo">La brecha entre potencial y aprovechamiento</p>', unsafe_allow_html=True)
        st.markdown("""
        El análisis central del proyecto cruza las dos fuentes de datos para responder la pregunta
        principal: ¿la inversión en proyectos solares sigue al recurso disponible, o existen otros
        factores —infraestructura de red, cercanía a centros de demanda, disponibilidad de tierras—
        que orientan la planificación? Se construyeron dos visualizaciones complementarias: una
        comparación a escala **regional** y un análisis de cuadrantes a escala **municipal**.
        """)

        st.markdown("**Figura 5 — Recurso solar vs. capacidad planificada UPME por región**")
        st.markdown(
            '<p class="fig-caption">Barras naranjas: irradiancia media diaria (eje izquierdo) · '
            'Barras azules: MW UPME planificados (eje derecho) · Región Insular excluida por '
            'tamaño muestral reducido.</p>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(build_fig10(df_nasa, df_solar), use_container_width=True)

        st.markdown("""
        <div class="insight-card">
            <div class="ins-label">Análisis</div>
            <p>La región <strong>Caribe</strong> combina el mayor recurso solar (~5,2 kWh/m²/día)
            con la mayor inversión planificada (>4.500 MW) — clasificada como <em>bien aprovechada</em>.
            La región <strong>Orinoquía</strong> presenta alta irradiancia pero baja inversión registrada
            (~500 MW) — una <em>brecha crítica</em> que sugiere potencial no explotado, posiblemente
            por barreras de conexión al Sistema Interconectado Nacional. La región <strong>Andina</strong>,
            con recurso moderado, concentra una fracción importante del pipeline, impulsada
            probablemente por su cercanía a los grandes centros de demanda energética del país.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Figura 6 — Potencial solar vs. inversión UPME por municipio (cuadrantes)**")
        st.markdown("""
        Los ejes de referencia son estadísticos y emergen de los propios datos. El eje X usa la
        **mediana nacional de irradiancia** (4,816 kWh/m²/día), que separa zonas de recurso alto y bajo.
        El eje Y usa la **mediana de capacidad de los municipios que sí tienen proyectos UPME** (~100 MW):
        se prefiere la mediana sobre la media porque la media estaría inflada por megaproyectos como
        Córdoba (2.017 MW), lo que desplazaría artificialmente el umbral y haría que la mayoría de
        municipios cayeran en «brecha crítica». Con la mediana, cada cuadrante captura aproximadamente
        el mismo número de municipios con inversión.
        """)
        st.markdown(
            '<p class="fig-caption">El eje Y usa escala logarítmica para separar visualmente municipios '
            'con proyectos pequeños de los grandes. Los municipios sin proyectos UPME tienen MW = 0 en '
            'la realidad; se muestran desplazados verticalmente de forma aleatoria para que sean '
            'visibles en la escala logarítmica — pasa el cursor sobre ellos para confirmar su valor real.</p>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(build_fig11(df_nasa, df_solar), use_container_width=True)

        st.markdown("""
        <div class="insight-card">
            <div class="ins-label">Análisis</div>
            <p>De los 88 municipios analizados, <strong>28 están en brecha crítica</strong> — alta
            irradiancia pero sin inversión suficiente. <strong>35 municipios no tienen ningún proyecto
            UPME registrado</strong> (sin prioridad). Solo <strong>16 municipios</strong> combinan buen
            recurso solar con inversión relevante (bien aprovechados), concentrados principalmente en
            Córdoba, La Guajira y el Atlántico. Los <strong>9 municipios sobreplanificados</strong>
            tienen proyectos de gran escala pese a un recurso solar por debajo de la mediana nacional,
            lo que puede implicar menor rentabilidad por MW instalado.</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ════════════════════════════════════════════════════════════════
        # HALLAZGOS E INTERPRETACIÓN
        # ════════════════════════════════════════════════════════════════
        st.markdown('<p class="seccion-titulo">Hallazgos e interpretación</p>', unsafe_allow_html=True)

        st.markdown("""
        1. **La región Caribe es el epicentro solar de Colombia.** Municipios como Santa Marta, Riohacha
           y Barranquilla combinan irradiancia superior a 5,5 kWh/m²/día con proyectos UPME
           consolidados. Córdoba, con 2.017 MW en 18 proyectos, concentra el 28% de toda la cartera
           solar nacional.

        2. **Existe correspondencia parcial, no total, entre recurso y planificación.** La región
           Caribe muestra alineación clara. Sin embargo, la Orinoquía (con buen recurso y solo ~500 MW
           planificados) y municipios de la región Andina presentan brechas que no responden al recurso
           disponible, sino a otros factores estructurales.

        3. **35 municipios del panel no tienen ningún proyecto UPME registrado.** Esto no implica
           inviabilidad — puede reflejar barreras de acceso al Sistema Interconectado Nacional,
           disponibilidad de tierras o ausencia de gestión de proyectos.

        4. **La cartera UPME es fundamentalmente prospectiva.** El 80% de los proyectos están en
           Fase 2 y el 14% en Fase 1. La diferencia entre los 7.155 MW registrados y los ~1.193 MW
           operativos ilustra la brecha entre intención y ejecución en el sector energético.

        5. **Correlación negativa entre irradiancia y humedad/precipitación (r ≈ −0,6 / −0,4).**
           Confirma el efecto de la nubosidad sobre la disponibilidad del recurso y valida la
           coherencia de los datos NASA POWER con el conocimiento geográfico del país.
        """)

        with st.expander("Conclusiones y recomendaciones"):
            st.markdown("""
            **Conclusiones**

            El análisis integrado de datos satelitales NASA POWER y la cartera UPME confirma que la
            distribución de la inversión solar en Colombia está **parcialmente alineada** con el recurso
            disponible. La región Caribe muestra el mejor aprovechamiento. La Orinoquía y varios
            municipios de la región Andina representan oportunidades no explotadas. La cartera
            registrada, si bien ambiciosa en volumen (7.155 MW), es mayoritariamente prospectiva y
            su materialización dependerá de la resolución de barreras regulatorias, de infraestructura
            y de financiamiento.

            **Recomendaciones basadas en datos**

            - **Priorización de la Orinoquía**: con irradiancia comparable a la Caribe y un pipeline
              reducido, municipios como Villavicencio y Puerto Gaitán son candidatos para análisis de
              viabilidad de conexión al SIN e incentivos diferenciados.
            - **Revisión de los 28 municipios en brecha crítica**: estos municipios deberían ser objeto
              de estudios de factibilidad y de política pública de promoción solar.
            - **Monitoreo de municipios sobreplanificados**: los 9 municipios con alta inversión y
              bajo recurso relativo podrían enfrentar rentabilidad reducida por MW instalado.
            - **Actualización continua**: el pipeline construido en este proyecto permite actualizar
              los resultados con cada nueva publicación de la UPME sin necesidad de rehacer el análisis.

            ---
            *Fuentes: NASA POWER API (2024–2026) · UPME Registro de Proyectos (corte marzo 2026)*
            *Herramientas: Python · pandas · NumPy · SQLite · Plotly · Streamlit · Scikit-learn*
            """)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — ANEXO TÉCNICO
# ════════════════════════════════════════════════════════════════════════════
with TAB_ANEXO:
    st.markdown(
        "Figuras estáticas generadas con Matplotlib para el informe académico."
    )

    fig01_path = FIG_DIR / "fig01_distribuciones_region.png"
    fig06_path = FIG_DIR / "fig06_correlacion_nasa.png"

    st.markdown('<p class="section-label">Figura 1 — Distribución de irradiancia por región natural</p>',
                unsafe_allow_html=True)
    if fig01_path.exists():
        st.image(str(fig01_path), use_container_width=True)
    else:
        st.warning(f"Figura no encontrada en `docs/figuras/fig01_distribuciones_region.png`. "
                   "Ejecuta el script de generación de figuras primero.")

    st.divider()

    st.markdown('<p class="section-label">Figura 6 — Matriz de correlación de Pearson (variables NASA)</p>',
                unsafe_allow_html=True)
    if fig06_path.exists():
        st.image(str(fig06_path), use_container_width=True)
    else:
        st.warning("Figura no encontrada en `docs/figuras/fig06_correlacion_nasa.png`. "
                   "Ejecuta el script de generación de figuras primero.")

    st.markdown(
        """
        <br>
        <small style="color:#8fd4ff;">
        Fuente: NASA POWER — mediciones diarias 2024-01-01 al 2026-05-09 (860 días) ·
        88 municipios · 63 píxeles únicos de la grilla satelital (0.5° × 0.5°)
        </small>
        """,
        unsafe_allow_html=True,
    )
