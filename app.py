from flask import (
    Flask, render_template, request, redirect,
    session, send_from_directory, send_file
)

import os
import pickle
import io
import zipfile
import sqlite3
import time

# ================= APP INIT =================
app = Flask(__name__)
app.secret_key = "change-this-secret-key"

# Max upload size (150MB)
app.config["MAX_CONTENT_LENGTH"] = 150 * 1024 * 1024

# ================= CONFIG =================
ADMIN_PASSWORD = "admin123"
PAYMENT_JOKE_MODE = True

PHOTO_DIR = "photos/all_photos"
ENCODING_FILE = "photos/encodings.pkl"
DB_FILE = "stats.db"
AUTO_DELETE_DAYS = 7

os.makedirs(PHOTO_DIR, exist_ok=True)

# ================= LAZY FACE RECOGNITION =================
def get_face_recognition():
    import face_recognition
    return face_recognition

# ================= DATABASE =================
def db():
    return sqlite3.connect(DB_FILE)

conn = db()
conn.execute("CREATE TABLE IF NOT EXISTS visits (id INTEGER PRIMARY KEY)")
conn.commit()
conn.close()

# ================= AUTO DELETE OLD PHOTOS =================
def auto_delete_old_photos(days):
    if not os.path.exists(PHOTO_DIR):
        return

    cutoff = time.time() - (days * 24 * 60 * 60)

    if os.path.exists(ENCODING_FILE) and os.path.getsize(ENCODING_FILE) > 0:
        with open(ENCODING_FILE, "rb") as f:
            faces = pickle.load(f)
    else:
        faces = {}

    changed = False

    for filename in os.listdir(PHOTO_DIR):
        path = os.path.join(PHOTO_DIR, filename)
        if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
            try:
                os.remove(path)
                faces.pop(filename, None)
                changed = True
            except:
                pass

    if changed:
        with open(ENCODING_FILE, "wb") as f:
            pickle.dump(faces, f)
        print("🧹 Old photos auto-deleted")

auto_delete_old_photos(AUTO_DELETE_DAYS)

# ================= LOAD ENCODINGS =================
if os.path.exists(ENCODING_FILE) and os.path.getsize(ENCODING_FILE) > 0:
    with open(ENCODING_FILE, "rb") as f:
        known_faces = pickle.load(f)
else:
    known_faces = {}

# ================= SERVE PHOTOS =================
@app.route("/photos/<path:filename>")
def photos(filename):
    return send_from_directory(PHOTO_DIR, filename)

# ================= USER ROUTES =================
@app.route("/")
def index():
    conn = db()
    conn.execute("INSERT INTO visits DEFAULT VALUES")
    conn.commit()
    conn.close()
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    if not known_faces:
        return "No photos indexed yet."

    file = request.files.get("selfie")
    if not file:
        return "No file uploaded"

    fr = get_face_recognition()

    img = fr.load_image_file(file)
    encs = fr.face_encodings(img)
    if not encs:
        return "No face detected"

    user_face = encs[0]
    matched = []

    for photo, faces in known_faces.items():
        for face in faces:
            if fr.compare_faces([face], user_face, 0.5)[0]:
                matched.append(photo)
                break

    return render_template(
        "results.html",
        photos=matched,
        joke_mode=PAYMENT_JOKE_MODE
    )

# ================= DOWNLOAD ZIP =================
@app.route("/download", methods=["POST"])
def download():
    photos = request.form.getlist("photos")
    if not photos:
        return "No photos selected"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in photos:
            path = os.path.join(PHOTO_DIR, p)
            if os.path.exists(path):
                z.write(path, arcname=p)

    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name="my_photos.zip",
        mimetype="application/zip"
    )

# ================= ADMIN LOGIN =================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin/dashboard")
        return "Wrong password"

    return render_template("admin_login.html")

# ================= ADMIN DASHBOARD =================
@app.route("/admin/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    conn = db()
    visits = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
    conn.close()

    photos = os.listdir(PHOTO_DIR)

    return render_template(
        "admin_dashboard.html",
        visits=visits,
        photo_count=len(photos),
        photos=photos
    )

# ================= ADMIN PHOTO GALLERY =================
@app.route("/admin/photos")
def admin_photos():
    if not session.get("admin"):
        return redirect("/admin")

    photos = sorted(os.listdir(PHOTO_DIR))
    return render_template(
        "admin_photos.html",
        photos=photos,
        count=len(photos)
    )

# ================= ADMIN UPLOAD =================
@app.route("/admin/upload", methods=["GET", "POST"])
def admin_upload():
    global known_faces

    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":
        files = request.files.getlist("photos")
        fr = get_face_recognition()

        if os.path.exists(ENCODING_FILE) and os.path.getsize(ENCODING_FILE) > 0:
            with open(ENCODING_FILE, "rb") as f:
                known_faces = pickle.load(f)
        else:
            known_faces = {}

        for file in files:
            if not file.filename:
                continue

            path = os.path.join(PHOTO_DIR, file.filename)
            file.save(path)

            try:
                img = fr.load_image_file(path)
                encs = fr.face_encodings(img)
                if encs:
                    known_faces[file.filename] = encs
            except Exception as e:
                print("⚠️ Face processing failed:", file.filename, e)

        with open(ENCODING_FILE, "wb") as f:
            pickle.dump(known_faces, f)

        return "Photos uploaded successfully"

    return render_template("admin_upload.html")

# ================= LOGOUT =================
@app.route("/admin/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")
