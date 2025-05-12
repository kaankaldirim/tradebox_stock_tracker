import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
import numpy as np

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
    df_display['Prev Close'] = prev_day_closes.reindex(df_display.index)
    df_display['% Change'] = ((df_display[f'Close ({last_trading_day.strftime("%Y-%m-%d")})'] - df_display['Prev Close']) / df_display['Prev Close']) * 100
else:
    df_display['Prev Close'] = float('nan')
    df_display['% Change'] = float('nan')

# Get Market Cap and Pre-market Data
market_caps_dict = {}
premarket_price_dict = {}
premarket_change_dict = {}

us_eastern = pytz.timezone('US/Eastern')
now_utc = datetime.datetime.now(datetime.timezone.utc)
now_est = now_utc.astimezone(us_eastern)

for ticker_symbol in df_display['Ticker']:
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        info = ticker_obj.fast_info
        market_caps_dict[ticker_symbol] = info.get('marketCap', float('nan'))
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
    except Exception:
        market_caps_dict[ticker_symbol] = float('nan')
        premarket_price_dict[ticker_symbol] = np.nan
        premarket_change_dict[ticker_symbol] = np.nan

df_display['Market Cap'] = df_display['Ticker'].map(market_caps_dict)
df_display['Pre-market Price'] = df_display['Ticker'].map(premarket_price_dict)
df_display['Pre-market % Change'] = df_display['Ticker'].map(premarket_change_dict)

# Reorder and select columns for display
cols = ['Ticker', f'Close ({last_trading_day.strftime("%Y-%m-%d")})', 'Prev Close', '% Change', 'Pre-market Price', 'Pre-market % Change', 'Market Cap']
df_display = df_display[cols]

# Format for display with conditional coloring
def highlight_change(val):
    if pd.isnull(val):
        return ''
    color = 'red' if val < 0 else 'green'
    return f'color: {color};'

styled = df_display.style.format({
    f'Close ({last_trading_day.strftime("%Y-%m-%d")})': '{:,.2f}',
    'Prev Close': '{:,.2f}',
    '% Change': '{:.2f}%',
    'Pre-market Price': '{:,.2f}',
    'Pre-market % Change': '{:.2f}%',
    'Market Cap': lambda x: '{:,.0f}'.format(x) if pd.notnull(x) else 'N/A'
}).applymap(highlight_change, subset=['% Change', 'Pre-market % Change'])

st.dataframe(styled, use_container_width=True) 