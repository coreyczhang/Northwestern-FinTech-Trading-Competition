"""
Northwestern FinTech Trading Competition — Strategy Demo
Hull Tactical Meeting | May 2026

Run with:  streamlit run app.py
"""

import time
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from collections import deque

st.set_page_config(page_title="Trading Strategies", layout="wide",
                   initial_sidebar_state="expanded")

# ── Design tokens ─────────────────────────────────────────────────────────────
DARK_BG = "#0a0e1a"
CARD_BG = "#111827"
BORDER  = "#1f2937"
AMBER   = "#f59e0b"
BLUE    = "#3b82f6"
RED     = "#ef4444"
GREEN   = "#22c55e"
MUTED   = "#6b7280"
TEXT2   = "#9ca3af"

PLOTLY_BASE = dict(
    paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
    font=dict(color=TEXT2, family="IBM Plex Mono, monospace", size=11),
    margin=dict(l=48, r=16, t=36, b=36),
    xaxis=dict(gridcolor=BORDER, zeroline=False),
    yaxis=dict(gridcolor=BORDER, zeroline=False),
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif !important; }
.stApp { background-color: #0a0e1a; }
section[data-testid="stSidebar"] { background-color: #0d1220 !important; border-right: 1px solid #1f2937; }
.kpi { background:#111827; border:1px solid #1f2937; border-top:2px solid #f59e0b; border-radius:4px; padding:10px 14px; font-family:'IBM Plex Mono',monospace; }
.kpi-label { color:#6b7280; font-size:10px; letter-spacing:.08em; text-transform:uppercase; margin-bottom:3px; }
.kpi-value { color:#f3f4f6; font-size:20px; font-weight:600; }
.banner-on  { background:#052e16; border:1px solid #22c55e; border-radius:4px; padding:7px 14px; color:#22c55e; font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:600; }
.banner-off { background:#1c0505; border:1px solid #ef4444; border-radius:4px; padding:7px 14px; color:#ef4444; font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:600; }
.section-head { color:#f59e0b; font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; letter-spacing:.1em; text-transform:uppercase; margin:18px 0 6px; border-bottom:1px solid #1f2937; padding-bottom:4px; }
.modebar { display:none !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
TICKERS     = ["ETH", "BTC", "LTC"]
INIT_PRICES = {"ETH": 2000.0, "BTC": 45000.0, "LTC": 80.0}
COLORS_T    = {"ETH": AMBER, "BTC": BLUE, "LTC": GREEN}
PH_SZ       = 32
DT          = 1 / 252

# ── Session state init ────────────────────────────────────────────────────────
def _init_mm():
    st.session_state.mm_prices     = {t: INIT_PRICES[t] for t in TICKERS}
    st.session_state.mm_pos        = {t: 0.0 for t in TICKERS}
    st.session_state.mm_cash       = 100_000.0
    st.session_state.mm_ph         = {t: deque([INIT_PRICES[t]] * PH_SZ, maxlen=PH_SZ) for t in TICKERS}
    st.session_state.mm_price_hist = {t: deque(maxlen=80) for t in TICKERS}
    st.session_state.mm_pnl_hist   = deque(maxlen=80)
    st.session_state.mm_bid_q      = {t: INIT_PRICES[t] * 0.999 for t in TICKERS}
    st.session_state.mm_ask_q      = {t: INIT_PRICES[t] * 1.001 for t in TICKERS}
    st.session_state.mm_mom        = {t: 0.0 for t in TICKERS}
    st.session_state.mm_tick_n          = 0
    st.session_state.mm_spread_revenue  = 0.0
    st.session_state.mm_revenue_hist    = deque(maxlen=80)

def _init_fi():
    st.session_state.fi_price       = 80.0
    st.session_state.fi_book_imb    = 1.0
    st.session_state.fi_flow_imb    = 1.0
    st.session_state.fi_price_hist  = deque(maxlen=80)
    st.session_state.fi_bid_hist    = deque(maxlen=80)
    st.session_state.fi_ask_hist    = deque(maxlen=80)
    st.session_state.fi_active_hist = deque(maxlen=80)
    st.session_state.fi_book_hist   = deque(maxlen=80)
    st.session_state.fi_flow_hist   = deque(maxlen=80)
    st.session_state.fi_log         = deque(maxlen=18)
    st.session_state.fi_fills       = {"buy": 0, "sell": 0}
    st.session_state.fi_tick        = 0

if "mm_tick_n" not in st.session_state:
    _init_mm()
if "fi_tick" not in st.session_state:
    _init_fi()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style='padding:12px 0 16px'>
        <div style='color:{AMBER};font-family:IBM Plex Mono,monospace;font-size:13px;font-weight:600;letter-spacing:.06em'>FINTECH TRADING</div>
        <div style='color:{MUTED};font-family:IBM Plex Mono,monospace;font-size:10px;margin-top:2px'>Northwestern Competition Strategies</div>
    </div>""", unsafe_allow_html=True)
    st.divider()

    tab_choice = st.radio("Strategy", ["Multi-Asset Market Maker", "Flow Imbalance Strategy"],
                          label_visibility="collapsed")
    st.divider()

    if tab_choice == "Multi-Asset Market Maker":
        st.markdown('<div class="section-head">Parameters</div>', unsafe_allow_html=True)
        sigma      = st.slider("Volatility σ",      0.001, 0.005, 0.002, 0.0005, format="%.4f")
        spread_fac = st.slider("Spread Factor",      0.10,  0.50,  0.25,  0.05)
        mom_th     = st.slider("Momentum Threshold", 0.001, 0.005, 0.0025, 0.0005, format="%.4f")
        max_pos    = st.slider("Max Position",       50,    500,   250,   50)
    else:
        sigma = spread_fac = mom_th = 0.0; max_pos = 250  # unused defaults
        st.markdown('<div class="section-head">Parameters</div>', unsafe_allow_html=True)
        book_thresh = st.slider("Book Threshold", 1.2, 2.5, 1.5, 0.1)
        flow_min    = st.slider("Flow Min",       0.85, 0.98, 0.95, 0.01)
        flow_max    = st.slider("Flow Max",       1.02, 1.15, 1.05, 0.01)
        mid_shift   = st.slider("Mid Shift",      0.10, 0.50, 0.25, 0.05)

    st.divider()
    if st.button("↺  Reset", use_container_width=True):
        _init_mm(); _init_fi(); st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — MULTI-ASSET MARKET MAKER
# ══════════════════════════════════════════════════════════════════════════════
if tab_choice == "Multi-Asset Market Maker":

    st.markdown(f"""
    <div style='margin-bottom:12px'>
        <span style='color:{AMBER};font-family:IBM Plex Mono,monospace;font-size:18px;font-weight:600'>Multi-Asset Market Maker</span>
        <span style='color:{MUTED};font-size:13px;margin-left:12px'>crypto_marketmaking.cpp — ETH / BTC / LTC</span>
    </div>""", unsafe_allow_html=True)

    @st.fragment(run_every=0.35)
    def mm_live():
        S   = st.session_state
        rng = np.random.default_rng()

        for t in TICKERS:
            mid = S.mm_prices[t]
            mid *= np.exp((sigma - 0.5*sigma**2)*DT + sigma*np.sqrt(DT)*rng.standard_normal())
            S.mm_prices[t] = mid
            S.mm_ph[t].append(mid)
            S.mm_price_hist[t].append(mid)

            spread = max(mid * 0.0008, mid * 0.0004)
            tick   = spread * spread_fac
            vals   = [v for v in S.mm_ph[t] if v > 0]
            mom    = ((np.mean(vals[:3]) - np.mean(vals[:12])) / np.mean(vals[:12])
                      if len(vals) >= 12 else 0.0)
            S.mm_mom[t] = mom

            pos = S.mm_pos[t]
            tb  = mid - tick + (-tick * 0.5 if pos > 0 else 0)
            ts  = mid + tick + ( tick * 0.5 if pos < 0 else 0)
            S.mm_bid_q[t] = tb
            S.mm_ask_q[t] = ts

            # Simulate a round-trip trade: both sides fill ~25% of ticks
            # This mirrors the actual market making edge — capture the spread
            if mom >= -mom_th and mom <= mom_th and abs(pos) < max_pos * 0.8:
                if rng.random() < 0.25:
                    # Buy fill
                    S.mm_pos[t] += 1.0
                    S.mm_cash   -= tb
                    S.mm_spread_revenue += tick  # spread captured on buy side
                if rng.random() < 0.25:
                    # Sell fill
                    S.mm_pos[t] -= 1.0
                    S.mm_cash   += ts
                    S.mm_spread_revenue += tick  # spread captured on sell side
            elif mom < -mom_th and abs(pos) < max_pos * 0.8:
                # Trending down — only sell fills
                if rng.random() < 0.20:
                    S.mm_pos[t] -= 1.0
                    S.mm_cash   += ts
                    S.mm_spread_revenue += tick
            elif mom > mom_th and abs(pos) < max_pos * 0.8:
                # Trending up — only buy fills
                if rng.random() < 0.20:
                    S.mm_pos[t] += 1.0
                    S.mm_cash   -= tb
                    S.mm_spread_revenue += tick

            # Soft inventory bleed — gradually flatten rather than hard liquidate
            if abs(S.mm_pos[t]) > max_pos * 0.7:
                bleed = 0.1 * S.mm_pos[t]
                S.mm_cash   += bleed * mid
                S.mm_pos[t] -= bleed

        mtm = sum(S.mm_pos[t] * S.mm_prices[t] for t in TICKERS)
        S.mm_pnl_hist.append(S.mm_cash + mtm)
        S.mm_revenue_hist.append(S.mm_spread_revenue)
        S.mm_tick_n += 1

        pnl = S.mm_cash + mtm - 100_000.0
        pc  = GREEN if pnl >= 0 else RED
        rc  = GREEN  # spread revenue always positive
        asp = (np.mean([S.mm_ask_q[t]-S.mm_bid_q[t] for t in TICKERS]) /
               np.mean([S.mm_prices[t] for t in TICKERS]) * 10_000)

        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f'<div class="kpi"><div class="kpi-label">Ticks</div><div class="kpi-value">{S.mm_tick_n}</div></div>', unsafe_allow_html=True)
        k2.markdown(f'<div class="kpi"><div class="kpi-label">Spread Revenue</div><div class="kpi-value" style="color:{rc}">${S.mm_spread_revenue:,.1f}</div></div>', unsafe_allow_html=True)
        k3.markdown(f'<div class="kpi"><div class="kpi-label">Total P&L (w/ MTM)</div><div class="kpi-value" style="color:{pc}">${pnl:+,.1f}</div></div>', unsafe_allow_html=True)
        k4.markdown(f'<div class="kpi"><div class="kpi-label">Avg Spread bps</div><div class="kpi-value">{asp:.1f}</div></div>', unsafe_allow_html=True)

        fig_p = go.Figure()
        for t in TICKERS:
            h = list(S.mm_price_hist[t])
            if h:
                fig_p.add_trace(go.Scatter(y=[p/h[0]*100 for p in h], name=t,
                                            line=dict(color=COLORS_T[t], width=1.5)))
        fig_p.update_layout(**PLOTLY_BASE, title="Normalised Price (base=100)", height=220,
                             showlegend=True, legend=dict(orientation="h", y=1.18, font=dict(size=11)))
        st.plotly_chart(fig_p, key="mm_price", use_container_width=True)

        c1, c2 = st.columns(2)
        pos_vals   = [S.mm_pos[t] for t in TICKERS]
        bar_colors = [RED if abs(p) > 0.7*max_pos else AMBER for p in pos_vals]
        fig_inv = go.Figure(go.Bar(x=TICKERS, y=pos_vals, marker_color=bar_colors,
                                   text=[f"{p:+.0f}" for p in pos_vals], textposition="outside",
                                   textfont=dict(family="IBM Plex Mono", size=11)))
        fig_inv.add_hline(y= max_pos, line_dash="dot", line_color=RED, line_width=1)
        fig_inv.add_hline(y=-max_pos, line_dash="dot", line_color=RED, line_width=1)
        fig_inv.update_layout(**PLOTLY_BASE, title="Inventory", height=220)
        c1.plotly_chart(fig_inv, key="mm_inv", use_container_width=True)

        fig_mom = go.Figure()
        for t in TICKERS:
            fig_mom.add_trace(go.Scatter(x=[t], y=[S.mm_mom[t]], mode="markers",
                marker=dict(size=16, color=COLORS_T[t], line=dict(width=1, color=DARK_BG)), name=t))
        fig_mom.add_hline(y= mom_th, line_dash="dot", line_color=RED,   line_width=1,
                           annotation_text="cancel bids", annotation_font_size=9)
        fig_mom.add_hline(y=-mom_th, line_dash="dot", line_color=GREEN, line_width=1,
                           annotation_text="cancel asks", annotation_font_size=9)
        fig_mom.add_hline(y=0, line_color=BORDER, line_width=1)
        fig_mom.update_layout(**PLOTLY_BASE, title="Momentum Signal", height=220, showlegend=False)
        fig_mom.update_yaxes(range=[-mom_th*3, mom_th*3])
        c2.plotly_chart(fig_mom, key="mm_mom", use_container_width=True)

        fig_pnl = go.Figure()
        fig_pnl.add_trace(go.Scatter(
            y=list(S.mm_revenue_hist), name="Spread Revenue",
            line=dict(color=GREEN, width=2),
            fill="tozeroy", fillcolor="rgba(34,197,94,0.08)",
        ))
        fig_pnl.add_trace(go.Scatter(
            y=[v - 100_000 for v in S.mm_pnl_hist], name="Total P&L (w/ MTM)",
            line=dict(color=AMBER, width=1.5, dash="dot"),
        ))
        fig_pnl.add_hline(y=0, line_color=BORDER, line_width=1)
        fig_pnl.update_layout(**PLOTLY_BASE, title="Spread Revenue vs Total P&L",
                               height=200, showlegend=True,
                               legend=dict(orientation="h", y=1.2, font=dict(size=11)))
        st.plotly_chart(fig_pnl, key="mm_pnl", use_container_width=True)

    mm_live()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — FLOW IMBALANCE STRATEGY
# ══════════════════════════════════════════════════════════════════════════════
else:
    st.markdown(f"""
    <div style='margin-bottom:12px'>
        <span style='color:{AMBER};font-family:IBM Plex Mono,monospace;font-size:18px;font-weight:600'>Flow Imbalance Strategy</span>
        <span style='color:{MUTED};font-size:13px;margin-left:12px'>hft_marketmaking.c++ — LTC only</span>
    </div>""", unsafe_allow_html=True)

    with st.expander("Key Logic — Two-Signal Filter  (hft_marketmaking.c++)"):
        st.code("""\
// FILTER 1: flow must be neutral — avoid informed traders
float flow = get_flow_imbalance(ticker);
if (flow < FLOW_MIN || flow > FLOW_MAX)
    return;   // ← SIT OUT

// FILTER 2: book must have a directional lean
float book = get_book_imbalance(ticker);
if (book > BOOK_THRESHOLD) {
    adjusted_mid = mid + MID_SHIFT * spread;
} else if (book < 1.0 / BOOK_THRESHOLD) {
    adjusted_mid = mid - MID_SHIFT * spread;
} else {
    return;   // ← SIT OUT
}""", language="cpp")
        st.info("The flow gate is adverse selection avoidance: one-sided flow signals an informed trader. Sitting out is strictly better than quoting into informed flow.")

    @st.fragment(run_every=0.35)
    def fi_live():
        S   = st.session_state
        rng = np.random.default_rng()

        mid = S.fi_price * np.exp((0.002-0.5*0.002**2)*DT + 0.002*np.sqrt(DT)*rng.standard_normal())
        S.fi_price = mid

        book = float(np.clip(S.fi_book_imb + 0.08*rng.standard_normal(), 0.2, 3.0))
        if rng.random() < 0.04:
            book = float(rng.uniform(1.7, 2.3) if rng.random() < 0.5 else rng.uniform(0.3, 0.6))
        S.fi_book_imb = book

        flow = float(np.clip(S.fi_flow_imb + 0.03*rng.standard_normal(), 0.4, 1.8))
        if rng.random() < 0.06:
            flow = float(rng.uniform(1.1, 1.5) if rng.random() < 0.5 else rng.uniform(0.6, 0.9))
        S.fi_flow_imb = flow

        spread       = mid * 0.001
        flow_ok      = flow_min <= flow <= flow_max
        book_bullish = book > book_thresh
        book_bearish = book < 1.0 / book_thresh
        quoting      = flow_ok and (book_bullish or book_bearish)

        bid = ask = None
        if quoting:
            adj = mid + mid_shift*spread if book_bullish else mid - mid_shift*spread
            bid, ask = adj - spread/2, adj + spread/2
            action = f"QUOTE  bid={bid:.3f}  ask={ask:.3f}"
            if rng.random() < 0.10: S.fi_fills["buy"]  += 1
            if rng.random() < 0.10: S.fi_fills["sell"] += 1
        elif not flow_ok:
            action = "SIT OUT — adverse flow"
        else:
            action = "SIT OUT — book neutral"

        S.fi_price_hist.append(mid);    S.fi_bid_hist.append(bid)
        S.fi_ask_hist.append(ask);      S.fi_active_hist.append(quoting)
        S.fi_book_hist.append(book);    S.fi_flow_hist.append(flow)
        S.fi_log.appendleft({"#": S.fi_tick, "Book": f"{book:.3f}",
                              "Flow": f"{flow:.3f}", "Action": action})
        S.fi_tick += 1

        if quoting:
            st.markdown('<div class="banner-on">● QUOTING — book signal active, flow neutral</div>', unsafe_allow_html=True)
        elif not flow_ok:
            st.markdown('<div class="banner-off">● SITTING OUT — adverse flow detected</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="banner-off">● SITTING OUT — no book signal</div>', unsafe_allow_html=True)

        prices  = list(S.fi_price_hist)
        bids    = list(S.fi_bid_hist)
        asks    = list(S.fi_ask_hist)
        actives = list(S.fi_active_hist)
        xs      = list(range(len(prices)))

        c_price, c_sig = st.columns([2, 1])

        fig_p = go.Figure()
        fig_p.add_trace(go.Scatter(x=xs, y=prices, name="LTC", line=dict(color=AMBER, width=1.5)))
        ax = [x for x, a in zip(xs, actives) if a]
        ab = [b for b, a in zip(bids, actives) if a and b is not None]
        aa = [a for a, ac in zip(asks, actives) if ac and a is not None]
        if ab: fig_p.add_trace(go.Scatter(x=ax[:len(ab)], y=ab, mode="markers", name="Bid",
                                           marker=dict(color=BLUE, size=5, symbol="triangle-up")))
        if aa: fig_p.add_trace(go.Scatter(x=ax[:len(aa)], y=aa, mode="markers", name="Ask",
                                           marker=dict(color=RED, size=5, symbol="triangle-down")))
        fig_p.update_layout(**PLOTLY_BASE, title="LTC Mid-Price + Active Quotes", height=300,
                             showlegend=True, legend=dict(orientation="h", y=1.18, font=dict(size=11)))
        c_price.plotly_chart(fig_p, key="fi_price", use_container_width=True)

        bh, fh = list(S.fi_book_hist), list(S.fi_flow_hist)
        fig_s  = make_subplots(rows=2, cols=1, subplot_titles=["Book Imbalance", "Flow Imbalance"],
                               vertical_spacing=0.18)
        bc = AMBER if (book > book_thresh or book < 1/book_thresh) else MUTED
        fc = GREEN if flow_ok else RED
        fig_s.add_trace(go.Scatter(y=bh, line=dict(color=bc, width=1.5), showlegend=False), row=1, col=1)
        fig_s.add_hline(y=book_thresh,     line_dash="dot", line_color=RED,  line_width=1, row=1, col=1)
        fig_s.add_hline(y=1.0/book_thresh, line_dash="dot", line_color=BLUE, line_width=1, row=1, col=1)
        fig_s.add_trace(go.Scatter(y=fh, line=dict(color=fc, width=1.5), showlegend=False), row=2, col=1)
        fig_s.add_hrect(y0=flow_min, y1=flow_max, fillcolor=GREEN, opacity=0.07, line_width=0, row=2, col=1)
        fig_s.add_hline(y=flow_min, line_dash="dot", line_color=GREEN, line_width=1, row=2, col=1)
        fig_s.add_hline(y=flow_max, line_dash="dot", line_color=GREEN, line_width=1, row=2, col=1)
        fig_s.update_layout(paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
                             font=dict(color=TEXT2, family="IBM Plex Mono, monospace", size=10),
                             height=300, margin=dict(l=40, r=10, t=40, b=20))
        fig_s.update_xaxes(gridcolor=BORDER, zeroline=False)
        fig_s.update_yaxes(gridcolor=BORDER, zeroline=False)
        c_sig.plotly_chart(fig_s, key="fi_sig", use_container_width=True)

        import pandas as pd
        c_log, c_fills = st.columns([3, 1])
        log_df = pd.DataFrame(list(S.fi_log))
        if not log_df.empty:
            c_log.dataframe(log_df, use_container_width=True, height=200, hide_index=True)
        c_fills.markdown(f"""
<div class="kpi" style="margin-bottom:8px">
  <div class="kpi-label">Buy Fills</div><div class="kpi-value" style="color:{BLUE}">{S.fi_fills['buy']}</div>
</div>
<div class="kpi">
  <div class="kpi-label">Sell Fills</div><div class="kpi-value" style="color:{RED}">{S.fi_fills['sell']}</div>
</div>""", unsafe_allow_html=True)

    fi_live()
