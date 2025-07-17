from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import json
import os
from datetime import datetime
import requests
import time
import yfinance as yf
import pandas as pd

app = Flask(__name__)
CORS(app)

# Database initialization
def init_db():
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    # Create positions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            average_price REAL NOT NULL,
            current_price REAL,
            pnl REAL,
            strategy TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            pnl REAL,
            strategy TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert sample data
    cursor.execute('SELECT COUNT(*) FROM positions')
    if cursor.fetchone()[0] == 0:
        sample_positions = [
            ('RELIANCE', 100, 2450.50, 2478.30, 2780.0, 'momentum'),
            ('TCS', 50, 3800.00, 3812.45, 622.5, 'growth'),
            ('HDFCBANK', 75, 1680.00, 1698.75, 1406.25, 'banking'),
        ]
        cursor.executemany('''
            INSERT INTO positions (symbol, quantity, average_price, current_price, pnl, strategy)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_positions)
    
    cursor.execute('SELECT COUNT(*) FROM trades')
    if cursor.fetchone()[0] == 0:
        sample_trades = [
            (f'T{int(time.time())}', 'RELIANCE', 'BUY', 100, 2450.50, 'momentum'),
            (f'T{int(time.time())+1}', 'TCS', 'BUY', 50, 3800.00, 'growth'),
            (f'T{int(time.time())+2}', 'HDFCBANK', 'BUY', 75, 1680.00, 'banking'),
        ]
        cursor.executemany('''
            INSERT INTO trades (trade_id, symbol, side, quantity, entry_price, strategy)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_trades)
    
    conn.commit()
    conn.close()

# Routes
@app.route('/')
def home():
    return jsonify({
        "message": "🚀 AI Trading Platform API",
        "version": "3.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "Live positions tracking",
            "Real-time trade management",
            "Real market data (Yahoo Finance)",
            "Live stock prices",
            "Market overview (NIFTY, BANK NIFTY, SENSEX)",
            "Stock search with live data",
            "Top gainers tracking",
            "Professional API endpoints"
        ]
    })

@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "version": "3.0"
    })

@app.route('/api/positions')
def get_positions():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM positions ORDER BY timestamp DESC')
        positions = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            "positions": positions,
            "count": len(positions),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/trades')
def get_trades():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM trades ORDER BY timestamp DESC LIMIT 100')
        trades = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            "trades": trades,
            "count": len(trades),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/market-data/<symbol>')
