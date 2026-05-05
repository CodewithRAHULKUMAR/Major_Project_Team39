import pandas as pd
import numpy as np

# Priority order: Express(1) > Mail(1) > Passenger(2) > Freight(4)
# Lower number = higher priority
PRIORITY_LABELS = {1: 'Express/Mail', 2: 'Passenger', 3: 'Mixed', 4: 'Freight'}


def generate_recommendations(merged_df, conflicts, blocks_df, trains_df):
    recommendations = []
    rec_id = 1

    # Build a priority lookup
    train_priority = dict(zip(trains_df['Train_ID'], trains_df['Priority_level']))
    train_type = dict(zip(trains_df['Train_ID'], trains_df['Train_type']))
    train_speed = dict(zip(trains_df['Train_ID'], trains_df['Train_avg_speed_kmph']))

    for conflict in conflicts:
        recs = resolve_conflict(conflict, merged_df, blocks_df, trains_df,
                                train_priority, train_type, train_speed)
        for r in recs:
            r['rec_id'] = f"R{rec_id:03d}"
            rec_id += 1
            recommendations.append(r)

    # Additional recommendations for delayed trains not already covered
    delayed_trains = merged_df[merged_df.get('Predicted_Delay_Min', merged_df.get('Is_Delayed', 0)) == 1]
    if 'Predicted_Delay_Min' in merged_df.columns:
        delayed_trains = merged_df[merged_df['Predicted_Delay_Min'] > 1]

    for _, row in delayed_trains.drop_duplicates('Train_ID').head(20).iterrows():
        tid = int(row['Train_ID'])
        delay = float(row.get('Predicted_Delay_Min', row.get('Delay_at_exit_min', 0)))
        priority = int(row.get('Priority_level', 2))
        ttype = str(row.get('Train_type', 'Express'))

        already_covered = any(r['affected_trains'] and tid in r['affected_trains'] for r in recommendations)
        if already_covered:
            continue

        if priority <= 1 and delay > 2:
            recommendations.append({
                'rec_id': f"R{rec_id:03d}",
                'action': 'PRIORITIZE',
                'target_train': tid,
                'affected_trains': [tid],
                'explanation': f"Train {tid} ({ttype}, Priority {priority}) has {delay:.1f} min predicted delay. "
                               f"Prioritize this train to reduce cascade delays on the network.",
                'expected_impact': f"Reduce delay by ~{min(delay, 3):.0f} minutes for this express train",
                'severity': 'HIGH',
                'conflict_id': None,
                'status': 'pending'
            })
            rec_id += 1
        elif delay > 2:
            recommendations.append({
                'rec_id': f"R{rec_id:03d}",
                'action': 'PROCEED_WITH_CAUTION',
                'target_train': tid,
                'affected_trains': [tid],
                'explanation': f"Train {tid} ({ttype}, Priority {priority}) has {delay:.1f} min predicted delay. "
                               f"Allow proceed with monitoring.",
                'expected_impact': f"Maintain schedule, delay may reduce to ~{max(0, delay-1):.0f} min",
                'severity': 'MEDIUM',
                'conflict_id': None,
                'status': 'pending'
            })
            rec_id += 1

    return recommendations


