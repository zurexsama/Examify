from flask import Flask, render_template, request, redirect, session, send_file, flash
import pymysql
pymysql.install_as_MySQLdb()
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import openpyxl
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/examify_db'
app.config['SECRET_KEY'] = 'your-secret-key-here'
db = SQLAlchemy(app)

# Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    role = db.Column(db.Enum('admin', 'teacher', 'student'))

class Topic(db.Model):
    __tablename__ = 'topics'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.Text)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    duration = db.Column(db.Integer)
    total_marks = db.Column(db.Integer)

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'))
    question_text = db.Column(db.Text)
    question_type = db.Column(db.Enum('multiple_choice', 'true_false'))
    marks = db.Column(db.Integer)
    correct_answer = db.Column(db.Text)

class Option(db.Model):
    __tablename__ = 'options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'))
    option_text = db.Column(db.Text)
    is_correct = db.Column(db.Boolean, default=False)

class StudentAttempt(db.Model):
    __tablename__ = 'student_attempts'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'))
    score = db.Column(db.Float)
    total_marks = db.Column(db.Integer)
    percentage = db.Column(db.Float)
    completed_at = db.Column(db.DateTime)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            session['name'] = user.name
            
            if user.role == 'teacher':
                return redirect('/teacher/dashboard')
            else:
                return redirect('/student/dashboard')
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('register.html', error="Email already registered")
        
        # Validate password length
        if len(password) < 6:
            return render_template('register.html', error="Password must be at least 6 characters")
        
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password=hashed_password, role=role)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return render_template('register.html', success="Registration successful! Please login.")
        except Exception as e:
            db.session.rollback()
            return render_template('register.html', error="Registration failed. Please try again.")
    
    return render_template('register.html')

@app.route('/teacher/dashboard')
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect('/login')
    
    teacher_id = session.get('user_id')
    topics = Topic.query.filter_by(teacher_id=teacher_id).all()
    quizzes = Quiz.query.filter_by(teacher_id=teacher_id).all()
    return render_template('teacher/dashboard.html', topics=topics, quizzes=quizzes)

@app.route('/teacher/create-topic', methods=['GET', 'POST'])
def create_topic():
    if session.get('role') != 'teacher':
        return redirect('/login')

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        teacher_id = session.get('user_id')

        new_topic = Topic(name=name, description=description, teacher_id=teacher_id)
        db.session.add(new_topic)
        db.session.commit()
        return redirect('/teacher/dashboard')
    return render_template('teacher/create_topic.html')

@app.route('/teacher/delete-topic/<int:topic_id>', methods=['POST'])
def delete_topic(topic_id):
    if session.get('role') != 'teacher':
        return redirect('/login')

    teacher_id = session.get('user_id')
    topic = Topic.query.filter_by(id=topic_id, teacher_id=teacher_id).first()

    if not topic:
        flash('Topic not found or you do not have permission to delete it.', 'error')
        return redirect('/teacher/dashboard')

    try:
        # Check if topic has associated quizzes
        associated_quizzes = Quiz.query.filter_by(topic_id=topic_id).count()
        if associated_quizzes > 0:
            flash(f'Cannot delete topic "{topic.name}" because it has {associated_quizzes} associated quiz(es). Please delete the quizzes first.', 'error')
            return redirect('/teacher/dashboard')

        db.session.delete(topic)
        db.session.commit()
        flash(f'Topic "{topic.name}" has been deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the topic. Please try again.', 'error')

    return redirect('/teacher/dashboard')

@app.route('/teacher/delete-quiz/<int:quiz_id>', methods=['POST'])
def delete_quiz(quiz_id):
    if session.get('role') != 'teacher':
        return redirect('/login')

    teacher_id = session.get('user_id')
    quiz = Quiz.query.filter_by(id=quiz_id, teacher_id=teacher_id).first()

    if not quiz:
        flash('Quiz not found or you do not have permission to delete it.', 'error')
        return redirect('/teacher/dashboard')

    try:
        # Check if quiz has associated attempts
        associated_attempts = StudentAttempt.query.filter_by(quiz_id=quiz_id).count()
        if associated_attempts > 0:
            flash(f'Cannot delete quiz "{quiz.title}" because it has {associated_attempts} associated attempt(s).', 'error')
            return redirect('/teacher/dashboard')

        # Delete options first
        questions = Question.query.filter_by(quiz_id=quiz_id).all()
        for question in questions:
            Option.query.filter_by(question_id=question.id).delete()

        # Delete questions
        Question.query.filter_by(quiz_id=quiz_id).delete()

        # Delete quiz
        db.session.delete(quiz)
        db.session.commit()
        flash(f'Quiz "{quiz.title}" has been deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the quiz. Please try again.', 'error')

    return redirect('/teacher/dashboard')

