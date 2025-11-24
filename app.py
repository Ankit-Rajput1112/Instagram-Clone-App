# InstaClone minimal Flask app (development only)
import os
import sqlite3
from flask import Flask, g, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify
from flask import send_file, make_response
import io
from PIL import Image, ImageDraw, ImageFont

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'instaclone.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif'}
3
app = Flask(__name__)
app.config.update(SECRET_KEY='dev-secret-key-change-me', UPLOAD_FOLDER=UPLOAD_FOLDER, MAX_CONTENT_LENGTH=8*1024*1024)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

AVATAR_FOLDER = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars')
os.makedirs(AVATAR_FOLDER, exist_ok=True)

def generate_avatar(username, size=256, bg_color=None, fg_color='white'):
    """
    Create a circular avatar PNG with the first letter of username (uppercase).
    Saves to uploads/avatars/<username>.png and returns relative filename (avatars/<username>.png).
    """
    if not username:
        username = 'U'
    first = username.strip()[0].upper()

    # choose background color deterministically from username
    if bg_color is None:
        # simple hash -> pick color from palette
        palette = [
            "#E57373","#F06292","#BA68C8","#9575CD","#64B5F6",
            "#4DB6AC","#81C784","#FFD54F","#FF8A65","#A1887F"
        ]
        bg_color = palette[abs(hash(username)) % len(palette)]

    filename = f"{username}.png"
    out_path = os.path.join(AVATAR_FOLDER, filename)

    # create image
    img = Image.new('RGBA', (size, size), bg_color)
    draw = ImageDraw.Draw(img)

    # draw circle (optional subtle antialias)
    circle_mask = Image.new('L', (size, size), 0)
    mc = ImageDraw.Draw(circle_mask)
    mc.ellipse((0,0,size-1,size-1), fill=255)
    img.putalpha(circle_mask)

    # font
    try:
        # try a common truetype font; fallback to default
        font_size = int(size * 0.5)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    # center letter
    w, h = draw.textsize(first, font=font)
    x = (size - w) / 2
    y = (size - h) / 2 - (size * 0.03)  # slight vertical adjustment
    draw.text((x, y), first, font=font, fill=fg_color)

    # save as PNG
    img.save(out_path, format='PNG')

    # return relative path used by upload route
    return f"avatars/{filename}"


def get_db():
    db = getattr(g, '_db', None)
    if db is None:
        db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        db.row_factory = sqlite3.Row
        g._db = db
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, '_db', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        schema_path = os.path.join(BASE_DIR, 'schema.sql')
        with open(schema_path, 'r') as f:
            db.executescript(f.read())
        db.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    db = get_db()
    return db.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()

# helper functions to use in templates
def get_like_count(message_id):
    db = get_db()
    row = db.execute('SELECT COUNT(*) AS cnt FROM message_likes WHERE message_id = ?', (message_id,)).fetchone()
    return row['cnt'] if row else 0


def get_comments_list(post_id):
    """Return list of comment rows for a post (each row has id, user_id, text, created_at, username)."""
    db = get_db()
    rows = db.execute('''
      SELECT c.id, c.user_id, c.text, c.created_at, u.username
      FROM comments c
      JOIN users u ON u.id = c.user_id
      WHERE c.post_id = ?
      ORDER BY c.created_at ASC
    ''', (post_id,)).fetchall()
    return rows

# expose to Jinja templates globally
@app.context_processor
def utility_processor():
    return {
        'get_comments_list': get_comments_list
        # you can also add other helpers here if needed
    }
# --------------------------------------------------------------


@app.route('/')
def index():
    db = get_db()
    rows = db.execute(
        'SELECT posts.*, users.username FROM posts JOIN users ON posts.user_id = users.id ORDER BY posts.created_at DESC LIMIT 200'
    ).fetchall()

    user = current_user()
    posts = []

    for r in rows:
        post = dict(r)
        
        # LIKE COUNT
        post['like_count'] = db.execute(
            'SELECT COUNT(*) FROM likes WHERE post_id = ?',
            (post['id'],)
        ).fetchone()[0]

        # COMMENT COUNT
        post['comment_count'] = db.execute(
            'SELECT COUNT(*) FROM comments WHERE post_id = ?',
            (post['id'],)
        ).fetchone()[0]

        # WHETHER USER LIKED THIS POST
        if user:
            liked = db.execute(
                'SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?',
                (user['id'], post['id'])
            ).fetchone()
            post['liked_by_me'] = bool(liked)
        else:
            post['liked_by_me'] = False
        
        posts.append(post)

    return render_template('feed.html', posts=posts, user=user)


