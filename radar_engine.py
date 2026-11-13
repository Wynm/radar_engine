import ast
import hashlib
import html
import json
import os
import re
import sys
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

MODE_LABELS = {
    "normal": "الوضع العادي (الفرص الرائجة + تتبع القفزات المفاجئة)",
    "full": "الوضع الكامل (رصد شامل للمستجدات)",
    "weekly": "التقرير الاستراتيجي الأسبوعي المجمع",
}

MEMORY_FILE = "memory.json"
REPORT_DIR = "reports"
ASSETS_DIR = "assets"

DOMAINS = {
    "الذكاء الاصطناعي والأتمتة": "(ai-agent OR automation OR workflow OR llm OR mcp-server OR browser-use)",
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
    (r"(\.ssh/id_rsa|wallet\.dat|AppData\\Local\\Google\\Chrome)", "محاولة الوصول لبيانات حساسة"),
    (r"(xmrig|stratum\+tcp|cryptonight)", "مؤشرات تعدين عملات رقمية"),
]


def load_memory():
    """تحميل الذاكرة وترقية القائمة القديمة إلى قاموس عند الحاجة."""
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
                uid: {
                    "title": uid,
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
    """حفظ آخر 4000 سجل بطريقة تقلل احتمال تلف الملف."""
    if len(memory_dict) > 4000:
        memory_dict = dict(list(memory_dict.items())[-4000:])
    temp_path = f"{MEMORY_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(memory_dict, file, ensure_ascii=False, indent=2)
    os.replace(temp_path, MEMORY_FILE)


def http_request(url, method="GET", headers=None, data=None, timeout=20, as_json=True):
    request_headers = {"User-Agent": "Mozilla/5.0 (compatible; AutonomousTechRadar/5.0)"}
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
        age_hours = max((datetime.now(timezone.utc) - created).total_seconds() / 3600, 1)
        return round(repo.get("stargazers_count", 0) / age_hours, 2)
    except (TypeError, ValueError):
        return 0.0


# ==================== 2. اكتشاف نماذج Gemini ====================
def discover_active_gemini_models():
    fallback_models = ["gemini-2.0-flash", "gemini-1.5-flash"]
    if not GEMINI_API_KEY:
        return fallback_models
    excluded = ("embedding", "imagen", "veo", "tts", "audio", "aqa", "robotics", "computer-use")
    try:
        data = http_request(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}",
            timeout=15,
        )
        flash, other = [], []
        for model in (data or {}).get("models", []):
            if "generateContent" not in model.get("supportedGenerationMethods", []):
                continue
            name = model.get("name", "").removeprefix("models/")
            if not name.startswith("gemini-") or any(tag in name for tag in excluded):
                continue
            (flash if "flash" in name else other).append(name)
        discovered = sorted(flash, reverse=True) + sorted(other, reverse=True)
        if discovered:
            print(f"🧠 النماذج المتاحة: {', '.join(discovered[:4])}")
            return discovered[:5]
    except Exception as exc:
        print(f"⚠️ تعذر جلب نماذج Gemini: {exc}")
    return fallback_models


# ==================== 3. تتبع قفزات GitHub ====================
def github_headers(accept="application/vnd.github+json"):
    headers = {"Accept": accept}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def check_github_breakouts(memory_dict):
    if RADAR_MODE != "normal":
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


# ==================== 4. مصادر الاكتشاف ====================
def get_github_files(repo_name, headers):
    try:
        items = http_request(f"https://api.github.com/repos/{repo_name}/contents", headers=headers, timeout=10)
        if isinstance(items, list):
            return [item.get("name", "") for item in items[:15]]
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
            time.sleep(1)
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
            if not item or not item.get("url") or not item.get("title"):
                continue
            title = item["title"].strip()
            score, comments = item.get("score", 0), item.get("descendants", 0)
            if RADAR_MODE == "normal" and (
                (score < 80 and comments < 40) or is_noise(title)
                or not any(word in title.lower() for word in keywords)
            ):
                continue
            discoveries.append({
                "uid": uid, "source": "hn", "is_breakout": False,
                "domain": "Hacker News (تقنية وأعمال)", "title": title,
                "url": item["url"], "description": f"طرح على Hacker News: {title}",
                "metrics": f"النقاط: {score} | التعليقات: {comments}",
                "stars": score, "files": [],
            })
            if len(discoveries) >= pick_limit:
                break
    except Exception as exc:
        print(f"⚠️ تنبيه Hacker News: {exc}")
    return discoveries


