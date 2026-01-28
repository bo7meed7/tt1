import pandas as pd
import os

# Find the most recent uploaded file
upload_folder = 'uploads'
files = [f for f in os.listdir(upload_folder) if f.endswith('.xlsx') or f.endswith('.xlsm')]
if not files:
    print("No Excel files found.")
    exit()

# Sort by modification time
latest_file = max([os.path.join(upload_folder, f) for f in files], key=os.path.getmtime)
print(f"Inspecting file: {latest_file}")

try:
    # Read first 20 rows
    df = pd.read_excel(latest_file, header=None, nrows=20)
    print("\nFirst 10 rows:")
    print(df.head(10))
    
    print("\nSearch for 'اسم المدرس':")
    for i, row in df.iterrows():
        row_str = " | ".join([str(x).strip() for x in row.values])
        if 'اسم المدرس' in row_str:
            print(f"Found 'اسم المدرس' in row {i}:")
            print(row_str)
            
            # Check the row below for periods
            if i + 1 < len(df):
                print(f"Row below ({i+1}):")
                print(" | ".join([str(x).strip() for x in df.iloc[i+1].values]))
            
except Exception as e:
    print(f"Error reading file: {e}")