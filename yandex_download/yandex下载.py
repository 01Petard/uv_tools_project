"""yande.re 图片下载工具。

支持两种下载模式：
- sync  ：单线程顺序下载（requests）
- async ：异步并发下载（aiohttp）

既可以作为模块调用 ``main()``（使用 argparse 默认参数），
也可以通过命令行执行:

    python yandex下载.py --mode async --start-page 1 --end-page 3
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import random
import time
from datetime import datetime
from urllib.parse import unquote, urljoin, urlparse

import aiohttp
import requests
from bs4 import BeautifulSoup

# ===== 默认配置（命令行参数默认值也取自这里）=====
BASE_URL = "https://yande.re/post?page={page}&tags=oni-noboru"
START_PAGE = 1
END_PAGE = 10
MAX_CONCURRENCY = 3                       # 异步模式并发数
DELAY_RANGE = (1.0, 2.0)                  # 每次下载之间的随机延迟（秒）
RETRY_TIMES = 3                           # 下载失败重试次数
TIMEOUT = 30.0                            # 单次请求超时（秒）

# 伪装客户端
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile Safari/604.1",
]


# ===== 通用工具 =====
def get_headers(referer: str | None = None) -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": referer or BASE_URL.format(page=1),
    }


def default_save_dir() -> str:
    """按当前时间生成默认保存目录。"""
    return f"./images_{datetime.now().strftime('%Y%m%d-%H%M')}"


def safe_filename_from_url(url: str) -> str:
    """从 URL 中提取安全且已解码的文件名。"""
    path = unquote(urlparse(url).path)
    name = os.path.basename(path)
    if not name:
        name = hashlib.sha1(url.encode()).hexdigest()
    return name


# ===== 抓取图片链接 =====
def fetch_page(
    session: requests.Session,
    base_url: str,
    page_num: int,
    timeout: float,
) -> list[tuple[str, str]]:
    """抓取单页，返回 [(图片链接, 该页 URL 作为 Referer), ...]。"""
    url = base_url.format(page=page_num)
    print(f"[INFO] 正在抓取第 {page_num} 页: {url}")
    resp = session.get(url, headers=get_headers(), timeout=timeout)
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
            img_links.append((urljoin(url, a_tag["href"]), url))

    print(f"[INFO] 第 {page_num} 页共找到 {len(img_links)} 张原图链接")
    return img_links


def fetch_all_pages(
    base_url: str,
    start_page: int,
    end_page: int,
    timeout: float = TIMEOUT,
) -> list[tuple[str, str]]:
    """抓取所有指定页面的图片链接。"""
    all_links: list[tuple[str, str]] = []
    with requests.Session() as session:
        for page in range(start_page, end_page + 1):
            all_links.extend(fetch_page(session, base_url, page, timeout))
    print(f"[INFO] 总共收集到 {len(all_links)} 张原图链接")
    return all_links


# ===== 同步下载 =====
def download_one_sync(
    session: requests.Session,
    img_url: str,
    referer: str,
    save_dir: str,
    retry: int,
    timeout: float,
    delay_range: tuple[float, float],
) -> bool:
    filename = safe_filename_from_url(img_url)
    filepath = os.path.join(save_dir, filename)
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        print(f"跳过（已存在）: {filename}")
        return True

    for attempt in range(1, retry + 1):
        try:
            delay = random.uniform(*delay_range)
            time.sleep(delay)

            with session.get(
                img_url, headers=get_headers(referer), timeout=timeout, stream=True
            ) as resp:
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
            print(f"⚠️ 下载失败 ({attempt}/{retry}): {img_url} -> {e}. 等待 {wait:.1f}s 后重试")
            time.sleep(wait)

    print(f"❌ 最终失败: {img_url}")
    return False


def download_images_sync(
    links: list[tuple[str, str]],
    save_dir: str,
    retry: int,
    timeout: float,
    delay_range: tuple[float, float],
) -> None:
    print(f"\n[同步下载] 总任务数: {len(links)}")
    with requests.Session() as session:
        for idx, (img_url, referer) in enumerate(links, start=1):
            print(f"[{idx}/{len(links)}] 下载: {img_url}")
            download_one_sync(session, img_url, referer, save_dir, retry, timeout, delay_range)


# ===== 异步下载 =====
async def download_one_async(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    img_url: str,
    referer: str,
    save_dir: str,
    retry: int,
    timeout: aiohttp.ClientTimeout,
    delay_range: tuple[float, float],
) -> bool:
    filename = safe_filename_from_url(img_url)
    filepath = os.path.join(save_dir, filename)
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        print(f"跳过（已存在）: {filename}")
        return True

    async with semaphore:
        for attempt in range(1, retry + 1):
            try:
                await asyncio.sleep(random.uniform(*delay_range))

                async with session.get(img_url, headers=get_headers(referer), timeout=timeout) as resp:
                    resp.raise_for_status()

                    content_type = resp.headers.get("Content-Type", "")
                    if not content_type.startswith("image/"):
                        print(f"⚠️ 非图片响应 ({content_type}): {img_url}")
                        return False

                    with open(filepath + ".part", "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 16):
                            if chunk:
                                f.write(chunk)
                os.replace(filepath + ".part", filepath)
                print(f"✅ 保存: {filename}")
                return True

            except Exception as e:
                wait = 1 + attempt * 2 + random.random()
                print(f"⚠️ 下载失败 ({attempt}/{retry}): {img_url} -> {e}. 等待 {wait:.1f}s 后重试")
                await asyncio.sleep(wait)

    print(f"❌ 最终失败: {img_url}")
    return False


async def download_images_async(
    links: list[tuple[str, str]],
    save_dir: str,
    concurrency: int,
    retry: int,
    timeout_seconds: float,
    delay_range: tuple[float, float],
) -> None:
    concurrency = max(1, concurrency)
    print(f"\n[异步下载] 并发数: {concurrency}，总任务数: {len(links)}")

    semaphore = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    connector = aiohttp.TCPConnector(limit=concurrency)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.create_task(
                download_one_async(
                    session, semaphore, img_url, referer,
                    save_dir, retry, timeout, delay_range,
                )
            )
            for img_url, referer in links
        ]

        done = 0
        for task in asyncio.as_completed(tasks):
            try:
                await task
            except Exception as e:  # 防止单个任务异常中断整体流程
                print(f"任务异常: {e}")
            done += 1
            print(f"[进度] {done}/{len(links)} 完成")


# ===== 处理文件名的问题（兜底：兼容仍含 %20 的历史文件）=====
def rename_files_replace_percent20(dir_path: str) -> None:
    for root, _dirs, files in os.walk(dir_path):
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


# ===== 命令行 =====
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="yande.re 图片下载工具（同步/异步）")
    parser.add_argument("--base-url", default=BASE_URL, help="页面 URL 模板，需包含 {page}")
    parser.add_argument("--start-page", type=int, default=START_PAGE, help="起始页码")
    parser.add_argument("--end-page", type=int, default=END_PAGE, help="结束页码")
    parser.add_argument("--save-dir", default=None, help="保存目录，默认 ./images_<时间戳>")
    parser.add_argument("--mode", choices=("sync", "async"), default="sync", help="下载模式")
    parser.add_argument("--concurrency", type=int, default=MAX_CONCURRENCY, help="异步模式并发数")
    parser.add_argument("--retry", type=int, default=RETRY_TIMES, help="失败重试次数")
    parser.add_argument("--timeout", type=float, default=TIMEOUT, help="单次请求超时（秒）")
    parser.add_argument("--delay-min", type=float, default=DELAY_RANGE[0], help="最小随机延迟（秒）")
    parser.add_argument("--delay-max", type=float, default=DELAY_RANGE[1], help="最大随机延迟（秒）")
    return parser


def main(argv: list[str] | None = None) -> None:
    """入口函数。``main()`` 使用默认参数，``main([...])`` 等价于命令行传参。"""
    args = build_parser().parse_args(argv)

    save_dir = args.save_dir or default_save_dir()
    os.makedirs(save_dir, exist_ok=True)
    delay_range = (args.delay_min, args.delay_max)

    links = fetch_all_pages(args.base_url, args.start_page, args.end_page, args.timeout)

    if args.mode == "sync":
        download_images_sync(links, save_dir, args.retry, args.timeout, delay_range)
    else:
        asyncio.run(
            download_images_async(
                links, save_dir, args.concurrency, args.retry, args.timeout, delay_range
            )
        )

    rename_files_replace_percent20(save_dir)
    print(f"\n[完成] 图片已保存到: {save_dir}")


if __name__ == "__main__":
    main()
