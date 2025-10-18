from enum import Enum
import time
from collections import defaultdict, deque

class Side(Enum):
    BUY = 0
    SELL = 1

class Ticker(Enum):
    ETH = 0
    BTC = 1
    LTC = 2

def place_market_order(side: Side, ticker: Ticker, quantity: float) -> bool:
    return True

def place_limit_order(side: Side, ticker: Ticker, quantity: float, price: float, ioc: bool = False) -> int:
    return 0

def cancel_order(ticker: Ticker, order_id: int) -> bool:
    return True

class Strategy:
    def __init__(self) -> None:
        # ===== CRYPTO CONFIG - 40 BIPS FEES =====
        # Trade all 3 tickers to diversify
        self.BOOK_THRESHOLD = 1.4   # Slightly lower for crypto (more conservative)
        self.FLOW_MIN = 0.92        # Tighter flow bands (fees matter)
        self.FLOW_MAX = 1.08
        self.TRADE_WINDOW = 10
        self.UPDATE_INTERVAL = 0.12 # Slower due to fees
        self.MID_SHIFT = 0.35       # Wider to absorb 40 bips
        self.BUY_SIZE = 60.0        # Smaller size (40 bips each way)
        self.SELL_SIZE = 60.0
        # ==========================================
        
        # Orderbook tracking
        self.bids = defaultdict(dict)
        self.asks = defaultdict(dict)
        
        # Trade flow tracking
        self.recent_trades = defaultdict(deque)
        
        # Order management
        self.active_orders = defaultdict(list)
        
        # Timing
        self.last_update = defaultdict(float)
        
        print("Crypto Market Maker initialized - book imbalance + flow detection")
    
    def on_trade_update(self, ticker: Ticker, side: Side, quantity: float, price: float) -> None:
        self.recent_trades[ticker].append({
            'time': time.time(),
            'side': side,
            'qty': quantity
        })
        
        cutoff = time.time() - 60
        while self.recent_trades[ticker] and self.recent_trades[ticker][0]['time'] < cutoff:
            self.recent_trades[ticker].popleft()
    
    def on_orderbook_update(
        self, ticker: Ticker, side: Side, quantity: float, price: float
    ) -> None:
        if side == Side.BUY:
            if quantity > 0:
                self.bids[ticker][price] = quantity
            else:
                self.bids[ticker].pop(price, None)
        else:
            if quantity > 0:
                self.asks[ticker][price] = quantity
            else:
                self.asks[ticker].pop(price, None)
        
        if time.time() - self.last_update[ticker] < self.UPDATE_INTERVAL:
            return
        self.last_update[ticker] = time.time()
        
        self.update_quotes(ticker)
    
    def on_account_update(
        self,
        ticker: Ticker,
        side: Side,
        price: float,
        quantity: float,
        capital_remaining: float,
    ) -> None:
        pass
    
    def get_book_imbalance(self, ticker: Ticker) -> float:
        if not self.bids[ticker] or not self.asks[ticker]:
            return 1.0
        
        bid_qty = sum(self.bids[ticker].values())
        ask_qty = sum(self.asks[ticker].values())
        
        if ask_qty == 0:
            return 5.0
        return bid_qty / ask_qty
    
    def get_flow_imbalance(self, ticker: Ticker) -> float:
        cutoff = time.time() - self.TRADE_WINDOW
        
        aggressive_buys = 0.0
        aggressive_sells = 0.0
        
        for trade in self.recent_trades[ticker]:
            if trade['time'] > cutoff:
                if trade['side'] == Side.BUY:
                    aggressive_buys += trade['qty']
                else:
                    aggressive_sells += trade['qty']
        
        if aggressive_sells == 0:
            return 5.0 if aggressive_buys > 0 else 1.0
        return aggressive_buys / aggressive_sells
    
    def update_quotes(self, ticker: Ticker):
        """Market make when book is imbalanced BUT flow is neutral"""
        if not self.bids[ticker] or not self.asks[ticker]:
            return
        
        book_imbalance = self.get_book_imbalance(ticker)
        flow_imbalance = self.get_flow_imbalance(ticker)
        
        # Cancel all active orders
        for order_id in self.active_orders[ticker]:
            cancel_order(ticker, order_id)
        self.active_orders[ticker] = []
        
        best_bid = max(self.bids[ticker].keys())
        best_ask = min(self.asks[ticker].keys())
        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        half_spread = spread / 2
        
        # CHECK: Flow must be neutral (avoid adverse selection)
        flow_is_neutral = self.FLOW_MIN <= flow_imbalance <= self.FLOW_MAX
        
        if not flow_is_neutral:
            return  # Don't trade if flow is skewed - too risky
        
        # Now check book imbalance (flow is safe)
        if book_imbalance > self.BOOK_THRESHOLD:
            # BULLISH book + neutral flow = SAFE to market make
            adjusted_mid = mid + (self.MID_SHIFT * spread)
            buy_price = adjusted_mid - half_spread
            sell_price = adjusted_mid + half_spread
            
        elif book_imbalance < (1.0 / self.BOOK_THRESHOLD):
            # BEARISH book + neutral flow = SAFE to market make
            adjusted_mid = mid - (self.MID_SHIFT * spread)
            buy_price = adjusted_mid - half_spread
            sell_price = adjusted_mid + half_spread
            
        else:
            return  # Book neutral - don't pay fees
        
        buy_id = place_limit_order(Side.BUY, ticker, self.BUY_SIZE, buy_price, ioc=False)
        sell_id = place_limit_order(Side.SELL, ticker, self.SELL_SIZE, sell_price, ioc=False)
        
        self.active_orders[ticker] = [buy_id, sell_id]