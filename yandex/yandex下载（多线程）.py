from datetime import datetime
import os
import time
import random
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

# ===== 配置 =====
BASE_URL = "https://yande.re/post?page={page}&tags=oni-noboru"
START_PAGE = 1
END_PAGE = 10
MAX_THREADS = 3
time_suffix = datetime.now().strftime("%Y%m%d-%H%M")
SAVE_DIR = f"./images_{time_suffix}"  # 图片保存目录
DELAY_RANGE = (1, 3)  # 每次下载之间的随机延迟（秒）
RETRY_TIMES = 3  # 下载失败重试次数
# 伪装客户端
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile Safari/604.1",
]


# ===== 配置初始化 =====
def get_headers(referer=None):
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": referer or BASE_URL.format(page=1),
    }


os.makedirs(SAVE_DIR, exist_ok=True)


# ===== 获取链接 =====
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
            img_links.append((a_tag["href"], url))  # 传递当前页url做referer

    print(f"[INFO] 第 {page_num} 页共找到 {len(img_links)} 张原图链接")
    return img_links


def safe_filename_from_url(url):
    from urllib.parse import unquote, urlparse
    path = unquote(urlparse(url).path)
    name = os.path.basename(path)
    if not name:
        import hashlib
        name = hashlib.sha1(url.encode()).hexdigest()
    return name


# ===== 单线程下载文件 =====
def download_one(session, img_url, referer):
    filename = safe_filename_from_url(img_url)
    filepath = os.path.join(SAVE_DIR, filename)
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        print(f"跳过（已存在）: {filename}")
        return True

    for attempt in range(1, RETRY_TIMES + 1):
        try:
            delay = random.uniform(*DELAY_RANGE)
            time.sleep(delay)

            headers = get_headers(referer=referer)
            resp = session.get(img_url, headers=headers, timeout=30, stream=True)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                print(f"⚠️ 非图片响应 ({content_type}): {img_url}")
                return False

            with open(filepath + ".part", "wb") as f:
                for chunk in resp.iter_content(1024 * 16):
                    if chunk:
                        f.write(chunk)
            os.replace(filepath + ".part", filepath)
            print(f"✅ 保存: {filename}")
            return True

        except Exception as e:
            wait = 1 + attempt * 2 + random.random()
            print(f"⚠️ 下载失败 ({attempt}/{RETRY_TIMES}): {img_url} -> {e}. 等待 {wait:.1f}s 后重试")
            time.sleep(wait)

    print(f"❌ 最终失败: {img_url}")
    return False


# ===== 多线程下载文件 =====
def download_images_multithreaded(links, max_workers):
    cpu_count = multiprocessing.cpu_count()
    workers = min(max_workers, cpu_count)
    print(f"\n[开始多线程下载] 线程数: {workers}，总任务数: {len(links)}")

    session = requests.Session()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for img_url, referer in links:
            futures.append(executor.submit(download_one, session, img_url, referer))

        done_count = 0
        for future in as_completed(futures):
            done_count += 1
            try:
                future.result()
            except Exception as e:
                print(f"线程异常: {e}")
            print(f"[进度] {done_count}/{len(links)} 完成")

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
    download_images_multithreaded(all_links, MAX_THREADS)
    rename_files_replace_percent20(SAVE_DIR)