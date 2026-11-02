from datetime import date, datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB = Path(__file__).with_name("leaveease.db")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, role TEXT NOT NULL,
            department TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL, leave_type TEXT NOT NULL,
            annual_quota INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL, leave_type TEXT NOT NULL,
            start_date TEXT NOT NULL, end_date TEXT NOT NULL,
            days INTEGER NOT NULL, reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY(employee_id) REFERENCES users(id)
        );
        """)
        if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            demo = [
                ("Aarav Employee", "employee@leaveease.demo", "employee123", "employee", "Engineering"),
                ("Meera Manager", "manager@leaveease.demo", "manager123", "manager", "Engineering"),
                ("HR Admin", "admin@leaveease.demo", "admin123", "admin", "HR"),
            ]
            for name, email, password, role, dept in demo:
                con.execute("INSERT INTO users(name,email,password_hash,role,department) VALUES(?,?,?,?,?)",
                            (name, email, generate_password_hash(password), role, dept))
            con.executemany("INSERT INTO policies(department,leave_type,annual_quota) VALUES(?,?,?)", [
                ("Engineering", "Annual Leave", 20),
                ("Engineering", "Sick Leave", 10),
                ("Engineering", "Casual Leave", 7),
                ("HR", "Annual Leave", 20),
                ("HR", "Sick Leave", 10),
            ])

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                flash("You do not have permission to view that page.", "error")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.update(user_id=user["id"], name=user["name"], role=user["role"], department=user["department"])
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as con:
        if session["role"] == "employee":
            requests = con.execute("SELECT * FROM requests WHERE employee_id=? ORDER BY id DESC",
                                   (session["user_id"],)).fetchall()
            policy = con.execute("SELECT leave_type, annual_quota FROM policies WHERE department=?",
                                 (session["department"],)).fetchall()
            used = {}
            for row in con.execute("SELECT leave_type, SUM(days) AS total FROM requests WHERE employee_id=? AND status='Approved' GROUP BY leave_type",
                                   (session["user_id"],)):
                used[row["leave_type"]] = row["total"] or 0
            balances = [{"type": p["leave_type"], "quota": p["annual_quota"],
                         "used": used.get(p["leave_type"], 0),
                         "remaining": max(0, p["annual_quota"] - used.get(p["leave_type"], 0))}
                        for p in policy]
            return render_template("employee.html", requests=requests, balances=balances)
        if session["role"] == "manager":
            requests = con.execute("""SELECT requests.*, users.name AS employee_name, users.department
                                      FROM requests JOIN users ON users.id=requests.employee_id
                                      WHERE users.department=? ORDER BY requests.id DESC""",
                                   (session["department"],)).fetchall()
            return render_template("manager.html", requests=requests)
        users = con.execute("SELECT id,name,email,role,department FROM users ORDER BY name").fetchall()
        policies = con.execute("SELECT * FROM policies ORDER BY department,leave_type").fetchall()
        total = con.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        pending = con.execute("SELECT COUNT(*) FROM requests WHERE status='Pending'").fetchone()[0]
        return render_template("admin.html", users=users, policies=policies, total=total, pending=pending)

@app.route("/apply", methods=["POST"])
@login_required
@role_required("employee")
def apply_leave():
    leave_type = request.form.get("leave_type", "")
    start = request.form.get("start_date", "")
    end = request.form.get("end_date", "")
    reason = request.form.get("reason", "").strip()
    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
        days = (end_d - start_d).days + 1
        if days < 1 or start_d < date.today() or not reason:
            raise ValueError()
    except ValueError:
        flash("Please enter valid future dates and a reason.", "error")
        return redirect(url_for("dashboard"))
    with db() as con:
        allowed = con.execute("SELECT annual_quota FROM policies WHERE department=? AND leave_type=?",
                              (session["department"], leave_type)).fetchone()
        if not allowed:
            flash("That leave type is not available for your department.", "error")
        else:
            used = con.execute("""SELECT COALESCE(SUM(days),0) FROM requests
                                  WHERE employee_id=? AND leave_type=? AND status='Approved'""",
                               (session["user_id"], leave_type)).fetchone()[0]
            pending = con.execute("""SELECT COALESCE(SUM(days),0) FROM requests
                                      WHERE employee_id=? AND leave_type=? AND status='Pending'""",
                                  (session["user_id"], leave_type)).fetchone()[0]
            if used + pending + days > allowed["annual_quota"]:
                flash("This request exceeds your available leave quota.", "error")
            else:
                con.execute("""INSERT INTO requests(employee_id,leave_type,start_date,end_date,days,reason,status,created_at)
                               VALUES(?,?,?,?,?,?,?,?)""",
                            (session["user_id"], leave_type, start, end, days, reason, "Pending", datetime.now().isoformat(timespec="minutes")))
                flash("Leave request submitted successfully.", "success")
    return redirect(url_for("dashboard"))

@app.route("/decision/<int:request_id>/<decision>", methods=["POST"])
@login_required
@role_required("manager")
def decision(request_id, decision):
    if decision not in ("Approved", "Rejected"):
        return redirect(url_for("dashboard"))
    with db() as con:
        row = con.execute("""SELECT requests.id FROM requests JOIN users ON users.id=requests.employee_id
                             WHERE requests.id=? AND users.department=? AND requests.status='Pending'""",
                          (request_id, session["department"])).fetchone()
        if row:
            con.execute("UPDATE requests SET status=? WHERE id=?", (decision, request_id))
            flash(f"Request {decision.lower()}.", "success")
    return redirect(url_for("dashboard"))

@app.route("/policy", methods=["POST"])
@login_required
@role_required("admin")
def add_policy():
    department = request.form.get("department", "").strip()
    leave_type = request.form.get("leave_type", "").strip()
    try:
        quota = int(request.form.get("quota", ""))
        if not department or not leave_type or quota < 0:
            raise ValueError()
    except ValueError:
        flash("Enter a department, leave type and valid quota.", "error")
        return redirect(url_for("dashboard"))
    with db() as con:
        con.execute("INSERT INTO policies(department,leave_type,annual_quota) VALUES(?,?,?)",
                    (department, leave_type, quota))
    flash("Policy added.", "success")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
