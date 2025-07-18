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
from threading import Timer

# Try to import yfinance with better error handling
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
    print("✅ yfinance loaded successfully")
except ImportError:
    YFINANCE_AVAILABLE = False
    print("⚠️ yfinance not available, using mock data")

app = Flask(__name__)
CORS(app)

# Global AI trading state
AI_TRADING_ACTIVE = False
AI_TRADING_THREAD = None

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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            user_id TEXT DEFAULT 'default',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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

# Enhanced market data with better error handling
def get_real_market_data(symbol):
    if YFINANCE_AVAILABLE:
        try:
            # Enhanced symbol mapping with fallbacks
            symbol_map = {
                'RELIANCE': ['RELIANCE.NS', 'RELIANCE.BO'],
                'TCS': ['TCS.NS', 'TCS.BO'],
                'HDFCBANK': ['HDFCBANK.NS', 'HDFCBANK.BO'],
                'INFY': ['INFY.NS', 'INFY.BO'],
                'ICICIBANK': ['ICICIBANK.NS', 'ICICIBANK.BO'],
                'SBIN': ['SBIN.NS', 'SBIN.BO'],
                'WIPRO': ['WIPRO.NS', 'WIPRO.BO'],
                'BHARTIARTL': ['BHARTIARTL.NS', 'BHARTIARTL.BO'],
                'LT': ['LT.NS', 'LT.BO'],
                'MARUTI': ['MARUTI.NS', 'MARUTI.BO'],
                'NIFTY': ['^NSEI', 'NIFTY50_USD.CC'],
                'BANKNIFTY': ['^NSEBANK', 'BANKNIFTY_USD.CC'],
                'SENSEX': ['^BSESN', 'BSE30.BO']
            }
            
            possible_symbols = symbol_map.get(symbol.upper(), [f"{symbol.upper()}.NS", f"{symbol.upper()}.BO"])
            
            for yahoo_symbol in possible_symbols:
                try:
                    stock = yf.Ticker(yahoo_symbol)
                    hist = stock.history(period='5d')  # Get more days for better data
                    
                    if len(hist) >= 1:
                        current_price = float(hist['Close'].iloc[-1])
                        if len(hist) >= 2:
                            previous_close = float(hist['Close'].iloc[-2])
                        else:
                            previous_close = current_price * 0.99  # Fallback
                        
                        change = current_price - previous_close
                        change_percent = (change / previous_close) * 100 if previous_close > 0 else 0
                        
                        return {
                            'symbol': symbol.upper(),
                            'current_price': round(current_price, 2),
                            'previous_close': round(previous_close, 2),
                            'change': round(change, 2),
                            'change_percent': round(change_percent, 2),
                            'timestamp': datetime.now().isoformat(),
                            'source': f'Yahoo Finance ({yahoo_symbol})',
                            'volume': int(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns and len(hist) > 0 else 0,
                            'high': round(float(hist['High'].iloc[-1]), 2) if len(hist) > 0 else current_price,
                            'low': round(float(hist['Low'].iloc[-1]), 2) if len(hist) > 0 else current_price,
                            'open': round(float(hist['Open'].iloc[-1]), 2) if len(hist) > 0 else current_price
                        }
                except Exception as e:
                    print(f"Failed to get data for {yahoo_symbol}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in yfinance for {symbol}: {e}")
    
    # Enhanced fallback with more realistic data
    return get_enhanced_mock_price(symbol)

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
        'source': 'Enhanced Mock Data',
        'volume': random.randint(100000, 10000000),
        'high': round(current_price * random.uniform(1.005, 1.025), 2),
        'low': round(current_price * random.uniform(0.975, 0.995), 2),
        'open': round(previous_close * random.uniform(0.995, 1.005), 2)
    }

