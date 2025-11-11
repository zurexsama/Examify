from flask import Flask, render_template, request, redirect, session, send_file, flash, url_for
import pymysql
pymysql.install_as_MySQLdb()
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import openpyxl
from datetime import datetime
import secrets
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
    code_expires_at = db.Column(db.DateTime)
    max_attempts = db.Column(db.Integer, default=1)  # 0 = unlimited, >0 = limited
    allow_concurrent = db.Column(db.Boolean, default=False)
    access_codes = db.relationship('AccessCode', backref='quiz', lazy=True)

class AccessCode(db.Model):
    __tablename__ = 'access_codes'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'))
    code = db.Column(db.String(8), unique=True)
    is_used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)

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

        # Security settings
        code_expires_at = request.form.get('code_expires_at')
        if code_expires_at:
            from datetime import datetime
            code_expires_at = datetime.fromisoformat(code_expires_at.replace('T', ' '))
        max_attempts = int(request.form.get('max_attempts', '1'))
        allow_concurrent = 'allow_concurrent' in request.form

        # Bulk code generation
        num_codes = int(request.form.get('num_codes', '1'))
        if num_codes < 1:
            num_codes = 1
        elif num_codes > 1000:  # Reasonable limit
            num_codes = 1000

        # Create quiz
        new_quiz = Quiz(
            title=title,
            topic_id=topic_id,
            teacher_id=teacher_id,
            duration=duration,
            total_marks=total_marks,
            code_expires_at=code_expires_at,
            max_attempts=max_attempts,
            allow_concurrent=allow_concurrent
        )
        db.session.add(new_quiz)
        db.session.flush()  # Get quiz ID

        # Generate unique access codes
        def generate_access_code():
            return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

        generated_codes = []
        for _ in range(num_codes):
            code = generate_access_code()
            while AccessCode.query.filter_by(code=code).first():
                code = generate_access_code()
            generated_codes.append(code)

        # Create access code records
        for code in generated_codes:
            access_code_record = AccessCode(
                quiz_id=new_quiz.id,
                code=code
            )
            db.session.add(access_code_record)
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

        # Store generated codes in session for distribution
        session['generated_codes'] = generated_codes
        session['quiz_title'] = title

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

@app.route('/teacher/codes/<int:quiz_id>')
def view_codes(quiz_id):
    if session.get('role') != 'teacher':
        return redirect('/login')

    quiz = Quiz.query.get(quiz_id)
    if not quiz or quiz.teacher_id != session.get('user_id'):
        flash('Quiz not found or access denied.', 'error')
        return redirect('/teacher/dashboard')

    codes = AccessCode.query.filter_by(quiz_id=quiz_id).all()
    # Create a dict of user_id -> user_name for used codes
    users = {}
    for code in codes:
        if code.used_by and code.used_by not in users:
            user = User.query.get(code.used_by)
            if user:
                users[code.used_by] = user.name
    return render_template('teacher/codes.html', quiz=quiz, codes=codes, users=users)

@app.route('/teacher/download-codes/<int:quiz_id>')
def download_codes(quiz_id):
    if session.get('role') != 'teacher':
        return redirect('/login')

    quiz = Quiz.query.get(quiz_id)
    if not quiz or quiz.teacher_id != session.get('user_id'):
        flash('Quiz not found or access denied.', 'error')
        return redirect('/teacher/dashboard')

    # Create Excel workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Access Codes"
    ws.append(['Code', 'Status', 'Used By', 'Used At'])

    codes = AccessCode.query.filter_by(quiz_id=quiz_id).all()
    for code in codes:
        used_by = User.query.get(code.used_by).name if code.used_by else 'Not used'
        used_at = code.used_at.strftime('%Y-%m-%d %H:%M:%S') if code.used_at else 'Not used'
        status = 'Used' if code.is_used else 'Available'
        ws.append([code.code, status, used_by, used_at])

    filename = f'quiz_{quiz_id}_codes.xlsx'
    wb.save(filename)
    return send_file(filename, as_attachment=True)

@app.route('/teacher/print-codes/<int:quiz_id>')
def print_codes(quiz_id):
    if session.get('role') != 'teacher':
        return redirect('/login')

    quiz = Quiz.query.get(quiz_id)
    if not quiz or quiz.teacher_id != session.get('user_id'):
        flash('Quiz not found or access denied.', 'error')
        return redirect('/teacher/dashboard')

    codes = AccessCode.query.filter_by(quiz_id=quiz_id, is_used=False).all()
    from datetime import datetime
    now = datetime.now()
    return render_template('teacher/print_codes.html', quiz=quiz, codes=codes, now=now)

