import pandas as pd
import numpy as np
from datetime import datetime


def time_to_minutes(t):
    if pd.isna(t):
        return 0
    try:
        parts = str(t).strip().split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except:
        return 0


def validate_datasets(blocks_df, movements_df, trains_df):
    errors = []
    warnings = []

    req_blocks = ['Block_ID', 'From_point', 'To_point', 'Block_length_km', 'Line_type', 'Has_loop_line', 'Loop_capacity']
    req_trains = ['Train_ID', 'Train_name', 'Train_type', 'Priority_level', 'Direction', 'Train_avg_speed_kmph', 'Max_dwell_time_min']
    req_movements = ['Train_ID', 'Block_id', 'Delay_at_entry_min', 'Delay_at_exit_min', 'Block_occupied_flag',
                     'Conflict_flag', 'Action_taken', 'Scheduled_Arrival_Time', 'Actual_Arrival_Time',
                     'Scheduled_Departure_Time', 'Actual_Departure_Time']

    for col in req_blocks:
        if col not in blocks_df.columns:
            errors.append(f"Missing column in Blocks: {col}")
    for col in req_trains:
        if col not in trains_df.columns:
            errors.append(f"Missing column in Trains: {col}")
    for col in req_movements:
        if col not in movements_df.columns:
            errors.append(f"Missing column in Movements: {col}")

    if blocks_df.isnull().any().any():
        warnings.append("Blocks data has missing values — will be filled")
    if trains_df.isnull().any().any():
        warnings.append("Trains data has missing values — will be filled")
    if movements_df.isnull().any().any():
        warnings.append("Movements data has missing values — will be filled")

    return errors, warnings


def clean_data(blocks_df, movements_df, trains_df):
    blocks_df = blocks_df.copy()
    movements_df = movements_df.copy()
    trains_df = trains_df.copy()

    # Normalize Block IDs so they match between datasets
    # e.g. movements might have 'B1' while blocks has 'B01'
    def normalize_block_id(bid):
        bid = str(bid).strip()
        # Extract the numeric part after 'B'
        if bid.upper().startswith('B'):
            num_part = bid[1:]
            try:
                return f"B{int(num_part)}"
            except ValueError:
                return bid
        return bid

    blocks_df['Block_ID'] = blocks_df['Block_ID'].apply(normalize_block_id)
    movements_df['Block_id'] = movements_df['Block_id'].apply(normalize_block_id)

    blocks_df['Block_length_km'] = pd.to_numeric(blocks_df['Block_length_km'], errors='coerce').fillna(blocks_df['Block_length_km'].median())
    blocks_df['Has_loop_line'] = blocks_df['Has_loop_line'].fillna(0).astype(int)
    blocks_df['Loop_capacity'] = blocks_df['Loop_capacity'].fillna(1).astype(int)
    blocks_df['Line_type'] = blocks_df['Line_type'].fillna('SINGLE')

    trains_df['Priority_level'] = pd.to_numeric(trains_df['Priority_level'], errors='coerce').fillna(2).astype(int)
    trains_df['Train_avg_speed_kmph'] = pd.to_numeric(trains_df['Train_avg_speed_kmph'], errors='coerce').fillna(60)
    trains_df['Max_dwell_time_min'] = pd.to_numeric(trains_df['Max_dwell_time_min'], errors='coerce').fillna(3).astype(int)
    trains_df['Direction'] = trains_df['Direction'].fillna('DOWN')
    trains_df['Train_type'] = trains_df['Train_type'].fillna('Express')

    movements_df['Delay_at_entry_min'] = pd.to_numeric(movements_df['Delay_at_entry_min'], errors='coerce').fillna(0)
    movements_df['Delay_at_exit_min'] = pd.to_numeric(movements_df['Delay_at_exit_min'], errors='coerce').fillna(0)
    movements_df['Block_occupied_flag'] = movements_df['Block_occupied_flag'].fillna(0).astype(int)
    movements_df['Conflict_flag'] = movements_df['Conflict_flag'].fillna(0).astype(int)
    movements_df['Action_taken'] = movements_df['Action_taken'].fillna('PROCEED')

    return blocks_df, movements_df, trains_df


