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

# You can use print() and view the logs after sandbox run has completed
class Strategy:
    def __init__(self) -> None:
        # ===== CONFIGURATION =====
        self.TRADE_TICKER = Ticker.LTC
        self.BOOK_THRESHOLD = 1.7  # Strong book imbalance needed
        self.FLOW_MIN = 0.95  # Flow must be between 0.95-1.05 (neutral)
        self.FLOW_MAX = 1.05
        self.TRADE_WINDOW = 10
        self.UPDATE_INTERVAL = 0.1
        self.MID_SHIFT = 0.25
        # =========================
        
        # Orderbook tracking
        self.bids = defaultdict(dict)
        self.asks = defaultdict(dict)
        
        # Trade flow tracking
        self.recent_trades = defaultdict(deque)
        
        # Order management
        self.active_orders = defaultdict(list)
        
        # Timing
        self.last_update = defaultdict(float)
        
        # Performance tracking
        self.buy_fills = 0
        self.sell_fills = 0
        self.last_print_time = time.time()
        
        if self.TRADE_TICKER:
            print(f"Market maker initialized - trading {self.TRADE_TICKER.name} only")
        else:
            print("Market maker initialized - trading all tickers")
    
    def should_trade(self, ticker: Ticker) -> bool:
        if self.TRADE_TICKER is None:
            return True
        return ticker == self.TRADE_TICKER
    
    def on_trade_update(self, ticker: Ticker, side: Side, quantity: float, price: float) -> None:
        if not self.should_trade(ticker):
            return
        
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
        if not self.should_trade(ticker):
            return
        
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
        if not self.should_trade(ticker):
            return
        
        # Track fills
        if side == Side.BUY:
            self.buy_fills += 1
        else:
            self.sell_fills += 1
        
        # Print stats every 30 seconds
        current_time = time.time()
        if current_time - self.last_print_time >= 30:
            total_trades = self.buy_fills + self.sell_fills
            print(f"=== 30s Stats ===")
            print(f"Total trades: {total_trades} (Buys: {self.buy_fills}, Sells: {self.sell_fills})")
            print(f"=================")
            self.last_print_time = current_time
        
        #print(f"Fill: {side.name} {quantity} {ticker.name} @ {price:.2f}")
    
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
        """Biased market making with shifted mid"""
        if not self.bids[ticker] or not self.asks[ticker]:
            return
        
        book_imbalance = self.get_book_imbalance(ticker)
        flow_imbalance = self.get_flow_imbalance(ticker)

        print(f"{ticker.name} - Book: {book_imbalance:.2f}, Flow: {flow_imbalance:.2f}")
        
        for order_id in self.active_orders[ticker]:
            cancel_order(ticker, order_id)
        self.active_orders[ticker] = []
        
        best_bid = max(self.bids[ticker].keys())
        best_ask = min(self.asks[ticker].keys())
        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        
        # CHECK: Flow must be neutral (avoid aggressive informed traders)
        flow_is_neutral = self.FLOW_MIN <= flow_imbalance <= self.FLOW_MAX
        
        if not flow_is_neutral:
            return
        
        # Exploit book imbalance with competitive pricing
        if book_imbalance > self.BOOK_THRESHOLD:
            # BULLISH: More buyers - competitive sell, avoid buying
            sell_price = mid + (self.MID_SHIFT * spread)  # Inside spread - competitive!
            sell_size = 100
            
            buy_price = best_bid - (2.0 * spread)  # Far below - avoid buying
            buy_size = 50
            
        elif book_imbalance < (1.0 / self.BOOK_THRESHOLD):
            # BEARISH: More sellers - competitive buy, avoid selling
            buy_price = mid - (self.MID_SHIFT * spread)  # Inside spread - competitive!
            buy_size = 100
            
            sell_price = best_ask + (2.0 * spread)  # Far above - avoid selling
            sell_size = 50
            
        else:
            return
        
        buy_id = place_limit_order(Side.BUY, ticker, buy_size, buy_price, ioc=False)
        sell_id = place_limit_order(Side.SELL, ticker, sell_size, sell_price, ioc=False)
        
        self.active_orders[ticker] = [buy_id, sell_id]