import os
import random
import subprocess
import tempfile
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ── App paths ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
FONT_PATH = BASE_DIR / "TikTokSans-Medium.ttf"
MUSIC_FOLDER = BASE_DIR / "music"

# Linux/Streamlit Cloud emoji font, with macOS fallbacks for local testing.
EMOJI_FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"),
    Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
    Path("/Library/Fonts/Apple Color Emoji.ttc"),
]

SUPPORTED_MUSIC_FORMATS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}

# ── Text variations ───────────────────────────────────────────────────────────
SALE_TEXTS = [
    "HUGE SALE",
    "MASSIVE SALE",
    "HEAVY DISCOUNT",
    "MAJOR DEAL",
    "BIG SAVINGS",
]

URGENCY_TEXTS = [
    "ENDS SOON",
    "TODAY ONLY",
    "LIMITED TIME",
    "ALMOST GONE",
    "LAST CHANCE",
]

EMOJI_PAIRS = [
    ("🚨", "🚨"),
    ("⚡", "⚡"),
    ("🔥", "🔥"),
    ("💥", "💥"),
    ("⏰", "⏰"),
]

# ── Design constants ──────────────────────────────────────────────────────────
CANVAS_W, CANVAS_H = 1080, 1920
RED_COLOR = (220, 30, 45, 255)
WHITE_COLOR = (255, 255, 255, 255)
BLACK_COLOR = (0, 0, 0, 255)

RED_FONT = 88
RED_PAD_X = 52
RED_PAD_Y = 28
RED_RADIUS = 14

WHITE_FONT = 60
WHITE_PAD_X = 36
WHITE_PAD_Y = 18
WHITE_RADIUS = 12

PROD_FONT = 58
PROD_GAP = 20
PROD_STROKE = 7
BADGE_TOP = int(CANVAS_H * 0.115)


def run_command(command: list[str]) -> subprocess.CompletedProcess:
    """Run a command and include useful FFmpeg output when it fails."""
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "FFmpeg/FFprobe was not found. Make sure FFmpeg is installed."
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "Unknown FFmpeg error").strip()
        raise RuntimeError(details[-4000:]) from exc


def find_emoji_font() -> Path | None:
    for font_path in EMOJI_FONT_CANDIDATES:
        if font_path.exists():
            return font_path
    return None


def load_text_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except (OSError, IOError):
        return ImageFont.load_default()


