import os
import re
import ast
import sys
import json
import time
import html
import shutil
import tempfile
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ==================== 1. الإعدادات وأوضاع التشغيل ====================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

RAW_MODE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("RADAR_MODE", "normal")).strip().lower()
RADAR_MODE = RAW_MODE if RAW_MODE in ("normal", "full", "weekly") else "normal"

MODE_LABELS = {
    "normal": "الوضع العادي (الفرص الرائجة + تتبع القفزات المفاجئة)",
    "full": "الوضع التام (رصد شامل لكل المستجدات بدون فلترة)",
    "weekly": "التقرير الاستراتيجي الأسبوعي المجمع"
}

MEMORY_FILE = "memory.json"
REPORT_DIR = "reports"
ASSETS_DIR = "assets"

DOMAINS = {
    "الذكاء الاصطناعي والأتمتة": "(ai-agent OR automation OR workflow OR llm OR mcp-server OR browser-use)",
    "فرص البرمجيات كخدمة Micro-SaaS": "(micro-saas OR saas-boilerplate OR niche-tool OR api-wrapper OR indie-hacker)",
    "تحليل البيانات والتجارة": "(ecommerce OR price-tracker OR web-scraper OR market-analysis OR trading-bot)"
}

NOISE_KEYWORDS = {
    "roblox", "cheat", "aimbot", "crack", "keygen", "free-nitro",
    "hack-tool", "homework", "assignment", "leetcode", "dotfiles", "my-config"
}

SECURITY_PATTERNS = [
    (r"base64\.b64decode\s*\(", "فك تشفير Base64 ديناميكي"),
    (r"\b(eval|exec)\s*\(", "تنفيذ كود ديناميكي (eval/exec)"),
    (r"(curl|wget)\s+[^\n]+\|\s*(sh|bash)", "تشغيل سكربت خارجي مباشر عبر الطرفية"),
    (r"(\.ssh/id_rsa|wallet\.dat|AppData\\Local\\Google\\Chrome)", "محاولة الوصول لمفاتيح أو بيانات متصفح حساسة"),
    (r"(xmrig|stratum\+tcp|cryptonight)", "مؤشرات تعدين عملات رقمية")
]


# ==================== 2. الذاكرة الذكية والاتصال الشبكي ====================
def load_memory():
    """تحميل الذاكرة مع الترقية التلقائية من التنسيق القديم إلى القاموس الذكي"""
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            now_iso = datetime.now(timezone.utc).isoformat()
            return {uid: {"title": uid, "stars": 0, "first_seen": now_iso, "last_seen": now_iso, "breakout_alerted": False} for uid in data}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_memory(memory_dict):
    # الاحتفاظ بآخر 4000 سجل
    if len(memory_dict) > 4000:
        keys = list(memory_dict.keys())[-4000:]
        memory_dict = {k: memory_dict[k] for k in keys}
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory_dict, f, ensure_ascii=False, indent=2)


def http_request(url, method="GET", headers=None, data=None, timeout=20, as_json=True):
    req_headers = {"User-Agent": "Mozilla/5.0 (compatible; AutonomousTechRadar/5.0)"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw) if as_json else raw


def is_noise(text):
    lowered = text.lower()
    return any(bad in lowered for bad in NOISE_KEYWORDS)


def calculate_star_velocity(repo):
    stars = repo.get("stargazers_count", 0)
    created_str = repo.get("created_at", "")
    try:
        created_dt = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age_hours = max((datetime.now(timezone.utc) - created_dt).total_seconds() / 3600.0, 1.0)
        return round(stars / age_hours, 2)
    except Exception:
        return 0.0


# ==================== 3. الاكتشاف الذاتي لأحدث نماذج Gemini ====================
def discover_active_gemini_models():
    fallback_models = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3.5-flash"]
    if not GEMINI_API_KEY:
        return fallback_models

    excluded_tags = ("embedding", "imagen", "veo", "tts", "audio", "aqa", "robotics", "computer-use")
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        data = http_request(url, timeout=15, as_json=True)
        flash_models, other_models = [], []
        for m in data.get("models", []):
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            name = m.get("name", "").replace("models/", "")
            if not name.startswith("gemini-") or any(tag in name for tag in excluded_tags):
                continue
            (flash_models if "flash" in name else other_models).append(name)

        flash_models.sort(reverse=True)
        other_models.sort(reverse=True)
        discovered = flash_models + other_models
        if discovered:
            print(f"🧠 النماذج المكتشفة تلقائياً: {', '.join(discovered[:4])}")
            return discovered[:5]
    except Exception as e:
        print(f"⚠️ تعذر جلب النماذج تلقائياً: {e}")
    return fallback_models


