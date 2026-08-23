from __future__ import annotations

import ast
import json
from pathlib import Path

import nbformat as nbf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "EC_Sprint_3_Albus_Hub_DeepL.ipynb"
METRICS_PATH = PROJECT_ROOT / "artifacts" / "metrics" / "risk_model_metrics.json"
RISK_SOURCE = PROJECT_ROOT / "src" / "albus_hub" / "models" / "risk"


def _latest_summary() -> str:
    if not METRICS_PATH.exists():
        return (
            "O notebook executa o treinamento completo a partir da Silver e calcula "
            "as métricas ao final da execução."
        )
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    test = metrics["ann"]["test"]
    population = metrics["population"]
    return (
        f"A base contém {population['eligible_incidents']:,} incidentes elegíveis e "
        f"{population['positive_incidents']} violações ({100 * population['positive_rate']:.3f}%). "
        f"No teste temporal, a ANN atingiu PR-AUC {test['pr_auc']:.4f}, "
        f"ROC-AUC {test['roc_auc']:.4f} e Recall {test['recall']:.1%}."
    ).replace(",", ".")


def _extract_symbols(filename: str, symbols: list[str]) -> str:
    """Copia para o notebook apenas definições acadêmicas do código de produção."""
    path = RISK_SOURCE / filename
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = set(symbols)
    found: set[str] = set()
    blocks: list[str] = []

    for node in tree.body:
        node_names: set[str] = set()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            node_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    node_names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            node_names.add(node.target.id)

        if node_names & wanted:
            segment = ast.get_source_segment(source, node)

            # ast.get_source_segment() começa na declaração da classe/função
            # e pode deixar decorators como @dataclass de fora.
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.decorator_list:
                lines = source.splitlines()
                start_line = min(decorator.lineno for decorator in node.decorator_list) - 1
                end_line = node.end_lineno
                segment = "\n".join(lines[start_line:end_line])

            if segment:
                blocks.append(segment)
                found.update(node_names & wanted)

    missing = wanted - found
    if missing:
        raise RuntimeError(f"Símbolos ausentes em {filename}: {sorted(missing)}")
    return "\n\n".join(blocks)


def _code(source: str):
    return nbf.v4.new_code_cell(source.strip())


def _md(source: str):
    return nbf.v4.new_markdown_cell(source.strip())


