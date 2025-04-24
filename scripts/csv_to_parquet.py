import pandas as pd

# 1) Read the original CSV
df = pd.read_csv("data/agcensus_wide.csv")

# 2) Write it out as Parquet
df.to_parquet("data/agcensus_wide.parquet", index=False)

print("✅ Parquet saved to data/agcensus_wide.parquet")
