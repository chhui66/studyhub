import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, send_from_directory
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
IMAGE_EXTS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
FILE_EXTS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'pdf', 'doc', 'docx', 'txt', 'zip', 'rar', 'xlsx', 'pptx'}
PASSWORD = 'admin123'
DB_PATH = os.path.join(DATA_DIR, 'site.db')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)


# ---------- Database ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        category TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS diary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        mood TEXT DEFAULT '😊',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS diary_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        diary_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        original_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        name TEXT DEFAULT '',
        bio TEXT DEFAULT '',
        skills TEXT DEFAULT '',
        contact TEXT DEFAULT '',
        avatar TEXT DEFAULT '',
        life_photos TEXT DEFAULT '',
        school TEXT DEFAULT '',
        major TEXT DEFAULT '',
        degree TEXT DEFAULT '',
        graduation_year TEXT DEFAULT '',
        experience TEXT DEFAULT '',
        birthday TEXT DEFAULT '',
        location TEXT DEFAULT ''
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        original_name TEXT NOT NULL,
        description TEXT DEFAULT '',
        category TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # 兼容旧表
    for col in ['life_photos', 'school', 'major', 'degree', 'graduation_year', 'experience', 'birthday', 'location']:
        try:
            conn.execute(f'ALTER TABLE profile ADD COLUMN {col} TEXT DEFAULT \'\'')
        except sqlite3.OperationalError:
            pass
    conn.execute('INSERT OR IGNORE INTO profile (id) VALUES (1)')
    conn.commit()
    conn.close()


# ---------- Auth ----------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ---------- Helpers ----------
def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in IMAGE_EXTS


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in FILE_EXTS


def save_upload(file_obj, prefix='file'):
    """保存上传文件，返回唯一文件名"""
    fname = secure_filename(file_obj.filename)
    base, ext = os.path.splitext(fname)
    unique = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}"
    file_obj.save(os.path.join(UPLOAD_FOLDER, unique))
    return unique, fname


def is_image(filename):
    return filename.rsplit('.', 1)[1].lower() in IMAGE_EXTS if '.' in filename else False


