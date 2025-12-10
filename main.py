from fastapi import FastAPI # importing fastapi
from fastapi.responses import HTMLResponse #for design
from pydantic import BaseModel #importing pydantic for data validation
import pandas as pd
from typing import List
import uuid
import time
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request


app = FastAPI()# creating an app

#simple logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

#middleware to add a request id + timing
@app.middleware("http")
async def add_request_id_and_timing(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start = time.time()

    #add header so downstream clinets get it too
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)

    response.headers["X-Request-ID"] = request_id

    #log a structured event
    logging.info(
        f"request_id={request_id}"
        f"path={request.url.path}"
        f"method={request.method}"
        f"duration_ms={duration}"
    )

    return response

MOCK_PRICES = { #pretend live market data from an equities feed
    "AAPL" :185.40,
    "MSFT" :320.10,
    "TSLA" :250.75,
    "AMZN" :140.30,
}

class Trade(BaseModel): #using pydantic for data validation 
    symbol: str
    qty: int
    price: float #execution price

class PnlEntry(BaseModel):
    symbol: str
    pnl: float #added pnl entry model

TRADES_DF = pd.read_csv("trades.csv") #big trades view
PRICES_DF = pd.read_csv("prices.csv") #mini market for screener


@app.get("/health") # first endpoint
def health_check():
    return {"status": "ok"} # returning simple JSON

@app.get("/prices/{symbol}")
def get_prices(symbol: str):
    symbol = symbol.upper() #turns into caps lock
    price = MOCK_PRICES.get(symbol)

    if price is None:
        #symbol not in our mock data
        return {"symbol": symbol, "error" : "symbol not found"}
    
    return {"symbol":symbol, "price": price}

@app.post("/trade") #create page
# - we look up current market price
def submit_trade(trade: Trade):

    # we look up the current market price
    # compare it to the trade price
    # return unrealised p&l
    
    symbol = trade.symbol.upper()
    market_price = MOCK_PRICES.get(symbol)

    if market_price is None:
        return {"symbol": symbol, "error": "symbol not found"}
    
    pnl = (market_price - trade.price) * trade.qty

    return {
        "symbol": symbol,
        "qty": trade.qty,
        "trade_price": trade.price,
        "market_price": market_price,
        "unrealised_pnl": pnl,
    }

def summarise_pnl_with_llm(total_pnl: float, count: int) -> str:
    direction = "profit" if total_pnl >= 0 else "loss"
    return (
        f"Across {count} trades, the total {direction} is {total_pnl:.2f}. "
        "This is a simple rule-based summary; in production an LLM via Bedrock "
        "would generate richer narrative and breakdowns."
        #just using a helper now, but this is exactly where a bedrock llm call would go
        #this is a simple rule-based summary; in production an LLM via bedrock would gen richer narrative and breakdowns
    )

@app.post("/summarise-pnl")
def summarise_pnl(entries: List[PnlEntry]):
    #accepts a list of p and l entries and return:
    # the total p and l
    # avg p and l
    # a simple "llm style" summary string

    if not entries:
        return {"error": "no PnL entries provided"}
    
    total = sum(e.pnl for e in entries)
    avg = total / len(entries)

    summary = summarise_pnl_with_llm(total, len(entries))

    return {
        "total_pnl": total,
        "average_pnl": avg,
        "count": len(entries),
        "summary": summary,
    }

@app.get("/screener")
def screener(limit: int = 5, direction: str = "gainers"):
   
    
   """" 
    uses PRICES_DF with columns: symbol,prices, prev price
    simple stock screene endpoint
    calculates percentage change
    ranks symbols by move
    returns top N gainers or losers as json
    """
    #starts global prices dataframe
   df = PRICES_DF.copy() #copied so it doesnt mutate the global data
   
   #avoids didivde by 0 or bad date
   df = df[df["prev_price"] > 0]#sanity check to filter out the division under 0

   #add a percentage change column, brain of screener here, compute % move for ticker
   df["change_pct"] = (df["price"] - df["prev_price"]) / df["prev_price"] * 100

   #decide how to sort: gainers vs losers
   if direction == "losers":
       ranked = df.sort_values("change_pct", ascending=True)
   else:
       #its gianers here
       ranked = df.sort_values("change_pct", ascending=False)

   result = ranked.head(limit)[["symbol", "price", "prev_price", "change_pct"]]
   
   return result.to_dict(orient="records")
       

   
