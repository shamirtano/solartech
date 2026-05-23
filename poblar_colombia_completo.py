import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

load_dotenv()

DIVIPOLA_URL = (
    "https://www.datos.gov.co/resource/gdxc-w37w.json"
    "?$limit=50000&$order=cod_dpto,cod_mpio"
)

DEPARTAMENTOS_BASE = [
    {"id": 1, "nombre": "Antioquia", "region_natural": "Andina", "codigo_dane": "05"},
    {"id": 2, "nombre": "Amazonas", "region_natural": "Amazonia", "codigo_dane": "91"},
    {"id": 3, "nombre": "Atlantico", "region_natural": "Caribe", "codigo_dane": "08"},
    {"id": 4, "nombre": "Valle del Cauca", "region_natural": "Pacifica", "codigo_dane": "76"},
    {"id": 5, "nombre": "Bogota, D.C.", "region_natural": "Andina", "codigo_dane": "11"},
    {"id": 6, "nombre": "Bolivar", "region_natural": "Caribe", "codigo_dane": "13"},
    {"id": 7, "nombre": "Boyaca", "region_natural": "Andina", "codigo_dane": "15"},
    {"id": 8, "nombre": "Caldas", "region_natural": "Andina", "codigo_dane": "17"},
    {"id": 9, "nombre": "Caqueta", "region_natural": "Amazonia", "codigo_dane": "18"},
    {"id": 10, "nombre": "Cauca", "region_natural": "Pacifica", "codigo_dane": "19"},
    {"id": 11, "nombre": "Cesar", "region_natural": "Caribe", "codigo_dane": "20"},
    {"id": 12, "nombre": "Cordoba", "region_natural": "Caribe", "codigo_dane": "23"},
    {"id": 13, "nombre": "Cundinamarca", "region_natural": "Andina", "codigo_dane": "25"},
    {"id": 14, "nombre": "Choco", "region_natural": "Pacifica", "codigo_dane": "27"},
    {"id": 15, "nombre": "Huila", "region_natural": "Andina", "codigo_dane": "41"},
    {"id": 16, "nombre": "La Guajira", "region_natural": "Caribe", "codigo_dane": "44"},
    {"id": 17, "nombre": "Magdalena", "region_natural": "Caribe", "codigo_dane": "47"},
    {"id": 18, "nombre": "Meta", "region_natural": "Orinoquia", "codigo_dane": "50"},
    {"id": 19, "nombre": "Narino", "region_natural": "Pacifica", "codigo_dane": "52"},
    {"id": 20, "nombre": "Norte de Santander", "region_natural": "Andina", "codigo_dane": "54"},
    {"id": 21, "nombre": "Quindio", "region_natural": "Andina", "codigo_dane": "63"},
    {"id": 22, "nombre": "Risaralda", "region_natural": "Andina", "codigo_dane": "66"},
    {"id": 23, "nombre": "Santander", "region_natural": "Andina", "codigo_dane": "68"},
    {"id": 24, "nombre": "Sucre", "region_natural": "Caribe", "codigo_dane": "70"},
    {"id": 25, "nombre": "Tolima", "region_natural": "Andina", "codigo_dane": "73"},
    {"id": 26, "nombre": "Arauca", "region_natural": "Orinoquia", "codigo_dane": "81"},
    {"id": 27, "nombre": "Casanare", "region_natural": "Orinoquia", "codigo_dane": "85"},
    {"id": 28, "nombre": "Putumayo", "region_natural": "Amazonia", "codigo_dane": "86"},
    {
        "id": 29,
        "nombre": "San Andres, Providencia y Santa Catalina",
        "region_natural": "Caribe",
        "codigo_dane": "88",
    },
    {"id": 30, "nombre": "Guainia", "region_natural": "Amazonia", "codigo_dane": "94"},
    {"id": 31, "nombre": "Guaviare", "region_natural": "Amazonia", "codigo_dane": "95"},
    {"id": 32, "nombre": "Vaupes", "region_natural": "Amazonia", "codigo_dane": "97"},
    {"id": 33, "nombre": "Vichada", "region_natural": "Orinoquia", "codigo_dane": "99"},
]

def obtener_engine():
    url_conexion = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
    )
    return create_engine(url_conexion)


def _titulo_colombia(texto):
    conectores = {"de", "del", "la", "las", "los", "y"}
    palabras = []

    for indice, palabra in enumerate(str(texto).strip().lower().split()):
        limpia = palabra.strip(",")
        nueva = palabra if indice > 0 and limpia in conectores else palabra.capitalize()
        palabras.append(nueva)

    return " ".join(palabras).replace("D.c.", "D.C.")


def _decimal_colombiano(valor):
    return float(str(valor).replace(",", "."))


