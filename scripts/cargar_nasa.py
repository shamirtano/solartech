"""Carga incremental de archivos NASA POWER al SQLite del proyecto."""
import argparse
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH      = PROJECT_ROOT / "data" / "potencial_solar.db"
DATA_DIR     = PROJECT_ROOT / "data"

NASA_COLUMNS = {
    "ALLSKY_SFC_SW_DWN": "irradiancia_global",
    "T2M":               "temperatura_2m",
    "RH2M":              "humedad_relativa",
    "WS2M":              "velocidad_viento",
    "PRECTOTCORR":       "precipitacion",
}

FILENAME_RE = re.compile(r"datos_nasa_(?P<municipio>.+)_(?P<fecha>\d{8})\.xlsx", re.IGNORECASE)


def normalizar(texto):
    """Convierte texto a [A-Z0-9_] estricto: sin tildes, sin puntuacion."""
    if texto is None:
        return ""
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_").upper()
    return s


def municipio_from_filename(path):
    m = FILENAME_RE.match(path.name)
    return m.group("municipio").strip() if m else None


def buscar_id_municipio(conn, nombre_municipio):
    cur = conn.cursor()
    cur.execute("SELECT id_municipio, nombre FROM municipios")
    target = normalizar(nombre_municipio)
    for id_m, nombre in cur.fetchall():
        if normalizar(nombre) == target:
            return id_m
    return None


def cargar_archivo(conn, archivo):
    municipio = municipio_from_filename(archivo)
    if municipio is None:
        print(f"  ! {archivo.name}: nombre no coincide con la convencion")
        return (0, 0)

    id_m = buscar_id_municipio(conn, municipio)
    if id_m is None:
        print(f"  ! {archivo.name}: municipio '{municipio}' no existe en `municipios`.")
        return (0, 0)

    df = pd.read_excel(archivo, sheet_name="NASA_POWER_Data")
    df = df.rename(columns={"index": "fecha", **NASA_COLUMNS})
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m-%d")
    df["id_municipio"] = id_m
    cols = ["id_municipio","fecha","irradiancia_global","temperatura_2m",
            "humedad_relativa","velocidad_viento","precipitacion"]
    df = df[cols].where(pd.notna(df[cols]), None)

    cur = conn.cursor()
    sql = """INSERT OR IGNORE INTO mediciones_nasa
        (id_municipio, fecha, irradiancia_global, temperatura_2m,
         humedad_relativa, velocidad_viento, precipitacion)
        VALUES (?, ?, ?, ?, ?, ?, ?)"""
    insertados = 0
    for row in df.itertuples(index=False, name=None):
        cur.execute(sql, row)
        insertados += cur.rowcount
    conn.commit()
    omitidos = len(df) - insertados
    print(f"  OK {archivo.name}: municipio={municipio} (id={id_m}) -> {insertados} insertados, {omitidos} omitidos")
    return (insertados, omitidos)


def main():
    parser = argparse.ArgumentParser(description="Append de archivos NASA POWER a SQLite.")
    parser.add_argument("archivos", nargs="*")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: la BD no existe en {DB_PATH}")
        sys.exit(1)

    archivos = [Path(a) for a in args.archivos] if args.archivos else sorted(DATA_DIR.glob("datos_nasa_*.xlsx"))
    if not archivos:
        print("No se encontraron archivos a cargar.")
        return

    print(f"Conectando a {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    total_ins = total_om = 0
    for archivo in archivos:
        ins, om = cargar_archivo(conn, archivo)
        total_ins += ins
        total_om  += om

    conn.close()
    print(f"\nTotal: {total_ins} insertados, {total_om} omitidos.")


if __name__ == "__main__":
    main()
