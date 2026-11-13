#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radar_engine.py — الرادار التقني المستقل (الإصدار الموحد الكامل)

- يعمل على خوادم GitHub Actions المجانية (ubuntu-latest) ولا يحتاج حاسوبك.
- المختبر الحي (IS_CLOUD_SANDBOX) يعمل تلقائياً على GitHub، ويتوقف محلياً
  إلا إذا ضبطت ENABLE_SANDBOX=true.
- متوافق مع autopilot.yml الحالي دون أي تعديل:
      python radar_engine.py [normal|full|weekly]
"""

import ast
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ==================== 1. الإعدادات وأوضاع التشغيل ====================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

RAW_MODE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("RADAR_MODE", "normal")).strip().lower()
RADAR_MODE = RAW_MODE if RAW_MODE in ("normal", "full", "weekly") else "normal"

# تفعيل المختبر الحي بأقصى طاقته تلقائياً على خوادم GitHub، وإيقافه افتراضياً على الحاسوب الشخصي
IS_CLOUD_SANDBOX = (
    os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    or os.environ.get("ENABLE_SANDBOX", "").lower() == "true"
)

# سياج كتل الكود (ثلاث علامات backtick) يُبنى برمجياً حتى لا يتعارض مع تنسيق Markdown عند النسخ واللصق
FENCE = "`" * 3

MODE_LABELS = {
    "normal": "الوضع العادي (الفرص الرائجة + تتبع القفزات المفاجئة)",
    "full": "الوضع التام (رصد شامل لكل المستجدات بدون فلترة)",
    "weekly": "التقرير الاستراتيجي الأسبوعي المجمع",
}

MEMORY_FILE = "memory.json"
REPORT_DIR = "reports"
ASSETS_DIR = "assets"

DOMAINS = {
    "الذكاء الاصطناعي والأتمتة": "(ai-agent OR automation OR workflow OR llm OR mcp-server)",
    "فرص البرمجيات كخدمة Micro-SaaS": "(micro-saas OR saas-boilerplate OR niche-tool OR api-wrapper OR indie-hacker)",
    "تحليل البيانات والتجارة": "(ecommerce OR price-tracker OR web-scraper OR market-analysis OR trading-bot)",
}

NOISE_KEYWORDS = {
    "roblox", "cheat", "aimbot", "crack", "keygen", "free-nitro",
    "hack-tool", "homework", "assignment", "leetcode", "dotfiles", "my-config",
}

SECURITY_PATTERNS = [
    (r"base64\.b64decode\s*\(", "فك تشفير Base64 ديناميكي"),
    (r"\b(eval|exec)\s*\(", "تنفيذ كود ديناميكي (eval/exec)"),
    (r"(curl|wget)\s+[^\n]+\|\s*(sh|bash)", "تشغيل سكربت خارجي مباشر عبر الطرفية"),
    (r"(\.ssh/id_rsa|wallet\.dat|AppData\\Local\\Google\\Chrome)", "محاولة الوصول لبيانات أو مفاتيح حساسة"),
    (r"(xmrig|stratum\+tcp|cryptonight)", "مؤشرات تعدين عملات رقمية"),
]


# ==================== 2. الذاكرة الذكية والاتصال الشبكي ====================
def load_memory():
    """تحميل الذاكرة وترقية القائمة القديمة إلى قاموس ذكي عند الحاجة."""
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            now_iso = datetime.now(timezone.utc).isoformat()
            return {
                str(uid): {
                    "title": str(uid),
                    "stars": 0,
                    "first_seen": now_iso,
                    "last_seen": now_iso,
                    "breakout_alerted": False,
                }
                for uid in data
            }
    except (OSError, json.JSONDecodeError) as exc:
        print(f"⚠️ تعذر قراءة ملف الذاكرة: {exc}")
    return {}


def save_memory(memory_dict):
    """حفظ آخر 4000 سجل بطريقة ذرية آمنة لمنع تلف الملف."""
    if len(memory_dict) > 4000:
        memory_dict = dict(list(memory_dict.items())[-4000:])
    temp_path = f"{MEMORY_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(memory_dict, file, ensure_ascii=False, indent=2)
    os.replace(temp_path, MEMORY_FILE)


def http_request(url, method="GET", headers=None, data=None, timeout=20, as_json=True):
    request_headers = {"User-Agent": "Mozilla/5.0 (compatible; AutonomousTechRadar/6.0)"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    if not as_json:
        return raw
    return json.loads(raw) if raw else None


def is_noise(text):
    lowered = text.lower()
    return any(keyword in lowered for keyword in NOISE_KEYWORDS)


def calculate_star_velocity(repo):
    try:
        created = datetime.strptime(repo.get("created_at", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age_hours = max((datetime.now(timezone.utc) - created).total_seconds() / 3600.0, 1.0)
        return round(repo.get("stargazers_count", 0) / age_hours, 2)
    except (TypeError, ValueError):
        return 0.0


def build_clean_env():
    """
    بيئة نظيفة للعمليات الفرعية (git / تشغيل MVP) بدون أي مفاتيح سرية
    (GEMINI_API_KEY / TELEGRAM_BOT_TOKEN / GITHUB_TOKEN) حتى لا يستطيع أي كود
    مُولَّد أو مسحوب من الخارج قراءتها من متغيرات البيئة.
    """
    allowed = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TMP", "TEMP", "SYSTEMROOT")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


# ==================== 3. الاكتشاف الذاتي لأحدث نماذج Gemini ====================
def _model_sort_key(model_name):
    nums = [int(n) for n in re.findall(r"\d+", model_name)]
    major = nums[0] if len(nums) > 0 else 0
    minor = nums[1] if len(nums) > 1 else 0
    is_lite = 1 if "lite" in model_name else 0
    is_preview = 1 if ("preview" in model_name or "exp" in model_name) else 0
    return (major, minor, -is_lite, -is_preview)


def discover_active_gemini_models():
    fallback_models = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3.5-flash"]
    if not GEMINI_API_KEY:
        return fallback_models
    excluded = ("embedding", "imagen", "veo", "tts", "audio", "aqa", "robotics", "computer-use", "bisect", "learnlm")
    try:
        data = http_request(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}",
            timeout=15,
        )
        flash, other = [], []
        for model in (data or {}).get("models", []):
            if "generateContent" not in model.get("supportedGenerationMethods", []):
                continue
            name = model.get("name", "").removeprefix("models/").strip()
            if not name.startswith("gemini-") or any(tag in name for tag in excluded):
                continue
            (flash if "flash" in name else other).append(name)
        flash.sort(key=_model_sort_key, reverse=True)
        other.sort(key=_model_sort_key, reverse=True)
        discovered = flash + other
        if discovered:
            print(f"🧠 النماذج المتاحة: {', '.join(discovered[:4])}")
            return discovered[:5]
    except Exception as exc:
        print(f"⚠️ تعذر جلب نماذج Gemini: {exc}")
    return fallback_models


# ==================== 4. تتبع القفزات المفاجئة (Breakout Tracker) ====================
def github_headers(accept="application/vnd.github+json"):
    headers = {"Accept": accept}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def check_github_breakouts(memory_dict):
    if RADAR_MODE != "normal" or not memory_dict:
        return []
    now = datetime.now(timezone.utc)
    candidates = []
    for uid, info in reversed(list(memory_dict.items())):
        if not uid.startswith("gh_") or info.get("breakout_alerted"):
            continue
        if info.get("stars", 0) >= 35 or "/" not in info.get("title", ""):
            continue
        try:
            first_seen = datetime.fromisoformat(info.get("first_seen", ""))
            if (now - first_seen).days <= 14:
                candidates.append((uid, info))
        except (TypeError, ValueError):
            continue
        if len(candidates) >= 6:
            break

    results = []
    for uid, info in candidates:
        try:
            repo = http_request(
                f"https://api.github.com/repos/{info['title']}",
                headers=github_headers(), timeout=12,
            )
            if not repo:
                continue
            current = repo.get("stargazers_count", 0)
            previous = info.get("stars", 0)
            jump = current - previous
            if jump >= 40 or (current >= 25 and current >= previous * 3):
                info.update(stars=current, last_seen=now.isoformat(), breakout_alerted=True)
                results.append({
                    "uid": uid, "source": "github", "is_breakout": True,
                    "domain": "🚨 قفزة مفاجئة (Breakout Alert)",
                    "title": repo.get("full_name", info["title"]),
                    "url": repo.get("html_url", f"https://github.com/{info['title']}"),
                    "description": (repo.get("description") or "قفزة مفاجئة في التفاعل").strip(),
                    "metrics": f"قفز من {previous} إلى {current} نجمة (+{jump}) | اللغة: {repo.get('language') or 'متعددة'}",
                    "stars": current, "files": [],
                })
            time.sleep(0.8)
        except Exception:
            continue
    return results


# ==================== 5. المصادر الخمسة للرصد ====================
def get_github_files(repo_name, headers):
    try:
        items = http_request(f"https://api.github.com/repos/{repo_name}/contents", headers=headers, timeout=10)
        if isinstance(items, list):
            return [item.get("name", "") for item in items if item.get("name")][:15]
    except Exception:
        pass
    return []


def fetch_github_discoveries(memory_dict):
    discoveries = []
    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    last_week = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    headers = github_headers()

    for domain, terms in DOMAINS.items():
        if RADAR_MODE == "normal":
            query = f"{terms} created:>={last_week} stars:>=50"
            sort, limit, pick_limit = "stars", 8, 1
        else:
            query = f"{terms} created:>={yesterday} stars:>=0"
            sort, limit, pick_limit = "updated", 8, 2
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({
            "q": query, "sort": sort, "order": "desc", "per_page": limit,
        })
        picked = 0
        try:
            data = http_request(url, headers=headers)
            for repo in (data or {}).get("items", []):
                uid = f"gh_{repo['id']}"
                if uid in memory_dict:
                    continue
                full_name = repo["full_name"]
                description = (repo.get("description") or "بدون وصف نصي").strip()
                if RADAR_MODE == "normal" and (
                    repo.get("fork") or repo.get("archived") or is_noise(f"{full_name} {description}")
                ):
                    memory_dict[uid] = {
                        "title": full_name, "stars": repo.get("stargazers_count", 0),
                        "first_seen": now.isoformat(), "last_seen": now.isoformat(),
                    }
                    continue
                stars = repo.get("stargazers_count", 0)
                discoveries.append({
                    "uid": uid, "source": "github", "is_breakout": False,
                    "domain": domain, "title": full_name, "url": repo["html_url"],
                    "description": description,
                    "metrics": f"النجوم: {stars} ({calculate_star_velocity(repo)} نجمة/ساعة) | اللغة: {repo.get('language') or 'متعددة'}",
                    "stars": stars, "files": get_github_files(full_name, headers),
                })
                picked += 1
                if picked >= pick_limit:
                    break
            time.sleep(1.0)
        except Exception as exc:
            print(f"⚠️ تنبيه GitHub ({domain}): {exc}")
    return discoveries


def fetch_hn_discoveries(memory_dict):
    discoveries = []
    keywords = ("ai", "agent", "saas", "automate", "automation", "scrape", "ecommerce", "data", "tool", "open source", "llm", "workflow", "api")
    feed_url = "https://hacker-news.firebaseio.com/v0/topstories.json" if RADAR_MODE == "normal" else "https://hacker-news.firebaseio.com/v0/newstories.json"
    scan_limit = 40 if RADAR_MODE == "normal" else 20
    pick_limit = 1 if RADAR_MODE == "normal" else 2
    try:
        feed = http_request(feed_url) or []
        for story_id in feed[:scan_limit]:
            uid = f"hn_{story_id}"
            if uid in memory_dict:
                continue
            item = http_request(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
            if not item or item.get("deleted") or item.get("dead") or not item.get("title"):
                continue
            title = item["title"].strip()
            item_url = (item.get("url") or f"https://news.ycombinator.com/item?id={story_id}").strip()
            score, comments = item.get("score", 0), item.get("descendants", 0)
            if RADAR_MODE == "normal" and (
                (score < 80 and comments < 40) or is_noise(title)
                or not any(word in title.lower() for word in keywords)
            ):
                continue
            discoveries.append({
                "uid": uid, "source": "hn", "is_breakout": False,
                "domain": "Hacker News (تقنية وأعمال)", "title": title,
                "url": item_url, "description": f"طرح على Hacker News: {title}",
                "metrics": f"النقاط: {score} | التعليقات: {comments}",
                "stars": score, "files": [],
            })
            if len(discoveries) >= pick_limit:
                break
    except Exception as exc:
        print(f"⚠️ تنبيه Hacker News: {exc}")
    return discoveries


def _find_first(element, *paths, namespaces=None):
    """
    بحث آمن داخل عنصر XML: يعتمد على `is not None` وليس على قيمة العنصر المنطقية،
    لأن عنصر ElementTree الذي لا يملك أبناء يُعدّ False حتى لو كان يحمل نصاً.
    """
    for path in paths:
        found = element.find(path, namespaces)
        if found is not None:
            return found
    return None


def fetch_producthunt_discoveries(memory_dict):
    discoveries = []
    try:
        xml_raw = http_request("https://www.producthunt.com/feed", timeout=15, as_json=False)
        root = ET.fromstring(xml_raw)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns) or root.findall(".//item")
        pick_limit = 1 if RADAR_MODE == "normal" else 2
        for entry in entries[:15]:
            title_el = _find_first(entry, "atom:title", "title", namespaces=ns)
            link_el = _find_first(entry, "atom:link", "link", namespaces=ns)
            summary_el = _find_first(entry, "atom:content", "description", namespaces=ns)
            title = (title_el.text or "").strip() if title_el is not None else ""
            if link_el is None:
                url = ""
            else:
                url = (link_el.attrib.get("href") or link_el.text or "").strip()
            summary = ""
            if summary_el is not None and summary_el.text:
                summary = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", summary_el.text))).strip()
            if not title or not url:
                continue
            uid = "ph_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
            if uid in memory_dict:
                continue
            discoveries.append({
                "uid": uid, "source": "producthunt", "is_breakout": False,
                "domain": "Product Hunt (منتجات تجارية و SaaS)", "title": title,
                "url": url, "description": summary[:300] or title,
                "metrics": "إطلاق تجاري جديد على Product Hunt", "stars": 0, "files": [],
            })
            if len(discoveries) >= pick_limit:
                break
    except Exception as exc:
        print(f"⚠️ تنبيه Product Hunt: {exc}")
    return discoveries


def fetch_huggingface_papers(memory_dict):
    discoveries = []
    try:
        papers = http_request("https://huggingface.co/api/daily_papers", timeout=15) or []
        pick_limit = 1 if RADAR_MODE == "normal" else 2
        for entry in papers[:15]:
            paper = entry.get("paper", {})
            paper_id = paper.get("id", "")
            title = (paper.get("title") or "").strip()
            upvotes = paper.get("upvotes", 0)
            if not paper_id or not title:
                continue
            uid = f"hf_{paper_id}"
            if uid in memory_dict or (RADAR_MODE == "normal" and upvotes < 20):
                continue
            discoveries.append({
                "uid": uid, "source": "huggingface", "is_breakout": False,
                "domain": "Hugging Face (أبحاث ونماذج AI)", "title": title,
                "url": f"https://huggingface.co/papers/{paper_id}",
                "description": (paper.get("summary") or title)[:400],
                "metrics": f"تصويت الباحثين (Upvotes): {upvotes}", "stars": upvotes, "files": [],
            })
            if len(discoveries) >= pick_limit:
                break
    except Exception as exc:
        print(f"⚠️ تنبيه Hugging Face: {exc}")
    return discoveries


def fetch_reddit_opportunities(memory_dict):
    discoveries = []
    for subreddit in ("SaaS", "LocalLLaMA", "Entrepreneur"):
        try:
            sort_path = "hot.json?limit=12" if RADAR_MODE == "normal" else "new.json?limit=10"
            data = http_request(
                f"https://www.reddit.com/r/{subreddit}/{sort_path}",
                headers={"User-Agent": "python:AutonomousTechRadar:v6.0"}, timeout=15,
            ) or {}
            children = data.get("data", {}).get("children", [])
            for child in children:
                post = child.get("data", {})
                if post.get("stickied"):
                    continue
                uid = f"rd_{post.get('id', '')}"
                if uid in memory_dict:
                    continue
                score, comments = post.get("score", 0), post.get("num_comments", 0)
                if RADAR_MODE == "normal" and score < 40 and comments < 20:
                    continue
                title = (post.get("title") or "").strip()
                if not title:
                    continue
                discoveries.append({
                    "uid": uid, "source": "reddit", "is_breakout": False,
                    "domain": f"Reddit r/{subreddit} (نبض السوق والعملاء)", "title": title,
                    "url": f"https://www.reddit.com{post.get('permalink', '')}",
                    "description": (post.get("selftext") or "")[:400].strip() or title,
                    "metrics": f"التصويت: {score} | التعليقات: {comments}",
                    "stars": score, "files": [],
                })
                return discoveries[:1]
        except Exception as exc:
            print(f"⚠️ تنبيه Reddit (r/{subreddit}): {exc}")
    return discoveries


# ==================== 6. الفحص الأمني والمختبر الحي بأقصى طاقته ====================
def audit_text_security(text_blob):
    warnings = [label for pattern, label in SECURITY_PATTERNS if re.search(pattern, text_blob, re.IGNORECASE)]
    return f"تحذير أمني 🔴 ({', '.join(warnings)})" if warnings else "آمن مبدئياً 🟢"


def run_live_git_sandbox(repo_url):
    """سحب المستودع في مجلد معزول على الخادم وفحص الكود المصدري والبنية النحوية والتبعيات"""
    tmp_dir = tempfile.mkdtemp(prefix="radar_sandbox_")
    code_corpus = ""
    code_snippets = []
    try:
        clone_res = subprocess.run(
            ["git", "clone", "--depth", "1", "--", repo_url, tmp_dir],
            capture_output=True, text=True, timeout=30, env=build_clean_env(),
        )
        if clone_res.returncode != 0:
            return "تعذر سحب المستودع في المختبر الحي.", "", ""

        py_files, js_files, other_code, manifests = [], [], [], []
        total_files = 0
        manifest_names = {"requirements.txt", "pyproject.toml", "package.json", "Dockerfile", "docker-compose.yml", "Cargo.toml", "go.mod"}

        for root_dir, dirs, files in os.walk(tmp_dir):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv", "venv")]
            for fname in files:
                total_files += 1
                fpath = os.path.join(root_dir, fname)
                rel_path = os.path.relpath(fpath, tmp_dir)
                if fname in manifest_names:
                    manifests.append(rel_path)
                if fname.endswith(".py"):
                    py_files.append((rel_path, fpath))
                elif fname.endswith((".js", ".ts", ".jsx", ".tsx")):
                    js_files.append((rel_path, fpath))
                elif fname.endswith((".go", ".rs", ".sh", ".java", ".cpp")):
                    other_code.append((rel_path, fpath))

        # استخلاص عينات من الكود المصدري الفعلي للتدقيق الأمني وتحليل المنطق البرمجي
        all_code_files = py_files + js_files + other_code
        for rel_path, fpath in all_code_files[:6]:
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(2500)
                    code_corpus += f"\n--- {rel_path} ---\n{content}"
                    if len(code_snippets) < 3 and content.strip():
                        code_snippets.append(f"[{rel_path}]:\n{content[:700]}")
            except Exception:
                pass

        # فحص البنية النحوية (AST Syntax Check) لملفات بايثون حتى 25 ملفاً
        syntax_errors = 0
        for _, fpath in py_files[:25]:
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    ast.parse(f.read())
            except (SyntaxError, ValueError):
                syntax_errors += 1

        summary_parts = [f"تم السحب والفحص الحي ({total_files} ملف)"]
        if py_files:
            summary_parts.append(f"Python: {len(py_files)} ملف (أخطاء نحوية: {syntax_errors})")
        if js_files:
            summary_parts.append(f"JS/TS: {len(js_files)} ملف")
        if other_code:
            summary_parts.append(f"لغات أخرى: {len(other_code)} ملف")
        if manifests:
            summary_parts.append(f"ملفات التهيئة: {', '.join(manifests[:5])}")

        snippets_text = "\n".join(code_snippets)
        return " | ".join(summary_parts), code_corpus, snippets_text
    except Exception as exc:
        return f"انتهت مهلة المختبر أو تعذر الفحص ({str(exc)[:80]})", "", ""
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def technical_probe(item):
    notes = []
    collected_text = f"{item['title']} {item['description']}"
    started = time.time()
    try:
        request = urllib.request.Request(
            item["url"],
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            notes.append(f"- حالة الرابط: نشط (HTTP {response.status} | {int((time.time() - started) * 1000)}ms)")
            if item["source"] in ("hn", "producthunt") and ("text/html" in content_type or "text/plain" in content_type):
                page = response.read(18000).decode("utf-8", errors="replace")
                page = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.DOTALL | re.IGNORECASE)
                clean = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page))).strip()
                if clean:
                    notes.append(f"- محتوى الصفحة الفعلي:\n{clean[:1000]}")
                    collected_text += " " + clean[:2000]
    except Exception as exc:
        notes.append(f"- حالة الرابط: تعذر الفتح ({str(exc)[:100]})")

    if item["source"] == "github":
        if item.get("files"):
            notes.append(f"- الملفات الرئيسية: {', '.join(item['files'])}")
        try:
            readme = http_request(
                f"https://api.github.com/repos/{item['title']}/readme",
                headers=github_headers("application/vnd.github.raw+json"), timeout=12, as_json=False,
            )
            if readme:
                notes.append(f"- مقتطف التوثيق (README):\n{readme[:1500]}")
                collected_text += " " + readme[:3000]
        except Exception:
            notes.append("- التوثيق: لا يوجد README قياسي.")

        # تشغيل المختبر الحي بأقصى درجة عند العمل على خادم GitHub السحابي
        if IS_CLOUD_SANDBOX:
            sandbox_report, code_corpus, code_snippets = run_live_git_sandbox(item["url"])
            notes.append(f"- المختبر الحي (Cloud Sandbox): {sandbox_report}")
            if code_snippets:
                notes.append(f"- عينات من الكود المصدري الفعلي:\n{code_snippets[:1400]}")
            collected_text += " " + code_corpus
        else:
            notes.append("- المختبر الحي: متوقف محلياً لحماية حاسوبك (يعمل تلقائياً في السحابة).")

    item["security"] = audit_text_security(collected_text)
    notes.insert(0, f"- التدقيق الأمني الآلي: {item['security']}")
    return "\n".join(notes)


# ==================== 7. التحليل وتوليد وتشغيل MVP ذاتياً ====================
def call_gemini_api(prompt_text, active_models, temperature=0.35):
    if not GEMINI_API_KEY:
        return "❌ لم يتم ضبط GEMINI_API_KEY.", False
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": temperature},
    }).encode("utf-8")
    last_error = ""
    for model in active_models:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        for _ in range(2):
            try:
                response = http_request(
                    endpoint, method="POST", headers={"Content-Type": "application/json"},
                    data=payload, timeout=40,
                ) or {}
                candidates = response.get("candidates", [])
                if not candidates or "content" not in candidates[0]:
                    last_error = f"استجابة فارغة من [{model}]"
                    break
                parts = candidates[0]["content"].get("parts", [])
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    return text, True
                last_error = f"نص فارغ من [{model}]"
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {exc.code} [{model}]: {body[:200]}"
                if exc.code == 429:
                    time.sleep(10)
                    continue
                if exc.code in (400, 403):
                    return f"⚠️ خطأ في إعداد API: {last_error}", False
                break
            except Exception as exc:
                last_error = str(exc)
                break
    return f"⚠️ تعذر التحليل: {last_error}", False


def analyze_discovery(item, probe_data, active_models):
    prompt = f"""