def engineer_features(blocks_df, movements_df, trains_df):
    merged = movements_df.merge(trains_df, on='Train_ID', how='left')
    merged = merged.merge(blocks_df, left_on='Block_id', right_on='Block_ID', how='left')

    merged['Scheduled_Arrival_Min'] = merged['Scheduled_Arrival_Time'].apply(time_to_minutes)
    merged['Actual_Arrival_Min'] = merged['Actual_Arrival_Time'].apply(time_to_minutes)
    merged['Scheduled_Departure_Min'] = merged['Scheduled_Departure_Time'].apply(time_to_minutes)
    merged['Actual_Departure_Min'] = merged['Actual_Departure_Time'].apply(time_to_minutes)

    merged['Arrival_Delay'] = merged['Actual_Arrival_Min'] - merged['Scheduled_Arrival_Min']
    merged['Departure_Delay'] = merged['Actual_Departure_Min'] - merged['Scheduled_Departure_Min']
    merged['Dwell_Time'] = merged['Actual_Departure_Min'] - merged['Actual_Arrival_Min']
    merged['Dwell_Time'] = merged['Dwell_Time'].clip(lower=0)

    merged['Delay_Increase'] = merged['Delay_at_exit_min'] - merged['Delay_at_entry_min']
    merged['Is_Delayed'] = (merged['Delay_at_exit_min'] > 0).astype(int)
    merged['Is_Single_Line'] = (merged['Line_type'] == 'SINGLE').astype(int)

    merged['Speed_Block_Ratio'] = merged['Train_avg_speed_kmph'] / merged['Block_length_km'].replace(0, 1)
    merged['Expected_Block_Time'] = (merged['Block_length_km'] / merged['Train_avg_speed_kmph'].replace(0, 60)) * 60

    merged['Is_Express'] = (merged['Train_type'] == 'Express').astype(int)
    merged['Is_Freight'] = (merged['Train_type'] == 'Freight').astype(int)
    merged['Is_Passenger'] = (merged['Train_type'] == 'Passenger').astype(int)
    merged['Is_UP'] = (merged['Direction'] == 'UP').astype(int)

    merged['Hour_of_Day'] = (merged['Scheduled_Arrival_Min'] // 60).clip(0, 23).astype(int)
    merged['Is_Peak_Hour'] = merged['Hour_of_Day'].apply(lambda h: 1 if h in [7,8,9,17,18,19] else 0)

    merged['Priority_Speed_Score'] = merged['Priority_level'] * merged['Train_avg_speed_kmph'] / 100
    merged['Congestion_Score'] = merged['Block_occupied_flag'] + merged['Conflict_flag'] + merged['Is_Single_Line']

    return merged


def get_summary_stats(blocks_df, movements_df, trains_df):
    stats = {
        'total_blocks': len(blocks_df),
        'total_trains': len(trains_df),
        'total_movements': len(movements_df),
        'avg_block_length': round(blocks_df['Block_length_km'].mean(), 1),
        'single_line_blocks': int((blocks_df['Line_type'] == 'SINGLE').sum()),
        'double_line_blocks': int((blocks_df['Line_type'] == 'DOUBLE').sum()),
        'loop_blocks': int(blocks_df['Has_loop_line'].sum()),
        'express_trains': int((trains_df['Train_type'] == 'Express').sum()),
        'passenger_trains': int((trains_df['Train_type'] == 'Passenger').sum()),
        'freight_trains': int((trains_df['Train_type'] == 'Freight').sum()),
        'up_trains': int((trains_df['Direction'] == 'UP').sum()),
        'down_trains': int((trains_df['Direction'] == 'DOWN').sum()),
        'conflict_movements': int(movements_df['Conflict_flag'].sum()),
        'occupied_movements': int(movements_df['Block_occupied_flag'].sum()),
        'avg_entry_delay': round(movements_df['Delay_at_entry_min'].mean(), 2),
        'avg_exit_delay': round(movements_df['Delay_at_exit_min'].mean(), 2),
        'max_delay': int(movements_df['Delay_at_exit_min'].max()),
        'on_time_pct': round((movements_df['Delay_at_exit_min'] <= 0).sum() / len(movements_df) * 100, 1),
    }
    return stats
