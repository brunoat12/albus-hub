-- =========================================================
-- ALBUS-HUB
-- Sprint 3 - Data Warehousing
-- Validação do Modelo Dimensional
-- =========================================================


-- ---------------------------------------------------------
-- 1. CONTAGEM DAS TABELAS
-- ---------------------------------------------------------

SELECT 'dim_tempo' AS tabela, COUNT(*) AS registros
FROM dim_tempo

UNION ALL

SELECT 'dim_prioridade', COUNT(*)
FROM dim_prioridade

UNION ALL

SELECT 'dim_produto', COUNT(*)
FROM dim_produto

UNION ALL

SELECT 'dim_categoria', COUNT(*)
FROM dim_categoria

UNION ALL

SELECT 'dim_grupo', COUNT(*)
FROM dim_grupo

UNION ALL

SELECT 'dim_item_configuracao', COUNT(*)
FROM dim_item_configuracao

UNION ALL

SELECT 'fato_incidente', COUNT(*)
FROM fato_incidente;


-- ---------------------------------------------------------
-- 2. VALIDAÇÃO DA GRANULARIDADE
-- Esperado:
-- total_incidentes = incidentes_distintos = 122543
-- ---------------------------------------------------------

SELECT
    COUNT(*) AS total_incidentes,
    COUNT(DISTINCT incident_id) AS incidentes_distintos
FROM fato_incidente;


-- ---------------------------------------------------------
-- 3. INCIDENTES POR PRIORIDADE
-- FATO + DIM_PRIORIDADE
-- ---------------------------------------------------------

SELECT
    p.priority_code,
    p.priority_label,
    SUM(f.qtd_incidente) AS quantidade_incidentes
FROM fato_incidente f
INNER JOIN dim_prioridade p
    ON f.sk_prioridade = p.sk_prioridade
GROUP BY
    p.priority_code,
    p.priority_label
ORDER BY
    p.priority_code;


-- ---------------------------------------------------------
-- 4. INCIDENTES POR ANO
-- FATO + DIM_TEMPO
-- ---------------------------------------------------------

SELECT
    t.ano,
    SUM(f.qtd_incidente) AS quantidade_incidentes
FROM fato_incidente f
INNER JOIN dim_tempo t
    ON f.sk_tempo = t.sk_tempo
GROUP BY
    t.ano
ORDER BY
    t.ano;


-- ---------------------------------------------------------
-- 5. TOP 10 PRODUTOS
-- FATO + DIM_PRODUTO
-- ---------------------------------------------------------

SELECT
    p.produto,
    SUM(f.qtd_incidente) AS quantidade_incidentes
FROM fato_incidente f
INNER JOIN dim_produto p
    ON f.sk_produto = p.sk_produto
GROUP BY
    p.produto
ORDER BY
    quantidade_incidentes DESC
LIMIT 10;


-- ---------------------------------------------------------
-- 6. TOP 10 GRUPOS
-- FATO + DIM_GRUPO
-- ---------------------------------------------------------

SELECT
    g.grupo,
    SUM(f.qtd_incidente) AS quantidade_incidentes
FROM fato_incidente f
INNER JOIN dim_grupo g
    ON f.sk_grupo = g.sk_grupo
GROUP BY
    g.grupo
ORDER BY
    quantidade_incidentes DESC
LIMIT 10;


-- ---------------------------------------------------------
-- 7. KPI POR PRIORIDADE
-- Demonstra uso analítico de medida + dimensão
-- ---------------------------------------------------------

SELECT
    p.priority_label,
    SUM(f.entered_kpi) AS incidentes_em_kpi,
    SUM(
        CASE
            WHEN f.kpi_breached = 1 THEN 1
            ELSE 0
        END
    ) AS kpis_violados
FROM fato_incidente f
INNER JOIN dim_prioridade p
    ON f.sk_prioridade = p.sk_prioridade
GROUP BY
    p.priority_label
ORDER BY
    incidentes_em_kpi DESC;


-- ---------------------------------------------------------
-- 8. CONSULTA ESTRELA COMPLETA
-- Evidência principal da modelagem dimensional
-- ---------------------------------------------------------

SELECT
    f.incident_id,
    t.data,
    p.priority_label AS prioridade,
    pr.produto,
    c.categoria,
    c.subcategoria,
    g.grupo,
    ci.item_configuracao,
    f.duration_hours,
    f.entered_kpi,
    f.kpi_breached
FROM fato_incidente f

INNER JOIN dim_tempo t
    ON f.sk_tempo = t.sk_tempo

INNER JOIN dim_prioridade p
    ON f.sk_prioridade = p.sk_prioridade

INNER JOIN dim_produto pr
    ON f.sk_produto = pr.sk_produto

INNER JOIN dim_categoria c
    ON f.sk_categoria = c.sk_categoria

INNER JOIN dim_grupo g
    ON f.sk_grupo = g.sk_grupo

INNER JOIN dim_item_configuracao ci
    ON f.sk_item_configuracao =
       ci.sk_item_configuracao

LIMIT 50;
