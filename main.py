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

TRADES_DF = pd.read_csv("trades.csv")


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

@app.get("/big-trades")
def big_trades(min_qty: int = 100):
    #return trades where quantity >+ min_qty
    #simulates basic analytics api used in equities platforms.

    filtered = TRADES_DF[TRADES_DF["qty"]>= min_qty]
    return filtered.to_dict(orient="records")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(min_qty: int = 100):
    # Build a small 'trader-style' dashboard:
    # - current prices table
    # - big trades table (qty >= min_qty)

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

  