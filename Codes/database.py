"""
RailMind AI - Database Module
==============================
Provides MySQL database connection and data loading functions.
This replaces pd.read_excel() calls with database queries.
"""

import mysql.connector
from mysql.connector import pooling, Error
import pandas as pd
from db_config import DB_CONFIG

# Connection pool
_pool = None


def get_connection_pool():
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="railmind_pool",
            pool_size=5,
            **DB_CONFIG
        )
        print("[DB] Connection pool created")
    return _pool


def get_connection():
    """Get a connection from the pool."""
    return get_connection_pool().get_connection()


def init_database():
    """Initialize database connection (call at startup)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        print("[DB] ✓ Database connection successful")
        return True
    except Error as e:
        print(f"[DB] ✗ Database connection failed: {e}")
        return False


# ============================================
# DATA LOADING FUNCTIONS
# These replace pd.read_excel() calls
# ============================================

def load_blocks_data():
    """Load blocks_data from MySQL. Returns DataFrame."""
    query = """
        SELECT Block_ID, From_point, To_point, Block_length_km, 
               Line_type, Has_loop_line, Loop_capacity
        FROM blocks_data
        ORDER BY Block_ID
    """
    conn = get_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def load_trains_data():
    """Load trains_data from MySQL. Returns DataFrame."""
    query = """
        SELECT Train_ID, Train_name, Train_type, Priority_level, 
               Direction, Train_avg_speed_kmph, Max_dwell_time_min
        FROM trains_data
        ORDER BY Train_ID
    """
    conn = get_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def load_train_movements():
    """Load train_movements from MySQL. Returns DataFrame."""
    query = """
        SELECT Train_ID, Block_id, Delay_at_entry_min, Delay_at_exit_min,
               Block_occupied_flag, Conflict_flag, Action_taken, Remarks,
               Scheduled_Arrival_Time, Actual_Arrival_Time, Train_Status_When_Arrived,
               Scheduled_Departure_Time, Actual_Departure_Time, Train_status_when_departed
        FROM train_movements
        ORDER BY id
    """
    conn = get_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def check_data_exists():
    """Check if data exists in database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM blocks_data")
        blocks_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM trains_data")
        trains_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM train_movements")
        movements_count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return blocks_count > 0 and trains_count > 0 and movements_count > 0
    except:
        return False


def get_data_counts():
    """Get record counts from each table."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        counts = {}
        for table in ['blocks_data', 'trains_data', 'train_movements']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        return counts
    except Exception as e:
        return {'error': str(e)}


# ============================================
# TEST FUNCTION
# ============================================

if __name__ == "__main__":
    print("Testing database connection...")
    
    if init_database():
        counts = get_data_counts()
        print(f"Data counts: {counts}")
        
        if check_data_exists():
            print("\n✓ Loading sample data...")
            blocks = load_blocks_data()
            print(f"  Blocks: {len(blocks)} rows")
            
            trains = load_trains_data()
            print(f"  Trains: {len(trains)} rows")
            
            movements = load_train_movements()
            print(f"  Movements: {len(movements)} rows")
            
            print("\n✓ All tests passed!")
        else:
            print("\n⚠ No data found. Run seed_data.py first.")
    else:
        print("\n✗ Connection test failed. Check db_config.py")
