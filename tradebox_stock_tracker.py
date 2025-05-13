import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
import numpy as np
import requests
from bs4 import BeautifulSoup
import feedparser
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import asyncio
import aiohttp
import nest_asyncio

st.set_page_config(page_title="Tradebox Stock Tracker", layout="wide")

# Ticker list (move this up before async scraping)
tickers = [
    'COIN','MSTR','MU','NEE','QCOM','MSFT','BSX','LMT','RTX','C','PLTR','IONQ','RGTI','CEG','LLY',
    'QQQ','DELL','TLT','NVO','RIOT','GOOGL','NVDA','AMZN','TSLA','MRVL','AA','AAL','AMD','FCX',
    'ONON'  # Added ONON
]

nest_asyncio.apply()

async def fetch_google_data(session, ticker):
    for suffix in [':NASDAQ', ':NYSE']:
        url = f"https://www.google.com/finance/quote/{ticker}{suffix}"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            async with session.get(url, headers=headers, timeout=5) as r:
                text = await r.text()
                soup = BeautifulSoup(text, "html.parser")
                price = soup.find("div", class_="YMlKec fxKbKc")
                name = soup.find("div", class_="zzDege")
                close_val = float(price.text.replace(",", "").replace("$", "")) if price else None
                company_name = name.text.strip() if name else ''
                if close_val:
                    return ticker, close_val, company_name
        except Exception:
            continue
    return ticker, None, ''

async def fetch_all_google_data(tickers):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_google_data(session, ticker) for ticker in tickers]
        results = await asyncio.gather(*tasks)
    return results

# Fetch all company names and close prices in parallel
loop = asyncio.get_event_loop()
google_results = loop.run_until_complete(fetch_all_google_data(tickers))
last_official_close_dict = {t: c for t, c, n in google_results}
company_names = {t: n for t, c, n in google_results}

# --- MODERN INDEX CARDS ---
import yfinance as yf
import time

major_indices = {
    'NASDAQ 100': '^NDX',
    'S&P 500': '^GSPC',
    'Dow Jones': '^DJI',
    'Russell 2000': '^RUT',
    'VIX': '^VIX',
    'Bitcoin': 'BTC-USD',
    'Ethereum': 'ETH-USD',
    'US10Y': '^TNX',
}

# Assign a unique color for each index label
index_label_colors = {
    'NASDAQ 100': '#1f77b4',  # blue
    'S&P 500': '#ff7f0e',     # orange
    'Dow Jones': '#2ca02c',   # green
    'Russell 2000': '#d62728',# red
    'VIX': '#9467bd',         # purple
    'Bitcoin': '#f2b90c',     # gold
}

@st.cache_data(ttl=300)
def get_index_prices_and_changes():
    prices = {}
    changes = {}
    for name, symbol in major_indices.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d", interval="1m")['Close']
            if not hist.empty:
                last_price = hist.iloc[-1]
                daily = ticker.history(period="2d", interval="1d")['Close']
                if len(daily) >= 2:
                    prev_close = daily.iloc[-2]
                else:
                    prev_close = None
                prices[name] = last_price
                if prev_close and prev_close != 0:
                    change = ((last_price - prev_close) / prev_close) * 100
                    changes[name] = change
                else:
                    changes[name] = None
            else:
                prices[name] = None
                changes[name] = None
        except Exception:
            prices[name] = None
            changes[name] = None
    return prices, changes

index_prices, index_changes = get_index_prices_and_changes()

