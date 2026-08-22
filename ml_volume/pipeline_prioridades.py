# -*- coding: utf-8 -*-
"""
Albus Hub - Frente ML (Integrante 2) - Pipeline v3: VOLUME por PRIORIDADE, DEDUPLICADO.

O que muda vs v2:
  - Alvo = serie DEDUPLICADA (so incidentes-raiz, sem 'Incidente Pai') -> conta eventos,
    nao alarmes de cascata. Alinha com o KPI (filho nao entra no KPI).
  - Uma serie por prioridade: ALL, P1, P2, P3, P4, P5 (cada uma com seu modelo).
Fluxo: dados -> features (sem vazamento) -> backtest walk-forward -> metricas (+cobertura)
       -> predicoes (contrato) -> graficos.
Le o dataset bruto (fonte de verdade); cacheia parquet local.
"""
import os, json, warnings
import numpy as np, pandas as pd, holidays
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
MODEL_VERSION = "volume_v3_2026-08-16"

# ---------------------------------------------------------------- 1. DADOS
if os.path.exists(CACHE): df = pd.read_parquet(CACHE)
else:
    df = pd.read_excel(SRC, sheet_name="Dataset Geral"); df.to_parquet(CACHE, index=False)
df["_prio"]=df["Prioridade"].str.extract(r"^\s*(\d)").astype("Int64")
df["Aberto"]=pd.to_datetime(df["Aberto"]); df["dia"]=df["Aberto"].dt.floor("D")
d25 = df[df["Aberto"].dt.year==2025].copy()
dedup = d25[d25["Incidente Pai"].isna()]          # <- DEDUPLICACAO (so raiz)

LAST=pd.Timestamp("2025-12-31"); idx=pd.date_range("2025-01-01",LAST+pd.Timedelta(days=7),freq="D")
def daily(frame, mask=None):
    f = frame if mask is None else frame[mask]
    s = f.groupby("dia").size().reindex(idx); s.loc[:LAST]=s.loc[:LAST].fillna(0); return s
series = {"ALL": daily(dedup)}
for p in [1,2,3,4,5]: series[f"P{p}"] = daily(dedup, dedup["_prio"].eq(p))
active_cis = d25.groupby("dia")["Item de configuração"].nunique().reindex(idx)
active_cis.loc[:LAST]=active_cis.loc[:LAST].fillna(0); active_cis=active_cis.ffill()

# ---------------------------------------------------------- 2. CALENDARIO
br=holidays.Brazil(years=[2025,2026]); BF=pd.Timestamp("2025-11-28")
def calfeat(dates):
    c=pd.DataFrame(index=dates); dow=dates.dayofweek
    for k in range(7): c[f"dow_{k}"]=(dow==k).astype(int)
    c["is_weekend"]=(dow>=5).astype(int)
    c["is_holiday"]=[1 if x in br else 0 for x in dates]
    c["black_week"]=[1 if BF-pd.Timedelta(days=1)<=x<=BF+pd.Timedelta(days=4) else 0 for x in dates]
    c["dec_season"]=((dates.month==12)&(dates.day>=15)).astype(int)
    return c
CAL=calfeat(idx); CALCOLS=list(CAL.columns)

# --------------------------------------------- 3. FEATURES (sem vazamento)
def build_Xy(y,h):
    ys=y.shift(h); X=pd.DataFrame(index=y.index)
    X["seas_lag7"]=y.shift(7); X["seas_lag14"]=y.shift(14); X["last"]=ys
    X["roll7_mean"]=ys.rolling(7).mean(); X["roll7_std"]=ys.rolling(7).std(); X["roll28_mean"]=ys.rolling(28).mean()
    X["exp_last"]=active_cis.shift(h); X["exp_roll7"]=active_cis.shift(h).rolling(7).mean()
    X["trend"]=np.arange(len(y))
    ex=X["exp_roll7"].replace(0,np.nan); exl=X["exp_last"].replace(0,np.nan)
    X["r_last"]=X["last"]/exl; X["r_roll7"]=X["roll7_mean"]/ex; X["r_seas7"]=X["seas_lag7"]/ex
    return X.join(CAL), y
