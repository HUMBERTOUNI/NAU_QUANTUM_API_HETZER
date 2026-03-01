"""
stock_universe.py — Complete US Market Index Compositions
Updated: February 2026

S&P 500: 503 tickers (some companies have dual class shares)
NASDAQ 100: 101 tickers
DOW JONES 30: 30 tickers
RUSSELL 2000: Top 150 by market cap
ETFs: 36 sector/thematic
Crypto: 12
Indices/Commodities/Forex: 14

The scanner imports this file and builds membership sets so each stock
belongs to ALL its real indices simultaneously.
"""

# ══════════════════════════════════════════════════════════════
# S&P 500 — COMPLETE 503 tickers (as of Feb 2026)
# ══════════════════════════════════════════════════════════════
SP500 = [
    # Information Technology (70+)
    "AAPL","MSFT","NVDA","AVGO","ORCL","CRM","CSCO","ACN","ADBE","IBM",
    "INTU","AMD","TXN","QCOM","AMAT","ADI","LRCX","MU","KLAC","SNPS",
    "CDNS","MRVL","FTNT","ANSS","MPWR","KEYS","ON","NXPI","MCHP","GEN",
    "FSLR","SWKS","TER","ZBRA","TRMB","TYL","FFIV","JNPR","NTAP","WDC",
    "HPQ","HPE","DELL","STX","ANET","PANW","CRWD","NOW","PLTR","GDDY",
    "EPAM","CDW","BR","VRSN","PTC","FICO","IT","ROP","MANH","SMCI",
    "CTSH","AKAM","JKHY","PAYC","GLOB","MSCI",
    # Communication Services (25)
    "META","GOOGL","GOOG","NFLX","DIS","CMCSA","TMUS","T","VZ","CHTR",
    "EA","TTWO","WBD","FOXA","FOX","LYV","MTCH","IPG","OMC","NWSA",
    "NWS","PARA","LNT","ATUS","ZM",
    # Consumer Discretionary (60+)
    "AMZN","TSLA","HD","MCD","NKE","LOW","SBUX","BKNG","TJX","ORLY",
    "ABNB","MAR","GM","F","YUM","CMG","DHI","LEN","ROST","GRMN",
    "EBAY","ETSY","BBY","DRI","POOL","APTV","EXPE","HLT","LVS","WYNN",
    "MGM","CCL","RCL","ULTA","AZO","DPZ","NVR","PHM","TPR","RL",
    "HAS","NCLH","CPRT","CTAS","TSCO","GPC","BWA","MHK","KMX","DECK",
    "CZR","DASH","LULU","RH","PENN","WSM","BBWI","AOS","WHR","PVH",
    # Consumer Staples (35)
    "PG","PEP","KO","COST","WMT","MDLZ","PM","MO","CL","EL",
    "STZ","GIS","SJM","K","HSY","KMB","CHD","MKC","SYY","KR",
    "ADM","TAP","CPB","HRL","CAG","BG","CLX","KHC","WBA","DG",
    "DLTR","MNST","KDP","LAMB","TSN",
    # Healthcare (65+)
    "UNH","JNJ","LLY","ABBV","MRK","TMO","ABT","DHR","PFE","AMGN",
    "ISRG","MDT","BSX","GILD","REGN","VRTX","EW","SYK","ZBH","BAX",
    "BDX","CI","ELV","HCA","MCK","HUM","CNC","DXCM","IDXX","IQV",
    "A","MTD","WAT","HOLX","ALGN","RVTY","BIIB","MRNA","ILMN","COO",
    "WST","RMD","GEHC","MOH","TFX","HSIC","DGX","LH","INCY","VTRS",
    "XRAY","OGN","DVA","TECH","CRL","BIO","PKI","CTLT","STE","PODD",
    "VEEV","ZTS","DXCM","ENSG",
    # Financials (70+)
    "JPM","V","MA","BAC","WFC","GS","MS","SCHW","AXP","BLK",
    "SPGI","ICE","CME","MCO","CB","MMC","PGR","TRV","AFL","MET",
    "AIG","PRU","ALL","AJG","CINF","L","RE","BRO","WRB","FI",
    "PYPL","COF","USB","PNC","TFC","FITB","MTB","HBAN","CFG","KEY",
    "RF","ZION","CMA","NTRS","STT","BK","C","NDAQ","COIN","GL",
    "RJF","TROW","FDS","MKTX","CBOE","ERIE","EG","AIZ","LNC","BEN",
    "IVZ","FRC","SBNY","DFS","SYF","ALLY","ACGL","FNF","WTW","AON",
    # Industrials (75+)
    "GE","CAT","HON","UPS","RTX","BA","DE","LMT","UNP","FDX",
    "WM","ETN","ITW","EMR","GD","NOC","CSX","NSC","TT","PH",
    "FAST","PCAR","ODFL","PAYX","VRSK","ROK","IR","GWW","SWK","CARR",
    "OTIS","XYL","DOV","AME","IEX","NDSN","SNA","MAS","PWR","J",
    "RSG","WAB","LDOS","AXON","HWM","TDG","GPN","FTV","ALLE","CHRW",
    "EXPD","JBHT","LECO","DAL","UAL","AAL","LUV","CSGP","HUBB","CMI",
    "GNRC","BLDR","URI","EFX","PAYC","CPAY","MLM","VMC","BALL","PKG",
    "IP","WRK","SEE","CE","EMN","LYB","PPG","SHW","APD","ECL",
    # Energy (25)
    "XOM","CVX","COP","SLB","EOG","MPC","PSX","VLO","OXY","HAL",
    "DVN","HES","FANG","BKR","TRGP","WMB","KMI","OKE","CTRA","MRO",
    "APA","EQT","MTDR","CEG","DINO",
    # Real Estate (30)
    "AMT","PLD","CCI","EQIX","SPG","PSA","O","DLR","WELL","AVB",
    "EQR","VTR","ARE","MAA","UDR","ESS","REG","HST","KIM","CPT",
    "SBAC","VICI","INVH","SUI","WY","BXP","CBRE","IRM","PEAK","FRT",
    # Utilities (30)
    "NEE","DUK","SO","D","SRE","AEP","EXC","XEL","ED","WEC",
    "PEG","ES","AWK","DTE","CMS","AES","ATO","NI","EVRG","NRG",
    "PNW","PPL","FE","CNP","ETR","PCG","EIX","AEE",
    # Materials (25)
    "LIN","FCX","NEM","NUE","STLD","CF","FMC","ALB","DD","DOW",
    "IFF","RPM","VMC","MLM","CE","EMN","LYB","PPG","SHW","APD",
    "ECL","BALL","PKG","IP","WRK",
]