# --- Modern white header (no emoji, no yellow, no image) ---
st.markdown("""
<style>
.header-title-modern {
    font-family: 'Roboto', 'Segoe UI', Arial, sans-serif;
    font-size: 2.7em;
    color: #222;
    letter-spacing: 1.5px;
    text-align: left;
    font-weight: 700;
    margin-bottom: 0.1em;
    margin-left: 10px;
}
@media (prefers-color-scheme: dark) {
    .header-title-modern { color: #fff; }
}
@media (max-width: 600px) {
    .header-title-modern {
        font-size: 1.3em;
        margin-top: 0.5em;
        margin-left: 4px;
    }
    .index-bar-cards {
        gap: 8px !important;
        padding: 4px 0 8px 0 !important;
    }
    .index-card {
        min-width: 120px !important;
        padding: 8px 8px !important;
    }
    .header-underline-modern {
        width: 90% !important;
    }
}
.index-bar-cards {
    display: flex;
    gap: 16px;
    overflow-x: auto;
    padding: 8px 0 12px 0;
    margin-bottom: 18px;
    scrollbar-color: #888 #222;
    scrollbar-width: thin;
}
.index-card {
    min-width: 150px;
    background: #23272f;
    border-radius: 10px;
    color: white;
    padding: 12px 18px;
    box-shadow: 0 2px 8px #0002;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    font-family: 'Roboto', 'Segoe UI', Arial, sans-serif;
}
.index-card.green { background: #1e7e34; }
.index-card.red { background: #c82333; }
.index-card.gray { background: #444; }
.index-title { font-weight: bold; font-size: 1.1em; letter-spacing: 0.5px; }
.index-price { font-size: 1.3em; margin: 4px 0; }
.index-change { font-size: 1em; }
.index-time { font-size: 0.85em; color: #ccc; margin-top: 4px; }
div[data-testid="stDataFrame"] > div {
    overflow-x: auto !important;
}
@media (max-width: 600px) {
    .index-title, .index-price, .index-change, .index-time {
        font-size: 0.95em !important;
    }
    .index-card {
        min-width: 110px !important;
        padding: 6px 6px !important;
    }
}
.header-underline-modern {
    width: 60%;
    margin: 0 0 18px 10px;
    border: 0;
    border-top: 3px solid #444;
    opacity: 0.7;
}
</style>
<div class="header-title-modern">
  Tradebox Stock Tracker
</div>
<hr class="header-underline-modern">
""", unsafe_allow_html=True)

# Only one centered Refresh Data button above the index cards
st.markdown('<div style="display:flex;justify-content:center;margin-bottom:10px;">', unsafe_allow_html=True)
if st.button("Refresh Data", help="Click to refresh all data immediately."):
    st.cache_data.clear()
st.markdown('</div>', unsafe_allow_html=True)

# Add GOLD (XAUUSD=X) to the major_indices and index bar
define_gold = False
if 'GOLD' not in major_indices:
    major_indices['GOLD'] = 'XAUUSD=X'

# --- Modern index bar as cards (horizontal scrollable) ---
from datetime import datetime

def get_index_time(symbol):
    # Try to get the latest time for the index (using yfinance), show as GMT+3 (Istanbul)
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="1m")
        if not hist.empty:
            ts = hist.index[-1]
            istanbul = pytz.timezone('Europe/Istanbul')
            ts_ist = ts.tz_localize('UTC').astimezone(istanbul) if ts.tzinfo is None else ts.astimezone(istanbul)
            return ts_ist.strftime('%H:%M')
    except Exception:
        pass
    return "-"

bar_card_items = []
for name, symbol in major_indices.items():
    price = index_prices.get(name)
    change = index_changes.get(name)
    price_str = f"{price:,.2f}" if price is not None else "N/A"
    time_str = get_index_time(symbol)
    if change is not None:
        color_class = "green" if change >= 0 else "red"
        sign = "+" if change >= 0 else ""
        change_str = f"{sign}{change:.2f}%"
    else:
        color_class = "gray"
        change_str = "N/A"
    bar_card_items.append(
        f"<div class='index-card {color_class}'><div class='index-title'>{name}</div><div class='index-price'>{price_str}</div><div class='index-change'>{change_str}</div><div class='index-time'>{time_str}</div></div>"
    )
bar_cards_html = ''.join(bar_card_items)

st.markdown(f"""
<style>
.index-bar-cards {{
  display: flex;
  gap: 16px;
  overflow-x: auto;
  padding: 8px 0 12px 0;
  margin-bottom: 18px;
  scrollbar-color: #888 #222;
  scrollbar-width: thin;
}}
.index-card {{
  min-width: 150px;
  background: #23272f;
  border-radius: 10px;
  color: white;
  padding: 12px 18px;
  box-shadow: 0 2px 8px #0002;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  font-family: 'Roboto', 'Segoe UI', Arial, sans-serif;
}}
.index-card.green {{ background: #1e7e34; }}
.index-card.red {{ background: #c82333; }}
.index-card.gray {{ background: #444; }}
.index-title {{ font-weight: bold; font-size: 1.1em; letter-spacing: 0.5px; }}
.index-price {{ font-size: 1.3em; margin: 4px 0; }}
.index-change {{ font-size: 1em; }}
.index-time {{ font-size: 0.85em; color: #ccc; margin-top: 4px; }}
</style>
<div class="index-bar-cards">{bar_cards_html}</div>
""", unsafe_allow_html=True)

