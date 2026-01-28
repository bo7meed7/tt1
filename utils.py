import pandas as pd
import os
from models import db, Teacher, Slot

# Arabic Day Names to English (for internal storage if needed, or keep Arabic)
# Keeping Arabic for display might be easier, but internal ID is better.
DAYS_MAP = {
    'الأحد': 'Sunday', 'الاحد': 'Sunday',
    'الإثنين': 'Monday', 'الاثنين': 'Monday',
    'الثلاثاء': 'Tuesday',
    'الأربعاء': 'Wednesday', 'الاربعاء': 'Wednesday',
    'الخميس': 'Thursday'
}

PERIODS = [1, 2, 3, 4, 5, 6, 7]

def parse_timetable(file_path, user_id):
    """
    Parses the Excel file and populates the database for a specific user.
    """
    try:
        # ... (Excel parsing logic remains same until DB operations)
        
        # Load the Excel file to get all sheet names
        xl = pd.ExcelFile(file_path)

        
        target_sheet = None
        header_row_index = None
        
        # Iterate through all sheets to find the one with the timetable
        for sheet_name in xl.sheet_names:
            # Read first 20 rows of the sheet
            df_raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=20)
            
            # Search for header row
            for i, row in df_raw.iterrows():
                row_values = [str(val).strip() for val in row.values]
                if any('اسم المدرس' in val for val in row_values):
                    header_row_index = i
                    target_sheet = sheet_name
                    break
            
            if target_sheet:
                break
        
        if target_sheet is None:
             raise ValueError("Could not find a row containing 'اسم المدرس' in any sheet. Please check the file format.")

        # Read the detected header row to check if it contains days
        df_header_check = pd.read_excel(file_path, sheet_name=target_sheet, header=header_row_index, nrows=0)
        header_cols = [str(c).strip() for c in df_header_check.columns]
        
        # Check if days are present in this row
        has_days = any(any(day in col for day in DAYS_MAP) for col in header_cols)
        
        df = None
        
        # SCENARIO 1: Days are in the row ABOVE the Teacher/Period row
        # This was the previous fix attempt.
        if not has_days and header_row_index > 0:
            # Read the full table starting from the row ABOVE the teacher row
            # We treat the row above as the primary header for Days
            
            # Read the row above (row_index - 1)
            df_above = pd.read_excel(file_path, sheet_name=target_sheet, header=None, skiprows=header_row_index-1, nrows=1)
            
            # Check if this row actually has days
            row_above_cols = [str(c).strip() for c in df_above.iloc[0].values]
            has_days_above = any(any(day in col for day in DAYS_MAP) for col in row_above_cols)
            
            if has_days_above:
                # Read the main table
                df = pd.read_excel(file_path, sheet_name=target_sheet, header=header_row_index)
                
                if not df_above.empty:
                    # Forward fill the values in the row above (handling merged cells for Days)
                    row_above_values = pd.Series(df_above.iloc[0].values).ffill()
                    
                    # Combine headers
                    new_columns = []
                    for i in range(len(df.columns)):
                        col_name = str(df.columns[i]).strip()
                        
                        # Get corresponding value from row above
                        above_val = str(row_above_values[i]).strip() if i < len(row_above_values) else ''
                        
                        if above_val.lower() == 'nan':
                            above_val = ''
                            
                        # Combine: "Sunday 1", "Sunday 2", etc.
                        new_columns.append(f"{above_val} {col_name}".strip())
                    
                    df.columns = new_columns

        # SCENARIO 2: Days are in the Teacher row (CURRENT), and Periods are in the row BELOW
        # This matches the user's description: "Sunday is on cell E6" (where Teacher name is likely also in Row 6)
        # And periods (1, 2, 3) are likely in Row 7.
        if df is None and has_days:
            # Read the row BELOW the header row to check for periods
            df_below = pd.read_excel(file_path, sheet_name=target_sheet, header=None, skiprows=header_row_index+1, nrows=1)
            
            if not df_below.empty:
                # Check if row below has numbers 1-7
                row_below_values = [str(val).strip() for val in df_below.iloc[0].values]
                has_periods_below = any(str(p) in val for p in PERIODS for val in row_below_values)
                
                if has_periods_below:
                    # We have split headers: Day on top, Period on bottom.
                    # We need to construct the combined header.
                    
                    # 1. Read the Day row (current header_row_index)
                    # We need it as data to forward fill
                    df_days_row = pd.read_excel(file_path, sheet_name=target_sheet, header=None, skiprows=header_row_index, nrows=1)
                    days_values = pd.Series(df_days_row.iloc[0].values).ffill()
                    
                    # 2. Read the Period row (header_row_index + 1)
                    df_periods_row = pd.read_excel(file_path, sheet_name=target_sheet, header=None, skiprows=header_row_index+1, nrows=1)
                    periods_values = df_periods_row.iloc[0].values
                    
                    # 3. Combine them
                    combined_headers = []
                    for i in range(len(days_values)):
                        day_val = str(days_values[i]).strip()
                        period_val = str(periods_values[i]).strip()
                        
                        if day_val.lower() == 'nan': day_val = ''
                        if period_val.lower() == 'nan': period_val = ''
                        
                        # If the column is 'اسم المدرس' (Teacher Name), it might be in day_val, and period_val might be empty or vice versa
                        # We want to keep the meaningful label.
                        if 'اسم المدرس' in day_val:
                            combined_headers.append(day_val)
                        elif 'اسم المدرس' in period_val:
                            combined_headers.append(period_val)
                        else:
                            combined_headers.append(f"{day_val} {period_val}".strip())
                    
                    # 4. Read the data, skipping BOTH header rows (header_row_index and header_row_index+1)
                    # So we skip header_row_index + 2 lines effectively? 
                    # header=header_row_index means we skip header_row_index lines, use the next as header.
                    # Here we want to start data from header_row_index + 2.
                    df = pd.read_excel(file_path, sheet_name=target_sheet, header=None, skiprows=header_row_index+2)
                    
                    # Assign our manually created headers
                    # Ensure length matches
                    if len(combined_headers) == len(df.columns):
                        df.columns = combined_headers
                    else:
                        # Fallback if dimensions don't match (rare)
                        # Just use standard read if this fails
                        df = None

        if df is None:
            # Standard read if no complex header splitting was needed
            df = pd.read_excel(file_path, sheet_name=target_sheet, header=header_row_index)
        
        # Normalize columns to string and strip whitespace
        df.columns = df.columns.astype(str).str.strip()
        
        # Deduplicate column names to avoid "Truth value of a Series is ambiguous" error
        # when accessing row[col] if multiple columns have the same name (e.g. empty strings)
        new_columns = []
        seen_columns = {}
        for col in df.columns:
            if col in seen_columns:
                seen_columns[col] += 1
                new_columns.append(f"{col}.{seen_columns[col]}")
            else:
                seen_columns[col] = 0
                new_columns.append(col)
        df.columns = new_columns
        
        # Find key columns
        teacher_col = next((c for c in df.columns if 'اسم المدرس' in c), None)
        subject_col = next((c for c in df.columns if 'المادة' in c), None)
        periods_count_col = next((c for c in df.columns if 'عدد الحصص' in c), None)
        
        if not teacher_col:
            raise ValueError(f"Found header row but could not identify 'اسم المدرس' column. Columns found: {list(df.columns)}")

        # Clear existing data for THIS USER only
        teachers_to_delete = Teacher.query.filter_by(user_id=user_id).all()
        for t in teachers_to_delete:
            db.session.delete(t)
        
        db.session.commit() # Commit deletion first
        
        for index, row in df.iterrows():
            teacher_name = row[teacher_col]
            if pd.isna(teacher_name) or str(teacher_name).strip() == '':
                continue
                
            subject = row[subject_col] if subject_col and not pd.isna(row[subject_col]) else "Unknown"
            total_periods = row[periods_count_col] if periods_count_col and not pd.isna(row[periods_count_col]) else 0
            
            # Create Teacher linked to User
            teacher = Teacher(
                name=str(teacher_name).strip(), 
                subject=str(subject).strip(), 
                total_periods=int(total_periods) if str(total_periods).isdigit() else 0,
                user_id=user_id
            )
            db.session.add(teacher)
            db.session.flush() # Get ID
            
            # Iterate through columns to find slots
            for col in df.columns:
                if col in [teacher_col, subject_col, periods_count_col]:
                    continue
                
                # Check if column represents a valid day/period
                # We expect columns like "الأحد 1", "الأحد - 1", "1 الأحد" etc.
                # Or maybe the columns are just periods and we have to guess the day?
                # The prompt says: "Then columns for days (...) and periods (1-7)"
                # This implies the column header likely contains BOTH day and period.
                
                cell_value = row[col]
                is_lesson = False
                if not pd.isna(cell_value) and str(cell_value).strip() != '':
                    is_lesson = True
                
                # Try to extract Day and Period from Column Name
                day_found = None
                for ar_day, en_day in DAYS_MAP.items():
                    if ar_day in col:
                        day_found = ar_day # Keep Arabic for display consistency or convert?
                        # Let's keep Arabic day name in DB for matching with UI which uses Arabic
                        break
                
                if not day_found:
                    continue # Not a day column (maybe a break or other info)
                
                # Check for "break" keywords
                if 'فرصة' in col or 'break' in col.lower():
                    continue

                # Find period number
                period_found = None
                for p in PERIODS:
                    # Check for explicit number in column name (e.g. "1", "2")
                    # Be careful not to match "1" in "10" (though periods are 1-7)
                    # We look for the digit p
                    if str(p) in col:
                        period_found = p
                        break
                
                if period_found:
                    # If cell is not empty, it's a lesson.
                    # Even if empty, we might want to record it as "Free" (has_lesson=False)
                    # Requirement: "If it is a teaching period column and not empty -> create slot with has_lesson = true"
                    # "If empty -> treat as free"
                    # So we should create slots for ALL valid periods, marking has_lesson accordingly.
                    
                    slot = Slot(
                        teacher_id=teacher.id,
                        day_of_week=day_found,
                        period_number=period_found,
                        has_lesson=is_lesson
                    )
                    db.session.add(slot)
        
        db.session.commit()
        return True, "Successfully uploaded and parsed timetable."

    except Exception as e:
        db.session.rollback()
        return False, str(e)