"""
Inicializa la base de datos SQLite del proyecto.
Crea el archivo data/potencial_solar.db, ejecuta el schema y el seed geográfico.

Uso:
    python scripts/crear_db.py            # crea si no existe
    python scripts/crear_db.py --reset    # borra y recrea desde cero
"""

import argparse
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH      = PROJECT_ROOT / "data" / "potencial_solar.db"
SCHEMA_SQL   = PROJECT_ROOT / "sql"  / "schema.sql"
SEED_SQL     = PROJECT_ROOT / "sql"  / "seed_geografia.sql"
SEED_UPME    = PROJECT_ROOT / "sql"  / "seed_municipios_upme.sql"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Borra la BD existente antes de crear")
    args = parser.parse_args()

    if args.reset and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"BD existente eliminada: {DB_PATH}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    print(f"Ejecutando schema: {SCHEMA_SQL.name}")
    conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))

    print(f"Ejecutando seed:   {SEED_SQL.name}")
    conn.executescript(SEED_SQL.read_text(encoding="utf-8"))

    if SEED_UPME.exists():
        print(f"Ejecutando seed:   {SEED_UPME.name}")
        conn.executescript(SEED_UPME.read_text(encoding="utf-8"))

    # Verificación
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM departamentos")
    n_dep = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM municipios")
    n_mun = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM recursos")
    n_rec = cur.fetchone()[0]
    print(f"\nResumen:")
    print(f"  Departamentos: {n_dep}")
    print(f"  Municipios:    {n_mun}")
    print(f"  Recursos:      {n_rec}")
    print(f"\nBD lista en {DB_PATH}")

    conn.close()


if __name__ == "__main__":
    main()
