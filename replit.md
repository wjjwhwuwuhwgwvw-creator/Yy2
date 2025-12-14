# AppOmar WhatsApp Bot

## Overview

A professional WhatsApp bot built with Node.js that provides APK/app downloading, media downloading from social platforms, AI-powered conversations, and group management features. The bot uses the Baileys library for WhatsApp Web API connectivity and integrates with Google's Gemini AI for intelligent responses.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Components

**Bot Engine (bot.js)**
- Main entry point using Baileys WhatsApp library (`@itsukichan/baileys`)
- Multi-file authentication state stored in `session/` directory
- Message caching with `node-cache` for retry handling and response deduplication
- Global error handlers to prevent bot crashes from unhandled rejections

**Plugin System (plugins/)**
- Modular architecture where each feature is a separate plugin
- Plugins export patterns (regex for URL matching) and commands (text commands)
- Social media downloaders: TikTok, Instagram, Facebook, Twitter/X, Pinterest, YouTube
- File downloaders: Google Drive, Mediafire with automatic file splitting for large files
- AI features: Image generation via external API
- Group management: Anti-link, anti-bad-words, scheduled group open/close times

**API Backend (src/api/api_server.py)**
- FastAPI server running on port 8000 for APK search and download functionality
- Integrates with `aria2c` for high-speed parallel downloads
- Web scraping from APK sites (apkdone.com) using BeautifulSoup and cloudscraper

**AI Integration (src/utils/gemini-brain.js)**
- Google Gemini AI for conversational responses
- Multiple API key rotation for rate limit handling
- Conversation history stored as JSON files in `conversations/` directory
- Image analysis capabilities via gemini-scraper.js

**Storage Layer (src/storage.js)**
- JSON file-based storage in `data/` directory
- Manages: blocklist, users, downloads history, group settings, anti-private settings, warnings

### Design Patterns

**Rate Limiting & Retry Logic**
- Automatic retry with exponential backoff for WhatsApp rate limits
- API key rotation when Gemini quotas are hit

**File Splitting (src/utils/file-splitter.js)**
- Large files (>1GB) automatically split for WhatsApp's file size limits
- Uses aria2c for parallel downloading before splitting

**Group Management (src/group-manager.js)**
- Anti-link detection with multiple platform patterns
- Bad words filtering with warning system
- Scheduled group open/close functionality
- Anti-private messaging with automatic blocking

## External Dependencies

### Third-Party Services
- **Google Gemini AI**: Conversational AI and image analysis
- **APK Sources**: apkdone.com scraped for app information and downloads
- **Social Media APIs**: Various unofficial APIs for downloading content from TikTok, Instagram, Facebook, Twitter, YouTube, Pinterest

### Databases
- **PostgreSQL** (optional): Schema defined in `database/schema.sql`, initialized via `init_database.js`
- **JSON Files** (primary): All data stored in `data/` directory as JSON files

### System Tools
- **aria2c**: High-speed parallel file downloader for large APK files
- **sharp**: Image processing for profile pictures and media handling
- **cloudscraper**: Bypass Cloudflare protection on scraped sites

### Key npm Packages
- `@itsukichan/baileys`: WhatsApp Web API library
- `@google/generative-ai`: Gemini AI SDK
- `axios`, `cheerio`: HTTP requests and HTML parsing
- `pg`: PostgreSQL client (optional database support)
- `pino`: Logging
- `adm-zip`: ZIP file handling for XAPK packages

### Python Dependencies
- `fastapi`, `uvicorn`: API server
- `beautifulsoup4`, `cloudscraper`: Web scraping
- `playwright`, `nodriver`: Browser automation for complex scraping