أنت مهندس استغلال تقني ومحلل أعمال صارم. حلل الاكتشاف التالي بموضوعية واختصار عملي شديد:
- المجال: {item['domain']}
- العنوان: {item['title']}
- الرابط: {item['url']}
- المؤشرات: {item['metrics']}
- الوصف: {item['description']}
- نتائج الفحص التقني والمختبر الحي والأمني:
{probe_data}

اكتب تقريراً تنفيذياً بالعربية (بدون مقدمات) يغطي البنود الستة التالية بدقة:
1. التقييم وحقيقة الأداة (من 10): درجة الجدوى، وما الذي تفعله الأداة فعلياً وهل هي جاهزة للإنتاج أم مجرد نموذج أولي.
2. المجال والفئة المستهدفة: من يحتاج هذا الحل تحديداً؟
3. الاستغلال الربحي المباشر: كيف يُحوّل إلى مال (Micro-SaaS، خدمة لعملاء، أو خفض تكلفة تشغيل)؟
4. اختصار مدة العمل: ما المهمة اليدوية التي يلغيها وكم يختصر من الوقت؟
5. الاستخدام العملي والحياتي: سيناريو تطبيق يومي ملموس.
6. خطوات التشغيل الفورية: (1، 2، 3) للبدء الآن.
"""
    return call_gemini_api(prompt, active_models)


def extract_python_block(text):
    """استخراج أول كتلة كود بايثون من رد النموذج (python أو py أو كتلة بدون لغة)."""
    match = re.search(FENCE + r"(?:python|py)?[ \t]*\r?\n(.*?)" + FENCE, text or "", re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else None


def build_and_verify_golden_asset(analyzed_items, active_models, timestamp_str):
    """بناء الأصل البرمجي للفرصة الذهبية وتشغيله فعلياً في السحابة مع الإصلاح التلقائي"""
    if not analyzed_items:
        return None, ""
    summary = "\n".join(
        f"[{index}] {item['title']} ({item['domain']}): {item['analysis'][:350]}"
        for index, item in enumerate(analyzed_items, 1)
    )
    prompt = f"""
