from flask import Flask, render_template, request, redirect, session, flash
import sqlite3, os
import cv2
import numpy as np

app = Flask(__name__)
app.secret_key = "bank_secret_key"

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect("bank.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        username TEXT UNIQUE,
        mobile TEXT,
        password TEXT,
        balance REAL DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount REAL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("bank.db")

# ---------------- FACE FUNCTIONS ----------------
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

def capture_face_image(username):
    cam = cv2.VideoCapture(0)

    if not cam.isOpened():
        print("Camera not accessible")
        return False

    captured_face = None

    while True:
        ret, frame = cam.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.2,
            minNeighbors=4,
            minSize=(80, 80)
        )

        # Draw rectangle if face detected
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

        # Instruction text on camera window
        cv2.putText(
            frame,
            "Press Q to capture face",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

        cv2.imshow("Face Capture", frame)

        # Capture only if face detected
        if len(faces) > 0 and cv2.waitKey(1) & 0xFF == ord('q'):
            x, y, w, h = faces[0]
            captured_face = gray[y:y+h, x:x+w]
            break

        # Allow ESC to cancel
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cam.release()
    cv2.destroyAllWindows()

    if captured_face is None:
        return False

    # Resize and save face
    captured_face = cv2.resize(captured_face, (200, 200))

    os.makedirs("faces", exist_ok=True)
    cv2.imwrite(f"faces/{username}.jpg", captured_face)

    return True


def verify_face_image(username, max_attempts=3):
    try:
        saved_face = cv2.imread(f"faces/{username}.jpg", 0)
    except:
        return False

    cam = cv2.VideoCapture(0)
    attempts = 0

    while attempts < max_attempts:
        ret, frame = cam.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.2,
            minNeighbors=4,
            minSize=(80, 80)
        )

        # Instruction text
        cv2.putText(
            frame,
            "Align your face properly",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 2)
            face_img = gray[y:y+h, x:x+w]
            face_img = cv2.resize(face_img, (200, 200))

            diff = np.mean((saved_face - face_img) ** 2)

            # MATCH FOUND
            if diff < 2000:
                cam.release()
                cv2.destroyAllWindows()
                return True

        cv2.imshow("Face Login", frame)

        attempts += 1

        if cv2.waitKey(1000) & 0xFF == 27:  # ESC to cancel
            break

    cam.release()
    cv2.destroyAllWindows()
    return False


# ---------------- ROUTES ----------------
@app.route('/')
def login():
    return render_template("login.html")

@app.route('/register')
def register():
    return render_template("register.html")

@app.route('/register_user', methods=['POST'])
def register_user():
    name = request.form['name']
    username = request.form['username']
    mobile = request.form['mobile']
    password = request.form['password']

    if not capture_face_image(username):
        flash("Face not detected. Try again.", "error")
        return redirect('/register')

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (name, username, mobile, password) VALUES (?, ?, ?, ?)",
            (name, username, mobile, password)
        )
        conn.commit()
        flash("Registration successful with face data!", "success")
    except sqlite3.IntegrityError:
        flash("Username already exists", "error")
        conn.close()
        return redirect('/register')

    conn.close()
    return redirect('/')

@app.route('/login_user', methods=['POST'])
def login_user():
    username = request.form['username'].strip()
    password = request.form['password'].strip()

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM users WHERE username=? AND password=?",
        (username, password)
    )
    user = c.fetchone()
    conn.close()

    # Step 1: Password check
    if not user:
        flash("Invalid username or password", "login_error")
        return redirect('/')

    # Step 2: Face verification
    if not verify_face_image(username):
        flash(
            "Face not recognized. Please keep your face straight, well-lit, and try again.",
            "login_error"
        )
        return redirect('/')

    # Step 3: Success
    session['user_id'] = user[0]
    session['username'] = username
    flash("Login successful with face verification!", "login_success")
    return redirect('/dashboard')


@app.route('/dashboard')
def dashboard():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?", (session['user_id'],))
    balance = c.fetchone()[0]
    conn.close()
    return render_template("dashboard.html", balance=balance, username=session['username'])

@app.route('/deposit', methods=['POST'])
def deposit():
    amount = float(request.form['amount'])
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, session['user_id']))
    c.execute("INSERT INTO transactions (user_id, type, amount) VALUES (?, ?, ?)",
              (session['user_id'], "Deposit", amount))
    conn.commit()
    conn.close()
    flash("Deposit successful", "success")
    return redirect('/dashboard')

@app.route('/withdraw', methods=['POST'])
def withdraw():
    amount = float(request.form['amount'])
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?", (session['user_id'],))
    balance = c.fetchone()[0]

    if amount > balance:
        flash("Insufficient balance", "error")
        conn.close()
        return redirect('/dashboard')

    c.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, session['user_id']))
    c.execute("INSERT INTO transactions (user_id, type, amount) VALUES (?, ?, ?)",
              (session['user_id'], "Withdraw", amount))
    conn.commit()
    conn.close()
    flash("Withdrawal successful", "success")
    return redirect('/dashboard')

@app.route('/transactions')
def transactions():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT type, amount, date FROM transactions WHERE user_id=?", (session['user_id'],))
    data = c.fetchall()
    conn.close()
    return render_template("transactions.html", data=data)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    app.run(debug=True)
