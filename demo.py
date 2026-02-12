import sqlite3
import datetime

# ---------------- DATABASE SETUP ----------------
def init_db():
    conn = sqlite3.connect("bank.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
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
        date TEXT
    )
    """)

    conn.commit()
    conn.close()

# ---------------- SIGN UP ----------------
def sign_up():
    username = input("Enter username: ")
    password = input("Enter password: ")

    conn = sqlite3.connect("bank.db")
    c = conn.cursor()

    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                  (username, password))
        conn.commit()
        print("✅ Registration successful! Please sign in.")
    except sqlite3.IntegrityError:
        print("❌ Username already exists.")
    conn.close()

# ---------------- SIGN IN ----------------
def sign_in():
    username = input("Username: ")
    password = input("Password: ")

    conn = sqlite3.connect("bank.db")
    c = conn.cursor()

    c.execute("SELECT id, balance FROM users WHERE username=? AND password=?",
              (username, password))
    user = c.fetchone()
    conn.close()

    if user:
        print("✅ Login successful!")
        dashboard(user[0])
    else:
        print("❌ Invalid username or password")

# ---------------- DASHBOARD ----------------
def dashboard(user_id):
    while True:
        print("\n--- DASHBOARD ---")
        print("1. Check Balance")
        print("2. Deposit")
        print("3. Withdraw")
        print("4. Transaction History")
        print("5. Logout")

        choice = input("Choose option: ")

        if choice == "1":
            check_balance(user_id)
        elif choice == "2":
            deposit(user_id)
        elif choice == "3":
            withdraw(user_id)
        elif choice == "4":
            transaction_history(user_id)
        elif choice == "5":
            print("👋 Logged out\n")
            break
        else:
            print("❌ Invalid choice")

# ---------------- CHECK BALANCE ----------------
def check_balance(user_id):
    conn = sqlite3.connect("bank.db")
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    balance = c.fetchone()[0]
    conn.close()
    print(f"💰 Current Balance: ₹{balance}")

# ---------------- DEPOSIT ----------------
def deposit(user_id):
    amount = float(input("Enter deposit amount: "))

    conn = sqlite3.connect("bank.db")
    c = conn.cursor()

    c.execute("UPDATE users SET balance = balance + ? WHERE id=?",
              (amount, user_id))

    c.execute("INSERT INTO transactions (user_id, type, amount, date) VALUES (?, ?, ?, ?)",
              (user_id, "Deposit", amount, str(datetime.datetime.now())))

    conn.commit()
    conn.close()
    print("✅ Amount deposited successfully")

# ---------------- WITHDRAW ----------------
def withdraw(user_id):
    amount = float(input("Enter withdraw amount: "))

    conn = sqlite3.connect("bank.db")
    c = conn.cursor()

    c.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    balance = c.fetchone()[0]

    if amount > balance:
        print("❌ Insufficient balance")
    else:
        c.execute("UPDATE users SET balance = balance - ? WHERE id=?",
                  (amount, user_id))

        c.execute("INSERT INTO transactions (user_id, type, amount, date) VALUES (?, ?, ?, ?)",
                  (user_id, "Withdraw", amount, str(datetime.datetime.now())))

        conn.commit()
        print("✅ Withdrawal successful")

    conn.close()

# ---------------- TRANSACTION HISTORY ----------------
def transaction_history(user_id):
    conn = sqlite3.connect("bank.db")
    c = conn.cursor()

    c.execute("SELECT type, amount, date FROM transactions WHERE user_id=?",
              (user_id,))
    transactions = c.fetchall()
    conn.close()

    print("\n--- TRANSACTION HISTORY ---")
    if not transactions:
        print("No transactions found")
    else:
        for t in transactions:
            print(f"{t[0]} | ₹{t[1]} | {t[2]}")

# ---------------- MAIN MENU ----------------
def main():
    init_db()

    while True:
        print("\n==== BANK MANAGEMENT SYSTEM ====")
        print("1. Sign Up")
        print("2. Sign In")
        print("3. Exit")

        choice = input("Choose option: ")

        if choice == "1":
            sign_up()
        elif choice == "2":
            sign_in()
        elif choice == "3":
            print("Thank you! 👋")
            break
        else:
            print("❌ Invalid choice")

# ---------------- RUN PROGRAM ----------------
if __name__ == "__main__":
    main()