# ---------- Routes: Auth ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == PASSWORD:
            session['logged_in'] = True
            flash('登录成功', 'success')
            return redirect(url_for('index'))
        flash('密码错误', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('已退出登录', 'info')
    return redirect(url_for('index'))


# ---------- Routes: Pages ----------
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/links')
def links():
    category = request.args.get('category', '')
    db = get_db()
    categories = [r[0] for r in db.execute('SELECT DISTINCT category FROM links WHERE category != ""').fetchall()]
    if category:
        links_data = db.execute('SELECT * FROM links WHERE category=? ORDER BY created_at DESC', (category,)).fetchall()
    else:
        links_data = db.execute('SELECT * FROM links ORDER BY created_at DESC').fetchall()
    db.close()
    return render_template('links.html', links=links_data, categories=categories, current_category=category)


@app.route('/links/add', methods=['POST'])
@login_required
def add_link():
    title = request.form['title'].strip()
    url = request.form['url'].strip()
    category = request.form.get('category', '').strip()
    if title and url:
        db = get_db()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute('INSERT INTO links (title, url, category, created_at) VALUES (?, ?, ?, ?)', (title, url, category, now))
        db.commit()
        db.close()
        flash('链接已添加', 'success')
    return redirect(url_for('links'))


@app.route('/links/delete/<int:link_id>')
@login_required
def delete_link(link_id):
    db = get_db()
    db.execute('DELETE FROM links WHERE id=?', (link_id,))
    db.commit()
    db.close()
    flash('链接已删除', 'info')
    return redirect(url_for('links'))


@app.route('/gallery')
def gallery():
    category = request.args.get('category', '')
    search = request.args.get('search', '').strip()
    db = get_db()
    query = 'SELECT * FROM images WHERE 1=1'
    params = []
    if category:
        query += ' AND category=?'
        params.append(category)
    if search:
        query += ' AND (original_name LIKE ? OR description LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])
    query += ' ORDER BY created_at DESC'
    images = db.execute(query, params).fetchall()
    categories = ['头像', '壁纸', '风景', '我']
    db.close()
    return render_template('gallery.html', images=images, categories=categories, current_category=category, search=search)


@app.route('/gallery/upload', methods=['POST'])
@login_required
def upload_image():
    file = request.files.get('image')
    if file and allowed_image(file.filename):
        unique_name, original_name = save_upload(file, 'img')
        db = get_db()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute('INSERT INTO images (filename, original_name, description, category, created_at) VALUES (?, ?, ?, ?, ?)',
                   (unique_name, original_name, request.form.get('description', '').strip(), request.form.get('category', '').strip(), now))
        db.commit()
        db.close()
        flash('图片已上传', 'success')
    else:
        flash('不支持的文件格式', 'error')
    return redirect(url_for('gallery'))


@app.route('/gallery/delete/<int:image_id>')
@login_required
def delete_image(image_id):
    db = get_db()
    img = db.execute('SELECT * FROM images WHERE id=?', (image_id,)).fetchone()
    if img:
        filepath = os.path.join(UPLOAD_FOLDER, img['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        db.execute('DELETE FROM images WHERE id=?', (image_id,))
        db.commit()
        flash('图片已删除', 'info')
    db.close()
    return redirect(url_for('gallery'))


# ---------- Diary ----------
@app.route('/diary')
def diary():
    search = request.args.get('search', '').strip()
    db = get_db()
    if search:
        entries = db.execute(
            'SELECT * FROM diary WHERE title LIKE ? ORDER BY created_at DESC',
            (f'%{search}%',)
        ).fetchall()
    else:
        entries = db.execute('SELECT * FROM diary ORDER BY created_at DESC').fetchall()
    db.close()
    return render_template('diary.html', entries=entries, search=search)


@app.route('/diary/view/<int:entry_id>')
def view_diary(entry_id):
    db = get_db()
    entry = db.execute('SELECT * FROM diary WHERE id=?', (entry_id,)).fetchone()
    if not entry:
        db.close()
        flash('日记不存在', 'error')
        return redirect(url_for('diary'))
    files = db.execute('SELECT * FROM diary_files WHERE diary_id=? ORDER BY created_at', (entry_id,)).fetchall()
    db.close()
    return render_template('diary_detail.html', entry=entry, files=files)


@app.route('/diary/write', methods=['GET', 'POST'])
@login_required
def write_diary():
    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        mood = request.form.get('mood', '😊')
        if title and content:
            db = get_db()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cur = db.execute('INSERT INTO diary (title, content, mood, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                             (title, content, mood, now, now))
            diary_id = cur.lastrowid
            # 处理附件
            for f in request.files.getlist('attachments'):
                if f and allowed_file(f.filename):
                    unique_name, original_name = save_upload(f, 'diary')
                    db.execute('INSERT INTO diary_files (diary_id, filename, original_name, created_at) VALUES (?, ?, ?, ?)',
                               (diary_id, unique_name, original_name, now))
            db.commit()
            db.close()
            flash('日记已保存', 'success')
            return redirect(url_for('view_diary', entry_id=diary_id))
    return render_template('write_diary.html', entry=None)


@app.route('/diary/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_diary(entry_id):
    db = get_db()
    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        mood = request.form.get('mood', '😊')
        if title and content:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute('UPDATE diary SET title=?, content=?, mood=?, updated_at=? WHERE id=?',
                       (title, content, mood, now, entry_id))
            # 新附件
            for f in request.files.getlist('attachments'):
                if f and allowed_file(f.filename):
                    unique_name, original_name = save_upload(f, 'diary')
                    db.execute('INSERT INTO diary_files (diary_id, filename, original_name, created_at) VALUES (?, ?, ?, ?)',
                               (entry_id, unique_name, original_name, now))
            db.commit()
            flash('日记已更新', 'success')
            db.close()
            return redirect(url_for('view_diary', entry_id=entry_id))
    entry = db.execute('SELECT * FROM diary WHERE id=?', (entry_id,)).fetchone()
    files = db.execute('SELECT * FROM diary_files WHERE diary_id=? ORDER BY created_at', (entry_id,)).fetchall()
    db.close()
    if not entry:
        flash('日记不存在', 'error')
        return redirect(url_for('diary'))
    return render_template('write_diary.html', entry=entry, files=files)


@app.route('/diary/delete/<int:entry_id>')
@login_required
def delete_diary(entry_id):
    db = get_db()
    # 删附件文件
    files = db.execute('SELECT * FROM diary_files WHERE diary_id=?', (entry_id,)).fetchall()
    for f in files:
        filepath = os.path.join(UPLOAD_FOLDER, f['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
    db.execute('DELETE FROM diary_files WHERE diary_id=?', (entry_id,))
    db.execute('DELETE FROM diary WHERE id=?', (entry_id,))
    db.commit()
    db.close()
    flash('日记已删除', 'info')
    return redirect(url_for('diary'))


@app.route('/diary/file/delete/<int:file_id>')
@login_required
def delete_diary_file(file_id):
    db = get_db()
    f = db.execute('SELECT * FROM diary_files WHERE id=?', (file_id,)).fetchone()
    if f:
        filepath = os.path.join(UPLOAD_FOLDER, f['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        diary_id = f['diary_id']
        db.execute('DELETE FROM diary_files WHERE id=?', (file_id,))
        db.commit()
        db.close()
        return redirect(url_for('edit_diary', entry_id=diary_id))
    db.close()
    return redirect(url_for('diary'))


# ---------- Profile ----------
@app.route('/profile')
def profile():
    db = get_db()
    profile_data = db.execute('SELECT * FROM profile WHERE id=1').fetchone()
    db.close()
    life_photos = []
    if profile_data['life_photos']:
        life_photos = [p.strip() for p in profile_data['life_photos'].split(',') if p.strip()]
    return render_template('profile.html', profile=profile_data, life_photos=life_photos)


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        bio = request.form.get('bio', '').strip()
        skills = request.form.get('skills', '').strip()
        contact = request.form.get('contact', '').strip()
        school = request.form.get('school', '').strip()
        major = request.form.get('major', '').strip()
        degree = request.form.get('degree', '').strip()
        graduation_year = request.form.get('graduation_year', '').strip()
        experience = request.form.get('experience', '').strip()
        birthday = request.form.get('birthday', '').strip()
        location = request.form.get('location', '').strip()

        avatar = None
        avatar_file = request.files.get('avatar')
        if avatar_file and allowed_image(avatar_file.filename):
            unique_name, _ = save_upload(avatar_file, 'avatar')
            avatar = unique_name
            old = db.execute('SELECT avatar FROM profile WHERE id=1').fetchone()
            if old and old['avatar']:
                old_path = os.path.join(UPLOAD_FOLDER, old['avatar'])
                if os.path.exists(old_path):
                    os.remove(old_path)

        life_files = request.files.getlist('life_photos')
        old_profile = db.execute('SELECT life_photos FROM profile WHERE id=1').fetchone()
        existing = []
        if old_profile and old_profile['life_photos']:
            existing = [p.strip() for p in old_profile['life_photos'].split(',') if p.strip()]
        for lf in life_files:
            if lf and allowed_image(lf.filename):
                unique_name, _ = save_upload(lf, 'life')
                existing.append(unique_name)
        life_photos_str = ','.join(existing)

        if avatar:
            db.execute('UPDATE profile SET name=?, bio=?, skills=?, contact=?, avatar=?, life_photos=?, school=?, major=?, degree=?, graduation_year=?, experience=?, birthday=?, location=? WHERE id=1',
                       (name, bio, skills, contact, avatar, life_photos_str, school, major, degree, graduation_year, experience, birthday, location))
        else:
            db.execute('UPDATE profile SET name=?, bio=?, skills=?, contact=?, life_photos=?, school=?, major=?, degree=?, graduation_year=?, experience=?, birthday=?, location=? WHERE id=1',
                       (name, bio, skills, contact, life_photos_str, school, major, degree, graduation_year, experience, birthday, location))
        db.commit()
        db.close()
        flash('个人简介已更新', 'success')
        return redirect(url_for('profile'))

    profile_data = db.execute('SELECT * FROM profile WHERE id=1').fetchone()
    db.close()
    life_photos = []
    if profile_data['life_photos']:
        life_photos = [p.strip() for p in profile_data['life_photos'].split(',') if p.strip()]
    return render_template('edit_profile.html', profile=profile_data, life_photos=life_photos)


@app.route('/profile/delete_photo/<filename>')
@login_required
def delete_life_photo(filename):
    db = get_db()
    old = db.execute('SELECT life_photos FROM profile WHERE id=1').fetchone()
    if old and old['life_photos']:
        photos = [p.strip() for p in old['life_photos'].split(',') if p.strip()]
        if filename in photos:
            photos.remove(filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            db.execute('UPDATE profile SET life_photos=? WHERE id=1', (','.join(photos),))
            db.commit()
    db.close()
    return redirect(url_for('edit_profile'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ---------- Init ----------
if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
