import pandas as pd
import numpy as np
from data_processing import time_to_minutes


def detect_all_conflicts(merged_df, blocks_df):
    """Detect conflicts grouped by block — one entry per block with all conflicting trains."""
    block_conflicts = {}  # block_id -> { type, severity, trains: set, description }

    _detect_block_conflicts(merged_df, block_conflicts)
    _detect_direction_conflicts(merged_df, block_conflicts)
    _detect_capacity_violations(merged_df, blocks_df, block_conflicts)

    # Convert to list format with one row per block, unique trains
    conflicts = []
    for i, (block_id, info) in enumerate(sorted(block_conflicts.items())):
        trains_list = sorted(list(info['trains']))
        conflicts.append({
            'conflict_id': f"C{i+1:03d}",
            'type': info['type'],
            'severity': info['severity'],
            'block_id': block_id,
            'trains': trains_list,
            'train_1': trains_list[0] if len(trains_list) > 0 else 0,
            'train_2': trains_list[1] if len(trains_list) > 1 else 0,
            'description': info['description'],
            'train_1_delay': info.get('train_1_delay', 0),
            'train_2_delay': info.get('train_2_delay', 0),
        })

    return conflicts


def _get_time_window(row):
    """Get arrival and departure time in minutes for a movement row."""
    arr = row.get('Scheduled_Arrival_Min', row.get('Actual_Arrival_Min', 0))
    dep = row.get('Scheduled_Departure_Min', row.get('Actual_Departure_Min', 0))
    if dep <= arr:
        dep = arr + row.get('Expected_Block_Time', 5)
    return float(arr), float(dep)


def _times_overlap(arr1, dep1, arr2, dep2):
    """Check if two time windows overlap."""
    return arr1 < dep2 and arr2 < dep1


def _detect_block_conflicts(merged_df, block_conflicts):
    """Detect block conflicts based on time overlap of trains with conflict_flag."""
    grouped = merged_df.groupby('Block_id')

    for block_id, group in grouped:
        conflict_rows = group[group['Conflict_flag'] == 1]
        if len(conflict_rows) <= 1:
            continue

        # Find trains with actual time overlaps
        overlapping_trains = set()
        rows_list = conflict_rows.to_dict('records')

        for i in range(len(rows_list)):
            arr_i, dep_i = _get_time_window(rows_list[i])
            for j in range(i + 1, len(rows_list)):
                if rows_list[i]['Train_ID'] == rows_list[j]['Train_ID']:
                    continue
                arr_j, dep_j = _get_time_window(rows_list[j])
                if _times_overlap(arr_i, dep_i, arr_j, dep_j):
                    overlapping_trains.add(int(rows_list[i]['Train_ID']))
                    overlapping_trains.add(int(rows_list[j]['Train_ID']))

        if overlapping_trains:
            if block_id in block_conflicts:
                block_conflicts[block_id]['trains'].update(overlapping_trains)
                if block_conflicts[block_id]['severity'] != 'CRITICAL':
                    block_conflicts[block_id]['severity'] = 'HIGH'
            else:
                trains_str = ', '.join(str(t) for t in sorted(overlapping_trains))
                block_conflicts[block_id] = {
                    'type': 'Block Conflict',
                    'severity': 'HIGH',
                    'trains': overlapping_trains,
                    'description': f"Trains {trains_str} have simultaneous time-overlap conflicts in block {block_id}",
                    'train_1_delay': 0,
                    'train_2_delay': 0,
                }


