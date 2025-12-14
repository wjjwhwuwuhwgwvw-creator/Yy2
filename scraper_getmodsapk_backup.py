import requests
from bs4 import BeautifulSoup
import time
import re
import os
import cloudscraper

BASE_URL = "https://getmodsapk.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

scraper = cloudscraper.create_scraper()

def fetch_page(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = scraper.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise Exception(f"Failed to fetch {url}: {e}")

def parse_app_card(card):
    try:
        url = card.get("href", "")
        if url and not url.startswith("http"):
            url = BASE_URL + url

        img_elem = card.find("img")
        image = ""
        if img_elem:
            image = img_elem.get("src", "") or img_elem.get("data-src", "")

        text_content = card.get_text(" ", strip=True)
        
        name = ""
        strong = card.find("strong")
        if strong:
            name = strong.get_text(strip=True)
        elif img_elem and img_elem.get("alt"):
            name = img_elem.get("alt", "")
        
        version = ""
        version_match = re.search(r'v[\d.]+[a-zA-Z0-9]*', text_content)
        if version_match:
            version = version_match.group()
        
        size = ""
        size_match = re.search(r'Size:\s*(\d+(?:\.\d+)?)\s*(MB|GB|KB)', text_content, re.IGNORECASE)
        if size_match:
            size = f"{size_match.group(1)} {size_match.group(2).upper()}"
        else:
            size_match = re.search(r'(\d+(?:\.\d+)?)\s*(MB|GB|KB)', text_content, re.IGNORECASE)
            if size_match:
                size = f"{size_match.group(1)} {size_match.group(2).upper()}"
        
        category = ""
        categories = ["Action", "Strategy", "Role-Playing", "Racing", "Simulation", 
                     "Puzzle", "Adventure", "Sports", "Arcade", "Photography", 
                     "Productivity", "Music", "Communication", "Entertainment",
                     "Art & Design", "Video Players", "Personalization", "Tools",
                     "Social", "Lifestyle", "Video Editor", "Education", "Finance",
                     "Health & Fitness", "Medical", "News & Magazines", "Shopping",
                     "Travel & Local", "Weather", "Books & Reference", "Business"]
        for cat in categories:
            if cat.lower() in text_content.lower():
                category = cat
                break
        
        mod_features = ""
        mod_keywords = [
            "MOD Menu", "Unlimited", "Premium Unlocked", "Pro Unlocked", 
            "VIP Unlocked", "Full Premium", "Free Shopping", "God Mode",
            "One Hit Kill", "Remove Ads", "Unlocked", "AD Free", "No Ads",
            "All Unlocked", "Mega Mod", "Unlimited Money", "Unlimited Coins",
            "Unlimited Gems", "Premium", "Pro", "VIP", "Full"
        ]
        
        found_mods = []
        for mod in mod_keywords:
            if mod.lower() in text_content.lower():
                if mod not in found_mods:
                    found_mods.append(mod)
        
        if found_mods:
            mod_features = ", ".join(found_mods[:3])
        
        return {
            "name": name,
            "version": version,
            "size": size,
            "category": category,
            "mod_features": mod_features,
            "url": url,
            "image": image
        }
    except Exception as e:
        print(f"Parse error: {e}")
        return None

def search_website(query):
    url = f"{BASE_URL}/search?query={query}"
    html = fetch_page(url)
    soup = BeautifulSoup(html, "lxml")
    
    results = []
    
    cards = soup.select('a[href*="-mod-apk"], a[href*="-modded-apk"], a[href*="-apk"]')
    
    seen_urls = set()
    for card in cards:
        href = card.get("href", "")
        
        if href in seen_urls:
            continue
        
        if not href or "/search" in href or "/category" in href or "/page/" in href:
            continue
        if "/games/" in href or "/apps/" in href:
            continue
            
        seen_urls.add(href)
        
        app_data = parse_app_card(card)
        if app_data and app_data.get("name"):
            results.append(app_data)
    
    return results

def get_app_details(app_url):
    html = fetch_page(app_url)
    soup = BeautifulSoup(html, "lxml")
    
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
        "download_page": app_url.rstrip("/") + "/download"
    }
    
    title = soup.find("h1")
    if title:
        details["name"] = title.get_text(strip=True)
    
    info_elements = soup.find_all(["div", "td", "tr", "span", "p"])
    for elem in info_elements:
        text = elem.get_text(strip=True)
        
        if "Version" in text:
            match = re.search(r'v?[\d.]+', text)
            if match:
                details["version"] = match.group()
        elif "Size" in text:
            match = re.search(r'(\d+(?:\.\d+)?)\s*(MB|GB|KB)', text, re.IGNORECASE)
            if match:
                details["size"] = f"{match.group(1)} {match.group(2).upper()}"
        elif "Category" in text:
            link = elem.find("a")
            if link:
                details["category"] = link.get_text(strip=True)
        elif "Developer" in text or "Publisher" in text:
            details["publisher"] = text.split(":")[-1].strip() if ":" in text else ""
        elif "Requires" in text or "Android" in text:
            match = re.search(r'Android\s*[\d.]+', text)
            if match:
                details["requirements"] = match.group()
        elif "Updated" in text:
            details["last_updated"] = text.split(":")[-1].strip() if ":" in text else ""
    
    return details

