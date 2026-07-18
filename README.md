# B2B SaaS Revenue Analytics

A revenue analytics pipeline for B2B SaaS companies — computes the core metrics that actually matter for growth decisions: **MRR movement, Net Revenue Retention, churn, and unit economics (CAC/LTV)**.

Built on a simulated 24-month SaaS billing dataset (500 customers, 3 pricing tiers, realistic segment/plan behavior) to demonstrate the full analytics workflow end to end: raw billing events → clean metrics → business insight.

## Why this matters

Most SaaS dashboards show one number: **total MRR**. That number can look completely healthy while a serious retention problem is building underneath it — expansion revenue from happy long-term customers can mask churn from newer, unhappy ones.

This project is built specifically to surface that gap. The dataset includes a deliberate 4-month period where customer churn spikes due to a support/onboarding issue. Headline MRR keeps climbing through the whole period — but **Net Revenue Retention drops from ~100% to ~91%** during the exact same months. You can't see the second finding by looking at the first metric. That's the point.

## What it computes

| Metric | What it tells you |
|---|---|
| **MRR Waterfall** | New / expansion / contraction / churned MRR, month by month |
| **Net Revenue Retention (NRR)** | Whether existing revenue is growing or shrinking — the single best early-warning signal in SaaS |
| **Customer churn rate** (raw + 3-month smoothed) | Logo retention over time, smoothed to avoid noisy single-month spikes |
| **CAC** (raw + 3-month smoothed) | Cost to acquire a customer, based on marketing spend |
| **LTV / LTV:CAC ratio** | Whether acquisition spend is actually paying off |
| **ARPU** | Average revenue per active customer |

## How it works

1. **`saas_analytics_pipeline.py`** generates a synthetic but realistic SaaS billing event log (signups, renewals, upgrades, downgrades, churn) across 500 customers and 24 months, then computes all metrics above from those raw events — the same way you'd process a real Stripe/Chargebee export.
2. Outputs 5 clean CSVs: `customers.csv`, `subscriptions.csv`, `marketing_spend.csv`, `mrr_waterfall.csv`, `saas_monthly_metrics.csv`.
3. `saas_monthly_metrics.csv` feeds directly into a Looker Studio dashboard for monthly reporting.

## Run it

```bash
pip install pandas numpy python-dateutil
python saas_analytics_pipeline.py
```

## Stack

Python (pandas, numpy) for data generation and metrics · Looker Studio for reporting

## About this project

This is a demonstration project built to showcase a revenue analytics methodology for B2B SaaS companies — the same approach used for real client billing data (Stripe, Chargebee, HubSpot, etc.) as a monthly analytics service.

**Interested in this as a service for your company?** Get in touch: [manoschdls@gmail.com / www.linkedin.com/in/emmanouil-chadalis]
