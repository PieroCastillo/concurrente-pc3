"""
Worker de Persistencia BD1 (PostgreSQL)
Recibe diagnósticos procesados desde RabbitMQ ('cola_persistencia_bd1')
y los almacena concurrentemente usando transacciones y control de concurrencia.
"""

import os
import json
import time
import hashlib
import pika
import psycopg2
from psycopg2 import pool

PG_HOST = os.environ.get("POSTGRES_HOST", "localhost")
PG_PORT = int(os.environ.get("POSTGRES_PORT", 5432))
PG_DB = os.environ.get("POSTGRES_DB", "bd1_diagnosticos")
PG_USER = os.environ.get("POSTGRES_USER", "admin_pg")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "SecretPassword123!")

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
QUEUE_PERSISTENCE = "cola_persistencia_bd1"

print("==========================================================")
print("[Nodo BD1 - PostgreSQL] Worker de Almacenamiento Diagnósticos")
print(f"PostgreSQL: {PG_HOST}:{PG_PORT} | DB: {PG_DB}")
print("==========================================================")

# Pool de conexiones concurrente para PostgreSQL
db_pool = None
for retry in range(15):
    try:
        db_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=2,
            maxconn=30,
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS
        )
        print("[+] Pool de conexiones a PostgreSQL inicializado exitosamente.")
        break
    except Exception as e:
        print(f"[-] Esperando conexion a PostgreSQL ({retry+1}/15): {e}")
        time.sleep(3)

def guardar_diagnostico_transaccional(data):
    """Guarda metadatos y diagnóstico en BD1 usando transacción ACID segura"""
    if not db_pool:
        return False
    
    conn = db_pool.getconn()
    try:
        id_solicitud = data.get("idSolicitud", "REQ-UNKNOWN")
        id_cliente = data.get("idCliente", "CLI-UNKNOWN")
        modelo = data.get("modelo", "MODELO_A")
        diagnostico = data.get("diagnostico", "INDETERMINADO")
        prob = float(data.get("probabilidad", 0.0))
        tiempo_ia = float(data.get("tiempo_ia_ms", 0.0))
        nodo_ia = data.get("nodo_ia", "NODO_2_WIN11_PYTHON")

        # Generar hash SHA256 simulado para los metadatos de imagen
        hash_sha256 = hashlib.sha256(id_solicitud.encode('utf-8')).hexdigest()

        with conn.cursor() as cur:
            # 1. Insertar metadatos de imagen (si no existe)
            cur.execute("""
                INSERT INTO metadatos_imagen (id_solicitud, hash_sha256, dimension_alto, dimension_ancho, formato, tamanio_bytes)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_solicitud) DO NOTHING;
            """, (id_solicitud, hash_sha256, 28, 28, "GRAYSCALE_RAW", 784))

            # 2. Insertar resultado diagnóstico en historial
            cur.execute("""
                INSERT INTO historial_diagnosticos (id_solicitud, id_cliente, modelo_usado, diagnostico, probabilidad, tiempo_ia_ms, nodo_ia)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, (id_solicitud, id_cliente, modelo, diagnostico, prob, tiempo_ia, nodo_ia))

        conn.commit()
        return True
    except Exception as err:
        conn.rollback()
        print(f"[!] Error al persistir en BD1: {err}")
        return False
    finally:
        db_pool.putconn(conn)

def start_worker():
    connection = None
    while not connection:
        try:
            params = pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600)
            connection = pika.BlockingConnection(params)
        except Exception:
            print(f"[-] Esperando broker RabbitMQ ({RABBITMQ_HOST})...")
            time.sleep(3)

    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_PERSISTENCE, durable=True)
    channel.basic_qos(prefetch_count=20)

    def on_message(ch, method, props, body):
        payload = json.loads(body.decode('utf-8'))
        guardar_diagnostico_transaccional(payload)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE_PERSISTENCE, on_message_callback=on_message)
    print(f"[*] Worker BD1 listo y consumiendo de '{QUEUE_PERSISTENCE}'...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()

if __name__ == "__main__":
    start_worker()
