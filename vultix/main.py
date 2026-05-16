import os, json, time, datetime, requests, threading, random

from google import genai

STATE_PATH          = 'Vultix_Master_State.json'
SCRIPTS_DIR         = 'video_queue/scripts'
PRODUCTION_INTERVAL = 7200
HEARTBEAT_INTERVAL  = 3600
OPENROUTER_FREE_MODELS = [
    'google/gemini-2.5-flash:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'deepseek/deepseek-r1:free',
    'microsoft/phi-4-reasoning:free',
]
OPENROUTER_URL      = 'https://openrouter.ai/api/v1/chat/completions'

os.makedirs(SCRIPTS_DIR, exist_ok=True)

class VultixSovereign:
    def __init__(self):
        self.token           = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        self.chat_id         = os.environ.get('OMAR_CHAT_ID', '').strip()
        self.openrouter_key  = os.environ.get('OPENROUTER_API_KEY', '').strip()
        self.state           = self.load_state()
        self.last_update_id  = 0
        self.production_active = True
        self.init_brain()

    # ─── State ────────────────────────────────────────────────────────────────

    def load_state(self):
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'status': 'DEPLOYED', 'cycle': 0, 'scripts_generated': 0, 'errors': []}

    def sync_state(self):
        self.state['last_sync'] = datetime.datetime.now().isoformat()
        with open(STATE_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=4, ensure_ascii=False)
        print(f"[State] Saved — Cycle #{self.state.get('cycle', 0)}")

    def log_error(self, source, error):
        entry = {'time': datetime.datetime.now().isoformat(), 'source': source, 'error': str(error)}
        self.state.setdefault('errors', []).append(entry)
        if len(self.state['errors']) > 50:
            self.state['errors'] = self.state['errors'][-50:]
        self.sync_state()
        self.send(
            f"⚠️ *خطأ تم رصده*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 المصدر: `{source}`\n"
            f"❌ الخطأ: `{str(error)[:200]}`\n"
            f"🔄 يتم إعادة المحاولة تلقائياً..."
        )

    # ─── Brain — Multi-Provider ───────────────────────────────────────────────

    def init_brain(self):
        raw_keys = [
            os.environ.get('GEMINI_API_KEY',   '').strip(),
            os.environ.get('GEMINI_API_KEY_2', '').strip(),
            os.environ.get('GEMINI_API_KEY_3', '').strip(),
        ]
        self.gemini_keys = [k for k in raw_keys if k]
        self.key_index   = 0
        self.model       = 'gemini-2.0-flash'

        if self.gemini_keys:
            self.gemini_client = genai.Client(api_key=self.gemini_keys[0])
            print(f"[Brain] Gemini ready — {len(self.gemini_keys)} key(s) | model: {self.model}")
        else:
            self.gemini_client = None
            print("[Brain] No Gemini keys found.")

        if self.openrouter_key:
            print(f"[Brain] OpenRouter Fallback ready — {len(OPENROUTER_FREE_MODELS)} free model(s)")
        else:
            print("[Brain] No OpenRouter key — fallback unavailable.")

    def _rotate_gemini_key(self):
        next_index = (self.key_index + 1) % len(self.gemini_keys)
        if next_index == self.key_index:
            return False
        self.key_index     = next_index
        self.gemini_client = genai.Client(api_key=self.gemini_keys[self.key_index])
        print(f"[Key Rotation] Switched to Gemini key #{self.key_index + 1}")
        self.send(f"🔄 *تبديل مفتاح Gemini*\nتم التبديل إلى المفتاح #{self.key_index + 1} بسبب انتهاء الحصة.")
        return True

    def _generate_via_gemini(self, prompt):
        tried = set()
        while len(tried) < len(self.gemini_keys):
            tried.add(self.key_index)
            try:
                response = self.gemini_client.models.generate_content(
                    model=self.model, contents=prompt
                )
                return response.text, f"gemini-key-{self.key_index + 1}"
            except Exception as e:
                err = str(e)
                is_quota = any(x in err for x in ['RESOURCE_EXHAUSTED', '429', 'quota'])
                if is_quota and self._rotate_gemini_key():
                    continue
                raise
        raise Exception("All Gemini keys exhausted")

    def _generate_via_openrouter(self, prompt):
        if not self.openrouter_key:
            raise Exception("OpenRouter key not configured")
        last_error = None
        for model in OPENROUTER_FREE_MODELS:
            try:
                res = requests.post(
                    OPENROUTER_URL,
                    headers={
                        'Authorization': f'Bearer {self.openrouter_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': model,
                        'messages': [{'role': 'user', 'content': prompt}]
                    },
                    timeout=30
                )
                data = res.json()
                if res.status_code == 402 or 'credits' in str(data).lower():
                    print(f"[OpenRouter] {model} — رصيد غير كافٍ، جاري التبديل...")
                    last_error = f"402 على {model}"
                    continue
                if res.status_code != 200:
                    print(f"[OpenRouter] {model} — خطأ {res.status_code}، جاري التبديل...")
                    last_error = f"HTTP {res.status_code} على {model}"
                    continue
                text = data['choices'][0]['message']['content']
                print(f"[OpenRouter] نجح: {model}")
                return text, f"openrouter/{model}"
            except Exception as e:
                print(f"[OpenRouter] {model} — {e}")
                last_error = str(e)
                continue
        raise Exception(f"فشلت جميع نماذج OpenRouter المجانية. آخر خطأ: {last_error}")

    def generate_script(self, topic=None):
        topics = [
            "أسرار الذكاء الاصطناعي التي تُخفيها الشركات الكبرى",
            "تقنية المستقبل التي ستغيّر العالم خلال 10 سنوات",
            "حقائق صادمة عن كيف تراقبك التكنولوجيا",
            "الخوارزميات الخفية التي تتحكم في حياتك اليومية",
            "ما لا تعرفه عن ChatGPT وما وراءه",
            "الروبوتات والذكاء الاصطناعي — هل ستسرق وظيفتك؟",
            "أسرار الإنترنت المظلم التي لا يريدونك أن تعرفها",
        ]
        chosen = topic or random.choice(topics)
        prompt = (
            f"أنت منشئ محتوى متخصص في قناة ميستري/تك باللغة العربية.\n"
            f"اكتب سيناريو فيديو قصير (60 ثانية) بأسلوب مثير وغامض عن: {chosen}\n"
            f"الصيغة:\n"
            f"- مقدمة صادمة (10 ثواني)\n"
            f"- 3 نقاط رئيسية مثيرة (30 ثانية)\n"
            f"- خاتمة Call-to-Action قوية (20 ثانية)\n"
            f"أضف عنواناً جذاباً باللغتين العربية والإنجليزية."
        )

        provider = None
        text     = None

        # 1) حاول عبر Gemini
        if self.gemini_client:
            try:
                text, provider = self._generate_via_gemini(prompt)
            except Exception as e:
                print(f"[Gemini] All keys failed: {e}")
                self.send(
                    "🚨 *انتهاء حصة Gemini*\n"
                    "جميع مفاتيح Gemini استُنفدت.\n"
                    "⚡ التبديل التلقائي إلى OpenRouter/DeepSeek..."
                )

        # 2) Fallback → OpenRouter
        if text is None:
            try:
                text, provider = self._generate_via_openrouter(prompt)
                self.send(f"✅ *Fallback نجح*\nتم التوليد عبر OpenRouter ({OPENROUTER_MODEL})")
            except Exception as e:
                self.log_error('openrouter_fallback', e)
                self.send(
                    "🚨 *فشل جميع المزودين*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "❌ Gemini: حصة منتهية\n"
                    "❌ OpenRouter: خطأ\n"
                    "⏳ سيُعاد المحاولة في الدورة القادمة.\n"
                    "📌 أضف مفتاحاً جديداً: `GEMINI_API_KEY_3`"
                )
                return None

        return {
            'topic':        chosen,
            'script':       text,
            'provider':     provider,
            'generated_at': datetime.datetime.now().isoformat(),
        }

    # ─── Telegram ─────────────────────────────────────────────────────────────

    def api(self, method, **kwargs):
        try:
            res = requests.post(
                f'https://api.telegram.org/bot{self.token}/{method}',
                json=kwargs, timeout=10
            )
            return res.json()
        except Exception as e:
            print(f"[Telegram Error] {method}: {e}")
            return {}

    def reply_keyboard(self):
        return {
            'keyboard': [
                [{'text': '📡 نبض مباشر'},       {'text': '📊 تقرير الحالة'}],
                [{'text': '🎬 آخر سيناريو'},     {'text': '📋 قائمة السيناريوهات'}],
                [{'text': '⚙️ الإعدادات'},        {'text': '❓ مساعدة'}],
            ],
            'resize_keyboard': True,
            'persistent':      True,
        }

    def send(self, text, chat_id=None, with_keyboard=True):
        payload = {
            'chat_id':    chat_id or self.chat_id,
            'text':       text,
            'parse_mode': 'Markdown',
        }
        if with_keyboard:
            payload['reply_markup'] = self.reply_keyboard()
        return self.api('sendMessage', **payload)

    # ─── Reports ──────────────────────────────────────────────────────────────

    def build_status_report(self):
        s   = self.load_state()
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        prod = "🟢 نشط" if self.production_active else "⏸️ موقوف"
        gemini_status = f"{len(self.gemini_keys)} مفتاح (نشط: #{self.key_index+1})" if self.gemini_keys else "غير متاح"
        or_status     = "✅ جاهز" if self.openrouter_key else "❌ غير مُعدّ"
        return (
            f"📊 *VULTIX — تقرير الحالة*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔄 الدورة: #{s.get('cycle', 0)}\n"
            f"📝 السيناريوهات: {s.get('scripts_generated', 0)}\n"
            f"⏱ آخر مزامنة: {s.get('last_sync', 'N/A')}\n"
            f"🔐 الحالة: {s.get('status', 'N/A')}\n"
            f"🎬 الإنتاج: {prod}\n"
            f"🧠 Gemini: {gemini_status}\n"
            f"⚡ OpenRouter Fallback: {or_status}\n"
            f"⚠️ الأخطاء: {len(s.get('errors', []))}\n"
            f"🕐 الوقت: {now}"
        )

    def latest_script_report(self):
        files = sorted([f for f in os.listdir(SCRIPTS_DIR) if f.endswith('.json')]) if os.path.exists(SCRIPTS_DIR) else []
        if not files:
            return "📭 لا توجد سيناريوهات مولّدة بعد."
        with open(os.path.join(SCRIPTS_DIR, files[-1]), 'r', encoding='utf-8') as f:
            d = json.load(f)
        preview = d.get('script', '')[:700]
        return (
            f"🎬 *آخر سيناريو*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 الموضوع: {d.get('topic','N/A')}\n"
            f"⚡ المزود: `{d.get('provider','N/A')}`\n"
            f"🕐 التوليد: {d.get('generated_at','N/A')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{preview}..."
        )

    def scripts_list_report(self):
        files = sorted([f for f in os.listdir(SCRIPTS_DIR) if f.endswith('.json')]) if os.path.exists(SCRIPTS_DIR) else []
        if not files:
            return "📭 لا توجد سيناريوهات بعد."
        lines = [f"📋 *السيناريوهات ({len(files)})*\n━━━━━━━━━━━━━━━━━━━━"]
        for i, name in enumerate(files[-10:], 1):
            lines.append(f"{i}. `{name}`")
        return "\n".join(lines)

    # ─── Message Handler ──────────────────────────────────────────────────────

    def handle_message(self, message):
        text    = message.get('text', '').strip()
        chat_id = message['chat']['id']

        if any(t in text for t in ['📡 نبض مباشر', '📊 تقرير الحالة', '/status', '/start', '/pulse']):
            self.send(self.build_status_report(), chat_id=chat_id)

        elif any(t in text for t in ['🎬 آخر سيناريو', '/latest']):
            self.send(self.latest_script_report(), chat_id=chat_id)

        elif any(t in text for t in ['📋 قائمة السيناريوهات', '/list']):
            self.send(self.scripts_list_report(), chat_id=chat_id)

        elif any(t in text for t in ['⚙️ الإعدادات', '/settings']):
            gemini_keys = len(self.gemini_keys)
            or_ready    = "✅" if self.openrouter_key else "❌"
            self.send(
                f"⚙️ *الإعدادات الحالية*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🧠 الموديل: `{self.model}`\n"
                f"🔑 مفاتيح Gemini: {gemini_keys}\n"
                f"⚡ OpenRouter Fallback: {or_ready}\n"
                f"🔄 الإنتاج كل: {PRODUCTION_INTERVAL//60} دقيقة\n"
                f"💾 Heartbeat كل: {HEARTBEAT_INTERVAL//60} دقيقة",
                chat_id=chat_id
            )

        elif any(t in text for t in ['❓ مساعدة', '/help']):
            self.send(
                "❓ *الأوامر المتاحة*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📡 نبض مباشر — تقرير فوري\n"
                "🎬 آخر سيناريو — آخر سيناريو مولّد\n"
                "📋 قائمة السيناريوهات — كل الملفات\n"
                "⚙️ الإعدادات — حالة المزودين والمفاتيح\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "✍️ `اكتب عن [موضوع]` — سيناريو فوري\n"
                "⏸️ `أوقف الإنتاج` — إيقاف مؤقت\n"
                "▶️ `ابدأ الإنتاج` — استئناف",
                chat_id=chat_id
            )

        elif text.startswith('اكتب عن ') or text.startswith('/write '):
            topic = text.replace('اكتب عن ', '').replace('/write ', '').strip()
            self.send(f"✍️ جاري كتابة سيناريو عن: *{topic}*...", chat_id=chat_id, with_keyboard=False)
            threading.Thread(target=self._manual_generate, args=(topic, chat_id), daemon=True).start()

        elif 'أوقف الإنتاج' in text:
            self.production_active = False
            self.state['production_status'] = 'PAUSED'
            self.sync_state()
            self.send("⏸️ تم إيقاف الإنتاج التلقائي.", chat_id=chat_id)

        elif 'ابدأ الإنتاج' in text:
            self.production_active = True
            self.state['production_status'] = 'ACTIVE'
            self.sync_state()
            self.send("▶️ تم تفعيل الإنتاج التلقائي!", chat_id=chat_id)

        else:
            self.send("👋 اختر من الأزرار أو أرسل:\n`اكتب عن [موضوع]`", chat_id=chat_id)

    def _manual_generate(self, topic, chat_id):
        try:
            data = self.generate_script(topic=topic)
            if data:
                fname = f"manual_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(os.path.join(SCRIPTS_DIR, fname), 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                self.state['scripts_generated'] = self.state.get('scripts_generated', 0) + 1
                self.sync_state()
                preview = data['script'][:800]
                self.send(
                    f"✅ *تم توليد السيناريو*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 الموضوع: {topic}\n"
                    f"⚡ المزود: `{data.get('provider','N/A')}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"{preview}...",
                    chat_id=chat_id
                )
        except Exception as e:
            self.log_error('manual_generate', e)

    # ─── Loops ────────────────────────────────────────────────────────────────

    def polling_loop(self):
        print("[Bot] Telegram polling — 24/7 monitor active.")
        while True:
            try:
                res = requests.get(
                    f'https://api.telegram.org/bot{self.token}/getUpdates',
                    params={'offset': self.last_update_id + 1, 'timeout': 30},
                    timeout=35
                ).json()
                if res.get('ok'):
                    for update in res.get('result', []):
                        self.last_update_id = update['update_id']
                        if 'message' in update:
                            self.handle_message(update['message'])
            except Exception as e:
                print(f"[Polling Error] {e}")
                time.sleep(5)

    def production_loop(self):
        print("[Production] Autonomous loop started.")
        time.sleep(30)
        while True:
            if self.production_active:
                try:
                    print("[Production] Generating script...")
                    data = self.generate_script()
                    if data:
                        fname = f"auto_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        with open(os.path.join(SCRIPTS_DIR, fname), 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=4, ensure_ascii=False)
                        self.state['scripts_generated'] = self.state.get('scripts_generated', 0) + 1
                        self.state['last_script'] = data['topic']
                        self.state['last_provider'] = data.get('provider', 'N/A')
                        self.sync_state()
                        self.send(
                            f"🎬 *سيناريو جديد تلقائياً*\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"📌 {data['topic']}\n"
                            f"⚡ المزود: `{data.get('provider','N/A')}`\n"
                            f"🕐 {data['generated_at']}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"اضغط *🎬 آخر سيناريو* لعرضه"
                        )
                except Exception as e:
                    self.log_error('production_loop', e)
            else:
                print("[Production] Paused.")
            time.sleep(PRODUCTION_INTERVAL)

    def monitor_loop(self):
        print("[Monitor] Heartbeat loop started.")
        while True:
            try:
                self.state = self.load_state()
                self.state['status'] = 'SOVEREIGN_ACTIVE'
                self.state['cycle']  = self.state.get('cycle', 0) + 1
                self.sync_state()
            except Exception as e:
                print(f"[Monitor Error] {e}")
                self.send(f"⚠️ *خطأ في المراقب*\n`{e}`")
            time.sleep(HEARTBEAT_INTERVAL)

    def run(self):
        gemini_count = len(self.gemini_keys)
        or_status    = "✅ جاهز" if self.openrouter_key else "❌ غير مُعدّ"
        self.send(
            f"🚀 *VULTIX — تم الإقلاع*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 Gemini: {gemini_count} مفتاح نشط\n"
            f"⚡ OpenRouter Fallback: {or_status}\n"
            f"🎬 الإنتاج: تلقائي كل {PRODUCTION_INTERVAL//60} دقيقة\n"
            f"🔍 المراقبة: مستمرة 24/7\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"اختر من الأزرار أو أرسل: `اكتب عن [موضوع]`"
        )
        threading.Thread(target=self.polling_loop,    daemon=True).start()
        threading.Thread(target=self.production_loop, daemon=True).start()
        self.monitor_loop()

if __name__ == '__main__':
    vultix = VultixSovereign()
    vultix.run()
