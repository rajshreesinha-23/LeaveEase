# LeaveEase — Employee Leave Management System

A beginner-friendly Flask + SQLite prototype based on the LeaveEase case study.

## Requirements
- Python 3.10 or newer
- Visual Studio Code (recommended)

## Run on Windows
1. Extract the ZIP file.
2. Open the `LeaveEase` folder in VS Code.
3. Open Terminal → New Terminal.
4. Create a virtual environment:
   ```powershell
   py -m venv venv
   ```
5. Activate it:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks activation, use Command Prompt and run:
   ```cmd
   venv\Scripts\activate.bat
   ```
6. Install Flask:
   ```powershell
   pip install -r requirements.txt
   ```
7. Start the website:
   ```powershell
   python app.py
   ```
8. Open http://127.0.0.1:5000 in your browser.

## Demo logins
| Role | Email | Password |
|---|---|---|
| Employee | employee@leaveease.demo | employee123 |
| Manager | manager@leaveease.demo | manager123 |
| HR Admin | admin@leaveease.demo | admin123 |

The SQLite database is created automatically the first time the app runs.

## Included
- Role-based demo login
- Employee leave application and request history
- Leave balance calculation from approved requests
- Manager approval/rejection workflow
- HR policy creation and user overview

## Important limitations
This is an academic prototype, not a production HR system. Before real deployment, add CSRF protection, stronger secret management, password reset, audit logs, robust policy/overlap validation, proper manager-to-team mapping, and production hosting. Demo credentials are for local testing only.