@app.get("/big-trades")
def big_trades(min_qty: int = 100):
    #return trades where quantity >+ min_qty
    #simulates basic analytics api used in equities platforms.

    filtered = TRADES_DF[TRADES_DF["qty"]>= min_qty]
    return filtered.to_dict(orient="records")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(min_qty: int = 100):
    # Price table rows
    price_rows = ""
    for symbol, price in MOCK_PRICES.items():
        price_rows += f"""
            <tr>
                <td class="symbol">{symbol}</td>
                <td class="price">£{price:.2f}</td>
            </tr>
        """

    # Big trades rows using pandas
    big = TRADES_DF[TRADES_DF["qty"] >= min_qty]
    trade_rows = ""
    for _, row in big.iterrows():
        notional = row["qty"] * row["price"]
        trade_rows += f"""
            <tr>
                <td class="symbol">{row['symbol']}</td>
                <td>{row['qty']}</td>
                <td>£{row['price']}</td>
                <td>£{notional:,.0f}</td>
            </tr>
        """

    # Top movers using PRICES_DF (basic screener logic)
    movers_df = PRICES_DF.copy()
    movers_df = movers_df[movers_df["prev_price"] > 0]
    movers_df["change_pct"] = (movers_df["price"] - movers_df["prev_price"]) / movers_df["prev_price"] * 100
    movers_df = movers_df.sort_values("change_pct", ascending=False).head(5)

    movers_rows = ""
    for _, row in movers_df.iterrows():
        direction_class = "move-up" if row["change_pct"] >= 0 else "move-down"
        movers_rows += f"""
            <tr>
                <td class="symbol">{row['symbol']}</td>
                <td>£{row['price']:.2f}</td>
                <td class="{direction_class}">{row['change_pct']:.2f}%</td>
            </tr>
        """

    html = f"""
    <html>
        <head>
            <title>Equities Trader Dashboard</title>
            <style>
                body {{
                    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                    background: radial-gradient(circle at top, #1b2735 0, #090a0f 45%, #050509 100%);
                    color: #e6e6e6;
                    margin: 0;
                    padding: 24px;
                }}
                h1 {{
                    margin: 0 0 0.25rem 0;
                    font-size: 1.8rem;
                }}
                .sub {{
                    color: #9ca3af;
                    font-size: 0.9rem;
                    margin-bottom: 1.5rem;
                }}
                .grid {{
                    display: grid;
                    grid-template-columns: 1.1fr 1.1fr;
                    gap: 1.5rem;
                    align-items: flex-start;
                }}
                .panel {{
                    background: rgba(10, 10, 15, 0.92);
                    border-radius: 10px;
                    padding: 14px 16px 12px 16px;
                    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5);
                    border: 1px solid rgba(75, 85, 99, 0.6);
                }}
                .panel h2 {{
                    margin: 0;
                    font-size: 1.1rem;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                }}
                .panel-wide {{
                    grid-column: 1 / -1; /* span full width */
                }}
                .tag {{
                    display: inline-block;
                    padding: 2px 8px;
                    border-radius: 999px;
                    font-size: 0.7rem;
                    background-color: #111827;
                    color: #9ca3af;
                    border: 1px solid #374151;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin-top: 0.75rem;
                    background-color: #020617;
                    font-size: 0.85rem;
                }}
                th, td {{
                    border: 1px solid #1f2937;
                    padding: 6px 8px;
                    text-align: right;
                }}
                th:first-child, td:first-child {{
                    text-align: left;
                }}
                th {{
                    background: linear-gradient(to right, #111827, #020617);
                    color: #9ca3af;
                    font-weight: 500;
                }}
                tr:nth-child(even) td {{
                    background-color: #050816;
                }}
                tr:hover td {{
                    background-color: #0b1120;
                }}
                .symbol {{
                    color: #f9fafb;
                    font-weight: 500;
                }}
                .price {{
                    color: #4ade80;
                }}
                .move-up {{
                    color: #22c55e;
                }}
                .move-down {{
                    color: #f97373;
                }}
                .pill {{
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    font-size: 0.75rem;
                    color: #a5b4fc;
                }}
                .pill-dot {{
                    width: 6px;
                    height: 6px;
                    border-radius: 999px;
                    background-color: #22c55e;
                }}
                code {{
                    background-color: #111827;
                    padding: 2px 4px;
                    border-radius: 4px;
                    font-size: 0.8rem;
                    color: #e5e7eb;
                }}
            </style>
        </head>
        <body>
            <h1>Equities Trader Dashboard</h1>
            <p class="sub">
                Mock service to help me learn how prices, trades, P&amp;L and analytics work.
                Try changing <code>?min_qty=</code> in the URL (e.g. <code>/dashboard?min_qty=300</code>).
            </p>

            <div class="grid">
                <div class="panel">
                    <h2>
                        Market Prices
                        <span class="pill">
                            <span class="pill-dot"></span>
                            LIVE (mock)
                        </span>
                    </h2>
                    <div class="sub">Backed by the <code>/prices/&lt;symbol&gt;</code> API.</div>
                    <table>
                        <thead>
                            <tr>
                                <th>Symbol</th>
                                <th>Last Price</th>
                            </tr>
                        </thead>
                        <tbody>
                            {price_rows}
                        </tbody>
                    </table>
                </div>

                <div class="panel">
                    <h2>
                        Big Trades (qty ≥ {min_qty})
                        <span class="tag">/big-trades</span>
                    </h2>
                    <div class="sub">
                        Loaded from <code>trades.csv</code> and filtered with pandas.
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>Symbol</th>
                                <th>Quantity</th>
                                <th>Price</th>
                                <th>Notional</th>
                            </tr>
                        </thead>
                        <tbody>
                            {trade_rows}
                        </tbody>
                    </table>
                </div>

                <div class="panel panel-wide">
                    <h2>
                        Top Movers
                        <span class="tag">/screener</span>
                    </h2>
                    <div class="sub">
                        Ranked by percentage move vs previous price.
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>Symbol</th>
                                <th>Last Price</th>
                                <th>Change %</th>
                            </tr>
                        </thead>
                        <tbody>
                            {movers_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </body>
    </html>
    """
    return html





  