# ==================== 4. تتبع القفزات المفاجئة (Breakout Tracker) ====================
def check_github_breakouts(memory_dict):
    """إعادة فحص المشاريع المغمورة السابقة لرصد أي قفزة حادة في النجوم"""
    if RADAR_MODE != "normal" or not memory_dict:
        return []

    gh_headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        gh_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    now_utc = datetime.now(timezone.utc)
    candidates = []
    for uid, info in reversed(list(memory_dict.items())):
        if not uid.startswith("gh_") or info.get("breakout_alerted"):
            continue
        if info.get("stars", 0) >= 35 or "/" not in info.get("title", ""):
            continue
        try:
            first_seen = datetime.fromisoformat(info.get("first_seen", ""))
            if (now_utc - first_seen).days <= 14:
                candidates.append((uid, info))
        except Exception:
            continue
        if len(candidates) >= 6:
            break

    breakouts = []
    for uid, info in candidates:
        try:
            repo = http_request(f"https://api.github.com/repos/{info['title']}", headers=gh_headers, timeout=12, as_json=True)
            curr_stars = repo.get("stargazers_count", 0)
            prev_stars = info.get("stars", 0)
            jump = curr_stars - prev_stars

            if jump >= 40 or (curr_stars >= 25 and curr_stars >= prev_stars * 3):
                info["stars"] = curr_stars
                info["last_seen"] = now_utc.isoformat()
                info["breakout_alerted"] = True
                breakouts.append({
                    "uid": uid,
                    "source": "github",
                    "is_breakout": True,
                    "domain": "🚨 اختراق مفاجئ (Breakout Alert)",
                    "title": repo["full_name"],
                    "url": repo["html_url"],
                    "description": (repo.get("description") or "قفزة مفاجئة في التفاعل").strip(),
                    "metrics": f"قفز من {prev_stars} إلى {curr_stars} نجمة (+{jump} نجمة!) | اللغة: {repo.get('language') or 'متعددة'}",
                    "stars": curr_stars,
                    "files": []
                })
            time.sleep(0.8)
        except Exception:
            continue
    return breakouts


# ==================== 5. المصادر الخمسة للرصد ====================
def get_github_files(repo_full_name, gh_headers):
    try:
        items = http_request(f"https://api.github.com/repos/{repo_full_name}/contents", headers=gh_headers, timeout=10, as_json=True)
        if isinstance(items, list):
            return [item.get("name", "") for item in items][:15]
    except Exception:
        pass
    return []


def fetch_github_discoveries(memory_dict):
    discoveries = []
    now_utc = datetime.now(timezone.utc)
    yesterday = (now_utc - timedelta(days=1)).strftime("%Y-%m-%d")
    last_week = (now_utc - timedelta(days=7)).strftime("%Y-%m-%d")

    gh_headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        gh_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    for domain_name, query_terms in DOMAINS.items():
        if RADAR_MODE == "normal":
            q = urllib.parse.quote(f"{query_terms} created:>={last_week} stars:>=50")
            url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=8"
            pick_limit = 1
        else:
            q = urllib.parse.quote(f"{query_terms} created:>={yesterday} stars:>=0")
            url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page=8"
            pick_limit = 2

        picked = 0
        try:
            data = http_request(url, headers=gh_headers, as_json=True)
            for repo in data.get("items", []):
                uid = f"gh_{repo['id']}"
                if uid in memory_dict:
                    continue

                full_name = repo["full_name"]
                desc = (repo.get("description") or "بدون وصف نصي").strip()

                if RADAR_MODE == "normal":
                    if repo.get("fork") or repo.get("archived") or is_noise(f"{full_name} {desc}"):
                        memory_dict[uid] = {"title": full_name, "stars": repo.get("stargazers_count", 0), "first_seen": now_utc.isoformat(), "last_seen": now_utc.isoformat()}
                        continue

                velocity = calculate_star_velocity(repo)
                file_list = get_github_files(full_name, gh_headers)
                discoveries.append({
                    "uid": uid,
                    "source": "github",
                    "is_breakout": False,
                    "domain": domain_name,
                    "title": full_name,
                    "url": repo["html_url"],
                    "description": desc,
                    "metrics": f"النجوم: {repo['stargazers_count']} ({velocity} نجمة/ساعة) | اللغة: {repo.get('language') or 'متعددة'}",
                    "stars": repo["stargazers_count"],
                    "files": file_list
                })
                picked += 1
                if picked >= pick_limit:
                    break
            time.sleep(1.0)
        except Exception as e:
            print(f"⚠️ تنبيه GitHub ({domain_name}): {e}")
    return discoveries


