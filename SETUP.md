# Examify Setup Instructions

## Prerequisites
- Python 3.7+
- MySQL Server
- Virtual environment (recommended)

## Installation

1. **Clone and navigate to the project directory**
   ```bash
   cd examify
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up MySQL database**
   - Create a MySQL database named `examify_db`
   - Update the database connection in `app.py` if needed:
     ```python
     app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://username:password@localhost/examify_db'
     ```

5. **Initialize the database**
   ```bash
   python init_db.py
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

7. **Access the application**
   - Open your browser and go to `http://localhost:5000`
   - Register a new account or login with existing credentials

## Features

- **User Registration**: Students and teachers can register with email and password
- **User Login**: Secure authentication with password hashing
- **Role-based Access**: Different dashboards for students and teachers
- **Session Management**: Users stay logged in across page visits
- **Error Handling**: Proper validation and error messages

## User Roles

- **Student**: Can take quizzes and view results
- **Teacher**: Can create topics, quizzes, and view student results

## Database Schema

The application uses the following main tables:
- `users`: User accounts with roles
- `topics`: Quiz topics created by teachers
- `quizzes`: Quizzes with questions
- `questions`: Individual quiz questions
- `student_attempts`: Student quiz attempts and scores
