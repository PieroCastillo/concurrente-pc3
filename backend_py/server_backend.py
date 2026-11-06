"""
Nodo Backend Central (Servidor Sockets TCP + RabbitMQ Middleware + Servidor HTTP Nativo)
Implementado usando ÚNICAMENTE el SDK estándar de Python (socket, threading, json, time).
No utiliza WebSockets, Flask, Django, Socket.IO ni librerías externas de transporte.

Flujo de la arquitectura:
Cliente TCP -> Sockets Backend -> RabbitMQ (Validación C# BD2) -> RabbitMQ (CNN IA)
            -> RabbitMQ (Persistencia BD1 Postgres) -> Sockets Backend -> Cliente TCP.
"""

import os
import sys
import socket
import threading
import json
import time
import uuid
import pika

HOST_TCP = "0.0.0.0"
PORT_TCP = 9000         # Puerto para Sockets TCP puros (Desktop, Android, Benchmarks)
PORT_HTTP = 8080        # Puerto HTTP Nativo con Sockets para Frontend Web

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")

QUEUE_MODELO_A = "cola_modeloA"
QUEUE_VALIDACION = "cola_validacion_cliente"
QUEUE_PERSISTENCIA = "cola_persistencia_bd1"
QUEUE_RESPUESTAS = "cola_respuestas_backend"

# Diccionario de respuestas pendientes correlacionadas por UUID
# Concurrencia protegida mediante Lock
pending_requests = {}
pending_lock = threading.Lock()

