import os
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from models import db, Teacher, Slot, Substitution
from utils import parse_timetable

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-secret')

# Database configuration: Use Railway's DATABASE_URL if available, else local SQLite
database_url = os.environ.get('DATABASE_URL', 'sqlite:///timetable.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db.init_app(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xlsm')):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        success, message = parse_timetable(filepath)
        if success:
            flash('Timetable uploaded and processed successfully!', 'success')
        else:
            flash(f'Error processing file: {message}', 'danger')
        return redirect(url_for('index'))
    else:
        flash('Invalid file type. Please upload Excel file.', 'danger')
        return redirect(url_for('index'))

@app.route('/find', methods=['GET', 'POST'])
def find_substitute():
    # Get lists for dropdowns
    teachers = Teacher.query.order_by(Teacher.name).all()
    # Unique days
    days = db.session.query(Slot.day_of_week).distinct().all()
    days = [d[0] for d in days if d[0]] # Flatten
    
    # Sort days if possible (custom sort order)
    day_order = ['الأحد', 'الإثنين', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس']
    days.sort(key=lambda x: day_order.index(x) if x in day_order else 99)
    
    periods = [1, 2, 3, 4, 5, 6, 7]

    if request.method == 'POST':
        teacher_id = request.form.get('teacher_id')
        day = request.form.get('day')
        period = request.form.get('period')

        if not all([teacher_id, day, period]):
            flash('Please select all fields', 'warning')
            return redirect(url_for('find_substitute'))
        
        period = int(period)
        original_teacher = Teacher.query.get(teacher_id)
        
        # Verify original teacher has a lesson
        original_slot = Slot.query.filter_by(
            teacher_id=teacher_id, 
            day_of_week=day, 
            period_number=period
        ).first()

        if not original_slot or not original_slot.has_lesson:
            flash(f'{original_teacher.name} does not have a lesson on {day} Period {period}.', 'warning')
            # We allow continuing? No, requirements say "If not, show warning."
            # But maybe they want to assign anyway? "The system suggests teachers..."
            # Let's stop if no lesson, or maybe just warn. 
            # "App checks... If not, show warning." implies we shouldn't proceed or at least warn.
            # I will return to form with warning.
            return render_template('find.html', teachers=teachers, days=days, periods=periods, selected={
                'teacher_id': int(teacher_id), 'day': day, 'period': period
            })

        # Find available teachers
        # Logic: Teachers who have a slot at this time AND has_lesson is False
        
        available_slots = Slot.query.filter_by(
            day_of_week=day,
            period_number=period,
            has_lesson=False
        ).all()
        
        candidates = []
        for slot in available_slots:
            teacher = slot.teacher
            
            # 1. Check if teacher has any lessons at all in the week
            # We can use the total_periods field if reliable, or count slots
            # Let's count slots to be safe and dynamic
            total_weekly_lessons = Slot.query.filter_by(teacher_id=teacher.id, has_lesson=True).count()
            
            # Filter removed as per user request to show all available teachers
            # if total_weekly_lessons == 0:
            #    continue 
            
            # 2. Calculate daily load for sorting
            daily_load = Slot.query.filter_by(
                teacher_id=teacher.id, 
                day_of_week=day, 
                has_lesson=True
            ).count()
            
            candidates.append({
                'teacher': teacher,
                'daily_load': daily_load,
                'weekly_load': total_weekly_lessons
            })
            
        # 3. Sort by weekly load first, then daily load
        # User requested "business" (load) calculation based on all the week.
        candidates.sort(key=lambda x: (x['weekly_load'], x['daily_load']))
        
        # Extract teacher objects for compatibility, but maybe we want to pass the whole dict to show stats?
        # The current template expects a list of teachers.
        # Let's update the template to show stats too.
            
        return render_template('results.html', 
                               original_teacher=original_teacher,
                               day=day,
                               period=period,
                               candidates=candidates) # Changed from available_teachers to candidates

    return render_template('find.html', teachers=teachers, days=days, periods=periods)

@app.route('/assign', methods=['POST'])
def assign_substitute():
    original_teacher_id = request.form.get('original_teacher_id')
    covering_teacher_id = request.form.get('covering_teacher_id')
    day = request.form.get('day')
    period = request.form.get('period')
    
    sub = Substitution(
        original_teacher_id=original_teacher_id,
        covering_teacher_id=covering_teacher_id,
        day_of_week=day,
        period_number=period
    )
    db.session.add(sub)
    db.session.commit()
    
    flash('Substitution assigned successfully!', 'success')
    return redirect(url_for('log'))

@app.route('/log')
def log():
    substitutions = Substitution.query.order_by(Substitution.created_at.desc()).all()
    return render_template('log.html', substitutions=substitutions)

@app.route('/delete_log/<int:id>', methods=['POST'])
def delete_log(id):
    sub = Substitution.query.get_or_404(id)
    db.session.delete(sub)
    db.session.commit()
    flash('تم حذف المناوبة بنجاح', 'success')
    return redirect(url_for('log'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