def build_notebook() -> None:
    contracts_code = _extract_symbols(
        "contracts.py",
        [
            "ELIGIBILITY_COLUMN",
            "TARGET_COLUMN",
            "IDENTIFIER_COLUMNS",
            "BASE_CATEGORICAL_FEATURES",
            "TEMPORAL_FEATURES",
            "HISTORICAL_FEATURES",
            "CATEGORICAL_FEATURES",
            "NUMERIC_FEATURES",
            "MODEL_FEATURES",
            "LEAKAGE_COLUMNS",
            "REQUIRED_SILVER_COLUMNS",
            "RiskDataContractError",
            "validate_silver_for_risk",
            "assert_no_leakage",
        ],
    )
    features_code = _extract_symbols(
        "features.py",
        [
            "_strict_previous_counts",
            "_known_group_outcomes_previous_30d",
            "build_risk_features",
        ],
    )
    preprocessing_code = _extract_symbols(
        "preprocessing.py", ["prepare_model_frame", "build_preprocessor"]
    )
    clustering_code = _extract_symbols("clustering.py", ["evaluate_clusters"])
    model_code = _extract_symbols(
        "model.py", ["ANNConfig", "ANN_CONFIGS", "build_ann", "train_ann", "predict_ann"]
    )
    metrics_code = _extract_symbols(
        "metrics.py", ["classification_metrics", "select_operating_threshold"]
    )
    probability_code = _extract_symbols(
        "probability.py",
        ["probability_logit", "fit_probability_calibrator", "apply_probability_calibrator"],
    )

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
        _md(
            f"""
# Albus-Hub — Deep Learning para risco de quebra de OLA/KPI

## Objetivo

Construir um MVP local capaz de estimar, **no momento de abertura do incidente**, a probabilidade de quebra do KPI/OLA. O notebook demonstra de forma executável o pré-processamento, a avaliação de clusterização, a construção e parametrização da ANN, a avaliação temporal e previsões reais.

**Resumo da execução de referência:** {_latest_summary()}

Como a classe positiva é rara, Accuracy não é usada como métrica principal. A análise prioriza PR-AUC, Recall, Precision, F1 e ROC-AUC.
"""
        ),
        _md(
            """
## 1. Bibliotecas

O notebook contém as funções essenciais do modelo. Assim, a construção da solução pode ser auditada diretamente no arquivo entregue, sem esconder a ANN, o pré-processamento ou a clusterização atrás de imports internos do projeto.
"""
        ),
        _code(
            """
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from IPython.display import display
from sklearn.cluster import MiniBatchKMeans
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
    silhouette_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEED = 42
np.random.seed(SEED)
"""
        ),
        _md(
            """
## 2. Contrato de dados e prevenção de leakage

A população oficial é formada por incidentes com `entered_kpi_source == True`, e o target é `kpi_breached_source`. Colunas conhecidas somente após o desfecho do incidente são bloqueadas como features. `closed_at` é utilizada apenas para determinar **quando um resultado histórico já era conhecido**, nunca como predictor do incidente corrente.
"""
        ),
        _code(contracts_code),
        _code(
            """
assert_no_leakage(MODEL_FEATURES)
pd.DataFrame({"feature_permitida": MODEL_FEATURES})
"""
        ),
        _md(
            """
## 3. Carregamento e qualidade da Silver

A Silver possui uma linha por incidente. A validação exige identificador único, data de abertura válida e target preenchido para a população elegível.
"""
        ),
        _code(
            """
DATA_PATH = Path("data/silver/locaweb_incidents.parquet")
if not DATA_PATH.exists():
    raise FileNotFoundError(
        "Dataset não encontrado em data/silver/locaweb_incidents.parquet. "
        "Disponibilize a Silver do projeto nesse caminho antes de executar o notebook."
    )

silver = pd.read_parquet(DATA_PATH)
validate_silver_for_risk(silver)

quality = pd.DataFrame({
    "linhas": [len(silver)],
    "colunas": [silver.shape[1]],
    "incident_id_duplicado": [int(silver["incident_id"].duplicated().sum())],
    "opened_at_nulo": [int(pd.to_datetime(silver["opened_at"], errors="coerce").isna().sum())],
    "abertura_min": [pd.to_datetime(silver["opened_at"]).min()],
    "abertura_max": [pd.to_datetime(silver["opened_at"]).max()],
})
display(quality)

nulls = silver.isna().sum().sort_values(ascending=False)
display(nulls[nulls.gt(0)].head(15).rename("nulos").to_frame())
"""
        ),
        _md(
            """
## 4. Feature engineering temporal e histórica

As features temporais usam apenas a data de abertura. As contagens históricas usam janelas estritamente anteriores ao timestamp corrente. A taxa histórica de quebra da equipe considera somente incidentes que já estavam encerrados antes da abertura atual, evitando vazamento de informação futura.
"""
        ),
        _code(features_code),
        _code(
            """
risk_features = build_risk_features(silver)
eligible = risk_features.loc[risk_features[ELIGIBILITY_COLUMN].eq(True)].copy()
eligible[TARGET_COLUMN] = eligible[TARGET_COLUMN].astype(bool)
eligible = eligible.sort_values(["opened_at", "incident_id"], kind="stable").reset_index(drop=True)

population = pd.Series({
    "total_incidents": len(silver),
    "eligible_incidents": len(eligible),
    "positive_incidents": int(eligible[TARGET_COLUMN].sum()),
    "negative_incidents": int((~eligible[TARGET_COLUMN]).sum()),
    "positive_rate": float(eligible[TARGET_COLUMN].mean()),
}, name="valor").to_frame()
display(population)

eligible[["incident_id", "opened_at", *MODEL_FEATURES, TARGET_COLUMN]].head(5)
"""
        ),
        _md(
            """
## 5. Split temporal

O dataset é ordenado por abertura e dividido em 60% treino, 20% validação e 20% teste. Não há embaralhamento. O teste permanece intocado até a escolha da arquitetura e do threshold, respeitando a ordem temporal.
"""
        ),
        _code(
            """
def split_temporally(frame, train_fraction=0.60, validation_fraction=0.20):
    train_end = int(len(frame) * train_fraction)
    validation_end = int(len(frame) * (train_fraction + validation_fraction))
    return (
        frame.iloc[:train_end].copy(),
        frame.iloc[train_end:validation_end].copy(),
        frame.iloc[validation_end:].copy(),
    )


def split_summary(frame):
    return {
        "rows": len(frame),
        "positives": int(frame[TARGET_COLUMN].sum()),
        "positive_rate": float(frame[TARGET_COLUMN].mean()),
        "opened_at_min": frame["opened_at"].min(),
        "opened_at_max": frame["opened_at"].max(),
    }

train, validation, test = split_temporally(eligible)
pd.DataFrame({
    "train": split_summary(train),
    "validation": split_summary(validation),
    "test": split_summary(test),
}).T
"""
        ),
        _md(
            """
## 6. Pré-processamento para entrada da ANN

As variáveis numéricas recebem imputação pela mediana e `StandardScaler`. As categóricas recebem imputação explícita e `OneHotEncoder`, com tratamento para categorias desconhecidas. O pré-processador é **ajustado apenas no treino** e reutilizado em validação e teste.
"""
        ),
        _code(preprocessing_code),
        _code(
            """
preprocessor = build_preprocessor()
x_train = preprocessor.fit_transform(prepare_model_frame(train)).astype(np.float32)
x_validation = preprocessor.transform(prepare_model_frame(validation)).astype(np.float32)
x_test = preprocessor.transform(prepare_model_frame(test)).astype(np.float32)

y_train = train[TARGET_COLUMN].astype(np.int8).to_numpy()
y_validation = validation[TARGET_COLUMN].astype(np.int8).to_numpy()
y_test = test[TARGET_COLUMN].astype(np.int8).to_numpy()

pd.DataFrame({
    "split": ["train", "validation", "test"],
    "linhas": [len(x_train), len(x_validation), len(x_test)],
    "dimensao_transformada": [x_train.shape[1], x_validation.shape[1], x_test.shape[1]],
    "positivos": [int(y_train.sum()), int(y_validation.sum()), int(y_test.sum())],
})
"""
        ),
        _md(
            """
## 7. Baseline interpretável

Uma regressão logística balanceada é usada como referência. A ANN só é interessante se produzir ganho sobre um modelo supervisionado simples no problema de classe rara.
"""
        ),
        _code(metrics_code),
        _code(
            """
baseline = LogisticRegression(
    class_weight="balanced",
    max_iter=1500,
    random_state=SEED,
    solver="lbfgs",
)
baseline.fit(x_train, y_train)
baseline_validation = baseline.predict_proba(x_validation)[:, 1]
baseline_test = baseline.predict_proba(x_test)[:, 1]

baseline_metrics = {
    "validation": classification_metrics(y_validation, baseline_validation, 0.5),
    "test": classification_metrics(y_test, baseline_test, 0.5),
}
pd.DataFrame(baseline_metrics).T
"""
        ),
        _md(
            """
## 8. Avaliação de clusterização

A clusterização é investigada como possível enriquecimento do feature engineering. O K-Means não utiliza o target no ajuste. São testados `k = 2, 3, 4, 5` e o melhor `k` é escolhido por silhouette. Em seguida, o rótulo do cluster é acrescentado a um baseline separado para verificar se existe ganho material de PR-AUC.

A clusterização **não é obrigada a entrar no modelo final**: ela só é mantida se demonstrar utilidade preditiva além de separar perfis operacionais.
"""
        ),
        _code(clustering_code),
        _code(
            """
cluster_results = evaluate_clusters(
    x_train,
    y_train,
    x_validation,
    y_validation,
    float(average_precision_score(y_validation, baseline_validation)),
    SEED,
)

display(pd.DataFrame(cluster_results["candidates"]))
pd.Series({
    "k_selecionado": cluster_results["selected_clusters"],
    "silhouette": cluster_results["selected_silhouette"],
    "PR_AUC_baseline": cluster_results["baseline_validation_pr_auc"],
    "PR_AUC_com_cluster": cluster_results["baseline_with_cluster_validation_pr_auc"],
    "ganho_absoluto": cluster_results["absolute_pr_auc_gain"],
    "usar_cluster_como_feature": cluster_results["use_as_model_feature"],
    "conclusao": cluster_results["conclusion"],
}, name="resultado").to_frame()
"""
        ),
        _md(
            """
## 9. Construção e parametrização da ANN

Foram testadas duas arquiteturas densas. Cada camada oculta utiliza ReLU seguida de Dropout; a saída possui um neurônio com Sigmoid. O treinamento usa Adam, binary cross-entropy e PR-AUC como métrica de validação.

O desbalanceamento é tratado com `class_weight`. `EarlyStopping` restaura os melhores pesos e `ReduceLROnPlateau` reduz a taxa de aprendizado quando a PR-AUC de validação deixa de evoluir.
"""
        ),
        _code(model_code),
        _code(
            """
pd.DataFrame([config.to_dict() for config in ANN_CONFIGS])
"""
        ),
        _md(
            """
## 10. Treinamento e seleção da arquitetura

A arquitetura é escolhida **somente pela PR-AUC da validação**. O conjunto de teste não participa da escolha.
"""
        ),
        _code(
            """
ann_results = []
trained_models = {}

for index, ann_config in enumerate(ANN_CONFIGS):
    model, history, class_weight = train_ann(
        x_train,
        y_train,
        x_validation,
        y_validation,
        ann_config,
        seed=SEED + index,
    )
    validation_probability = predict_ann(model, x_validation)
    test_probability = predict_ann(model, x_test)
    validation_pr_auc = float(average_precision_score(y_validation, validation_probability))

    ann_results.append({
        "config": ann_config.to_dict(),
        "epochs_run": len(history["loss"]),
        "class_weight": class_weight,
        "validation_pr_auc": validation_pr_auc,
        "validation_metrics_at_0_5": classification_metrics(
            y_validation, validation_probability, 0.5
        ),
    })
    trained_models[ann_config.name] = (
        model,
        validation_probability,
        test_probability,
    )

candidate_table = pd.DataFrame([
    {
        **item["config"],
        "epochs_run": item["epochs_run"],
        "class_weight_positive": item["class_weight"][1],
        "validation_pr_auc": item["validation_pr_auc"],
    }
    for item in ann_results
])
display(candidate_table)

selected_result = max(ann_results, key=lambda item: item["validation_pr_auc"])
selected_name = selected_result["config"]["name"]
selected_model, ann_validation_raw, ann_test_raw = trained_models[selected_name]
print(f"ANN selecionada: {selected_name}")
selected_model.summary()
"""
        ),
        _md(
            """
## 11. Calibração e escolha do threshold

A saída Sigmoid é calibrada por Platt scaling usando exclusivamente a validação. O threshold operacional também é escolhido na validação, priorizando Recall mínimo de 70% e, entre os candidatos elegíveis, maior Precision/F1. Só então ele é aplicado ao teste final.
"""
        ),
        _code(probability_code),
        _code(
            """
calibrator = fit_probability_calibrator(ann_validation_raw, y_validation)
ann_validation = apply_probability_calibrator(calibrator, ann_validation_raw)
ann_test = apply_probability_calibrator(calibrator, ann_test_raw)

selected_threshold, threshold_table = select_operating_threshold(
    y_validation,
    ann_validation,
    minimum_recall=0.70,
)
print(f"Threshold selecionado: {selected_threshold:.6f}")
threshold_table.sort_values(["recall", "precision"], ascending=False).head(10)
"""
        ),
        _md(
            """
## 12. Avaliação de desempenho

Devido à raridade do target, PR-AUC e Recall recebem atenção especial. ROC-AUC complementa a leitura de ranking; Precision e F1 explicitam o custo de falsos positivos; a matriz de confusão mostra o impacto operacional do threshold escolhido.
"""
        ),
        _code(
            """
ann_validation_metrics = classification_metrics(
    y_validation, ann_validation, selected_threshold
)
ann_test_metrics = classification_metrics(y_test, ann_test, selected_threshold)

comparison = pd.DataFrame({
    "baseline_test@0.5": baseline_metrics["test"],
    "ann_validation": ann_validation_metrics,
    "ann_test": ann_test_metrics,
}).T

display(comparison[["threshold", "pr_auc", "roc_auc", "brier_score", "precision", "recall", "f1"]])

pd.Series(ann_test_metrics["confusion_matrix"], name="quantidade").to_frame()
"""
        ),
        _md(
            """
## 13. Previsões reais

A tabela abaixo aplica a ANN escolhida aos incidentes do conjunto temporal de teste. `breach_probability` representa a probabilidade calibrada de quebra e `predicted_breach` aplica o threshold definido exclusivamente na validação.
"""
        ),
        _code(
            """
predictions = test[["incident_id", "opened_at", "priority_code", TARGET_COLUMN]].copy()
predictions["breach_probability"] = ann_test
predictions["predicted_breach"] = ann_test >= selected_threshold

predictions.sort_values("breach_probability", ascending=False).head(15)
"""
        ),
        _md(
            """
## 14. Interpretação e limitações

- A classe positiva é extremamente rara, portanto um threshold com alto Recall produz muitos falsos positivos. O modelo deve apoiar **priorização**, não decisão automática.
- O split temporal reduz risco de leakage e representa melhor o uso futuro do modelo.
- A clusterização é avaliada quantitativamente; se não houver ganho material de PR-AUC, seu rótulo não entra na ANN final.
- A calibração usa apenas a janela de validação e deve ser reavaliada com novos dados.
- Antes de produção, são necessários monitoramento de drift, avaliação de custo operacional dos alertas e recalibração periódica.

## Conclusão

O MVP demonstra viabilidade técnica: carrega os dados, produz features disponíveis na abertura, avalia clusterização, treina e compara ANNs, seleciona arquitetura e threshold sem consultar o teste final e gera probabilidades reais para incidentes futuros no recorte temporal de teste.
"""
        ),
    ]

    notebook["cells"] = cells
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, NOTEBOOK_PATH)
    print(f"Notebook acadêmico gerado: {NOTEBOOK_PATH}")
    print(f"Células: {len(cells)}")


if __name__ == "__main__":
    build_notebook()
