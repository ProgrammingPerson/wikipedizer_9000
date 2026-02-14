#!/usr/bin/env python3
"""
Science Olympiad Astronomy 2026 - Web Interface
================================================
A Flask web application for the astronomy research scraper.
Includes secure Google Drive integration for cloud storage.
"""

import os
import io
import json
import time
import zipfile
import uuid
import shutil
import secrets
from datetime import datetime, timedelta

# Load environment variables from .env file (for local development)
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
from threading import Thread
from queue import Queue
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix

from flask import (
    Flask, render_template, request, jsonify, send_file, 
    Response, stream_with_context, session, redirect, url_for
)

# Import the scraper
from astro_scraper import AstronomyScraper, ScraperConfig, DEFAULT_CATEGORIES

# Google Drive imports (optional - gracefully handle if not installed)
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    GoogleAuthRequest = None  # Placeholder when not available
    print("Google Drive integration not available. Install google-auth-oauthlib and google-api-python-client to enable.")

# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)

# Production configuration - MUST use secure secret key in production
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_urlsafe(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size

# Secure session configuration
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS access to cookies
# Use 'Lax' in production, 'None' causes issues; for dev we can be less strict
app.config['SESSION_COOKIE_SAMESITE'] = None
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)  # Session expiry

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_port=1
)

# Determine environment
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RENDER') or os.environ.get('RAILWAY_ENVIRONMENT')

if IS_PRODUCTION:
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="None"
    )
else:
    app.config.update(
        SESSION_COOKIE_SECURE=False,
        SESSION_COOKIE_SAMESITE="Lax"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE CONFIGURATION (Secure)
# ═══════════════════════════════════════════════════════════════════════════════

# OAuth 2.0 scopes - MINIMAL permissions needed
GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/drive.file'  # Only access files created by app
]

# Get OAuth credentials from environment (NEVER hardcode these)
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

def get_redirect_uri():
    """Get redirect URI based on environment."""
    if IS_PRODUCTION:
        return os.environ.get('GOOGLE_REDIRECT_URI', 'https://wikipedizer-9000.onrender.com/oauth/callback')
    else:
        return 'http://localhost:5001/oauth/callback'

def get_google_client_config():
    """Generate OAuth client config from environment variables."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return None
    
    # Determine redirect URI based on environment
    redirect_uri = get_redirect_uri()
    
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri]
        }
    }

def google_drive_enabled():
    """Check if Google Drive integration is properly configured."""
    return bool(GOOGLE_DRIVE_AVAILABLE and GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def generate_state_token():
    """Generate a secure state token for OAuth CSRF protection."""
    state = secrets.token_urlsafe(32)
    session.permanent = True  # Make session persist
    session['oauth_state'] = state
    session['oauth_state_time'] = datetime.now().isoformat()
    session.modified = True  # Force session save
    return state

def validate_state_token(state):
    """Validate OAuth state token to prevent CSRF attacks."""
    stored_state = session.get('oauth_state')
    state_time = session.get('oauth_state_time')
    
    if not stored_state or not state_time:
        return False
    
    # Check state matches
    if not secrets.compare_digest(stored_state, state):
        return False
    
    # Check state hasn't expired (10 minute window)
    try:
        created = datetime.fromisoformat(state_time)
        if datetime.now() - created > timedelta(minutes=10):
            return False
    except (ValueError, TypeError):
        return False
    
    # Clear used state
    session.pop('oauth_state', None)
    session.pop('oauth_state_time', None)
    
    return True

def require_google_auth(f):
    """Decorator to require Google Drive authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not google_drive_enabled():
            return jsonify({"error": "Google Drive integration not configured"}), 503
        
        credentials = session.get('google_credentials')
        if not credentials:
            return jsonify({"error": "Not authenticated with Google", "needs_auth": True}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def get_drive_service():
    """Get authenticated Google Drive service from session credentials."""
    credentials_data = session.get('google_credentials')
    if not credentials_data:
        return None
    
    try:
        credentials = Credentials(
            token=credentials_data['token'],
            refresh_token=credentials_data.get('refresh_token'),
            token_uri=credentials_data['token_uri'],
            client_id=credentials_data['client_id'],
            client_secret=credentials_data['client_secret'],
            scopes=credentials_data['scopes']
        )
        
        # Check if credentials are expired
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(GoogleAuthRequest())
            # Update session with refreshed credentials
            session['google_credentials'] = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': list(credentials.scopes)
            }
        
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        print(f"Error creating Drive service: {e}")
        session.pop('google_credentials', None)
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

# Store active scraping jobs and their progress
jobs = {}
job_queues = {}


