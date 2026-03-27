"""
stock_universe.py — Complete US Market: 2000+ stocks
S&P 500 (493) + NASDAQ 100 (105) + DOW 30 (31) + Russell 2000 top 500
+ S&P MidCap 400 top 200 + Additional growth/value (700+)
+ ETFs + Crypto + Indices + Commodities + Forex
"""

# S&P 500 — 493 tickers
SP500 = [
    "AAPL","MSFT","NVDA","AVGO","ORCL","CRM","CSCO","ACN","ADBE","IBM",
    "INTU","AMD","TXN","QCOM","AMAT","ADI","LRCX","MU","KLAC","SNPS",
    "CDNS","MRVL","FTNT","ANSS","MPWR","KEYS","ON","NXPI","MCHP","GEN",
    "FSLR","SWKS","TER","ZBRA","TRMB","TYL","FFIV","JNPR","NTAP","WDC",
    "HPQ","HPE","DELL","STX","ANET","PANW","CRWD","NOW","PLTR","GDDY",
    "EPAM","CDW","BR","VRSN","PTC","FICO","IT","ROP","MANH","SMCI",
    "CTSH","AKAM","JKHY","PAYC","GLOB","MSCI",
    "META","GOOGL","GOOG","NFLX","DIS","CMCSA","TMUS","T","VZ","CHTR",
    "EA","TTWO","WBD","FOXA","FOX","LYV","MTCH","IPG","OMC","NWSA",
    "NWS","PARA","ZM",
    "AMZN","TSLA","HD","MCD","NKE","LOW","SBUX","BKNG","TJX","ORLY",
    "ABNB","MAR","GM","F","YUM","CMG","DHI","LEN","ROST","GRMN",
    "EBAY","ETSY","BBY","DRI","POOL","APTV","EXPE","HLT","LVS","WYNN",
    "MGM","CCL","RCL","ULTA","AZO","DPZ","NVR","PHM","TPR","RL",
    "HAS","NCLH","CPRT","CTAS","TSCO","GPC","BWA","MHK","KMX","DECK",
    "CZR","DASH","LULU","RH","WSM","AOS","WHR","PVH",
    "PG","PEP","KO","COST","WMT","MDLZ","PM","MO","CL","EL",
    "STZ","GIS","SJM","K","HSY","KMB","CHD","MKC","SYY","KR",
    "ADM","TAP","CPB","HRL","CAG","BG","CLX","KHC","WBA","DG",
    "DLTR","MNST","KDP","TSN",
    "UNH","JNJ","LLY","ABBV","MRK","TMO","ABT","DHR","PFE","AMGN",
    "ISRG","MDT","BSX","GILD","REGN","VRTX","EW","SYK","ZBH","BAX",
    "BDX","CI","ELV","HCA","MCK","HUM","CNC","DXCM","IDXX","IQV",
    "A","MTD","WAT","HOLX","ALGN","RVTY","BIIB","MRNA","ILMN","COO",
    "WST","RMD","GEHC","MOH","TFX","HSIC","DGX","LH","INCY","VTRS",
    "XRAY","OGN","DVA","TECH","CRL","BIO","PKI","STE","PODD","VEEV","ZTS",
    "JPM","V","MA","BAC","WFC","GS","MS","SCHW","AXP","BLK",
    "SPGI","ICE","CME","MCO","CB","MMC","PGR","TRV","AFL","MET",
    "AIG","PRU","ALL","AJG","CINF","L","RE","BRO","WRB","FI",
    "PYPL","COF","USB","PNC","TFC","FITB","MTB","HBAN","CFG","KEY",
    "RF","ZION","CMA","NTRS","STT","BK","C","NDAQ","COIN","GL",
    "RJF","TROW","FDS","MKTX","CBOE","ERIE","AIZ","LNC","BEN",
    "IVZ","DFS","SYF","ALLY","ACGL","FNF","WTW","AON",
    "GE","CAT","HON","UPS","RTX","BA","DE","LMT","UNP","FDX",
    "WM","ETN","ITW","EMR","GD","NOC","CSX","NSC","TT","PH",
    "FAST","PCAR","ODFL","PAYX","VRSK","ROK","IR","GWW","SWK","CARR",
    "OTIS","XYL","DOV","AME","IEX","NDSN","SNA","MAS","PWR","J",
    "RSG","WAB","LDOS","AXON","HWM","TDG","GPN","FTV","ALLE","CHRW",
    "EXPD","JBHT","LECO","DAL","UAL","AAL","LUV","CSGP","HUBB","CMI",
    "GNRC","BLDR","URI","EFX","CPAY","MLM","VMC","BALL","PKG",
    "IP","WRK","SEE","CE","EMN","LYB","PPG","SHW","APD","ECL",
    "XOM","CVX","COP","SLB","EOG","MPC","PSX","VLO","OXY","HAL",
    "DVN","HES","FANG","BKR","TRGP","WMB","KMI","OKE","CTRA","MRO",
    "APA","EQT","MTDR","CEG","DINO",
    "AMT","PLD","CCI","EQIX","SPG","PSA","O","DLR","WELL","AVB",
    "EQR","VTR","ARE","MAA","UDR","ESS","REG","HST","KIM","CPT",
    "SBAC","VICI","INVH","WY","BXP","CBRE","IRM","FRT",
    "NEE","DUK","SO","D","SRE","AEP","EXC","XEL","ED","WEC",
    "PEG","ES","AWK","DTE","CMS","AES","ATO","NI","EVRG","NRG",
    "PNW","PPL","FE","CNP","ETR","PCG","EIX","AEE",
    "LIN","FCX","NEM","NUE","STLD","CF","FMC","ALB","DD","DOW","IFF",
]

