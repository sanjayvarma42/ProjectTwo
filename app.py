from flask import Flask, render_template, request, redirect, session, flash
import sqlite3, os
import cv2
import numpy as np
from werkzeug.security import generate_password_hash, check_password_hash

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

# ---------------- FACE CAPTURE (REGISTRATION) ----------------
def capture_face(account_number):
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cam.isOpened():
        return False

    while True:
        ret, frame = cam.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.2, 4)

        for (x,y,w,h) in faces:
            cv2.rectangle(frame,(x,y),(x+w,y+h),(0,255,0),2)

        cv2.putText(frame,"Press Q to Capture",
                    (20,30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,(0,255,0),2)

        cv2.imshow("Face Capture",frame)

        if len(faces)>0 and cv2.waitKey(1)&0xFF==ord('q'):
            x,y,w,h = faces[0]
            face_img = gray[y:y+h,x:x+w]
            face_img = cv2.resize(face_img,(200,200))

            os.makedirs("faces",exist_ok=True)
            cv2.imwrite(f"faces/{account_number}.jpg",face_img)
            break

    cam.release()
    cv2.destroyAllWindows()
    return True

# ---------------- FACE VERIFY ----------------
def verify_face(account_number):
    path = f"faces/{account_number}.jpg"

    if not os.path.exists(path):
        print("Stored face not found")
        return False

    saved_face = cv2.imread(path, 0)
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cam.isOpened():
        print("Camera not accessible")
        return False

    while True:
        ret, frame = cam.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x,y,w,h) in faces:
            cv2.rectangle(frame,(x,y),(x+w,y+h),(0,255,0),2)

        cv2.putText(frame,"Press Q to Verify",
                    (20,30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,(0,0,255),2)

        cv2.imshow("Face Verification", frame)

        key = cv2.waitKey(1)

        if key & 0xFF == ord('q'):
            if len(faces) == 0:
                print("No face detected")
                continue

            x,y,w,h = faces[0]
            test_face = gray[y:y+h,x:x+w]
            test_face = cv2.resize(test_face,(200,200))
            break

    cam.release()
    cv2.destroyAllWindows()

    diff = np.mean((saved_face - test_face)**2)

    print("Difference:", diff)

    return diff < 2000
# ---------------- ROUTES ----------------

@app.route('/')
def home():
    return render_template("home.html")

@app.route('/login')
def login():
    return render_template("login.html")

@app.route('/register')
def register():
    return render_template("register.html")

@app.route('/about')
def about():
    return render_template("about.html")

# ---- Capture Face ----
@app.route('/capture_face',methods=['POST'])
def capture_face_route():
    account_number = request.form['account_number']

    if not (account_number.isdigit() and len(account_number)==6):
        flash("Account number must be 6 digits","register_error")
        return redirect('/register')

    if capture_face(account_number):
        flash("Face captured successfully!","register_success")
    else:
        flash("Face capture failed","register_error")

    return redirect('/register')

# ---- Register ----
@app.route('/register_user',methods=['POST'])
def register_user():
    name = request.form['name']
    account_number = request.form['account_number']
    mobile = request.form['mobile']
    password = request.form['password']

    if not os.path.exists(f"faces/{account_number}.jpg"):
        flash("Capture face before registering","register_error")
        return redirect('/register')

    hashed_password = generate_password_hash(password)

    conn=get_db()
    c=conn.cursor()
    try:
        c.execute("INSERT INTO users(name,account_number,mobile,password) VALUES (?,?,?,?)",
                  (name,account_number,mobile,hashed_password))
        conn.commit()
        flash("Registration Successful!","login_success")
    except:
        flash("Account already exists","register_error")

    conn.close()
    return redirect('/')

# ---- Face Verify Button ----
@app.route('/verify_face_only',methods=['POST'])
def verify_face_only():
    account_number = request.form['account_number']

    conn=get_db()
    c=conn.cursor()
    c.execute("SELECT id FROM users WHERE account_number=?",(account_number,))
    user=c.fetchone()
    conn.close()

    if not user:
        flash("Invalid account number","login_error")
        return redirect('/')

    if not verify_face(account_number):
        flash("Face verification failed","login_error")
        return redirect('/')

    session['face_verified'] = True
    session['temp_account'] = account_number

    flash("Face Verified! Now click Login.","login_success")
    return redirect('/')

# ---- Final Login ----
@app.route('/login_user',methods=['POST'])
def login_user():
    account_number = request.form['account_number']
    password = request.form['password']

    if 'face_verified' not in session or session.get('temp_account') != account_number:
        flash("Please verify Face ID first","login_error")
        return redirect('/')

    conn=get_db()
    c=conn.cursor()
    c.execute("SELECT id,password FROM users WHERE account_number=?",
              (account_number,))
    user=c.fetchone()
    conn.close()

    if not user:
        flash("Invalid account number","login_error")
        return redirect('/')

    if not check_password_hash(user[1],password):
        flash("Incorrect password","login_error")
        return redirect('/')

    session.pop('face_verified',None)
    session.pop('temp_account',None)

    session['user_id']=user[0]
    session['account_number']=account_number

    flash("Login Successful!","login_success")
    return redirect('/dashboard')

# ---- Dashboard ----
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')

    conn=get_db()
    c=conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?",
              (session['user_id'],))
    balance=c.fetchone()[0]
    conn.close()

    return render_template("dashboard.html",
                           balance=balance,
                           account_number=session['account_number'])

# ---- Deposit ----
@app.route('/deposit',methods=['POST'])
def deposit():
    if 'user_id' not in session:
        return redirect('/')

    amount=float(request.form['amount'])

    if amount<=0:
        flash("Enter valid amount","dashboard_error")
        return redirect('/dashboard')

    conn=get_db()
    c=conn.cursor()
    c.execute("UPDATE users SET balance=balance+? WHERE id=?",
              (amount,session['user_id']))
    c.execute("INSERT INTO transactions(user_id,type,amount) VALUES (?,?,?)",
              (session['user_id'],"Deposit",amount))
    conn.commit()
    conn.close()

    flash("Deposit Successful!","dashboard_success")
    return redirect('/dashboard')

# ---- Withdraw ----
@app.route('/withdraw',methods=['POST'])
def withdraw():
    if 'user_id' not in session:
        return redirect('/')

    amount=float(request.form['amount'])

    conn=get_db()
    c=conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?",
              (session['user_id'],))
    balance=c.fetchone()[0]

    if amount>balance:
        flash("Insufficient Balance","dashboard_error")
        conn.close()
        return redirect('/dashboard')

    c.execute("UPDATE users SET balance=balance-? WHERE id=?",
              (amount,session['user_id']))
    c.execute("INSERT INTO transactions(user_id,type,amount) VALUES (?,?,?)",
              (session['user_id'],"Withdraw",amount))
    conn.commit()
    conn.close()

    flash("Withdrawal Successful!","dashboard_success")
    return redirect('/dashboard')

# ---- Transactions ----
@app.route('/transactions')
def transactions():
    if 'user_id' not in session:
        return redirect('/')

    conn=get_db()
    c=conn.cursor()
    c.execute("SELECT type,amount,date FROM transactions WHERE user_id=? ORDER BY date DESC",
              (session['user_id'],))
    data=c.fetchall()
    conn.close()

    return render_template("transactions.html",data=data)

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully","login_success")
    return redirect('/')

if __name__=="__main__":
    app.run(debug=True)