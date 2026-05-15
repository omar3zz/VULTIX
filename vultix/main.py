import os, json, time, datetime, requests, threading, random

from google import genai

STATE_PATH = 'Vultix_Master_State.json'
SCRIPTS_DIR = 'video_queue/scripts'
PRODUCTION_INTERVAL = 7200
HEARTBEAT_INTERVAL  = 3600
MONITOR_INTERVAL    = 300

os.makedirs(SCRIPTS_DIR, exist_ok=True)

class VultixSovereign:
    def __init__(self):
        self.token      = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        self.chat_id    = os.environ.get('OMAR_CHAT_ID', '').strip()
        self.gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
        self.state      = self.load_state()
        self.last_update_id = 0
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
            f"🕐 الوقت: {entry['time']}\n"
            f"🔄 يتم إعادة المحاولة تلقائياً..."
        )

    # ─── Brain ────────────────────────────────────────────────────────────────

    def init_brain(self):
        if self.gemini_key:
            self.client = genai.Client(api_key=self.gemini_key)
            self.model  = 'gemini-1.5-flash'
            print(f"[VULTIX] Brain ready: {self.model}")
        else:
            self.client = None
            print("[WARNING] GEMINI_API_KEY missing.")

    def generate_script(self, topic=None):
        if not self.client:
            return None
        topics = [
            "أسرار الذكاء الاصطناعي التي تُخفيها الشركات الكبرى",
            "تقنية المستقبل التي ستغيّر العالم خلال 10 سنوات",
            "حقائق صادمة عن كيف تراقبك التكنولوجيا",
            "الخوارزميات الخفية التي تتحكم في حياتك اليومية",
            "ما لا تعرفه عن ChatGPT وما وراءه"
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
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return {'topic': chosen, 'script': response.text, 'generated_at': datetime.datetime.now().isoformat()}

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
                [{'text': '📡 نبض مباشر'}, {'text': '📊 تقرير الحالة'}],
                [{'text': '🎬 آخر سيناريو'}, {'text': '📋 قائمة السيناريوهات'}],
                [{'text': '⚙️ الإعدادات'}, {'text': '❓ مساعدة'}]
            ],
            'resize_keyboard': True,
            'persistent': True
        }

    def send(self, text, chat_id=None, with_keyboard=True):
        payload = {
            'chat_id': chat_id or self.chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        if with_keyboard:
            payload['reply_markup'] = self.reply_keyboard()
        return self.api('sendMessage', **payload)

    # ─── Status & Reports ─────────────────────────────────────────────────────

    def build_status_report(self):
        s = self.load_state()
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        prod_status = "🟢 نشط — يعمل تلقائياً" if self.production_active else "⏸️ موقوف"
        return (
            f"📊 *VULTIX — تقرير الحالة*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔄 الدورة: #{s.get('cycle', 0)}\n"
            f"📝 السيناريوهات المولّدة: {s.get('scripts_generated', 0)}\n"
            f"⏱ آخر مزامنة: {s.get('last_sync', 'N/A')}\n"
            f"🔐 الحالة: {s.get('status', 'N/A')}\n"
            f"🎬 الإنتاج: {prod_status}\n"
            f"⚠️ الأخطاء المسجّلة: {len(s.get('errors', []))}\n"
            f"🕐 وقت الاستعلام: {now}"
        )

    def latest_script_report(self):
        scripts = sorted([
            f for f in os.listdir(SCRIPTS_DIR) if f.endswith('.json')
        ]) if os.path.exists(SCRIPTS_DIR) else []
        if not scripts:
            return "📭 لا توجد سيناريوهات مولّدة حتى الآن."
        with open(os.path.join(SCRIPTS_DIR, scripts[-1]), 'r', encoding='utf-8') as f:
            data = json.load(f)
        script_preview = data.get('script', '')[:600]
        return (
            f"🎬 *آخر سيناريو مولّد*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 الموضوع: {data.get('topic', 'N/A')}\n"
            f"🕐 وقت التوليد: {data.get('generated_at', 'N/A')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{script_preview}..."
        )

    def scripts_list_report(self):
        scripts = sorted([
            f for f in os.listdir(SCRIPTS_DIR) if f.endswith('.json')
        ]) if os.path.exists(SCRIPTS_DIR) else []
        if not scripts:
            return "📭 لا توجد سيناريوهات بعد."
        lines = [f"📋 *السيناريوهات المولّدة ({len(scripts)})*\n━━━━━━━━━━━━━━━━━━━━"]
        for i, s in enumerate(scripts[-10:], 1):
            lines.append(f"{i}. `{s}`")
        return "\n".join(lines)

    # ─── Message Handler ──────────────────────────────────────────────────────

    def handle_message(self, message):
        text     = message.get('text', '').strip()
        chat_id  = message['chat']['id']
        text_low = text.lower()

        if any(t in text for t in ['📡 نبض مباشر', '📊 تقرير الحالة', 'ما الذي يحدث', '/status', '/start', '/pulse']):
            self.send(self.build_status_report(), chat_id=chat_id)

        elif any(t in text for t in ['🎬 آخر سيناريو', '/latest']):
            self.send(self.latest_script_report(), chat_id=chat_id)

        elif any(t in text for t in ['📋 قائمة السيناريوهات', '/list']):
            self.send(self.scripts_list_report(), chat_id=chat_id)

        elif any(t in text for t in ['⚙️ الإعدادات', '/settings']):
            self.send(
                f"⚙️ *الإعدادات الحالية*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🧠 النموذج: `gemini-1.5-flash`\n"
                f"🔄 الإنتاج كل: {PRODUCTION_INTERVAL//60} دقيقة\n"
                f"💾 Heartbeat كل: {HEARTBEAT_INTERVAL//60} دقيقة\n"
                f"🔍 المراقبة كل: {MONITOR_INTERVAL//60} دقيقة",
                chat_id=chat_id
            )

        elif any(t in text for t in ['❓ مساعدة', '/help']):
            self.send(
                "❓ *الأوامر المتاحة*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📡 *نبض مباشر* — تقرير الحالة الفوري\n"
                "🎬 *آخر سيناريو* — عرض آخر سيناريو مولّد\n"
                "📋 *قائمة السيناريوهات* — كل السيناريوهات\n"
                "⚙️ *الإعدادات* — إعدادات النظام\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "*أوامر يدوية مباشرة:*\n"
                "🎯 `اكتب عن [موضوع]` — توليد سيناريو بموضوع محدد\n"
                "⏸️ `أوقف الإنتاج` — إيقاف الإنتاج التلقائي\n"
                "▶️ `ابدأ الإنتاج` — تشغيل الإنتاج التلقائي",
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
            self.send("⏸️ تم إيقاف الإنتاج التلقائي.\nأرسل *ابدأ الإنتاج* للاستئناف.", chat_id=chat_id)

        elif 'ابدأ الإنتاج' in text:
            self.production_active = True
            self.state['production_status'] = 'ACTIVE'
            self.sync_state()
            self.send("▶️ تم تفعيل الإنتاج التلقائي!\nسيبدأ توليد السيناريوهات الآن.", chat_id=chat_id)

        else:
            self.send("👋 اختر من الأزرار أدناه أو أرسل:\n`اكتب عن [موضوع]` لسيناريو مخصص.", chat_id=chat_id)

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
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"{preview}...",
                    chat_id=chat_id
                )
        except Exception as e:
            self.log_error('manual_generate', e)

    # ─── Loops ────────────────────────────────────────────────────────────────

    def polling_loop(self):
        print("[Bot] Telegram polling started — monitor mode active.")
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
        print("[Production] Autonomous script generation started.")
        time.sleep(30)
        while True:
            if self.production_active:
                try:
                    print("[Production] Generating new script...")
                    data = self.generate_script()
                    if data:
                        fname = f"auto_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        with open(os.path.join(SCRIPTS_DIR, fname), 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=4, ensure_ascii=False)
                        self.state['scripts_generated'] = self.state.get('scripts_generated', 0) + 1
                        self.state['last_script'] = data['topic']
                        self.sync_state()
                        self.send(
                            f"🎬 *سيناريو جديد تم توليده تلقائياً*\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"📌 الموضوع: {data['topic']}\n"
                            f"🕐 الوقت: {data['generated_at']}\n"
                            f"📁 محفوظ في: `{SCRIPTS_DIR}/{fname}`\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"اضغط *🎬 آخر سيناريو* لعرضه كاملاً"
                        )
                except Exception as e:
                    self.log_error('production_loop', e)
            else:
                print("[Production] Paused — waiting for activation.")
            time.sleep(PRODUCTION_INTERVAL)

    def monitor_loop(self):
        print("[Monitor] State monitor started.")
        while True:
            try:
                self.state = self.load_state()
                self.state['status'] = 'SOVEREIGN_ACTIVE'
                self.state['cycle'] = self.state.get('cycle', 0) + 1
                self.sync_state()
            except Exception as e:
                print(f"[Monitor Error] {e}")
                self.send(f"⚠️ *خطأ في المراقب*\n`{e}`")
            time.sleep(HEARTBEAT_INTERVAL)

    def run(self):
        self.send(
            "🚀 *VULTIX — تم الإقلاع*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 السيستم: يعمل تلقائياً بحرية كاملة\n"
            "🎬 الإنتاج: نشط — يولّد سيناريوهات\n"
            "🔍 البوت: مراقبة مستمرة 24/7\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "اختر من الأزرار أو أرسل: `اكتب عن [موضوع]`"
        )
        threading.Thread(target=self.polling_loop,    daemon=True).start()
        threading.Thread(target=self.production_loop, daemon=True).start()
        self.monitor_loop()

if __name__ == '__main__':
    vultix = VultixSovereign()
    vultix.run()
