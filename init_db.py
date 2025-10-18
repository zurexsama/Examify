#!/usr/bin/env python3
"""
Database initialization script for Examify
Run this script to create the database tables
"""

from app import app, db

def init_database():
    """Initialize the database with all tables"""
    with app.app_context():
        try:
            # Drop tables in correct order to avoid foreign key constraints
            print("Dropping existing tables...")
            try:
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))
                db.drop_all()
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
                print("Tables dropped successfully!")
            except Exception as e:
                print(f"Warning: Could not drop tables: {e}")
                print("Continuing with table creation...")
            
            # Create all tables
            print("Creating database tables...")
            db.create_all()
            print("Database tables created successfully!")
            
            # Check if tables exist
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Created tables: {', '.join(tables)}")
            
            # Show table schemas
            for table_name in tables:
                columns = inspector.get_columns(table_name)
                print(f"\nTable '{table_name}' columns:")
                for col in columns:
                    print(f"  - {col['name']}: {col['type']}")
            
        except Exception as e:
            print(f"Error creating database: {e}")
            print("Make sure MySQL is running and the database 'examify_db' exists")

if __name__ == "__main__":
    init_database()