# Calculate the target "last Friday" date
today = date.today()
if today.weekday() >= 4: # Friday, Saturday, Sunday
    # Last Friday is this week's Friday
    days_to_subtract = today.weekday() - 4
else: # Monday, Tuesday, Wednesday, Thursday
    # Last Friday is last week's Friday
    days_to_subtract = today.weekday() + 3
target_friday_date = today - timedelta(days=days_to_subtract)
target_friday_ts = pd.Timestamp(target_friday_date)

# Define data fetching period
start_download_date = target_friday_ts - pd.Timedelta(days=15)
end_download_date = target_friday_ts + pd.Timedelta(days=1)

# Show last refresh time
now = time.strftime('%Y-%m-%d %H:%M:%S')
st.caption(f"Last data refresh: {now}")

# Download historical data
try:
    hist_data_all_fields = yf.download(tickers, start=start_download_date, end=end_download_date, progress=False)
    if hist_data_all_fields.empty:
        st.error(f"No historical data downloaded for the period around {target_friday_ts.strftime('%Y-%m-%d')}.")
        st.stop()
    close_prices_hist = hist_data_all_fields['Close']
    # If only one ticker, yf.download might return a Series for 'Close'. Ensure it's a DataFrame.
    if isinstance(close_prices_hist, pd.Series):
        close_prices_hist = close_prices_hist.to_frame(name=tickers[0] if len(tickers) == 1 else 'Close')
        if len(tickers) == 1 : # if it was a series and became a frame, column name is ticker
             pass # Already named correctly
        elif 'Close' in close_prices_hist.columns and len(tickers) >1 : #Should not happen often with list of tickers
             st.warning("Unexpected data structure for close_prices_hist from yfinance.")


except Exception as e:
    st.error(f"Error downloading data from Yahoo Finance: {e}")
    st.stop()

# Filter data up to the target Friday and ensure index is DatetimeIndex
df_idx = close_prices_hist.index
if not isinstance(df_idx, pd.DatetimeIndex):
    close_prices_hist.index = pd.to_datetime(close_prices_hist.index)

# Find the last available trading day BEFORE today (for pre-market % change)
dates_before_today = close_prices_hist.index[close_prices_hist.index < pd.Timestamp.today().normalize()]
if len(dates_before_today) == 0:
    st.error(f"No trading data found before today.")
    st.stop()
last_trading_day = dates_before_today[-1]

# Prepare the main DataFrame for display
last_day_closes = close_prices_hist.loc[last_trading_day]
df_display = pd.DataFrame(index=last_day_closes.index)
df_display['Ticker'] = df_display.index
# Add company name column using async results
df_display['Company Name'] = df_display['Ticker'].map(company_names)
df_display[f'Close ({last_trading_day.strftime("%Y-%m-%d")})'] = last_day_closes

# Find the previous trading day (for % change)
dates_before_last = close_prices_hist.index[close_prices_hist.index < last_trading_day]
if len(dates_before_last) == 0:
    prev_trading_day = None
else:
    prev_trading_day = dates_before_last[-1]

if prev_trading_day is not None:
    prev_day_closes = close_prices_hist.loc[prev_trading_day]
    df_display['% Change'] = ((df_display[f'Close ({last_trading_day.strftime("%Y-%m-%d")})'] - prev_day_closes) / prev_day_closes) * 100
else:
    df_display['% Change'] = float('nan')