class ProgressTracker:
    """Track and report scraping progress."""
    
    def __init__(self, job_id: str, queue: Queue):
        self.job_id = job_id
        self.queue = queue
        self.total_topics = 0
        self.completed_topics = 0
        self.current_topic = ""
        self.current_source = ""
        self.status = "initializing"
        self.files = []
    
    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.queue.put(self.to_dict())
    
    def to_dict(self):
        return {
            "job_id": self.job_id,
            "total_topics": self.total_topics,
            "completed_topics": self.completed_topics,
            "current_topic": self.current_topic,
            "current_source": self.current_source,
            "status": self.status,
            "progress": (self.completed_topics / self.total_topics * 100) if self.total_topics > 0 else 0,
            "files_count": len(self.files)
        }


class WebScraper(AstronomyScraper):
    """Extended scraper with progress tracking for web interface."""
    
    def __init__(self, config, progress_tracker):
        super().__init__(config)
        self.progress = progress_tracker
    
    def fetch_topic(self, topic: str, use_cache: bool = True) -> dict:
        """Override to add progress tracking."""
        self.progress.update(current_topic=topic, status="fetching")
        
        results = {"topic": topic, "sources": {}}
        
        for source_name in self.config.include_sources:
            if source_name not in self.sources:
                continue
            
            self.progress.update(current_source=source_name)
            
            # Check cache first
            if use_cache:
                cached = self._load_from_cache(topic, source_name)
                if cached:
                    results["sources"][source_name] = cached
                    continue
            
            # Fetch from source
            source = self.sources[source_name]
            try:
                data = source.get_article(topic)
                if data:
                    results["sources"][source_name] = data
                    if use_cache:
                        self._save_to_cache(topic, source_name, data)
                    print(f"  ✓ Got {len(data.get('sections', []))} sections from {source_name} for {topic}")
                else:
                    print(f"  ✗ No data from {source_name} for {topic}")
            except Exception as e:
                print(f"  ⚠ Error from {source_name} for {topic}: {e}")
            
            # Rate limiting
            time.sleep(self.config.request_delay)
        
        return results
    
    def scrape_category(self, category: str, topics: list) -> list:
        """Override to add progress tracking."""
        saved_files = []
        
        for topic in topics:
            topic_data = self.fetch_topic(topic)
            
            if topic_data["sources"]:
                filepath = self.save_topic(topic_data, category)
                saved_files.append(str(filepath))
                self.progress.files.append(str(filepath))
            
            self.progress.update(
                completed_topics=self.progress.completed_topics + 1,
                status="processing"
            )
        
        return saved_files


