import os
from app import app
from models import db, User, Subject, Task

with app.app_context():
    # SQLite cannot alter columns easily, and since we just added user_id to Subject and Task and created a User model,
    # it is safest to drop all tables and recreate them if we are still in development.
    print("Dropping all existing tables...")
    db.drop_all()
    
    print("Creating tables with new schema...")
    db.create_all()
    
    print("Database has been successfully re-initialized with the Authentication schema!")
