import logging
import requests
from datetime import datetime, timezone

from .db import save_to_file
# --- Tiempo ---

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

# --- API Calls ---

def obtain_assets(session: requests.Session, api_url_assets: str, headers: dict) -> list[dict]:
    after = None
    data: list[dict] = []
    
    # hasPagination = True
    
    while True:
        params = {"type":"vehicle"}
        if after:
            params["after"] = after
            
        try:
            r = session.get(api_url_assets, headers=headers, params=params, timeout=30)
            if r.status_code != 200:
                logging.error("Error en API Assets: status=%s body=%s", r.status_code, r.text)
                break
            
            body = r.json()
            for asset in body.get("data", []):
                if "name" in asset and "id" in asset:
                    data.append({"name": asset["name"],"id": asset["id"]})
            pag = body.get("pagination") or {}
            if pag.get("hasNextPage"):
                after = pag.get("endCursor")
                if not after:
                    logging.error("Paginación inconsistente: endCursor no encontrado")
                    break
            else:
                break
        except requests.exceptions.RequestException as e:
            logging.error("Error en API Assets (request): %s", e)
            break
    return data    

def request_travel_time(session: requests.Session, api_url_trips: str, asset: dict, start_ms, end_ms, headers: dict) -> int:
    after = None
    travel_time = 0
    
    params = {
        "vehicleId": asset["id"],
        "startMs": start_ms,
        "endMs": end_ms
    }
    
    while True:
        if after:
            params["after"] = after
        try:
            r = session.get(api_url_trips, headers=headers, params=params, timeout=30)
            if r.status_code != 200:
                logging.error("Error en API Travel Time: status=%s body=%s", r.status_code, r.text)
                return 0
            body = r.json()
            tmp = {
                "Params": params,
                "body": r.json()
            }
            # save_to_file(tmp, f"units\\{asset['name']}.json")
            for trip in body.get('trips', []):
                s = trip.get('startMs'); 
                e = trip.get('endMs') 
                e = end_ms if e == 9223372036854775807 else e
                if isinstance(s, int) and isinstance(e, int) and e >= s:
                    travel_time += (e - s) // 1000
            logging.debug("Asset %s: Trip de secs=%d", asset['name'], travel_time)
                    
            pag = body.get("pagination") or {}
            if pag.get("hasNextPage"):
                after = pag.get("endCursor")
                if not after:
                    logging.error("Paginación inconsistente: endCursor no encontrado")
                    break
            else:
                break
        except requests.exceptions.RequestException as e:
            logging.error("Error en API Travel Time (request): %s", e)
            return 0
    return travel_time