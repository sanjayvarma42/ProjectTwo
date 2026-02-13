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
        account_number TEXT UNIQUE,
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

# ---------------- FACE SETUP ----------------
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# ---------------- FACE CAPTURE ----------------
def capture_face_image(account_number):
    cam = cv2.VideoCapture(0)

    if not cam.isOpened():
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

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

        cv2.putText(frame, "Press Q to capture face",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2)

        cv2.imshow("Face Capture", frame)

        if len(faces) > 0 and cv2.waitKey(1) & 0xFF == ord('q'):
            x, y, w, h = faces[0]
            captured_face = gray[y:y+h, x:x+w]
            break

        if cv2.waitKey(1) & 0xFF == 27:
            break

    cam.release()
    cv2.destroyAllWindows()

    if captured_face is None:
        return False

    captured_face = cv2.resize(captured_face, (200, 200))
    os.makedirs("faces", exist_ok=True)
    cv2.imwrite(f"faces/{account_number}.jpg", captured_face)

    return True


# ---------------- FACE VERIFY ----------------
def verify_face_image(account_number, max_attempts=3):
    path = f"faces/{account_number}.jpg"

    if not os.path.exists(path):
        return False

    saved_face = cv2.imread(path, 0)
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

        cv2.putText(frame, "Align your face properly",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2)

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 2)
            face_img = gray[y:y+h, x:x+w]
            face_img = cv2.resize(face_img, (200, 200))

            diff = np.mean((saved_face - face_img) ** 2)

            if diff < 2000:
                cam.release()
                cv2.destroyAllWindows()
                return True

        cv2.imshow("Face Login", frame)
        attempts += 1

        if cv2.waitKey(1000) & 0xFF == 27:
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
    account_number = request.form['account_number']
    mobile = request.form['mobile']
    password = request.form['password']

    if not (account_number.isdigit() and len(account_number) == 6):
        flash("Account number must be exactly 6 digits.", "register_error")
        return redirect('/register')

    if not capture_face_image(account_number):
        flash("Face not detected. Try again.", "register_error")
        return redirect('/register')

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (name, account_number, mobile, password) VALUES (?, ?, ?, ?)",
            (name, account_number, mobile, password)
        )
        conn.commit()
        flash("Registration successful! Please login.", "login_success")
    except sqlite3.IntegrityError:
        flash("Account number already exists.", "register_error")
        conn.close()
        return redirect('/register')

    conn.close()
    return redirect('/')


@app.route('/login_user', methods=['POST'])
def login_user():
    account_number = request.form['account_number']
    password = request.form['password']

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM users WHERE account_number=? AND password=?",
        (account_number, password)
    )
    user = c.fetchone()
    conn.close()

    if not user:
        flash("Invalid account number or password.", "login_error")
        return redirect('/')

    if not verify_face_image(account_number):
        flash("Face not recognized. Try again.", "login_error")
        return redirect('/')

    session['user_id'] = user[0]
    session['account_number'] = account_number

    flash("Login successful!", "login_success")
    return redirect('/dashboard')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?", (session['user_id'],))
    balance = c.fetchone()[0]
    conn.close()

    return render_template(
        "dashboard.html",
        balance=balance,
        account_number=session['account_number']
    )


# ---------------- DEPOSIT ----------------
@app.route('/deposit', methods=['POST'])
def deposit():
    amount = float(request.form['amount'])

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE id=?",
              (amount, session['user_id']))
    c.execute("INSERT INTO transactions (user_id, type, amount) VALUES (?, ?, ?)",
              (session['user_id'], "Deposit", amount))
    conn.commit()
    conn.close()

    flash("Deposit successful!", "dashboard_success")
    return redirect('/dashboard')


# ---------------- WITHDRAW ----------------
@app.route('/withdraw', methods=['POST'])
def withdraw():
    amount = float(request.form['amount'])

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?",
              (session['user_id'],))
    balance = c.fetchone()[0]

    if amount > balance:
        flash("Insufficient balance!", "dashboard_error")
        conn.close()
        return redirect('/dashboard')

    c.execute("UPDATE users SET balance = balance - ? WHERE id=?",
              (amount, session['user_id']))
    c.execute("INSERT INTO transactions (user_id, type, amount) VALUES (?, ?, ?)",
              (session['user_id'], "Withdraw", amount))
    conn.commit()
    conn.close()

    flash("Withdrawal successful!", "dashboard_success")
    return redirect('/dashboard')


# ---------------- TRANSACTIONS ----------------
@app.route('/transactions')
def transactions():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT type, amount, date FROM transactions WHERE user_id=? ORDER BY date DESC",
              (session['user_id'],))
    data = c.fetchall()
    conn.close()

    return render_template("transactions.html", data=data)


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "login_success")
    return redirect('/')


if __name__ == "__main__":
    app.run(debug=True)