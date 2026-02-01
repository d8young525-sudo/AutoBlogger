"""
네이버 에디터 스티커 수집 스크립트
1회 실행하여 스티커 팩별 이미지를 다운로드하고 개별 이미지로 crop합니다.

사용법:
    python tools/collect_stickers.py --id YOUR_NAVER_ID --pw YOUR_NAVER_PW

결과:
    assets/stickers/{pack_name}/  — 개별 스티커 이미지 (PNG)
    assets/stickers/raw_data.json — 수집 메타데이터
"""
import argparse
import json
import logging
import os
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets" / "stickers"


def create_driver():
    """Chrome WebDriver 생성"""
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def login_naver(driver, user_id: str, user_pw: str) -> bool:
    """네이버 로그인"""
    driver.get("https://nid.naver.com/nidlogin.login")
    time.sleep(2)

    try:
        import pyperclip
        # ID 입력
        id_input = driver.find_element(By.ID, "id")
        id_input.click()
        pyperclip.copy(user_id)
        id_input.send_keys("\ue009" + "v")  # Ctrl+V
        time.sleep(0.3)

        # PW 입력
        pw_input = driver.find_element(By.ID, "pw")
        pw_input.click()
        pyperclip.copy(user_pw)
        pw_input.send_keys("\ue009" + "v")  # Ctrl+V
        time.sleep(0.3)

        # 로그인 버튼
        login_btn = driver.find_element(By.ID, "log.login")
        login_btn.click()
        time.sleep(3)

        if "nid.naver.com" not in driver.current_url:
            logger.info("로그인 성공")
            return True
        else:
            logger.error("로그인 실패 — 캡차 또는 2차 인증 필요할 수 있습니다")
            logger.info("수동으로 로그인 후 Enter를 눌러주세요...")
            input()
            return True

    except Exception as e:
        logger.error(f"로그인 오류: {e}")
        logger.info("수동으로 로그인 후 Enter를 눌러주세요...")
        input()
        return True


def go_to_editor(driver) -> bool:
    """네이버 블로그 에디터 진입"""
    driver.get("https://blog.naver.com/tnlqofg?Redirect=Write&")
    time.sleep(3)

    # 임시저장 팝업 닫기
    try:
        cancel_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR,
                "button.se-popup-button-cancel, button.se-popup-button.se-popup-button-cancel"))
        )
        cancel_btn.click()
        time.sleep(1)
    except TimeoutException:
        pass

    # 도움말 패널 닫기
    try:
        close_btn = driver.find_element(By.CSS_SELECTOR, "button.se-help-panel-close-button")
        close_btn.click()
        time.sleep(0.5)
    except NoSuchElementException:
        pass

    logger.info("에디터 진입 완료")
    return True


def open_sticker_picker(driver) -> bool:
    """스티커 피커 열기"""
    try:
        sticker_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR,
                "button.se-sticker-toolbar-button, button[data-name='sticker']"))
        )
        sticker_btn.click()
        time.sleep(1.5)

        # 피커가 열렸는지 확인
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                ".se-sidebar-element-sticker, .se-sidebar-sticker"))
        )
        logger.info("스티커 피커 열림")
        return True

    except TimeoutException:
        logger.error("스티커 피커 열기 실패")
        return False


def collect_pack_tabs(driver) -> list:
    """스티커 팩 탭 목록 수집"""
    tabs = driver.find_elements(By.CSS_SELECTOR,
        "ul.se-sidebar-list.se-is-on li.se-sidebar-item")

    if not tabs:
        # 대안 셀렉터
        tabs = driver.find_elements(By.CSS_SELECTOR,
            ".se-panel-side-bar li button, .se-sidebar-item button")

    logger.info(f"스티커 팩 탭 {len(tabs)}개 발견")
    return tabs


