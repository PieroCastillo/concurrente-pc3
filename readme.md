# Arquitectura Distribuida y Reporte de Pruebas de Saturación (PC3)

## 1. Arquitectura Diseñada y Heterogeneidad Estricta

El sistema cumple con el principio **Open AI Cubes** mediante nodos distribuidos desacoplados que interactúan a través de sockets estándar y RabbitMQ.

```mermaid
flowchart TD
    subgraph Clientes ["Capa de Clientes Heterogéneos"]
        C1["Cliente Desktop Kotlin/Java (Swing GUI)"]
        C2["Cliente Web (HTML5/Canvas + JS Nativo)"]
        C3["Cliente Móvil Android (Kotlin nativo)"]
    end

    subgraph Backend ["Nodo Central (Backend Gateway)"]
        B1["Servidor Sockets TCP (Puerto 9000)"]
        B2["Servidor Web Nativo HTTP (Puerto 8080)"]
    end

    subgraph Middleware ["Middleware Asíncrono"]
        MQ[("RabbitMQ Message Broker")]
    end

    subgraph Workers ["Nodos Distribuidos Heterogéneos"]
        W_IA["Nodo 2 (Windows 11 / Python 3.10)<br/>CNN Chest X-Ray From Scratch"]
        W_C["Nodo 3 (Debian Linux / .NET C#)<br/>Worker Validación y Control"]
        BD1[("BD 1: PostgreSQL 15<br/>Historial & Metadatos Diagnóstico")]
        BD2[("BD 2: MariaDB 10.11<br/>Auditoría & Clientes Autorizados")]
    end

    C1 -- "Sockets TCP (Frame JSON + '\n')" --> B1
    C2 -- "HTTP/1.1 Nativo sobre Sockets" --> B2
    C3 -- "Sockets TCP (java.net.Socket)" --> B1

    B1 <-->|AMQP RPC / Correlation-Id| MQ
    B2 <-->|AMQP RPC / Correlation-Id| MQ

    MQ <-->|cola_modeloA / cola_resultadosA| W_IA
    MQ <-->|cola_validacion_cliente| W_C
    MQ -->|cola_persistencia_bd1| BD1
    W_C <-->|Transacciones ACID Concurrente| BD2
```

---

## 2. Diagrama de Protocolo de Comunicación y Flujo Completo

```mermaid
sequenceDiagram
    autonumber
    actor Cliente as Cliente (Desktop Kotlin / Web / Android)
    participant Backend as Nodo Backend (Python Sockets)
    participant Broker as RabbitMQ Middleware
    participant Nodo3 as Nodo 3 Debian (Worker C#)
    participant MariaDB as BD2 (MariaDB)
    participant NodoIA as Nodo 2 (CNN IA From Scratch)
    participant Postgres as BD1 (PostgreSQL)

    Cliente->>Backend: Frame TCP (JSON: idCliente, token, imagenB64, tipoConsulta)
    Backend->>Broker: BasicPublish (cola_validacion_cliente, ReplyTo: cola_respuestas, CorrId)
    Broker->>Nodo3: BasicConsume (petición de validación)
    Nodo3->>MariaDB: Transacción SELECT & INSERT registro_validaciones (Locks concurrentes)
    MariaDB-->>Nodo3: Validación Aprobada
    Nodo3->>Broker: BasicPublish (cola_respuestas, CorrId, valido=true)
    Broker-->>Backend: Notificación asíncrona de Validación

    Backend->>Broker: BasicPublish (cola_modeloA, imagenB64, CorrId)
    Broker->>NodoIA: BasicConsume (petición de inferencia)
    Note over NodoIA: Micro Chunk Convolución (Filtros multihilo)<br/>+ Micro Chunk ReLU + MaxPool + MLP Softmax
    NodoIA->>Broker: BasicPublish (cola_respuestas, CorrId, diagnóstico: NORMAL/NEUMONÍA)
    Broker-->>Backend: Notificación asíncrona de Diagnóstico

    Backend-)Broker: BasicPublish asíncrono (cola_persistencia_bd1, diagnóstico, metadatos)
    Broker-)Postgres: Worker BD1 almacena metadatos e historial de diagnóstico

    Backend-->>Cliente: Frame TCP con Diagnóstico final y tiempo de respuesta
```

---

## 3. Matriz de Heterogeneidad y Tecnologías

| Dimensión | Nodo 1 (Backend & HTTP) | Nodo 2 (Inferencia IA) | Nodo 3 (Worker Validación) | Bases de Datos | Capa Clientes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Sistema Operativo** | Linux (Ubuntu WSL2) | Windows 11 Pro (Host físico) | Debian Bookworm (Contenedor Slim) | Linux Alpine | Multiplataforma |
| **Lenguaje de Programación** | Python 3 (LP1) | Python 3 (LP1) | C# 8.0 (.NET SDK) (LP3) | SQL Estándar / DDL | Kotlin / Java (LP2) + HTML/JS |
| **Motor de Base de Datos** | N/A | N/A | MariaDB 10.11 (BD2) | PostgreSQL 15 (BD1) | N/A |
| **Transporte / Red** | TCP Socket Nativo + AMQP | AMQP (RabbitMQ) | AMQP (RabbitMQ) | Protocolos RDBMS nativos | Sockets TCP estándar |

---

## 4. Resultados de las Pruebas de Rendimiento y Saturación (1000 Transacciones)

Las pruebas se ejecutaron mediante la suite `run_saturation_test.py` enviando 1000 transacciones completas con perturbaciones y delays aleatorios para saturar el bus de RabbitMQ y las bases de datos:

| Modalidad | Transacciones | Concurrencia | Throughput (TPS) | Latencia Media | Latencia P95 | Tasa de Error |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Secuencial** | 100 | 1 proceso, 1 hilo | **38.93 TPS** | 23.69 ms | 31.40 ms | **0.00%** |
| **2. Paralelo** | 200 | 1 máquina, 8 hilos | **83.21 TPS** | 92.77 ms | 148.50 ms | **0.00%** |
| **3. Distribuido** | 200 | M nodos coordinados | **84.16 TPS** | 32.84 ms | 56.12 ms | **0.00%** |
| **4. Paralelo Distribuido** | **1000** | **M nodos x 20 hilos** | **81.57 TPS** | 242.34 ms | 385.20 ms | **0.00%** |

### Gráfica Comparativa de Throughput (Transacciones por Segundo)
```text
 1. Secuencial (1 proceso, 1 hilo)     | ################## 38.93 TPS
 2. Paralelo (N núcleos, H hilos)      | ####################################### 83.21 TPS
 3. Distribuido (M nodos coordinados)  | ######################################## 84.16 TPS
 4. Paralelo Distribuido (Saturación)  | ###################################### 81.57 TPS
```

### Verificación de Persistencia en Bases de Datos Heterogéneas
- **BD1 PostgreSQL:** **1,501 registros** persistidos en `historial_diagnosticos` y **1,428 registros** en `metadatos_imagen`.
- **BD2 MariaDB:** **1,506 registros** auditados concurrentemente en `registro_validaciones`.
- **Cero bloqueos o condiciones de carrera:** Demostrado mediante el uso de pools de conexiones y transacciones atómicas.
