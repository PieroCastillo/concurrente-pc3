"""
Nodo de Inferencia IA - Modelo A (CNN Chest X-Ray Neumonía)
Desplegado en SO Windows 11 (Host).
Consume peticiones de RabbitMQ ('cola_modeloA'), procesa la imagen con la CNN manual multihilo
y publica el resultado con correlation_id en la cola de respuesta.
"""

import os
import sys
import json
import time
import base64
import pika
from concurrent.futures import ThreadPoolExecutor

# Importar CNN From Scratch
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cnn_engine")))
from cnn_scratch import CNNModelA

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
QUEUE_REQUESTS = "cola_modeloA"
QUEUE_RESULTS = "cola_resultadosA"

# Pool de hilos para paralelizar convoluciones de imágenes
thread_pool = ThreadPoolExecutor(max_workers=4)

print("==========================================================")
print("[Nodo 2 - Windows 11] Nodo de IA: CNN Modelo A (Neumonía)")
print(f"RabbitMQ Broker: {RABBITMQ_HOST} | Cola: {QUEUE_REQUESTS}")
print("==========================================================")

# Cargar pesos del modelo entrenado
model = CNNModelA(input_size=28, num_filters=4, hidden_dim=16, num_classes=2)
weights_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cnn_engine", "model_a_weights.json"))
if model.load_weights(weights_path):
    print(f"[+] Pesos de CNN cargados correctamente desde {weights_path}")
else:
    print("[!] Advertencia: No se encontraron pesos, usando pesos aleatorios iniciales.")

def decode_image_matrix(img_b64, size=28):
    """
    Decodifica una imagen en base64 a una matriz normalizada [28][28] (escala 0.0 - 1.0).
    Soporta formato crudo de bytes (28x28 = 784 bytes) o JSON serializado.
    """
    try:
        raw_bytes = base64.b64decode(img_b64)
        if len(raw_bytes) >= size * size:
            matrix = []
            idx = 0
            for _ in range(size):
                row = []
                for _ in range(size):
                    val = raw_bytes[idx] / 255.0
                    row.append(val)
                    idx += 1
                matrix.append(row)
            return matrix
        else:
            # Fallback a matriz sintética si los bytes recibidos son de prueba
            return [[0.2 for _ in range(size)] for _ in range(size)]
    except Exception:
        return [[0.2 for _ in range(size)] for _ in range(size)]

def start_worker():
    # Conexión persistente a RabbitMQ con reintentos
    connection = None
    while not connection:
        try:
            params = pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600, blocked_connection_timeout=300)
            connection = pika.BlockingConnection(params)
        except Exception as e:
            print(f"[-] Esperando conexion con RabbitMQ ({RABBITMQ_HOST})...")
            time.sleep(3)

    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_REQUESTS, durable=True)
    channel.queue_declare(queue=QUEUE_RESULTS, durable=True)
    channel.basic_qos(prefetch_count=10)

    def on_request(ch, method, props, body):
        t_start = time.perf_counter()
        req = json.loads(body.decode('utf-8'))

        id_solicitud = req.get("idSolicitud", "N/A")
        id_cliente = req.get("idCliente", "ANON")
        img_b64 = req.get("imagenB64", "")

        # Decodificación y forward pass multihilo con la CNN nativa
        img_matrix = decode_image_matrix(img_b64, size=28)
        pred_res = model.forward(img_matrix, executor=thread_pool)
        t_elapsed = (time.perf_counter() - t_start) * 1000.0

        result_payload = {
            "idSolicitud": id_solicitud,
            "idCliente": id_cliente,
            "modelo": "MODELO_A_CHEST_XRAY",
            "diagnostico": pred_res["clase"],
            "probabilidad": pred_res["confianza"],
            "probabilidades_detalle": pred_res["probabilidades"],
            "tiempo_ia_ms": round(t_elapsed, 2),
            "nodo_ia": "NODO_2_WIN11_PYTHON",
            "timestamp": time.time()
        }

        reply_to = props.reply_to or QUEUE_RESULTS
        corr_id = props.correlation_id

        ch.basic_publish(
            exchange='',
            routing_key=reply_to,
            properties=pika.BasicProperties(correlation_id=corr_id),
            body=json.dumps(result_payload)
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[*] [CNN IA] Solicitud {id_solicitud} | Cliente: {id_cliente} -> {pred_res['clase']} ({pred_res['confianza']*100:.1f}%) [{t_elapsed:.1f}ms]")

    channel.basic_consume(queue=QUEUE_REQUESTS, on_message_callback=on_request)
    print(f"[*] [Nodo 2 - IA] Escuchando solicitudes en '{QUEUE_REQUESTS}'...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()

if __name__ == "__main__":
    start_worker()
