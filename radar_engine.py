import os
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# ================= الإعدادات والمفاتيح المجانية =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # يضاف تلقائياً داخل GitHub Actions

MEMORY_FILE = "memory.json"
REPORT_DIR = "reports"

# الكلمات المفتاحية للمجالات الثلاثة
DOMAINS = {
    "AI & Automation": "(ai-agent OR automation OR workflow OR llm OR mcp-server)",
    "Micro-SaaS": "(micro-saas OR saas-boilerplate OR niche-tool OR api-wrapper OR indie-hacker)",
    "Data & Commerce": "(ecommerce OR price-tracker OR web-scraper OR market-analysis OR trading-bot)"
}

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_memory(seen_ids):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_ids)[-2000:], f, ensure_ascii=False, indent=2)

def http_get_json(url, extra_headers=None):
    headers = {"User-Agent": "AutonomousTechRadar/1.0"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

# ================= 1. طبقة الالتقاط (رادار الصفر + العادي) =================
def fetch_github_discoveries(seen_ids):
    discoveries = []
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    last_week = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    gh_headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        gh_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    for domain_name, query_terms in DOMAINS.items():
        # أ) مسار رادار الصفر: مشاريع أنشئت آخر 24 ساعة حتى لو كانت بـ 0 نجوم
        zero_query = urllib.parse.quote(f"{query_terms} created:>={yesterday} stars:>=0")
        zero_url = f"https://api.github.com/search/repositories?q={zero_query}&sort=updated&order=desc&per_page=5"
        
        # ب) المسار العادي: مشاريع آخر أسبوع بدأت تثبت نجاحها
        std_query = urllib.parse.quote(f"{query_terms} created:>={last_week} stars:>=25")
        std_url = f"https://api.github.com/search/repositories?q={std_query}&sort=stars&order=desc&per_page=3"

        for mode_label, url in [("رادار الصفر (جديد كلياً - 0+ نجوم)", zero_url), ("تشخيص عادي (صاعد ومثبت)", std_url)]:
            try:
                data = http_get_json(url, gh_headers)
                for repo in data.get("items", []):
                    uid = f"gh_{repo['id']}"
                    desc = repo.get("description") or ""
                    # فلتر جودة مبدئي: استبعاد المشاريع الفارغة بدون وصف حقيقي
                    if uid not in seen_ids and len(desc) >= 35 and not repo.get("fork"):
                        discoveries.append({
                            "uid": uid,
                            "mode": mode_label,
                            "domain": domain_name,
                            "title": repo["full_name"],
                            "url": repo["html_url"],
                            "description": desc,
                            "metrics": f"Stars: {repo['stargazers_count']} | Lang: {repo.get('language', 'N/A')}",
                            "default_branch": repo.get("default_branch", "main")
                        })
                        seen_ids.add(uid)
                        break  # أخذ أفضل مرشح لكل مسار ومجال لتوفير الحصة المجانية
                time.sleep(1.5)
            except Exception as e:
                print(f"GitHub Fetch Warning ({domain_name}): {e}")
    return discoveries

def fetch_hn_fresh(seen_ids):
    """التقاط أحدث المنشورات من Hacker News فور نشرها (0 نقاط مطلوبة)"""
    discoveries = []
    try:
        new_ids = http_get_json("https://hacker-news.firebaseio.com/v0/newstories.json")[:25]
        keywords = ["ai", "agent", "saas", "automate", "scrape", "ecommerce", "data", "tool", "open source"]
        for sid in new_ids:
            uid = f"hn_{sid}"
            if uid in seen_ids:
                continue
            item = http_get_json(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
            if item and item.get("url") and item.get("title"):
                title_lower = item["title"].lower()
                if any(k in title_lower for k in keywords):
                    discoveries.append({
                        "uid": uid,
                        "mode": "رادار الصفر (لحظة النشر على HN)",
                        "domain": "Tech / Startup / Web",
                        "title": item["title"],
                        "url": item["url"],
                        "description": f"منشور حديث جداً على Hacker News بعنوان: {item['title']}",
                        "metrics": f"Score: {item.get('score', 0)}",
                        "default_branch": None
                    })
                    seen_ids.add(uid)
                    if len(discoveries) >= 2:
                        break
    except Exception as e:
        print(f"HN Fetch Warning: {e}")
    return discoveries

# ================= 2. طبقة الفحص والتجربة التقنية =================
def technical_probe(item):
    """فحص استجابة الرابط وقراءة ملف README الفعلي للتحقق من الجاهزية"""
    probe_notes = []
    try:
        req = urllib.request.Request(item["url"], method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            probe_notes.append(f"حالة الرابط: نشط ({resp.status})")
    except Exception as e:
        probe_notes.append(f"حالة الرابط: تعذر الوصول المباشر ({e})")

    # إذا كان مستودع GitHub، نجلب أول 1200 حرف من README لفحص طريقة التثبيت والتشغيل
    if item["uid"].startswith("gh_") and item.get("default_branch"):
        raw_readme = f"https://raw.githubusercontent.com/{item['title']}/{item['default_branch']}/README.md"
        try:
            req = urllib.request.Request(raw_readme, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                readme_text = resp.read().decode("utf-8", errors="ignore")[:1200]
                probe_notes.append(f"مقتطف التوثيق الفعلي (README):\n{readme_text}")
        except Exception:
            probe_notes.append("ملاحظة: لا يوجد ملف README قياسي.")
    return "\n".join(probe_notes)

# ================= 3. محرك التحليل والاستغلال (Gemini Free API) =================
def analyze_with_gemini(item, tech_probe_data):
    if not GEMINI_API_KEY:
        return "⚠️ لم يتم ضبط GEMINI_API_KEY."

    prompt = f"""
أنت مهندس استغلال تقني ومحلل أعمال صارم. حلل الاكتشاف التالي بموضوعية تامة دون أي ترويج أو مجاملة:
- المسار: {item['mode']}
- المجال: {item['domain']}
- الاسم/العنوان: {item['title']}
- الرابط: {item['url']}
- المؤشرات الأولية: {item['metrics']}
- الوصف: {item['description']}
- نتيجة الفحص التقني المباشر:
{tech_probe_data}

المطلوب صياغة تقرير عملي مركز جداً باللغة العربية يتضمن النقاط الخمس التالية بدقة:
1. **حقيقة الأداة ومجالها:** ماذا تفعل فعلياً في سطرين، وهل هي جاهزة للاستخدام أم مجرد نموذج أولي؟
2. **الاستغلال الربحي المباشر:** كيف يمكن تحويلها لمصدر دخل (خدمة مصغرة Micro-SaaS، خدمة لعملاء، أو خفض تكلفة تشغيل)؟
3. **اختصار مدة العمل:** ما المهمة اليدوية التي تلغيها وكم توفر من الوقت؟
4. **الاستخدام العملي والحياتي:** سيناريو تطبيق يومي ملموس.
5. **خطوات التشغيل السريع:** (1، 2، 3) للبدء فوراً بناءً على التوثيق المفحوص.
"""
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return res_data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"خطأ أثناء التحليل: {e}"

# ================= 4. التجميع والإرسال الفوري =================
def send_to_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    # تقسيم الرسالة إذا تجاوزت حد تيليجرام (4000 حرف)
    chunks = [text[i:i+3900] for i in range(0, len(text), 3900)]
    for chunk in chunks:
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=15)
            time.sleep(1)
        except Exception as e:
            print(f"Telegram Send Error: {e}")

def main():
    seen_ids = load_memory()
    items = fetch_github_discoveries(seen_ids) + fetch_hn_fresh(seen_ids)
    
    if not items:
        print("لا توجد اكتشافات جديدة مطابقة لمعايير الجودة في هذه الدورة.")
        return

    now_str = datetime.utcnow().strftime("%Y-%m-%d_%H-%M")
    report_lines = [f"# تقرير الرصد والاستغلال الآلي ({now_str} UTC)\n"]

    for item in items:
        print(f"جاري فحص وتحليل: {item['title']} [{item['mode']}]")
        probe = technical_probe(item)
        analysis = analyze_with_gemini(item, probe)
        
        section = (
            f"### {item['title']}\n"
            f"- **المسار:** {item['mode']} | **المجال:** {item['domain']}\n"
            f"- **الرابط:** {item['url']}\n\n"
            f"{analysis}\n\n---\n"
        )
        report_lines.append(section)
        time.sleep(2)  # احترام حدود الطبقة المجانية لـ Gemini

    full_report = "\n".join(report_lines)
    
    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = os.path.join(REPORT_DIR, f"report_{now_str}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    save_memory(seen_ids)
    send_to_telegram(full_report)
    print(f"تمت الدورة بنجاح وحفظ التقرير في {report_path}")

if __name__ == "__main__":
    main()
