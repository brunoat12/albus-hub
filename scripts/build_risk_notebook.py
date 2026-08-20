from __future__ import annotations

import json
from pathlib import Path

import nbformat as nbf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "EC_Sprint_3_Albus_Hub_DeepL.ipynb"
METRICS_PATH = PROJECT_ROOT / "artifacts" / "metrics" / "risk_model_metrics.json"


def _latest_summary() -> str:
    if not METRICS_PATH.exists():
        return "Execute o notebook para produzir as métricas observadas."
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    test = metrics["ann"]["test"]
    population = metrics["population"]
    return (
        f"A base contém {population['eligible_incidents']:,} incidentes elegíveis e "
        f"{population['positive_incidents']} violações ({100 * population['positive_rate']:.3f}%). "
        f"No teste temporal, a ANN atingiu PR-AUC {test['pr_auc']:.4f}, "
        f"Recall {test['recall']:.1%} e Precision {test['precision']:.1%}."
    ).replace(",", ".")


def build_notebook() -> None:
    notebook = nbf.v4.new_notebook()
    notebook["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.12"},
    }
    cells = [
        nbf.v4.new_markdown_cell(
            "# Albus-Hub — Deep Learning para risco OLA/KPI\n\n"
            "## tl;dr\n\n"
            f"{_latest_summary()}\n\n"
            "A probabilidade é calibrada e mantida separada do score operacional 70/20/10. "
            "O principal limite é a raridade do target: decisões de alerta precisam considerar "
            "capacidade operacional e custo de falsos positivos."
        ),
        nbf.v4.new_markdown_cell(
            "## Contexto e métodos\n\n"
            "Objetivo: prever, na abertura do incidente, a violação do KPI/OLA e produzir um "
            "score consumível pelo Streamlit. A população oficial é "
            "`entered_kpi_source == True`; o target é `kpi_breached_source`.\n\n"
            "### Premissas principais\n\n"
            "- A Silver tratada é `data/silver/locaweb_incidents.parquet`.\n"
            "- `opened_at` é preservado no fuso/semântica da fonte, que não informa timezone.\n"
            "- Agregações usam apenas aberturas anteriores; taxas históricas usam somente "
            "desfechos encerrados antes da abertura corrente.\n"
            "- O split final é temporal 60%/20%/20%.\n"
            "- Accuracy não é usada como métrica de decisão."
        ),
        nbf.v4.new_code_cell(
            "import json\n"
            "from pathlib import Path\n\n"
            "import pandas as pd\n"
            "from IPython.display import Image, display\n\n"
            "from albus_hub.config import get_settings\n"
            "from albus_hub.models.risk.contracts import LEAKAGE_COLUMNS, MODEL_FEATURES\n"
            "from albus_hub.models.risk.inference import RiskPredictor\n"
            "from albus_hub.models.risk.train import RiskTrainingConfig, train_risk_model\n\n"
            "PROJECT_ROOT = Path.cwd()\n"
            "settings = get_settings()\n"
            "RUN_TRAINING = False\n"
            "metrics_path = PROJECT_ROOT / 'artifacts/metrics/risk_model_metrics.json'\n"
            "if RUN_TRAINING or not metrics_path.exists():\n"
            "    config = RiskTrainingConfig(\n"
            "        silver_path=PROJECT_ROOT / settings.locaweb_silver_file,\n"
            "        risk_features_path=PROJECT_ROOT / settings.locaweb_risk_features_file,\n"
            "        risk_scores_path=PROJECT_ROOT / settings.locaweb_risk_scores_file,\n"
            "        model_dir=PROJECT_ROOT / settings.model_risk_path,\n"
            "        metrics_path=metrics_path,\n"
            "        figures_dir=PROJECT_ROOT / settings.locaweb_risk_eda_output_dir,\n"
            "    )\n"
            "    train_risk_model(config)\n"
            "metrics = json.loads(metrics_path.read_text(encoding='utf-8'))\n"
            "silver = pd.read_parquet(PROJECT_ROOT / settings.locaweb_silver_file)\n"
            "risk_features = pd.read_parquet(PROJECT_ROOT / settings.locaweb_risk_features_file)\n"
            "risk_scores = pd.read_parquet(PROJECT_ROOT / settings.locaweb_risk_scores_file)"
        ),
        nbf.v4.new_markdown_cell("## Dados e qualidade"),
        nbf.v4.new_code_cell(
            "pd.DataFrame({\n"
            "    'linhas': [len(silver)],\n"
            "    'colunas': [silver.shape[1]],\n"
            "    'incidentes_duplicados': [silver['incident_id'].duplicated().sum()],\n"
            "    'abertura_min': [silver['opened_at'].min()],\n"
            "    'abertura_max': [silver['opened_at'].max()],\n"
            "})"
        ),
        nbf.v4.new_markdown_cell("### População, target e desbalanceamento"),
        nbf.v4.new_code_cell(
            "pd.Series(metrics['population'], name='valor').to_frame()"
        ),
        nbf.v4.new_code_cell(
            "display(Image(filename=PROJECT_ROOT / 'artifacts/eda/risk/target_distribution.png'))\n"
            "display(Image(filename=PROJECT_ROOT / 'artifacts/eda/risk/breach_rate_by_priority.png'))\n"
            "display(Image(filename=PROJECT_ROOT / 'artifacts/eda/risk/monthly_breach_rate.png'))"
        ),
        nbf.v4.new_markdown_cell(
            "## Data leakage\n\n"
            "As colunas abaixo são bloqueadas pelo código. `closed_at` é consultado somente "
            "como relógio de disponibilidade de desfechos históricos; seu valor nunca entra "
            "na matriz de predictors do incidente corrente."
        ),
        nbf.v4.new_code_cell(
            "pd.DataFrame({'coluna_proibida': LEAKAGE_COLUMNS})"
        ),
        nbf.v4.new_markdown_cell("## Feature engineering"),
        nbf.v4.new_code_cell(
            "pd.DataFrame({'feature_permitida': MODEL_FEATURES})"
        ),
        nbf.v4.new_code_cell(
            "risk_features.loc[\n"
            "    risk_features['entered_kpi_source'].eq(True),\n"
            "    ['incident_id', 'opened_at', *MODEL_FEATURES, 'kpi_breached_source']\n"
            "].head(5)"
        ),
        nbf.v4.new_markdown_cell("## Split temporal e pré-processamento"),
        nbf.v4.new_code_cell(
            "pd.DataFrame(metrics['splits']).T"
        ),
        nbf.v4.new_code_cell(
            "pd.Series(metrics['preprocessing'], name='valor').to_frame()"
        ),
        nbf.v4.new_markdown_cell("## Clusterização"),
        nbf.v4.new_code_cell(
            "cluster = metrics['clustering']\n"
            "display(pd.DataFrame(cluster['candidates']))\n"
            "pd.Series({\n"
            "    'silhouette_selecionado': cluster['selected_silhouette'],\n"
            "    'PR-AUC baseline': cluster['baseline_validation_pr_auc'],\n"
            "    'PR-AUC baseline + cluster': cluster['baseline_with_cluster_validation_pr_auc'],\n"
            "    'usar_como_feature': cluster['use_as_model_feature'],\n"
            "    'conclusao': cluster['conclusion'],\n"
            "}, name='resultado').to_frame()"
        ),
        nbf.v4.new_markdown_cell("## Baseline interpretável"),
        nbf.v4.new_code_cell(
            "pd.DataFrame(metrics['baseline']).T"
        ),
        nbf.v4.new_markdown_cell(
            "## Arquitetura e parametrizações da ANN\n\n"
            "As configurações usam Dense/ReLU, Dropout, saída Sigmoid, binary cross-entropy, "
            "Adam, class weights e EarlyStopping por PR-AUC de validação."
        ),
        nbf.v4.new_code_cell(
            "pd.DataFrame([\n"
            "    {\n"
            "        **candidate['config'],\n"
            "        'epochs_run': candidate['epochs_run'],\n"
            "        'validation_pr_auc': candidate['validation_pr_auc'],\n"
            "    }\n"
            "    for candidate in metrics['ann_candidates']\n"
            "])"
        ),
        nbf.v4.new_code_cell(
            "predictor = RiskPredictor(PROJECT_ROOT / settings.model_risk_path)\n"
            "predictor.model.summary()"
        ),
        nbf.v4.new_markdown_cell("## Avaliação temporal e threshold"),
        nbf.v4.new_code_cell(
            "pd.DataFrame(metrics['ann']).T"
        ),
        nbf.v4.new_code_cell(
            "thresholds = pd.DataFrame(metrics['threshold_table'])\n"
            "requested = [metrics['selected_threshold'], 0.30, 0.40, 0.50, 0.60]\n"
            "rows = [thresholds.iloc[(thresholds['threshold'] - value).abs().argmin()] for value in requested]\n"
            "pd.DataFrame(rows).drop_duplicates('threshold').sort_values('threshold')"
        ),
        nbf.v4.new_code_cell(
            "display(Image(filename=PROJECT_ROOT / 'artifacts/eda/risk/precision_recall_test.png'))\n"
            "display(Image(filename=PROJECT_ROOT / 'artifacts/eda/risk/confusion_matrix_test.png'))"
        ),
        nbf.v4.new_markdown_cell(
            "## Probabilidade, score e níveis\n\n"
            "`breach_probability` é a probabilidade calibrada. O score operacional aplica "
            "70% probabilidade, 20% impacto da prioridade e 10% pressão operacional. "
            "Os níveis seguem as faixas atuais do contrato e não são o mesmo que o threshold "
            "binário de classificação."
        ),
        nbf.v4.new_code_cell(
            "risk_scores[['breach_probability', 'risk_score']].describe(percentiles=[.5, .9, .95, .99])"
        ),
        nbf.v4.new_code_cell(
            "risk_scores['risk_level'].value_counts().rename_axis('nivel').to_frame('incidentes')"
        ),
        nbf.v4.new_markdown_cell("## Previsões reais e explicabilidade local"),
        nbf.v4.new_code_cell(
            "risk_scores.sort_values('risk_score', ascending=False).head(10)"
        ),
        nbf.v4.new_markdown_cell(
            "## Limitações e próximos passos\n\n"
            "- Apenas 248 positivos existem em toda a população; intervalos de confiança e "
            "monitoramento de drift são necessários antes de produção.\n"
            "- A cobertura de elegibilidade muda fortemente em 2025.\n"
            "- A calibração usa somente 33 positivos de validação.\n"
            "- O threshold de alto recall gera muitos falsos positivos e deve ser acordado "
            "com a capacidade da operação.\n"
            "- Os clusters separam perfis operacionais, mas não melhoram o PR-AUC do baseline; "
            "por isso não entram no modelo final.\n"
            "- Os níveis 0–24/25–49/50–74/75–100 são provisórios e, com probabilidades "
            "calibradas baixas, não produziram níveis alto/crítico no teste atual.\n\n"
            "## Takeaways\n\n"
            "A ANN fornece ranking substancialmente melhor que o baseline, mas o produto deve "
            "usar o score como priorização e não como decisão automática. O próximo passo é "
            "validar custo de alertas, acompanhar drift e recalibrar threshold/faixas com a operação."
        ),
    ]
    notebook["cells"] = cells
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, NOTEBOOK_PATH)
    print(NOTEBOOK_PATH)


if __name__ == "__main__":
    build_notebook()
