#!/usr/bin/env python3
"""
DJ Screw version of "I Don't Get Tired" by Kevin Gates.
Slowed + chopped + purple tint + overlay image = classic screwed video.

Chop technique based on analysis of real DJ Screw mixes:
- S.O.S. Band - No One's Gonna Love You
- Guerilla Maab - Fondren and Main
"""

import subprocess
import json
import re
import sys
import os
import time
from pathlib import Path

# --- Config ---
BASE_DIR = Path("/home/sam/claude-workspace/game-videos")
OVERLAY_IMG = BASE_DIR / "screwed_overlay.png"
YT_DLP = "/home/sam/miniconda3/bin/yt-dlp"
SCREW_RATE = 0.55  # 55% speed — authentic DJ Screw (1.8x longer)

# Set per-song via CLI args or defaults
ORIGINAL = None
OUTPUT = None
SONG_TITLE = None
YT_URL = None

# Chop parameters (derived from real DJ Screw analysis)
BACKSPIN_DURATION = 0.25  # seconds — reverse audio to simulate turntable backspin
ECHO_DECAY = 0.15         # echo decay amount (lower = less echo, cleaner sound)
PHRASE_LEN_MAJOR = 4.0  # seconds — phrase length for major chops
PHRASE_LEN_MINOR = 3.0  # seconds — phrase length for minor chops


def download_video():
    """Step 1: Download the music video."""
    if ORIGINAL.exists():
        print(f"Original video already exists: {ORIGINAL}")
        return
    print(f"Downloading {SONG_TITLE}...")
    cmd = [
        YT_DLP,
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
        "-o", str(ORIGINAL),
        "--merge-output-format", "mp4",
        YT_URL,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"yt-dlp error: {result.stderr[-500:]}")
        sys.exit(1)
    print(f"Downloaded: {ORIGINAL}")


def generate_overlay():
    """Step 2: Generate drowsy/leaning overlay image.

    Uses ollama with image generation if available, otherwise creates
    a stylized purple silhouette programmatically with PIL.
    """
    if OVERLAY_IMG.exists():
        print(f"Overlay image already exists: {OVERLAY_IMG}")
        return

    print("Generating overlay image...")
    from PIL import Image, ImageDraw, ImageFilter
    import random

    random.seed(42)
    W, H = 400, 500
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw a stylized silhouette of person leaning/slouching
    # Purple-tinted figure with smoky edges
    purple = (120, 40, 180)
    dark_purple = (60, 15, 90)

    # Head (slightly tilted/drooping)
    head_cx, head_cy = 200, 100
    draw.ellipse([head_cx-40, head_cy-45, head_cx+35, head_cy+40], fill=purple)

    # Body (leaning back)
    body_points = [
        (160, 140),  # left shoulder
        (245, 145),  # right shoulder
        (260, 320),  # right hip (leaning)
        (235, 420),  # right leg
        (200, 460),  # between legs
        (155, 430),  # left leg
        (140, 310),  # left hip
    ]
    draw.polygon(body_points, fill=purple)

    # Arms (one drooping down, one resting)
    # Left arm hanging
    draw.line([(160, 155), (120, 250), (110, 340)], fill=purple, width=28)
    # Right arm resting on leg
    draw.line([(240, 155), (270, 250), (250, 340)], fill=purple, width=28)

    # Add some purple glow/smoke around the figure
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for _ in range(60):
        x = random.randint(80, 320)
        y = random.randint(50, 450)
        r = random.randint(15, 60)
        alpha = random.randint(15, 50)
        pr = random.randint(80, 160)
        pb = random.randint(120, 220)
        glow_draw.ellipse([x-r, y-r, x+r, y+r], fill=(pr, 20, pb, alpha))

    # Blur the glow for smoky effect
    glow = glow.filter(ImageFilter.GaussianBlur(radius=15))

    # Composite: glow behind figure
    result = Image.alpha_composite(glow, img)

    # Apply gaussian blur to the whole thing for that hazy look
    result = result.filter(ImageFilter.GaussianBlur(radius=3))

    # Reduce overall opacity
    pixels = result.load()
    for y in range(H):
        for x in range(W):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (r, g, b, min(a, 180))

    result.save(str(OVERLAY_IMG))
    print(f"Overlay saved: {OVERLAY_IMG}")


