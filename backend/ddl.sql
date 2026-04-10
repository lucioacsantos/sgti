CREATE TABLE tipo_ativo (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) UNIQUE NOT NULL, -- ex: host, aplicacao, banco, api, cluster
    descricao TEXT
);

CREATE TABLE tipo_relacionamento (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) UNIQUE NOT NULL, -- ex: depende_de, roda_em, conecta_em
    descricao TEXT
);

CREATE TABLE ambiente (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(50) UNIQUE NOT NULL -- dev, hml, prod
);

CREATE TABLE status_ativo (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(50) UNIQUE NOT NULL -- ativo, inativo, descontinuado
);

CREATE TABLE criticidade (
    id SERIAL PRIMARY KEY,
    nivel VARCHAR(50) UNIQUE NOT NULL -- baixa, media, alta, critica
);

CREATE TABLE ativo (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    descricao TEXT,

    tipo_id INT NOT NULL REFERENCES tipo_ativo(id),
    ambiente_id INT REFERENCES ambiente(id),
    status_id INT REFERENCES status_ativo(id),
    criticidade_id INT REFERENCES criticidade(id),

    responsavel VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ativo_tipo ON ativo(tipo_id);
CREATE INDEX idx_ativo_nome ON ativo(nome);

CREATE TABLE relacionamento (
    id SERIAL PRIMARY KEY,

    origem_id INT NOT NULL REFERENCES ativo(id) ON DELETE CASCADE,
    destino_id INT NOT NULL REFERENCES ativo(id) ON DELETE CASCADE,

    tipo_id INT NOT NULL REFERENCES tipo_relacionamento(id),

    descricao TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rel_origem ON relacionamento(origem_id);
CREATE INDEX idx_rel_destino ON relacionamento(destino_id);
CREATE INDEX idx_rel_tipo ON relacionamento(tipo_id);

CREATE TABLE host (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(255) UNIQUE NOT NULL,
    ip VARCHAR(50),
    sistema_operacional VARCHAR(100),

    ambiente_id INT REFERENCES ambiente(id),

    ativo_id INT UNIQUE REFERENCES ativo(id) ON DELETE SET NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aplicacao (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    descricao TEXT,

    ativo_id INT UNIQUE REFERENCES ativo(id) ON DELETE SET NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE instancia_aplicacao (
    id SERIAL PRIMARY KEY,

    aplicacao_id INT NOT NULL REFERENCES aplicacao(id) ON DELETE CASCADE,
    host_id INT REFERENCES host(id) ON DELETE SET NULL,

    porta INT,
    path_execucao VARCHAR(255),

    ativo_id INT UNIQUE REFERENCES ativo(id) ON DELETE SET NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE servico (
    id SERIAL PRIMARY KEY,

    nome VARCHAR(255) NOT NULL,
    tipo VARCHAR(50), -- systemd, docker, etc

    host_id INT REFERENCES host(id) ON DELETE CASCADE,

    ativo_id INT UNIQUE REFERENCES ativo(id) ON DELETE SET NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cluster (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) UNIQUE NOT NULL,
    descricao TEXT,

    ativo_id INT UNIQUE REFERENCES ativo(id) ON DELETE SET NULL
);

CREATE TABLE namespace (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,

    cluster_id INT REFERENCES cluster(id) ON DELETE CASCADE,

    ativo_id INT UNIQUE REFERENCES ativo(id) ON DELETE SET NULL
);

CREATE TABLE servico_negocio (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    descricao TEXT,

    ativo_id INT UNIQUE REFERENCES ativo(id) ON DELETE SET NULL
);

CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,

    entidade VARCHAR(100) NOT NULL,
    entidade_id INT,

    acao VARCHAR(50), -- INSERT, UPDATE, DELETE

    antes JSONB,
    depois JSONB,

    usuario VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_entidade ON audit_log(entidade);

CREATE TABLE api_token (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255),
    token TEXT UNIQUE NOT NULL,

    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE service_accounts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    token VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE usuario (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL, -- login AD
    nome VARCHAR(255),
    email VARCHAR(255),
    totp_secret VARCHAR(64),
    totp_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE usuario_backup_code (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    codigo_hash VARCHAR(255) NOT NULL,
    usado BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);