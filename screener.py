import requests
import datetime
import time
import json
import os
import re
import csv
import sys

# --- CONFIGURATION ---
# Get token from @BotFather
BOT_TOKEN = ""
# Get chat ID from @userinfobot
CHAT_ID = ""

# State file to prevent duplicate alerts
#STATE_FILE = "/root/screener_state.json"
STATE_FILE = "screener_state.json"

# URLs for dynamic lists
URL_NASDAQ = "https://www.slickcharts.com/nasdaq100"
URL_SP500 = "https://www.slickcharts.com/sp500"

# Local file in the same folder
LOCAL_FILE = "lookup_stocks"


# --- DATA GATHERING FUNCTIONS ---

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def clean(text):
    """Escapes special characters for Telegram HTML."""
    if text is None: return "N/A"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_state(state):
    try:
        with open(STATE_FILE, 'w') as f: json.dump(state, f)
    except: pass

def fetch_slickcharts_tickers(url):
    """Scrapes tickers from Slickcharts table."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            log(f"⚠️ Failed to fetch {url} ({r.status_code})")
            return []
        
        # Find symbols in links like <a href="/symbol/AAPL">
        symbols = re.findall(r'/symbol/([A-Z0-9.]+)', r.text)
        
        # Normalize dots to dashes for Yahoo (e.g. BRK.B -> BRK-B)
        normalized = [s.replace('.', '-') for s in symbols]
        log(f"✅ Fetched {len(normalized)} tickers from {url.split('/')[-1]}")
        return normalized
    except Exception as e:
        log(f"❌ Error fetching list: {e}")
        return []

def load_local_file(filename):
    """Reads tickers from a local CSV/text file."""
    tickers = []
    
    # --- FIX FOR JUPYTER / INTERACTIVE MODE ---
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd() # Fallback if __file__ is missing
    # ------------------------------------------
        
    path = os.path.join(base_dir, filename)
    
    # Try looking in current working directory too if path fails
    if not os.path.exists(path):
        path = filename
    
    if not os.path.exists(path):
        log(f"ℹ️ Local file '{filename}' not found, skipping.")
        return []
        
    try:
        with open(path, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                for item in row: # Handle multi-column or single-column
                    clean_item = item.strip().upper().replace('.', '-')
                    if clean_item:
                        tickers.append(clean_item)
        log(f"✅ Loaded {len(tickers)} tickers from {filename}")
    except Exception as e:
        log(f"❌ Error reading file: {e}")
    return tickers

# --- ANALYSIS FUNCTIONS ---

def fetch_fundamentals_finviz(ticker):
    # EU-Friendly Finviz Scraper
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: return ticker, "N/A"
        html = r.text
        
        title_match = re.search(r'<title>[^-]+- (.*?) Stock Price', html)
        name = title_match.group(1) if title_match else ticker
        
        pe_match = re.search(r'>P/E</td>.*?<b>(.*?)</b>', html, re.DOTALL)
        pe = pe_match.group(1) if pe_match else "N/A"
        if pe != "N/A": pe = re.sub(r'<.*?>', '', pe)
        
        return name, pe
    except:
        return ticker, "N/A"

def fetch_price_history(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=2y&interval=1d"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if not data['chart']['result']: return []
        res = data['chart']['result'][0]
        return [{'date': datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d'), 'close': c} 
                for t, c in zip(res['timestamp'], res['indicators']['quote'][0]['close']) if c is not None]
    except:
        return []

def calculate_ema(prices, period):
    if len(prices) < period: return []
    k = 2.0 / (period + 1)
    ema = [sum(prices[:period]) / period]
    ema.extend([None] * (period - 1))
    curr = ema[0]
    out = [None] * (period-1) + [curr]
    for price in prices[period:]:
        curr = (price * k) + (curr * (1 - k))
        out.append(curr)
    return out

def get_regime_start_date(dates, prices, ema200, current_state):
    for i in range(len(prices)-2, 0, -1):
        if ema200[i] is None: break
        state = "ABOVE" if prices[i] > ema200[i] else "BELOW"
        if state != current_state: return dates[i+1]
    return dates[0]

def generate_chart_url(ticker, dates, prices, ema50, ema200):
    limit = 100
    qc = {
        "type": "line",
        "data": {
            "labels": dates[-limit:],
            "datasets": [
                {"label": "Price", "data": prices[-limit:], "borderColor": "black", "fill": False, "pointRadius": 0, "borderWidth": 2},
                {"label": "EMA 50", "data": ema50[-limit:], "borderColor": "blue", "fill": False, "pointRadius": 0, "borderWidth": 1},
                {"label": "EMA 200", "data": ema200[-limit:], "borderColor": "red", "fill": False, "pointRadius": 0, "borderWidth": 1}
            ]
        },
        "options": {
            "title": {"display": True, "text": f"{ticker} Daily Chart"},
            "scales": {"xAxes": [{"display": False}], "yAxes": [{"display": True, "ticks": {"beginAtZero": False}}]}
        }
    }
    try:
        r = requests.post('https://quickchart.io/chart/create', json={'chart': qc, 'width': 800, 'height': 400})
        if r.status_code == 200: return r.json().get('url')
    except: pass
    return None

def send_telegram(caption, image_url):
    base = f"https://api.telegram.org/bot{BOT_TOKEN}"
    if image_url:
        try:
            requests.post(f"{base}/sendPhoto", data={'chat_id': CHAT_ID, 'photo': image_url, 'caption': caption, 'parse_mode': 'HTML'}, timeout=20)
            return
        except: pass
    requests.post(f"{base}/sendMessage", data={'chat_id': CHAT_ID, 'text': caption, 'parse_mode': 'HTML'}, timeout=20)

# --- MAIN ---

def main():
    log("--- STARTING STOCK SCAN ---")
    
    # 1. Build Watchlist
    nasdaq = fetch_slickcharts_tickers(URL_NASDAQ)
    sp500 = fetch_slickcharts_tickers(URL_SP500)
    local = load_local_file(LOCAL_FILE)
    
    # Deduplicate and Sort
    TICKERS = sorted(list(set(nasdaq + sp500 + local)))
    log(f"📋 Total unique stocks to scan: {len(TICKERS)}")
    
    state = load_state()
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    
    for i, ticker in enumerate(TICKERS):
        if i % 50 == 0 and i > 0: log(f"Progress: {i}/{len(TICKERS)}...")

        if state.get(ticker) == today_str:
            continue

        data = fetch_price_history(ticker)
        if len(data) < 201: continue
        
        closes = [d['close'] for d in data]
        dates = [d['date'] for d in data]
        ema50 = calculate_ema(closes, 50)
        ema200 = calculate_ema(closes, 200)
        
        if None in [ema200[-1], ema200[-2]]: continue

        msg = ""
        signal_type = ""
        
        if closes[-2] < ema200[-2] and closes[-1] > ema200[-1]:
            msg = "🚀 Price crossed <b>ABOVE</b> 200 EMA"
            signal_type = "ABOVE"
        elif closes[-2] > ema200[-2] and closes[-1] < ema200[-1]:
            msg = "🔻 Price crossed <b>BELOW</b> 200 EMA"
            signal_type = "BELOW"
        elif ema50[-2] and ema50[-2] < ema200[-2] and ema50[-1] > ema200[-1]:
            msg = "🌟 <b>GOLDEN CROSS</b> (50 &gt; 200)"
            signal_type = "ABOVE"
        elif ema50[-2] and ema50[-2] > ema200[-2] and ema50[-1] < ema200[-1]:
            msg = "☠️ <b>DEATH CROSS</b> (50 &lt; 200)"
            signal_type = "BELOW"

        if msg:
            log(f"🎯 Signal: {ticker}")
            name, pe = fetch_fundamentals_finviz(ticker)
            since_date = get_regime_start_date(dates, closes, ema200, signal_type)
            
            caption = (
                f"<b>{ticker}</b> - {clean(name)}\n"
                f"{msg}\n\n"
                f"📊 P/E Ratio: <b>{clean(pe)}</b>\n"
                f"📅 Trend Start: {since_date}\n"
                f"💵 Price: ${closes[-1]:.2f}"
            )
            
            chart = generate_chart_url(ticker, dates, closes, ema50, ema200)
            send_telegram(caption, chart)
            
            state[ticker] = today_str
            
        #time.sleep(2)
            
    save_state(state)
    log("--- SCAN COMPLETE ---")

if __name__ == "__main__":
    main()
