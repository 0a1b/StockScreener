AI slob:

A lightweight, automated stock screener designed to run on **OpenWrt routers** or low-power Linux devices. It scans the **NASDAQ 100**, **S&P 500**, and a custom watchlist for technical breakout signals and sends rich notifications via **Telegram**.

## ✨ Features

*   **📊 Technical Analysis:** Detects **200-Day EMA Crossovers**, **Golden Crosses** (50 > 200), and **Death Crosses** (50 < 200).
*   **🇪🇺 EU-Friendly:** Bypasses Yahoo Finance GDPR/Geo-blocks by scraping **Finviz** for fundamental data (P/E Ratio, Company Name).
*   **🚀 Dynamic Watchlists:** Automatically scrapes **Slickcharts** for the latest S&P 500 & NASDAQ 100 components every run.
*   **📉 Charts & Trends:** Generates instant price charts with EMA trendlines using the QuickChart API.
*   **🛡️ Spam Protection:** Uses a local state file (`screener_state.json`) to prevent duplicate alerts for the same stock on the same day.
*   **⚡ Lightweight:** Built with pure Python (`requests` only) — no heavy libraries like `pandas` or `numpy`.

***

## 🛠️ Prerequisites

### 1. Router Dependencies
SSH into your OpenWrt router and install Python 3:

```bash
opkg update
opkg install python3-light python3-pip python3-requests python3-openssl ca-certificates
# Optional: For easier file transfer
opkg install openssh-sftp-server
```

### 2. Telegram Configuration
1.  Chat with **[@BotFather](https://t.me/BotFather)** to create a bot and get your `BOT_TOKEN`.
2.  Chat with **[@userinfobot](https://t.me/userinfobot)** to get your numeric `CHAT_ID`.
3.  Edit `screener.py` and update the configuration section:

```python
# --- CONFIGURATION ---
BOT_TOKEN = "123456789:AbCdeF..."
CHAT_ID = "987654321"
```

***

## 📦 Installation

### 1. Transfer Files
Copy the script and your custom watchlist to the router using `scp`. 
*(Note: Use `-O` for legacy SCP protocol if you didn't install sftp-server)*.

```bash
# Copy the script
scp -O screener.py root@192.168.1.120:/root/screener.py

# Copy custom watchlist (optional)
scp -O lookup_stocks root@192.168.1.120:/root/lookup_stocks
```

### 2. Custom Watchlist (Optional)
Create a file named `lookup_stocks` in the same directory. Add tickers line-by-line or comma-separated:

```text
INTC
GME, AMC
PLTR
```

***

## 🤖 Automation (Cron)

To run the scanner automatically every weekday (Mon-Fri) at **10:00 PM**:

1.  SSH into your router.
2.  Edit the crontab: `crontab -e`
3.  Add the following line:

```cron
0 22 * * 1-5 /usr/bin/python3 /root/screener.py >> /tmp/screener.log 2>&1
```

4.  Restart cron:
```bash
/etc/init.d/cron restart
```

***

## 🔍 Usage

### Manual Run
You can trigger a scan manually at any time:

```bash
python3 /root/screener.py
```

### Resetting Daily Alerts
The script tracks sent alerts in `screener_state.json`. To force a re-scan of stocks you've already seen today:

```bash
rm /root/screener_state.json
```

***

## 📝 Troubleshooting

| Issue | Solution |
| :--- | :--- |
| `scp: /usr/libexec/sftp-server: not found` | Use `scp -O ...` (legacy mode) or install `openssh-sftp-server`. |
| **Telegram Photo Error 400** | The script automatically handles URL shortening. If this persists, check if the stock symbol is valid. |
| **Yahoo "User unable to access"** | The script uses **Finviz** for fundamentals to fix this. Ensure your router isn't blocking `finviz.com`. |
| `NameError: name '__file__' is not defined` | This happens in Jupyter Notebooks. The script includes a fallback to `os.getcwd()` to fix this. |

***

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).
```
