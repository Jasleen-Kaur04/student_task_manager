from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_guest = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tasks = db.relationship('Task', backref='user', lazy=True, cascade="all, delete-orphan")
    subjects = db.relationship('Subject', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.email}>'

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False) # Removed unique=True so different users can have same subject names
    color = db.Column(db.String(20), nullable=False, default='blue')
    
    # Ownership
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationship to tasks
    tasks = db.relationship('Task', backref='subject_rel', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Subject {self.name}>'

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    
    subject = db.Column(db.String(50), nullable=True) 
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    
    # Ownership
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    deadline = db.Column(db.Date, nullable=True, default=date.today)
    priority = db.Column(db.String(20), nullable=False, default='Medium') 
    status = db.Column(db.String(20), nullable=False, default='Pending') 
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Task {self.title}>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'subject': self.subject_rel.name if self.subject_rel else self.subject,
            'subject_color': self.subject_rel.color if self.subject_rel else 'gray',
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'priority': self.priority,
            'status': self.status,
            'description': self.description
        }
