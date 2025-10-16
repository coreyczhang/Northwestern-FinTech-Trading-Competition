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
    """Mean-reversion strategy with small thresholds and cooldown."""

    def __init__(self) -> None:
        self.prices = []
        self.max_prices_stored = 30
        self.capital = 100000
        self.position = 0
        self.max_position = 100
        self.ticker = Ticker.ETH
        self.last_trade_time = 0
        self.cooldown = 0.1  # seconds between trades

    def on_trade_update(self, ticker: Ticker, side: Side, price: float, quantity: float) -> None:
        self.prices.append(price)
        if len(self.prices) > self.max_prices_stored:
            self.prices.pop(0)

        if len(self.prices) < 5:
            return

        avg_price = sum(self.prices) / len(self.prices)
        latest_price = price
        trade_qty = 1

        now = time.time()
        if now - self.last_trade_time < self.cooldown:
            return

        # Buy if price slightly below average
        if latest_price < 0.9995 * avg_price:
            if self.capital >= latest_price * trade_qty and self.position < self.max_position:
                place_market_order(Side.BUY, ticker, trade_qty)
                self.last_trade_time = now

        # Sell if price slightly above average
        elif latest_price > 1.0005 * avg_price:
            if self.position >= trade_qty:
                place_market_order(Side.SELL, ticker, trade_qty)
                self.last_trade_time = now

    def on_orderbook_update(self, ticker: Ticker, side: Side, price: float, quantity: float) -> None:
        pass

    def on_account_update(
        self, ticker: Ticker, side: Side, price: float, quantity: float, capital_remaining: float
    ) -> None:
        if side == Side.BUY:
            self.position += quantity
        elif side == Side.SELL:
            self.position -= quantity
        self.capital = capital_remaining