# --- Modify fetch_ticker_data to use last_official_close for pre-market % change ---
def fetch_ticker_data(ticker_symbol, last_official_close):
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        info = ticker_obj.fast_info
        # Last price
        hist = ticker_obj.history(period="1d", interval="1m")
        last_price = hist['Close'].iloc[-1] if not hist.empty else None
        # Last price % change from last official close
        if pd.notnull(last_price) and pd.notnull(last_official_close) and last_official_close != 0:
            last_price_change = ((last_price - last_official_close) / last_official_close) * 100
        else:
            last_price_change = None
        # Pre-market price: only use the latest price before 09:30 US/Eastern
        us_eastern = pytz.timezone('US/Eastern')
        pre_hist = ticker_obj.history(period="2d", interval="1m", prepost=True)
        pre_market_price = None
        pre_market_ts = None
        if not pre_hist.empty:
            for ts, row in pre_hist.iloc[::-1].iterrows():
                ts_est = ts.tz_convert(us_eastern)
                if ts_est.hour < 9 or (ts_est.hour == 9 and ts_est.minute < 30):
                    pre_market_price = row['Close']
                    pre_market_ts = ts_est
                    break
        # Pre-market % change: only if pre-market price exists
        if pre_market_price is not None and last_official_close is not None and last_official_close != 0:
            pre_market_change = ((pre_market_price - last_official_close) / last_official_close) * 100
        else:
            pre_market_change = None
        # Market cap, P/E
        market_cap = info.get('marketCap', None)
        pe = info.get('pe_ratio', None)
        if pe is None:
            try:
                pe = ticker_obj.info.get('trailingPE', None)
            except Exception:
                pe = None
        return {
            "Ticker": ticker_symbol,
            "Last Price": last_price,
            "Last Price % Change": last_price_change,
            "Pre-market Price": pre_market_price,
            "Pre-market % Change": pre_market_change,
            "Market Cap": market_cap,
            "P/E Ratio": pe,
        }
    except Exception as e:
        print(f"Error for {ticker_symbol}: {e}")
        return {
            "Ticker": ticker_symbol,
            "Last Price": None,
            "Last Price % Change": None,
            "Pre-market Price": None,
            "Pre-market % Change": None,
            "Market Cap": None,
            "P/E Ratio": None,
        }

# --- Update ThreadPoolExecutor to pass last_official_close ---
with ThreadPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(lambda t: fetch_ticker_data(t, last_official_close_dict.get(t)), df_display['Ticker']))

# Build DataFrame from results
parallel_df = pd.DataFrame(results).set_index('Ticker')

# Merge with df_display to keep the same order and index
for col in parallel_df.columns:
    df_display[col] = parallel_df[col]

# Adjust the columns for display: move 'Last Price' right after 'Ticker'
cols = ['Ticker', 'Company Name', 'Last Price', 'Last Price % Change', 'Pre-market Price', 'Pre-market % Change', 'Market Cap', 'P/E Ratio']
df_display = df_display[cols]

# Ensure all None values are replaced with np.nan for Arrow compatibility
for col in df_display.columns:
    try:
        df_display[col] = pd.to_numeric(df_display[col])
    except Exception:
        pass

# Format for display with conditional coloring
def highlight_change(val):
    if pd.isnull(val):
        return ''
    color = 'red' if val < 0 else 'green'
    return f'color: {color};'

styled = df_display.style.format({
    'Pre-market Price': lambda x: f"{x:,.2f}" if pd.notnull(x) else "N/A",
    'Pre-market % Change': lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A",
    'Last Price': lambda x: f"{x:,.2f}" if pd.notnull(x) else "N/A",
    'Last Price % Change': lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A",
    'Market Cap': lambda x: f"{x:,.0f}" if pd.notnull(x) else "N/A",
    'P/E Ratio': lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A"
}).map(highlight_change, subset=['Pre-market % Change', 'Last Price % Change'])

st.dataframe(styled, use_container_width=True)

st.markdown('---')
st.header('📰 Latest Market News')

feed_url = "https://news.google.com/rss/search?q=stock+market"
feed = feedparser.parse(feed_url)

if feed.entries:
    for entry in feed.entries[:10]:
        st.markdown(f"- [{entry.title}]({entry.link})")
else:
    st.info("No news found.")

def remove_week_caption():
    pass  # This is just a placeholder to indicate removal 

# NOTE: Google Finance scraping is slow for many tickers. For production, consider async requests or caching results. 

# Remove the following from the end of the file:
# @st.cache_data(ttl=3600)
# def get_google_close_price_and_name(ticker):
#     try:
#         return yf.Ticker(ticker).info.get('shortName', ''), get_google_close_price_and_name(ticker)[0]
#     except Exception:
#         return '', 0 
# ... rest of code unchanged ... 