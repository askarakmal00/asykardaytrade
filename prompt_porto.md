ADD NEW FEATURE: PORTFOLIO MANAGEMENT + AI PORTFOLIO ADVISOR

IMPORTANT:
Add this as a NEW module called "Portfolio".
DO NOT remove, rewrite, break, or change the existing:
- Swing Engine
- Intraday Day Trade Engine
- Screener
- Existing AI Analyst
- Existing market data system
- Existing dashboard
- Existing SQLite database structure unless adding new tables/columns is necessary
- Existing routes and UI

The Portfolio feature must work independently from the existing Swing and Intraday engines.

==================================================
1. OBJECTIVE
==================================================

I want to add a Portfolio Management feature where I can manually enter stocks that I actually own.

For every holding, the application should calculate:
- invested capital
- current market value
- unrealized profit/loss
- profit/loss percentage
- holding duration
- average buy price
- current price

Then the application should provide an AI-based portfolio recommendation.

Possible AI actions:

- HOLD
- STRONG HOLD
- WATCH
- TAKE PROFIT PARTIAL
- TAKE PROFIT
- TIGHTEN STOP LOSS
- CUT LOSS
- EXIT
- WAIT / NO ACTION

The AI recommendation must be based on actual portfolio position data + available technical data + existing rule-based analysis.

The AI must NOT blindly replace the existing trading engines.

==================================================
2. PORTFOLIO DATABASE
==================================================

Create a new portfolio holdings table.

Suggested table:

portfolio_holdings

Fields:

- id
- symbol
- company_name
- quantity
- avg_buy_price
- buy_date
- notes
- target_price
- stop_loss_price
- created_at
- updated_at
- is_active

Use the existing SQLite database and SQLAlchemy architecture.

Do not use a separate database.

Use appropriate numeric types for prices and quantities.

Do not use CLOB for normal portfolio fields.

If the existing database/model conventions differ, follow the existing project architecture.

==================================================
3. ADD POSITION
==================================================

Create an "Add Position" form.

Fields:

Required:
- Stock Symbol
- Quantity / Lot
- Average Buy Price
- Buy Date

Optional:
- Target Price
- Stop Loss
- Notes

Example:

Symbol:
BBCA

Quantity:
10 lots

Average Buy:
8500

Buy Date:
2026-09-01

Target:
9000

Stop Loss:
8200

Notes:
Bought based on bullish breakout

The form must validate:
- symbol exists in IDX symbols/data
- quantity > 0
- avg_buy_price > 0
- valid date

Allow the user to edit and delete positions.

==================================================
4. LOT VS SHARES
==================================================

The UI should use LOT as the primary quantity input because this is Indonesian stock trading.

1 lot = 100 shares.

Internally, calculate shares correctly.

Example:

10 lots
= 1,000 shares

Invested Capital:

quantity_lots × 100 × avg_buy_price

Do not confuse lots with shares.

==================================================
5. PORTFOLIO DASHBOARD
==================================================

Create a new Portfolio page.

Display:

Portfolio Summary:

- Total Invested
- Current Portfolio Value
- Unrealized P/L
- Unrealized P/L %
- Number of Holdings
- Number of profitable positions
- Number of losing positions

Example:

PORTFOLIO

Total Invested
Rp 25,000,000

Current Value
Rp 27,350,000

Unrealized P/L
+Rp 2,350,000

Return
+9.40%

Holdings
5 Stocks

==================================================
6. HOLDINGS TABLE
==================================================

Create a holdings table with:

- Symbol
- Company
- Lots
- Avg Buy
- Current Price
- Invested
- Current Value
- Unrealized P/L
- P/L %
- Holding Days
- AI Action
- AI Confidence

Example:

BBCA
10 lot
8,500
8,850
+4.12%
HOLD
High

BRMS
20 lot
3,200
3,550
+10.94%
TAKE PROFIT PARTIAL
Medium

