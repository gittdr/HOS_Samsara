import json
import logging
import requests
from datetime import datetime, timedelta

from app.config import API_URL_ASSETS, API_URL_TRIPS, auth_headers
from app.samsara_req import obtain_assets, request_travel_time, dt_to_ms
from app.db import save_to_database, save_to_file

log_filename = 'Logs\\test_log.log'

# TODO: AJUSTAR PARA CLOUDWATCH
# logging.basicConfig(
#     filename = log_filename,
#     level = logging.INFO,
#     format = "%(asctime)s - %(levelname)s - %(message)s"
# )

# DONE: AJUSTAR PARA CLOUDWATCH

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def run() -> dict:
    hoy_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ayer_inicio = hoy_inicio - timedelta(days=1)
    
    start_ms = dt_to_ms(ayer_inicio)
    end_ms = dt_to_ms(hoy_inicio)
    fecha_str = ayer_inicio.strftime('%Y-%m-%d')
    
    headers = auth_headers()
    session = requests.Session()
    
    # 1 Obtener assets
    assets = obtain_assets(session, API_URL_ASSETS, headers)
    logging.info("Assets obtenidos: %d", len(assets))
    
    # 2 Por cada asset, obtener travel time
    rows = [] 
    for asset in assets:
        secs = request_travel_time(session, API_URL_TRIPS, asset, start_ms, end_ms, headers)
        rows.append((asset['id'], asset['name'], secs, str(timedelta(seconds=secs))))
        
    # 3 Guardar en BD
    inserted = save_to_database(rows, fecha_str)
    logging.info("Registros insertados en BD: %d", inserted)
    
    result = {
        "date": fecha_str,
        "assets": len(assets),
        "inserted": inserted,
        "total_seconds": sum(r[2] for r in rows)
    }

    logging.info("Resultado de la ejecución: %s", result)
    return result

def lambda_handler(event, context):
    try:
        res = run()
        return {"statusCode": 200, "body": json.dumps(res)}
    except Exception as e:
        logging.error("Error en el lambda_handler: %s", e)
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=4))
