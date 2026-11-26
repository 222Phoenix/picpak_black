#!/usr/bin/env python3
"""
Generate a 400x300 PicPak weather card for Alameda, CA.

Uses the U.S. National Weather Service API (no API key required).
Alternates between a fun fact and a motivational quote based on the
calendar day: even day = fun fact, odd day = quote.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont

W, H = 400, 300
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (220, 0, 0)
YELLOW = (255, 195, 0)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "weather.png"

USER_AGENT = "picpak-weather-github-action/1.0 (GitHub Actions)"
LAT, LON = 37.7652, -122.2416  # Alameda, CA


def get_json(url):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"})
    with urlopen(req, timeout=20) as r:
        return json.load(r)


def nws_forecast():
    from zoneinfo import ZoneInfo

    point = get_json(f"https://api.weather.gov/points/{LAT},{LON}")
    forecast_url = point["properties"]["forecastHourly"]
    hourly = get_json(forecast_url)["properties"]["periods"]

    # Use the closest NWS hourly forecast to 8 AM, noon, and 9 PM
    # in Alameda local time. Do not require an arbitrary +/-2 hour window;
    # that can cause the same hourly period to be reused for multiple rows.
    pacific = ZoneInfo("America/Los_Angeles")
    today = datetime.now(pacific).date()
    wanted = {"morning": 8, "noon": 12, "night": 21}
    result = {}

    candidates = []
    for period in hourly:
        dt = datetime.fromisoformat(period["startTime"].replace("Z", "+00:00"))
        local = dt.astimezone(pacific)
        if local.date() == today:
            candidates.append((local.hour + local.minute / 60, period))

    if not candidates:
        raise RuntimeError("NWS hourly forecast contains no periods for today")

    for name, target in wanted.items():
        _, period = min(candidates, key=lambda x: abs(x[0] - target))
        result[name] = {
            "temp": period["temperature"],
            "unit": period["temperatureUnit"],
            "short": period["shortForecast"],
            "isDaytime": period["isDaytime"],
        }

    return result


def load_content():
    data = json.loads((ROOT / "data" / "content.json").read_text())
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    mode = "trivia" if today.day % 2 == 0 else "quote"
    items = data[mode]
    # Deterministic daily rotation through the full collection, using Alameda's date.
    index = today.toordinal() % len(items)
    return mode, items[index]


def font(size, bold=False):
    # GitHub Ubuntu runners provide DejaVu Sans. For a specific Roboto build,
    # place a Roboto TTF at fonts/Roboto-Bold.ttf and fonts/Roboto-Regular.ttf.
    candidates = [
        ROOT / "fonts" / ("Roboto-Bold.ttf" if bold else "Roboto-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
             else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def fit_text(draw, text, max_width, start_size, bold=True, min_size=10):
    size = start_size
    while size >= min_size:
        f = font(size, bold)
        if draw.textbbox((0, 0), text, font=f)[2] <= max_width:
            return f
        size -= 1
    return font(min_size, bold)


def weather_icon(draw, x, y, kind, scale=1):
    # Small four-color icons designed specifically for the 400x300 card.
    r = int(17 * scale)
    if "sun" in kind.lower() or "clear" in kind.lower():
        draw.ellipse((x-r, y-r, x+r, y+r), fill=YELLOW, outline=BLACK, width=max(1, int(2*scale)))
        for dx, dy in [(0,-27),(0,27),(-27,0),(27,0),(-19,-19),(19,-19),(-19,19),(19,19)]:
            draw.line((x+dx*.8, y+dy*.8, x+dx, y+dy), fill=YELLOW, width=max(2,int(4*scale)))
    elif "night" in kind.lower():
        draw.pieslice((x-r, y-r, x+r, y+r), 60, 300, fill=YELLOW, outline=BLACK, width=2)
        draw.ellipse((x-3, y-r-1, x+r+12, y+5), fill=WHITE)
    else:
        # Cloud, optionally with sun behind it.
        if "partly" in kind.lower() or "mostly" in kind.lower():
            draw.ellipse((x-20, y-23, x+10, y+7), fill=YELLOW, outline=BLACK, width=2)
        draw.ellipse((x-28, y-4, x+2, y+18), fill=WHITE, outline=BLACK, width=2)
        draw.ellipse((x-10, y-17, x+20, y+18), fill=WHITE, outline=BLACK, width=2)
        draw.rounded_rectangle((x-30, y+1, x+25, y+21), radius=10, fill=WHITE, outline=BLACK, width=2)


def icon_kind(period, short):
    s = short.lower()
    if period == "night":
        if "clear" in s:
            return "night"
        if "partly" in s or "mostly" in s:
            return "night-cloud"
    if "sunny" in s or "clear" in s:
        return "sunny"
    if "partly" in s or "mostly" in s:
        return "partly cloudy"
    return "cloudy"


def draw_card(forecast, mode, content):
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # Header
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    date_text = now.strftime("%A %m/%d/%y")
    f = fit_text(d, date_text, 370, 31, True, 22)
    box = d.textbbox((0, 0), date_text, font=f)
    d.text(((W-(box[2]-box[0]))/2, 8), date_text, fill=BLACK, font=f)
    d.line((8, 54, 392, 54), fill=BLACK, width=3)

    rows = [("Morning", "morning", 72), ("Noon", "noon", 123), ("Night", "night", 174)]
    for label, key, y in rows:
        p = forecast[key]
        weather_icon(d, 35, y+14, icon_kind(key, p["short"]), 0.65)

        lf = font(20, True)
        sf = fit_text(d, p["short"], 175, 13, False, 10)
        d.text((82, y), f"{label}:", fill=BLACK, font=lf)
        d.text((68, y+23), p["short"], fill=BLACK, font=sf)

        tf = fit_text(d, f'{p["temp"]}°{p["unit"]}', 90, 28, True, 20)
        tb = d.textbbox((0, 0), f'{p["temp"]}°{p["unit"]}', font=tf)
        d.text((380-(tb[2]-tb[0]), y+5), f'{p["temp"]}°{p["unit"]}', fill=BLACK, font=tf)

    d.line((8, 222, 392, 222), fill=BLACK, width=3)

    heading = "DAILY TRIVIA" if mode == "trivia" else "MOTIVATION"
    hf = fit_text(d, heading, 300, 19, True, 15)
    hb = d.textbbox((0, 0), heading, font=hf)
    d.text(((W-(hb[2]-hb[0]))/2 + 12, 225), heading, fill=RED, font=hf)

    if mode == "trivia":
        question = content["question"]
        answer = content["answer"]
        qf = fit_text(d, question, 372, 16, True, 11)
        af = fit_text(d, answer, 372, 14, False, 10)
        def centered_line(text, f, y):
            b = d.textbbox((0, 0), text, font=f)
            d.text(((W-(b[2]-b[0]))/2 + 12, y), text, fill=BLACK, font=f)
        centered_line(question, qf, 249)
        centered_line(answer, af, 276)
    else:
        text = f'“{content["text"]}”'
        author = content.get("author")
        qf = fit_text(d, text, 372, 16, True, 11)
        words = text.split()
        lines, line = [], ""
        for word in words:
            trial = (line + " " + word).strip()
            if d.textbbox((0, 0), trial, font=qf)[2] <= 372:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        for i, line in enumerate(lines[:2]):
            b = d.textbbox((0, 0), line, font=qf)
            d.text(((W-(b[2]-b[0]))/2 + 12, 250+i*19), line, fill=BLACK, font=qf)
        if author:
            af = fit_text(d, f"— {author}", 250, 11, True, 9)
            b = d.textbbox((0, 0), f"— {author}", font=af)
            d.text(((W-(b[2]-b[0]))/2 + 12, 285), f"— {author}", fill=BLACK, font=af)

    return img


def main():
    forecast = nws_forecast()
    mode, content = load_content()
    img = draw_card(forecast, mode, content)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"Wrote {OUT} using {mode}: {content}")


if __name__ == "__main__":
    main()