def fetch_producthunt_discoveries(memory_dict):
    discoveries = []
    try:
        xml_raw = http_request("https://www.producthunt.com/feed", timeout=15, as_json=False)
        root = ET.fromstring(xml_raw)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns) or root.findall(".//item")
        pick_limit = 1 if RADAR_MODE == "normal" else 2
        for entry in entries[:15]:
            title_el = entry.find("atom:title", ns) or entry.find("title")
            link_el = entry.find("atom:link", ns) or entry.find("link")
            summary_el = entry.find("atom:content", ns) or entry.find("description")
            title = (title_el.text or "").strip() if title_el is not None else ""
            if link_el is None:
                url = ""
            else:
                url = link_el.attrib.get("href", (link_el.text or "").strip())
            summary = re.sub(r"<[^>]+>", " ", summary_el.text or "").strip() if summary_el is not None else ""
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
                headers={"User-Agent": "python:AutonomousTechRadar:v5.0"}, timeout=15,
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
            print(f"⚠️ تنبيه Reddit r/{subreddit}: {exc}")
    return discoveries


# ==================== 5. الفحص التقني والأمني ====================
def audit_text_security(text_blob):
    warnings = [label for pattern, label in SECURITY_PATTERNS if re.search(pattern, text_blob, re.IGNORECASE)]
    return f"تحذير أمني 🔴 ({', '.join(warnings)})" if warnings else "آمن مبدئياً 🟢"


