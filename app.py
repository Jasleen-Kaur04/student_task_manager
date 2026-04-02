import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Task, Subject, User
from datetime import date, timedelta, datetime

# Ensure database directory exists
db_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

app = Flask(__name__)
# Basic config
app.config['SECRET_KEY'] = 'dev-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(db_dir, 'tasks.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Flask-Login Configuration
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize DB
with app.app_context():
    # Since we added new non-nullable columns, this might fail on an existing DB.
    # We will try to create all. If updating an existing schema, SQLite requires a manual drop or migration.
    # For this exercise, dropping all might be necessary to recreate clean tables if we run into issues,
    # but db.create_all() works for new DB creations.
    db.create_all()

# --- AUTH ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
            
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return redirect(url_for('register'))
            
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already exists.', 'danger')
            return redirect(url_for('register'))
            
        # Create new user
        new_user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
            is_guest=False
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully. You can now log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/guest-login', methods=['POST'])
def guest_login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    # Create a unique guest email using timestamp
    guest_email = f"guest_{datetime.now().strftime('%Y%md%H%M%S')}@temp.local"
    
    # Create temporary guest user
    guest_user = User(
        name="Guest User",
        email=guest_email,
        password_hash=generate_password_hash("guest_pass_random", method='pbkdf2:sha256'),
        is_guest=True
    )
    
    db.session.add(guest_user)
    db.session.commit()
    
    # Pre-populate some subjects for the guest
    defaults = [
        Subject(name='Mathematics', color='blue', user_id=guest_user.id),
        Subject(name='Science', color='green', user_id=guest_user.id),
        Subject(name='Literature', color='purple', user_id=guest_user.id)
    ]
    db.session.bulk_save_objects(defaults)
    db.session.commit()
    
    # Pre-populate a sample task
    sample_subj = Subject.query.filter_by(user_id=guest_user.id).first()
    sample_task = Task(
        title="Welcome to Student Task Manager!",
        description="This is a sample task. Feel free to edit or delete it.",
        priority="Medium",
        deadline=date.today(),
        user_id=guest_user.id,
        subject_id=sample_subj.id if sample_subj else None
    )
    db.session.add(sample_task)
    db.session.commit()
    
    login_user(guest_user)
    flash('Logged in as Guest. Your data will be deleted when you log out.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    # If it's a guest user, clean up their data
    if current_user.is_guest:
        # Relationships cascade="all, delete-orphan" will auto-delete subjects and tasks linked to user_id
        db.session.delete(current_user)
        db.session.commit()
        flash('Guest session ended. Data wiped cleanly.', 'info')
    else:
        flash('You have been logged out.', 'info')
        
    logout_user()
    return redirect(url_for('login'))


# --- DASHBOARD ROUTE ---
@app.route('/')
@app.route('/dashboard') # Explicit alias for url_for mapping consistency
@login_required
def dashboard():
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.deadline.asc()).limit(5).all()
    
    # Calculate analytics
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    total_tasks = len(all_tasks)
    completed_tasks = sum(1 for task in all_tasks if task.status == 'Completed')
    pending_tasks = total_tasks - completed_tasks
    
    today = date.today()
    due_today = sum(1 for task in all_tasks if task.deadline == today and task.status != 'Completed')

    completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    return render_template('dashboard.html', 
                           tasks=tasks, 
                           total_tasks=total_tasks,
                           completed_tasks=completed_tasks,
                           pending_tasks=pending_tasks,
                           due_today=due_today,
                           completion_percentage=completion_percentage,
                           today=today)

# --- TASKS ROUTES ---
@app.route('/tasks')
@login_required
def tasks_page():
    search_query = request.args.get('search', '')
    subject_filter = request.args.get('subject_id', '')
    sort_by = request.args.get('sort', 'deadline')

    query = Task.query.filter_by(user_id=current_user.id)

    if search_query:
        query = query.filter(Task.title.ilike(f'%{search_query}%') | Task.description.ilike(f'%{search_query}%'))
    
    if subject_filter:
        query = query.filter_by(subject_id=subject_filter)

    if sort_by == 'deadline':
        query = query.order_by(Task.deadline.asc())
    elif sort_by == 'priority':
        query = query.order_by(Task.priority.desc())
    elif sort_by == 'subject':
        query = query.order_by(Task.subject_id.asc())

    tasks = query.all()
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()

    return render_template('tasks.html', tasks=tasks, subjects=subjects, today=date.today())

