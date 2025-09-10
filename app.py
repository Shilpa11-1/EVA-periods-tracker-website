from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta
from flask import make_response, request
from utils import calculate_cycle_length, predict_next_period, send_email_reminder, get_cycle_advice
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key'

@app.before_request
def check_guest_cookie():
    if 'user_id' not in session:
        guest_id = request.cookies.get('eva_guest_id')
        if guest_id:
            session['user_id'] = guest_id
            session['name'] = 'Guest'
            session['guest'] = True

@app.template_filter('datetimeformat')
def format_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').strftime('%d-%m-%Y')
    except:
        return value

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/guest')
def guest():
    guest_id = f"guest_{uuid.uuid4().hex[:8]}"
    session['user_id'] = guest_id
    session['name'] = 'Guest'
    session['guest'] = True
    flash('Welcome to Eva! You can use all features for 30 days as a guest. Your data will be saved during this period.', 'info')

    resp = make_response(redirect(url_for('dashboard')))
    resp.set_cookie('eva_guest_id', guest_id, max_age=30*24*60*60)  # 30 days
    return resp

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        conn = get_db()
        c = conn.cursor()

        # Check for existing email or name
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        if c.fetchone():
            flash("Email already registered. Please use a different email.", "danger")
            conn.close()
            return redirect(url_for('register'))

        c.execute("SELECT * FROM users WHERE name = ?", (name,))
        if c.fetchone():
            flash("Name already taken. Try a different one.", "danger")
            conn.close()
            return redirect(url_for('register'))

        # Insert user if all is good
        c.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, password))
        conn.commit()
        conn.close()

        flash("Registration successful!", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['name'] = user['name']
            session.pop('guest', None)  # Remove guest flag
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    logs = conn.execute('SELECT * FROM periods WHERE user_id = ? ORDER BY start_date DESC', 
                        (session['user_id'],)).fetchall()
    conn.close()

    # Convert logs to list for safer handling
    logs_list = [dict(log) for log in logs] if logs else []
    
    next_period = predict_next_period(logs_list)
    return render_template('dashboard.html', name=session['name'], logs=logs_list, next_period=next_period)

@app.route('/track', methods=['GET', 'POST'])
def track():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        start_date = request.form.get('start')
        end_date = request.form.get('end')
        note = request.form.get('note', '')
        user_id = session['user_id']

        # Validate dates
        if not start_date or not end_date:
            flash('Please provide both start and end dates.', 'danger')
            return redirect(url_for('track'))

        try:
            # Validate date format and logic
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            if end_dt < start_dt:
                flash('End date cannot be before start date.', 'danger')
                return redirect(url_for('track'))
            
            cycle_length = calculate_cycle_length(start_date, end_date)
            
        except ValueError:
            flash('Invalid date format. Please use the date picker.', 'danger')
            return redirect(url_for('track'))

        conn = get_db()
        try:
            conn.execute('INSERT INTO periods (user_id, start_date, end_date, length, note) VALUES (?, ?, ?, ?, ?)',
                         (user_id, start_date, end_date, cycle_length, note))
            conn.commit()
            
            # Get cycle advice
            advice = get_cycle_advice(cycle_length)
            
            # Only send email reminder if not guest and has email
            if not session.get('guest') and session.get('email'):
                try:
                    next_start = start_dt + timedelta(days=cycle_length)
                    reminder_date = next_start - timedelta(days=3)
                    send_email_reminder(session['email'], reminder_date, next_start)
                except Exception as e:
                    print(f"Email reminder failed: {e}")
            
            flash(f'Cycle tracked successfully! {advice}', 'success')
            
        except Exception as e:
            print(f"Database error: {e}")
            flash('Error saving cycle data. Please try again.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('dashboard'))

    return render_template('track.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/logout')
def logout():
    session.clear()
    resp = make_response(redirect(url_for('home')))
    resp.set_cookie('eva_guest_id', '', expires=0)  # Clear guest cookie
    return resp

@app.route('/delete_cycle/<int:cycle_id>', methods=['POST'])
def delete_cycle(cycle_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    try:
        conn.execute('DELETE FROM periods WHERE id = ? AND user_id = ?', (cycle_id, session['user_id']))
        conn.commit()
        flash('Cycle entry deleted successfully.', 'success')
    except Exception as e:
        print(f"Delete error: {e}")
        flash('Error deleting cycle entry.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

def init_db():
    conn = get_db()
    try:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT UNIQUE,
                password TEXT
            );
            CREATE TABLE IF NOT EXISTS periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                start_date TEXT,
                end_date TEXT,
                length INTEGER,
                note TEXT
            );
        ''')
        conn.commit()
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)