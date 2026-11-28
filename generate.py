#!/usr/bin/env python3
"""
Generate a 400x300 PicPak weather card for Alameda, CA.

Uses the U.S. National Weather Service API (no API key required).
Cycles through a quote, fun fact, and kid-friendly joke based on the
calendar day. The bottom section shows one item at a time.
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
    modes = ["quote", "trivia", "joke"]
    mode = modes[today.toordinal() % len(modes)]
    items = data[mode]
    # Deterministic rotation through the selected collection, using Alameda's date.
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
    date_text = now.strftime("%A  %m/%d/%y")
    f = fit_text(d, date_text, 370, 31, True, 22)
    box = d.textbbox((0, 0), date_text, font=f)
    d.text(((W-(box[2]-box[0]))/2, 8), date_text, fill=BLACK, font=f)
    d.line((8, 54, 392, 54), fill=BLACK, width=3)

    # Three equal forecast columns, defined by two vertical divider lines.
    # The dividers connect the header and lower horizontal rules to form the
    # three boxes without separate rounded rectangles.
    columns = [
        ("Morning", "morning", 8, 136),
        ("Noon", "noon", 136, 264),
        ("Night", "night", 264, 392),
    ]
    for label, key, left, right in columns:
        p = forecast[key]
        cx = (left + right) // 2

        # Period label
        lf = fit_text(d, label, right-left-12, 15, True, 11)
        lb = d.textbbox((0, 0), label, font=lf)
        d.text((cx-(lb[2]-lb[0])/2, 61), label, fill=BLACK, font=lf)

        # Weather icon centered in its own column
        weather_icon(d, cx, 109, icon_kind(key, p["short"]), 0.82)

        # Prominent centered temperature
        temp_text = f'{p["temp"]}°{p["unit"]}'
        tf = fit_text(d, temp_text, right-left-12, 25, True, 17)
        tb = d.textbbox((0, 0), temp_text, font=tf)
        d.text((cx-(tb[2]-tb[0])/2, 142), temp_text, fill=BLACK, font=tf)

        # Center and wrap the condition within the card width.
        sf = fit_text(d, p["short"], right-left-14, 11, False, 9)
        words = p["short"].split()
        desc_lines = []
        line = ""
        for word in words:
            trial = (line + " " + word).strip()
            if d.textlength(trial, font=sf) <= right-left-14:
                line = trial
            else:
                if line:
                    desc_lines.append(line)
                line = word
        if line:
            desc_lines.append(line)
        for i, desc in enumerate(desc_lines[:2]):
            dw = d.textlength(desc, font=sf)
            d.text((cx-dw/2, 175+i*13), desc, fill=BLACK, font=sf)

    # Two dividers connect the header and lower horizontal rules.
    d.line((136, 54, 136, 222), fill=BLACK, width=2)
    d.line((264, 54, 264, 222), fill=BLACK, width=2)
    d.line((8, 222, 392, 222), fill=BLACK, width=3)

    # All content types share the same centered body layout and typography.
    if mode == "trivia":
        parts = [content["question"], content["answer"]]
    elif mode == "joke":
        parts = [content["text"], content["answer"]]
    else:
        parts = [content["text"]]
        if content.get("author"):
            parts.append(f'— {content["author"]}')

    # Wrap each joke/question/answer independently and use the largest font
    # that fits in the available bottom area.
    def wrap_part(text, face, max_width):
        words = str(text).replace("\\n", " ").split()
        wrapped = []
        line = ""
        for word in words:
            trial = (line + " " + word).strip()
            if d.textlength(trial, font=face) <= max_width:
                line = trial
                continue
            if line:
                wrapped.append(line)
                line = ""
            # Split a single overlong token rather than letting it overflow.
            piece = ""
            for char in word:
                candidate = piece + char
                if piece and d.textlength(candidate, font=face) > max_width:
                    wrapped.append(piece)
                    piece = char
                else:
                    piece = candidate
            line = piece
        if line:
            wrapped.append(line)
        return wrapped

    available_top, available_bottom = 228, 297
    max_width = 372
    body_font = font(22, True)
    lines = []
    for size in range(22, 9, -1):
        candidate_font = font(size, True)
        candidate_lines = []
        for part in parts:
            candidate_lines.extend(wrap_part(part, candidate_font, max_width))
        line_height = size + 3
        if len(candidate_lines) * line_height <= available_bottom - available_top:
            body_font = candidate_font
            lines = candidate_lines
            break
    if not lines:
        body_font = font(10, True)
        lines = []
        for part in parts:
            lines.extend(wrap_part(part, body_font, max_width))

    line_height = body_font.size + 3
    total_height = len(lines) * line_height
    y = available_top + max(0, (available_bottom - available_top - total_height) // 2)
    for line in lines:
        text_width = d.textlength(line, font=body_font)
        x = (W - text_width) / 2
        d.text((x, y), line, fill=BLACK, font=body_font)
        y += line_height

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
