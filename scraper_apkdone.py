import requests
from bs4 import BeautifulSoup
import time
import re
import os
import cloudscraper
from difflib import SequenceMatcher

BASE_URL = "https://apkdone.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

scraper = cloudscraper.create_scraper()

_sitemap_cache = None
_sitemap_cache_time = 0
CACHE_DURATION = 3600

def fetch_page(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = scraper.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise Exception(f"Failed to fetch {url}: {e}")

def load_sitemap():
    global _sitemap_cache, _sitemap_cache_time
    
    if _sitemap_cache and (time.time() - _sitemap_cache_time) < CACHE_DURATION:
        return _sitemap_cache
    
    all_urls = []
    
    try:
        sitemap_index = fetch_page(f"{BASE_URL}/sitemap.xml")
        soup = BeautifulSoup(sitemap_index, "xml")
        sitemap_urls = [loc.text for loc in soup.find_all("loc") if "post-sitemap" in loc.text]
        
        for sitemap_url in sitemap_urls[:15]:
            try:
                sitemap_content = fetch_page(sitemap_url)
                sitemap_soup = BeautifulSoup(sitemap_content, "xml")
                for loc in sitemap_soup.find_all("loc"):
                    url = loc.text
                    if re.match(r'https://apkdone\.com/[a-z0-9-]+/?$', url):
                        if '/app/' not in url and '/game/' not in url and '/author/' not in url:
                            all_urls.append(url)
                time.sleep(0.5)
            except Exception as e:
                print(f"Error fetching sitemap {sitemap_url}: {e}")
                continue
    except Exception as e:
        print(f"Error loading sitemap index: {e}")
    
    _sitemap_cache = list(set(all_urls))
    _sitemap_cache_time = time.time()
    return _sitemap_cache

def url_to_name(url):
    slug = url.rstrip('/').split('/')[-1]
    name = slug.replace('-', ' ').replace('mod apk', '').replace('apk', '').strip()
    return name.title()

def search_website(query):
    query_lower = query.lower().strip()
    
    try:
        all_urls = load_sitemap()
    except:
        all_urls = []
    
    results = []
    
    for url in all_urls:
        slug = url.rstrip('/').split('/')[-1]
        name = url_to_name(url)
        
        score = 0
        if query_lower in slug:
            score = 100
        elif query_lower in name.lower():
            score = 90
        else:
            ratio = SequenceMatcher(None, query_lower, slug).ratio()
            if ratio > 0.5:
                score = int(ratio * 80)
        
        if score > 0:
            results.append({
                "name": name,
                "url": url,
                "score": score,
                "version": "",
                "size": "",
                "category": "",
                "mod_features": "",
                "image": ""
            })
    
    results.sort(key=lambda x: x["score"], reverse=True)
    
    if not results:
        guessed_slug = query_lower.replace(' ', '-')
        guessed_url = f"{BASE_URL}/{guessed_slug}/"
        try:
            resp = scraper.head(guessed_url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                results.append({
                    "name": query.title(),
                    "url": guessed_url,
                    "score": 50,
                    "version": "",
                    "size": "",
                    "category": "",
                    "mod_features": "",
                    "image": ""
                })
        except:
            pass
    
    return results[:20]

def get_app_details(app_url):
    html = fetch_page(app_url)
    soup = BeautifulSoup(html, "lxml")
    
    download_page_url = app_url.rstrip("/") + "/download/"
    details = {
        "name": "",
        "version": "",
        "size": "",
        "category": "",
        "publisher": "",
        "requirements": "",
        "last_updated": "",
        "rating": "",
        "description": "",
        "icon": "",
        "download_page": download_page_url
    }
    
    h1 = soup.find("h1")
    if h1:
        title_text = h1.get_text(strip=True)
        details["name"] = title_text
        version_match = re.search(r'(\d+\.\d+[\d.]*)', title_text)
        if version_match:
            details["version"] = version_match.group(1)
    
    for elem in soup.find_all(["div", "span", "td", "tr", "p"]):
        text = elem.get_text(strip=True)
        
        if "Version" in text and not details["version"]:
            match = re.search(r'(\d+\.\d+[\d.]*)', text)
            if match:
                details["version"] = match.group(1)
        elif "Size" in text:
            match = re.search(r'(\d+(?:\.\d+)?)\s*(MB|GB|KB)', text, re.IGNORECASE)
            if match:
                details["size"] = f"{match.group(1)} {match.group(2).upper()}"
        elif "Requires" in text or "Android" in text:
            match = re.search(r'Android\s*[\d.]+', text)
            if match:
                details["requirements"] = match.group()
    
    icon = soup.find("img", class_=re.compile(r'poster|icon|logo', re.I))
    if icon:
        details["icon"] = icon.get("src", "") or icon.get("data-src", "")
    
    category_link = soup.find("a", href=re.compile(r'/app/[a-z-]+/|/game/[a-z-]+/'))
    if category_link:
        details["category"] = category_link.get_text(strip=True)
    
    developer_link = soup.find("a", href=re.compile(r'/developer/'))
    if developer_link:
        details["publisher"] = developer_link.get_text(strip=True)
    
    if not details["size"] or not details["version"] or not details["requirements"]:
        try:
            download_html = fetch_page(download_page_url)
            download_soup = BeautifulSoup(download_html, "lxml")
            
            for elem in download_soup.find_all(["div", "span", "td", "tr", "p", "li"]):
                text = elem.get_text(strip=True)
                
                if not details["version"] and "Version" in text:
                    match = re.search(r'(\d+\.\d+[\d.]*)', text)
                    if match:
                        details["version"] = match.group(1)
                
                if not details["size"] and "Size" in text:
                    match = re.search(r'(\d+(?:\.\d+)?)\s*(MB|GB|KB)', text, re.IGNORECASE)
                    if match:
                        details["size"] = f"{match.group(1)} {match.group(2).upper()}"
                
                if not details["requirements"] and ("Requires" in text or "Android" in text):
                    match = re.search(r'Android\s*[\d.]+', text)
                    if match:
                        details["requirements"] = match.group()
        except Exception as e:
            print(f"Could not fetch download page for details: {e}")
    
    return details

def get_download_links(app_url):
    download_url = app_url.rstrip("/") + "/download/"
    
    try:
        html = fetch_page(download_url)
    except:
        html = fetch_page(app_url)
    
    soup = BeautifulSoup(html, "lxml")
    hole_links = []
    file_links = []
    other_links = []
    
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text(strip=True)
        
        if "hole.apkdone.io" in href:
            size_match = re.search(r'(\d+(?:\.\d+)?)\s*(MB|GB|KB)', text, re.IGNORECASE)
            size = f"{size_match.group(1)} {size_match.group(2).upper()}" if size_match else ""
            
            hole_links.append({
                "name": text[:50] if text else "Download APK",
                "url": href,
                "size": size,
                "direct": True
            })
        elif "file.apkdone.io" in href:
            size_match = re.search(r'(\d+(?:\.\d+)?)\s*(MB|GB|KB)', text, re.IGNORECASE)
            size = f"{size_match.group(1)} {size_match.group(2).upper()}" if size_match else ""
            
            file_links.append({
                "name": text[:50] if text else "Download APK",
                "url": href,
                "size": size,
                "direct": True
            })
        elif href.endswith(('.apk', '.xapk', '.zip')):
            other_links.append({
                "name": text[:50] if text else "Download",
                "url": href,
                "size": "",
                "direct": True
            })
    
    downloads = hole_links + file_links + other_links
    
    if not downloads:
        for link in soup.find_all("a", href=True, class_=re.compile(r'download|btn', re.I)):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if href and "apkdone" in href and "download" in href.lower():
                downloads.append({
                    "name": text[:50] if text else "Download",
                    "url": href,
                    "size": "",
                    "direct": False
                })
    
    return downloads

def download_file(url, output_dir="downloads"):
    os.makedirs(output_dir, exist_ok=True)
    
    response = scraper.get(url, headers=HEADERS, stream=True, timeout=120, allow_redirects=True)
    response.raise_for_status()
    
    content_disp = response.headers.get("Content-Disposition", "")
    if "filename=" in content_disp:
        filename = re.search(r'filename="?([^";\n]+)"?', content_disp)
        filename = filename.group(1) if filename else "download.apk"
    else:
        final_url = response.url
        filename = final_url.split("/")[-1].split("?")[0] or "download.apk"
        if not filename.endswith((".apk", ".xapk", ".zip")):
            filename += ".apk"
    
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filepath = os.path.join(output_dir, filename)
    
    total_size = int(response.headers.get("content-length", 0))
    downloaded = 0
    
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\rDownloading: {percent:.1f}%", end="", flush=True)
    
    print()
    return filepath

def scrape_games(page=1, limit=20):
    url = f"{BASE_URL}/game/"
    if page > 1:
        url = f"{BASE_URL}/game/page/{page}/"
    
    html = fetch_page(url)
    soup = BeautifulSoup(html, "lxml")
    
    games = []
    seen_urls = set()
    
    for link in soup.find_all("a", href=re.compile(r'apkdone\.com/[a-z0-9-]+/?$')):
        href = link.get("href", "")
        if href in seen_urls or '/game/' in href or '/app/' in href:
            continue
        seen_urls.add(href)
        
        name = link.get("title", "") or link.get_text(strip=True) or url_to_name(href)
        if name and len(name) > 2:
            games.append({
                "name": name,
                "url": href,
                "version": "",
                "size": "",
                "category": "Game",
                "mod_features": "",
                "image": ""
            })
    
    return games[:limit]

def scrape_apps(page=1, limit=20):
    url = f"{BASE_URL}/app/"
    if page > 1:
        url = f"{BASE_URL}/app/page/{page}/"
    
    html = fetch_page(url)
    soup = BeautifulSoup(html, "lxml")
    
    apps = []
    seen_urls = set()
    
    for link in soup.find_all("a", href=re.compile(r'apkdone\.com/[a-z0-9-]+/?$')):
        href = link.get("href", "")
        if href in seen_urls or '/game/' in href or '/app/' in href:
            continue
        seen_urls.add(href)
        
        name = link.get("title", "") or link.get_text(strip=True) or url_to_name(href)
        if name and len(name) > 2:
            apps.append({
                "name": name,
                "url": href,
                "version": "",
                "size": "",
                "category": "App",
                "mod_features": "",
                "image": ""
            })
    
    return apps[:limit]

def scrape_homepage():
    html = fetch_page(BASE_URL)
    soup = BeautifulSoup(html, "lxml")
    
    results = {"all_items": []}
    seen_urls = set()
    
    for link in soup.find_all("a", href=re.compile(r'apkdone\.com/[a-z0-9-]+/?$')):
        href = link.get("href", "")
        if href in seen_urls or '/game/' in href or '/app/' in href or '/author/' in href:
            continue
        seen_urls.add(href)
        
        name = link.get("title", "") or link.get_text(strip=True) or url_to_name(href)
        if name and len(name) > 2:
            results["all_items"].append({
                "name": name,
                "url": href,
                "version": "",
                "size": "",
                "category": "",
                "mod_features": "",
                "image": ""
            })
    
    return results

def search_items(query, category="all"):
    return search_website(query)