def technical_probe(item):
    notes = []
    collected_text = f"{item['title']} {item['description']}"
    started = time.time()
    try:
        request = urllib.request.Request(item["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=12) as response:
            notes.append(f"- حالة الرابط: نشط (HTTP {response.status} | {int((time.time() - started) * 1000)}ms)")
            if item["source"] in ("hn", "producthunt"):
                page = response.read(15000).decode("utf-8", errors="replace")
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
            notes.append("- التوثيق: تعذر جلب README.")

    item["security"] = audit_text_security(collected_text)
    notes.insert(0, f"- التدقيق الأمني الآلي: {item['security']}")
    return "\n".join(notes)


# ==================== 6. التحليل وتوليد MVP ====================
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
                text = response["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text, True
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
أنت محلل تقني وتجاري صارم. حلل الاكتشاف التالي بموضوعية واختصار:
- المجال: {item['domain']}
- العنوان: {item['title']}
- الرابط: {item['url']}
- المؤشرات: {item['metrics']}
- الوصف: {item['description']}
- الفحص التقني والأمني:
{probe_data}

اكتب تقريراً تنفيذياً بالعربية يغطي:
1. التقييم من 10 وما الذي تفعله الأداة وهل هي جاهزة للإنتاج.
2. المجال والفئة المستهدفة.
3. نموذج ربح مباشر أو خفض تكلفة.
4. المهمة اليدوية التي تختصرها والوقت التقديري.
5. سيناريو استخدام يومي ملموس.
6. ثلاث خطوات عملية للبدء.
"""
    return call_gemini_api(prompt, active_models)


def build_and_verify_golden_asset(analyzed_items, active_models, timestamp_str):
    """إنشاء ملف MVP وفحصه نحوياً فقط؛ لا يُشغّل كود النموذج على الجهاز."""
    if not analyzed_items:
        return None, ""
    summary = "\n".join(
        f"[{index}] {item['title']} ({item['domain']}): {item['analysis'][:350]}"
        for index, item in enumerate(analyzed_items, 1)
    )
    prompt = f"""
اعتماداً على الاكتشافات التالية:
{summary}

اختر فرصة قابلة للتطبيق، واكتب ملخصاً تنفيذياً عربياً من ثلاثة أسطر، ثم أنشئ نموذج Python مفيداً يعتمد على المكتبات القياسية فقط.
لا تضع أسراراً أو بيانات اعتماد في الكود، واجعل --self-test يعمل دون اتصال بالشبكة أو تعديل ملفات المستخدم.
أخرج الرد بهذا التنسيق حصراً:
### EXECUTIVE_SUMMARY
الملخص هنا
### PYTHON_MVP
```python
الكود الكامل هنا
```
"""
    response, ok = call_gemini_api(prompt, active_models, temperature=0.25)
    if not ok:
        return None, ""
    summary_match = re.search(r"### EXECUTIVE_SUMMARY\s*(.*?)\s*### PYTHON_MVP", response, re.DOTALL)
    code_match = re.search(r"```python\s*(.*?)\s*```", response, re.DOTALL)
    executive_summary = summary_match.group(1).strip() if summary_match else response[:400]
    if not code_match:
        return None, executive_summary

    code = code_match.group(1).strip()
    try:
        ast.parse(code)
        status = "✅ اجتاز فحص البنية النحوية فقط؛ لم يتم تشغيله. راجعه قبل الاستخدام."
    except SyntaxError as exc:
        status = f"⚠️ فشل فحص البنية النحوية: {exc.msg} (السطر {exc.lineno})؛ لم يتم تشغيله."
    os.makedirs(ASSETS_DIR, exist_ok=True)
    output_path = os.path.join(ASSETS_DIR, f"mvp_{timestamp_str}.py")
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(code + "\n")
    executive_summary += f"\n\n🛠️ <b>حالة الأصل البرمجي:</b> {status}"
    return output_path, executive_summary


# ==================== 7. التقرير الأسبوعي ====================
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
أنت استراتيجي تقني وتجاري. حلل تقارير الأسبوع:
{corpus}

اكتب بالعربية: خريطة التوجهات، أفضل ثلاث فرص ربحية ونموذج الربح، فجوات السوق من Reddit وHN، ومشروعاً واحداً لخطة تنفيذ خ��ال 48 ساعة.
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
    send_telegram_html(f"📅 التقرير الاستراتيجي الأسبوعي ({date_text})\n\n{md_to_tg_html(synthesis[:3400])}")
    print(f"🏁 تم حفظ التقرير: {output_path}")


# ==================== 8. تيليجرام ====================
def md_to_tg_html(text):
    return html.escape(text or "")


def format_telegram_cards(now_str, exec_summary, analyzed_items):
    header = (
        f"📡 تقرير الرادار ({now_str} UTC)\n"
        f"⚙️ {html.escape(MODE_LABELS[RADAR_MODE])}\n"
    )
    if exec_summary:
        header += f"\n🏆 الفرصة الذهبية:\n{md_to_tg_html(exec_summary)}\n"
    messages = []
    current = header + "\n━━━━━━━━━━━━━━\n"
    for index, item in enumerate(analyzed_items, 1):
        analysis = md_to_tg_html(item.get("analysis", ""))
        if len(analysis) > 2200:
            analysis = analysis[:2200] + "\n… (التفاصيل في التقرير المحفوظ)"
        card = (
            f"\n🔹 <b>{index}. {html.escape(item['title'])}</b>\n"
            f"📂 {html.escape(item['domain'])}\n"
            f"📊 {html.escape(item['metrics'])}\n"
            f"🛡️ {html.escape(item.get('security', 'آمن مبدئياً 🟢'))} | "
            f"🔗 <a href=\"{html.escape(item['url'], quote=True)}\">فتح المصدر</a>\n"
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
        time.sleep(1)
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
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{TELEGRAM_CHAT_ID}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption[:1000]}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\nContent-Type: text/x-python\r\n\r\n".encode(),
        file_bytes,
        f"\r\n--{boundary}--\r\n".encode(),
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


# ==================== 9. نقطة التشغيل ====================
def main():
    print(f"🚀 بدء التشغيل | {MODE_LABELS[RADAR_MODE]}")
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
                caption="نموذج MVP مولّد آلياً؛ اجتاز فحصاً نحوياً فقط ولم يتم تشغيله. راجعه قبل الاستخدام.",
            )
    print(f"🏁 اكتملت الدورة. التقرير محفوظ في: {report_path}")


if __name__ == "__main__":
    main()