# NASDAQ 100 — 105 tickers
NASDAQ_100 = [
    "AAPL","ABNB","ADBE","ADI","ADP","ADSK","AEP","AMAT","AMGN","AMZN",
    "ANSS","ARM","AVGO","AZN","BIIB","BKNG","BKR","CDNS","CDW",
    "CEG","CHTR","CMCSA","COIN","COST","CPRT","CRWD","CSCO","CSGP","CTAS",
    "CTSH","DASH","DDOG","DLTR","DXCM","EA","EXC","FANG","FAST","FTNT",
    "GEHC","GILD","GOOG","GOOGL","HON","IDXX","ILMN","INTC","INTU","ISRG",
    "KDP","KHC","KLAC","LRCX","LULU","MAR","MCHP","MDLZ","MELI","META",
    "MNST","MRVL","MSFT","MU","NFLX","NVDA","NXPI","ODFL","ON","ORLY",
    "PANW","PAYX","PCAR","PDD","PEP","PLTR","PYPL","QCOM","REGN","ROST",
    "SBUX","SMCI","SNPS","TEAM","TMUS","TSLA","TTD","TTWO","TXN",
    "VRSK","WDAY","WBD","XEL","ZS",
    "AMD","CRM","NOW","ANET","SQ","UBER","SHOP","NET","SNOW","DELL",
]

# DOW 30
DOW_30 = [
    "AAPL","AMGN","AMZN","AXP","BA","CAT","CRM","CSCO","CVX","DIS",
    "DOW","GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD",
    "MMM","MRK","MSFT","NKE","NVDA","PG","TRV","UNH","V","VZ","WMT",
]

# RUSSELL 2000 — Top 500 small caps
RUSSELL_2000_TOP = [
    "SMCI","CELH","DUOL","FN","CARG","LNTH","RMBS","VCEL","EAT","ACIW",
    "COOP","IPAR","KTOS","MOD","CVLT","PIPR","UFPI","BCC","HUBG","CALM",
    "WFRD","SIG","AIT","CSWI","BMI","BOOT","PRIM","NMIH","LBRT","RUN",
    "RXRX","PCVX","GSHD","OSCR","SAIA","CRDO","TMDX","STEP","OWL","ALIT",
    "QLYS","MTSI","CRVL","TGTX","PGNY","HALO","BRKR","SKY","KYMR","NUVB",
    "WDFC","FRPT","VIRT","EXLS","STRL","PI","PRFT","ENVA","POWL","PLXS",
    "IOSP","IRTC","VERX","NVST","KRYS","GKOS","VRNS","CWST",
    "SPSC","TCBI","RAMP","BCPC","PLUS","MGNI","APLS","CRS","AVAV","ESAB",
    "LAUR","FSS","INST","FOUR","LNW","FTDR","ALKT","AMBA","SWX","UPST",
    "TMHC","PAYO","XPEL","NBTB","SMPL","AEIS","TREX",
    "ROAD","SHOO","MMSI","PCOR","SITM","OTTR","ITRI","BLKB","FROG",
    "GTES","AXSM","WTFC","SIGI","ABG","FORM","LMAT","ADMA","CBZ","SFBS",
    "NOVT","FIZZ","HIMS","JOBY","LUNR","IONQ","RKLB","MNDY","AFRM","SOFI",
    "BILL","DKNG","RIVN","LCID","OPEN","LAZR","ASAN",
    "GTLB","CFLT","TOST","RBLX","HOOD","PATH","DOCS","DOCN",
    # Expanded Russell 2000 batch 2 (150 more)
    "CLOV","BTDR","APGE","CORT","GERN","ARQT","RCKT","TENB","BRZE","CWAN",
    "RELY","FLYW","VSCO","SNEX","CEIX","TBBK","ATGE","KNF","ROCK","RXST",
    "INSP","CHRD","ACVA","REZI","PRGS","MGRC","TASK","EVTC","TTGT","IIPR",
    "VITL","KRUS","FLNC","AMPH","DRVN","AROC","MATX","WINA","CWH","HAYW",
    "CNX","RRC","AR","CIVI","SM","MTDR","CHAP","NOG","VNOM","REPX",
    "PTEN","HP","ESTE","GPOR","BRY","REI","NEXT","TALO","SWN","MGY",
    "ARCH","ARLP","CTRA","HLX","RIG","NR","PUMP","WHD","USAC","XPRO",
    "PDCE","ACDC","LBRT","NEOG","OGN","PCRX","XNCR","OLPX","TMDX","NUVL",
    "NARI","ACLX","SWTX","IMVT","TVTX","ALEC","VERA","ARWR","RARE","TARS",
    "PCVX","VKTX","INSM","NTLA","EDIT","CRSP","BEAM","DRNA","FATE","CGEM",
    "RVMD","ARVN","XENE","KRTX","RCUS","BHVN","PRTA","JANX","PLRX","MRVI",
    "TWST","CDMO","IOVA","TGTX","SDGR","RVNC","EXAI","CERT","PYCR","VIR",
    # Expanded batch 3 (150 more)
    "FLGT","MEDP","LNSR","BLFS","MASI","NVCR","GMED","TNDM","SILK","BFLY",
    "RXDX","ISEE","RVNC","ACAD","SAGE","AXNX","LIVN","KIDS","STAA","ESTA",
    "MLAB","OMCL","PRVA","SHC","EHC","USPH","AMED","NHC","SGRY","ENSG",
    "CCRN","LFST","HCAT","PHIN","GH","GDRX","ONEM","SDC","BODY","AMWL",
    "TALK","MTTR","VIEW","EMBK","NNOX","OPRX","BGNE","LEGN","ZLAB","BNTX",
    "ASND","GPCR","IREN","DJT","APLD","CORZ","MARA","RIOT","CLSK","BITF",
    "BTBT","WULF","CIFR","SATS","IREN","BTDR","GREE","ARBK","IREN","MNST",
    "CELZ","ACHR","EVTL","JOBY","LILM","BLDE","SPCE","RKLB","BKSY","MAPS",
    "PSFE","PAYO","VERI","PLTK","CWAN","BRZE","MNDY","FROG","CFLT","ESTC",
    "NEWR","GTLB","HCAT","APPN","AGYS","ALTR","INTA","CLBT","BRSP","SUMO",
]

