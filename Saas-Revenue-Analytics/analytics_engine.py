import pandas as pd
import numpy as np
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta

np.random.seed(42)
random.seed(42)

# =========================================================
# PART 1 - GENERATE SYNTHETIC SAAS BILLING DATA
# =========================================================

num_customers = 500
customer_ids = [f"CUST_{str(i).zfill(4)}" for i in range(1, num_customers + 1)]
companies = [f"Company_{i}" for i in range(1, num_customers + 1)]
segments = np.random.choice(['SMB', 'Mid-Market', 'Enterprise'], size=num_customers, p=[0.6, 0.3, 0.1])

segment_plan_p = {
    'SMB':        [0.85, 0.14, 0.01],
    'Mid-Market': [0.25, 0.60, 0.15],
    'Enterprise': [0.02, 0.28, 0.70],
}
plan_names = ['Basic', 'Pro', 'Enterprise']
plans = {'Basic': 99, 'Pro': 299, 'Enterprise': 999}

df_customers = pd.DataFrame({
    'customer_id': customer_ids,
    'company_name': companies,
    'segment': segments,
})

start_date = datetime(2024, 1, 1)
n_months = 24
month_list = [start_date + relativedelta(months=i) for i in range(n_months)]
problem_months = set(month_list[13:17])  # temporary spike in churn/downgrades

weights = np.array([1 + i * 0.35 for i in range(n_months)])
weights = weights / weights.sum()
signup_idx = np.random.choice(range(n_months), size=num_customers, p=weights)
df_customers['signup_month'] = [month_list[i] for i in signup_idx]

transactions = []

for _, row in df_customers.iterrows():
    cust_id = row['customer_id']
    segment = row['segment']
    p = segment_plan_p[segment]
    current_plan = np.random.choice(plan_names, p=p)
    mrr = plans[current_plan] * np.random.uniform(0.92, 1.1)
    current_date = row['signup_month']

    transactions.append([cust_id, current_date, 'New', current_plan, round(mrr, 2)])

    is_active = True
    month_cursor = current_date
    while is_active and month_cursor < month_list[-1]:
        month_cursor = month_cursor + relativedelta(months=1)
        in_problem_window = month_cursor in problem_months

        churn_p = 0.03 * (2.5 if in_problem_window else 1.0)
        change_p = 0.05 * (0.6 if in_problem_window else 1.0)
        downgrade_bonus = 0.02 if in_problem_window else 0.0

        dice = random.random()
        if dice < churn_p:
            transactions.append([cust_id, month_cursor, 'Churn', current_plan, 0.0])
            is_active = False
        elif dice < churn_p + change_p + downgrade_bonus:
            idx_plan = plan_names.index(current_plan)
            if in_problem_window and dice > churn_p + change_p:
                new_idx = max(0, idx_plan - 1)
            else:
                new_idx = np.random.choice([max(0, idx_plan - 1), idx_plan, min(2, idx_plan + 1)])
            new_plan = plan_names[new_idx]
            if new_plan != current_plan:
                event_type = 'Upgrade' if plans[new_plan] > plans[current_plan] else 'Downgrade'
                current_plan = new_plan
                mrr = plans[current_plan] * np.random.uniform(0.92, 1.1)
                transactions.append([cust_id, month_cursor, event_type, current_plan, round(mrr, 2)])
            else:
                transactions.append([cust_id, month_cursor, 'Renewal', current_plan, round(mrr, 2)])
        else:
            transactions.append([cust_id, month_cursor, 'Renewal', current_plan, round(mrr, 2)])

df_subscriptions = pd.DataFrame(
    transactions,
    columns=['customer_id', 'event_date', 'event_type', 'plan_name', 'mrr'],
)

new_per_month = df_customers.groupby('signup_month').size().reindex(month_list, fill_value=0)
df_spend = pd.DataFrame({
    'month': month_list,
    'new_customers': new_per_month.values,
    'marketing_spend': (new_per_month.values * np.random.uniform(600, 1300, n_months)).round(2),
})

df_customers.to_csv('customers.csv', index=False)
df_subscriptions.to_csv('subscriptions.csv', index=False)
df_spend.to_csv('marketing_spend.csv', index=False)

print(f"Generated {len(df_customers)} customers, {len(df_subscriptions)} billing events")

# =========================================================
# PART 2 - COMPUTE METRICS (MRR waterfall, NRR, churn, CAC, LTV)
# =========================================================

df_subs = df_subscriptions.copy()
df_cust = df_customers.copy()

df_subs['event_date'] = pd.to_datetime(df_subs['event_date'])
df_subs = df_subs.sort_values('event_date')
df_subs['month'] = df_subs['event_date'].dt.to_period('M')
df_spend['month'] = pd.to_datetime(df_spend['month']).dt.to_period('M')

monthly_mrr_per_cust = df_subs.groupby(['month', 'customer_id'])['mrr'].last().reset_index()