FEATS_LEVEL=["seas_lag7","seas_lag14","last","roll7_mean","roll7_std","roll28_mean","exp_last","exp_roll7","trend"]+CALCOLS
FEATS_RATE =["r_last","r_roll7","r_seas7"]+CALCOLS
ALLF=list(dict.fromkeys(FEATS_LEVEL+FEATS_RATE)); MODELS=["naive","poisson_off","ridge","gbr"]

def mk(name):
    if name=="ridge": return make_pipeline(StandardScaler(),Ridge(alpha=5.0))
    if name=="gbr":   return HistGradientBoostingRegressor(loss="poisson",max_depth=3,learning_rate=0.08,max_iter=250,min_samples_leaf=15,random_state=0)
def fit_pred(name,Xtr,ytr,xrow):
    if ytr.nunique()<=1: return float(ytr.iloc[0]) if len(ytr) else 0.0   # serie constante (ex.: P1)
    if name=="naive": return max(0.0,float(xrow["seas_lag7"].iloc[0]))
    if name=="poisson_off":
        expo=Xtr["exp_roll7"].clip(lower=1e-6); rate=ytr/expo
        if rate.sum()==0: return 0.0
        m=make_pipeline(StandardScaler(),PoissonRegressor(alpha=1e-4,max_iter=6000))
        m.fit(Xtr[FEATS_RATE],rate,poissonregressor__sample_weight=expo.values)
        return max(0.0,float(m.predict(xrow[FEATS_RATE])[0])*max(1e-6,float(xrow["exp_roll7"].iloc[0])))
    m=mk(name); m.fit(Xtr[FEATS_LEVEL],ytr); return max(0.0,float(m.predict(xrow[FEATS_LEVEL])[0]))

def smape(a,p): a,p=np.asarray(a,float),np.asarray(p,float); return float(100*np.mean(2*np.abs(a-p)/(np.abs(a)+np.abs(p)+1e-9)))
def mets(a,p): a,p=np.asarray(a,float),np.asarray(p,float); return {"MAE":float(np.mean(np.abs(a-p))),"RMSE":float(np.sqrt(np.mean((a-p)**2))),"sMAPE":smape(a,p),"n":int(len(a))}

# -------------------------------------------------- 4. BACKTEST + PREVISAO
TEST0=pd.Timestamp("2025-09-01"); all_metrics={}; all_preds=[]
for scope,y in series.items():
    all_metrics[scope]={}
    for h,hn in [(1,"D+1"),(7,"D+7")]:
        X,yt=build_Xy(y,h); ok=X[ALLF].notna().all(axis=1)
        hist=ok & yt.notna() & (yt.index<=LAST); td=yt.index[hist & (yt.index>=TEST0)]
        preds={m:[] for m in MODELS}
        for d in td:
            tr=hist & (yt.index<d); Xtr,ytr,xr=X.loc[tr],yt.loc[tr],X.loc[[d]]
            for m in MODELS: preds[m].append(fit_pred(m,Xtr,ytr,xr))
        a=yt.loc[td].values
        for m in MODELS: all_metrics[scope].setdefault(hn,{})[m]=mets(a,preds[m])
        base=all_metrics[scope][hn]["naive"]["MAE"]
        for m in MODELS: all_metrics[scope][hn][m]["skill_vs_naive"]=float(1-all_metrics[scope][hn][m]["MAE"]/base) if base>1e-9 else float("nan")
        best=min(MODELS,key=lambda m: all_metrics[scope][hn][m]["MAE"]); all_metrics[scope][hn]["_best"]=best
        bp=np.array(preds[best]); res=a-bp
        lo,hi=(float(np.quantile(res,.1)),float(np.quantile(res,.9))) if len(res)>=5 else (0.0,0.0)
        k=int(len(res)*0.6)
        cov=float(np.mean((a[k:]>=bp[k:]+np.quantile(res[:k],.1))&(a[k:]<=bp[k:]+np.quantile(res[:k],.9)))) if k>=5 and len(res)-k>=3 else float("nan")
        all_metrics[scope][hn]["_coverage"]={"nominal":.8,"empirico_oos":cov}
        for dte,av,pv in zip(td,a,bp):
            all_preds.append(dict(reference_date=dte.date(),horizon=hn,scope=scope,predicted_incidents=int(round(pv)),
                actual_incidents=int(av),lower_bound=max(0,int(round(pv+lo))),upper_bound=int(round(pv+hi)),model=best,model_version=MODEL_VERSION))
        fut=LAST+pd.Timedelta(days=h); fp=fit_pred(best,X.loc[hist],yt.loc[hist],X.loc[[fut]])
        all_preds.append(dict(reference_date=fut.date(),horizon=hn,scope=scope,predicted_incidents=int(round(fp)),
            actual_incidents=None,lower_bound=max(0,int(round(fp+lo))),upper_bound=int(round(fp+hi)),model=best,model_version=MODEL_VERSION))

