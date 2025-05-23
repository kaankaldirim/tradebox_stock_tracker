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
import base64
import urllib.parse
import matplotlib.pyplot as plt
import io
import matplotlib.dates as mdates
import mplfinance as mpf
from functools import lru_cache
import json
from io import StringIO
import calendar
import random
import re

# --- NEWS KARTLARI İÇİN FAVICON, PREVIEW IMAGE ve KATEGORİ ---
def get_favicon(domain):
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=32"

def get_news_image(entry):
    # RSS'de media_content veya media:thumbnail veya links'te image olabilir
    if hasattr(entry, 'media_content') and entry.media_content:
        url = entry.media_content[0].get('url', '')
        if url: return url
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get('url', '')
        if url: return url
    if hasattr(entry, 'links'):
        for l in entry.links:
            if l.get('type', '').startswith('image'):
                url = l.get('href', '')
                if url: return url
    # Başlıktan anahtar kelime seç, Unsplash görseli oluştur
    stopwords = set(['the','a','an','and','or','for','to','of','in','on','at','by','with','is','are','was','were','be','as','from','that','this','it','its','but','not','will','may','can','should','after','up','over','why','how','if','so','than','then','out','off','into','about','more','less','new','old','all','any','some','no','yes','just','you','i','we','he','she','they','their','his','her','our','your','my','me','us','them','who','what','which','when','where'])
    title = getattr(entry, 'title', '')
    words = re.findall(r"\b\w+\b", title.lower())
    keywords = [w for w in words if w not in stopwords and len(w) > 2][:2]
    if keywords:
        unsplash_url = f"https://source.unsplash.com/600x400/?{','.join(keywords)}"
        return unsplash_url
    # Kategoriye göre fallback
    cat = None
    if hasattr(entry, 'title'):
        cat = get_category(entry.title)
    default_images = {
        "Tech": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=600&q=80",
        "Earnings": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=600&q=80",
        "Macro": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=600&q=80",
        "Dividend": "https://images.unsplash.com/photo-1464983953574-0892a716854b?auto=format&fit=crop&w=600&q=80",
        "General": "https://images.unsplash.com/photo-1465101046530-73398c7f28ca?auto=format&fit=crop&w=600&q=80"
    }
    return default_images.get(cat, default_images["General"])

def get_category(title):
    title = title.lower()
    if any(x in title for x in ["earnings", "profit", "revenue"]):
        return "Earnings"
    if any(x in title for x in ["dividend"]):
        return "Dividend"
    if any(x in title for x in ["inflation", "fed", "macro", "cpi", "ecb", "rate"]):
        return "Macro"
    if any(x in title for x in ["ai", "tech", "chip", "semiconductor", "nvidia", "apple", "google", "microsoft"]):
        return "Tech"
    return "General"

# --- Market Movers veri çekme fonksiyonu ---
@lru_cache(maxsize=3)
def get_yahoo_movers(mover_type):
    url_map = {
        'gainers': 'https://finance.yahoo.com/screener/predefined/day_gainers',
        'losers': 'https://finance.yahoo.com/screener/predefined/day_losers',
        'actives': 'https://finance.yahoo.com/screener/predefined/most_actives',
    }
    url = url_map[mover_type]
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find('table')
    if not table:
        return pd.DataFrame()
    df = pd.read_html(StringIO(str(table)))[0]
    df = df.head(15)
    return df

# --- Economic Calendar ve Selenium fonksiyonları tamamen kaldırıldı ---

st.set_page_config(page_title="Tradebox Stock Tracker", layout="wide")

# --- MOBİL (iOS) DOSTU CSS ---
st.markdown('''
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<style>
/* Navbar mobil */
@media (max-width: 700px) {
  .stRadio [role="radiogroup"] label { font-size: 1.08em !important; padding: 8px 10px !important; margin: 0 2px 0 0 !important; min-width: 90px; }
}
/* Heatmap mobil */
@media (max-width: 700px) {
  .sector-heatmap-mobile { flex-direction: column !important; gap: 7px !important; }
  .sector-heatmap-mobile > div { min-width: 0 !important; width: 100% !important; margin-bottom: 4px; font-size: 0.98em !important; padding: 8px 7px !important; }
}
/* Kartlar mobil */
@media (max-width: 700px) {
  .trade-ideas-row-center { flex-direction: column !important; gap: 14px !important; align-items: stretch !important; }
  .trade-idea-box { min-width: 0 !important; max-width: 100% !important; width: 100% !important; margin-bottom: 0 !important; padding: 12px 7px 10px 7px !important; }
  .trade-idea-title { font-size: 1.05em !important; }
  .trade-idea-row { font-size: 0.97em !important; }
  .trade-idea-sparkline-img { height: 32px !important; margin-top: 8px !important; }
}
/* TradingView widget mobil */
@media (max-width: 700px) {
  .tradingview-widget-wrap iframe { height: 320px !important; min-height: 220px !important; }
}
</style>
''', unsafe_allow_html=True)

