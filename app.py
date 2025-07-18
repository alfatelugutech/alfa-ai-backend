from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import json
import os
from datetime import datetime
import requests
import time
import random

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

# Mock market data - Replace with real API integration
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
    
    if base_price:
        base = base_price
    else:
        base = base_prices.get(symbol.upper(), 1000.0)
    
    # Add random variation (-2% to +2%)
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
        'source': 'Mock Data'
    }

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
            "Market data integration",
            "Professional API endpoints",
            "Stock search",
            "Market overview",
            "Top gainers"
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

@app.route('/api/market-overview')
def get_market_overview():
    try:
        market_data = {
            'NIFTY': get_mock_price('NIFTY', 19567.80),
            'BANKNIFTY': get_mock_price('BANKNIFTY', 45234.50),
            'SENSEX': get_mock_price('SENSEX', 65432.10)
        }
        
        # Determine market status based on time
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
def get_real_market_data(symbol):
    try:
        data = get_mock_price(symbol)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/market-data/<symbol>')
def get_market_data(symbol):
    try:
        data = get_mock_price(symbol)
        return jsonify({
            "symbol": data['symbol'],
            "price": data['current_price'],
            "change": data['change'],
            "change_percent": data['change_percent'],
            "timestamp": data['timestamp']
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stock-search/<query>')
def search_stocks(query):
    try:
        # Mock stock search results
        all_stocks = [
            {'symbol': 'RELIANCE', 'name': 'Reliance Industries Ltd'},
            {'symbol': 'TCS', 'name': 'Tata Consultancy Services'},
            {'symbol': 'HDFCBANK', 'name': 'HDFC Bank Ltd'},
            {'symbol': 'INFY', 'name': 'Infosys Ltd'},
            {'symbol': 'ICICIBANK', 'name': 'ICICI Bank Ltd'},
            {'symbol': 'SBIN', 'name': 'State Bank of India'},
            {'symbol': 'WIPRO', 'name': 'Wipro Ltd'},
            {'symbol': 'BHARTIARTL', 'name': 'Bharti Airtel Ltd'},
            {'symbol': 'LT', 'name': 'Larsen & Toubro Ltd'},
            {'symbol': 'MARUTI', 'name': 'Maruti Suzuki India Ltd'}
        ]
        
        # Filter stocks based on query
        filtered_stocks = [
            stock for stock in all_stocks 
            if query.upper() in stock['symbol'] or query.upper() in stock['name'].upper()
        ]
        
        # Add price data to results
        results = []
        for stock in filtered_stocks[:5]:  # Limit to 5 results
            price_data = get_mock_price(stock['symbol'])
            results.append({
                'symbol': stock['symbol'],
                'name': stock['name'],
                'price': price_data['current_price'],
                'change': price_data['change'],
                'change_percent': price_data['change_percent']
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
            data = get_mock_price(symbol)
            if data['change_percent'] > 0:
                gainers.append({
                    'symbol': symbol,
                    'price': data['current_price'],
                    'change': data['change'],
                    'change_percent': data['change_percent']
                })
        
        # Sort by change percentage
        gainers.sort(key=lambda x: x['change_percent'], reverse=True)
        
        return jsonify({
            "top_gainers": gainers[:6],
            "count": len(gainers[:6]),
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
    app.run(host='0.0.0.0', port=port, debug=False)