def make_banner_overlay(
    product_name: str,
    out_path: str,
    sale_text: str,
    urgency_text: str,
    emoji_pair: tuple[str, str],
) -> None:
    img = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_red = load_text_font(RED_FONT)
    font_white = load_text_font(WHITE_FONT)
    font_product = load_text_font(PROD_FONT)

    def text_size(text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    red_text_w, red_text_h = text_size(sale_text, font_red)
    white_text_w, white_text_h = text_size(urgency_text, font_white)

    emoji_size = 96
    emoji_gap = 12
    emoji_width = 0
    emoji_font = None
    emoji_font_path = find_emoji_font()
    emoji_left, emoji_right = emoji_pair

    if emoji_font_path:
        try:
            emoji_font = ImageFont.truetype(str(emoji_font_path), emoji_size, index=0)
            emoji_box = draw.textbbox((0, 0), emoji_left, font=emoji_font)
            emoji_width = emoji_box[2] - emoji_box[0]
        except Exception:
            emoji_font = None

    if emoji_font:
        content_width = (
            emoji_width
            + emoji_gap
            + red_text_w
            + emoji_gap
            + emoji_width
        )
    else:
        content_width = red_text_w

    red_pill_w = content_width + (RED_PAD_X * 2)
    red_pill_h = red_text_h + (RED_PAD_Y * 2)
    white_pill_w = white_text_w + (WHITE_PAD_X * 2)
    white_pill_h = white_text_h + (WHITE_PAD_Y * 2)

    red_pill_x = (CANVAS_W - red_pill_w) // 2
    white_pill_x = (CANVAS_W - white_pill_w) // 2
    red_pill_y = BADGE_TOP
    white_pill_y = red_pill_y + red_pill_h

    draw.rounded_rectangle(
        [
            red_pill_x,
            red_pill_y,
            red_pill_x + red_pill_w,
            red_pill_y + red_pill_h,
        ],
        radius=RED_RADIUS,
        fill=RED_COLOR,
    )

    draw.rounded_rectangle(
        [
            white_pill_x,
            white_pill_y,
            white_pill_x + white_pill_w,
            white_pill_y + white_pill_h,
        ],
        radius=WHITE_RADIUS,
        fill=WHITE_COLOR,
    )

    red_center_y = red_pill_y + (red_pill_h // 2)

    if emoji_font:
        left_x = red_pill_x + RED_PAD_X
        draw.text(
            (left_x, red_center_y),
            emoji_left,
            font=emoji_font,
            embedded_color=True,
            anchor="lm",
        )
        draw.text(
            (left_x + emoji_width + emoji_gap, red_center_y),
            sale_text,
            font=font_red,
            fill=WHITE_COLOR,
            anchor="lm",
        )
        draw.text(
            (
                left_x
                + emoji_width
                + emoji_gap
                + red_text_w
                + emoji_gap,
                red_center_y,
            ),
            emoji_right,
            font=emoji_font,
            embedded_color=True,
            anchor="lm",
        )
    else:
        # Fall back to plain text if the server cannot render color emoji.
        draw.text(
            (red_pill_x + (red_pill_w // 2), red_center_y),
            sale_text,
            font=font_red,
            fill=WHITE_COLOR,
            anchor="mm",
        )

    draw.text(
        (
            white_pill_x + (white_pill_w // 2),
            white_pill_y + (white_pill_h // 2),
        ),
        urgency_text,
        font=font_white,
        fill=BLACK_COLOR,
        anchor="mm",
    )

    draw.text(
        (
            CANVAS_W // 2,
            white_pill_y + white_pill_h + PROD_GAP,
        ),
        product_name,
        font=font_product,
        fill=WHITE_COLOR,
        stroke_width=PROD_STROKE,
        stroke_fill=BLACK_COLOR,
        anchor="mt",
    )

    img.save(out_path, "PNG")


def get_video_duration(input_path: str) -> float:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            input_path,
        ]
    )

    try:
        duration = float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("Could not determine the uploaded video's duration.") from exc

    if duration <= 0:
        raise RuntimeError("The uploaded video has an invalid duration.")

    return duration


def video_has_audio(input_path: str) -> bool:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            input_path,
        ]
    )
    return bool(result.stdout.strip())


def get_music_files() -> list[Path]:
    if not MUSIC_FOLDER.exists():
        return []

    return sorted(
        file_path
        for file_path in MUSIC_FOLDER.iterdir()
        if file_path.is_file()
        and file_path.suffix.lower() in SUPPORTED_MUSIC_FORMATS
    )


def choose_random_song() -> Path:
    songs = get_music_files()

    if not songs:
        raise RuntimeError(
            "No songs were found. Create a folder named 'music' beside app.py "
            "and add your MP3, WAV, M4A, AAC, OGG, or FLAC files."
        )

    previous_song = st.session_state.get("last_song")
    choices = [song for song in songs if song.name != previous_song]

    # With only one song, reusing it is unavoidable.
    selected_song = random.choice(choices or songs)
    st.session_state["last_song"] = selected_song.name
    return selected_song


def process_video(
    input_path: str,
    overlay_path: str,
    music_path: str,
    output_path: str,
    music_volume: float,
    keep_original_audio: bool,
    original_audio_volume: float,
) -> None:
    source_duration = get_video_duration(input_path)
    finished_duration = source_duration * 2
    has_original_audio = video_has_audio(input_path)

    # The video is played forward and then reversed, matching the original app.
    video_filters = (
        f"[0:v]"
        f"scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,"
        f"crop={CANVAS_W}:{CANVAS_H},setsar=1,"
        f"split=2[forward][reverse_source];"
        f"[reverse_source]reverse[backward];"
        f"[forward][backward]concat=n=2:v=1:a=0[video_loop];"
        f"[1:v]format=rgba[overlay_image];"
        f"[video_loop][overlay_image]overlay=0:0:format=auto[v_final]"
    )

    music_filter = (
        f"[2:a]atrim=0:{finished_duration:.6f},"
        f"asetpts=PTS-STARTPTS,"
        f"volume={music_volume:.3f}[music]"
    )

    if keep_original_audio and has_original_audio:
        # Keep the source audio during the forward half. The reverse half uses
        # music only, avoiding duplicated or backwards speech.
        audio_filters = (
            f"{music_filter};"
            f"[0:a]atrim=0:{source_duration:.6f},"
            f"asetpts=PTS-STARTPTS,"
            f"volume={original_audio_volume:.3f},"
            f"apad=whole_dur={finished_duration:.6f},"
            f"atrim=0:{finished_duration:.6f}[original_audio];"
            f"[original_audio][music]"
            f"amix=inputs=2:duration=longest:dropout_transition=0,"
            f"alimiter=limit=0.95[a_final]"
        )
    else:
        audio_filters = f"{music_filter};[music]alimiter=limit=0.95[a_final]"

    filter_complex = f"{video_filters};{audio_filters}"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-loop",
        "1",
        "-i",
        overlay_path,
        "-stream_loop",
        "-1",
        "-i",
        music_path,
        "-filter_complex",
        filter_complex,
        "-map",
        "[v_final]",
        "-map",
        "[a_final]",
        "-t",
        f"{finished_duration:.6f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        output_path,
    ]

    run_command(command)


# ── Streamlit UI ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Scrap & Roll Video Editor",
    page_icon="🎬",
    layout="centered",
)

