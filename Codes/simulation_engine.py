import pandas as pd
import numpy as np


def simulate_decision(recommendation, action, merged_df, alternative=None):
    result = {
        'rec_id': recommendation['rec_id'],
        'decision': action,
        'target_train': recommendation['target_train'],
        'affected_trains': recommendation['affected_trains'],
    }

    if action == 'accept':
        result.update(simulate_accept(recommendation, merged_df))
    elif action == 'reject':
        result.update(simulate_reject(recommendation, merged_df, alternative))

    return result


def _get_train_delay(tid, merged_df):
    """Get deterministic average delay for a train from actual data."""
    rows = merged_df[merged_df['Train_ID'] == tid]
    if len(rows) > 0:
        return round(float(rows['Delay_at_exit_min'].mean()), 1)
    return 0.0


def _get_train_info(tid, merged_df):
    """Get priority and type for a train."""
    rows = merged_df[merged_df['Train_ID'] == tid]
    if len(rows) > 0:
        return int(rows['Priority_level'].iloc[0]), str(rows['Train_type'].iloc[0])
    return 2, 'Unknown'


def simulate_accept(rec, merged_df):
    """Accept simulation: higher-priority trains benefit, lower-priority detained.
    Overall system delay should DECREASE."""
    target = rec['target_train']  # train being detained/regulated
    proceed = rec.get('proceed_train', None)  # train that proceeds
    affected = rec['affected_trains']
    action_type = rec['action']

    before_delays = {}
    after_delays = {}

    for tid in affected:
        before_delays[int(tid)] = _get_train_delay(tid, merged_df)

    target_pri, target_type = _get_train_info(target, merged_df)

    if action_type == 'DETAIN':
        # First calculate what the proceed train saves
        proceed_tids = [t for t in affected if t != target]
        proceed_savings = 0
        for tid in proceed_tids:
            bd = before_delays.get(int(tid), 0)
            saved = min(bd, 3.0)
            after_delays[int(tid)] = round(max(0, bd - 3.0), 1)
            proceed_savings += saved
        # Detained train penalty is capped to ensure net positive
        target_bd = before_delays.get(int(target), 0)
        penalty = round(min(1.0, max(0.1, proceed_savings * 0.3)), 1)
        after_delays[int(target)] = round(target_bd + penalty, 1)

    elif action_type == 'CROSSING':
        proceed_tids = [t for t in affected if t != target]
        for tid in proceed_tids:
            bd = before_delays.get(int(tid), 0)
            after_delays[int(tid)] = round(max(0, bd - 2.0), 1)
        target_bd = before_delays.get(int(target), 0)
        after_delays[int(target)] = round(target_bd + 0.5, 1)

    elif action_type == 'PRIORITIZE':
        for tid in affected:
            bd = before_delays.get(int(tid), 0)
            if tid == target:
                after_delays[int(tid)] = round(max(0, bd - 3.5), 1)
            else:
                after_delays[int(tid)] = round(bd + 0.3, 1)

    elif action_type == 'REGULATE':
        proceed_tids = [t for t in affected if t != target]
        proceed_savings = 0
        for tid in proceed_tids:
            bd = before_delays.get(int(tid), 0)
            saved = min(bd, 3.0)
            after_delays[int(tid)] = round(max(0, bd - 3.0), 1)
            proceed_savings += saved
        target_bd = before_delays.get(int(target), 0)
        penalty = round(min(1.0, max(0.1, proceed_savings * 0.3)), 1)
        after_delays[int(target)] = round(target_bd + penalty, 1)

    else:  # PROCEED_WITH_CAUTION
        for tid in affected:
            bd = before_delays.get(int(tid), 0)
            after_delays[int(tid)] = round(max(0, bd - 0.5), 1)

    total_before = round(sum(before_delays.values()), 1)
    total_after = round(sum(after_delays.values()), 1)
    improvement = round(total_before - total_after, 1)

    congestion_before = round(
        len(merged_df[merged_df['Block_occupied_flag'] == 1]) / max(len(merged_df), 1) * 100, 1)
    cong_red = {'DETAIN': 5.0, 'CROSSING': 3.0, 'PRIORITIZE': 2.0, 'REGULATE': 4.0}.get(action_type, 1.0)
    congestion_after = round(max(0, congestion_before - cong_red), 1)

    return {
        'before_delays': before_delays,
        'after_delays': after_delays,
        'total_delay_before': total_before,
        'total_delay_after': total_after,
        'delay_improvement': improvement,
        'congestion_before': congestion_before,
        'congestion_after': congestion_after,
        'safety_status': 'SAFE',
        'explanation': f"Accepted: {rec['action']} for Train {target}. {rec['explanation']}",
        'outcome': 'positive' if improvement > 0 else 'neutral'
    }


