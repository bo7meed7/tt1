import pandas as pd
import os

upload_folder = 'uploads'
files = [f for f in os.listdir(upload_folder) if f.endswith('.xlsx') or f.endswith('.xlsm')]
if not files:
    print("No Excel files found.")
    exit()

latest_file = max([os.path.join(upload_folder, f) for f in files], key=os.path.getmtime)
print(f"Inspecting file: {latest_file}")

try:
    xl = pd.ExcelFile(latest_file)
    for sheet in xl.sheet_names:
        print(f"\n--- Sheet: {sheet} ---")
        df = pd.read_excel(latest_file, sheet_name=sheet, header=None, nrows=20)
        
        # Find header row
        header_row_index = None
        teacher_col_idx = None
        
        for r_idx, row in df.iterrows():
            for c_idx, val in enumerate(row.values):
                if 'اسم المدرس' in str(val):
                    header_row_index = r_idx
                    teacher_col_idx = c_idx
                    print(f"Found 'اسم المدرس' at Row {r_idx}, Col {c_idx}")
                    break
            if header_row_index is not None:
                break
        
        if header_row_index is not None:
            # Load data with this header
            df_data = pd.read_excel(latest_file, sheet_name=sheet, header=header_row_index)
            
            # Identify adjacent columns
            # Column indices in the loaded df
            # The column name for teacher
            teacher_col_name = df_data.columns[teacher_col_idx]
            print(f"Teacher Column Name: '{teacher_col_name}'")
            
            # Check columns to the "right" (index + 1 and index - 1)
            # Note: In pandas, columns are ordered 0..N. 
            # If user says "right", in Arabic RTL sheet (A on right), 
            # "Right" of B is A (index - 1). 
            # "Left" of B is C (index + 1).
            
            # Let's show data for Col-1, Col, Col+1
            cols_to_show = []
            if teacher_col_idx > 0:
                cols_to_show.append(teacher_col_idx - 1)
            cols_to_show.append(teacher_col_idx)
            if teacher_col_idx < len(df_data.columns) - 1:
                cols_to_show.append(teacher_col_idx + 1)
                
            print("\nSample Data (First 10 rows):")
            for i in range(10):
                row_vals = []
                for c_idx in cols_to_show:
                    col_name = df_data.columns[c_idx]
                    val = df_data.iloc[i, c_idx]
                    row_vals.append(f"Col {c_idx} ({col_name}): {val}")
                print(f"Row {i}: " + " | ".join(row_vals))
                
except Exception as e:
    print(f"Error: {e}")