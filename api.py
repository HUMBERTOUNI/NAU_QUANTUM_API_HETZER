"""
NAU Quantum v5.0 "Sentinel Quantum Edge" — FastAPI Backend
Features: Smart search, signal explanations, fast scanner, VWAP/EMAs,
          NYSE timezone, all timeframes, in-memory cache, PWA-ready
"""
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import yfinance as yf
import pandas as pd
import numpy as np
import traceback, time, os, json, asyncio
from datetime import datetime, timezone
from nau_quantum_engine import NAUQuantumAlphaIndicator

app = FastAPI(title="NAU Quantum v5.0 — Sentinel Quantum Edge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Cache ──
CACHE = {}
CACHE_TTL = 60

def cache_get(key):
    if key in CACHE and time.time() - CACHE[key][1] < CACHE_TTL:
        return CACHE[key][0]
    return None

def cache_set(key, data):
    CACHE[key] = (data, time.time())

# ── Symbol Database for Smart Search ──
SYMBOLS_DB = [
    {"s":"AAPL","n":"Apple Inc","sec":"Technology"},{"s":"MSFT","n":"Microsoft Corp","sec":"Technology"},
    {"s":"NVDA","n":"NVIDIA Corp","sec":"Technology"},{"s":"GOOGL","n":"Alphabet (Google)","sec":"Technology"},
    {"s":"GOOG","n":"Alphabet Class C","sec":"Technology"},{"s":"META","n":"Meta Platforms","sec":"Technology"},
    {"s":"TSLA","n":"Tesla Inc","sec":"Technology"},{"s":"PLTR","n":"Palantir Technologies","sec":"Technology"},
    {"s":"AMD","n":"Advanced Micro Devices","sec":"Technology"},{"s":"INTC","n":"Intel Corp","sec":"Technology"},
    {"s":"CRM","n":"Salesforce Inc","sec":"Technology"},{"s":"NFLX","n":"Netflix Inc","sec":"Technology"},
    {"s":"AVGO","n":"Broadcom Inc","sec":"Technology"},{"s":"QCOM","n":"Qualcomm Inc","sec":"Technology"},
    {"s":"MU","n":"Micron Technology","sec":"Technology"},{"s":"SNDK","n":"SanDisk (now WDC)","sec":"Technology"},
    {"s":"WDC","n":"Western Digital","sec":"Technology"},{"s":"ORCL","n":"Oracle Corp","sec":"Technology"},
    {"s":"ADBE","n":"Adobe Inc","sec":"Technology"},{"s":"CSCO","n":"Cisco Systems","sec":"Technology"},
    {"s":"IBM","n":"IBM Corp","sec":"Technology"},{"s":"UBER","n":"Uber Technologies","sec":"Technology"},
    {"s":"SHOP","n":"Shopify Inc","sec":"Technology"},{"s":"SQ","n":"Block Inc (Square)","sec":"Technology"},
    {"s":"SNOW","n":"Snowflake Inc","sec":"Technology"},{"s":"NET","n":"Cloudflare Inc","sec":"Technology"},
    {"s":"PANW","n":"Palo Alto Networks","sec":"Technology"},{"s":"CRWD","n":"CrowdStrike","sec":"Technology"},
    {"s":"DDOG","n":"Datadog Inc","sec":"Technology"},{"s":"ZS","n":"Zscaler Inc","sec":"Technology"},
    {"s":"MRVL","n":"Marvell Technology","sec":"Technology"},{"s":"ON","n":"ON Semiconductor","sec":"Technology"},
    {"s":"ARM","n":"ARM Holdings","sec":"Technology"},{"s":"SMCI","n":"Super Micro Computer","sec":"Technology"},
    {"s":"DELL","n":"Dell Technologies","sec":"Technology"},{"s":"HPQ","n":"HP Inc","sec":"Technology"},
    {"s":"ANET","n":"Arista Networks","sec":"Technology"},{"s":"NOW","n":"ServiceNow","sec":"Technology"},
    {"s":"INTU","n":"Intuit Inc","sec":"Technology"},{"s":"PYPL","n":"PayPal Holdings","sec":"Finance"},
    {"s":"JPM","n":"JPMorgan Chase","sec":"Finance"},{"s":"BAC","n":"Bank of America","sec":"Finance"},
    {"s":"GS","n":"Goldman Sachs","sec":"Finance"},{"s":"MS","n":"Morgan Stanley","sec":"Finance"},
    {"s":"V","n":"Visa Inc","sec":"Finance"},{"s":"MA","n":"Mastercard","sec":"Finance"},
    {"s":"COIN","n":"Coinbase Global","sec":"Finance"},{"s":"C","n":"Citigroup","sec":"Finance"},
    {"s":"WFC","n":"Wells Fargo","sec":"Finance"},{"s":"AXP","n":"American Express","sec":"Finance"},
    {"s":"SCHW","n":"Charles Schwab","sec":"Finance"},{"s":"BLK","n":"BlackRock","sec":"Finance"},
    {"s":"JNJ","n":"Johnson & Johnson","sec":"Healthcare"},{"s":"UNH","n":"UnitedHealth Group","sec":"Healthcare"},
    {"s":"LLY","n":"Eli Lilly","sec":"Healthcare"},{"s":"ABBV","n":"AbbVie Inc","sec":"Healthcare"},
    {"s":"PFE","n":"Pfizer Inc","sec":"Healthcare"},{"s":"MRK","n":"Merck & Co","sec":"Healthcare"},
    {"s":"TMO","n":"Thermo Fisher","sec":"Healthcare"},{"s":"ABT","n":"Abbott Labs","sec":"Healthcare"},
    {"s":"XOM","n":"Exxon Mobil","sec":"Energy"},{"s":"CVX","n":"Chevron Corp","sec":"Energy"},
    {"s":"OXY","n":"Occidental Petroleum","sec":"Energy"},{"s":"COP","n":"ConocoPhillips","sec":"Energy"},
    {"s":"SLB","n":"Schlumberger","sec":"Energy"},{"s":"WMT","n":"Walmart Inc","sec":"Consumer"},
    {"s":"COST","n":"Costco Wholesale","sec":"Consumer"},{"s":"DIS","n":"Walt Disney","sec":"Consumer"},
    {"s":"MCD","n":"McDonald's Corp","sec":"Consumer"},{"s":"KO","n":"Coca-Cola Co","sec":"Consumer"},
    {"s":"PEP","n":"PepsiCo Inc","sec":"Consumer"},{"s":"NKE","n":"Nike Inc","sec":"Consumer"},
    {"s":"HD","n":"Home Depot","sec":"Consumer"},{"s":"SBUX","n":"Starbucks","sec":"Consumer"},
    {"s":"TGT","n":"Target Corp","sec":"Consumer"},{"s":"AMZN","n":"Amazon.com","sec":"Consumer"},
    {"s":"SPY","n":"S&P 500 ETF","sec":"ETF"},{"s":"QQQ","n":"Nasdaq 100 ETF","sec":"ETF"},
    {"s":"IWM","n":"Russell 2000 ETF","sec":"ETF"},{"s":"DIA","n":"Dow Jones ETF","sec":"ETF"},
    {"s":"SOXX","n":"Semiconductor ETF","sec":"ETF"},{"s":"ARKK","n":"ARK Innovation ETF","sec":"ETF"},
    {"s":"XLF","n":"Financial Select ETF","sec":"ETF"},{"s":"XLE","n":"Energy Select ETF","sec":"ETF"},
    {"s":"XLK","n":"Technology Select ETF","sec":"ETF"},{"s":"GLD","n":"Gold ETF","sec":"ETF"},
    {"s":"SLV","n":"Silver ETF","sec":"ETF"},{"s":"TLT","n":"20+ Year Treasury ETF","sec":"ETF"},
    {"s":"VTI","n":"Total Stock Market ETF","sec":"ETF"},{"s":"VOO","n":"Vanguard S&P 500 ETF","sec":"ETF"},
    {"s":"BTC-USD","n":"Bitcoin","sec":"Crypto"},{"s":"ETH-USD","n":"Ethereum","sec":"Crypto"},
    {"s":"SOL-USD","n":"Solana","sec":"Crypto"},{"s":"BNB-USD","n":"Binance Coin","sec":"Crypto"},
    {"s":"XRP-USD","n":"Ripple XRP","sec":"Crypto"},{"s":"ADA-USD","n":"Cardano","sec":"Crypto"},
    {"s":"DOGE-USD","n":"Dogecoin","sec":"Crypto"},{"s":"DOT-USD","n":"Polkadot","sec":"Crypto"},
    {"s":"AVAX-USD","n":"Avalanche","sec":"Crypto"},{"s":"MATIC-USD","n":"Polygon","sec":"Crypto"},
    {"s":"^GSPC","n":"S&P 500 Index","sec":"Index"},{"s":"^DJI","n":"Dow Jones Industrial","sec":"Index"},
    {"s":"^IXIC","n":"Nasdaq Composite","sec":"Index"},{"s":"^RUT","n":"Russell 2000 Index","sec":"Index"},
    {"s":"^VIX","n":"VIX Volatility Index","sec":"Index"},{"s":"^TNX","n":"10-Year Treasury Yield","sec":"Index"},
    {"s":"GC=F","n":"Gold Futures","sec":"Commodities"},{"s":"SI=F","n":"Silver Futures","sec":"Commodities"},
    {"s":"CL=F","n":"Crude Oil Futures","sec":"Commodities"},{"s":"NG=F","n":"Natural Gas Futures","sec":"Commodities"},
    {"s":"EURUSD=X","n":"EUR/USD","sec":"Forex"},{"s":"GBPUSD=X","n":"GBP/USD","sec":"Forex"},
    {"s":"USDJPY=X","n":"USD/JPY","sec":"Forex"},{"s":"AUDUSD=X","n":"AUD/USD","sec":"Forex"},
]

INTERVAL_MAP = {
    "1m":{"yf":"1m","period":"7d","resample":None},
    "5m":{"yf":"5m","period":"60d","resample":None},
    "15m":{"yf":"15m","period":"60d","resample":None},
    "30m":{"yf":"30m","period":"60d","resample":None},
    "1h":{"yf":"1h","period":"730d","resample":None},
    "4h":{"yf":"1h","period":"730d","resample":"4h"},
    "1d":{"yf":"1d","period":"5y","resample":None},
    "1wk":{"yf":"1wk","period":"10y","resample":None},
    "1mo":{"yf":"1mo","period":"max","resample":None},
    "3mo":{"yf":"3mo","period":"max","resample":None},
}

indicator = NAUQuantumAlphaIndicator()


def signal_label(score, confidence):
    """Convert raw score to human-readable signal label."""
    conf = confidence * 100 if confidence <= 1 else confidence
    if score > 35 and conf > 70: return "COMPRA FUERTE"
    if score > 20 and conf > 60: return "COMPRA"
    if score < -35 and conf > 70: return "VENTA FUERTE"
    if score < -20 and conf > 60: return "VENTA"
    return "NEUTRAL"


def generate_explanation(summary, sl_tp, factors):
    """Generate natural language explanation of why to enter or not."""
    sig = summary["signal"]
    conf = summary["confidence"]
    regime = summary["regime_name"]
    label = signal_label(sig, conf)
    sym = summary["symbol"]

    # Count aligned factors
    bullish = sum(1 for f in factors.values() if f > 10)
    bearish = sum(1 for f in factors.values() if f < -10)
    neutral = 18 - bullish - bearish

    if label in ("COMPRA FUERTE", "COMPRA"):
        action = "COMPRAR (LONG)"
        direction = "alcista"
        emoji = "🟢"
    elif label in ("VENTA FUERTE", "VENTA"):
        action = "VENDER (SHORT)"
        direction = "bajista"
        emoji = "🔴"
    else:
        action = "ESPERAR"
        direction = "indefinida"
        emoji = "🟡"

    lines = [f"{emoji} SEÑAL: {label} — Acción recomendada: {action}"]
    lines.append(f"Confianza: {conf:.0f}% | Régimen: {regime} | Score: {sig:+.1f}")
    lines.append("")

    if label != "NEUTRAL":
        lines.append(f"CONFLUENCIA: {bullish if sig>0 else bearish} de 18 factores alineados en dirección {direction}.")
        # Top 3 factors
        sorted_f = sorted(factors.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        lines.append("Factores principales:")
        for name, val in sorted_f:
            direction_f = "alcista" if val > 0 else "bajista"
            lines.append(f"  • {name}: {val:+.1f} ({direction_f})")

        if sl_tp:
            lines.append("")
            lines.append(f"ENTRADA: ${sl_tp['entry']:.2f}")
            lines.append(f"STOP LOSS: ${sl_tp['sl']:.2f} (riesgo: ${abs(sl_tp['entry']-sl_tp['sl']):.2f})")
            lines.append(f"TP1: ${sl_tp['tp1']:.2f} | TP2: ${sl_tp['tp2']:.2f} | TP3: ${sl_tp['tp3']:.2f}")
            rr = abs(sl_tp['tp2']-sl_tp['entry']) / max(abs(sl_tp['entry']-sl_tp['sl']), 0.01)
            lines.append(f"Risk:Reward = 1:{rr:.1f}")
    else:
        lines.append(f"Los factores están divididos: {bullish} alcistas, {bearish} bajistas, {neutral} neutrales.")
        lines.append("No hay confluencia suficiente para una operación de alta probabilidad.")
        lines.append("RECOMENDACIÓN: Esperar hasta que la confianza supere 65% y el score supere ±20.")

    return "\n".join(lines)


def compute_technicals(df):
    """Compute VWAP, EMAs, SMA, Bollinger Bands on DataFrame."""
    c = df["Close"].values.astype(float)
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    v = df["Volume"].values.astype(float)

    # VWAP (cumulative)
    tp = (h + l + c) / 3
    cum_tpv = np.cumsum(tp * v)
    cum_v = np.cumsum(v)
    df["VWAP"] = np.where(cum_v > 0, cum_tpv / cum_v, c)

    # EMAs
    for period in [9, 21, 50, 200]:
        if len(c) >= period:
            ema = pd.Series(c).ewm(span=period, adjust=False).mean().values
            df[f"EMA_{period}"] = ema

    # SMA 20
    if len(c) >= 20:
        df["SMA_20"] = pd.Series(c).rolling(20).mean().values

    # Bollinger Bands
    if len(c) >= 20:
        sma20 = pd.Series(c).rolling(20).mean()
        std20 = pd.Series(c).rolling(20).std()
        df["BB_upper"] = (sma20 + 2 * std20).values
        df["BB_lower"] = (sma20 - 2 * std20).values
        df["BB_mid"] = sma20.values

    # RSI
    if len(c) >= 14:
        delta = pd.Series(c).diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        df["RSI"] = (100 - 100 / (1 + rs)).values

    # MACD
    if len(c) >= 26:
        ema12 = pd.Series(c).ewm(span=12, adjust=False).mean()
        ema26 = pd.Series(c).ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal_line = macd.ewm(span=9, adjust=False).mean()
        df["MACD"] = macd.values
        df["MACD_signal"] = signal_line.values
        df["MACD_hist"] = (macd - signal_line).values

    return df


def safe_download(sym, period, interval, prepost=False):
    try:
        raw = yf.download(sym, period=period, interval=interval,
                          prepost=prepost, auto_adjust=True, progress=False)
    except Exception as e:
        return None, str(e)
    if raw is None or raw.empty:
        return None, "Empty"
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.loc[:, ~raw.columns.duplicated(keep='first')]
    rename = {}
    for c in raw.columns:
        cl = str(c).lower().strip()
        if cl == 'open': rename[c] = 'Open'
        elif cl == 'high': rename[c] = 'High'
        elif cl == 'low': rename[c] = 'Low'
        elif cl in ('close', 'adj close'): rename[c] = 'Close'
        elif cl == 'volume': rename[c] = 'Volume'
    raw = raw.rename(columns=rename)
    needed = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing = [c for c in needed if c not in raw.columns]
    if missing: return None, f"Missing: {missing}"
    df = raw[needed].copy()
    for col in needed:
        s = df[col]
        if isinstance(s, pd.DataFrame): s = s.iloc[:, 0]
        df[col] = pd.to_numeric(s, errors='coerce')
    df['Volume'] = df['Volume'].fillna(0)
    df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
    return df, None


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
        df = df.resample(config["resample"]).agg(
            {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()

    if len(df) < 50: return {"error": f"Only {len(df)} bars for {sym} on {interval}. Need 50+."}

    t0 = time.time()
    try:
        df = indicator.compute(df)
    except Exception as e:
        return {"error": f"Engine error: {str(e)} | {traceback.format_exc()[-400:]}"}

    df = compute_technicals(df)
    calc_time = time.time() - t0

    # Build response
    bars, signals = [], []
    factor_cols = ["NAU_Kalman_Score","NAU_Wavelet_Score","NAU_HMM_Score","NAU_Entropy_Score",
                   "NAU_Hurst_Score","NAU_Fractal_Score","NAU_OB_Score","NAU_FVG_Score",
                   "NAU_Structure_Score","NAU_Williams_Score","NAU_Attention_Score","NAU_RL_Score",
                   "NAU_DeepRegime_Score","NAU_OrderFlow_Score","NAU_MicroStructure_Score","NAU_MTF_Score"]
    all_cols = ["NAU_Signal","NAU_Confidence","NAU_Regime","NAU_Kalman"] + factor_cols + \
               ["VWAP","EMA_9","EMA_21","EMA_50","EMA_200","SMA_20","BB_upper","BB_lower","BB_mid",
                "RSI","MACD","MACD_signal","MACD_hist"]

    for idx, row in df.iterrows():
        try: ts = int(idx.timestamp())
        except: ts = int(pd.Timestamp(idx).timestamp())
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

    # SL/TP — only for CURRENT signal (last 5 bars), not historical
    sl_tp = None
    last = df.iloc[-1]
    sig_val = float(last["NAU_Signal"])
    conf_val = float(last["NAU_Confidence"])
    current_label = signal_label(sig_val, conf_val)
    if current_label not in ("NEUTRAL",) and signals:
        ls = signals[-1]
        last_bar_time = bars[-1]["time"] if bars else 0
        # Only show SL/TP if the last signal is recent (within last 5 bars)
        bar_times = [b["time"] for b in bars[-6:]] if len(bars) >= 6 else [b["time"] for b in bars]
        if ls["time"] in bar_times or ls["time"] >= bar_times[0]:
            atr = np.mean([bars[i]["high"]-bars[i]["low"] for i in range(max(0,len(bars)-14),len(bars))])
            e = bars[-1]["close"]  # Use CURRENT price as entry, not historical signal price
            if current_label in ("COMPRA FUERTE", "COMPRA"):
                sl_tp = {"type":"LONG","entry":round(e,4),"sl":round(e-1.5*atr,4),
                         "tp1":round(e+2*atr,4),"tp2":round(e+3*atr,4),"tp3":round(e+4.5*atr,4),"atr":round(atr,4)}
            elif current_label in ("VENTA FUERTE", "VENTA"):
                sl_tp = {"type":"SHORT","entry":round(e,4),"sl":round(e+1.5*atr,4),
                         "tp1":round(e-2*atr,4),"tp2":round(e-3*atr,4),"tp3":round(e-4.5*atr,4),"atr":round(atr,4)}

    factors_dict = {}
    for col in factor_cols:
        if col in df.columns and pd.notna(last.get(col)):
            factors_dict[col.replace("NAU_","").replace("_Score","")] = round(float(last[col]),1)

    summary = {
        "symbol":sym,"interval":interval,"bars_count":len(bars),
        "signal":round(sig_val,1),"confidence":round(conf_val*100,1),
        "regime":int(last["NAU_Regime"]),
        "regime_name":{0:"BULL",1:"BEAR",2:"RANGE"}.get(int(last["NAU_Regime"]),"RANGE"),
        "label":signal_label(sig_val, conf_val),
        "total_long":int(df["NAU_Long"].sum()),"total_short":int(df["NAU_Short"].sum()),
        "last_price":round(float(last["Close"]),4),
        "timing":{"download":round(dl_time,2),"compute":round(calc_time,2)},
    }

    explanation = generate_explanation(summary, sl_tp, factors_dict)

    result = {"bars":bars,"signals":signals,"sl_tp":sl_tp,"summary":summary,
              "explanation":explanation,"factors":factors_dict}
    cache_set(ck, result)
    return result


# ═══ ENDPOINTS ═══

@app.get("/api/chart")
def get_chart(symbol:str=Query("AAPL"), interval:str=Query("1d"), prepost:bool=Query(False)):
    try: return download_and_compute(symbol.upper().strip(), interval, prepost)
    except Exception as e: return {"error":f"Server error: {str(e)}"}

@app.get("/api/search")
def search_symbols(q:str=Query("")):
    if len(q) < 1: return {"results": SYMBOLS_DB[:20]}
    ql = q.lower()
    results = [s for s in SYMBOLS_DB if ql in s["s"].lower() or ql in s["n"].lower()]
    return {"results": results[:20]}

@app.get("/api/scan")
def scan_stocks(interval:str=Query("1d"), min_confidence:float=Query(60)):
    scan_list = ["AAPL","MSFT","NVDA","GOOGL","META","TSLA","PLTR","AMD","NFLX","MU",
                 "INTC","AVGO","QCOM","CRM","JPM","BAC","GS","V","MA","COIN",
                 "JNJ","UNH","LLY","XOM","CVX","WMT","COST","AMZN","DIS","HD",
                 "SPY","QQQ","IWM","SOXX","BTC-USD","ETH-USD","SOL-USD"]
    results = []
    for sym in scan_list:
        try:
            data = download_and_compute(sym, interval, False)
            if "error" in data: continue
            s = data["summary"]
            if s["confidence"] >= min_confidence and abs(s["signal"]) > 20 and s.get("label","NEUTRAL") != "NEUTRAL":
                entry_info = data.get("sl_tp") or {}
                # Build reasoning
                factors = data.get("factors", {})
                top3 = sorted(factors.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
                reason_parts = [f"{k}: {v:+.0f}" for k, v in top3]
                reasoning = f"{s['label']} | Régimen: {s['regime_name']} | Factores: {', '.join(reason_parts)}"

                results.append({
                    "symbol":sym,"sector":next((x["sec"] for x in SYMBOLS_DB if x["s"]==sym),"Other"),
                    "signal":s["signal"],"confidence":s["confidence"],
                    "regime":s["regime_name"],"label":s["label"],
                    "direction":"LONG" if s["signal"]>0 else "SHORT",
                    "price":s["last_price"],
                    "entry":entry_info.get("entry",s["last_price"]),
                    "sl":entry_info.get("sl",0),"tp1":entry_info.get("tp1",0),
                    "tp2":entry_info.get("tp2",0),"tp3":entry_info.get("tp3",0),
                    "reasoning":reasoning,
                    "score":round(abs(s["signal"])*(s["confidence"]/100),1),
                })
        except: continue
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"scan_results":results[:20],"total_scanned":len(scan_list),"timestamp":int(time.time())}

@app.get("/api/health")
def health():
    return {"status":"ok","version":"5.0","engine":"Sentinel Quantum Edge — 18 Factor AI/ML",
            "cache_entries":len(CACHE)}

@app.get("/")
def root():
    if os.path.exists("/app/static/index.html"):
        return FileResponse("/app/static/index.html")
    return {"message":"NAU Quantum v5.0 API","docs":"/docs"}

# Serve static files
if os.path.exists("/app/static"):
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000, workers=4)
