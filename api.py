"""
NAU Quantum v5.3 "Sentinel Quantum Edge" — FastAPI Backend
=============================================================
FIXES v5.3:
  [1] ATR con True Range real → SL/TP/ENTRADA correctos por símbolo
  [2] S&P500 y NASDAQ100 usan sus listas originales → no pierden símbolos
  [3] Batch downloads (10 símbolos por llamada) → 5-8x más rápido
  [4] max_workers=20, cache TTL=60s
  [5] TP1 corregido: e ± 1.5*ATR (simétrico con SL)
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import yfinance as yf
import pandas as pd
import numpy as np
import traceback, time, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from nau_quantum_engine import NAUQuantumAlphaIndicator
from stock_universe import (
    SCAN_UNIVERSE, INDEX_MEMBERSHIP, SYMBOLS_DB,
    SP500, NASDAQ_100, DOW_30, RUSSELL_2000_TOP,
    ETFS, CRYPTO, INDICES, COMMODITIES_FOREX
)

app = FastAPI(title="NAU Quantum v5.3 — Sentinel Quantum Edge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CACHE = {}
CACHE_TTL = 300

def cache_get(key):
    if key in CACHE and time.time() - CACHE[key][1] < CACHE_TTL:
        return CACHE[key][0]
    return None

def cache_set(key, data):
    CACHE[key] = (data, time.time())

INTERVAL_MAP = {
    "1m":  {"yf": "1m",  "period": "7d",   "resample": None},
    "5m":  {"yf": "5m",  "period": "60d",  "resample": None},
    "15m": {"yf": "15m", "period": "60d",  "resample": None},
    "30m": {"yf": "30m", "period": "60d",  "resample": None},
    "1h":  {"yf": "1h",  "period": "730d", "resample": None},
    "4h":  {"yf": "1h",  "period": "730d", "resample": "4h"},
    "1d":  {"yf": "1d",  "period": "5y",   "resample": None},
    "1wk": {"yf": "1wk", "period": "10y",  "resample": None},
    "1mo": {"yf": "1mo", "period": "max",  "resample": None},
    "3mo": {"yf": "3mo", "period": "max",  "resample": None},
}

indicator = NAUQuantumAlphaIndicator()

# ── UNIVERSO POR ÍNDICE ──────────────────────────────────────────────────────
_INDEX_MAP = {
    "S&P500":      SP500,
    "NASDAQ100":   NASDAQ_100,
    "DOW30":       DOW_30,
    "RUSSELL2000": RUSSELL_2000_TOP,
    "ETF":         ETFS,
    "CRYPTO":      CRYPTO,
    "INDEX":       INDICES,
    "COMM/FX":     COMMODITIES_FOREX,
}

def get_index_symbols(index_filter: str) -> list:
    if index_filter == "ALL":
        return SCAN_UNIVERSE
    raw_list = _INDEX_MAP.get(index_filter)
    if raw_list is not None:
        seen, result = set(), []
        for s in raw_list:
            if s not in seen:
                seen.add(s)
                result.append({"s": s, "idx": " · ".join(sorted(INDEX_MEMBERSHIP.get(s, {"OTHER"})))})
        return result
    return [u for u in SCAN_UNIVERSE if index_filter in INDEX_MEMBERSHIP.get(u["s"], set())]

# ── SEÑAL ────────────────────────────────────────────────────────────────────
def signal_label(score, confidence):
    conf = confidence * 100 if confidence <= 1 else confidence
    if   score >  35 and conf > 70: return "COMPRA FUERTE"
    elif score >  20 and conf > 60: return "COMPRA"
    elif score < -35 and conf > 70: return "VENTA FUERTE"
    elif score < -20 and conf > 60: return "VENTA"
    return "NEUTRAL"

def generate_explanation(summary, sl_tp, factors):
    sig, conf, label = summary["signal"], summary["confidence"], signal_label(summary["signal"], summary["confidence"])
    bullish = sum(1 for f in factors.values() if f >  10)
    bearish = sum(1 for f in factors.values() if f < -10)
    neutral = 18 - bullish - bearish
    if   label in ("COMPRA FUERTE","COMPRA"): action,direction,emoji = "COMPRAR (LONG)","alcista","🟢"
    elif label in ("VENTA FUERTE","VENTA"):   action,direction,emoji = "VENDER (SHORT)","bajista","🔴"
    else:                                      action,direction,emoji = "ESPERAR","indefinida","🟡"
    lines = [f"{emoji} SEÑAL: {label} — Acción: {action}",
             f"Confianza: {conf:.0f}% | Régimen: {summary['regime_name']} | Score: {sig:+.1f}", ""]
    if label != "NEUTRAL":
        aligned = bullish if sig > 0 else bearish
        lines.append(f"CONFLUENCIA: {aligned}/18 factores {direction}.")
        for name, val in sorted(factors.items(), key=lambda x: abs(x[1]), reverse=True)[:5]:
            lines.append(f"  • {name}: {val:+.1f} ({'alcista' if val>0 else 'bajista'})")
        if sl_tp:
            rr = abs(sl_tp["tp2"]-sl_tp["entry"]) / max(abs(sl_tp["entry"]-sl_tp["sl"]),0.01)
            lines += ["", f"ENTRADA: ${sl_tp['entry']:.2f}",
                      f"SL: ${sl_tp['sl']:.2f} | TP1: ${sl_tp['tp1']:.2f} | TP2: ${sl_tp['tp2']:.2f} | TP3: ${sl_tp['tp3']:.2f}",
                      f"R:R = 1:{rr:.1f}"]
    else:
        lines += [f"Factores: {bullish} alcistas, {bearish} bajistas, {neutral} neutrales.", "Esperar confluencia > 65%."]
    return "\n".join(lines)

# ── TÉCNICOS + ATR REAL ──────────────────────────────────────────────────────
def compute_technicals(df):
    c = df["Close"].values.astype(float)
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    v = df["Volume"].values.astype(float)
    tp = (h+l+c)/3; cv = np.cumsum(v)
    df["VWAP"] = np.where(cv>0, np.cumsum(tp*v)/cv, c)
    for p in [9,21,50,200]:
        if len(c)>=p: df[f"EMA_{p}"] = pd.Series(c).ewm(span=p,adjust=False).mean().values
    if len(c)>=20:
        s20=pd.Series(c).rolling(20).mean(); st20=pd.Series(c).rolling(20).std()
        df["SMA_20"]=s20.values; df["BB_upper"]=(s20+2*st20).values; df["BB_lower"]=(s20-2*st20).values
    if len(c)>=14:
        d=pd.Series(c).diff(); g=d.where(d>0,0).rolling(14).mean(); lo=(-d.where(d<0,0)).rolling(14).mean()
        df["RSI"]=(100-100/(1+g/(lo+1e-10))).values
    if len(c)>=26:
        e12=pd.Series(c).ewm(span=12,adjust=False).mean(); e26=pd.Series(c).ewm(span=26,adjust=False).mean()
        macd=e12-e26; sig=macd.ewm(span=9,adjust=False).mean()
        df["MACD"]=macd.values; df["MACD_signal"]=sig.values; df["MACD_hist"]=(macd-sig).values
    # ── ATR TRUE RANGE (FIX) ─────────────────────────────────────────────────
    if len(c)>=14:
        prev_c = np.concatenate([[c[0]], c[:-1]])
        tr = np.maximum(h-l, np.maximum(np.abs(h-prev_c), np.abs(l-prev_c)))
        df["ATR14"] = pd.Series(tr).rolling(14).mean().values
    return df

# ── NORMALIZACIÓN OHLCV ──────────────────────────────────────────────────────
def _normalize_df(raw):
    if raw is None or (hasattr(raw,"empty") and raw.empty): return None,"Empty"
    if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)
    raw = raw.loc[:, ~raw.columns.duplicated(keep="first")]
    rename = {}
    for col in raw.columns:
        cl = str(col).lower().strip()
        if   cl=="open":               rename[col]="Open"
        elif cl=="high":               rename[col]="High"
        elif cl=="low":                rename[col]="Low"
        elif cl in("close","adj close"):rename[col]="Close"
        elif cl=="volume":             rename[col]="Volume"
    raw = raw.rename(columns=rename)
    needed=["Open","High","Low","Close","Volume"]
    missing=[c for c in needed if c not in raw.columns]
    if missing: return None,f"Missing:{missing}"
    df=raw[needed].copy()
    for col in needed:
        s=df[col]
        if isinstance(s,pd.DataFrame): s=s.iloc[:,0]
        df[col]=pd.to_numeric(s,errors="coerce")
    df["Volume"]=df["Volume"].fillna(0)
    df=df.dropna(subset=["Open","High","Low","Close"])
    if len(df)<2: return None,"Too few rows"
    return df,None

def safe_download(sym,period,interval,prepost=False):
    try:
        raw=yf.download(sym,period=period,interval=interval,prepost=prepost,auto_adjust=True,progress=False)
    except Exception as e: return None,str(e)
    return _normalize_df(raw)

# ── BATCH DOWNLOAD (FIX VELOCIDAD) ──────────────────────────────────────────
BATCH_SIZE = 10

def batch_download(symbols:list, period:str, interval:str) -> dict:
    if not symbols: return {}
    if len(symbols)==1:
        df,err=safe_download(symbols[0],period,interval)
        return {symbols[0]: df if not err else None}
    try:
        raw=yf.download(symbols,period=period,interval=interval,
                        auto_adjust=True,progress=False,group_by="ticker",threads=True)
    except Exception:
        return {s:None for s in symbols}
    result={}
    for sym in symbols:
        try:
            if sym not in raw.columns.get_level_values(0): result[sym]=None; continue
            df,_=_normalize_df(raw[sym].copy())
            result[sym]=df
        except: result[sym]=None
    return result

# ── CONSTRUIR RESULTADO ──────────────────────────────────────────────────────
FACTOR_COLS=[
    "NAU_Kalman_Score","NAU_Wavelet_Score","NAU_HMM_Score","NAU_Entropy_Score",
    "NAU_Hurst_Score","NAU_Fractal_Score","NAU_OB_Score","NAU_FVG_Score",
    "NAU_Structure_Score","NAU_Williams_Score","NAU_Attention_Score","NAU_RL_Score",
    "NAU_DeepRegime_Score","NAU_OrderFlow_Score","NAU_MicroStructure_Score","NAU_MTF_Score"
]
ALL_COLS=(["NAU_Signal","NAU_Confidence","NAU_Regime","NAU_Kalman"]+FACTOR_COLS+
          ["VWAP","EMA_9","EMA_21","EMA_50","EMA_200","SMA_20","BB_upper","BB_lower",
           "RSI","MACD","MACD_signal","MACD_hist","ATR14"])

def _build_result(sym,interval,df,dl_time=0,calc_time=0):
    bars,signals=[],[]
    for idx,row in df.iterrows():
        try:    ts=int(idx.timestamp())
        except: ts=int(pd.Timestamp(idx).timestamp())
        bar={"time":ts,"open":round(float(row["Open"]),4),"high":round(float(row["High"]),4),
             "low":round(float(row["Low"]),4),"close":round(float(row["Close"]),4),
             "volume":int(float(row["Volume"]))}
        for col in ALL_COLS:
            if col in df.columns:
                v=row.get(col)
                if v is not None and pd.notna(v): bar[col]=round(float(v),4)
        bars.append(bar)
        if row.get("NAU_Long",False):
            signals.append({"time":ts,"type":"LONG","price":bar["close"],
                            "confidence":round(float(row["NAU_Confidence"])*100,1),
                            "signal_score":round(float(row["NAU_Signal"]),1),
                            "label":signal_label(row["NAU_Signal"],row["NAU_Confidence"])})
        if row.get("NAU_Short",False):
            signals.append({"time":ts,"type":"SHORT","price":bar["close"],
                            "confidence":round(float(row["NAU_Confidence"])*100,1),
                            "signal_score":round(float(row["NAU_Signal"]),1),
                            "label":signal_label(row["NAU_Signal"],row["NAU_Confidence"])})
    last=df.iloc[-1]
    sig_val=float(last["NAU_Signal"]); conf_val=float(last["NAU_Confidence"])
    cur_label=signal_label(sig_val,conf_val)
    # ── SL/TP con ATR real (FIX) ─────────────────────────────────────────────
    sl_tp=None
    if cur_label!="NEUTRAL":
        if "ATR14" in df.columns and pd.notna(last.get("ATR14")):
            atr=float(last["ATR14"])
        else:
            tail=df.tail(14); prev_c=tail["Close"].shift(1).fillna(tail["Close"])
            tr=np.maximum(tail["High"].values-tail["Low"].values,
                          np.maximum(np.abs(tail["High"].values-prev_c.values),
                                     np.abs(tail["Low"].values-prev_c.values)))
            atr=float(np.mean(tr))
        atr=max(atr,0.01); e=float(last["Close"])
        if cur_label in("COMPRA FUERTE","COMPRA"):
            sl_tp={"type":"LONG","entry":round(e,4),"sl":round(e-1.5*atr,4),
                   "tp1":round(e+1.5*atr,4),"tp2":round(e+3.0*atr,4),"tp3":round(e+4.5*atr,4),"atr":round(atr,4)}
        else:
            sl_tp={"type":"SHORT","entry":round(e,4),"sl":round(e+1.5*atr,4),
                   "tp1":round(e-1.5*atr,4),"tp2":round(e-3.0*atr,4),"tp3":round(e-4.5*atr,4),"atr":round(atr,4)}
    factors_dict={}
    for col in FACTOR_COLS:
        if col in df.columns and pd.notna(last.get(col)):
            factors_dict[col.replace("NAU_","").replace("_Score","")]=round(float(last[col]),1)
    summary={"symbol":sym,"interval":interval,"bars_count":len(bars),
             "signal":round(sig_val,1),"confidence":round(conf_val*100,1),
             "regime":int(last["NAU_Regime"]),
             "regime_name":{0:"BULL",1:"BEAR",2:"RANGE"}.get(int(last["NAU_Regime"]),"RANGE"),
             "label":cur_label,"last_price":round(float(last["Close"]),4),
             "timing":{"download":round(dl_time,2),"compute":round(calc_time,2)}}
    explanation=generate_explanation(summary,sl_tp,factors_dict)
    return{"bars":bars,"signals":signals,"sl_tp":sl_tp,"summary":summary,"explanation":explanation,"factors":factors_dict}

def _compute_from_df(sym,interval,df_raw,resample=None):
    df=df_raw.copy()
    if resample:
        df=df.resample(resample).agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
    if len(df)<50: return{"error":f"Only {len(df)} bars — need 50+"}
    try:    df=indicator.compute(df)
    except Exception as e: return{"error":f"Engine:{str(e)[:120]}"}
    df=compute_technicals(df)
    return _build_result(sym,interval,df)

def download_and_compute(sym,interval,prepost=False):
    ck=f"{sym}:{interval}:{prepost}"
    cached=cache_get(ck)
    if cached: return cached
    config=INTERVAL_MAP.get(interval)
    if not config: return{"error":f"Invalid interval:{interval}"}
    t0=time.time()
    df,err=safe_download(sym,config["period"],config["yf"],prepost)
    dl_time=time.time()-t0
    if err: return{"error":f"Download failed for {sym}:{err}"}
    if df is None or df.empty: return{"error":f"No data for {sym}"}
    if config["resample"]:
        df=df.resample(config["resample"]).agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
    if len(df)<50: return{"error":f"Only {len(df)} bars for {sym} on {interval}. Need 50+."}
    t0=time.time()
    try:    df=indicator.compute(df)
    except Exception as e: return{"error":f"Engine error:{str(e)} | {traceback.format_exc()[-300:]}"}
    df=compute_technicals(df)
    result=_build_result(sym,interval,df,dl_time,time.time()-t0)
    cache_set(ck,result)
    return result

# ═══ SCANNER PARALELO CON BATCH DOWNLOADS ════════════════════════════════════
def _make_scan_row(sym,data,idx_label,min_conf):
    if not data or "error" in data: return None
    s=data["summary"]
    if s["confidence"]<min_conf or abs(s["signal"])<15 or s["label"]=="NEUTRAL": return None
    ei=data.get("sl_tp") or {}; f=data.get("factors",{})
    top5=sorted(f.items(),key=lambda x:abs(x[1]),reverse=True)[:5]
    reasoning=f"{s['label']} | {s['regime_name']} | "+", ".join(f"{k}:{v:+.0f}" for k,v in top5)
    return{"symbol":sym,"index":idx_label,"signal":s["signal"],"confidence":s["confidence"],
           "regime":s["regime_name"],"label":s["label"],
           "direction":"LONG" if s["signal"]>0 else "SHORT","price":s["last_price"],
           "entry":ei.get("entry",s["last_price"]),"sl":ei.get("sl",0),
           "tp1":ei.get("tp1",0),"tp2":ei.get("tp2",0),"tp3":ei.get("tp3",0),
           "reasoning":reasoning,"score":round(abs(s["signal"])*(s["confidence"]/100),1)}

@app.get("/api/scan")
def scan_stocks(interval:str=Query("1d"),min_confidence:float=Query(55),index:str=Query("ALL")):
    universe=get_index_symbols(index)
    config=INTERVAL_MAP.get(interval)
    if not config: return{"error":f"Invalid interval:{interval}"}
    t0=time.time(); results=[]
    # 1. Caché
    to_download=[]
    for si in universe:
        sym=si["s"]; ck=f"{sym}:{interval}:False"
        idx_label=si.get("idx"," · ".join(sorted(INDEX_MEMBERSHIP.get(sym,{"OTHER"}))))
        cached=cache_get(ck)
        if cached:
            row=_make_scan_row(sym,cached,idx_label,min_confidence)
            if row: results.append(row)
        else: to_download.append(si)
    # 2. Batch downloads
    syms_only=[si["s"] for si in to_download]
    batches=[syms_only[i:i+BATCH_SIZE] for i in range(0,len(syms_only),BATCH_SIZE)]
    batch_dfs={}
    with ThreadPoolExecutor(max_workers=20) as ex:
        futs={ex.submit(batch_download,b,config["period"],config["yf"]):b for b in batches}
        for fut in as_completed(futs):
            try: batch_dfs.update(fut.result())
            except: pass
    # 3. Computar en paralelo
    def _process(si):
        sym=si["s"]; idx_label=si.get("idx"," · ".join(sorted(INDEX_MEMBERSHIP.get(sym,{"OTHER"}))))
        ck=f"{sym}:{interval}:False"; df_raw=batch_dfs.get(sym)
        if df_raw is None or (hasattr(df_raw,"empty") and df_raw.empty): return None
        data=_compute_from_df(sym,interval,df_raw,config.get("resample"))
        if "error" not in data: cache_set(ck,data)
        return _make_scan_row(sym,data,idx_label,min_confidence)
    with ThreadPoolExecutor(max_workers=20) as ex:
        for row in ex.map(_process,to_download):
            if row: results.append(row)
    results.sort(key=lambda x:x["score"],reverse=True)
    return{"scan_results":results[:50],"total_scanned":len(universe),"total_found":len(results),
           "scan_time":round(time.time()-t0,1),"interval":interval,"index_filter":index,"timestamp":int(time.time())}

@app.get("/api/chart")
def get_chart(symbol:str=Query("AAPL"),interval:str=Query("1d"),prepost:bool=Query(False)):
    try: return download_and_compute(symbol.upper().strip(),interval,prepost)
    except Exception as e: return{"error":f"Server error:{str(e)}"}

@app.get("/api/search")
def search_symbols(q:str=Query("")):
    if len(q)<1: return{"results":SYMBOLS_DB[:20]}
    ql=q.lower()
    return{"results":[s for s in SYMBOLS_DB if ql in s["s"].lower() or ql in s["n"].lower()][:20]}

@app.get("/api/health")
def health():
    return{"status":"ok","version":"5.3","engine":"Sentinel Quantum Edge 18-Factor AI/ML",
           "scan_universe":len(SCAN_UNIVERSE),"cache":len(CACHE),
           "indices":{"SP500":len(set(SP500)),"NASDAQ100":len(set(NASDAQ_100)),
                      "DOW30":len(set(DOW_30)),"RUSSELL2000":len(set(RUSSELL_2000_TOP))}}

@app.get("/")
def root():
    if os.path.exists("/app/static/index.html"): return FileResponse("/app/static/index.html")
    return{"message":"NAU Quantum v5.3","docs":"/docs"}

if os.path.exists("/app/static"):
    app.mount("/static",StaticFiles(directory="/app/static"),name="static")

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=9000,workers=4)
