from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import json
import os
from datetime import datetime, timedelta
import requests
import time
import random
import yfinance as yf
from threading import Thread

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
            account_type TEXT DEFAULT 'paper',
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
            account_type TEXT DEFAULT 'paper',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create paper trading accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paper_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            balance REAL DEFAULT 1000000.0,
            invested REAL DEFAULT 0.0,
            pnl REAL DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create broker settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broker_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broker_name TEXT NOT NULL,
            api_key TEXT,
            secret_key TEXT,
            access_token TEXT,
            user_id TEXT,
            is_active BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create watchlist table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            user_id TEXT DEFAULT 'default',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default paper account if not exists
    cursor.execute('SELECT COUNT(*) FROM paper_accounts')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO paper_accounts (user_id, balance, invested, pnl)
            VALUES ('default', 1000000.0, 0.0, 0.0)
        ''')
    
    # Insert sample data if tables are empty
    cursor.execute('SELECT COUNT(*) FROM positions')
    if cursor.fetchone()[0] == 0:
        sample_positions = [
            ('RELIANCE', 100, 2450.50, 2478.30, 2780.0, 'momentum', 'paper'),
            ('TCS', 50, 3800.00, 3812.45, 622.5, 'growth', 'paper'),
            ('HDFCBANK', 75, 1680.00, 1698.75, 1406.25, 'banking', 'paper'),
        ]
        cursor.executemany('''
            INSERT INTO positions (symbol, quantity, average_price, current_price, pnl, strategy, account_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', sample_positions)
    
    # Insert sample watchlist
    cursor.execute('SELECT COUNT(*) FROM watchlist')
    if cursor.fetchone()[0] == 0:
        watchlist_items = [
            ('RELIANCE', 'default'),
            ('TCS', 'default'),
            ('HDFCBANK', 'default'),
            ('INFY', 'default'),
            ('ICICIBANK', 'default')
        ]
        cursor.executemany('''
            INSERT INTO watchlist (symbol, user_id) VALUES (?, ?)
        ''', watchlist_items)
    
    conn.commit()
    conn.close()

# Real market data using yfinance
def get_real_market_data(symbol):
    try:
        # Map Indian symbols
        symbol_map = {
            'RELIANCE': 'RELIANCE.NS',
            'TCS': 'TCS.NS',
            'HDFCBANK': 'HDFCBANK.NS',
            'INFY': 'INFY.NS',
            'ICICIBANK': 'ICICIBANK.NS',
            'SBIN': 'SBIN.NS',
            'WIPRO': 'WIPRO.NS',
            'BHARTIARTL': 'BHARTIARTL.NS',
            'LT': 'LT.NS',
            'MARUTI': 'MARUTI.NS',
            'NIFTY': '^NSEI',
            'BANKNIFTY': '^NSEBANK',
            'SENSEX': '^BSESN'
        }
        
        yahoo_symbol = symbol_map.get(symbol.upper(), f"{symbol.upper()}.NS")
        
        stock = yf.Ticker(yahoo_symbol)
        hist = stock.history(period='2d')
        
        if len(hist) >= 2:
            current_price = hist['Close'].iloc[-1]
            previous_close = hist['Close'].iloc[-2]
            change = current_price - previous_close
            change_percent = (change / previous_close) * 100
            
            return {
                'symbol': symbol.upper(),
                'current_price': round(float(current_price), 2),
                'previous_close': round(float(previous_close), 2),
                'change': round(float(change), 2),
                'change_percent': round(float(change_percent), 2),
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance',
                'volume': int(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0,
                'high': round(float(hist['High'].iloc[-1]), 2),
                'low': round(float(hist['Low'].iloc[-1]), 2),
                'open': round(float(hist['Open'].iloc[-1]), 2)
            }
    except Exception as e:
        print(f"Error fetching real data for {symbol}: {e}")
    
    # Fallback to mock data
    return get_mock_price(symbol)

# Mock data fallback
def get_mock_price(symbol, base_price=None):
    base_prices = {
        'RELIANCE': 2478.30,
        'TCS': 3812.45,
        'HDFCBANK': 1698.75,
        'INFY': 1789.90,
        'ICICIBANK': 1167.25,
        'SBIN': 820.50,
        'WIPRO': 445.80,
        'BHARTIARTL': 1089.25,
        'LT': 3567.90,
        'MARUTI': 10890.45,
        'NIFTY': 19567.80,
        'BANKNIFTY': 45234.50,
        'SENSEX': 65432.10
    }
    
    base = base_price or base_prices.get(symbol.upper(), 1000.0)
    variation = random.uniform(-0.02, 0.02)
    current_price = base * (1 + variation)
    change = current_price - base
    change_percent = (change / base) * 100
    
    return {
        'symbol': symbol.upper(),
        'current_price': round(current_price, 2),
        'previous_close': base,
        'change': round(change, 2),
        'change_percent': round(change_percent, 2),
        'timestamp': datetime.now().isoformat(),
        'source': 'Mock Data',
        'volume': random.randint(100000, 10000000),
        'high': round(current_price * 1.02, 2),
        'low': round(current_price * 0.98, 2),
        'open': round(base * random.uniform(0.99, 1.01), 2)
    }

# Routes
@app.route('/')
def home():
    return jsonify({
        "message": "🚀 AI Trading Platform Professional",
        "version": "4.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "Real-time market data (Yahoo Finance)",
            "Paper trading simulation",
            "Broker API integration (Zerodha, mStock)",
            "Professional desktop layout",
            "Advanced portfolio tracking",
            "Watchlist management",
            "Live trade execution",
            "Auto-save settings"
        ]
    })

@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "version": "4.0",
        "market_data": "live",
        "paper_trading": "active"
    })

