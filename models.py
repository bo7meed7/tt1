from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    teachers = db.relationship('Teacher', backref='owner', lazy=True, cascade="all, delete-orphan")

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100))
    total_periods = db.Column(db.Integer, default=0)
    substitution_quota = db.Column(db.Integer, default=0)
    is_excluded = db.Column(db.Boolean, default=False)
    slots = db.relationship('Slot', backref='teacher', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Teacher {self.name}>'

class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    day_of_week = db.Column(db.String(20), nullable=False)
    period_number = db.Column(db.Integer, nullable=False)
    has_lesson = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Slot {self.day_of_week} P{self.period_number} - {"Busy" if self.has_lesson else "Free"}>'

class Substitution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    covering_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    day_of_week = db.Column(db.String(20), nullable=False)
    period_number = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships for easy access
    original_teacher = db.relationship('Teacher', foreign_keys=[original_teacher_id], backref='substitutions_requested')
    covering_teacher = db.relationship('Teacher', foreign_keys=[covering_teacher_id], backref='substitutions_covered')

    def __repr__(self):
        return f'<Substitution {self.day_of_week} P{self.period_number}>'