def get_download_links(app_url):
    download_url = app_url.rstrip("/") + "/download"
    html = fetch_page(download_url)
    soup = BeautifulSoup(html, "lxml")
    
    downloads = []
    intermediate_links = []
    
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text(strip=True)
        
        if href.endswith(('.apk', '.xapk', '.zip')) or 'files.5modapk.com' in href:
            size_match = re.search(r'\(([^)]+)\)', text)
            size = size_match.group(1) if size_match else ""
            
            downloads.append({
                "name": text or "Download",
                "url": href,
                "size": size,
                "direct": True
            })
        elif "/download/" in href and re.search(r'/\d+$', href):
            size_match = re.search(r'\(([^)]+)\)', text)
            size = size_match.group(1) if size_match else ""
            
            intermediate_links.append({
                "name": text or "Download",
                "url": href if href.startswith("http") else BASE_URL + href,
                "size": size,
                "direct": False
            })
    
    if downloads:
        return downloads
    
    for item in intermediate_links:
        try:
            inter_html = fetch_page(item["url"])
            inter_soup = BeautifulSoup(inter_html, "lxml")
            
            for link in inter_soup.find_all("a", href=True):
                href = link.get("href", "")
                link_text = link.get_text(strip=True)
                
                if href.endswith(('.apk', '.xapk', '.zip')) or 'files.5modapk.com' in href:
                    size_match = re.search(r'\(([^)]+)\)', link_text)
                    size = size_match.group(1) if size_match else item.get("size", "")
                    
                    downloads.append({
                        "name": link_text or item.get("name", "Download"),
                        "url": href,
                        "size": size,
                        "direct": True
                    })
        except Exception as e:
            print(f"Error fetching intermediate link: {e}")
            downloads.append(item)
    
    return downloads if downloads else intermediate_links

def download_file(url, output_dir="downloads"):
    os.makedirs(output_dir, exist_ok=True)
    
    response = scraper.get(url, headers=HEADERS, stream=True, timeout=120, allow_redirects=True)
    response.raise_for_status()
    
    content_disp = response.headers.get("Content-Disposition", "")
    if "filename=" in content_disp:
        filename = re.search(r'filename="?([^";\n]+)"?', content_disp)
        filename = filename.group(1) if filename else "download.apk"
    else:
        filename = url.split("/")[-1] or "download.apk"
        if not filename.endswith((".apk", ".xapk", ".zip")):
            filename += ".apk"
    
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

def scrape_games(page=1, sort="updated"):
    url = f"{BASE_URL}/games/"
    if sort == "latest":
        url = f"{BASE_URL}/games?sort=latest"
    if page > 1:
        url += f"&page={page}" if "?" in url else f"?page={page}"
    
    html = fetch_page(url)
    soup = BeautifulSoup(html, "lxml")
    
    games = []
    cards = soup.select('a[href*="-mod-apk"], a[href*="-modded-apk"]')
    
    seen_urls = set()
    for card in cards:
        href = card.get("href", "")
        if href in seen_urls or not href:
            continue
        if "/games/" in href or "/apps/" in href or "/category/" in href:
            continue
        seen_urls.add(href)
        
        app_data = parse_app_card(card)
        if app_data and app_data.get("name"):
            games.append(app_data)
    
    return games

def scrape_apps(page=1, sort="updated"):
    url = f"{BASE_URL}/apps/"
    if sort == "latest":
        url = f"{BASE_URL}/apps?sort=latest"
    if page > 1:
        url += f"&page={page}" if "?" in url else f"?page={page}"
    
    html = fetch_page(url)
    soup = BeautifulSoup(html, "lxml")
    
    apps = []
    cards = soup.select('a[href*="-mod-apk"], a[href*="-modded-apk"]')
    
    seen_urls = set()
    for card in cards:
        href = card.get("href", "")
        if href in seen_urls or not href:
            continue
        if "/games/" in href or "/apps/" in href or "/category/" in href:
            continue
        seen_urls.add(href)
        
        app_data = parse_app_card(card)
        if app_data and app_data.get("name"):
            apps.append(app_data)
    
    return apps

def scrape_homepage():
    html = fetch_page(BASE_URL)
    soup = BeautifulSoup(html, "lxml")
    
    results = {"all_items": []}
    
    cards = soup.select('a[href*="-mod-apk"], a[href*="-modded-apk"], a[href*="-free-apk"]')
    
    seen_urls = set()
    for card in cards:
        href = card.get("href", "")
        if href in seen_urls or not href:
            continue
        if "/games/" in href or "/apps/" in href or "/category/" in href:
            continue
        seen_urls.add(href)
        
        app_data = parse_app_card(card)
        if app_data and app_data.get("name"):
            results["all_items"].append(app_data)
    
    return results

def search_items(query, category="all"):
    return search_website(query)
