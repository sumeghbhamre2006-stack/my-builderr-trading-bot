from __future__ import annotations

# The high-momentum AI/Chip universe recommended in ANATOMY.md
_UNIVERSE = ("NVDA", "AMD", "MU", "MRVL", "AVGO", "SMH")

# Strategy Constants
_LOOKBACK_3M = 60      # ~3 months of trading days to calculate momentum
_STOCK_MA = 50         # Asset trend filter
_MARKET_MA = 100       # Macro safety switch lookback
_MAX_POSITIONS = 4     # Top 4 assets maximum (25% each to stay under 30% cap)

def decide(market_state, portfolio_state, cash):
    # 1. MACRO SAFETY SWITCH: Check QQQ 100-day Moving Average
    qqq_bars = market_state.get("QQQ") or []
    if len(qqq_bars) < _MARKET_MA:
        return [] # Wait for enough data
        
    qqq_closes = [float(b["close"]) for b in qqq_bars]
    qqq_current = qqq_closes[-1]
    qqq_ma = sum(qqq_closes[-_MARKET_MA:]) / _MARKET_MA
    
    # Parse current portfolio
    positions_list = portfolio_state.get("positions") or []
    current_positions = {p["ticker"]: p["quantity"] for p in positions_list if p.get("quantity", 0) > 0}
    orders = []

    # Calculate total portfolio value to ensure we size accurately based on overall wealth
    total_equity = cash + sum(
        current_positions.get(t, 0) * float(market_state[t][-1]["close"])
        for t in current_positions if t in market_state and market_state[t]
    )

    # If QQQ is below its 100-day average -> EMERGENCY LIQUIDATION TO CASH
    if qqq_current < qqq_ma:
        for ticker, qty in current_positions.items():
            if qty > 0:
                orders.append({"ticker": ticker, "side": "sell", "quantity": qty})
        return orders

    # 2. MOMENTUM RANKING (Only runs if market is safe)
    valid_candidates = []
    
    for ticker in _UNIVERSE:
        bars = market_state.get(ticker) or []
        if len(bars) < max(_LOOKBACK_3M, _STOCK_MA):
            continue
            
        closes = [float(b["close"]) for b in bars]
        current_price = closes[-1]
        
        # Calculate 50-day moving average for the individual stock
        stock_ma = sum(closes[-_STOCK_MA:]) / _STOCK_MA
        
        # Rule: Stock MUST be above its own 50-day MA to be considered
        if current_price > stock_ma:
            # Calculate 3-month return
            return_3m = (current_price / closes[-_LOOKBACK_3M]) - 1
            valid_candidates.append((ticker, return_3m))
            
    # Sort candidates by highest return descending
    valid_candidates.sort(key=lambda x: x[1], reverse=True)
    
    # Pick the top 4 strongest performers
    target_tickers = [item[0] for item in valid_candidates[:_MAX_POSITIONS]]

    # 3. EXECUTE REBALANCING
    # Sell anything we currently hold that didn't make the top list anymore
    for ticker, qty in current_positions.items():
        if ticker not in target_tickers and qty > 0:
            orders.append({"ticker": ticker, "side": "sell", "quantity": qty})

    if not target_tickers:
        return orders

    # FIX: Always size based on total equity divided by 4 (exactly 25% max allocation per asset)
    # This ensures we NEVER breach the 30% concentration cap, even if only 1 stock qualifies.
    per_ticker_cash_limit = total_equity / 4
    
    for t in target_tickers:
        # If we already hold it, keep it
        if t in current_positions:
            continue
            
        bars = market_state.get(t) or []
        last_close = float(bars[-1]["close"])
        if last_close <= 0:
            continue
        
        # Spend up to our 25% limit, but make sure we don't buy more than actual available cash
        spend_cash = min(per_ticker_cash_limit, cash)
        qty = int(spend_cash // last_close)
        if qty > 0:
            orders.append({"ticker": t, "side": "buy", "quantity": qty})
            cash -= (qty * last_close) # Deduct cash as we prepare orders

    return orders