# Toggle like on a specific message (server-side, no JS)
@app.route('/messages/<int:other_id>/like_message/<int:message_id>', methods=('POST',))
def like_message_server(other_id, message_id):
    user = current_user()
    if not user:
        flash('Login required')
        return redirect(url_for('login'))
    db = get_db()
    try:
        db.execute('INSERT INTO message_likes(message_id, user_id) VALUES (?, ?)', (message_id, user['id']))
        db.commit()
    except sqlite3.IntegrityError:
        db.execute('DELETE FROM message_likes WHERE message_id = ? AND user_id = ?', (message_id, user['id']))
        db.commit()
    # redirect back to conversation view
    return redirect(url_for('messages_thread', other_id=other_id))


@app.route('/post/<int:post_id>/comment/<int:comment_id>/delete', methods=('POST',))
def delete_comment(post_id, comment_id):
    user = current_user()
    if not user:
        flash('Login required')
        return redirect(url_for('login'))

    db = get_db()
    # fetch comment
    comment = db.execute('SELECT * FROM comments WHERE id = ?', (comment_id,)).fetchone()
    if not comment:
        flash('Comment not found')
        return redirect(url_for('post_comments_page', post_id=post_id))

    # fetch post owner
    post = db.execute('SELECT id, user_id FROM posts WHERE id = ?', (post_id,)).fetchone()
    if not post:
        flash('Post not found')
        return redirect(url_for('index'))

    # allow if commenter OR post owner
    if comment['user_id'] != user['id'] and post['user_id'] != user['id']:
        flash('You are not authorized to delete this comment')
        return redirect(url_for('post_comments_page', post_id=post_id))

    # perform delete
    db.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
    db.commit()
    flash('Comment deleted')
    return redirect(url_for('post_comments_page', post_id=post_id))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, conditional=True)

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

# Messages listing: show recent conversations (simple)
@app.route('/messages')
def messages_index():
    user = current_user()
    if not user:
        flash('Login required')
        return redirect(url_for('login'))
    db = get_db()
    # get list of distinct other_user ids that this user has messages with
    rows = db.execute("""
        SELECT u.id, u.username,
               (SELECT text FROM messages m2 WHERE (m2.sender_id = u.id AND m2.receiver_id = ?) OR (m2.sender_id = ? AND m2.receiver_id = u.id) ORDER BY m2.created_at DESC LIMIT 1) AS last_text,
               (SELECT m3.created_at FROM messages m3 WHERE (m3.sender_id = u.id AND m3.receiver_id = ?) OR (m3.sender_id = ? AND m3.receiver_id = u.id) ORDER BY m3.created_at DESC LIMIT 1) AS last_at
        FROM users u
        WHERE u.id != ?
        ORDER BY last_at DESC
        LIMIT 100
    """, (user['id'], user['id'], user['id'], user['id'], user['id'])).fetchall()
    return render_template('messages_index.html', user=user, conversations=rows)

# Conversation view + sending
@app.route('/messages/<int:other_id>', methods=('GET','POST'))
def messages_thread(other_id):
    user = current_user()
    if not user:
        flash('Login required')
        return redirect(url_for('login'))
    db = get_db()
    other = db.execute('SELECT id, username FROM users WHERE id = ?', (other_id,)).fetchone()
    if not other:
        flash('User not found')
        return redirect(url_for('messages_index'))
    if request.method == 'POST':
        text = request.form.get('text','').strip()
        if text:
            db.execute('INSERT INTO messages(sender_id, receiver_id, text) VALUES (?, ?, ?)', (user['id'], other_id, text))
            db.commit()
        return redirect(url_for('messages_thread', other_id=other_id))
    # fetch last 100 messages between them
    msgs = db.execute("""
        SELECT m.*, us.username as sender_username
        FROM messages m
        JOIN users us ON us.id = m.sender_id
        WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)
        ORDER BY m.created_at ASC
        LIMIT 500
    """, (user['id'], other_id, other_id, user['id'])).fetchall()
    other_pic_url = '/mnt/data/021ed325-9a52-4ff6-92c9-59fd77f32641.png'
    return render_template('messages_thread.html',
                       user=user,
                       other=other,
                       messages=msgs,
                       other_pic_url=other_pic_url,
                       get_like_count=get_like_count,
                       get_comments_list=get_comments_list,
                       icon_url='/mnt/data/80e1a1d6-6d42-4c3d-846d-d420d5940577.png'   # your uploaded icon path
                       )

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

# Server-side like (form POST) for posts — redirects back to feed
@app.route('/post/<int:post_id>/like_form', methods=('POST',))
def toggle_post_like_form(post_id):
    user = current_user()
    if not user:
        flash('Login required to like posts')
        return redirect(url_for('login'))
    db = get_db()
    try:
        db.execute('INSERT INTO likes(user_id, post_id) VALUES (?, ?)', (user['id'], post_id))
        db.commit()
    except sqlite3.IntegrityError:
        db.execute('DELETE FROM likes WHERE user_id = ? AND post_id = ?', (user['id'], post_id))
        db.commit()
    # redirect back to the page user came from (feed)
    referer = request.form.get('next') or url_for('index')
    return redirect(referer)

