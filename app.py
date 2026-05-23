from datetime import datetime
from io import BytesIO
import os
import time
import unicodedata

import emoji
import numpy as np
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


st.set_page_config(
    page_title="Solar Intelligence - NASA POWER",
    page_icon=emoji.emojize(":sun:"),
    layout="wide",
)

load_dotenv()

NASA_BACKGROUND_URL = (
    "https://images-assets.nasa.gov/image/iss065e066456/"
    "iss065e066456~large.jpg"
)
PROJECT_TITLE_IMAGE_URL = (
    "https://static.vecteezy.com/system/resources/thumbnails/007/449/150/small/"
    "hand-holding-tree-growing-on-globe-with-solar-cell-and-turbine-concept-"
    "clean-energy-for-save-world-elements-of-this-image-furnished-nasa-free-photo.jpg"
)

UPME_TABLE_NAME = "proyectos_upme"
UPME_TEMPLATE_COLUMNS = [
    "codigo_proyecto",
    "marco_normativo_aplicable",
    "fecha_inscripcion_proyecto",
    "fecha_limite_validez",
    "nombre_proyecto",
    "estado",
    "recurso",
    "tipo",
    "tecnologia",
    "capacidad_mw",
    "departamento",
    "municipio",
    "fecha_inicio_construccion",
    "fecha_estimada_operacion",
    "codigo_dane_municipio",
    "latitud",
    "longitud",
    "id_municipio",
    "observaciones",
]
UPME_REQUIRED_COLUMNS = {
    "codigo_proyecto",
    "nombre_proyecto",
    "departamento",
    "municipio",
}
UPME_COLUMN_DEFINITIONS = {
    "codigo_proyecto": "TEXT",
    "marco_normativo_aplicable": "TEXT",
    "fecha_inscripcion_proyecto": "DATE",
    "fecha_limite_validez": "DATE",
    "nombre_proyecto": "TEXT",
    "estado": "TEXT",
    "recurso": "TEXT",
    "tipo": "TEXT",
    "tecnologia": "TEXT",
    "capacidad_mw": "NUMERIC",
    "departamento": "TEXT",
    "municipio": "TEXT",
    "fecha_inicio_construccion": "DATE",
    "fecha_estimada_operacion": "DATE",
    "codigo_dane_municipio": "TEXT",
    "observaciones": "TEXT",
    "id_municipio": "INTEGER",
    "latitud": "NUMERIC",
    "longitud": "NUMERIC",
    "fecha_cargue": "TIMESTAMP",
}
UPME_COLUMN_ALIASES = {
    "codigo_proyecto": "codigo_proyecto",
    "codigo_del_proyecto": "codigo_proyecto",
    "codigo_upme": "codigo_proyecto",
    "marco_normativo_aplicable": "marco_normativo_aplicable",
    "fecha_inscripcion_proyecto": "fecha_inscripcion_proyecto",
    "fecha_de_inscripcion_proyecto": "fecha_inscripcion_proyecto",
    "fecha_limite_de_validez": "fecha_limite_validez",
    "fecha_limite_validez": "fecha_limite_validez",
    "nombre_del_proyecto": "nombre_proyecto",
    "nombre_proyecto": "nombre_proyecto",
    "estado": "estado",
    "recurso": "recurso",
    "tipo": "tipo",
    "tecnologia": "tecnologia",
    "capacidad_[mw]": "capacidad_mw",
    "capacidad_mw": "capacidad_mw",
    "departamento": "departamento",
    "municipio": "municipio",
    "fecha_de_inicio_de_construccion": "fecha_inicio_construccion",
    "fecha_inicio_construccion": "fecha_inicio_construccion",
    "fecha_de_entrada_en_operacion": "fecha_estimada_operacion",
    "fecha_entrada_operacion": "fecha_estimada_operacion",
    "fecha_estimada_operacion": "fecha_estimada_operacion",
}
UPME_SAMPLE_PROJECTS = [
    {
        "codigo_proyecto": "3880",
        "marco_normativo_aplicable": "Resolucion UPME No. 749 de 2025",
        "fecha_inscripcion_proyecto": "2026-02-27",
        "fecha_limite_validez": "2027-09-23",
        "nombre_proyecto": "Parque Solar Cordoba 200MW",
        "estado": "FASE 2",
        "recurso": "SOLAR",
        "tipo": "SOL",
        "tecnologia": "FOTOVOLTAICO",
        "capacidad_mw": 200.0,
        "departamento": "Cordoba",
        "municipio": "Pueblo Nuevo",
        "fecha_inicio_construccion": "2027-09-23",
        "fecha_estimada_operacion": "2029-10-31",
        "observaciones": "Registro de prueba con estructura UPME real.",
        "id_municipio": None,
    },
    {
        "codigo_proyecto": "3882",
        "marco_normativo_aplicable": "Resolucion UPME No. 749 de 2025",
        "fecha_inscripcion_proyecto": "2026-02-18",
        "fecha_limite_validez": "2028-02-18",
        "nombre_proyecto": "Parque Solar El Buho",
        "estado": "FASE 2",
        "recurso": "SOLAR",
        "tipo": "SOL",
        "tecnologia": "FOTOVOLTAICO",
        "capacidad_mw": 99.9,
        "departamento": "Boyaca",
        "municipio": "San Miguel de Sema",
        "fecha_inicio_construccion": "2028-07-01",
        "fecha_estimada_operacion": "2029-12-01",
        "observaciones": "Registro de prueba con estructura UPME real.",
        "id_municipio": None,
    },
    {
        "codigo_proyecto": "UPME-DEMO-003",
        "marco_normativo_aplicable": "Resolucion UPME No. 749 de 2025",
        "fecha_inscripcion_proyecto": "2026-05-23",
        "fecha_limite_validez": "2028-05-23",
        "nombre_proyecto": "Parque Solar Horizonte",
        "estado": "FASE 2",
        "recurso": "SOLAR",
        "tipo": "SOL",
        "tecnologia": "FOTOVOLTAICO",
        "capacidad_mw": 19.9,
        "departamento": "La Guajira",
        "municipio": "Uribia",
        "fecha_inicio_construccion": "2027-06-01",
        "fecha_estimada_operacion": "2027-12-01",
        "observaciones": "Registro de prueba con coordenadas para mapa.",
        "id_municipio": None,
    },
]


