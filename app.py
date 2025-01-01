import os
import re
import json
import uuid
import bcrypt
import logging
import subprocess
import threading
import time
import queue
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse
from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

AUDIO_FORMATS: List[Tuple[str, str]] = [
    ("flac", "FLAC (Lossless)"),
    ("wav", "WAV (Lossless)"),
    ("aac", "AAC (High Quality)"),
    ("m4a", "M4A (High Quality)"),
    ("opus", "Opus (High Quality)"),
    ("vorbis", "Vorbis (High Quality)"),
    ("mp3", "MP3 (Compatible)")
]

@dataclass
class DownloadTask:
    """Represents a download task in the queue."""
    id: str
    url: str
    user: str
    priority: int = 0
    paused: bool = False
    speed_limit: Optional[float] = None  # in MB/s
    progress: float = 0.0
    title: Optional[str] = None
    status: str = "queued"
    error: Optional[str] = None

class DownloadQueue:
    """Manages download queue and concurrent downloads."""
    def __init__(self, max_concurrent: int = 2):
        self.queue = queue.PriorityQueue()
        self.active_downloads: Dict[str, DownloadTask] = {}
        self.max_concurrent = max_concurrent
        self.lock = threading.Lock()
        self.global_speed_limit: Optional[float] = None  # in MB/s
        
        # Start queue processor
        self.processor_thread = threading.Thread(target=self._process_queue)
        self.processor_thread.daemon = True
        self.processor_thread.start()
    
    def add_task(self, task: DownloadTask) -> None:
        """Add a task to the queue."""
        # Priority queue sorts by first element, negative to make higher priority come first
        self.queue.put((-task.priority, task))
        logger.info(f"Added task to queue: {task.id}")
    
    def pause_task(self, task_id: str) -> bool:
        """Pause a download task."""
        with self.lock:
            if task_id in self.active_downloads:
                self.active_downloads[task_id].paused = True
                return True
            # Search in queue
            with self.queue.mutex:
                for _, task in self.queue.queue:
                    if task.id == task_id:
                        task.paused = True
                        return True
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """Resume a paused download task."""
        with self.lock:
            if task_id in self.active_downloads:
                self.active_downloads[task_id].paused = False
                return True
            # Search in queue
            with self.queue.mutex:
                for _, task in self.queue.queue:
                    if task.id == task_id:
                        task.paused = False
                        return True
        return False
    
    def set_global_speed_limit(self, limit: Optional[float]) -> None:
        """Set global speed limit in MB/s."""
        self.global_speed_limit = limit
        logger.info(f"Set global speed limit to: {limit} MB/s")
    
    def get_all_tasks(self) -> List[DownloadTask]:
        """Get all tasks (queued and active)."""
        with self.lock:
            # Get active downloads
            tasks = list(self.active_downloads.values())
            # Get queued tasks
            with self.queue.mutex:
                tasks.extend([task for _, task in self.queue.queue])
            return tasks
    
    def _process_queue(self) -> None:
        """Process the download queue."""
        while True:
            try:
                # Check if we can start new downloads
                with self.lock:
                    if len(self.active_downloads) >= self.max_concurrent:
                        time.sleep(1)
                        continue
                
                # Get next task
                _, task = self.queue.get(block=True)
                
                # Skip if paused
                if task.paused:
                    self.queue.put((-task.priority, task))
                    time.sleep(1)
                    continue
                
                # Add to active downloads
                with self.lock:
                    self.active_downloads[task.id] = task
                
                # Start download thread
                thread = threading.Thread(
                    target=self._download_worker,
                    args=(task,)
                )
                thread.daemon = True
                thread.start()
                
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                time.sleep(1)
    
    def _download_worker(self, task: DownloadTask) -> None:
        """Handle individual download."""
        try:
            # Apply speed limit
            speed_limit = self.global_speed_limit
            if task.speed_limit is not None:
                speed_limit = min(speed_limit, task.speed_limit) if speed_limit else task.speed_limit
            
            # Start download with speed limit
            process_download(task.url, task.user, task.id, speed_limit)
            
        except Exception as e:
            logger.error(f"Error in download worker: {e}")
            task.status = "failed"
            task.error = str(e)
        finally:
            # Remove from active downloads
            with self.lock:
                self.active_downloads.pop(task.id, None)

# Initialize download queue
download_queue = DownloadQueue(max_concurrent=2)

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

def get_format_fallbacks(preferred_format: str) -> List[str]:
    """Get list of formats to try in order of preference."""
    format_order = [f[0] for f in AUDIO_FORMATS]
    try:
        start_index = format_order.index(preferred_format)
        return format_order[start_index:] + format_order[:start_index]
    except ValueError:
        return format_order  # If preferred format not found, try all formats

