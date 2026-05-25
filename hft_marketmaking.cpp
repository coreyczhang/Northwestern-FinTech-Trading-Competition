#include <cstdint>
#include <string>
#include <unordered_map>
#include <map>
#include <deque>
#include <vector>
#include <cmath>
#include <chrono>
#include <sstream>
#include <iomanip>
#include <algorithm>

enum class Side { buy = 0, sell = 1 };
enum class Ticker : std::uint8_t { ETH = 0, BTC = 1, LTC = 2 };

bool place_market_order(Side side, Ticker ticker, float quantity);
std::int64_t place_limit_order(Side side, Ticker ticker, float quantity,
                               float price, bool ioc = false);
bool cancel_order(Ticker ticker, std::int64_t order_id);
void println(const std::string &text);

struct Trade {
    double time;
    Side side;
    float qty;
};

class Strategy {
private:
    // ===== CONFIGURATION =====
    static constexpr Ticker TRADE_TICKER = Ticker::LTC;
    static constexpr float BOOK_THRESHOLD = 1.5f;
    static constexpr float FLOW_MIN = 0.95f;
    static constexpr float FLOW_MAX = 1.05f;
    static constexpr int TRADE_WINDOW = 10;
    static constexpr double UPDATE_INTERVAL = 0.05;  // Faster updates for more gains
    static constexpr float MID_SHIFT = 0.25f;
    static constexpr float BUY_SIZE = 100.0f;
    static constexpr float SELL_SIZE = 100.0f;
    // =========================
    
    // Orderbook tracking - use map for O(log n) best bid/ask
    std::unordered_map<int, std::map<float, float>> bids;  // ticker -> price -> qty
    std::unordered_map<int, std::map<float, float>> asks;  // ticker -> price -> qty
    
    // Trade flow tracking
    std::unordered_map<int, std::deque<Trade>> recent_trades;
    
    // Order management
    std::unordered_map<int, std::vector<std::int64_t>> active_orders;
    
    // Timing
    std::unordered_map<int, double> last_update;
    
    double get_time() const {
        return std::chrono::duration<double>(
            std::chrono::high_resolution_clock::now().time_since_epoch()
        ).count();
    }
    
    bool should_trade(Ticker ticker) const {
        return ticker == TRADE_TICKER;
    }
    
    float get_book_imbalance(Ticker ticker) {
        int t = static_cast<int>(ticker);
        
        if (bids[t].empty() || asks[t].empty()) {
            return 1.0f;
        }
        
        float bid_qty = 0.0f;
        for (auto& p : bids[t]) bid_qty += p.second;
        
        float ask_qty = 0.0f;
        for (auto& p : asks[t]) ask_qty += p.second;
        
        if (ask_qty == 0.0f) return 5.0f;
        return bid_qty / ask_qty;
    }
    
    float get_flow_imbalance(Ticker ticker) {
        int t = static_cast<int>(ticker);
        double cutoff = get_time() - TRADE_WINDOW;
        
        float aggressive_buys = 0.0f;
        float aggressive_sells = 0.0f;
        
        for (auto& trade : recent_trades[t]) {
            if (trade.time > cutoff) {
                if (trade.side == Side::buy) {
                    aggressive_buys += trade.qty;
                } else {
                    aggressive_sells += trade.qty;
                }
            }
        }
        
        if (aggressive_sells == 0.0f) {
            return aggressive_buys > 0.0f ? 5.0f : 1.0f;
        }
        return aggressive_buys / aggressive_sells;
    }
    
    void update_quotes(Ticker ticker) {
        int t = static_cast<int>(ticker);
        
        if (bids[t].empty() || asks[t].empty()) {
            return;
        }
        
        float book_imbalance = get_book_imbalance(ticker);
        float flow_imbalance = get_flow_imbalance(ticker);
        
        // Cancel all active orders
        for (auto oid : active_orders[t]) {
            try {
                cancel_order(ticker, oid);
            } catch (...) {}
        }
        active_orders[t].clear();
        
        // Get best bid/ask
        float best_bid = bids[t].rbegin()->first;
        float best_ask = asks[t].begin()->first;
        float mid = (best_bid + best_ask) * 0.5f;
        float spread = best_ask - best_bid;
        float half_spread = spread * 0.5f;
        
        // CHECK: Flow must be neutral
        bool flow_is_neutral = (flow_imbalance >= FLOW_MIN) && (flow_imbalance <= FLOW_MAX);
        
        if (!flow_is_neutral) {
            return;  // Avoid adverse selection
        }
        
        float adjusted_mid = mid;
        float buy_price = 0.0f;
        float sell_price = 0.0f;
        
        // Bullish book
        if (book_imbalance > BOOK_THRESHOLD) {
            adjusted_mid = mid + (MID_SHIFT * spread);
            buy_price = adjusted_mid - half_spread;
            sell_price = adjusted_mid + half_spread;
        }
        // Bearish book
        else if (book_imbalance < (1.0f / BOOK_THRESHOLD)) {
            adjusted_mid = mid - (MID_SHIFT * spread);
            buy_price = adjusted_mid - half_spread;
            sell_price = adjusted_mid + half_spread;
        }
        else {
            return;  // Book neutral - sit out
        }
        
        // Place orders
        try {
            std::int64_t buy_id = place_limit_order(Side::buy, ticker, BUY_SIZE, buy_price, false);
            std::int64_t sell_id = place_limit_order(Side::sell, ticker, SELL_SIZE, sell_price, false);
            active_orders[t].push_back(buy_id);
            active_orders[t].push_back(sell_id);
        } catch (...) {}
    }
    
public:
    Strategy() {
        println("Market maker initialized - trading LTC only (max gainz mode)");
    }
    
    void on_trade_update(Ticker ticker, Side side, float quantity, float price) {
        if (!should_trade(ticker)) return;
        
        int t = static_cast<int>(ticker);
        recent_trades[t].push_back({get_time(), side, quantity});
        
        // Cleanup old trades
        double cutoff = get_time() - 60.0;
        while (!recent_trades[t].empty() && recent_trades[t].front().time < cutoff) {
            recent_trades[t].pop_front();
        }
    }
    
    void on_orderbook_update(Ticker ticker, Side side, float quantity, float price) {
        if (!should_trade(ticker)) return;
        
        int t = static_cast<int>(ticker);
        
        if (side == Side::buy) {
            if (quantity > 0.0f) {
                bids[t][price] = quantity;
            } else {
                bids[t].erase(price);
            }
        } else {
            if (quantity > 0.0f) {
                asks[t][price] = quantity;
            } else {
                asks[t].erase(price);
            }
        }
        
        double now = get_time();
        if (now - last_update[t] < UPDATE_INTERVAL) {
            return;
        }
        last_update[t] = now;
        
        update_quotes(ticker);
    }
    
    void on_account_update(Ticker ticker, Side side, float price, float quantity,
                          float capital_remaining) {
        if (!should_trade(ticker)) return;
        // Fill received - continue trading
    }
};