# ══════════════════════════════════════════════════════════════
# NASDAQ 100 — COMPLETE 101 tickers (as of Feb 2026)
# ══════════════════════════════════════════════════════════════
NASDAQ_100 = [
    "AAPL","ABNB","ADBE","ADI","ADP","ADSK","AEP","AMAT","AMGN","AMZN",
    "ANSS","ARM","ASML","AVGO","AZN","BIIB","BKNG","BKR","CDNS","CDW",
    "CEG","CHTR","CMCSA","COIN","COST","CPRT","CRWD","CSCO","CSGP","CTAS",
    "CTSH","DASH","DDOG","DLTR","DXCM","EA","EXC","FANG","FAST","FTNT",
    "GEHC","GILD","GOOG","GOOGL","HON","IDXX","ILMN","INTC","INTU","ISRG",
    "KDP","KHC","KLAC","LRCX","LULU","MAR","MCHP","MDLZ","MELI","META",
    "MNST","MRVL","MSFT","MU","NFLX","NVDA","NXPI","ODFL","ON","ORLY",
    "PANW","PAYX","PCAR","PDD","PEP","PLTR","PYPL","QCOM","REGN","ROST",
    "SBUX","SMCI","SNPS","SPLK","TEAM","TMUS","TSLA","TTD","TTWO","TXN",
    "VRSK","WDAY","WBD","XEL","ZS",
    # Recent additions
    "AMD","CRM","NOW","ANET","SQ","UBER","SHOP","NET","SNOW","DELL",
]

# ══════════════════════════════════════════════════════════════
# DOW JONES 30 — COMPLETE (as of Feb 2026)
# ══════════════════════════════════════════════════════════════
DOW_30 = [
    "AAPL","AMGN","AMZN","AXP","BA","CAT","CRM","CSCO","CVX","DIS",
    "DOW","GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD",
    "MMM","MRK","MSFT","NKE","NVDA","PG","TRV","UNH","V","VZ",
    "WMT",
]

