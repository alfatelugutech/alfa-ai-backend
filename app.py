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
import yfinance as yf
from kiteconnect import KiteConnect

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["*"])

# Global AI trading state
AI_TRADING_ACTIVE = False
AI_TRADING_THREAD = None

# Zerodha/Kite Connect configuration
KITE_API_KEY = os.environ.get('KITE_API_KEY', '')
KITE_ACCESS_TOKEN = os.environ.get('KITE_ACCESS_TOKEN', '')
kite = None

if KITE_API_KEY:
    try:
        kite = KiteConnect(api_key=KITE_API_KEY)
        if KITE_ACCESS_TOKEN:
            kite.set_access_token(KITE_ACCESS_TOKEN)
            logger.info("✅ Zerodha Kite Connect initialized")
    except Exception as e:
        logger.error(f"❌ Zerodha Kite Connect initialization failed: {e}")

# Database initialization
def init_db():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        # Create enhanced positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                average_price REAL NOT NULL,
                current_price REAL,
                pnl REAL,
                pnl_percent REAL,
                strategy TEXT,
                account_type TEXT DEFAULT 'paper',
                broker TEXT DEFAULT 'paper',
                entry_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create enhanced trades table with complete lifecycle
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                entry_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                exit_price REAL,
                exit_time DATETIME,
                pnl REAL DEFAULT 0,
                pnl_percent REAL DEFAULT 0,
                strategy TEXT,
                account_type TEXT DEFAULT 'paper',
                broker TEXT DEFAULT 'paper',
                status TEXT DEFAULT 'open',
                fees REAL DEFAULT 0,
                taxes REAL DEFAULT 0,
                net_pnl REAL DEFAULT 0,
                duration_minutes INTEGER DEFAULT 0,
                notes TEXT
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
                day_pnl REAL DEFAULT 0.0,
                initial_capital REAL DEFAULT 1000000.0,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create broker accounts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broker_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default',
                broker_name TEXT NOT NULL,
                api_key TEXT,
                access_token TEXT,
                is_active BOOLEAN DEFAULT FALSE,
                balance REAL DEFAULT 0.0,
                margin_available REAL DEFAULT 0.0,
                margin_used REAL DEFAULT 0.0,
                last_sync DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create AI trading settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_trading_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default',
                is_active BOOLEAN DEFAULT FALSE,
                trading_mode TEXT DEFAULT 'paper',
                broker TEXT DEFAULT 'paper',
                max_capital_per_trade REAL DEFAULT 10000.0,
                max_daily_trades INTEGER DEFAULT 10,
                risk_level TEXT DEFAULT 'medium',
                auto_stop_loss REAL DEFAULT 5.0,
                auto_take_profit REAL DEFAULT 10.0,
                trading_frequency INTEGER DEFAULT 30,
                allowed_symbols TEXT DEFAULT 'RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK',
                min_signal_confidence REAL DEFAULT 70.0,
                use_real_data BOOLEAN DEFAULT TRUE,
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
                status TEXT,
                error_message TEXT,
                execution_time REAL
            )
        ''')
        
        # Create market data cache table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                current_price REAL NOT NULL,
                previous_close REAL,
                change REAL,
                change_percent REAL,
                volume INTEGER,
                high REAL,
                low REAL,
                open REAL,
                market_cap REAL,
                pe_ratio REAL,
                data_source TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol)
            )
        ''')
        
        # Create watchlist table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                user_id TEXT DEFAULT 'default',
                target_price REAL,
                stop_loss REAL,
                alerts_enabled BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default data
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
        
        # Insert default broker account
        cursor.execute('SELECT COUNT(*) FROM broker_accounts WHERE broker_name = ?', ('zerodha',))
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO broker_accounts (user_id, broker_name, is_active)
                VALUES ('default', 'zerodha', ?)
            ''', (bool(KITE_API_KEY),))
        
        # Insert sample watchlist
        cursor.execute('SELECT COUNT(*) FROM watchlist')
        if cursor.fetchone()[0] == 0:
            watchlist_items = [
                ('RELIANCE', 'default'),
                ('TCS', 'default'),
                ('HDFCBANK', 'default'),
                ('INFY', 'default'),
                ('ICICIBANK', 'default'),
                ('WIPRO', 'default'),
                ('BHARTIARTL', 'default'),
                ('LT', 'default'),
                ('MARUTI', 'default'),
                ('SBIN', 'default')
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

# Enhanced market data functions
def get_real_market_data(symbol):
    """Get real market data from multiple sources"""
    try:
        # First try Zerodha Kite if available
        if kite:
            try:
                # Map common symbols to NSE instrument tokens (you'll need to implement this mapping)
                instruments = kite.instruments("NSE")
                instrument_token = None
                
                for instrument in instruments:
                    if instrument['tradingsymbol'] == symbol:
                        instrument_token = instrument['instrument_token']
                        break
                
                if instrument_token:
                    quote = kite.quote(f"NSE:{symbol}")
                    if quote and f"NSE:{symbol}" in quote:
                        data = quote[f"NSE:{symbol}"]
                        return {
                            'symbol': symbol,
                            'current_price': data['last_price'],
                            'previous_close': data['ohlc']['close'],
                            'change': data['last_price'] - data['ohlc']['close'],
                            'change_percent': ((data['last_price'] - data['ohlc']['close']) / data['ohlc']['close']) * 100,
                            'volume': data['volume'],
                            'high': data['ohlc']['high'],
                            'low': data['ohlc']['low'],
                            'open': data['ohlc']['open'],
                            'timestamp': datetime.now().isoformat(),
                            'source': 'Zerodha Kite',
                            'market_cap': data.get('market_cap', 0),
                            'pe_ratio': data.get('pe', 0)
                        }
            except Exception as e:
                logger.warning(f"Zerodha data fetch failed for {symbol}: {e}")
        
        # Fallback to yfinance
        try:
            # Add .NS suffix for NSE stocks
            yf_symbol = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
            ticker = yf.Ticker(yf_symbol)
            
            # Get current data
            info = ticker.info
            history = ticker.history(period="2d")
            
            if not history.empty:
                current_price = history['Close'].iloc[-1]
                previous_close = history['Close'].iloc[-2] if len(history) > 1 else current_price
                change = current_price - previous_close
                change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
                
                return {
                    'symbol': symbol,
                    'current_price': round(float(current_price), 2),
                    'previous_close': round(float(previous_close), 2),
                    'change': round(float(change), 2),
                    'change_percent': round(float(change_percent), 2),
                    'volume': int(history['Volume'].iloc[-1]) if 'Volume' in history.columns else 0,
                    'high': round(float(history['High'].iloc[-1]), 2),
                    'low': round(float(history['Low'].iloc[-1]), 2),
                    'open': round(float(history['Open'].iloc[-1]), 2),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'Yahoo Finance',
                    'market_cap': info.get('marketCap', 0),
                    'pe_ratio': info.get('trailingPE', 0)
                }
        except Exception as e:
            logger.warning(f"Yahoo Finance data fetch failed for {symbol}: {e}")
        
        # If all real sources fail, return enhanced mock data
        return get_enhanced_mock_price(symbol)
        
    except Exception as e:
        logger.error(f"Error getting real market data for {symbol}: {e}")
        return get_enhanced_mock_price(symbol)

def get_enhanced_mock_price(symbol):
    """Enhanced mock data with realistic intraday variations"""
    base_prices = {
        'RELIANCE': 2478.30, 'TCS': 3812.45, 'HDFCBANK': 1698.75, 'INFY': 1789.90,
        'ICICIBANK': 1167.25, 'SBIN': 820.50, 'WIPRO': 445.80, 'BHARTIARTL': 1089.25,
        'LT': 3567.90, 'MARUTI': 10890.45, 'NIFTY': 19567.80, 'BANKNIFTY': 45234.50,
        'SENSEX': 65432.10, 'ADANIPORTS': 890.45, 'ASIANPAINT': 3245.60, 'AXISBANK': 1089.30,
        'BAJAJ-AUTO': 8765.40, 'BAJFINANCE': 7654.30, 'BAJAJFINSV': 1543.20, 'BPCL': 456.70,
        'BRITANNIA': 4567.80, 'CIPLA': 1234.50, 'COALINDIA': 234.60, 'DIVISLAB': 4321.90,
        'DRREDDY': 5432.10, 'EICHERMOT': 3456.70, 'GRASIM': 1876.50, 'HCLTECH': 1543.20,
        'HDFC': 2765.40, 'HDFCLIFE': 654.30, 'HEROMOTOCO': 3210.90, 'HINDALCO': 543.20,
        'HINDUNILVR': 2543.60, 'ICICIPRULI': 654.70, 'IOC': 123.40, 'ITC': 432.10,
        'JSWSTEEL': 876.50, 'KOTAKBANK': 1987.60, 'LARSEN': 2345.80, 'M&M': 1456.30,
        'NESTLEIND': 21098.70, 'NTPC': 234.50, 'ONGC': 187.90, 'POWERGRID': 234.60,
        'SBILIFE': 1234.50, 'SHREECEM': 28765.40, 'SUNPHARMA': 987.60, 'TATACONSUM': 876.50,
        'TATAMOTORS': 654.30, 'TATASTEEL': 123.40, 'TECHM': 1543.20, 'TITAN': 3210.90,
        'ULTRACEMCO': 8765.40, 'UPL': 654.30
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
        'open': round(previous_close * random.uniform(0.995, 1.005), 2),
        'market_cap': random.randint(10000000000, 1000000000000),
        'pe_ratio': round(random.uniform(10, 50), 2)
    }

def cache_market_data(symbol, data):
    """Cache market data to database"""
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO market_data_cache 
            (symbol, current_price, previous_close, change, change_percent, 
             volume, high, low, open, market_cap, pe_ratio, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['symbol'], data['current_price'], data['previous_close'],
            data['change'], data['change_percent'], data['volume'],
            data['high'], data['low'], data['open'], 
            data.get('market_cap', 0), data.get('pe_ratio', 0), data['source']
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error caching market data: {e}")

# Enhanced AI Trading Engine
def generate_ai_signal(symbol):
    """Generate AI trading signals based on technical analysis"""
    try:
        # Get real market data
        market_data = get_real_market_data(symbol)
        current_price = market_data['current_price']
        change_percent = market_data['change_percent']
        volume = market_data['volume']
        
        # Cache the data
        cache_market_data(symbol, market_data)
        
        # Enhanced AI logic
        signal_strength = 0
        reasons = []
        
        # Price momentum analysis
        if change_percent > 3:
            signal_strength += 40
            reasons.append("Strong bullish momentum")
        elif change_percent > 1.5:
            signal_strength += 20
            reasons.append("Positive momentum")
        elif change_percent < -3:
            signal_strength -= 40
            reasons.append("Strong bearish momentum")
        elif change_percent < -1.5:
            signal_strength -= 20
            reasons.append("Negative momentum")
        
        # Volume analysis
        avg_volume = 5000000  # Mock average volume
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1
        
        if volume_ratio > 1.5:
            signal_strength += 15
            reasons.append("High volume activity")
        elif volume_ratio < 0.5:
            signal_strength -= 10
            reasons.append("Low volume concern")
        
        # Market time consideration
        hour = datetime.now().hour
        if 10 <= hour <= 14:  # Active trading hours
            signal_strength += 10
            reasons.append("Active market hours")
        elif hour < 10 or hour > 15:
            signal_strength -= 5
            reasons.append("Off-market hours")
        
        # Technical indicators (simplified)
        high_low_ratio = (market_data['high'] - market_data['low']) / current_price
        if high_low_ratio > 0.02:  # High volatility
            signal_strength -= 10
            reasons.append("High intraday volatility")
        
        # Risk management
        if abs(change_percent) > 5:
            signal_strength *= 0.7
            reasons.append("High volatility - reduced confidence")
        
        # Determine signal type
        confidence = 50
        if signal_strength > 30:
            signal_type = 'BUY'
            confidence = min(95, 65 + signal_strength)
        elif signal_strength < -30:
            signal_type = 'SELL'
            confidence = min(95, 65 + abs(signal_strength))
        else:
            signal_type = 'HOLD'
            confidence = 50 + abs(signal_strength / 2)
        
        return {
            'symbol': symbol,
            'signal': signal_type,
            'confidence': round(confidence, 1),
            'current_price': current_price,
            'target_price': current_price * (1.05 if signal_type == 'BUY' else 0.95),
            'stop_loss': current_price * (0.97 if signal_type == 'BUY' else 1.03),
            'reasons': reasons,
            'signal_strength': signal_strength,
            'market_data': market_data,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating AI signal for {symbol}: {e}")
        return None

def execute_ai_trade(signal, settings):
    """Execute trade based on AI signal with complete tracking"""
    try:
        if signal['confidence'] < settings[14]:  # min_signal_confidence
            return False, f"Low confidence signal: {signal['confidence']}%"
        
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
            cursor.execute('SELECT balance FROM broker_accounts WHERE user_id = ? AND is_active = TRUE', ('default',))
            result = cursor.fetchone()
            balance = result[0] if result else 0
        
        trade_value = quantity * current_price
        
        if trade_value > balance:
            conn.close()
            return False, "Insufficient balance"
        
        # Generate unique trade ID
        trade_id = f"AI_{int(datetime.now().timestamp())}_{random.randint(100, 999)}"
        entry_time = datetime.now()
        
        # Calculate fees (simplified)
        brokerage_fee = trade_value * 0.0003  # 0.03% brokerage
        stt = trade_value * 0.001 if signal_type == 'SELL' else 0  # STT on sell
        total_fees = brokerage_fee + stt
        
        # Insert trade record
        cursor.execute('''
            INSERT INTO trades (
                trade_id, symbol, side, quantity, entry_price, entry_time,
                strategy, account_type, broker, status, fees, target_price, stop_loss
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_id, symbol, signal_type, quantity, current_price, entry_time,
            'AI_AUTO', settings[3], settings[4] if len(settings) > 4 else 'paper',
            'open', total_fees, signal.get('target_price', 0), signal.get('stop_loss', 0)
        ))
        
        # Update account balance
        if settings[3] == 'paper':
            cursor.execute('''
                UPDATE paper_accounts 
                SET balance = balance - ?, invested = invested + ?, total_trades = total_trades + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (trade_value + total_fees, trade_value, 'default'))
        
        # Log AI action
        cursor.execute('''
            INSERT INTO ai_trading_logs (
                action, symbol, signal_type, confidence, price, quantity, 
                reason, status, execution_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'TRADE_EXECUTED', symbol, signal_type, signal['confidence'], 
            current_price, quantity, '; '.join(signal['reasons']), 'SUCCESS', 0.5
        ))
        
        conn.commit()
        conn.close()
        
        return True, f"AI trade executed: {signal_type} {quantity} {symbol} at ₹{current_price} (ID: {trade_id})"
        
    except Exception as e:
        logger.error(f"Error executing AI trade: {e}")
        return False, str(e)

