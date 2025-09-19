import glob
import os
from dotenv import load_dotenv

# Solo para pruebas, no necesario en el contenedor
load_dotenv()

required_env_vars = [
    "API_TOKEN", 
    "API_URL_TRIPS", 
    "API_URL_ASSETS",
    "BD_DRIVER", 
    "BD_SERVER", 
    "BD_DATABASE", 
    "BD_USERNAME", 
    "BD_PASSWORD", 
    "BD_TABLE"
]

missing = [k for k in required_env_vars if not os.getenv(k)]
if missing:
    raise EnvironmentError(f"Faltan las siguientes variables de entorno: {', '.join(missing)}")

# Helpers
API_TOKEN = os.getenv("API_TOKEN")
API_URL_TRIPS = os.getenv("API_URL_TRIPS")
API_URL_ASSETS = os.getenv("API_URL_ASSETS")
BD_TABLE = os.getenv("BD_TABLE")

def conn_str() -> str:
    driver_path = sorted(glob.glob("/opt/microsoft/msodbcsql18/lib64/libmsodbcsql-*.so*"))[0]
    return (
        f'DRIVER={driver_path};'
        f'SERVER={os.getenv("BD_SERVER")};'
        f'DATABASE={os.getenv("BD_DATABASE")};'
        f'UID={os.getenv("BD_USERNAME")};'
        f'PWD={os.getenv("BD_PASSWORD")};'
        'TrustServerCertificate=yes;'
        'Encrypt=yes;'
    )

def auth_headers() -> dict:
    return {
        "accept": "application/json",
        "authorization": "Bearer " + API_TOKEN
    }