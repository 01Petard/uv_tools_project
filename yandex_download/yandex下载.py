import os
import time
import random
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# ===== 配置 =====
BASE_URL = "https://yande.re/post?page={page}&tags=oni-noboru"
START_PAGE = 1
END_PAGE = 10
time_suffix = datetime.now().strftime("%Y%m%d-%H%M")
SAVE_DIR = f"./images_{time_suffix}"  # 图片保存目录
# SAVE_DIR = "./images"  # 图片保存目录
DELAY_RANGE = (1, 2)  # 每次下载之间的随机延迟（秒）
RETRY_TIMES = 3  # 下载失败重试次数

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile Safari/604.1",
]


def get_headers(referer=None):
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": referer or BASE_URL.format(page=1),
    }


os.makedirs(SAVE_DIR, exist_ok=True)


def fetch_page(base_url, page_num):
    url = base_url.format(page=page_num)
    print(f"[INFO] 正在抓取第 {page_num} 页: {url}")
    resp = requests.get(url, headers=get_headers())
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    ul_tag = soup.find("ul", id="post-list-posts")
    if not ul_tag:
        print(f"⚠️ 第 {page_num} 页找不到图片列表")
        return []

    img_links = []
    for li in ul_tag.find_all("li"):
        a_tag = li.find("a", class_="directlink largeimg")
        if a_tag and a_tag.get("href"):
            img_links.append(a_tag["href"])

    print(f"[INFO] 第 {page_num} 页共找到 {len(img_links)} 张原图链接")
    return img_links


def download_images(links):
    random.shuffle(links)
    for idx, img_url in enumerate(links, start=1):
        for attempt in range(1, RETRY_TIMES + 1):
            try:
                delay = random.uniform(*DELAY_RANGE)
                print(f"[{idx}/{len(links)}] 下载: {img_url} (延迟 {delay:.2f}s)")
                time.sleep(delay)

                res = requests.get(img_url, headers=get_headers(referer=BASE_URL), timeout=15)
                res.raise_for_status()

                filename = os.path.basename(urlparse(img_url).path)
                file_path = os.path.join(SAVE_DIR, filename)
                with open(file_path, "wb") as f:
                    f.write(res.content)

                print(f"✅ 成功保存到 {file_path}")
                break

            except Exception as e:
                print(f"⚠️ 下载失败 (尝试 {attempt}/{RETRY_TIMES}): {e}")
                if attempt == RETRY_TIMES:
                    print(f"❌ 放弃下载: {img_url}")


# ===== 处理文件名的问题 =====
def rename_files_replace_percent20(dir_path):
    for root, dirs, files in os.walk(dir_path):
        for fname in files:
            if "%20" in fname:
                old_path = os.path.join(root, fname)
                new_fname = fname.replace("%20", " ")
                new_path = os.path.join(root, new_fname)
                try:
                    os.rename(old_path, new_path)
                    print(f"重命名: {fname} -> {new_fname}")
                except Exception as e:
                    print(f"重命名失败: {fname} -> {new_fname}, 错误: {e}")


if __name__ == "__main__":

    all_links = []
    for page in range(START_PAGE, END_PAGE + 1):
        all_links.extend(fetch_page(BASE_URL, page))

    print(f"[INFO] 总共收集到 {len(all_links)} 张原图链接")
    for link in all_links:
        print(link)

    download_images(all_links)

    rename_files_replace_percent20(SAVE_DIR)