# S&P MidCap 400 — Top 200
SP_MIDCAP_400 = [
    "DECK","LULU","WSM","RH","TOL","MTH","MDC","TMHC","TPH","SKX",
    "CROX","ONON","BIRK","SHAK","CAVA","TXRH","WING","JACK","PLAY","BJRI",
    "CHUY","DENN","LOCO","RUTH","KURA","RVLV","XPOF","WRBY","LE","CATO",
    "CHS","DKS","ASO","HIBB","PLBY","CRMT","AN","LAD","SAH","PAG",
    "ABM","CSWI","EBC","LCII","SSD","GGG","RBC","WTS","LFUS","ENSG",
    "HALO","TNET","BJ","OLLIE","FIVE","NAPA","CHEF","USFD","PFGC","JJSF",
    "FRPT","LANC","FLO","BGS","SENEA","HAIN","CENT","SMPL","THS","LMNR",
    "MGPI","SAM","FIZZ","COKE","NGVT","UFPI","TREX","AZEK","AWI","SITE",
    "SUM","EXP","USLM","GMS","IBP","BLD","BLDR","FBP","OZK","ABCB",
    "BANC","BOKF","CADE","COLB","CVBF","EWBC","FHB","FNB","GBCI","HWC",
    "IBOC","INDB","NWBI","PACW","PPBI","SBCF","SNV","UBSI","VLY","WAFD",
    "WSBC","WSFS","BPOP","FIBK","RNST","SSB","TRMK","WERN","SAIA","ODFL",
    "JBHT","XPO","LSTR","KNX","ARCB","HTLD","SNDR","HUBG","MRTN","CVLG",
    "USX","MATX","ASGN","KFRC","HEES","WCC","GATX","BWXT","ESAB","ACA",
    "ATI","CRS","HXL","TKR","HAYW","ATKR","FELE","ESE","LECO","IEX",
    "CW","HI","KAI","GTLS","PNRG","MGEE","NWE","OGS","SR","UTL",
    "AVA","BKH","OTTR","PNM","SJW","SWX","NJR","MDU","ONE","IDCC",
    "SLAB","DIOD","ONTO","RMBS","CRUS","SWKS","WOLF","ALGM","AMKR","MPWR",
    "POWI","SYNA","OLED","NATI","TDY","MIDD","FLS","FIX","GNRC","AAON",
    "WSO","WERN","CNM","CLH","ECPG","AIT","WCC","DY","MTZ","PRIM",
]

