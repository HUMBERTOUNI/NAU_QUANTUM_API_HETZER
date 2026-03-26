"""
NAU Quantum v5.4 "Sentinel Quantum Edge" — FastAPI Backend
FIXED: Bulk Download + 260-Bar Truncation for Extreme Scanner Speed
Peru timezone: UTC-5 applied to all timestamps
"""
from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import yfinance as yf
import pandas as pd
import numpy as np
import traceback, time, os, pickle, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from nau_quantum_engine import NAUQuantumAlphaIndicator
from stock_universe import (
    SCAN_UNIVERSE, INDEX_MEMBERSHIP, SYMBOLS_DB, filter_universe,
    SP500, NASDAQ_100, DOW_30, RUSSELL_2000_TOP
)

app = FastAPI(title="NAU Quantum v5.4 — Sentinel Quantum Edge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CACHE = {}
CACHE_TTL = 300  # 5 min caché — CX43 tiene RAM suficiente para guardar más tiempo
SCAN_CACHE = {}
PREV_CLOSE_CACHE = {}

# ═══ SIGNAL LOCK CACHE ═══
# Señales de velas CERRADAS nunca se modifican una vez calculadas.
# Clave: "SYM:interval:timestamp_utc" → {"type","confidence","signal_score","label"}
SIGNAL_LOCK_CACHE = {}
SIGNAL_LOCK_FILE = "signal_lock_cache.pkl"
_signal_lock_mutex = threading.Lock()

def _load_signal_lock():
    global SIGNAL_LOCK_CACHE
    try:
        if os.path.exists(SIGNAL_LOCK_FILE):
            with open(SIGNAL_LOCK_FILE, "rb") as f:
                SIGNAL_LOCK_CACHE = pickle.load(f)
    except:
        SIGNAL_LOCK_CACHE = {}

def _save_signal_lock():
    try:
        with open(SIGNAL_LOCK_FILE, "wb") as f:
            pickle.dump(SIGNAL_LOCK_CACHE, f)
    except:
        pass

_load_signal_lock()

def cache_get(key):
    if key in CACHE and time.time() - CACHE[key][1] < CACHE_TTL:
        return CACHE[key][0]
    return None

def cache_set(key, data):
    CACHE[key] = (data, time.time())

INTERVAL_MAP = {
    "1m":{"yf":"1m","period":"7d","resample":None},
    "5m":{"yf":"5m","period":"60d","resample":None},
    "15m":{"yf":"15m","period":"60d","resample":None},
    "30m":{"yf":"30m","period":"60d","resample":None},
    "1h":{"yf":"1h","period":"730d","resample":None},
    "2h":{"yf":"1h","period":"730d","resample":"2h"},
    "4h":{"yf":"1h","period":"730d","resample":"4h"},
    "1d":{"yf":"1d","period":"5y","resample":None},
    "1wk":{"yf":"1wk","period":"10y","resample":None},
    "1mo":{"yf":"1mo","period":"max","resample":None},
    "3mo":{"yf":"3mo","period":"max","resample":None},
    "6mo":{"yf":"1mo","period":"max","resample":"6MS"},
    "1y":{"yf":"3mo","period":"max","resample":"YS"},
}

# =================================================================
# SISTEMA DE CACHÉ INTELIGENTE Y DESCARGA MASIVA
# =================================================================
CACHE_DIR = "market_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
FAST_RAM_CACHE = {}

def bulk_warmup(symbols, period, interval, prepost):
    """Descarga hasta 500 acciones de golpe para evitar bloqueos y acelerar el escáner."""
    expire_sec = 60 if "m" in interval else (900 if "h" in interval else 14400)
    missing = []
    
    for sym in symbols:
        ckey = f"{sym}_{interval}_{prepost}"
        found = False
        if ckey in FAST_RAM_CACHE:
            if time.time() - FAST_RAM_CACHE[ckey][1] < expire_sec: found = True
        if not found:
            filepath = os.path.join(CACHE_DIR, f"{ckey}.pkl")
            if os.path.exists(filepath) and time.time() - os.path.getmtime(filepath) < expire_sec:
                try:
                    FAST_RAM_CACHE[ckey] = (pickle.load(open(filepath, "rb")), os.path.getmtime(filepath))
                    found = True
                except: pass
        if not found: missing.append(sym)
        
    if not missing: return
    
    try:
        # Descarga en bloques de 150 para no sobrecargar RAM
        for i in range(0, len(missing), 150):
            chunk = missing[i:i+150]
            raw = yf.download(chunk, period=period, interval=interval, prepost=prepost, group_by='ticker', progress=False, threads=True)
            if raw is None or raw.empty: continue
            
            for sym in chunk:
                try:
                    if len(chunk) == 1: df = raw.copy()
                    else:
                        if sym not in raw.columns.get_level_values(0): continue
                        df = raw[sym].copy()
                    
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                        
                    df = df.dropna(subset=['Close'])
                    if df.empty: continue
                    
                    rename = {c: str(c).title() for c in df.columns}
                    if 'Adj Close' in rename: rename['Adj Close'] = 'Close'
                    df = df.rename(columns=rename)
                    
                    needed = ['Open','High','Low','Close','Volume']
                    for c in needed:
                        if c not in df.columns: df[c] = df['Close'] if c != 'Volume' else 0
                            
                    df = df[needed]
                    for col in needed:
                        if isinstance(df[col], pd.DataFrame): df[col] = pd.to_numeric(df[col].iloc[:,0], errors='coerce')
                        else: df[col] = pd.to_numeric(df[col], errors='coerce')
                            
                    df['Volume'] = df['Volume'].fillna(0)
                    df = df.dropna(subset=['Open','High','Low','Close'])
                    if df.empty: continue
                    
                    ckey = f"{sym}_{interval}_{prepost}"
                    FAST_RAM_CACHE[ckey] = (df, time.time())
                    try: pickle.dump(df, open(os.path.join(CACHE_DIR, f"{ckey}.pkl"), "wb"))
                    except: pass
                except: pass
    except: pass


def safe_download(sym, period, interval, prepost=False):
    ckey = f"{sym}_{interval}_{prepost}"
    
    if "m" in interval: expire_sec = 60       
    elif "h" in interval: expire_sec = 900    
    else: expire_sec = 14400                  

    if ckey in FAST_RAM_CACHE:
        df_cached, timestamp = FAST_RAM_CACHE[ckey]
        if time.time() - timestamp < expire_sec:
            return df_cached.copy(), None

    filepath = os.path.join(CACHE_DIR, f"{ckey}.pkl")
    if os.path.exists(filepath):
        if time.time() - os.path.getmtime(filepath) < expire_sec:
            try:
                df_cached = pickle.load(open(filepath, "rb"))
                FAST_RAM_CACHE[ckey] = (df_cached, os.path.getmtime(filepath))
                return df_cached.copy(), None
            except: pass

    try:
        raw = yf.download(sym, period=period, interval=interval, prepost=prepost, progress=False)
    except Exception as e:
        return None, str(e)
        
    if raw is None or raw.empty: return None, "Empty"
    
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.loc[:, ~raw.columns.duplicated(keep='first')]
    
    rename = {}
    for c in raw.columns:
        cl = str(c).lower().strip()
        if cl == 'open': rename[c] = 'Open'
        elif cl == 'high': rename[c] = 'High'
        elif cl == 'low': rename[c] = 'Low'
        elif cl in ('close','adj close'): rename[c] = 'Close'
        elif cl == 'volume': rename[c] = 'Volume'
        
    raw = raw.rename(columns=rename)
    needed = ['Open','High','Low','Close','Volume']
    missing = [c for c in needed if c not in raw.columns]
    if missing: return None, f"Missing: {missing}"
    
    df = raw[needed].copy()
    
    for col in needed:
        s = df[col]
        if isinstance(s, pd.DataFrame): 
            df[col] = pd.to_numeric(s.iloc[:,0], errors='coerce')
        else:
            df[col] = pd.to_numeric(s, errors='coerce')
            
    df['Volume'] = df['Volume'].fillna(0)
    df = df.dropna(subset=['Open','High','Low','Close'])
    
    FAST_RAM_CACHE[ckey] = (df, time.time())
    try:
        pickle.dump(df, open(filepath, "wb"))
    except: pass
        
    return df, None

def _safe_get_data(symbols, period="1mo"):
    bulk_warmup(symbols, period, "1d", False)
    results = {}
    def fetch(sym):
        df, err = safe_download(sym, period, "1d", False)
        if df is not None and not df.empty and len(df) >= 2:
            return sym, df
        return sym, None
        
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_sym = {executor.submit(fetch, sym): sym for sym in symbols}
        for future in as_completed(future_to_sym):
            sym, hist = future.result()
            if hist is not None:
                results[sym] = hist
    return results

def get_prev_close(sym):
    ck = f"pc:{sym}"
    if ck in PREV_CLOSE_CACHE and time.time() - PREV_CLOSE_CACHE[ck][1] < 3600:
        return PREV_CLOSE_CACHE[ck][0]
    try:
        t = yf.Ticker(sym)
        info = t.fast_info
        pc = float(info.get("previousClose", 0) or info.get("regularMarketPreviousClose", 0))
        if pc > 0:
            PREV_CLOSE_CACHE[ck] = (pc, time.time())
            return pc
    except:
        pass
    return 0

indicator = NAUQuantumAlphaIndicator()

def signal_label(score, confidence):
    conf = confidence * 100 if confidence <= 1 else confidence
    if score > 35 and conf > 70: return "COMPRA FUERTE"
    if score > 20 and conf > 60: return "COMPRA"
    if score < -35 and conf > 70: return "VENTA FUERTE"
    if score < -20 and conf > 60: return "VENTA"
    return "NEUTRAL"

def generate_explanation(summary, sl_tp, factors):
    sig, conf, regime = summary["signal"], summary["confidence"], summary["regime_name"]
    label = signal_label(sig, conf)
    bullish = sum(1 for f in factors.values() if f > 10)
    bearish = sum(1 for f in factors.values() if f < -10)
    neutral = 18 - bullish - bearish
    if label in ("COMPRA FUERTE","COMPRA"):
        action, direction, emoji = "COMPRAR (LONG)", "alcista", "🟢"
    elif label in ("VENTA FUERTE","VENTA"):
        action, direction, emoji = "VENDER (SHORT)", "bajista", "🔴"
    else:
        action, direction, emoji = "ESPERAR", "indefinida", "🟡"
    lines = [f"{emoji} SEÑAL: {label} — Acción: {action}",
             f"Confianza: {conf:.0f}% | Régimen: {regime} | Score: {sig:+.1f}", ""]
    if label != "NEUTRAL":
        aligned = bullish if sig > 0 else bearish
        lines.append(f"CONFLUENCIA: {aligned}/18 factores {direction}.")
        for name, val in sorted(factors.items(), key=lambda x: abs(x[1]), reverse=True)[:5]:
            lines.append(f"  • {name}: {val:+.1f} ({'alcista' if val>0 else 'bajista'})")
        if sl_tp:
            lines += ["",f"ENTRADA: ${sl_tp['entry']:.2f}",
                      f"SL: ${sl_tp['sl']:.2f} | TP1: ${sl_tp['tp1']:.2f} | TP2: ${sl_tp['tp2']:.2f} | TP3: ${sl_tp['tp3']:.2f}",
                      f"R:R = 1:{abs(sl_tp['tp2']-sl_tp['entry'])/max(abs(sl_tp['entry']-sl_tp['sl']),0.01):.1f}"]
    else:
        lines += [f"Factores: {bullish} alcistas, {bearish} bajistas, {neutral} neutrales.",
                  "Esperar confluencia > 65%."]
    return "\n".join(lines)

def compute_technicals(df):
    c = df["Close"].values.astype(float)
    h, l, v = df["High"].values.astype(float), df["Low"].values.astype(float), df["Volume"].values.astype(float)
    tp = (h + l + c) / 3; cv = np.cumsum(v)
    df["VWAP"] = np.where(cv > 0, np.cumsum(tp * v) / cv, c)
    for p in [9, 21, 50, 200]:
        if len(c) >= p: df[f"EMA_{p}"] = pd.Series(c).ewm(span=p, adjust=False).mean().values
    if len(c) >= 20:
        s20 = pd.Series(c).rolling(20).mean(); st20 = pd.Series(c).rolling(20).std()
        df["SMA_20"] = s20.values; df["BB_upper"] = (s20+2*st20).values; df["BB_lower"] = (s20-2*st20).values
    if len(c) >= 14:
        d = pd.Series(c).diff()
        g = d.where(d>0,0).rolling(14).mean(); lo = (-d.where(d<0,0)).rolling(14).mean()
        df["RSI"] = (100 - 100/(1+g/(lo+1e-10))).values
    if len(c) >= 26:
        e12 = pd.Series(c).ewm(span=12,adjust=False).mean(); e26 = pd.Series(c).ewm(span=26,adjust=False).mean()
        macd = e12-e26; sig = macd.ewm(span=9,adjust=False).mean()
        df["MACD"] = macd.values; df["MACD_signal"] = sig.values; df["MACD_hist"] = (macd-sig).values
    return df

def download_and_compute(sym, interval, prepost=False):
    ck = f"{sym}:{interval}:{prepost}"
    cached = cache_get(ck)
    if cached: return cached
    config = INTERVAL_MAP.get(interval)
    if not config: return {"error": f"Invalid interval: {interval}"}
    t0 = time.time()
    df, err = safe_download(sym, config["period"], config["yf"], prepost)
    dl_time = time.time() - t0
    if err: return {"error": f"Download failed for {sym}: {err}"}
    if df is None or df.empty: return {"error": f"No data for {sym}"}
    if config["resample"]:
        rs = config["resample"]
        from datetime import datetime
        import calendar
        now = datetime.utcnow()
        mar_second_sun = 14 - calendar.weekday(now.year, 3, 1) % 7 + 7
        nov_first_sun = 7 - calendar.weekday(now.year, 11, 1) % 7
        is_dst = (datetime(now.year, 3, mar_second_sun, 7) <= now < datetime(now.year, 11, nov_first_sun, 6))
        nyse_open_utc_min = 13*60+30 if is_dst else 14*60+30
        
        if rs == "2h":
            off_min = nyse_open_utc_min % 120
            df = df.resample(rs, offset=f"{off_min}min").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
        elif rs == "4h":
            off_min = nyse_open_utc_min % 240
            df = df.resample(rs, offset=f"{off_min}min").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
        else:
            df = df.resample(rs).agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
    if len(df) < 50: return {"error": f"Only {len(df)} bars for {sym} on {interval}. Need 50+."}
    t0 = time.time()
    try:
        df = indicator.compute(df)
    except Exception as e:
        return {"error": f"Engine error: {str(e)} | {traceback.format_exc()[-300:]}"}
    df = compute_technicals(df)
    calc_time = time.time() - t0

    bars, signals = [], []
    factor_cols = ["NAU_Kalman_Score","NAU_Wavelet_Score","NAU_HMM_Score","NAU_Entropy_Score",
                   "NAU_Hurst_Score","NAU_Fractal_Score","NAU_OB_Score","NAU_FVG_Score",
                   "NAU_Structure_Score","NAU_Williams_Score","NAU_Attention_Score","NAU_RL_Score",
                   "NAU_DeepRegime_Score","NAU_OrderFlow_Score","NAU_MicroStructure_Score","NAU_MTF_Score"]
    all_cols = ["NAU_Signal","NAU_Confidence","NAU_Regime","NAU_Kalman"] + factor_cols + \
               ["VWAP","EMA_9","EMA_21","EMA_50","EMA_200","SMA_20","BB_upper","BB_lower",
                "RSI","MACD","MACD_signal","MACD_hist"]
    PERU_OFFSET_SEC = -5 * 3600

    # Determinar cuál es la última vela (puede estar incompleta)
    all_timestamps = list(df.index)
    last_closed_idx = len(all_timestamps) - 2  # penúltima = última cerrada con certeza

    new_locks = {}

    for i, (idx, row) in enumerate(df.iterrows()):
        try: ts = int(idx.timestamp()) + PERU_OFFSET_SEC
        except: ts = int(pd.Timestamp(idx).timestamp()) + PERU_OFFSET_SEC
        bar = {"time":ts,"open":round(float(row["Open"]),4),"high":round(float(row["High"]),4),
               "low":round(float(row["Low"]),4),"close":round(float(row["Close"]),4),
               "volume":int(float(row["Volume"]))}
        for col in all_cols:
            if col in df.columns:
                v = row.get(col)
                if v is not None and pd.notna(v): bar[col] = round(float(v), 4)
        bars.append(bar)

        # ═══ SIGNAL LOCK LOGIC ═══
        # Para velas cerradas: primero consultar el lock cache.
        # Si ya hay una señal bloqueada, usarla. Si el engine genera nueva señal, guardarla.
        # La última vela (posiblemente abierta) NO se bloquea.
        is_closed = (i <= last_closed_idx)
        lock_key = f"{sym}:{interval}:{ts}"

        if is_closed and lock_key in SIGNAL_LOCK_CACHE:
            # Señal ya bloqueada — usar la original, ignorar recálculo del engine
            locked = SIGNAL_LOCK_CACHE[lock_key]
            signals.append({**locked, "time": ts})
        else:
            has_long = bool(row.get("NAU_Long", False))
            has_short = bool(row.get("NAU_Short", False))
            sig_entry = None
            if has_long:
                sig_entry = {"time":ts,"type":"LONG","price":bar["close"],
                             "confidence":round(float(row["NAU_Confidence"])*100,1),
                             "signal_score":round(float(row["NAU_Signal"]),1),
                             "label":signal_label(row["NAU_Signal"], row["NAU_Confidence"])}
            elif has_short:
                sig_entry = {"time":ts,"type":"SHORT","price":bar["close"],
                             "confidence":round(float(row["NAU_Confidence"])*100,1),
                             "signal_score":round(float(row["NAU_Signal"]),1),
                             "label":signal_label(row["NAU_Signal"], row["NAU_Confidence"])}

            if sig_entry:
                signals.append(sig_entry)
                if is_closed:
                    # Bloquear esta señal para que nunca desaparezca
                    new_locks[lock_key] = sig_entry

    # Persistir nuevas señales bloqueadas
    if new_locks:
        with _signal_lock_mutex:
            SIGNAL_LOCK_CACHE.update(new_locks)
            _save_signal_lock()

    last = df.iloc[-1]
    sig_val = float(last["NAU_Signal"])
    conf_val = float(last["NAU_Confidence"])
    current_label = signal_label(sig_val, conf_val)
    sl_tp = None
    if current_label != "NEUTRAL":
        atr = np.mean([bars[i]["high"]-bars[i]["low"] for i in range(max(0,len(bars)-14),len(bars))])
        e = bars[-1]["close"]
        if current_label in ("COMPRA FUERTE","COMPRA"):
            sl_tp = {"type":"LONG","entry":round(e,4),"sl":round(e-1.5*atr,4),
                     "tp1":round(e+2*atr,4),"tp2":round(e+3*atr,4),"tp3":round(e+4.5*atr,4),"atr":round(atr,4)}
        else:
            sl_tp = {"type":"SHORT","entry":round(e,4),"sl":round(e+1.5*atr,4),
                     "tp1":round(e-2*atr,4),"tp2":round(e-3*atr,4),"tp3":round(e-4.5*atr,4),"atr":round(atr,4)}

    factors_dict = {}
    for col in factor_cols:
        if col in df.columns and pd.notna(last.get(col)):
            factors_dict[col.replace("NAU_","").replace("_Score","")] = round(float(last[col]),1)

    prev_close = get_prev_close(sym)
    summary = {"symbol":sym,"interval":interval,"bars_count":len(bars),
        "signal":round(sig_val,1),"confidence":round(conf_val*100,1),
        "regime":int(last["NAU_Regime"]),
        "regime_name":{0:"BULL",1:"BEAR",2:"RANGE"}.get(int(last["NAU_Regime"]),"RANGE"),
        "label":current_label,"last_price":round(float(last["Close"]),4),
        "prev_close":round(prev_close,4),
        "timing":{"download":round(dl_time,2),"compute":round(calc_time,2)}}
    explanation = generate_explanation(summary, sl_tp, factors_dict)
    result = {"bars":bars,"signals":signals,"sl_tp":sl_tp,"summary":summary,
              "explanation":explanation,"factors":factors_dict}
    cache_set(ck, result)
    return result

def scan_fast(sym, interval):
    try:
        config = INTERVAL_MAP.get(interval, INTERVAL_MAP["1d"])
        yf_interval = config["yf"]
        scan_period = config["period"]

        df, err = safe_download(sym, scan_period, yf_interval, True)
        if err or df is None or df.empty:
            return None

        resample_map = {"2h":"2h","4h":"4h","6mo":"6MS","1y":"YS"}
        if interval in resample_map:
            rs = resample_map[interval]
            if rs in ("2h", "4h"):
                from datetime import datetime
                import calendar
                now = datetime.utcnow()
                mar_second_sun = 14 - calendar.weekday(now.year, 3, 1) % 7 + 7
                nov_first_sun = 7 - calendar.weekday(now.year, 11, 1) % 7
                is_dst = (datetime(now.year, 3, mar_second_sun, 7) <= now < datetime(now.year, 11, nov_first_sun, 6))
                nyse_open_utc_min = 13*60+30 if is_dst else 14*60+30
                interval_min = 120 if rs == "2h" else 240
                off_min = nyse_open_utc_min % interval_min
                df = df.resample(rs, offset=f"{off_min}min").agg(
                    {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
            else:
                df = df.resample(rs).agg(
                    {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()

        # ─── TRUNCADO INTELIGENTE PARA ACELERAR EL ESCÁNER 80% ───
        # Solo usamos 260 velas, suficiente para EMA200 y Modelos Ocultos. 
        if len(df) > 260:
            df = df.iloc[-260:].copy()

        if len(df) < 50:
            return None

        local_indicator = NAUQuantumAlphaIndicator()
        df = local_indicator.compute(df)
        last = df.iloc[-1]

        sig_val = float(last["NAU_Signal"])
        conf_val = float(last["NAU_Confidence"])
        conf_pct = conf_val * 100 if conf_val <= 1 else conf_val
        label = signal_label(sig_val, conf_pct)
        price = float(last["Close"])
        regime = {0:"BULL",1:"BEAR",2:"RANGE"}.get(int(last["NAU_Regime"]), "?")

        highs = df["High"].iloc[-14:].values.astype(float)
        lows = df["Low"].iloc[-14:].values.astype(float)
        atr = float(np.mean(highs - lows))

        factor_cols = ["NAU_Kalman_Score","NAU_Wavelet_Score","NAU_HMM_Score",
                       "NAU_Hurst_Score","NAU_OrderFlow_Score","NAU_Attention_Score"]
        factors = {}
        for col in factor_cols:
            if col in df.columns and pd.notna(last.get(col)):
                factors[col.replace("NAU_","").replace("_Score","")] = round(float(last[col]),1)

        return {
            "signal": round(sig_val, 1),
            "confidence": round(conf_pct, 1),
            "label": label,
            "price": round(price, 2),
            "regime": regime,
            "atr": atr,
            "factors": factors,
        }
    except Exception:
        return None

def scan_vc_one(sym_info, interval):
    """
    Busca acciones con 2+ señales consecutivas del MISMO tipo (LONG/SHORT)
    en las últimas velas CERRADAS y confirmadas.
    - Solo cuenta velas donde NAU_Long o NAU_Short = True (señal real generada por el engine)
    - Excluye la vela más reciente (puede estar incompleta)
    - Cuenta racha real hacia atrás
    """
    sym = sym_info["s"]
    try:
        config = INTERVAL_MAP.get(interval, INTERVAL_MAP["1d"])
        yf_int = config["yf"]
        scan_period = config["period"]

        df, err = safe_download(sym, scan_period, yf_int, True)
        if err or df is None or df.empty:
            return None

        resample_map = {"2h":"2h","4h":"4h","6mo":"6MS","1y":"YS"}
        if interval in resample_map:
            rs = resample_map[interval]
            if rs in ("2h", "4h"):
                from datetime import datetime as _dt
                import calendar as _cal
                _now = _dt.utcnow()
                _ms = 14 - _cal.weekday(_now.year, 3, 1) % 7 + 7
                _ns = 7 - _cal.weekday(_now.year, 11, 1) % 7
                _dst = (_dt(_now.year, 3, _ms, 7) <= _now < _dt(_now.year, 11, _ns, 6))
                _nopen = 13*60+30 if _dst else 14*60+30
                _intmin = 120 if rs == "2h" else 240
                df = df.resample(rs, offset=f"{_nopen % _intmin}min").agg(
                    {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
            else:
                df = df.resample(rs).agg(
                    {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()

        if len(df) > 260:
            df = df.iloc[-260:].copy()
        if len(df) < 50:
            return None

        local_ind = NAUQuantumAlphaIndicator()
        df = local_ind.compute(df)

        if len(df) < 10:
            return None

        # Usar SOLO velas cerradas (excluir la última que puede estar incompleta)
        completed = df.iloc[:-1]
        if len(completed) < 4:
            return None

        # Construir lista de señales por vela
        raw_signals = []
        for _, row in completed.iterrows():
            has_long = bool(row.get("NAU_Long", False))
            has_short = bool(row.get("NAU_Short", False))
            if has_long:
                raw_signals.append("LONG")
            elif has_short:
                raw_signals.append("SHORT")
            else:
                raw_signals.append("NONE")

        # La última señal del listado debe ser LONG o SHORT (no NONE)
        last_sig = raw_signals[-1]
        if last_sig == "NONE":
            return None

        # Contar racha consecutiva hacia atrás
        consecutive = 0
        for s in reversed(raw_signals):
            if s == last_sig:
                consecutive += 1
            else:
                break

        # Mínimo 2 señales consecutivas del mismo tipo
        if consecutive < 2:
            return None

        is_buy = (last_sig == "LONG")

        # Usar datos de la última vela cerrada para métricas
        last_closed = completed.iloc[-1]
        sig_val = float(last_closed.get("NAU_Signal", 0))
        conf_val = float(last_closed.get("NAU_Confidence", 0))
        label = signal_label(sig_val, conf_val)

        # Precio actual (última vela, puede estar abierta)
        current = df.iloc[-1]
        price = float(current["Close"])

        # ATR real sobre últimas 14 velas
        highs = df["High"].iloc[-14:].values.astype(float)
        lows  = df["Low"].iloc[-14:].values.astype(float)
        atr = float(np.mean(highs - lows))
        if atr <= 0 or np.isnan(atr):
            atr = price * 0.015

        if is_buy:
            entry = price
            sl    = round(price - 1.5 * atr, 2)
            tp1   = round(price + 2.0 * atr, 2)
            tp2   = round(price + 3.0 * atr, 2)
            tp3   = round(price + 4.5 * atr, 2)
        else:
            entry = price
            sl    = round(price + 1.5 * atr, 2)
            tp1   = round(price - 2.0 * atr, 2)
            tp2   = round(price - 3.0 * atr, 2)
            tp3   = round(price - 4.5 * atr, 2)

        name = sym
        for s in SYMBOLS_DB:
            if s["s"] == sym:
                name = s["n"]
                break

        return {
            "symbol": sym,
            "name": name,
            "label": label,
            "direction": "LONG" if is_buy else "SHORT",
            "consecutive": consecutive,
            "price": round(price, 2),
            "entry": round(entry, 2),
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
        }
    except Exception:
        return None

def scan_bridge(sym_info, interval, min_confidence):
    sym = sym_info["s"]
    res = scan_fast(sym, interval)
    if res and res["confidence"] >= min_confidence:
        res["symbol"] = sym
        res["index"] = " · ".join(sorted(INDEX_MEMBERSHIP.get(sym, {"OTHER"})))
        res["reasoning"] = f"Confluencia IA: {res['signal']:+.1f}. Régimen: {res['regime']}."
        res["entry"] = res["price"]
        
        if res["signal"] > 0:
            res["sl"] = res["price"] - 1.5 * res["atr"]
            res["tp1"] = res["price"] + 2 * res["atr"]
            res["tp2"] = res["price"] + 3 * res["atr"]
            res["direction"] = "LONG"
        else:
            res["sl"] = res["price"] + 1.5 * res["atr"]
            res["tp1"] = res["price"] - 2 * res["atr"]
            res["tp2"] = res["price"] - 3 * res["atr"]
            res["direction"] = "SHORT"
        return res
    return None

@app.get("/api/scan")
def scan_stocks(interval: str = Query("1d"), min_confidence: float = Query(55), index: str = Query("ALL")):
    try:
        universe = filter_universe(index)
        # Subimos el límite a 500 porque ahora el servidor vuela
        max_map = {"ALL": 500, "S&P500": 500, "NASDAQ100": 103, "DOW30": 31, "RUSSELL2000": 500, "ETF": 100}
        max_stocks = max_map.get(index, 250)
        universe = universe[:max_stocks]
        
        t0 = time.time()
        
        # DESCARGA MASIVA ANTES DE PROCESAR
        config = INTERVAL_MAP.get(interval, INTERVAL_MAP["1d"])
        sym_list = [s["s"] for s in universe]
        bulk_warmup(sym_list, config["period"], config["yf"], True)
        
        results = []
        with ThreadPoolExecutor(max_workers=48) as executor:
            future_map = {executor.submit(scan_bridge, si, interval, min_confidence): si for si in universe}
            for future in as_completed(future_map):
                try:
                    r = future.result()
                    if r: results.append(r)
                except Exception:
                    pass

        results.sort(key=lambda x: abs(x.get("signal", 0)), reverse=True)
        return {
            "scan_results": results[:50],
            "total_scanned": len(universe),
            "total_found": len(results),
            "scan_time": round(time.time() - t0, 1),
            "interval": interval,
            "index_filter": index
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/scan_vc")
def scan_vc(interval: str = Query("1d"), page: int = Query(1)):
    try:
        from stock_universe import SP500, NASDAQ_100, DOW_30, RUSSELL_2000_TOP, SP_MIDCAP_400, ADDITIONAL_STOCKS, ETFS, CRYPTO, INDICES, COMMODITIES_FOREX
        
        seen = set()
        def make_page(lists, max_n=500):
            page_syms = []
            for lst in lists:
                for s in lst:
                    if s not in seen and len(page_syms) < max_n:
                        seen.add(s)
                        page_syms.append({"s": s, "idx": " · ".join(sorted(INDEX_MEMBERSHIP.get(s, {"OTHER"})))})
            return page_syms
        
        pages = {
            1: make_page([SP500, NASDAQ_100, DOW_30], 500),
            2: make_page([RUSSELL_2000_TOP, SP_MIDCAP_400], 500),
            3: make_page([ADDITIONAL_STOCKS], 500),
            4: make_page([ETFS, CRYPTO, INDICES, COMMODITIES_FOREX], 500),
        }
        total_pages = len(pages)
        
        universe = pages.get(page, [])
        if not universe:
            return {"results": [], "total_scanned": 0, "scan_time": 0,
                    "page": page, "total_pages": total_pages, "error": "No more stocks"}
        
        t0 = time.time()
        
        # DESCARGA MASIVA ANTES DE PROCESAR
        config = INTERVAL_MAP.get(interval, INTERVAL_MAP["1d"])
        sym_list = [s["s"] for s in universe]
        bulk_warmup(sym_list, config["period"], config["yf"], True)
        
        results = []
        with ThreadPoolExecutor(max_workers=48) as executor:
            future_map = {executor.submit(scan_vc_one, si, interval): si for si in universe}
            for future in as_completed(future_map):
                try:
                    r = future.result()
                    if r is not None:
                        results.append(r)
                except Exception:
                    pass
        
        results.sort(key=lambda x: x.get("consecutive", 0), reverse=True)
        return {
            "results": results,
            "total_scanned": len(universe),
            "scan_time": round(time.time() - t0, 1),
            "interval": interval,
            "page": page,
            "total_pages": total_pages,
            "total_universe": 500,
            "timestamp": int(time.time()),
        }
    except Exception as e:
        return {"results": [], "total_scanned": 0, "scan_time": 0, "error": str(e),
                "page": page, "total_pages": 0}

@app.get("/api/report")
def generate_report(section: str = Query("all"), interval: str = Query("1d")):
    try:
        t0 = time.time()
        html_parts = []
        sections_to_run = list(range(1, 12)) if section == "all" else [int(section)]
        
        for sec in sections_to_run:
            try:
                if sec == 1: html_parts.append(report_top_performers_4weeks())
                elif sec == 2: html_parts.append(report_top_performers_4days())
                elif sec == 3: html_parts.append(report_earnings_next_10days())
                elif sec == 4: html_parts.append(report_likely_up_this_week())
                elif sec == 5: html_parts.append(report_likely_down_this_week())
                elif sec == 6: html_parts.append(report_4day_outlook())
                elif sec == 7: html_parts.append(report_sector_news())
                elif sec == 8: html_parts.append(report_market_today())
                elif sec == 9: html_parts.append(report_ai_tech_news())
                elif sec == 10: html_parts.append(report_ema200_stocks(interval))
                elif sec == 11: html_parts.append(report_fibonacci_fallen(interval))
            except Exception as e:
                html_parts.append(f'<div class="rpt-section"><h2>Sección {sec} — Error</h2><p>{str(e)}</p>')
        
        return {"html": "\n".join(html_parts), "generation_time": round(time.time() - t0, 1),
                "sections": sections_to_run, "interval": interval}
    except Exception as e:
        return {"error": str(e), "html": ""}

REPORT_CSS = """
<style>
.rpt-table{border-collapse:collapse;width:100%;margin:16px 0;font-size:12px}
.rpt-table th{background:#1a2332;color:#00bcd4;padding:10px 12px;text-align:left;border:1px solid #2a3a4a;font-size:11px;text-transform:uppercase;letter-spacing:0.5px}
.rpt-table td{padding:8px 12px;border:1px solid #1a2a3a;vertical-align:top}
.rpt-table tr:nth-child(even){background:rgba(255,255,255,0.02)}
.rpt-table tr:hover{background:rgba(0,188,212,0.05)}
.up{color:#26a69a;font-weight:600}.down{color:#ef5350;font-weight:600}
.neutral{color:#ff9800}
.rpt-section{margin:30px 0;padding:20px;background:rgba(255,255,255,0.02);border-radius:8px;border-left:4px solid #00bcd4}
.rpt-section h2{color:#00bcd4;margin:0 0 12px 0;font-size:18px}
.rpt-section h3{color:#ff9800;margin:16px 0 8px 0;font-size:14px}
.rpt-narrative{color:#ccc;line-height:1.7;margin:12px 0}
.rpt-badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600}
.badge-bull{background:#1b5e20;color:#66bb6a}.badge-bear{background:#b71c1c;color:#ef9a9a}
.badge-neutral{background:#4e342e;color:#ffab40}
.rpt-highlight{background:rgba(0,188,212,0.1);padding:12px;border-radius:6px;margin:12px 0;border:1px solid rgba(0,188,212,0.2)}
.rpt-footer{font-size:10px;color:#666;margin-top:8px;font-style:italic}
</style>
"""

def _deep_analysis(sym, hist):
    c = hist["Close"].values.astype(float)
    h = hist["High"].values.astype(float)
    l = hist["Low"].values.astype(float)
    v = hist["Volume"].values.astype(float)
    price = c[-1]
    
    emas = _calc_emas(c)
    rsi = _calc_rsi(c)
    
    macd_line = pd.Series(c).ewm(span=12).mean().iloc[-1] - pd.Series(c).ewm(span=26).mean().iloc[-1]
    macd_signal = (pd.Series(c).ewm(span=12).mean() - pd.Series(c).ewm(span=26).mean()).ewm(span=9).mean().iloc[-1]
    macd_hist = macd_line - macd_signal
    
    sma20 = pd.Series(c).rolling(20).mean().iloc[-1] if len(c) >= 20 else price
    std20 = pd.Series(c).rolling(20).std().iloc[-1] if len(c) >= 20 else 0
    bb_upper = sma20 + 2*std20
    bb_lower = sma20 - 2*std20
    bb_position = "cerca de banda superior (sobrecompra)" if price > bb_upper - std20*0.5 else (
        "cerca de banda inferior (sobreventa)" if price < bb_lower + std20*0.5 else "dentro de las bandas (normal)")
    
    vol_5d = np.mean(v[-5:]) if len(v) >= 5 else np.mean(v)
    vol_20d = np.mean(v[-20:]) if len(v) >= 20 else np.mean(v)
    vol_ratio = vol_5d / max(vol_20d, 1)
    vol_text = "volumen alto confirma movimiento" if vol_ratio > 1.3 else (
        "volumen bajo sugiere debilidad" if vol_ratio < 0.7 else "volumen normal")
    
    pct_5d = ((c[-1]-c[-5])/c[-5])*100 if len(c) >= 5 else 0
    
    ema_bull = price > emas["ema9"] > emas["ema21"]
    ema_bear = price < emas["ema9"] < emas["ema21"]
    
    parts = []
    
    if pct_5d > 3: parts.append(f"<b>Tendencia fuerte alcista</b> con {pct_5d:+.1f}% en 5 días")
    elif pct_5d > 0.5: parts.append(f"<b>Tendencia alcista moderada</b> ({pct_5d:+.1f}% en 5 días)")
    elif pct_5d < -3: parts.append(f"<b>Tendencia fuerte bajista</b> con {pct_5d:+.1f}% en 5 días")
    elif pct_5d < -0.5: parts.append(f"<b>Tendencia bajista moderada</b> ({pct_5d:+.1f}% en 5 días)")
    else: parts.append(f"<b>Movimiento lateral</b> ({pct_5d:+.1f}% en 5 días)")
    
    if ema_bull: parts.append("EMAs alineadas alcistamente (precio > EMA9 > EMA21)")
    elif ema_bear: parts.append("EMAs alineadas bajistamente (precio < EMA9 < EMA21)")
    else: parts.append("EMAs sin alineación clara — señal mixta")
    
    if emas["ema200"]:
        if price > emas["ema200"]: parts.append(f"Sobre EMA200 (${emas['ema200']}) — tendencia de largo plazo alcista")
        else: parts.append(f"<span class='down'>Bajo EMA200 (${emas['ema200']}) — tendencia de largo plazo bajista</span>")
    
    if rsi > 70: parts.append(f"<span class='down'>RSI {rsi} — SOBRECOMPRA, riesgo de corrección inminente</span>")
    elif rsi > 60: parts.append(f"RSI {rsi} — momentum fuerte pero acercándose a sobrecompra")
    elif rsi < 30: parts.append(f"<span class='up'>RSI {rsi} — SOBREVENTA, posible rebote técnico</span>")
    elif rsi < 40: parts.append(f"RSI {rsi} — momentum débil, posible oportunidad si hay soporte")
    else: parts.append(f"RSI {rsi} — zona neutral")
    
    if macd_hist > 0: parts.append(f"MACD positivo ({macd_hist:.2f}) — momentum comprador")
    else: parts.append(f"MACD negativo ({macd_hist:.2f}) — momentum vendedor")
    
    parts.append(f"Volumen: {vol_ratio:.1f}x promedio 20d — {vol_text}")
    parts.append(f"Bollinger: {bb_position}")
    
    return ". ".join(parts) + "."

def _calc_rsi(close_arr, period=14):
    d = pd.Series(close_arr).diff()
    g = d.where(d>0,0).rolling(period).mean().iloc[-1]
    l = (-d.where(d<0,0)).rolling(period).mean().iloc[-1]
    return round(100 - 100/(1+g/(l+1e-10)), 1)

def _calc_emas(close_arr):
    s = pd.Series(close_arr)
    return {
        "ema9": round(s.ewm(span=9).mean().iloc[-1], 2),
        "ema21": round(s.ewm(span=21).mean().iloc[-1], 2),
        "ema50": round(s.ewm(span=50).mean().iloc[-1], 2) if len(s) >= 50 else None,
        "ema200": round(s.ewm(span=200).mean().iloc[-1], 2) if len(s) >= 200 else None,
    }

def _get_name(sym):
    for s in SYMBOLS_DB:
        if s["s"] == sym: return s["n"]
    return sym

def _trend_text(pct):
    if pct > 5: return '<span class="badge-bull rpt-badge">FUERTE ALCISTA</span>'
    if pct > 1: return '<span class="badge-bull rpt-badge">ALCISTA</span>'
    if pct < -5: return '<span class="badge-bear rpt-badge">FUERTE BAJISTA</span>'
    if pct < -1: return '<span class="badge-bear rpt-badge">BAJISTA</span>'
    return '<span class="badge-neutral rpt-badge">LATERAL</span>'

def _rsi_text(rsi):
    if rsi > 70: return f'<span class="down">RSI {rsi} — SOBRECOMPRA</span>'
    if rsi > 60: return f'<span class="neutral">RSI {rsi} — Zona alta</span>'
    if rsi < 30: return f'<span class="up">RSI {rsi} — SOBREVENTA</span>'
    if rsi < 40: return f'<span class="neutral">RSI {rsi} — Zona baja</span>'
    return f'RSI {rsi} — Neutral'

def report_top_performers_4weeks():
    candidates = list(dict.fromkeys(SP500[:200] + NASDAQ_100[:50]))
    data = _safe_get_data(candidates[:150], "2mo")
    
    performers = []
    for sym, hist in data.items():
        c = hist["Close"].values.astype(float)
        if len(c) < 20: continue
        price = c[-1]
        price_4wk = c[-20]
        pct = ((price - price_4wk) / price_4wk) * 100
        rsi = _calc_rsi(c)
        vol_now = float(hist["Volume"].iloc[-5:].mean())
        vol_avg = float(hist["Volume"].iloc[-20:].mean())
        vol_ratio = vol_now / max(vol_avg, 1)
        emas = _calc_emas(c)
        performers.append({"sym":sym,"price":price,"price_4wk":price_4wk,"pct":pct,"rsi":rsi,"vol_ratio":vol_ratio,"emas":emas})
    
    performers.sort(key=lambda x: x["pct"], reverse=True)
    top = performers[:20]
    
    rows = ""
    for i, p in enumerate(top):
        name = _get_name(p["sym"])
        cls = "up" if p["pct"] > 0 else "down"
        analysis = f'{_trend_text(p["pct"])} | {_rsi_text(p["rsi"])} | Vol: {p["vol_ratio"]:.1f}x promedio'
        rows += f"""<tr><td>{i+1}</td><td><b>{p["sym"]}</b></td><td>{name}</td>
        <td class="{cls}"><b>{p["pct"]:+.2f}%</b></td><td>${p["price"]:.2f}</td><td>${p["price_4wk"]:.2f}</td>
        <td style="font-size:11px">{analysis}</td></tr>"""
    
    return REPORT_CSS + f"""<div class="rpt-section">
<h2>📈 1. Top 20 Acciones — Mejor Rendimiento Últimas 4 Semanas</h2>
<table class="rpt-table"><thead><tr>
<th>#</th><th>Ticker</th><th>Nombre</th><th>Var. 4 sem</th><th>Precio Actual</th><th>Precio 4 sem</th><th>Análisis Técnico</th>
</tr></thead><tbody>{rows}</tbody></table>
</div>"""

def report_top_performers_4days():
    candidates = list(dict.fromkeys(SP500[:200] + NASDAQ_100[:50]))
    data = _safe_get_data(candidates[:150], "1mo")
    
    performers = []
    for sym, hist in data.items():
        c = hist["Close"].values.astype(float)
        v = hist["Volume"].values.astype(float)
        if len(c) < 5: continue
        price = c[-1]; price_4d = c[-5]
        pct = ((price - price_4d) / price_4d) * 100
        rsi = _calc_rsi(c)
        vol_ratio = np.mean(v[-4:]) / max(np.mean(v[-20:]), 1)
        performers.append({"sym":sym,"price":price,"pct":pct,"rsi":rsi,"vol_ratio":vol_ratio})
    
    performers.sort(key=lambda x: x["pct"], reverse=True)
    
    rows = ""
    for i, p in enumerate(performers[:10]):
        name = _get_name(p["sym"])
        rows += f"""<tr><td>{i+1}</td><td><b>{p["sym"]}</b></td><td>{name}</td>
        <td class="up"><b>{p["pct"]:+.2f}%</b></td><td>${p["price"]:.2f}</td>
        <td>{p["vol_ratio"]:.1f}x</td><td>{_rsi_text(p["rsi"])}</td></tr>"""
    
    return f"""<div class="rpt-section">
<h2>🔥 2. Top 10 Activos — Mejor Desempeño Últimos 4 Días</h2>
<table class="rpt-table"><thead><tr>
<th>#</th><th>Ticker</th><th>Nombre</th><th>Var. 4 días</th><th>Precio</th><th>Volumen</th><th>RSI</th>
</tr></thead><tbody>{rows}</tbody></table>
</div>"""

def report_earnings_next_10days():
    return """<div class="rpt-section"><h2>📅 3. Earnings Próximos 10 Días</h2>
<p class="rpt-narrative">Desactivado temporalmente para optimizar velocidad del servidor.</p></div>"""

def _advanced_analysis(sym, hist):
    """
    Análisis avanzado con Python + estadística: regresión, Hurst, detección de patrones,
    soporte/resistencia dinámico, divergencias, predicción de tendencia.
    """
    c = hist["Close"].values.astype(float)
    h = hist["High"].values.astype(float)
    l = hist["Low"].values.astype(float)
    v = hist["Volume"].values.astype(float)
    n = len(c)
    price = c[-1]

    # ── 1. Regresión lineal para tendencia estadística ──
    x = np.arange(n)
    slope, intercept = np.polyfit(x[-20:], c[-20:], 1)
    slope_pct = (slope / (np.mean(c[-20:]) + 1e-10)) * 100
    r2 = np.corrcoef(x[-20:], c[-20:])[0,1]**2

    # ── 2. Exponente de Hurst (tendencia vs reversión) ──
    def hurst_exp(ts):
        lags = range(2, min(20, len(ts)//2))
        tau = [np.std(np.subtract(ts[lag:], ts[:-lag])) for lag in lags]
        if len(tau) < 3 or min(tau) <= 0: return 0.5
        try:
            reg = np.polyfit(np.log(list(lags)), np.log(tau), 1)
            return float(reg[0])
        except: return 0.5
    hurst = hurst_exp(c[-60:]) if n >= 60 else 0.5

    # ── 3. Volatilidad estadística (anualizada) ──
    returns = np.diff(np.log(c[-30:] + 1e-10)) if n >= 30 else np.diff(np.log(c + 1e-10))
    vol_ann = float(np.std(returns) * np.sqrt(252) * 100)

    # ── 4. Soporte y resistencia dinámicos (pivotes locales) ──
    def find_pivots(highs, lows, window=5):
        supports, resistances = [], []
        for i in range(window, len(highs) - window):
            if lows[i] == min(lows[i-window:i+window+1]):
                supports.append(lows[i])
            if highs[i] == max(highs[i-window:i+window+1]):
                resistances.append(highs[i])
        return sorted(set(round(x, 2) for x in supports))[-3:], \
               sorted(set(round(x, 2) for x in resistances))[:3]

    supports, resistances = find_pivots(h, l)
    nearest_sup = max((s for s in supports if s < price), default=None)
    nearest_res = min((r for r in resistances if r > price), default=None)

    # ── 5. Divergencia volumen-precio ──
    pct_5d = ((c[-1] - c[-5]) / c[-5] * 100) if n >= 5 else 0
    vol_5d_avg = np.mean(v[-5:]) if n >= 5 else np.mean(v)
    vol_20d_avg = np.mean(v[-20:]) if n >= 20 else np.mean(v)
    vol_ratio = vol_5d_avg / max(vol_20d_avg, 1)

    div_text = ""
    if pct_5d > 1 and vol_ratio < 0.7:
        div_text = "⚠️ Divergencia bajista: precio sube con volumen bajo (señal débil)"
    elif pct_5d < -1 and vol_ratio < 0.7:
        div_text = "⚠️ Divergencia alcista: precio cae con volumen bajo (posible agotamiento bajista)"
    elif pct_5d > 1 and vol_ratio > 1.3:
        div_text = "✅ Confirmación alcista: precio sube con volumen alto"
    elif pct_5d < -1 and vol_ratio > 1.3:
        div_text = "❌ Confirmación bajista: precio cae con volumen alto"

    # ── 6. Formaciones chartistas (Doble techo/suelo) ──
    pattern_text = ""
    if n >= 30:
        recent_highs = [h[i] for i in range(n-20, n) if h[i] == max(h[max(0,i-3):i+4])]
        recent_lows  = [l[i] for i in range(n-20, n) if l[i] == min(l[max(0,i-3):i+4])]
        if len(recent_highs) >= 2 and abs(recent_highs[-1] - recent_highs[-2]) / recent_highs[-2] < 0.02:
            pattern_text = "📊 Patrón: Doble techo detectado → posible reversión bajista"
        elif len(recent_lows) >= 2 and abs(recent_lows[-1] - recent_lows[-2]) / recent_lows[-2] < 0.02:
            pattern_text = "📊 Patrón: Doble suelo detectado → posible reversión alcista"

    # ── 7. Predicción de tendencia 4 días (regresión + Hurst) ──
    proj_price = price + slope * 4
    proj_pct = ((proj_price - price) / price) * 100
    if hurst > 0.6 and slope > 0:
        pred = f"📈 SUBIRÁ ~{proj_pct:+.1f}% (Hurst={hurst:.2f} indica tendencia persistente, R²={r2:.2f})"
    elif hurst > 0.6 and slope < 0:
        pred = f"📉 BAJARÁ ~{proj_pct:+.1f}% (Hurst={hurst:.2f} indica tendencia persistente, R²={r2:.2f})"
    elif hurst < 0.4:
        pred = f"↔️ REVERSIÓN PROBABLE (Hurst={hurst:.2f} indica mercado mean-reverting)"
    else:
        pred = f"⚖️ INDECISIÓN (Hurst={hurst:.2f} aleatorio, tendencia lineal: {proj_pct:+.1f}%)"

    parts = [pred]
    if nearest_sup: parts.append(f"Soporte clave: ${nearest_sup}")
    if nearest_res: parts.append(f"Resistencia clave: ${nearest_res}")
    if div_text: parts.append(div_text)
    if pattern_text: parts.append(pattern_text)
    parts.append(f"Volatilidad anualizada: {vol_ann:.1f}% | Vol. relativo: {vol_ratio:.1f}x")

    return " | ".join(parts)


def report_likely_up_this_week():
    data = _safe_get_data(SP500[:150], "3mo")
    bullish = []
    for sym, hist in data.items():
        c = hist["Close"].values.astype(float)
        h = hist["High"].values.astype(float)
        l = hist["Low"].values.astype(float)
        v = hist["Volume"].values.astype(float)
        if len(c) < 50: continue
        price = c[-1]
        emas = _calc_emas(c)
        rsi = _calc_rsi(c)
        pct_5d = ((c[-1]-c[-5])/c[-5])*100 if len(c)>=5 else 0

        # Regresión + Hurst para filtrar solo tendencias reales
        x = np.arange(min(20, len(c)))
        slope, _ = np.polyfit(x, c[-len(x):], 1)
        slope_pct = (slope / (np.mean(c[-20:]) + 1e-10)) * 100

        vol_ratio = np.mean(v[-5:]) / max(np.mean(v[-20:]), 1)

        # Criterio estricto: alineación EMA + RSI sano + pendiente positiva + volumen
        if (price > emas["ema9"] > emas["ema21"] and
                40 < rsi < 68 and
                slope_pct > 0.05 and
                vol_ratio > 0.8):
            analysis = _advanced_analysis(sym, hist)
            bullish.append({"sym":sym,"price":price,"rsi":rsi,"pct_5d":pct_5d,
                            "slope_pct":slope_pct,"vol_ratio":vol_ratio,"analysis":analysis})

    bullish.sort(key=lambda x: x["slope_pct"], reverse=True)
    rows = "".join(f"""<tr><td><b>{p["sym"]}</b></td><td>{_get_name(p["sym"])}</td>
        <td>${p["price"]:.2f}</td><td>{_rsi_text(p["rsi"])}</td>
        <td class="up">{p["pct_5d"]:+.2f}%</td>
        <td style="font-size:10px;max-width:300px">{p["analysis"]}</td></tr>""" for p in bullish[:15])

    return f"""<div class="rpt-section"><h2>🟢 4. Acciones que Pueden SUBIR Esta Semana — Análisis IA + Estadística</h2>
<table class="rpt-table"><thead><tr><th>Ticker</th><th>Nombre</th><th>Precio</th><th>RSI</th><th>Var. 5d</th><th>Análisis Avanzado</th></tr></thead><tbody>{rows}</tbody></table></div>"""


def report_likely_down_this_week():
    data = _safe_get_data(SP500[:150], "3mo")
    bearish = []
    for sym, hist in data.items():
        c = hist["Close"].values.astype(float)
        v = hist["Volume"].values.astype(float)
        if len(c) < 50: continue
        price = c[-1]
        emas = _calc_emas(c)
        rsi = _calc_rsi(c)
        pct_5d = ((c[-1]-c[-5])/c[-5])*100 if len(c)>=5 else 0

        x = np.arange(min(20, len(c)))
        slope, _ = np.polyfit(x, c[-len(x):], 1)
        slope_pct = (slope / (np.mean(c[-20:]) + 1e-10)) * 100
        vol_ratio = np.mean(v[-5:]) / max(np.mean(v[-20:]), 1)

        if (price < emas["ema9"] < emas["ema21"] and
                rsi < 50 and
                slope_pct < -0.05):
            analysis = _advanced_analysis(sym, hist)
            bearish.append({"sym":sym,"price":price,"rsi":rsi,"pct_5d":pct_5d,
                            "slope_pct":slope_pct,"vol_ratio":vol_ratio,"analysis":analysis})

    bearish.sort(key=lambda x: x["slope_pct"])
    rows = "".join(f"""<tr><td><b>{p["sym"]}</b></td><td>{_get_name(p["sym"])}</td>
        <td>${p["price"]:.2f}</td><td>{_rsi_text(p["rsi"])}</td>
        <td class="down">{p["pct_5d"]:+.2f}%</td>
        <td style="font-size:10px;max-width:300px">{p["analysis"]}</td></tr>""" for p in bearish[:15])

    return f"""<div class="rpt-section"><h2>🔴 5. Acciones que Pueden BAJAR Esta Semana — Análisis IA + Estadística</h2>
<table class="rpt-table"><thead><tr><th>Ticker</th><th>Nombre</th><th>Precio</th><th>RSI</th><th>Var. 5d</th><th>Análisis Avanzado</th></tr></thead><tbody>{rows}</tbody></table></div>"""


def report_4day_outlook():
    indices = {"^GSPC":"S&P 500","^DJI":"Dow Jones","^IXIC":"NASDAQ","^RUT":"Russell 2000"}
    data = _safe_get_data(list(indices.keys()), "6mo")

    from nau_quantum_engine import NAUQuantumAlphaIndicator
    local_ind = NAUQuantumAlphaIndicator()

    rows = ""
    for sym, name in indices.items():
        if sym not in data: continue
        hist = data[sym]
        if len(hist) < 50: continue

        try:
            df_ia = local_ind.compute(hist.copy())
            last_ia = df_ia.iloc[-1]
        except: continue

        c = hist["Close"].values.astype(float)
        price = c[-1]
        pct_5d = ((c[-1]-c[-5])/c[-5])*100 if len(c)>=5 else 0

        sig = float(last_ia.get("NAU_Signal", 0))
        conf = float(last_ia.get("NAU_Confidence", 0)) * 100
        hurst_score = float(last_ia.get("NAU_Hurst_Score", 0))

        # Análisis estadístico avanzado
        adv = _advanced_analysis(sym, hist)

        if sig > 15 and conf > 50:
            pred_dir = "📈 SUBIRÁ (Próximos 4 días)"
        elif sig < -15 and conf > 50:
            pred_dir = "📉 BAJARÁ (Próximos 4 días)"
        else:
            pred_dir = "⚖️ LATERAL / INDECISIÓN"

        rows += f"""<tr><td><b>{sym}</b></td><td>{name}</td><td>${price:,.2f}</td>
        <td class="{"up" if pct_5d>0 else "down"}">{pct_5d:+.2f}%</td>
        <td><b>{pred_dir}</b></td>
        <td style="font-size:10px;max-width:280px">{adv}</td></tr>"""

    return f"""<div class="rpt-section">
<h2>🔮 6. Predicción con IA + Estadística — Perspectiva Próximos 4 Días</h2>
<table class="rpt-table"><thead><tr><th>Índice</th><th>Nombre</th><th>Precio</th><th>Var. 5d</th><th>Predicción IA</th><th>Sustento Estadístico</th></tr></thead><tbody>{rows}</tbody></table></div>"""


def report_fibonacci_fallen(interval="1d"):
    candidates = list(dict.fromkeys(SP500[:80]))
    data = _safe_get_data(candidates, "6mo")

    from nau_quantum_engine import NAUQuantumAlphaIndicator
    local_ind = NAUQuantumAlphaIndicator()

    fallen = []
    for sym, hist in data.items():
        if len(hist) < 60: continue

        c = hist["Close"].values.astype(float)
        h = hist["High"].values.astype(float)
        l = hist["Low"].values.astype(float)
        high = float(np.max(c[-120:] if len(c)>=120 else c))
        low  = float(np.min(c[-120:] if len(c)>=120 else c))
        price = c[-1]
        drop = ((price - high) / high) * 100

        if drop < -12:
            diff = high - low
            fib_levels = {
                "23.6%": round(high - diff*0.236, 2),
                "38.2%": round(high - diff*0.382, 2),
                "50.0%": round(high - diff*0.500, 2),
                "61.8%": round(high - diff*0.618, 2),
                "78.6%": round(high - diff*0.786, 2),
            }
            # Nivel Fibonacci más cercano al precio actual
            nearest_fib = min(fib_levels.items(), key=lambda x: abs(x[1] - price))
            dist_fib = ((price - nearest_fib[1]) / nearest_fib[1]) * 100

            try:
                df_ia = local_ind.compute(hist.copy())
                last_ia = df_ia.iloc[-1]
                sig = float(last_ia.get("NAU_Signal", 0))
                conf = float(last_ia.get("NAU_Confidence", 0)) * 100
            except:
                sig, conf = 0, 0

            # Análisis estadístico avanzado
            x = np.arange(min(10, len(c)))
            slope, _ = np.polyfit(x, c[-len(x):], 1)
            rsi = _calc_rsi(c)

            # Predicción combinada IA + Fibonacci + Estadística
            at_support = abs(dist_fib) < 2.5  # Cerca del nivel Fib
            if sig > 15 and at_support and rsi < 40:
                pred = "🟢 REBOTE PROBABLE: Soporte Fib + señal IA alcista + RSI sobreventa"
                cambio_tend = "SÍ — Posible cambio de tendencia a alcista"
            elif sig > 15 and slope > 0:
                pred = f"🟡 REBOTE POSIBLE: Momentum IA positivo pero sin soporte Fib confirmado"
                cambio_tend = "PARCIAL — Necesita confirmar quiebre"
            elif sig < -15:
                pred = "🔴 CONTINUACIÓN BAJISTA: IA detecta presión vendedora persistente"
                cambio_tend = "NO — Tendencia bajista continúa"
            elif at_support:
                pred = f"🟡 EN SOPORTE Fib {nearest_fib[0]}: Zona de decisión crítica"
                cambio_tend = "INDEFINIDO — Esperar confirmación"
            else:
                pred = f"⚪ Sin señal clara. Próximo soporte: {nearest_fib[0]} = ${nearest_fib[1]}"
                cambio_tend = "NO DETERMINADO"

            fib_str = " | ".join(f"{k}=${v}" for k,v in fib_levels.items())
            fallen.append({
                "sym": sym, "price": price, "drop": drop,
                "fib_nearest": f"{nearest_fib[0]}=${nearest_fib[1]}",
                "fib_all": fib_str,
                "pred": pred,
                "cambio": cambio_tend,
                "rsi": rsi,
                "sig": sig,
            })

    fallen.sort(key=lambda x: x["drop"])
    rows = "".join(f"""<tr>
        <td><b>{p["sym"]}</b></td>
        <td>${p["price"]:.2f}</td>
        <td class="down"><b>{p["drop"]:.1f}%</b></td>
        <td style="font-size:10px">{p["fib_nearest"]}</td>
        <td>{_rsi_text(p["rsi"])}</td>
        <td style="font-size:10px"><b>{p["pred"]}</b></td>
        <td style="font-size:10px;color:{'#26a69a' if 'SÍ' in p['cambio'] else '#ef5350' if 'NO —' in p['cambio'] else '#ff9800'}">{p["cambio"]}</td>
    </tr>""" for p in fallen[:15])

    return f"""<div class="rpt-section">
<h2>📉 11. Fibonacci Predictivo + IA — Cambio de Tendencia</h2>
<p class="rpt-narrative">Análisis combinado: niveles Fibonacci 6 meses + señal NAU Quantum + RSI + regresión estadística para predecir si habrá cambio de tendencia.</p>
<table class="rpt-table"><thead><tr>
<th>Ticker</th><th>Precio</th><th>Caída</th><th>Fib más cercano</th><th>RSI</th><th>Predicción IA</th><th>Cambio Tendencia</th>
</tr></thead><tbody>{rows}</tbody></table></div>"""

@app.get("/api/chart")
def get_chart(symbol: str = Query("AAPL"), interval: str = Query("1d"), prepost: bool = Query(False)):
    try:
        return download_and_compute(symbol.upper().strip(), interval, prepost)
    except Exception as e:
        return {"error": f"Server error: {str(e)}"}

@app.get("/api/search")
def search_symbols(q: str = Query("")):
    if len(q) < 1:
        return {"results": SYMBOLS_DB[:20]}
    ql = q.lower()
    local = [s for s in SYMBOLS_DB if ql in s["s"].lower() or ql in s["n"].lower()]
    if local:
        return {"results": local[:20]}
    try:
        ticker = yf.Ticker(q.upper())
        info = ticker.fast_info
        if hasattr(info, 'last_price') and info.last_price:
            try:
                full_info = ticker.info
                name = full_info.get("shortName", q.upper())
                sector = full_info.get("sector", "Unknown")
            except:
                name, sector = q.upper(), "Unknown"
            return {"results": [{"s": q.upper(), "n": name, "sec": sector}]}
    except:
        pass
    return {"results": []}

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "5.4"}

@app.get("/")
def root():
    if os.path.exists("/app/static/index.html"):
        return FileResponse("/app/static/index.html")
    return {"message": "NAU Quantum API", "docs": "/docs"}

if os.path.exists("/app/static"):
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000, workers=8)
