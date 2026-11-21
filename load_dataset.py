import pandas as pd

df = pd.read_csv("crime_dataset_india.csv")

print(df.head())
print("Total records:", len(df))
