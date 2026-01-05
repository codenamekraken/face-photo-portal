from flask import Flask, render_template, request, redirect, url_for, session
import face_recognition
import os
import pickle

app = Flask(__name__)

# ================= CONFIG =================
app.secret_key = "change-this-secret-key"   # change later
ADMIN_PASSWORD = "admin123"                 # change later

PHOTO_DIR = "photos/all_photos"
ENCODING_FILE = "photos/encodings.pkl"

# Ensure photo directory exists
os.makedirs(PHOTO_DIR, exist_ok=True)

# ================= SAFE LOAD ENCODINGS =================
if os.path.exists(ENCODING_FILE) and os.path.getsize(ENCODING_FILE) > 0:
    with open(ENCODING_FILE, "rb") as f:
        known_faces = pickle.load(f)
else:
    known_faces = {}
    print("⚠️ No face encodings found. Upload photos first.")

# ================= USER ROUTES =================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    if not known_faces:
        return "No photos indexed yet. Please try later."

    file = request.files.get("selfie")
    if not file:
        return "No file uploaded"

    img = face_recognition.load_image_file(file)
    encodings = face_recognition.face_encodings(img)

    if not encodings:
        return "No face detected in selfie"

    user_face = encodings[0]
    matched_photos = []

    for photo, face_list in known_faces.items():
        for face in face_list:
            if face_recognition.compare_faces([face], user_face, tolerance=0.5)[0]:
                matched_photos.append(photo)
                break

    return render_template("results.html", photos=matched_photos)

# ================= ADMIN LOGIN =================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin/upload")
        else:
            return "❌ Wrong password"

    return """
    <h2>Admin Login</h2>
    <form method="post">
        <input type="password" name="password" placeholder="Admin password" required>
        <br><br>
        <button type="submit">Login</button>
    </form>
    """

# ================= ADMIN UPLOAD + FACE INDEX =================
@app.route("/admin/upload", methods=["GET", "POST"])
def admin_upload():
    global known_faces

    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":
        files = request.files.getlist("photos")

        if not files:
            return "No files selected"

        # Load existing encodings safely
        if os.path.exists(ENCODING_FILE) and os.path.getsize(ENCODING_FILE) > 0:
            with open(ENCODING_FILE, "rb") as f:
                known_faces = pickle.load(f)
        else:
            known_faces = {}

        for file in files:
            if file.filename == "":
                continue

            filename = file.filename
            save_path = os.path.join(PHOTO_DIR, filename)
            file.save(save_path)

            image = face_recognition.load_image_file(save_path)
            encs = face_recognition.face_encodings(image)

            if encs:
                known_faces[filename] = encs

        # Save updated encodings
        with open(ENCODING_FILE, "wb") as f:
            pickle.dump(known_faces, f)

        return "✅ Photos uploaded & indexed successfully"

    return """
    <h2>Upload Photos (Admin)</h2>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="photos" multiple required>
        <br><br>
        <button type="submit">Upload & Index</button>
    </form>
    """

# ================= LOGOUT =================
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/")
