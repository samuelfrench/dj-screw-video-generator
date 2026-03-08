# DJ Screw Video Generator

RIP DJ Screw 1971-2000 TEXAS LEGEND

Automatically creates chopped & screwed versions of any YouTube music video.

## What it does

- Downloads any YouTube music video
- Slows to 0.55x speed (authentic DJ Screw tempo)
- Drops pitch via `asetrate` for that deep screwed sound
- Detects energy transitions and inserts chop zones (dip + phrase repeat)
- Adds purple tint, vignette, and darkened visuals
- Bass boost + echo + EQ matched to real screwed tapes
- Overlay silhouette + tribute text

## Requirements

```bash
pip install Pillow
```

- `ffmpeg` (with libx264, aac)
- `yt-dlp`
- Python 3.8+

## Usage

```bash
# Screw any YouTube video
python make_screwed.py "https://www.youtube.com/watch?v=VIDEO_ID"

# With custom title
python make_screwed.py "https://www.youtube.com/watch?v=VIDEO_ID" --title "Artist - Song"

# Skip intro (cut first N seconds before processing)
python make_screwed.py "https://www.youtube.com/watch?v=VIDEO_ID" --skip 5
```

## How it works

1. Downloads the video via yt-dlp
2. Analyzes RMS energy to find chop points (energy jumps > 4dB)
3. Inserts chop zones from last to first (preserves timestamps):
   - Brief volume dip (~0.35s "record lift")
   - Phrase repeat (3-4s segment replayed 2-3x)
4. Applies screw effects: slow + pitch drop + purple + bass + echo

Chop technique based on analysis of real DJ Screw mixes (S.O.S. Band, Guerilla Maab).

## Configuration

Edit the constants at the top of `make_screwed.py`:

- `SCREW_RATE` — speed multiplier (default 0.55)
- `DIP_DURATION` — length of volume dip in seconds
- `DIP_VOLUME` — volume during dip (0.15 = ~15dB drop)
- `PHRASE_LEN_MAJOR` / `PHRASE_LEN_MINOR` — phrase repeat lengths
