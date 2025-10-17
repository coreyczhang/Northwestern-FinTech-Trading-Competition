from enum import Enum
import time

class Side(Enum):
    BUY = 0
    SELL = 1

class Ticker(Enum):
    ETH = 0
    BTC = 1
    LTC = 2

def place_market_order(side: Side, ticker: Ticker, quantity: float) -> bool:
    """Place a market order - DO NOT MODIFY

    Parameters
    ----------
    side
        Side of order to place (Side.BUY or Side.SELL)
    ticker
        Ticker of order to place (Ticker.ETH, Ticker.BTC, or "LTC")
    quantity
        Volume of order to place
    """
    return True

def place_limit_order(side: Side, ticker: Ticker, quantity: float, price: float, ioc: bool = False) -> int:
    """Place a limit order - DO NOT MODIFY

    Parameters
    ----------
    side
        Side of order to place (Side.BUY or Side.SELL)
    ticker
        Ticker of order to place (Ticker.ETH, Ticker.BTC, or "LTC")
    quantity
        Volume of order to place
    price
        Price of order to place

    Returns
    -------
    order_id
    """
    return 0

def cancel_order(ticker: Ticker, order_id: int) -> bool:
    """Place a limit order - DO NOT MODIFY
    Parameters
    ----------
    ticker
        Ticker of order to place (Ticker.ETH, Ticker.BTC, or "LTC")
    order_id
        order_id returned by place_limit_order
    """
    return True

# You can use print() and view the logs after sandbox run has completed
# Might help for debugging
class Strategy:
    def __init__(self) -> None:
        self.tickers = [Ticker.ETH, Ticker.BTC, Ticker.LTC]

        self.best_bid = {t: None for t in self.tickers}
        self.best_ask = {t: None for t in self.tickers}
        self.prices_ts = {t: 0 for t in self.tickers}
        self.last_reprice = 0.0
        self.reprice_interval = 0.2
        self.max_prices_stored = 50
        self.prices = {t: [] for t in self.tickers}
        self.positions = {t: 0 for t in self.tickers}
        self.capital = 100000
        self.max_position = 200
        self.order_book_orders = {t: {"buy": None, "sell": None} for t in self.tickers}
        self.order_book_prices = {t: {"buy": None, "sell": None} for t in self.tickers}
        self.order_size = 10

    def _safe_cancel(self, ticker: Ticker, side_str: str):
        oid = self.order_book_orders[ticker][side_str]
        if oid is not None:
            try:
                cancel_order(ticker, oid)
            except Exception:
                pass
            self.order_book_orders[ticker][side_str] = None
            self.order_book_prices[ticker][side_str] = None

    def _place_limit(self, side: Side, ticker: Ticker, qty: float, price: float):
        try:
            oid = place_limit_order(side, ticker, qty, price, ioc=False)
            if side == Side.BUY:
                self.order_book_orders[ticker]["buy"] = oid
                self.order_book_prices[ticker]["buy"] = price
            else:
                self.order_book_orders[ticker]["sell"] = oid
                self.order_book_prices[ticker]["sell"] = price
        except Exception:
            pass

    def _manage_market_maker(self, ticker: Ticker):
        bid = self.best_bid[ticker]
        ask = self.best_ask[ticker]
        if bid is None or ask is None:
            return
        mid = (bid + ask) / 2.0
        spread = ask - bid
        tick = max(0.01, spread * 0.25)

        target_buy = round(mid - tick, 8)
        target_sell = round(mid + tick, 8)

        pos = self.positions[ticker]
        can_buy = pos < self.max_position and (self.capital > target_buy * self.order_size)
        can_sell = pos > -self.max_position

        current_buy_price = self.order_book_prices[ticker]["buy"]
        if current_buy_price is None or abs(current_buy_price - target_buy) > max(0.0001, 0.5 * tick):
            self._safe_cancel(ticker, "buy")
            if can_buy:
                self._place_limit(Side.BUY, ticker, self.order_size, target_buy)

        current_sell_price = self.order_book_prices[ticker]["sell"]
        if current_sell_price is None or abs(current_sell_price - target_sell) > max(0.0001, 0.5 * tick):
            self._safe_cancel(ticker, "sell")
            if can_sell:
                self._place_limit(Side.SELL, ticker, self.order_size, target_sell)

    def on_trade_update(self, ticker: Ticker, side: Side, price: float, quantity: float) -> None:
        self.prices[ticker].append(price)
        if len(self.prices[ticker]) > self.max_prices_stored:
            self.prices[ticker].pop(0)
        now = time.time()
        if now - self.last_reprice > self.reprice_interval:
            for t in [Ticker.ETH, Ticker.BTC, Ticker.LTC]:
                self._manage_market_maker(t)
            self.last_reprice = now

    def on_orderbook_update(self, ticker: Ticker, side: Side, price: float, quantity: float) -> None:
        if side == Side.BUY:
            self.best_bid[ticker] = price
        elif side == Side.SELL:
            self.best_ask[ticker] = price
        self.prices_ts[ticker] = time.time()
        now = time.time()
        if now - self.last_reprice > self.reprice_interval:
            for t in [Ticker.ETH, Ticker.BTC, Ticker.LTC]:
                self._manage_market_maker(t)
            self.last_reprice = now

    def on_account_update(self, ticker: Ticker, side: Side, price: float, quantity: float, capital_remaining: float) -> None:
        if side == Side.BUY:
            self.positions[ticker] += quantity
        elif side == Side.SELL:
            self.positions[ticker] -= quantity
        self.capital = capital_remaining
        if self.positions[ticker] >= self.max_position:
            self._safe_cancel(ticker, "buy")
        if self.positions[ticker] <= -self.max_position:
            self._safe_cancel(ticker, "sell")
        total_value = self.capital + sum(self.positions[t] * (self.prices[t][-1] if self.prices[t] else 0) for t in self.tickers)
        print(f"Portfolio Value: {total_value:.2f}")