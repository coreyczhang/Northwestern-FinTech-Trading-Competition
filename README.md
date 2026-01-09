# Cryptocurrency Market Making Strategy - NUTC 2025

An algorithmic market-making strategy developed for the Northwestern University Trading Competition (NUTC), achieving **top 20% placement** among competing teams.

## Overview

This strategy implements an adaptive market maker that exploits order book imbalances while filtering out adverse selection from informed traders. The algorithm continuously monitors both passive liquidity (order book depth) and aggressive order flow to identify profitable market-making opportunities in cryptocurrency markets.

## Strategy Logic

### Core Concept: Biased Market Making with Flow Filtering

The strategy identifies market conditions where one side of the order book has significantly more liquidity than the other, indicating potential short-term price movement. However, unlike naive approaches, it includes a critical **flow filter** to avoid getting picked off by informed traders.

### Key Components

**1. Order Book Imbalance Detection**
```
Imbalance Ratio = Total Bid Quantity / Total Ask Quantity
```
- **Bullish Signal** (ratio > 1.75): More buyers stacking bids
- **Bearish Signal** (ratio < 0.57): More sellers stacking asks
- **Neutral** (0.57-1.75): No clear directional pressure

**2. Trade Flow Analysis**
```
Flow Ratio = Aggressive Buys / Aggressive Sells (last 10 seconds)
```
The strategy tracks "aggressive" orders (market orders) to detect informed trading activity. If flow becomes imbalanced (>1.10 or <0.90), the strategy **stands aside** to avoid adverse selection.

**3. Adaptive Quote Placement**

When conditions are favorable (strong book imbalance + neutral flow):

- **Competitive Side**: Places order *inside* the spread (mid ± 0.25 spread) with large size (100 units)
- **Defensive Side**: Places order *far from* the market (best ± 2.0 spread) with small size (50 units)

This asymmetric approach captures profits from the imbalance while maintaining exchange connectivity requirements.

## Technical Implementation

### Architecture

- **Event-driven design**: Reacts to order book and trade updates in real-time
- **Efficient data structures**: Uses `defaultdict` and `deque` for O(1) order book lookups and rolling window calculations
- **Rate limiting**: Updates quotes maximum once per 100ms to avoid excessive messaging
- **Active order management**: Cancels and replaces orders on each update for precise price control

### Configuration Parameters
```python
TRADE_TICKER = Ticker.LTC          # Focus on single asset for liquidity
BOOK_THRESHOLD = 1.75              # Minimum imbalance to trade
FLOW_MIN/MAX = 0.90/1.10           # Neutral flow bounds
TRADE_WINDOW = 10                  # Flow calculation window (seconds)
MID_SHIFT = 0.25                   # Competitive quote positioning
```

### Performance Tracking

Built-in metrics system tracks:
- Total trades executed
- Buy/sell fill distribution
- 30-second rolling statistics
- Real-time imbalance diagnostics

## Results

- **Competition Rank**: Top 20% of participants
- **Primary Market**: LTC (Litecoin)
- **Strategy Type**: Statistical arbitrage via imbalance exploitation

## Key Insights

1. **Flow filtering is critical**: Naive imbalance trading gets picked off by informed orders. The flow filter prevents this.

2. **Asymmetric sizing**: Small size on the defensive side prevents inventory buildup while maintaining exchange requirements.

3. **Fast cancellation**: Replacing orders on every update (vs. letting them rest) provides better price control in volatile conditions.

## Technical Skills Demonstrated

- Algorithmic trading strategy development
- Real-time data processing and event-driven architecture
- Statistical signal generation (order book analytics, flow analysis)
- Risk management through position sizing and flow filtering
- Python optimization for low-latency trading

## Competition Context

The Northwestern University Trading Competition (NUTC) is a quantitative trading competition where teams develop algorithmic strategies to compete in simulated market environments. This market-making case required balancing profitability with inventory risk and adverse selection.

---

**Note**: This code is designed for the NUTC simulation environment. The strategy demonstrates core market-making principles but would require additional risk controls, latency optimization, and exchange-specific adaptations for production deployment.
