#!/usr/bin/env python3
"""
Generate a terminal-styled GitHub Activity Graph SVG for Vinay-1774.
Fetches real contribution data directly from GitHub (via GraphQL or public scraper fallback)
and renders a self-hosted, responsive SVG adhering to the #000000 / #00FF41 neon aesthetic.
"""

import os
import sys
import re
import json
import math
import urllib.request
from datetime import datetime

USERNAME = os.environ.get("GITHUB_USERNAME", "Vinay-1774")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "assets/activity-graph.svg")
DAYS_TO_SHOW = 31

def fetch_contributions_graphql(username, token):
    query = """
    query($login: String!) {
      user(login: $login) {
        name
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": username}}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "Antigravity-Activity-Graph-Generator",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        data = json.loads(res.read().decode("utf-8"))
    
    user = data.get("data", {}).get("user")
    if not user:
        raise ValueError(f"User '{username}' not found in GraphQL API response")
    
    display_name = user.get("name") or username
    days = []
    weeks = user.get("contributionsCollection", {}).get("contributionCalendar", {}).get("weeks", [])
    for week in weeks:
        for day in week.get("contributionDays", []):
            days.append((day["date"], int(day["contributionCount"])))
    days.sort(key=lambda x: x[0])
    return display_name, days

def fetch_contributions_scrape(username):
    url = f"https://github.com/users/{username}/contributions"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=15) as res:
        html = res.read().decode("utf-8")
    
    matches = re.findall(r'<td[^>]*data-date="([0-9-]+)"[^>]*id="([^"]+)"', html)
    tooltips = dict(re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>(.*?)</tool-tip>', html))
    
    days = []
    for date_str, cid in matches:
        tip = tooltips.get(cid, "")
        m = re.match(r"^([0-9]+)\s+contribution", tip.strip())
        count = int(m.group(1)) if m else 0
        days.append((date_str, count))
    
    days.sort(key=lambda x: x[0])
    
    # Try to fetch display name via public API, fallback to default
    display_name = "Vinay Pratap Raghuwanshi"
    try:
        u_req = urllib.request.Request(
            f"https://api.github.com/users/{username}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(u_req, timeout=5) as u_res:
            u_data = json.loads(u_res.read().decode("utf-8"))
            if u_data.get("name"):
                display_name = u_data["name"]
    except Exception:
        pass

    return display_name, days

def calculate_y_axis(max_val):
    if max_val <= 4:
        return 4, 1
    if max_val <= 8:
        return 8, 2
    if max_val <= 12:
        return 12, 3
    if max_val <= 16:
        return 16, 4
    if max_val <= 20:
        return 20, 4
    if max_val <= 30:
        return 30, 5
    if max_val <= 50:
        return 50, 10
    step = math.ceil(max_val / 5 / 5) * 5
    return step * 5, step

def build_smooth_bezier(points, base_y, top_y):
    if not points:
        return ""
    if len(points) == 1:
        return f"M {points[0][0]:.2f},{points[0][1]:.2f}"
    
    path = [f"M {points[0][0]:.2f},{points[0][1]:.2f}"]
    for i in range(len(points) - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else p2
        
        # If both points are on the baseline (0 contributions), draw a straight line
        if p1[1] == base_y and p2[1] == base_y:
            path.append(f"L {p2[0]:.2f},{p2[1]:.2f}")
            continue

        cp1_x = p1[0] + (p2[0] - p0[0]) / 6.0
        cp1_y = p1[1] + (p2[1] - p0[1]) / 6.0
        cp2_x = p2[0] - (p3[0] - p1[0]) / 6.0
        cp2_y = p2[1] - (p3[1] - p1[1]) / 6.0
        
        # Clamp control points so they don't dip below baseline or exceed top
        cp1_y = max(top_y, min(base_y, cp1_y))
        cp2_y = max(top_y, min(base_y, cp2_y))
        
        path.append(f"C {cp1_x:.2f},{cp1_y:.2f} {cp2_x:.2f},{cp2_y:.2f} {p2[0]:.2f},{p2[1]:.2f}")
    
    return " ".join(path)

def generate_svg(display_name, recent_days):
    width = 1200
    height = 420
    x_start = 90
    x_end = 1150
    base_y = 350
    top_y = 80
    chart_h = base_y - top_y
    n = len(recent_days)
    dx = (x_end - x_start) / max(1, n - 1)
    
    max_c = max(c for _, c in recent_days) if recent_days else 0
    max_y_val, y_step = calculate_y_axis(max_c)
    
    # Calculate point coordinates
    points = []
    for i, (date_str, count) in enumerate(recent_days):
        x = x_start + i * dx
        y = base_y - (count / max_y_val) * chart_h
        points.append((x, y, date_str, count))
    
    line_path = build_smooth_bezier([(p[0], p[1]) for p in points], base_y, top_y)
    area_path = f"{line_path} L {points[-1][0]:.2f},{base_y:.2f} L {points[0][0]:.2f},{base_y:.2f} Z"
    
    # Grid lines & Y labels
    y_grid_elements = []
    val = 0
    while val <= max_y_val:
        y = base_y - (val / max_y_val) * chart_h
        y_grid_elements.append(
            f'  <line x1="{x_start}" y1="{y:.1f}" x2="{x_end}" y2="{y:.1f}" stroke="#00FF41" stroke-opacity="0.15" stroke-dasharray="3 3"/>'
        )
        y_grid_elements.append(
            f'  <text x="{x_start - 12}" y="{y + 4:.1f}" text-anchor="end" fill="#00FF41" font-size="12" font-family="\'Fira Code\', monospace, sans-serif">{val}</text>'
        )
        val += y_step
    
    # Vertical grid lines & X labels (day of month)
    x_grid_elements = []
    for i, (x, y, date_str, count) in enumerate(points):
        x_grid_elements.append(
            f'  <line x1="{x:.1f}" y1="{top_y}" x2="{x:.1f}" y2="{base_y}" stroke="#00FF41" stroke-opacity="0.08" stroke-dasharray="2 4"/>'
        )
        day_num = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d").lstrip("0")
        x_grid_elements.append(
            f'  <text x="{x:.1f}" y="{base_y + 22}" text-anchor="middle" fill="#00FF41" font-size="11" font-family="\'Fira Code\', monospace, sans-serif">{day_num}</text>'
        )
    
    # Data circles
    point_elements = []
    for x, y, date_str, count in points:
        plural = "s" if count != 1 else ""
        if count > 0:
            point_elements.append(
                f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#FFFFFF" stroke="#00FF41" stroke-width="2.5" class="point">'
                f'<title>{date_str}: {count} contribution{plural}</title>'
                f'</circle>'
            )
        else:
            point_elements.append(
                f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="#00FF41" fill-opacity="0.35">'
                f'<title>{date_str}: 0 contributions</title>'
                f'</circle>'
            )

    title_text = f"{display_name.title()}'s Contribution Graph"
    
    svg = f"""<svg width="100%" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#00FF41" stop-opacity="0.28"/>
      <stop offset="85%" stop-color="#00FF41" stop-opacity="0.04"/>
      <stop offset="100%" stop-color="#00FF41" stop-opacity="0"/>
    </linearGradient>
    <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <style>
      .title {{
        font-family: 'Fira Code', 'Segoe UI', Ubuntu, monospace, sans-serif;
        font-size: 20px;
        font-weight: 600;
        fill: #00FF41;
        letter-spacing: 0.5px;
      }}
      .axis-title {{
        font-family: 'Fira Code', 'Segoe UI', Ubuntu, monospace, sans-serif;
        font-size: 13px;
        font-weight: 600;
        fill: #00FF41;
        opacity: 0.85;
      }}
      .point:hover {{
        r: 6.5;
        cursor: pointer;
        stroke-width: 3;
      }}
    </style>
  </defs>

  <!-- Background Card -->
  <rect width="100%" height="100%" fill="#000000" rx="8" stroke="#00FF41" stroke-opacity="0.2" stroke-width="1.5"/>

  <!-- Title -->
  <text x="600" y="46" text-anchor="middle" class="title">{title_text}</text>

  <!-- Grids & Axis Labels -->
{chr(10).join(y_grid_elements)}
{chr(10).join(x_grid_elements)}

  <!-- Axis Titles -->
  <text x="620" y="402" text-anchor="middle" class="axis-title">Days</text>
  <text x="26" y="215" text-anchor="middle" class="axis-title" transform="rotate(-90 26 215)">Contributions</text>

  <!-- Area Gradient Fill -->
  <path d="{area_path}" fill="url(#areaGradient)"/>

  <!-- Line Glow & Main Stroke -->
  <path d="{line_path}" fill="none" stroke="#00FF41" stroke-opacity="0.4" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" filter="url(#neonGlow)"/>
  <path d="{line_path}" fill="none" stroke="#00FF41" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>

  <!-- Data Points -->
{chr(10).join(point_elements)}
</svg>
"""
    return svg

def main():
    token = os.environ.get("GITHUB_TOKEN")
    display_name = "Vinay Pratap Raghuwanshi"
    days = []
    
    if token:
        try:
            print("Attempting to fetch contribution data via GitHub GraphQL API...")
            display_name, days = fetch_contributions_graphql(USERNAME, token)
            print(f"Successfully fetched {len(days)} days via GraphQL API.")
        except Exception as e:
            print(f"GraphQL fetch failed ({e}), falling back to public scraper...")
            days = []

    if not days:
        try:
            print(f"Fetching contribution data via public scraper for '{USERNAME}'...")
            name_scraped, days = fetch_contributions_scrape(USERNAME)
            if name_scraped:
                display_name = name_scraped
            print(f"Successfully fetched {len(days)} days via public scraper.")
        except Exception as e:
            print(f"Error fetching contribution data: {e}", file=sys.stderr)
            if os.path.exists(OUTPUT_PATH):
                print("Existing SVG file found. Leaving intact to prevent broken link.")
                sys.exit(0)
            else:
                sys.exit(1)

    recent_days = days[-DAYS_TO_SHOW:]
    print(f"Rendering last {len(recent_days)} days for {display_name}...")
    
    svg = generate_svg(display_name, recent_days)
    
    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_PATH)), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    
    print(f"Activity graph SVG generated successfully at: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
