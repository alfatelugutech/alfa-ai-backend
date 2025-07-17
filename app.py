from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os
import time
from datetime import datetime

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
    
    # Insert sample data if empty
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
        "version": "2.1",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "version": "2.1"
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
        # Simulate market data
        base_prices = {
            'RELIANCE': 2478.30,
            'TCS': 3812.45,
            'HDFCBANK': 1698.75,
            'INFY': 1789.90,
            'ICICIBANK': 1167.25
        }
        
        base_price = base_prices.get(symbol.upper(), 1000.0)
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

# This is crucial for Render deployment
if __name__ == '__main__':
    print("🚀 Starting AI Trading Platform API...")
    init_db()
    print("✅ Database initialized")
    
    # Get port from environment variable (Render sets this)
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Starting server on port {port}")
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=False)