اعتماداً على الاكتشافات التالية في هذه الدورة:
{summary}

المطلوب:
1. اختر **الفرصة الذهبية رقم 1** الأكثر ربحية وقابلية للتطبيق الفوري.
2. اكتب ملخصاً تنفيذياً عربياً من 3 أسطر يوضح لماذا هي الفرصة الذهبية وكيف نربح منها اليوم.
3. اكتب **كود Python متكامل وجاهز للتشغيل الفوري** (يعتمد على مكتبات Python القياسية فقط بدون pip) يطبق هذه الفرصة عملياً (مثلاً: أداة أتمتة، محلل بيانات/أسعار، أو نواة خدمة Micro-SaaS) ويدعم المعامل `--self-test` لتنفيذ اختبار ذاتي حقيقي وطباعة النتيجة بوضوح دون تعديل ملفات النظام.

أخرج الرد بهذا التنسيق حصراً:
### EXECUTIVE_SUMMARY
الملخص التنفيذي بالعربية هنا
### PYTHON_MVP
{FENCE}python
الكود الكامل هنا
{FENCE}
"""
    response, ok = call_gemini_api(prompt, active_models, temperature=0.25)
    if not ok:
        return None, ""

    summary_match = re.search(r"### EXECUTIVE_SUMMARY\s*(.*?)\s*### PYTHON_MVP", response, re.DOTALL)
    code = extract_python_block(response)
    executive_summary = summary_match.group(1).strip() if summary_match else response[:400]
    if not code:
        return None, executive_summary

    os.makedirs(ASSETS_DIR, exist_ok=True)
    output_path = os.path.join(ASSETS_DIR, f"mvp_{timestamp_str}.py")

    if not IS_CLOUD_SANDBOX:
        try:
            ast.parse(code)
            status = "✅ اجتاز فحص البنية النحوية (التشغيل التلقائي معطّل محلياً لحماية حاسوبك)."
        except SyntaxError as exc:
            status = f"⚠️ خطأ نحوي في السطر {exc.lineno}: {exc.msg}"
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(code + "\n")
        executive_summary += f"\n\n🛠️ **حالة الأصل البرمجي الجاهز:** {status}"
        return output_path, executive_summary

    # التشغيل الذاتي الفعلي على خادم GitHub السحابي مع محاولة الإصلاح التلقائي عند الفشل
    status = "⚠️ لم يتم التحقق"
    err_trace = ""
    test_workdir = tempfile.mkdtemp(prefix="mvp_exec_")
    try:
        for attempt in range(2):
            with open(output_path, "w", encoding="utf-8") as file:
                file.write(code + "\n")
            try:
                ast.parse(code)
                # بيئة نظيفة: الكود المُولَّد لا يرى مفاتيح GEMINI/TELEGRAM/GITHUB
                run_res = subprocess.run(
                    [sys.executable, os.path.abspath(output_path), "--self-test"],
                    cwd=test_workdir, capture_output=True, text=True, timeout=20,
                    env=build_clean_env(),
                )
                if run_res.returncode == 0:
                    sample_out = (run_res.stdout or "نجح التنفيذ").strip()[:220]
                    status = f"✅ تم البناء والتشغيل الفعلي بنجاح | مخرج الاختبار: {sample_out}"
                    break
                err_trace = (run_res.stderr or "رمز خروج غير صفري")[:500]
            except Exception as exc:
                err_trace = str(exc)

            if attempt == 0:
                fix_prompt = (
                    f"أصلح الخطأ التالي في كود Python وأعد الكود كاملاً داخل {FENCE}python فقط دون شرح:\n"
                    f"الخطأ:\n{err_trace}\n\nالكود:\n{FENCE}python\n{code}\n{FENCE}"
                )
                fixed_resp, fix_ok = call_gemini_api(fix_prompt, active_models, temperature=0.1)
                fixed_code = extract_python_block(fixed_resp) if fix_ok else None
                if fixed_code:
                    code = fixed_code
                else:
                    status = f"⚠️ تم توليد الكود مع ملاحظة تشغيلية: {err_trace[:140]}"
                    break
            else:
                status = f"⚠️ تم توليد الكود مع ملاحظة تشغيلية: {err_trace[:140]}"
    finally:
        shutil.rmtree(test_workdir, ignore_errors=True)

    executive_summary += f"\n\n🛠️ **حالة الأصل البرمجي الجاهز:** {status}"
    return output_path, executive_summary


# ==================== 8. التقرير الاستراتيجي الأسبوعي ====================
def run_weekly_synthesis(active_models):
    print("📅 بدء إعداد التقرير الاستراتيجي الأسبوعي...")
    if not os.path.isdir(REPORT_DIR):
        print("ℹ️ لا يوجد مجلد تقارير بعد.")
        return
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    reports = []
    for filename in sorted(os.listdir(REPORT_DIR)):
        if not filename.startswith("report_") or not filename.endswith(".md"):
            continue
        path = os.path.join(REPORT_DIR, filename)
        if datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc) >= cutoff:
            with open(path, "r", encoding="utf-8") as file:
                reports.append(file.read()[:3500])
    if not reports:
        print("ℹ️ لا توجد تقارير خلال آخر 7 أيام.")
        return
    corpus = "\n\n===\n\n".join(reports)[:24000]
    prompt = f"""
