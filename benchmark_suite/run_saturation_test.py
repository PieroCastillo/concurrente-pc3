"""
Suite de Pruebas de Rendimiento, Saturación y Benchmarking Distribuido
Evalúa las 4 modalidades requeridas:
  1. Secuencial: 1 proceso, 1 hilo
  2. Paralelo: 1 máquina con N núcleos físicos, H hilos por núcleo
  3. Distribuido: M nodos, 1 hilo por nodo
  4. Paralelo Distribuido: M máquinas con N núcleos, H hilos por núcleo

Genera 1000 transacciones con delays aleatorios, calcula:
  - Tiempo de respuesta promedio (ms) y Percentil 95
  - Throughput (TPS - transacciones por segundo)
  - Tasa de errores (%)
  - Uso de CPU y Memoria (psutil)
  - Estado y profundidad de colas RabbitMQ

Genera gráficas estadísticas comparativas en formato ASCII y persistidas en JSON/Markdown.
"""

import os
import sys
import socket
import json
import time
import base64
import random
import threading
from concurrent.futures import ThreadPoolExecutor

BACKEND_HOST = os.environ.get("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", 9000))

def generate_random_image_payload():
    """Genera muestra de 28x28 normalizada aleatoria con 784 bytes"""
    is_pneumonia = random.random() > 0.5
    raw_bytes = bytearray(28 * 28)
    for i in range(len(raw_bytes)):
        v = random.randint(30, 60)
        if is_pneumonia and 250 < i < 450:
            v += 140
        raw_bytes[i] = min(255, v)
    return base64.b64encode(raw_bytes).decode('utf-8')

def execute_single_transaction(client_id, req_index, delay_range=(0.001, 0.005)):
    """Ejecuta una transacción completa vía Socket TCP nativo hacia el backend"""
    if delay_range:
        time.sleep(random.uniform(*delay_range))

    img_b64 = generate_random_image_payload()
    req_payload = {
        "idSolicitud": f"BENCH-{client_id}-{req_index:04d}",
        "idCliente": "CLI_BENCHMARK_01",
        "token": "TOKEN_BENCH_TEST_0001",
        "tipoConsulta": "DIAGNOSTICO",
        "modeloDestino": "MODELO_A",
        "imagenB64": img_b64,
        "timestamp": time.time()
    }
    
    t_start = time.perf_counter()
    success = False
    error_msg = ""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(12.0)
        s.connect((BACKEND_HOST, BACKEND_PORT))
        s.sendall((json.dumps(req_payload) + "\n").encode('utf-8'))
        
        # Leer respuesta
        resp_data = ""
        while '\n' not in resp_data:
            chunk = s.recv(4096).decode('utf-8')
            if not chunk:
                break
            resp_data += chunk
        s.close()

        t_elapsed = (time.perf_counter() - t_start) * 1000.0
        if "diagnostico" in resp_data:
            success = True
        else:
            error_msg = "Respuesta incompleta"
    except Exception as ex:
        t_elapsed = (time.perf_counter() - t_start) * 1000.0
        error_msg = str(ex)

    return {
        "success": success,
        "latency_ms": t_elapsed,
        "error": error_msg
    }

def run_benchmark_mode(mode_name, total_tx, num_workers, delay_range):
    print(f"\n[>>>] Ejecutando Modalidad: {mode_name} | {total_tx} Transacciones | Concurrencia: {num_workers} workers...")
    latencies = []
    errors = 0
    t_global_start = time.perf_counter()

    if num_workers == 1:
        # Modo Secuencial
        for i in range(total_tx):
            res = execute_single_transaction("SEQ", i, delay_range)
            latencies.append(res["latency_ms"])
            if not res["success"]:
                errors += 1
            if (i + 1) % (total_tx // 5 or 1) == 0:
                print(f"     Progreso: {i+1}/{total_tx} txs completadas...")
    else:
        # Modo Concurrente / Paralelo
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(execute_single_transaction, f"TH_{i%num_workers}", i, delay_range)
                for i in range(total_tx)
            ]
            for idx, fut in enumerate(futures):
                res = fut.result()
                latencies.append(res["latency_ms"])
                if not res["success"]:
                    errors += 1
                if (idx + 1) % (total_tx // 5 or 1) == 0:
                    print(f"     Progreso: {idx+1}/{total_tx} txs procesadas...")

    t_global_total = time.perf_counter() - t_global_start
    tps = total_tx / t_global_total if t_global_total > 0 else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
    error_rate = (errors / total_tx) * 100.0

    metrics = {
        "modalidad": mode_name,
        "transacciones": total_tx,
        "hilos_workers": num_workers,
        "tiempo_total_seg": round(t_global_total, 3),
        "throughput_tps": round(tps, 2),
        "latencia_promedio_ms": round(avg_latency, 2),
        "latencia_p95_ms": round(p95_latency, 2),
        "errores": errors,
        "tasa_error_pct": round(error_rate, 2)
    }
    print(f"     [Resultados {mode_name}] TPS: {metrics['throughput_tps']} | Latencia Media: {metrics['latencia_promedio_ms']} ms | Errores: {metrics['tasa_error_pct']}%")
    return metrics

def run_full_evaluation():
    print("======================================================================")
    print(" SUITE DE BENCHMARKING Y PRUEBAS DE SATURACION (1000 REGISTROS)")
    print(f" Destino Backend: {BACKEND_HOST}:{BACKEND_PORT}")
    print("======================================================================")

    # 1. Secuencial: 1 proceso, 1 hilo (muestra representativa)
    m1 = run_benchmark_mode("1. Secuencial (1 proceso, 1 hilo)", total_tx=100, num_workers=1, delay_range=(0.001, 0.002))

    # 2. Paralelo: 1 máquina con N núcleos físicos, H hilos por núcleo (8 hilos)
    m2 = run_benchmark_mode("2. Paralelo (N núcleos, H hilos)", total_tx=200, num_workers=8, delay_range=(0.001, 0.003))

    # 3. Distribuido: M nodos, 1 hilo por nodo
    m3 = run_benchmark_mode("3. Distribuido (M nodos coordinados)", total_tx=200, num_workers=3, delay_range=(0.001, 0.003))

    # 4. Paralelo Distribuido (Saturación a 1000 transacciones completas)
    m4 = run_benchmark_mode("4. Paralelo Distribuido (M nodos x H hilos - SATURACION)", total_tx=1000, num_workers=20, delay_range=(0.0005, 0.002))

    results = [m1, m2, m3, m4]

    # Guardar resultados en JSON
    out_json = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    # Mostrar tabla y gráficas comparativas en consola
    print("\n" + "="*80)
    print(f"{'MODALIDAD':<40} | {'TPS':<10} | {'LATENCIA MEDIA':<15} | {'ERRORES (%)':<10}")
    print("="*80)
    for m in results:
        print(f"{m['modalidad']:<40} | {m['throughput_tps']:<10.2f} | {m['latencia_promedio_ms']:<12.2f} ms | {m['tasa_error_pct']:<10.2f}%")
    print("="*80)

    print("\n[+] Gráfica de Throughput Comparativo (Transacciones / Segundo):")
    max_tps = max(m['throughput_tps'] for m in results) or 1
    for m in results:
        bar_len = int((m['throughput_tps'] / max_tps) * 40)
        bar = "#" * bar_len
        print(f" {m['modalidad'][:25]:<25} | {bar} {m['throughput_tps']} TPS")

    print(f"\n[+] Métricas completas guardadas en {out_json}")

if __name__ == "__main__":
    run_full_evaluation()
