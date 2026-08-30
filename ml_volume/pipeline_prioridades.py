# -*- coding: utf-8 -*-
"""
Albus Hub - Frente ML (Integrante 2) - Pipeline v3.2: VOLUME por PRIORIDADE, DEDUPLICADO.

HISTORICO
  v3   - serie deduplicada (so incidentes-raiz) + um modelo por prioridade.
  v3.1 - intervalo conformal adaptativo (faixa que se ajusta sozinha).
  v3.2 - HONESTIDADE METODOLOGICA (esta versao). Tres correcoes:
    (1) BASELINE JUSTO. Antes comparavamos so com "naive7" (mesmo dia da semana passada).
        Descobrimos que em series SEM sazonalidade semanal (P4: forca sazonal 0,03) essa
        regua e um espantalho. Agora concorremos contra a MELHOR de tres reguas bobas:
        naive7, media7 (media dos ultimos 7 dias) e ultimo (repete o valor conhecido).
    (2) JANELA DE TREINO TESTADA. Hipotese: treinar so no regime pleno (Set-Dez) seria
        melhor. FALSA - o Ridge PIORA 21-24% com menos dados. Mantemos o ano inteiro.
    (3) PREDITOR FIXADO A PRIORI. Antes o codigo escolhia o vencedor olhando o proprio
        teste (viesado). Agora escolhe em SET-OUT e reporta em NOV-DEZ. As reguas bobas
        SAO CANDIDATAS de pleno direito e vale a regra de Occam ao longo da escada de
        complexidade: fica o preditor mais SIMPLES que chega a 5% do melhor.

PROTOCOLO
  walk-forward diario | selecao: set-out/2025 (61d) | nota: nov-dez/2025 (61d nunca vistos)
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
OUT = os.path.join(HERE, "outputs")
PLOTS = os.path.join(HERE, "plots")
for d in (OUT, PLOTS):
    os.makedirs(d, exist_ok=True)

MODEL_VERSION = "volume_v3.2_2026-08-21"

# ---------------------------------------------------------------- 1. DADOS
# Sprint 4: a Silver governada passa a ser a fonte oficial do ML.
from albus_hub.config import get_settings

settings = get_settings()

df = pd.read_parquet(
    settings.absolute_path(settings.locaweb_silver_file)
)

df["_prio"] = pd.to_numeric(
    df["priority_code"],
    errors="coerce",
).astype("Int64")

df["Aberto"] = pd.to_datetime(
    df["opened_at"],
    errors="coerce",
)

df["Item de configuração"] = df["configuration_item"]
df["Incidente Pai"] = df["parent_incident_id"]

df["dia"] = df["Aberto"].dt.floor("D")

d25 = df[df["Aberto"].dt.year == 2025].copy()

parent = (
    d25["Incidente Pai"]
    .astype("string")
    .str.strip()
)

dedup = d25[
    parent.isna() | parent.eq("")
].copy()

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
ALLF=list(dict.fromkeys(FEATS_LEVEL+FEATS_RATE))

# REGUAS BOBAS (candidatas de pleno direito) e MODELOS
BASES  = ["naive7","media7","ultimo"]         # simples: sem treino, so aritmetica do passado
LEARNED= ["ridge","poisson_off","gbr"]        # aprendidos
CANDS  = BASES + LEARNED
# escada de complexidade, do mais simples ao mais complexo (usada na regra de Occam):
# regua boba < linear interpretavel < contagem interpretavel < caixa-preta
ORDER  = ["naive7","media7","ultimo","ridge","poisson_off","gbr"]
def base_series(y,h):
    """As tres reguas bobas, ja com o shift correto para o horizonte h."""
    return {"naive7": y.shift(7),                       # mesmo dia da semana passada
            "media7": y.shift(h).rolling(7).mean(),     # media dos ultimos 7 dias conhecidos
            "ultimo": y.shift(h)}                       # repete o ultimo valor conhecido
def fit_pred(name,Xtr,ytr,xrow):
    if len(ytr)==0: return 0.0
    if ytr.nunique()<=1: return float(ytr.iloc[0])      # serie constante (ex.: P1)
    if name=="poisson_off":
        expo=Xtr["exp_roll7"].clip(lower=1e-6); rate=ytr/expo
        if rate.sum()==0: return 0.0
        m=make_pipeline(StandardScaler(),PoissonRegressor(alpha=1e-4,max_iter=6000))
        m.fit(Xtr[FEATS_RATE],rate,poissonregressor__sample_weight=expo.values)
        return max(0.0,float(m.predict(xrow[FEATS_RATE])[0])*max(1e-6,float(xrow["exp_roll7"].iloc[0])))
    m=(make_pipeline(StandardScaler(),Ridge(alpha=5.0)) if name=="ridge"
       else HistGradientBoostingRegressor(loss="poisson",max_depth=3,learning_rate=0.08,
                                          max_iter=250,min_samples_leaf=15,random_state=0))
    m.fit(Xtr[FEATS_LEVEL],ytr); return max(0.0,float(m.predict(xrow[FEATS_LEVEL])[0]))

def smape(a,p): a,p=np.asarray(a,float),np.asarray(p,float); return float(100*np.mean(2*np.abs(a-p)/(np.abs(a)+np.abs(p)+1e-9)))
def mae(a,p): return float(np.mean(np.abs(np.asarray(a,float)-np.asarray(p,float))))
def mets(a,p): a,p=np.asarray(a,float),np.asarray(p,float); return {"MAE":mae(a,p),"RMSE":float(np.sqrt(np.mean((a-p)**2))),"sMAPE":smape(a,p),"n":int(len(a))}

# ------------------------------------- 3b. INTERVALO CONFORMAL ADAPTATIVO (v3.1)
# Largura proporcional a sqrt(previsto) (escala de contagem) + auto-correcao diaria do
# alpha (ACI): caiu fora -> alarga amanha; sobrou folga -> aperta. So residuos passados.
ALPHA=0.20; BURN=28; WIN=60; GAMMA=0.03
def _s(x): return max(1.0, float(np.sqrt(max(float(x),0.0))))
def bands(a,p):
    n=len(a); lo=np.full(n,np.nan); hi=np.full(n,np.nan); sc=[]; at=ALPHA; qlo=qhi=0.0
    for i in range(n):
        if i>=BURN:
            ps=np.array(sc[-WIN:])
            qlo=float(np.quantile(ps,at/2)); qhi=float(np.quantile(ps,1-at/2))
            lo[i]=max(0.0,p[i]+qlo*_s(p[i])); hi[i]=p[i]+qhi*_s(p[i])
            at=float(np.clip(at+GAMMA*(ALPHA-(0.0 if lo[i]<=a[i]<=hi[i] else 1.0)),0.01,0.60))
        sc.append((a[i]-p[i])/_s(p[i]))
    ev=np.zeros(n,bool); ev[BURN:]=True
    return lo,hi,ev,(qlo,qhi)
def _bf(v,p):
    v=np.asarray(v,float).copy(); ok=np.flatnonzero(~np.isnan(v))
    if len(ok)==0: return np.asarray(p,float).copy()
    v[:ok[0]]=v[ok[0]]; return v

# ---------------------------- 4. WALK-FORWARD + SELECAO HONESTA + PREVISAO
EVAL0=pd.Timestamp("2025-09-01")    # comeco do walk-forward (inicio do regime pleno)
SELEND=pd.Timestamp("2025-10-31")   # SET+OUT (61d): so para escolher e aquecer o conformal.
                                    # 1 mes so era ruidoso demais e escolhia mal; 2 meses estabiliza.
REP0=pd.Timestamp("2025-11-01")     # daqui em diante: a nota (61 dias, nunca vistos na escolha)
TIEBREAK=0.05                       # se a regua boba chega a 5% do melhor, fica a regua (Occam)

all_metrics={}; all_preds=[]; chosen={}
for scope,y in series.items():
    all_metrics[scope]={}
    for h,hn in [(1,"D+1"),(7,"D+7")]:
        X,yt=build_Xy(y,h); ok=X[ALLF].notna().all(axis=1) & yt.notna() & (yt.index<=LAST)
        B=base_series(y,h); td=yt.index[ok & (yt.index>=EVAL0)]
        preds={c:[] for c in CANDS}
        for d in td:
            tr=ok & (yt.index<d); Xtr,ytr,xr=X.loc[tr],yt.loc[tr],X.loc[[d]]
            for c in BASES:   preds[c].append(max(0.0,float(B[c].loc[d])))
            for c in LEARNED: preds[c].append(fit_pred(c,Xtr,ytr,xr))
        a=yt.loc[td].values; Pm={c:np.array(preds[c]) for c in CANDS}
        sel=td<=SELEND; rep=td>=REP0

        # --- (3) escolha do preditor: SO com set-out. Regra de Occam ao longo da escada de
        # complexidade (ORDER): fica o PRIMEIRO candidato que chega a 5% do melhor. Assim
        # so pagamos complexidade (e perda de interpretabilidade) quando ela compra acerto.
        msel={c:mae(a[sel],Pm[c][sel]) for c in CANDS}
        floor_=min(msel.values())
        pick=next(c for c in ORDER if msel[c] <= floor_*(1+TIEBREAK))
        chosen[(scope,hn)]=pick

        # --- (1) nota em nov-dez contra a MELHOR regua boba (medida no proprio periodo)
        mrep={c:mae(a[rep],Pm[c][rep]) for c in CANDS}
        base_ref=min(BASES,key=lambda c: mrep[c])
        m=mets(a[rep],Pm[pick][rep])
        m["skill_vs_melhor_regua"]=float(1-mrep[pick]/mrep[base_ref]) if mrep[base_ref]>1e-9 else float("nan")
        m["skill_vs_naive7"]      =float(1-mrep[pick]/mrep["naive7"]) if mrep["naive7"]>1e-9 else float("nan")
        all_metrics[scope][hn]={"_escolhido":pick,"_tipo":("regua simples" if pick in BASES else "modelo"),
            "_regua_referencia":base_ref,"_mae_candidatos_nov_dez":{c:round(mrep[c],2) for c in CANDS},
            "_mae_candidatos_out":{c:round(msel[c],2) for c in CANDS}, **m}

        # --- intervalo conformal sobre o preditor escolhido
        bp=Pm[pick]; lo,hi,ev,(qlo,qhi)=bands(a,bp)
        evr=ev & rep
        all_metrics[scope][hn]["_coverage"]={"nominal":.8,
            "conformal_nov_dez":float(np.mean((a[evr]>=lo[evr])&(a[evr]<=hi[evr]))) if evr.any() else float("nan"),
            "largura_media":float(np.nanmean(hi[evr]-lo[evr])) if evr.any() else float("nan"),
            "n_avaliado":int(evr.sum()),
            "q_low":float(qlo),
            "q_high":float(qhi)}
        LO,HI=_bf(lo,bp),_bf(hi,bp)
        for dte,av,pv,l_,h_ in zip(td,a,bp,LO,HI):
            all_preds.append(dict(reference_date=dte.date(),horizon=hn,scope=scope,predicted_incidents=int(round(pv)),
                actual_incidents=int(av),lower_bound=max(0,int(round(l_))),upper_bound=int(round(max(h_,l_))),
                model=pick,model_version=MODEL_VERSION))
        # --- previsao futura com o preditor escolhido
        fut=LAST+pd.Timedelta(days=h)
        fp=(max(0.0,float(B[pick].loc[fut])) if pick in BASES
            else fit_pred(pick,X.loc[ok],yt.loc[ok],X.loc[[fut]]))
        fl,fh=max(0.0,fp+qlo*_s(fp)),fp+qhi*_s(fp)
        all_preds.append(dict(reference_date=fut.date(),horizon=hn,scope=scope,predicted_incidents=int(round(fp)),
            actual_incidents=None,lower_bound=max(0,int(round(fl))),upper_bound=int(round(max(fh,fl))),
            model=pick,model_version=MODEL_VERSION))

pred_df=pd.DataFrame(all_preds)
pred_df.to_csv(os.path.join(OUT,"predictions_volume.csv"),index=False)
pred_df.to_parquet(os.path.join(OUT,"predictions_volume.parquet"),index=False)
json.dump(all_metrics,open(os.path.join(OUT,"metrics.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=2,default=str)

# ---------------------------------------------------------- 5. RESUMO
print("="*110)
print("PIPELINE v3.2 - VOLUME por PRIORIDADE, DEDUPLICADO")
print("  escolha do preditor: SET+OUT/2025  |  nota: NOV-DEZ/2025 (61 dias, nao usados na escolha)")
print("  skill = ganho sobre a MELHOR das 3 reguas bobas (naive7 / media7 / ultimo)")
print("="*110)
print(f"{'scope':6}{'hor':5}{'preditor':>13}{'tipo':>16}{'regua':>9}{'MAE':>8}{'sMAPE':>8}"
      f"{'skill':>8}{'(vs naive7)':>13}{'cobert':>8}")
pct=lambda v: "n/a" if not np.isfinite(v) else f"{v*100:+.0f}%"
for scope in series:
    for hn in ["D+1","D+7"]:
        m=all_metrics[scope][hn]; c=m["_coverage"]
        cv="n/a" if not np.isfinite(c["conformal_nov_dez"]) else f"{c['conformal_nov_dez']*100:.0f}%"
        print(f"{scope:6}{hn:5}{m['_escolhido']:>13}{m['_tipo']:>16}{m['_regua_referencia']:>9}"
              f"{m['MAE']:>8.1f}{m['sMAPE']:>7.1f}%{pct(m['skill_vs_melhor_regua']):>8}"
              f"{pct(m['skill_vs_naive7']):>13}{cv:>8}")

n_mod=sum(1 for v in chosen.values() if v in LEARNED)
print(f"\nPreditor escolhido: MODELO em {n_mod}/{len(chosen)} combinacoes; REGUA SIMPLES nas demais.")
print("(entregar a regua simples onde ela ganha e decisao de engenharia, nao fracasso do ML)")

print("\nPREVISAO FUTURA (a partir de 2025-12-31):")
print(pred_df[pred_df.actual_incidents.isna()][["scope","horizon","reference_date",
      "predicted_incidents","lower_bound","upper_bound","model"]].to_string(index=False))

# ---------------------------------------------------------- 6. GRAFICO
plt.rcParams.update({"font.size":10,"axes.grid":True,"grid.alpha":.25,"axes.spines.top":False,"axes.spines.right":False})
show=["ALL","P2","P3","P4"]; fig,ax=plt.subplots(len(show),1,figsize=(14,13),constrained_layout=True)
fig.suptitle("v3.2 — Backtest D+1: previsto vs real + intervalo conformal (nota: Nov–Dez 2025)",fontweight="bold",fontsize=13)
for a_,scope in zip(ax,show):
    sub=pred_df[(pred_df.scope==scope)&(pred_df.horizon=="D+1")&(pred_df.actual_incidents.notna())]
    dts=pd.to_datetime(sub.reference_date)
    a_.plot(dts,sub.actual_incidents,color="#263238",lw=1.3,label="real")
    a_.plot(dts,sub.predicted_incidents,color="#c62828",lw=1.3,ls="--",label="previsto")
    a_.fill_between(dts,sub.lower_bound,sub.upper_bound,color="#c62828",alpha=.15,label="intervalo 80%")
    a_.axvline(REP0,color="#1565c0",lw=1.2,ls=":"); a_.text(REP0,a_.get_ylim()[1],"  início da nota",
        color="#1565c0",va="top",fontsize=8)
    m=all_metrics[scope]["D+1"]
    a_.set_title(f"{scope} — preditor: {m['_escolhido']} ({m['_tipo']}) · MAE {m['MAE']:.1f} · "
                 f"skill {pct(m['skill_vs_melhor_regua'])} vs melhor régua")
    a_.set_ylabel("eventos/dia"); a_.legend(loc="upper left",ncol=3)
fig.savefig(os.path.join(PLOTS,"backtest_v32_D1.png"),dpi=140,bbox_inches="tight")
print("\nSALVOS: outputs/ (predictions_volume.csv/parquet, metrics.json) + plots/backtest_v32_D1.png")
