"""
RailMind AI - Flask Application (MySQL Version)
================================================
This version loads data from MySQL database instead of Excel files.
"""

import os
import json
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify, session

# Database import (NEW - replaces Excel reading)
from database import init_database, load_blocks_data, load_trains_data, load_train_movements, check_data_exists

from data_processing import validate_datasets, clean_data, engineer_features, get_summary_stats
from ml_engine import train_models, predict_single, predict_all, FEATURE_COLS
from conflict_detection import detect_all_conflicts, get_conflict_summary
from recommendation_engine import generate_recommendations, get_train_recommendation
from simulation_engine import simulate_decision, run_whatif, get_performance_kpis

app = Flask(__name__)
app.secret_key = 'railway_ai_system_2024'
app.config['JSON_SORT_KEYS'] = False
os.makedirs('models', exist_ok=True)

# Global state
STATE = {
    'blocks_df': None,
    'movements_df': None,
    'trains_df': None,
    'merged_df': None,
    'conflicts': [],
    'recommendations': [],
    'model_metrics': None,
    'decisions': {},
    'data_loaded': False,
    'models_trained': False,
    'summary': None,
}


# ============ AUTO-LOAD DATA FROM MYSQL ============
def auto_load_data():
    """Load and process data from MySQL database."""
    print("[RailMind] Initializing database connection...")
    
    # Initialize database connection
    if not init_database():
        print("[RailMind] ERROR: Database connection failed!")
        print("           Please check db_config.py and ensure MySQL is running.")
        return
    
    # Check if data exists
    if not check_data_exists():
        print("[RailMind] WARNING: No data in database!")
        print("           Please run: python seed_data.py")
        return
    
    print("[RailMind] Loading data from MySQL database...")
    
    # Load data from MySQL (instead of Excel)
    blocks_df = load_blocks_data()
    trains_df = load_trains_data()
    movements_df = load_train_movements()
    
    print(f"[RailMind] Loaded: {len(blocks_df)} blocks, {len(trains_df)} trains, {len(movements_df)} movements")
    
    # Validate
    errors, warnings = validate_datasets(blocks_df, movements_df, trains_df)
    if errors:
        print(f"[RailMind] Validation errors: {errors}")
        return
    
    # Clean and engineer features
    blocks_df, movements_df, trains_df = clean_data(blocks_df, movements_df, trains_df)
    merged_df = engineer_features(blocks_df, movements_df, trains_df)
    summary = get_summary_stats(blocks_df, movements_df, trains_df)
    
    STATE['blocks_df'] = blocks_df
    STATE['movements_df'] = movements_df
    STATE['trains_df'] = trains_df
    STATE['merged_df'] = merged_df
    STATE['summary'] = summary
    STATE['data_loaded'] = True
    
    # Train ML models
    print("[RailMind] Training ML models...")
    model_metrics = train_models(merged_df)
    STATE['model_metrics'] = model_metrics
    STATE['models_trained'] = True
    
    # Predict
    merged_df = predict_all(merged_df)
    STATE['merged_df'] = merged_df
    
    # Detect conflicts
    print("[RailMind] Detecting conflicts...")
    conflicts = detect_all_conflicts(merged_df, blocks_df)
    STATE['conflicts'] = conflicts
    
    # Generate recommendations
    print("[RailMind] Generating recommendations...")
    recommendations = generate_recommendations(merged_df, conflicts, blocks_df, trains_df)
    STATE['recommendations'] = recommendations
    
    print(f"[RailMind] ✓ System ready — {len(blocks_df)} blocks, {len(trains_df)} trains, "
          f"{len(movements_df)} movements, {len(conflicts)} conflicts, {len(recommendations)} recommendations")
    if warnings:
        print(f"[RailMind] Warnings: {warnings}")


# Run auto-load
auto_load_data()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/init')
def init_data():
    """Return initial system state — called by frontend on page load."""
    if not STATE['data_loaded']:
        return jsonify({'success': False, 'error': 'Data not loaded. Check database connection.'}), 500

    return jsonify({
        'success': True,
        'summary': STATE['summary'],
        'model_metrics': STATE['model_metrics'],
        'conflicts_count': len(STATE['conflicts']),
        'recommendations_count': len(STATE['recommendations']),
    })


