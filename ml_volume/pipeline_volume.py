# -*- coding: utf-8 -*-
"""
Albus Hub - Integrante 2 - Previsao de VOLUME de incidentes D+1 / D+7 (ALL/P2/P3).
Pipeline v2: dados -> features (sem vazamento) -> backtest walk-forward -> metricas
(+ cobertura dos intervalos) -> predicoes (contrato) -> modelos -> graficos.

Modelos: naive sazonal | Poisson | Poisson-OFFSET (taxa por CI ativo) | Ridge | GBR.
Usa TODO o 2025 (dois regimes) com CIs ativos (exposicao) atravessando a quebra de set/2025.
Le o dataset bruto (fonte de verdade); cacheia parquet local para iterar rapido.
"""
import os, json, warnings
import numpy as np, pandas as pd, holidays, joblib
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from sklearn.linear_model import PoissonRegressor, Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, "..", "Dados", "LW-DATASET.xlsx")
CACHE= os.path.join(HERE, "data", "incidents.parquet")
OUT  = os.path.join(HERE, "outputs"); PLOTS = os.path.join(HERE, "plots")
for d in (os.path.dirname(CACHE), OUT, PLOTS): os.makedirs(d, exist_ok=True)
MODEL_VERSION = "volume_v2_2026-08-16"

# ------------------------------------------------------------------ 1. DADOS
if os.path.exists(CACHE):
    df = pd.read_parquet(CACHE)
else:
    df = pd.read_excel(SRC, sheet_name="Dataset Geral"); df.to_parquet(CACHE, index=False)
df["_prio"] = df["Prioridade"].str.extract(r"^\s*(\d)").astype("Int64")
df["Aberto"] = pd.to_datetime(df["Aberto"]); df["dia"] = df["Aberto"].dt.floor("D")
d25 = df[df["Aberto"].dt.year == 2025].copy()

LAST = pd.Timestamp("2025-12-31")
idx = pd.date_range("2025-01-01", LAST + pd.Timedelta(days=7), freq="D")
def daily(mask):
    s = d25[mask].groupby("dia").size().reindex(idx)
    s.loc[:LAST] = s.loc[:LAST].fillna(0)
    return s
series = {"ALL": daily(d25["_prio"].notna() | d25["_prio"].isna()),
          "P2": daily(d25["_prio"].eq(2)), "P3": daily(d25["_prio"].eq(3))}
active_cis = d25.groupby("dia")["Item de configuração"].nunique().reindex(idx)
active_cis.loc[:LAST] = active_cis.loc[:LAST].fillna(0)
active_cis = active_cis.ffill()
child_ratio = (d25[d25["Incidente Pai"].notna()].groupby("dia").size().reindex(idx).fillna(0)
               / series["ALL"].replace(0, np.nan)).fillna(0)

# ------------------------------------------------------------ 2. CALENDARIO
br = holidays.Brazil(years=[2023,2024,2025,2026]); BF = pd.Timestamp("2025-11-28")
def calendar_features(dates):
    c = pd.DataFrame(index=dates); dow = dates.dayofweek
    for k in range(7): c[f"dow_{k}"] = (dow == k).astype(int)
    c["is_weekend"]     = (dow >= 5).astype(int)
    c["is_holiday"]     = [1 if x in br else 0 for x in dates]
    c["is_holiday_eve"] = [1 if (x + pd.Timedelta(days=1)) in br else 0 for x in dates]
    c["black_week"]     = [1 if BF - pd.Timedelta(days=1) <= x <= BF + pd.Timedelta(days=4) else 0 for x in dates]
    c["dec_season"]     = ((dates.month == 12) & (dates.day >= 15)).astype(int)
    return c
CAL = calendar_features(idx); CALCOLS = list(CAL.columns)
EXT_EVENTS = {"AWS outage": pd.Timestamp("2025-10-20"), "Cloudflare outage": pd.Timestamp("2025-11-18")}

