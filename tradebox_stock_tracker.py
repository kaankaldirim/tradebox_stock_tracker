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

st.set_page_config(page_title="Tradebox Stock Tracker", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700&display=swap');
.header-title {
    font-family: 'Orbitron', monospace;
    font-size: 3em;
    color: #FFD700;
    letter-spacing: 2px;
    text-shadow: 0 2px 8px #222, 0 0px 1px #FFD700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 0.1em;
}
.header-emoji {
    font-size: 1.3em;
    margin-right: 18px;
    animation: bounce 1.2s infinite alternate;
}
@keyframes bounce {
    0% { transform: translateY(0);}
    100% { transform: translateY(-8px);}
}
.header-underline {
    width: 60%;
    margin: 0 auto 18px auto;
    border: 0;
    border-top: 3px solid #FFD700;
    opacity: 0.7;
}
</style>
<div class="header-title">
  <span class="header-emoji">📈🚀</span>
  Tradebox Stock Tracker
</div>
<hr class="header-underline">
""", unsafe_allow_html=True)

# --- MODERN INDEX CARDS ---
import yfinance as yf
import time

major_indices = {
    'NASDAQ 100': '^NDX',
    'S&P 500': '^GSPC',
    'Dow Jones': '^DJI',
    'Russell 2000': '^RUT',
    'VIX': '^VIX',
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

st.markdown("""
<style>
.index-card {
    background: linear-gradient(90deg, #232526 0%, #414345 100%);
    border-radius: 10px;
    padding: 12px 0 8px 0;
    margin-bottom: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}
</style>
""", unsafe_allow_html=True)

cols = st.columns(len(major_indices))
for i, name in enumerate(major_indices):
    price = index_prices.get(name)
    change = index_changes.get(name)
    price_str = f"{price:,.2f}" if price is not None else "N/A"
    if change is not None:
        color = "#00FF41" if change >= 0 else "#FF4136"
        sign = "+" if change >= 0 else ""
        change_str = f"<span style='color:{color}; font-weight:bold;'>{sign}{change:.2f}%</span>"
    else:
        change_str = "<span style='color:gray;'>N/A</span>"
    cols[i].markdown(
        f"<div class='index-card' style='text-align:center; font-size:1.1em;'>"
        f"<b>{name}</b><br>"
        f"<span style='color:#FFD700; font-size:1.3em;'>{price_str}</span><br>"
        f"{change_str}</div>",
        unsafe_allow_html=True
    )

# Ticker list
tickers = [
    'COIN','MSTR','MU','NEE','QCOM','MSFT','BSX','LMT','RTX','C','PLTR','IONQ','RGTI','CEG','LLY',
    'QQQ','SPY','TLT','VXX','NVO','RIOT','GOOGL','NVDA','AMZN','TSLA','MRVL','AA','AAL','AMD','FCX'
]

# Calculate the target "last Friday" date
today = datetime.date.today()
if today.weekday() >= 4: # Friday, Saturday, Sunday
    # Last Friday is this week's Friday
    days_to_subtract = today.weekday() - 4
else: # Monday, Tuesday, Wednesday, Thursday
    # Last Friday is last week's Friday
    days_to_subtract = today.weekday() + 3
target_friday_date = today - datetime.timedelta(days=days_to_subtract)
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

# Find the last available trading day on or before target Friday
dates_before_friday = close_prices_hist.index[close_prices_hist.index <= target_friday_ts]
if len(dates_before_friday) == 0:
    st.error(f"No trading data found on or before {target_friday_ts.strftime('%Y-%m-%d')}.")
    st.stop()
last_trading_day = dates_before_friday[-1]

# Find the previous trading day (for % change)
if len(dates_before_friday) < 2:
    prev_trading_day = None
else:
    prev_trading_day = dates_before_friday[-2]

# Prepare the main DataFrame for display
last_day_closes = close_prices_hist.loc[last_trading_day]
df_display = pd.DataFrame(index=last_day_closes.index)
df_display['Ticker'] = df_display.index
df_display[f'Close ({last_trading_day.strftime("%Y-%m-%d")})'] = last_day_closes

if prev_trading_day is not None:
    prev_day_closes = close_prices_hist.loc[prev_trading_day]
    df_display['% Change'] = ((df_display[f'Close ({last_trading_day.strftime("%Y-%m-%d")})'] - prev_day_closes) / prev_day_closes) * 100
else:
    df_display['% Change'] = float('nan')

def fetch_ticker_data(ticker_symbol, friday_close):
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        info = ticker_obj.fast_info
        # Last price
        hist = ticker_obj.history(period="1d", interval="1m")
        last_price = hist['Close'].iloc[-1] if not hist.empty else None
        # Last price % change from last Friday close
        if pd.notnull(last_price) and pd.notnull(friday_close) and friday_close != 0:
            last_price_change = ((last_price - friday_close) / friday_close) * 100
        else:
            last_price_change = None
        # Pre-market price
        pre_hist = ticker_obj.history(period="1d", interval="1m", prepost=True)
        premarket_price = pre_hist['Close'].iloc[-1] if not pre_hist.empty else None
        # Pre-market % change
        if pd.notnull(premarket_price) and pd.notnull(friday_close) and friday_close != 0:
            premarket_change = ((premarket_price - friday_close) / friday_close) * 100
        else:
            premarket_change = None
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
            "Pre-market Price": premarket_price,
            "Pre-market % Change": premarket_change,
            "Market Cap": market_cap,
            "P/E Ratio": pe,
        }
    except Exception:
        return {
            "Ticker": ticker_symbol,
            "Last Price": None,
            "Last Price % Change": None,
            "Pre-market Price": None,
            "Pre-market % Change": None,
            "Market Cap": None,
            "P/E Ratio": None,
        }

# Get last Friday close prices for all tickers (from previous yf.download)
friday_close_dict = {}
for ticker in tickers:
    try:
        friday_close_dict[ticker] = last_day_closes[ticker]
    except Exception:
        friday_close_dict[ticker] = None

with ThreadPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(lambda t: fetch_ticker_data(t, friday_close_dict.get(t)), df_display['Ticker']))

# Build DataFrame from results
parallel_df = pd.DataFrame(results).set_index('Ticker')

# Merge with df_display to keep the same order and index
for col in parallel_df.columns:
    df_display[col] = parallel_df[col]

# Adjust the columns for display: move 'Last Price' right after 'Ticker'
cols = ['Ticker', 'Last Price', 'Last Price % Change', 'Pre-market Price', 'Pre-market % Change', 'Market Cap', 'P/E Ratio']
df_display = df_display[cols]

# Ensure all None values are replaced with np.nan for Arrow compatibility
for col in df_display.columns:
    df_display[col] = df_display[col].replace({None: np.nan})
    # Also, if column is object type, try to convert to numeric (ignore errors)
    if df_display[col].dtype == object:
        df_display[col] = pd.to_numeric(df_display[col], errors='ignore')

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

st.sidebar.button("Refresh Data", on_click=st.cache_data.clear, help="Click to refresh all data immediately.")

def remove_week_caption():
    pass  # This is just a placeholder to indicate removal 