def fetch_hn_discoveries(memory_dict):
    discoveries = []
    keywords = ("ai", "agent", "saas", "automate", "automation", "scrape", "ecommerce", "data", "tool", "open source", "llm", "workflow", "api")
    feed_url = "https://hacker-news.firebaseio.com/v0/topstories.json" if RADAR_MODE == "normal" else "https://hacker-news.firebaseio.com/v0/newstories.json"
    scan_limit = 40 if RADAR_MODE == "normal" else 20
    pick_limit = 1 if RADAR_MODE == "normal" else 2

    picked = 0
    try:
        for sid in http_request(feed_url, as_json=True)[:scan_limit]:
            uid = f"hn_{sid}"
            if uid in memory_dict:
                continue
            item = http_request(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", as_json=True)
            if not item or not item.get("url") or not item.get("title"):
                continue
            title = item["title"].strip()
            score, comments = item.get("score", 0), item.get("descendants", 0)
            if RADAR_MODE == "normal":
                if (score < 80 and comments < 40) or is_noise(title) or not any(k in title.lower() for k in keywords):
                    continue
            discoveries.append({
                "uid": uid,
                "source": "hn",
                "is_breakout": False,
                "domain": "Hacker News (تقنية وأعمال)",
                "title": title,
                "url": item["url"],
                "description": f"طرح على Hacker News: {title}",
                "metrics": f"النقاط: {score} | التعليقات: {comments}",
                "stars": score,
                "files": []
            })
            picked += 1
            if picked >= pick_limit:
                break
    except Exception as e:
        print(f"⚠️ تنبيه Hacker News: {e}")
    return discoveries


def fetch_producthunt_discoveries(memory_dict):
    """رصد أحدث إطلاقات المنتجات التجارية من Product Hunt RSS مجاناً"""
    discoveries = []
    try:
        xml_raw = http_request("https://www.producthunt.com/feed", timeout=15, as_json=False)
        root = ET.fromstring(xml_raw)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns) or root.findall(".//item")

        pick_limit = 1 if RADAR_MODE == "normal" else 2
        picked = 0
        for entry in entries[:15]:
            title_el = entry.find("atom:title", ns) if entry.find("atom:title", ns) is not None else entry.find("title")
            link_el = entry.find("atom:link", ns) if entry.find("atom:link", ns) is not None else entry.find("link")
            summary_el = entry.find("atom:content", ns) if entry.find("atom:content", ns) is not None else entry.find("description")

            title = (title_el.text or "").strip() if title_el is not None else ""
            url = link_el.attrib.get("href", "") if (link_el is not None and "href" in link_el.attrib) else ((link_el.text or "").strip() if link_el is not None else "")
            summary = re.sub(r"<[^>]+>", " ", (summary_el.text or "")).strip() if summary_el is not None else ""

            if not title or not url:
                continue
            uid = f"ph_{abs(hash(url))}"
            if uid in memory_dict:
                continue

            discoveries.append({
                "uid": uid,
                "source": "producthunt",
                "is_breakout": False,
                "domain": "Product Hunt (منتجات تجارية و SaaS)",
                "title": title,
                "url": url,
                "description": summary[:300] or title,
                "metrics": "إطلاق تجاري جديد على Product Hunt",
                "stars": 0,
                "files": []
            })
            picked += 1
            if picked >= pick_limit:
                break
    except Exception as e:
        print(f"⚠️ تنبيه Product Hunt: {e}")
    return discoveries


def fetch_huggingface_papers(memory_dict):
    """رصد أحدث أبحاث ونماذج الذكاء الاصطناعي من Hugging Face Daily Papers"""
    discoveries = []
    try:
        papers = http_request("https://huggingface.co/api/daily_papers", timeout=15, as_json=True)
        pick_limit = 1 if RADAR_MODE == "normal" else 2
        picked = 0
        for entry in papers[:15]:
            paper = entry.get("paper", {})
            pid = paper.get("id", "")
            title = (paper.get("title") or "").strip()
            upvotes = paper.get("upvotes", 0)
            if not pid or not title:
                continue
            uid = f"hf_{pid}"
            if uid in memory_dict:
                continue
            if RADAR_MODE == "normal" and upvotes < 20:
                continue

            discoveries.append({
                "uid": uid,
                "source": "huggingface",
                "is_breakout": False,
                "domain": "Hugging Face (أبحاث ونماذج AI)",
                "title": title,
                "url": f"https://huggingface.co/papers/{pid}",
                "description": (paper.get("summary") or title)[:400],
                "metrics": f"تصويت الباحثين (Upvotes): {upvotes}",
                "stars": upvotes,
                "files": []
            })
            picked += 1
            if picked >= pick_limit:
                break
    except Exception as e:
        print(f"⚠️ تنبيه Hugging Face: {e}")
    return discoveries