# --------------------------------------------------- 3. MATRIZ X,y (sem vazamento)
def build_Xy(y, h):
    ys = y.shift(h)
    X = pd.DataFrame(index=y.index)
    X["seas_lag7"]  = y.shift(7); X["seas_lag14"] = y.shift(14); X["last"] = ys
    X["roll7_mean"] = ys.rolling(7).mean(); X["roll7_std"] = ys.rolling(7).std()
    X["roll28_mean"]= ys.rolling(28).mean()
    X["exp_last"]   = active_cis.shift(h)
    X["exp_roll7"]  = active_cis.shift(h).rolling(7).mean()   # <- offset proxy (exposicao)
    X["child_last"] = child_ratio.shift(h); X["trend"] = np.arange(len(y))
    # features de TAXA (por CI ativo) para o Poisson-offset:
    ex = X["exp_roll7"].replace(0, np.nan); exl = X["exp_last"].replace(0, np.nan)
    X["r_last"]  = X["last"] / exl
    X["r_roll7"] = X["roll7_mean"] / ex
    X["r_seas7"] = X["seas_lag7"] / ex
    X = X.join(CAL)
    return X, y

FEATS_LEVEL = ["seas_lag7","seas_lag14","last","roll7_mean","roll7_std","roll28_mean",
               "exp_last","exp_roll7","child_last","trend"] + CALCOLS
FEATS_RATE  = ["r_last","r_roll7","r_seas7"] + CALCOLS
ALL_FEATS   = list(dict.fromkeys(FEATS_LEVEL + FEATS_RATE))
MODELS = ["naive","poisson","poisson_off","ridge","gbr"]

def mk_level(name):
    if name=="poisson": return make_pipeline(StandardScaler(), PoissonRegressor(alpha=1.0, max_iter=3000))
    if name=="ridge":   return make_pipeline(StandardScaler(), Ridge(alpha=5.0))
    if name=="gbr":     return HistGradientBoostingRegressor(loss="poisson", max_depth=3,
                          learning_rate=0.08, max_iter=250, min_samples_leaf=15, random_state=0)

def fit_pred(name, Xtr, ytr, xrow):
    if name == "naive":
        return max(0.0, float(xrow["seas_lag7"].iloc[0]))
    if name == "poisson_off":
        expo = Xtr["exp_roll7"].clip(lower=1e-6); rate = ytr / expo
        m = make_pipeline(StandardScaler(), PoissonRegressor(alpha=1e-4, max_iter=6000))
        m.fit(Xtr[FEATS_RATE], rate, poissonregressor__sample_weight=expo.values)
        et = max(1e-6, float(xrow["exp_roll7"].iloc[0]))
        return max(0.0, float(m.predict(xrow[FEATS_RATE])[0]) * et)
    m = mk_level(name); m.fit(Xtr[FEATS_LEVEL], ytr)
    return max(0.0, float(m.predict(xrow[FEATS_LEVEL])[0]))

def smape(a,p): a,p=np.asarray(a,float),np.asarray(p,float); return 100*np.mean(2*np.abs(a-p)/(np.abs(a)+np.abs(p)+1e-9))
def metrics(a,p):
    a,p=np.asarray(a,float),np.asarray(p,float)
    return {"MAE":float(np.mean(np.abs(a-p))),"RMSE":float(np.sqrt(np.mean((a-p)**2))),
            "sMAPE":float(smape(a,p)),"n":int(len(a))}

# ------------------------------------------------------------ 4. BACKTEST + PREV
TEST_START = pd.Timestamp("2025-09-01")
all_metrics, all_preds, coef_store, resid_store = {}, [], {}, {}