# fixed 24-month range, independent of which months happen to have events -
# guarantees no silent gaps in the time series
months = pd.period_range(start=month_list[0], periods=n_months, freq='M')
cust_ids = df_cust['customer_id'].unique()
grid = pd.MultiIndex.from_product([months, cust_ids], names=['month', 'customer_id']).to_frame().reset_index(drop=True)

monthly_mrr = pd.merge(grid, monthly_mrr_per_cust, on=['month', 'customer_id'], how='left').fillna(0)
monthly_mrr['is_active'] = monthly_mrr['mrr'] > 0

monthly_summary = monthly_mrr.groupby('month').agg(
    total_mrr=('mrr', 'sum'),
    active_customers=('is_active', 'sum')
).reset_index()

# --- MRR waterfall: new / expansion / contraction / churned ---
pivot = monthly_mrr.pivot(index='customer_id', columns='month', values='mrr')
pivot = pivot[months]

waterfall = []
for i, m in enumerate(months):
    curr = pivot[m]
    prev = pivot[months[i - 1]] if i > 0 else pd.Series(0, index=pivot.index)
    is_new = (prev == 0) & (curr > 0)
    delta = curr[~is_new] - prev[~is_new]
    waterfall.append({
        'month': m,
        'starting_mrr': prev.sum(),
        'new_mrr': curr[is_new].sum(),
        'expansion_mrr': delta[delta > 0].sum(),
        'contraction_mrr': delta[(delta < 0) & (curr[~is_new] > 0)].sum(),
        'churned_mrr': delta[(delta < 0) & (curr[~is_new] == 0)].sum(),
    })
waterfall_df = pd.DataFrame(waterfall)
waterfall_df['nrr_pct'] = np.where(
    waterfall_df['starting_mrr'] > 0,
    (waterfall_df['starting_mrr'] + waterfall_df['expansion_mrr'] + waterfall_df['contraction_mrr'] + waterfall_df['churned_mrr'])
    / waterfall_df['starting_mrr'] * 100,
    np.nan
)

# --- churn rate (raw + 3-month smoothed) ---
churn_events = df_subs[df_subs['event_type'] == 'Churn'].groupby('month').size().reset_index(name='churned_customers')
monthly_summary = pd.merge(monthly_summary, churn_events, on='month', how='left').fillna(0)

monthly_summary['prev_active_customers'] = monthly_summary['active_customers'].shift(1).fillna(0)
monthly_summary['churn_rate_raw'] = np.where(
    monthly_summary['prev_active_customers'] > 0,
    monthly_summary['churned_customers'] / monthly_summary['prev_active_customers'],
    0
)
monthly_summary['churn_rate_3m'] = monthly_summary['churn_rate_raw'].rolling(3, min_periods=1).mean()

monthly_summary = pd.merge(monthly_summary, df_spend, on='month', how='left')

monthly_summary['cac_raw'] = np.where(
    monthly_summary['new_customers'] > 0,
    monthly_summary['marketing_spend'] / monthly_summary['new_customers'],
    np.nan
)
monthly_summary['cac_3m'] = monthly_summary['cac_raw'].rolling(3, min_periods=1).mean()

monthly_summary['arpu'] = np.where(
    monthly_summary['active_customers'] > 0,
    monthly_summary['total_mrr'] / monthly_summary['active_customers'],
    0
)

monthly_summary['ltv'] = np.where(
    monthly_summary['churn_rate_3m'] > 0,
    monthly_summary['arpu'] / monthly_summary['churn_rate_3m'],
    np.nan
)
monthly_summary['ltv_to_cac'] = monthly_summary['ltv'] / monthly_summary['cac_3m']

monthly_summary = pd.merge(monthly_summary, waterfall_df[['month', 'nrr_pct']], on='month', how='left')

# round every decimal-heavy column - unrounded floats (15+ digits) get mangled
# on import into Sheets under some locale settings
round_cols = {
    'churn_rate_raw': 4, 'churn_rate_3m': 4, 'cac_raw': 2, 'cac_3m': 2,
    'arpu': 2, 'ltv': 2, 'ltv_to_cac': 2, 'nrr_pct': 2, 'total_mrr': 2,
}
for col, decimals in round_cols.items():
    monthly_summary[col] = monthly_summary[col].round(decimals)

waterfall_df['nrr_pct'] = waterfall_df['nrr_pct'].round(2)
for col in ['starting_mrr', 'new_mrr', 'expansion_mrr', 'contraction_mrr', 'churned_mrr']:
    waterfall_df[col] = waterfall_df[col].round(2)

monthly_summary['month'] = monthly_summary['month'].astype(str)
waterfall_df['month'] = waterfall_df['month'].astype(str)

monthly_summary.to_csv('saas_monthly_metrics.csv', index=False)
waterfall_df.to_csv('mrr_waterfall.csv', index=False)

print("Metrics computed and saved: saas_monthly_metrics.csv, mrr_waterfall.csv")
print(monthly_summary[['month', 'total_mrr', 'churn_rate_3m', 'cac_3m', 'ltv', 'ltv_to_cac', 'nrr_pct']].to_string())