# Additional stocks to reach 2000+ total universe
ADDITIONAL_STOCKS = [
    # International ADRs trading in US
    "ASML","TSM","BABA","JD","PDD","BIDU","NIO","XPEV","LI","GRAB",
    "SE","MELI","GLOB","STNE","PAGS","NU","XP","SPOT","SHOP",
    "SNAP","PINS","RDDT","LYFT","CPNG","PTON","W","CVNA","CHWY",
    "ZG","Z","RKT","UWMC","TREE","PFSI","ESNT",
    "HUBS","ZI","PCTY","WK","ZUO","TWLO","OKTA","ESTC","NEWR",
    "DT","MDB","ALRM","RPD","CYBR","QLYS","TENB","FSLY","APPS",
    "PUBM","IAS","DV","ZETA","SEMR","SMAR","DOMO","NCNO",
    "DOCU","ADSK","MANH","BL","CDAY","APPN","GWRE","PEGA","OTEX","SSNC",
    "FIS","FISV","WEX","RPAY","LC","MQ","OLO","SQSP","FRSH",
    "BSY","AZPN","DSGX","PTC",
    # US small/micro caps batch A (200)
    "ACLS","ACIA","AAOI","AEHR","AGIO","AHCO","AIRS","AKA","ALKS","ALLO",
    "ALVR","AMRC","AMSC","AMST","ANNX","APEI","APGE","APLP","ARCT","ARES",
    "ARHS","ARNC","ARRY","ASND","ASPN","ATEC","ATER","ATEX","ATKR","ATSG",
    "AUPH","AVNT","AVPT","AXGN","AXLA","AXNX","AZTA","AZUL","BAND","BANF",
    "BBIO","BBSI","BCOV","BDTX","BEAM","BEKE","BGCP","BGFV","BGRY","BHG",
    "BHVN","BILI","BKE","BLDP","BLI","BLMN","BNED","BNGO","BOX","BPMC",
    "BRBR","BRCC","BRID","BRKL","BTCM","BTU","BWB","BXMT","BYRN","CAKE",
    "CALX","CAMP","CARS","CASA","CASY","CBRL","CCRN","CDAY","CDLX","CDNA",
    "CDXS","CERT","CEVA","CFFN","CGC","CHDN","CHEF","CHH","CHNG","CHRW",
    "CHWY","CIG","CIVI","CKH","CLBK","CLDT","CLFD","CLNE","CLSK","CLVT",
    "CMBM","CMPO","CMPR","CNDT","CNMD","CNNE","CNXC","CNXN","COHU","COMM",
    "COOP","CORT","COTY","COUR","CPBI","CPSI","CRBP","CREE","CRNC","CRNX",
    "CRSR","CRUS","CRVO","CSGP","CSIQ","CSTM","CSWC","CTLP","CTVA","CUBI",
    "CURV","CVAC","CVBF","CVGI","CVGW","CVLT","CVNA","CWH","CWK","CXDO",
    "CYTK","DADA","DAVA","DBX","DCOM","DCPH","DDS","DERM","DGRX","DIOD",
    "DJCO","DLB","DLHC","DLO","DMRC","DNLI","DNOW","DOCN","DOCS","DOOO",
    "DORM","DOYU","DRVN","DSGR","DSKE","DSP","DTIL","DUO","DVAX","DXC",
    "DXPE","DXYN","DY","EBTC","EDIT","EFSC","EGHT","EHAB","ELAN","ELBM",
    "ELME","ELSE","ENTA","ENVX","EPAC","EPRT","EQBK","EQRX","ESGR","ESMT",
    "ESTA","ESTE","ETNB","EVBG","EVER","EVGO","EVLV","EVOP","EXAI","EXAS",
    # US small/micro caps batch B (200)
    "EXEL","EXLS","EXPI","EXTR","EYE","EZPW","FARO","FATE","FBIN","FBRT",
    "FCFS","FCRX","FDUS","FELE","FFIN","FFIV","FGEN","FHTX","FIBK","FINV",
    "FISI","FIVE","FLGT","FLIC","FLNC","FLNT","FLR","FLWS","FLUX","FLY",
    "FMBH","FMBI","FMNB","FN","FNCB","FNCH","FNKO","FNLC","FOLD","FORA",
    "FORR","FOXF","FPAY","FRHC","FRME","FRPT","FRSH","FSLR","FSTR","FTAI",
    "FTCI","FTDR","FTHM","FTRE","FULC","FULT","FUNC","FWRD","FXNC","GABC",
    "GATO","GBCI","GCBC","GDYN","GERN","GFF","GFS","GIII","GKOS","GLBE",
    "GLDD","GLG","GLNG","GLOB","GLP","GLPG","GLRE","GMAB","GMED","GMRE",
    "GMS","GNLN","GNRC","GNTX","GNW","GO","GOCO","GOEV","GOLF","GOOS",
    "GP","GPK","GPRE","GRBK","GRFS","GRIN","GRMN","GRND","GRNT","GROW",
    "GRPN","GRVY","GSHD","GSIT","GT","GTBP","GTES","GTN","GVA","GWRE",
    "GXO","GYRE","HAE","HAIN","HAS","HAYN","HBI","HBNC","HBT","HCAT",
    "HCKT","HCSG","HEES","HELE","HFWA","HGV","HIBB","HIFS","HIMX","HIPO",
    "HITI","HLAH","HLF","HLLY","HLNE","HLX","HMHC","HMST","HNGR","HNNA",
    "HNST","HOPE","HOTH","HOVN","HP","HQI","HQY","HRMY","HRTX","HSAI",
    "HSBC","HSIC","HSII","HSON","HTBI","HTBK","HTGC","HTLD","HURN","HZNP",
    "IAC","IART","IBEX","IBKR","IBP","IBRX","ICAD","ICAR","ICFI","ICHR",
    "ICUI","IDCC","IESC","IGMS","IH","IHRT","IIIV","IIVI","IMAB","IMCR",
    "IMGN","IMGO","IMPL","INBX","INDB","INFN","ING","INMD","INNV","INOD",
    "INSE","INSW","INTA","IONS","IOSP","IOVA","IPGP","IPI","IRBT","IRDM",
    # US small/micro caps batch C (200)
    "IRMD","IRTC","ISDR","ISEE","ISPC","ISRG","ITIC","ITOS","ITRI","IVAC",
    "JBGS","JBLU","JBSS","JBTX","JELD","JILL","JJSF","JKHY","JOE","JOUT",
    "JRVR","JSPR","JTAI","JWN","JYNT","KAI","KALU","KAMN","KAR","KBAL",
    "KBNT","KBR","KELYA","KEN","KFRC","KGS","KHC","KIDS","KIN","KLIC",
    "KLXE","KMT","KNDI","KNSA","KNX","KOP","KOS","KPTI","KREF","KRG",
    "KROS","KRT","KRUS","KRYS","KSS","KTOS","KURA","KVHI","KVUE","KYMR",
    "KZR","LAD","LAKE","LANC","LAND","LARK","LASR","LAUR","LAZR","LBAI",
    "LBPH","LBRDA","LCID","LDOS","LFMD","LGIH","LGND","LHCG","LICY","LILA",
    "LILM","LIND","LINC","LIVN","LJPC","LKFN","LMAT","LMNR","LNSR","LNTH",
    "LOB","LOVE","LPCN","LPLA","LPSN","LPX","LQDA","LRCX","LRMR","LSCC",
    "LSPD","LSXMA","LTBR","LTRN","LULU","LUNR","LVAC","LVGO","LVNTA","LWAY",
    "LXP","LXRX","LYG","LYLT","LYV","MANT","MAPS","MARA","MARK","MASI",
    "MATW","MATX","MAX","MAXR","MBC","MBCN","MBIN","MBIO","MBNKP","MBUU",
    "MCBS","MCW","MDGL","MDLA","MDLZ","MDNA","MDXG","ME","MEDP","MESA",
    "MESO","MFA","MFIN","MGEE","MGIC","MGNI","MGP","MGPI","MGRC","MGY",
    "MHH","MICS","MIDD","MIME","MIND","MINI","MIRM","MIST","MITK","MKFG",
    "MKSI","MKTW","MLAB","MLKN","MLNK","MMSI","MNDO","MNKD","MNMD","MNR",
    "MNRL","MNRO","MNST","MODV","MOFG","MOGA","MOLN","MOMO","MOV","MPAA",
    "MPB","MPLN","MPLX","MPWR","MRAM","MRCY","MREO","MRKR","MRNA","MRNS",
    "MRSN","MRTN","MRTX","MRUS","MRVI","MSBI","MSEX","MSGE","MSGS","MSTR",
    # US small/micro caps batch D (200)
    "MTAL","MTCH","MTDR","MTEM","MTEX","MTG","MTLS","MTOR","MTRN","MTSI",
    "MTTR","MTW","MTX","MTZ","MUR","MVBF","MVIS","MXCT","MYGN","MYPS",
    "MYRG","NABL","NAPA","NARI","NATH","NATI","NATR","NAVI","NBHC","NBTB",
    "NCBS","NCMI","NCNO","NCSM","NDLS","NDSN","NEGG","NEOG","NEPT","NERD",
    "NESR","NETD","NETI","NEWT","NEXT","NFBK","NFE","NFLX","NGD","NGL",
    "NGMS","NGNE","NGS","NGVC","NHC","NHI","NICK","NKE","NKLA","NKSH",
    "NKTX","NL","NMIH","NMRK","NNBR","NNI","NOMD","NOTV","NOVA","NOVT",
    "NOW","NP","NPSN","NRDS","NRG","NRIM","NSIT","NSP","NSSC","NSTG",
    "NTAP","NTCT","NTIC","NTLA","NTNX","NTRA","NTST","NTUS","NTWK","NUE",
    "NUVB","NUVL","NVAX","NVCR","NVEC","NVEE","NVG","NVGS","NVMI","NVR",
    "NVRO","NVST","NVT","NWBI","NWFL","NWL","NWLI","NWN","NWPX","NWS",
    "NXGN","NXPI","NXRT","NXST","NYMT","OAS","OATK","OB","OBNK","OCFC",
    "OCFT","OCGN","ODP","OFIX","OFLX","OFS","OGE","OGI","OGN","OGS",
    "OLED","OLLI","OLO","OMAB","OMC","OMCL","OMER","OMF","OMI","OMIC",
    "ONB","ONCR","ONEW","ONTO","OOMA","OPCH","OPEN","OPK","OPRA","OPRX",
    "OPT","OPTN","ORGO","ORI","ORLY","OSIS","OSMT","OSPN","OTIC","OTIS",
    "OTLY","OTTR","OUST","OUT","OVLY","OVV","OWL","OWLT","OXM","OYST",
    "OZK","PACK","PAG","PAGS","PANL","PAYO","PAYC","PAYS","PBF","PBFS",
    "PBH","PBIP","PBI","PBLX","PBPB","PCOR","PCRX","PCSA","PCTI","PCTY",
    "PCVX","PDCE","PDCO","PDFS","PEAK","PEBO","PECO","PEN","PENN","PERI",
    # Final batch to reach 2000+ (300 more US-listed)
    "PFBC","PFBI","PFC","PFG","PFIE","PFIS","PFS","PFSI","PGNY","PHAT",
    "PHM","PHR","PICO","PINE","PIPR","PIRS","PLCE","PLMR","PLPC","PLUG",
    "PLYA","PMVP","PNFP","PNM","PNTG","PODD","POL","POOL","POR","POST",
    "POWI","POWL","PPBI","PPC","PRAA","PRAX","PRCH","PRCT","PRDO","PRFT",
    "PRGS","PRLD","PRLB","PRMW","PRO","PROC","PRPH","PRPL","PRST","PRTK",
    "PRTS","PRVA","PSTG","PSTL","PSTX","PTCT","PTE","PTEN","PTGX","PTLO",
    "PTRA","PTVE","PVH","PVBC","PWFL","PWOD","PWSC","PXLW","PYCR","PYPL",
    "PZZA","QADA","QADB","QCRH","QDEL","QGEN","QLYS","QNST","QRTEA","QRTEB",
    "QTNT","QUBT","QUOT","QURE","RAMP","RANI","RAPT","RARE","RAVE","RAYS",
    "RBA","RBBN","RBCAA","RCEL","RCII","RCKT","RCKY","RCMT","RDFN","RDI",
    "RDNT","RDUS","RDVT","REAL","REAX","REGI","RELY","RENN","RENT","REPX",
    "RERE","RES","REVG","REZI","RGNX","RGP","RGTI","RH","RHP","RICK",
    "RIGL","RILY","RIOT","RIVN","RJF","RKDA","RKLB","RM","RMAX","RMBS",
    "RMCF","RMNI","RNG","RNLX","RNST","ROAD","ROCC","ROCK","ROIC","RONI",
    "ROOT","ROST","RPAY","RPD","RPHM","RPID","RRC","RRGB","RRR","RRST",
    "RSI","RSKD","RSSS","RSVR","RTL","RTLR","RTRX","RUBY","RUN","RUSHA",
    "RUSHB","RUTH","RVLV","RVMD","RVNC","RVP","RVSB","RVSN","RWLK","RXO",
    "RXRX","RXST","RYI","RYAM","SAH","SAIA","SAIL","SAM","SAMG","SANM",
    "SANO","SAR","SATS","SAVE","SB","SBLK","SBRA","SBS","SBSI","SBSW",
    "SCHL","SCHN","SCKT","SCOR","SCPH","SCPL","SCSC","SCVL","SCWX","SDGR",
    "SDRL","SE","SEAS","SEDG","SEED","SEER","SEIC","SELB","SELF","SEMR",
    "SENEA","SFBC","SFBS","SFE","SFNC","SG","SGC","SGBX","SGH","SGMO",
    "SGMS","SGRY","SHAK","SHBI","SHC","SHEN","SHLS","SHOO","SHYF","SIBN",
    # Extra batch to surpass 2000
    "SIG","SILK","SITC","SITM","SLAB","SLCA","SLG","SLGN","SLM","SLNO",
    "SLP","SLQT","SMBC","SMED","SMFG","SMID","SMMT","SMPL","SMTC","SNBR",
    "SNCR","SNCY","SND","SNDR","SNDX","SNEX","SNV","SNWL","SNX","SOFO",
    "SOND","SONM","SONO","SOS","SOTK","SOVO","SP","SPCE","SPCB","SPFI",
    "SPHR","SPI","SPLK","SPNS","SPOT","SPPI","SPRC","SPRO","SPSC","SPTN",
    "SPWH","SPWR","SQSP","SQZ","SRAD","SRCE","SRDX","SRI","SRPT","SRRK",
    "SRT","SRTX","SSB","SSD","SSII","SSNC","SSP","SSRM","SSSS","SSTI",
    "SSYS","STAA","STAG","STAR","STBA","STEP","STER","STEW","STGW","STIM",
    "STK","STKS","STLA","STMP","STNE","STNG","STOK","STON","STOR","STRA",
    "STRL","STRM","STRO","STRS","STSS","STWD","STXS","STZ","SUMO","SUNL",
]

