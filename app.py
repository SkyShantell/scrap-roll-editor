import io
import os
import random
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ── App paths ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
FONT_PATH = BASE_DIR / "TikTokSans-Medium.ttf"
MUSIC_FOLDER = BASE_DIR / "music"
EMOJI_ASSET_FOLDER = BASE_DIR / "emoji_assets"

# Streamlit Cloud/Linux font, followed by macOS fallbacks for local testing.
EMOJI_FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"),
    Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
    Path("/Library/Fonts/Apple Color Emoji.ttc"),
]

SUPPORTED_MUSIC_FORMATS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}

# The PNG filenames should match the Apple-style assets generated on the Mac.
EMOJI_OPTIONS = [
    ("🚨", "alert.png"),
    ("⚡", "lightning.png"),
    ("🔥", "fire.png"),
    ("💥", "boom.png"),
    ("⏰", "clock.png"),
]

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

# Requested settings.
EMOJI_RENDER_SIZE = 80
MUSIC_VOLUME = 1.0


def run_command(command: list[str]) -> subprocess.CompletedProcess:
    """Run FFmpeg/FFprobe and expose useful error information."""
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "FFmpeg or FFprobe is missing. Confirm packages.txt is in the "
            "GitHub repository root and contains the line: ffmpeg"
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "Unknown FFmpeg error").strip()
        raise RuntimeError(details[-5000:]) from exc


def load_text_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except (OSError, IOError):
        return ImageFont.load_default()


def find_emoji_font() -> Path | None:
    for font_path in EMOJI_FONT_CANDIDATES:
        if font_path.exists():
            return font_path
    return None