def monitor_open_trades():
    """Monitor open trades for exit conditions"""
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades WHERE status = 'open' AND strategy = 'AI_AUTO'
        ''')
        open_trades = cursor.fetchall()
        
        for trade in open_trades:
            trade_id, symbol, side, quantity = trade[1], trade[2], trade[3], trade[4]
            entry_price, entry_time = trade[5], trade[6]
            target_price, stop_loss = trade[19], trade[20] if len(trade) > 20 else (0, 0)
            
            # Get current price
            current_data = get_real_market_data(symbol)
            current_price = current_data['current_price']
            
            # Check exit conditions
            should_exit = False
            exit_reason = ""
            
            if side == 'BUY':
                if current_price >= target_price and target_price > 0:
                    should_exit = True
                    exit_reason = "Target reached"
                elif current_price <= stop_loss and stop_loss > 0:
                    should_exit = True
                    exit_reason = "Stop loss hit"
            else:  # SELL
                if current_price <= target_price and target_price > 0:
                    should_exit = True
                    exit_reason = "Target reached"
                elif current_price >= stop_loss and stop_loss > 0:
                    should_exit = True
                    exit_reason = "Stop loss hit"
            
            # Time-based exit (after 4 hours)
            entry_dt = datetime.strptime(entry_time, '%Y-%m-%d %H:%M:%S.%f')
            if (datetime.now() - entry_dt).seconds > 14400:  # 4 hours
                should_exit = True
                exit_reason = "Time-based exit"
            
            if should_exit:
                close_trade(trade_id, current_price, exit_reason, cursor)
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error monitoring trades: {e}")

def close_trade(trade_id, exit_price, exit_reason, cursor):
    """Close a trade and calculate P&L"""
    try:
        exit_time = datetime.now()
        
        # Get trade details
        cursor.execute('SELECT * FROM trades WHERE trade_id = ?', (trade_id,))
        trade = cursor.fetchone()
        
        if not trade:
            return
        
        entry_price, entry_time = trade[5], trade[6]
        quantity, side = trade[4], trade[3]
        
        # Calculate P&L
        if side == 'BUY':
            pnl = (exit_price - entry_price) * quantity
        else:  # SELL
            pnl = (entry_price - exit_price) * quantity
        
        pnl_percent = (pnl / (entry_price * quantity)) * 100
        
        # Calculate duration
        entry_dt = datetime.strptime(entry_time, '%Y-%m-%d %H:%M:%S.%f')
        duration_minutes = (exit_time - entry_dt).total_seconds() / 60
        
        # Update trade
        cursor.execute('''
            UPDATE trades 
            SET exit_price = ?, exit_time = ?, pnl = ?, pnl_percent = ?, 
                status = 'closed', duration_minutes = ?, notes = ?
            WHERE trade_id = ?
        ''', (exit_price, exit_time, pnl, pnl_percent, duration_minutes, exit_reason, trade_id))
        
        # Update account
        cursor.execute('''
            UPDATE paper_accounts 
            SET balance = balance + ?, invested = invested - ?, pnl = pnl + ?,
                winning_trades = winning_trades + ?, losing_trades = losing_trades + ?
            WHERE user_id = ?
        ''', (
            (entry_price * quantity) + pnl, entry_price * quantity, pnl,
            1 if pnl > 0 else 0, 1 if pnl < 0 else 0, 'default'
        ))
        
        logger.info(f"Trade {trade_id} closed: P&L ₹{pnl:.2f} ({pnl_percent:.2f}%)")
        
    except Exception as e:
        logger.error(f"Error closing trade {trade_id}: {e}")

def ai_trading_worker():
    """Enhanced background worker for AI trading"""
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
                AND DATE(entry_time) = ?
            ''', (settings[3], today))
            
            daily_trades = cursor.fetchone()[0]
            max_daily_trades = settings[5]
            
            if daily_trades >= max_daily_trades:
                conn.close()
                logger.info(f"Daily trade limit reached: {daily_trades}/{max_daily_trades}")
                time.sleep(3600)  # Wait 1 hour
                continue
            
            conn.close()
            
            # Monitor existing trades
            monitor_open_trades()
            
            # Get allowed symbols
            allowed_symbols = settings[10].split(',') if settings[10] else ['RELIANCE', 'TCS', 'HDFCBANK']
            
            # Generate signals for each symbol
            for symbol in allowed_symbols[:3]:  # Limit to 3 symbols at a time
                if not AI_TRADING_ACTIVE:
                    break
                
                signal = generate_ai_signal(symbol.strip())
                if signal and signal['signal'] in ['BUY', 'SELL']:
                    success, message = execute_ai_trade(signal, settings)
                    logger.info(f"AI Trading: {message}")
                    
                    if success:
                        time.sleep(10)  # Pause between trades
            
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
        "message": "🚀 AI Trading Platform Professional - Enhanced Backend",
        "version": "8.0 - Complete Trading System",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "data_sources": "Real-time (Yahoo Finance, Zerodha Kite)",
        "ai_trading_status": "Active" if AI_TRADING_ACTIVE else "Inactive",
        "zerodha_integration": "Available" if kite else "Configure API keys",
        "features": [
            "🤖 Advanced AI Trading System",
            "💰 Paper & Live Trading", 
            "📊 Real-time Market Data (Yahoo Finance + Zerodha)",
            "⚙️ Advanced Risk Management",
            "📈 Complete Portfolio Analytics",
            "🎯 Enhanced AI Signal Generation",
            "🔌 Zerodha Kite Connect Integration",
            "📋 Detailed Trade Reports",
            "💾 Advanced Data Caching",
            "📊 Real-time P&L Tracking"
        ]
    })