st.title("🎬 Scrap & Roll Auto Editor")
st.markdown(
    "Upload a product video, enter the product name, and download the edited "
    "version with a randomly selected background song."
)

music_count = len(get_music_files())
if music_count:
    st.caption(f"🎵 {music_count} music track(s) available")
else:
    st.warning(
        "No music tracks found yet. Add your 15 audio files to a folder named "
        "`music` beside `app.py`, then commit the folder to GitHub."
    )

product_name = st.text_input(
    "Product Name",
    placeholder="e.g. HiSmile Mouthwash",
)

uploaded = st.file_uploader(
    "Upload Video (MP4 or MOV, max 20MB)",
    type=["mp4", "mov"],
)

with st.expander("🎵 Audio settings"):
    music_volume_percent = st.slider(
        "Background music volume",
        min_value=0,
        max_value=100,
        value=18,
        step=1,
    )

    keep_original_audio = st.checkbox(
        "Keep original video audio",
        value=True,
        help=(
            "Original audio plays during the forward half. The randomly selected "
            "song continues through the entire finished video."
        ),
    )

    original_audio_percent = st.slider(
        "Original audio volume",
        min_value=0,
        max_value=100,
        value=100,
        step=1,
        disabled=not keep_original_audio,
    )

process_disabled = not (product_name.strip() and uploaded and music_count > 0)

if st.button("✨ Process Video", disabled=process_disabled):
    with st.spinner("Processing your video..."):
        with tempfile.TemporaryDirectory() as temp_dir:
            safe_upload_name = Path(uploaded.name).name
            input_path = os.path.join(temp_dir, safe_upload_name)
            overlay_path = os.path.join(temp_dir, "overlay.png")
            output_path = os.path.join(temp_dir, "output.mp4")

            with open(input_path, "wb") as file:
                file.write(uploaded.getbuffer())

            sale_text = random.choice(SALE_TEXTS)
            urgency_text = random.choice(URGENCY_TEXTS)
            emoji_pair = random.choice(EMOJI_PAIRS)
            selected_song = choose_random_song()

            try:
                make_banner_overlay(
                    product_name=product_name.strip(),
                    out_path=overlay_path,
                    sale_text=sale_text,
                    urgency_text=urgency_text,
                    emoji_pair=emoji_pair,
                )

                process_video(
                    input_path=input_path,
                    overlay_path=overlay_path,
                    music_path=str(selected_song),
                    output_path=output_path,
                    music_volume=music_volume_percent / 100,
                    keep_original_audio=keep_original_audio,
                    original_audio_volume=original_audio_percent / 100,
                )

                with open(output_path, "rb") as file:
                    video_bytes = file.read()

                st.success(
                    f"✅ Done! Used {emoji_pair[0]} **{sale_text}** | "
                    f"**{urgency_text}** | 🎵 **{selected_song.stem}**"
                )
                st.video(video_bytes)
                st.download_button(
                    label="⬇️ Download Video",
                    data=video_bytes,
                    file_name=(
                        f"{product_name.strip().replace(' ', '_')}_edited.mp4"
                    ),
                    mime="video/mp4",
                )

            except Exception as error:
                st.error("The video could not be processed.")
                with st.expander("Technical error details"):
                    st.code(str(error))