def resolve_conflict(conflict, merged_df, blocks_df, trains_df,
                     train_priority, train_type, train_speed):
    recs = []
    ctype = conflict['type']
    block = conflict['block_id']

    # Get all conflicting trains from the conflict (not just train_1/train_2)
    all_trains = conflict.get('trains', [conflict['train_1'], conflict['train_2']])
    all_trains = [t for t in all_trains if t != 0]

    if len(all_trains) < 2:
        return recs

    # Sort trains by priority (lower = higher priority), then by speed (faster first)
    def sort_key(tid):
        p = train_priority.get(tid, 2)
        s = train_speed.get(tid, 60)
        return (p, -s)  # lower priority number first, then higher speed

    sorted_trains = sorted(all_trains, key=sort_key)

    # The highest-priority train proceeds, lowest-priority train gets detained
    proceed_train = sorted_trains[0]
    detain_train = sorted_trains[-1]

    proceed_type = train_type.get(proceed_train, 'Express')
    detain_type = train_type.get(detain_train, 'Freight')
    proceed_pri = train_priority.get(proceed_train, 1)
    detain_pri = train_priority.get(detain_train, 4)

    # Calculate actual delays from data
    proceed_delay = float(merged_df[merged_df['Train_ID'] == proceed_train]['Delay_at_exit_min'].mean()) \
        if len(merged_df[merged_df['Train_ID'] == proceed_train]) > 0 else 0
    detain_delay = float(merged_df[merged_df['Train_ID'] == detain_train]['Delay_at_exit_min'].mean()) \
        if len(merged_df[merged_df['Train_ID'] == detain_train]) > 0 else 0

    if ctype == 'Block Conflict':
        recs.append({
            'action': 'DETAIN',
            'target_train': detain_train,
            'proceed_train': proceed_train,
            'affected_trains': [proceed_train, detain_train],
            'explanation': f"Block conflict on {block} with {len(all_trains)} trains. "
                           f"Detain Train {detain_train} ({detain_type}, P{detain_pri}) and let "
                           f"Train {proceed_train} ({proceed_type}, P{proceed_pri}) proceed first. "
                           f"Express/higher-priority trains always get right of way.",
            'expected_impact': f"Train {proceed_train} delay reduced by ~{min(proceed_delay, 2):.1f} min. "
                               f"Train {detain_train} held ~3 min.",
            'severity': conflict['severity'],
            'conflict_id': conflict.get('conflict_id'),
            'status': 'pending'
        })

    elif ctype == 'Direction Conflict':
        block_info = blocks_df[blocks_df['Block_ID'] == block]
        has_loop = int(block_info['Has_loop_line'].iloc[0]) if len(block_info) > 0 else 0

        if has_loop:
            recs.append({
                'action': 'CROSSING',
                'target_train': detain_train,
                'proceed_train': proceed_train,
                'affected_trains': [proceed_train, detain_train],
                'explanation': f"Direction conflict on single-line block {block}. "
                               f"Train {proceed_train} ({proceed_type}, P{proceed_pri}) takes main line. "
                               f"Train {detain_train} ({detain_type}, P{detain_pri}) uses loop for crossing.",
                'expected_impact': f"Both trains cross safely. Train {proceed_train} minimal delay (~1 min). "
                                   f"Train {detain_train} held ~2-3 min at loop.",
                'severity': conflict['severity'],
                'conflict_id': conflict.get('conflict_id'),
                'status': 'pending'
            })
        else:
            recs.append({
                'action': 'DETAIN',
                'target_train': detain_train,
                'proceed_train': proceed_train,
                'affected_trains': [proceed_train, detain_train],
                'explanation': f"Direction conflict on single-line block {block} (no loop). "
                               f"Detain Train {detain_train} ({detain_type}, P{detain_pri}) at previous station "
                               f"until Train {proceed_train} ({proceed_type}, P{proceed_pri}) clears the block.",
                'expected_impact': f"Train {proceed_train} proceeds on time. "
                                   f"Train {detain_train} delayed ~5-8 min. Safety maintained.",
                'severity': conflict['severity'],
                'conflict_id': conflict.get('conflict_id'),
                'status': 'pending'
            })

    elif ctype == 'Capacity Violation':
        recs.append({
            'action': 'REGULATE',
            'target_train': detain_train,
            'proceed_train': proceed_train,
            'affected_trains': [proceed_train, detain_train],
            'explanation': f"Capacity exceeded on block {block} ({len(all_trains)} trains). "
                           f"Regulate entry: hold Train {detain_train} ({detain_type}, P{detain_pri}) "
                           f"until capacity frees. Train {proceed_train} ({proceed_type}, P{proceed_pri}) proceeds.",
            'expected_impact': f"Train {detain_train} waits ~3-5 min. Block congestion reduced.",
            'severity': conflict['severity'],
            'conflict_id': conflict.get('conflict_id'),
            'status': 'pending'
        })

    return recs


def get_train_recommendation(train_id, recommendations):
    return [r for r in recommendations if r.get('target_train') == train_id or
            (r.get('affected_trains') and train_id in r['affected_trains'])]