for scope, y in series.items():
    all_metrics[scope] = {}
    for h, hname in [(1,"D+1"),(7,"D+7")]:
        X, yt = build_Xy(y, h)
        ok = X[ALL_FEATS].notna().all(axis=1)
        hist = ok & yt.notna() & (yt.index <= LAST)
        test_dates = yt.index[hist & (yt.index >= TEST_START)]
        preds = {m: [] for m in MODELS}
        for d in test_dates:
            tr = hist & (yt.index < d)
            Xtr, ytr, xrow = X.loc[tr], yt.loc[tr], X.loc[[d]]
            for m in MODELS: preds[m].append(fit_pred(m, Xtr, ytr, xrow))
        actual = yt.loc[test_dates].values
        for m in MODELS: all_metrics[scope].setdefault(hname, {})[m] = metrics(actual, preds[m])
        base = all_metrics[scope][hname]["naive"]["MAE"]
        for m in MODELS: all_metrics[scope][hname][m]["skill_vs_naive"] = float(1 - all_metrics[scope][hname][m]["MAE"]/base)
        best = min(MODELS, key=lambda m: all_metrics[scope][hname][m]["MAE"])
        all_metrics[scope][hname]["_best"] = best
        bp = np.array(preds[best]); res = actual - bp
        lo, hi = float(np.quantile(res,.10)), float(np.quantile(res,.90))
        resid_store[(scope,hname)] = pd.Series(res, index=test_dates)
        # ---- validacao de cobertura (fora da amostra: calibra em 60%, mede em 40%) ----
        k = int(len(res)*0.6)
        clo, chi = np.quantile(res[:k],.10), np.quantile(res[:k],.90)
        cov = float(np.mean((actual[k:] >= bp[k:]+clo) & (actual[k:] <= bp[k:]+chi)))
        all_metrics[scope][hname]["_coverage"] = {"nominal":0.80,"empirico_oos":cov,"n_calib":k,"n_teste":len(res)-k}
        # ---- linhas de backtest (contrato) ----
        for dte,a,p in zip(test_dates, actual, bp):
            all_preds.append(dict(reference_date=dte.date(), horizon=hname, scope=scope,
                predicted_incidents=int(round(p)), actual_incidents=int(a),
                lower_bound=max(0,int(round(p+lo))), upper_bound=int(round(p+hi)),
                model=best, model_version=MODEL_VERSION))
        # ---- previsao futura ----
        fut = LAST + pd.Timedelta(days=h)
        fp = fit_pred(best, X.loc[hist], yt.loc[hist], X.loc[[fut]])
        all_preds.append(dict(reference_date=fut.date(), horizon=hname, scope=scope,
            predicted_incidents=int(round(fp)), actual_incidents=None,
            lower_bound=max(0,int(round(fp+lo))), upper_bound=int(round(fp+hi)),
            model=best, model_version=MODEL_VERSION))
        # ---- drivers (Poisson-offset, interpretavel e estavel) ----
        expo = X.loc[hist,"exp_roll7"].clip(lower=1e-6); rate = yt.loc[hist]/expo
        pm = make_pipeline(StandardScaler(), PoissonRegressor(alpha=1e-4, max_iter=6000))
        pm.fit(X.loc[hist,FEATS_RATE], rate, poissonregressor__sample_weight=expo.values)
        coef_store[(scope,hname)] = pd.Series(pm.named_steps["poissonregressor"].coef_, index=FEATS_RATE)

# ------------------------------------------------------------------ 5. SALVAR
pred_df = pd.DataFrame(all_preds)
pred_df.to_csv(os.path.join(OUT,"predictions_volume.csv"), index=False)
pred_df.to_parquet(os.path.join(OUT,"predictions_volume.parquet"), index=False)
with open(os.path.join(OUT,"metrics.json"),"w",encoding="utf-8") as f:
    json.dump(all_metrics, f, ensure_ascii=False, indent=2, default=str)
coef_store[("ALL","D+1")].to_csv(os.path.join(OUT,"drivers_ALL_D1.csv"))