class BackendServer:
    def __init__(self):
        self.rabbit_conn = None
        self.rabbit_channel = None
        self.init_rabbitmq()

    def init_rabbitmq(self):
        """Inicializa colas y canal RabbitMQ"""
        retries = 0
        while not self.rabbit_conn and retries < 15:
            try:
                params = pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600)
                self.rabbit_conn = pika.BlockingConnection(params)
                self.rabbit_channel = self.rabbit_conn.channel()
                
                # Declaración de todas las colas del sistema
                self.rabbit_channel.queue_declare(queue=QUEUE_MODELO_A, durable=True)
                self.rabbit_channel.queue_declare(queue=QUEUE_VALIDACION, durable=True)
                self.rabbit_channel.queue_declare(queue=QUEUE_PERSISTENCIA, durable=True)
                self.rabbit_channel.queue_declare(queue=QUEUE_RESPUESTAS, durable=True)
                print("[+] Conectado a RabbitMQ desde Backend Central.")
                break
            except Exception as e:
                retries += 1
                print(f"[-] Esperando a RabbitMQ... ({retries}/15): {e}")
                time.sleep(3)

        # Hilo dedicado para consumir respuestas asíncronas de RabbitMQ
        threading.Thread(target=self._rabbit_consumer_loop, daemon=True).start()

    def _rabbit_consumer_loop(self):
        """Escucha respuestas de IA y Validación para despertar hilos de clientes correspondientes"""
        try:
            params = pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600)
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.queue_declare(queue=QUEUE_RESPUESTAS, durable=True)

            def on_reply(ch_sub, method, props, body):
                corr_id = props.correlation_id
                data = json.loads(body.decode('utf-8'))
                
                with pending_lock:
                    if corr_id in pending_requests:
                        event, result_box = pending_requests[corr_id]
                        result_box.append(data)
                        event.set()
                ch_sub.basic_ack(delivery_tag=method.delivery_tag)

            ch.basic_consume(queue=QUEUE_RESPUESTAS, on_message_callback=on_reply)
            ch.start_consuming()
        except Exception as ex:
            print(f"[!] Error en hilo consumidor RabbitMQ: {ex}")

    def rpc_call(self, queue_name, payload, timeout=10.0):
        """Publica a RabbitMQ y espera respuesta sincronizada por Correlation-Id"""
        corr_id = str(uuid.uuid4())
        event = threading.Event()
        result_box = []

        with pending_lock:
            pending_requests[corr_id] = (event, result_box)

        # Publicar usando conexión segura (canal local temporal si es multihilo)
        try:
            params = pika.ConnectionParameters(host=RABBITMQ_HOST)
            conn_temp = pika.BlockingConnection(params)
            ch_temp = conn_temp.channel()
            ch_temp.basic_publish(
                exchange='',
                routing_key=queue_name,
                properties=pika.BasicProperties(
                    reply_to=QUEUE_RESPUESTAS,
                    correlation_id=corr_id
                ),
                body=json.dumps(payload)
            )
            conn_temp.close()
        except Exception as err:
            with pending_lock:
                pending_requests.pop(corr_id, None)
            return {"error": f"Fallo al publicar en RabbitMQ: {err}"}

        # Esperar respuesta
        notified = event.wait(timeout=timeout)
        with pending_lock:
            pending_requests.pop(corr_id, None)

        if notified and result_box:
            return result_box[0]
        else:
            return {"error": "Timeout esperando respuesta de los nodos distribuidos"}

    def handle_client_socket(self, client_sock, client_addr):
        """
        Maneja cada cliente conectado por Socket TCP puro.
        Protocolo delimitado por newline: cada paquete termina en '\n'.
        """
        buffer = ""
        try:
            while True:
                data = client_sock.recv(4096)
                if not data:
                    break
                buffer += data.decode('utf-8')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue
                    
                    req_json = json.loads(line)
                    req_id = req_json.get("idSolicitud", str(uuid.uuid4()))
                    id_cliente = req_json.get("idCliente", "CLI_DESKTOP")
                    tipo = req_json.get("tipoConsulta", "DIAGNOSTICO")

                    if tipo == "PING":
                        resp = {"status": "PONG", "timestamp": time.time()}
                        client_sock.sendall((json.dumps(resp) + "\n").encode('utf-8'))
                        continue

                    # PASO 1: Validación en BD2 (MariaDB) vía RabbitMQ (Worker C# en Debian)
                    val_req = {
                        "idSolicitud": req_id,
                        "idCliente": id_cliente,
                        "token": req_json.get("token", ""),
                        "modeloDestino": req_json.get("modeloDestino", "MODELO_A")
                    }
                    val_res = self.rpc_call(QUEUE_VALIDACION, val_req, timeout=5.0)

                    if not val_res.get("valido", False):
                        err_resp = {
                            "idSolicitud": req_id,
                            "error": f"Acceso denegado por BD2: {val_res.get('motivo', 'Cliente invalido')}",
                            "estado": "RECHAZADO"
                        }
                        client_sock.sendall((json.dumps(err_resp) + "\n").encode('utf-8'))
                        continue

                    # PASO 2: Inferencia en Nodo IA (CNN from scratch) vía RabbitMQ
                    ia_req = {
                        "idSolicitud": req_id,
                        "idCliente": id_cliente,
                        "imagenB64": req_json.get("imagenB64", ""),
                        "formato": req_json.get("formato", "GRAYSCALE_28X28")
                    }
                    ia_res = self.rpc_call(QUEUE_MODELO_A, ia_req, timeout=10.0)

                    # PASO 3: Publicar asíncronamente en BD1 (PostgreSQL) para persistir historial
                    if "diagnostico" in ia_res:
                        try:
                            # Notificar persistencia asíncrona a BD1
                            p_conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
                            p_ch = p_conn.channel()
                            p_ch.basic_publish(
                                exchange='',
                                routing_key=QUEUE_PERSISTENCIA,
                                body=json.dumps(ia_res)
                            )
                            p_conn.close()
                        except Exception as e:
                            print(f"[!] Error enviando a cola_persistencia: {e}")

                    # PASO 4: Enviar diagnóstico completo al Cliente
                    client_sock.sendall((json.dumps(ia_res) + "\n").encode('utf-8'))

        except Exception as ex:
            # Cliente desconectado o error
            pass
        finally:
            client_sock.close()

    def start_tcp_server(self):
        """Inicia servidor Socket TCP multihilo"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST_TCP, PORT_TCP))
        server.listen(100)
        print(f"[+] Servidor Socket TCP escuchando en {HOST_TCP}:{PORT_TCP}")

        while True:
            client_sock, client_addr = server.accept()
            # Hilo concurrente por cada cliente TCP
            t = threading.Thread(target=self.handle_client_socket, args=(client_sock, client_addr), daemon=True)
            t.start()

    def handle_http_request(self, client_sock):
        """
        Servidor Web HTTP 1.1 implementado NATIVAMENTE con sockets puros.
        Sin Flask, FastAPI, Django ni dependencias externas.
        Sirve el HTML/JS estático y responde endpoints API /api/diagnosticar y /api/ping.
        """
        try:
            req_data = client_sock.recv(65536).decode('utf-8', errors='ignore')
            if not req_data:
                client_sock.close()
                return

            lines = req_data.split('\r\n')
            req_line = lines[0].split(' ')
            if len(req_line) < 2:
                client_sock.close()
                return

            method, path = req_line[0], req_line[1]

            # Servir página Web HTML
            if method == "GET" and (path == "/" or path.startswith("/index")):
                html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "client_web", "index.html"))
                content = b"<h1>Portal Web Medico CNN</h1>"
                if os.path.exists(html_path):
                    with open(html_path, 'rb') as f:
                        content = f.read()

                headers = "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n" \
                          f"Content-Length: {len(content)}\r\nConnection: close\r\n\r\n"
                client_sock.sendall(headers.encode('utf-8') + content)

            # Endpoint API POST /api/diagnosticar
            elif method == "POST" and path == "/api/diagnosticar":
                # Extraer body después de las cabeceras
                parts = req_data.split('\r\n\r\n', 1)
                body_json = parts[1] if len(parts) > 1 else "{}"
                req_json = json.loads(body_json)

                req_id = req_json.get("idSolicitud", str(uuid.uuid4()))
                id_cliente = req_json.get("idCliente", "CLI_WEB_01")

                # Validación BD2
                val_req = {"idSolicitud": req_id, "idCliente": id_cliente, "token": req_json.get("token", ""), "modeloDestino": "MODELO_A"}
                val_res = self.rpc_call(QUEUE_VALIDACION, val_req, timeout=5.0)

                if not val_res.get("valido", False):
                    resp_data = {"error": f"BD2 Rechazado: {val_res.get('motivo')}"}
                else:
                    # Inferencia IA
                    ia_req = {"idSolicitud": req_id, "idCliente": id_cliente, "imagenB64": req_json.get("imagenB64", "")}
                    resp_data = self.rpc_call(QUEUE_MODELO_A, ia_req, timeout=10.0)

                resp_bytes = json.dumps(resp_data).encode('utf-8')
                headers = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n" \
                          f"Content-Length: {len(resp_bytes)}\r\nConnection: close\r\n\r\n"
                client_sock.sendall(headers.encode('utf-8') + resp_bytes)

            else:
                resp = b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                client_sock.sendall(resp)

        except Exception as e:
            pass
        finally:
            client_sock.close()

    def start_http_server(self):
        """Inicia servidor HTTP nativo sobre sockets"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST_TCP, PORT_HTTP))
        server.listen(50)
        print(f"[+] Servidor HTTP Nativo con Sockets escuchando en http://localhost:{PORT_HTTP}")

        while True:
            client_sock, _ = server.accept()
            threading.Thread(target=self.handle_http_request, args=(client_sock,), daemon=True).start()

def main():
    print("==========================================================")
    print("[Nodo Backend Central] Iniciando Servidores Distribuidos")
    print(f"RabbitMQ: {RABBITMQ_HOST} | TCP Port: {PORT_TCP} | HTTP Port: {PORT_HTTP}")
    print("==========================================================")
    backend = BackendServer()

    # Hilo para servidor HTTP Nativo
    threading.Thread(target=backend.start_http_server, daemon=True).start()

    # Hilo principal para Servidor TCP Sockets
    backend.start_tcp_server()

if __name__ == "__main__":
    main()