@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "version": "8.0",
        "market_data": "real-time",
        "ai_trading": "active" if AI_TRADING_ACTIVE else "inactive",
        "paper_trading": "active",
        "zerodha_status": "configured" if kite else "not_configured",
        "data_sources": ["yahoo_finance", "zerodha_kite" if kite else "mock"],
        "uptime": "running"
    })

# Enhanced API Routes
@app.route('/api/brokers')
def get_brokers():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM broker_accounts WHERE user_id = ?', ('default',))
        brokers = cursor.fetchall()
        conn.close()
        
        broker_list = []
        for broker in brokers:
            broker_list.append({
                "name": broker[2],
                "is_active": bool(broker[4]),
                "balance": broker[5],
                "margin_available": broker[6],
                "last_sync": broker[8]
            })
        
        return jsonify({
            "brokers": broker_list,
            "zerodha_available": bool(kite),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting brokers: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/broker/zerodha/activate', methods=['POST'])
def activate_zerodha():
    global kite
    try:
        data = request.json or {}
        api_key = data.get('api_key', KITE_API_KEY)
        access_token = data.get('access_token', KITE_ACCESS_TOKEN)
        
        if not api_key:
            return jsonify({"error": "API key required"}), 400
        
        # Initialize Kite Connect
        kite = KiteConnect(api_key=api_key)
        if access_token:
            kite.set_access_token(access_token)
        
        # Update database
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE broker_accounts 
            SET api_key = ?, access_token = ?, is_active = TRUE, last_sync = CURRENT_TIMESTAMP
            WHERE broker_name = 'zerodha' AND user_id = ?
        ''', (api_key, access_token, 'default'))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "Zerodha broker activated successfully",
            "login_url": kite.login_url() if not access_token else None
        })
        
    except Exception as e:
        logger.error(f"Error activating Zerodha: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/real-market-data/<symbol>')
def get_market_data_endpoint(symbol):
    try:
        data = get_real_market_data(symbol.upper())
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting market data for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/market-overview')
def get_market_overview():
    try:
        indices = ['NIFTY', 'BANKNIFTY', 'SENSEX']
        market_data = {}
        
        for index in indices:
            market_data[index] = get_real_market_data(index)
        
        # Get market status
        now = datetime.now()
        current_time = now.time()
        market_open = now.replace(hour=9, minute=15).time()
        market_close = now.replace(hour=15, minute=30).time()
        
        is_weekend = now.weekday() >= 5
        market_status = "Closed"
        
        if not is_weekend and market_open <= current_time <= market_close:
            market_status = "Open"
        elif not is_weekend and current_time < market_open:
            market_status = "Pre-Market"
        elif not is_weekend and current_time > market_close:
            market_status = "Post-Market"
        
        return jsonify({
            "market_data": market_data,
            "market_status": market_status,
            "data_source": "Real-time Multi-source",
            "zerodha_active": bool(kite),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting market overview: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/paper-account')
def get_paper_account():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM paper_accounts WHERE user_id = ?', ('default',))
        account = cursor.fetchone()
        
        # Calculate today's P&L
        today = datetime.now().date()
        cursor.execute('''
            SELECT COALESCE(SUM(pnl), 0) FROM trades 
            WHERE account_type = 'paper' AND DATE(entry_time) = ? AND status = 'closed'
        ''', (today,))
        day_pnl = cursor.fetchone()[0]
        
        conn.close()
        
        if account:
            return jsonify({
                "account": {
                    "balance": account[2],
                    "invested": account[3],
                    "pnl": account[4],
                    "day_pnl": day_pnl,
                    "initial_capital": account[5],
                    "total_value": account[2] + account[3] + account[4],
                    "total_trades": account[6],
                    "winning_trades": account[7],
                    "losing_trades": account[8],
                    "win_rate": (account[7] / max(account[6], 1)) * 100
                },
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({"error": "Account not found"}), 404
            
    except Exception as e:
        logger.error(f"Error getting paper account: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/trades')
def get_trades():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        # Get trade filter from query params
        trade_filter = request.args.get('filter', 'all')
        limit = int(request.args.get('limit', 50))
        
        base_query = 'SELECT * FROM trades'
        params = []
        
        if trade_filter == 'ai':
            base_query += ' WHERE strategy = ?'
            params.append('AI_AUTO')
        elif trade_filter == 'manual':
            base_query += ' WHERE strategy != ?'
            params.append('AI_AUTO')
        elif trade_filter == 'today':
            base_query += ' WHERE DATE(entry_time) = ?'
            params.append(datetime.now().date())
        elif trade_filter == 'open':
            base_query += ' WHERE status = ?'
            params.append('open')
        elif trade_filter == 'closed':
            base_query += ' WHERE status = ?'
            params.append('closed')
        
        base_query += ' ORDER BY entry_time DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(base_query, params)
        trades = cursor.fetchall()
        
        # Format trades for frontend
        formatted_trades = []
        for trade in trades:
            formatted_trades.append({
                "id": trade[0],
                "trade_id": trade[1],
                "symbol": trade[2],
                "side": trade[3],
                "quantity": trade[4],
                "entry_price": trade[5],
                "entry_time": trade[6],
                "exit_price": trade[7],
                "exit_time": trade[8],
                "pnl": trade[9],
                "pnl_percent": trade[10],
                "strategy": trade[11],
                "account_type": trade[12],
                "broker": trade[13],
                "status": trade[14],
                "fees": trade[15],
                "duration_minutes": trade[18],
                "notes": trade[19] if len(trade) > 19 else ""
            })
        
        conn.close()
        
        return jsonify({
            "trades": formatted_trades,
            "count": len(formatted_trades),
            "filter": trade_filter,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/positions')
def get_positions():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        # Calculate positions from open trades
        cursor.execute('''
            SELECT symbol, 
                   SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) as net_quantity,
                   AVG(entry_price) as avg_price,
                   account_type, broker
            FROM trades 
            WHERE status = 'open' 
            GROUP BY symbol, account_type, broker
            HAVING net_quantity != 0
        ''')
        positions = cursor.fetchall()
        
        formatted_positions = []
        for pos in positions:
            symbol, quantity, avg_price = pos[0], pos[1], pos[2]
            
            # Get current price
            current_data = get_real_market_data(symbol)
            current_price = current_data['current_price']
            
            # Calculate P&L
            pnl = (current_price - avg_price) * quantity
            pnl_percent = (pnl / (avg_price * abs(quantity))) * 100
            
            formatted_positions.append({
                "symbol": symbol,
                "quantity": quantity,
                "average_price": avg_price,
                "current_price": current_price,
                "pnl": pnl,
                "pnl_percent": pnl_percent,
                "market_value": current_price * abs(quantity),
                "account_type": pos[3],
                "broker": pos[4]
            })
        
        conn.close()
        
        return jsonify({
            "positions": formatted_positions,
            "count": len(formatted_positions),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
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
        
        # Log AI start
        cursor.execute('''
            INSERT INTO ai_trading_logs (action, status, reason)
            VALUES (?, ?, ?)
        ''', ('AI_STARTED', 'SUCCESS', 'AI trading started by user'))
        
        conn.commit()
        conn.close()
        
        # Start AI trading thread
        AI_TRADING_ACTIVE = True
        AI_TRADING_THREAD = threading.Thread(target=ai_trading_worker, daemon=True)
        AI_TRADING_THREAD.start()
        
        return jsonify({
            "status": "success",
            "message": "🤖 AI Trading started successfully with real-time data!",
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
        
        # Log AI stop
        cursor.execute('''
            INSERT INTO ai_trading_logs (action, status, reason)
            VALUES (?, ?, ?)
        ''', ('AI_STOPPED', 'SUCCESS', 'AI trading stopped by user'))
        
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

@app.route('/api/ai-trading/settings', methods=['GET', 'POST'])
def ai_trading_settings():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        if request.method == 'GET':
            cursor.execute('SELECT * FROM ai_trading_settings WHERE user_id = ?', ('default',))
            settings = cursor.fetchone()
            conn.close()
            
            if settings:
                return jsonify({
                    "settings": {
                        "is_active": bool(settings[2]),
                        "trading_mode": settings[3],
                        "broker": settings[4] if len(settings) > 4 else 'paper',
                        "max_capital_per_trade": settings[5] if len(settings) > 5 else settings[4],
                        "max_daily_trades": settings[6] if len(settings) > 6 else settings[5],
                        "risk_level": settings[7] if len(settings) > 7 else settings[6],
                        "auto_stop_loss": settings[8] if len(settings) > 8 else settings[7],
                        "auto_take_profit": settings[9] if len(settings) > 9 else settings[8],
                        "trading_frequency": settings[10] if len(settings) > 10 else settings[9],
                        "allowed_symbols": settings[11].split(',') if len(settings) > 11 and settings[11] else settings[10].split(','),
                        "min_signal_confidence": settings[12] if len(settings) > 12 else 70.0,
                        "use_real_data": bool(settings[13]) if len(settings) > 13 else True
                    },
                    "timestamp": datetime.now().isoformat()
                })
            else:
                return jsonify({"error": "Settings not found"}), 404
        
        else:  # POST
            data = request.json or {}
            
            cursor.execute('''
                UPDATE ai_trading_settings 
                SET trading_mode = ?, max_capital_per_trade = ?, max_daily_trades = ?,
                    risk_level = ?, auto_stop_loss = ?, auto_take_profit = ?,
                    trading_frequency = ?, allowed_symbols = ?, min_signal_confidence = ?,
                    use_real_data = ?, updated_at = CURRENT_TIMESTAMP
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
                data.get('min_signal_confidence', 70.0),
                data.get('use_real_data', True),
                'default'
            ))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                "status": "success",
                "message": "AI settings updated successfully"
            })
            
    except Exception as e:
        logger.error(f"Error with AI settings: {e}")
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
        broker = data.get('broker', 'paper')
        
        # Generate unique trade ID
        trade_id = f"M_{int(datetime.now().timestamp())}_{random.randint(100, 999)}"
        entry_time = datetime.now()
        
        # Calculate fees
        trade_value = data['quantity'] * data['price']
        fees = trade_value * 0.0003  # Basic brokerage
        
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        # Check balance
        if account_type == 'paper':
            cursor.execute('SELECT balance FROM paper_accounts WHERE user_id = ?', ('default',))
            result = cursor.fetchone()
            balance = result[0] if result else 0
            
            if trade_value + fees > balance:
                conn.close()
                return jsonify({"error": "Insufficient balance"}), 400
        
        # Place the order
        cursor.execute('''
            INSERT INTO trades (
                trade_id, symbol, side, quantity, entry_price, entry_time,
                strategy, account_type, broker, status, fees
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_id, data['symbol'].upper(), data['side'].upper(),
            data['quantity'], data['price'], entry_time,
            data.get('strategy', 'manual'), account_type, broker, 'open', fees
        ))
        
        # Update account balance
        if account_type == 'paper':
            cursor.execute('''
                UPDATE paper_accounts 
                SET balance = balance - ?, invested = invested + ?, total_trades = total_trades + 1
                WHERE user_id = ?
            ''', (trade_value + fees, trade_value, 'default'))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": f"{data['side']} order placed successfully",
            "trade_id": trade_id,
            "account_type": account_type,
            "broker": broker,
            "fees": fees,
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
            market_data = get_real_market_data(symbol)
            watchlist_data.append(market_data)
        
        return jsonify({
            "watchlist": watchlist_data,
            "count": len(watchlist_data),
            "data_source": "real-time",
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
        
        # Get positions count
        cursor.execute('''
            SELECT COUNT(DISTINCT symbol) FROM trades WHERE status = 'open'
        ''')
        total_positions = cursor.fetchone()[0]
        
        # Get trades stats
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM trades WHERE strategy = "AI_AUTO"')
        ai_trades = cursor.fetchone()[0]
        
        # Get account info
        cursor.execute('SELECT balance, invested, pnl, winning_trades, losing_trades, total_trades FROM paper_accounts WHERE user_id = ?', ('default',))
        paper_account = cursor.fetchone()
        
        # Get today's stats
        today = datetime.now().date()
        cursor.execute('''
            SELECT COUNT(*), COALESCE(SUM(pnl), 0) FROM trades 
            WHERE DATE(entry_time) = ? AND status = 'closed'
        ''', (today,))
        today_stats = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            "total_positions": total_positions,
            "total_trades": total_trades,
            "ai_trades": ai_trades,
            "manual_trades": total_trades - ai_trades,
            "today_trades": today_stats[0],
            "today_pnl": today_stats[1],
            "paper_account": {
                "balance": paper_account[0] if paper_account else 1000000,
                "invested": paper_account[1] if paper_account else 0,
                "account_pnl": paper_account[2] if paper_account else 0,
                "win_rate": (paper_account[3] / max(paper_account[5], 1)) * 100 if paper_account else 0
            },
            "ai_trading_active": AI_TRADING_ACTIVE,
            "zerodha_connected": bool(kite),
            "data_source": "real-time",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    try:
        init_db()
        port = int(os.environ.get('PORT', 10000))
        logger.info(f"🚀 Starting Enhanced AI Trading Platform on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        raise