@app.route('/api/network')
def network_overview():
    if not STATE['data_loaded']:
        return jsonify({'success': False, 'error': 'No data loaded'}), 400

    blocks = STATE['blocks_df'].to_dict('records')
    merged = STATE['merged_df']

    # Build a conflict lookup: which blocks have detected conflicts and which trains
    block_conflict_trains = {}
    block_conflict_severity = {}
    for c in STATE.get('conflicts', []):
        bid = c.get('block_id', '')
        sev = c.get('severity', 'LOW')
        if bid not in block_conflict_trains:
            block_conflict_trains[bid] = set()
        block_conflict_trains[bid].add(c['train_1'])
        block_conflict_trains[bid].add(c['train_2'])
        if bid not in block_conflict_severity or sev == 'CRITICAL':
            block_conflict_severity[bid] = sev

    block_status = {}
    for _, row in STATE['blocks_df'].iterrows():
        bid = row['Block_ID']
        block_movements = merged[merged['Block_id'] == bid]

        # All unique trains that traverse this block (from actual movement data)
        all_trains_in_block = block_movements['Train_ID'].unique().tolist()
        all_trains_in_block = [int(t) for t in all_trains_in_block]

        conflict_train_ids = list(block_conflict_trains.get(bid, set()))
        n_conflicts = len(conflict_train_ids)
        severity = block_conflict_severity.get(bid)

        # Status logic based on conflicts and occupancy
        if severity == 'CRITICAL':
            status = 'conflict'
        elif severity == 'HIGH' and n_conflicts >= 4:
            status = 'conflict'
        elif n_conflicts > 0:
            status = 'occupied'
        elif len(all_trains_in_block) > 0:
            status = 'occupied'
        else:
            status = 'free'

        block_status[bid] = {
            'status': status,
            'trains': all_trains_in_block,
            'occupied_count': len(all_trains_in_block),
            'conflict_count': n_conflicts,
            'from': row['From_point'],
            'to': row['To_point'],
            'length': float(row['Block_length_km']),
            'line_type': row['Line_type'],
            'has_loop': int(row['Has_loop_line']),
        }

    return jsonify({'success': True, 'blocks': blocks, 'block_status': block_status})


@app.route('/api/trains')
def get_trains():
    if not STATE['data_loaded']:
        return jsonify({'success': False, 'error': 'No data loaded'}), 400

    trains = STATE['trains_df'].to_dict('records')
    for t in trains:
        t['Train_ID'] = int(t['Train_ID'])
    return jsonify({'success': True, 'trains': trains})


