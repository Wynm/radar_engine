import os
import re
import json
import time
import html
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta

# ==================== 1. الإعدادات والمفاتيح ====================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

MEMORY_FILE = "memory.json"
REPORT_DIR = "reports"

# المجالات الثلاثة المستهدفة
DOMAINS = {
    "الذكاء الاصطناعي والأتمتة": "(ai-agent OR automation OR workflow OR llm OR mcp-server OR browser-use)",
    "فرص البرمجيات كخدمة Micro-SaaS": "(micro-saas OR saas-boilerplate OR niche-tool OR api-wrapper OR indie-hacker)",
    "تحليل البيانات والتجارة": "(ecommerce OR price-tracker OR web-scraper OR market-analysis OR trading-bot)"
}

# كلمات مستبعدة لتنقية الرادار من الضجيج
NOISE_KEYWORDS = {
    "roblox", "cheat", "aimbot", "crack", "keygen", "free-nitro",
    "hack-tool", "homework", "assignment", "leetcode", "dotfiles", "my-config"
}


# ==================== 2. إدارة الذاكرة والاتصال ====================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_memory(seen_ids):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_ids)[-3000:], f, ensure_ascii=False, indent=2)


def http_request(url, method="GET", headers=None, data=None, timeout=20, as_json=True):
    req_headers = {"User-Agent": "AutonomousTechRadar/3.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw) if as_json else raw


def is_noise(text):
    lowered = text.lower()
    return any(bad in lowered for bad in NOISE_KEYWORDS)


# ==================== 3. الاكتشاف الذاتي لأحدث نماذج Gemini ====================
def discover_active_gemini_models():
    """جلب أحدث نماذج Gemini الفعالة تلقائياً من حسابك لمنع أخطاء 404 مستقبلاً"""
    fallback_models = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3.5-flash"]
    if not GEMINI_API_KEY:
        return fallback_models

    excluded_tags = ("embedding", "imagen", "veo", "tts", "audio", "aqa", "robotics", "computer-use")
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        data = http_request(url, timeout=15, as_json=True)
        flash_models = []
        other_models = []

        for m in data.get("models", []):
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" not in methods:
                continue
            name = m.get("name", "").replace("models/", "")
            if not name.startswith("gemini-") or any(tag in name for tag in excluded_tags):
                continue
            if "flash" in name:
                flash_models.append(name)
            else:
                other_models.append(name)

        # ترتيب تنازلي لاختيار أحدث إصدار أولاً (مثل gemini-3.8-flash)
        flash_models.sort(reverse=True)
        other_models.sort(reverse=True)
        discovered = flash_models + other_models

        if discovered:
            print(f"🧠 النماذج المكتشفة تلقائياً: {', '.join(discovered[:4])}")
            return discovered[:5]
    except Exception as e:
        print(f"⚠️ تعذر جلب قائمة النماذج تلقائياً، سيتم استخدام القائمة الافتراضية: {e}")

    return fallback_models


# ==================== 4. طبقة الرصد المزدوج (رادار الصفر + العادي) ====================
def verify_github_repo_structure(repo_full_name, gh_headers):
    """التحقق من وجود ملفات برمجية حقيقية داخل المستودع"""
    try:
        contents_url = f"https://api.github.com/repos/{repo_full_name}/contents"
        items = http_request(contents_url, headers=gh_headers, timeout=12, as_json=True)
        if not isinstance(items, list) or len(items) == 0:
            return False, []
        filenames = [item.get("name", "") for item in items]
        code_indicators = (
            ".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".sh",
            "package.json", "requirements.txt", "pyproject.toml", "Dockerfile",
            "Cargo.toml", "go.mod", "src", "app", "lib", "index.html"
        )
        has_real_code = any(
            name.endswith(code_indicators) or name in code_indicators
            for name in filenames
        )
        return has_real_code, filenames[:15]
    except Exception:
        return False, []


def fetch_github_discoveries(seen_ids):
    discoveries = []
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    last_week = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

    gh_headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        gh_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    for domain_name, query_terms in DOMAINS.items():
        zero_q = urllib.parse.quote(f"{query_terms} created:>={yesterday} stars:>=0 size:>=5")
        zero_url = f"https://api.github.com/search/repositories?q={zero_q}&sort=updated&order=desc&per_page=8"

        std_q = urllib.parse.quote(f"{query_terms} created:>={last_week} stars:>=20 size:>=10")
        std_url = f"https://api.github.com/search/repositories?q={std_q}&sort=stars&order=desc&per_page=5"

        modes = [
            ("رادار الصفر (جديد كلياً - 0+ نجوم)", zero_url),
            ("تشخيص عادي (صاعد ومثبت)", std_url)
        ]

        for mode_label, url in modes:
            try:
                data = http_request(url, headers=gh_headers, as_json=True)
                for repo in data.get("items", []):
                    uid = f"gh_{repo['id']}"
                    if uid in seen_ids:
                        continue

                    full_name = repo["full_name"]
                    desc = (repo.get("description") or "").strip()

                    if repo.get("fork") or repo.get("archived") or len(desc) < 30 or is_noise(f"{full_name} {desc}"):
                        seen_ids.add(uid)
                        continue

                    has_code, file_list = verify_github_repo_structure(full_name, gh_headers)
                    if not has_code:
                        seen_ids.add(uid)
                        continue

                    discoveries.append({
                        "uid": uid,
                        "source": "github",
                        "mode": mode_label,
                        "domain": domain_name,
                        "title": full_name,
                        "url": repo["html_url"],
                        "description": desc,
                        "metrics": f"النجوم: {repo['stargazers_count']} | اللغة: {repo.get('language') or 'متعددة'} | الحجم: {repo.get('size', 0)}KB",
                        "files": file_list
                    })
                    break
                time.sleep(1.2)
            except Exception as e:
                print(f"⚠️ تنبيه جلب GitHub ({domain_name}): {e}")

    return discoveries


def fetch_hn_discoveries(seen_ids):
    """رصد أحدث الابتكارات والنقاشات من Hacker News"""
    discoveries = []
    keywords = (
        "ai", "agent", "saas", "automate", "automation", "scrape", "scraper",
        "ecommerce", "data", "tool", "open source", "open-source", "llm", "workflow", "api"
    )

    endpoints = [
        ("رادار الصفر (لحظة النشر على HN)", "https://hacker-news.firebaseio.com/v0/newstories.json", 30, 1),
        ("تشخيص عادي (الأكثر تفاعلاً على HN)", "https://hacker-news.firebaseio.com/v0/topstories.json", 25, 1)
    ]

    for mode_label, feed_url, scan_limit, pick_limit in endpoints:
        picked = 0
        try:
            story_ids = http_request(feed_url, as_json=True)[:scan_limit]
            for sid in story_ids:
                uid = f"hn_{sid}"
                if uid in seen_ids:
                    continue

                item = http_request(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", as_json=True)
                if not item or not item.get("url") or not item.get("title"):
                    continue

                title = item["title"].strip()
                if is_noise(title):
                    seen_ids.add(uid)
                    continue

                if any(k in title.lower() for k in keywords):
                    discoveries.append({
                        "uid": uid,
                        "source": "hn",
                        "mode": mode_label,
                        "domain": "تقنيات الويب والأعمال والذكاء الاصطناعي",
                        "title": title,
                        "url": item["url"],
                        "description": f"طرح تقني على Hacker News: {title}",
                        "metrics": f"النقاط: {item.get('score', 0)} | التعليقات: {item.get('descendants', 0)}",
                        "files": []
                    })
                    picked += 1
                    if picked >= pick_limit:
                        break
        except Exception as e:
            print(f"⚠️ تنبيه جلب Hacker News ({mode_label}): {e}")

    return discoveries


# ==================== 5. طبقة الفحص والتجربة التقنية المباشرة ====================
def technical_probe(item):
    """اختبار استجابة الرابط واستخلاص التوثيق الفعلي أو محتوى الصفحة"""
    notes = []
    start_time = time.time()

    try:
        req = urllib.request.Request(item["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            latency_ms = int((time.time() - start_time) * 1000)
            notes.append(f"- حالة الرابط: نشط ويعمل (HTTP {resp.status} | زمن الاستجابة: {latency_ms}ms)")
            if item["source"] == "hn":
                page_html = resp.read().decode("utf-8", errors="ignore")[:15000]
                clean_text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page_html, flags=re.DOTALL | re.IGNORECASE)
                clean_text = re.sub(r"<[^>]+>", " ", clean_text)
                clean_text = re.sub(r"\s+", " ", html.unescape(clean_text)).strip()
                if clean_text:
                    notes.append(f"- مقتطف من محتوى الصفحة الفعلي:\n{clean_text[:1200]}")
    except Exception as e:
        notes.append(f"- حالة الرابط: تعذر الفتح المباشر ({str(e)[:120]})")

    if item["source"] == "github":
        if item.get("files"):
            notes.append(f"- الملفات الرئيسية في المستودع: {', '.join(item['files'])}")

        gh_headers = {"Accept": "application/vnd.github.raw+json"}
        if GITHUB_TOKEN:
            gh_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        try:
            readme_url = f"https://api.github.com/repos/{item['title']}/readme"
            readme_raw = http_request(readme_url, headers=gh_headers, timeout=12, as_json=False)
            if readme_raw:
                notes.append(f"- مقتطف التوثيق الفعلي (README):\n{readme_raw[:1800]}")
        except Exception:
            notes.append("- ملاحظة التوثيق: لا يوجد ملف README قياسي، يعتمد على قراءة الكود مباشرة.")

    return "\n".join(notes)


# ==================== 6. محرك التحليل والاستغلال (Gemini API) ====================
def call_gemini_api(prompt_text, active_models):
    if not GEMINI_API_KEY:
        return "❌ لم يتم ضبط GEMINI_API_KEY في GitHub Secrets.", False

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": 0.4}
    }).encode("utf-8")

    last_error = ""
    for model in active_models:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        for attempt in range(2):
            try:
                res_data = http_request(
                    endpoint,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    data=payload,
                    timeout=35,
                    as_json=True
                )
                text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text, True
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                last_error = f"HTTP {e.code} [{model}]: {err_body[:250]}"
                print(f"❌ فشل {model} (محاولة {attempt + 1}): HTTP {e.code}")
                if e.code == 429:
                    time.sleep(10)
                    continue
                if e.code in (400, 403):
                    print(f"🚨 خطأ في صلاحية المفتاح: {last_error}")
                    return f"⚠️ خطأ في مفتاح Gemini API: {last_error}", False
                break
            except Exception as e:
                last_error = str(e)
                break

    print(f"🚨 تفاصيل فشل التحليل: {last_error}")
    return f"⚠️ تعذر إتمام التحليل حالياً: {last_error}", False


def analyze_discovery(item, probe_data, active_models):
    prompt = f"""
أنت مهندس استغلال تقني ومحلل أعمال صارم. قم بتشخيص الاكتشاف التالي بموضوعية تامة دون أي ترويج أو مبالغة:

- المسار: {item['mode']}
- المجال: {item['domain']}
- العنوان/المستودع: {item['title']}
- الرابط: {item['url']}
- المؤشرات: {item['metrics']}
- الوصف الأولي: {item['description']}
- نتائج الفحص التقني المباشر:
{probe_data}

اكتب تقريراً تنفيذياً مركزاً باللغة العربية وفق البنود الستة التالية بدقة:
1. **التقييم وحقيقة الأداة (من 10):** أعطِ درجة جدوى من 10، واشرح في سطرين ماذا تفعل فعلياً وهل هي جاهزة للإنتاج أم مجرد تجربة أولية.
2. **المجال الدقيق والفئة المستهدفة:** من يحتاج هذا الحل تحديداً؟
3. **الاستغلال الربحي المباشر:** كيف يُحوّل إلى مال (تقديمه كخدمة Micro-SaaS، بيعه كخدمة مستقلة لعملاء، أو خفض تكاليف تشغيلية)؟
4. **اختصار مدة العمل:** ما المهمة اليدوية التي يؤتمتها وكم يختصر من الوقت؟
5. **الاستخدام العملي والحياتي:** سيناريو تطبيق يومي ملموس وسريع.
6. **دليل التشغيل والاستفادة الفورية:** خطوات عملية مرقمة (1، 2، 3) للبدء فوراً بناءً على التوثيق والملفات المفحوصة.
"""
    return call_gemini_api(prompt, active_models)


def generate_executive_summary(analyzed_items, active_models):
    if len(analyzed_items) <= 1:
        return ""
    brief_list = "\n".join([f"- {x['title']} ({x['mode']}): {x['analysis'][:300]}..." for x in analyzed_items])
    prompt = f"""
بناءً على الاكتشافات التالية التي تم تحليلها اليوم:
{brief_list}

اكتب فقرة قصيرة (4 أسطر كحد أقصى) باللغة العربية بعنوان **أفضل فرصة ذهبية في هذه الدورة** تحدد فيها الاكتشاف الأكثر ربحية وقابلية للتطبيق الفوري اليوم ولماذا.
"""
    summary_text, ok = call_gemini_api(prompt, active_models)
    return f"{summary_text}\n\n---\n\n" if ok else ""


# ==================== 7. الإرسال الذكي إلى تيليجرام ====================
def smart_chunk_text(text, max_len=3800):
    if len(text) <= max_len:
        return [text]
    chunks = []
    current = ""
    for block in text.split("\n---\n"):
        candidate = f"{current}\n---\n{block}" if current else block
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            if len(block) <= max_len:
                current = block
            else:
                for i in range(0, len(block), max_len):
                    chunks.append(block[i:i + max_len])
                current = ""
    if current.strip():
        chunks.append(current.strip())
    return chunks


def send_to_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ تنبيه: مفاتيح تيليجرام غير مضبوطة في Secrets.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = smart_chunk_text(text, max_len=3800)

    for idx, chunk in enumerate(chunks, 1):
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True
        }).encode("utf-8")
        try:
            http_request(url, method="POST", headers={"Content-Type": "application/json"}, data=payload, timeout=15)
            print(f"✅ تم إرسال الجزء {idx}/{len(chunks)} إلى تيليجرام بنجاح.")
            time.sleep(1.2)
        except urllib.error.HTTPError as e:
            print(f"❌ خطأ تيليجرام HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')}")
        except Exception as e:
            print(f"❌ خطأ إرسال تيليجرام: {e}")