@app.route('/teacher/email-codes/<int:quiz_id>', methods=['GET', 'POST'])
def email_codes(quiz_id):
    if session.get('role') != 'teacher':
        return redirect('/login')

    quiz = Quiz.query.get(quiz_id)
    if not quiz or quiz.teacher_id != session.get('user_id'):
        flash('Quiz not found or access denied.', 'error')
        return redirect('/teacher/dashboard')

    if request.method == 'POST':
        emails = request.form.get('emails', '').split(',')
        emails = [email.strip() for email in emails if email.strip()]

        if not emails:
            flash('Please enter at least one email address.', 'error')
            return redirect(url_for('email_codes', quiz_id=quiz_id))

        codes = AccessCode.query.filter_by(quiz_id=quiz_id, is_used=False).limit(len(emails)).all()

        if len(codes) < len(emails):
            flash(f'Not enough available codes. Only {len(codes)} codes available for {len(emails)} emails.', 'error')
            return redirect(url_for('email_codes', quiz_id=quiz_id))

            # Email configuration
        SMTP_SERVER = 'smtp.gmail.com'
        SMTP_PORT = 587
        SENDER_EMAIL = 'lamanilaoexequiel4@gmail.com'  # Replace with actual Gmail address
        SENDER_PASSWORD = 'oytl rkgz lwvl qisf'  # Replace with app password


        try:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)

            for i, email in enumerate(emails):
                if i < len(codes):
                    code = codes[i]

                    msg = MIMEMultipart()
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = email
                    msg['Subject'] = f'Access Code for Quiz: {quiz.title}'

                    body = f"""
                    Hello,

                    You have been assigned an access code for the quiz "{quiz.title}".

                    Access Code: {code.code}

                    Please use this code to access the quiz. The code can only be used once.

                    Best regards,
                    Examify Team
                    """
                    msg.attach(MIMEText(body, 'plain'))

                    server.send_message(msg)

            server.quit()
            flash(f'Successfully sent {len(emails)} access codes via email.', 'success')

        except Exception as e:
            flash(f'Failed to send emails: {str(e)}. Please check your email configuration.', 'error')

        return redirect(url_for('view_codes', quiz_id=quiz_id))

    return render_template('teacher/email_codes.html', quiz=quiz)

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

@app.route('/student/dashboard', methods=['GET', 'POST'])
def student_dashboard():
    if session.get('role') != 'student':
        return redirect('/login')

    # Get student's past attempts
    student_id = session.get('user_id')
    attempts = StudentAttempt.query.filter_by(student_id=student_id).all()

    return render_template('student/dashboard.html',
                          attempts=attempts)

@app.route('/student/take-quiz/<int:quiz_id>')
def take_quiz(quiz_id):
    if session.get('role') != 'student':
        return redirect('/login')

    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect('/student/dashboard')

    # Verify access code was used (since we redirect here only after valid access code)
    # Additional security: check if student has already attempted
    student_id = session.get('user_id')
    existing_attempt = StudentAttempt.query.filter_by(student_id=student_id, quiz_id=quiz_id).first()
    if existing_attempt:
        flash('You have already attempted this quiz.', 'error')
        return redirect('/student/dashboard')

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

    # Clear active session for this quiz
    if 'active_quiz_sessions' in session and quiz_id in session['active_quiz_sessions']:
        session['active_quiz_sessions'].remove(quiz_id)
        session.modified = True

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

@app.route('/student/enter-access-code', methods=['POST'])
def enter_access_code():
    if session.get('role') != 'student':
        return redirect('/login')

    access_code = request.form.get('access_code', '').strip().upper()
    if not access_code:
        flash('Please enter an access code.', 'error')
        return redirect('/student/dashboard')

    # Validate format (8 characters, alphanumeric uppercase)
    if len(access_code) != 8 or not access_code.isalnum():
        flash('Invalid format: Access code must be exactly 8 alphanumeric characters.', 'error')
        return redirect('/student/dashboard')

    # Find access code in database
    code_record = AccessCode.query.filter_by(code=access_code).first()
    if not code_record:
        flash('Invalid access code: Code does not exist.', 'error')
        return redirect('/student/dashboard')

    quiz = Quiz.query.get(code_record.quiz_id)
    if not quiz:
        flash('Invalid access code: Associated quiz not found.', 'error')
        return redirect('/student/dashboard')

    # Check if code is already used
    if code_record.is_used:
        flash('Code already used: This access code has already been redeemed.', 'error')
        return redirect('/student/dashboard')

    # Check expiration
    if quiz.code_expires_at and datetime.now() > quiz.code_expires_at:
        flash('Code expired: This access code has expired.', 'error')
        return redirect('/student/dashboard')

    student_id = session.get('user_id')

    # Check concurrent access
    if not quiz.allow_concurrent:
        # Check if any student is currently taking this quiz
        # This is a simple check - in production, you'd want more sophisticated session tracking
        active_sessions = session.get('active_quiz_sessions', [])
        if quiz.id in active_sessions:
            flash('Quiz in use: Another student is currently taking this quiz. Please wait and try again.', 'error')
            return redirect('/student/dashboard')

    # Check attempt limits
    existing_attempts = StudentAttempt.query.filter_by(student_id=student_id, quiz_id=quiz.id).count()
    if quiz.max_attempts > 0 and existing_attempts >= quiz.max_attempts:
        flash(f'Attempt limit reached: You have reached the maximum number of attempts ({quiz.max_attempts}) for this quiz.', 'error')
        return redirect('/student/dashboard')

    # Mark code as used
    code_record.is_used = True
    code_record.used_by = student_id
    code_record.used_at = datetime.now()
    db.session.commit()

    # Mark session as active for this quiz
    if not quiz.allow_concurrent:
        if 'active_quiz_sessions' not in session:
            session['active_quiz_sessions'] = []
        if quiz.id not in session['active_quiz_sessions']:
            session['active_quiz_sessions'].append(quiz.id)

    return redirect(f'/student/take-quiz/{quiz.id}')

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
    # Clear any active quiz sessions on logout
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

