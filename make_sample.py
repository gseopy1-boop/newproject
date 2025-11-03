
from pathlib import Path
from datetime import datetime
from automation.trends import get_daily_keywords
from automation.prompt_builder import build_image_prompt
from automation.caption_builder import build_caption
from app.media.image_gen import generate_image_with_reference

ROOT = Path(__file__).resolve().parent
Path(ROOT/'output/images').mkdir(parents=True, exist_ok=True)

kws = get_daily_keywords(limit=30)[:3] or ['memory','light','city']
prompt_dict = build_image_prompt(kws, theme_hint=None, seed=42, locale='ko')
caption = build_caption(kws, theme_hint=prompt_dict['theme_key'], seed=42)

ts = datetime.now().strftime('%Y%m%d_%H%M%S')
out = ROOT / f'output/images/sample_{ts}.jpg'
img = generate_image_with_reference(prompt=prompt_dict['prompt'], reference_img_path=None)
img.convert('RGB').save(out, 'JPEG', quality=90)

print('keywords :', ", ".join(kws))
print('theme    :', prompt_dict['theme_key'])
print('image    :', out)
print('caption  :', caption.splitlines()[0][:120] + '...')
