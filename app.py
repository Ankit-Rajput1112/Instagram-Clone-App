import os
import sqlite3
from flask import Flask, g, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify
from flask import send_file, make_response

@app.route('/register', methods=('GET','POST'))
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        db = get_db()
        if not username or not password:
            flash('Provide username and password')
            return redirect(url_for('register'))
        try:
            db.execute('INSERT INTO users(username, password_hash) VALUES (?, ?)', (username, generate_password_hash(password)))
            db.commit()
        except sqlite3.IntegrityError:
            flash('Username already taken')
            return redirect(url_for('register'))
        
        try:
            avatar_rel = generate_avatar(username)
            # optional: if you want to store avatar path in DB, update users table with avatar column here
            # db.execute('UPDATE users SET avatar_path = ? WHERE username = ?', (avatar_rel, username))
            # db.commit()
        except Exception as e:
            app.logger.warning(f"Avatar generation failed: {e}")

        
        flash('Registered! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=('GET','POST'))
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        db = get_db()

        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if not user:
            flash("No user found")
            return redirect(url_for('login'))

        if not check_password_hash(user['password_hash'], password):
            flash("Wrong password")
            return redirect(url_for('login'))

        session['user_id'] = user['id']
        return redirect(url_for('index'))

    return render_template('login.html')



@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_db()
        print('Initialized database at', DB_PATH)
    app.run(host='0.0.0.0', port=5000, debug=True)
