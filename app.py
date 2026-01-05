from flask import Flask, render_template, request
import face_recognition
import os
import pickle

app = Flask(__name__)   # 👈 THIS MUST EXIST

PHOTO_DIR = "photos/all_photos"
ENCODING_FILE = "photos/encodings.pkl"

with open(ENCODING_FILE, "rb") as f:
    known_faces = pickle.load(f)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
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


# ❌ DO NOT RUN app.run() IN PRODUCTION
# Gunicorn handles running the server