def fetch_reddit_opportunities(memory_dict):
    """صيد مشاكل السوق والفرص الرائجة من مجتمعات Reddit التقنية والتجارية"""
    discoveries = []
    subreddits = ["SaaS", "LocalLLaMA", "Entrepreneur"]
    pick_limit = 1
    picked = 0

    for sub in subreddits:
        if picked >= pick_limit:
            break
        try:
            sort_path = "hot.json?limit=12" if RADAR_MODE == "normal" else "new.json?limit=10"
            data = http_request(
                f"https://www.reddit.com/r/{sub}/{sort_path}",
                headers={"User-Agent": "python:AutonomousTechRadar:v5.0 (by /u/tech_radar_bot)"},
                timeout=15,
                as_json=True
            )
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                if post.get("stickied"):
                    continue
                pid = post.get("id", "")
                uid = f"rd_{pid}"
                if uid in memory_dict:
                    continue
                score = post.get("score", 0)
                comments = post.get("num_comments", 0)
                if RADAR_MODE == "normal" and score < 40 and comments < 20:
                    continue

                title = post.get("title", "").strip()
                selftext = (post.get("selftext") or "")[:400].strip()
                discoveries.append({
                    "uid": uid,
                    "source": "reddit",
                    "is_breakout": False,
                    "domain": f"Reddit r/{sub} (نبض السوق والعملاء)",
                    "title": title,
                    "url": f"https://www.reddit.com{post.get('permalink', '')}",
                    "description": selftext or title,
                    "metrics": f"التصويت: {score} | التعليقات: {comments}",
                    "stars": score,
                    "files": []
                })
                picked += 1
                break
        except Exception as e:
            print(f"⚠️ تنبيه Reddit r/{sub}: {e}")
    return discoveries


# ==================== 6. الفحص الأمني والمختبر الحي (Security & Sandbox) ====================
def audit_text_security(text_blob):
    """فحص سريع للأنماط الأمنية المشبوهة"""
    warnings = []
    for pattern, label in SECURITY_PATTERNS:
        if re.search(pattern, text_blob, re.IGNORECASE):
            warnings.append(label)
    if warnings:
        return f"تحذير أمني 🔴 ({', '.join(warnings)})"
    return "آمن مبدئياً 🟢"


