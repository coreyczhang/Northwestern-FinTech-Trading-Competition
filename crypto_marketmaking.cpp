#include <cstdint>
#include <string>
#include <array>
#include <chrono>
#include <cmath>
#include <vector>
#include <cstdio>

// ---------- Exchange API Stubs (do not modify) ----------
enum class Side { buy = 0, sell = 1 };
enum class Ticker : std::uint8_t { ETH = 0, BTC = 1, LTC = 2 };

bool place_market_order(Side side, Ticker ticker, float quantity);
std::int64_t place_limit_order(Side side, Ticker ticker, float quantity, float price, bool ioc = false);
bool cancel_order(Ticker ticker, std::int64_t order_id);
void println(const std::string &text);

// ---------- Strategy Implementation ----------
class Strategy {
public:
  Strategy() {
    using namespace std::chrono;
    last_reprice = steady_clock::now();
    for (size_t i = 0; i < N; ++i) {
      best_bid[i] = best_ask[i] = 0.0f;
      have_bid[i] = have_ask[i] = false;
      order_id_buy[i] = order_id_sell[i] = 0;
      pos[i] = 0.0f;
      last_trade_price[i] = 0.0f;
      ph_write_idx[i] = 0;
      price_history[i].fill(0.0f);
    }
  }

  void on_trade_update(Ticker ticker, Side side, float quantity, float price) {
    size_t i = idx(ticker);
    last_trade_price[i] = price;
    price_history[i][ph_write_idx[i]] = price;
    ph_write_idx[i] = (ph_write_idx[i] + 1) % PH_SZ;
    maybe_reprice();
  }

  void on_orderbook_update(Ticker ticker, Side side, float quantity, float price) {
    size_t i = idx(ticker);
    if (side == Side::buy) {
      best_bid[i] = price;
      have_bid[i] = true;
    } else {
      best_ask[i] = price;
      have_ask[i] = true;
    }
    maybe_reprice();
  }

  void on_account_update(Ticker ticker, Side side, float price, float quantity, float capital_remaining) {
    size_t i = idx(ticker);
    if (side == Side::buy)
      pos[i] += quantity;
    else
      pos[i] -= quantity;

    cash = capital_remaining;
    if (pos[i] > MAX_POS) place_market_order(Side::sell, ticker, pos[i] - MAX_POS);
    if (pos[i] < -MAX_POS) place_market_order(Side::buy, ticker, -MAX_POS - pos[i]);

    float total = cash;
    for (size_t j = 0; j < N; ++j)
      total += pos[j] * mark_price(j);
    println("Portfolio Value: " + to_fixed(total, 2));
  }

private:
  // ===== Parameters =====
  static constexpr size_t N = 3;
  static constexpr int REPRICE_MS = 1;          // ultra-high frequency
  static constexpr float ORDER_SIZE = 2.0f;
  static constexpr float MAX_POS = 250.0f;
  static constexpr float MIN_TICK = 0.0001f;
  static constexpr float SPREAD_FACTOR = 0.25f;
  static constexpr size_t PH_SZ = 32;
  static constexpr float MOM_TH = 0.0025f;

  // ===== State =====
  std::array<float, N> best_bid{};
  std::array<float, N> best_ask{};
  std::array<bool, N> have_bid{};
  std::array<bool, N> have_ask{};
  std::array<std::int64_t, N> order_id_buy{};
  std::array<std::int64_t, N> order_id_sell{};
  std::array<float, N> order_price_buy{};
  std::array<float, N> order_price_sell{};
  std::array<float, N> pos{};
  std::array<float, N> last_trade_price{};
  std::array<std::array<float, PH_SZ>, N> price_history{};
  std::array<size_t, N> ph_write_idx{};
  float cash = 100000.0f;
  std::chrono::steady_clock::time_point last_reprice;

  // ===== Utility =====
  static size_t idx(Ticker t) { return static_cast<size_t>(t); }

  static std::string to_fixed(double v, int p) {
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%.*f", p, v);
    return std::string(buf);
  }

