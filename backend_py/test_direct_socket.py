import socket
import json
import base64

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 9000))
    print("[+] Socket conectado a 127.0.0.1:9000")

    # Prueba 1: Ping
    req_ping = {"idSolicitud": "PING-1", "idCliente": "CLI_BENCHMARK_01", "tipoConsulta": "PING"}
    s.sendall((json.dumps(req_ping) + "\n").encode())
    res1 = s.recv(1024).decode()
    print("[+] Respuesta Ping:", res1.strip())

    # Prueba 2: Diagnostico
    dummy_img = base64.b64encode(bytes([50]*784)).decode()
    req_diag = {
        "idSolicitud": "REQ-TEST-DIAG-01",
        "idCliente": "CLI_BENCHMARK_01",
        "token": "TOKEN_BENCH_TEST_0001",
        "tipoConsulta": "DIAGNOSTICO",
        "modeloDestino": "MODELO_A",
        "imagenB64": dummy_img
    }
    s.sendall((json.dumps(req_diag) + "\n").encode())
    res2 = s.recv(4096).decode()
    print("[+] Respuesta Diagnostico:", res2.strip())
    s.close()
except Exception as e:
    print("[-] Error:", e)
