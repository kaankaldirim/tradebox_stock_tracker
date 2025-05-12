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

st.set_page_config(page_title="Tradebox Stock Tracker", layout="wide")
st.title("📈 Tradebox Stock Tracker")

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

st.caption(f"Data for week ending on Friday: {target_friday_ts.strftime('%Y-%m-%d')}")

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

# Get Market Cap and Pre-market Data
market_caps_dict = {}
premarket_price_dict = {}
premarket_change_dict = {}
pe_ratio_dict = {}
last_price_dict = {}
last_price_change_dict = {}

us_eastern = pytz.timezone('US/Eastern')
now_utc = datetime.datetime.now(datetime.timezone.utc)
now_est = now_utc.astimezone(us_eastern)

for ticker_symbol in df_display['Ticker']:
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        info = ticker_obj.fast_info
        market_caps_dict[ticker_symbol] = info.get('marketCap', float('nan'))
        # Last price using 1-minute bar
        try:
            hist = ticker_obj.history(period="1d", interval="1m")
            if not hist.empty:
                last_price = hist['Close'].iloc[-1]
            else:
                last_price = None
        except Exception:
            last_price = None
        last_price_dict[ticker_symbol] = last_price
        # Last price % change from last Friday close
        friday_close = df_display.loc[ticker_symbol, f'Close ({last_trading_day.strftime("%Y-%m-%d")})'] if f'Close ({last_trading_day.strftime("%Y-%m-%d")})' in df_display.columns else None
        if pd.notnull(last_price) and pd.notnull(friday_close) and friday_close != 0:
            last_price_change = ((last_price - friday_close) / friday_close) * 100
        else:
            last_price_change = None
        last_price_change_dict[ticker_symbol] = last_price_change
        # Get pre-market price using 1m interval
        hist = ticker_obj.history(period="1d", interval="1m", prepost=True)
        if not hist.empty:
            last_row = hist.iloc[-1]
            last_time = last_row.name.tz_convert(us_eastern) if last_row.name.tzinfo else us_eastern.localize(last_row.name)
            # Only show pre-market price if before 09:30 US/Eastern
            if last_time.hour < 9 or (last_time.hour == 9 and last_time.minute < 30):
                premarket_price = last_row['Close']
                premarket_price_dict[ticker_symbol] = premarket_price
                close_price = df_display.loc[ticker_symbol, f'Close ({last_trading_day.strftime("%Y-%m-%d")})']
                if pd.notnull(premarket_price) and pd.notnull(close_price) and close_price != 0:
                    premarket_change = ((premarket_price - close_price) / close_price) * 100
                else:
                    premarket_change = np.nan
                premarket_change_dict[ticker_symbol] = premarket_change
            else:
                premarket_price_dict[ticker_symbol] = np.nan
                premarket_change_dict[ticker_symbol] = np.nan
        else:
            premarket_price_dict[ticker_symbol] = np.nan
            premarket_change_dict[ticker_symbol] = np.nan
        # P/E ratio
        pe = info.get('pe_ratio', None)
        if pe is None:
            try:
                pe = ticker_obj.info.get('trailingPE', None)
            except Exception:
                pe = None
        pe_ratio_dict[ticker_symbol] = pe if pe is not None else None
    except Exception:
        market_caps_dict[ticker_symbol] = float('nan')
        premarket_price_dict[ticker_symbol] = np.nan
        premarket_change_dict[ticker_symbol] = np.nan
        last_price_dict[ticker_symbol] = None
        last_price_change_dict[ticker_symbol] = None
        pe_ratio_dict[ticker_symbol] = None

df_display['Market Cap'] = df_display['Ticker'].map(market_caps_dict)
df_display['Pre-market Price'] = df_display['Ticker'].map(premarket_price_dict)
df_display['Pre-market % Change'] = df_display['Ticker'].map(premarket_change_dict)
df_display['Last Price'] = df_display['Ticker'].map(last_price_dict)
df_display['Last Price % Change'] = df_display['Ticker'].map(last_price_change_dict)
df_display['P/E Ratio'] = df_display['Ticker'].map(pe_ratio_dict)

# Adjust the columns for display: move 'Last Price' right after 'Ticker'
cols = ['Ticker', 'Last Price', 'Last Price % Change', '% Change', 'Pre-market Price', 'Pre-market % Change', 'Market Cap', 'P/E Ratio']
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
    '% Change': lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A",
    'Pre-market Price': lambda x: f"{x:,.2f}" if pd.notnull(x) else "N/A",
    'Pre-market % Change': lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A",
    'Last Price': lambda x: f"{x:,.2f}" if pd.notnull(x) else "N/A",
    'Last Price % Change': lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A",
    'Market Cap': lambda x: f"{x:,.0f}" if pd.notnull(x) else "N/A",
    'P/E Ratio': lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A"
}).map(highlight_change, subset=['% Change', 'Pre-market % Change', 'Last Price % Change'])

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