def extract_stickers_from_current_pack(driver) -> dict:
    """현재 열린 팩에서 스티커 정보 추출"""
    sticker_buttons = driver.find_elements(By.CSS_SELECTOR,
        "button.se-sidebar-element.se-sidebar-element-sticker")

    if not sticker_buttons:
        sticker_buttons = driver.find_elements(By.CSS_SELECTOR,
            "button[data-log='lsk.attach']")

    pack_data = {
        "pack_name": "",
        "sprite_url": "",
        "stickers": []
    }

    for btn in sticker_buttons:
        try:
            # span.se-sidebar-sticker에서 background-image 추출
            sticker_span = btn.find_element(By.CSS_SELECTOR, "span.se-sidebar-sticker")
            bg_image = sticker_span.value_of_css_property("background-image")
            bg_position = sticker_span.value_of_css_property("background-position")

            # se-blind에서 이름 추출
            try:
                blind_span = btn.find_element(By.CSS_SELECTOR, "span.se-blind")
                sticker_name = blind_span.text
            except NoSuchElementException:
                sticker_name = ""

            data_index = btn.get_attribute("data-index") or ""
            data_animated = btn.get_attribute("data-animated") or "false"

            # URL 추출
            url_match = re.search(r'url\("?([^")\s]+)"?\)', bg_image)
            sprite_url = url_match.group(1) if url_match else ""

            if sprite_url and not pack_data["sprite_url"]:
                pack_data["sprite_url"] = sprite_url
                # 팩 이름 추출 (URL에서)
                pack_match = re.search(r'pstatic\.net/([^/]+)/', sprite_url)
                if pack_match:
                    pack_data["pack_name"] = pack_match.group(1)

            # background-position 파싱 (예: "0px -74px" → (0, 74))
            pos_match = re.findall(r'(-?\d+)px', bg_position)
            pos_x = int(pos_match[0]) if len(pos_match) > 0 else 0
            pos_y = int(pos_match[1]) if len(pos_match) > 1 else 0

            pack_data["stickers"].append({
                "index": data_index,
                "name": sticker_name,
                "pos_x": abs(pos_x),
                "pos_y": abs(pos_y),
                "animated": data_animated == "true"
            })

        except Exception as e:
            logger.warning(f"스티커 추출 실패: {e}")
            continue

    return pack_data