def run_scrape_job(job_id: str, categories: dict, sources: list, output_dir: str, queue: Queue):
    """Background task to run scraping job."""
    try:
        # Calculate total topics
        total = sum(
            len(data.get("topics", data) if isinstance(data, dict) else data)
            for data in categories.values()
        )
        
        progress = ProgressTracker(job_id, queue)
        progress.update(total_topics=total, status="starting")
        
        config = ScraperConfig(
            output_dir=output_dir,
            include_sources=sources,
            request_delay=0.3  # Slightly faster for web
        )
        
        scraper = WebScraper(config, progress)
        
        # Run the scraping
        for category, data in categories.items():
            if isinstance(data, dict):
                topics = data.get("topics", [])
            else:
                topics = data
            
            scraper.scrape_category(category, topics)
        
        # Save index files
        scraper._save_index(
            {
                "started_at": datetime.now().isoformat(),
                "categories": {k: {"topics_count": len(v.get("topics", v) if isinstance(v, dict) else v)} 
                              for k, v in categories.items()},
                "total_files": len(progress.files)
            },
            categories
        )
        
        progress.update(status="complete")
        jobs[job_id] = {
            "status": "complete",
            "output_dir": output_dir,
            "files": progress.files
        }
        
    except Exception as e:
        queue.put({"job_id": job_id, "status": "error", "error": str(e)})
        jobs[job_id] = {"status": "error", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Main page."""
    google_connected = 'google_credentials' in session
    return render_template(
        "index.html", 
        categories=DEFAULT_CATEGORIES,
        google_drive_enabled=google_drive_enabled(),
        google_connected=google_connected
    )


@app.route("/health")
def health_check():
    """Health check endpoint for hosting platforms."""
    return jsonify({"status": "healthy", "service": "wikipedizer-9000"})


@app.route("/api/categories")
def get_categories():
    """Get default categories."""
    return jsonify(DEFAULT_CATEGORIES)


@app.route("/api/scrape", methods=["POST"])
def start_scrape():
    """Start a new scraping job."""
    data = request.json
    
    # Get selected categories and topics
    selected_categories = data.get("categories", {})
    sources = data.get("sources", ["wikipedia", "nasa", "esa", "educational"])
    
    if not selected_categories:
        return jsonify({"error": "No categories selected"}), 400
    
    # Create unique job ID and output directory
    job_id = str(uuid.uuid4())[:8]
    output_dir = f"output_{job_id}"
    
    # Create job queue for progress updates
    queue = Queue()
    job_queues[job_id] = queue
    jobs[job_id] = {"status": "running", "output_dir": output_dir}
    
    # Start background scraping task
    thread = Thread(
        target=run_scrape_job,
        args=(job_id, selected_categories, sources, output_dir, queue)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"job_id": job_id, "status": "started"})


@app.route("/api/progress/<job_id>")
def get_progress(job_id):
    """Server-sent events for progress updates."""
    def generate():
        if job_id not in job_queues:
            yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
            return
        
        queue = job_queues[job_id]
        
        while True:
            try:
                progress = queue.get(timeout=30)
                yield f"data: {json.dumps(progress)}\n\n"
                
                if progress.get("status") in ["complete", "error"]:
                    break
            except Exception:
                # Timeout - send heartbeat
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.route("/api/download/<job_id>")
def download_results(job_id):
    """Download results as ZIP file."""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = jobs[job_id]
    if job["status"] != "complete":
        return jsonify({"error": "Job not complete"}), 400
    
    output_dir = job["output_dir"]
    
    if not os.path.exists(output_dir):
        return jsonify({"error": "Output directory not found"}), 404
    
    # Create ZIP file in memory
    memory_file = io.BytesIO()
    
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_dir)
                zf.write(file_path, f"astronomy_notes/{arcname}")
    
    memory_file.seek(0)
    
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"astronomy_notes_{job_id}.zip"
    )


@app.route("/api/download-text/<job_id>")
def download_text_file(job_id):
    """Download all results as a single concatenated text file."""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = jobs[job_id]
    if job["status"] != "complete":
        return jsonify({"error": "Job not complete"}), 400
    
    output_dir = job["output_dir"]
    
    if not os.path.exists(output_dir):
        return jsonify({"error": "Output directory not found"}), 404
    
    # Collect all text files and sort them
    text_files = []
    for root, _, files in os.walk(output_dir):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, output_dir)
                text_files.append((rel_path, file_path))
    
    # Sort files by path for consistent ordering
    text_files.sort(key=lambda x: x[0])
    
    if not text_files:
        return jsonify({"error": "No text files found"}), 404
    
    # Concatenate all files with separators
    concatenated_content = []
    
    # Add header
    concatenated_content.append("=" * 80)
    concatenated_content.append("  ASTRONOMY RESEARCH NOTES - COMPLETE COLLECTION")
    concatenated_content.append("=" * 80)
    concatenated_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    concatenated_content.append(f"Total Files: {len(text_files)}")
    concatenated_content.append("=" * 80)
    concatenated_content.append("")
    
    # Add each file's content
    for i, (rel_path, file_path) in enumerate(text_files, 1):
        concatenated_content.append("")
        concatenated_content.append("")
        concatenated_content.append("╔" + "═" * 78 + "╗")
        concatenated_content.append(f"║  File {i}/{len(text_files)}: {rel_path}".ljust(79) + "║")
        concatenated_content.append("╚" + "═" * 78 + "╝")
        concatenated_content.append("")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                concatenated_content.append(content)
        except Exception as e:
            concatenated_content.append(f"[Error reading file: {str(e)}]")
        
        concatenated_content.append("")
        concatenated_content.append("")
    
    # Add footer
    concatenated_content.append("")
    concatenated_content.append("=" * 80)
    concatenated_content.append("  END OF COLLECTION")
    concatenated_content.append("=" * 80)
    
    # Create text file in memory
    text_content = "\n".join(concatenated_content)
    memory_file = io.BytesIO()
    memory_file.write(text_content.encode('utf-8'))
    memory_file.seek(0)
    
    return send_file(
        memory_file,
        mimetype="text/plain",
        as_attachment=True,
        download_name=f"astronomy_notes_{job_id}.txt"
    )


@app.route("/api/cleanup/<job_id>", methods=["POST"])
def cleanup_job(job_id):
    """Clean up job files."""
    if job_id in jobs:
        output_dir = jobs[job_id].get("output_dir")
        if output_dir and os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        
        if job_id in job_queues:
            del job_queues[job_id]
        del jobs[job_id]
    
    return jsonify({"status": "cleaned"})


# ═══════════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE OAUTH ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/google/status")
def google_status():
    """Check Google Drive connection status."""
    return jsonify({
        "enabled": google_drive_enabled(),
        "connected": 'google_credentials' in session
    })


@app.route("/oauth/google/authorize")
def google_authorize():
    """Initiate Google OAuth flow."""
    if not google_drive_enabled():
        return jsonify({"error": "Google Drive integration not configured"}), 503
    
    client_config = get_google_client_config()
    if not client_config:
        return jsonify({"error": "Google OAuth not configured"}), 503
    
    # Determine redirect URI
    redirect_uri = get_redirect_uri()
    
    # Create OAuth flow
    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=redirect_uri
    )
    
    # Generate secure state token for CSRF protection
    state = generate_state_token()
    
    # Generate authorization URL
    authorization_url, _ = flow.authorization_url(
        access_type='offline',  # Get refresh token
        include_granted_scopes='true',
        prompt='consent',  # Always show consent screen
        state=state
    )
    
    return redirect(authorization_url)


@app.route("/oauth/callback")
def oauth_callback():
    print("ARGS:", dict(request.args))
    print("SESSION:", dict(session))
    """Handle OAuth callback from Google."""
    if not google_drive_enabled():
        return "Google Drive integration not configured", 503
    
    # Verify state token (CSRF protection)
    state = request.args.get('state')
    if not state or not validate_state_token(state):
        return "Invalid state token - possible CSRF attack", 400
    
    # Check for errors
    error = request.args.get('error')
    if error:
        return f"Authorization failed: {error}", 400
    
    # Get authorization code
    code = request.args.get('code')
    if not code:
        return "No authorization code received", 400
    
    client_config = get_google_client_config()
    
    # Determine redirect URI (must match exactly)
    redirect_uri = get_redirect_uri()
    
    try:
        # Create flow and exchange code for credentials
        flow = Flow.from_client_config(
            client_config,
            scopes=GOOGLE_SCOPES,
            state=state,
            redirect_uri=redirect_uri
        )
        
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        # Store credentials in session (encrypted by Flask)
        session['google_credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': list(credentials.scopes)
        }
        
        session.permanent = True  # Use permanent session
        
        # Redirect back to main page
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"OAuth error: {e}")
        return f"Authentication failed: {str(e)}", 500


@app.route("/oauth/google/disconnect", methods=["POST"])
def google_disconnect():
    """Disconnect Google Drive."""
    session.pop('google_credentials', None)
    return jsonify({"status": "disconnected"})


# ═══════════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE API ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/drive/upload/<job_id>", methods=["POST"])
@require_google_auth
def upload_to_drive(job_id):
    """Upload job results to Google Drive."""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = jobs[job_id]
    if job["status"] != "complete":
        return jsonify({"error": "Job not complete"}), 400
    
    output_dir = job["output_dir"]
    if not os.path.exists(output_dir):
        return jsonify({"error": "Output directory not found"}), 404
    
    # Get target folder ID (optional)
    data = request.json or {}
    folder_id = data.get("folder_id")  # None = upload to root
    folder_name = data.get("folder_name", f"Astronomy_Notes_{job_id}")
    
    service = get_drive_service()
    if not service:
        return jsonify({"error": "Failed to connect to Google Drive", "needs_auth": True}), 401
    
    try:
        # Create a new folder for this export
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if folder_id:
            folder_metadata['parents'] = [folder_id]
        
        created_folder = service.files().create(
            body=folder_metadata,
            fields='id, name, webViewLink'
        ).execute()
        
        parent_folder_id = created_folder['id']
        uploaded_files = []
        
        # Upload all files
        for root, _, files in os.walk(output_dir):
            # Create subfolders
            rel_path = os.path.relpath(root, output_dir)
            current_parent = parent_folder_id
            
            if rel_path != '.':
                # Create subfolder
                subfolder_metadata = {
                    'name': rel_path.replace('/', '_'),
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [parent_folder_id]
                }
                subfolder = service.files().create(
                    body=subfolder_metadata,
                    fields='id'
                ).execute()
                current_parent = subfolder['id']
            
            # Upload files in this directory
            for filename in files:
                file_path = os.path.join(root, filename)
                
                file_metadata = {
                    'name': filename,
                    'parents': [current_parent]
                }
                
                # Read file content
                with open(file_path, 'rb') as f:
                    media = MediaIoBaseUpload(
                        io.BytesIO(f.read()),
                        mimetype='text/plain',
                        resumable=True
                    )
                
                uploaded_file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, name'
                ).execute()
                
                uploaded_files.append(uploaded_file['name'])
        
        return jsonify({
            "status": "success",
            "folder_name": created_folder['name'],
            "folder_link": created_folder.get('webViewLink'),
            "files_uploaded": len(uploaded_files)
        })
        
    except Exception as e:
        print(f"Drive upload error: {e}")
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Ensure templates and static directories exist
    Path("templates").mkdir(exist_ok=True)
    Path("static/css").mkdir(parents=True, exist_ok=True)
    Path("static/js").mkdir(parents=True, exist_ok=True)
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5001))
    debug = not IS_PRODUCTION
    
    # Security warning for development
    if debug and not GOOGLE_CLIENT_ID:
        print("\n⚠️  Google Drive integration disabled (no credentials configured)")
        print("   Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables to enable.\n")
    
    print(f"Starting server on port {port} (debug={debug})")
    app.run(debug=debug, host='0.0.0.0', port=port, threaded=True)
