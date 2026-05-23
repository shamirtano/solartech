# :sun_with_face: Inteligencia Solar - NASA POWER :rocket:

Este proyecto es una plataforma interactiva de analítica de datos diseñada para evaluar la viabilidad técnica y el potencial energético de proyectos de energía solar fotovoltaica en los 32 departamentos de Colombia. La aplicación extrae de forma dinámica datos climatológicos y satelitales en tiempo real a través de la API global **NASA POWER (Renewable Energy Community)**, cruzándolos con la división político-administrativa del país gestionada en una base de datos relacional en **Supabase**.

---

## :bar_chart: Características Principales

* :earth_americas: **Cobertura Nacional Completa:** Catálogo de municipios distribuido por departamentos con coordenadas geográficas reales (Latitud y Longitud) almacenadas de forma nativa.
* :arrows_clockwise: **Sincronización en Tiempo Real:** Conexión directa con la API de la NASA para la extracción de series temporales diarias de variables meteorológicas críticas.
* :shield: **Depuración Automática de Datos:** Filtro algorítmico integrado que detecta, aísla y descarta códigos de error de transmisión (valores negativos o `-999`), garantizando promedios limpios y realistas.
* :chart_with_upwards_trend: **Visualización Interactiva:** Enfoque cartográfico dinámico mediante mapas interactivos y renderizado de gráficos lineales de evolución histórica con soporte cross-platform.
* :clipboard: **Dictamen Técnico Automatizado:** Módulo algorítmico que evalúa el promedio de irradiancia capturado y genera un reporte de viabilidad detallado (Alta, Moderada o Condicionada) según el recurso disponible.

---

## :chart_with_upwards_trend: Variables Analíticas Soportadas

1. **Irradiancia Global (ALLSKY_SFC_SW_DWN):** Flujo de energía solar incidente en la superficie (kWh/m²/día).
2. **Temperatura Ambiente (T2M):** Temperatura media del aire a 2 metros de altura (°C).
3. **Humedad Relativa (RH2M):** Porcentaje de humedad en el ambiente a 2 metros (%).
4. **Velocidad del Viento (WS2M):** Velocidad media del viento a 2 metros de altura (m/s).
5. **Precipitación (PRECTOTCORR):** Pluviometría corregida diaria (mm/día).

---

## :gear: Arquitectura del Modelo de Datos (Supabase)

La base de datos relacional está estructurada para optimizar el rendimiento y escalabilidad de la aplicación mediante el siguiente mapa de relaciones:

* **`departamentos`:** Entidad maestra que contiene el nombre, código DANE de dos dígitos y la región natural de Colombia.
* **`municipios`:** Almacena los registros municipales georreferenciados enlazados mediante una llave foránea (`id_departamento`) a la entidad superior.
* **`estados_proyectos`, `recursos` y `tecnologias`:** Tablas de catálogo para la clasificación estandarizada de proyectos bajo los lineamientos de la UPME (Unidad de Planeación Minero Energética).
* **`mediciones_nasa` y `proyectos_upme`:** Entidades transaccionales y de registro histórico indexadas por municipio.

---

## :rocket: Guía de Despliegue Local

Sigue estos pasos paso a paso para configurar tu entorno local y ejecutar la aplicación:

### 1. Clonar el Repositorio e Instalar Dependencias
Asegúrate de contar con Python 3.10 o superior instalado. Abre la terminal en el directorio del proyecto y ejecuta:

```bash
# Instalar las librerías requeridas del ecosistema de Python
pip install streamlit pandas requests emoji sqlalchemy psycopg2-binary python-dotenv numpy
```

### 2. Configurar Variables de Entorno2.
Crea un archivo llamado .env en la raíz del proyecto para almacenar de forma segura las credenciales de conexión a tu clúster de Supabase:

```bash
DB_USER=postgres
DB_PASSWORD=tu_contraseña_de_supabase
DB_HOST=your-project-id.supabase.co
DB_PORT=5432
DB_NAME=postgres
```

### 3. Poblar la Base de Datos con Cobertura Nacional
Antes de lanzar la interfaz, ejecuta el script de migración masiva local para limpiar e inyectar el catálogo robusto de municipios y departamentos georreferenciados:

```bash
python poblar_completo_colombia.py
```

### 4. Lanzar la Aplicación en Streamlit
Inicia el servidor local de desarrollo de Streamlit para desplegar la interfaz en tu navegador:

```bash
streamlit run app.py
```

### :globe_with_meridians: Despliegue en la Nube (Streamlit Community Cloud)
Para publicar el proyecto de forma pública y gratuita, sigue estos pasos:

1. Sube el código completo a un repositorio público en GitHub (asegúrate de agregar el archivo .env al archivo .gitignore para no filtrar tus contraseñas).

2. Crea un archivo llamado requirements.txt en la raíz con el listado de librerías para que la nube pueda instalarlas automáticamente:

    ```bash
        streamlit
        pandas
        requests
        emoji
        sqlalchemy
        psycopg2-binary
        python-dotenv
        numpy
    ```
3. Inicia sesión en Streamlit Share utilizando tu cuenta de GitHub.

4. Haz clic en "New app", selecciona tu repositorio, la rama (main o master) y el archivo de entrada (app.py).

5. Despliega el menú "Advanced settings" y en la sección "Secrets", pega los mismos valores de tu archivo .env utilizando el formato TOML admitido por Streamlit:

    ```toml
    DB_USER = "postgres"
    DB_PASSWORD = "tu_contraseña_de_supabase"
    DB_HOST = "your-project-id.supabase.co"
    DB_PORT = 5432
    DB_NAME = "postgres"
    ```
6. Haz clic en "Deploy!" y en un par de minutos tu plataforma de Inteligencia Solar estará operativa a nivel mundial.