@app.route('/api/train/<int:train_id>')
def get_train_analysis(train_id):
    if not STATE['data_loaded']:
        return jsonify({'success': False, 'error': 'No data loaded'}), 400

    merged = STATE['merged_df']
    train_data = merged[merged['Train_ID'] == train_id]

    if len(train_data) == 0:
        return jsonify({'success': False, 'error': f'Train {train_id} not found'}), 404

    train_info = STATE['trains_df'][STATE['trains_df']['Train_ID'] == train_id]
    info = train_info.iloc[0].to_dict() if len(train_info) > 0 else {}
    info['Train_ID'] = int(info.get('Train_ID', train_id))

    row = train_data.iloc[0]
    my_priority = int(row.get('Priority_level', 2))
    my_type = str(row.get('Train_type', ''))
    my_dir = str(row.get('Direction', ''))

    prediction = {
        'is_delayed': int(row.get('Predicted_Delayed', row.get('Is_Delayed', 0))),
        'predicted_delay_min': round(float(row.get('Predicted_Delay_Min', row.get('Delay_at_exit_min', 0))), 2),
        'delay_status': str(row.get('Delay_Status', 'Unknown')),
    }

    # Build train priority/type lookups
    train_priority = dict(zip(STATE['trains_df']['Train_ID'], STATE['trains_df']['Priority_level']))
    train_type_map = dict(zip(STATE['trains_df']['Train_ID'], STATE['trains_df']['Train_type']))
    train_speed_map = dict(zip(STATE['trains_df']['Train_ID'], STATE['trains_df']['Train_avg_speed_kmph']))
    train_dir_map = dict(zip(STATE['trains_df']['Train_ID'], STATE['trains_df']['Direction']))

    # ---------- Build movements + conflicts from ACTUAL data flags ----------
    train_conflicts = []
    movements = []
    rec_id = 1

    for _, trow in train_data.iterrows():
        block_id = trow['Block_id']
        has_conflict_flag = int(trow.get('Conflict_flag', 0)) == 1
        is_single = int(trow.get('Is_Single_Line', 0))
        has_loop = int(trow.get('Has_loop_line', 0))

        # Find other trains in this block that ALSO have conflict flags
        conflicting_tids = []
        if has_conflict_flag:
            same_block_conflicts = merged[
                (merged['Block_id'] == block_id) &
                (merged['Train_ID'] != train_id) &
                (merged['Conflict_flag'] == 1)
            ]
            conflicting_tids = [int(t) for t in same_block_conflicts['Train_ID'].unique()]

        # Determine action
        if has_conflict_flag and conflicting_tids:
            higher_priority_exists = any(
                int(train_priority.get(t, 2)) < my_priority for t in conflicting_tids
            )
            opposite_dir_exists = any(
                str(train_dir_map.get(t, '')) != my_dir for t in conflicting_tids
            ) if is_single else False

            if higher_priority_exists:
                computed_action = 'HOLD'
            elif is_single and opposite_dir_exists and has_loop:
                computed_action = 'CROSSING'
            elif is_single and opposite_dir_exists and not has_loop:
                computed_action = 'HOLD'
            elif len(conflicting_tids) > 3:
                computed_action = 'REGULATE'
            else:
                computed_action = 'PROCEED_WITH_CAUTION'
        elif has_conflict_flag:
            computed_action = 'PROCEED_WITH_CAUTION'
        else:
            computed_action = 'PROCEED'

        movements.append({
            'Block_id': block_id,
            'Delay_at_entry_min': float(trow['Delay_at_entry_min']),
            'Delay_at_exit_min': float(trow['Delay_at_exit_min']),
            'Block_occupied_flag': int(trow.get('Block_occupied_flag', 0)),
            'Conflict_flag': 1 if (has_conflict_flag and conflicting_tids) else 0,
            'Action_taken': computed_action,
            'Scheduled_Arrival_Time': trow['Scheduled_Arrival_Time'],
            'Actual_Arrival_Time': trow['Actual_Arrival_Time'],
            'conflicting_trains': conflicting_tids,
        })

        # Add conflict entry for this block
        if has_conflict_flag and conflicting_tids:
            opposite_dir_exists = any(
                str(train_dir_map.get(t, '')) != my_dir for t in conflicting_tids
            ) if is_single else False

            if is_single and opposite_dir_exists:
                ctype = 'Direction Conflict'
                severity = 'CRITICAL'
            elif len(conflicting_tids) > 2:
                ctype = 'Block Conflict'
                severity = 'HIGH'
            else:
                ctype = 'Block Conflict'
                severity = 'MEDIUM'

            trains_str = ', '.join(str(t) for t in conflicting_tids[:5])
            train_conflicts.append({
                'type': ctype,
                'severity': severity,
                'block_id': block_id,
                'train_1': train_id,
                'train_2': conflicting_tids[0] if conflicting_tids else 0,
                'trains': conflicting_tids,
                'description': f"Train {train_id} conflicts with trains {trains_str} in block {block_id}",
            })

    # ---------- Generate one AI recommendation per conflict ----------
    train_recs = []
    for conflict in train_conflicts:
        block_id = conflict['block_id']
        ctype = conflict['type']
        severity = conflict['severity']
        conflicting_tids = conflict['trains']

        # Find the block info
        block_info = STATE['blocks_df'][STATE['blocks_df']['Block_ID'] == block_id]
        is_single = int(block_info['Is_Single_Line'].iloc[0]) if 'Is_Single_Line' in block_info.columns else \
            int(block_info['Line_type'].iloc[0] == 'SINGLE') if len(block_info) > 0 else 0
        has_loop = int(block_info['Has_loop_line'].iloc[0]) if len(block_info) > 0 else 0

        # Sort conflicting trains by priority to decide who proceeds / who is detained
        def sort_key(tid):
            return (int(train_priority.get(tid, 2)), -int(train_speed_map.get(tid, 60)))

        all_involved = [train_id] + conflicting_tids
        sorted_trains = sorted(all_involved, key=sort_key)
        proceed_train = sorted_trains[0]
        detain_train = sorted_trains[-1]

        proceed_type = str(train_type_map.get(proceed_train, 'Express'))
        detain_type = str(train_type_map.get(detain_train, 'Freight'))
        proceed_pri = int(train_priority.get(proceed_train, 1))
        detain_pri = int(train_priority.get(detain_train, 4))

        if ctype == 'Direction Conflict' and has_loop:
            action = 'CROSSING'
            explanation = (f"Direction conflict on single-line block {block_id}. "
                          f"Train {proceed_train} ({proceed_type}, P{proceed_pri}) takes main line. "
                          f"Train {detain_train} ({detain_type}, P{detain_pri}) uses loop for safe crossing.")
            impact = (f"Both trains cross safely. Train {proceed_train} minimal delay (~1 min). "
                     f"Train {detain_train} held ~2-3 min at loop.")
        elif ctype == 'Direction Conflict' and not has_loop:
            action = 'DETAIN'
            explanation = (f"Direction conflict on single-line block {block_id} (no loop line). "
                          f"Detain Train {detain_train} ({detain_type}, P{detain_pri}) at previous station "
                          f"until Train {proceed_train} ({proceed_type}, P{proceed_pri}) clears the block.")
            impact = (f"Train {proceed_train} proceeds on time. "
                     f"Train {detain_train} delayed ~5-8 min. Safety maintained.")
        elif severity == 'HIGH':
            action = 'REGULATE'
            explanation = (f"Heavy congestion on block {block_id} with {len(all_involved)} trains. "
                          f"Regulate entry: hold Train {detain_train} ({detain_type}, P{detain_pri}) "
                          f"until block clears. Train {proceed_train} ({proceed_type}, P{proceed_pri}) proceeds.")
            impact = f"Train {detain_train} waits ~3-5 min. Block congestion reduced."
        else:
            action = 'DETAIN'
            explanation = (f"Block conflict on {block_id}. "
                          f"Detain Train {detain_train} ({detain_type}, P{detain_pri}) and let "
                          f"Train {proceed_train} ({proceed_type}, P{proceed_pri}) proceed first.")
            impact = (f"Train {proceed_train} delay reduced. "
                     f"Train {detain_train} held ~3 min.")

        train_recs.append({
            'rec_id': f"R{rec_id:03d}",
            'action': action,
            'target_train': detain_train,
            'proceed_train': proceed_train,
            'affected_trains': [proceed_train, detain_train],
            'explanation': explanation,
            'expected_impact': impact,
            'severity': severity,
            'conflict_id': conflict.get('conflict_id'),
            'status': 'pending',
        })
        rec_id += 1

    return jsonify({
        'success': True,
        'info': info,
        'prediction': prediction,
        'conflicts': train_conflicts,
        'recommendations': train_recs,
        'movements': movements,
    })


