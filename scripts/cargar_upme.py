"""
Carga del informe UPME de proyectos de generación al SQLite.

Uso:
    python scripts/cargar_upme.py
    python scripts/cargar_upme.py data/Informe_registros_activos_de_proyectos_generacion_electrica_marzo_2026.xlsx

Lee el archivo Excel oficial de la UPME, limpia el formato (encabezados en la fila 3,
columnas vacías al final) y carga los proyectos en `proyectos_upme`.
La carga es idempotente: si el proyecto ya existe se actualiza con UPSERT.
"""

import argparse
import sqlite3
import sys
import unicodedata
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH      = PROJECT_ROOT / "data" / "potencial_solar.db"
DEFAULT_FILE = PROJECT_ROOT / "data" / "Informe_registros_activos_de_proyectos_generacion_electrica_marzo_2026.xlsx"


def normalizar(texto):
    if pd.isna(texto):
        return None
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return s.strip().upper()


def fecha_a_str(valor):
    if pd.isna(valor):
        return None
    try:
        return pd.to_datetime(valor).strftime("%Y-%m-%d")
    except Exception:
        return None


def cargar(archivo: Path):
    if not DB_PATH.exists():
        print(f"ERROR: la base de datos no existe en {DB_PATH}")
        sys.exit(1)

    df = pd.read_excel(archivo, sheet_name="Informe", header=2)
    # Quitar primera columna vacía (Unnamed: 0)
    df = df.iloc[:, 1:]
    # Quitar columnas vacías 'Columna1'..'Columna5'
    df = df.drop(columns=[c for c in df.columns if str(c).startswith("Columna")], errors="ignore")
    # Filtrar filas sin código de proyecto
    df = df.dropna(subset=["Codigo Proyecto"]).reset_index(drop=True)

    # Normalizar nombres de columnas internos
    df = df.rename(columns={
        "Codigo Proyecto":                                       "codigo_proyecto",
        "Marco normativo \naplicable":                           "marco_normativo",
        "Fecha Inscripción proyecto":                            "fecha_inscripcion",
        "Fecha de validez: Marco normativo + Fecha construcción": "fecha_validez_full",
        "Fecha límite de validez0":                              "fecha_validez0",
        "Fecha límite de validez":                               "fecha_validez",
        "Nombre  del proyecto":                                  "nombre",
        "Estado":                                                "estado",
        "Recurso ":                                              "recurso",
        "Tipo":                                                  "tipo",
        "Tecnología":                                            "tecnologia",
        "Capacidad [MW]":                                        "capacidad_mw",
        "Departamento":                                          "departamento",
        "Municipio":                                             "municipio",
        "Fecha de inicio de construcción":                       "fecha_inicio_construccion",
        "Fecha de entrada en operación":                         "fecha_entrada_operacion",
    })

    # Limpieza de strings con espacios sobrantes
    for c in ["estado", "recurso", "tecnologia", "departamento", "municipio"]:
        df[c] = df[c].astype(str).str.strip().replace({"nan": None})

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # Construir diccionarios de lookup
    cur.execute("SELECT id_recurso, nombre FROM recursos")
    recursos = {normalizar(n): i for i, n in cur.fetchall()}
    cur.execute("SELECT id_tecnologia, nombre FROM tecnologias")
    tecnologias = {normalizar(n): i for i, n in cur.fetchall()}
    cur.execute("SELECT id_estado, nombre FROM estados_proyecto")
    estados = {normalizar(n): i for i, n in cur.fetchall()}
    cur.execute("""
        SELECT m.id_municipio, m.nombre, d.nombre
        FROM municipios m JOIN departamentos d ON d.id_departamento = m.id_departamento
    """)
    municipios = {(normalizar(d), normalizar(m)): i for i, m, d in cur.fetchall()}

    cur.execute("SELECT id_departamento, nombre FROM departamentos")
    departamentos = {normalizar(n): i for i, n in cur.fetchall()}

    insertados, faltan_municipio, faltan_departamento = 0, 0, 0
    for row in df.itertuples(index=False):
        rec_id  = recursos.get(normalizar(row.recurso))
        tec_id  = tecnologias.get(normalizar(row.tecnologia))
        est_id  = estados.get(normalizar(row.estado))

        dep_norm = normalizar(row.departamento)
        mun_norm = normalizar(row.municipio)
        mun_id = municipios.get((dep_norm, mun_norm))

        if mun_id is None:
            # Si tenemos el departamento pero no el municipio, lo creamos
            dep_id = departamentos.get(dep_norm)
            if dep_id is None:
                faltan_departamento += 1
                continue
            cur.execute(
                "INSERT OR IGNORE INTO municipios (nombre, id_departamento) VALUES (?, ?)",
                (mun_norm, dep_id),
            )
            cur.execute(
                "SELECT id_municipio FROM municipios WHERE nombre=? AND id_departamento=?",
                (mun_norm, dep_id),
            )
            mun_id = cur.fetchone()[0]
            municipios[(dep_norm, mun_norm)] = mun_id
            faltan_municipio += 1

        cur.execute("""
            INSERT INTO proyectos_upme (
                codigo_proyecto, nombre, marco_normativo,
                fecha_inscripcion, fecha_validez,
                id_estado, id_recurso, id_tecnologia,
                capacidad_mw, id_municipio,
                fecha_inicio_construccion, fecha_entrada_operacion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(codigo_proyecto) DO UPDATE SET
                nombre=excluded.nombre,
                marco_normativo=excluded.marco_normativo,
                fecha_inscripcion=excluded.fecha_inscripcion,
                fecha_validez=excluded.fecha_validez,
                id_estado=excluded.id_estado,
                id_recurso=excluded.id_recurso,
                id_tecnologia=excluded.id_tecnologia,
                capacidad_mw=excluded.capacidad_mw,
                id_municipio=excluded.id_municipio,
                fecha_inicio_construccion=excluded.fecha_inicio_construccion,
                fecha_entrada_operacion=excluded.fecha_entrada_operacion
        """, (
            int(row.codigo_proyecto),
            row.nombre,
            row.marco_normativo,
            fecha_a_str(row.fecha_inscripcion),
            fecha_a_str(row.fecha_validez),
            est_id,
            rec_id,
            tec_id,
            float(row.capacidad_mw) if pd.notna(row.capacidad_mw) else None,
            mun_id,
            fecha_a_str(row.fecha_inicio_construccion),
            fecha_a_str(row.fecha_entrada_operacion),
        ))
        insertados += 1

    conn.commit()
    conn.close()
    print(f"Proyectos cargados/actualizados: {insertados}")
    if faltan_municipio:
        print(f"  Municipios creados al vuelo (no estaban en el seed): {faltan_municipio}")
    if faltan_departamento:
        print(f"  Proyectos omitidos por departamento desconocido: {faltan_departamento}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archivo", nargs="?", default=str(DEFAULT_FILE))
    args = parser.parse_args()
    cargar(Path(args.archivo))


if __name__ == "__main__":
    main()