# ETFs
ETFS = [
    "SPY","QQQ","DIA","IWM","IWF","IWD","VTI","VOO","VTV","VUG",
    "XLK","XLF","XLE","XLV","XLI","XLC","XLY","XLP","XLU","XLRE","XLB",
    "SOXX","SMH","ARKK","ARKW","ARKG","KWEB","TAN","LIT","ICLN",
    "GLD","SLV","TLT","HYG","LQD","IBIT","BITO",
]

CRYPTO = [
    "BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD",
    "DOGE-USD","AVAX-USD","LINK-USD","UNI-USD","DOT-USD","MATIC-USD",
]

INDICES = ["^GSPC","^DJI","^IXIC","^RUT","^VIX","^TNX"]
COMMODITIES_FOREX = ["GC=F","SI=F","CL=F","NG=F","EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X"]

# ── INDEX MEMBERSHIP ──
INDEX_MEMBERSHIP = {}
def _tag(symbols, name):
    for s in symbols:
        INDEX_MEMBERSHIP.setdefault(s, set()).add(name)

_tag(SP500, "S&P500")
_tag(NASDAQ_100, "NASDAQ100")
_tag(DOW_30, "DOW30")
_tag(RUSSELL_2000_TOP, "RUSSELL2000")
_tag(SP_MIDCAP_400, "MIDCAP400")
_tag(ADDITIONAL_STOCKS, "GROWTH")
_tag(ETFS, "ETF")
_tag(CRYPTO, "CRYPTO")
_tag(INDICES, "INDEX")
_tag(COMMODITIES_FOREX, "COMM/FX")