# --- LOGO & HEADER ---
st.markdown('''
<style>
.sw-header-row {
  display: flex;
  align-items: center;
  width: 100%;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.sw-header-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 0;
  margin-top: 8px;
}
.sw-refresh-btn {
  width: 44px;
  height: 44px;
  background: #232;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s, transform 0.18s;
  margin-right: 2px;
  box-shadow: 0 2px 8px #0002;
}
.sw-refresh-btn:hover {
  background: #38e38e;
  box-shadow: 0 4px 16px #38e38e44;
  transform: scale(1.08) rotate(-10deg);
}
.sw-refresh-icon {
  width: 28px;
  height: 28px;
  fill: #6ee26e;
  display: block;
  transition: fill 0.2s;
}
.sw-logo-text {
  font-family: 'Segoe UI', 'Roboto', Arial, sans-serif;
  font-size: 2.1em;
  font-weight: 800;
  letter-spacing: -1px;
  display: flex;
  align-items: center;
}
.sw-logo-stock {
  color: #fff;
  font-weight: 800;
}
.sw-logo-watcher {
  color: #6ee26e;
  font-weight: 800;
  margin-left: 2px;
  position: relative;
}
@media (max-width: 700px) {
  .sw-header-logo { font-size: 1.2em; }
  .sw-refresh-btn { width: 32px; height: 32px; }
  .sw-refresh-icon { width: 20px; height: 20px; }
}
</style>
<div class="sw-header-row">
  <div class="sw-header-logo">
    <button class="sw-refresh-btn" onclick="window.location.reload()">
      <svg class="sw-refresh-icon" viewBox="0 0 24 24">
        <path d="M12 4V1L7 6l5 5V7c3.31 0 6 2.69 6 6 0 3.31-2.69 6-6 6s-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
      </svg>
    </button>
    <span class="sw-logo-text">
      <span class="sw-logo-stock">Stock</span>
      <span class="sw-logo-watcher">Core</span>
    </span>
  </div>
</div>
''', unsafe_allow_html=True)

# --- MODERN SPINNER/SHIMMER ---
spinner_css = '''<style>
@keyframes shimmer {
  0% { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}
.shimmer {
  height: 38px;
  width: 100%;
  border-radius: 8px;
  background: linear-gradient(90deg, #23272f 25%, #2e323a 50%, #23272f 75%);
  background-size: 400px 100%;
  animation: shimmer 1.2s infinite linear;
  margin-bottom: 10px;
}
</style>'''

# --- VIX GÖSTERGESİ ---
def get_vix_value():
    try:
        vix = yf.Ticker('^VIX')
        hist = vix.history(period="1d", interval="1m")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception:
        pass
    return None
vix_val = get_vix_value()
vix_color = '#6ee26e' if vix_val and vix_val < 15 else '#fbbc04' if vix_val and vix_val < 25 else '#d93025'
vix_label = 'Calm' if vix_val and vix_val < 15 else 'Neutral' if vix_val and vix_val < 25 else 'Fear'
vix_html = f'''
<style>
.vix-box {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: #232c2f;
  border-radius: 10px;
  border: 1.5px solid #232;
  box-shadow: 0 2px 8px #0002;
  padding: 7px 18px 7px 12px;
  font-size: 1.08em;
  font-weight: 700;
  color: {vix_color};
  margin-left: 18px;
  margin-bottom: 0;
  margin-top: 0;
}}
.vix-dot {{
  width: 13px; height: 13px; border-radius: 50%; background: {vix_color}; display: inline-block; margin-right: 2px;
}}
</style>
<div class="vix-box">
  <span class="vix-dot"></span>VIX: <span style="color:{vix_color}; margin-left:4px;">{vix_val:.2f}</span> <span style="color:#fff; font-size:0.97em; margin-left:7px;">{vix_label}</span>
</div>
''' if vix_val else ''

# --- SEKTÖR HEATMAP (KOYU PASTEL, EN ALTA, BİTİŞİK) ---
sector_heatmap_data = [
    {"sector": "Tech", "change": 2.1},
    {"sector": "Finance", "change": -1.3},
    {"sector": "Healthcare", "change": 0.7},
    {"sector": "Energy", "change": -0.9},
    {"sector": "Consumer", "change": 1.5},
    {"sector": "Utilities", "change": -0.2},
]
sector_colors = lambda chg: '#234e3c' if chg > 1 else '#3a3a2e' if chg > 0 else '#4a2323' if chg < 0 else '#33343a'
heatmap_html = '<div class="sector-heatmap-mobile" style="display:flex;gap:0;margin:0 0 0 0;flex-wrap:wrap;">'
for i, s in enumerate(sector_heatmap_data):
    color = sector_colors(s['change'])
    sign = '+' if s['change'] > 0 else ''
    left_radius = '10px' if i == 0 else '0'
    right_radius = '10px' if i == len(sector_heatmap_data)-1 else '0'
    heatmap_html += f'<div style="background:{color};color:#e0e0e0;font-weight:700;border-top-left-radius:{left_radius};border-bottom-left-radius:{left_radius};border-top-right-radius:{right_radius};border-bottom-right-radius:{right_radius};padding:10px 18px;min-width:90px;text-align:center;box-shadow:0 2px 8px #0001;font-size:1.08em;border-right:1.5px solid #232;">'
    heatmap_html += f'<span style="color:#e0e0e0;font-weight:700;">{s["sector"]}</span><br>'
    heatmap_html += f'<span style="font-size:0.97em;font-weight:700;color:#e0e0e0;">{sign}{s["change"]:.2f}%</span>'
    heatmap_html += '</div>'
heatmap_html += '</div>'

