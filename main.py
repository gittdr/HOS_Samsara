import glob, json, logging, requests, pytz, os, pyodbc, subprocess

from datetime import datetime, timedelta

from app.config import API_URL_ASSETS, API_URL_TRIPS, auth_headers, BD_TABLE_HIST, BD_TABLE_NOW
from app.samsara_req import obtain_assets, request_travel_time, dt_to_ms, ms_to_dt
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

def _debug_odbc():
    print("LD_LIBRARY_PATH:", os.environ.get("LD_LIBRARY_PATH"))
    print("ODBCINSTINI:", os.environ.get("ODBCINSTINI"))
    try:
        out = subprocess.check_output(["cat", "/etc/odbcinst.ini"]).decode()
        print("/etc/odbcinst.ini:\n", out)
    except Exception as e:
        print("cat /etc/odbcinst.ini error:", repr(e))
    try:
        print("pyodbc.drivers():", pyodbc.drivers())
    except Exception as e:
        print("pyodbc.drivers() error:", repr(e))
    print("Driver files:", glob.glob("/opt/microsoft/msodbcsql18/lib64/libmsodbcsql-*.so*"))

def run() -> dict:

    execution_time = datetime.now().astimezone(pytz.timezone("America/Mexico_City"))  # Adjust for debugging
    local_time = execution_time.astimezone(pytz.timezone("America/Mexico_City")) if execution_time else None
    hoy_utc = local_time.astimezone(pytz.utc)
    hour = hoy_utc.hour if local_time else None
    minute = hoy_utc.minute if local_time else None

    hoy_inicio = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    # hoy_inicio = hoy_inicio_local.astimezone(pytz.timezone("America/Mexico_City"))
    # print("Hoy inicio (local):", hoy_inicio_local, "Hoy inicio (UTC):", hoy_inicio)
    # print("Hoy (local):", local_time, "Hoy (UTC):", hoy_utc)
    if hour == 6 and minute == 0:
        ayer_inicio = hoy_inicio - timedelta(days=1)
        start_ms = dt_to_ms(ayer_inicio)
        end_ms = dt_to_ms(hoy_inicio)
        fecha_str = ayer_inicio.strftime('%Y-%m-%d')
        tbl = BD_TABLE_HIST
    elif not hour:
        logging.warning(f"La hora de ejecución no está disponible: {execution_time}, se usará el rango desde el inicio del día hasta ahora.")
        start_ms = dt_to_ms(hoy_inicio)
        end_ms = dt_to_ms(datetime.now())
        fecha_str = hoy_inicio.strftime('%Y-%m-%d')
        tbl = BD_TABLE_NOW
    else:
        start_ms = dt_to_ms(hoy_inicio)
        end_ms = dt_to_ms(hoy_utc)
        fecha_str = hoy_inicio.strftime('%Y-%m-%d')
        tbl = BD_TABLE_NOW
    
    headers = auth_headers()
    session = requests.Session()
    
    # 1 Obtener assets
    assets = obtain_assets(session, API_URL_ASSETS, headers)
    logging.info("Assets obtenidos: %d", len(assets))
    print(f"Assets obtenidos: {len(assets)}")
    
    # 2 Por cada asset, obtener travel time
    rows = [] 
    count = 1
    for asset in assets:
        secs = request_travel_time(session, API_URL_TRIPS, asset, start_ms, end_ms, headers)
        inicio = ms_to_dt(start_ms)
        fin = ms_to_dt(end_ms)
        # logging.info("Unidad %s - segundos: %s - tiempo: %s - inicio: %s - fin: %s", asset['name'], secs, str(timedelta(seconds=secs)), ms_to_dt(start_ms), ms_to_dt(end_ms))
        print(f"Count: {count} Unidad {asset['name']} - segundos: {secs} - tiempo: {str(timedelta(seconds=secs))} - inicio: {inicio} - fin: {fin}")
        count += 1
        rows.append((asset['id'], asset['name'], secs, str(timedelta(seconds=secs))))
        
    # 3 Guardar en BD
    inserted = save_to_database(rows, fecha_str, tbl)
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
        # _debug_odbc()
        res = run()
        return {"statusCode": 200, "body": json.dumps(res)}
    except Exception as e:
        logging.error("Error en el lambda_handler: %s", e)
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=4))

    event = {
        "version": "0",
        "id": "a1b2c3d4-5678-90ab-cdef-EXAMPLE11111",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "account": "123456789012",
        "time": "2025-09-22T18:00:00Z",
        "region": "us-east-1",
        "resources": ["arn:aws:events:us-east-1:123456789012:rule/MyRule"],
        "detail": {}
    }
    context = {}
    lambda_handler(event, context)