def get_duration(filepath):
    """Get video/audio duration in seconds."""
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(filepath)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(json.loads(result.stdout)['format']['duration'])
    except (KeyError, json.JSONDecodeError) as e:
        print(f"    WARNING: ffprobe failed for {filepath}")
        print(f"    stderr: {result.stderr[-500:]}")
        print(f"    stdout: {result.stdout[:500]}")
        raise RuntimeError(f"Cannot get duration for {filepath}: {e}")


def detect_chop_points(filepath):
    """Find all significant energy transitions for chop/phrase-repeat insertion.

    Scans RMS energy in 1-second bins, finds rises of >4 dB vs the previous
    3-second average. Returns the top 6-8, spaced at least 15s apart.

    Returns list of (timestamp, magnitude) tuples sorted by time.
    """
    print("Analyzing audio for chop point detection...")

    cmd = [
        "ffmpeg", "-i", str(filepath), "-af",
        "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    levels = []
    current_time = 0.0
    for line in (result.stderr + result.stdout).split('\n'):
        time_match = re.search(r'pts_time:(\d+\.?\d*)', line)
        if time_match:
            current_time = float(time_match.group(1))
        rms_match = re.search(r'lavfi\.astats\.Overall\.RMS_level=(-?\d+\.?\d*)', line)
        if rms_match:
            rms = float(rms_match.group(1))
            if rms > -100:
                levels.append((current_time, rms))

    if not levels:
        print("  No audio data, using default chop points")
        return [(30.0, 8.0), (75.0, 6.0), (120.0, 6.0), (165.0, 7.0), (210.0, 5.0)]

    duration = get_duration(filepath)
    bin_size = 1.0
    num_bins = int(duration / bin_size) + 1
    bins = [-100.0] * num_bins

    for t, rms in levels:
        idx = min(int(t / bin_size), num_bins - 1)
        bins[idx] = max(bins[idx], rms)

    # Find energy jumps: current bin vs average of previous 3 bins
    jumps = []
    for i in range(3, num_bins):
        lookback = min(3, i)
        prev_avg = sum(bins[i - lookback:i]) / lookback
        jump = bins[i] - prev_avg
        if jump > 4.0:
            jumps.append((i * bin_size, jump))

    # Lower threshold if too few found
    if len(jumps) < 3:
        for i in range(3, num_bins):
            lookback = min(3, i)
            prev_avg = sum(bins[i - lookback:i]) / lookback
            jump = bins[i] - prev_avg
            if 2.0 < jump <= 4.0:
                jumps.append((i * bin_size, jump))

    if not jumps:
        print("  No energy transitions found, using evenly spaced points")
        spacing = duration / 7
        return [(spacing * i, 5.0) for i in range(1, 7)]

    # Sort by magnitude (strongest first), pick top with 10s minimum spacing
    # Real DJ Screw mixes have frequent backspins — aim for one every 10-20s
    jumps.sort(key=lambda x: -x[1])
    selected = []
    for t, mag in jumps:
        if t < 8.0 or t > duration - 8.0:
            continue
        if all(abs(t - st) >= 10.0 for st, _ in selected):
            selected.append((t, mag))
            if len(selected) >= 14:
                break

    selected.sort(key=lambda x: x[0])

    # Fill gaps — ensure backspins every ~15s throughout the track
    gap_fill_spacing = 15.0
    t = 10.0
    while t < duration - 8.0:
        if all(abs(t - st) >= 10.0 for st, _ in selected):
            selected.append((t, 3.0))
        t += gap_fill_spacing
    selected.sort(key=lambda x: x[0])

    print(f"  Found {len(selected)} chop points:")
    for t, mag in selected:
        print(f"    {t:.1f}s (energy jump: +{mag:.1f} dB)")

    return selected


def build_chop_zone(input_path, output_path, chop_time, magnitude, median_mag):
    """Run one ffmpeg pass to insert a backspin + phrase repeat at chop_time.

    Real DJ Screw turntable technique:
    1. Backspin (~0.25s of reversed audio) — physically spinning the record back
    2. Phrase repeat (3-4s segment before chop, played 2-3x)
    3. Resume from chop point

    Timeline: [pre] [backspin] [phrase x repeats] [post from chop_time]
    """
    # Vary params based on magnitude (major vs minor chop)
    if magnitude > median_mag:
        phrase_len = PHRASE_LEN_MAJOR
        repeats = 3  # play phrase 3 times total (2 extra)
    else:
        phrase_len = PHRASE_LEN_MINOR
        repeats = 2  # play phrase 2 times total (1 extra)

    # Phrase comes from just before chop point
    phrase_start = max(0.1, chop_time - phrase_len)
    phrase_end = chop_time
    actual_phrase_len = phrase_end - phrase_start

    # Backspin: take audio from just before the phrase zone and reverse it
    backspin_end = phrase_start
    backspin_start = max(0.05, backspin_end - BACKSPIN_DURATION)

    # Number of splits: pre + backspin + phrase*repeats + post
    n_splits = 1 + 1 + repeats + 1
    filter_parts = []

    # Split streams
    v_outs = "".join(f"[v{i}]" for i in range(n_splits))
    a_outs = "".join(f"[a{i}]" for i in range(n_splits))
    filter_parts.append(f"[0:v]split={n_splits}{v_outs}")
    filter_parts.append(f"[0:a]asplit={n_splits}{a_outs}")

    idx = 0
    concat_v = []
    concat_a = []

    # Pre section (unchanged)
    filter_parts.append(f"[v{idx}]trim=0:{backspin_start},setpts=PTS-STARTPTS[vpre]")
    filter_parts.append(f"[a{idx}]atrim=0:{backspin_start},asetpts=PTS-STARTPTS[apre]")
    concat_v.append("[vpre]")
    concat_a.append("[apre]")
    idx += 1

    # Backspin section — reverse the audio to simulate turntable backspin
    filter_parts.append(
        f"[v{idx}]trim={backspin_start}:{backspin_end},setpts=PTS-STARTPTS,"
        f"reverse[vspin]"
    )
    filter_parts.append(
        f"[a{idx}]atrim={backspin_start}:{backspin_end},asetpts=PTS-STARTPTS,"
        f"areverse[aspin]"
    )
    concat_v.append("[vspin]")
    concat_a.append("[aspin]")
    idx += 1

    # Phrase repeats (the classic DJ Screw "rewind and replay")
    for r in range(repeats):
        label = f"ph{r}"
        filter_parts.append(
            f"[v{idx}]trim={phrase_start}:{phrase_end},setpts=PTS-STARTPTS[v{label}]"
        )
        filter_parts.append(
            f"[a{idx}]atrim={phrase_start}:{phrase_end},asetpts=PTS-STARTPTS[a{label}]"
        )
        concat_v.append(f"[v{label}]")
        concat_a.append(f"[a{label}]")
        idx += 1

    # Post section (resumes from chop point)
    filter_parts.append(f"[v{idx}]trim={chop_time},setpts=PTS-STARTPTS[vpost]")
    filter_parts.append(f"[a{idx}]atrim={chop_time},asetpts=PTS-STARTPTS[apost]")
    concat_v.append("[vpost]")
    concat_a.append("[apost]")

    # Normalize all audio segments to stereo before concat (prevents channel layout errors)
    normalized_a = []
    for i, alabel in enumerate(concat_a):
        # Strip brackets for filter naming
        name = alabel.strip('[]')
        norm_name = f"anorm{i}"
        filter_parts.append(f"{alabel}aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[{norm_name}]")
        normalized_a.append(f"[{norm_name}]")

    # Concat all sections
    n_parts = len(concat_v)
    filter_parts.append(f"{''.join(concat_v)}concat=n={n_parts}:v=1:a=0[vout]")
    filter_parts.append(f"{''.join(normalized_a)}concat=n={n_parts}:v=0:a=1[aout]")

    filtergraph = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-filter_complex", filtergraph,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "256k",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"    Chop zone error:\n{result.stderr[-1500:]}")
        sys.exit(1)

    # Verify output is valid
    if not Path(output_path).exists():
        print(f"    Error: output file does not exist")
        sys.exit(1)
    fsize = Path(output_path).stat().st_size
    if fsize < 1000:
        print(f"    Error: output file too small ({fsize} bytes)")
        sys.exit(1)

    kind = "major" if magnitude > median_mag else "minor"
    extra = repeats - 1
    print(f"    {kind}: backspin + {actual_phrase_len:.1f}s phrase x{repeats} (+{extra * actual_phrase_len:.1f}s)")


def generate_intro(song_title, duration=20):
    """Generate a DJ Screw-style intro using real Screw voice samples.

    Uses pre-downloaded DJ Screw voice clips over a dark purple screen.
    The voice is screwed (slowed + pitch down + echo) for authenticity.
    Returns path to the intro video clip, or None if voice samples missing.
    """
    slug = slugify(song_title)
    intro_path = BASE_DIR / f"intro_{slug}.mp4"
    if intro_path.exists():
        return intro_path

    print("Generating DJ Screw intro with real voice samples...")

    # Use pre-built intro if available, otherwise build from voice samples
    prebuilt = BASE_DIR / "screw_intro_real.mp4"
    if prebuilt.exists():
        import shutil
        shutil.copy2(str(prebuilt), str(intro_path))
        print(f"  Intro ready: {get_duration(intro_path):.1f}s")
        return intro_path

    # Build from voice sample clips
    voice_file = BASE_DIR / "screw_intro_voice.wav"
    if not voice_file.exists():
        print("  No DJ Screw voice samples found. Run with voice clips first.")
        return None

    font = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    intro_filter = (
        f"color=c=0x1a0a2e:s=1280x720:d={duration},"
        f"drawtext=fontfile={font}:text=DJ SCREW:fontsize=72:"
        f"fontcolor=0xBB66EE@0.9:x=(w-text_w)/2:y=(h-text_h)/2-40:"
        f"shadowcolor=black@0.7:shadowx=2:shadowy=2,"
        f"drawtext=fontfile={font}:text=CHOPPED AND SCREWED:fontsize=36:"
        f"fontcolor=0x9944CC@0.7:x=(w-text_w)/2:y=(h-text_h)/2+50:"
        f"shadowcolor=black@0.5:shadowx=1:shadowy=1,"
        f"vignette=PI/3[vintro];"
        f"[0:a]asetrate=44100*0.55,aresample=44100,"
        f"aecho=0.7:0.8:40:0.2,"
        f"equalizer=f=50:t=q:w=0.7:g=5,"
        f"equalizer=f=200:t=q:w=1:g=3,"
        f"equalizer=f=2000:t=q:w=1:g=-4,"
        f"apad=whole_dur={duration}[aintro]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(voice_file),
        "-filter_complex", intro_filter,
        "-map", "[vintro]", "-map", "[aintro]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "256k",
        "-shortest",
        str(intro_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"  Intro video error: {r.stderr[-500:]}")
        return None

    print(f"  Intro generated: {get_duration(intro_path):.1f}s")
    return intro_path


def concat_intro(intro_path, main_path, output_path):
    """Concatenate intro clip with main screwed video."""
    # Normalize both to same format before concat
    norm_intro = BASE_DIR / "intro_norm.mp4"
    norm_main = BASE_DIR / "main_norm.mp4"

    for src, dst in [(intro_path, norm_intro), (main_path, norm_main)]:
        r = subprocess.run([
            "ffmpeg", "-y", "-i", str(src),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:a", "aac", "-b:a", "256k", "-ar", "44100", "-ac", "2",
            "-video_track_timescale", "90000",
            str(dst)
        ], capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print(f"  Normalize error: {r.stderr[-500:]}")
            return False

    concat_file = BASE_DIR / "intro_concat.txt"
    concat_file.write_text(f"file '{norm_intro}'\nfile '{norm_main}'\n")

    r = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy", "-movflags", "+faststart",
        str(output_path)
    ], capture_output=True, text=True, timeout=120)

    norm_intro.unlink(missing_ok=True)
    norm_main.unlink(missing_ok=True)
    concat_file.unlink(missing_ok=True)

    return r.returncode == 0


def build_screwed_video(chop_points):
    """Apply chopped & screwed effects.

    Pass 1: Multi-pass chopping — one ffmpeg pass per chop point (last to first)
             Each pass inserts: brief dip + phrase repeat (real DJ Screw technique)
    Pass 2: Screw effects (slow + purple + overlay + audio processing)
    """
    print(f"\nBuilding screwed video with {len(chop_points)} chop zones...")

    # === Pass 1: Insert chop zones ===
    # Note: ORIGINAL is already H.264 (transcoded in main() Step 1c if needed)
    print("Pass 1: Creating chopped version with phrase repeats...")

    magnitudes = [m for _, m in chop_points]
    median_mag = sorted(magnitudes)[len(magnitudes) // 2]

    # Process from last to first to preserve earlier timestamps
    sorted_points = list(reversed(chop_points))
    current_input = str(ORIGINAL)

    for zone_idx, (chop_time, magnitude) in enumerate(sorted_points):
        zone_num = len(sorted_points) - zone_idx
        print(f"  Chop zone {zone_num}/{len(chop_points)} at {chop_time:.1f}s...")

        slug = slugify(SONG_TITLE)
        output_path = str(BASE_DIR / f"chop_pass_{slug}_{zone_idx}.mp4")
        build_chop_zone(current_input, output_path, chop_time, magnitude, median_mag)

        # Clean up previous intermediate (but never the original)
        if current_input != str(ORIGINAL):
            Path(current_input).unlink(missing_ok=True)
        current_input = output_path
        print(f"    Duration: {get_duration(current_input):.1f}s")

    # Rename final intermediate for Pass 2
    intermediate = BASE_DIR / f"chopped_intermediate_{slugify(SONG_TITLE)}.mp4"
    if intermediate.exists():
        intermediate.unlink()
    Path(current_input).rename(intermediate)

    print(f"  Chopped total: {get_duration(intermediate):.1f}s")

    # === Pass 2: Apply screw effects + overlay ===
    print("Pass 2: Applying screw effects (slow + purple + overlay)...")

    # Video: slow + purple tint + vignette + darken + title card + silhouette overlay
    # Audio: pitch down + echo + bass boost
    font = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    screw_filter = (
        f"[0:v]setpts=PTS/{SCREW_RATE},"
        f"colorbalance=rs=0.15:gs=-0.05:bs=0.25:rh=0.1:bh=0.2,"
        f"vignette=PI/4,"
        f"eq=brightness=-0.05:saturation=0.9,"
        f"drawtext=fontfile={font}:text='INSPIRED BY DJ SCREW 1971–2000':fontsize=28:"
        f"fontcolor=0xBB66EE@0.7:x=20:y=h-80:shadowcolor=black@0.5:shadowx=1:shadowy=1,"
        f"drawtext=fontfile={font}:text='TEXAS LEGEND. Keeping the dream alive. Praise Jesus.':fontsize=22:"
        f"fontcolor=0x9944CC@0.6:x=20:y=h-45:shadowcolor=black@0.5:shadowx=1:shadowy=1"
        f"[vscrewed];"
        f"[1:v]scale=-1:ih/5,format=rgba,colorchannelmixer=aa=0.4[ovr];"
        f"[vscrewed][ovr]overlay=W-w-20:H-h-20[vfinal];"
        f"[0:a]asetrate=44100*0.65,"
        f"aresample=44100,"
        f"atempo={SCREW_RATE/0.65},"
        f"aecho=0.8:0.9:35:{ECHO_DECAY},"
        f"equalizer=f=50:t=q:w=0.7:g=7,"
        f"equalizer=f=120:t=q:w=1:g=4,"
        f"equalizer=f=400:t=q:w=1.5:g=-2,"
        f"equalizer=f=1000:t=q:w=1.5:g=-3,"
        f"equalizer=f=3000:t=q:w=1:g=-1,"
        f"equalizer=f=6000:t=q:w=1:g=0,"
        f"loudnorm=I=-13:TP=-0.3:LRA=9[ascrewed]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(intermediate),
        "-i", str(OVERLAY_IMG),
        "-filter_complex", screw_filter,
        "-map", "[vfinal]",
        "-map", "[ascrewed]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart",
        str(OUTPUT),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if result.returncode != 0:
        print(f"Pass 2 error:\n{result.stderr[-1500:]}")
        sys.exit(1)

    # Cleanup intermediate
    intermediate.unlink(missing_ok=True)

    print(f"\nOutput: {OUTPUT}")
    final_dur = get_duration(OUTPUT)
    size_mb = os.path.getsize(OUTPUT) / (1024 * 1024)
    orig_dur = get_duration(ORIGINAL)
    print(f"Duration: {final_dur:.1f}s ({final_dur/60:.1f} min)")
    print(f"Size: {size_mb:.1f} MB")
    print(f"Duration ratio: {final_dur / orig_dur:.2f}x (target ~2.0-2.4x with chops)")


def slugify(text):
    """Convert text to a safe filename slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s-]+', '_', text)
    return text[:60]


def main():
    global ORIGINAL, OUTPUT, SONG_TITLE, YT_URL, SCREW_RATE, ECHO_DECAY

    import argparse
    parser = argparse.ArgumentParser(description="DJ Screw any music video")
    parser.add_argument("url", nargs="?",
                        default="ytsearch1:Kevin Gates I Don't Get Tired official video",
                        help="YouTube URL or search query")
    parser.add_argument("--title", default=None,
                        help="Song title (auto-detected if not provided)")
    parser.add_argument("--skip", type=float, default=0,
                        help="Skip first N seconds of the video (cut intro)")
    parser.add_argument("--speed", type=float, default=None,
                        help="Override screw speed (default 0.55, lower = slower)")
    parser.add_argument("--echo", type=float, default=None,
                        help="Echo decay (default 0.15, lower = less echo)")
    parser.add_argument("--intro", action="store_true",
                        help="Add DJ Screw spoken intro (leaned out rambling)")
    args = parser.parse_args()

    YT_URL = args.url
    if args.speed is not None:
        SCREW_RATE = args.speed
    if args.echo is not None:
        global ECHO_DECAY
        ECHO_DECAY = args.echo

    # Auto-detect title from YouTube if not provided
    if args.title:
        SONG_TITLE = args.title
    else:
        print("Detecting song title...")
        r = subprocess.run([YT_DLP, "--get-title", YT_URL],
                           capture_output=True, text=True, timeout=30)
        SONG_TITLE = r.stdout.strip() if r.returncode == 0 else "Unknown Track"

    slug = slugify(SONG_TITLE)
    ORIGINAL = BASE_DIR / f"{slug}_original.mp4"
    OUTPUT = BASE_DIR / f"{slug}_screwed.mp4"

    print(f"=== DJ Screw - {SONG_TITLE} ===\n")

    # Step 1: Download
    download_video()

    # Step 1b: Trim intro if --skip specified
    if args.skip > 0:
        trimmed = ORIGINAL.with_suffix('.trimmed.mp4')
        if not trimmed.exists():
            print(f"Trimming first {args.skip}s...")
            r = subprocess.run([
                "ffmpeg", "-y", "-ss", str(args.skip), "-i", str(ORIGINAL),
                "-c", "copy", "-avoid_negative_ts", "make_zero", str(trimmed)
            ], capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                print(f"Trim error: {r.stderr[-500:]}")
                sys.exit(1)
        ORIGINAL = trimmed
        print(f"  Trimmed to {get_duration(ORIGINAL):.1f}s")

    # Step 1c: Transcode to H264 if needed (AV1 causes issues with split/trim filters)
    probe_cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(ORIGINAL)]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    streams = json.loads(probe_result.stdout).get('streams', [])
    video_codec = next((s['codec_name'] for s in streams if s['codec_type'] == 'video'), 'unknown')
    if video_codec != 'h264':
        h264_path = ORIGINAL.with_suffix('.h264.mp4')
        if not h264_path.exists():
            print(f"Transcoding from {video_codec} to H264 (required for chop filters)...")
            r = subprocess.run([
                "ffmpeg", "-y", "-i", str(ORIGINAL),
                "-vf", "scale='min(1920,iw)':-2",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-g", "15", "-keyint_min", "15",
                "-c:a", "aac", "-b:a", "256k", "-ac", "2",
                "-movflags", "+faststart",
                str(h264_path)
            ], capture_output=True, text=True, timeout=900)
            if r.returncode != 0:
                print(f"Transcode error: {r.stderr[-500:]}")
                sys.exit(1)
        ORIGINAL = h264_path
        print(f"  Using H264 version: {get_duration(ORIGINAL):.1f}s")

    # Step 2: Generate overlay
    generate_overlay()

    # Step 3: Detect chop points (multiple energy transitions)
    chop_points = detect_chop_points(ORIGINAL)

    # Step 4 & 5: Build screwed video with all effects
    build_screwed_video(chop_points)

    # Step 6: Add spoken intro if requested
    if args.intro:
        intro_path = generate_intro(SONG_TITLE)
        if intro_path:
            print("Adding intro to screwed video...")
            final_with_intro = OUTPUT.with_suffix('.with_intro.mp4')
            if concat_intro(intro_path, OUTPUT, final_with_intro):
                OUTPUT.unlink()
                final_with_intro.rename(OUTPUT)
                intro_path.unlink(missing_ok=True)
                final_dur = get_duration(OUTPUT)
                size_mb = os.path.getsize(OUTPUT) / (1024 * 1024)
                print(f"Final with intro: {final_dur:.1f}s ({final_dur/60:.1f} min), {size_mb:.1f} MB")
            else:
                print("  Failed to add intro, keeping video without it")

    print("\nDone! Screwed video ready.")


if __name__ == "__main__":
    main()
