"""Check actual database schema"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Modules'))

from database import ado_connect

conn = ado_connect()
if conn:
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("=" * 70)
    print("DATABASE SCHEMA")
    print("=" * 70)
    
    for table in tables:
        table_name = table[0]
        print(f"\nTable: {table_name}")
        print("-" * 70)
        
        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        for col in columns:
            print(f"  {col[1]:20s} {col[2]:15s} {'NOT NULL' if col[3] else ''}")
        
        # Get sample count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"\n  Total records: {count}")
    
    cursor.close()
    conn.close()