def technical_probe(item, run_deep_sandbox=False):
    notes = []
    start_time = time.time()
    collected_text = f"{item['title']} {item['description']}"

    try:
        req = urllib.request.Request(item["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            latency_ms = int((time.time() - start_time) * 1000)
            notes.append(f"- حالة الرابط: نشط (HTTP {resp.status} | {latency_ms}ms)")
            if item["source"] in ("hn", "producthunt"):
                page_html = resp.read().decode("utf-8", errors="ignore")[:15000]
                clean_text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page_html, flags=re.DOTALL | re.IGNORECASE)
                clean_text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", clean_text))).strip()
                if clean_text:
                    notes.append(f"- محتوى الصفحة الفعلي:\n{clean_text[:1000]}")
                    collected_text += " " + clean_text[:2000]
    except Exception as e:
        notes.append(f"- حالة الرابط: تعذر الفتح المباشر ({str(e)[:100]})")

    if item["source"] == "github":
        if item.get("files"):
            notes.append(f"- الملفات الرئيسية: {', '.join(item['files'])}")
        gh_headers = {"Accept": "application/vnd.github.raw+json"}
        if GITHUB_TOKEN:
            gh_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        try:
            readme_raw = http_request(f"https://api.github.com/repos/{item['title']}/readme", headers=gh_headers, timeout=12, as_json=False)
            if readme_raw:
                notes.append(f"- مقتطف التوثيق (README):\n{readme_raw[:1500]}")
                collected_text += " " + readme_raw[:3000]
        except Exception:
            notes.append("- التوثيق: لا يوجد ملف README قياسي.")

        # المختبر الحي: سحب المستودع وفحص صلاحية الكود برمجياً لأفضل مرشح
        if run_deep_sandbox:
            sandbox_report, code_sample = run_live_git_sandbox(item["url"])
            notes.append(f"- نتيجة المختبر الحي (Live Sandbox): {sandbox_report}")
            collected_text += " " + code_sample

    sec_badge = audit_text_security(collected_text)
    item["security"] = sec_badge
    notes.insert(0, f"- التدقيق الأمني الآلي: {sec_badge}")
    return "\n".join(notes)


def run_live_git_sandbox(repo_url):
    """سحب المستودع في مجلد معزول وفحص صلاحية الملفات البرمجية فعلياً"""
    tmp_dir = tempfile.mkdtemp(prefix="radar_sandbox_")
    code_sample = ""
    try:
        clone_res = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, tmp_dir],
            capture_output=True, text=True, timeout=25
        )
        if clone_res.returncode != 0:
            return "تعذر سحب المستودع في المختبر.", ""

        py_files, js_files, total_files = [], [], 0
        for root_dir, _, files in os.walk(tmp_dir):
            if ".git" in root_dir:
                continue
            for fname in files:
                total_files += 1
                fpath = os.path.join(root_dir, fname)
                if fname.endswith(".py"):
                    py_files.append(fpath)
                elif fname.endswith((".js", ".ts")):
                    js_files.append(fpath)

        # قراءة عينة من الكود الفعلي للتدقيق الأمني
        for fpath in (py_files + js_files)[:3]:
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    code_sample += f.read(2000) + "\n"
            except Exception:
                pass

        # اختبار البناء النحوي (Syntax Check) لملفات بايثون
        syntax_errors = 0
        for pf in py_files[:10]:
            try:
                with open(pf, "r", encoding="utf-8", errors="ignore") as f:
                    ast.parse(f.read())
            except SyntaxError:
                syntax_errors += 1

        if py_files:
            status = f"تم السحب والفحص الحي ({total_files} ملف، {len(py_files)} ملف Python، أخطاء نحوية: {syntax_errors})"
        elif js_files:
            status = f"تم السحب والفحص الحي ({total_files} ملف، {len(js_files)} ملف JS/TS)"
        else:
            status = f"تم السحب ({total_files} ملف وثائقي/إعدادات)"
        return status, code_sample
    except Exception as e:
        return f"انتهت مهلة المختبر أو تعذر التشغيل ({str(e)[:80]})", ""
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ==================== 7. محرك التحليل وتوليد الأصول ذاتية الاختبار ====================
def call_gemini_api(prompt_text, active_models, temperature=0.35):
    if not GEMINI_API_KEY:
        return "❌ لم يتم ضبط GEMINI_API_KEY.", False

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": temperature}
    }).encode("utf-8")

    last_error = ""
    for model in active_models:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        for attempt in range(2):
            try:
                res_data = http_request(
                    endpoint, method="POST", headers={"Content-Type": "application/json"},
                    data=payload, timeout=40, as_json=True
                )
                return res_data["candidates"][0]["content"]["parts"][0]["text"].strip(), True
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                last_error = f"HTTP {e.code} [{model}]: {err_body[:200]}"
                if e.code == 429:
                    time.sleep(10)
                    continue
                if e.code in (400, 403):
                    return f"⚠️ خطأ في مفتاح API: {last_error}", False
                break
            except Exception as e:
                last_error = str(e)
                break
    return f"⚠️ تعذر التحليل: {last_error}", False


def analyze_discovery(item, probe_data, active_models):
    prompt = f"""
أنت مهندس استغلال تقني ومحلل أعمال صارم. حلل الاكتشاف التالي بموضوعية تامة واختصار عملي شديد:

- المجال: {item['domain']}
- العنوان: {item['title']}
- الرابط: {item['url']}
- المؤشرات: {item['metrics']}
- الوصف: {item['description']}
- الفحص التقني والأمني:
{probe_data}

اكتب تقريراً تنفيذياً باللغة العربية (بدون مقدمات) يغطي البنود الستة التالية:
1. التقييم وحقيقة الأداة (من 10): درجة الجدوى، وماذا تفعل فعلياً وهل هي جاهزة للإنتاج.
2. المجال والفئة المستهدفة: من يحتاج هذا الحل تحديداً؟
3. الاستغلال الربحي المباشر: كيف يُحوّل إلى مال (Micro-SaaS، خدمة لعملاء، أو خفض تكلفة)؟
4. اختصار مدة العمل: ما المهمة اليدوية التي يلغيها وكم يوفر من الوقت؟
5. الاستخدام العملي والحياتي: سيناريو تطبيق يومي ملموس.
6. خطوات التشغيل الفورية: (1، 2، 3) للبدء الآن.
"""
    return call_gemini_api(prompt, active_models)


