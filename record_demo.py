import os
import time
import subprocess
import imageio_ffmpeg
from playwright.sync_api import sync_playwright

def record_demo():
    print("Starting Playwright demo recording...")
    video_dir = os.path.abspath("demo_recording")
    os.makedirs(video_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=video_dir,
            record_video_size={"width": 1280, "height": 720}
        )
        page = context.new_page()

        print("Navigating to http://localhost:8080/ ...")
        page.goto("http://localhost:8080/", wait_until="networkidle")
        time.sleep(2)  # Pause to show clean welcome banner & prompt chips

        # Interaction 1: Click on the prompt chip "🌿 Plant Catalog" (doing what app does best)
        print("Executing Interaction 1: Click Plant Catalog prompt chip")
        chip = page.locator(".prompt-chip").first
        chip.click()

        # Wait for agent response bubble to appear
        page.wait_for_selector(".msg.agent", timeout=35000)
        print("Interaction 1 response received!")
        time.sleep(5)  # Pause for viewer to read catalog response

        # Interaction 2: Richer prompt showing off tool call, Firestore lookup & image generation
        print("Executing Interaction 2: Rich prompt for Monstera lookup and image generation")
        input_el = page.locator("#input")
        form_btn = page.locator("#form button")

        input_el.fill("Look up details for Monstera Deliciosa in our catalog and generate a visual preview image for it.")
        time.sleep(1)
        form_btn.click()

        # Wait for agent response and generated image
        print("Waiting for Interaction 2 response and generated image...")
        time.sleep(18)  # Wait for tool execution and image generation
        print("Interaction 2 complete!")
        time.sleep(6)  # Pause to view card & image

        video_path = page.video.path()
        context.close()
        browser.close()
        print("Raw recording saved at:", video_path)

    # Convert webm + overlay lofi_bg_music.wav to mp4 using imageio-ffmpeg
    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    output_mp4 = os.path.abspath("greenhouse_assistant_demo.mp4")
    music_wav = os.path.abspath("lofi_bg_music.wav")

    print(f"Merging video ({video_path}) and music ({music_wav}) into {output_mp4}...")
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", video_path,
        "-i", music_wav,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        output_mp4
    ]
    subprocess.run(cmd, check=True)
    print(f"SUCCESS! Final demo video created at: {output_mp4}")

if __name__ == "__main__":
    record_demo()
