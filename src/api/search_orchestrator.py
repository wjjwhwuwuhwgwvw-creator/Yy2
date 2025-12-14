#!/usr/bin/env python3
"""
Search Orchestrator - Dual-source search system
Combines apkdone (primary) with Google Play Scraper (fallback)
"""
import os
import sys
import re
import json
import time
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

CACHE_FILE = Path(__file__).parent.parent.parent / "data" / "package_cache.json"
CACHE_TTL = 86400  # 24 hours

_package_cache = {}
_cache_loaded = False

def load_cache():
    global _package_cache, _cache_loaded
    if _cache_loaded:
        return
    try:
        CACHE_FILE.parent.mkdir(exist_ok=True)
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r') as f:
                _package_cache = json.load(f)
    except:
        _package_cache = {}
    _cache_loaded = True

def save_cache():
    try:
        CACHE_FILE.parent.mkdir(exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(_package_cache, f, indent=2)
    except Exception as e:
        print(f"Cache save failed: {e}")

def get_cached_package(slug: str) -> Optional[Dict]:
    load_cache()
    entry = _package_cache.get(slug.lower())
    if entry and (time.time() - entry.get('timestamp', 0)) < CACHE_TTL:
        return entry
    return None

def cache_package(slug: str, package_name: str, title: str, icon: str = "", source: str = "google"):
    load_cache()
    _package_cache[slug.lower()] = {
        'package': package_name,
        'title': title,
        'icon': icon,
        'source': source,
        'timestamp': time.time()
    }
    save_cache()

def is_package_name(name: str) -> bool:
    """Check if string looks like a package name (com.xxx.xxx)"""
    return bool(re.match(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$', name.lower()))

def search_google_play(query: str, num: int = 10) -> List[Dict]:
    """Search Google Play Store using google-play-scraper npm package"""
    try:
        script = f"""
        const gplay = require('google-play-scraper').default || require('google-play-scraper');
        gplay.search({{
            term: {json.dumps(query)},
            num: {num},
            lang: 'en',
            country: 'us'
        }}).then(results => {{
            console.log(JSON.stringify(results));
        }}).catch(err => {{
            console.error(JSON.stringify({{error: err.message}}));
        }});
        """
        result = subprocess.run(
            ['node', '-e', script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(__file__).parent.parent.parent)
        )
        
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if isinstance(data, list):
                apps = []
                for app in data[:num]:
                    apps.append({
                        'name': app.get('title', ''),
                        'package': app.get('appId', ''),
                        'appId': app.get('appId', ''),
                        'version': '',
                        'size': app.get('size', ''),
                        'icon': app.get('icon', ''),
                        'image': app.get('icon', ''),
                        'developer': app.get('developer', ''),
                        'score': app.get('score', 0),
                        'url': f"https://play.google.com/store/apps/details?id={app.get('appId', '')}",
                        'source': 'google',
                        'category': app.get('genre', '')
                    })
                return apps
    except subprocess.TimeoutExpired:
        print("Google Play search timeout")
    except Exception as e:
        print(f"Google Play search error: {e}")
    return []

def get_google_play_app(package_name: str) -> Optional[Dict]:
    """Get app details from Google Play Store"""
    try:
        script = f"""
        const gplay = require('google-play-scraper').default || require('google-play-scraper');
        gplay.app({{
            appId: {json.dumps(package_name)},
            lang: 'en',
            country: 'us'
        }}).then(app => {{
            console.log(JSON.stringify(app));
        }}).catch(err => {{
            console.error(JSON.stringify({{error: err.message}}));
        }});
        """
        result = subprocess.run(
            ['node', '-e', script],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(Path(__file__).parent.parent.parent)
        )
        
        if result.returncode == 0 and result.stdout.strip():
            app = json.loads(result.stdout.strip())
            if 'error' not in app:
                return {
                    'name': app.get('title', ''),
                    'package': app.get('appId', ''),
                    'appId': app.get('appId', ''),
                    'version': app.get('version', ''),
                    'size': app.get('size', ''),
                    'icon': app.get('icon', ''),
                    'developer': app.get('developer', ''),
                    'description': app.get('summary', ''),
                    'score': app.get('score', 0),
                    'url': app.get('url', ''),
                    'source': 'google',
                    'category': app.get('genre', '')
                }
    except Exception as e:
        print(f"Google Play app error: {e}")
    return None

def combined_search(query: str, num: int = 10) -> Dict[str, Any]:
    """
    Combined search: searches both apkdone and Google Play
    Interleaves results to show both sources, prioritizing exact matches
    """
    from scraper import search_website
    
    results = {
        'apkdone': [],
        'google': [],
        'combined': []
    }
    
    query_lower = query.lower().strip()
    
    # Get results from apkdone
    try:
        apkdone_results = search_website(query)
        for app in apkdone_results[:num]:
            app['source'] = 'apkdone'
            results['apkdone'].append(app)
    except Exception as e:
        print(f"apkdone search failed: {e}")
    
    # Always search Google Play for better coverage
    try:
        google_results = search_google_play(query, num)
        for app in google_results:
            app['source'] = 'google'
            results['google'].append(app)
            
            slug = app.get('name', '').lower().replace(' ', '-')
            slug = re.sub(r'[^a-z0-9-]', '', slug)
            cache_package(slug, app.get('package', ''), app.get('name', ''), app.get('icon', ''))
    except Exception as e:
        print(f"Google Play search failed: {e}")
    
    # Combine results prioritizing apkdone (more reliable downloads) over Google
    seen_names = set()
    seen_packages = set()
    
    # Helper to check if app name matches query
    def is_relevant(app):
        name = app.get('name', '').lower()
        return query_lower in name or any(word in name for word in query_lower.split())
    
    # Helper to normalize name for comparison
    def normalize_name(name):
        # Remove common suffixes for comparison
        name = name.lower()
        for suffix in [' - aio tunnel vpn', ' vpn', ' pro', ' plus', ' vip', ' mod', ' premium']:
            name = name.replace(suffix, '')
        return name.strip()
    
    # 1. Add relevant apkdone results FIRST (priority for downloads)
    for app in results['apkdone']:
        name_key = app.get('name', '').lower()
        norm_name = normalize_name(name_key)
        if name_key not in seen_names and is_relevant(app):
            results['combined'].append(app)
            seen_names.add(name_key)
            seen_names.add(norm_name)  # Also mark normalized name as seen
    
    # 2. Add relevant Google results (skip if similar app already from apkdone)
    for app in results['google']:
        name_key = app.get('name', '').lower()
        norm_name = normalize_name(name_key)
        pkg = app.get('package', '')
        # Skip if name or normalized name already exists
        if name_key in seen_names or norm_name in seen_names or pkg in seen_packages:
            continue
        if is_relevant(app):
            results['combined'].append(app)
            seen_names.add(name_key)
            seen_packages.add(pkg)
    
    # 3. Add remaining apkdone results
    for app in results['apkdone']:
        name_key = app.get('name', '').lower()
        if name_key not in seen_names and len(results['combined']) < num:
            results['combined'].append(app)
            seen_names.add(name_key)
    
    # 4. Add remaining Google results
    for app in results['google']:
        name_key = app.get('name', '').lower()
        pkg = app.get('package', '')
        if name_key not in seen_names and pkg not in seen_packages and len(results['combined']) < num:
            results['combined'].append(app)
            seen_names.add(name_key)
            seen_packages.add(pkg)
    
    results['combined'] = results['combined'][:num]
    return results

def get_package_for_slug(slug: str) -> Optional[str]:
    """Get package name for a slug, checking cache and Google Play"""
    cached = get_cached_package(slug)
    if cached:
        return cached.get('package')
    
    search_term = slug.replace('-', ' ')
    google_results = search_google_play(search_term, 5)
    
    for app in google_results:
        app_name = app.get('name', '').lower().replace(' ', '-')
        app_name = re.sub(r'[^a-z0-9-]', '', app_name)
        if slug.lower() in app_name or app_name in slug.lower():
            cache_package(slug, app.get('package', ''), app.get('name', ''), app.get('icon', ''))
            return app.get('package')
    
    if google_results:
        app = google_results[0]
        cache_package(slug, app.get('package', ''), app.get('name', ''), app.get('icon', ''))
        return app.get('package')
    
    return None
