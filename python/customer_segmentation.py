import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import urllib.parse

# ==========================================
# 1. DATABASE CONNECTION
# ==========================================
# Password is typed in when the script runs:
import getpass
raw_password = input("Enter DB password: ")
encoded_password = urllib.parse.quote_plus(raw_password)

DB_URI = f"postgresql+psycopg2://postgres:{encoded_password}@localhost:5432/ecommerce_analytics"
engine = create_engine(DB_URI)

print("Connecting to PostgreSQL and reading view...")
df = pd.read_sql("SELECT * FROM v_customer_transactions", engine)
df['order_date'] = pd.to_datetime(df['order_date'])
print(f"Loaded {len(df):,} transactions.\n")

# ==========================================
# 2. STATISTICAL METRICS (Order Values)
# ==========================================
spend = df['total_order_value']

mean_val = spend.mean()
median_val = spend.median()
std_val = spend.std()
q1 = spend.quantile(0.25)
q3 = spend.quantile(0.75)
iqr = q3 - q1
upper_bound = q3 + (1.5 * iqr)

print("============ STATISTICAL SUMMARY ============")
print(f"Mean Order Value:   R$ {mean_val:.2f}")
print(f"Median Order Value: R$ {median_val:.2f}")
print(f"Std Deviation:      R$ {std_val:.2f}")
print(f"25th Percentile:    R$ {q1:.2f}")
print(f"75th Percentile:    R$ {q3:.2f}")
print(f"IQR (Q3 - Q1):      R$ {iqr:.2f}")
print(f"Outlier Boundary:   R$ {upper_bound:.2f}")
print(f"Shape:              {'Right-skewed (Mean > Median)' if mean_val > median_val else 'Symmetric'}")
print("=============================================\n")

# ==========================================
# 3. RFM AGGREGATION
# ==========================================
snapshot_date = df['order_date'].max() + pd.Timedelta(days=1)

print("Calculating RFM metrics per customer...")
rfm = df.groupby('customer_unique_id').agg({
    'order_date': lambda x: (snapshot_date - x.max()).days,
    'order_id': 'nunique',
    'total_order_value': 'sum'
}).reset_index()

rfm.columns = ['customer_unique_id', 'recency_days', 'frequency', 'monetary_value']

# Quartile scoring (1 to 4)
# Recency: lower days = better score (4 is most recent)
rfm['r_score'] = pd.qcut(rfm['recency_days'], 4, labels=[4, 3, 2, 1]).astype(int)

# Monetary: higher spend = better score (4 is highest spend)
rfm['m_score'] = pd.qcut(rfm['monetary_value'], 4, labels=[1, 2, 3, 4]).astype(int)

# Frequency: manual bins (1 order = 1, 2 = 2, 3+ = 3)
rfm['f_score'] = pd.cut(rfm['frequency'], bins=[0, 1, 2, np.inf], labels=[1, 2, 3]).astype(int)

# ==========================================
# 4. BUSINESS SEGMENTS
# ==========================================
# Original 4 segments (based on Recency and Monetary) - used by the dashboard
def assign_segment(row):
    r, m = row['r_score'], row['m_score']
    if r >= 3 and m >= 3:
        return 'Champions (High Value, Recent)'
    elif r >= 3 and m < 3:
        return 'Active Low Spenders'
    elif r < 3 and m >= 3:
        return 'At Risk (High Value, Lapsed)'
    else:
        return 'Hibernating / Lost'

# Detailed 5 segments - this one also uses Frequency (repeat buyers)
def assign_detailed_segment(row):
    r, f, m = row['r_score'], row['f_score'], row['m_score']
    if r >= 3:                      # bought recently
        if f >= 2:
            return 'Loyal Repeat Buyers'
        elif m >= 3:
            return 'Big Spenders (One-time)'
        else:
            return 'New / Low Spenders'
    else:                           # has not bought recently
        if f >= 2 or m >= 3:
            return 'Win-back Priority'
        else:
            return 'Lost'

rfm['customer_segment'] = rfm.apply(assign_segment, axis=1)
rfm['detailed_segment'] = rfm.apply(assign_detailed_segment, axis=1)

print("Customer Segment Counts:")
print(rfm['customer_segment'].value_counts())
print("\nDetailed Segment Counts:")
print(rfm['detailed_segment'].value_counts())

one_time_pct = (rfm['frequency'] == 1).mean() * 100
print(f"\nCustomers who ordered only once: {one_time_pct:.1f}%")

# ==========================================
# 5. SEGMENT SUMMARY (customers, revenue, share)
# ==========================================
def build_summary(data, column):
    summary = data.groupby(column).agg(
        customers=('customer_unique_id', 'count'),
        revenue=('monetary_value', 'sum'),
        avg_spend=('monetary_value', 'mean')
    ).reset_index().rename(columns={column: 'segment'})
    summary['revenue_share_pct'] = (summary['revenue'] / summary['revenue'].sum() * 100).round(1)
    summary['revenue'] = summary['revenue'].round(2)
    summary['avg_spend'] = summary['avg_spend'].round(2)
    return summary.sort_values('revenue', ascending=False)

summary_main = build_summary(rfm, 'customer_segment')
summary_detail = build_summary(rfm, 'detailed_segment')

print("\n=== Revenue by Segment ===")
print(summary_main.to_string(index=False))
print("\n=== Revenue by Detailed Segment ===")
print(summary_detail.to_string(index=False))

# ==========================================
# 6. WRITE RESULTS BACK TO POSTGRESQL
# ==========================================
print("\nSaving tables back to PostgreSQL...")
rfm.to_sql('customer_rfm_segments', engine, if_exists='replace', index=False)
summary_main.to_sql('segment_summary', engine, if_exists='replace', index=False)
summary_detail.to_sql('detailed_segment_summary', engine, if_exists='replace', index=False)
print("Complete! Tables ready in PostgreSQL: customer_rfm_segments, segment_summary, detailed_segment_summary")