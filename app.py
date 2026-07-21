import os
import random
import subprocess
import tempfile
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# --- FONT PATHS (update if deploying to Linux server) ---
FONT_PATH       = "/Library/Fonts/TikTokSans-Medium.ttf"
EMOJI_FONT_PATH = "/System/Library/Fonts/Apple Color Emoji.ttc"

# --- TEXT VARIATIONS ---
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
    ("\U0001F6A8", "\U0001F6A8"),
    ("\U000026A1", "\U000026A1"),
    ("\U0001F525", "\U0001F525"),
    ("\U0001F4A5", "\U0001F4A5"),
    ("\U000023F0", "\U000023F0"),
]

# --- DESIGN CONSTANTS ---
CANVAS_W, CANVAS_H = 1080, 1920
RED_COLOR   = (220, 30, 45, 255)
WHITE_COLOR = (255, 255, 255, 255)
BLACK_COLOR = (0, 0, 0, 255)
RED_FONT    = 88;  RED_PAD_X  = 52;  RED_PAD_Y  = 28;  RED_RADIUS  = 14
WHITE_FONT  = 60;  WHITE_PAD_X= 36;  WHITE_PAD_Y= 18;  WHITE_RADIUS= 12
PROD_FONT   = 58;  PROD_GAP   = 20;  PROD_STROKE= 7
BADGE_TOP   = int(CANVAS_H * 0.115)


def make_banner_overlay(product_name, out_path, sale_text, urgency_text, emoji_pair):
    img  = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        font_red   = ImageFont.truetype(FONT_PATH, RED_FONT)
        font_white = ImageFont.truetype(FONT_PATH, WHITE_FONT)
        font_prod  = ImageFont.truetype(FONT_PATH, PROD_FONT)
    except IOError:
        font_red = font_white = font_prod = ImageFont.load_default()

    def text_size(text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    red_tw, red_th = text_size(sale_text, font_red)
    wht_tw, wht_th = text_size(urgency_text, font_white)

    emoji_size = 96; emoji_gap = 12
    has_emoji  = False; emoji_w = 0
    emoji_left, emoji_right = emoji_pair
    try:
        font_emoji = ImageFont.truetype(EMOJI_FONT_PATH, emoji_size, index=0)
        eb = draw.textbbox((0, 0), emoji_left, font=font_emoji)
        emoji_w = eb[2] - eb[0]
        has_emoji = True
    except Exception:
        pass

    content_w  = (emoji_w + emoji_gap + red_tw + emoji_gap + emoji_w) if has_emoji else red_tw
    red_pill_w = content_w + RED_PAD_X * 2;   red_pill_h = red_th + RED_PAD_Y * 2
    wht_pill_w = wht_tw + WHITE_PAD_X * 2;    wht_pill_h = wht_th + WHITE_PAD_Y * 2
    red_pill_x = (CANVAS_W - red_pill_w) // 2; wht_pill_x = (CANVAS_W - wht_pill_w) // 2
    red_pill_y = BADGE_TOP;                    wht_pill_y = red_pill_y + red_pill_h

    draw.rounded_rectangle([red_pill_x, red_pill_y, red_pill_x+red_pill_w, red_pill_y+red_pill_h],
                            radius=RED_RADIUS, fill=RED_COLOR)
    draw.rounded_rectangle([wht_pill_x, wht_pill_y, wht_pill_x+wht_pill_w, wht_pill_y+wht_pill_h],
                            radius=WHITE_RADIUS, fill=WHITE_COLOR)

    cy = red_pill_y + red_pill_h // 2
    if has_emoji:
        lx = red_pill_x + RED_PAD_X
        draw.text((lx, cy), emoji_left, font=font_emoji, embedded_color=True, anchor="lm")
        draw.text((lx + emoji_w + emoji_gap, cy), sale_text, font=font_red, fill=WHITE_COLOR, anchor="lm")
        draw.text((lx + emoji_w + emoji_gap + red_tw + emoji_gap, cy), emoji_right,
                  font=font_emoji, embedded_color=True, anchor="lm")
    else:
        draw.text((red_pill_x + red_pill_w // 2, cy), sale_text, font=font_red, fill=WHITE_COLOR, anchor="mm")

    draw.text((wht_pill_x + wht_pill_w // 2, wht_pill_y + wht_pill_h // 2),
              urgency_text, font=font_white, fill=BLACK_COLOR, anchor="mm")
    draw.text((CANVAS_W // 2, wht_pill_y + wht_pill_h + PROD_GAP), product_name,
              font=font_prod, fill=WHITE_COLOR, stroke_width=PROD_STROKE,
              stroke_fill=BLACK_COLOR, anchor="mt")
    img.save(out_path, "PNG")


def process_video(input_path, overlay_path, output_path):
    filter_complex = (
        "[0:v]split[original][copy];"
        "[copy]reverse[reversed];"
        "[original][reversed]concat=n=2:v=1:a=0[v_loop];"
        "[1:v][v_loop]scale2ref[overlay][base];"
        "[base][overlay]overlay=0:0[v_final]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", overlay_path,
        "-filter_complex", filter_complex,
        "-map", "[v_final]",
        "-c:v", "libx264",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)


# ── Streamlit UI ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Scrap & Roll Video Editor", page_icon="🎬", layout="centered")

st.title("🎬 Scrap & Roll Auto Editor")
st.markdown("Upload a product video, enter the name, and download the edited version ready to post.")

product_name = st.text_input("Product Name", placeholder="e.g. HiSmile Mouthwash")
uploaded     = st.file_uploader("Upload Video (MP4 or MOV, max 20MB)", type=["mp4", "mov"])

if st.button("✨ Process Video", disabled=not (product_name and uploaded)):
    with st.spinner("Processing... this takes about 10–15 seconds"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Save uploaded video
            input_path   = os.path.join(tmp_dir, uploaded.name)
            overlay_path = os.path.join(tmp_dir, "overlay.png")
            output_path  = os.path.join(tmp_dir, "output.mp4")

            with open(input_path, "wb") as f:
                f.write(uploaded.read())

            # Pick random combos
            sale_text    = random.choice(SALE_TEXTS)
            urgency_text = random.choice(URGENCY_TEXTS)
            emoji_pair   = random.choice(EMOJI_PAIRS)

            try:
                make_banner_overlay(product_name, overlay_path, sale_text, urgency_text, emoji_pair)
                process_video(input_path, overlay_path, output_path)

                with open(output_path, "rb") as f:
                    video_bytes = f.read()

                st.success(f"✅ Done!  Used: {emoji_pair[0]} **{sale_text}** | **{urgency_text}**")
                st.video(video_bytes)
                st.download_button(
                    label="⬇️ Download Video",
                    data=video_bytes,
                    file_name=f"{product_name.replace(' ', '_')}_edited.mp4",
                    mime="video/mp4"
                )

            except subprocess.CalledProcessError as e:
                st.error("FFmpeg failed. Make sure FFmpeg is installed on the server.")
            except Exception as e:
                st.error(f"Error: {e}")
