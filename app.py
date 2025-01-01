import os
import re
import json
import uuid
import bcrypt
import logging
import subprocess
import threading
import time
from urllib.parse import urlparse
from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Load configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['DOWNLOAD_DIR'] = os.environ.get('DOWNLOAD_DIR', 'downloads')
app.config['STATUS_FILE'] = os.environ.get('STATUS_FILE', 'data/download_status.json')
app.config['USERS_FILE'] = os.environ.get('USERS_FILE', 'data/users.json')

def load_status():
    """Load download status from JSON file."""
    try:
        os.makedirs(os.path.dirname(app.config['STATUS_FILE']), exist_ok=True)
        if os.path.exists(app.config['STATUS_FILE']):
            with open(app.config['STATUS_FILE'], 'r') as f:
                return json.load(f)
        return {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    except Exception as e:
        logger.error(f"Error loading status: {e}")
        return {}

def save_status(status_data):
    """Save download status to JSON file."""
    try:
        os.makedirs(os.path.dirname(app.config['STATUS_FILE']), exist_ok=True)
        with open(app.config['STATUS_FILE'], 'w') as f:
            json.dump(status_data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving status: {e}")

def update_job_status(user, job_id, updates):
    """Update a specific job's status."""
    status_data = load_status()
    if user not in status_data:
        status_data[user] = []
    
    # Find and update the job
    job_found = False
    for job in status_data[user]:
        if job["id"] == job_id:
            job.update(updates)
            job_found = True
            break
    
    # If job wasn't found (e.g., after server restart), create it
    if not job_found and "title" in updates:
        status_data[user].append({
            "id": job_id,
            "status": "in_progress",
            **updates
        })
    
    save_status(status_data)

# Clean up old status entries
def cleanup_old_status():
    """Remove completed downloads older than 7 days."""
    try:
        status_data = load_status()
        current_time = time.time()
        seven_days_ago = current_time - (7 * 24 * 60 * 60)  # 7 days in seconds

        for username in status_data:
            # Keep only recent or non-completed downloads
            status_data[username] = [
                download for download in status_data[username]
                if (
                    download.get("status") != "completed" or
                    not download.get("completed_at") or
                    time.mktime(time.strptime(download["completed_at"], "%Y-%m-%d %H:%M:%S")) > seven_days_ago
                )
            ]
        
        save_status(status_data)
    except Exception as e:
        logger.error(f"Error cleaning up old status: {e}")

# Run cleanup periodically
def start_cleanup_thread():
    """Start a thread to periodically clean up old status entries."""
    def cleanup_loop():
        while True:
            cleanup_old_status()
            time.sleep(24 * 60 * 60)  # Run once per day

    cleanup_thread = threading.Thread(target=cleanup_loop)
    cleanup_thread.daemon = True
    cleanup_thread.start()

# Start the cleanup thread when the app starts
start_cleanup_thread()

# Load initial status
downloads_status = load_status()

def is_spotify_url(url):
    """Check if the URL is a Spotify URL."""
    parsed = urlparse(url)
    return parsed.netloc in ['open.spotify.com', 'spotify.com']

def process_spotify_download(url, user_dir, safe_title=None):
    """Download a Spotify track using spotdl."""
    cmd = [
        "spotdl",
        "--output", user_dir,
        "--format", "flac",
        url
    ]
    return subprocess.run(cmd, capture_output=True, text=True)

def process_youtube_download(url, user_dir, safe_title):
    """Download a YouTube video and convert to FLAC."""
    output_tmpl = os.path.join(user_dir, f"{safe_title} [%(id)s].%(ext)s")
    cmd = ["yt-dlp", "-x", "--audio-format", "flac", "-o", output_tmpl, url]
    return subprocess.run(cmd, capture_output=True, text=True)

def get_title(url):
    """Get the title of the track/video."""
    if is_spotify_url(url):
        cmd = ["spotdl", "--print-url", url]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise Exception(f"Failed to get Spotify track info: {proc.stderr}")
        # spotdl outputs multiple lines, we want the first one which contains the title
        return proc.stdout.strip().split('\n')[0]
    else:
        cmd = ["yt-dlp", "--print", "%(title)s", url]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise Exception(f"Failed to get title: {proc.stderr}")
        return proc.stdout.strip()

def process_download(url, user, job_id):
    """Process download in a separate thread."""
    try:
        user_dir = os.path.join(app.config['DOWNLOAD_DIR'], user)
        os.makedirs(user_dir, exist_ok=True)

        # Get title
        raw_title = get_title(url)
        safe_title = re.sub(r'[^A-Za-z0-9_\-\s]+', '_', raw_title)

        # Update job with title
        update_job_status(user, job_id, {
            "title": safe_title,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        # Download based on URL type
        if is_spotify_url(url):
            proc_download = process_spotify_download(url, user_dir, safe_title)
        else:
            proc_download = process_youtube_download(url, user_dir, safe_title)

        # Update job status
        if proc_download.returncode == 0:
            update_job_status(user, job_id, {
                "status": "completed",
                "completed_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            logger.info(f"Download completed: user={user}, title={safe_title}")
        else:
            update_job_status(user, job_id, {
                "status": "failed",
                "error": proc_download.stderr,
                "completed_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            logger.error(f"Download failed: user={user}, error={proc_download.stderr}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Download failed: user={user}, error={error_msg}")
        update_job_status(user, job_id, {
            "status": "failed",
            "error": error_msg,
            "completed_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })

def load_users():
    """Load users from JSON file."""
    try:
        with open(app.config['USERS_FILE'], 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        return {"users": []}

def save_users(users_data):
    """Save users to JSON file."""
    try:
        os.makedirs(os.path.dirname(app.config['USERS_FILE']), exist_ok=True)
        with open(app.config['USERS_FILE'], 'w') as f:
            json.dump(users_data, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving users: {e}")
        return False

def hash_password(password):
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')

def verify_password(password, hashed):
    """Verify a password against a hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

def update_user_password(username, new_password):
    """Update a user's password."""
    users_data = load_users()
    for user in users_data['users']:
        if user['username'] == username:
            user['password_hash'] = hash_password(new_password)
            return save_users(users_data)
    return False

def get_user_data(username):
    """Get user data without password hash."""
    users_data = load_users()
    for user in users_data['users']:
        if user['username'] == username:
            return {k: v for k, v in user.items() if k != 'password_hash'}
    return None

def is_admin(username):
    """Check if user is admin."""
    return username == 'admin'

USERS = load_users()

@app.before_request
def check_auth():
    """Check if user is authenticated for protected routes."""
    public_routes = ['login', 'static']
    if request.endpoint not in public_routes and 'logged_in' not in session:
        return redirect(url_for('login'))

@app.route('/')
def index():
    """Home page with download form."""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        stored_hash = USERS.get(username)

        if stored_hash and verify_password(password, stored_hash):
            session['logged_in'] = True
            session['username'] = username
            logger.info(f"Successful login for user: {username}")
            return redirect(url_for('index'))
        else:
            logger.warning(f"Failed login attempt for user: {username}")
            flash('Invalid credentials', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Handle user logout."""
    session.clear()
    return redirect(url_for('login'))

@app.route('/download', methods=['POST'])
def download():
    """Handle FLAC download requests."""
    url = request.form.get('url', '').strip()
    user = session['username']

    if not url:
        flash('Please provide a valid URL', 'error')
        return redirect(url_for('index'))

    # Initialize tracking for user
    status_data = load_status()
    if user not in status_data:
        status_data[user] = []

    # Create job entry
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "title": "Fetching title...",
        "status": "in_progress",
        "url": url,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    status_data[user].append(job)
    save_status(status_data)

    # Start download process in a separate thread
    thread = threading.Thread(target=process_download, args=(url, user, job_id))
    thread.daemon = True
    thread.start()

    flash('Download started! Check the status page for progress.', 'success')
    return redirect(url_for('status'))

@app.route('/status')
def status():
    """Show download status page."""
    user = session['username']
    status_data = load_status()
    user_downloads = status_data.get(user, [])
    return render_template('status.html', downloads=user_downloads)

@app.route('/profile')
def profile():
    """User profile page."""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_data = get_user_data(session['username'])
    return render_template('profile.html', user=user_data, is_admin=is_admin(session['username']))

@app.route('/change_password', methods=['POST'])
def change_password():
    """Handle password change requests."""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not all([current_password, new_password, confirm_password]):
        flash('All fields are required', 'error')
        return redirect(url_for('profile'))

    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('profile'))

    # Verify current password
    users_data = load_users()
    user = next((u for u in users_data['users'] if u['username'] == session['username']), None)
    if not user or not verify_password(current_password, user['password_hash']):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('profile'))

    # Update password
    if update_user_password(session['username'], new_password):
        flash('Password updated successfully', 'success')
    else:
        flash('Failed to update password', 'error')

    return redirect(url_for('profile'))

@app.route('/admin/update_admin', methods=['POST'])
def update_admin():
    """Update admin credentials - only works from command line."""
    if not request.is_json:
        return jsonify({'success': False, 'message': 'JSON required'}), 400

    data = request.get_json()
    new_password = data.get('password')
    
    if not new_password:
        return jsonify({'success': False, 'message': 'Password required'}), 400

    if update_user_password('admin', new_password):
        return jsonify({'success': True, 'message': 'Admin password updated'})
    return jsonify({'success': False, 'message': 'Failed to update password'}), 500

def update_username(old_username, new_username):
    """Update a user's username."""
    if old_username == new_username:
        return True
        
    users_data = load_users()
    # Check if new username already exists
    if any(u["username"] == new_username for u in users_data["users"]):
        return False
        
    for user in users_data["users"]:
        if user["username"] == old_username:
            user["username"] = new_username
            if save_users(users_data):
                # Update status data with new username
                status_data = load_status()
                if old_username in status_data:
                    status_data[new_username] = status_data.pop(old_username)
                    save_status(status_data)
                # Update downloads directory
                old_dir = os.path.join(app.config['DOWNLOAD_DIR'], old_username)
                new_dir = os.path.join(app.config['DOWNLOAD_DIR'], new_username)
                if os.path.exists(old_dir):
                    os.makedirs(os.path.dirname(new_dir), exist_ok=True)
                    try:
                        os.rename(old_dir, new_dir)
                    except OSError:
                        logger.error(f"Failed to rename directory from {old_dir} to {new_dir}")
                return True
    return False

def create_user(username, password):
    """Create a new user."""
    users_data = load_users()
    if any(u["username"] == username for u in users_data["users"]):
        return False
    
    users_data["users"].append({
        "username": username,
        "password_hash": hash_password(password)
    })
    return save_users(users_data)

def delete_user(username):
    """Delete a user."""
    if username == "admin":  # Prevent admin deletion
        return False
        
    users_data = load_users()
    users_data["users"] = [u for u in users_data["users"] if u["username"] != username]
    if save_users(users_data):
        # Clean up user's status data
        status_data = load_status()
        if username in status_data:
            del status_data[username]
            save_status(status_data)
        # Optionally clean up user's download directory
        user_dir = os.path.join(app.config['DOWNLOAD_DIR'], username)
        if os.path.exists(user_dir):
            try:
                import shutil
                shutil.rmtree(user_dir)
            except OSError:
                logger.error(f"Failed to delete directory: {user_dir}")
        return True
    return False

@app.route('/profile/update_username', methods=['POST'])
def update_user_username():
    """Handle username change requests."""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    new_username = request.form.get('new_username')
    if not new_username:
        flash('Username is required', 'error')
        return redirect(url_for('profile'))

    if update_username(session['username'], new_username):
        session['username'] = new_username
        flash('Username updated successfully', 'success')
    else:
        flash('Failed to update username. It might already be taken.', 'error')

    return redirect(url_for('profile'))

@app.route('/admin/users')
def admin_users():
    """Admin user management page."""
    if not is_admin(session.get('username')):
        return redirect(url_for('index'))
    
    users_data = load_users()
    return render_template('admin_users.html', users=users_data["users"])

@app.route('/admin/users/create', methods=['POST'])
def admin_create_user():
    """Handle user creation by admin."""
    if not is_admin(session.get('username')):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        flash('Username and password are required', 'error')
        return redirect(url_for('admin_users'))

    if create_user(username, password):
        flash(f'User {username} created successfully', 'success')
    else:
        flash('Failed to create user. Username might already exist.', 'error')

    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<username>', methods=['POST'])
def admin_delete_user(username):
    """Handle user deletion by admin."""
    if not is_admin(session.get('username')):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    if delete_user(username):
        flash(f'User {username} deleted successfully', 'success')
    else:
        flash('Failed to delete user', 'error')

    return redirect(url_for('admin_users'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 