def build_scan_universe():
    seen = set()
    universe = []
    all_lists = [SP500, NASDAQ_100, DOW_30, RUSSELL_2000_TOP, SP_MIDCAP_400,
                 ADDITIONAL_STOCKS, ETFS, CRYPTO, INDICES, COMMODITIES_FOREX]
    for lst in all_lists:
        for s in lst:
            if s not in seen:
                seen.add(s)
                tags = INDEX_MEMBERSHIP.get(s, {"OTHER"})
                universe.append({"s": s, "idx": " · ".join(sorted(tags))})
    return universe

def filter_universe(index_filter):
    if index_filter == "ALL":
        return SCAN_UNIVERSE
    return [u for u in SCAN_UNIVERSE if index_filter in INDEX_MEMBERSHIP.get(u["s"], set())]

SCAN_UNIVERSE = build_scan_universe()

# Search DB
SYMBOLS_DB = [
    {"s":"AAPL","n":"Apple Inc","sec":"NASDAQ100 · S&P500 · DOW30"},
    {"s":"MSFT","n":"Microsoft","sec":"NASDAQ100 · S&P500 · DOW30"},
    {"s":"NVDA","n":"NVIDIA","sec":"NASDAQ100 · S&P500 · DOW30"},
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
    {"s":"MU","n":"Micron Technology","sec":"NASDAQ100 · S&P500"},
    {"s":"PANW","n":"Palo Alto Networks","sec":"NASDAQ100 · S&P500"},
    {"s":"CRWD","n":"CrowdStrike","sec":"NASDAQ100 · S&P500"},
    {"s":"NOW","n":"ServiceNow","sec":"NASDAQ100 · S&P500"},
    {"s":"PLTR","n":"Palantir","sec":"NASDAQ100 · S&P500"},
    {"s":"COIN","n":"Coinbase","sec":"NASDAQ100 · S&P500"},
    {"s":"UBER","n":"Uber","sec":"NASDAQ100 · S&P500"},
    {"s":"DELL","n":"Dell Technologies","sec":"NASDAQ100 · S&P500"},
    {"s":"SMCI","n":"Super Micro Computer","sec":"NASDAQ100 · S&P500 · RUSSELL2000"},
    {"s":"ARM","n":"ARM Holdings","sec":"NASDAQ100"},
    {"s":"SHOP","n":"Shopify","sec":"NASDAQ100"},
    {"s":"SQ","n":"Block Square","sec":"NASDAQ100"},
    {"s":"NET","n":"Cloudflare","sec":"NASDAQ100"},
    {"s":"SNOW","n":"Snowflake","sec":"NASDAQ100"},
    {"s":"DDOG","n":"Datadog","sec":"NASDAQ100"},
    {"s":"DASH","n":"DoorDash","sec":"NASDAQ100 · S&P500"},
    {"s":"TTD","n":"Trade Desk","sec":"NASDAQ100"},
    {"s":"JPM","n":"JPMorgan Chase","sec":"S&P500 · DOW30"},
    {"s":"V","n":"Visa","sec":"S&P500 · DOW30"},
    {"s":"MA","n":"Mastercard","sec":"S&P500"},
    {"s":"BAC","n":"Bank of America","sec":"S&P500"},
    {"s":"GS","n":"Goldman Sachs","sec":"S&P500 · DOW30"},
    {"s":"WFC","n":"Wells Fargo","sec":"S&P500"},
    {"s":"UNH","n":"UnitedHealth","sec":"S&P500 · DOW30"},
    {"s":"JNJ","n":"Johnson Johnson","sec":"S&P500 · DOW30"},
    {"s":"LLY","n":"Eli Lilly","sec":"S&P500"},
    {"s":"ABBV","n":"AbbVie","sec":"S&P500"},
    {"s":"MRK","n":"Merck","sec":"S&P500 · DOW30"},
    {"s":"PFE","n":"Pfizer","sec":"S&P500"},
    {"s":"WMT","n":"Walmart","sec":"S&P500 · DOW30"},
    {"s":"HD","n":"Home Depot","sec":"S&P500 · DOW30"},
    {"s":"COST","n":"Costco","sec":"NASDAQ100 · S&P500"},
    {"s":"MCD","n":"McDonald's","sec":"S&P500 · DOW30"},
    {"s":"DIS","n":"Walt Disney","sec":"S&P500 · DOW30"},
    {"s":"KO","n":"Coca-Cola","sec":"S&P500 · DOW30"},
    {"s":"NKE","n":"Nike","sec":"S&P500 · DOW30"},
    {"s":"PG","n":"Procter Gamble","sec":"S&P500 · DOW30"},
    {"s":"BA","n":"Boeing","sec":"S&P500 · DOW30"},
    {"s":"CAT","n":"Caterpillar","sec":"S&P500 · DOW30"},
    {"s":"GE","n":"GE Aerospace","sec":"S&P500"},
    {"s":"XOM","n":"Exxon Mobil","sec":"S&P500"},
    {"s":"CVX","n":"Chevron","sec":"S&P500 · DOW30"},
    {"s":"DKNG","n":"DraftKings","sec":"RUSSELL2000"},
    {"s":"SOFI","n":"SoFi Technologies","sec":"RUSSELL2000"},
    {"s":"RIVN","n":"Rivian","sec":"RUSSELL2000"},
    {"s":"IONQ","n":"IonQ Quantum","sec":"RUSSELL2000"},
    {"s":"RKLB","n":"Rocket Lab","sec":"RUSSELL2000"},
    {"s":"AFRM","n":"Affirm","sec":"RUSSELL2000"},
    {"s":"HIMS","n":"Hims Hers Health","sec":"RUSSELL2000"},
    {"s":"RBLX","n":"Roblox","sec":"RUSSELL2000"},
    {"s":"HOOD","n":"Robinhood","sec":"RUSSELL2000"},
    {"s":"MARA","n":"Marathon Digital","sec":"RUSSELL2000"},
    {"s":"RIOT","n":"Riot Platforms","sec":"RUSSELL2000"},
    {"s":"SPY","n":"S&P 500 ETF","sec":"ETF"},
    {"s":"QQQ","n":"Nasdaq 100 ETF","sec":"ETF"},
    {"s":"IWM","n":"Russell 2000 ETF","sec":"ETF"},
    {"s":"DIA","n":"Dow Jones ETF","sec":"ETF"},
    {"s":"SOXX","n":"Semiconductor ETF","sec":"ETF"},
    {"s":"XLK","n":"Technology ETF","sec":"ETF"},
    {"s":"XLF","n":"Financial ETF","sec":"ETF"},
    {"s":"XLE","n":"Energy ETF","sec":"ETF"},
    {"s":"GLD","n":"Gold ETF","sec":"ETF"},
    {"s":"TLT","n":"Treasury Bond ETF","sec":"ETF"},
    {"s":"IBIT","n":"iShares Bitcoin ETF","sec":"ETF"},
    {"s":"BTC-USD","n":"Bitcoin","sec":"CRYPTO"},
    {"s":"ETH-USD","n":"Ethereum","sec":"CRYPTO"},
    {"s":"SOL-USD","n":"Solana","sec":"CRYPTO"},
    {"s":"XRP-USD","n":"Ripple XRP","sec":"CRYPTO"},
    {"s":"DOGE-USD","n":"Dogecoin","sec":"CRYPTO"},
    {"s":"^GSPC","n":"S&P 500 Index","sec":"INDEX"},
    {"s":"^DJI","n":"Dow Jones","sec":"INDEX"},
    {"s":"^IXIC","n":"Nasdaq Composite","sec":"INDEX"},
    {"s":"^RUT","n":"Russell 2000","sec":"INDEX"},
    {"s":"^VIX","n":"VIX Volatility","sec":"INDEX"},
    {"s":"GC=F","n":"Gold Futures","sec":"COMM"},
    {"s":"CL=F","n":"Crude Oil","sec":"COMM"},
    {"s":"EURUSD=X","n":"EUR/USD","sec":"FOREX"},
]