# ------------------------------------------------------- 6. RESUMO NO CONSOLE
print("="*80,"\nBACKTEST walk-forward (teste = Set-Dez 2025) — v2\n","="*80)
for scope in series:
    for hname in ["D+1","D+7"]:
        mm = all_metrics[scope][hname]; b = mm["_best"]; cv = mm["_coverage"]
        print(f"\n{scope} {hname}: MELHOR = {b} | cobertura intervalo (nom 80%) = {cv['empirico_oos']*100:.0f}% oos")
        for m in MODELS:
            r=mm[m]; print(f"   {m:12} MAE {r['MAE']:6.1f} | RMSE {r['RMSE']:6.1f} | sMAPE {r['sMAPE']:5.1f}% | skill {r['skill_vs_naive']*100:+4.0f}%")

print("\n"+"="*80,"\nPREVISAO FUTURA (a partir de 2025-12-31)\n","="*80)
print(pred_df[pred_df.actual_incidents.isna()][["scope","horizon","reference_date","predicted_incidents","lower_bound","upper_bound","model"]].to_string(index=False))

print("\n"+"="*80,"\nDRIVERS — Poisson-offset (efeito na TAXA por CI; ALL D+1)\n","="*80)
print(coef_store[("ALL","D+1")].sort_values(ascending=False).round(3).to_string())

print("\n"+"="*80,"\nCHECAGEM DE EVENTOS EXTERNOS (residuo do modelo, ALL D+1)\n","="*80)
r = resid_store[("ALL","D+1")]
for nm,d in EXT_EVENTS.items():
    if d in r.index: print(f"  {nm} {d.date()}: residuo {r[d]:+.0f} (media|res| {r.abs().mean():.0f})")
bw = CAL['black_week']; bwd = r.index[bw.reindex(r.index).fillna(0).astype(bool)]
if len(bwd): print(f"  Black Week: residuo medio {r.loc[bwd].mean():+.0f}")

# ----------------------------------------------------------------- 7. GRAFICOS
plt.rcParams.update({"font.size":10,"axes.grid":True,"grid.alpha":.25,"axes.spines.top":False,"axes.spines.right":False})
fig, ax = plt.subplots(3,1, figsize=(14,12), constrained_layout=True)
fig.suptitle("Backtest D+1 — previsto vs real (regime Set–Dez 2025) — v2", fontweight="bold", fontsize=13)
for a,scope in zip(ax, series):
    sub = pred_df[(pred_df.scope==scope)&(pred_df.horizon=="D+1")&(pred_df.actual_incidents.notna())]
    a.plot(pd.to_datetime(sub.reference_date), sub.actual_incidents, color="#263238", lw=1.4, label="real")
    a.plot(pd.to_datetime(sub.reference_date), sub.predicted_incidents, color="#c62828", lw=1.4, ls="--", label="previsto")
    a.fill_between(pd.to_datetime(sub.reference_date), sub.lower_bound, sub.upper_bound, color="#c62828", alpha=.15, label="intervalo 10–90%")
    mm=all_metrics[scope]["D+1"]; b=mm["_best"]
    a.set_title(f"{scope}  (modelo {b}: MAE {mm[b]['MAE']:.1f}, sMAPE {mm[b]['sMAPE']:.0f}%, skill {mm[b]['skill_vs_naive']*100:+.0f}%, cobertura {mm['_coverage']['empirico_oos']*100:.0f}%)")
    a.set_ylabel("incidentes/dia"); a.legend(loc="upper left", ncol=3)
fig.savefig(os.path.join(PLOTS,"backtest_D1.png"), dpi=140, bbox_inches="tight")

fig2, ax2 = plt.subplots(figsize=(9,6), constrained_layout=True)
cc = coef_store[("ALL","D+1")].sort_values()
ax2.barh(cc.index, cc.values, color=["#c62828" if v<0 else "#2e7d32" for v in cc.values])
ax2.axvline(0,color="k",lw=.8); ax2.set_title("Drivers — Poisson-offset (coef. padronizados na taxa; ALL D+1)")
fig2.savefig(os.path.join(PLOTS,"drivers_ALL_D1.png"), dpi=140, bbox_inches="tight")
print("\nSALVOS: outputs/ (predictions_volume.csv/parquet, metrics.json, drivers_ALL_D1.csv) + plots/")