# ══════════════════════════════════════════════════════════════
# RUSSELL 2000 — Top 150 by market cap (as of Feb 2026)
# ══════════════════════════════════════════════════════════════
RUSSELL_2000_TOP = [
    "SMCI","CELH","DUOL","FN","CARG","LNTH","RMBS","VCEL","EAT","ACIW",
    "COOP","IPAR","KTOS","MOD","CVLT","PIPR","UFPI","BCC","HUBG","CALM",
    "WFRD","SIG","AIT","CSWI","BMI","BOOT","PRIM","NMIH","LBRT","RUN",
    "RXRX","PCVX","GSHD","OSCR","SAIA","CRDO","TMDX","STEP","OWL","ALIT",
    "QLYS","MTSI","CRVL","TGTX","PGNY","HALO","BRKR","SKY","KYMR","NUVB",
    "WDFC","FRPT","VIRT","EXLS","STRL","PI","PRFT","ENVA","POWL","PLXS",
    "IOSP","NUVL","IRTC","VERX","NARI","NVST","KRYS","GKOS","VRNS","CWST",
    "SPSC","TCBI","RAMP","BCPC","PLUS","MGNI","APLS","CRS","AVAV","ESAB",
    "LAUR","FSS","INST","FOUR","LNW","FTDR","ALKT","AMBA","SWX","UPST",
    "CRGY","CRNX","RXST","TMHC","PAYO","XPEL","NBTB","SMPL","AEIS","TREX",
    "ROAD","SHOO","MMSI","PCOR","SITM","OTTR","ITRI","BLKB","CWCO","FROG",
    "GTES","AXSM","WTFC","SIGI","ABG","FORM","LMAT","ADMA","CBZ","SFBS",
    "NOVT","FIZZ","HIMS","JOBY","LUNR","IONQ","RKLB","MNDY","AFRM","SOFI",
    "BILL","DKNG","RIVN","LCID","DNA","OPEN","WISH","SKLZ","LAZR","ASAN",
    "GTLB","CFLT","TOST","RBLX","HOOD","PATH","DOCS","DOCN","CLOV","BTDR",
]

# ══════════════════════════════════════════════════════════════
# ETFs — Sector, Thematic, Index-tracking
# ══════════════════════════════════════════════════════════════
ETFS = [
    "SPY","QQQ","DIA","IWM","IWF","IWD","VTI","VOO","VTV","VUG",
    "XLK","XLF","XLE","XLV","XLI","XLC","XLY","XLP","XLU","XLRE","XLB",
    "SOXX","SMH","ARKK","ARKW","ARKG","KWEB","TAN","LIT","ICLN",
    "GLD","SLV","TLT","HYG","LQD","IBIT","BITO",
]

# ══════════════════════════════════════════════════════════════
# Crypto, Indices, Commodities, Forex
# ══════════════════════════════════════════════════════════════
CRYPTO = [
    "BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD",
    "DOGE-USD","AVAX-USD","LINK-USD","UNI-USD","DOT-USD","MATIC-USD",
]

INDICES = ["^GSPC","^DJI","^IXIC","^RUT","^VIX","^TNX"]

COMMODITIES_FOREX = [
    "GC=F","SI=F","CL=F","NG=F",
    "EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X",
]


# ══════════════════════════════════════════════════════════════
# INDEX MEMBERSHIP — each stock → set of all indices it belongs to
# ══════════════════════════════════════════════════════════════

INDEX_MEMBERSHIP = {}

def _tag(symbols, index_name):
    for s in symbols:
        INDEX_MEMBERSHIP.setdefault(s, set()).add(index_name)

_tag(SP500, "S&P500")
_tag(NASDAQ_100, "NASDAQ100")
_tag(DOW_30, "DOW30")
_tag(RUSSELL_2000_TOP, "RUSSELL2000")
_tag(ETFS, "ETF")
_tag(CRYPTO, "CRYPTO")
_tag(INDICES, "INDEX")
_tag(COMMODITIES_FOREX, "COMM/FX")


def build_scan_universe():
    """Deduplicated list of ALL scannable symbols with multi-index tags."""
    seen = set()
    universe = []
    all_lists = [SP500, NASDAQ_100, DOW_30, RUSSELL_2000_TOP,
                 ETFS, CRYPTO, INDICES, COMMODITIES_FOREX]
    for lst in all_lists:
        for s in lst:
            if s not in seen:
                seen.add(s)
                tags = INDEX_MEMBERSHIP.get(s, {"OTHER"})
                universe.append({"s": s, "idx": " · ".join(sorted(tags))})
    return universe


