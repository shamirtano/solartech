"""Descarga masiva de datos NASA POWER, genera Excel por municipio."""
import argparse
import re
import sqlite3
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH      = PROJECT_ROOT / "data" / "potencial_solar.db"
DATA_DIR     = PROJECT_ROOT / "data"

API_URL   = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS    = ["ALLSKY_SFC_SW_DWN", "T2M", "RH2M", "WS2M", "PRECTOTCORR"]
COMMUNITY = "RE"
PIXEL_DEG = 0.5

DEFAULT_INICIO = "20240101"
DEFAULT_FIN    = "20260501"


def normalizar(texto):
    """[A-Z0-9_] estricto. Debe coincidir con cargar_nasa.py."""
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_").upper()


def cargar_municipios(filtro=None):
    if not DB_PATH.exists():
        sys.exit(f"ERROR: BD no existe en {DB_PATH}. Ejecuta crear_db.py primero.")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT m.id_municipio, m.nombre AS municipio, d.nombre AS departamento,
               m.latitud, m.longitud
        FROM municipios m
        JOIN departamentos d ON d.id_departamento = m.id_departamento
        WHERE m.latitud IS NOT NULL AND m.longitud IS NOT NULL
        ORDER BY d.nombre, m.nombre
    """, conn)
    conn.close()
    if filtro:
        objetivos = {normalizar(n) for n in filtro}
        df = df[df["municipio"].apply(lambda x: normalizar(x) in objetivos)].reset_index(drop=True)
    return df


def agrupar_por_pixel(df):
    df = df.copy()
    df["pixel_lat"] = (df["latitud"]  / PIXEL_DEG).round().astype(int) * PIXEL_DEG
    df["pixel_lon"] = (df["longitud"] / PIXEL_DEG).round().astype(int) * PIXEL_DEG
    df["pixel_id"]  = df["pixel_lat"].astype(str) + "_" + df["pixel_lon"].astype(str)
    return df


def consultar_nasa_power(lat, lon, inicio, fin, max_reintentos=3):
    parametros_str = ",".join(PARAMS)
    url = (f"{API_URL}?parameters={parametros_str}&community={COMMUNITY}"
           f"&longitude={lon}&latitude={lat}&start={inicio}&end={fin}&format=JSON")
    for intento in range(1, max_reintentos + 1):
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                data = r.json()
                df = pd.DataFrame(data["properties"]["parameter"])
                df = df.replace(-999, pd.NA)
                df.index = pd.to_datetime(df.index, format="%Y%m%d")
                df.index.name = "index"
                return df
            print(f"    Intento {intento}: HTTP {r.status_code}")
        except requests.RequestException as e:
            print(f"    Intento {intento}: error ({e})")
        if intento < max_reintentos:
            time.sleep(2 ** intento)
    return None


def guardar_excel(df, municipio, fecha_descarga):
    archivo = DATA_DIR / f"datos_nasa_{normalizar(municipio)}_{fecha_descarga}.xlsx"
    with pd.ExcelWriter(archivo, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="NASA_POWER_Data")
    return archivo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inicio",     default=DEFAULT_INICIO)
    parser.add_argument("--fin",        default=DEFAULT_FIN)
    parser.add_argument("--municipios", nargs="*")
    parser.add_argument("--force",      action="store_true")
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--pausa",      type=float, default=0.5)
    args = parser.parse_args()

    print(f"Inicio: {args.inicio}  Fin: {args.fin}")
    print(f"Parametros: {', '.join(PARAMS)}")

    df_mun = cargar_municipios(args.municipios)
    if df_mun.empty:
        sys.exit("Sin municipios a procesar.")

    df_mun = agrupar_por_pixel(df_mun)
    pix_unicos = df_mun["pixel_id"].nunique()
    print(f"\nMunicipios: {len(df_mun)}  Pixeles unicos: {pix_unicos}")

    if args.dry_run:
        print("\n--- Plan (dry-run) ---")
        for px, grupo in df_mun.groupby("pixel_id"):
            mun = ", ".join(grupo["municipio"].tolist())
            print(f"  Pixel {px} -> {mun}")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fecha = datetime.now().strftime("%Y%m%d")
    cache = {}
    n_ok = n_skip = n_fail = 0

    for idx, row in df_mun.iterrows():
        municipio = row["municipio"]
        pixel_id  = row["pixel_id"]
        archivo_dest = DATA_DIR / f"datos_nasa_{normalizar(municipio)}_{fecha}.xlsx"

        if archivo_dest.exists() and not args.force:
            print(f"[{idx+1}/{len(df_mun)}] {municipio}: ya existe")
            n_skip += 1
            continue

        if pixel_id in cache:
            df_px = cache[pixel_id]
            print(f"[{idx+1}/{len(df_mun)}] {municipio}: reusando pixel {pixel_id}")
        else:
            print(f"[{idx+1}/{len(df_mun)}] {municipio}: descargando pixel {pixel_id}...")
            df_px = consultar_nasa_power(row["latitud"], row["longitud"], args.inicio, args.fin)
            if df_px is None:
                print(f"    FAIL")
                n_fail += 1
                continue
            cache[pixel_id] = df_px
            time.sleep(args.pausa)

        salida = guardar_excel(df_px, municipio, fecha)
        print(f"    OK {salida.name}")
        n_ok += 1

    print(f"\nResumen: {n_ok} OK, {n_skip} omitidos, {n_fail} fallidos. Pixeles consultados: {len(cache)}")


if __name__ == "__main__":
    main()
