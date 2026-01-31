# Science Olympiad Astronomy 2026 - Research Hub 🔭

A comprehensive multi-source research tool for gathering Science Olympiad Astronomy study materials. Features both a beautiful web interface and command-line tool. Scrapes content from Wikipedia, NASA, ESA, and educational astronomy sites, organizing everything into clean, well-structured text files.

## Features

- **🌐 Modern Web Interface**: Beautiful space-themed UI with real-time progress tracking
- **Multi-Source Scraping**: Pulls content from Wikipedia, NASA, ESA, and educational astronomy sites
- **Interactive Topic Selection**: Choose from default 2026 SciOly topics or define your own
- **Organized Output**: Hierarchical folder structure by category with index files
- **📦 ZIP Download**: Download all generated notes as a single ZIP file
- **Efficient Caching**: Avoids redundant requests with local caching
- **Rate Limiting**: Respectful scraping with configurable delays
- **Clean Text Output**: Removes citations, cleans formatting, preserves structure

## Installation

```bash
# Clone or download the repository
cd wikipedizer_9000

# Install dependencies
pip install -r requirements.txt
```

## Usage

### 🌐 Web Interface (Recommended)

Launch the web application for a visual, user-friendly experience:

```bash
python app.py
```

Then open your browser to **http://localhost:5000**

The web interface features:
- Visual topic selection with category cards
- Source selection (Wikipedia, NASA, ESA, Educational)
- Real-time progress tracking with animated progress ring
- One-click ZIP download of all generated notes

### Command Line - Interactive Mode

Run the scraper directly with interactive prompts:

```bash
python astro_scraper.py
```

You'll be prompted to:
1. Choose topic source (defaults, custom, or config file)
2. Select which sources to scrape (Wikipedia, NASA, ESA, educational)
3. Specify output directory

### Programmatic Mode

Use the `quick_scrape()` function in your own scripts:

```python
from astro_scraper import quick_scrape

# Scrape specific topics
results = quick_scrape(
    topics=["Stellar evolution", "Black hole", "Exoplanet"],
    category="stellar_physics",
    sources=["wikipedia", "nasa"],
    output_dir="my_notes"
)
```

### Using a Config File

Create a `topics.json` file (see included template) and load it:

```bash
python astro_scraper.py
# Select option [4] Load from config file
```

## Configuration File Format

The `topics.json` file structure:

```json
{
  "category_name": {
    "description": "Category description",
    "topics": [
      "Topic 1",
      "Topic 2",
      "Topic 3"
    ]
  }
}
```

## Output Structure

```
astronomy_notes/
├── INDEX.txt                    # Human-readable index
├── index.json                   # Machine-readable index
├── stellar_evolution/
│   ├── Stellar_evolution.txt
│   ├── Protostar.txt
│   └── ...
├── exoplanets/
│   ├── Exoplanet.txt
│   ├── Transit_method.txt
│   └── ...
└── deep_sky_objects/
    ├── Orion_Nebula.txt
    └── ...
```

## Default 2026 Topics

The scraper includes comprehensive default topics for the 2026 Science Olympiad Astronomy event:

- **Stellar Evolution**: Life cycles, formation, end states
- **Stellar Classification**: HR diagram, spectral types, luminosity classes
- **Star Formation**: Molecular clouds, protostars, T Tauri stars
- **Stellar Physics**: Nuclear fusion, nucleosynthesis, stellar structure
- **Exoplanets**: Detection methods, planet types, habitable zones
- **Notable Exoplanets 2026**: HD 80606 b, WASP-17b, K2-18b, and more
- **Deep Sky Objects**: Orion Nebula, Tarantula Nebula, etc.
- **Observational Techniques**: Distance ladder, parallax, standard candles
- **Fundamental Physics**: Blackbody radiation, Kepler's laws, orbital mechanics

## Adding Custom Topics

When running interactively, you can add topics using:

```
category_name: topic1, topic2, topic3
```

Example:
```
exoplanets: Proxima Centauri b, TRAPPIST-1e, Kepler-442b
```

## Sources

| Source | Description |
|--------|-------------|
| Wikipedia | Comprehensive encyclopedia articles |
| NASA | Official NASA science pages and resources |
| ESA | European Space Agency content |
| Educational | Swinburne Astronomy Online and similar sites |

## Tips

1. **Start with defaults**: The built-in 2026 topics cover most event material
2. **Use caching**: Re-running won't re-fetch cached content (delete `.cache/` to refresh)
3. **Be patient**: Rate limiting means large scrapes take time (by design)
4. **Check INDEX.txt**: Quick reference for all generated content

## Project Structure

```
wikipedizer_9000/
├── app.py                 # Flask web application
├── wsgi.py                # WSGI entry point for production
├── astro_scraper.py       # Core scraping engine
├── topics.json            # Default topics configuration
├── requirements.txt       # Python dependencies
├── Procfile               # Heroku/Railway deployment
├── render.yaml            # Render.com deployment
├── railway.json           # Railway deployment
├── templates/
│   └── index.html         # Web interface template
├── static/
│   ├── css/
│   │   └── style.css      # Space-themed styling
│   └── js/
│       └── main.js        # Frontend interactivity
└── astro_prototype.py     # Original prototype (legacy)
```

## 🚀 Deployment

### Option 1: Render (Recommended - Free Tier Available)

1. Push your code to GitHub
2. Go to [render.com](https://render.com) and sign up
3. Click **New > Web Service**
4. Connect your GitHub repository
5. Render will auto-detect the `render.yaml` configuration
6. Click **Create Web Service**

Your app will be live at `https://your-app-name.onrender.com`

### Option 2: Railway

1. Push your code to GitHub
2. Go to [railway.app](https://railway.app) and sign up
3. Click **New Project > Deploy from GitHub repo**
4. Select your repository
5. Railway will auto-detect the configuration

Your app will be live at `https://your-app-name.up.railway.app`

### Option 3: Heroku

```bash
# Install Heroku CLI, then:
heroku login
heroku create your-app-name
git push heroku main
```

### Option 4: Self-Hosted / VPS

```bash
# Install dependencies
pip install -r requirements.txt

# Run with Gunicorn (production)
gunicorn wsgi:app --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:8000

# Or use the provided Procfile
# Behind Nginx or similar reverse proxy
```

### Environment Variables

Set these in your hosting platform:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | Auto-generated |
| `FLASK_ENV` | `production` or `development` | `development` |
| `PORT` | Server port | `5001` |

## Screenshots

The web interface features a modern, space-themed design with:
- Dark nebula background with animated stars
- Glowing accent colors inspired by stellar phenomena
- Smooth animations and micro-interactions
- Responsive layout for all screen sizes

## Legacy Script

The original `astro_prototype.py` is preserved for reference but `astro_scraper.py` and the web app are recommended.

## License

MIT License - Use freely for educational purposes.

---

*Built for Science Olympiad competitors. Good luck at competition!* 🚀
