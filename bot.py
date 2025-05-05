import os
import pandas as pd
from ta.trend import SMAIndicator
import oandapyV20
import oandapyV20.endpoints.instruments as instr
import oandapyV20.endpoints.orders as orders

# === ① OANDA-API-Zugang (als GitHub Secrets hinterlegen) ===
API_KEY    = os.getenv("OANDA_API_KEY")
ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
INSTRUMENT = "EUR_JPY"

client = oandapyV20.API(access_token=API_KEY)

# === ② PARAMETER (wie im Pine Script) ===
SMA_LENGTH    = 20    # smaLength
MIN_BARS_HELD = 15    # minBarsHeld (wird hier nicht implementiert, da GitHub Actions nur den aktuellen Signal-Status prüft)

def fetch_data():
    """Holt die letzten 500 1-Minuten-Kerzen und gibt sie als DataFrame zurück."""
    params = {"granularity": "M1", "count": 500}
    req = instr.InstrumentsCandles(instrument=INSTRUMENT, params=params)
    client.request(req)
    candles = req.response["candles"]
    data = [
        {
            "time":  c["time"],
            "high":  float(c["mid"]["h"]),
            "low":   float(c["mid"]["l"]),
            "close": float(c["mid"]["c"])
        }
        for c in candles
        if c["complete"]
    ]
    return pd.DataFrame(data)

def generate_signal(df):
    """Berechnet SMA High/Low und liefert  1 = SHORT-Entry, -1 = LONG-Entry, 0 = kein Signal."""
    # SMAs
    df["smaHigh"] = SMAIndicator(close=df["high"], window=SMA_LENGTH).sma_indicator()
    df["smaLow"]  = SMAIndicator(close=df["low"],  window=SMA_LENGTH).sma_indicator()

    # Entry-Bedingungen (getauscht wie gewünscht):
    # longCondition  = close > smaHigh and close > smaLow  → hier = SHORT-Entry (=1)
    # shortCondition = close < smaHigh and close < smaLow  → hier = LONG-Entry (=-1)
    df["signal"] = 0
    df.loc[
        (df["close"] > df["smaHigh"]) & (df["close"] > df["smaLow"]),
        "signal"
    ] = 1
    df.loc[
        (df["close"] < df["smaHigh"]) & (df["close"] < df["smaLow"]),
        "signal"
    ] = -1

    # Exit-Bedingungen – in diesem Einmal-Skript steuern wir über wechselndes Signal
    # (GitHub Actions läuft jede Minute, also schließt ein neuer entgegengesetzter Signal die Position)
    return int(df.iloc[-1]["signal"])

def send_order(units):
    """Platziert eine Market-Order."""
    body = {
        "order": {
            "instrument":   INSTRUMENT,
            "units":        str(units),
            "type":         "MARKET",
            "positionFill": "DEFAULT"
        }
    }
    req = orders.OrderCreate(accountID=ACCOUNT_ID, data=body)
    client.request(req)
    print(f"Order gesendet: {units}")

def main():
    df = fetch_data()
    sig = generate_signal(df)
    if sig ==  1:
        # Pine Script longCondition → hier SHORT-Entry
        send_order(-100)
    elif sig == -1:
        # Pine Script shortCondition → hier LONG-Entry
        send_order(100)
    else:
        print("Kein neues Signal")

if __name__ == "__main__":
    main()