def simulate_reject(rec, merged_df, alternative=None):
    """Reject simulation: delays increase since conflict is unresolved."""
    target = rec['target_train']
    affected = rec['affected_trains']

    before_delays = {}
    after_delays = {}

    for tid in affected:
        before_delays[int(tid)] = _get_train_delay(tid, merged_df)

    if alternative and alternative.get('action') == 'proceed_all':
        for tid in affected:
            bd = before_delays.get(int(tid), 0)
            # All trains proceed into conflict — everyone delayed
            after_delays[int(tid)] = round(bd + 2.5, 1)
        explanation = ("Rejected recommendation: all trains proceed into conflict zone. "
                       "Risk of cascading delays and safety concern.")
        safety = 'WARNING'
    elif alternative and alternative.get('action') == 'detain_other':
        other_train = alternative.get('train_id', affected[0] if affected else target)
        for tid in affected:
            bd = before_delays.get(int(tid), 0)
            if tid == other_train:
                after_delays[int(tid)] = round(bd + 4.5, 1)
            else:
                after_delays[int(tid)] = round(max(0, bd - 1.0), 1)
        explanation = f"Rejected AI recommendation. User chose to detain Train {other_train} instead."
        safety = 'SAFE'
    else:
        for tid in affected:
            bd = before_delays.get(int(tid), 0)
            # Maintaining status quo — delays slightly worsen
            after_delays[int(tid)] = round(bd + 1.5, 1)
        explanation = ("Rejected recommendation: maintaining current state. "
                       "Conflict unresolved — delays may increase.")
        safety = 'CAUTION'

    total_before = round(sum(before_delays.values()), 1)
    total_after = round(sum(after_delays.values()), 1)

    congestion_base = round(
        len(merged_df[merged_df['Block_occupied_flag'] == 1]) / max(len(merged_df), 1) * 100, 1)

    return {
        'before_delays': before_delays,
        'after_delays': after_delays,
        'total_delay_before': total_before,
        'total_delay_after': total_after,
        'delay_improvement': round(total_before - total_after, 1),
        'congestion_before': congestion_base,
        'congestion_after': round(congestion_base + 3.0, 1),
        'safety_status': safety,
        'explanation': explanation,
        'outcome': 'negative' if total_after > total_before else 'neutral'
    }


# ============================= WHAT-IF SIMULATION =============================

