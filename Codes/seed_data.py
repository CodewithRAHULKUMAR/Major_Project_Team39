"""
RailMind AI - Data Seeding Script
===================================
Imports data from Excel files into MySQL database.

Usage:
    python seed_data.py
"""

import pandas as pd
import mysql.connector
from mysql.connector import Error
from db_config import DB_CONFIG
import os
import sys


def get_connection():
    """Create database connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"[ERROR] Cannot connect to MySQL: {e}")
        print("\nPlease check:")
        print("  1. MySQL server is running")
        print("  2. Password in db_config.py is correct")
        print("  3. Database 'railmind_db' exists (run schema.sql first)")
        sys.exit(1)


def normalize_block_id(bid):
    """Normalize block ID (B9 -> B9, B01 -> B1)."""
    bid = str(bid).strip()
    if bid.upper().startswith('B'):
        num = bid[1:]
        try:
            return f"B{int(num)}"
        except:
            return bid
    return bid


def seed_all_data(conn, blocks_path, trains_path, movements_path):
    """Seed all tables in correct order with foreign key handling."""
    cursor = conn.cursor()
    
    # DISABLE foreign key checks
    print("\n[0/3] Disabling foreign key checks...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    
    try:
        # ============ BLOCKS ============
        print(f"\n[1/3] Loading blocks from {os.path.basename(blocks_path)}...")
        cursor.execute("TRUNCATE TABLE blocks_data")
        
        df = pd.read_excel(blocks_path)
        query = """
            INSERT INTO blocks_data 
            (Block_ID, From_point, To_point, Block_length_km, Line_type, Has_loop_line, Loop_capacity)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        count = 0
        for _, row in df.iterrows():
            values = (
                normalize_block_id(row['Block_ID']),
                str(row['From_point']),
                str(row['To_point']),
                int(row['Block_length_km']),
                str(row['Line_type']).upper(),
                int(row['Has_loop_line']),
                int(row['Loop_capacity'])
            )
            cursor.execute(query, values)
            count += 1
        conn.commit()
        print(f"      ✓ Inserted {count} blocks")
        
        # ============ TRAINS ============
        print(f"\n[2/3] Loading trains from {os.path.basename(trains_path)}...")
        cursor.execute("TRUNCATE TABLE trains_data")
        
        df = pd.read_excel(trains_path)
        query = """
            INSERT INTO trains_data 
            (Train_ID, Train_name, Train_type, Priority_level, Direction, Train_avg_speed_kmph, Max_dwell_time_min)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        count = 0
        for _, row in df.iterrows():
            values = (
                int(row['Train_ID']),
                str(row['Train_name']),
                str(row['Train_type']),
                int(row['Priority_level']),
                str(row['Direction']).upper(),
                int(row['Train_avg_speed_kmph']),
                int(row['Max_dwell_time_min'])
            )
            cursor.execute(query, values)
            count += 1
        conn.commit()
        print(f"      ✓ Inserted {count} trains")
        
        # ============ MOVEMENTS ============
        print(f"\n[3/3] Loading movements from {os.path.basename(movements_path)}...")
        cursor.execute("TRUNCATE TABLE train_movements")
        
        df = pd.read_excel(movements_path)
        query = """
            INSERT INTO train_movements 
            (Train_ID, Block_id, Delay_at_entry_min, Delay_at_exit_min, Block_occupied_flag,
             Conflict_flag, Action_taken, Remarks, Scheduled_Arrival_Time, Actual_Arrival_Time,
             Train_Status_When_Arrived, Scheduled_Departure_Time, Actual_Departure_Time, 
             Train_status_when_departed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        count = 0
        errors = 0
        
        for idx, row in df.iterrows():
            try:
                values = (
                    int(row['Train_ID']),
                    normalize_block_id(row['Block_id']),
                    int(row['Delay_at_entry_min']),
                    int(row['Delay_at_exit_min']),
                    int(row['Block_occupied_flag']),
                    int(row['Conflict_flag']),
                    str(row['Action_taken']).upper(),
                    str(row['Remarks']) if pd.notna(row['Remarks']) else None,
                    str(row['Scheduled_Arrival_Time']),
                    str(row['Actual_Arrival_Time']),
                    str(row['Train_Status_When_Arrived']) if pd.notna(row.get('Train_Status_When_Arrived')) else 'On Time',
                    str(row['Scheduled_Departure_Time']),
                    str(row['Actual_Departure_Time']),
                    str(row['Train_status_when_departed']) if pd.notna(row.get('Train_status_when_departed')) else 'On Time'
                )
                cursor.execute(query, values)
                count += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"      Warning row {idx}: {e}")
        
        conn.commit()
        print(f"      ✓ Inserted {count} movements ({errors} errors)")
        
    finally:
        # RE-ENABLE foreign key checks
        print("\n[✓] Re-enabling foreign key checks...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    
    return True


def verify_data(conn):
    """Verify data was inserted correctly."""
    print("\n" + "=" * 50)
    print("VERIFICATION")
    print("=" * 50)
    
    cursor = conn.cursor()
    
    tables = ['blocks_data', 'trains_data', 'train_movements']
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   {table}: {count} records")
    
    # Show conflicts
    cursor.execute("SELECT COUNT(*) FROM train_movements WHERE Conflict_flag = 1")
    conflicts = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM train_movements")
    total = cursor.fetchone()[0]
    if total > 0:
        print(f"\n   Conflicts: {conflicts}/{total} ({conflicts*100/total:.1f}%)")
    
    cursor.close()


def main():
    print("=" * 50)
    print("RailMind AI - Database Seeding")
    print("=" * 50)
    
    # Check for Excel files
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    
    files = {
        'blocks': os.path.join(data_dir, 'Blocks_Data.xlsx'),
        'trains': os.path.join(data_dir, 'Trains_Data.xlsx'),
        'movements': os.path.join(data_dir, 'Train_Movements_Balanced.xlsx')
    }
    
    missing = [f for f in files.values() if not os.path.exists(f)]
    if missing:
        print("\n[ERROR] Missing Excel files!")
        print("\nPlease copy these files to the 'data' folder:")
        for f in missing:
            print(f"   - {os.path.basename(f)}")
        print(f"\nExpected location: {data_dir}")
        sys.exit(1)
    
    # Connect to database
    conn = get_connection()
    print(f"\n✓ Connected to MySQL ({DB_CONFIG['host']})")
    
    try:
        # Seed all data
        seed_all_data(conn, files['blocks'], files['trains'], files['movements'])
        
        # Verify
        verify_data(conn)
        
        print("\n" + "=" * 50)
        print("✓ DATABASE SEEDING COMPLETE!")
        print("=" * 50)
        print("\nYou can now run: python app.py")
        
    except Exception as e:
        print(f"\n[ERROR] Seeding failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
