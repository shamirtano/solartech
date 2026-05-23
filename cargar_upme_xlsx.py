import argparse
from datetime import datetime
import os
from pathlib import Path
import unicodedata

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv()

TABLA_DESTINO = "proyectos_upme"
COLUMNAS_PLANTILLA = [
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
COLUMNAS_OBLIGATORIAS = {
    "codigo_proyecto",
    "nombre_proyecto",
    "departamento",
    "municipio",
}
DEFINICIONES_COLUMNAS = {
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
ALIAS_COLUMNAS = {
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


def normalizar_texto(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return " ".join(texto.replace("_", " ").replace("-", " ").split())


def normalizar_columna(columna):
    return normalizar_texto(columna).replace(" ", "_")


def homologar_columnas(df):
    df = df.copy()
    df.columns = [
        ALIAS_COLUMNAS.get(normalizar_columna(columna), normalizar_columna(columna))
        for columna in df.columns
    ]
    return df.loc[:, ~df.columns.duplicated()]


def crear_plantilla(ruta_salida):
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

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
                "observaciones": "Columnas geograficas se completan desde la base.",
            }
        ],
        columns=COLUMNAS_PLANTILLA,
    )

    diccionario = pd.DataFrame(
        {
            "columna": COLUMNAS_PLANTILLA,
            "obligatoria": [
                "SI" if columna in COLUMNAS_OBLIGATORIAS else "NO"
                for columna in COLUMNAS_PLANTILLA
            ],
        }
    )

    with pd.ExcelWriter(ruta_salida, engine="openpyxl") as writer:
        ejemplo.to_excel(writer, sheet_name="Plantilla_UPME", index=False)
        diccionario.to_excel(writer, sheet_name="Diccionario", index=False)

    print(f"Plantilla generada: {ruta_salida}")

# Consulta la base de datos para obtener la geografía de municipios, con validaciones de consistencia y formato adecuado para cruces posteriores
def leer_geografia(engine):
    query = """
        SELECT
            mun.id AS id_municipio,
            mun.nombre AS municipio,
            mun.codigo_dane,
            mun.latitud,
            mun.longitud,
            dep.nombre AS departamento
        FROM municipios mun
        JOIN departamentos dep ON mun.id_departamento = dep.id;
    """
    return pd.read_sql(query, con=engine)

# Funcion para completar la geografía de municipios a partir de cruces por código DANE y por nombre, con validaciones de consistencia
def completar_geografia(df, df_geo):
    if df_geo.empty:
        df["id_municipio"] = np.nan
        return df

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

    por_codigo = geo[
        ["codigo_dane_municipio", "geo_id_municipio", "geo_latitud", "geo_longitud"]
    ].drop_duplicates("codigo_dane_municipio")
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
        df.loc[pendientes, "id_municipio"] = resueltos["geo_id_municipio_nombre"].values
        df.loc[pendientes, "codigo_dane_municipio"] = resueltos[
            "codigo_dane_municipio_nombre"
        ].values
        df.loc[pendientes, "latitud"] = resueltos["geo_latitud_nombre"].values
        df.loc[pendientes, "longitud"] = resueltos["geo_longitud_nombre"].values

    return df.drop(
        columns=[
            "departamento_norm",
            "municipio_norm",
            "geo_id_municipio",
            "geo_latitud",
            "geo_longitud",
        ]
    )

# Funcion para cargar el dataframe con los datos del XLSX, normalizar columnas, convertir tipos, completar geografia y validar coordenadas dentro del rango de Colombia
def preparar_dataframe(ruta_xlsx, df_geo):
    df = pd.read_excel(ruta_xlsx)
    if df.empty:
        raise ValueError("El archivo no contiene registros para cargar.")

    df = homologar_columnas(df)
    faltantes = sorted(COLUMNAS_OBLIGATORIAS - set(df.columns))
    if faltantes:
        raise ValueError("Faltan columnas obligatorias: " + ", ".join(faltantes))

    for columna in COLUMNAS_PLANTILLA:
        if columna not in df.columns:
            df[columna] = np.nan

    df = df[COLUMNAS_PLANTILLA].copy()
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
    df.loc[
        df["codigo_dane_municipio"].isin(["", "<NA>", "nan", "None"]),
        "codigo_dane_municipio",
    ] = pd.NA
    df["codigo_dane_municipio"] = df["codigo_dane_municipio"].str.zfill(5)

    df = completar_geografia(df, df_geo)
    df["fecha_cargue"] = datetime.now()
    return df

# Funcion para asegurar que la tabla destino existe con las columnas necesarias antes de cargar los datos
def asegurar_tabla(engine):
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {TABLA_DESTINO} (
        id BIGSERIAL PRIMARY KEY
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))
        for columna, tipo in DEFINICIONES_COLUMNAS.items():
            conn.execute(
                text(
                    f"ALTER TABLE {TABLA_DESTINO} "
                    f"ADD COLUMN IF NOT EXISTS {columna} {tipo};"
                )
            )