BUMI
30 lot
250
235
-6.00%
CUT LOSS
High

Use badges/colors for actions but keep the existing application visual style.

==================================================
7. CURRENT PRICE
==================================================

Use the existing market data provider and architecture.

Do NOT create a completely new market data system.

For each portfolio holding:
- retrieve the latest available price
- calculate portfolio P/L

Important:

The application must clearly indicate whether the current price is:
- realtime
- delayed
- end-of-day

Do not present delayed data as realtime.

If the existing Yahoo Finance provider is being used, preserve the existing behavior and label the data appropriately.

==================================================
8. PROFIT / LOSS CALCULATION
==================================================

For each position:

Shares =
lots × 100

Invested Capital =
shares × avg_buy_price

Current Value =
shares × current_price

Unrealized P/L =
current_value - invested_capital

P/L % =
(unrealized_pnl / invested_capital) × 100

Example:

10 lots BBCA
Avg Buy = 8,500
Current = 8,850

Shares = 1,000

Invested:
1,000 × 8,500
= Rp 8,500,000

Current:
1,000 × 8,850
= Rp 8,850,000

P/L:
+Rp 350,000

P/L:
+4.12%

==================================================
9. POSITION DETAIL
==================================================

Clicking a portfolio position should open a detail page/panel.

Show:

- Symbol
- Company
- Position size
- Average buy price
- Current price
- Invested capital
- Current value
- Unrealized P/L
- P/L %
- Buy date
- Holding days
- Target price
- Stop loss
- Notes

Also show technical information available from the existing system:

- RSI
- EMA9
- EMA21
- EMA50
- VWAP if intraday data exists
- MACD
- Volume
- Volume Ratio
- ATR
- Support
- Resistance
- Trend
- Existing Swing Score if available
- Existing Intraday Score if available
- Existing signal/status if available

Do not duplicate calculation logic if these indicators already exist.

Reuse existing indicator/strategy services whenever possible.

==================================================
10. AI PORTFOLIO ADVISOR
==================================================

Add a button:

"AI Portfolio Analysis"

The AI analysis should be ON-DEMAND.

Do not run AI continuously in the background.

When the user clicks the button:

1. Gather portfolio positions
2. Gather current market data
3. Gather existing technical indicators
4. Gather existing Swing analysis if available
5. Gather existing Intraday analysis if available
6. Gather P/L information
7. Gather target/stop-loss information
8. Send structured data to the existing AI system
9. Return structured portfolio recommendations

Use the existing AI architecture.

If the project has already been migrated to Ollama/local AI, use Ollama.

If the current implementation still uses Gemini, do not break it. Follow the current configured AI provider architecture.

==================================================
11. AI MUST NOT INVENT DATA
==================================================

This is extremely important.

The AI may ONLY analyze information explicitly supplied by the application.

The AI must NOT claim that it has access to:
- realtime market data
- live order book
- broker flow
- news
- company fundamentals
- external market information

unless that information is actually provided in the AI input.

If information is missing, say:

"INSUFFICIENT_DATA"

Do not hallucinate.

==================================================
12. AI PORTFOLIO LOGIC
==================================================

The AI should evaluate each position using:

A. Position Performance
- current P/L %
- current P/L amount
- holding duration

B. Technical Trend
- trend direction
- price vs EMA
- RSI
- MACD
- volume
- support/resistance
- ATR

C. Existing Strategy Signals
- Swing score
- Swing status
- Intraday score
- Intraday status
- existing setup

D. Risk
- distance to stop loss
- distance to support
- volatility
- risk/reward if target and stop are available

E. Profit Protection
If the position has significant profit, evaluate whether:
- continue holding
- take partial profit
- move stop loss higher
- exit

F. Loss Management
If the position is losing, evaluate:
- whether the trend is still valid
- whether stop loss has been violated
- whether the original thesis is invalidated
- whether to hold or cut loss

