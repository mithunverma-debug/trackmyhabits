"""
CLI utility to securely create or promote the first Administrator account.
Run from terminal:
    python create_admin.py --email admin@example.com --name "System Administrator" --password "your_secure_password"
"""
import sys
import argparse
from werkzeug.security import generate_password_hash
import db
import repos

def main():
    parser = argparse.ArgumentParser(description="Secure initial Admin creation tool for TrackMyHabits")
    parser.add_argument("--email", required=True, help="Administrator email address")
    parser.add_argument("--name", default="Admin", help="Administrator display name")
    parser.add_argument("--password", required=True, help="Administrator password (min 8 chars)")

    args = parser.parse_args()
    if len(args.password) < 8:
        print("Error: Password must be at least 8 characters.")
        sys.exit(1)

    email = args.email.strip().lower()
    name = args.name.strip()
    pw_hash = generate_password_hash(args.password)

    try:
        existing = db.execute_query("SELECT id, role FROM users WHERE email = %s", (email,), fetch_one=True)
        if existing:
            db.execute_query(
                "UPDATE users SET role = 'admin', password_hash = %s, full_name = %s, is_active = TRUE WHERE id = %s",
                (pw_hash, name, existing['id']), commit=True
            )
            print(f"Updated existing user '{email}' to Administrator.")
            repos.log_admin_audit(existing['id'], email, 'promote_admin_cli', 'user', existing['id'], {'cli': True})
        else:
            new_u = db.execute_query(
                "INSERT INTO users (full_name, email, password_hash, role, is_active) VALUES (%s, %s, %s, 'admin', TRUE) RETURNING id",
                (name, email, pw_hash), commit=True, fetch_one=True
            )
            db.execute_query(
                "INSERT INTO user_settings (user_id, theme, timezone) VALUES (%s, 'dark', 'Asia/Kolkata') ON CONFLICT DO NOTHING",
                (new_u['id'],), commit=True
            )
            print(f"Created new Administrator '{email}' successfully (ID: {new_u['id']}).")
            repos.log_admin_audit(new_u['id'], email, 'create_admin_cli', 'user', new_u['id'], {'cli': True})
    except Exception as e:
        print(f"Failed to create admin: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
