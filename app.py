import os
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, Teacher, Slot, Substitution, User
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

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

db.init_app(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود مسبقاً', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(username=username, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        
        flash('تم إنشاء الحساب بنجاح! الرجاء تسجيل الدخول', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('خطأ في اسم المستخدم أو كلمة المرور', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
@login_required
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
        
        success, message = parse_timetable(filepath, current_user.id)
        if success:
            flash('Timetable uploaded and processed successfully!', 'success')
        else:
            flash(f'Error processing file: {message}', 'danger')
        return redirect(url_for('index'))
    else:
        flash('Invalid file type. Please upload Excel file.', 'danger')
        return redirect(url_for('index'))

@app.route('/find', methods=['GET', 'POST'])
@login_required
def find_substitute():
    # Get lists for dropdowns
    teachers = Teacher.query.filter_by(user_id=current_user.id).order_by(Teacher.name).all()
    # Unique days
    days = db.session.query(Slot.day_of_week).join(Teacher).filter(Teacher.user_id == current_user.id).distinct().all()
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
        
        if original_teacher.user_id != current_user.id:
            flash('Unauthorized', 'danger')
            return redirect(url_for('find_substitute'))
        
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
        
        available_slots = Slot.query.join(Teacher).filter(
            Teacher.user_id == current_user.id,
            Slot.day_of_week == day,
            Slot.period_number == period,
            Slot.has_lesson == False
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
@login_required
def assign_substitute():
    original_teacher_id = request.form.get('original_teacher_id')
    covering_teacher_id = request.form.get('covering_teacher_id')
    
    ot = Teacher.query.get(original_teacher_id)
    ct = Teacher.query.get(covering_teacher_id)
    if not ot or ot.user_id != current_user.id or not ct or ct.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('find_substitute'))

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
@login_required
def log():
    substitutions = Substitution.query.join(Teacher, Substitution.original_teacher_id == Teacher.id)\
        .filter(Teacher.user_id == current_user.id)\
        .order_by(Substitution.created_at.desc()).all()
    return render_template('log.html', substitutions=substitutions)

@app.route('/delete_log/<int:id>', methods=['POST'])
@login_required
def delete_log(id):
    sub = Substitution.query.get_or_404(id)
    if sub.original_teacher.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('log'))
    db.session.delete(sub)
    db.session.commit()
    flash('تم حذف المناوبة بنجاح', 'success')
    return redirect(url_for('log'))

@app.route('/manage_teachers')
@login_required
def manage_teachers():
    teachers = Teacher.query.filter_by(user_id=current_user.id).order_by(Teacher.name).all()
    return render_template('manage_teachers.html', teachers=teachers)

@app.route('/teachers/add', methods=['POST'])
@login_required
def add_teacher():
    name = request.form.get('name')
    subject = request.form.get('subject')
    
    if name:
        teacher = Teacher(name=name, subject=subject, user_id=current_user.id)
        db.session.add(teacher)
        db.session.commit()
        flash('تم إضافة المعلم بنجاح', 'success')
    
    return redirect(url_for('manage_teachers'))

@app.route('/teachers/toggle_exclude/<int:id>', methods=['POST'])
@login_required
def toggle_exclude_teacher(id):
    teacher = Teacher.query.get_or_404(id)
    if teacher.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('manage_teachers'))
        
    # Check if is_excluded exists (it should if models updated)
    if not hasattr(teacher, 'is_excluded'):
        # Fallback if migration not done properly, though we updated models.py
        pass 
    else:
        teacher.is_excluded = not teacher.is_excluded
        db.session.commit()
        status = "استبعاد" if teacher.is_excluded else "تضمين"
        flash(f'تم {status} المعلم {teacher.name} بنجاح', 'success')
        
    return redirect(url_for('manage_teachers'))

@app.route('/manage_teachers')
@login_required
def manage_teachers():
    teachers = Teacher.query.filter_by(user_id=current_user.id).order_by(Teacher.name).all()
    return render_template('manage_teachers.html', teachers=teachers)

@app.route('/teachers/add', methods=['POST'])
@login_required
def add_teacher():
    name = request.form.get('name')
    subject = request.form.get('subject')
    
    if name:
        teacher = Teacher(name=name, subject=subject, user_id=current_user.id)
        db.session.add(teacher)
        db.session.commit()
        flash('تم إضافة المعلم بنجاح', 'success')
    
    return redirect(url_for('manage_teachers'))

@app.route('/teachers/toggle_exclude/<int:id>', methods=['POST'])
@login_required
def toggle_exclude_teacher(id):
    teacher = Teacher.query.get_or_404(id)
    if teacher.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('manage_teachers'))
        
    # Check if is_excluded exists (it should if models updated)
    if not hasattr(teacher, 'is_excluded'):
        # Fallback if migration not done properly, though we updated models.py
        pass 
    else:
        teacher.is_excluded = not teacher.is_excluded
        db.session.commit()
        status = "استبعاد" if teacher.is_excluded else "تضمين"
        flash(f'تم {status} المعلم {teacher.name} بنجاح', 'success')
        
    return redirect(url_for('manage_teachers'))

@app.route('/manage_teachers')
@login_required
def manage_teachers():
    teachers = Teacher.query.filter_by(user_id=current_user.id).order_by(Teacher.name).all()
    return render_template('manage_teachers.html', teachers=teachers)

@app.route('/teachers/add', methods=['POST'])
@login_required
def add_teacher():
    name = request.form.get('name')
    subject = request.form.get('subject')
    
    if name:
        teacher = Teacher(name=name, subject=subject, user_id=current_user.id)
        db.session.add(teacher)
        db.session.commit()
        flash('تم إضافة المعلم بنجاح', 'success')
    
    return redirect(url_for('manage_teachers'))

@app.route('/teachers/toggle_exclude/<int:id>', methods=['POST'])
@login_required
def toggle_exclude_teacher(id):
    teacher = Teacher.query.get_or_404(id)
    if teacher.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('manage_teachers'))
        
    # Check if is_excluded exists (it should if models updated)
    if not hasattr(teacher, 'is_excluded'):
        # Fallback if migration not done properly, though we updated models.py
        pass 
    else:
        teacher.is_excluded = not teacher.is_excluded
        db.session.commit()
        status = "استبعاد" if teacher.is_excluded else "تضمين"
        flash(f'تم {status} المعلم {teacher.name} بنجاح', 'success')
        
    return redirect(url_for('manage_teachers'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