def process_spotify_download(url, user_dir, safe_title=None, speed_limit=None):
    """Download a Spotify track."""
    # Get user's preferred format
    users_data = load_users()
    user = next((u for u in users_data['users'] if u['username'] == session['username']), None)
    preferred_format = user.get('default_format', 'flac')
    
    # Get format fallbacks
    formats_to_try = get_format_fallbacks(preferred_format)
    
    for audio_format in formats_to_try:
        cmd = [
            "spotdl",
            url,
            "--format", audio_format,
            "--output", user_dir,
            "--print-errors",
            "--lyrics",
            "--threads", "1"
        ]
        
        # Add speed limit if specified
        if speed_limit:
            cmd.extend(["--yt-dlp-args", f"--limit-rate {int(speed_limit * 1024 * 1024)}"])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Successfully downloaded in {audio_format} format")
            break
        else:
            logger.warning(f"Failed to download in {audio_format} format, trying next format: {result.stderr}")
    
    return result

def process_youtube_download(url, user_dir, safe_title, speed_limit=None):
    """Download a YouTube video and convert to audio."""
    output_tmpl = os.path.join(user_dir, f"{safe_title} [%(id)s].%(ext)s")
    
    # Get user's preferred format
    users_data = load_users()
    user = next((u for u in users_data['users'] if u['username'] == session['username']), None)
    preferred_format = user.get('default_format', 'flac')
    
    # Get format fallbacks
    formats_to_try = get_format_fallbacks(preferred_format)
    
    for audio_format in formats_to_try:
        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format", audio_format,
            "--audio-quality", "0",
            "--embed-thumbnail",  # Add thumbnail as cover art
            "--embed-metadata",   # Include metadata
            "--parse-metadata", "%(title)s:%(meta_title)s",
            "--parse-metadata", "%(uploader)s:%(meta_artist)s",
            "--add-metadata",
            "--progress",  # Show progress
            "-o", output_tmpl,
        ]
        
        # Add speed limit if specified
        if speed_limit:
            cmd.extend(["--limit-rate", f"{int(speed_limit * 1024 * 1024)}"])
        
        cmd.append(url)
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Successfully downloaded in {audio_format} format")
            return result
        else:
            logger.warning(f"Failed to download in {audio_format} format, trying next format")
    
    # If all formats failed
    return result  # Return the last failed result

def get_title(url):
    """Get the title of the track/video."""
    if is_spotify_url(url):
        cmd = ["spotdl", "--print-errors", url]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise Exception(f"Failed to get Spotify track info: {proc.stderr}")
        # Parse output for title
        for line in proc.stdout.strip().split('\n'):
            if 'Title:' in line:
                return line.split('Title:', 1)[1].strip()
        raise Exception("Could not find title in Spotify track info")
    else:
        cmd = ["yt-dlp", "--print", "%(title)s", url]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise Exception(f"Failed to get title: {proc.stderr}")
        return proc.stdout.strip()