# Funcion para ejecutar la carga del XLSX a la base de datos, con validaciones y conteo de registros sin cruce geografico
def cargar_xlsx(ruta_xlsx):
    ruta_xlsx = Path(ruta_xlsx)
    if not ruta_xlsx.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta_xlsx}")

    engine = obtener_engine()
    df_geo = leer_geografia(engine)
    
    # 1. Leemos el DataFrame original manteniendo el índice para saber el número de fila real del Excel
    df_original = pd.read_excel(ruta_xlsx)
    
    # 2. Preparamos el dataframe para la base de datos
    df_upme = preparar_dataframe(ruta_xlsx, df_geo)
    
    # 3. Le transferimos el índice original para calcular la fila exacta del archivo Excel
    df_upme.index = df_original.index
    
    asegurar_tabla(engine)
    
    # =========================================================================
    # BORRADO DE DATOS ANTERIORES (REESCRITURA COMPLETA)
    # =========================================================================
    with engine.begin() as conn:
        print(f"\n Vaciando registros anteriores de la tabla '{TABLA_DESTINO}'...")
        conn.execute(text(f"TRUNCATE TABLE {TABLA_DESTINO} RESTART IDENTITY CASCADE;"))

    # Inyección de los nuevos datos limpios
    df_upme.to_sql(TABLA_DESTINO, con=engine, if_exists="append", index=False)

    # =========================================================================
    # AUDITORÍA DE REGISTROS NO ASOCIADOS (FILAS AFECTADAS)
    # =========================================================================
    # Filtramos las filas donde id_municipio quedó vacío/nulo
    df_sin_municipio = df_upme[df_upme["id_municipio"].isna()].copy()
    sin_municipio_cuenta = len(df_sin_municipio)
    
    print("\n" + "="*80)
    print(f" REPORTE DE CONSOLIDACIÓN Y CARGA")
    print(f"   -> Total registros procesados e inyectados: {len(df_upme)}")
    print("="*80)
    
    if sin_municipio_cuenta > 0:
        print(f"\n  ALERTA: Se detectaron {sin_municipio_cuenta} filas que NO pudieron asociarse geográficamente.")
        print("   Se guardaron en la base de datos con id_municipio vacío (NULL).")
        print("   Corrígelas en tu archivo Excel usando la siguiente guía de filas:\n")
        
        # Calculamos la fila real del Excel: índice de Pandas (inicia en 0) + 1 (por el encabezado) + 1 (índice base 1) = index + 2
        df_sin_municipio["Fila_Excel"] = df_sin_municipio.index + 2
        
        # Columnas clave para la auditoría rápida
        columnas_auditoria = ["Fila_Excel", "codigo_proyecto", "departamento", "municipio", "nombre_proyecto"]
        df_reporte = df_sin_municipio[columnas_auditoria].copy()
        
        # Configuración forzada de Pandas para que NO trunque el texto en la terminal
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        pd.set_option('display.max_colwidth', 40)  # Evita que nombres kilométricos dañen el diseño
        
        # Imprimimos el reporte final con formato de tabla rígida
        print(df_reporte.to_string(index=False))
        
        print("\n Tip de corrección:")
        print("   1. Abre tu archivo Excel y ve directamente a los números de la columna 'Fila_Excel'.")
        print("   2. Verifica que los nombres de 'departamento' y 'municipio' no tengan errores de ortografía.")
        print("   3. Si el municipio es correcto, asegúrate de que exista exactamente igual en tu tabla de la base geográfica.")
        print("="*80 + "\n")
    else:
        print("\n ¡Éxito absoluto! Todos los registros se asociaron correctamente a la base geográfica.")
        print("="*80 + "\n")

# Funcion para generar la cobertura nacional de municipios y departamentos desde la base de datos, con conteo por departamento
def main():
    parser = argparse.ArgumentParser(
        description="Carga datos de proyectos UPME desde un archivo XLSX."
    )
    parser.add_argument(
        "--archivo",
        help="Ruta del XLSX a cargar en la tabla proyectos_upme.",
    )
    parser.add_argument(
        "--generar-plantilla",
        help="Ruta donde se generara una plantilla XLSX de ejemplo.",
    )
    args = parser.parse_args()

    if args.generar_plantilla:
        crear_plantilla(args.generar_plantilla)

    if args.archivo:
        cargar_xlsx(args.archivo)

    if not args.generar_plantilla and not args.archivo:
        parser.print_help()


if __name__ == "__main__":
    main()
