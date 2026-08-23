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

Construir um MVP local para estimar, **no momento de abertura do incidente**, a probabilidade de quebra do KPI/OLA. O notebook passa pelas etapas de preparação dos dados, teste de clusterização, treinamento da ANN, avaliação do modelo e geração das previsões.

**Resumo da execução de referência:** {_latest_summary()}

Como existem poucos casos positivos, Accuracy sozinha poderia dar uma visão enganosa do resultado. Por isso, usamos principalmente PR-AUC, Recall, Precision e F1, deixando ROC-AUC como métrica complementar.
"""
        ),
        _md(
            """
## 1. Bibliotecas

As principais funções usadas no modelo foram incluídas no próprio notebook. Isso facilita acompanhar o que foi feito em cada etapa, principalmente no pré-processamento, na clusterização e na construção da ANN.
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

Para o treinamento, consideramos apenas os incidentes com `entered_kpi_source == True`, usando `kpi_breached_source` como target. Para evitar leakage, não usamos como features informações que só aparecem depois que o incidente foi resolvido. O `closed_at` serve apenas para verificar se o resultado de um incidente anterior já era conhecido naquele momento.
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

Cada linha da Silver representa um incidente. Antes de montar as features, verificamos duplicidade no identificador, datas de abertura inválidas e se o target está preenchido nos casos elegíveis.
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

As features temporais são criadas a partir da data de abertura. Já as features históricas usam apenas acontecimentos anteriores ao incidente atual. Na taxa de quebra da equipe, por exemplo, só entram incidentes que já tinham sido encerrados naquele momento. Assim, o modelo não recebe informação do futuro.
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

Como os incidentes possuem ordem temporal, não usamos embaralhamento. A base é ordenada pela data de abertura e dividida em 60% treino, 20% validação e 20% teste. A validação é usada nas escolhas de modelagem, enquanto o teste fica separado até a avaliação final.
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

Nas variáveis numéricas, preenchemos os valores ausentes pela mediana e aplicamos `StandardScaler`. Nas categóricas, tratamos os nulos e usamos `OneHotEncoder`, permitindo categorias novas. O ajuste do pré-processamento é feito somente com o treino e depois reaplicado na validação e no teste.
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

Testamos a clusterização para verificar se os grupos encontrados ajudariam na previsão. O K-Means é ajustado sem usar o target, com `k = 2, 3, 4, 5`, e o melhor valor é escolhido pelo silhouette. Depois, o cluster selecionado é adicionado a um baseline separado para comparar a PR-AUC.

Se o cluster não melhorar o resultado, ele não é usado como feature da ANN. Assim, a clusterização entra como experimento e não como uma etapa obrigatória do modelo final.
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

Foram testadas duas arquiteturas densas. Cada camada oculta usa ReLU seguida de Dropout, enquanto a saída possui um neurônio com Sigmoid. O treinamento usa Adam, binary cross-entropy e PR-AUC como métrica de validação.

Como a classe positiva é rara, usamos `class_weight`. O `EarlyStopping` recupera os melhores pesos e o `ReduceLROnPlateau` reduz a taxa de aprendizado quando a PR-AUC de validação para de melhorar.
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

A saída Sigmoid é calibrada com Platt scaling usando a validação. O threshold também é escolhido nessa etapa: buscamos Recall de pelo menos 70% e, entre os thresholds que atendem esse critério, priorizamos melhores valores de Precision/F1. Depois disso, o threshold escolhido é aplicado ao teste final.
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

Como há poucos casos de quebra do KPI/OLA, damos mais atenção à PR-AUC e ao Recall. Também analisamos ROC-AUC, Precision, F1 e a matriz de confusão para entender quantas quebras o modelo consegue encontrar e quantos falsos alertas ele gera com o threshold escolhido.
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

Na tabela abaixo aplicamos a ANN escolhida aos incidentes do conjunto de teste. A coluna `breach_probability` mostra a probabilidade calibrada de quebra, enquanto `predicted_breach` indica o resultado após aplicar o threshold escolhido na validação.
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

- A classe positiva é rara. Por isso, aumentar o Recall também tende a aumentar a quantidade de falsos positivos. O modelo deve apoiar **priorização**, não decisão automática.
- O split temporal foi mantido para respeitar a ordem dos incidentes e reduzir o risco de leakage.
- A clusterização só entra no modelo se realmente melhorar a PR-AUC; separar perfis por si só não é suficiente.
- A calibração foi feita apenas com a validação e precisa ser revista quando houver novos dados.
- Em uma aplicação futura, também será necessário acompanhar mudanças no comportamento dos dados e revisar periodicamente o threshold e a calibração.

## Conclusão

Os testes mostram que é possível usar os dados disponíveis na abertura do incidente para estimar o risco de quebra do KPI/OLA. Durante o desenvolvimento, comparamos diferentes configurações da ANN e também testamos se a clusterização ajudaria no resultado.

A avaliação respeitou a ordem temporal dos dados e manteve o conjunto de teste separado das decisões de modelagem. Como as violações são raras, o principal ponto de atenção continua sendo o equilíbrio entre identificar as quebras e evitar um número excessivo de falsos alertas.
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
