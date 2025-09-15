import requests 
import json
import logging
import os
import pyodbc
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()

required_env_vars = ["API_TOKEN", "API_URL_TRIPS", "API_URL_ASSETS", "BD_DRIVER", "BD_SERVER", "BD_DATABASE", "BD_USERNAME", "BD_PASSWORD", "BD_TABLE"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
existing_vars = [var for var in required_env_vars if os.getenv(var)]
# print(str(existing_vars))
if missing_vars:
    raise EnvironmentError(f"Faltan las siguientes variables de entorno: {', '.join(missing_vars)}")

bearer = os.getenv("API_TOKEN")

hoy = datetime.now()
log_filename = f".\\Logs\\HOS_{hoy.strftime('%Y-%m-%d_%H-%M-%S')}.log"

hoy_inicio_mx = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
ayer_inicio_mx = hoy_inicio_mx - timedelta(days=1)

headers = {
        "accept": "application/json",
        "authorization": "Bearer " + bearer
    }

logging.basicConfig(
    filename = log_filename,
    level = logging.WARNING,
    format = "%(asctime)s - %(levelname)s - %(message)s"
)

def dt_to_ms(dt: datetime) -> int:
    try:
        if dt.tzinfo is None:  # naive
            dt = dt.replace(tzinfo=timezone.utc)
        else:  # aware
            dt = dt.astimezone(timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception as e:
        logging.error("Error converting date to ms: %s", e)
        return 0
    
def ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)

def request_travel_time(asset_id, start_ms, end_ms, headers):
    after = None
    hasPagination = True
    travel_time = 0
    
    params = {
        "vehicleId": asset_id.get('id'),
        "startMs": start_ms,
        "endMs": end_ms
    }
    
    
    while hasPagination:
        if after:
            params["after"] = after
            
        try:
            response = requests.get(os.getenv('API_URL_TRIPS'), headers=headers, params=params, timeout=30)
            if response.status_code != 200:
                logging.error("Error en API Travel Time: status=%s body=%s", response.status_code, response.text)
                return 0
            trips = response.json()    
                
            for trip in trips.get('trips', []):
                data = ((trip['endMs'] - trip['startMs']) // 1000)
                travel_time += data
            pagination = trips.get("pagination", {}) or {}
            if pagination.get("hasNextPage"):
                endCursor = pagination.get("endCursor")
                if not endCursor:
                    logging.error("Error: endCursor no encontrado en la paginación")
                    break
                after = pagination.get("endCursor")
            else:
                hasPagination = False
        except requests.exceptions.RequestException as e:
            logging.error("Error en el request a la API: %s", e)
            return 0
    return travel_time

def obtain_assets(headers):
    after = None
    data = []
    
    hasPagination = True
    
    while hasPagination:
        params = {"type":"vehicle"}
        if after:
            params["after"] = after
            
        try:
            response = requests.get(os.getenv('API_URL_ASSETS'), headers=headers, params=params, timeout=30)
            if response.status_code != 200:
                logging.error("Error en API Assets: status=%s body=%s", response.status_code, response.text)
                break
            
            data_response = response.json()
            # save_to_file(data_response)
        except requests.exceptions.RequestException as e:
            logging.error("Error en API Assets (request): %s", e)
            break
        
        try:
            for asset in data_response.get('data', []):
                # print(asset)
                if "name" in asset and "id" in asset:
                    data.append({"name": asset["name"],"id": asset["id"]})
                
        except Exception as e:
            logging.error("Error procesando los datos de la API: %s", e)
            break
        
        pagination = data_response.get("pagination") or {}
        if pagination.get("hasNextPage"):
            endCursor = pagination.get("endCursor")
            if not endCursor:
                logging.error("Paginación inconsistente: endCursor no encontrado")
                break
            after = endCursor
        else:
            hasPagination = False
    return data

def save_to_file(data):
    with open('trips.json','w', encoding="utf-8") as f:
        json.dump(data, f ,indent=4, ensure_ascii=False)
# count = 1

def save_to_database(data):
    # Establecer conexión a la base de datos
    
    conn = pyodbc.connect(
        f'DRIVER={{ODBC Driver 18 for SQL Server}};'
        f'SERVER={os.getenv("BD_SERVER")};'
        f'DATABASE={os.getenv("BD_DATABASE")};'
        f'UID={os.getenv("BD_USERNAME")};'
        f'PWD={os.getenv("BD_PASSWORD")};'
        'TrustServerCertificate=yes;'
        'Encrypt=yes;'
    )
    bd = os.getenv('BD_TABLE')
    
    try:
        cursor = conn.cursor()
        cursor.execute(f"TRUNCATE TABLE {bd};")

        # Insertar los registros en la BD
        
        for trc in data:
            cursor.execute(f"""
                INSERT INTO {bd} (idUnidad, nombreUnidad, fechaViaje, tiempoViaje, totalTiempoViaje)
                VALUES (?, ?, ?, ?, ?)
            """, trc['asset_id'], trc['asset_name'], ayer_inicio_mx.strftime('%Y-%m-%d'), trc['traveltimeSeconds'], trc['TravelTime'])

        conn.commit()
    except Exception as e:
        logging.error("Error al guardar en la base de datos: %s", e)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


start_ms = dt_to_ms(ayer_inicio_mx)
end_ms = dt_to_ms(hoy_inicio_mx)
assets = obtain_assets(headers)
assets_data = []

for asset in assets:
    traveltime = request_travel_time(asset, start_ms, end_ms, headers)
    asset_data = {
        "asset_id" : asset['id'],
        "asset_name" : asset['name'],
        "traveltimeSeconds" : traveltime,
        "TravelTime" : str(timedelta(seconds=traveltime))
    }
    # print("count", count, "asset_data", asset_data)
    assets_data.append(asset_data)
    # count += 1

data = {
    "date": ayer_inicio_mx.strftime('%Y-%m-%d'),
    "assets": assets_data
}

# with open('trips.json', 'r', encoding="utf-8") as f:
#     data = json.load(f)

save_to_database(data.get('assets'))