# --- NAVBAR: StockCore altına ---
navbar_options = ["Home", "Market Movers", "News", "ETFs", "Stock Heatmap"]
selected_nav = st.radio("", navbar_options, horizontal=True, label_visibility="collapsed")

# --- STOCK HEATMAP WIDGET ---
if selected_nav == "Stock Heatmap":
    st.subheader("Stock Heatmap (S&P 500)")
    st.markdown("""
    <div style="width:100%;height:600px;">
    <iframe src="https://www.tradingview.com/widget/stock-heatmap/?dataSource=SPX500&grouping=sector&blockSize=market_cap_basic&blockColor=change&locale=en&colorTheme=dark&hasTopBar=false&isDataSetEnabled=false&isZoomEnabled=true&hasSymbolTooltip=true&isMonoSize=false" 
    width="100%" height="600" frameborder="0" allowtransparency="true" scrolling="no" style="border-radius:12px;"></iframe>
    </div>
    """, unsafe_allow_html=True)

# --- ECONOMIC EVENTS CARD (FULL WIDTH BANNER) + VIX ---
css_econ_events = """
<style>
.econ-events-banner {
  width: 100%;
  max-width: none;
  box-sizing: border-box;
  background: linear-gradient(90deg, #23272f 80%, #263 100%);
  border-radius: 10px;
  border: 1.5px solid #232;
  box-shadow: 0 2px 12px #0003;
  padding: 8px 24px 8px 18px;
  margin-bottom: 0;
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 22px;
  height: 54px;
}
.econ-events-title {
  font-size: 1.08em;
  font-weight: 800;
  color: #6ee26e;
  margin-bottom: 0;
  margin-right: 18px;
  letter-spacing: -0.5px;
  white-space: nowrap;
}
.econ-event-row {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 0;
  font-size: 1em;
  margin-right: 18px;
  white-space: nowrap;
}
.econ-event-time {
  color: #fbbc04;
  font-weight: 700;
  min-width: 38px;
  font-size: 1em;
}
.econ-event-title {
  color: #fff;
  font-weight: 500;
  font-size: 1em;
}
.econ-event-flag {
  font-size: 1.13em;
  margin-right: 2px;
}
@media (max-width: 900px) {
  .econ-events-banner { flex-wrap: wrap; height: auto; padding: 10px 10px 10px 10px; gap: 10px; }
  .econ-events-title { margin-bottom: 4px; margin-right: 10px; }
  .econ-event-row { margin-bottom: 2px; margin-right: 10px; }
}
@media (max-width: 700px) {
  .econ-events-banner { flex-direction: column; align-items: flex-start; min-width: 0; max-width: 100%; width: 100%; height: auto; padding: 8px 7px 8px 7px; }
  .econ-events-title { font-size: 1em; margin-bottom: 2px; }
  .econ-event-row { font-size: 0.97em; margin-bottom: 2px; }
}
</style>
"""
today_events = [
    {"time": "15:30", "country": "🇺🇸", "title": "US Initial Jobless Claims"},
    {"time": "17:00", "country": "🇪🇺", "title": "ECB Rate Decision"},
    {"time": "18:00", "country": "🇬🇧", "title": "BoE Gov. Speech"},
]
econ_events_html = '<div class="econ-events-banner">'
econ_events_html += '<div class="econ-events-title">Today\'s Major Economic Events</div>'
for event in today_events:
    econ_events_html += (
        f'<div class="econ-event-row">'
        f'<span class="econ-event-flag">{event["country"]}</span>'
        f'<span class="econ-event-time">{event["time"]}</span>'
        f'<span class="econ-event-title">{event["title"]}</span>'
        f'</div>'
    )
if vix_html:
    econ_events_html += vix_html

st.markdown(css_econ_events, unsafe_allow_html=True)
st.markdown(econ_events_html, unsafe_allow_html=True)

# --- HEATMAP ANA SAYFADA ve ANA NAV BLOKLARI ---
if selected_nav == "Home":
    # ... diğer ana sayfa içeriği ...
    # Tabloyu ve diğer ana içerikleri burada bırak
    # En alta heatmap başlığı ve kutuları ekle
    st.markdown("""
    <div style='margin-top:48px; margin-bottom:0;'>
      <h3 style='margin-bottom:10px;color:#fff;font-weight:800;'>Sectoral Heatmaps</h3>
      {heatmap}
    </div>
    """.replace('{heatmap}', heatmap_html), unsafe_allow_html=True)