def obtener_divipola():
    print("Descargando DIVIPOLA oficial desde Datos Abiertos Colombia...")
    df = pd.read_json(DIVIPOLA_URL, dtype=False)

    columnas_requeridas = {
        "cod_dpto",
        "dpto",
        "cod_mpio",
        "nom_mpio",
        "latitud",
        "longitud",
    }
    faltantes = columnas_requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"Columnas faltantes en DIVIPOLA: {', '.join(sorted(faltantes))}")

    df = df.dropna(subset=["cod_dpto", "cod_mpio", "nom_mpio", "latitud", "longitud"])
    df["cod_dpto"] = df["cod_dpto"].astype(str).str.zfill(2)
    df["cod_mpio"] = df["cod_mpio"].astype(str).str.zfill(5)
    df["latitud"] = df["latitud"].map(_decimal_colombiano)
    df["longitud"] = df["longitud"].map(_decimal_colombiano)

    fuera_colombia = ~(
        df["latitud"].between(-5.0, 13.8) & df["longitud"].between(-82.5, -66.0)
    )
    if fuera_colombia.any():
        codigos = ", ".join(df.loc[fuera_colombia, "cod_mpio"].head(10))
        raise ValueError(f"Coordenadas fuera de rango para Colombia: {codigos}")

    return df


def generar_cobertura_nacional():
    print("Generando matriz completa de municipios de Colombia...")

    df_divipola = obtener_divipola()
    df_departamentos = pd.DataFrame(DEPARTAMENTOS_BASE)
    nombres_oficiales = (
        df_divipola.groupby("cod_dpto")["dpto"].first().map(_titulo_colombia).to_dict()
    )
    df_departamentos["nombre"] = df_departamentos["codigo_dane"].map(nombres_oficiales)

    mapa_departamentos = df_departamentos.set_index("codigo_dane")["id"].to_dict()
    codigos_sin_departamento = sorted(set(df_divipola["cod_dpto"]) - set(mapa_departamentos))
    if codigos_sin_departamento:
        raise ValueError(
            "Departamentos no configurados: " + ", ".join(codigos_sin_departamento)
        )

    df_municipios = pd.DataFrame(
        {
            "nombre": df_divipola["nom_mpio"].map(_titulo_colombia),
            "id_departamento": df_divipola["cod_dpto"].map(mapa_departamentos),
            "latitud": df_divipola["latitud"].round(6),
            "longitud": df_divipola["longitud"].round(6),
            "codigo_dane": df_divipola["cod_mpio"],
        }
    )
    df_municipios = df_municipios.sort_values(["id_departamento", "codigo_dane"]).reset_index(
        drop=True
    )
    df_municipios.insert(0, "id", range(1, len(df_municipios) + 1))

    return df_departamentos, df_municipios


def mostrar_resumen(df_departamentos, df_municipios):
    conteo = (
        df_municipios.merge(
            df_departamentos[["id", "nombre", "codigo_dane"]],
            left_on="id_departamento",
            right_on="id",
            suffixes=("_municipio", "_departamento"),
        )
        .groupby(["codigo_dane_departamento", "nombre_departamento"], as_index=False)
        .size()
        .rename(
            columns={
                "codigo_dane_departamento": "codigo_departamento",
                "nombre_departamento": "departamento",
                "size": "municipios",
            }
        )
        .sort_values("codigo_departamento")
    )

    print("\nResumen por departamento:")
    print(conteo.to_string(index=False))

    print("\nPrimeros 12 municipios generados:")
    columnas = ["id", "codigo_dane", "nombre", "id_departamento", "latitud", "longitud"]
    print(df_municipios[columnas].head(12).to_string(index=False))

    print(
        f"\nTotal: {len(df_departamentos)} departamentos y "
        f"{len(df_municipios)} municipios/areas no municipalizadas."
    )


def ejecutar_carga_completa():
    try:
        engine = obtener_engine()
        df_deps, df_muns = generar_cobertura_nacional()
        mostrar_resumen(df_deps, df_muns)

        print("\nLimpiando registros antiguos para evitar duplicacion...")
        with engine.begin() as con:
            con.execute(text("TRUNCATE TABLE municipios CASCADE;"))
            con.execute(text("TRUNCATE TABLE departamentos CASCADE;"))

        print(f"-> Inyectando {len(df_deps)} departamentos...")
        df_deps.to_sql("departamentos", con=engine, if_exists="append", index=False)

        print(f"-> Inyectando {len(df_muns)} municipios consolidados...")
        df_muns.to_sql("municipios", con=engine, if_exists="append", index=False)

        print("\nBase de datos poblada con coordenadas y codigos DANE oficiales.")
    except Exception as e:
        print(f"Error en la carga: {e}")


if __name__ == "__main__":
    ejecutar_carga_completa()
