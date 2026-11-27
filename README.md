# PicPak Daily Weather Card

Generates a 400×300 PNG for a PicPak frame.

## What it does

Every day the GitHub Action:

1. Gets Alameda, California hourly weather from the National Weather Service API.
2. Creates morning/noon/night weather rows with weather information.
3. Selects one item from the daily fun-content pools: a trivia question, motivational quote, or kid-friendly joke.
4. Saves the result as `docs/weather.png`.
5. Creates a uniquely named image such as `weather-2026-11-27-123456789-1.png`.
6. Updates `docs/latest.json` with the unique image URL.
7. Commits the generated files and deploys them to GitHub Pages.

## Daily content

The bottom section rotates among three content types:

- **Fun Fact** — a trivia question with its answer.
- **Motivation** — a motivational quote.
- **Joke** — a kid-friendly joke.

All three categories use the same centered heading and content layout.

The generator selects the content type and entry based on the date, so the same date produces the same content.

The content pools currently contain 500 trivia entries, 500 quotes, and 500 jokes.

## GitHub Pages and PicPak

In the repository settings, enable Pages using:

- Source: GitHub Actions

The stable preview image remains available at:

`https://222phoenix.github.io/picpak_black/weather.png`

**For PicPak uploads, use the unique image URL instead.** Each workflow run creates a new filename containing the Pacific date, GitHub run ID, and run attempt. This prevents PicPak or an intermediary CDN from reusing an older image cached under the same URL.

The current unique URL is also written to:

`https://222phoenix.github.io/picpak_black/latest.json`

The GitHub Actions run summary prints the exact unique URL after generation. Copy that URL when adding the image to the PicPak My Agent queue.

## Important

The workflow generates and publishes the image, but does **not** automatically push it into PicPak. The image must currently be added to the PicPak My Agent queue separately. No supported public API for sending a generated image from GitHub Actions has been documented or configured.

## Local test

```bash
pip install Pillow
python generate.py
```

The result is `docs/weather.png`.

## Time

The generator uses Pacific time for the date and daily content selection. The GitHub Actions schedule runs around Pacific midnight.