def process_download(url, user, job_id, speed_limit=None):
    """Process download in a separate thread."""
    try:
        user_dir = os.path.join(app.config['DOWNLOAD_DIR'], user)
        os.makedirs(user_dir, exist_ok=True)

        # Get title and update initial status
        try:
            raw_title = get_title(url)
            safe_title = re.sub(r'[^A-Za-z0-9_\-\s]+', '_', raw_title)
        except Exception as e:
            logger.error(f"Failed to get title: {str(e)}")
            safe_title = "Unknown Title"
            raw_title = "Unknown Title"

        # Always create an initial status entry
        update_job_status(user, job_id, {
            "title": raw_title,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "url": url,
            "status": "in_progress"
        })

        # Download based on URL type
        if is_spotify_url(url):
            proc_download = process_spotify_download(url, user_dir, safe_title, speed_limit)
        else:
            proc_download = process_youtube_download(url, user_dir, safe_title, speed_limit)

        # Update job status
        if proc_download.returncode == 0:
            update_job_status(user, job_id, {
                "status": "completed",
                "completed_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            logger.info(f"Download completed: user={user}, title={safe_title}")
        else:
            error_msg = proc_download.stderr or "Unknown error occurred"
            update_job_status(user, job_id, {
                "status": "failed",
                "error": error_msg,
                "completed_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            logger.error(f"Download failed: user={user}, error={error_msg}")

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
        os.makedirs(os.path.dirname(app.config['USERS_FILE']), exist_ok=True)
        if os.path.exists(app.config['USERS_FILE']):
            with open(app.config['USERS_FILE'], 'r') as f:
                return json.load(f)
        
        # Create default admin user if file doesn't exist
        default_users = {
            "users": [{
                "username": "admin",
                "password_hash": hash_password("admin"),
                "role": "admin",
                "default_format": "flac"
            }]
        }
        with open(app.config['USERS_FILE'], 'w') as f:
            json.dump(default_users, f, indent=4)
        return default_users
        
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        # Return default admin user even if file operations fail
        return {
            "users": [{
                "username": "admin",
                "password_hash": hash_password("admin"),
                "role": "admin",
                "default_format": "flac"
            }]
        }

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
    users_data = load_users()
    user = next((u for u in users_data['users'] if u['username'] == username), None)
    return user and user.get('role') == 'admin'

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
        
        # Get user from users list
        users_data = load_users()
        user = next((u for u in users_data['users'] if u['username'] == username), None)

        if user and verify_password(password, user['password_hash']):
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
    priority = int(request.form.get('priority', 0))

    if not url:
        flash('Please provide a valid URL', 'error')
        return redirect(url_for('index'))

    # Create download task
    task = DownloadTask(
        id=str(uuid.uuid4()),
        url=url,
        user=user,
        priority=priority
    )
    
    # Add to queue
    download_queue.add_task(task)
    
    flash('Download added to queue! Check the status page for progress.', 'success')
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
    
    # Store original state for rollback
    original_users = json.loads(json.dumps(users_data))
    original_status = load_status()
    
    try:
        # 1. Update username in users.json
        user = next((u for u in users_data["users"] if u["username"] == old_username), None)
        if not user:
            raise Exception("User not found")
            
        user["username"] = new_username
        if not save_users(users_data):
            raise Exception("Failed to save user data")
            
        # 2. Update status data
        status_data = load_status()
        if old_username in status_data:
            status_data[new_username] = status_data.pop(old_username)
            if not save_status(status_data):
                raise Exception("Failed to save status data")
        
        # 3. Update downloads directory
        old_dir = os.path.join(app.config['DOWNLOAD_DIR'], old_username)
        new_dir = os.path.join(app.config['DOWNLOAD_DIR'], new_username)
        if os.path.exists(old_dir):
            os.makedirs(os.path.dirname(new_dir), exist_ok=True)
            try:
                os.rename(old_dir, new_dir)
            except OSError as e:
                raise Exception(f"Failed to rename downloads directory: {str(e)}")
        
        return True
        
    except Exception as e:
        # Rollback on any error
        logger.error(f"Username update failed, rolling back: {str(e)}")
        save_users(original_users)
        save_status(original_status)
        
        # Try to restore directory if it was renamed
        new_dir = os.path.join(app.config['DOWNLOAD_DIR'], new_username)
        old_dir = os.path.join(app.config['DOWNLOAD_DIR'], old_username)
        if os.path.exists(new_dir) and not os.path.exists(old_dir):
            try:
                os.rename(new_dir, old_dir)
            except OSError:
                logger.error(f"Failed to rollback directory rename from {new_dir} to {old_dir}")
        
        return False

def create_user(username, password):
    """Create a new user."""
    users_data = load_users()
    if any(u["username"] == username for u in users_data["users"]):
        return False
    
    users_data["users"].append({
        "username": username,
        "password_hash": hash_password(password),
        "role": "user",
        "default_format": "flac"
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

    try:
        if update_username(session['username'], new_username):
            # Store the user's role before updating session
            was_admin = is_admin(session['username'])
            session['username'] = new_username
            flash('Username updated successfully', 'success')
            
            # If user was admin, ensure they keep admin access
            if was_admin and not is_admin(new_username):
                users_data = load_users()
                user = next((u for u in users_data['users'] if u['username'] == new_username), None)
                if user:
                    user['role'] = 'admin'
                    save_users(users_data)
        else:
            flash('Failed to update username. It might already be taken.', 'error')
    except Exception as e:
        flash(f'Error updating username: {str(e)}', 'error')

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

@app.route('/admin/queue')
def admin_queue():
    """Admin queue management page."""
    if not is_admin(session.get('username')):
        return redirect(url_for('index'))
    
    # Get all tasks
    all_tasks = download_queue.get_all_tasks()
    
    # Split into active and queued
    active_downloads = []
    queued_downloads = []
    for task in all_tasks:
        if task.id in download_queue.active_downloads:
            active_downloads.append(task)
        else:
            queued_downloads.append(task)
    
    return render_template('admin_queue.html',
                         active_downloads=active_downloads,
                         queued_downloads=queued_downloads,
                         global_speed_limit=download_queue.global_speed_limit)

@app.route('/admin/queue/speed_limit', methods=['POST'])
def admin_set_speed_limit():
    """Set global download speed limit."""
    if not is_admin(session.get('username')):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403
    
    try:
        speed_limit = float(request.form.get('speed_limit', 0))
        if speed_limit <= 0:
            speed_limit = None
        download_queue.set_global_speed_limit(speed_limit)
        flash('Speed limit updated successfully', 'success')
    except ValueError:
        flash('Invalid speed limit value', 'error')
    
    return redirect(url_for('admin_queue'))

@app.route('/admin/queue/pause/<task_id>', methods=['POST'])
def admin_pause_task(task_id):
    """Pause a download task."""
    if not is_admin(session.get('username')):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403
    
    if download_queue.pause_task(task_id):
        flash('Task paused successfully', 'success')
    else:
        flash('Failed to pause task', 'error')
    
    return redirect(url_for('admin_queue'))

@app.route('/admin/queue/resume/<task_id>', methods=['POST'])
def admin_resume_task(task_id):
    """Resume a paused download task."""
    if not is_admin(session.get('username')):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403
    
    if download_queue.resume_task(task_id):
        flash('Task resumed successfully', 'success')
    else:
        flash('Failed to resume task', 'error')
    
    return redirect(url_for('admin_queue'))

@app.route('/admin/queue/priority/<task_id>', methods=['POST'])
def admin_set_priority(task_id):
    """Set priority for a queued download task."""
    if not is_admin(session.get('username')):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403
    
    try:
        priority = int(request.form.get('priority', 0))
        # Find task and update priority
        all_tasks = download_queue.get_all_tasks()
        for task in all_tasks:
            if task.id == task_id:
                task.priority = priority
                flash('Priority updated successfully', 'success')
                break
        else:
            flash('Task not found', 'error')
    except ValueError:
        flash('Invalid priority value', 'error')
    
    return redirect(url_for('admin_queue'))

@app.route('/preview')
def preview():
    """Get preview information for a URL."""
    url = request.args.get('url', '').strip()
    if not url:
        return jsonify({'success': False, 'message': 'No URL provided'})

    try:
        if is_spotify_url(url):
            # Get Spotify track info using spotdl
            cmd = ["spotdl", "--print-errors", url]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            
            if proc.returncode != 0:
                logger.error(f"Spotify preview error: {proc.stderr}")
                return jsonify({'success': False, 'message': 'Failed to get track info'})
            
            # Parse spotdl output
            output = proc.stdout.strip()
            title = None
            artist = None
            thumbnail = None
            duration = None
            
            for line in output.split('\n'):
                if 'Title:' in line:
                    title = line.split('Title:', 1)[1].strip()
                elif 'Artist:' in line:
                    artist = line.split('Artist:', 1)[1].strip()
                elif 'Thumbnail:' in line:
                    thumbnail = line.split('Thumbnail:', 1)[1].strip()
                elif 'Duration:' in line:
                    duration = line.split('Duration:', 1)[1].strip()
            
            if not title:
                return jsonify({'success': False, 'message': 'Could not extract track information'})
            
            return jsonify({
                'success': True,
                'title': title,
                'artist': artist or "Unknown Artist",
                'thumbnail': thumbnail or "",
                'duration': duration or ""
            })
        else:
            # Get YouTube video info
            cmd = [
                "yt-dlp",
                "--print", "%(title)s",
                "--print", "%(uploader)s",
                "--print", "%(thumbnail)s",
                "--print", "%(duration_string)s",
                url
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                return jsonify({'success': False, 'message': 'Failed to get video info'})
            
            # Parse yt-dlp output
            lines = proc.stdout.strip().split('\n')
            return jsonify({
                'success': True,
                'title': lines[0],
                'artist': lines[1],
                'thumbnail': lines[2],
                'duration': lines[3]
            })
            
    except Exception as e:
        logger.error(f"Preview error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/batch_download', methods=['POST'])
def batch_download():
    """Handle batch download requests."""
    urls = request.form.get('urls', '').strip().split('\n')
    urls = [url.strip() for url in urls if url.strip()]
    base_priority = int(request.form.get('priority', 0))
    user = session['username']

    if not urls:
        flash('Please provide at least one valid URL', 'error')
        return redirect(url_for('index'))

    # Add each URL to the queue with incrementing priority
    for i, url in enumerate(urls):
        task = DownloadTask(
            id=str(uuid.uuid4()),
            url=url,
            user=user,
            priority=base_priority + i  # Increment priority for each URL
        )
        download_queue.add_task(task)

    flash(f'Added {len(urls)} downloads to queue! Check the status page for progress.', 'success')
    return redirect(url_for('status'))

@app.route('/profile/update_format', methods=['POST'])
def update_format_preference():
    """Update user's preferred audio format."""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    new_format = request.form.get('default_format')
    if not new_format or new_format not in [f[0] for f in AUDIO_FORMATS]:
        flash('Invalid format selection', 'error')
        return redirect(url_for('profile'))

    users_data = load_users()
    for user in users_data['users']:
        if user['username'] == session['username']:
            user['default_format'] = new_format
            if save_users(users_data):
                flash('Audio format preference updated successfully', 'success')
            else:
                flash('Failed to update format preference', 'error')
            break

    return redirect(url_for('profile'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 