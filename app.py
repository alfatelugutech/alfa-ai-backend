from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import json
import os
from datetime import datetime, timedelta
import requests
import time
import random
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["*"])

# Global AI trading state
AI_TRADING_ACTIVE = False
AI_TRADING_THREAD = None

# Database initialization
def init_db():
    try:
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
        
        # Create enhanced paper trading accounts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default',
                balance REAL DEFAULT 1000000.0,
                invested REAL DEFAULT 0.0,
                pnl REAL DEFAULT 0.0,
                initial_capital REAL DEFAULT 1000000.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create AI trading settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_trading_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default',
                is_active BOOLEAN DEFAULT FALSE,
                trading_mode TEXT DEFAULT 'paper',
                max_capital_per_trade REAL DEFAULT 10000.0,
                max_daily_trades INTEGER DEFAULT 10,
                risk_level TEXT DEFAULT 'medium',
                auto_stop_loss REAL DEFAULT 5.0,
                auto_take_profit REAL DEFAULT 10.0,
                trading_frequency INTEGER DEFAULT 30,
                allowed_symbols TEXT DEFAULT 'RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create AI trading logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_trading_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                action TEXT NOT NULL,
                symbol TEXT,
                signal_type TEXT,
                confidence REAL,
                price REAL,
                quantity INTEGER,
                reason TEXT,
                status TEXT
            )
        ''')
        
        # Create real trading accounts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS real_trading_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default',
                available_capital REAL DEFAULT 0.0,
                allocated_for_ai REAL DEFAULT 0.0,
                daily_limit REAL DEFAULT 5000.0,
                max_position_size REAL DEFAULT 50000.0,
                is_active BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
        
        # Insert default accounts if not exist
        cursor.execute('SELECT COUNT(*) FROM paper_accounts')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO paper_accounts (user_id, balance, invested, pnl, initial_capital)
                VALUES ('default', 1000000.0, 0.0, 0.0, 1000000.0)
            ''')
        
        cursor.execute('SELECT COUNT(*) FROM ai_trading_settings')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO ai_trading_settings (user_id) VALUES ('default')
            ''')
        
        cursor.execute('SELECT COUNT(*) FROM real_trading_accounts')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO real_trading_accounts (user_id) VALUES ('default')
            ''')
        
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
        logger.info("✅ Database initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

# Enhanced mock data (no external dependencies)
def get_enhanced_mock_price(symbol):
    """Enhanced mock data with realistic intraday variations"""
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
    
    base = base_prices.get(symbol.upper(), 1000.0)
    
    # More realistic price movements
    hour = datetime.now().hour
    if 9 <= hour <= 15:  # Market hours - more volatility
        variation = random.uniform(-0.03, 0.03)
    else:  # After hours - less movement
        variation = random.uniform(-0.005, 0.005)
    
    current_price = base * (1 + variation)
    previous_close = base
    change = current_price - previous_close
    change_percent = (change / previous_close) * 100
    
    return {
        'symbol': symbol.upper(),
        'current_price': round(current_price, 2),
        'previous_close': round(previous_close, 2),
        'change': round(change, 2),
        'change_percent': round(change_percent, 2),
        'timestamp': datetime.now().isoformat(),
        'source': 'Enhanced Mock Data (Deployment Mode)',
        'volume': random.randint(100000, 10000000),
        'high': round(current_price * random.uniform(1.005, 1.025), 2),
        'low': round(current_price * random.uniform(0.975, 0.995), 2),
        'open': round(previous_close * random.uniform(0.995, 1.005), 2)
    }

# AI Trading Engine
def generate_ai_signal(symbol):
    """Generate AI trading signals based on technical analysis"""
    try:
        # Get market data
        market_data = get_enhanced_mock_price(symbol)
        current_price = market_data['current_price']
        change_percent = market_data['change_percent']
        
        # Simple AI logic
        signal_strength = 0
        reasons = []
        
        # Price momentum analysis
        if change_percent > 2:
            signal_strength += 30
            reasons.append("Strong upward momentum")
        elif change_percent > 1:
            signal_strength += 15
            reasons.append("Positive momentum")
        elif change_percent < -2:
            signal_strength -= 30
            reasons.append("Strong downward momentum")
        elif change_percent < -1:
            signal_strength -= 15
            reasons.append("Negative momentum")
        
        # Volume analysis (mock)
        volume_factor = random.uniform(0.8, 1.2)
        if volume_factor > 1.1:
            signal_strength += 10
            reasons.append("High volume")
        
        # Market time consideration
        hour = datetime.now().hour
        if 10 <= hour <= 14:  # Active trading hours
            signal_strength += 5
            reasons.append("Active market hours")
        
        # Risk management
        if abs(change_percent) > 5:
            signal_strength *= 0.5
            reasons.append("High volatility - reduced confidence")
        
        # Determine signal type
        if signal_strength > 25:
            signal_type = 'BUY'
            confidence = min(95, 60 + signal_strength)
        elif signal_strength < -25:
            signal_type = 'SELL'
            confidence = min(95, 60 + abs(signal_strength))
        else:
            signal_type = 'HOLD'
            confidence = 50 + abs(signal_strength)
        
        return {
            'symbol': symbol,
            'signal': signal_type,
            'confidence': round(confidence, 1),
            'current_price': current_price,
            'reasons': reasons,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating AI signal for {symbol}: {e}")
        return None

def execute_ai_trade(signal, settings):
    """Execute trade based on AI signal"""
    try:
        if signal['confidence'] < 70:
            return False, "Low confidence signal"
        
        symbol = signal['symbol']
        signal_type = signal['signal']
        current_price = signal['current_price']
        
        # Calculate quantity based on settings
        max_trade_value = settings[4]  # max_capital_per_trade
        quantity = int(max_trade_value / current_price)
        
        if quantity <= 0:
            return False, "Insufficient capital for trade"
        
        # Check account balance
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        if settings[3] == 'paper':  # trading_mode
            cursor.execute('SELECT balance FROM paper_accounts WHERE user_id = ?', ('default',))
            result = cursor.fetchone()
            balance = result[0] if result else 0
        else:
            cursor.execute('SELECT available_capital FROM real_trading_accounts WHERE user_id = ?', ('default',))
            result = cursor.fetchone()
            balance = result[0] if result else 0
        
        trade_value = quantity * current_price
        
        if trade_value > balance:
            conn.close()
            return False, "Insufficient balance"
        
        # Place the trade
        trade_id = f"AI_{int(datetime.now().timestamp())}"
        
        cursor.execute('''
            INSERT INTO trades (trade_id, symbol, side, quantity, entry_price, strategy, account_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (trade_id, symbol, signal_type, quantity, current_price, 'AI_AUTO', settings[3]))
        
        # Update account balance
        if settings[3] == 'paper':
            cursor.execute('''
                UPDATE paper_accounts 
                SET balance = balance - ?, invested = invested + ?
                WHERE user_id = ?
            ''', (trade_value, trade_value, 'default'))
        
        # Log AI action
        cursor.execute('''
            INSERT INTO ai_trading_logs (action, symbol, signal_type, confidence, price, quantity, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('TRADE_EXECUTED', symbol, signal_type, signal['confidence'], current_price, quantity, 
              ', '.join(signal['reasons']), 'SUCCESS'))
        
        conn.commit()
        conn.close()
        
        return True, f"AI trade executed: {signal_type} {quantity} {symbol} at ₹{current_price}"
        
    except Exception as e:
        logger.error(f"Error executing AI trade: {e}")
        return False, str(e)

def ai_trading_worker():
    """Background worker for AI trading"""
    global AI_TRADING_ACTIVE
    
    while AI_TRADING_ACTIVE:
        try:
            # Get AI trading settings
            conn = sqlite3.connect('trading.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM ai_trading_settings WHERE user_id = ? AND is_active = TRUE', ('default',))
            settings = cursor.fetchone()
            
            if not settings:
                conn.close()
                time.sleep(60)
                continue
            
            # Check daily trade limit
            today = datetime.now().date()
            cursor.execute('''
                SELECT COUNT(*) FROM trades 
                WHERE account_type = ? AND strategy = 'AI_AUTO' 
                AND DATE(timestamp) = ?
            ''', (settings[3], today))
            
            daily_trades = cursor.fetchone()[0]
            max_daily_trades = settings[5]
            
            if daily_trades >= max_daily_trades:
                conn.close()
                logger.info(f"Daily trade limit reached: {daily_trades}/{max_daily_trades}")
                time.sleep(3600)  # Wait 1 hour
                continue
            
            conn.close()
            
            # Get allowed symbols
            allowed_symbols = settings[10].split(',') if settings[10] else ['RELIANCE', 'TCS', 'HDFCBANK']
            
            # Generate signals for each symbol
            for symbol in allowed_symbols:
                if not AI_TRADING_ACTIVE:
                    break
                
                signal = generate_ai_signal(symbol.strip())
                if signal and signal['signal'] in ['BUY', 'SELL']:
                    success, message = execute_ai_trade(signal, settings)
                    logger.info(f"AI Trading: {message}")
                    
                    if success:
                        time.sleep(5)  # Brief pause between trades
            
            # Wait for next trading cycle
            trading_frequency = settings[9] if settings[9] else 30
            time.sleep(trading_frequency)
            
        except Exception as e:
            logger.error(f"Error in AI trading worker: {e}")
            time.sleep(60)

# Routes
@app.route('/')
def home():
    return jsonify({
        "message": "🚀 AI Trading Platform Professional",
        "version": "7.0 - Deployment Ready",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "mode": "Mock Data (Deployment Optimized)",
        "ai_trading_status": "Active" if AI_TRADING_ACTIVE else "Inactive",
        "features": [
            "🤖 Automated AI Trading System",
            "💰 Paper Trading Mode", 
            "📊 Mock Market Data",
            "⚙️ Risk Management Controls",
            "📈 Portfolio Analytics",
            "🎯 AI Signal Generation"
        ]
    })

@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "version": "7.0",
        "market_data": "mock",
        "ai_trading": "active" if AI_TRADING_ACTIVE else "inactive",
        "paper_trading": "active",
        "deployment": "optimized"
    })

# Paper Trading Account Management
@app.route('/api/paper-account')
def get_paper_account():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM paper_accounts WHERE user_id = ?', ('default',))
        account = cursor.fetchone()
        conn.close()
        
        if account:
            return jsonify({
                "account": {
                    "balance": account[2],
                    "invested": account[3],
                    "pnl": account[4],
                    "initial_capital": account[5],
                    "total_value": account[2] + account[3] + account[4]
                },
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({"error": "Account not found"}), 404
            
    except Exception as e:
        logger.error(f"Error getting paper account: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/paper-account/reset', methods=['POST'])
def reset_paper_account():
    try:
        data = request.json or {}
        new_capital = data.get('capital', 1000000.0)
        
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE paper_accounts 
            SET balance = ?, invested = 0.0, pnl = 0.0, initial_capital = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (new_capital, new_capital, 'default'))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "Paper account reset successfully",
            "new_balance": new_capital
        })
    except Exception as e:
        logger.error(f"Error resetting paper account: {e}")
        return jsonify({"error": str(e)}), 500

# AI Trading Management
@app.route('/api/ai-trading/settings', methods=['GET'])
def get_ai_settings():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM ai_trading_settings WHERE user_id = ?', ('default',))
        settings = cursor.fetchone()
        conn.close()
        
        if settings:
            return jsonify({
                "settings": {
                    "is_active": bool(settings[2]),
                    "trading_mode": settings[3],
                    "max_capital_per_trade": settings[4],
                    "max_daily_trades": settings[5],
                    "risk_level": settings[6],
                    "auto_stop_loss": settings[7],
                    "auto_take_profit": settings[8],
                    "trading_frequency": settings[9],
                    "allowed_symbols": settings[10].split(',') if settings[10] else []
                },
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({"error": "Settings not found"}), 404
            
    except Exception as e:
        logger.error(f"Error getting AI settings: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai-trading/start', methods=['POST'])
def start_ai_trading():
    global AI_TRADING_ACTIVE, AI_TRADING_THREAD
    
    try:
        if AI_TRADING_ACTIVE:
            return jsonify({"error": "AI trading is already active"}), 400
        
        # Update settings to active
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE ai_trading_settings 
            SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', ('default',))
        
        conn.commit()
        conn.close()
        
        # Start AI trading thread
        AI_TRADING_ACTIVE = True
        AI_TRADING_THREAD = threading.Thread(target=ai_trading_worker, daemon=True)
        AI_TRADING_THREAD.start()
        
        return jsonify({
            "status": "success",
            "message": "🤖 AI Trading started successfully!",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error starting AI trading: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai-trading/stop', methods=['POST'])
def stop_ai_trading():
    global AI_TRADING_ACTIVE
    
    try:
        AI_TRADING_ACTIVE = False
        
        # Update settings to inactive
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE ai_trading_settings 
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', ('default',))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "🛑 AI Trading stopped successfully!",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error stopping AI trading: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/market-overview')
def get_market_overview():
    try:
        import yfinance as yf
        indices = ['NIFTY', 'BANKNIFTY', 'SENSEX']
        index_map = {
            'NIFTY': '^NSEI',
            'BANKNIFTY': '^NSEBANK',
            'SENSEX': '^BSESN'
        }

        market_data = {}
        for index in indices:
            try:
                ticker = yf.Ticker(index_map[index])
                data = ticker.history(period="2d")
                if not data.empty:
                    current_price = float(data["Close"].iloc[-1])
                    previous_close = float(data["Close"].iloc[-2])
                    change = round(current_price - previous_close, 2)
                    change_percent = round((change / previous_close) * 100, 2)
                    market_data[index] = {
                        'symbol': index,
                        'current_price': current_price,
                        'previous_close': previous_close,
                        'change': change,
                        'change_percent': change_percent,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'Yahoo Finance'
                    }
                else:
                    market_data[index] = {"error": "No data"}
            except Exception as e:
                market_data[index] = {"error": str(e)}

        current_hour = datetime.now().hour
        market_status = "Open" if 9 <= current_hour <= 15 else "Closed"

        return jsonify({
            "market_data": market_data,
            "market_status": market_status,
            "data_source": "Yahoo Finance",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting market overview: {e}")
        return jsonify({"error": str(e)}), 500)
    except Exception as e:
        logger.error(f"Error getting market overview: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/real-market-data/<symbol>')
def get_market_data_endpoint(symbol):
    try:
        data = get_enhanced_mock_price(symbol)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting market data for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

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
        logger.error(f"Error getting positions: {e}")
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
        logger.error(f"Error getting trades: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/place-order', methods=['POST'])
def place_order():
    try:
        data = request.json or {}
        
        required_fields = ['symbol', 'side', 'quantity', 'price']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        account_type = data.get('account_type', 'paper')
        
        # Place the order
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        trade_id = f"M{int(datetime.now().timestamp())}"
        
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
        logger.error(f"Error placing order: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlist')
def get_watchlist():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT symbol FROM watchlist WHERE user_id = ?', ('default',))
        symbols = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        watchlist_data = []
        for symbol in symbols:
            market_data = get_enhanced_mock_price(symbol)
            watchlist_data.append(market_data)
        
        return jsonify({
            "watchlist": watchlist_data,
            "count": len(watchlist_data),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting watchlist: {e}")
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
        
        cursor.execute('SELECT COUNT(*) FROM trades WHERE strategy = "AI_AUTO"')
        ai_trades = cursor.fetchone()[0]
        
        cursor.execute('SELECT balance, invested, pnl FROM paper_accounts WHERE user_id = ?', ('default',))
        paper_account = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            "total_positions": total_positions,
            "total_trades": total_trades,
            "ai_trades": ai_trades,
            "paper_account": {
                "balance": paper_account[0] if paper_account else 1000000,
                "invested": paper_account[1] if paper_account else 0,
                "account_pnl": paper_account[2] if paper_account else 0
            },
            "ai_trading_active": AI_TRADING_ACTIVE,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    try:
        init_db()
        port = int(os.environ.get('PORT', 10000))
        logger.info(f"🚀 Starting AI Trading Platform on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        raise
