# PicPak Daily Weather Card

Generates a 400×300 PNG for a PicPak frame.

## What it does

Every day the GitHub Action:

1. Gets Alameda, California hourly weather from the National Weather Service API.
2. Creates morning/noon/night rows with weather icons.
3. Alternates between a daily trivia question with its answer and a motivational quote.
4. Saves the result as `docs/weather.png`.
5. Commits the updated image so GitHub Pages can publish it.

## Daily content

- Even-numbered days: trivia question and answer.
- Odd-numbered days: motivational quote.

The trivia pool currently contains 50 Q&A entries. The selected entry rotates by date through the collection.

## GitHub Pages

In the repository settings, enable Pages using:

- Source: GitHub Actions

The image will then be available at:

`https://222phoenix.github.io/picpak_black/weather.png`

That URL is suitable for PicPak's `push_image` once the repository is public and Pages is active.

## Important

The workflow generates and publishes the image, but does **not** automatically push it into PicPak. PicPak's ChatGPT tool accepts a public image URL, but a standalone PicPak API endpoint/credential suitable for GitHub Actions has not been established.

## Local test

```bash
pip install Pillow
python generate.py
```

The result is `docs/weather.png`.

## Time

GitHub Actions schedules use UTC. The included schedule targets approximately 7 AM Pacific Standard Time. During daylight saving time, change `15:00 UTC` to `14:00 UTC`.