Do NOT automatically recommend holding a losing position just because the stock may recover.

==================================================
13. AI ACTION RULES
==================================================

The AI should choose ONE primary action:

STRONG HOLD
HOLD
WATCH
TIGHTEN STOP LOSS
TAKE PROFIT PARTIAL
TAKE PROFIT
CUT LOSS
EXIT
INSUFFICIENT_DATA

The AI should also provide:

- confidence: HIGH / MEDIUM / LOW
- reason
- key factors
- risk
- suggested action
- suggested stop loss if appropriate
- suggested take profit if appropriate

==================================================
14. IMPORTANT: PARTIAL TAKE PROFIT
==================================================

Support partial take profit.

Example:

Position:
100 lots

AI recommendation:
TAKE PROFIT PARTIAL

Suggested:
Sell 30–50% of position

Keep the remaining position if trend remains bullish.

Do not execute trades automatically.

The application only provides suggestions.

==================================================
15. AI OUTPUT FORMAT
==================================================

Use structured JSON.

Example:

{
  "symbol": "BBCA",
  "action": "TAKE_PROFIT_PARTIAL",
  "confidence": "HIGH",
  "summary": "Position is already profitable and price is approaching resistance.",
  "reason": [
    "P/L is +12.5%",
    "Price is near resistance",
    "RSI is elevated",
    "Trend remains bullish"
  ],
  "risk": [
    "Potential pullback from resistance"
  ],
  "suggested_action": "Consider taking partial profit while keeping part of the position if the bullish trend remains intact.",
  "suggested_take_profit": 9000,
  "suggested_stop_loss": 8500,
  "suggested_sell_percentage": 40
}

IMPORTANT:
The AI does NOT execute any buy/sell order.

==================================================
16. PORTFOLIO-LEVEL AI ANALYSIS
==================================================

In addition to per-stock analysis, provide an overall portfolio analysis.

Example:

AI PORTFOLIO HEALTH

Score:
78 / 100

Status:
GOOD

Summary:
Portfolio is generally healthy, but two positions have elevated downside risk.

Actions:

BBCA
HOLD

BRMS
TAKE PROFIT PARTIAL

BUMI
CUT LOSS

TLKM
WATCH

Also provide:

- concentration risk
- number of losing positions
- number of profitable positions
- biggest winner
- biggest loser
- positions requiring attention

==================================================
17. PORTFOLIO HEALTH SCORE
==================================================

Create an AI Portfolio Health Score from 0–100.

This score should NOT replace the existing stock score.

It is a separate portfolio-level metric.

Example:

90–100 = EXCELLENT
80–89 = GOOD
70–79 = FAIR
60–69 = RISKY
<60 = HIGH RISK

Factors may include:

- diversification
- concentration
- unrealized P/L
- technical health
- stop-loss discipline
- position risk
- number of weak positions

Clearly label this as:

"AI Portfolio Health"

==================================================
18. PORTFOLIO CHARTS
==================================================

Add simple portfolio visualizations:

1. Portfolio allocation
   - percentage by stock

2. Unrealized P/L by stock

3. Portfolio total value

4. Portfolio P/L

Keep charts lightweight and consistent with the existing dashboard.

Do not introduce a heavy charting framework if the project already has one.

==================================================
19. POSITION HISTORY
==================================================

Prepare the architecture for future transaction history.

For now, the user must be able to:
- add position
- edit position
- remove position

Structure the code so future features can support:
- buy transaction
- sell transaction
- partial sell
- average price recalculation
- realized P/L

Do not implement a complex transaction ledger unless necessary for this feature.

==================================================
20. API ENDPOINTS
==================================================

Add clean REST endpoints following the existing FastAPI architecture.

Suggested:

GET
/api/portfolio

POST
/api/portfolio

GET
/api/portfolio/{id}

PUT
/api/portfolio/{id}

DELETE
/api/portfolio/{id}

GET
/api/portfolio/summary