def _detect_direction_conflicts(merged_df, block_conflicts):
    """Detect direction conflicts on single-line blocks using time overlap."""
    if 'Direction' not in merged_df.columns:
        return

    grouped = merged_df.groupby('Block_id')
    for block_id, group in grouped:
        if 'Is_Single_Line' not in group.columns or group['Is_Single_Line'].iloc[0] != 1:
            continue

        up_rows = group[group['Direction'] == 'UP'].to_dict('records')
        down_rows = group[group['Direction'] == 'DOWN'].to_dict('records')

        if not up_rows or not down_rows:
            continue

        overlapping_trains = set()
        for ur in up_rows:
            arr_u, dep_u = _get_time_window(ur)
            for dr in down_rows:
                arr_d, dep_d = _get_time_window(dr)
                if _times_overlap(arr_u, dep_u, arr_d, dep_d):
                    overlapping_trains.add(int(ur['Train_ID']))
                    overlapping_trains.add(int(dr['Train_ID']))

        if overlapping_trains:
            trains_str = ', '.join(str(t) for t in sorted(overlapping_trains))
            if block_id in block_conflicts:
                block_conflicts[block_id]['trains'].update(overlapping_trains)
                block_conflicts[block_id]['severity'] = 'CRITICAL'
                block_conflicts[block_id]['type'] = 'Direction Conflict'
                block_conflicts[block_id]['description'] = f"Opposite direction trains ({trains_str}) on single-line block {block_id} with time overlap"
            else:
                block_conflicts[block_id] = {
                    'type': 'Direction Conflict',
                    'severity': 'CRITICAL',
                    'trains': overlapping_trains,
                    'description': f"Opposite direction trains ({trains_str}) on single-line block {block_id} with time overlap",
                    'train_1_delay': 0,
                    'train_2_delay': 0,
                }


def _detect_capacity_violations(merged_df, blocks_df, block_conflicts):
    """Detect capacity violations using time-window based occupancy count."""
    block_caps = dict(zip(blocks_df['Block_ID'], blocks_df['Loop_capacity']))

    grouped = merged_df.groupby('Block_id')
    for block_id, group in grouped:
        cap = block_caps.get(block_id, 1)
        occupied_rows = group[group['Block_occupied_flag'] == 1].to_dict('records')

        if len(occupied_rows) <= cap:
            continue

        # Find max concurrent occupancy using time overlap
        # Count how many trains overlap with each other at the same time
        overlapping_trains = set()
        for i in range(len(occupied_rows)):
            concurrent = {int(occupied_rows[i]['Train_ID'])}
            arr_i, dep_i = _get_time_window(occupied_rows[i])
            for j in range(len(occupied_rows)):
                if i == j:
                    continue
                arr_j, dep_j = _get_time_window(occupied_rows[j])
                if _times_overlap(arr_i, dep_i, arr_j, dep_j):
                    concurrent.add(int(occupied_rows[j]['Train_ID']))
            if len(concurrent) > cap:
                overlapping_trains.update(concurrent)

        if overlapping_trains:
            trains_str = ', '.join(str(t) for t in sorted(overlapping_trains))
            if block_id in block_conflicts:
                block_conflicts[block_id]['trains'].update(overlapping_trains)
                if block_conflicts[block_id]['severity'] != 'CRITICAL':
                    block_conflicts[block_id]['severity'] = 'HIGH'
            else:
                block_conflicts[block_id] = {
                    'type': 'Capacity Violation',
                    'severity': 'HIGH',
                    'trains': overlapping_trains,
                    'description': f"Block {block_id} has {len(overlapping_trains)} concurrent trains ({trains_str}) exceeding capacity of {cap}",
                    'train_1_delay': 0,
                    'train_2_delay': 0,
                }


def get_conflict_summary(conflicts):
    if not conflicts:
        return {'total': 0, 'by_type': {}, 'by_severity': {}, 'affected_blocks': [], 'affected_trains': []}

    df = pd.DataFrame(conflicts)
    affected_trains = set()
    for c in conflicts:
        for t in c.get('trains', []):
            affected_trains.add(t)
        affected_trains.add(c.get('train_1', 0))
        affected_trains.add(c.get('train_2', 0))
    affected_trains.discard(0)

    return {
        'total': len(conflicts),
        'by_type': df['type'].value_counts().to_dict(),
        'by_severity': df['severity'].value_counts().to_dict(),
        'affected_blocks': df['block_id'].unique().tolist(),
        'affected_trains': sorted(list(affected_trains)),
    }