def aplicar_estilos():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                linear-gradient(120deg, rgba(6, 13, 30, 0.92), rgba(8, 30, 45, 0.82)),
                url("{NASA_BACKGROUND_URL}");
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
            color: #f5f7fb;
        }}
        .stApp,
        .stApp p,
        .stApp span,
        .stApp label,
        .stApp div,
        .stApp li,
        .stApp h1,
        .stApp h2,
        .stApp h3,
        .stApp h4,
        .stApp h5,
        .stApp h6,
        [data-testid="stMarkdownContainer"],
        [data-testid="stWidgetLabel"],
        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"] {{
            color: #f5f7fb;
        }}
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li {{
            color: #d9e7ef;
        }}
        .stApp a {{
            color: #8fd4ff;
        }}
        .stApp a:hover {{
            color: #ffd166;
        }}
        [data-testid="stSidebar"] {{
            background: rgba(2, 10, 24, 0.88);
            border-right: 1px solid rgba(255, 255, 255, 0.12);
        }}
        [data-testid="stSidebar"] *,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p {{
            color: #f5f7fb;
        }}
        [data-testid="stHeader"] {{
            background: rgba(2, 10, 24, 0);
        }}
        .block-container {{
            padding-top: 1.4rem;
            padding-bottom: 3rem;
        }}
        .solar-hero {{
            border: 1px solid rgba(255, 255, 255, 0.16);
            background:
                linear-gradient(90deg, rgba(3, 12, 28, 0.92) 0%, rgba(8, 35, 48, 0.78) 48%, rgba(8, 35, 48, 0.38) 100%),
                url("{PROJECT_TITLE_IMAGE_URL}");
            background-size: cover;
            background-position: center right;
            border-radius: 8px;
            min-height: 210px;
            padding: 1.55rem 1.6rem;
            margin-bottom: 1rem;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25);
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .solar-hero h1 {{
            margin: 0;
            max-width: 720px;
            font-size: 2.35rem;
            line-height: 1.1;
            letter-spacing: 0;
            color: #ffffff;
            text-shadow: 0 2px 14px rgba(0, 0, 0, 0.55);
        }}
        .solar-hero p {{
            margin: 0.55rem 0 0;
            max-width: 680px;
            color: #e6f4f7;
            font-size: 1rem;
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
        }}
        .metric-band {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.8rem;
            margin: 0.8rem 0 1.2rem;
        }}
        .metric-tile {{
            border: 1px solid rgba(255, 255, 255, 0.14);
            background: rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 0.9rem 1rem;
        }}
        .metric-tile span {{
            color: #a8d8ff;
            font-size: 0.78rem;
            text-transform: uppercase;
        }}
        .metric-tile strong {{
            display: block;
            margin-top: 0.25rem;
            font-size: 1.25rem;
            color: #ffffff;
        }}
        div[data-testid="stMetric"] {{
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            padding: 0.8rem;
        }}
        div[data-testid="stMetric"]:hover,
        .metric-tile:hover {{
            background: rgba(255, 255, 255, 0.14);
            border-color: rgba(255, 209, 102, 0.48);
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.35rem;
        }}
        .stTabs [data-baseweb="tab"] {{
            background: rgba(255, 255, 255, 0.08);
            border-radius: 8px 8px 0 0;
            padding: 0.5rem 0.9rem;
            color: #f5f7fb;
        }}
        .stTabs [data-baseweb="tab"] p {{
            color: #f5f7fb;
            font-weight: 600;
        }}
        .stTabs [data-baseweb="tab"]:hover {{
            background: rgba(255, 209, 102, 0.18);
        }}
        .stTabs [aria-selected="true"] {{
            background: rgba(143, 212, 255, 0.22);
            border-bottom: 2px solid #ffd166;
        }}
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        [data-baseweb="textarea"] textarea,
        [data-testid="stDateInput"] input {{
            background: rgba(255, 255, 255, 0.94);
            color: #081627;
            border-color: rgba(143, 212, 255, 0.55);
        }}
        [data-baseweb="select"] span,
        [data-baseweb="select"] div,
        [data-baseweb="input"] input,
        [data-testid="stDateInput"] input {{
            color: #081627;
        }}
        [data-baseweb="select"] > div:hover,
        [data-baseweb="input"] > div:hover,
        [data-testid="stDateInput"] input:hover {{
            border-color: #ffd166;
            box-shadow: 0 0 0 1px rgba(255, 209, 102, 0.35);
        }}
        [data-baseweb="popover"] *,
        [role="listbox"] *,
        [role="option"] {{
            color: #081627;
        }}
        [role="option"]:hover {{
            background: rgba(255, 209, 102, 0.24);
            color: #081627;
        }}
        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFileUploaderDropzone"] {{
            background: rgba(255, 255, 255, 0.92);
            color: #081627;
            border: 1px solid rgba(143, 212, 255, 0.7);
            border-radius: 8px;
        }}
        .stButton > button *,
        .stDownloadButton > button *,
        [data-testid="stFileUploaderDropzone"] * {{
            color: #081627;
        }}
        .stButton > button:hover,
        .stDownloadButton > button:hover,
        [data-testid="stFileUploaderDropzone"]:hover {{
            background: #ffd166;
            color: #081627;
            border-color: #ffd166;
        }}
        [data-testid="stFileUploader"] {{
            background: rgba(4, 16, 34, 0.72);
            border: 1px solid rgba(143, 212, 255, 0.24);
            border-radius: 8px;
            padding: 0.9rem;
        }}
        [data-testid="stFileUploader"] label,
        [data-testid="stFileUploader"] label *,
        [data-testid="stFileUploader"] [data-testid="stWidgetLabel"] * {{
            color: #f5f7fb;
        }}
        [data-testid="stFileUploaderDropzone"] {{
            min-height: 118px;
        }}
        [data-testid="stFileUploaderDropzone"] button {{
            background: #081627;
            color: #f5f7fb;
            border: 1px solid rgba(143, 212, 255, 0.55);
            position: relative;
        }}
        [data-testid="stFileUploaderDropzone"] button:hover {{
            background: #ffd166;
            color: #081627;
            border-color: #ffd166;
        }}
        [data-testid="stFileUploaderDropzone"] button p {{
            font-size: 0;
        }}
        [data-testid="stFileUploaderDropzone"] button p::after {{
            content: "Cargar archivo";
            font-size: 0.9rem;
            color: #f5f7fb;
            font-weight: 600;
        }}
        [data-testid="stFileUploaderDropzone"] button:hover p::after {{
            color: #081627;
        }}
        [data-testid="stFileUploaderDropzoneInstructions"] {{
            min-width: 0;
        }}
        [data-testid="stFileUploaderDropzoneInstructions"] span {{
            display: block;
            font-size: 0;
            color: transparent;
            line-height: 1.4;
        }}
        [data-testid="stFileUploaderDropzoneInstructions"] span::after {{
            content: "200 MB por archivo • XLSX";
            display: block;
            font-size: 0.85rem;
            color: #081627;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        [data-testid="stFileUploaderFile"],
        [data-testid="stFileUploaderFile"] * {{
            color: #081627;
        }}
        [data-testid="stDataFrame"] {{
            background: rgba(255, 255, 255, 0.96);
            border-radius: 8px;
            padding: 0.25rem;
        }}
        [data-testid="stDataFrame"] * {{
            color: #081627;
        }}
        [data-testid="stExpander"] {{
            background: rgba(4, 16, 34, 0.86);
            border: 1px solid rgba(143, 212, 255, 0.28);
            border-radius: 8px;
        }}
        [data-testid="stExpander"] summary {{
            background: rgba(255, 255, 255, 0.08);
            border-radius: 8px 8px 0 0;
            color: #f5f7fb;
        }}
        [data-testid="stExpander"] summary:hover {{
            background: rgba(255, 209, 102, 0.18);
        }}
        [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] [data-testid="stMarkdownContainer"] *,
        [data-testid="stExpander"] div {{
            color: #f5f7fb;
        }}
        div[data-testid="stTooltipHoverTarget"] *, 
        div[data-testid="stTooltipContent"] *,
        .stTooltipContent,
        div[role="tooltip"] {{
            color: #1A1A1A !important;
        }}        
        div[data-testid="stTooltipContent"] {{
            background-color: #FFFFFF !important;
            border: 1px solid #DCDFE6 !important;
            box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.1) !important;
        }}        
        *[title] {{
            color: #1A1A1A;
        }}
        @media (max-width: 760px) {{
            .solar-hero h1 {{ font-size: 1.55rem; }}
            .metric-band {{ grid-template-columns: 1fr; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def obtener_engine():
    url_conexion = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME"),
    )
    return create_engine(url_conexion, pool_pre_ping=True)


@st.cache_data(ttl=600)
def cargar_parametros_geograficos():
    try:
        query = """
            SELECT
                mun.id AS id_municipio,
                mun.nombre AS municipio,
                mun.latitud,
                mun.longitud,
                mun.codigo_dane,
                dep.nombre AS departamento
            FROM municipios mun
            JOIN departamentos dep ON mun.id_departamento = dep.id;
        """
        return pd.read_sql(query, con=obtener_engine())
    except Exception as exc:
        st.sidebar.error(f"Error de lectura en BD: {exc}")
        return pd.DataFrame()


def normalizar_texto(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return " ".join(texto.replace("_", " ").replace("-", " ").split())


def normalizar_nombre_columna(columna):
    return normalizar_texto(columna).replace(" ", "_")


def homologar_columnas_upme(df):
    df = df.copy()
    df.columns = [
        UPME_COLUMN_ALIASES.get(normalizar_nombre_columna(columna), normalizar_nombre_columna(columna))
        for columna in df.columns
    ]
    return df.loc[:, ~df.columns.duplicated()]


def crear_plantilla_upme():
    ejemplo = pd.DataFrame(
        [
            {
                "codigo_proyecto": "3880",
                "marco_normativo_aplicable": "Resolucion UPME No. 749 de 2025",
                "fecha_inscripcion_proyecto": "27/02/2026",
                "fecha_limite_validez": "23/09/2027",
                "nombre_proyecto": "PARQUE SOLAR CORDOBA 200MW",
                "estado": "FASE 2",
                "recurso": "SOLAR",
                "tipo": "SOL",
                "tecnologia": "FOTOVOLTAICO",
                "capacidad_mw": 200.0,
                "departamento": "CORDOBA",
                "municipio": "PUEBLO NUEVO",
                "fecha_inicio_construccion": "23/09/2027",
                "fecha_estimada_operacion": "31/10/2029",
                "codigo_dane_municipio": "",
                "latitud": "",
                "longitud": "",
                "id_municipio": "",
                "observaciones": "Columnas geograficas se completan con la base si hay cruce.",
            }
        ],
        columns=UPME_TEMPLATE_COLUMNS,
    )

    diccionario = pd.DataFrame(
        {
            "columna": UPME_TEMPLATE_COLUMNS,
            "obligatoria": [
                "SI" if columna in UPME_REQUIRED_COLUMNS else "NO"
                for columna in UPME_TEMPLATE_COLUMNS
            ],
            "descripcion": [
                "Codigo Proyecto reportado por UPME.",
                "Marco normativo aplicable.",
                "Fecha Inscripcion proyecto en formato DD/MM/AAAA.",
                "Fecha limite de validez en formato DD/MM/AAAA.",
                "Nombre del proyecto reportado por UPME.",
                "Estado o fase del proyecto.",
                "Recurso energetico.",
                "Tipo reportado por UPME.",
                "Tecnologia del proyecto.",
                "Capacidad del proyecto en MW.",
                "Departamento reportado por UPME.",
                "Municipio reportado por UPME.",
                "Fecha de inicio de construccion en formato DD/MM/AAAA.",
                "Fecha de entrada en operacion en formato DD/MM/AAAA.",
                "Se completa desde la base geografica si esta vacio.",
                "Se completa desde la base geografica si esta vacio.",
                "Se completa desde la base geografica si esta vacio.",
                "Se completa desde la base geografica si esta vacio.",
                "Notas o comentarios de soporte.",
            ],
        }
    )

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        ejemplo.to_excel(writer, sheet_name="Plantilla_UPME", index=False)
        diccionario.to_excel(writer, sheet_name="Diccionario", index=False)
    buffer.seek(0)
    return buffer


def preparar_dataframe_upme(archivo, df_geo):
    df = pd.read_excel(archivo)
    if df.empty:
        raise ValueError("El archivo no contiene registros para cargar.")

    df = homologar_columnas_upme(df)
    faltantes = sorted(UPME_REQUIRED_COLUMNS - set(df.columns))
    if faltantes:
        raise ValueError("Faltan columnas obligatorias: " + ", ".join(faltantes))

    for columna in UPME_TEMPLATE_COLUMNS:
        if columna not in df.columns:
            df[columna] = np.nan

    df = df[UPME_TEMPLATE_COLUMNS].copy()
    df["capacidad_mw"] = pd.to_numeric(df["capacidad_mw"], errors="coerce")
    df["latitud"] = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    df["id_municipio"] = pd.to_numeric(df["id_municipio"], errors="coerce")

    for columna_fecha in [
        "fecha_inscripcion_proyecto",
        "fecha_limite_validez",
        "fecha_inicio_construccion",
        "fecha_estimada_operacion",
    ]:
        df[columna_fecha] = pd.to_datetime(
            df[columna_fecha], errors="coerce", dayfirst=True
        ).dt.date

    df["codigo_dane_municipio"] = (
        df["codigo_dane_municipio"]
        .astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )
    df.loc[df["codigo_dane_municipio"].isin(["", "<NA>", "nan", "None"]), "codigo_dane_municipio"] = pd.NA
    df["codigo_dane_municipio"] = df["codigo_dane_municipio"].str.zfill(5)

    if not df_geo.empty:
        geo = df_geo.copy()
        geo["codigo_dane_municipio"] = geo["codigo_dane"].astype("string").str.zfill(5)
        geo["departamento_norm"] = geo["departamento"].map(normalizar_texto)
        geo["municipio_norm"] = geo["municipio"].map(normalizar_texto)
        geo = geo.rename(
            columns={
                "id_municipio": "geo_id_municipio",
                "latitud": "geo_latitud",
                "longitud": "geo_longitud",
            }
        )

        df["departamento_norm"] = df["departamento"].map(normalizar_texto)
        df["municipio_norm"] = df["municipio"].map(normalizar_texto)

        columnas_geo = [
            "codigo_dane_municipio",
            "geo_id_municipio",
            "geo_latitud",
            "geo_longitud",
        ]
        por_codigo = geo[columnas_geo].drop_duplicates("codigo_dane_municipio")
        df = df.merge(por_codigo, on="codigo_dane_municipio", how="left")

        df["id_municipio"] = df["id_municipio"].fillna(df["geo_id_municipio"])
        df["latitud"] = df["latitud"].fillna(df["geo_latitud"])
        df["longitud"] = df["longitud"].fillna(df["geo_longitud"])

        pendientes = df["id_municipio"].isna()
        if pendientes.any():
            por_nombre = geo[
                [
                    "departamento_norm",
                    "municipio_norm",
                    "codigo_dane_municipio",
                    "geo_id_municipio",
                    "geo_latitud",
                    "geo_longitud",
                ]
            ].drop_duplicates()
            resueltos = df.loc[pendientes].merge(
                por_nombre,
                on=["departamento_norm", "municipio_norm"],
                how="left",
                suffixes=("", "_nombre"),
            )
            df.loc[pendientes, "id_municipio"] = resueltos[
                "geo_id_municipio_nombre"
            ].values
            df.loc[pendientes, "codigo_dane_municipio"] = resueltos[
                "codigo_dane_municipio_nombre"
            ].values
            df.loc[pendientes, "latitud"] = resueltos[
                "geo_latitud_nombre"
            ].values
            df.loc[pendientes, "longitud"] = resueltos[
                "geo_longitud_nombre"
            ].values

        df = df.drop(
            columns=[
                "departamento_norm",
                "municipio_norm",
                "geo_id_municipio",
                "geo_latitud",
                "geo_longitud",
            ]
        )
    else:
        df["id_municipio"] = np.nan

    df["fecha_cargue"] = datetime.now()
    return df


def asegurar_tabla_upme():
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {UPME_TABLE_NAME} (
        id BIGSERIAL PRIMARY KEY
    );
    """
    with obtener_engine().begin() as conn:
        conn.execute(text(ddl))
        for columna, tipo in UPME_COLUMN_DEFINITIONS.items():
            conn.execute(
                text(
                    f"ALTER TABLE {UPME_TABLE_NAME} "
                    f"ADD COLUMN IF NOT EXISTS {columna} {tipo};"
                )
            )


def guardar_upme_en_bd(df_upme):
    asegurar_tabla_upme()
    engine = obtener_engine()
    
    # Vaciado completo de la tabla antes de inyectar los nuevos datos en línea
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {UPME_TABLE_NAME} RESTART IDENTITY CASCADE;"))
        
    df_upme.to_sql(UPME_TABLE_NAME, con=engine, if_exists="append", index=False)
    cargar_proyectos_upme.clear()


def insertar_datos_prueba_upme():
    asegurar_tabla_upme()
    columnas = list(UPME_COLUMN_DEFINITIONS.keys())
    columnas_sql = ", ".join(columnas)
    valores_sql = ", ".join(f":{columna}" for columna in columnas)
    insert_sql = text(
        f"""
        INSERT INTO {UPME_TABLE_NAME} ({columnas_sql})
        VALUES ({valores_sql});
        """
    )

    registros = []
    for proyecto in UPME_SAMPLE_PROJECTS:
        registro = {columna: proyecto.get(columna) for columna in columnas}
        for columna_fecha in [
            "fecha_inscripcion_proyecto",
            "fecha_limite_validez",
            "fecha_inicio_construccion",
            "fecha_estimada_operacion",
        ]:
            registro[columna_fecha] = pd.to_datetime(
                registro[columna_fecha], errors="coerce"
            ).date()
        registro["fecha_cargue"] = datetime.now()
        registros.append(registro)

    with obtener_engine().begin() as conn:
        conn.execute(
            text(
                f"""
                DELETE FROM {UPME_TABLE_NAME}
                WHERE codigo_proyecto IN ('3880', '3882', 'UPME-DEMO-003');
                """
            )
        )
        conn.execute(insert_sql, registros)

    cargar_proyectos_upme.clear()
    return len(registros)


@st.cache_data(ttl=120)
def cargar_proyectos_upme():
    try:
        asegurar_tabla_upme()
        query = f"""
            SELECT
                codigo_proyecto,
                marco_normativo_aplicable,
                fecha_inscripcion_proyecto,
                fecha_limite_validez,
                nombre_proyecto,
                estado,
                recurso,
                tipo,
                tecnologia,
                capacidad_mw,
                departamento,
                municipio,
                fecha_inicio_construccion,
                fecha_estimada_operacion,
                codigo_dane_municipio,
                latitud,
                longitud,
                id_municipio,
                observaciones,
                fecha_cargue
            FROM {UPME_TABLE_NAME}
            ORDER BY fecha_cargue DESC NULLS LAST, nombre_proyecto ASC;
        """
        return pd.read_sql(query, con=obtener_engine())
    except Exception as exc:
        st.error(f"No fue posible leer proyectos UPME: {exc}")
        return pd.DataFrame()


MAPEO_VARIABLES = {
    emoji.emojize(":sun: Irradiancia Global (kWh/m2/dia)"): {
        "nasa": "ALLSKY_SFC_SW_DWN",
        "col_bd": "irradiancia",
        "unidad": " kWh/m²/día (Kilovatios hora x m² por día)"
    },
    emoji.emojize(":thermometer: Temperatura Ambiente (C)"): {
        "nasa": "T2M",
        "col_bd": "temperatura",
        "unidad": " °C (Grados Celsius)"
    },
    emoji.emojize(":droplet: Humedad Relativa (%)"): {
        "nasa": "RH2M",
        "col_bd": "humedad",
        "unidad": " % (Porcentaje de humedad relativa)"
    },
    emoji.emojize(":dashing_away: Velocidad del Viento (m/s)"): {
        "nasa": "WS2M",
        "col_bd": "viento",
        "unidad": " m/s (Metros por segundo)"
    },
    emoji.emojize(":cloud_with_rain: Precipitacion (mm/dia)"): {
        "nasa": "PRECTOTCORR",
        "col_bd": "precipitacion",
        "unidad": " mm/día (Milímetros por día)"
    },
}

# Se aplican los estilos personalizados para toda la aplicación
aplicar_estilos()

st.markdown(
    f"""
    <section class="solar-hero">
        <h2>{emoji.emojize(':sun_with_face:')} Solar Intelligence - Usando NASA POWER</h2>
        <p>
            Analisis territorial de recurso solar, sincronizacion satelital y
            cargue operativo de proyectos UPME, todo en una sola plataforma.
        </p>
    </section>
    """,
    unsafe_allow_html=True,
)

df_geo = cargar_parametros_geograficos()

st.sidebar.markdown(f"### {emoji.emojize(':round_pushpin:')} Filtros de ubicacion")

if not df_geo.empty:
    lista_deps = sorted(df_geo["departamento"].dropna().unique())
    dep_sel = st.sidebar.selectbox(
        "Departamento",
        lista_deps,
        placeholder="Selecciona un departamento",
    )
    df_muns_filtrados = df_geo[df_geo["departamento"] == dep_sel]
    lista_muns = sorted(df_muns_filtrados["municipio"].dropna().unique())
    mun_sel = st.sidebar.selectbox(
        "Municipio / Ciudad",
        lista_muns,
        placeholder="Selecciona un municipio o ciudad",
    )

    datos_mun = df_muns_filtrados[df_muns_filtrados["municipio"] == mun_sel].iloc[0]
    lat_mun = float(datos_mun["latitud"])
    lon_mun = float(datos_mun["longitud"])
    id_municipio_sel = int(datos_mun["id_municipio"])
else:
    lat_mun, lon_mun, dep_sel, mun_sel, id_municipio_sel = (
        6.2442,
        -75.5812,
        "Antioquia",
        "Medellin",
        None,
    )

st.sidebar.markdown(f"### {emoji.emojize(':calendar:')} Rango de fechas")
fecha_desde = st.sidebar.date_input(
    "Desde",
    datetime(2026, 1, 1),
    format="DD/MM/YYYY",
    help="Selecciona la fecha inicial.",
)
fecha_hasta = st.sidebar.date_input(
    "Hasta",
    datetime(2026, 3, 31),
    format="DD/MM/YYYY",
    help="Selecciona la fecha final.",
)

st.sidebar.markdown(f"### {emoji.emojize(':bar_chart:')} Parametros de consulta")
variables_sel_labels = st.sidebar.multiselect(
    "Variables analiticas",
    options=list(MAPEO_VARIABLES.keys()),
    default=[list(MAPEO_VARIABLES.keys())[0], list(MAPEO_VARIABLES.keys())[1]],
    placeholder="Selecciona variables analiticas",
)

st.sidebar.markdown("---")
btn_sincronizar = st.sidebar.button(
    emoji.emojize(":rocket: Sincronizar y analizar"),
    width="stretch",
)

tab_analisis, tab_proyectos, tab_upme = st.tabs(
    ["Analisis NASA POWER", "Proyectos actuales según UPME", "Cargue proyectos UPME XLSX"]
)

with tab_analisis:
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
    st.map(df_mapa, zoom=11, width="stretch")

    if btn_sincronizar:
        st.markdown("---")
        st.subheader(
            emoji.emojize(
                f":chart_with_upwards_trend: Resultados del analisis en {mun_sel}, {dep_sel}"
            )
        )

        if not variables_sel_labels:
            st.warning("Selecciona al menos una variable en el panel lateral.")
        elif fecha_desde > fecha_hasta:
            st.warning("La fecha inicial no puede ser posterior a la fecha final.")
        else:
            codigos_nasa = [MAPEO_VARIABLES[label]["nasa"] for label in variables_sel_labels]
            str_parameters = ",".join(codigos_nasa)
            f_inicio_str = fecha_desde.strftime("%Y%m%d")
            f_fin_str = fecha_hasta.strftime("%Y%m%d")

            url_api = (
                "https://power.larc.nasa.gov/api/temporal/daily/point"
                f"?parameters={str_parameters}&community=RE&longitude={lon_mun}"
                f"&latitude={lat_mun}&start={f_inicio_str}&end={f_fin_str}&format=JSON"
            )

            try:
                with st.spinner(
                    "Sincronizando registros con la grilla satelital de NASA POWER...",
                    show_time=True,
                ):
                    time.sleep(0.2)
                    response = requests.get(url_api, timeout=45)
                    response.raise_for_status()
                    json_data = response.json()

                properties = json_data["properties"]["parameter"]
                primer_codigo = codigos_nasa[0]
                lista_fechas = list(properties[primer_codigo].keys())

                registros_procesados = []
                for fecha_nasa in lista_fechas:
                    fecha_dt = pd.to_datetime(fecha_nasa, format="%Y%m%d").date()
                    fila = {"id_municipio": id_municipio_sel, "fecha": fecha_dt}

                    for label_sel in variables_sel_labels:
                        cod_nasa = MAPEO_VARIABLES[label_sel]["nasa"]
                        col_limpia = MAPEO_VARIABLES[label_sel]["col_bd"]
                        val_crudo = properties[cod_nasa][fecha_nasa]
                        fila[col_limpia] = val_crudo if val_crudo >= 0 else np.nan

                    registros_procesados.append(fila)

                df_resultados = pd.DataFrame(registros_procesados)

                st.markdown(
                    f"#### {emoji.emojize(':light_bulb:')} Valores promedio del periodo"
                )
                columnas_metricas = st.columns(len(variables_sel_labels))

                # Mostrar métricas promedio para cada variable seleccionada incluyendo la unidad en el label
                for idx, col_label in enumerate(variables_sel_labels):
                    col_limpia = MAPEO_VARIABLES[col_label]["col_bd"]
                    with columnas_metricas[idx]:
                        promedio_val = df_resultados[col_limpia].mean()
                        valor = "No disp." if pd.isna(promedio_val) else round(promedio_val, 2)
                        st.metric(label=col_label, value=valor, delta=MAPEO_VARIABLES[col_label]["unidad"])

                # =========================================================================
                # ANÁLISIS TEMPORAL AVANZADO
                # =========================================================================
                st.markdown(
                    f"#### {emoji.emojize(':chart_with_upwards_trend:')} Análisis y Comportamiento Temporal"
                )
                
                if len(variables_sel_labels) > 0:
                    
                    # --- VISTA 1: OPCIÓN A (Gráfico Comparativo Multilínea) ---
                    # El contenedor con borde añade márgenes internos y externos automáticamente
                    with st.container(border=True):
                        st.markdown(f"### {emoji.emojize(':dna:')} Vista Comparativa")
                        st.caption("Útil para identificar correlaciones entre múltiples variables en un mismo eje de tiempo.")
                        
                        # Extraemos los nombres reales de las columnas de la BD según la selección
                        columnas_a_graficar = [
                            MAPEO_VARIABLES[label]["col_bd"] for label in variables_sel_labels
                        ]
                        
                        # Estructuramos un DataFrame indexado por fecha para el gráfico unificado
                        df_comparativo = df_resultados.set_index("fecha")[columnas_a_graficar]
                        
                        # Renderizamos el gráfico multilínea unificado
                        st.line_chart(df_comparativo, x_label="Fecha", y_label="Valor General")
                    
                    # Margen de seguridad vertical para separar de forma limpia las dos tarjetas
                    st.write("") 
                    
                    # --- VISTA 2: OPCIÓN B (Gráficos Individuales por Pestañas) ---
                    with st.container(border=True):
                        st.markdown(f"### {emoji.emojize(':bookmark_tabs:')} Vista Individual")
                        st.caption("Muestra la tendencia limpia y aislada de cada variable respetando su propia escala y unidad.")
                        
                        # Creamos dinámicamente las pestañas interactivas utilizando las etiquetas
                        pestanas = st.tabs(variables_sel_labels)
                        
                        for idx, col_label in enumerate(variables_sel_labels):
                            col_limpia = MAPEO_VARIABLES[col_label]["col_bd"]
                            
                            # Dibujamos de forma aislada cada gráfico dentro de su respectiva pestaña
                            with pestanas[idx]:
                                st.write(f"{emoji.emojize(':bar_chart:')} **Evolución histórica detallada:** {col_label}")
                                st.line_chart(
                                    data=df_resultados,
                                    x="fecha",
                                    y=col_limpia,
                                    width="stretch",
                                )
                else:
                    st.info(
                        emoji.emojize(":light_bulb: Selecciona una o más variables analíticas en la barra lateral para desplegar los paneles de análisis temporal.")
                    )

                st.markdown("---")
                st.subheader(emoji.emojize(":robot: Conclusion tecnica de viabilidad solar"))

                col_irr_limpia = MAPEO_VARIABLES[
                    emoji.emojize(":sun: Irradiancia Global (kWh/m2/dia)")
                ]["col_bd"]
                irr_media = (
                    df_resultados[col_irr_limpia].mean()
                    if col_irr_limpia in df_resultados.columns
                    else np.nan
                )

                with st.expander("Ver reporte de viabilidad detallado", expanded=True):
                    st.markdown("### **Evaluación del Recurso Energético Disponible**")
                    
                    # Redondeo del promedio limpio para reutilizarlo en los mensajes
                    irr_formateada = round(irr_media, 2)
                    
                    # ALGORITMO EXTENDIDO DE VIABILIDAD MULTI-RANGO
                    if pd.isna(irr_media) or irr_media <= 0:
                        st.error(
                            emoji.emojize(":warning: No se registran suficientes mediciones válidas de irradiancia para las coordenadas o periodo seleccionado.")
                        )
                        
                    elif irr_media >= 5.5:
                        # RANGO 1: Potencial excepcional (Ej: La Guajira, Altos niveles de radiación)
                        st.success(
                            emoji.emojize(":sun_with_face: **VIABILIDAD EXCEPCIONAL / EXCELENTE**\n\n"
                            f"El municipio registra un promedio óptimo de **{irr_formateada} kWh/m²/día**. "
                            "Esta zona cuenta con un recurso de clase mundial, ideal para el desarrollo de grandes centrales fotovoltaicas (Utility-Scale), "
                            "parques solares comerciales y sistemas de exportación a la red nacional con un retorno de inversión acelerado.")
                        )
                        
                    elif irr_media >= 4.5:
                        # RANGO 2: Potencial óptimo para autogeneración masiva (Ej: Valles interandinos, Llanos)
                        st.success(
                            emoji.emojize(":sun: **VIABILIDAD ALTA**\n\n"
                            f"El municipio presenta un promedio de **{irr_formateada} kWh/m²/día**. "
                            "El recurso solar es altamente competitivo y estable. Recomendado para la implementación de proyectos integrales de autogeneración "
                            "comercial, industrial (AGPE) y soluciones residenciales a gran escala con alta tasa de eficiencia.")
                        )
                        
                    elif irr_media >= 3.8:
                        # RANGO 3: Transición moderada estándar (Muchos municipios de la región Andina/Antioquia)
                        st.info(
                            emoji.emojize(":sun_behind_small_cloud: **VIABILIDAD MODERADA-ALTA**\n\n"
                            f"El municipio promedia un recurso de **{irr_formateada} kWh/m²/día**. "
                            "El potencial es totalmente viable para transición energética. Es idóneo para sistemas fotovoltaicos conectados a red (On-Grid) "
                            "en hogares y comercios que buscan mitigar el costo de la tarifa de energía convencional.")
                        )
                        
                    elif irr_media >= 3.0:
                        # RANGO 4: Zonas con alta nubosidad o microclimas húmedos
                        st.warning(
                            emoji.emojize(":cloud: **VIABILIDAD MODERADA / CONDICIONADA**\n\n"
                            f"El área registra un promedio de **{irr_formateada} kWh/m²/día**. "
                            "La presencia de nubosidad persistente o factores microclimáticos limita la captación máxima. El proyecto es viable, "
                            "pero se sugiere instalar paneles de alta eficiencia para baja irradiancia (tecnología monocristalina PERC o tipo N) "
                            "y realizar un análisis de sombras detallado.")
                        )
                        
                    else:
                        # RANGO 5: Potencial bajo (Zonas de selva densa o extrema pluviosidad constante)
                        st.error(
                            emoji.emojize(":cloud_with_rain: **VIABILIDAD BAJA / RESTRINGIDA**\n\n"
                            f"El promedio histórico en este rango es de **{irr_formateada} kWh/m²/día**. "
                            "El recurso solar disponible es limitado debido al alto índice de precipitación o nubosidad. No se recomienda para inversión "
                            "comercial masiva de inyección, a menos que se use como sistema de respaldo híbrido complementado con otras fuentes "
                            "de energía (baterías o generación diésel/eólica).")
                        )
            except Exception as exc:
                st.error(f"Error de enlace con NASA POWER: {exc}")

with tab_upme:
    st.subheader("Cargue de proyectos UPME desde XLSX")
    st.write(
        "Descarga la plantilla, completa los registros y sube el archivo para validar "
        "el contenido antes de enviarlo a la base de datos."
    )

    st.download_button(
        "Descargar plantilla XLSX",
        data=crear_plantilla_upme(),
        file_name="plantilla_cargue_upme.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

    archivo_upme = st.file_uploader(
        "Archivo UPME en formato XLSX",
        type=["xlsx"],
        accept_multiple_files=False,
        help="Selecciona un archivo XLSX con la plantilla UPME.",
    )
    st.caption("Límite: 200 MB por archivo. Formato permitido: XLSX.")

    if archivo_upme is not None:
        try:
            with st.spinner("Validando estructura y preparando registros UPME...", show_time=True):
                time.sleep(0.2)
                # Leemos el archivo original para rastrear el número exacto de fila del XLSX
                df_original_excel = pd.read_excel(archivo_upme)
                df_upme = preparar_dataframe_upme(archivo_upme, df_geo)
                # Conservamos el índice original mapeado
                df_upme.index = df_original_excel.index

            st.success(f"Archivo válido: {len(df_upme)} registros listos para cargar.")

            # =========================================================================
            # DETECCIÓN E INFORME EN INTERFAZ DE FILAS NO ASOCIADAS
            # =========================================================================
            df_sin_municipio = df_upme[df_upme["id_municipio"].isna()].copy()
            sin_municipio = len(df_sin_municipio)
            
            if sin_municipio:
                st.warning(
                    f"{emoji.emojize(':warning:')} {sin_municipio} registros no pudieron asociarse a un municipio "
                    "de la base geográfica. Se cargarán con id_municipio vacío (NULL)."
                )
                
                # Calculamos el número de fila real del archivo Excel original
                df_sin_municipio["Fila_Excel"] = df_sin_municipio.index + 2
                
                # Columnas clave para el reporte rápido en pantalla
                cols_reporte = ["Fila_Excel", "codigo_proyecto", "departamento", "municipio", "nombre_proyecto"]
                cols_visibles = [col for col in cols_reporte if col in df_sin_municipio.columns]
                
                with st.expander(f"{emoji.emojize(':mag:')} Ver detalles de las {sin_municipio} filas afectadas para corrección", expanded=True):
                    st.markdown("**Revisa la ortografía de estas filas en tu archivo Excel original:**")
                    st.dataframe(
                        df_sin_municipio[cols_visibles],
                        width="stretch",
                        hide_index=True
                    )
            else:
                st.success(f"{emoji.emojize(':white_check_mark:')} Todos los registros se asociaron geográficamente de forma perfecta.")

            # Vista previa general de los datos que se van a procesar
            st.markdown("### Vista previa de datos listos para inyección:")
            st.dataframe(df_upme.head(50), width="stretch", hide_index=True)

            if st.button("Guardar registros UPME en la base de datos", width="stretch"):
                with st.spinner("Cargando proyectos UPME en Supabase/Postgres...", show_time=True):
                    time.sleep(0.2)
                    guardar_upme_en_bd(df_upme)
                st.success(
                    f"Cargue completado en la tabla {UPME_TABLE_NAME}: "
                    f"{len(df_upme)} registros insertados con reescritura completa."
                )
                time.sleep(1)
                st.rerun()
                
        except Exception as exc:
            st.error(f"No fue posible procesar el archivo: {exc}")

with tab_proyectos:
    st.subheader("Proyectos UPME cargados en la base de datos")

    # 1. Consultar primero los proyectos almacenados para verificar si existen datos
    with st.spinner("Consultando proyectos UPME almacenados...", show_time=True):
        df_proyectos = cargar_proyectos_upme()
    
    # 2. Determinar si la base de datos ya contiene registros cargados
    tiene_datos = not df_proyectos.empty

    col_accion_1, col_accion_2 = st.columns(2)
    with col_accion_1:
        if st.button("Actualizar datos UPME", width="stretch"):
            cargar_proyectos_upme.clear()
            st.rerun()
            
    with col_accion_2:
        # El botón se desactiva dinámicamente si 'tiene_datos' es True
        if st.button(
            "Insertar datos de prueba", 
            width="stretch", 
            disabled=tiene_datos,
            help="El botón se desactiva de forma automática si ya existen proyectos registrados en la base de datos." if tiene_datos else None
        ):
            try:
                with st.spinner("Insertando proyectos UPME de prueba...", show_time=True):
                    registros_demo = insertar_datos_prueba_upme()
                st.success(f"Se insertaron {registros_demo} proyectos de prueba.")
                st.rerun()
            except Exception as exc:
                st.error(f"No fue posible insertar datos de prueba: {exc}")

    # 3. Renderizar la interfaz según la presencia de registros
    if df_proyectos.empty:
        st.info(
            "La tabla UPME existe o fue preparada correctamente, pero aun no tiene "
            "registros para mostrar. Puedes cargar un XLSX en la pestaña anterior "
            "o usar el boton de datos de prueba."
        )
    else:
        df_vista = df_proyectos.copy()
        df_vista["capacidad_mw"] = pd.to_numeric(
            df_vista["capacidad_mw"], errors="coerce"
        )

        col_filtro_1, col_filtro_2, col_filtro_3 = st.columns(3)
        with col_filtro_1:
            departamentos = sorted(df_vista["departamento"].dropna().unique())
            departamentos_sel = st.multiselect(
                "Departamento",
                departamentos,
                default=departamentos,
                placeholder="Selecciona departamentos",
            )
        with col_filtro_2:
            estados = sorted(df_vista["estado"].dropna().unique())
            estados_sel = st.multiselect(
                "Estado",
                estados,
                default=estados,
                placeholder="Selecciona estados",
            )
        with col_filtro_3:
            recursos = sorted(df_vista["recurso"].dropna().unique())
            recursos_sel = st.multiselect(
                "Recurso",
                recursos,
                default=recursos,
                placeholder="Selecciona recursos",
            )

        if departamentos_sel:
            df_vista = df_vista[df_vista["departamento"].isin(departamentos_sel)]
        if estados_sel:
            df_vista = df_vista[df_vista["estado"].isin(estados_sel)]
        if recursos_sel:
            df_vista = df_vista[df_vista["recurso"].isin(recursos_sel)]

        total_proyectos = len(df_vista)
        capacidad_total = df_vista["capacidad_mw"].sum(min_count=1)
        municipios_total = df_vista["municipio"].nunique()

        st.markdown(
            f"""
            <div class="metric-band">
                <div class="metric-tile"><span>Proyectos visibles</span><strong>{total_proyectos}</strong></div>
                <div class="metric-tile"><span>Capacidad total</span><strong>{0 if pd.isna(capacidad_total) else round(capacidad_total, 2)} MW</strong></div>
                <div class="metric-tile"><span>Municipios</span><strong>{municipios_total}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        columnas_tabla = [
            "codigo_proyecto",
            "marco_normativo_aplicable",
            "fecha_inscripcion_proyecto",
            "fecha_limite_validez",
            "nombre_proyecto",
            "estado",
            "recurso",
            "tipo",
            "tecnologia",
            "capacidad_mw",
            "departamento",
            "municipio",
            "codigo_dane_municipio",
            "fecha_inicio_construccion",
            "fecha_estimada_operacion",
            "fecha_cargue",
        ]
        columnas_disponibles = [
            columna for columna in columnas_tabla if columna in df_vista.columns
        ]

        st.dataframe(
            df_vista[columnas_disponibles],
            width="stretch",
            hide_index=True,
        )

        df_mapa_upme = df_vista.dropna(subset=["latitud", "longitud"]).copy()
        if not df_mapa_upme.empty:
            df_mapa_upme["lat"] = pd.to_numeric(df_mapa_upme["latitud"], errors="coerce")
            df_mapa_upme["lon"] = pd.to_numeric(df_mapa_upme["longitud"], errors="coerce")
            df_mapa_upme = df_mapa_upme.dropna(subset=["lat", "lon"])
            if not df_mapa_upme.empty:
                st.markdown("#### Ubicacion de proyectos con coordenadas")
                st.map(df_mapa_upme[["lat", "lon"]], zoom=5, width="stretch")
