from flask import (
    Flask, render_template, request, redirect,
    session, send_from_directory, send_file
)
import face_recognition
import os
import pickle
import io
import zipfile
import sqlite3

app = Flask(__name__)

# ================= CONFIG =================
app.secret_key = "change-this-secret-key"
ADMIN_PASSWORD = "admin123"

PAYMENT_JOKE_MODE = True   # 🔥 TRUE = ₹500/₹100 joke | FALSE = free download

PHOTO_DIR = "photos/all_photos"
ENCODING_FILE = "photos/encodings.pkl"
DB_FILE = "stats.db"

os.makedirs(PHOTO_DIR, exist_ok=True)

# ================= DATABASE =================
def db():
    return sqlite3.connect(DB_FILE)

conn = db()
conn.execute("CREATE TABLE IF NOT EXISTS visits (id INTEGER PRIMARY KEY)")
conn.commit()
conn.close()

# ================= SAFE LOAD ENCODINGS =================
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

    img = face_recognition.load_image_file(file)
    encs = face_recognition.face_encodings(img)
    if not encs:
        return "No face detected"

    user_face = encs[0]
    matched = []

    for photo, faces in known_faces.items():
        for face in faces:
            if face_recognition.compare_faces([face], user_face, 0.5)[0]:
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

    photo_count = len(os.listdir(PHOTO_DIR))

    return render_template(
        "admin_dashboard.html",
        visits=visits,
        photo_count=photo_count
    )

# ================= ADMIN UPLOAD =================
@app.route("/admin/upload", methods=["GET", "POST"])
def admin_upload():
    global known_faces

    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":
        files = request.files.getlist("photos")

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

            img = face_recognition.load_image_file(path)
            encs = face_recognition.face_encodings(img)
            if encs:
                known_faces[file.filename] = encs

        with open(ENCODING_FILE, "wb") as f:
            pickle.dump(known_faces, f)

        return "Photos uploaded & indexed"

    return render_template("admin_upload.html")

# ================= LOGOUT =================
@app.route("/admin/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")
