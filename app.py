import os
import re
import json
import uuid
import bcrypt
import logging
import subprocess
import threading
from flask import Flask, request, render_template, redirect, url_for, session, flash
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

# In-memory download tracking
downloads_status = {}

def process_download(url, user, job_id):
    """Process download in a separate thread."""
    try:
        user_dir = os.path.join(app.config['DOWNLOAD_DIR'], user)
        os.makedirs(user_dir, exist_ok=True)

        # Get video title
        title_cmd = ["yt-dlp", "--print", "%(title)s", url]
        proc_title = subprocess.run(title_cmd, capture_output=True, text=True)
        
        if proc_title.returncode != 0:
            raise Exception(f"Failed to get title: {proc_title.stderr}")

        raw_title = proc_title.stdout.strip()
        safe_title = re.sub(r'[^A-Za-z0-9_\-\s]+', '_', raw_title)

        # Update job with title
        for job in downloads_status[user]:
            if job["id"] == job_id:
                job["title"] = safe_title
                break

        # Build output template
        output_tmpl = os.path.join(user_dir, f"{safe_title} [%(id)s].%(ext)s")

        # Download and convert to FLAC
        cmd = ["yt-dlp", "-x", "--audio-format", "flac", "-o", output_tmpl, url]
        proc_download = subprocess.run(cmd, capture_output=True, text=True)

        # Update job status
        for job in downloads_status[user]:
            if job["id"] == job_id:
                if proc_download.returncode == 0:
                    job["status"] = "completed"
                    logger.info(f"Download completed: user={user}, title={safe_title}")
                else:
                    job["status"] = "failed"
                    job["error"] = proc_download.stderr
                    logger.error(f"Download failed: user={user}, error={proc_download.stderr}")
                break

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Download failed: user={user}, error={error_msg}")
        for job in downloads_status[user]:
            if job["id"] == job_id:
                job["status"] = "failed"
                job["error"] = error_msg
                break

def verify_password(password, hashed):
    """Verify a password against a hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

def load_users():
    """Load users from JSON file."""
    try:
        with open("users.json", "r") as f:
            data = json.load(f)
            return {u["username"]: u["password_hash"] for u in data["users"]}
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        # If no users file exists, create default admin user
        hashed = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt(12))
        users_data = {
            "users": [{
                "username": "admin",
                "password_hash": hashed.decode('utf-8')
            }]
        }
        with open("users.json", "w") as f:
            json.dump(users_data, f, indent=4)
        return {"admin": hashed.decode('utf-8')}

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
    if user not in downloads_status:
        downloads_status[user] = []

    # Create job entry
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "title": "Fetching title...",
        "status": "in_progress",
        "url": url
    }
    downloads_status[user].append(job)

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
    user_downloads = downloads_status.get(user, [])
    return render_template('status.html', downloads=user_downloads)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 