أنت استراتيجي تقني وتجاري. حلل تقارير الأسبوع التالية:
{corpus}

اكتب بالعربية:
1. خريطة التوجهات: ما التقنيات والأنماط المتكررة بقوة؟
2. أفضل ثلاث فرص ربحية ونموذج الربح لكل منها.
3. فجوات السوق المستخلصة من نقاشات Reddit وHacker News.
4. مشروع واحد محدد وخطة تنفيذه خلال 48 ساعة.
"""
    synthesis, ok = call_gemini_api(prompt, active_models)
    if not ok:
        print(f"❌ فشل التقرير الأسبوعي: {synthesis}")
        return
    date_text = now.strftime("%Y-%m-%d")
    os.makedirs(REPORT_DIR, exist_ok=True)
    output_path = os.path.join(REPORT_DIR, f"weekly_synthesis_{date_text}.md")
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(f"# التقرير الاستراتيجي الأسبوعي ({date_text})\n\n{synthesis}")
    tg_msg = (
        f"📅 <b>التقرير الاستراتيجي الأسبوعي ({date_text})</b>\n\n"
        f"{md_to_tg_html(synthesis[:3400])}"
    )
    send_telegram_html(tg_msg)
    print(f"🏁 تم حفظ التقرير: {output_path}")


# ==================== 9. واجهة تيليجرام المطوية وإرسال الملفات ====================
def md_to_tg_html(text):
    """تهريب HTML ثم تحويل **نص** إلى <b>نص</b> بما يتوافق مع parse_mode=HTML."""
    escaped = html.escape(text or "")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return escaped


def format_telegram_cards(now_str, exec_summary, analyzed_items):
    header = (
        f"📡 <b>تقرير الرادار ({now_str} UTC)</b>\n"
        f"⚙️ {html.escape(MODE_LABELS[RADAR_MODE])}\n"
    )
    if exec_summary:
        header += f"\n🏆 <b>الفرصة الذهبية:</b>\n{md_to_tg_html(exec_summary)}\n"
    messages = []
    current = header + "\n━━━━━━━━━━━━━━\n"
    for index, item in enumerate(analyzed_items, 1):
        raw_analysis = item.get("analysis", "")
        analysis = md_to_tg_html(raw_analysis[:2200])
        if len(raw_analysis) > 2200:
            analysis += "\n… (التفاصيل الكاملة في التقرير المحفوظ)"
        safe_url = html.escape(item["url"], quote=True)
        card = (
            f"\n🔹 <b>{index}. {html.escape(item['title'])}</b>\n"
            f"📂 {html.escape(item['domain'])}\n"
            f"📊 {html.escape(item['metrics'])}\n"
            f"🛡️ {html.escape(item.get('security', 'آمن مبدئياً 🟢'))} | "
            f'🔗 <a href="{safe_url}">فتح المصدر</a>\n'
            f"<blockquote expandable>{analysis}</blockquote>\n"
        )
        if len(current) + len(card) > 3900 and current.strip():
            messages.append(current.strip())
            current = card
        else:
            current += card
    if current.strip():
        messages.append(current.strip())
    return messages


def send_telegram_html(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ مفاتيح تيليجرام غير مضبوطة.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    try:
        http_request(url, method="POST", headers={"Content-Type": "application/json"}, data=payload, timeout=15)
        print("✅ تم إرسال رسالة تيليجرام.")
        time.sleep(1.2)
    except urllib.error.HTTPError as exc:
        err_detail = exc.read().decode("utf-8", errors="replace")
        print(f"⚠️ تعذر إرسال HTML ({exc.code})، جاري الإرسال كنص عادي...")
        plain = re.sub(r"<[^>]+>", "", html.unescape(message))[:3800]
        fallback = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID, "text": plain, "disable_web_page_preview": True,
        }).encode("utf-8")
        try:
            http_request(url, method="POST", headers={"Content-Type": "application/json"}, data=fallback, timeout=15)
            print("✅ تم إرسال الرسالة كنص بديل.")
        except Exception as sub_exc:
            print(f"❌ فشل إرسال تيليجرام: {sub_exc} | {err_detail[:120]}")
    except Exception as exc:
        print(f"❌ خطأ إرسال تيليجرام: {exc}")


def send_telegram_document(file_path, caption=""):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not os.path.isfile(file_path):
        return
    boundary = f"----RadarBoundary{int(time.time() * 1000)}"
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as file:
        file_bytes = file.read()
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{TELEGRAM_CHAT_ID}\r\n'.encode("utf-8"),
        f'--{boundary}\r\nContent-Disposition: form-data; name="caption"\r\n\r\n{caption[:1000]}\r\n'.encode("utf-8"),
        f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\nContent-Type: text/x-python\r\n\r\n'.encode("utf-8"),
        file_bytes,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    try:
        http_request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument",
            method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            data=b"".join(parts), timeout=25,
        )
        print(f"📎 تم إرسال الملف {filename} إلى تيليجرام.")
    except Exception as exc:
        print(f"⚠️ تعذر إرسال الملف: {exc}")


# ==================== 10. نقطة التشغيل الرئيسية ====================
def main():
    sandbox_mode_txt = "مفعّل بأقصى طاقة (بيئة سحابية)" if IS_CLOUD_SANDBOX else "متوقف افتراضياً (بيئة محلية)"
    print(f"🚀 بدء التشغيل | {MODE_LABELS[RADAR_MODE]} | المختبر الحي: {sandbox_mode_txt}")
    active_models = discover_active_gemini_models()
    if RADAR_MODE == "weekly":
        run_weekly_synthesis(active_models)
        return

    memory = load_memory()
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d_%H-%M")
    discoveries = (
        check_github_breakouts(memory)
        + fetch_github_discoveries(memory)
        + fetch_hn_discoveries(memory)
        + fetch_producthunt_discoveries(memory)
        + fetch_huggingface_papers(memory)
        + fetch_reddit_opportunities(memory)
    )
    if not discoveries:
        print("ℹ️ لا توجد مستجدات جديدة في هذه الدورة.")
        save_memory(memory)
        return

    analyzed_items = []
    report_sections = []
    for item in discoveries:
        print(f"🔍 فحص وتحليل: {item['title']} [{item['domain']}]")
        probe = technical_probe(item)
        analysis, success = analyze_discovery(item, probe, active_models)
        if success:
            previous = memory.get(item["uid"], {})
            memory[item["uid"]] = {
                "title": item["title"], "stars": item.get("stars", 0),
                "first_seen": previous.get("first_seen", now.isoformat()),
                "last_seen": now.isoformat(),
                "breakout_alerted": item.get("is_breakout", False),
            }
            analyzed_items.append({**item, "analysis": analysis})
        report_sections.append(
            f"### {item['title']}\n"
            f"- **المجال:** {item['domain']}\n"
            f"- **المؤشرات:** {item['metrics']}\n"
            f"- **الأمان:** {item.get('security', 'آمن مبدئياً 🟢')}\n"
            f"- **الرابط:** {item['url']}\n\n{analysis}\n"
        )
        time.sleep(2.2)

    mvp_path, executive_summary = build_and_verify_golden_asset(analyzed_items, active_models, timestamp)
    clean_summary = re.sub(r"<[^>]+>", "", executive_summary or "")
    report = (
        f"# تقرير الرادار ({timestamp} UTC)\n"
        f"**الوضع التشغيلي:** {MODE_LABELS[RADAR_MODE]}\n\n"
    )
    if clean_summary:
        report += f"## 🏆 الفرصة الذهبية\n{clean_summary}\n\n---\n\n"
    report += "\n---\n\n".join(report_sections)
    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = os.path.join(REPORT_DIR, f"report_{RADAR_MODE}_{timestamp}.md")
    with open(report_path, "w", encoding="utf-8") as file:
        file.write(report)
    save_memory(memory)

    if analyzed_items:
        for message in format_telegram_cards(timestamp, executive_summary, analyzed_items):
            send_telegram_html(message)
        if mvp_path:
            send_telegram_document(
                mvp_path,
                caption="🚀 الأصل البرمجي الجاهز (MVP) للفرصة الذهبية - تم بناؤه واختباره في السحابة.",
            )
    print(f"🏁 اكتملت الدورة. التقرير محفوظ في: {report_path}")


if __name__ == "__main__":
    main()
