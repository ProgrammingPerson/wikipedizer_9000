#!/usr/bin/env python3
"""
Science Olympiad Astronomy 2026 - Web Interface
================================================
A Flask web application for the astronomy research scraper.
"""

import os
import io
import json
import time
import zipfile
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from threading import Thread
from queue import Queue

from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context

# Import the scraper
from astro_scraper import AstronomyScraper, ScraperConfig, DEFAULT_CATEGORIES

# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)

# Production configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size

# Determine environment
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RENDER') or os.environ.get('RAILWAY_ENVIRONMENT')

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


@app.route("/")
def index():
    """Main page."""
    return render_template("index.html", categories=DEFAULT_CATEGORIES)


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
    
    # Clean up output directory after download
    # (Optional: could keep for a while with cleanup job)
    
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"astronomy_notes_{job_id}.zip"
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


if __name__ == "__main__":
    # Ensure templates and static directories exist
    Path("templates").mkdir(exist_ok=True)
    Path("static/css").mkdir(parents=True, exist_ok=True)
    Path("static/js").mkdir(parents=True, exist_ok=True)
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5001))
    debug = not IS_PRODUCTION
    
    print(f"Starting server on port {port} (debug={debug})")
    app.run(debug=debug, host='0.0.0.0', port=port, threaded=True)