POST
/api/portfolio/ai-analysis

POST
/api/portfolio/{id}/ai-analysis

Use the existing repository/service architecture.

Do not put business logic directly inside route handlers.

==================================================
21. SERVICES
==================================================

Create a dedicated portfolio service if appropriate:

app/services/portfolio_service.py

Responsibilities:

- calculate position metrics
- calculate portfolio summary
- retrieve current market prices
- combine technical analysis
- prepare AI input

Create a dedicated AI portfolio analyst if appropriate:

app/services/portfolio_ai_analyst.py

Responsibilities:

- build structured AI prompt
- call existing AI provider
- validate JSON response
- normalize AI action
- return structured result

Do not duplicate the existing AI provider implementation.

Reuse existing AI infrastructure.

==================================================
22. UI NAVIGATION
==================================================

Add:

Portfolio

to the main navigation.

Recommended order:

Dashboard
Screener
Swing
Intraday
Portfolio

The Portfolio page should feel like part of the existing application.

Do not redesign the entire application.

==================================================
23. DATA REFRESH
==================================================

Add a Refresh button.

When clicked:

- refresh current prices
- recalculate P/L
- update portfolio summary

Do not automatically call AI on every refresh.

AI analysis must remain ON-DEMAND.

==================================================
24. NO AUTO TRADING
==================================================

This application is an analysis and decision-support tool.

NEVER:
- place broker orders
- automatically sell
- automatically buy
- connect to broker trading APIs
- execute trades

AI only provides recommendations.

The user makes the final trading decision.

==================================================
25. ERROR HANDLING
==================================================

If market data is unavailable:

Do not show fake prices.

Display:

"Market data unavailable"

If technical data is insufficient:

"Insufficient technical data"

If AI fails:

"AI analysis unavailable"

The Portfolio page must still work without AI.

==================================================
26. RESOURCE MANAGEMENT
==================================================

Follow the existing AI resource-management design.

AI should be invoked only when the user clicks:

"AI Portfolio Analysis"

Do not keep an AI model running continuously only for Portfolio.

If using local Ollama:
- reuse the existing Ollama configuration
- do not start multiple Ollama instances
- do not load multiple unnecessary models
- respect existing model idle/unload settings

==================================================
27. TESTING
==================================================

After implementation test:

1. Add a portfolio position
2. Edit position
3. Delete position
4. Calculate lots correctly
5. Calculate invested capital
6. Calculate current value
7. Calculate P/L
8. Calculate P/L %
9. Portfolio summary
10. Multiple holdings
11. Market data unavailable
12. AI analysis
13. AI invalid JSON
14. Missing technical data
15. Existing Swing feature still works
16. Existing Intraday feature still works
17. Existing Screener still works
18. Existing AI Analyst still works

==================================================
28. BACKWARD COMPATIBILITY
==================================================

This is a feature expansion.

DO NOT rewrite the application from scratch.

DO NOT remove existing features.

DO NOT replace existing Swing logic.

DO NOT replace existing Intraday logic.

DO NOT replace existing Screener.

DO NOT replace existing AI Analyst.

Use the current project architecture and extend it.

Before modifying code:
- inspect the existing project
- identify existing models
- identify existing repositories
- identify existing market-data services
- identify existing AI services
- identify existing indicator calculations
- identify existing UI/navigation

Reuse existing components wherever possible.

==================================================
29. FINAL IMPLEMENTATION REQUIREMENT
==================================================

After implementation, provide a concise implementation report containing:

1. Files created
2. Files modified
3. Database tables added
4. API endpoints added
5. UI pages/components added
6. AI integration details
7. How Portfolio AI works
8. How P/L is calculated
9. Any limitations
10. Confirmation that existing Swing + Intraday + Screener functionality was preserved

Do not stop after creating the UI.

The feature must be fully connected:
UI → API → Service → Database → Market Data → AI.

Implement this feature cleanly and incrementally within the existing application.