import os
import sys
import time
import concurrent.futures

# Ensure root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal, engine
from app.database import models, repositories

SECTOR_MAP = {
    'Financials': [
        'BANK', 'BRIS', 'BTPS', 'JMAS', 'PNBS', 'SRTG', 'PALM', 'DEFI'
    ],
    'Energy': [
        'AADI', 'ABMM', 'ADMR', 'ADRO', 'AKRA', 'ARII', 'ATLA', 'BBRM', 'BESS', 'BOAT',
        'BSML', 'BSSR', 'BULL', 'BUMI', 'BYAN', 'CANI', 'CGAS', 'COAL', 'DEWA', 'DSSA',
        'DWGL', 'ELSA', 'ENRG', 'FIRE', 'GEMS', 'HRUM', 'IATA', 'INDY', 'ITMA', 'ITMG',
        'KKGI', 'KOPI', 'MAHA', 'MBAP', 'MCOL', 'MEDC', 'MKAP', 'MYOH', 'PGAS', 'PKPK',
        'PSAT', 'PSSI', 'PTBA', 'PTIS', 'RAJA', 'RATU', 'RGAS', 'RMKE', 'RMKO', 'RUIS',
        'SEMA', 'SGER', 'SICO', 'SMMT', 'SOCI', 'SUNI', 'TCPI', 'TEBE', 'TOBA', 'TPMA',
        'UNIQ', 'WINS', 'WOWS'
    ],
    'Basic Materials': [
        'ADMG', 'AGII', 'AKPI', 'ALDO', 'ALKA', 'ANTM', 'APLI', 'ARCI', 'ASPR', 'AVIA',
        'AYLS', 'BATR', 'BLES', 'BMSR', 'BRMS', 'BRNA', 'CHEM', 'CITA', 'CLPI', 'CTBN',
        'DGWG', 'DKFT', 'EKAD', 'EPAC', 'ESIP', 'ESSA', 'FASW', 'FPNI', 'FWCT', 'GDST',
        'GGRP', 'IFII', 'IFSH', 'IGAR', 'INCI', 'INKP', 'INTD', 'INTP', 'IPOL', 'ISSP',
        'KDSI', 'KKES', 'LMSH', 'LTLS', 'MBMA', 'MDKA', 'MDKI', 'MINE', 'NICE', 'NICL',
        'NIKL', 'OBMD', 'OKAS', 'PACK', 'PBID', 'PDPP', 'PICO', 'PPRI', 'PSAB', 'PTMR',
        'SAMF', 'SBMA', 'SMBR', 'SMCB', 'SMGA', 'SMGR', 'SMKL', 'SMLE', 'SOLA', 'SPMA',
        'SULI', 'TALF', 'TBMS', 'TINS', 'TIRT', 'TKIM', 'TPIA', 'TRST', 'UNIC', 'WTON',
        'YPAS'
    ],
    'Industrials': [
        'AMFG', 'AMIN', 'APII', 'ARNA', 'ASGR', 'BINO', 'BLUE', 'CAKK', 'CCSI', 'CRSN',
        'DYAN', 'FOLK', 'GPSO', 'HEXA', 'HOPE', 'HYGN', 'ICON', 'IKAI', 'IKBI', 'IMPC',
        'JECC', 'JTPE', 'KBLI', 'KBLM', 'KIAS', 'KING', 'KOBX', 'KOIN', 'KONI', 'KUAS',
        'LION', 'MARK', 'MFMI', 'MHKI', 'MLIA', 'MUTU', 'NAIK', 'NTBK', 'PADA', 'PTMP',
        'SCCO', 'SKRN', 'SMIL', 'SOSS', 'SPTO', 'TIRA', 'TOTO', 'UNTR', 'VISI', 'VOKS',
        'WIDI'
    ],
    'Consumer Non-Cyclicals': [
        'AALI', 'ADES', 'AGAR', 'AISA', 'AMMS', 'ASHA', 'AYAM', 'BISI', 'BOBA', 'BRRC',
        'BUAH', 'BUDI', 'BWPT', 'CAMP', 'CEKA', 'CLEO', 'CMRY', 'CPIN', 'CPRO', 'CSRA',
        'DAYA', 'DEWI', 'DMND', 'DSFI', 'DSNG', 'EPMT', 'EURO', 'FISH', 'FLMC', 'FOOD',
        'FORE', 'GOOD', 'GRPM', 'GULA', 'GUNA', 'GZCO', 'HERO', 'HOKI', 'ICBP', 'IKAN',
        'INDF', 'JARR', 'JAWA', 'JPFA', 'KEJU', 'KINO', 'KMDS', 'LSIP', 'MAIN', 'MAXI',
        'MBTO', 'MKTR', 'MLPL', 'MPPA', 'MRAT', 'MSJA', 'MYOR', 'NANO', 'NASI', 'NAYZ',
        'NEST', 'NSSS', 'PCAR', 'PGUN', 'PNGO', 'PSDN', 'PSGO', 'PTPS', 'RANC', 'ROTI',
        'SDPC', 'SGRO', 'SIMP', 'SIPD', 'SKBM', 'SKLT', 'SMAR', 'STAA', 'STTP', 'TAPG',
        'TCID', 'TGKA', 'TGUK', 'TLDN', 'UCID', 'UDNG', 'ULTJ', 'UNVR', 'VICI', 'WAPO',
        'YUPI'
    ],
    'Consumer Cyclicals': [
        'ACES', 'AEGS', 'ASLC', 'AUTO', 'BABY', 'BAIK', 'BAUT', 'BAYU', 'BELL', 'BIKE',
        'BLTZ', 'BMBL', 'BMTR', 'BOGA', 'BOLT', 'BRAM', 'CINT', 'CNMA', 'CSAP', 'CSMI',
        'DEPO', 'DOOH', 'DOSS', 'DRMA', 'EAST', 'ECII', 'ENAK', 'ERAA', 'ERAL', 'ERTX',
        'ESTA', 'FAST', 'FILM', 'GDYR', 'GEMA', 'GJTL', 'GOLF', 'GRPH', 'GWSA', 'HAJJ',
        'HRTA', 'IDEA', 'IIKP', 'INDR', 'INDS', 'IPTV', 'ISAP', 'JGLE', 'JIHD', 'KAQI',
        'KICI', 'KLIN', 'KOTA', 'KPIG', 'LFLO', 'LIVE', 'LMAX', 'LMPI', 'LPIN', 'LPPF',
        'MAPA', 'MAPB', 'MAPI', 'MDIA', 'MDIY', 'MEJA', 'MERI', 'MGLV', 'MICE', 'MKNT',
        'MNCN', 'MSIN', 'MSKY', 'OLIV', 'PANR', 'PART', 'PDES', 'PGLI', 'PJAA', 'PLAN',
        'PMJS', 'PMUI', 'POLU', 'PSKT', 'PTSP', 'PZZA', 'RAAM', 'RALS', 'SCNP', 'SHID',
        'SLIS', 'SMSM', 'SNLK', 'SOFA', 'SOTS', 'SPRE', 'SSTM', 'SWID', 'TFCO', 'TMPO',
        'TOOL', 'TRIS', 'TYRE', 'UFOE', 'VERN', 'VKTR', 'WOOD', 'YELO', 'ZONE'
    ],
    'Healthcare': [
        'BMHS', 'CARE', 'CHEK', 'DGNS', 'DVLA', 'HALO', 'HEAL', 'IKPM', 'IRRA', 'KLBF',
        'LABS', 'MDLA', 'MEDS', 'MERK', 'MIKA', 'MMIX', 'MTMH', 'OBAT', 'OMED', 'PEHA',
        'PEVE', 'PRAY', 'PRDA', 'PRIM', 'RSCH', 'RSGK', 'SAME', 'SCPI', 'SILO', 'SOHO',
        'SURI', 'TSPC'
    ],
    'Real Estate': [
        'ADCP', 'AMAN', 'APLN', 'ASPI', 'ASRI', 'ATAP', 'BAPI', 'BBSS', 'BCIP', 'BEST',
        'BIPP', 'BKDP', 'BKSL', 'BSBK', 'BSDE', 'CITY', 'CSIS', 'CTRA', 'DADA', 'DILD',
        'DMAS', 'DUTI', 'ELTY', 'EMDE', 'FMII', 'GMTD', 'GPRA', 'GRIA', 'HBAT', 'HOMI',
        'INPP', 'IPAC', 'JRPT', 'KBAG', 'KIJA', 'KOCI', 'LAND', 'LPCK', 'LPLI', 'MKPI',
        'MMLP', 'MSIE', 'MTLA', 'MTSM', 'NZIA', 'PAMG', 'PLIN', 'POLI', 'PURI', 'RBMS',
        'REAL', 'RELF', 'RISE', 'ROCK', 'RODA', 'SAGE', 'SATU', 'SMDM', 'SMRA', 'UANG',
        'URBN', 'VAST', 'WINR'
    ],
    'Technology': [
        'AREA', 'ATIC', 'AWAN', 'AXIO', 'BELI', 'CASH', 'CHIP', 'CYBR', 'DCII', 'DIVA',
        'DMMX', 'ELIT', 'GLVA', 'HDIT', 'IOTF', 'IRSX', 'JATI', 'KIOS', 'KREN', 'LUCK',
        'MCAS', 'MLPT', 'MPIX', 'MSTI', 'MTDL', 'NFCX', 'PGJO', 'PTSN', 'RUNS', 'TFAS',
        'TOSK', 'TRON', 'UVCR', 'WGSH', 'WIFI', 'WIRG', 'ZYRX'
    ],
    'Infrastructures': [
        'ASLI', 'BALI', 'BDKR', 'CASS', 'CMNP', 'DATA', 'DGIK', 'EXCL', 'FIMP', 'GHON',
        'GOLD', 'HADE', 'IBST', 'IDPR', 'INET', 'IPCM', 'ISAT', 'JAST', 'JKON', 'JSMR',
        'KARW', 'KEEN', 'KETR', 'KOKA', 'MANG', 'META', 'MORA', 'MPOW', 'MTEL', 'MTPS',
        'NRCA', 'PORT', 'POWR', 'PPRE', 'PTPP', 'PTPW', 'SMKM', 'SSIA', 'SUPR', 'TAMA',
        'TLKM', 'TOTL', 'WEGE'
    ],
    'Transportation & Logistics': [
        'AKSI', 'ASSA', 'BIRD', 'BLOG', 'BLTA', 'CMPP', 'ELPI', 'GIAA', 'GTRA', 'HAIS',
        'HATM', 'HELI', 'JAYA', 'KJEN', 'KLAS', 'LAJU', 'LOPI', 'LRNA', 'MIRA', 'MITI',
        'NELY', 'PJHB', 'PPGL', 'PURA', 'RCCC', 'SAFE', 'SAPX', 'SMDR', 'TAXI', 'TMAS',
        'TNCA', 'TRJA', 'TRUK', 'WBSA', 'WEHA'
    ]
}