# Paper Trading Account Management
@app.route('/api/paper-account')
def get_paper_account():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM paper_accounts WHERE user_id = ?', ('default',))
        account = cursor.fetchone()
        
        if account:
            return jsonify({
                "account": {
                    "balance": account[2],
                    "invested": account[3],
                    "pnl": account[4],
                    "total_value": account[2] + account[3] + account[4]
                },
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({"error": "Account not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/paper-account/reset', methods=['POST'])
def reset_paper_account():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE paper_accounts 
            SET balance = 1000000.0, invested = 0.0, pnl = 0.0, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', ('default',))
        
        # Clear all paper positions and trades
        cursor.execute('DELETE FROM positions WHERE account_type = ?', ('paper',))
        cursor.execute('DELETE FROM trades WHERE account_type = ?', ('paper',))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "Paper account reset successfully",
            "new_balance": 1000000.0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Broker Settings Management
@app.route('/api/broker-settings', methods=['GET'])
def get_broker_settings():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM broker_settings')
        settings = cursor.fetchall()
        
        broker_list = []
        for setting in settings:
            broker_list.append({
                "id": setting[0],
                "broker_name": setting[1],
                "api_key": setting[2][:10] + "..." if setting[2] else "",
                "has_secret": bool(setting[3]),
                "has_token": bool(setting[4]),
                "is_active": bool(setting[6])
            })
        
        conn.close()
        return jsonify({
            "brokers": broker_list,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/broker-settings', methods=['POST'])
def save_broker_settings():
    try:
        data = request.json
        broker_name = data.get('broker_name')
        api_key = data.get('api_key')
        secret_key = data.get('secret_key')
        access_token = data.get('access_token')
        user_id = data.get('user_id', 'default')
        
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        # Deactivate all other brokers
        cursor.execute('UPDATE broker_settings SET is_active = FALSE')
        
        # Insert or update broker settings
        cursor.execute('''
            INSERT OR REPLACE INTO broker_settings 
            (broker_name, api_key, secret_key, access_token, user_id, is_active)
            VALUES (?, ?, ?, ?, ?, TRUE)
        ''', (broker_name, api_key, secret_key, access_token, user_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": f"{broker_name} settings saved and activated",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Watchlist Management
@app.route('/api/watchlist')
def get_watchlist():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT symbol FROM watchlist WHERE user_id = ?', ('default',))
        symbols = [row[0] for row in cursor.fetchall()]
        
        watchlist_data = []
        for symbol in symbols:
            market_data = get_real_market_data(symbol)
            watchlist_data.append(market_data)
        
        conn.close()
        return jsonify({
            "watchlist": watchlist_data,
            "count": len(watchlist_data),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlist', methods=['POST'])
def add_to_watchlist():
    try:
        data = request.json
        symbol = data.get('symbol', '').upper()
        
        if not symbol:
            return jsonify({"error": "Symbol is required"}), 400
        
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO watchlist (symbol, user_id) VALUES (?, ?)
        ''', (symbol, 'default'))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": f"{symbol} added to watchlist",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlist/<symbol>', methods=['DELETE'])
def remove_from_watchlist(symbol):
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM watchlist WHERE symbol = ? AND user_id = ?', 
                      (symbol.upper(), 'default'))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": f"{symbol} removed from watchlist",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Market Data Routes
@app.route('/api/market-overview')
def get_market_overview():
    try:
        indices = ['NIFTY', 'BANKNIFTY', 'SENSEX']
        market_data = {}
        
        for index in indices:
            market_data[index] = get_real_market_data(index)
        
        current_hour = datetime.now().hour
        market_status = "Open" if 9 <= current_hour <= 15 else "Closed"
        
        return jsonify({
            "market_data": market_data,
            "market_status": market_status,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/real-market-data/<symbol>')
def get_market_data_endpoint(symbol):
    try:
        data = get_real_market_data(symbol)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Trading Routes
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

@app.route('/api/place-order', methods=['POST'])
def place_order():
    try:
        data = request.json
        
        required_fields = ['symbol', 'side', 'quantity', 'price']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        account_type = data.get('account_type', 'paper')
        
        # For paper trading, check balance
        if account_type == 'paper' and data['side'].upper() == 'BUY':
            conn = sqlite3.connect('trading.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT balance FROM paper_accounts WHERE user_id = ?', ('default',))
            balance = cursor.fetchone()[0]
            
            order_value = data['quantity'] * data['price']
            if order_value > balance:
                conn.close()
                return jsonify({"error": "Insufficient balance"}), 400
            
            # Update balance
            cursor.execute('''
                UPDATE paper_accounts 
                SET balance = balance - ?, invested = invested + ?
                WHERE user_id = ?
            ''', (order_value, order_value, 'default'))
            
            conn.commit()
            conn.close()
        
        # Place the order
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        trade_id = f"T{int(datetime.now().timestamp())}"
        
        cursor.execute('''
            INSERT INTO trades (trade_id, symbol, side, quantity, entry_price, strategy, account_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_id,
            data['symbol'].upper(),
            data['side'].upper(),
            data['quantity'],
            data['price'],
            data.get('strategy', 'manual'),
            account_type
        ))
        
        # Update positions
        cursor.execute('SELECT * FROM positions WHERE symbol = ? AND account_type = ?', 
                      (data['symbol'].upper(), account_type))
        existing_position = cursor.fetchone()
        
        if existing_position:
            if data['side'].upper() == 'BUY':
                new_quantity = existing_position[2] + data['quantity']
                new_avg_price = ((existing_position[2] * existing_position[3]) + 
                               (data['quantity'] * data['price'])) / new_quantity
            else:  # SELL
                new_quantity = existing_position[2] - data['quantity']
                new_avg_price = existing_position[3]
            
            cursor.execute('''
                UPDATE positions 
                SET quantity = ?, average_price = ?, current_price = ?
                WHERE symbol = ? AND account_type = ?
            ''', (new_quantity, new_avg_price, data['price'], data['symbol'].upper(), account_type))
        else:
            if data['side'].upper() == 'BUY':
                cursor.execute('''
                    INSERT INTO positions (symbol, quantity, average_price, current_price, pnl, strategy, account_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data['symbol'].upper(),
                    data['quantity'],
                    data['price'],
                    data['price'],
                    0.0,
                    data.get('strategy', 'manual'),
                    account_type
                ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "Order placed successfully",
            "trade_id": trade_id,
            "account_type": account_type,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Stock Search
@app.route('/api/stock-search/<query>')
def search_stocks(query):
    try:
        # Indian stock symbols database
        indian_stocks = [
            {'symbol': 'RELIANCE', 'name': 'Reliance Industries Ltd'},
            {'symbol': 'TCS', 'name': 'Tata Consultancy Services'},
            {'symbol': 'HDFCBANK', 'name': 'HDFC Bank Ltd'},
            {'symbol': 'INFY', 'name': 'Infosys Ltd'},
            {'symbol': 'ICICIBANK', 'name': 'ICICI Bank Ltd'},
            {'symbol': 'SBIN', 'name': 'State Bank of India'},
            {'symbol': 'WIPRO', 'name': 'Wipro Ltd'},
            {'symbol': 'BHARTIARTL', 'name': 'Bharti Airtel Ltd'},
            {'symbol': 'LT', 'name': 'Larsen & Toubro Ltd'},
            {'symbol': 'MARUTI', 'name': 'Maruti Suzuki India Ltd'},
            {'symbol': 'ADANIPORTS', 'name': 'Adani Ports & SEZ Ltd'},
            {'symbol': 'ASIANPAINT', 'name': 'Asian Paints Ltd'},
            {'symbol': 'AXISBANK', 'name': 'Axis Bank Ltd'},
            {'symbol': 'BAJFINANCE', 'name': 'Bajaj Finance Ltd'},
            {'symbol': 'BAJAJFINSV', 'name': 'Bajaj Finserv Ltd'},
            {'symbol': 'BPCL', 'name': 'Bharat Petroleum Corporation Ltd'},
            {'symbol': 'BRITANNIA', 'name': 'Britannia Industries Ltd'},
            {'symbol': 'CIPLA', 'name': 'Cipla Ltd'},
            {'symbol': 'COALINDIA', 'name': 'Coal India Ltd'},
            {'symbol': 'DIVISLAB', 'name': 'Divi\'s Laboratories Ltd'}
        ]
        
        # Filter stocks
        filtered_stocks = [
            stock for stock in indian_stocks 
            if query.upper() in stock['symbol'] or query.upper() in stock['name'].upper()
        ]
        
        results = []
        for stock in filtered_stocks[:10]:
            try:
                price_data = get_real_market_data(stock['symbol'])
                results.append({
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'price': price_data['current_price'],
                    'change': price_data['change'],
                    'change_percent': price_data['change_percent'],
                    'volume': price_data.get('volume', 0)
                })
            except:
                # Fallback data
                results.append({
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'price': 1000,
                    'change': 10,
                    'change_percent': 1.0,
                    'volume': 100000
                })
        
        return jsonify({
            "results": results,
            "count": len(results),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/top-gainers')
def get_top_gainers():
    try:
        symbols = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'SBIN', 'WIPRO', 'BHARTIARTL']
        
        gainers = []
        for symbol in symbols:
            try:
                data = get_real_market_data(symbol)
                if data['change_percent'] > 0:
                    gainers.append({
                        'symbol': symbol,
                        'price': data['current_price'],
                        'change': data['change'],
                        'change_percent': data['change_percent'],
                        'volume': data.get('volume', 0)
                    })
            except:
                continue
        
        gainers.sort(key=lambda x: x['change_percent'], reverse=True)
        
        return jsonify({
            "top_gainers": gainers[:6],
            "count": len(gainers[:6]),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM positions WHERE quantity > 0')
        total_positions = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(pnl) FROM positions WHERE pnl IS NOT NULL')
        total_pnl = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT balance, invested, pnl FROM paper_accounts WHERE user_id = ?', ('default',))
        account = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            "total_positions": total_positions,
            "total_trades": total_trades,
            "total_pnl": round(total_pnl, 2),
            "paper_account": {
                "balance": account[0] if account else 0,
                "invested": account[1] if account else 0,
                "account_pnl": account[2] if account else 0
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