def load_emoji_image(emoji: str, asset_filename: str) -> Image.Image | None:
    """
    Prefer an Apple-style transparent PNG from emoji_assets.
    If unavailable, render the installed color emoji font and resize to 80px.
    """
    asset_path = EMOJI_ASSET_FOLDER / asset_filename

    if asset_path.exists():
        try:
            image = Image.open(asset_path).convert("RGBA")
            image.thumbnail(
                (EMOJI_RENDER_SIZE, EMOJI_RENDER_SIZE),
                Image.Resampling.LANCZOS,
            )
            return image
        except Exception:
            pass

    font_path = find_emoji_font()
    if not font_path:
        return None

    try:
        # Noto Color Emoji commonly renders only at its embedded 109px strike.
        emoji_font = ImageFont.truetype(str(font_path), 109, index=0)
        temp = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp)
        bbox = temp_draw.textbbox((0, 0), emoji, font=emoji_font)

        x = 90 - ((bbox[2] - bbox[0]) // 2) - bbox[0]
        y = 90 - ((bbox[3] - bbox[1]) // 2) - bbox[1]

        temp_draw.text(
            (x, y),
            emoji,
            font=emoji_font,
            embedded_color=True,
        )

        alpha_bbox = temp.getbbox()
        if not alpha_bbox:
            return None

        cropped = temp.crop(alpha_bbox)
        cropped.thumbnail(
            (EMOJI_RENDER_SIZE, EMOJI_RENDER_SIZE),
            Image.Resampling.LANCZOS,
        )
        return cropped
    except Exception:
        return None


def make_banner_overlay(
    product_name: str,
    out_path: str,
    sale_text: str,
    urgency_text: str,
    emoji: str,
    emoji_asset: str,
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

    emoji_image = load_emoji_image(emoji, emoji_asset)
    emoji_gap = 18

    if emoji_image:
        emoji_w, emoji_h = emoji_image.size
        content_width = emoji_w + emoji_gap + red_text_w + emoji_gap + emoji_w
        red_content_h = max(red_text_h, emoji_h)
    else:
        emoji_w = emoji_h = 0
        content_width = red_text_w
        red_content_h = red_text_h

    red_pill_w = content_width + (RED_PAD_X * 2)
    red_pill_h = red_content_h + (RED_PAD_Y * 2)
    white_pill_w = white_text_w + (WHITE_PAD_X * 2)
    white_pill_h = white_text_h + (WHITE_PAD_Y * 2)

    red_pill_x = (CANVAS_W - red_pill_w) // 2
    white_pill_x = (CANVAS_W - white_pill_w) // 2
    red_pill_y = BADGE_TOP
    white_pill_y = red_pill_y + red_pill_h

    draw.rounded_rectangle(
        (
            red_pill_x,
            red_pill_y,
            red_pill_x + red_pill_w,
            red_pill_y + red_pill_h,
        ),
        radius=RED_RADIUS,
        fill=RED_COLOR,
    )

    draw.rounded_rectangle(
        (
            white_pill_x,
            white_pill_y,
            white_pill_x + white_pill_w,
            white_pill_y + white_pill_h,
        ),
        radius=WHITE_RADIUS,
        fill=WHITE_COLOR,
    )

    red_center_y = red_pill_y + (red_pill_h // 2)

    if emoji_image:
        cursor_x = red_pill_x + RED_PAD_X
        emoji_y = red_center_y - (emoji_h // 2)

        img.alpha_composite(emoji_image, (cursor_x, emoji_y))
        cursor_x += emoji_w + emoji_gap

        draw.text(
            (cursor_x, red_center_y),
            sale_text,
            font=font_red,
            fill=WHITE_COLOR,
            anchor="lm",
        )
        cursor_x += red_text_w + emoji_gap
        img.alpha_composite(emoji_image, (cursor_x, emoji_y))
    else:
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
        (CANVAS_W // 2, white_pill_y + white_pill_h + PROD_GAP),
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
        raise RuntimeError("Could not determine the video duration.") from exc

    if duration <= 0:
        raise RuntimeError("The uploaded video has an invalid duration.")

    return duration


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
            "No songs were found. Create a folder named music beside app.py "
            "and place the audio files inside it."
        )

    previous_song = st.session_state.get("last_song")
    choices = [song for song in songs if song.name != previous_song]

    selected_song = random.choice(choices or songs)
    st.session_state["last_song"] = selected_song.name
    return selected_song


def process_video(
    input_path: str,
    overlay_path: str,
    music_path: str,
    output_path: str,
) -> None:
    source_duration = get_video_duration(input_path)
    finished_duration = source_duration * 2

    filter_complex = (
        f"[0:v]"
        f"scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,"
        f"crop={CANVAS_W}:{CANVAS_H},setsar=1,"
        f"split=2[forward][reverse_source];"
        f"[reverse_source]reverse[backward];"
        f"[forward][backward]concat=n=2:v=1:a=0[video_loop];"
        f"[1:v]format=rgba[overlay_image];"
        f"[video_loop][overlay_image]overlay=0:0:format=auto[v_final];"
        f"[2:a]"
        f"atrim=0:{finished_duration:.6f},"
        f"asetpts=PTS-STARTPTS,"
        f"volume={MUSIC_VOLUME:.3f},"
        f"alimiter=limit=0.95[a_final]"
    )

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


def safe_output_filename(product_name: str, index: int | None = None) -> str:
    """Create a safe, predictable MP4 filename."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", product_name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_") or "product"

    if index is not None:
        return f"{index:02d}_{cleaned}_edited.mp4"
    return f"{cleaned}_edited.mp4"


def uploaded_signature(files: list) -> tuple[tuple[str, int], ...]:
    return tuple((uploaded.name, int(uploaded.size)) for uploaded in files)


def create_zip_bytes(results: list[dict]) -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for result in results:
            archive.writestr(result["output_name"], result["video_bytes"])
    return zip_buffer.getvalue()


def process_uploaded_video(
    uploaded_file,
    product_name: str,
    temp_dir: str,
    item_index: int | None = None,
) -> dict:
    """Process one uploaded video and return its downloadable data."""
    prefix = f"{item_index:02d}_" if item_index is not None else ""
    safe_upload_name = Path(uploaded_file.name).name
    input_path = os.path.join(temp_dir, f"{prefix}{safe_upload_name}")
    overlay_path = os.path.join(temp_dir, f"{prefix}overlay.png")
    output_path = os.path.join(temp_dir, f"{prefix}output.mp4")

    with open(input_path, "wb") as file:
        file.write(uploaded_file.getbuffer())

    sale_text = random.choice(SALE_TEXTS)
    urgency_text = random.choice(URGENCY_TEXTS)
    emoji, emoji_asset = random.choice(EMOJI_OPTIONS)
    selected_song = choose_random_song()

    make_banner_overlay(
        product_name=product_name.strip(),
        out_path=overlay_path,
        sale_text=sale_text,
        urgency_text=urgency_text,
        emoji=emoji,
        emoji_asset=emoji_asset,
    )

    process_video(
        input_path=input_path,
        overlay_path=overlay_path,
        music_path=str(selected_song),
        output_path=output_path,
    )

    with open(output_path, "rb") as file:
        video_bytes = file.read()

    return {
        "source_name": uploaded_file.name,
        "product_name": product_name.strip(),
        "output_name": safe_output_filename(product_name, item_index),
        "video_bytes": video_bytes,
        "sale_text": sale_text,
        "urgency_text": urgency_text,
        "emoji": emoji,
        "song_name": selected_song.stem,
    }


# ── Streamlit UI ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Scrap & Roll Video Editor",
    page_icon="🎬",
    layout="centered",
)

st.title("🎬 Scrap & Roll Auto Editor")
st.markdown(
    "Process one video or upload a batch. Every video receives its own product "
    "name, random sale text, emoji, urgency text, and background song."
)

# Helpful deployment diagnostic.
missing_tools = [
    tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None
]
if missing_tools:
    st.error(
        "Server setup is incomplete. Missing: "
        + ", ".join(missing_tools)
        + ". Add packages.txt to the repository root and reboot the app."
    )

music_count = len(get_music_files())
if music_count:
    st.caption(f"🎵 {music_count} music track(s) available")
else:
    st.warning(
        "No music tracks found. Add the audio files to a folder named `music` "
        "beside `app.py`, then commit the folder to GitHub."
    )

mode = st.radio(
    "Processing mode",
    options=["Single video", "Bulk videos"],
    horizontal=True,
)

# ── Single-video mode ─────────────────────────────────────────────────────────
if mode == "Single video":
    product_name = st.text_input(
        "Product Name",
        placeholder="e.g. HiSmile Mouthwash",
        key="single_product_name",
    )

    uploaded = st.file_uploader(
        "Upload Video (MP4 or MOV)",
        type=["mp4", "mov"],
        key="single_uploader",
    )

    process_disabled = (
        not product_name.strip()
        or uploaded is None
        or music_count == 0
        or bool(missing_tools)
    )

    if st.button("✨ Process Video", disabled=process_disabled):
        st.session_state.pop("single_result", None)

        with st.spinner("Processing your video..."):
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    result = process_uploaded_video(
                        uploaded_file=uploaded,
                        product_name=product_name,
                        temp_dir=temp_dir,
                    )
                    result["input_signature"] = (uploaded.name, int(uploaded.size))
                    st.session_state["single_result"] = result
                except Exception as error:
                    st.error("The video could not be processed.")
                    with st.expander("Technical error details"):
                        st.code(str(error))

    single_result = st.session_state.get("single_result")
    current_signature = (
        (uploaded.name, int(uploaded.size)) if uploaded is not None else None
    )

    if (
        single_result
        and single_result.get("input_signature") == current_signature
        and single_result.get("product_name") == product_name.strip()
    ):
        st.success(
            f"✅ Done! Used {single_result['emoji']} "
            f"**{single_result['sale_text']}** | "
            f"**{single_result['urgency_text']}** | "
            f"🎵 **{single_result['song_name']}**"
        )
        st.video(single_result["video_bytes"])
        st.download_button(
            label="⬇️ Download Video",
            data=single_result["video_bytes"],
            file_name=single_result["output_name"],
            mime="video/mp4",
        )

# ── Bulk mode ─────────────────────────────────────────────────────────────────
else:
    st.info(
        "Upload multiple videos, then enter the correct product name for every "
        "video. All product-name fields are required."
    )

    uploaded_files = st.file_uploader(
        "Upload Videos (MP4 or MOV)",
        type=["mp4", "mov"],
        accept_multiple_files=True,
        key="bulk_uploader",
    )

    if uploaded_files:
        st.subheader("Product names")
        product_names: list[str] = []

        for index, uploaded_file in enumerate(uploaded_files, start=1):
            st.markdown(f"**{index}. {uploaded_file.name}**")
            product_name = st.text_input(
                f"Product name for video {index}",
                placeholder="Enter the product name shown in this video",
                key=f"bulk_product_{index}_{uploaded_file.name}_{uploaded_file.size}",
                label_visibility="collapsed",
            )
            product_names.append(product_name.strip())

        missing_name_numbers = [
            str(index)
            for index, name in enumerate(product_names, start=1)
            if not name
        ]

        if missing_name_numbers:
            st.caption(
                "Product name still needed for video(s): "
                + ", ".join(missing_name_numbers)
            )

        bulk_disabled = (
            bool(missing_name_numbers)
            or music_count == 0
            or bool(missing_tools)
        )

        if st.button(
            f"✨ Process All {len(uploaded_files)} Videos",
            disabled=bulk_disabled,
        ):
            st.session_state.pop("bulk_results", None)
            st.session_state.pop("bulk_errors", None)
            st.session_state.pop("bulk_zip", None)

            results: list[dict] = []
            errors: list[dict] = []
            progress = st.progress(0)
            status = st.empty()

            with tempfile.TemporaryDirectory() as temp_dir:
                total = len(uploaded_files)

                for index, (uploaded_file, product_name) in enumerate(
                    zip(uploaded_files, product_names),
                    start=1,
                ):
                    status.write(
                        f"Processing {index} of {total}: **{uploaded_file.name}**"
                    )

                    try:
                        result = process_uploaded_video(
                            uploaded_file=uploaded_file,
                            product_name=product_name,
                            temp_dir=temp_dir,
                            item_index=index,
                        )
                        results.append(result)
                    except Exception as error:
                        errors.append(
                            {
                                "source_name": uploaded_file.name,
                                "error": str(error),
                            }
                        )

                    progress.progress(index / total)

            status.empty()

            signature = uploaded_signature(uploaded_files)
            names_signature = tuple(product_names)

            st.session_state["bulk_results"] = {
                "items": results,
                "input_signature": signature,
                "names_signature": names_signature,
            }
            st.session_state["bulk_errors"] = {
                "items": errors,
                "input_signature": signature,
                "names_signature": names_signature,
            }

            if results:
                st.session_state["bulk_zip"] = {
                    "data": create_zip_bytes(results),
                    "input_signature": signature,
                    "names_signature": names_signature,
                }

        current_signature = uploaded_signature(uploaded_files)
        current_names_signature = tuple(product_names)
        bulk_results_state = st.session_state.get("bulk_results")
        bulk_errors_state = st.session_state.get("bulk_errors")
        bulk_zip_state = st.session_state.get("bulk_zip")

        signatures_match = (
            bulk_results_state
            and bulk_results_state.get("input_signature") == current_signature
            and bulk_results_state.get("names_signature") == current_names_signature
        )

        if signatures_match:
            results = bulk_results_state.get("items", [])
            errors = (
                bulk_errors_state.get("items", [])
                if bulk_errors_state
                else []
            )

            if results:
                st.success(
                    f"✅ Finished {len(results)} of {len(uploaded_files)} videos."
                )

                if (
                    bulk_zip_state
                    and bulk_zip_state.get("input_signature") == current_signature
                    and bulk_zip_state.get("names_signature")
                    == current_names_signature
                ):
                    st.download_button(
                        label="⬇️ Download All Videos as ZIP",
                        data=bulk_zip_state["data"],
                        file_name="scrap_roll_edited_videos.zip",
                        mime="application/zip",
                    )

                st.subheader("Individual downloads")
                for result in results:
                    with st.expander(
                        f"{result['product_name']} — {result['source_name']}"
                    ):
                        st.caption(
                            f"{result['emoji']} {result['sale_text']} | "
                            f"{result['urgency_text']} | "
                            f"🎵 {result['song_name']}"
                        )
                        st.video(result["video_bytes"])
                        st.download_button(
                            label=f"⬇️ Download {result['output_name']}",
                            data=result["video_bytes"],
                            file_name=result["output_name"],
                            mime="video/mp4",
                            key=f"download_{result['output_name']}",
                        )

            if errors:
                st.error(f"{len(errors)} video(s) could not be processed.")
                with st.expander("Failed-video details"):
                    for error_item in errors:
                        st.markdown(f"**{error_item['source_name']}**")
                        st.code(error_item["error"])
    else:
        st.caption("Add two or more videos to begin a bulk batch.")
