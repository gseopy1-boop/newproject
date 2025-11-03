from app.media.image_gen import generate_image_with_reference

img = generate_image_with_reference(
    prompt="기억의 파동 · 빛 신호 · 도시 리듬, retro pc mood",
    reference_img_path=None  # 있으면 경로 문자열로 교체
)
img.convert("RGB").save("output/images/_quick_test.jpg", "JPEG", quality=90)
print("saved: output/images/_quick_test.jpg")