  float mark_price(size_t i) const {
    if (have_bid[i] && have_ask[i]) return 0.5f * (best_bid[i] + best_ask[i]);
    float p = last_trade_price[i];
    if (p > 0.0f) return p;
    return price_history[i][(ph_write_idx[i] + PH_SZ - 1) % PH_SZ];
  }

  void maybe_reprice() {
    using namespace std::chrono;
    auto now = steady_clock::now();
    if (duration_cast<milliseconds>(now - last_reprice).count() < REPRICE_MS) return;
    last_reprice = now;
    for (Ticker t : {Ticker::ETH, Ticker::BTC, Ticker::LTC})
      manage_ticker(t);
  }

  void manage_ticker(Ticker t) {
    size_t i = idx(t);
    if (!have_bid[i] || !have_ask[i]) return;

    float bid = best_bid[i];
    float ask = best_ask[i];
    if (ask <= bid) return;

    float mid = 0.5f * (bid + ask);
    float spread = std::max(ask - bid, mid * 0.0002f);
    float tick = std::max(MIN_TICK, spread * SPREAD_FACTOR);
    float target_buy = mid - tick;
    float target_sell = mid + tick;

    float cur_pos = pos[i];
    if (cur_pos > 0.0f) target_buy -= tick * 0.5f;
    else if (cur_pos < 0.0f) target_sell += tick * 0.5f;

    // momentum filter
    float mom = compute_momentum(i);
    if (mom < -MOM_TH) safe_cancel_buy(i);
    else if (need_replace(order_price_buy[i], target_buy, tick)) {
      safe_cancel_buy(i);
      if (cur_pos < MAX_POS && cash > target_buy * ORDER_SIZE)
        place_limit_buy(t, ORDER_SIZE, target_buy);
    }

    if (mom > MOM_TH) safe_cancel_sell(i);
    else if (need_replace(order_price_sell[i], target_sell, tick)) {
      safe_cancel_sell(i);
      if (cur_pos > -MAX_POS)
        place_limit_sell(t, ORDER_SIZE, target_sell);
    }

    // small momentum scalping
    if (mom > MOM_TH && cur_pos > -MAX_POS)
      place_market_order(Side::buy, t, 1.0f);
    else if (mom < -MOM_TH && cur_pos < MAX_POS)
      place_market_order(Side::sell, t, 1.0f);
  }

  bool need_replace(float cur, float target, float tick) {
    return cur == 0.0f || std::fabs(cur - target) > 0.5f * tick;
  }

  float compute_momentum(size_t i) {
    float short_sum = 0, long_sum = 0;
    int short_n = 3, long_n = 12;
    std::vector<float> vals;
    for (size_t k = 0; k < PH_SZ; ++k) {
      float v = price_history[i][(ph_write_idx[i] + PH_SZ - 1 - k) % PH_SZ];
      if (v > 0.0f) vals.push_back(v);
    }
    if ((int)vals.size() < long_n) return 0.0f;
    for (int j = 0; j < short_n; ++j) short_sum += vals[j];
    for (int j = 0; j < long_n; ++j) long_sum += vals[j];
    return ((short_sum / short_n) - (long_sum / long_n)) / (long_sum / long_n);
  }

  void safe_cancel_buy(size_t i) {
    if (order_id_buy[i] != 0) {
      cancel_order(static_cast<Ticker>(i), order_id_buy[i]);
      order_id_buy[i] = 0; order_price_buy[i] = 0;
    }
  }
  void safe_cancel_sell(size_t i) {
    if (order_id_sell[i] != 0) {
      cancel_order(static_cast<Ticker>(i), order_id_sell[i]);
      order_id_sell[i] = 0; order_price_sell[i] = 0;
    }
  }
  void place_limit_buy(Ticker t, float qty, float price) {
    std::int64_t oid = place_limit_order(Side::buy, t, qty, price, false);
    if (oid != 0) {
      size_t i = idx(t);
      order_id_buy[i] = oid;
      order_price_buy[i] = price;
    }
  }
  void place_limit_sell(Ticker t, float qty, float price) {
    std::int64_t oid = place_limit_order(Side::sell, t, qty, price, false);
    if (oid != 0) {
      size_t i = idx(t);
      order_id_sell[i] = oid;
      order_price_sell[i] = price;
    }
  }
};