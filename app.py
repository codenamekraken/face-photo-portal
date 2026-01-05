from flask import Flask, render_template, request
import face_recognition
import os
import pickle

app = Flask(__name__)

PHOTO_DIR = "photos/all_photos"
ENCODING_FILE = "photos/encodings.pkl"

# ✅ Safe loading
if os.path.exists(ENCODING_FILE) and os.path.getsize(ENCODING_FILE) > 0:
    with open(ENCODING_FILE, "rb") as f:
        known_faces = pickle.load(f)
else:
    known_faces = {}
    print("⚠️ No face encodings found. Upload photos first.")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    if not known_faces:
        return "No photos indexed yet. Please try later."

    file = request.files["selfie"]
    img = face_recognition.load_image_file(file)
    encodings = face_recognition.face_encodings(img)

    if not encodings:
        return "No face detected"

    user_face = encodings[0]
    matched_photos = []

    for photo, face_list in known_faces.items():
        for face in face_list:
            if face_recognition.compare_faces([face], user_face, tolerance=0.5)[0]:
                matched_photos.append(photo)
                break

    return render_template("results.html", photos=matched_photos)