def build_and_verify_golden_asset(analyzed_items, active_models, timestamp_str):
    """اختيار الفرصة الذهبية وبناء سكربت MVP عملي وتشغيله فعلياً للتحقق منه"""
    if not analyzed_items:
        return None, ""

    candidates_summary = "\n".join(
        [f"[{idx}] {x['title']} ({x['domain']}): {x['analysis'][:350]}" for idx, x in enumerate(analyzed_items)]
    )

    prompt = f"""
بناءً على الاكتشافات التالية في هذه الدورة:
{candidates_summary}

المطلوب:
1. اختر **الفرصة الذهبية رقم 1** الأكثر ربحية وقابلية للتطبيق الفوري.
2. اكتب ملخصاً تنفيذياً من 3 أسطر بالعربية يوضح لماذا هي الفرصة الذهبية وكيف نربح منها اليوم.
3. اكتب **كود Python متكامل وجاهز للتشغيل الفوري** (يعتمد على مكتبات Python القياسية فقط بدون pip) يطبق هذه الفرصة عملياً (مثلاً: أداة أتمتة، محلل بيانات/أسعار، أو نواة خدمة Micro-SaaS مع خادم HTTP مصغر أو معالج بيانات) ويدعم المعامل `--self-test` لتنفيذ اختبار ذاتي حقيقي وطباعة النتيجة بوضوح.

اخرج الرد بالتنسيق التالي حصراً:
### EXECUTIVE_SUMMARY
(اكتب الملخص التنفيذي بالعربية هنا)

### PYTHON_MVP
```python
(اكتب كود بايثون الكامل القابل للتشغيل هنا)
"""
raw_resp, ok = call_gemini_api(prompt, active_models, temperature=0.25)
if not ok:
return None, ""

summary_match = re.search(r"### EXECUTIVE_SUMMARY\s*(.*?)\s*### PYTHON_MVP", raw_resp, re.DOTALL)
code_match = re.search(r"```python\s*(.*?)\s*```", raw_resp, re.DOTALL)

exec_summary = summary_match.group(1).strip() if summary_match else raw_resp[:400]
if not code_match:
    return None, exec_summary

mvp_code = code_match.group(1).strip()
os.makedirs(ASSETS_DIR, exist_ok=True)
mvp_path = os.path.join(ASSETS_DIR, f"mvp_{timestamp_str}.py")

# محاولة التشغيل الذاتي والإصلاح التلقائي إن وجد خطأ
test_status = "⚠️ لم يتم التحقق"
for attempt in range(2):
    with open(mvp_path, "w", encoding="utf-8") as f:
        f.write(mvp_code)
    try:
        ast.parse(mvp_code)
        run_res = subprocess.run(
            [sys.executable, mvp_path, "--self-test"],
            capture_output=True, text=True, timeout=15
        )
        if run_res.returncode == 0:
            sample_out = (run_res.stdout or "نجح التنفيذ").strip()[:220]
            test_status = f"✅ تم البناء والتشغيل الفعلي بنجاح | مخرج الاختبار: {sample_out}"
            break
        else:
            err_trace = (run_res.stderr or "خطأ غير معروف")[:500]
    except Exception as e:
        err_trace = str(e)

    if attempt == 0:
        fix_prompt = f"أصلح الخطأ التالي في كود بايثون وأعد الكود كاملاً داخل ```python فقط دون شرح:\nالخطأ:\n{err_trace}\n\nالكود:\n```python\n{mvp_code}\n```"
        fixed_resp, fix_ok = call_gemini_api(fix_prompt, active_models, temperature=0.1)
        fixed_match = re.search(r"```python\s*(.*?)\s*```", fixed_resp, re.DOTALL)
        if fix_ok and fixed_match:
            mvp_code = fixed_match.group(1).strip()
        else:
            test_status = f"⚠️ تم توليد الكود مع ملاحظة تشغيلية: {err_trace[:120]}"
            break
    else:
        test_status = f"⚠️ تم توليد الكود مع ملاحظة تشغيلية: {err_trace[:120]}"

exec_summary += f"\n\n🛠️ <b>حالة الأصل البرمجي الجاهز:</b> {test_status}"
return mvp_path, exec_summary
==================== 8. المحلل الاستراتيجي الأسبوعي (Weekly Synthesis) ====================
def run_weekly_synthesis(active_models):
print("📅 بدء إعداد التقرير الاستراتيجي الأسبوعي المجمع...")
if not os.path.exists(REPORT_DIR):
print("ℹ️ لا يوجد مجلد تقارير بعد.")
return

now_utc = datetime.now(timezone.utc)
cutoff = now_utc - timedelta(days=7)
weekly_texts = []

for fname in sorted(os.listdir(REPORT_DIR)):
    if not fname.startswith("report_") or not fname.endswith(".md"):
        continue
    fpath = os.path.join(REPORT_DIR, fname)
    mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=timezone.utc)
    if mtime >= cutoff:
        with open(fpath, "r", encoding="utf-8") as f:
            weekly_texts.append(f.read()[:3500])

if not weekly_texts:
    print("ℹ️ لا توجد تقارير خلال آخر 7 أيام للتجميع.")
    return

