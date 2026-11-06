-- ====================================================================
-- Script DDL para BD1: PostgreSQL (Historial Diagnostico y Metadatos)
-- ====================================================================

CREATE TABLE IF NOT EXISTS metadatos_imagen (
    id SERIAL PRIMARY KEY,
    id_solicitud VARCHAR(64) UNIQUE NOT NULL,
    hash_sha256 VARCHAR(64) NOT NULL,
    dimension_alto INT NOT NULL,
    dimension_ancho INT NOT NULL,
    formato VARCHAR(32) NOT NULL,
    tamanio_bytes INT NOT NULL,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS historial_diagnosticos (
    id SERIAL PRIMARY KEY,
    id_solicitud VARCHAR(64) NOT NULL,
    id_cliente VARCHAR(64) NOT NULL,
    modelo_usado VARCHAR(32) NOT NULL,
    diagnostico VARCHAR(64) NOT NULL,
    probabilidad NUMERIC(5, 4) NOT NULL,
    tiempo_ia_ms NUMERIC(10, 2) NOT NULL,
    nodo_ia VARCHAR(64) NOT NULL,
    fecha_diagnostico TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_solicitud FOREIGN KEY (id_solicitud) REFERENCES metadatos_imagen(id_solicitud) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_historial_cliente ON historial_diagnosticos(id_cliente);
CREATE INDEX IF NOT EXISTS idx_historial_fecha ON historial_diagnosticos(fecha_diagnostico);
