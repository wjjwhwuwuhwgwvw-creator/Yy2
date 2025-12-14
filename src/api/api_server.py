#!/usr/bin/env python3
import os
import sys
import re
import json
import asyncio
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scraper import search_website, get_app_details, get_download_links, download_file, scrape_games, scrape_apps
from search_orchestrator import combined_search, search_google_play, get_google_play_app, get_package_for_slug, is_package_name

app = FastAPI(title="APK Download API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = Path(__file__).parent.parent.parent / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

APKEEP_PATH = Path(__file__).parent.parent.parent / "apkeep"

async def run_aria2c(url, output_dir, filename=None, referer=None):
    cmd = [
        "aria2c",
        "--max-connection-per-server=16",
        "--split=16",
        "--min-split-size=512K",
        "--max-concurrent-downloads=16",
        "--continue=true",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        "--file-allocation=none",
        "--timeout=120",
        "--connect-timeout=15",
        "--max-tries=5",
        "--retry-wait=2",
        "--enable-http-pipelining=true",
        "--http-accept-gzip=true",
        "--stream-piece-selector=geom",
        "--lowest-speed-limit=50K",
        "--async-dns=true",
        "--check-certificate=false",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-d", str(output_dir),
    ]
    if referer:
        cmd.extend(["--referer", referer])
    else:
        cmd.extend(["--referer", "https://apkdone.com/"])
    if filename:
        cmd.extend(["-o", filename])
    cmd.append(url)
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode == 0, stdout.decode(), stderr.decode()

async def run_apkeep(package_name, output_dir):
    cmd = [
        str(APKEEP_PATH),
        "-a", package_name,
        "-d", "apk-pure",
        str(output_dir)
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode == 0, stdout.decode(), stderr.decode()

@app.get("/")
async def root():
    return {"status": "ok", "message": "APK Download API Server"}

@app.get("/search")
async def search_apps(q: str = Query(..., description="Search query"), num: int = Query(10, description="Number of results"), combined: bool = Query(True, description="Use combined search")):
    try:
        if combined:
            search_results = combined_search(q, num)
            formatted_results = []
            for app in search_results.get('combined', [])[:num]:
                source = app.get('source', 'apkdone')
                if source == 'google':
                    formatted_results.append({
                        "title": app.get("name", ""),
                        "name": app.get("name", ""),
                        "version": app.get("version", ""),
                        "size": app.get("size", ""),
                        "package": app.get("package", ""),
                        "appId": app.get("appId", ""),
                        "url": app.get("url", ""),
                        "image": app.get("icon", ""),
                        "icon": app.get("icon", ""),
                        "category": app.get("category", ""),
                        "mod_features": "",
                        "source": "google"
                    })
                else:
                    formatted_results.append({
                        "title": app.get("name", ""),
                        "name": app.get("name", ""),
                        "version": app.get("version", ""),
                        "size": app.get("size", ""),
                        "package": extract_package_from_url(app.get("url", "")),
                        "appId": extract_package_from_url(app.get("url", "")),
                        "url": app.get("url", ""),
                        "image": app.get("image", ""),
                        "icon": app.get("image", ""),
                        "category": app.get("category", ""),
                        "mod_features": app.get("mod_features", ""),
                        "source": "apkdone"
                    })
            return {"results": formatted_results, "count": len(formatted_results)}
        else:
            results = search_website(q)
            formatted_results = []
            for app in results[:num]:
                formatted_results.append({
                    "title": app.get("name", ""),
                    "name": app.get("name", ""),
                    "version": app.get("version", ""),
                    "size": app.get("size", ""),
                    "package": extract_package_from_url(app.get("url", "")),
                    "appId": extract_package_from_url(app.get("url", "")),
                    "url": app.get("url", ""),
                    "image": app.get("image", ""),
                    "icon": app.get("image", ""),
                    "category": app.get("category", ""),
                    "mod_features": app.get("mod_features", ""),
                    "source": "apkdone"
                })
            return {"results": formatted_results, "count": len(formatted_results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_package_from_url(url):
    if not url:
        return ""
    slug = url.rstrip('/').split('/')[-1]
    if not slug or slug in ['app', 'game', 'download']:
        return ""
    slug = re.sub(r'-mod-apk.*', '', slug)
    slug = re.sub(r'-apk.*', '', slug)
    return slug

@app.get("/app/{app_id}")
async def get_app_info(app_id: str, url: str = Query(None, description="Direct app URL")):
    try:
        if url:
            app_url = url
            details = get_app_details(app_url)
            download_links = get_download_links(app_url)
            results = [{"name": details.get("name", ""), "image": ""}]
        else:
            results = search_website(app_id.replace("-", " "))
            if not results:
                raise HTTPException(status_code=404, detail="App not found")
            app_url = results[0].get("url", "")
            details = get_app_details(app_url)
            download_links = get_download_links(app_url)
        
        app_name = details.get("name", results[0].get("name", ""))
        return {
            "appId": app_id,
            "title": app_name,
            "name": app_name,
            "version": details.get("version", results[0].get("version", "")),
            "size": details.get("size", results[0].get("size", "")),
            "category": details.get("category", ""),
            "publisher": details.get("publisher", ""),
            "requirements": details.get("requirements", ""),
            "last_updated": details.get("last_updated", ""),
            "icon": results[0].get("image", ""),
            "download_links": download_links,
            "url": app_url
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{package_name}")
async def download_app(package_name: str, background_tasks: BackgroundTasks, force_apkeep: bool = Query(False), source: str = Query("auto", description="Source: auto, apkdone, google")):
    try:
        output_dir = DOWNLOAD_DIR / package_name
        output_dir.mkdir(exist_ok=True)
        
        existing_files = list(output_dir.glob("*.apk")) + list(output_dir.glob("*.xapk"))
        if existing_files and not force_apkeep:
            return FileResponse(
                path=str(existing_files[0]),
                filename=existing_files[0].name,
                media_type="application/vnd.android.package-archive",
                headers={"X-Source": "cache"}
            )
        
        use_apkeep_directly = is_package_name(package_name) or source == "google" or force_apkeep
        
        if use_apkeep_directly:
            success, stdout, stderr = await run_apkeep(package_name, output_dir)
            if success:
                files = list(output_dir.glob("*.apk")) + list(output_dir.glob("*.xapk"))
                if files:
                    return FileResponse(
                        path=str(files[0]),
                        filename=files[0].name,
                        media_type="application/vnd.android.package-archive",
                        headers={"X-Source": "apkeep+google"}
                    )
        
        from scraper import BASE_URL
        
        app_url = f"{BASE_URL}/{package_name}/"
        
        download_links = get_download_links(app_url)
        
        if download_links:
            for link in download_links:
                if not link.get('direct'):
                    continue
                download_url = link.get('url')
                if not download_url:
                    continue
                
                try:
                    success, stdout, stderr = await run_aria2c(download_url, output_dir)
                    if success:
                        files = sorted(output_dir.glob("*.*"), key=os.path.getmtime, reverse=True)
                        apk_files = [f for f in files if f.suffix.lower() in ['.apk', '.xapk', '.zip']]
                        if apk_files:
                            return FileResponse(
                                path=str(apk_files[0]),
                                filename=apk_files[0].name,
                                media_type="application/vnd.android.package-archive",
                                headers={"X-Source": "aria2c+apkdone"}
                            )
                except Exception as e:
                    print(f"aria2c failed: {e}, trying cloudscraper...")
                
                try:
                    filepath = download_file(download_url, str(output_dir))
                    if Path(filepath).exists():
                        return FileResponse(
                            path=filepath,
                            filename=Path(filepath).name,
                            media_type="application/vnd.android.package-archive",
                            headers={"X-Source": "cloudscraper+apkdone"}
                        )
                except Exception as e:
                    print(f"cloudscraper failed: {e}")
                    continue
        
        if force_apkeep or not download_links:
            success, stdout, stderr = await run_apkeep(package_name, output_dir)
            
            if success:
                files = list(output_dir.glob("*.apk")) + list(output_dir.glob("*.xapk"))
                if files:
                    return FileResponse(
                        path=str(files[0]),
                        filename=files[0].name,
                        media_type="application/vnd.android.package-archive",
                        headers={"X-Source": "apkeep"}
                    )
            
            raise HTTPException(status_code=500, detail=f"Download failed: {stderr}")
        
        raise HTTPException(status_code=500, detail="No download links found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download-direct")
async def download_direct(url: str = Query(...), filename: str = Query(None), referer: str = Query(None)):
    try:
        output_dir = DOWNLOAD_DIR / "direct"
        output_dir.mkdir(exist_ok=True)
        
        success, stdout, stderr = await run_aria2c(url, output_dir, filename, referer)
        
        if success:
            if filename:
                filepath = output_dir / filename
            else:
                downloaded_files = sorted(output_dir.glob("*"), key=os.path.getmtime, reverse=True)
                if downloaded_files:
                    filepath = downloaded_files[0]
                else:
                    raise HTTPException(status_code=500, detail="No file downloaded")
            
            if filepath.exists():
                return FileResponse(
                    path=str(filepath),
                    filename=filepath.name,
                    media_type="application/octet-stream"
                )
        
        raise HTTPException(status_code=500, detail=f"Download failed: {stderr}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/fast-download/{package_name}")
async def fast_download(package_name: str):
    """Fast download - skips search, uses direct URL pattern"""
    try:
        output_dir = DOWNLOAD_DIR / package_name
        output_dir.mkdir(exist_ok=True)
        
        existing_files = list(output_dir.glob("*.apk")) + list(output_dir.glob("*.xapk"))
        if existing_files:
            return FileResponse(
                path=str(existing_files[0]),
                filename=existing_files[0].name,
                media_type="application/vnd.android.package-archive",
                headers={"X-Source": "cache"}
            )
        
        from scraper import BASE_URL
        app_url = f"{BASE_URL}/{package_name}/"
        download_links = get_download_links(app_url)
        
        if download_links:
            for link in download_links:
                if not link.get('direct'):
                    continue
                download_url = link.get('url')
                if not download_url:
                    continue
                
                success, stdout, stderr = await run_aria2c(download_url, output_dir)
                if success:
                    files = sorted(output_dir.glob("*.*"), key=os.path.getmtime, reverse=True)
                    apk_files = [f for f in files if f.suffix.lower() in ['.apk', '.xapk', '.zip']]
                    if apk_files:
                        return FileResponse(
                            path=str(apk_files[0]),
                            filename=apk_files[0].name,
                            media_type="application/vnd.android.package-archive",
                            headers={"X-Source": "aria2c+fast"}
                        )
        
        raise HTTPException(status_code=404, detail="No download links found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/games")
async def list_games(limit: int = Query(20)):
    try:
        games = scrape_games()
        return {"results": games[:limit], "count": len(games[:limit])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/apps")
async def list_apps(limit: int = Query(20)):
    try:
        apps = scrape_apps()
        return {"results": apps[:limit], "count": len(apps[:limit])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{package_name}")
async def check_download_status(package_name: str):
    output_dir = DOWNLOAD_DIR / package_name
    if output_dir.exists():
        files = list(output_dir.glob("*.apk")) + list(output_dir.glob("*.xapk"))
        if files:
            return {
                "status": "ready",
                "file": files[0].name,
                "size": files[0].stat().st_size
            }
    return {"status": "not_found"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
