#!/usr/bin/env python3
"""
Science Olympiad Astronomy 2026 - Multi-Source Research Scraper
================================================================
A comprehensive tool for gathering astronomy study materials from multiple sources
including Wikipedia, NASA, and astronomical databases.

Features:
- Multi-source scraping (Wikipedia, NASA, ESA, educational sites)
- User-defined starting points and topics
- Organized folder structure by category
- Efficient async processing with rate limiting
- Clean text output with source attribution
"""

import re
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup
from lxml import etree

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScraperConfig:
    """Configuration for the astronomy scraper."""
    output_dir: str = "astronomy_notes"
    cache_dir: str = ".cache"
    max_concurrent: int = 5
    request_delay: float = 0.5  # seconds between requests (be respectful)
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    include_sources: list = field(default_factory=lambda: ["wikipedia", "nasa", "esa", "educational"])
    

# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT 2026 SCIENCE OLYMPIAD ASTRONOMY TOPICS
# Based on official Science Olympiad Division C Rules 2026
# Focus: Stellar Evolution and Exoplanets
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_CATEGORIES = {
    "stellar_evolution_basics": {
        "description": "Core concepts of how stars change over time",
        "topics": [
            "Stellar evolution",
            "Star formation",
            "Jeans mass",
            "Protostar",
            "Pre-main-sequence star",
            "Zero-age main sequence",
            "Main sequence",
            "Stellar mass",
            "Mass-luminosity relation",
        ]
    },
    "stellar_classification": {
        "description": "Classification systems and stellar properties",
        "topics": [
            "Stellar classification",
            "Hertzsprung-Russell diagram",
            "Spectral type",
            "Luminosity class",
            "Morgan-Keenan classification",
            "Color index",
            "Effective temperature",
            "Absolute magnitude",
            "Apparent magnitude",
        ]
    },
    "star_formation_regions": {
        "description": "Processes and regions of star formation",
        "topics": [
            "Molecular cloud",
            "Giant molecular cloud",
            "Bok globule",
            "H II region",
            "H I region",
            "Interstellar medium",
            "Herbig-Haro object",
            "T Tauri star",
            "Herbig Ae/Be star",
            "Protoplanetary disk",
            "Debris disk",
            "Bipolar outflow",
        ]
    },
    "low_mass_evolution": {
        "description": "Evolution of low and medium mass stars",
        "topics": [
            "Red dwarf",
            "Brown dwarf",
            "Subgiant",
            "Red giant branch",
            "Red giant",
            "Horizontal branch",
            "Asymptotic giant branch",
            "Planetary nebula",
            "White dwarf",
            "Chandrasekhar limit",
            "Electron degeneracy pressure",
        ]
    },
    "high_mass_evolution": {
        "description": "Evolution of massive stars",
        "topics": [
            "Blue giant",
            "Blue supergiant",
            "Red supergiant",
            "Wolf-Rayet star",
            "Luminous blue variable",
            "Supernova",
            "Core-collapse supernova",
            "Type II supernova",
            "Supernova remnant",
            "Neutron star",
            "Pulsar",
            "Magnetar",
            "Black hole",
        ]
    },
    "binary_variable_stars": {
        "description": "Binary systems and variable stars",
        "topics": [
            "Binary star",
            "Eclipsing binary",
            "Spectroscopic binary",
            "Type Ia supernova",
            "Nova",
            "Variable star",
            "Cepheid variable",
            "RR Lyrae variable",
            "Mira variable",
        ]
    },
    "stellar_physics": {
        "description": "Physical processes in stars",
        "topics": [
            "Nuclear fusion",
            "Proton-proton chain",
            "CNO cycle",
            "Triple-alpha process",
            "Stellar nucleosynthesis",
            "S-process",
            "R-process",
            "Hydrostatic equilibrium",
            "Radiation pressure",
            "Convection zone",
            "Radiative zone",
            "Stellar core",
        ]
    },
    "exoplanet_detection": {
        "description": "Methods for detecting exoplanets",
        "topics": [
            "Exoplanet",
            "Methods of detecting exoplanets",
            "Transit photometry",
            "Doppler spectroscopy",
            "Radial velocity method",
            "Direct imaging",
            "Gravitational microlensing",
            "Astrometry",
        ]
    },
    "exoplanet_types": {
        "description": "Types and characteristics of exoplanets",
        "topics": [
            "Hot Jupiter",
            "Super-Earth",
            "Mini-Neptune",
            "Gas giant",
            "Terrestrial planet",
            "Habitable zone",
            "Planetary equilibrium temperature",
        ]
    },
    "exoplanet_missions": {
        "description": "Space missions for exoplanet discovery",
        "topics": [
            "Kepler space telescope",
            "TESS (spacecraft)",
            "James Webb Space Telescope",
        ]
    },
    "2026_dsos": {
        "description": "Official 2026 Science Olympiad Deep Sky Objects",
        "topics": [
            "Orion Molecular Cloud Complex",
            "NGC 6559",
            "Sharpless 29",
            "HP Tau",
            "T Tauri star",
            "Mira",
            "Mira variable",
            "Helix Nebula",
            "Janus (star)",
            "White dwarf",
        ]
    },
    "observational_techniques": {
        "description": "Measurement techniques and distance determination",
        "topics": [
            "Cosmic distance ladder",
            "Parallax",
            "Stellar parallax",
            "Standard candle",
            "Distance modulus",
            "Light curve",
            "Stellar kinematics",
            "Proper motion",
            "Spectroscopy",
            "Photometry",
        ]
    },
    "fundamental_physics": {
        "description": "Physics foundations for astronomy",
        "topics": [
            "Black-body radiation",
            "Wien's displacement law",
            "Stefan-Boltzmann law",
            "Planck's law",
            "Luminosity",
            "Solar luminosity",
            "Inverse-square law",
            "Kepler's laws of planetary motion",
            "Orbital mechanics",
            "Orbital period",
            "Semi-major axis",
            "Electromagnetic spectrum",
        ]
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

class BaseSource:
    """Base class for content sources."""
    
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})
    
    def fetch(self, url: str) -> Optional[str]:
        """Fetch content from URL with error handling."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"  ⚠ Error fetching {url}: {e}")
            return None
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        # Remove citation numbers [1], [2], etc.
        text = re.sub(r'\[\d+\]', '', text)
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        # Remove multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


class WikipediaSource(BaseSource):
    """Handler for Wikipedia content."""
    
    SOURCE_NAME = "Wikipedia"
    BASE_URL = "https://en.wikipedia.org/wiki/"
    
    def get_article(self, topic: str) -> Optional[dict]:
        """Fetch and parse a Wikipedia article."""
        # Convert topic to Wikipedia URL format
        wiki_title = topic.replace(" ", "_")
        url = f"{self.BASE_URL}{quote(wiki_title)}"
        
        html = self.fetch(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Get article title
        title_elem = soup.find('h1', {'id': 'firstHeading'})
        title = title_elem.get_text() if title_elem else topic
        
        # Extract main content
        content_div = soup.find('div', {'id': 'mw-content-text'})
        if not content_div:
            return None
        
        sections = []
        current_section = {"heading": "Overview", "content": []}
        
        for elem in content_div.find_all(['p', 'h2', 'h3', 'h4', 'ul', 'ol', 'table']):
            # Skip navigation/metadata elements
            if elem.find_parent(['table', 'div'], class_=['infobox', 'navbox', 'metadata', 'mw-empty-elt']):
                continue
            
            if elem.name in ['h2', 'h3', 'h4']:
                # Save previous section if it has content
                if current_section["content"]:
                    sections.append(current_section)
                
                # Get heading text without edit links
                heading_text = elem.get_text().replace('[edit]', '').strip()
                
                # Skip certain sections
                if heading_text.lower() in ['see also', 'references', 'external links', 'notes', 'further reading']:
                    current_section = {"heading": None, "content": []}
                    continue
                
                current_section = {"heading": heading_text, "content": []}
            
            elif elem.name == 'p' and current_section["heading"] is not None:
                # Handle MathML in paragraphs
                for math in elem.find_all('math'):
                    try:
                        math_text = self._mathml_to_text(str(math))
                        math.replace_with(math_text)
                    except (etree.XMLSyntaxError, ValueError, TypeError):
                        math.replace_with('[mathematical expression]')
                
                text = elem.get_text().strip()
                if text:
                    current_section["content"].append(self.clean_text(text))
            
            elif elem.name in ['ul', 'ol'] and current_section["heading"] is not None:
                items = []
                for li in elem.find_all('li', recursive=False):
                    item_text = li.get_text().strip()
                    if item_text:
                        items.append(f"  • {self.clean_text(item_text)}")
                if items:
                    current_section["content"].append("\n".join(items))
        
        # Add final section
        if current_section["content"] and current_section["heading"]:
            sections.append(current_section)
        
        return {
            "title": title,
            "source": self.SOURCE_NAME,
            "url": url,
            "sections": sections,
            "fetched_at": datetime.now().isoformat()
        }
    
    def _mathml_to_text(self, mathml: str) -> str:
        """Convert MathML to readable text."""
        parser = etree.XMLParser(recover=True)
        tree = etree.fromstring(mathml.encode(), parser)
        return ''.join(tree.itertext())


class NASASource(BaseSource):
    """Handler for NASA educational content."""
    
    SOURCE_NAME = "NASA"
    SEARCH_URL = "https://www.nasa.gov/search-results/"
    
    # Direct URLs for important NASA pages
    DIRECT_URLS = {
        "exoplanet": "https://exoplanets.nasa.gov/what-is-an-exoplanet/overview/",
        "stellar evolution": "https://science.nasa.gov/astrophysics/focus-areas/how-do-stars-form-and-evolve/",
        "star formation": "https://science.nasa.gov/astrophysics/focus-areas/how-do-stars-form-and-evolve/",
        "black hole": "https://science.nasa.gov/astrophysics/focus-areas/black-holes/",
        "hubble": "https://science.nasa.gov/mission/hubble/",
        "james webb": "https://science.nasa.gov/mission/webb/",
    }
    
    def get_article(self, topic: str) -> Optional[dict]:
        """Fetch NASA content for a topic."""
        topic_lower = topic.lower()
        
        # Check for direct URL match
        url = None
        for key, direct_url in self.DIRECT_URLS.items():
            if key in topic_lower:
                url = direct_url
                break
        
        if not url:
            # Try science.nasa.gov search
            search_topic = topic.replace(" ", "-").lower()
            url = f"https://science.nasa.gov/universe/{search_topic}/"
        
        html = self.fetch(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract main content
        content = []
        
        # Try various content containers used by NASA sites
        for selector in ['article', 'main', '.content', '.wysiwyg-content', '#main-content']:
            container = soup.select_one(selector)
            if container:
                for p in container.find_all('p'):
                    text = p.get_text().strip()
                    if text and len(text) > 50:  # Filter out short snippets
                        content.append(self.clean_text(text))
                break
        
        if not content:
            return None
        
        return {
            "title": f"{topic} (NASA)",
            "source": self.SOURCE_NAME,
            "url": url,
            "sections": [{"heading": "NASA Overview", "content": content}],
            "fetched_at": datetime.now().isoformat()
        }


class ESASource(BaseSource):
    """Handler for European Space Agency content."""
    
    SOURCE_NAME = "ESA"
    BASE_URL = "https://www.esa.int/Science_Exploration/Space_Science/"
    
    def get_article(self, topic: str) -> Optional[dict]:
        """Fetch ESA content for a topic."""
        # ESA has good pages on specific topics
        search_url = f"https://www.esa.int/esearch?q={quote(topic)}"
        
        html = self.fetch(search_url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find first relevant result
        results = soup.select('.search-result a, .result-title a')
        if not results:
            return None
        
        article_url = results[0].get('href')
        if article_url and not article_url.startswith('http'):
            article_url = urljoin("https://www.esa.int", article_url)
        
        if not article_url:
            return None
        
        article_html = self.fetch(article_url)
        if not article_html:
            return None
        
        article_soup = BeautifulSoup(article_html, 'html.parser')
        
        content = []
        for p in article_soup.find_all('p'):
            text = p.get_text().strip()
            if text and len(text) > 50:
                content.append(self.clean_text(text))
        
        if not content:
            return None
        
        title = article_soup.find('h1')
        title_text = title.get_text().strip() if title else topic
        
        return {
            "title": title_text,
            "source": self.SOURCE_NAME,
            "url": article_url,
            "sections": [{"heading": "ESA Article", "content": content[:10]}],  # Limit sections
            "fetched_at": datetime.now().isoformat()
        }


class EducationalSource(BaseSource):
    """Handler for educational astronomy websites."""
    
    SOURCE_NAME = "Educational"
    
    # Curated educational URLs
    EDUCATIONAL_SITES = {
        "stellar evolution": [
            "https://astronomy.swin.edu.au/cosmos/s/Stellar+Evolution",
        ],
        "hertzsprung-russell": [
            "https://astronomy.swin.edu.au/cosmos/h/Hertzsprung-Russell+Diagram",
        ],
        "exoplanet": [
            "https://exoplanets.nasa.gov/what-is-an-exoplanet/overview/",
        ],
    }
    
    def get_article(self, topic: str) -> Optional[dict]:
        """Fetch educational content for a topic."""
        topic_lower = topic.lower()
        
        # Find matching educational URLs
        urls = []
        for key, site_urls in self.EDUCATIONAL_SITES.items():
            if key in topic_lower:
                urls.extend(site_urls)
        
        if not urls:
            return None
        
        all_content = []
        source_url = None
        
        for url in urls[:2]:  # Limit to 2 sources
            html = self.fetch(url)
            if not html:
                continue
            
            source_url = url
            soup = BeautifulSoup(html, 'html.parser')
            
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if text and len(text) > 50:
                    all_content.append(self.clean_text(text))
        
        if not all_content:
            return None
        
        return {
            "title": f"{topic} (Educational)",
            "source": self.SOURCE_NAME,
            "url": source_url,
            "sections": [{"heading": "Educational Overview", "content": all_content[:15]}],
            "fetched_at": datetime.now().isoformat()
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SCRAPER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class AstronomyScraper:
    """Main scraper class coordinating all sources."""
    
    def __init__(self, config: Optional[ScraperConfig] = None):
        self.config = config or ScraperConfig()
        self.sources = {
            "wikipedia": WikipediaSource(self.config),
            "nasa": NASASource(self.config),
            "esa": ESASource(self.config),
            "educational": EducationalSource(self.config),
        }
        self.cache = {}
        self._setup_directories()
    
    def _setup_directories(self):
        """Create output directory structure."""
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.cache_dir).mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, topic: str, source: str) -> Path:
        """Get cache file path for a topic/source combination."""
        key = hashlib.md5(f"{topic}_{source}".encode()).hexdigest()
        return Path(self.config.cache_dir) / f"{key}.json"
    
    def _load_from_cache(self, topic: str, source: str) -> Optional[dict]:
        """Load cached content if available."""
        cache_path = self._get_cache_path(topic, source)
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError, OSError):
                pass
        return None
    
    def _save_to_cache(self, topic: str, source: str, data: dict):
        """Save content to cache."""
        cache_path = self._get_cache_path(topic, source)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except (IOError, OSError):
            pass
    
    def fetch_topic(self, topic: str, use_cache: bool = True) -> dict:
        """Fetch content for a topic from all configured sources."""
        results = {"topic": topic, "sources": {}}
        
        for source_name in self.config.include_sources:
            if source_name not in self.sources:
                continue
            
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
            except (requests.RequestException, ValueError, AttributeError) as e:
                print(f"  ⚠ Error fetching {topic} from {source_name}: {e}")
            
            # Rate limiting
            time.sleep(self.config.request_delay)
        
        return results
    
    def generate_text_file(self, topic_data: dict, category: str) -> str:
        """Generate a formatted text file from topic data."""
        lines = []
        topic = topic_data["topic"]
        
        # Header
        lines.append("=" * 80)
        lines.append(f"  {topic.upper()}")
        lines.append("=" * 80)
        lines.append(f"\nCategory: {category}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("-" * 80)
        
        # Content from each source
        for source_name, source_data in topic_data["sources"].items():
            lines.append(f"\n{'─' * 40}")
            lines.append(f"  Source: {source_data.get('source', source_name).upper()}")
            lines.append(f"  URL: {source_data.get('url', 'N/A')}")
            lines.append(f"{'─' * 40}\n")
            
            for section in source_data.get("sections", []):
                heading = section.get("heading", "")
                if heading:
                    lines.append(f"\n## {heading}\n")
                
                for paragraph in section.get("content", []):
                    lines.append(paragraph)
                    lines.append("")
        
        # Footer
        lines.append("\n" + "=" * 80)
        lines.append("  END OF DOCUMENT")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def save_topic(self, topic_data: dict, category: str):
        """Save topic content to a text file in the appropriate category folder."""
        # Create category folder
        category_dir = Path(self.config.output_dir) / category.replace(" ", "_")
        category_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        topic = topic_data["topic"]
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', topic)
        safe_filename = safe_filename.replace(" ", "_")
        filepath = category_dir / f"{safe_filename}.txt"
        
        # Generate and save content
        content = self.generate_text_file(topic_data, category)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return filepath
    
    def scrape_category(self, category: str, topics: list) -> list:
        """Scrape all topics in a category."""
        print(f"\n{'═' * 60}")
        print(f"  Processing Category: {category.upper()}")
        print(f"{'═' * 60}")
        
        saved_files = []
        
        for i, topic in enumerate(topics, 1):
            print(f"\n  [{i}/{len(topics)}] {topic}")
            print(f"  {'─' * 40}")
            
            topic_data = self.fetch_topic(topic)
            
            if topic_data["sources"]:
                filepath = self.save_topic(topic_data, category)
                saved_files.append(filepath)
                sources_found = list(topic_data["sources"].keys())
                print(f"  ✓ Saved: {filepath.name}")
                print(f"    Sources: {', '.join(sources_found)}")
            else:
                print("  ✗ No content found")
        
        return saved_files
    
    def scrape_all(self, categories: dict = None) -> dict:
        """Scrape all categories and topics."""
        if categories is None:
            categories = DEFAULT_CATEGORIES
        
        results = {
            "started_at": datetime.now().isoformat(),
            "categories": {},
            "total_files": 0,
        }
        
        print("\n" + "╔" + "═" * 58 + "╗")
        print("║" + " SCIENCE OLYMPIAD ASTRONOMY 2026 - RESEARCH SCRAPER ".center(58) + "║")
        print("╚" + "═" * 58 + "╝")
        
        for category, data in categories.items():
            if isinstance(data, dict):
                topics = data.get("topics", [])
                description = data.get("description", "")
            else:
                topics = data
                description = ""
            
            saved_files = self.scrape_category(category, topics)
            results["categories"][category] = {
                "description": description,
                "topics_count": len(topics),
                "files_saved": len(saved_files),
                "files": [str(f) for f in saved_files]
            }
            results["total_files"] += len(saved_files)
        
        results["completed_at"] = datetime.now().isoformat()
        
        # Save index
        self._save_index(results, categories)
        
        return results
    
    def _save_index(self, results: dict, categories: dict):
        """Save an index file summarizing all scraped content."""
        index_path = Path(self.config.output_dir) / "INDEX.txt"
        
        lines = []
        lines.append("=" * 80)
        lines.append("  SCIENCE OLYMPIAD ASTRONOMY 2026 - STUDY MATERIALS INDEX")
        lines.append("=" * 80)
        lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Total Files: {results['total_files']}")
        lines.append("\n" + "-" * 80)
        
        for category, data in categories.items():
            if isinstance(data, dict):
                description = data.get("description", "")
                topics = data.get("topics", [])
            else:
                description = ""
                topics = data
            
            lines.append(f"\n## {category.upper().replace('_', ' ')}")
            if description:
                lines.append(f"   {description}")
            lines.append(f"   Topics: {len(topics)}")
            lines.append("")
            
            for topic in topics:
                lines.append(f"   • {topic}")
        
        lines.append("\n" + "=" * 80)
        
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        # Also save JSON index for programmatic access
        json_path = Path(self.config.output_dir) / "index.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# USER INPUT INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════

def get_user_input() -> dict:
    """Interactive prompt for user to specify topics and starting points."""
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " SCIENCE OLYMPIAD ASTRONOMY 2026 - SETUP ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    
    categories = {}
    
    print("\n" + "─" * 60)
    print("  CONFIGURATION OPTIONS")
    print("─" * 60)
    print("\n  [1] Use default 2026 Science Olympiad topics")
    print("  [2] Add custom topics to defaults")
    print("  [3] Enter completely custom topics")
    print("  [4] Load from config file (topics.json)")
    
    choice = input("\n  Enter choice (1-4): ").strip()
    
    if choice == "1":
        return DEFAULT_CATEGORIES
    
    elif choice == "2":
        categories = DEFAULT_CATEGORIES.copy()
        print("\n  Enter additional topics (one per line, empty line to finish):")
        print("  Format: category_name: topic1, topic2, topic3")
        print("  Example: exoplanets: Proxima Centauri b, TRAPPIST-1e\n")
        
        while True:
            line = input("  > ").strip()
            if not line:
                break
            
            if ":" in line:
                cat_name, topics_str = line.split(":", 1)
                cat_name = cat_name.strip().lower().replace(" ", "_")
                new_topics = [t.strip() for t in topics_str.split(",") if t.strip()]
                
                if cat_name in categories:
                    if isinstance(categories[cat_name], dict):
                        categories[cat_name]["topics"].extend(new_topics)
                    else:
                        categories[cat_name].extend(new_topics)
                else:
                    categories[cat_name] = {
                        "description": "Custom category",
                        "topics": new_topics
                    }
                print(f"    Added {len(new_topics)} topics to {cat_name}")
        
        return categories
    
    elif choice == "3":
        print("\n  Enter your categories and topics:")
        print("  Format: category_name: topic1, topic2, topic3")
        print("  Empty line when done.\n")
        
        while True:
            line = input("  > ").strip()
            if not line:
                break
            
            if ":" in line:
                cat_name, topics_str = line.split(":", 1)
                cat_name = cat_name.strip().lower().replace(" ", "_")
                topics = [t.strip() for t in topics_str.split(",") if t.strip()]
                
                categories[cat_name] = {
                    "description": "Custom category",
                    "topics": topics
                }
                print(f"    Created {cat_name} with {len(topics)} topics")
        
        if not categories:
            print("  No topics entered, using defaults.")
            return DEFAULT_CATEGORIES
        
        return categories
    
    elif choice == "4":
        config_path = input("\n  Enter config file path (default: topics.json): ").strip()
        if not config_path:
            config_path = "topics.json"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                categories = json.load(f)
            print(f"  Loaded {len(categories)} categories from {config_path}")
            return categories
        except FileNotFoundError:
            print(f"  File not found: {config_path}")
            print("  Using default topics.")
            return DEFAULT_CATEGORIES
        except json.JSONDecodeError:
            print(f"  Invalid JSON in {config_path}")
            print("  Using default topics.")
            return DEFAULT_CATEGORIES
    
    else:
        print("  Invalid choice, using defaults.")
        return DEFAULT_CATEGORIES


def configure_sources() -> list:
    """Let user select which sources to use."""
    print("\n" + "─" * 60)
    print("  SELECT SOURCES")
    print("─" * 60)
    print("\n  Available sources:")
    print("  [1] Wikipedia (comprehensive articles)")
    print("  [2] NASA (official space agency content)")
    print("  [3] ESA (European Space Agency)")
    print("  [4] Educational sites (Swinburne, etc.)")
    print("\n  Enter numbers separated by commas (default: all)")
    print("  Example: 1,2 for Wikipedia and NASA only")
    
    choice = input("\n  > ").strip()
    
    source_map = {
        "1": "wikipedia",
        "2": "nasa", 
        "3": "esa",
        "4": "educational"
    }
    
    if not choice:
        return list(source_map.values())
    
    selected = []
    for num in choice.split(","):
        num = num.strip()
        if num in source_map:
            selected.append(source_map[num])
    
    return selected if selected else list(source_map.values())


def configure_output() -> str:
    """Let user specify output directory."""
    print("\n" + "─" * 60)
    print("  OUTPUT DIRECTORY")
    print("─" * 60)
    
    output_dir = input("\n  Enter output directory (default: astronomy_notes): ").strip()
    return output_dir if output_dir else "astronomy_notes"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point with interactive configuration."""
    # Get user configuration
    categories = get_user_input()
    sources = configure_sources()
    output_dir = configure_output()
    
    # Create config
    config = ScraperConfig(
        output_dir=output_dir,
        include_sources=sources
    )
    
    # Summary
    total_topics = sum(
        len(data.get("topics", data) if isinstance(data, dict) else data)
        for data in categories.values()
    )
    
    print("\n" + "═" * 60)
    print("  CONFIGURATION SUMMARY")
    print("═" * 60)
    print(f"  Categories: {len(categories)}")
    print(f"  Total Topics: {total_topics}")
    print(f"  Sources: {', '.join(sources)}")
    print(f"  Output: {output_dir}/")
    print("═" * 60)
    
    confirm = input("\n  Start scraping? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\n  Cancelled.")
        return
    
    # Run scraper
    scraper = AstronomyScraper(config)
    results = scraper.scrape_all(categories)
    
    # Final summary
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " SCRAPING COMPLETE ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    print(f"\n  Total files generated: {results['total_files']}")
    print(f"  Output directory: {output_dir}/")
    print(f"  Index file: {output_dir}/INDEX.txt")
    print(f"  JSON index: {output_dir}/index.json")
    
    for category, data in results["categories"].items():
        print(f"\n  {category}: {data['files_saved']}/{data['topics_count']} topics")


def quick_scrape(topics: list = None, category: str = "custom", sources: list = None, output_dir: str = "astronomy_notes"):
    """
    Programmatic interface for quick scraping without interactive prompts.
    
    Args:
        topics: List of topic strings to scrape
        category: Category name for organization
        sources: List of sources to use (default: all)
        output_dir: Output directory path
    
    Returns:
        dict: Results summary
    
    Example:
        >>> quick_scrape(
        ...     topics=["Stellar evolution", "Black hole", "Neutron star"],
        ...     category="stellar_physics",
        ...     sources=["wikipedia", "nasa"],
        ...     output_dir="my_notes"
        ... )
    """
    if topics is None:
        topics = ["Stellar evolution"]
    
    if sources is None:
        sources = ["wikipedia", "nasa", "esa", "educational"]
    
    config = ScraperConfig(
        output_dir=output_dir,
        include_sources=sources
    )
    
    categories = {
        category: {
            "description": "Quick scrape",
            "topics": topics
        }
    }
    
    scraper = AstronomyScraper(config)
    return scraper.scrape_all(categories)


if __name__ == "__main__":
    main()