@app.route('/tasks/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form['title']
        subject_id = request.form.get('subject_id')
        deadline_str = request.form.get('deadline')
        priority = request.form['priority']
        description = request.form['description']

        deadline = date.fromisoformat(deadline_str) if deadline_str else None

        new_task = Task(
            title=title,
            subject_id=subject_id if subject_id else None,
            user_id=current_user.id,
            deadline=deadline,
            priority=priority,
            description=description
        )

        db.session.add(new_task)
        db.session.commit()
        flash('Task added successfully!', 'success')
        return redirect(url_for('tasks_page'))

    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()
    return render_template('add_task.html', subjects=subjects)

@app.route('/tasks/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_task(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        task.title = request.form['title']
        task.subject_id = request.form.get('subject_id') if request.form.get('subject_id') else None
        deadline_str = request.form.get('deadline')
        task.priority = request.form['priority']
        task.description = request.form['description']
        
        if 'status' in request.form:
             task.status = request.form['status']

        if deadline_str:
            task.deadline = date.fromisoformat(deadline_str)
        else:
            task.deadline = None

        db.session.commit()
        flash('Task updated successfully!', 'success')
        return redirect(url_for('tasks_page'))

    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()
    return render_template('edit_task.html', task=task, subjects=subjects)

@app.route('/tasks/complete/<int:id>', methods=['POST'])
@login_required
def complete_task(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    if task.status == 'Completed':
        task.status = 'Pending'
        flash('Task marked as pending.', 'info')
    else:
        task.status = 'Completed'
        flash('Task marked as completed.', 'success')
    db.session.commit()
    return redirect(request.referrer or url_for('tasks_page'))

@app.route('/tasks/delete/<int:id>', methods=['POST'])
@login_required
def delete_task(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully!', 'danger')
    return redirect(url_for('tasks_page'))

# --- SUBJECTS ROUTES ---
@app.route('/subjects', methods=['GET', 'POST'])
@login_required
def subjects_page():
    if request.method == 'POST':
        name = request.form['name']
        color = request.form['color']
        
        # Check if exists for this user
        existing = Subject.query.filter_by(name=name, user_id=current_user.id).first()
        if existing:
            flash(f'Subject "{name}" already exists.', 'danger')
        else:
            new_subj = Subject(name=name, color=color, user_id=current_user.id)
            db.session.add(new_subj)
            db.session.commit()
            flash('Subject created successfully!', 'success')
            return redirect(url_for('subjects_page'))
            
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()
    return render_template('subjects.html', subjects=subjects)

@app.route('/subjects/delete/<int:id>', methods=['POST'])
@login_required
def delete_subject(id):
    subject = Subject.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(subject)
    db.session.commit()
    flash('Subject deleted successfully!', 'danger')
    return redirect(url_for('subjects_page'))

# --- CALENDAR ROUTE ---
@app.route('/calendar')
@login_required
def calendar_page():
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    tasks_data = [t.to_dict() for t in all_tasks]
    return render_template('calendar.html', tasks_json=tasks_data)

# --- ANALYTICS ROUTE ---
@app.route('/analytics')
@login_required
def analytics_page():
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    total_tasks = len(all_tasks)
    completed_tasks = sum(1 for task in all_tasks if task.status == 'Completed')
    completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Tasks by subject
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    subject_counts = []
    subject_colors = []
    
    for subj in subjects:
        count = sum(1 for task in all_tasks if task.subject_id == subj.id)
        subject_counts.append(count)
        color_map = {
            'blue': '#3B82F6', 'red': '#EF4444', 'green': '#10B981', 
            'yellow': '#EAB308', 'purple': '#8B5CF6', 'pink': '#EC4899', 
            'indigo': '#6366F1', 'gray': '#6B7280'
        }
        subject_colors.append(color_map.get(subj.color, '#6B7280'))

    # Weekly completion data
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    
    weekly_labels = [(start_of_week + timedelta(days=i)).strftime('%a') for i in range(7)]
    weekly_completed = [0] * 7
    weekly_pending = [0] * 7
    
    for task in all_tasks:
        if task.deadline and start_of_week <= task.deadline <= start_of_week + timedelta(days=6):
            day_idx = (task.deadline - start_of_week).days
            if task.status == 'Completed':
                weekly_completed[day_idx] += 1
            else:
                weekly_pending[day_idx] += 1

    return render_template('analytics.html',
                           total=total_tasks,
                           completed=completed_tasks,
                           percentage=completion_percentage,
                           subjects=[s.name for s in subjects],
                           subject_counts=subject_counts,
                           subject_colors=subject_colors,
                           weekly_labels=weekly_labels,
                           weekly_completed=weekly_completed,
                           weekly_pending=weekly_pending)

# --- SETTINGS ROUTE ---
@app.route('/settings')
@login_required
def settings_page():
    return render_template('settings.html')


if __name__ == '__main__':
    app.run(debug=True, port=5000)