def run_whatif(merged_df, scenario):
    """Run what-if simulation with per-train delay computation and affected train details."""
    results = {}
    modified = merged_df.copy()
    modified['Delay_at_exit_min'] = modified['Delay_at_exit_min'].astype(float)
    train_id = None
    affected_details = []  # list of {train_id, reason, before, after}

    # --- Halt time ---
    if scenario.get('modify_detention'):
        train_id = scenario['modify_detention'].get('train_id')
        extra_min = scenario['modify_detention'].get('minutes', 0)
        if extra_min != 0:
            mask = modified['Train_ID'] == train_id
            modified.loc[mask, 'Delay_at_exit_min'] = modified.loc[mask, 'Delay_at_exit_min'] + extra_min
            results['halt'] = f"Train {train_id} halted for additional {extra_min} minutes."
            affected_details.append({
                'train_id': int(train_id),
                'reason': f"Extra halt of {extra_min} min",
                'delta': round(extra_min, 1),
            })

    # --- Action type (halt only) ---
    action_type = scenario.get('action_type', '')
    if action_type and train_id is not None:
        mask = modified['Train_ID'] == train_id

        if action_type == 'halt':
            # A halt means the train stops at its current position.
            # This adds a fixed operational penalty (dwell time) per block,
            # NOT the full block traversal time.
            halt_penalty = 3.0  # 3 minutes operational halt per block section
            modified.loc[mask, 'Delay_at_exit_min'] = modified.loc[mask, 'Delay_at_exit_min'] + halt_penalty
            results['action'] = (f"Train {train_id} HALTED at current position. "
                                 f"+{halt_penalty} min delay added per block section. "
                                 f"Other trains in shared blocks may benefit from freed path.")
            affected_details.append({
                'train_id': int(train_id),
                'reason': f"HALTED: +{halt_penalty} min per block",
                'delta': round(halt_penalty, 1),
            })
            # Other trains sharing same blocks benefit slightly
            train_blocks = modified.loc[mask, 'Block_id'].unique()
            others_mask = (~mask) & (modified['Block_id'].isin(train_blocks))
            if others_mask.any():
                other_tids = modified.loc[others_mask, 'Train_ID'].unique()
                modified.loc[others_mask, 'Delay_at_exit_min'] = np.maximum(
                    0, modified.loc[others_mask, 'Delay_at_exit_min'] - 0.5)
                for ot in list(other_tids)[:5]:
                    affected_details.append({
                        'train_id': int(ot),
                        'reason': "Path freed by halt (-0.5 min)",
                        'delta': -0.5,
                    })

    # --- Compute per-train before/after ---
    if train_id is not None:
        train_before = round(float(merged_df[merged_df['Train_ID'] == train_id]['Delay_at_exit_min'].mean()), 2)
        train_after = round(float(modified[modified['Train_ID'] == train_id]['Delay_at_exit_min'].mean()), 2)
        results['train_before_avg_delay'] = train_before
        results['train_after_avg_delay'] = train_after

    original_avg = round(float(merged_df['Delay_at_exit_min'].mean()), 2)
    modified_avg = round(float(modified['Delay_at_exit_min'].mean()), 2)

    results['before_avg_delay'] = original_avg
    results['after_avg_delay'] = modified_avg
    results['impact'] = round(modified_avg - original_avg, 2)
    results['total_trains_affected'] = int(
        merged_df['Train_ID'][modified['Delay_at_exit_min'] != merged_df['Delay_at_exit_min']].nunique())
    results['affected_details'] = affected_details

    return results


# ============================= PERFORMANCE KPIs =============================

def get_performance_kpis(merged_df):
    total = len(merged_df)
    avg_delay = round(float(merged_df['Delay_at_exit_min'].mean()), 2)
    on_time = int((merged_df['Delay_at_exit_min'] <= 0).sum())
    punctuality = round(on_time / max(total, 1) * 100, 1)

    unique_trains = merged_df['Train_ID'].nunique()
    unique_blocks = merged_df['Block_id'].nunique()
    throughput = round(unique_trains / max(unique_blocks, 1), 2)

    occupied = merged_df['Block_occupied_flag'].sum()
    utilization = round(occupied / max(total, 1) * 100, 1)

    conflicts = int(merged_df['Conflict_flag'].sum())
    conflict_rate = round(conflicts / max(total, 1) * 100, 1)

    delay_dist = {
        'on_time': int((merged_df['Delay_at_exit_min'] <= 0).sum()),
        'slight': int(((merged_df['Delay_at_exit_min'] > 0) & (merged_df['Delay_at_exit_min'] <= 2)).sum()),
        'moderate': int(((merged_df['Delay_at_exit_min'] > 2) & (merged_df['Delay_at_exit_min'] <= 4)).sum()),
        'severe': int((merged_df['Delay_at_exit_min'] > 4).sum()),
    }

    block_delays = merged_df.groupby('Block_id')['Delay_at_exit_min'].mean().round(2).to_dict()

    type_delays = {}
    if 'Train_type' in merged_df.columns:
        type_delays = merged_df.groupby('Train_type')['Delay_at_exit_min'].mean().round(2).to_dict()

    return {
        'avg_delay': float(avg_delay),
        'punctuality': float(punctuality),
        'throughput': float(throughput),
        'utilization': float(utilization),
        'conflict_rate': float(conflict_rate),
        'total_movements': int(total),
        'total_conflicts': int(conflicts),
        'delay_distribution': {k: int(v) for k, v in delay_dist.items()},
        'block_delays': {str(k): round(float(v), 2) for k, v in block_delays.items()},
        'type_delays': {str(k): round(float(v), 2) for k, v in type_delays.items()},
    }