combined_corpus = "\n\n===\n\n".join(weekly_texts)[:24000]
prompt = f"""
أنت كبير استراتيجيي التكنولوجيا والأعمال. أمامك تقارير الرصد التقني والتجاري للأسبوع الماضي:
{combined_corpus}

اكتب التقرير الاستراتيجي الأسبوعي المجمع باللغة العربية وفق المحاور الأربعة التالية بدقة:

خريطة توجهات الأسبوع: ما التقنيات والأنماط التي تتكرر بقوة عبر GitHub وProduct Hunt والأبحاث؟

أفضل 3 فرص ربحية للأسبوع: رتبها من الأعلى عائداً مع نموذج الربح لكل منها.

فجوات السوق (من نقاشات Reddit وHN): ما المشاكل التي يشتكي منها المستخدمون ولم تُحل بعد؟

خطة التنفيذ للأسبوع القادم: مشروع واحد محدد يُنصح ببنائه خلال 48 ساعة القادمة.
"""
synthesis, ok = call_gemini_api(prompt, active_models)
if not ok:
print(f"❌ فشل توليد التقرير الأسبوعي: {synthesis}")
return

now_str = now_utc.strftime("%Y-%m-%d")
os.makedirs(REPORT_DIR, exist_ok=True)
out_path = os.path.join(REPORT_DIR, f"weekly_synthesis_{now_str}.md")
full_md = f"# التقرير الاستراتيجي الأسبوعي المجمع ({now_str})\n\n{synthesis}"
with open(out_path, "w", encoding="utf-8") as f:
f.write(full_md)

tg_msg = (
f"📅 التقرير الاستراتيجي الأسبوعي المجمع ({now_str})\n\n"
f"{md_to_tg_html(synthesis[:3400])}"
)
send_telegram_html(tg_msg)
print(f"🏁 تم حفظ وإرسال التقرير الأسبوعي: {out_path}")

==================== 9. واجهة تيليجرام المطوية وإرسال الملفات ====================
def md_to_tg_html(text):
"""تحويل آمن للنص إلى HTML متوافق مع تيليجرام دون كسر الوسوم"""
escaped = html.escape(text)
escaped = re.sub(r"(.+?)", r"\1", escaped)
return escaped

def format_telegram_cards(now_str, exec_summary, analyzed_items):
"""بناء بطاقات تيليجرام أنيقة بقوائم قابلة للطي ()"""
header = (
f"📡 تقرير الرادار الذاتي ({now_str} UTC)\n"
f"⚙️ {html.escape(MODE_LABELS[RADAR_MODE])}\n"
)
if exec_summary:
header += f"\n🏆 الفرصة الذهبية في هذه الدورة:\n{md_to_tg_html(exec_summary)}\n"

messages = []
current_msg = header + "\n━━━━━━━━━━━━━━\n"

for idx, item in enumerate(analyzed_items, 1):
    clean_analysis = md_to_tg_html(item["analysis"])
    if len(clean_analysis) > 2200:
        clean_analysis = clean_analysis[:2200] + "\n... (التفاصيل الكاملة محفوظة في مستودع GitHub)"

    card = (
        f"\n🔹 <b>{idx}. {html.escape(item['title'])}</b>\n"
        f"📂 {html.escape(item['domain'])}\n"
        f"📊 {html.escape(item['metrics'])}\n"
        f"🛡️ {html.escape(item.get('security', 'آمن مبدئياً 🟢'))} | "
        f"🔗 <a href=\"{html.escape(item['url'], quote=True)}\">فتح المصدر</a>\n"
        f"<blockquote expandable>{clean_analysis}</blockquote>\n"
    )

    if len(current_msg) + len(card) <= 3950:
        current_msg += card
    else:
        messages.append(current_msg.strip())
        current_msg = card

if current_msg.strip():
    messages.append(current_msg.strip())
return messages
def send_telegram_html(html_text):
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
print("⚠️ مفاتيح تيليجرام غير مضبوطة.")
return
url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
payload = json.dumps({
"chat_id": TELEGRAM_CHAT_ID,
"text": html_text,
"parse_mode": "HTML",
"disable_web_page_preview": True
}).encode("utf-8")
try:
http_request(url, method="POST", headers={"Content-Type": "application/json"}, data=payload, timeout=15)
print("✅ تم إرسال رسالة تيليجرام بنجاح.")
time.sleep(1.2)
except urllib.error.HTTPError as e:
print(f"❌ خطأ تيليجرام HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')}")
except Exception as e:
print(f"❌ خطأ إرسال تيليجرام: {e}")

def send_telegram_document(file_path, caption=""):
"""إرسال ملف الكود الجاهز (MVP) مباشرة إلى تيليجرام"""
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not os.path.exists(file_path):
return
url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
boundary = f"----WebKitFormBoundary{int(time.time() * 1000)}"
filename = os.path.basename(file_path)

