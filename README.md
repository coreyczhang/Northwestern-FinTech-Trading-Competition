# Northwestern FinTech Trading Competition — Market Making Strategies

Two C++ market making strategies built for the Northwestern FinTech Trading Competition. **Finished top 20% of competing teams.**

Both strategies implement event-driven architectures responding to live order book and trade feed updates.

---

## Strategies

### 1. Multi-Asset Market Maker (`crypto_marketmaking.cpp`)

Quotes bid and ask simultaneously across ETH, BTC, and LTC. Reprices every **1ms**.

**Key logic:**
- **Inventory skew** — shifts quotes toward reducing position. Long inventory: buy quote moves down. Short inventory: sell quote moves up.
- **Momentum filter** — computes short (3-tick) vs long (12-tick) moving average ratio over a 32-sample ring buffer. Cancels the quote on the trending side and scalps with a market order in the trend direction.
- **Dynamic spread** — spread is proportional to the current best bid/ask spread with a minimum floor, scaled by `SPREAD_FACTOR = 0.25`.
- **Hard inventory cap** — `MAX_POS = 250` units per asset. Excess immediately liquidated via market order.

**Parameters:**
| Parameter | Value | Description |
|---|---|---|
| `REPRICE_MS` | 1 | Repricing interval (ms) |
| `SPREAD_FACTOR` | 0.25 | Quote offset as fraction of spread |
| `MAX_POS` | 250 | Max inventory per asset |
| `MOM_TH` | 0.0025 | Momentum threshold (0.25%) |
| `PH_SZ` | 32 | Price history ring buffer size |

---

### 2. Flow Imbalance Strategy (`hft_marketmaking.cpp`)

Single-asset (LTC) strategy focused on adverse selection avoidance. Reprices every **50ms**.

**Key logic:**
- **Flow neutrality gate** — computes aggressive buy/sell volume ratio over a 10-second rolling window. Only quotes when flow is balanced (`FLOW_MIN = 0.95`, `FLOW_MAX = 1.05`). Steps out entirely during one-sided flow to avoid being picked off by informed traders.
- **Book imbalance signal** — computes total bid vs ask depth ratio. Only quotes when the book shows a directional bias (`BOOK_THRESHOLD = 1.5`). Shifts the mid price toward the heavier side by `MID_SHIFT = 0.25` spreads.
- **Dual gate** — both flow and book conditions must be met simultaneously to place orders. Neutral book = sit out.

**Parameters:**
| Parameter | Value | Description |
|---|---|---|
| `UPDATE_INTERVAL` | 0.05s | Repricing interval |
| `BOOK_THRESHOLD` | 1.5 | Min bid/ask depth ratio to quote |
| `FLOW_MIN / FLOW_MAX` | 0.95 / 1.05 | Flow neutrality band |
| `MID_SHIFT` | 0.25 | Quote shift as fraction of spread |
| `TRADE_WINDOW` | 10s | Rolling window for flow calculation |

---

## Interactive Demo

A live Streamlit simulation of both strategies is in the `demo/` directory.

```bash
cd demo
pip install -r requirements.txt
streamlit run app.py --server.port 8502
```

Simulates GBM price process, Poisson-distributed fills, and real-time PnL tracking. Runs at `localhost:8502`.

---

## Architecture

Both strategies implement the same three-callback interface expected by the competition exchange:

```cpp
void on_trade_update(Ticker, Side, float quantity, float price);
void on_orderbook_update(Ticker, Side, float quantity, float price);
void on_account_update(Ticker, Side, float price, float quantity, float capital_remaining);
```

No external dependencies. C++17.

---

## Design Notes

`crypto_marketmaking.cpp` prioritizes throughput — quoting all three assets at 1ms with inventory management and momentum filtering. `hft_marketmaking.cpp` prioritizes selectivity — only quoting when both flow and book conditions align, accepting fewer fills in exchange for lower adverse selection risk. The two strategies reflect a core market making tradeoff: fill rate vs toxicity.
