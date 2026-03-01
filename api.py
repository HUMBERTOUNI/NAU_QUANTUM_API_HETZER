"""
NAU Quantum v5.1 "Sentinel Quantum Edge" — FastAPI Backend
Scanner PRO: NASDAQ100 + S&P500 + DOW30 + Russell2000 + ETFs + Crypto
Parallel scanning with ThreadPoolExecutor (10 workers)
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import yfinance as yf
import pandas as pd
import numpy as np
import traceback, time, os, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from nau_quantum_engine import NAUQuantumAlphaIndicator

app = FastAPI(title="NAU Quantum v5.1 — Sentinel Quantum Edge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CACHE = {}
CACHE_TTL = 90

def cache_get(key):
    if key in CACHE and time.time() - CACHE[key][1] < CACHE_TTL:
        return CACHE[key][0]
    return None

def cache_set(key, data):
    CACHE[key] = (data, time.time())

# ══════════════════════════════════════════════════════════════
# COMPLETE US MARKET UNIVERSE — 200+ stocks by Index
# ══════════════════════════════════════════════════════════════

NASDAQ_100 = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","AVGO","TSLA","COST","NFLX",
    "AMD","ADBE","QCOM","PEP","CSCO","INTC","INTU","CMCSA","TMUS","TXN",
    "AMAT","ISRG","AMGN","MU","LRCX","ADI","BKNG","KLAC","PANW","SBUX",
    "MDLZ","ADP","GILD","REGN","SNPS","CDNS","MRVL","CRWD","PYPL","ORLY",
    "MNST","MELI","CSX","MAR","ABNB","CTAS","CPRT","PCAR","NXPI","MCHP",
    "FTNT","DASH","DXCM","ROST","ODFL","PAYX","WDAY","FANG","MRNA","FAST",
    "KHC","KDP","VRSK","EXC","XEL","GEHC","IDXX","CTSH","ON","ANSS",
    "CDW","BKR","DDOG","BIIB","ZS","ILMN","CEG","TEAM","TTD","SMCI",
    "ARM","PLTR","COIN","CRM","NOW","SHOP","NET","SNOW","SQ","UBER",
    "DELL","ANET","ORCL","IBM","WDC",
]

SP500_EXTRA = [
    "JPM","V","MA","UNH","JNJ","PG","HD","BAC","XOM","CVX",
    "MRK","LLY","ABBV","PFE","TMO","ABT","DHR","WMT","DIS","MCD",
    "NKE","KO","WFC","MS","GS","C","AXP","SCHW","BLK","CB",
    "MMC","PGR","TRV","AFL","MET","ICE","SPGI","CME","MCO","MSCI",
    "RTX","LMT","BA","GE","CAT","HON","DE","UPS","FDX","UNP",
    "NEE","DUK","SO","D","SRE","AEP","AMT","PLD","CCI","EQIX",
    "SPG","PSA","SYK","MDT","BSX","EW","HCA","CI","ELV","MCK",
    "LIN","SHW","APD","ECL","FCX","NEM","COP","SLB","OXY","EOG",
    "MPC","VLO","PSX","HES","DVN","HAL",
]

DOW_30 = [
    "AAPL","MSFT","AMZN","NVDA","UNH","JNJ","V","JPM","PG","HD",
    "MRK","DIS","MCD","CSCO","VZ","KO","INTC","WMT","BA","CAT",
    "GS","AXP","HON","TRV","IBM","MMM","DOW","NKE","CRM","AMGN",
]

RUSSELL_2000_TOP = [
    "SMCI","CELH","DUOL","FN","CARG","LNTH","RMBS","VCEL","EAT",
    "ACIW","COOP","IPAR","KTOS","MOD","CVLT","PIPR","UFPI","BCC","HUBG",
    "CALM","WFRD","SIG","AIT","CSWI","BMI","BOOT","PRIM","NMIH","LBRT",
]

ETFS = [
    "SPY","QQQ","DIA","IWM","IWF","IWD","VTI","VOO","VTV","VUG",
    "XLK","XLF","XLE","XLV","XLI","XLC","XLY","XLP","XLU","XLRE","XLB",
    "SOXX","SMH","ARKK","ARKW","KWEB","TAN","LIT","ICLN","GLD","SLV",
    "TLT","HYG","LQD","IBIT","BITO",
]

CRYPTO = [
    "BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD",
    "DOGE-USD","AVAX-USD","LINK-USD","UNI-USD",
]

INDICES_LIST = ["^GSPC","^DJI","^IXIC","^RUT","^VIX"]
COMM_FX = ["GC=F","SI=F","CL=F","NG=F","EURUSD=X","GBPUSD=X","USDJPY=X"]

# ── Index MEMBERSHIP sets (a stock can belong to multiple indices) ──
# The FULL S&P 500 includes most NASDAQ100 stocks + SP500_EXTRA
SP500_FULL = list(set(NASDAQ_100 + SP500_EXTRA))  # ~180 of the top S&P 500
DOW30_SET = set(DOW_30)

INDEX_MEMBERSHIP = {}  # symbol -> set of index names
for s in NASDAQ_100: INDEX_MEMBERSHIP.setdefault(s, set()).add("NASDAQ100")
for s in SP500_FULL: INDEX_MEMBERSHIP.setdefault(s, set()).add("S&P500")
for s in DOW_30: INDEX_MEMBERSHIP.setdefault(s, set()).add("DOW30")
for s in RUSSELL_2000_TOP: INDEX_MEMBERSHIP.setdefault(s, set()).add("RUSSELL2000")
for s in ETFS: INDEX_MEMBERSHIP.setdefault(s, set()).add("ETF")
for s in CRYPTO: INDEX_MEMBERSHIP.setdefault(s, set()).add("CRYPTO")
for s in INDICES_LIST: INDEX_MEMBERSHIP.setdefault(s, set()).add("INDEX")
for s in COMM_FX: INDEX_MEMBERSHIP.setdefault(s, set()).add("COMM/FX")

def build_scan_universe():
    """Build deduplicated scan list. Each stock has ALL its index memberships."""
    seen = set()
    universe = []
    all_syms = NASDAQ_100 + SP500_EXTRA + DOW_30 + RUSSELL_2000_TOP + ETFS + CRYPTO + INDICES_LIST + COMM_FX
    for s in all_syms:
        if s not in seen:
            seen.add(s)
            indices = INDEX_MEMBERSHIP.get(s, {"OTHER"})
            universe.append({"s": s, "idx": " · ".join(sorted(indices))})
    return universe

SCAN_UNIVERSE = build_scan_universe()

def filter_universe(index_filter):
    """Filter universe by index membership (not just primary tag)."""
    if index_filter == "ALL":
        return SCAN_UNIVERSE
    return [u for u in SCAN_UNIVERSE if index_filter in INDEX_MEMBERSHIP.get(u["s"], set())]

# Symbol DB for search
SYMBOLS_DB = [
    {"s":"AAPL","n":"Apple Inc","sec":"NASDAQ100"},{"s":"MSFT","n":"Microsoft","sec":"NASDAQ100"},
    {"s":"NVDA","n":"NVIDIA Corp","sec":"NASDAQ100"},{"s":"GOOGL","n":"Alphabet Google","sec":"NASDAQ100"},
    {"s":"META","n":"Meta Platforms","sec":"NASDAQ100"},{"s":"TSLA","n":"Tesla","sec":"NASDAQ100"},
    {"s":"PLTR","n":"Palantir","sec":"NASDAQ100"},{"s":"AMD","n":"Advanced Micro Devices","sec":"NASDAQ100"},
    {"s":"INTC","n":"Intel Corp","sec":"NASDAQ100"},{"s":"CRM","n":"Salesforce","sec":"NASDAQ100"},
    {"s":"NFLX","n":"Netflix","sec":"NASDAQ100"},{"s":"AVGO","n":"Broadcom","sec":"NASDAQ100"},
    {"s":"QCOM","n":"Qualcomm","sec":"NASDAQ100"},{"s":"MU","n":"Micron Technology","sec":"NASDAQ100"},
    {"s":"ORCL","n":"Oracle","sec":"NASDAQ100"},{"s":"ADBE","n":"Adobe","sec":"NASDAQ100"},
    {"s":"CSCO","n":"Cisco Systems","sec":"NASDAQ100"},{"s":"IBM","n":"IBM","sec":"S&P500"},
    {"s":"UBER","n":"Uber Technologies","sec":"NASDAQ100"},{"s":"SHOP","n":"Shopify","sec":"NASDAQ100"},
    {"s":"SQ","n":"Block Square","sec":"NASDAQ100"},{"s":"SNOW","n":"Snowflake","sec":"NASDAQ100"},
    {"s":"NET","n":"Cloudflare","sec":"NASDAQ100"},{"s":"PANW","n":"Palo Alto Networks","sec":"NASDAQ100"},
    {"s":"CRWD","n":"CrowdStrike","sec":"NASDAQ100"},{"s":"DDOG","n":"Datadog","sec":"NASDAQ100"},
    {"s":"ZS","n":"Zscaler","sec":"NASDAQ100"},{"s":"MRVL","n":"Marvell Technology","sec":"NASDAQ100"},
    {"s":"ON","n":"ON Semiconductor","sec":"NASDAQ100"},{"s":"ARM","n":"ARM Holdings","sec":"NASDAQ100"},
    {"s":"SMCI","n":"Super Micro Computer","sec":"RUSSELL2000"},{"s":"DELL","n":"Dell","sec":"NASDAQ100"},
    {"s":"NOW","n":"ServiceNow","sec":"NASDAQ100"},{"s":"INTU","n":"Intuit","sec":"NASDAQ100"},
    {"s":"COIN","n":"Coinbase","sec":"NASDAQ100"},{"s":"ANET","n":"Arista Networks","sec":"NASDAQ100"},
    {"s":"AMZN","n":"Amazon","sec":"NASDAQ100"},{"s":"COST","n":"Costco","sec":"NASDAQ100"},
    {"s":"AMGN","n":"Amgen","sec":"NASDAQ100"},{"s":"ISRG","n":"Intuitive Surgical","sec":"NASDAQ100"},
    {"s":"ABNB","n":"Airbnb","sec":"NASDAQ100"},{"s":"DASH","n":"DoorDash","sec":"NASDAQ100"},
    {"s":"MELI","n":"MercadoLibre","sec":"NASDAQ100"},{"s":"TTD","n":"Trade Desk","sec":"NASDAQ100"},
    {"s":"TEAM","n":"Atlassian","sec":"NASDAQ100"},{"s":"WDAY","n":"Workday","sec":"NASDAQ100"},
    {"s":"JPM","n":"JPMorgan Chase","sec":"S&P500"},{"s":"BAC","n":"Bank of America","sec":"S&P500"},
    {"s":"GS","n":"Goldman Sachs","sec":"DOW30"},{"s":"MS","n":"Morgan Stanley","sec":"S&P500"},
    {"s":"V","n":"Visa","sec":"DOW30"},{"s":"MA","n":"Mastercard","sec":"S&P500"},
    {"s":"C","n":"Citigroup","sec":"S&P500"},{"s":"WFC","n":"Wells Fargo","sec":"S&P500"},
    {"s":"AXP","n":"American Express","sec":"DOW30"},{"s":"SCHW","n":"Charles Schwab","sec":"S&P500"},
    {"s":"BLK","n":"BlackRock","sec":"S&P500"},{"s":"PYPL","n":"PayPal","sec":"S&P500"},
    {"s":"JNJ","n":"Johnson Johnson","sec":"DOW30"},{"s":"UNH","n":"UnitedHealth","sec":"DOW30"},
    {"s":"LLY","n":"Eli Lilly","sec":"S&P500"},{"s":"ABBV","n":"AbbVie","sec":"S&P500"},
    {"s":"PFE","n":"Pfizer","sec":"S&P500"},{"s":"MRK","n":"Merck","sec":"DOW30"},
    {"s":"TMO","n":"Thermo Fisher","sec":"S&P500"},{"s":"ABT","n":"Abbott Labs","sec":"S&P500"},
    {"s":"XOM","n":"Exxon Mobil","sec":"S&P500"},{"s":"CVX","n":"Chevron","sec":"S&P500"},
    {"s":"OXY","n":"Occidental Petroleum","sec":"S&P500"},{"s":"COP","n":"ConocoPhillips","sec":"S&P500"},
    {"s":"SLB","n":"Schlumberger","sec":"S&P500"},{"s":"WMT","n":"Walmart","sec":"DOW30"},
    {"s":"DIS","n":"Walt Disney","sec":"DOW30"},{"s":"MCD","n":"McDonald's","sec":"DOW30"},
    {"s":"KO","n":"Coca-Cola","sec":"DOW30"},{"s":"PEP","n":"PepsiCo","sec":"NASDAQ100"},
    {"s":"NKE","n":"Nike","sec":"DOW30"},{"s":"HD","n":"Home Depot","sec":"DOW30"},
    {"s":"BA","n":"Boeing","sec":"DOW30"},{"s":"CAT","n":"Caterpillar","sec":"DOW30"},
    {"s":"HON","n":"Honeywell","sec":"DOW30"},{"s":"GE","n":"GE Aerospace","sec":"S&P500"},
    {"s":"RTX","n":"RTX Corp","sec":"S&P500"},{"s":"LMT","n":"Lockheed Martin","sec":"S&P500"},
    {"s":"LIN","n":"Linde","sec":"S&P500"},{"s":"NEE","n":"NextEra Energy","sec":"S&P500"},
    {"s":"PG","n":"Procter Gamble","sec":"DOW30"},
    {"s":"SPY","n":"S&P 500 ETF","sec":"ETF"},{"s":"QQQ","n":"Nasdaq 100 ETF","sec":"ETF"},
    {"s":"IWM","n":"Russell 2000 ETF","sec":"ETF"},{"s":"DIA","n":"Dow Jones ETF","sec":"ETF"},
    {"s":"SOXX","n":"Semiconductor ETF","sec":"ETF"},{"s":"ARKK","n":"ARK Innovation","sec":"ETF"},
    {"s":"XLF","n":"Financial ETF","sec":"ETF"},{"s":"XLE","n":"Energy ETF","sec":"ETF"},
    {"s":"XLK","n":"Technology ETF","sec":"ETF"},{"s":"GLD","n":"Gold ETF","sec":"ETF"},
    {"s":"SLV","n":"Silver ETF","sec":"ETF"},{"s":"TLT","n":"Treasury Bond ETF","sec":"ETF"},
    {"s":"VTI","n":"Total Market ETF","sec":"ETF"},{"s":"VOO","n":"Vanguard S&P500","sec":"ETF"},
    {"s":"IBIT","n":"iShares Bitcoin ETF","sec":"ETF"},{"s":"SMH","n":"VanEck Semiconductor","sec":"ETF"},
    {"s":"BTC-USD","n":"Bitcoin","sec":"CRYPTO"},{"s":"ETH-USD","n":"Ethereum","sec":"CRYPTO"},
    {"s":"SOL-USD","n":"Solana","sec":"CRYPTO"},{"s":"BNB-USD","n":"Binance Coin","sec":"CRYPTO"},
    {"s":"XRP-USD","n":"Ripple XRP","sec":"CRYPTO"},{"s":"ADA-USD","n":"Cardano","sec":"CRYPTO"},
    {"s":"DOGE-USD","n":"Dogecoin","sec":"CRYPTO"},{"s":"AVAX-USD","n":"Avalanche","sec":"CRYPTO"},
    {"s":"^GSPC","n":"S&P 500 Index","sec":"INDEX"},{"s":"^DJI","n":"Dow Jones","sec":"INDEX"},
    {"s":"^IXIC","n":"Nasdaq Composite","sec":"INDEX"},{"s":"^RUT","n":"Russell 2000","sec":"INDEX"},
    {"s":"^VIX","n":"VIX Volatility","sec":"INDEX"},
    {"s":"GC=F","n":"Gold Futures","sec":"COMM"},{"s":"SI=F","n":"Silver Futures","sec":"COMM"},
    {"s":"CL=F","n":"Crude Oil","sec":"COMM"},{"s":"EURUSD=X","n":"EUR/USD","sec":"FOREX"},
    {"s":"GBPUSD=X","n":"GBP/USD","sec":"FOREX"},{"s":"USDJPY=X","n":"USD/JPY","sec":"FOREX"},
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
        lines += [f"Factores divididos: {bullish} alcistas, {bearish} bajistas, {neutral} neutrales.",
                  "Esperar confluencia > 65%."]
    return "\n".join(lines)

def compute_technicals(df):
    c = df["Close"].values.astype(float)
    h, l, v = df["High"].values.astype(float), df["Low"].values.astype(float), df["Volume"].values.astype(float)
    tp = (h + l + c) / 3
    cv = np.cumsum(v)
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

def safe_download(sym, period, interval, prepost=False):
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
        df = df.resample(config["resample"]).agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
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

    summary = {"symbol":sym,"interval":interval,"bars_count":len(bars),
        "signal":round(sig_val,1),"confidence":round(conf_val*100,1),
        "regime":int(last["NAU_Regime"]),
        "regime_name":{0:"BULL",1:"BEAR",2:"RANGE"}.get(int(last["NAU_Regime"]),"RANGE"),
        "label":current_label,"last_price":round(float(last["Close"]),4),
        "timing":{"download":round(dl_time,2),"compute":round(calc_time,2)}}

    explanation = generate_explanation(summary, sl_tp, factors_dict)
    result = {"bars":bars,"signals":signals,"sl_tp":sl_tp,"summary":summary,
              "explanation":explanation,"factors":factors_dict}
    cache_set(ck, result)
    return result

# ══════════════════════════════════════════════════
# PROFESSIONAL PARALLEL SCANNER
# ══════════════════════════════════════════════════

def scan_one(sym_info, interval, min_conf):
    sym = sym_info["s"]
    idx_label = " · ".join(sorted(INDEX_MEMBERSHIP.get(sym, {"OTHER"})))
    try:
        data = download_and_compute(sym, interval, False)
        if "error" in data: return None
        s = data["summary"]
        if s["confidence"] < min_conf or abs(s["signal"]) < 15 or s["label"] == "NEUTRAL":
            return None
        ei = data.get("sl_tp") or {}
        f = data.get("factors", {})
        top5 = sorted(f.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        reasoning = f"{s['label']} | {s['regime_name']} | " + ", ".join(f"{k}:{v:+.0f}" for k,v in top5)
        return {"symbol":sym,"index":idx_label,"signal":s["signal"],"confidence":s["confidence"],
                "regime":s["regime_name"],"label":s["label"],
                "direction":"LONG" if s["signal"]>0 else "SHORT",
                "price":s["last_price"],"entry":ei.get("entry",s["last_price"]),
                "sl":ei.get("sl",0),"tp1":ei.get("tp1",0),"tp2":ei.get("tp2",0),"tp3":ei.get("tp3",0),
                "reasoning":reasoning,"score":round(abs(s["signal"])*(s["confidence"]/100),1)}
    except:
        return None

@app.get("/api/scan")
def scan_stocks(interval:str=Query("1d"), min_confidence:float=Query(55), index:str=Query("ALL")):
    universe = filter_universe(index)
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(scan_one, si, interval, min_confidence): si for si in universe}
        for fut in as_completed(futs):
            r = fut.result()
            if r: results.append(r)
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"scan_results":results[:50],"total_scanned":len(universe),"total_found":len(results),
            "scan_time":round(time.time()-t0,1),"interval":interval,"index_filter":index,
            "timestamp":int(time.time())}

@app.get("/api/chart")
def get_chart(symbol:str=Query("AAPL"), interval:str=Query("1d"), prepost:bool=Query(False)):
    try: return download_and_compute(symbol.upper().strip(), interval, prepost)
    except Exception as e: return {"error":f"Server error: {str(e)}"}

@app.get("/api/search")
def search_symbols(q:str=Query("")):
    if len(q) < 1: return {"results": SYMBOLS_DB[:20]}
    ql = q.lower()
    return {"results": [s for s in SYMBOLS_DB if ql in s["s"].lower() or ql in s["n"].lower()][:20]}

@app.get("/api/health")
def health():
    return {"status":"ok","version":"5.1","engine":"Sentinel Quantum Edge 18-Factor AI/ML",
            "scan_universe":len(SCAN_UNIVERSE),"cache_entries":len(CACHE)}

@app.get("/")
def root():
    if os.path.exists("/app/static/index.html"): return FileResponse("/app/static/index.html")
    return {"message":"NAU Quantum v5.1 API","docs":"/docs"}

if os.path.exists("/app/static"):
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000, workers=4)