# ==================== 8. نقطة التشغيل الرئيسية ====================
def main():
    print("🚀 بدء دورة الرصد والتشخيص والاستغلال...")
    active_models = discover_active_gemini_models()
    seen_ids = load_memory()

    discoveries = fetch_github_discoveries(seen_ids) + fetch_hn_discoveries(seen_ids)
    if not discoveries:
        print("ℹ️ لا توجد اكتشافات جديدة مطابقة لمعايير الجودة في هذه الدورة.")
        save_memory(seen_ids)
        return

    now_str = datetime.utcnow().strftime("%Y-%m-%d_%H-%M")
    analyzed_records = []
    report_sections = []

    for item in discoveries:
        print(f"🔍 فحص وتحليل: {item['title']} | [{item['mode']}]")
        probe_data = technical_probe(item)
        analysis, success = analyze_discovery(item, probe_data, active_models)

        if success:
            seen_ids.add(item["uid"])
            analyzed_records.append({"title": item["title"], "mode": item["mode"], "analysis": analysis})

        section = (
            f"### {item['title']}\n"
            f"- **المسار:** {item['mode']}\n"
            f"- **المجال:** {item['domain']}\n"
            f"- **المؤشرات:** {item['metrics']}\n"
            f"- **الرابط:** {item['url']}\n\n"
            f"{analysis}\n"
        )
        report_sections.append(section)
        time.sleep(2.5)

    exec_summary = generate_executive_summary(analyzed_records, active_models)
    header = f"# تقرير الرصد والاستغلال التقني ({now_str} UTC)\n\n{exec_summary}"
    full_report = header + "\n---\n\n".join(report_sections)

    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = os.path.join(REPORT_DIR, f"report_{now_str}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    save_memory(seen_ids)
    send_to_telegram(full_report)
    print(f"🏁 اكتملت الدورة بنجاح. التقرير محفوظ في: {report_path}")


if __name__ == "__main__":
    main()
