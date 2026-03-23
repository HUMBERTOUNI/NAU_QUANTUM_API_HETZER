"""
NAU Quantum v5.4 "Sentinel Quantum Edge" — FastAPI Backend
FIXED SCANNER: scan_fast() downloads only 200 bars per stock (not 5 years)
Peru timezone: UTC-5 applied to all timestamps
"""
from fastapi import FastAPI, Query, BackgroundTasks
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
    SCAN_UNIVERSE, INDEX_MEMBERSHIP, SYMBOLS_DB, filter_universe,
    SP500, NASDAQ_100, DOW_30, RUSSELL_2000_TOP
)

app = FastAPI(title="NAU Quantum v5.4 — Sentinel Quantum Edge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CACHE = {}
CACHE_TTL = 180
SCAN_CACHE = {}  # Separate cache for scan results
PREV_CLOSE_CACHE = {}

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

# SCAN uses SHORT periods for speed
SCAN_PERIOD_MAP = {
    "1m":"2d","5m":"10d","15m":"15d","30m":"20d",
    "1h":"1mo","2h":"3mo","4h":"3mo",
    "1d":"1y","1wk":"2y","1mo":"5y","3mo":"5y","6mo":"5y","1y":"10y",
}

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

import threading

# yfinance is NOT thread-safe — downloads must be serialized
_download_lock = threading.Lock()

def safe_download(sym, period, interval, prepost=False):
    with _download_lock:
        try:
            raw = yf.download(sym, period=period, interval=interval, prepost=prepost, auto_adjust=True, progress=False)
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
        if isinstance(s, pd.DataFrame): s = s.iloc[:,0]
        df[col] = pd.to_numeric(s, errors='coerce')
    df['Volume'] = df['Volume'].fillna(0)
    df = df.dropna(subset=['Open','High','Low','Close'])
    return df, None

def get_prev_close(sym):
    ck = f"pc:{sym}"
    if ck in PREV_CLOSE_CACHE and time.time() - PREV_CLOSE_CACHE[ck][1] < 3600:
        return PREV_CLOSE_CACHE[ck][0]
    try:
        with _download_lock:
            t = yf.Ticker(sym)
            info = t.fast_info
            pc = float(info.get("previousClose", 0) or info.get("regularMarketPreviousClose", 0))
        if pc > 0:
            PREV_CLOSE_CACHE[ck] = (pc, time.time())
            return pc
    except:
        pass
    return 0

# Peru timezone offset: UTC-5 = -18000 seconds
PERU_OFFSET = -5 * 3600

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
        # Align intraday resamples with NYSE open (9:30 AM ET)
        # During DST (Mar-Nov): ET=UTC-4, open=13:30 UTC
        # During EST (Nov-Mar): ET=UTC-5, open=14:30 UTC
        # Auto-detect: check if US is in DST right now
        from datetime import datetime
        import calendar
        now = datetime.utcnow()
        # US DST: 2nd Sunday March to 1st Sunday November
        mar_second_sun = 14 - calendar.weekday(now.year, 3, 1) % 7 + 7
        nov_first_sun = 7 - calendar.weekday(now.year, 11, 1) % 7
        is_dst = (datetime(now.year, 3, mar_second_sun, 7) <= now < datetime(now.year, 11, nov_first_sun, 6))
        nyse_open_utc_min = 13*60+30 if is_dst else 14*60+30  # minutes from midnight UTC
        
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
    # Peru = UTC-5 always (no DST in Peru)
    PERU_OFFSET_SEC = -5 * 3600
    
    for idx, row in df.iterrows():
        # Convert UTC timestamp to Peru time for display (LWC v4 shows UTC)
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
        if row.get("NAU_Long", False):
            signals.append({"time":ts,"type":"LONG","price":bar["close"],
                           "confidence":round(float(row["NAU_Confidence"])*100,1),
                           "signal_score":round(float(row["NAU_Signal"]),1),
                           "label":signal_label(row["NAU_Signal"], row["NAU_Confidence"])})
        if row.get("NAU_Short", False):
            signals.append({"time":ts,"type":"SHORT","price":bar["close"],
                           "confidence":round(float(row["NAU_Confidence"])*100,1),
                           "signal_score":round(float(row["NAU_Signal"]),1),
                           "label":signal_label(row["NAU_Signal"], row["NAU_Confidence"])})

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


# ══════════════════════════════════════════════════════════════
# FAST SCANNER — downloads only what's needed, no full bar construction
# ══════════════════════════════════════════════════════════════

def scan_fast(sym, interval):
    """Thread-safe scan: creates own indicator instance, downloads SHORT period."""
    try:
        yf_interval_map = {"1m":"1m","5m":"5m","15m":"15m","30m":"30m","1h":"1h",
                           "2h":"1h","4h":"1h","1d":"1d","1wk":"1wk","1mo":"1mo",
                           "3mo":"3mo","6mo":"1mo","1y":"3mo"}
        yf_interval = yf_interval_map.get(interval, "1d")
        scan_period = SCAN_PERIOD_MAP.get(interval, "1y")

        df, err = safe_download(sym, scan_period, yf_interval, False)
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

        if len(df) < 50:
            return None

        # CRITICAL: Create a NEW indicator instance for thread safety
        local_indicator = NAUQuantumAlphaIndicator()
        df = local_indicator.compute(df)
        last = df.iloc[-1]

        sig_val = float(last["NAU_Signal"])
        conf_val = float(last["NAU_Confidence"])
        conf_pct = conf_val * 100 if conf_val <= 1 else conf_val
        label = signal_label(sig_val, conf_pct)
        price = float(last["Close"])
        regime = {0:"BULL",1:"BEAR",2:"RANGE"}.get(int(last["NAU_Regime"]), "?")

        # Calculate ATR for SL/TP
        highs = df["High"].iloc[-14:].values.astype(float)
        lows = df["Low"].iloc[-14:].values.astype(float)
        atr = float(np.mean(highs - lows))

        # Get top factors
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


def scan_one(sym_info, interval, min_conf):
    """Scan one stock. Returns formatted result or None."""
    sym = sym_info["s"]
    try:
        result = scan_fast(sym, interval)
        if result is None:
            return None

        conf = result["confidence"]
        sig = result["signal"]
        label = result["label"]

        if conf < min_conf or abs(sig) < 15 or label == "NEUTRAL":
            return None

        price = result["price"]
        atr = result["atr"]
        idx_label = " · ".join(sorted(INDEX_MEMBERSHIP.get(sym, {"OTHER"})))

        if label in ("COMPRA FUERTE", "COMPRA"):
            entry, sl = price, round(price - 1.5 * atr, 2)
            tp1, tp2 = round(price + 2 * atr, 2), round(price + 3 * atr, 2)
        else:
            entry, sl = price, round(price + 1.5 * atr, 2)
            tp1, tp2 = round(price - 2 * atr, 2), round(price - 3 * atr, 2)

        factors = result.get("factors", {})
        top5 = sorted(factors.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        reasoning = f"{label} | {result['regime']} | " + ", ".join(f"{k}:{v:+.0f}" for k, v in top5)

        return {
            "symbol": sym, "index": idx_label,
            "signal": sig, "confidence": conf,
            "regime": result["regime"], "label": label,
            "direction": "LONG" if sig > 0 else "SHORT",
            "price": price, "entry": round(entry, 2),
            "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": 0,
            "reasoning": reasoning,
            "score": round(abs(sig) * (conf / 100), 1),
        }
    except Exception:
        return None


@app.get("/api/scan")
def scan_stocks(interval: str = Query("1d"), min_confidence: float = Query(55), index: str = Query("ALL")):
    """Professional parallel scanner. Always returns valid JSON."""
    try:
        universe = filter_universe(index)
        # Limit to keep scan time reasonable (~3s per stock serialized)
        max_map = {"ALL": 100, "S&P500": 100, "NASDAQ100": 103, "DOW30": 31,
                   "RUSSELL2000": 100, "MIDCAP400": 100, "GROWTH": 100,
                   "ETF": 37, "CRYPTO": 12, "INDEX": 6, "COMM/FX": 8}
        max_stocks = max_map.get(index, 100)
        universe = universe[:max_stocks]
        
        t0 = time.time()
        results = []
        errors = 0

        # 4 workers — downloads are serialized for data integrity
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_map = {executor.submit(scan_one, si, interval, min_confidence): si for si in universe}
            for future in as_completed(future_map):
                try:
                    r = future.result()
                    if r is not None:
                        results.append(r)
                except Exception:
                    errors += 1

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return {
            "scan_results": results[:50],
            "total_scanned": len(universe),
            "total_found": len(results),
            "errors": errors,
            "scan_time": round(time.time() - t0, 1),
            "interval": interval,
            "index_filter": index,
            "timestamp": int(time.time()),
        }
    except Exception as e:
        return {
            "scan_results": [], "total_scanned": 0, "total_found": 0,
            "errors": 1, "scan_time": 0, "error": str(e),
            "interval": interval, "index_filter": index,
            "timestamp": int(time.time()),
        }


# ═══ OTHER ENDPOINTS ═══

# Feature 4: Consecutive Signal Scanner (Señal V/C)
def scan_vc_one(sym_info, interval):
    """
    Find stocks where the ONLY 2 consecutive signals are the most recent ones.
    
    Algorithm:
    1. Get signals for last 20 completed candles
    2. Scan from most recent backward to find the first pair of consecutive BUY or SELL
    3. Check ALL candles before that pair — if ANY has the same signal type → REJECT
    4. This ensures we catch ONLY the start of a new trend
    """
    sym = sym_info["s"]
    try:
        yf_interval_map = {"1m":"1m","5m":"5m","15m":"15m","30m":"30m","1h":"1h",
                           "2h":"1h","4h":"1h","1d":"1d","1wk":"1wk","1mo":"1mo",
                           "3mo":"3mo","6mo":"1mo","1y":"3mo"}
        yf_int = yf_interval_map.get(interval, "1d")
        scan_period = SCAN_PERIOD_MAP.get(interval, "1y")
        
        df, err = safe_download(sym, scan_period, yf_int, False)
        if err or df is None or df.empty or len(df) < 50:
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
        
        if len(df) < 50:
            return None
        
        local_ind = NAUQuantumAlphaIndicator()
        df = local_ind.compute(df)
        
        if len(df) < 10:
            return None
        
        # Apply the SAME signal gap filter as the chart display
        # The chart shows arrows only with minimum time gap between them
        gap_map = {"1m":120,"5m":600,"15m":1800,"30m":3600,"1h":7200,
                   "2h":14400,"4h":28800,"1d":172800,"1wk":604800,"1mo":2592000}
        min_gap = gap_map.get(interval, 7200)
        
        completed = df.iloc[:-1]  # Exclude current forming candle
        
        # Build signal list WITH gap filter (exactly like chart markers)
        all_signals = []  # list of "LONG", "SHORT", or "NONE"
        last_signal_time = 0
        
        for idx_ts, row in completed.iterrows():
            try: ts = int(idx_ts.timestamp())
            except: ts = 0
            
            has_long = bool(row.get("NAU_Long", False))
            has_short = bool(row.get("NAU_Short", False))
            
            if (has_long or has_short) and (ts - last_signal_time >= min_gap):
                if has_long:
                    all_signals.append("LONG")
                else:
                    all_signals.append("SHORT")
                last_signal_time = ts
            else:
                all_signals.append("NONE")
        
        if len(all_signals) < 3:
            return None
        
        # Step 1: The 2 most recent signals (not bars!) must be consecutive and same direction
        # Find the last 2 actual signals from the end
        signal_positions = [(i, s) for i, s in enumerate(all_signals) if s != "NONE"]
        
        if len(signal_positions) < 2:
            return None
        
        last_sig_pos, last_sig = signal_positions[-1]
        prev_sig_pos, prev_sig = signal_positions[-2]
        
        # Both must be same direction
        if last_sig != prev_sig:
            return None
        
        is_buy = last_sig == "LONG"
        
        # Step 2: These must be the ONLY 2 signals — no prior signals of ANY type
        if len(signal_positions) > 2:
            return None  # More than 2 signals exist = not a new trend
        
        # Step 3: The signals must be RECENT (within the last 8 bars)
        if last_sig_pos < len(all_signals) - 8:
            return None  # Signal too old, not recent
        
        # Get the label for display
        sig_val = float(df.iloc[-2]["NAU_Signal"])
        conf_val = float(df.iloc[-2]["NAU_Confidence"])
        label = signal_label(sig_val, conf_val)
        
        # MATCH: These are the FIRST 2 consecutive signals of this type = new trend start
        current = df.iloc[-1]
        price = float(current["Close"])
        atr = float(np.mean(df["High"].iloc[-14:].values.astype(float) - df["Low"].iloc[-14:].values.astype(float)))
        
        if is_buy:
            entry, sl = price, round(price - 1.5*atr, 2)
            tp1, tp2, tp3 = round(price + 2*atr, 2), round(price + 3*atr, 2), round(price + 4.5*atr, 2)
        else:
            entry, sl = price, round(price + 1.5*atr, 2)
            tp1, tp2, tp3 = round(price - 2*atr, 2), round(price - 3*atr, 2), round(price - 4.5*atr, 2)
        
        name = sym
        for s in SYMBOLS_DB:
            if s["s"] == sym:
                name = s["n"]
                break
        
        return {
            "symbol": sym, "name": name, "label": label,
            "direction": "LONG" if is_buy else "SHORT",
            "consecutive": 2, "price": round(price, 2),
            "entry": round(entry, 2), "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        }
    except Exception:
        return None


@app.get("/api/scan_vc")
def scan_vc(interval: str = Query("1d"), page: int = Query(1)):
    """
    Find stocks with 2+ consecutive buy/sell signals.
    Pages organized by importance:
    1 = S&P500 + NASDAQ100 + DOW30 (top ~500)
    2 = Russell 2000 top + MidCap 400 (~400)
    3 = Growth/Value stocks (~500)
    4 = ETFs + Crypto + remaining (~200)
    """
    try:
        from stock_universe import SP500, NASDAQ_100, DOW_30, RUSSELL_2000_TOP, SP_MIDCAP_400, ADDITIONAL_STOCKS, ETFS, CRYPTO, INDICES, COMMODITIES_FOREX
        
        # Build curated pages by investment quality
        # Tanda 1: Top 200 large-cap + 300 innovative leaders
        # Tanda 2: Mid-cap with upside (Russell + MidCap)  
        # Tanda 3: Growth/Value with high potential
        # Tanda 4: ETFs + Crypto + Indices + remaining
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
        results = []
        errors = 0
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_map = {executor.submit(scan_vc_one, si, interval): si for si in universe}
            for future in as_completed(future_map):
                try:
                    r = future.result()
                    if r is not None:
                        results.append(r)
                except Exception:
                    errors += 1
        
        results.sort(key=lambda x: x.get("consecutive", 0), reverse=True)
        return {
            "results": results,
            "total_scanned": len(universe),
            "scan_time": round(time.time() - t0, 1),
            "interval": interval,
            "page": page,
            "total_pages": total_pages,
            "total_universe": len(SCAN_UNIVERSE),
            "timestamp": int(time.time()),
        }
    except Exception as e:
        return {"results": [], "total_scanned": 0, "scan_time": 0, "error": str(e),
                "page": page, "total_pages": 0}


@app.get("/api/report")
def generate_report(section: str = Query("all")):
    """Generate market report. Uses Gemini AI for analysis when available."""
    try:
        t0 = time.time()
        html_parts = []
        
        sections_to_run = list(range(1, 12)) if section == "all" else [int(section)]
        
        for sec in sections_to_run:
            try:
                if sec == 1:
                    html_parts.append(report_top_performers_4weeks())
                elif sec == 2:
                    html_parts.append(report_top_performers_4days())
                elif sec == 3:
                    html_parts.append(report_earnings_next_10days())
                elif sec == 4:
                    html_parts.append(report_likely_up_this_week())
                elif sec == 5:
                    html_parts.append(report_likely_down_this_week())
                elif sec == 6:
                    html_parts.append(report_4day_outlook())
                elif sec == 7:
                    html_parts.append(report_sector_news())
                elif sec == 8:
                    html_parts.append(report_market_today())
                elif sec == 9:
                    html_parts.append(report_ai_tech_news())
                elif sec == 10:
                    html_parts.append(report_ema200_stocks())
                elif sec == 11:
                    html_parts.append(report_fibonacci_fallen())
            except Exception as e:
                html_parts.append(f'<div class="rpt-section"><h2>Sección {sec} — Error</h2><p>{str(e)}</p></div>')
        
        # Try to enhance with Gemini AI analysis
        gemini_analysis = ""
        try:
            gemini_analysis = _gemini_enhance(sections_to_run, html_parts)
        except:
            pass
        
        final_html = "\n".join(html_parts)
        if gemini_analysis:
            final_html += gemini_analysis
        
        return {
            "html": final_html,
            "generation_time": round(time.time() - t0, 1),
            "sections": sections_to_run,
            "ai_enhanced": bool(gemini_analysis),
        }
    except Exception as e:
        return {"error": str(e), "html": ""}


def _gemini_enhance(sections, html_parts):
    """Use Gemini AI to add deep analysis to the report."""
    import urllib.request, json
    GEMINI_KEY = "AIzaSyDzjpolj7IDRBaLOuFXZBv4aRaxlBeNHF0"
    
    # Extract key data points from HTML for Gemini to analyze
    summary = "Basándote en los siguientes datos del mercado de hoy, proporciona un análisis profesional en español:\n\n"
    for i, html in enumerate(html_parts):
        # Extract text from HTML (strip tags roughly)
        import re
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        summary += f"SECCIÓN {sections[i]}: {text[:800]}\n\n"
    
    summary += """
Instrucciones:
1. Genera un ANÁLISIS EJECUTIVO PROFESIONAL del mercado (en español)
2. Incluye: tendencia general, sectores fuertes/débiles, riesgos principales, oportunidades
3. Menciona niveles técnicos clave del S&P 500
4. Da una perspectiva para los próximos 2-4 días
5. Formato HTML con <h2>, <h3>, <p>, <b>, <ul><li>
6. Máximo 500 palabras
"""
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": summary}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2000}
        }).encode()
        
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        
        ai_text = data["candidates"][0]["content"]["parts"][0]["text"]
        
        return f"""<div class="rpt-section" style="border-left-color:#ff6b35">
<h2>🧠 Análisis AI — Gemini</h2>
<div class="rpt-narrative">{ai_text}</div>
<p class="rpt-footer">Análisis generado por Google Gemini AI basado en datos de Yahoo Finance</p></div>"""
    except Exception as e:
        return f"""<div class="rpt-section" style="border-left-color:#ff6b35">
<h2>🧠 Análisis AI</h2>
<p class="rpt-narrative" style="color:#ff9800">Gemini AI no disponible: {str(e)[:100]}</p></div>"""


# ═══ REPORT HELPER FUNCTIONS (Professional) ═══

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

def _safe_get_data(symbols, period="1mo"):
    """Get price data for a list of symbols."""
    results = {}
    for sym in symbols:
        try:
            with _download_lock:
                hist = yf.download(sym, period=period, interval="1d", progress=False, auto_adjust=True)
            if hist is not None and not hist.empty and len(hist) >= 2:
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = hist.columns.get_level_values(0)
                results[sym] = hist
        except:
            pass
    return results

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
        ema_analysis = ""
        if p["emas"]["ema50"]:
            if p["price"] > p["emas"]["ema50"] > p["emas"]["ema200"] if p["emas"]["ema200"] else True:
                ema_analysis = "Precio sobre EMAs — estructura alcista"
            else:
                ema_analysis = "Precio bajo EMAs — precaución"
        
        analysis = f'{_trend_text(p["pct"])} | {_rsi_text(p["rsi"])} | Vol: {p["vol_ratio"]:.1f}x promedio'
        if p["rsi"] > 70: analysis += ' | ⚠️ Riesgo de corrección por sobrecompra'
        if p["vol_ratio"] > 1.5: analysis += ' | ✅ Volumen confirma movimiento'
        
        rows += f"""<tr><td>{i+1}</td><td><b>{p["sym"]}</b></td><td>{name}</td>
        <td class="{cls}"><b>{p["pct"]:+.2f}%</b></td><td>${p["price"]:.2f}</td><td>${p["price_4wk"]:.2f}</td>
        <td style="font-size:11px">{analysis}</td></tr>"""
    
    return REPORT_CSS + f"""<div class="rpt-section">
<h2>📈 1. Top 20 Acciones — Mejor Rendimiento Últimas 4 Semanas</h2>
<p class="rpt-narrative">Análisis de las {len(performers)} acciones más importantes del mercado estadounidense (S&P 500 + NASDAQ 100).
Se identificaron las 20 con mayor incremento porcentual en las últimas 20 sesiones bursátiles.
El análisis incluye evaluación técnica de RSI, volumen relativo y posición respecto a medias móviles.</p>
<table class="rpt-table"><thead><tr>
<th>#</th><th>Ticker</th><th>Nombre</th><th>Var. 4 sem</th><th>Precio Actual</th><th>Precio 4 sem</th><th>Análisis Técnico</th>
</tr></thead><tbody>{rows}</tbody></table>
<p class="rpt-footer">Fuente: Yahoo Finance | {len(performers)} acciones analizadas | Periodo: 20 sesiones</p>
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
        vol_4d = np.mean(v[-4:]); vol_20d = np.mean(v[-20:])
        vol_ratio = vol_4d / max(vol_20d, 1)
        performers.append({"sym":sym,"price":price,"pct":pct,"rsi":rsi,"vol_ratio":vol_ratio,"vol_4d":vol_4d})
    
    performers.sort(key=lambda x: x["pct"], reverse=True)
    top = performers[:10]
    
    rows = ""
    for i, p in enumerate(top):
        name = _get_name(p["sym"])
        vol_analysis = "✅ Volumen confirma" if p["vol_ratio"] > 1.3 else ("⚠️ Volumen débil" if p["vol_ratio"] < 0.8 else "Volumen normal")
        rsi_note = "⚠️ SOBRECOMPRA" if p["rsi"] > 70 else ("Momentum fuerte" if p["rsi"] > 55 else "Neutral")
        continuity = "ALTA" if p["vol_ratio"] > 1.3 and p["rsi"] < 70 else ("MEDIA" if p["rsi"] < 75 else "BAJA — riesgo corrección")
        
        rows += f"""<tr><td>{i+1}</td><td><b>{p["sym"]}</b></td><td>{name}</td>
        <td class="up"><b>{p["pct"]:+.2f}%</b></td><td>${p["price"]:.2f}</td>
        <td>{p["vol_ratio"]:.1f}x — {vol_analysis}</td><td>{_rsi_text(p["rsi"])}</td>
        <td>{continuity}</td></tr>"""
    
    return f"""<div class="rpt-section">
<h2>🔥 2. Top 10 Activos — Mejor Desempeño Últimos 4 Días</h2>
<p class="rpt-narrative">Identificación de los 10 activos con mayor apreciación en las últimas 4 sesiones bursátiles.
El análisis de volumen compara el promedio de 4 días contra el promedio de 20 días para validar la fortaleza del movimiento.
Un ratio de volumen superior a 1.3x confirma interés institucional; inferior a 0.8x sugiere movimiento frágil.</p>
<table class="rpt-table"><thead><tr>
<th>#</th><th>Ticker</th><th>Nombre</th><th>Var. 4 días</th><th>Precio</th><th>Volumen</th><th>RSI</th><th>Prob. Continuidad</th>
</tr></thead><tbody>{rows}</tbody></table>
<p class="rpt-footer">Fuente: Yahoo Finance | Periodo: 4 sesiones | Ratio volumen = Vol 4d / Vol 20d</p>
</div>"""


def report_earnings_next_10days():
    earnings = []
    for sym in SP500[:80]:
        try:
            with _download_lock:
                t = yf.Ticker(sym)
                cal = t.calendar
            if cal is not None and not cal.empty:
                if 'Earnings Date' in cal.index:
                    ed = cal.loc['Earnings Date']
                    if hasattr(ed, 'iloc'): ed = ed.iloc[0]
                    earnings.append({"sym":sym,"date":str(ed),"name":_get_name(sym)})
        except:
            pass
    
    if not earnings:
        return """<div class="rpt-section"><h2>📅 3. Earnings Próximos 10 Días</h2>
<p class="rpt-narrative">No se encontraron datos de earnings en Yahoo Finance para el periodo consultado.
Las fechas de publicación de resultados financieros suelen actualizarse 2-3 semanas antes del evento.</p></div>"""
    
    rows = "".join(f'<tr><td><b>{e["sym"]}</b></td><td>{e["name"]}</td><td>{e["date"]}</td></tr>' for e in earnings[:25])
    
    return f"""<div class="rpt-section">
<h2>📅 3. Earnings — Publicación de Resultados Próximos 10 Días</h2>
<p class="rpt-narrative">Las siguientes empresas tienen programada la publicación de sus resultados financieros trimestrales.
Los earnings son catalizadores clave que pueden generar movimientos de ±5-15% en una sola sesión.
Se recomienda precaución con posiciones abiertas antes de la publicación, especialmente en acciones con alta volatilidad implícita.</p>
<div class="rpt-highlight">⚠️ <b>Nota:</b> Los movimientos post-earnings dependen de si los resultados superan o no las expectativas del consenso de analistas,
no solo de si son positivos o negativos en términos absolutos.</div>
<table class="rpt-table"><thead><tr><th>Ticker</th><th>Empresa</th><th>Fecha Earnings</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="rpt-footer">Fuente: Yahoo Finance Calendar | {len(earnings)} empresas identificadas</p></div>"""


def report_likely_up_this_week():
    data = _safe_get_data(SP500[:120], "3mo")
    bullish = []
    for sym, hist in data.items():
        c = hist["Close"].values.astype(float)
        if len(c) < 50: continue
        price = c[-1]
        emas = _calc_emas(c)
        rsi = _calc_rsi(c)
        pct_5d = ((c[-1]-c[-5])/c[-5])*100 if len(c)>=5 else 0
        pct_20d = ((c[-1]-c[-20])/c[-20])*100 if len(c)>=20 else 0
        
        if price > emas["ema9"] > emas["ema21"] and 40 < rsi < 68:
            reason = "Precio sobre EMA9 > EMA21 con RSI en zona óptima (40-68). "
            if pct_5d > 0: reason += f"Momentum positivo reciente ({pct_5d:+.1f}% en 5 días). "
            if emas["ema50"] and price > emas["ema50"]: reason += "Sobre EMA50 confirma tendencia media. "
            bullish.append({"sym":sym,"price":price,"rsi":rsi,"pct_5d":pct_5d,"pct_20d":pct_20d,"reason":reason,"emas":emas})
    
    bullish.sort(key=lambda x: x["pct_5d"], reverse=True)
    
    rows = ""
    for p in bullish[:15]:
        name = _get_name(p["sym"])
        risk = "Bajo" if p["rsi"] < 55 else ("Medio" if p["rsi"] < 65 else "Alto — cerca de sobrecompra")
        rows += f"""<tr><td><b>{p["sym"]}</b></td><td>{name}</td><td>${p["price"]:.2f}</td>
        <td>{_rsi_text(p["rsi"])}</td><td class="up">{p["pct_5d"]:+.2f}%</td>
        <td style="font-size:11px">{p["reason"]}</td><td>{risk}</td></tr>"""
    
    return f"""<div class="rpt-section">
<h2>🟢 4. Acciones que Pueden SUBIR Esta Semana</h2>
<p class="rpt-narrative">Selección de acciones con estructura técnica alcista basada en análisis de medias móviles y momentum.
<b>Criterios:</b> Precio &gt; EMA9 &gt; EMA21 (alineación alcista), RSI entre 40-68 (momentum positivo sin sobrecompra).
Estas acciones muestran una confluencia de factores técnicos que sugieren continuación alcista en el corto plazo.</p>
<table class="rpt-table"><thead><tr>
<th>Ticker</th><th>Nombre</th><th>Precio</th><th>RSI</th><th>Var. 5d</th><th>Análisis</th><th>Riesgo</th>
</tr></thead><tbody>{rows}</tbody></table>
<p class="rpt-footer">Fuente: Yahoo Finance | Análisis técnico: EMA 9/21/50, RSI 14 | {len(bullish)} acciones identificadas</p></div>"""


def report_likely_down_this_week():
    data = _safe_get_data(SP500[:120], "3mo")
    bearish = []
    for sym, hist in data.items():
        c = hist["Close"].values.astype(float)
        if len(c) < 50: continue
        price = c[-1]
        emas = _calc_emas(c)
        rsi = _calc_rsi(c)
        pct_5d = ((c[-1]-c[-5])/c[-5])*100 if len(c)>=5 else 0
        
        if price < emas["ema9"] < emas["ema21"] and rsi < 48:
            reason = "Precio bajo EMA9 < EMA21 con RSI débil. "
            if pct_5d < -1: reason += f"Caída reciente ({pct_5d:.1f}%) confirma presión vendedora. "
            if emas["ema50"] and price < emas["ema50"]: reason += "Bajo EMA50 indica debilidad estructural. "
            bearish.append({"sym":sym,"price":price,"rsi":rsi,"pct_5d":pct_5d,"reason":reason})
    
    bearish.sort(key=lambda x: x["pct_5d"])
    
    rows = ""
    for p in bearish[:15]:
        name = _get_name(p["sym"])
        rows += f"""<tr><td><b>{p["sym"]}</b></td><td>{name}</td><td>${p["price"]:.2f}</td>
        <td>{_rsi_text(p["rsi"])}</td><td class="down">{p["pct_5d"]:+.2f}%</td>
        <td style="font-size:11px">{p["reason"]}</td></tr>"""
    
    return f"""<div class="rpt-section">
<h2>🔴 5. Acciones que Pueden BAJAR Esta Semana</h2>
<p class="rpt-narrative">Identificación de acciones con estructura técnica bajista.
<b>Criterios:</b> Precio &lt; EMA9 &lt; EMA21 (alineación bajista), RSI &lt; 48 (momentum negativo).
Estas acciones muestran debilidad técnica que podría resultar en caídas adicionales en los próximos días.</p>
<div class="rpt-highlight">⚠️ <b>Importante:</b> Las acciones con RSI &lt; 30 podrían estar en zona de sobreventa
y experimentar rebotes técnicos de corto plazo. Considere esto para operaciones SHORT.</div>
<table class="rpt-table"><thead><tr>
<th>Ticker</th><th>Nombre</th><th>Precio</th><th>RSI</th><th>Var. 5d</th><th>Análisis</th>
</tr></thead><tbody>{rows}</tbody></table>
<p class="rpt-footer">Fuente: Yahoo Finance | {len(bearish)} acciones con estructura bajista</p></div>"""


def report_4day_outlook():
    indices = {"^GSPC":"S&P 500","^DJI":"Dow Jones","^IXIC":"NASDAQ Composite","^RUT":"Russell 2000","^VIX":"VIX (Volatilidad)","^TNX":"Bono 10 Años US"}
    data = _safe_get_data(list(indices.keys()), "1mo")
    
    rows = ""
    analysis_text = ""
    for sym, name in indices.items():
        if sym not in data: continue
        c = data[sym]["Close"].values.astype(float)
        price = c[-1]
        pct_1d = ((c[-1]-c[-2])/c[-2])*100 if len(c)>=2 else 0
        pct_5d = ((c[-1]-c[-5])/c[-5])*100 if len(c)>=5 else 0
        pct_20d = ((c[-1]-c[-20])/c[-20])*100 if len(c)>=20 else 0
        rsi = _calc_rsi(c)
        
        rows += f"""<tr><td><b>{sym}</b></td><td>{name}</td><td>${price:,.2f}</td>
        <td class="{"up" if pct_1d>0 else "down"}">{pct_1d:+.2f}%</td>
        <td class="{"up" if pct_5d>0 else "down"}">{pct_5d:+.2f}%</td>
        <td class="{"up" if pct_20d>0 else "down"}">{pct_20d:+.2f}%</td>
        <td>{_rsi_text(rsi)}</td><td>{_trend_text(pct_5d)}</td></tr>"""
        
        if sym == "^GSPC":
            if pct_5d > 1: analysis_text += f"<p>📊 <b>S&P 500:</b> Tendencia alcista con {pct_5d:+.1f}% en la semana. "
            elif pct_5d < -1: analysis_text += f"<p>📊 <b>S&P 500:</b> Presión bajista con {pct_5d:+.1f}% en la semana. "
            else: analysis_text += f"<p>📊 <b>S&P 500:</b> Movimiento lateral ({pct_5d:+.1f}%). "
            if rsi > 65: analysis_text += "RSI en zona elevada sugiere cautela. "
            elif rsi < 35: analysis_text += "RSI en sobreventa podría generar rebote. "
            analysis_text += "</p>"
        elif sym == "^VIX":
            if price > 25: analysis_text += f"<p>⚡ <b>VIX a {price:.1f}:</b> Alta volatilidad — mercado temeroso, posibles movimientos bruscos.</p>"
            elif price < 15: analysis_text += f"<p>⚡ <b>VIX a {price:.1f}:</b> Baja volatilidad — mercado complaciente, posible calma antes de tormenta.</p>"
    
    return f"""<div class="rpt-section">
<h2>🔮 6. Perspectiva de Mercado — Próximos 4 Días</h2>
<p class="rpt-narrative">Análisis de los principales índices bursátiles de EE.UU. y su dirección probable para los próximos 4 días de operación.
Se evalúan tendencias de corto (1 día), medio (5 días) y largo plazo (20 días) junto con indicadores de momentum.</p>
<table class="rpt-table"><thead><tr>
<th>Índice</th><th>Nombre</th><th>Precio</th><th>Var. 1d</th><th>Var. 5d</th><th>Var. 20d</th><th>RSI</th><th>Tendencia</th>
</tr></thead><tbody>{rows}</tbody></table>
<h3>📝 Análisis Narrativo</h3>
<div class="rpt-narrative">{analysis_text}</div>
<p class="rpt-footer">Fuente: Yahoo Finance | Análisis automático basado en datos técnicos</p></div>"""


def report_sector_news():
    sectors = {"XLK":"Tecnología","XLF":"Financieros","XLE":"Energía","XLV":"Salud",
               "XLY":"Consumo Discrecional","XLP":"Consumo Básico","XLI":"Industriales",
               "XLB":"Materiales","XLRE":"Bienes Raíces","XLU":"Utilidades","XLC":"Comunicaciones"}
    data = _safe_get_data(list(sectors.keys()), "1mo")
    
    rows = ""
    analysis = ""
    best_sector = ("", -999)
    worst_sector = ("", 999)
    
    for etf, name in sectors.items():
        if etf not in data: continue
        c = data[etf]["Close"].values.astype(float)
        v = data[etf]["Volume"].values.astype(float)
        price = c[-1]
        pct_1w = ((c[-1]-c[-5])/c[-5])*100 if len(c)>=5 else 0
        pct_1m = ((c[-1]-c[0])/c[0])*100
        rsi = _calc_rsi(c)
        vol_ratio = np.mean(v[-5:])/max(np.mean(v),1)
        
        if pct_1w > best_sector[1]: best_sector = (name, pct_1w)
        if pct_1w < worst_sector[1]: worst_sector = (name, pct_1w)
        
        rows += f"""<tr><td>{etf}</td><td><b>{name}</b></td><td>${price:.2f}</td>
        <td class="{"up" if pct_1w>0 else "down"}">{pct_1w:+.2f}%</td>
        <td class="{"up" if pct_1m>0 else "down"}">{pct_1m:+.2f}%</td>
        <td>{_rsi_text(rsi)}</td><td>{_trend_text(pct_1w)}</td></tr>"""
    
    analysis = f"""<p>🏆 <b>Mejor sector de la semana:</b> {best_sector[0]} ({best_sector[1]:+.2f}%)</p>
<p>📉 <b>Peor sector de la semana:</b> {worst_sector[0]} ({worst_sector[1]:+.2f}%)</p>"""
    
    return f"""<div class="rpt-section">
<h2>📰 7. Análisis por Sector S&P 500 (GICS)</h2>
<p class="rpt-narrative">Rendimiento de los 11 sectores del S&P 500 medido a través de ETFs sectoriales de SPDR.
La rotación sectorial es clave para identificar hacia dónde fluye el capital institucional.
Los sectores con mejor rendimiento semanal y volumen creciente suelen continuar su tendencia en el corto plazo.</p>
<table class="rpt-table"><thead><tr>
<th>ETF</th><th>Sector</th><th>Precio</th><th>Var. 1 sem</th><th>Var. 1 mes</th><th>RSI</th><th>Tendencia</th>
</tr></thead><tbody>{rows}</tbody></table>
<h3>📝 Resumen de Rotación Sectorial</h3>
<div class="rpt-narrative">{analysis}</div>
<p class="rpt-footer">Fuente: Yahoo Finance | ETFs sectoriales SPDR</p></div>"""


def report_market_today():
    indices = {"^GSPC":"S&P 500","^DJI":"Dow Jones","^IXIC":"NASDAQ","^RUT":"Russell 2000","^VIX":"VIX","^TNX":"10Y Treasury","GC=F":"Oro","CL=F":"Petróleo WTI","DX-Y.NYB":"Dólar Index"}
    data = _safe_get_data(list(indices.keys()), "5d")
    
    rows = ""
    narrative = "<p><b>Resumen del día:</b> "
    sp_chg = 0
    
    for sym, name in indices.items():
        if sym not in data: continue
        c = data[sym]["Close"].values.astype(float)
        price = c[-1]; prev = c[-2] if len(c)>=2 else price
        chg = ((price-prev)/prev)*100
        if sym == "^GSPC": sp_chg = chg
        rows += f"""<tr><td><b>{sym}</b></td><td>{name}</td><td>${price:,.2f}</td>
        <td class="{"up" if chg>0 else "down"}"><b>{chg:+.2f}%</b></td></tr>"""
    
    if sp_chg > 0.5: narrative += "Sesión positiva con el S&P 500 avanzando. Sentimiento optimista predomina. "
    elif sp_chg < -0.5: narrative += "Sesión negativa con presión vendedora en el S&P 500. "
    else: narrative += "Sesión mixta con movimientos laterales en los principales índices. "
    narrative += "</p>"
    
    return f"""<div class="rpt-section">
<h2>🏛️ 8. Comportamiento del Mercado Hoy</h2>
<p class="rpt-narrative">Panorama actual de los principales índices, commodities y divisas del mercado estadounidense.</p>
<table class="rpt-table"><thead><tr><th>Índice</th><th>Nombre</th><th>Precio</th><th>Var. Diaria</th></tr></thead>
<tbody>{rows}</tbody></table>
<h3>📝 Análisis de la Sesión</h3>
<div class="rpt-narrative">{narrative}</div>
<p class="rpt-footer">Fuente: Yahoo Finance | Precios con delay de ~15 minutos</p></div>"""


def report_ai_tech_news():
    tech = {"NVDA":"NVIDIA","AMD":"AMD","MSFT":"Microsoft","GOOGL":"Alphabet","META":"Meta",
            "AMZN":"Amazon","AAPL":"Apple","TSM":"TSMC","AVGO":"Broadcom","PLTR":"Palantir",
            "ARM":"ARM Holdings","SMCI":"Super Micro","CRWD":"CrowdStrike","SNOW":"Snowflake","IONQ":"IonQ","SOUN":"SoundHound AI"}
    data = _safe_get_data(list(tech.keys()), "1mo")
    
    rows = ""
    for sym, name in tech.items():
        if sym not in data: continue
        c = data[sym]["Close"].values.astype(float)
        price = c[-1]
        pct_1w = ((c[-1]-c[-5])/c[-5])*100 if len(c)>=5 else 0
        pct_1m = ((c[-1]-c[0])/c[0])*100
        rsi = _calc_rsi(c)
        emas = _calc_emas(c)
        
        tech_note = ""
        if emas["ema50"] and price > emas["ema50"]: tech_note = "Sobre EMA50 ✅"
        elif emas["ema50"]: tech_note = "Bajo EMA50 ⚠️"
        if rsi > 70: tech_note += " | Sobrecompra"
        elif rsi < 30: tech_note += " | Sobreventa"
        
        rows += f"""<tr><td><b>{sym}</b></td><td>{name}</td><td>${price:.2f}</td>
        <td class="{"up" if pct_1w>0 else "down"}">{pct_1w:+.2f}%</td>
        <td class="{"up" if pct_1m>0 else "down"}">{pct_1m:+.2f}%</td>
        <td>{_rsi_text(rsi)}</td><td style="font-size:11px">{tech_note}</td></tr>"""
    
    return f"""<div class="rpt-section">
<h2>🤖 9. Sector AI / Tecnología / Semiconductores</h2>
<p class="rpt-narrative">Seguimiento de las empresas clave en inteligencia artificial, cloud computing, semiconductores y tecnología disruptiva.
Este sector lidera la innovación global y representa el mayor peso en los índices S&P 500 y NASDAQ.
Las tendencias en AI (modelos de lenguaje, chips para inferencia, cloud AI) siguen siendo el motor principal del mercado.</p>
<table class="rpt-table"><thead><tr>
<th>Ticker</th><th>Empresa</th><th>Precio</th><th>Var. 1 sem</th><th>Var. 1 mes</th><th>RSI</th><th>Técnico</th>
</tr></thead><tbody>{rows}</tbody></table>
<p class="rpt-footer">Fuente: Yahoo Finance | Sector AI/Tech/Semiconductores</p></div>"""


def report_ema200_stocks():
    data = _safe_get_data(SP500[:100], "1y")
    near = {"above":[],"below":[]}
    
    for sym, hist in data.items():
        c = hist["Close"].values.astype(float)
        if len(c) < 200: continue
        ema200 = pd.Series(c).ewm(span=200).mean().iloc[-1]
        price = c[-1]; dist = ((price-ema200)/ema200)*100
        rsi = _calc_rsi(c)
        pct_5d = ((c[-1]-c[-5])/c[-5])*100 if len(c)>=5 else 0
        
        if abs(dist) < 5:
            entry = {"sym":sym,"price":price,"ema200":ema200,"dist":dist,"rsi":rsi,"pct_5d":pct_5d}
            if dist > 0: near["above"].append(entry)
            else: near["below"].append(entry)
    
    near["above"].sort(key=lambda x: x["dist"])
    near["below"].sort(key=lambda x: x["dist"], reverse=True)
    
    def make_rows(items):
        r = ""
        for p in items[:10]:
            name = _get_name(p["sym"])
            cls = "up" if p["dist"]>0 else "down"
            trend = "↗️ Tendencia alcista" if p["pct_5d"]>0.5 else ("↘️ Tendencia bajista" if p["pct_5d"]<-0.5 else "→ Lateral")
            r += f"""<tr><td><b>{p["sym"]}</b></td><td>{name}</td><td>${p["price"]:.2f}</td>
            <td>${p["ema200"]:.2f}</td><td class="{cls}">{p["dist"]:+.2f}%</td>
            <td>{_rsi_text(p["rsi"])}</td><td>{trend}</td></tr>"""
        return r
    
    return f"""<div class="rpt-section">
<h2>📏 10. Acciones Cerca del EMA 200</h2>
<p class="rpt-narrative">El EMA 200 es considerado la línea divisoria entre tendencia alcista y bajista de largo plazo.
Las acciones que cruzan este nivel generan señales importantes:
<b>Cruce alcista</b> (precio sube sobre EMA200) = potencial inicio de tendencia alcista.
<b>Cruce bajista</b> (precio cae bajo EMA200) = potencial inicio de tendencia bajista.
Se listan acciones dentro del ±5% de su EMA 200 diaria.</p>

<h3 style="color:#26a69a">📈 Sobre EMA 200 — Tendencia Alcista</h3>
<table class="rpt-table"><thead><tr><th>Ticker</th><th>Nombre</th><th>Precio</th><th>EMA 200</th><th>Distancia</th><th>RSI</th><th>Tendencia</th></tr></thead>
<tbody>{make_rows(near["above"])}</tbody></table>

<h3 style="color:#ef5350">📉 Bajo EMA 200 — Tendencia Bajista</h3>
<table class="rpt-table"><thead><tr><th>Ticker</th><th>Nombre</th><th>Precio</th><th>EMA 200</th><th>Distancia</th><th>RSI</th><th>Tendencia</th></tr></thead>
<tbody>{make_rows(near["below"])}</tbody></table>
<p class="rpt-footer">Fuente: Yahoo Finance | EMA 200 en temporalidad diaria | {len(near["above"])+len(near["below"])} acciones encontradas</p></div>"""


def report_fibonacci_fallen():
    candidates = list(dict.fromkeys(SP500[:120] + NASDAQ_100[:50]))
    data = _safe_get_data(candidates[:120], "6mo")
    
    fallen = []
    for sym, hist in data.items():
        c = hist["Close"].values.astype(float)
        if len(c) < 50: continue
        high = float(np.max(c)); low = float(np.min(c))
        price = c[-1]; drop = ((price-high)/high)*100
        fib_618 = high - (high-low)*0.618
        fib_786 = high - (high-low)*0.786
        rsi = _calc_rsi(c)
        
        if drop < -25:
            near_fib = ""
            if abs(price-fib_618)/fib_618 < 0.03: near_fib = "Cerca de Fib 0.618"
            elif abs(price-fib_786)/fib_786 < 0.03: near_fib = "Cerca de Fib 0.786"
            elif price < fib_786: near_fib = f"Bajo Fib 0.786 ({drop:.0f}% caída)"
            
            risk = "Bajo" if rsi < 30 else ("Medio" if rsi < 45 else "Alto")
            fallen.append({"sym":sym,"price":price,"high":high,"drop":drop,
                          "fib_618":fib_618,"fib_786":fib_786,"rsi":rsi,"near_fib":near_fib,"risk":risk})
    
    fallen.sort(key=lambda x: x["drop"])
    
    if not fallen:
        return """<div class="rpt-section"><h2>📉 11. Acciones Desplomadas — Análisis Fibonacci</h2>
<p class="rpt-narrative">No se encontraron acciones del S&P 500/NASDAQ 100 con caídas superiores al 25% desde sus máximos de 6 meses.
Esto puede indicar un mercado general sano sin grandes desplomes individuales.</p></div>"""
    
    rows = ""
    for p in fallen[:15]:
        name = _get_name(p["sym"])
        rows += f"""<tr><td><b>{p["sym"]}</b></td><td>{name}</td><td>${p["price"]:.2f}</td>
        <td>${p["high"]:.2f}</td><td class="down"><b>{p["drop"]:.1f}%</b></td>
        <td>${p["fib_618"]:.2f}</td><td>${p["fib_786"]:.2f}</td>
        <td>{_rsi_text(p["rsi"])}</td><td>{p["near_fib"]}</td><td>{p["risk"]}</td></tr>"""
    
    return f"""<div class="rpt-section">
<h2>📉 11. Acciones Desplomadas — Análisis Fibonacci</h2>
<p class="rpt-narrative">Identificación de acciones que han sufrido caídas significativas (>25%) desde sus máximos de 6 meses.
Se evalúan niveles de retroceso Fibonacci (0.618 y 0.786) como posibles zonas de soporte y rebote.
Las acciones en sobreventa (RSI &lt; 30) cerca de niveles Fibonacci clave representan oportunidades potenciales de rebote técnico,
aunque deben evaluarse fundamentales antes de operar.</p>
<div class="rpt-highlight">📐 <b>Niveles Fibonacci clave:</b> 0.618 (retroceso dorado) — zona de probable soporte fuerte.
0.786 — si se rompe, indica debilidad extrema y posible caída adicional.</div>
<table class="rpt-table"><thead><tr>
<th>Ticker</th><th>Nombre</th><th>Precio</th><th>Máximo 6m</th><th>Caída</th><th>Fib 0.618</th><th>Fib 0.786</th><th>RSI</th><th>Nivel Fibonacci</th><th>Riesgo</th>
</tr></thead><tbody>{rows}</tbody></table>
<p class="rpt-footer">Fuente: Yahoo Finance | Retrocesos Fibonacci sobre máximos/mínimos de 6 meses | {len(fallen)} acciones identificadas</p></div>"""



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
    return {"status": "ok", "version": "5.4", "engine": "Sentinel Quantum Edge 18-Factor AI/ML",
            "scan_universe": len(SCAN_UNIVERSE), "cache": len(CACHE),
            "timezone": "America/Lima (UTC-5)",
            "indices": {"SP500": len(set(SP500)), "NASDAQ100": len(set(NASDAQ_100)),
                        "DOW30": len(set(DOW_30)), "RUSSELL2000": len(set(RUSSELL_2000_TOP))}}

@app.get("/")
def root():
    if os.path.exists("/app/static/index.html"):
        return FileResponse("/app/static/index.html")
    return {"message": "NAU Quantum v5.4 API", "docs": "/docs"}

if os.path.exists("/app/static"):
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000, workers=8)
