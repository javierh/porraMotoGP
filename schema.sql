-- Esquema de la base de datos para PorraMotoGP

-- Tabla de Circuitos (eventos)
CREATE TABLE IF NOT EXISTS Circuitos (
    event_id VARCHAR(36) PRIMARY KEY,
    circuit_name VARCHAR(255) NOT NULL,
    date_start VARCHAR(255),  -- Changed from DATETIME to VARCHAR
    date_end VARCHAR(255),    -- Changed from DATETIME to VARCHAR
    hashtag VARCHAR(255)
);

-- Tabla de Sesiones
CREATE TABLE IF NOT EXISTS Sesiones (
    session_id VARCHAR(36) PRIMARY KEY,
    circuit_id VARCHAR(36) NOT NULL,
    circuit_name VARCHAR(255) NOT NULL,
    shortname VARCHAR(50) NOT NULL,  -- SPR o RAC (Sprint o Carrera)
    date_start VARCHAR(255),        -- Changed from DATETIME to VARCHAR
    date_end VARCHAR(255),          -- Changed from DATETIME to VARCHAR
    category_id VARCHAR(50),
    category_name VARCHAR(255),
    FOREIGN KEY (circuit_id) REFERENCES Circuitos(event_id)
);

-- Tabla de Pilotos
CREATE TABLE IF NOT EXISTS Pilotos (
    rider_id VARCHAR(36) PRIMARY KEY,
    rider_name VARCHAR(255) NOT NULL,
    team VARCHAR(255),
    number INT
);

-- Tabla de Usuarios (Jugones)
CREATE TABLE IF NOT EXISTS Jugones (
    chat_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    join_date DATETIME
);

-- Tabla de Apuestas
CREATE TABLE IF NOT EXISTS Apuestas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    circuit_id VARCHAR(36) NOT NULL,
    user_id BIGINT NOT NULL,
    hashtag VARCHAR(255),
    posicion1 VARCHAR(255) NOT NULL,
    posicion2 VARCHAR(255) NOT NULL,
    posicion3 VARCHAR(255) NOT NULL,
    evento VARCHAR(50) NOT NULL,  -- 'sprint' o 'carrera'
    timestamp DATETIME NOT NULL,
    UNIQUE KEY unique_apuesta (circuit_id, user_id, evento),
    FOREIGN KEY (circuit_id) REFERENCES Circuitos(event_id),
    FOREIGN KEY (user_id) REFERENCES Jugones(chat_id)
);

-- Tabla de Calificación Q2
CREATE TABLE IF NOT EXISTS Q2 (
    circuit_id VARCHAR(36) PRIMARY KEY,
    posicion1 VARCHAR(255) NOT NULL,
    posicion2 VARCHAR(255) NOT NULL,
    posicion3 VARCHAR(255) NOT NULL,
    FOREIGN KEY (circuit_id) REFERENCES Circuitos(event_id)
);

-- Tabla de Ranking
CREATE TABLE IF NOT EXISTS Ranking (
    user_id BIGINT PRIMARY KEY,
    score INT NOT NULL DEFAULT 0,
    points_last_circuit INT NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES Jugones(chat_id)
);

-- Tabla de resultados Q2 para almacenar datos de clasificación Q2
CREATE TABLE IF NOT EXISTS q2_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    circuit_id VARCHAR(255),
    circuit_name VARCHAR(255),
    event_id VARCHAR(255),
    rider_id VARCHAR(255),
    rider_name VARCHAR(255),
    time VARCHAR(255),
    timestamp DATETIME
);

-- Tabla para almacenar resultados de carreras
CREATE TABLE IF NOT EXISTS resultados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    circuit_id VARCHAR(255),
    circuit_name VARCHAR(255),
    event_id VARCHAR(255),
    event_name VARCHAR(255),
    rider_id VARCHAR(255),
    rider_name VARCHAR(255),
    position VARCHAR(50),
    gap VARCHAR(255)
);