@app.route('/teacher/create-quiz', methods=['GET', 'POST'])
def create_quiz():
    if session.get('role') != 'teacher':
        return redirect('/login')
    
    if request.method == 'POST':
        title = request.form['title']
        topic_id = request.form['topic_id']
        duration = int(request.form['duration'])
        total_marks = int(request.form['total_marks'])
        teacher_id = session.get('user_id')
        
        # Create quiz
        new_quiz = Quiz(
            title=title,
            topic_id=topic_id,
            teacher_id=teacher_id,
            duration=duration,
            total_marks=total_marks
        )
        db.session.add(new_quiz)
        db.session.flush()  # Get the quiz ID
        
        # Add questions
        question_index = 0
        while f'questions[{question_index}][text]' in request.form:
            question_text = request.form[f'questions[{question_index}][text]']
            marks = int(request.form[f'questions[{question_index}][marks]'])
            
            # Get options
            options = []
            option_index = 0
            while f'questions[{question_index}][options][{option_index}]' in request.form:
                option_text = request.form[f'questions[{question_index}][options][{option_index}]']
                if option_text.strip():  # Only add non-empty options
                    options.append(option_text.strip())
                option_index += 1
            
            # Get correct answer index
            correct_answer_index = int(request.form.get(f'questions[{question_index}][correct]', '0'))
            
            if len(options) >= 2:  # At least 2 options required
                # Create question
                new_question = Question(
                    quiz_id=new_quiz.id,
                    question_text=question_text,
                    question_type='multiple_choice',
                    marks=marks,
                    correct_answer=str(correct_answer_index)
                )
                db.session.add(new_question)
                db.session.flush()  # Get the question ID
                
                # Create options
                for i, option_text in enumerate(options):
                    new_option = Option(
                        question_id=new_question.id,
                        option_text=option_text,
                        is_correct=(i == correct_answer_index)
                    )
                    db.session.add(new_option)
            
            question_index += 1
        
        db.session.commit()
        return redirect('/teacher/dashboard')
    
    # Get topics for the dropdown
    teacher_id = session.get('user_id')
    topics = Topic.query.filter_by(teacher_id=teacher_id).all()
    return render_template('teacher/create_quiz.html', topics=topics)

@app.route('/teacher/results/<int:quiz_id>')
def view_results(quiz_id):
    # Get all attempts for this quiz with student details
    results = db.session.query(
        StudentAttempt, User
    ).join(User, StudentAttempt.student_id == User.id
    ).filter(StudentAttempt.quiz_id == quiz_id).all()
    
    quiz = Quiz.query.get(quiz_id)
    return render_template('teacher/results.html', results=results, quiz=quiz)

@app.route('/teacher/download-scores/<int:quiz_id>')
def download_scores(quiz_id):
    # Create Excel workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Quiz Results"
    
    # Headers
    ws.append(['Student Name', 'Email', 'Score', 'Total Marks', 'Percentage', 'Date'])
    
    # Fetch data
    results = db.session.query(
        User.name, User.email, 
        StudentAttempt.score, StudentAttempt.total_marks, 
        StudentAttempt.percentage, StudentAttempt.completed_at
    ).join(User, StudentAttempt.student_id == User.id
    ).filter(StudentAttempt.quiz_id == quiz_id).all()
    
    for result in results:
        ws.append(list(result))
    
    # Save file
    filename = f'quiz_{quiz_id}_scores.xlsx'
    wb.save(filename)
    return send_file(filename, as_attachment=True)

@app.route('/student/dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        return redirect('/login')
    
    # Get available quizzes grouped by topics
    topics_with_quizzes = db.session.query(Topic, Quiz).join(
        Quiz, Topic.id == Quiz.topic_id
    ).all()
    
    # Get student's past attempts
    student_id = session.get('user_id')
    attempts = StudentAttempt.query.filter_by(student_id=student_id).all()
    
    return render_template('student/dashboard.html', 
                         topics_with_quizzes=topics_with_quizzes,
                         attempts=attempts)

@app.route('/student/take-quiz/<int:quiz_id>')
def take_quiz(quiz_id):
    if session.get('role') != 'student':
        return redirect('/login')
    
    quiz = Quiz.query.get(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    
    # Get options for each question
    questions_with_options = []
    for question in questions:
        options = Option.query.filter_by(question_id=question.id).all()
        questions_with_options.append({
            'question': question,
            'options': options
        })
    
    return render_template('student/take_quiz.html', quiz=quiz, questions_with_options=questions_with_options)

@app.route('/student/submit-quiz/<int:quiz_id>', methods=['POST'])
def submit_quiz(quiz_id):
    if session.get('role') != 'student':
        return redirect('/login')
    
    student_id = session.get('user_id')
    quiz = Quiz.query.get(quiz_id)
    
    # Calculate score
    total_score = 0
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    
    for question in questions:
        student_answer = request.form.get(f'question_{question.id}')
        if student_answer == question.correct_answer:
            total_score += question.marks
    
    percentage = (total_score / quiz.total_marks) * 100
    
    # Save attempt
    attempt = StudentAttempt(
        student_id=student_id,
        quiz_id=quiz_id,
        score=total_score,
        total_marks=quiz.total_marks,
        percentage=percentage,
        completed_at=datetime.now()
    )
    db.session.add(attempt)
    db.session.commit()
    
    return redirect(f'/student/result/{attempt.id}')

@app.route('/student/result/<int:attempt_id>')
def view_result(attempt_id):
    if session.get('role') != 'student':
        return redirect('/login')
    
    attempt = StudentAttempt.query.get(attempt_id)
    if not attempt or attempt.student_id != session.get('user_id'):
        return redirect('/student/dashboard')
    
    quiz = Quiz.query.get(attempt.quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz.id).all()
    
    return render_template('student/result.html', 
                         attempt=attempt, 
                         quiz=quiz, 
                         questions=questions)

@app.route('/')
def index():
    if session.get('user_id'):
        if session.get('role') == 'teacher':
            return redirect('/teacher/dashboard')
        else:
            return redirect('/student/dashboard')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/quiz')
def quiz():
    # Example question and choices (replace with db-driven logic)
    question = {
        'number': 1,
        'text': 'Which of the following is considered father of modern psychology?',
        'choices': ['Wilhelm Wundt', 'Sigmum Freud', 'B.F. Skinner', 'Carl Jung'],
        'selected': None,
        'progress': '1/10',
        'time_left': '09:30',
    }
    return render_template('quiz.html', question=question)
# ... Add more routes for next, previous, submit, etc.




if __name__ == "__main__":
    app.run(debug=True)