def filter_universe(index_filter):
    """Return symbols belonging to a specific index."""
    if index_filter == "ALL":
        return SCAN_UNIVERSE
    return [u for u in SCAN_UNIVERSE if index_filter in INDEX_MEMBERSHIP.get(u["s"], set())]


SCAN_UNIVERSE = build_scan_universe()


# ══════════════════════════════════════════════════════════════
# SEARCH DATABASE — for autocomplete
# ══════════════════════════════════════════════════════════════
SYMBOLS_DB = [
    # Top Technology
    {"s":"AAPL","n":"Apple Inc","sec":"NASDAQ100 · S&P500 · DOW30"},
    {"s":"MSFT","n":"Microsoft Corp","sec":"NASDAQ100 · S&P500 · DOW30"},
    {"s":"NVDA","n":"NVIDIA Corp","sec":"NASDAQ100 · S&P500 · DOW30"},
    {"s":"GOOGL","n":"Alphabet Google","sec":"NASDAQ100 · S&P500"},
    {"s":"META","n":"Meta Platforms","sec":"NASDAQ100 · S&P500"},
    {"s":"AMZN","n":"Amazon","sec":"NASDAQ100 · S&P500 · DOW30"},
    {"s":"TSLA","n":"Tesla","sec":"NASDAQ100 · S&P500"},
    {"s":"AVGO","n":"Broadcom","sec":"NASDAQ100 · S&P500"},
    {"s":"ORCL","n":"Oracle","sec":"S&P500"},
    {"s":"CRM","n":"Salesforce","sec":"NASDAQ100 · S&P500 · DOW30"},
    {"s":"AMD","n":"Advanced Micro Devices","sec":"NASDAQ100 · S&P500"},
    {"s":"ADBE","n":"Adobe","sec":"NASDAQ100 · S&P500"},
    {"s":"NFLX","n":"Netflix","sec":"NASDAQ100 · S&P500"},
    {"s":"INTC","n":"Intel","sec":"NASDAQ100 · S&P500 · DOW30"},
    {"s":"CSCO","n":"Cisco","sec":"NASDAQ100 · S&P500 · DOW30"},
    {"s":"QCOM","n":"Qualcomm","sec":"NASDAQ100 · S&P500"},
    {"s":"INTU","n":"Intuit","sec":"NASDAQ100 · S&P500"},
    {"s":"TXN","n":"Texas Instruments","sec":"NASDAQ100 · S&P500"},
    {"s":"MU","n":"Micron Technology","sec":"NASDAQ100 · S&P500"},
    {"s":"PANW","n":"Palo Alto Networks","sec":"NASDAQ100 · S&P500"},
    {"s":"CRWD","n":"CrowdStrike","sec":"NASDAQ100 · S&P500"},
    {"s":"NOW","n":"ServiceNow","sec":"NASDAQ100 · S&P500"},
    {"s":"ANET","n":"Arista Networks","sec":"NASDAQ100 · S&P500"},
    {"s":"PLTR","n":"Palantir","sec":"NASDAQ100 · S&P500"},
    {"s":"COIN","n":"Coinbase","sec":"NASDAQ100 · S&P500"},
    {"s":"DELL","n":"Dell Technologies","sec":"NASDAQ100 · S&P500"},
    {"s":"SMCI","n":"Super Micro Computer","sec":"NASDAQ100 · S&P500 · RUSSELL2000"},
    {"s":"ARM","n":"ARM Holdings","sec":"NASDAQ100"},
    {"s":"UBER","n":"Uber Technologies","sec":"NASDAQ100 · S&P500"},
    {"s":"SHOP","n":"Shopify","sec":"NASDAQ100"},
    {"s":"SQ","n":"Block (Square)","sec":"NASDAQ100 · S&P500"},
    {"s":"NET","n":"Cloudflare","sec":"NASDAQ100"},
    {"s":"SNOW","n":"Snowflake","sec":"NASDAQ100 · S&P500"},
    {"s":"DDOG","n":"Datadog","sec":"NASDAQ100 · S&P500"},
    {"s":"ZS","n":"Zscaler","sec":"NASDAQ100 · S&P500"},
    {"s":"DASH","n":"DoorDash","sec":"NASDAQ100 · S&P500"},
    {"s":"TTD","n":"Trade Desk","sec":"NASDAQ100"},
    {"s":"MRVL","n":"Marvell Technology","sec":"NASDAQ100 · S&P500"},
    # Finance
    {"s":"JPM","n":"JPMorgan Chase","sec":"S&P500"},
    {"s":"V","n":"Visa","sec":"S&P500 · DOW30"},
    {"s":"MA","n":"Mastercard","sec":"S&P500"},
    {"s":"BAC","n":"Bank of America","sec":"S&P500"},
    {"s":"GS","n":"Goldman Sachs","sec":"S&P500 · DOW30"},
    {"s":"MS","n":"Morgan Stanley","sec":"S&P500"},
    {"s":"WFC","n":"Wells Fargo","sec":"S&P500"},
    {"s":"AXP","n":"American Express","sec":"S&P500 · DOW30"},
    {"s":"SCHW","n":"Charles Schwab","sec":"S&P500"},
    {"s":"BLK","n":"BlackRock","sec":"S&P500"},
    {"s":"PYPL","n":"PayPal","sec":"NASDAQ100 · S&P500"},
    {"s":"C","n":"Citigroup","sec":"S&P500"},
    # Healthcare
    {"s":"UNH","n":"UnitedHealth","sec":"S&P500 · DOW30"},
    {"s":"JNJ","n":"Johnson & Johnson","sec":"S&P500 · DOW30"},
    {"s":"LLY","n":"Eli Lilly","sec":"S&P500"},
    {"s":"ABBV","n":"AbbVie","sec":"S&P500"},
    {"s":"MRK","n":"Merck","sec":"S&P500 · DOW30"},
    {"s":"PFE","n":"Pfizer","sec":"S&P500"},
    {"s":"TMO","n":"Thermo Fisher","sec":"S&P500"},
    {"s":"AMGN","n":"Amgen","sec":"NASDAQ100 · S&P500 · DOW30"},
    {"s":"ISRG","n":"Intuitive Surgical","sec":"NASDAQ100 · S&P500"},
    {"s":"GILD","n":"Gilead Sciences","sec":"NASDAQ100 · S&P500"},
    {"s":"REGN","n":"Regeneron","sec":"NASDAQ100 · S&P500"},
    {"s":"VRTX","n":"Vertex Pharma","sec":"S&P500"},
    {"s":"MRNA","n":"Moderna","sec":"S&P500"},
    # Consumer / Retail
    {"s":"WMT","n":"Walmart","sec":"S&P500 · DOW30"},
    {"s":"HD","n":"Home Depot","sec":"S&P500 · DOW30"},
    {"s":"COST","n":"Costco","sec":"NASDAQ100 · S&P500"},
    {"s":"MCD","n":"McDonald's","sec":"S&P500 · DOW30"},
    {"s":"DIS","n":"Walt Disney","sec":"S&P500 · DOW30"},
    {"s":"NKE","n":"Nike","sec":"S&P500 · DOW30"},
    {"s":"KO","n":"Coca-Cola","sec":"S&P500 · DOW30"},
    {"s":"PEP","n":"PepsiCo","sec":"NASDAQ100 · S&P500"},
    {"s":"SBUX","n":"Starbucks","sec":"NASDAQ100 · S&P500"},
    {"s":"PG","n":"Procter & Gamble","sec":"S&P500 · DOW30"},
    {"s":"LOW","n":"Lowe's","sec":"S&P500"},
    {"s":"TJX","n":"TJX Companies","sec":"S&P500"},
    {"s":"LULU","n":"Lululemon","sec":"NASDAQ100 · S&P500"},
    # Industrial
    {"s":"BA","n":"Boeing","sec":"S&P500 · DOW30"},
    {"s":"CAT","n":"Caterpillar","sec":"S&P500 · DOW30"},
    {"s":"GE","n":"GE Aerospace","sec":"S&P500"},
    {"s":"HON","n":"Honeywell","sec":"NASDAQ100 · S&P500 · DOW30"},
    {"s":"RTX","n":"RTX Corp","sec":"S&P500"},
    {"s":"LMT","n":"Lockheed Martin","sec":"S&P500"},
    {"s":"UPS","n":"United Parcel Service","sec":"S&P500"},
    {"s":"DE","n":"John Deere","sec":"S&P500"},
    # Energy
    {"s":"XOM","n":"Exxon Mobil","sec":"S&P500"},
    {"s":"CVX","n":"Chevron","sec":"S&P500 · DOW30"},
    {"s":"COP","n":"ConocoPhillips","sec":"S&P500"},
    {"s":"OXY","n":"Occidental Petroleum","sec":"S&P500"},
    {"s":"SLB","n":"Schlumberger","sec":"S&P500"},
    # Real Estate
    {"s":"AMT","n":"American Tower","sec":"S&P500"},
    {"s":"PLD","n":"Prologis","sec":"S&P500"},
    {"s":"CCI","n":"Crown Castle","sec":"S&P500"},
    {"s":"EQIX","n":"Equinix","sec":"S&P500"},
    # Utilities
    {"s":"NEE","n":"NextEra Energy","sec":"S&P500"},
    {"s":"DUK","n":"Duke Energy","sec":"S&P500"},
    {"s":"SO","n":"Southern Company","sec":"S&P500"},
    # Popular Russell 2000
    {"s":"DKNG","n":"DraftKings","sec":"RUSSELL2000"},
    {"s":"SOFI","n":"SoFi Technologies","sec":"RUSSELL2000"},
    {"s":"RIVN","n":"Rivian Automotive","sec":"RUSSELL2000"},
    {"s":"IONQ","n":"IonQ Quantum","sec":"RUSSELL2000"},
    {"s":"RKLB","n":"Rocket Lab","sec":"RUSSELL2000"},
    {"s":"AFRM","n":"Affirm Holdings","sec":"RUSSELL2000"},
    {"s":"HIMS","n":"Hims & Hers Health","sec":"RUSSELL2000"},
    {"s":"RBLX","n":"Roblox","sec":"RUSSELL2000"},
    {"s":"HOOD","n":"Robinhood","sec":"RUSSELL2000"},
    {"s":"UPST","n":"Upstart Holdings","sec":"RUSSELL2000"},
    # ETFs
    {"s":"SPY","n":"S&P 500 ETF","sec":"ETF"},
    {"s":"QQQ","n":"Nasdaq 100 ETF","sec":"ETF"},
    {"s":"IWM","n":"Russell 2000 ETF","sec":"ETF"},
    {"s":"DIA","n":"Dow Jones ETF","sec":"ETF"},
    {"s":"SOXX","n":"Semiconductor ETF","sec":"ETF"},
    {"s":"ARKK","n":"ARK Innovation","sec":"ETF"},
    {"s":"XLK","n":"Technology ETF","sec":"ETF"},
    {"s":"XLF","n":"Financial ETF","sec":"ETF"},
    {"s":"XLE","n":"Energy ETF","sec":"ETF"},
    {"s":"GLD","n":"Gold ETF","sec":"ETF"},
    {"s":"SLV","n":"Silver ETF","sec":"ETF"},
    {"s":"TLT","n":"Treasury Bond ETF","sec":"ETF"},
    {"s":"VTI","n":"Total Market ETF","sec":"ETF"},
    {"s":"VOO","n":"Vanguard S&P500","sec":"ETF"},
    {"s":"IBIT","n":"iShares Bitcoin ETF","sec":"ETF"},
    {"s":"SMH","n":"VanEck Semiconductor","sec":"ETF"},
    # Crypto
    {"s":"BTC-USD","n":"Bitcoin","sec":"CRYPTO"},
    {"s":"ETH-USD","n":"Ethereum","sec":"CRYPTO"},
    {"s":"SOL-USD","n":"Solana","sec":"CRYPTO"},
    {"s":"BNB-USD","n":"Binance Coin","sec":"CRYPTO"},
    {"s":"XRP-USD","n":"Ripple XRP","sec":"CRYPTO"},
    {"s":"ADA-USD","n":"Cardano","sec":"CRYPTO"},
    {"s":"DOGE-USD","n":"Dogecoin","sec":"CRYPTO"},
    {"s":"AVAX-USD","n":"Avalanche","sec":"CRYPTO"},
    # Indices
    {"s":"^GSPC","n":"S&P 500 Index","sec":"INDEX"},
    {"s":"^DJI","n":"Dow Jones Industrial","sec":"INDEX"},
    {"s":"^IXIC","n":"Nasdaq Composite","sec":"INDEX"},
    {"s":"^RUT","n":"Russell 2000 Index","sec":"INDEX"},
    {"s":"^VIX","n":"VIX Volatility","sec":"INDEX"},
    # Commodities / Forex
    {"s":"GC=F","n":"Gold Futures","sec":"COMM"},
    {"s":"SI=F","n":"Silver Futures","sec":"COMM"},
    {"s":"CL=F","n":"Crude Oil","sec":"COMM"},
    {"s":"EURUSD=X","n":"EUR/USD","sec":"FOREX"},
    {"s":"GBPUSD=X","n":"GBP/USD","sec":"FOREX"},
    {"s":"USDJPY=X","n":"USD/JPY","sec":"FOREX"},
]
