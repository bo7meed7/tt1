import pandas as pd
import os

upload_folder = 'uploads'
files = [f for f in os.listdir(upload_folder) if f.endswith('.xlsx') or f.endswith('.xlsm')]
if not files:
    print("No Excel files found.")
    exit()

latest_file = max([os.path.join(upload_folder, f) for f in files], key=os.path.getmtime)
print(f"Checking file: {latest_file}")

xl = pd.ExcelFile(latest_file)
print("Sheets found:", xl.sheet_names)

for sheet in xl.sheet_names:
    df = pd.read_excel(latest_file, sheet_name=sheet, header=None, nrows=20)
    found = False
    for i, row in df.iterrows():
        if any('اسم المدرس' in str(val) for val in row.values):
            found = True
            break
    print(f"Sheet '{sheet}': Contains 'اسم المدرس'? {found}")