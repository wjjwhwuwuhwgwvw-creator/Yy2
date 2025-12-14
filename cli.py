#!/usr/bin/env python3
import click
import json
import csv
from tabulate import tabulate
from scraper import (
    scrape_games, scrape_apps, scrape_homepage, 
    search_website, get_app_details, get_download_links, download_file
)

@click.group()
@click.version_option(version="1.0.0", prog_name="getmodsapk-scraper")
def cli():
    """CLI tool to scrape APK information from getmodsapk.com"""
    pass

@cli.command()
@click.option("--sort", type=click.Choice(["updated", "latest"]), default="updated", help="Sort order")
@click.option("--limit", default=20, help="Number of items to display")
@click.option("--export", type=click.Choice(["json", "csv"]), help="Export format")
@click.option("--output", default="games", help="Output filename (without extension)")
def games(sort, limit, export, output):
    """Scrape games from getmodsapk.com"""
    click.echo(f"Fetching games (sort: {sort})...")
    
    try:
        data = scrape_games(sort=sort)
        data = data[:limit]
        
        if not data:
            click.echo("No games found.")
            return
        
        if export:
            export_data(data, export, output)
        else:
            display_table(data, "Games")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command()
@click.option("--sort", type=click.Choice(["updated", "latest"]), default="updated", help="Sort order")
@click.option("--limit", default=20, help="Number of items to display")
@click.option("--export", type=click.Choice(["json", "csv"]), help="Export format")
@click.option("--output", default="apps", help="Output filename (without extension)")
def apps(sort, limit, export, output):
    """Scrape apps from getmodsapk.com"""
    click.echo(f"Fetching apps (sort: {sort})...")
    
    try:
        data = scrape_apps(sort=sort)
        data = data[:limit]
        
        if not data:
            click.echo("No apps found.")
            return
        
        if export:
            export_data(data, export, output)
        else:
            display_table(data, "Apps")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command()
@click.argument("query")
@click.option("--limit", default=20, help="Number of items to display")
@click.option("--export", type=click.Choice(["json", "csv"]), help="Export format")
@click.option("--output", default="search_results", help="Output filename (without extension)")
def search(query, limit, export, output):
    """Search for apps/games by name"""
    click.echo(f"Searching for '{query}'...")
    
    try:
        data = search_website(query)
        data = data[:limit]
        
        if not data:
            click.echo("No results found.")
            return
        
        if export:
            export_data(data, export, output)
        else:
            display_table(data, f"Search Results for '{query}'")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command()
@click.argument("app_url")
def info(app_url):
    """Get detailed info about an app/game"""
    click.echo(f"Fetching app details...")
    
    try:
        details = get_app_details(app_url)
        
        click.echo(f"\n{'='*60}")
        click.echo(f" {details.get('name', 'Unknown')}")
        click.echo(f"{'='*60}")
        click.echo(f"Version: {details.get('version', 'N/A')}")
        click.echo(f"Size: {details.get('size', 'N/A')}")
        click.echo(f"Category: {details.get('category', 'N/A')}")
        click.echo(f"Publisher: {details.get('publisher', 'N/A')}")
        click.echo(f"Requirements: {details.get('requirements', 'N/A')}")
        click.echo(f"Last Updated: {details.get('last_updated', 'N/A')}")
        click.echo(f"Download Page: {details.get('download_page', 'N/A')}")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command()
@click.argument("app_url")
@click.option("--download", "-d", is_flag=True, help="Download the first available file")
@click.option("--output-dir", default="downloads", help="Output directory for downloads")
def download(app_url, download, output_dir):
    """Get download links for an app/game"""
    click.echo(f"Fetching download links...")
    
    try:
        links = get_download_links(app_url)
        
        if not links:
            click.echo("No download links found.")
            return
        
        click.echo(f"\nAvailable Downloads ({len(links)}):\n")
        for i, link in enumerate(links, 1):
            click.echo(f"  [{i}] {link.get('name', 'Unknown')}")
            click.echo(f"      Size: {link.get('size', 'N/A')}")
            click.echo(f"      URL: {link.get('url', 'N/A')}")
            click.echo()
        
        if download and links:
            click.echo(f"Downloading first file to '{output_dir}'...")
            filepath = download_file(links[0]["url"], output_dir)
            click.echo(f"Downloaded: {filepath}")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command()
@click.option("--export", type=click.Choice(["json", "csv"]), help="Export format")
@click.option("--output", default="homepage", help="Output filename (without extension)")
def homepage(export, output):
    """Scrape the homepage (featured, updated, new items)"""
    click.echo("Fetching homepage data...")
    
    try:
        data = scrape_homepage()
        
        if export:
            with open(f"{output}.json", "w") as f:
                json.dump(data, f, indent=2)
            click.echo(f"Data exported to {output}.json")
        else:
            items = data.get("all_items", [])
            if items:
                display_table(items[:10], "Homepage Items")
                    
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

def display_table(data, title):
    if title:
        click.echo(f"\n{title} ({len(data)} items):\n")
    
    table_data = []
    for i, item in enumerate(data, 1):
        table_data.append([
            i,
            item.get("name", "")[:30],
            item.get("version", ""),
            item.get("size", ""),
            item.get("category", "")[:15],
            item.get("mod_features", "")[:30] + ("..." if len(item.get("mod_features", "")) > 30 else "")
        ])
    
    headers = ["#", "Name", "Version", "Size", "Category", "MOD Features"]
    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))

def export_data(data, format_type, filename):
    if format_type == "json":
        with open(f"{filename}.json", "w") as f:
            json.dump(data, f, indent=2)
        click.echo(f"Data exported to {filename}.json")
    elif format_type == "csv":
        if data:
            with open(f"{filename}.csv", "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            click.echo(f"Data exported to {filename}.csv")

if __name__ == "__main__":
    cli()
