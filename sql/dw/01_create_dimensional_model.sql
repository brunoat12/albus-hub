-- =========================================================
-- ALBUS-HUB
-- Sprint 3 - Data Warehousing
-- Modelo Dimensional
-- =========================================================


-- ---------------------------------------------------------
-- DIMENSÃO TEMPO
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_tempo (
    sk_tempo INT NOT NULL,
    data DATE NOT NULL,
    ano SMALLINT NOT NULL,
    mes TINYINT NOT NULL,
    dia TINYINT NOT NULL,
    dia_semana TINYINT NOT NULL,
    semana_ano TINYINT NOT NULL,
    trimestre TINYINT NOT NULL,
    fim_semana BOOLEAN NOT NULL,

    PRIMARY KEY (sk_tempo),
    UNIQUE KEY uk_dim_tempo_data (data)
);


-- ---------------------------------------------------------
-- DIMENSÃO PRIORIDADE
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_prioridade (
    sk_prioridade INT NOT NULL,
    priority_code TINYINT NOT NULL,
    priority_label VARCHAR(50) NOT NULL,

    PRIMARY KEY (sk_prioridade),
    UNIQUE KEY uk_dim_prioridade_code (priority_code)
);


-- ---------------------------------------------------------
-- DIMENSÃO PRODUTO
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_produto (
    sk_produto INT NOT NULL,
    produto VARCHAR(255) NOT NULL,

    PRIMARY KEY (sk_produto),
    UNIQUE KEY uk_dim_produto (produto)
);


-- ---------------------------------------------------------
-- DIMENSÃO CATEGORIA
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_categoria (
    sk_categoria INT NOT NULL,
    categoria VARCHAR(255) NOT NULL,
    subcategoria VARCHAR(255) NOT NULL,

    PRIMARY KEY (sk_categoria),

    UNIQUE KEY uk_dim_categoria (
        categoria,
        subcategoria
    )
);


-- ---------------------------------------------------------
-- DIMENSÃO GRUPO
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_grupo (
    sk_grupo INT NOT NULL,
    grupo VARCHAR(255) NOT NULL,

    PRIMARY KEY (sk_grupo),
    UNIQUE KEY uk_dim_grupo (grupo)
);


-- ---------------------------------------------------------
-- DIMENSÃO ITEM DE CONFIGURAÇÃO
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_item_configuracao (
    sk_item_configuracao INT NOT NULL,
    item_configuracao VARCHAR(255) NOT NULL,

    PRIMARY KEY (sk_item_configuracao),
    UNIQUE KEY uk_dim_item_configuracao (
        item_configuracao
    )
);


-- ---------------------------------------------------------
-- TABELA FATO
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS fato_incidente (
    incident_id VARCHAR(50) NOT NULL,

    sk_tempo INT NOT NULL,
    sk_prioridade INT NOT NULL,
    sk_produto INT NOT NULL,
    sk_categoria INT NOT NULL,
    sk_grupo INT NOT NULL,
    sk_item_configuracao INT NOT NULL,

    qtd_incidente TINYINT NOT NULL DEFAULT 1,

    duration_seconds BIGINT,
    duration_hours DECIMAL(12,2),

    entered_kpi BOOLEAN NOT NULL,
    kpi_breached BOOLEAN NULL,

    is_monitoring_opened BOOLEAN NOT NULL,
    is_no_intervention BOOLEAN NOT NULL,

    opened_hour TINYINT,

    PRIMARY KEY (incident_id),

    CONSTRAINT fk_fato_tempo
        FOREIGN KEY (sk_tempo)
        REFERENCES dim_tempo(sk_tempo),

    CONSTRAINT fk_fato_prioridade
        FOREIGN KEY (sk_prioridade)
        REFERENCES dim_prioridade(sk_prioridade),

    CONSTRAINT fk_fato_produto
        FOREIGN KEY (sk_produto)
        REFERENCES dim_produto(sk_produto),

    CONSTRAINT fk_fato_categoria
        FOREIGN KEY (sk_categoria)
        REFERENCES dim_categoria(sk_categoria),

    CONSTRAINT fk_fato_grupo
        FOREIGN KEY (sk_grupo)
        REFERENCES dim_grupo(sk_grupo),

    CONSTRAINT fk_fato_item_configuracao
        FOREIGN KEY (sk_item_configuracao)
        REFERENCES dim_item_configuracao(sk_item_configuracao)
);
