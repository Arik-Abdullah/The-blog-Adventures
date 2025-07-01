from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import sqlite3
import hashlib
import os
import bcrypt
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# Fix 1: Use environment variable for secret key with secure fallback
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Database initialization
def init_db():
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL
        )
    ''')
    
    # Posts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    
    # Fix 2: Use parameterized queries to prevent SQL injection
    search_term = request.args.get('search', '')
    if search_term:
        cursor.execute("SELECT * FROM posts WHERE title LIKE ? OR content LIKE ?", 
                      (f'%{search_term}%', f'%{search_term}%'))
    else:
        cursor.execute("SELECT * FROM posts ORDER BY created_at DESC")
    
    posts = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', posts=posts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('blog.db')
        cursor = conn.cursor()
        
        # Fix 3: Proper password verification with hashing
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2]):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        conn = sqlite3.connect('blog.db')
        cursor = conn.cursor()
        
        try:
            # Fix 3: Hash passwords before storing them
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            cursor.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                          (username, password_hash, email))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error='Username already exists')
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM posts WHERE author_id = ?", (session['user_id'],))
    user_posts = cursor.fetchall()
    conn.close()
    
    return render_template('dashboard.html', posts=user_posts)

@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        conn = sqlite3.connect('blog.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO posts (title, content, author_id) VALUES (?, ?, ?)",
                      (title, content, session['user_id']))
        conn.commit()
        conn.close()
        
        return redirect(url_for('dashboard'))
    
    return render_template('create_post.html')

@app.route('/api/posts')
def api_posts():
    # Fix 4: Add pagination to prevent memory issues
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    offset = (page - 1) * per_page
    
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    
    # Get total count for pagination metadata
    cursor.execute("SELECT COUNT(*) FROM posts")
    total_posts = cursor.fetchone()[0]
    
    # Get paginated results
    cursor.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT ? OFFSET ?", 
                  (per_page, offset))
    posts = cursor.fetchall()
    conn.close()
    
    # Convert to list of dictionaries
    post_list = []
    for post in posts:
        post_dict = {
            'id': post[0],
            'title': post[1],
            'content': post[2],
            'author_id': post[3],
            'created_at': post[4]
        }
        post_list.append(post_dict)
    
    # Return paginated response with metadata
    return jsonify({
        'posts': post_list,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total_posts,
            'pages': (total_posts + per_page - 1) // per_page
        }
    })

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    # Fix 5: Use environment variable to control debug mode
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode)