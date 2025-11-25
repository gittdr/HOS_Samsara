import logging
import pyodbc
import json
from .config import conn_str, BD_TABLE_NOW

def connectdb():
    try:
        conn = pyodbc.connect(conn_str())
        return conn
    except Exception as e:
        logging.error("Error conectando a la base de datos: %s", e)
        raise
    
def save_to_database(rows:list[tuple], fecha_str:str, tbl:str) -> int:
    # Establecer conexión a la base de datos
    
    if not rows:
        logging.warning("No hay datos para guardar en la base de datos.")
        return 0
    
    inserted =0
    conn = None
    
    try:    
        conn = connectdb()
        cur = conn.cursor()
    
        try:
            cur.fast_executemany = True
        except Exception:
            pass
        if tbl == BD_TABLE_NOW:
            cur.execute(f"TRUNCATE TABLE {tbl}")
        
        insert_sql = f"""
        INSERT INTO {tbl} (idUnidad, nombreUnidad, fechaViaje, tiempoViaje, totalTiempoViaje)
        VALUES (?, ?, ?, ?, ?)
        """
        
        payload = [(a_id, a_name, fecha_str, secs, human) for (a_id, a_name, secs, human) in rows]
        
        cur.executemany(insert_sql, payload)
        conn.commit()
        inserted = len(rows)
        return inserted
    except Exception as e: 
        logging.error("Error al guardar en la base de datos: %s", e)
        if conn: 
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
            
def save_to_file(data, name):
    with open(name,'w', encoding="utf-8") as f:
        json.dump(data, f ,indent=4, ensure_ascii=False)