# AI Trading Engine
def generate_ai_signal(symbol):
    """Generate AI trading signals based on technical analysis"""
    try:
        # Get historical data for the symbol
        market_data = get_real_market_data(symbol)
        current_price = market_data['current_price']
        change_percent = market_data['change_percent']
        
        # Simple AI logic (you can enhance with ML models)
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
            signal_strength *= 0.5  # Reduce signal in highly volatile conditions
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
        print(f"Error generating AI signal for {symbol}: {e}")
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
            balance = cursor.fetchone()[0]
        else:
            cursor.execute('SELECT available_capital FROM real_trading_accounts WHERE user_id = ?', ('default',))
            balance = cursor.fetchone()[0]
        
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
        else:
            cursor.execute('''
                UPDATE real_trading_accounts 
                SET available_capital = available_capital - ?, allocated_for_ai = allocated_for_ai + ?
                WHERE user_id = ?
            ''', (trade_value, trade_value, 'default'))
        
        # Update positions
        cursor.execute('SELECT * FROM positions WHERE symbol = ? AND account_type = ?', (symbol, settings[3]))
        existing_position = cursor.fetchone()
        
        if existing_position and signal_type == 'BUY':
            new_quantity = existing_position[2] + quantity
            new_avg_price = ((existing_position[2] * existing_position[3]) + (quantity * current_price)) / new_quantity
            cursor.execute('''
                UPDATE positions 
                SET quantity = ?, average_price = ?, current_price = ?
                WHERE symbol = ? AND account_type = ?
            ''', (new_quantity, new_avg_price, current_price, symbol, settings[3]))
        elif signal_type == 'BUY':
            cursor.execute('''
                INSERT INTO positions (symbol, quantity, average_price, current_price, pnl, strategy, account_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, quantity, current_price, current_price, 0.0, 'AI_AUTO', settings[3]))
        
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
        print(f"Error executing AI trade: {e}")
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
                print(f"Daily trade limit reached: {daily_trades}/{max_daily_trades}")
                time.sleep(3600)  # Wait 1 hour
                continue
            
            conn.close()
            
            # Get allowed symbols
            allowed_symbols = settings[8].split(',') if settings[8] else ['RELIANCE', 'TCS', 'HDFCBANK']
            
            # Generate signals for each symbol
            for symbol in allowed_symbols:
                if not AI_TRADING_ACTIVE:
                    break
                
                signal = generate_ai_signal(symbol.strip())
                if signal and signal['signal'] in ['BUY', 'SELL']:
                    success, message = execute_ai_trade(signal, settings)
                    print(f"AI Trading: {message}")
                    
                    if success:
                        time.sleep(5)  # Brief pause between trades
            
            # Wait for next trading cycle
            trading_frequency = settings[7] if settings[7] else 30
            time.sleep(trading_frequency)
            
        except Exception as e:
            print(f"Error in AI trading worker: {e}")
            time.sleep(60)

# Routes
@app.route('/')
def home():
    return jsonify({
        "message": "🚀 AI Trading Platform Professional",
        "version": "5.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "yfinance_status": "Available" if YFINANCE_AVAILABLE else "Mock Data Mode",
        "ai_trading_status": "Active" if AI_TRADING_ACTIVE else "Inactive",
        "features": [
            "🤖 Automated AI Trading System",
            "💰 Customizable Capital Management",
            "📊 Paper & Real Trading Modes",
            "🔄 Real-time Market Data",
            "⚙️ Risk Management Controls",
            "📈 Advanced Portfolio Analytics",
            "🎯 AI Signal Generation",
            "🔒 Position Size Limits"
        ]
    })

@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "version": "5.0",
        "market_data": "live" if YFINANCE_AVAILABLE else "mock",
        "ai_trading": "active" if AI_TRADING_ACTIVE else "inactive",
        "paper_trading": "active",
        "yfinance": YFINANCE_AVAILABLE
    })

# Enhanced Paper Trading Account Management
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
                    "initial_capital": account[5],
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
        data = request.json
        new_capital = data.get('capital', 1000000.0)
        
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE paper_accounts 
            SET balance = ?, invested = 0.0, pnl = 0.0, initial_capital = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (new_capital, new_capital, 'default'))
        
        # Clear all paper positions and trades
        cursor.execute('DELETE FROM positions WHERE account_type = ?', ('paper',))
        cursor.execute('DELETE FROM trades WHERE account_type = ?', ('paper',))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "Paper account reset successfully",
            "new_balance": new_capital
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/paper-account/update-capital', methods=['POST'])
def update_paper_capital():
    try:
        data = request.json
        new_capital = float(data.get('capital', 1000000.0))
        
        if new_capital < 10000 or new_capital > 100000000:
            return jsonify({"error": "Capital must be between ₹10,000 and ₹10,00,00,000"}), 400
        
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE paper_accounts 
            SET balance = ?, initial_capital = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (new_capital, new_capital, 'default'))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": f"Paper trading capital updated to ₹{new_capital:,.2f}",
            "new_capital": new_capital
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Real Trading Account Management
@app.route('/api/real-account')
def get_real_account():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM real_trading_accounts WHERE user_id = ?', ('default',))
        account = cursor.fetchone()
        
        if account:
            return jsonify({
                "account": {
                    "available_capital": account[2],
                    "allocated_for_ai": account[3],
                    "daily_limit": account[4],
                    "max_position_size": account[5],
                    "is_active": bool(account[6])
                },
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({"error": "Account not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/real-account/setup', methods=['POST'])
def setup_real_account():
    try:
        data = request.json
        available_capital = float(data.get('capital', 0))
        daily_limit = float(data.get('daily_limit', 5000))
        max_position_size = float(data.get('max_position_size', 50000))
        
        if available_capital < 1000:
            return jsonify({"error": "Minimum capital is ₹1,000"}), 400
        
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE real_trading_accounts 
            SET available_capital = ?, daily_limit = ?, max_position_size = ?, is_active = TRUE, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (available_capital, daily_limit, max_position_size, 'default'))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": f"Real trading account setup with ₹{available_capital:,.2f}",
            "settings": {
                "capital": available_capital,
                "daily_limit": daily_limit,
                "max_position_size": max_position_size
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# AI Trading Management
@app.route('/api/ai-trading/settings', methods=['GET'])
def get_ai_settings():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM ai_trading_settings WHERE user_id = ?', ('default',))
        settings = cursor.fetchone()
        
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
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/ai-trading/settings', methods=['POST'])
def update_ai_settings():
    try:
        data = request.json
        
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE ai_trading_settings 
            SET trading_mode = ?, max_capital_per_trade = ?, max_daily_trades = ?, 
                risk_level = ?, auto_stop_loss = ?, auto_take_profit = ?, 
                trading_frequency = ?, allowed_symbols = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (
            data.get('trading_mode', 'paper'),
            data.get('max_capital_per_trade', 10000),
            data.get('max_daily_trades', 10),
            data.get('risk_level', 'medium'),
            data.get('auto_stop_loss', 5.0),
            data.get('auto_take_profit', 10.0),
            data.get('trading_frequency', 30),
            ','.join(data.get('allowed_symbols', ['RELIANCE', 'TCS', 'HDFCBANK'])),
            'default'
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "AI trading settings updated successfully"
        })
    except Exception as e:
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
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai-trading/logs')
def get_ai_logs():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM ai_trading_logs 
            ORDER BY timestamp DESC LIMIT 100
        ''')
        logs = cursor.fetchall()
        
        log_list = []
        for log in logs:
            log_list.append({
                'id': log[0],
                'timestamp': log[1],
                'action': log[2],
                'symbol': log[3],
                'signal_type': log[4],
                'confidence': log[5],
                'price': log[6],
                'quantity': log[7],
                'reason': log[8],
                'status': log[9]
            })
        
        conn.close()
        
        return jsonify({
            "logs": log_list,
            "count": len(log_list),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai-trading/signals')
def get_current_signals():
    try:
        # Get allowed symbols from settings
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT allowed_symbols FROM ai_trading_settings WHERE user_id = ?', ('default',))
        result = cursor.fetchone()
        allowed_symbols = result[0].split(',') if result and result[0] else ['RELIANCE', 'TCS', 'HDFCBANK']
        
        conn.close()
        
        signals = []
        for symbol in allowed_symbols:
            signal = generate_ai_signal(symbol.strip())
            if signal:
                signals.append(signal)
        
        return jsonify({
            "signals": signals,
            "count": len(signals),
            "generated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Include all previous routes (market-overview, positions, trades, etc.)
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
            "data_source": "Yahoo Finance" if YFINANCE_AVAILABLE else "Enhanced Mock Data",
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
        
        trade_id = f"M{int(datetime.now().timestamp())}"  # M for Manual
        
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

# Watchlist and other existing endpoints remain the same...
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
            {'symbol': 'MARUTI', 'name': 'Maruti Suzuki India Ltd'}
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
        
        cursor.execute('SELECT COUNT(*) FROM trades WHERE strategy = "AI_AUTO"')
        ai_trades = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(pnl) FROM positions WHERE pnl IS NOT NULL')
        total_pnl = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT balance, invested, pnl FROM paper_accounts WHERE user_id = ?', ('default',))
        paper_account = cursor.fetchone()
        
        cursor.execute('SELECT available_capital, allocated_for_ai FROM real_trading_accounts WHERE user_id = ?', ('default',))
        real_account = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            "total_positions": total_positions,
            "total_trades": total_trades,
            "ai_trades": ai_trades,
            "total_pnl": round(total_pnl, 2),
            "paper_account": {
                "balance": paper_account[0] if paper_account else 0,
                "invested": paper_account[1] if paper_account else 0,
                "account_pnl": paper_account[2] if paper_account else 0
            },
            "real_account": {
                "available_capital": real_account[0] if real_account else 0,
                "allocated_for_ai": real_account[1] if real_account else 0
            },
            "ai_trading_active": AI_TRADING_ACTIVE,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