elif selected_nav == "News":
    st.subheader('📰 Latest Market News')
    feed_url = "https://news.google.com/rss/search?q=stock+market"
    import feedparser
    feed = feedparser.parse(feed_url)
    if feed.entries:
        for entry in feed.entries[:12]:
            title = entry.title
            link = entry.link
            summary = entry.summary if hasattr(entry, 'summary') else ''
            summary_short = summary[:110] + '...' if len(summary) > 110 else summary
            parsed_url = urllib.parse.urlparse(link)
            domain = parsed_url.netloc.replace('www.', '')
            st.markdown(f"""
            <div style='margin-bottom:18px;'>
                <a href='{link}' target='_blank' style='font-size:1.08em;font-weight:700;color:#6ee26e;text-decoration:none;'>{title}</a><br>
                <span style='font-size:0.97em;color:#888;'>{domain}</span><br>
                <span style='font-size:0.97em;color:#b5b5b5;font-style:italic;'>{summary_short}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No news found.")
elif selected_nav == "Market Movers":
    st.subheader('Market Movers (US)')
    try:
        movers_tab = st.tabs(["Gainers", "Losers", "Actives"])
        movers_types = ['gainers', 'losers', 'actives']
        for i, tab in enumerate(movers_tab):
            with tab:
                df = get_yahoo_movers(movers_types[i])
                if not df.empty:
                    df = df.reset_index(drop=True)  # Index sütununu kaldır
                    if 'Unnamed: 0' in df.columns:
                        df = df.drop(columns=['Unnamed: 0'])
                    # Sade ve okunaklı sayı formatı uygula
                    for col in df.columns:
                        if any(x in col.lower() for x in ['price', 'change', 'close', 'open', 'low', 'high']):
                            try:
                                df[col] = df[col].apply(lambda x: f"{float(str(x).replace(',','')):,.2f}" if pd.notnull(x) and str(x).replace('.','',1).replace('-','',1).replace(',','').replace('%','').isdigit() else x)
                            except Exception:
                                pass
                        if 'volume' in col.lower():
                            def fmt_vol(val):
                                try:
                                    v = float(str(val).replace(',',''))
                                    if v >= 1e9:
                                        return f"{v/1e9:.2f}B"
                                    elif v >= 1e6:
                                        return f"{v/1e6:.2f}M"
                                    elif v >= 1e3:
                                        return f"{v/1e3:.2f}K"
                                    else:
                                        return f"{v:.0f}"
                                except:
                                    return val
                            df[col] = df[col].apply(fmt_vol)
                        if 'market cap' in col.lower():
                            def fmt_mc(val):
                                try:
                                    v = float(str(val).replace(',',''))
                                    if v >= 1e9:
                                        return f"{v/1e9:.2f}B"
                                    elif v >= 1e6:
                                        return f"{v/1e6:.2f}M"
                                    else:
                                        return f"{v:.0f}"
                                except:
                                    return val
                            df[col] = df[col].apply(fmt_mc)
                    # Hangi sütun varsa onu renklendir
                    change_col = None
                    for col in ['% Change', 'Change %']:
                        if col in df.columns:
                            change_col = col
                            break
                    if change_col:
                        def color_mover(val):
                            try:
                                v = float(str(val).replace('%','').replace(',',''))
                                if v > 0:
                                    return 'color: #188038; font-weight: bold;'
                                elif v < 0:
                                    return 'color: #d93025; font-weight: bold;'
                            except:
                                pass
                            return ''
                        styled = df.style.applymap(color_mover, subset=[change_col])
                        st.dataframe(styled, use_container_width=True, hide_index=True)
                    else:
                        st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.warning("No data found. Showing example data.")
                    test_df = pd.DataFrame({
                        'Symbol': ['AAPL', 'MSFT'],
                        'Change %': ['+2.5%', '-1.2%']
                    })
                    test_df = test_df.reset_index(drop=True)
                    def color_mover(val):
                        try:
                            v = float(str(val).replace('%','').replace(',',''))
                            if v > 0:
                                return 'color: #188038; font-weight: bold;'
                            elif v < 0:
                                return 'color: #d93025; font-weight: bold;'
                        except:
                            pass
                        return ''
                    styled = test_df.style.applymap(color_mover, subset=['Change %'])
                    st.dataframe(styled, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error loading Market Movers: {e}")
        test_df = pd.DataFrame({
            'Symbol': ['AAPL', 'MSFT'],
            'Change %': ['+2.5%', '-1.2%']
        })
        test_df = test_df.reset_index(drop=True)
        def color_mover(val):
            try:
                v = float(str(val).replace('%','').replace(',',''))
                if v > 0:
                    return 'color: #188038; font-weight: bold;'
                elif v < 0:
                    return 'color: #d93025; font-weight: bold;'
            except:
                pass
            return ''
        styled = test_df.style.applymap(color_mover, subset=['Change %'])
        st.dataframe(styled, use_container_width=True, hide_index=True)
elif selected_nav == "ETFs":
    st.subheader('Most Traded US ETFs')
    try:
        etf_list = [
            {"Symbol": "SPY", "Name": "SPDR S&P 500 ETF Trust"},
            {"Symbol": "QQQ", "Name": "Invesco QQQ Trust"},
            {"Symbol": "IWM", "Name": "iShares Russell 2000 ETF"},
            {"Symbol": "VTI", "Name": "Vanguard Total Stock Market ETF"},
            {"Symbol": "DIA", "Name": "SPDR Dow Jones Industrial Average ETF Trust"},
            {"Symbol": "GLD", "Name": "SPDR Gold Shares"},
            {"Symbol": "TLT", "Name": "iShares 20+ Year Treasury Bond ETF"},
            {"Symbol": "XLF", "Name": "Financial Select Sector SPDR Fund"},
            {"Symbol": "XLE", "Name": "Energy Select Sector SPDR Fund"},
            {"Symbol": "XLY", "Name": "Consumer Discretionary Select Sector SPDR Fund"},
            {"Symbol": "XLC", "Name": "Communication Services Select Sector SPDR Fund"},
            {"Symbol": "XLI", "Name": "Industrial Select Sector SPDR Fund"},
            {"Symbol": "XLV", "Name": "Health Care Select Sector SPDR Fund"},
            {"Symbol": "ARKK", "Name": "ARK Innovation ETF"},
            {"Symbol": "EEM", "Name": "iShares MSCI Emerging Markets ETF"},
        ]
        etf_df = pd.DataFrame(etf_list)
        def get_etf_data(symbol):
            try:
                t = yf.Ticker(symbol)
                hist = t.history(period="1d", interval="1m")
                last_price = hist['Close'].iloc[-1] if not hist.empty else None
                change = None
                if not hist.empty and len(hist) > 1:
                    prev = hist['Close'].iloc[0]
                    change = ((last_price - prev) / prev) * 100 if prev else None
                volume = hist['Volume'].iloc[-1] if not hist.empty else None
                return last_price, change, volume
            except:
                return None, None, None
        import time as _time
        etf_df['Last Price'] = None
        etf_df['% Change'] = None
        etf_df['Volume'] = None
        for i, row in etf_df.iterrows():
            price, chg, vol = get_etf_data(row['Symbol'])
            etf_df.at[i, 'Last Price'] = f"{price:,.2f}" if price is not None else "-"
            etf_df.at[i, '% Change'] = f"{chg:+.2f}%" if chg is not None else "-"
            etf_df.at[i, 'Volume'] = f"{int(vol):,}" if vol is not None else "-"
            _time.sleep(0.1)
        def etf_color(val):
            try:
                v = float(str(val).replace('%',''))
                if v > 0:
                    return 'color: #188038; font-weight: bold;'
                elif v < 0:
                    return 'color: #d93025; font-weight: bold;'
            except:
                pass
            return ''
        styled = etf_df.style.applymap(etf_color, subset=['% Change'])
        st.dataframe(styled, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error loading ETFs: {e}")
        test_etf = pd.DataFrame({
            'Symbol': ['SPY', 'QQQ'],
            'Name': ['SPDR S&P 500 ETF Trust', 'Invesco QQQ Trust'],
            'Last Price': ['512.34', '432.10'],
            '% Change': ['+0.45%', '-0.12%'],
            'Volume': ['45,000,000', '38,000,000']
        })
        st.dataframe(test_etf)

# Ticker list (move this up before async scraping)
tickers = [
    'COIN','MSTR','MU','NEE','QCOM','MSFT','WMT','LMT','NFLX','C','PLTR','IONQ','RGTI','CEG','LLY',
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
    'Bitcoin': 'BTC-USD',
    'Ethereum': 'ETH-USD',
    'US10Y': '^TNX',
}

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

def get_sparkline_svg(prices, width=80, height=24, color="#fff"):
    if prices is None or len(prices) < 2:
        return ""
    prices = np.array(prices)
    # Normalize to [0, height]
    min_p, max_p = np.min(prices), np.max(prices)
    if max_p - min_p == 0:
        y = np.full_like(prices, height//2)
    else:
        y = height - ((prices - min_p) / (max_p - min_p) * (height-4) + 2)
    x = np.linspace(2, width-2, len(prices))
    points = " ".join(f"{int(xi)},{int(yi)}" for xi, yi in zip(x, y))
    svg = f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg"><polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/></svg>'
    return svg

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

# Russell 2000 için fallback uygula
if index_prices.get('Russell 2000') is None and index_prices.get('Russell 2000 ETF') is not None:
    index_prices['Russell 2000'] = index_prices['Russell 2000 ETF']
    index_changes['Russell 2000'] = index_changes['Russell 2000 ETF']

# --- MODERN DARK HEADER WITH SEARCH ---
# (Bu bölümü tamamen kaldır)

# --- MODERN TICKER TAPE (SCROLLING INDEX BAR) ---
ticker_items = []
for name, symbol in major_indices.items():
    price = index_prices.get(name)
    change = index_changes.get(name)
    if change is not None:
        arrow = "▲" if change > 0 else "▼" if change < 0 else ""
        color = "#6ee26e" if change > 0 else "#ff5c5c" if change < 0 else "#ccc"
        sign = "+" if change > 0 else ""
        change_str = f"{arrow} {sign}{change:.2f}%"
    else:
        color = "#ccc"
        change_str = "N/A"
    price_str = f"{price:,.2f}" if price is not None else "N/A"
    ticker_items.append(
        f"<span class='ticker-item' style='color:{color};'><b>{name}</b> {price_str} <span>{change_str}</span></span>"
    )
ticker_tape_html = " ".join(ticker_items)

st.markdown(f'''
<style>
.ticker-tape {{
  width: 100%;
  overflow: hidden;
  background: rgba(30,32,36,0.85);
  border-radius: 10px;
  padding: 10px 0 10px 0;
  margin-bottom: 18px;
  font-family: 'Roboto', 'Segoe UI', Arial, sans-serif;
  font-size: 1.08em;
  box-shadow: 0 2px 8px #0002;
  position: relative;
  height: 44px;
}}
.ticker-tape-inner {{
  display: inline-block;
  white-space: nowrap;
  animation: ticker-scroll 32s linear infinite;
}}
@keyframes ticker-scroll {{
  0% {{ transform: translateX(100%); }}
  100% {{ transform: translateX(-100%); }}
}}
.ticker-item {{
  display: inline-block;
  margin: 0 32px 0 0;
  font-weight: 500;
  letter-spacing: 0.5px;
}}
@media (max-width: 700px) {{
  .ticker-tape {{ font-size: 0.98em; padding: 7px 0 7px 0; height: 36px; }}
  .ticker-item {{ margin: 0 14px 0 0; }}
}}
</style>
<div class="ticker-tape">
  <div class="ticker-tape-inner">{ticker_tape_html}</div>
</div>
''', unsafe_allow_html=True)

# --- TRADE IDEAS CENTERED BELOW INDEX BAR ---
trade_ideas = [
    {
        "Ticker": "MRVL",
        "Type": "AL",
        "Date": "2025-05-13",
        "Price": 64.50,
        "StopLoss": 59.40,
        "TakeProfit": 73.50,
    },
    {
        "Ticker": "NVDA",
        "Type": "AL",
        "Date": "2025-05-12",
        "Price": 122.21,
        "StopLoss": 116.80,
        "TakeProfit": 143.50,
    },
    {
        "Ticker": "AAL",
        "Type": "AL",
        "Date": "2025-05-08",
        "Price": 10.78,
        "StopLoss": 9.90,
        "TakeProfit": 12.50,
    },
]
# Update current price and performance for each trade idea
for idea in trade_ideas:
    try:
        ticker = yf.Ticker(idea["Ticker"])
        hist = ticker.history(period="1d", interval="1m")
        if not hist.empty:
            current_price = hist['Close'].iloc[-1]
            idea["Current Price"] = current_price
            idea["Performance"] = ((current_price - idea["Price"]) / idea["Price"]) * 100
        else:
            idea["Current Price"] = None
            idea["Performance"] = None
    except Exception:
        idea["Current Price"] = None
        idea["Performance"] = None

def get_sparkline_base64(ticker):
    try:
        hist = yf.Ticker(ticker).history(period="1mo", interval="1d")['Close']
        if hist.empty:
            return ""
        fig, ax = plt.subplots(figsize=(3.5, 0.9))
        ax.plot(hist.values, color="#6ee26e", linewidth=2.5)
        ax.axis('off')
        plt.tight_layout(pad=0)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        return f'<img src="data:image/png;base64,{img_base64}" class="trade-idea-sparkline-img" />'
    except Exception:
        return ""

symbol_to_domain = {
    "NVDA": "nvidia.com",
    "MRVL": "marvell.com",
    "AAL": "aa.com",
    # Diğer semboller için domain ekleyebilirsin
}

st.markdown("""
<style>
.trade-ideas-row-center {
    display: flex;
    flex-wrap: wrap;
    gap: 28px;
    justify-content: flex-start;
    margin-left: 0;
    margin-top: 10px;
}
.trade-idea-box {
    background: #23272f;
    border-radius: 14px;
    border: 1.5px solid #222;
    box-shadow: 0 4px 24px #0005;
    min-width: 260px;
    max-width: 320px;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: 18px 16px 16px 16px;
    margin-bottom: 0;
    position: relative;
    transition: box-shadow 0.2s;
}
.trade-idea-box:hover {
    box-shadow: 0 8px 32px #0007;
    border-color: #6ee26e;
}
.trade-idea-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.trade-idea-title {
    font-size: 1.18em;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #fff;
}
.trade-idea-logo-img {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    object-fit: contain;
    background: #fff;
    box-shadow: 0 2px 8px #0002;
    display: inline-block;
    vertical-align: middle;
}
.trade-idea-row { margin-bottom: 7px; font-size: 1em; }
.trade-idea-label { color: #b5b5b5; font-size: 0.97em; }
.trade-idea-perf-pos { color: #6ee26e; font-weight: bold; }
.trade-idea-perf-neg { color: #ff5c5c; font-weight: bold; }
.trade-idea-sparkline-img {
  margin-left: 0;
  margin-top: 10px;
  height: 48px;
  max-width: 100%;
  width: 100%;
  display: block;
}
@media (max-width: 900px) {
  .trade-ideas-row-center { gap: 14px; }
  .trade-idea-box { min-width: 0; max-width: 100%; }
}
@media (max-width: 700px) {
  .trade-ideas-row-center {
    flex-direction: column;
    gap: 14px;
    align-items: stretch;
  }
  .trade-idea-box {
    min-width: 0;
    max-width: 100%;
    width: 100%;
    margin-bottom: 0;
    padding: 12px 7px 10px 7px;
  }
  .trade-idea-title { font-size: 1.05em; }
  .trade-idea-row { font-size: 0.97em; }
  .trade-idea-sparkline-img { height: 32px; margin-top: 8px; }
}
</style>
""", unsafe_allow_html=True)

# Trade Ideas kartları için Analyst Rating örnek verisi (gerçek API ile entegre edilebilir)
def get_analyst_rating():
    # Gerçek API yoksa örnek: rastgele oranlar
    buy = random.randint(40, 80)
    hold = random.randint(10, 40)
    sell = 100 - buy - hold
    if sell < 0: sell = 0
    return buy, hold, sell

trade_ideas_boxes_html = ""
for idea in trade_ideas:
    perf = idea.get("Performance")
    perf_str = f"{perf:+.2f}%" if perf is not None else "N/A"
    perf_class = "trade-idea-perf-pos" if perf is not None and perf >= 0 else "trade-idea-perf-neg"
    price_str = f"{idea['Price']:.2f}" if idea.get('Price') is not None else "N/A"
    curr_str = f"{idea.get('Current Price', 0):.2f}" if idea.get('Current Price') is not None else "N/A"
    stop_str = f"{idea.get('StopLoss', 0):.2f}" if idea.get('StopLoss') is not None else "N/A"
    tp_str = f"{idea.get('TakeProfit', 0):.2f}" if idea.get('TakeProfit') is not None else "N/A"
    sparkline_img = get_sparkline_base64(idea['Ticker'])
    logo_url = f"https://logo.clearbit.com/{symbol_to_domain.get(idea['Ticker'], 'yahoo.com')}"
    trade_ideas_boxes_html += (
        f'<div class="trade-idea-box">'
        f'<div class="trade-idea-title-row">'
        f'<img src="{logo_url}" class="trade-idea-logo-img" alt="{idea["Ticker"]} logo"/>'
        f'<span class="trade-idea-title">Trade Ideas</span>'
        f'</div>'
        f'<div class="trade-idea-row"><span class="trade-idea-label">Symbol:</span> {idea["Ticker"]}</div>'
        f'<div class="trade-idea-row"><span class="trade-idea-label">Action:</span> {idea["Type"]} ({idea["Date"]})</div>'
        f'<div class="trade-idea-row"><span class="trade-idea-label">Entry Price:</span> {price_str}</div>'
        f'<div class="trade-idea-row"><span class="trade-idea-label">Stop Loss:</span> {stop_str}</div>'
        f'<div class="trade-idea-row"><span class="trade-idea-label">Take Profit:</span> {tp_str}</div>'
        f'<div class="trade-idea-row"><span class="trade-idea-label">Current Price:</span> {curr_str}</div>'
        f'<div class="trade-idea-row"><span class="trade-idea-label">Performance:</span> <span class="{perf_class}">{perf_str}</span></div>'
        f'{sparkline_img}'
        f'</div>'
    )

st.markdown(f"""
<div class="trade-ideas-row-center">
{trade_ideas_boxes_html}
</div>
""", unsafe_allow_html=True)

# --- DATA PREPARATION (MUST BE BEFORE LAYOUT) ---
# Calculate the target "last Friday" date
today = date.today()
if today.weekday() >= 4: # Friday, Saturday, Sunday
    days_to_subtract = today.weekday() - 4
else: # Monday, Tuesday, Wednesday, Thursday
    days_to_subtract = today.weekday() + 3
target_friday_date = today - timedelta(days=days_to_subtract)
target_friday_ts = pd.Timestamp(target_friday_date)

start_download_date = target_friday_ts - pd.Timedelta(days=15)
end_download_date = target_friday_ts + pd.Timedelta(days=1)

try:
    hist_data_all_fields = yf.download(tickers, start=start_download_date, end=end_download_date, progress=False, auto_adjust=False)
    if hist_data_all_fields.empty:
        st.error(f"No historical data downloaded for the period around {target_friday_ts.strftime('%Y-%m-%d') }.")
        st.stop()
    close_prices_hist = hist_data_all_fields['Close']
    if isinstance(close_prices_hist, pd.Series):
        close_prices_hist = close_prices_hist.to_frame(name=tickers[0] if len(tickers) == 1 else 'Close')
        if len(tickers) == 1 :
             pass
        elif 'Close' in close_prices_hist.columns and len(tickers) >1 :
             st.warning("Unexpected data structure for close_prices_hist from yfinance.")
except Exception as e:
    st.error(f"Error downloading data from Yahoo Finance: {e}")
    st.stop()

df_idx = close_prices_hist.index
if not isinstance(df_idx, pd.DatetimeIndex):
    close_prices_hist.index = pd.to_datetime(close_prices_hist.index)

dates_before_today = close_prices_hist.index[close_prices_hist.index < pd.Timestamp.today().normalize()]
if len(dates_before_today) == 0:
    st.error(f"No trading data found before today.")
    st.stop()
last_trading_day = dates_before_today[-1]

last_day_closes = close_prices_hist.loc[last_trading_day]
df_display = pd.DataFrame(index=last_day_closes.index)
df_display['Ticker'] = df_display.index
df_display['Company Name'] = df_display['Ticker'].map(company_names)
df_display[f'Close ({last_trading_day.strftime("%Y-%m-%d")})'] = last_day_closes

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

def color_pnl(val):
    try:
        v = float(val)
        if v > 0:
            return 'color: #188038; font-weight: bold;'
        elif v < 0:
            return 'color: #d93025; font-weight: bold;'
    except:
        pass
    return ''

def fetch_ticker_data(ticker_symbol, last_official_close):
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        # Previous close: her zaman bir önceki günün kapanışı
        daily_hist = ticker_obj.history(period="2d", interval="1d")['Close']
        if len(daily_hist) >= 2:
            prev_close = daily_hist.iloc[-2]
        else:
            prev_close = None
        # Last price: gün içi son fiyat
        hist = ticker_obj.history(period="1d", interval="1m")
        last_price = hist['Close'].iloc[-1] if not hist.empty else None
        if pd.notnull(last_price) and pd.notnull(prev_close) and prev_close != 0:
            last_price_change = ((last_price - prev_close) / prev_close) * 100
        else:
            last_price_change = None
        # Pre-market price: prepost ile alınan en son pre-market fiyat
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
        if pre_market_price is not None and prev_close is not None and prev_close != 0:
            pre_market_change = ((pre_market_price - prev_close) / prev_close) * 100
        else:
            pre_market_change = None
        info = ticker_obj.fast_info
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

with ThreadPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(lambda t: fetch_ticker_data(t, last_official_close_dict.get(t)), df_display['Ticker']))

parallel_df = pd.DataFrame(results).set_index('Ticker')
for col in parallel_df.columns:
    df_display[col] = parallel_df[col]
cols = ['Ticker', 'Company Name', 'Last Price', 'Last Price % Change', 'Pre-market Price', 'Pre-market % Change', 'Market Cap']
df_display = df_display[cols]
for col in df_display.columns:
    try:
        df_display[col] = pd.to_numeric(df_display[col])
    except Exception:
        pass

# --- TABLE AND TRADE IDEAS LAYOUT ---
col1, col2 = st.columns([4, 1])

with col1:
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    st.caption(f"Last data refresh: {now}")
    def make_yahoo_link(val):
        if pd.isnull(val):
            return val
        url = f'https://finance.yahoo.com/quote/{val}'
        return f'{val}'  # st.dataframe HTML desteklemez, düz metin
    def format_market_cap(val):
        try:
            val = float(val)
            if val >= 1e9:
                return f"{val/1e9:.1f}B"
            elif val >= 1e6:
                return f"{val/1e6:.1f}M"
            else:
                return f"{val:.0f}"
        except:
            return val
    df_disp = df_display.copy()
    df_disp['Ticker'] = df_disp['Ticker'].apply(make_yahoo_link)
    df_disp['Pre-market Price'] = df_disp['Pre-market Price'].map(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")
    df_disp['Last Price'] = df_disp['Last Price'].map(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")
    df_disp['Market Cap'] = df_disp['Market Cap'].map(format_market_cap)
    if 'Last Price % Change' in df_disp:
        df_disp['Last Price % Change'] = df_disp['Last Price % Change'].map(lambda x: f"{float(x):+0.2f}%" if pd.notnull(x) else "")
    if 'Pre-market % Change' in df_disp:
        df_disp['Pre-market % Change'] = df_disp['Pre-market % Change'].map(lambda x: f"{float(x):+0.2f}%" if pd.notnull(x) else "")
    if '% Change' in df_disp:
        df_disp['% Change'] = df_disp['% Change'].map(lambda x: f"{float(x):+0.2f}%" if pd.notnull(x) else "")
    # Index sütununu kaldır
    df_disp = df_disp.reset_index(drop=True)
    # Negatif/pozitif renklendirme için Styler kullan
    def color_pnl(val):
        try:
            v = float(str(val).replace('%',''))
            if v > 0:
                return 'color: #188038; font-weight: bold;'
            elif v < 0:
                return 'color: #d93025; font-weight: bold;'
        except:
            pass
        return ''
    style_cols = [col for col in ['Last Price % Change', 'Pre-market % Change', '% Change'] if col in df_disp.columns]
    styled = df_disp.style.map(color_pnl, subset=style_cols)
    st.dataframe(styled, use_container_width=True, hide_index=True)

# GOOGL ve Dow Jones veri kontrolü
if 'GOOGL' in df_display.index and df_display.loc['GOOGL'].isnull().any():
    st.warning("GOOGL verileri alınamadı.")
if 'Dow Jones' in index_prices and index_prices.get('Dow Jones') is None:
    st.warning("Dow Jones verisi alınamadı.")

# --- TRADINGVIEW WIDGET (EMBED) ---
tradingview_css = """
<style>
.tradingview-widget-wrap { background: #23272f; border-radius: 12px; box-shadow: 0 2px 12px #0003; padding: 12px 10px 8px 10px; margin-bottom: 18px; }
.tradingview-title { color: #fff; font-weight: 700; font-size: 1.08em; margin-bottom: 7px; }
</style>
"""
tradingview_symbols = [
    {"label": "NASDAQ 100", "value": "NASDAQ:NDX"},
    {"label": "S&P 500", "value": "SP:SPX"},
    {"label": "Dow Jones", "value": "DJ:DJI"},
    {"label": "Russell 2000", "value": "CBOE:RU20"},
    {"label": "Bitcoin", "value": "COINBASE:BTCUSD"},
    {"label": "Ethereum", "value": "COINBASE:ETHUSD"},
    {"label": "US10Y", "value": "TVC:US10Y"},
]
def get_tradingview_embed(symbol):
    return f"""
    <div class='tradingview-widget-wrap'>
      <div class='tradingview-title'>Live Chart ({symbol})</div>
      <iframe src='https://s.tradingview.com/widgetembed/?symbol={symbol}&interval=15&theme=dark&style=1&locale=en&utm_source=localhost&utm_medium=widget&utm_campaign=chart&utm_term={symbol}' width='100%' height='420' frameborder='0' allowtransparency='true' scrolling='no' style='border-radius:10px;'></iframe>
    </div>
    """
if selected_nav == "Home":
    st.markdown(tradingview_css, unsafe_allow_html=True)
    tv_symbol_labels = [s['label'] for s in tradingview_symbols]
    tv_symbol_map = {s['label']: s['value'] for s in tradingview_symbols}
    tv_selected = st.selectbox("Select Symbol for Live Chart", tv_symbol_labels, index=0, key="tv_symbol")
    tv_embed_html = get_tradingview_embed(tv_symbol_map[tv_selected])
    st.markdown(tv_embed_html, unsafe_allow_html=True)

# --- CNN FEAR & GREED INDEX (MARKET SENTIMENT) ---
# (Bu bölümü kaldırdım) 