def download_and_crop_stickers(pack_data: dict) -> int:
    """스프라이트 시트 다운로드 후 개별 스티커로 crop"""
    pack_name = pack_data["pack_name"]
    sprite_url = pack_data["sprite_url"]
    stickers = pack_data["stickers"]

    if not pack_name or not sprite_url or not stickers:
        logger.warning(f"팩 데이터 불충분: {pack_name}")
        return 0

    # 원본 해상도 스프라이트 시트 URL (p100_100 제거)
    original_url = re.sub(r'\?type=p\d+_\d+', '', sprite_url)

    pack_dir = ASSETS_DIR / pack_name
    pack_dir.mkdir(parents=True, exist_ok=True)

    # 스프라이트 시트 다운로드
    try:
        resp = requests.get(original_url, timeout=30)
        if resp.status_code != 200:
            # type 파라미터 포함 URL로 재시도
            resp = requests.get(sprite_url, timeout=30)
        resp.raise_for_status()

        sprite_image = Image.open(BytesIO(resp.content))
        sprite_image.save(pack_dir / "sprite_sheet.png")
        logger.info(f"[{pack_name}] 스프라이트 시트 다운로드: {sprite_image.size}")

    except Exception as e:
        logger.error(f"[{pack_name}] 스프라이트 다운로드 실패: {e}")
        return 0

    # 개별 스티커 crop
    # 피커 표시 크기: 80x74px, 스프라이트 시트는 원본 비율로 더 클 수 있음
    # 스프라이트 시트의 열 수 계산
    sprite_w, sprite_h = sprite_image.size

    if not stickers:
        return 0

    # position 값에서 그리드 크기 추정
    max_x = max(s["pos_x"] for s in stickers) if stickers else 0
    max_y = max(s["pos_y"] for s in stickers) if stickers else 0

    # CSS 크기 (피커 표시: 240px background-size, 80x74 개별)
    css_cell_w = 80
    css_cell_h = 74
    css_total_w = 240  # background-size: 240px auto

    # 실제 이미지와 CSS 사이의 비율 계산
    if max_x > 0:
        cols = (max_x // css_cell_w) + 1
    else:
        cols = 3  # 기본 3열

    scale = sprite_w / css_total_w if css_total_w > 0 else 1
    cell_w = int(css_cell_w * scale)
    cell_h = int(css_cell_h * scale)

    cropped_count = 0
    for sticker in stickers:
        try:
            x = int(sticker["pos_x"] * scale)
            y = int(sticker["pos_y"] * scale)

            box = (x, y, min(x + cell_w, sprite_w), min(y + cell_h, sprite_h))
            cropped = sprite_image.crop(box)

            idx = sticker["index"]
            output_path = pack_dir / f"sticker_{idx}.png"
            cropped.save(output_path)
            cropped_count += 1

        except Exception as e:
            logger.warning(f"[{pack_name}] 스티커 {sticker['index']} crop 실패: {e}")

    logger.info(f"[{pack_name}] {cropped_count}개 스티커 이미지 저장")
    return cropped_count


def collect_all_packs(driver) -> list:
    """모든 팩을 순회하며 스티커 수집"""
    all_packs = []

    # 첫 번째 팩 (이미 열려있음) 수집
    logger.info("현재 팩 수집 중...")
    pack_data = extract_stickers_from_current_pack(driver)
    if pack_data["stickers"]:
        count = download_and_crop_stickers(pack_data)
        pack_data["cropped_count"] = count
        all_packs.append(pack_data)
        logger.info(f"팩 '{pack_data['pack_name']}': {len(pack_data['stickers'])}개 스티커")

    # 팩 탭 순회
    tabs = collect_pack_tabs(driver)

    for i in range(len(tabs)):
        try:
            # 탭을 다시 찾기 (DOM이 변경될 수 있음)
            tabs = collect_pack_tabs(driver)
            if i >= len(tabs):
                break

            tab = tabs[i]

            # 이미 수집한 첫 번째 팩이면 건너뛰기
            if i == 0 and all_packs:
                continue

            # 탭의 버튼 클릭
            try:
                btn = tab.find_element(By.CSS_SELECTOR, "button")
                btn.click()
            except NoSuchElementException:
                tab.click()

            time.sleep(1)

            logger.info(f"팩 탭 {i + 1}/{len(tabs)} 수집 중...")
            pack_data = extract_stickers_from_current_pack(driver)

            if pack_data["stickers"]:
                # 중복 체크
                if any(p["pack_name"] == pack_data["pack_name"] for p in all_packs):
                    logger.info(f"  이미 수집된 팩: {pack_data['pack_name']}, 건너뜀")
                    continue

                count = download_and_crop_stickers(pack_data)
                pack_data["cropped_count"] = count
                all_packs.append(pack_data)
                logger.info(f"팩 '{pack_data['pack_name']}': {len(pack_data['stickers'])}개 스티커")

        except Exception as e:
            logger.warning(f"팩 탭 {i} 수집 실패: {e}")
            continue

    return all_packs


def main():
    parser = argparse.ArgumentParser(description="네이버 에디터 스티커 수집")
    parser.add_argument("--id", required=True, help="네이버 아이디")
    parser.add_argument("--pw", required=True, help="네이버 비밀번호")
    args = parser.parse_args()

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    driver = None
    try:
        driver = create_driver()
        driver.maximize_window()

        # 로그인
        if not login_naver(driver, args.id, args.pw):
            return

        # 에디터 진입
        if not go_to_editor(driver):
            return

        # 스티커 피커 열기
        if not open_sticker_picker(driver):
            return

        # 모든 팩 수집
        all_packs = collect_all_packs(driver)

        # raw_data.json 저장
        raw_data = {
            "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_packs": len(all_packs),
            "packs": []
        }

        for pack in all_packs:
            raw_data["packs"].append({
                "pack_name": pack["pack_name"],
                "sprite_url": pack["sprite_url"],
                "sticker_count": len(pack["stickers"]),
                "cropped_count": pack.get("cropped_count", 0),
                "stickers": pack["stickers"]
            })

        raw_data_path = ASSETS_DIR / "raw_data.json"
        with open(raw_data_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2)

        logger.info(f"\n수집 완료!")
        logger.info(f"  총 팩 수: {len(all_packs)}")
        logger.info(f"  총 스티커 수: {sum(len(p['stickers']) for p in all_packs)}")
        logger.info(f"  저장 위치: {ASSETS_DIR}")
        logger.info(f"  메타데이터: {raw_data_path}")

    except KeyboardInterrupt:
        logger.info("사용자 중단")
    except Exception as e:
        logger.error(f"수집 실패: {e}")
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
