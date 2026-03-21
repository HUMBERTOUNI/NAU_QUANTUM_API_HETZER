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
    "1m":"5d","5m":"30d","15m":"30d","30m":"30d",
    "1h":"3mo","2h":"3mo","4h":"3mo",
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
    Detect consecutive buy or sell signals in the MOST RECENT completed candles.
    Checks the last 2-3 CLOSED candles (market hours only).
    If the last 2 closed candles both have BUY or both have SELL → match.
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
        
        if len(df) < 4:
            return None
        
        # Get signals for the LAST 3 COMPLETED candles (exclude current forming candle)
        # iloc[-1] = current (possibly still forming), iloc[-2] = last closed, iloc[-3] = before that
        recent = df.iloc[-4:-1]  # 3 most recent COMPLETED candles
        labels = []
        for _, row in recent.iterrows():
            sig = float(row.get("NAU_Signal", 0))
            conf = float(row.get("NAU_Confidence", 0))
            lbl = signal_label(sig, conf)
            labels.append(lbl)
        
        # Check: last 2 completed candles must both be BUY or both be SELL
        if len(labels) < 2:
            return None
        
        last_two = labels[-2:]  # The 2 most recent completed candles
        
        # Both must be buy-type or both sell-type
        both_buy = all("COMPRA" in l for l in last_two)
        both_sell = all("VENTA" in l for l in last_two)
        
        if not both_buy and not both_sell:
            return None
        
        is_buy = both_buy
        last_label = last_two[-1]
        
        # Count how many consecutive going back (including the 3rd candle if it matches)
        consecutive = 2
        if len(labels) >= 3:
            third = labels[0]
            if is_buy and "COMPRA" in third:
                consecutive = 3
            elif not is_buy and "VENTA" in third:
                consecutive = 3
        
        # Price and SL/TP from current bar
        last = df.iloc[-1]
        price = float(last["Close"])
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
            "symbol": sym, "name": name, "label": last_label,
            "direction": "LONG" if is_buy else "SHORT",
            "consecutive": consecutive, "price": round(price, 2),
            "entry": round(entry, 2), "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        }
    except Exception:
        return None


@app.get("/api/scan_vc")
def scan_vc(interval: str = Query("1d"), page: int = Query(1)):
    """
    Find stocks with 2+ consecutive buy/sell signals in last completed candles.
    Paginated: page=1 → stocks 1-500, page=2 → 501-1000, page=3 → 1001-1500, page=4 → 1501-2000+
    """
    try:
        page_size = 500
        start = (page - 1) * page_size
        end = start + page_size
        universe = SCAN_UNIVERSE[start:end]
        total_pages = (len(SCAN_UNIVERSE) + page_size - 1) // page_size
        
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