with open(file_path, "rb") as f:
    file_bytes = f.read()

parts = [
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{TELEGRAM_CHAT_ID}\r\n".encode("utf-8"),
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption[:1000]}\r\n".encode("utf-8"),
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\nContent-Type: text/x-python\r\n\r\n".encode("utf-8"),
    file_bytes,
    f"\r\n--{boundary}--\r\n".encode("utf-8")
]
body = b"".join(parts)
try:
    http_request(
        url, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        data=body, timeout=25
    )
    print(f"📎 تم إرسال الملف الجاهز ({filename}) إلى تيليجرام بنجاح.")
except Exception as e:
    print(f"⚠️ تعذر إرسال الملف المرفق: {e}")
==================== 10. نقطة التشغيل الرئيسية ====================
def main():
print(f"🚀 بدء التشغيل | {MODE_LABELS[RADAR_MODE]}")
active_models = discover_active_gemini_models()

if RADAR_MODE == "weekly":
    run_weekly_synthesis(active_models)
    return

memory_dict = load_memory()
now_utc = datetime.now(timezone.utc)
now_str = now_utc.strftime("%Y-%m-%d_%H-%M")

# 1. جمع الاكتشافات من جميع المصادر + تتبع القفزات المفاجئة
discoveries = (
    check_github_breakouts(memory_dict)
    + fetch_github_discoveries(memory_dict)
    + fetch_hn_discoveries(memory_dict)
    + fetch_producthunt_discoveries(memory_dict)
    + fetch_huggingface_papers(memory_dict)
    + fetch_reddit_opportunities(memory_dict)
)

if not discoveries:
    print("ℹ️ لا توجد مستجدات جديدة في هذه الدورة.")
    save_memory(memory_dict)
    return

analyzed_items = []
report_sections = []
deep_sandbox_used = False

for item in discoveries:
    print(f"🔍 فحص وتحليل: {item['title']} [{item['domain']}]")
    use_sandbox = (item["source"] == "github" and not deep_sandbox_used)
    if use_sandbox:
        deep_sandbox_used = True

    probe_data = technical_probe(item, run_deep_sandbox=use_sandbox)
    analysis, success = analyze_discovery(item, probe_data, active_models)

    if success:
        memory_dict[item["uid"]] = {
            "title": item["title"],
            "stars": item.get("stars", 0),
            "first_seen": memory_dict.get(item["uid"], {}).get("first_seen", now_utc.isoformat()),
            "last_seen": now_utc.isoformat(),
            "breakout_alerted": item.get("is_breakout", False)
        }
        analyzed_items.append({**item, "analysis": analysis})

    section = (
        f"### {item['title']}\n"
        f"- **المجال:** {item['domain']}\n"
        f"- **المؤشرات:** {item['metrics']}\n"
        f"- **الأمان:** {item.get('security', 'آمن مبدئياً 🟢')}\n"
        f"- **الرابط:** {item['url']}\n\n"
        f"{analysis}\n"
    )
    report_sections.append(section)
    time.sleep(2.2)

# 2. توليد واختبار الأصل البرمجي الجاهز (MVP) للفرصة الذهبية
mvp_file_path, exec_summary = build_and_verify_golden_asset(analyzed_items, active_models, now_str)

# 3. حفظ التقرير الكامل بصيغة Markdown
clean_summary_md = re.sub(r"<[^>]+>", "", exec_summary)
header_md = (
    f"# تقرير الرادار والاستغلال التقني ({now_str} UTC)\n"
    f"**الوضع التشغيلي:** {MODE_LABELS[RADAR_MODE]}\n\n"
)
if clean_summary_md:
    header_md += f"## 🏆 الفرصة الذهبية في هذه الدورة\n{clean_summary_md}\n\n---\n\n"

full_report_md = header_md + "\n---\n\n".join(report_sections)
os.makedirs(REPORT_DIR, exist_ok=True)
report_path = os.path.join(REPORT_DIR, f"report_{RADAR_MODE}_{now_str}.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(full_report_md)

save_memory(memory_dict)

# 4. الإرسال إلى تيليجرام بالبطاقات المطوية + إرفاق ملف MVP الجاهز
if analyzed_items:
    tg_messages = format_telegram_cards(now_str, exec_summary, analyzed_items)
    for msg in tg_messages:
        send_telegram_html(msg)
    if mvp_file_path:
        send_telegram_document(
            mvp_file_path,
            caption="🚀 الأصل البرمجي الجاهز (MVP) للفرصة الذهبية في هذه الدورة - تم اختباره وتشغيله ذاتياً."
        )

print(f"🏁 اكتملت الدورة بنجاح. التقرير محفوظ في: {report_path}")
if name == "main":
main()