@app.route('/api/conflicts')
def get_conflicts():
    if not STATE['data_loaded']:
        return jsonify({'success': False, 'error': 'No data loaded'}), 400

    summary = get_conflict_summary(STATE['conflicts'])
    return jsonify({'success': True, 'conflicts': STATE['conflicts'], 'summary': summary})


@app.route('/api/recommendations')
def get_recommendations():
    if not STATE['data_loaded']:
        return jsonify({'success': False, 'error': 'No data loaded'}), 400
    return jsonify({'success': True, 'recommendations': STATE['recommendations']})


@app.route('/api/decide', methods=['POST'])
def make_decision():
    if not STATE['data_loaded']:
        return jsonify({'success': False, 'error': 'No data loaded'}), 400

    data = request.json
    rec_id = data.get('rec_id')
    action = data.get('action')  # 'accept' or 'reject'
    alternative = data.get('alternative')

    rec = next((r for r in STATE['recommendations'] if r['rec_id'] == rec_id), None)
    if not rec:
        return jsonify({'success': False, 'error': 'Recommendation not found'}), 404

    result = simulate_decision(rec, action, STATE['merged_df'], alternative)
    rec['status'] = 'accepted' if action == 'accept' else 'rejected'
    STATE['decisions'][rec_id] = result

    return jsonify({'success': True, 'result': result})


@app.route('/api/whatif', methods=['POST'])
def whatif():
    if not STATE['data_loaded']:
        return jsonify({'success': False, 'error': 'No data loaded'}), 400

    scenario = request.json
    result = run_whatif(STATE['merged_df'], scenario)
    return jsonify({'success': True, 'result': result})


@app.route('/api/performance')
def performance():
    if not STATE['data_loaded']:
        return jsonify({'success': False, 'error': 'No data loaded'}), 400

    kpis = get_performance_kpis(STATE['merged_df'])
    kpis['model_metrics'] = STATE.get('model_metrics', {})
    return jsonify({'success': True, 'kpis': kpis})


@app.route('/api/status')
def system_status():
    return jsonify({
        'data_loaded': STATE['data_loaded'],
        'models_trained': STATE['models_trained'],
        'total_conflicts': len(STATE['conflicts']),
        'total_recommendations': len(STATE['recommendations']),
        'decisions_made': len(STATE['decisions']),
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