pred_df=pd.DataFrame(all_preds)
pred_df.to_csv(os.path.join(OUT,"predictions_volume.csv"),index=False)
pred_df.to_parquet(os.path.join(OUT,"predictions_volume.parquet"),index=False)
json.dump(all_metrics,open(os.path.join(OUT,"metrics.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=2,default=str)

# ---------------------------------------------------------- 5. RESUMO
print("="*84,"\nPIPELINE v3 — VOLUME por PRIORIDADE, DEDUPLICADO — backtest Set-Dez 2025\n","="*84)
print(f"{'scope':6}{'total25':>9}{'media/d':>9}  {'horiz':6}{'melhor':>12}{'MAE':>8}{'sMAPE':>8}{'skill':>7}{'cobert':>8}")
for scope in series:
    tot=int(series[scope].loc[:LAST].sum()); md=series[scope].loc["2025-09":LAST].mean()
    for hn in ["D+1","D+7"]:
        mm=all_metrics[scope][hn]; b=mm["_best"]; r=mm[b]
        sk="n/a" if not np.isfinite(r["skill_vs_naive"]) else f"{r['skill_vs_naive']*100:+.0f}%"
        cv=mm["_coverage"]["empirico_oos"]; cvs="n/a" if not np.isfinite(cv) else f"{cv*100:.0f}%"
        print(f"{scope:6}{tot:>9}{md:>9.1f}  {hn:6}{b:>12}{r['MAE']:>8.1f}{r['sMAPE']:>7.1f}%{sk:>7}{cvs:>8}")

print("\nPREVISAO FUTURA (a partir de 2025-12-31):")
print(pred_df[pred_df.actual_incidents.isna()][["scope","horizon","reference_date","predicted_incidents","lower_bound","upper_bound","model"]].to_string(index=False))

# ---------------------------------------------------------- 6. GRAFICO
plt.rcParams.update({"font.size":10,"axes.grid":True,"grid.alpha":.25,"axes.spines.top":False,"axes.spines.right":False})
show=["ALL","P2","P3","P4"]; fig,ax=plt.subplots(len(show),1,figsize=(14,13),constrained_layout=True)
fig.suptitle("v3 — Backtest D+1 previsto vs real (série deduplicada, Set–Dez 2025)",fontweight="bold",fontsize=13)
for a_,scope in zip(ax,show):
    sub=pred_df[(pred_df.scope==scope)&(pred_df.horizon=="D+1")&(pred_df.actual_incidents.notna())]
    a_.plot(pd.to_datetime(sub.reference_date),sub.actual_incidents,color="#263238",lw=1.3,label="real")
    a_.plot(pd.to_datetime(sub.reference_date),sub.predicted_incidents,color="#c62828",lw=1.3,ls="--",label="previsto")
    a_.fill_between(pd.to_datetime(sub.reference_date),sub.lower_bound,sub.upper_bound,color="#c62828",alpha=.15,label="intervalo")
    mm=all_metrics[scope]["D+1"]; b=mm["_best"]
    a_.set_title(f"{scope} (modelo {b}: MAE {mm[b]['MAE']:.1f}, sMAPE {mm[b]['sMAPE']:.0f}%)"); a_.set_ylabel("eventos/dia"); a_.legend(loc="upper left",ncol=3)
fig.savefig(os.path.join(PLOTS,"backtest_v3_D1.png"),dpi=140,bbox_inches="tight")
print("\nSALVOS: outputs/ (predictions_volume.csv/parquet, metrics.json) + plots/backtest_v3_D1.png")
