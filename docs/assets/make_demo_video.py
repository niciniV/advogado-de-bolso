from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = ROOT / "docs" / "assets"
CAPTURES = ASSET_DIR / "captures"
TMP_FRAMES = ASSET_DIR / "_demo_frames"
OUT_MP4 = ASSET_DIR / "advogado-de-bolso-demo.mp4"

W, H = 1280, 720
FPS = 60
FADE_FRAMES = 24

SCENES = [
    {
        "file": "01-home-dashboard.png",
        "title": "Painel inicial",
        "subtitle": "Casos recentes, guias rapidos e entrada para uma nova consulta.",
        "duration": 3.2,
        "crop": (150, 75, 1290, 735),
    },
    {
        "file": "02-new-consultation.png",
        "title": "Nova consulta",
        "subtitle": "O usuario descreve o problema de consumo em linguagem natural.",
        "duration": 2.7,
        "crop": (90, 190, 1350, 950),
    },
    {
        "file": "03-real-answer.png",
        "title": "Resposta real do backend",
        "subtitle": "A espera da IA foi cortada; o video salta direto para a resposta validada.",
        "duration": 5.6,
        "crop": (150, 90, 1265, 770),
    },
    {
        "file": "05-cases-list.png",
        "title": "Caso persistido",
        "subtitle": "A consulta vira um caso salvo para continuar depois.",
        "duration": 3.2,
        "crop": (150, 70, 1265, 315),
    },
    {
        "file": "06-preferences.png",
        "title": "Preferencias e seguranca",
        "subtitle": "Estilo de resposta, base de conhecimento, citacoes e revisao ativa.",
        "duration": 3.6,
        "crop": (145, 90, 1268, 740),
    },
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


TITLE = font(34, bold=True)
BODY = font(18)
LABEL = font(14, bold=True)


def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * t)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def make_background(scene_idx: int) -> Image.Image:
    bg = Image.new("RGB", (W, H), "#f8f4ef")
    draw = ImageDraw.Draw(bg)
    for y in range(H):
        ratio = y / H
        draw.line((0, y, W, y), fill=(248 - int(7 * ratio), 244 - int(8 * ratio), 239))
    accents = [
        ((-140, -170, 460, 390), "#d6e3ff"),
        ((940, 340, 1510, 900), "#002147"),
        ((-170, 460, 260, 900), "#fff6df"),
    ]
    for idx, (box, color) in enumerate(accents):
        if idx == scene_idx % 3 or idx == 1:
            draw.ellipse(box, fill=color)
    return bg.filter(ImageFilter.GaussianBlur(18))


def prepare_screen(path: Path, crop: tuple[int, int, int, int]) -> Image.Image:
    img = Image.open(path).convert("RGB")
    cropped = img.crop(crop)
    max_w, max_h = 1160, 530
    scale = min(max_w / cropped.width, max_h / cropped.height)
    target_w = int(cropped.width * scale)
    target_h = int(cropped.height * scale)
    screen = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS).convert("RGBA")
    mask = rounded_mask(screen.size, 24)
    screen.putalpha(mask)
    return screen


def draw_screen(canvas: Image.Image, screen: Image.Image) -> tuple[int, int]:
    x = (W - screen.width) // 2
    y = 158 + max(0, (530 - screen.height) // 2)
    shadow = Image.new("RGBA", screen.size, (0, 0, 0, 120))
    shadow.putalpha(screen.getchannel("A").filter(ImageFilter.GaussianBlur(18)))
    canvas.alpha_composite(shadow, (x, y + 15))
    canvas.alpha_composite(screen, (x, y))
    return x, y

def draw_caption(canvas: Image.Image, title: str, subtitle: str, t: float, progress: float) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    enter = ease_out(min(t / 0.35, 1))
    y_shift = int((1 - enter) * -28)
    panel = (46, 32 + y_shift, W - 46, 130 + y_shift)
    draw.rounded_rectangle(panel, radius=26, fill=(0, 33, 71, 235))
    draw.text((82, 54 + y_shift), title, fill="#ffffff", font=TITLE)
    draw.text((84, 96 + y_shift), subtitle, fill="#d6e3ff", font=BODY)
    draw.text((W - 224, 62 + y_shift), "Advogado de Bolso", fill="#aec7f6", font=LABEL)
    bar_w = int((W - 164) * progress)
    draw.rounded_rectangle((82, 121 + y_shift, 82 + bar_w, 126 + y_shift), radius=4, fill="#aec7f6")


def scene_frame(scene_idx: int, local: int, count: int, progress: float, screen: Image.Image) -> Image.Image:
    scene = SCENES[scene_idx]
    t = local / max(count - 1, 1)
    canvas = make_background(scene_idx).convert("RGBA")
    draw_screen(canvas, screen)
    draw_caption(canvas, scene["title"], scene["subtitle"], t, progress)
    return canvas.convert("RGB")


def blend(a: Image.Image, b: Image.Image, alpha: float) -> Image.Image:
    return Image.blend(a, b, ease_in_out(alpha))


def render() -> None:
    if TMP_FRAMES.exists():
        shutil.rmtree(TMP_FRAMES)
    TMP_FRAMES.mkdir(parents=True)

    screens = [prepare_screen(CAPTURES / scene["file"], scene["crop"]) for scene in SCENES]
    scene_counts = [int(scene["duration"] * FPS) for scene in SCENES]
    total_frames = sum(scene_counts) - FADE_FRAMES * (len(SCENES) - 1)

    frame_no = 0
    prev_tail: list[Image.Image] = []
    for scene_idx, count in enumerate(scene_counts):
        frames = [
            scene_frame(scene_idx, local, count, frame_no / max(total_frames - 1, 1), screens[scene_idx])
            for local in range(count)
        ]

        if scene_idx == 0:
            emit = frames
        else:
            emit = [
                blend(prev_tail[i], frames[i], (i + 1) / FADE_FRAMES) for i in range(FADE_FRAMES)
            ] + frames[FADE_FRAMES:]

        if scene_idx < len(SCENES) - 1:
            prev_tail = emit[-FADE_FRAMES:]
            emit = emit[:-FADE_FRAMES]

        for frame in emit:
            frame.save(TMP_FRAMES / f"frame_{frame_no:05d}.png", compress_level=2)
            frame_no += 1

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(TMP_FRAMES / "frame_%05d.png"),
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(OUT_MP4),
        ],
        check=True,
    )
    shutil.rmtree(TMP_FRAMES)


if __name__ == "__main__":
    render()