# Comments page: GET shows comments and form, POST submits a comment then reloads.
@app.route('/post/<int:post_id>/comments', methods=('GET','POST'))
def post_comments_page(post_id):
    db = get_db()
    post = db.execute('SELECT p.*, u.username FROM posts p JOIN users u ON u.id = p.user_id WHERE p.id = ?', (post_id,)).fetchone()
    if not post:
        flash('Post not found')
        return redirect(url_for('index'))
    user = current_user()
    if request.method == 'POST':
        if not user:
            flash('Login required to comment')
            return redirect(url_for('login'))
        text = (request.form.get('text') or '').strip()
        if text:
            db.execute('INSERT INTO comments(user_id, post_id, text) VALUES (?, ?, ?)', (user['id'], post_id, text))
            db.commit()
        return redirect(url_for('post_comments_page', post_id=post_id))
    # GET: load comments
    comments = db.execute('''
        SELECT c.id, c.user_id, c.text, c.created_at, u.username
        FROM comments c JOIN users u ON u.id = c.user_id
        WHERE c.post_id = ?
        ORDER BY c.created_at ASC
    ''', (post_id,)).fetchall()

    # counts and whether current user liked this post
    like_count = db.execute('SELECT COUNT(*) as cnt FROM likes WHERE post_id = ?', (post_id,)).fetchone()['cnt']
    comment_count = len(comments)
    liked_by_me = False
    if user:
        liked_by_me = bool(db.execute('SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?', (user['id'], post_id)).fetchone())
    # developer-provided icon path passed as icon_url
    icon_url = '/mnt/data/35b4c313-40ea-49a8-a4fb-4fb7d64007a9.png'
    return render_template('post_comments.html',
                           post=post,
                           comments=comments,
                           like_count=like_count,
                           comment_count=comment_count,
                           liked_by_me=liked_by_me,
                           user=user,
                           icon_url=icon_url)

@app.route('/post', methods=('GET','POST'))
def post():
    user = current_user()
    if not user:
        flash('Login required')
        return redirect(url_for('login'))
    if request.method == 'POST':
        file = request.files.get('image')
        caption = request.form.get('caption','').strip()
        if not file or file.filename == '' or not allowed_file(file.filename):
            flash('Choose a valid image file (png/jpg/jpeg/gif)')
            return redirect(url_for('post'))
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        i = 1
        base_name, ext = os.path.splitext(filename)
        while os.path.exists(save_path):
            filename = f"{base_name}_{i}{ext}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            i += 1
        file.save(save_path)
        db = get_db()
        db.execute('INSERT INTO posts(user_id, image_path, caption) VALUES (?, ?, ?)', (user['id'], filename, caption))
        db.commit()
        return redirect(url_for('index'))
    return render_template('create_post.html')

@app.route('/post/<int:post_id>/delete', methods=('POST',))
def delete_post(post_id):
    user = current_user()
    if not user:
        flash('Login required')
        return redirect(url_for('login'))

    db = get_db()
    post = db.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    if not post:
        flash('Post not found')
        return redirect(url_for('index'))

    # Only post owner can delete
    if post['user_id'] != user['id']:
        flash('You are not authorized to delete this post')
        return redirect(url_for('index'))

    # Delete associated comments and likes first (optional but tidy)
    db.execute('DELETE FROM comments WHERE post_id = ?', (post_id,))
    db.execute('DELETE FROM likes WHERE post_id = ?', (post_id,))
    db.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    db.commit()

    # Remove image file if present
    try:
        img_path = os.path.join(app.config['UPLOAD_FOLDER'], post['image_path'])
        if post['image_path'] and os.path.exists(img_path):
            os.remove(img_path)
    except Exception as e:
        # don't crash on file delete errors, just log a flash if you want
        app.logger.warning(f"Failed to remove image file: {e}")

    flash('Post deleted')
    # redirect back to the page user came from if provided
    next_url = request.form.get('next') or url_for('index')
    return redirect(next_url)

@app.route('/like/<int:post_id>', methods=('POST',))
def like(post_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'login required'}), 401
    db = get_db()
    try:
        db.execute('INSERT INTO likes(user_id, post_id) VALUES (?, ?)', (user['id'], post_id))
        db.commit()
    except sqlite3.IntegrityError:
        db.execute('DELETE FROM likes WHERE user_id = ? AND post_id = ?', (user['id'], post_id))
        db.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_db()
        print('Initialized database at', DB_PATH)
    app.run(host='0.0.0.0', port=5000, debug=True)
