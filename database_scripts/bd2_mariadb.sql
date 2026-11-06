-- ====================================================================
-- Script DDL para BD2: MariaDB / MySQL (Validacion y Reglas de Negocio)
-- ====================================================================

CREATE TABLE IF NOT EXISTS clientes_autorizados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_cliente VARCHAR(64) UNIQUE NOT NULL,
    nombre_usuario VARCHAR(100) NOT NULL,
    token_auth VARCHAR(128) NOT NULL,
    tipo_cliente ENUM('ANDROID', 'DESKTOP', 'WEB', 'SISTEMA') NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    limite_consultas_minuto INT DEFAULT 120,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS catalogo_modelos (
    id_modelo VARCHAR(32) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    dimension_esperada INT NOT NULL,
    umbral_confianza_minimo DECIMAL(4, 3) DEFAULT 0.500,
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS registro_validaciones (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    id_solicitud VARCHAR(64) NOT NULL,
    id_cliente VARCHAR(64) NOT NULL,
    id_modelo VARCHAR(32) NOT NULL,
    estado_validacion ENUM('APROBADO', 'RECHAZADO') NOT NULL,
    motivo VARCHAR(255),
    ip_origen VARCHAR(45),
    timestamp_validacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Registros iniciales de validación
INSERT INTO clientes_autorizados (id_cliente, nombre_usuario, token_auth, tipo_cliente)
VALUES 
('CLI_KOTLIN_DESK_01', 'Operador Radiologia Desktop', 'TOKEN_KOTLIN_DESK_9921', 'DESKTOP'),
('CLI_WEB_01', 'Usuario Portal Web Medico', 'TOKEN_WEB_PORTAL_3310', 'WEB'),
('CLI_ANDROID_01', 'Dr. Movil Android', 'TOKEN_ANDROID_APP_7741', 'ANDROID'),
('CLI_BENCHMARK_01', 'Suite Saturacion 1000 Reg', 'TOKEN_BENCH_TEST_0001', 'SISTEMA')
ON DUPLICATE KEY UPDATE activo=TRUE;

INSERT INTO catalogo_modelos (id_modelo, nombre, descripcion, dimension_esperada, umbral_confianza_minimo)
VALUES 
('MODELO_A', 'CNN Chest X-Ray (Neumonia)', 'Detector Convolucional de Patrones de Opacidad Pulmonar', 28, 0.600)
ON DUPLICATE KEY UPDATE activo=TRUE;
