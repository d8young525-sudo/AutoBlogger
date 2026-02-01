"""
스티커 감정 분류 스크립트
collect_stickers.py로 수집한 이미지를 Gemini 비전으로 분류하여 sticker_map.json 생성.

사용법:
    python tools/classify_stickers.py

필요:
    - GEMINI_API_KEY 환경변수
    - assets/stickers/{pack_name}/ 폴더에 개별 스티커 이미지
"""
import json
import logging
import os
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets" / "stickers"

# 분류할 감정 카테고리
EMOTION_CATEGORIES = [
    "happy",       # 기쁨, 즐거움, 축하
    "sad",         # 슬픔, 아쉬움
    "surprised",   # 놀람, 충격
    "angry",       # 화남, 불만
    "love",        # 사랑, 좋아함
    "thinking",    # 생각, 고민
    "greeting",    # 인사, 환영
    "goodbye",     # 작별, 마무리
    "excited",     # 흥분, 신남
    "tired",       # 피곤, 지침
    "neutral",     # 중립, 일반
]


def classify_pack(pack_dir: Path, api_key: str) -> list:
    """한 팩의 모든 스티커를 Gemini 비전으로 분류"""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    sticker_files = sorted(pack_dir.glob("sticker_*.png"), key=lambda p: int(p.stem.split("_")[1]))

    if not sticker_files:
        logger.warning(f"  {pack_dir.name}: 스티커 이미지 없음")
        return []

    results = []
    # 배치 처리 (5개씩 묶어서 API 호출 절약)
    batch_size = 5

    for batch_start in range(0, len(sticker_files), batch_size):
        batch = sticker_files[batch_start:batch_start + batch_size]

        # 이미지들을 하나의 요청으로 묶기
        contents = []
        indices = []

        for img_path in batch:
            idx = int(img_path.stem.split("_")[1])
            indices.append(idx)

            img_data = img_path.read_bytes()
            contents.append(types.Part.from_bytes(data=img_data, mime_type="image/png"))

        prompt_text = f"""이 {len(batch)}개의 스티커 이미지를 순서대로 감정/상황으로 분류해주세요.

각 이미지에 대해 다음 카테고리 중 가장 적합한 것을 1~2개 선택:
{', '.join(EMOTION_CATEGORIES)}

JSON 배열로만 응답 (다른 텍스트 없이):
[{{"index": 0, "emotions": ["happy", "excited"]}}, ...]

index는 이미지 순서 (0부터)입니다."""

        contents.append(types.Part.from_text(text=prompt_text))

        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[types.Content(parts=contents, role="user")],
            )

            # JSON 파싱
            response_text = response.text.strip()
            # ```json ... ``` 블록 제거
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            batch_results = json.loads(response_text)

            for item in batch_results:
                order = item.get("index", 0)
                if order < len(indices):
                    actual_idx = indices[order]
                    emotions = item.get("emotions", ["neutral"])
                    results.append({
                        "index": actual_idx,
                        "emotions": emotions
                    })

            logger.info(f"  분류 완료: 스티커 {indices[0]}~{indices[-1]}")

        except json.JSONDecodeError as e:
            logger.warning(f"  JSON 파싱 실패: {e}, 응답: {response_text[:200]}")
            # 실패한 배치는 neutral로 처리
            for idx in indices:
                results.append({"index": idx, "emotions": ["neutral"]})

        except Exception as e:
            logger.error(f"  Gemini API 오류: {e}")
            for idx in indices:
                results.append({"index": idx, "emotions": ["neutral"]})

        # API rate limit 대응
        time.sleep(1)

    return results


def main():
    # .env 파일에서 로드 시도
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    os.environ.setdefault("GEMINI_API_KEY", val)

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("GEMINI_API_KEY 환경변수가 설정되지 않았습니다. (.env 파일 또는 환경변수)")
        return

    # raw_data.json 읽기
    raw_data_path = ASSETS_DIR / "raw_data.json"
    if not raw_data_path.exists():
        logger.error(f"{raw_data_path} 파일이 없습니다. collect_stickers.py를 먼저 실행하세요.")
        return

    with open(raw_data_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    sticker_map = {
        "version": "1.0",
        "classified_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "packs": {}
    }

    packs_data = raw_data.get("packs", {})
    for pack_name, pack_info in packs_data.items():
        pack_dir = ASSETS_DIR / pack_name

        if not pack_dir.exists():
            logger.warning(f"팩 디렉토리 없음: {pack_dir}")
            continue

        logger.info(f"팩 분류 중: {pack_name} ({pack_info['sticker_count']}개)")

        results = classify_pack(pack_dir, api_key)

        sticker_map["packs"][pack_name] = {
            "sticker_count": pack_info["sticker_count"],
            "sprite_url": pack_info["sprite_url"],
            "stickers": results
        }

    # sticker_map.json 저장
    map_path = ASSETS_DIR / "sticker_map.json"
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(sticker_map, f, ensure_ascii=False, indent=2)

    total_stickers = sum(len(p["stickers"]) for p in sticker_map["packs"].values())
    logger.info(f"\n분류 완료!")
    logger.info(f"  총 팩: {len(sticker_map['packs'])}")
    logger.info(f"  총 스티커: {total_stickers}")
    logger.info(f"  저장: {map_path}")


if __name__ == "__main__":
    main()
