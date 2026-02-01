"""
스프라이트 시트에서 개별 스티커 이미지 crop
assets/stickers/{pack}/sprite_sheet.png → assets/stickers/{pack}/sticker_0.png, ...

사용법:
    python tools/crop_stickers.py
"""
from PIL import Image
from pathlib import Path
import json

ASSETS_DIR = Path(__file__).parent.parent / "assets" / "stickers"


def crop_pack(pack_dir: Path) -> int:
    sprite_path = pack_dir / "sprite_sheet.png"
    if not sprite_path.exists():
        return 0

    img = Image.open(sprite_path)
    w, h = img.size
    pack_name = pack_dir.name

    # 네이버 스티커 피커: background-size 240px, 개별 80x74px → 3열
    cols = 3
    cell_w = w // cols
    cell_h = int(cell_w * 74 / 80)  # 80:74 비율 유지

    rows = h // cell_h if cell_h > 0 else 0

    idx = 0
    for row in range(rows):
        for col in range(cols):
            x = col * cell_w
            y = row * cell_h

            if x + cell_w > w or y + cell_h > h:
                continue

            box = (x, y, x + cell_w, y + cell_h)
            cropped = img.crop(box)

            # 빈 이미지 체크 (완전 투명이면 건너뛰기)
            if cropped.mode == "RGBA":
                alpha = cropped.split()[-1]
                if alpha.getbbox() is None:
                    continue

            out_path = pack_dir / f"sticker_{idx}.png"
            cropped.save(out_path)
            idx += 1

    return idx


def main():
    raw_data = {"packs": {}}

    for pack_dir in sorted(ASSETS_DIR.iterdir()):
        if not pack_dir.is_dir():
            continue

        pack_name = pack_dir.name
        sprite_path = pack_dir / "sprite_sheet.png"
        if not sprite_path.exists():
            continue

        img = Image.open(sprite_path)
        w, h = img.size

        count = crop_pack(pack_dir)

        cols = 3
        cell_w = w // cols
        cell_h = int(cell_w * 74 / 80)

        raw_data["packs"][pack_name] = {
            "sprite_size": [w, h],
            "cell_size": [cell_w, cell_h],
            "sticker_count": count,
            "sprite_url": f"https://storep-phinf.pstatic.net/{pack_name}/original_preview.png"
        }

        print(f"{pack_name}: {w}x{h}, cell={cell_w}x{cell_h}, {count} stickers")

    with open(ASSETS_DIR / "raw_data.json", "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)

    total = sum(p["sticker_count"] for p in raw_data["packs"].values())
    print(f"\n완료! 총 {len(raw_data['packs'])}개 팩, {total}개 스티커")
    print(f"raw_data.json 저장: {ASSETS_DIR / 'raw_data.json'}")


if __name__ == "__main__":
    main()