def get_market_data(symbol):
    try:
        # Simulate market data (replace with real API later)
        base_prices = {
            'RELIANCE': 2478.30,
            'TCS': 3812.45,
            'HDFCBANK': 1698.75,
            'INFY': 1789.90,
            'ICICIBANK': 1167.25
        }
        
        base_price = base_prices.get(symbol.upper(), 1000.0)
        # Add small random variation
        import random
        current_price = base_price + random.uniform(-50, 50)
        change = current_price - base_price
        
        return jsonify({
            "symbol": symbol.upper(),
            "price": round(current_price, 2),
            "change": round(change, 2),
            "change_percent": round((change / base_price) * 100, 2),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# NEW: Real Market Data Routes
@app.route('/api/real-market-data/<symbol>')
def get_real_market_data(symbol):
    try:
        # Get data from Yahoo Finance (free, no API key needed)
        ticker = yf.Ticker(f"{symbol}.NS")  # NSE stocks
        
        # Get current price
        info = ticker.info
        current_price = info.get('currentPrice', 0)
        previous_close = info.get('previousClose', 0)
        
        # If no current price, try to get from history
        if current_price == 0:
            hist = ticker.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                previous_close = hist['Open'].iloc[-1]
        
        # Calculate change
        change = current_price - previous_close
        change_percent = (change / previous_close) * 100 if previous_close else 0
        
        # Get additional data
        volume = info.get('volume', 0)
        market_cap = info.get('marketCap', 0)
        
        return jsonify({
            "symbol": symbol.upper(),
            "current_price": round(current_price, 2),
            "previous_close": round(previous_close, 2),
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "volume": volume,
            "market_cap": market_cap,
            "timestamp": datetime.now().isoformat(),
            "source": "Yahoo Finance"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/market-overview')
def get_market_overview():
    try:
        # Get data for major indices
        market_data = {}
        
        # NIFTY 50
        try:
            nifty = yf.Ticker("^NSEI")
            nifty_info = nifty.info
            nifty_price = nifty_info.get('currentPrice', 0)
            nifty_previous = nifty_info.get('previousClose', 0)
            
            # If no current price, try to get from history
            if nifty_price == 0:
                hist = nifty.history(period="1d")
                if not hist.empty:
                    nifty_price = hist['Close'].iloc[-1]
                    nifty_previous = hist['Open'].iloc[-1]
            
            nifty_change = nifty_price - nifty_previous
            nifty_change_percent = (nifty_change / nifty_previous) * 100 if nifty_previous else 0
            
            market_data['NIFTY'] = {
                "price": round(nifty_price, 2),
                "change": round(nifty_change, 2),
                "change_percent": round(nifty_change_percent, 2)
            }
        except:
            market_data['NIFTY'] = {"price": 19500, "change": 125.50, "change_percent": 0.64}
        
        # BANK NIFTY
        try:
            banknifty = yf.Ticker("^NSEBANK")
            bank_info = banknifty.info
            bank_price = bank_info.get('currentPrice', 0)
            bank_previous = bank_info.get('previousClose', 0)
            
            # If no current price, try to get from history
            if bank_price == 0:
                hist = banknifty.history(period="1d")
                if not hist.empty:
                    bank_price = hist['Close'].iloc[-1]
                    bank_previous = hist['Open'].iloc[-1]
            
            bank_change = bank_price - bank_previous
            bank_change_percent = (bank_change / bank_previous) * 100 if bank_previous else 0
            
            market_data['BANKNIFTY'] = {
                "price": round(bank_price, 2),
                "change": round(bank_change, 2),
                "change_percent": round(bank_change_percent, 2)
            }
        except:
            market_data['BANKNIFTY'] = {"price": 45000, "change": 200.30, "change_percent": 0.45}
        
        # SENSEX
        try:
            sensex = yf.Ticker("^BSESN")
            sensex_info = sensex.info
            sensex_price = sensex_info.get('currentPrice', 0)
            sensex_previous = sensex_info.get('previousClose', 0)
            
            # If no current price, try to get from history
            if sensex_price == 0:
                hist = sensex.history(period="1d")
                if not hist.empty:
                    sensex_price = hist['Close'].iloc[-1]
                    sensex_previous = hist['Open'].iloc[-1]
            
            sensex_change = sensex_price - sensex_previous
            sensex_change_percent = (sensex_change / sensex_previous) * 100 if sensex_previous else 0
            
            market_data['SENSEX'] = {
                "price": round(sensex_price, 2),
                "change": round(sensex_change, 2),
                "change_percent": round(sensex_change_percent, 2)
            }
        except:
            market_data['SENSEX'] = {"price": 65000, "change": 180.75, "change_percent": 0.28}
        
        return jsonify({
            "market_data": market_data,
            "timestamp": datetime.now().isoformat(),
            "market_status": "Open" if 9 <= datetime.now().hour < 16 else "Closed"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/top-gainers')
def get_top_gainers():
    try:
        # Popular Indian stocks
        stocks = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'KOTAKBANK', 'SBIN', 'BHARTIARTL', 'ITC', 'ASIANPAINT']
        gainers = []
        
        for stock in stocks:
            try:
                ticker = yf.Ticker(f"{stock}.NS")
                info = ticker.info
                current_price = info.get('currentPrice', 0)
                previous_close = info.get('previousClose', 0)
                
                # If no current price, try to get from history
                if current_price == 0:
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        previous_close = hist['Open'].iloc[-1]
                
                if current_price > 0 and previous_close > 0:
                    change_percent = ((current_price - previous_close) / previous_close) * 100
                    
                    gainers.append({
                        "symbol": stock,
                        "price": round(current_price, 2),
                        "change_percent": round(change_percent, 2)
                    })
            except:
                # Skip if data not available
                continue
        
        # Sort by change percent (descending)
        gainers.sort(key=lambda x: x['change_percent'], reverse=True)
        
        return jsonify({
            "top_gainers": gainers[:10],
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stock-search/<query>')
def search_stocks(query):
    try:
        # Simple stock search
        indian_stocks = {
            'RELIANCE': 'Reliance Industries Ltd',
            'TCS': 'Tata Consultancy Services',
            'HDFCBANK': 'HDFC Bank Ltd',
            'INFY': 'Infosys Ltd',
            'ICICIBANK': 'ICICI Bank Ltd',
            'KOTAKBANK': 'Kotak Mahindra Bank',
            'HINDUNILVR': 'Hindustan Unilever Ltd',
            'SBIN': 'State Bank of India',
            'BHARTIARTL': 'Bharti Airtel Ltd',
            'ITC': 'ITC Ltd',
            'ASIANPAINT': 'Asian Paints Ltd',
            'MARUTI': 'Maruti Suzuki India Ltd',
            'BAJFINANCE': 'Bajaj Finance Ltd',
            'AXISBANK': 'Axis Bank Ltd',
            'LT': 'Larsen & Toubro Ltd',
            'WIPRO': 'Wipro Ltd',
            'ULTRACEMCO': 'UltraTech Cement Ltd',
            'TITAN': 'Titan Company Ltd',
            'POWERGRID': 'Power Grid Corporation',
            'NTPC': 'NTPC Ltd'
        }
        
        results = []
        query_upper = query.upper()
        
        for symbol, name in indian_stocks.items():
            if query_upper in symbol or query_upper in name.upper():
                try:
                    ticker = yf.Ticker(f"{symbol}.NS")
                    info = ticker.info
                    current_price = info.get('currentPrice', 0)
                    previous_close = info.get('previousClose', 0)
                    
                    # If no current price, try to get from history
                    if current_price == 0:
                        hist = ticker.history(period="1d")
                        if not hist.empty:
                            current_price = hist['Close'].iloc[-1]
                            previous_close = hist['Open'].iloc[-1]
                    
                    if current_price > 0 and previous_close > 0:
                        change_percent = ((current_price - previous_close) / previous_close) * 100
                        
                        results.append({
                            "symbol": symbol,
                            "name": name,
                            "price": round(current_price, 2),
                            "change_percent": round(change_percent, 2)
                        })
                    else:
                        results.append({
                            "symbol": symbol,
                            "name": name,
                            "price": 1000,
                            "change_percent": 0.5
                        })
                except:
                    results.append({
                        "symbol": symbol,
                        "name": name,
                        "price": 1000,
                        "change_percent": 0.5
                    })
        
        return jsonify({
            "results": results,
            "query": query,
            "count": len(results),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/historical-data/<symbol>')
def get_historical_data(symbol):
    try:
        # Get historical data from Yahoo Finance
        ticker = yf.Ticker(f"{symbol}.NS")
        
        # Get last 30 days of data
        hist = ticker.history(period="30d")
        
        # Convert to list of dictionaries
        data = []
        for date, row in hist.iterrows():
            data.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(row['Open'], 2),
                "high": round(row['High'], 2),
                "low": round(row['Low'], 2),
                "close": round(row['Close'], 2),
                "volume": int(row['Volume'])
            })
        
        return jsonify({
            "symbol": symbol.upper(),
            "data": data,
            "count": len(data),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/place-order', methods=['POST'])
def place_order():
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['symbol', 'side', 'quantity', 'price']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        # Generate trade ID
        trade_id = f"T{int(datetime.now().timestamp())}"
        
        # Insert trade
        cursor.execute('''
            INSERT INTO trades (trade_id, symbol, side, quantity, entry_price, strategy)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            trade_id,
            data['symbol'].upper(),
            data['side'].upper(),
            data['quantity'],
            data['price'],
            data.get('strategy', 'manual')
        ))
        
        # Update positions (simplified logic)
        cursor.execute('SELECT * FROM positions WHERE symbol = ?', (data['symbol'].upper(),))
        existing_position = cursor.fetchone()
        
        if existing_position:
            # Update existing position
            if data['side'].upper() == 'BUY':
                new_quantity = existing_position[2] + data['quantity']
                new_avg_price = ((existing_position[2] * existing_position[3]) + (data['quantity'] * data['price'])) / new_quantity
            else:  # SELL
                new_quantity = existing_position[2] - data['quantity']
                new_avg_price = existing_position[3]  # Keep same average price
            
            cursor.execute('''
                UPDATE positions 
                SET quantity = ?, average_price = ?, current_price = ?
                WHERE symbol = ?
            ''', (new_quantity, new_avg_price, data['price'], data['symbol'].upper()))
        else:
            # Create new position
            if data['side'].upper() == 'BUY':
                cursor.execute('''
                    INSERT INTO positions (symbol, quantity, average_price, current_price, pnl, strategy)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    data['symbol'].upper(),
                    data['quantity'],
                    data['price'],
                    data['price'],
                    0.0,
                    data.get('strategy', 'manual')
                ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "Order placed successfully",
            "trade_id": trade_id,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        # Get total positions
        cursor.execute('SELECT COUNT(*) FROM positions WHERE quantity > 0')
        total_positions = cursor.fetchone()[0]
        
        # Get total trades
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        
        # Get total PnL
        cursor.execute('SELECT SUM(pnl) FROM positions WHERE pnl IS NOT NULL')
        total_pnl = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            "total_positions": total_positions,
            "total_trades": total_trades,
            "total_pnl": round(total_pnl, 2),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 10000))
    print(f"🚀 Starting AI Trading Platform API v3.0 on port {port}")
    print("✅ Features: Real market data, Live prices, Market overview, Stock search")
    app.run(host='0.0.0.0', port=port, debug=False)