def clean_company_name(name: str, ticker: str) -> str:
    if not name or name.strip() == "":
        return f"{ticker} Tbk"
    name = name.replace('"', '').replace(',', ' ').strip()
    # Normalize double spaces
    while '  ' in name:
        name = name.replace('  ', ' ')
    return name

def fetch_ticker_name(symbol_jk: str, default_name: str = None) -> tuple:
    ticker = symbol_jk.replace('.JK', '')
    if default_name and default_name != symbol_jk:
        return symbol_jk, clean_company_name(default_name, ticker)
    try:
        t = yf.Ticker(symbol_jk)
        info = t.info
        name = info.get('longName') or info.get('shortName') or f"{ticker} Tbk"
        return symbol_jk, clean_company_name(name, ticker)
    except Exception:
        return symbol_jk, f"{ticker} Tbk"

def main():
    csv_path = "data/idx_symbols.csv"
    existing_map = {}
    if os.path.exists(csv_path):
        df_old = pd.read_csv(csv_path)
        for _, row in df_old.iterrows():
            sym = str(row['symbol']).strip().upper()
            existing_map[sym] = {
                'name': str(row.get('name', '')),
                'sector': str(row.get('sector', ''))
            }

    # Build full list of (symbol_jk, ticker, sector)
    all_tickers = []
    seen = set()

    for sector, tickers in SECTOR_MAP.items():
        for t in tickers:
            t = t.strip().upper()
            sym_jk = f"{t}.JK"
            if sym_jk not in seen:
                seen.add(sym_jk)
                all_tickers.append((sym_jk, t, sector))

    # Keep any existing symbols not in the new list (e.g. BBCA, BBRI, BMRI, BBNI, etc.)
    for sym, val in existing_map.items():
        if sym not in seen:
            seen.add(sym)
            t = sym.replace('.JK', '')
            all_tickers.append((sym, t, val['sector'] or 'Financials'))

    print(f"Total symbols to process: {len(all_tickers)}")

    # Collect tasks to fetch names
    name_tasks = []
    for sym_jk, t, sector in all_tickers:
        existing_name = existing_map.get(sym_jk, {}).get('name')
        name_tasks.append((sym_jk, existing_name))

    print(f"Resolving names with ThreadPoolExecutor...")
    names_dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        future_to_sym = {executor.submit(fetch_ticker_name, sym, name): sym for sym, name in name_tasks}
        for future in concurrent.futures.as_completed(future_to_sym):
            sym, name = future.result()
            names_dict[sym] = name

    # Build final rows
    rows = []
    for sym_jk, t, sector in all_tickers:
        name = names_dict.get(sym_jk, f"{t} Tbk")
        rows.append({
            'symbol': sym_jk,
            'name': name,
            'sector': sector
        })

    # Sort alphabetically by symbol
    df_new = pd.DataFrame(rows)
    df_new.sort_values(by='symbol', inplace=True)
    df_new.reset_index(drop=True, inplace=True)

    # Save to CSV
    df_new.to_csv(csv_path, index=False)
    print(f"Saved {len(df_new)} symbols to {csv_path}")

    # Seed into database
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        repositories.seed_symbols_from_csv(db, csv_path=csv_path)
        active_count = len(repositories.get_active_symbols(db))
        print(f"Database seeded successfully. Active symbols in DB: {active_count}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
