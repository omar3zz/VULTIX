import os, json, time, datetime, requests, threading

from google import genai

STATE_PATH = 'Vultix_Master_State.json'
VIDEO_QUEUE_PATH = 'video_queue/pilot_video.json'
HEARTBEAT_INTERVAL = 3600

class VultixSovereign:
    def __init__(self):
        self.token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        self.chat_id = os.environ.get('OMAR_CHAT_ID', '').strip()
        self.gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
        self.state = self.load_state()
        self.last_update_id = 0
        self.init_brain()

    def load_state(self):
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'status': 'DEPLOYED', 'cycle': 0}

    def sync_state(self):
        self.state['last_sync'] = datetime.datetime.now().isoformat()
        with open(STATE_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=4, ensure_ascii=False)
        print(f"[State] Saved — Cycle #{self.state.get('cycle', 0)}")

    def init_brain(self):
        if self.gemini_key:
            self.client = genai.Client(api_key=self.gemini_key)
            self.model = 'gemini-1.5-flash'
            print(f"[VULTIX] Brain ready: {self.model}")
        else:
            self.client = None
            print("[WARNING] GEMINI_API_KEY missing.")

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
                [
                    {'text': '📡 نبض مباشر'},
                    {'text': '📊 تقرير الحالة'}
                ],
                [
                    {'text': '🎬 توليد فوري'},
                    {'text': '⚙️ الإعدادات'}
                ],
                [
                    {'text': '🎞️ الفيديو الافتتاحي'},
                    {'text': '❓ مساعدة'}
                ]
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

    def build_status_report(self):
        s = self.load_state()
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return (
            f"📊 *VULTIX — تقرير الحالة*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 الهوية: {s.get('identity', 'VULTIX SUPREME')}\n"
            f"🔄 الدورة: #{s.get('cycle', 0)}\n"
            f"⏱ آخر مزامنة: {s.get('last_sync', 'N/A')}\n"
            f"🔐 الحالة: {s.get('status', 'N/A')}\n"
            f"🤖 الطيار الآلي: {s.get('autopilot_status', 'N/A')}\n"
            f"📋 البروتوكول: {s.get('protocol', 'N/A')}\n"
            f"🕐 وقت الاستعلام: {now}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎬 الإنتاج: *مجمّد* ⏸️\n"
            f"🎞️ الفيديو الافتتاحي: جاهز للانطلاق بأمرك"
        )

    def pilot_video_report(self):
        if os.path.exists(VIDEO_QUEUE_PATH):
            with open(VIDEO_QUEUE_PATH, 'r', encoding='utf-8') as f:
                v = json.load(f)
            return (
                f"🎞️ *الفيديو الافتتاحي — جاهز*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 العنوان: {v.get('title', 'N/A')}\n"
                f"🎯 الهدف: {v.get('target_audience', 'N/A')}\n"
                f"⏱ المدة: {v.get('duration_seconds', 'N/A')} ثانية\n"
                f"📝 المحتوى:\n"
                + "\n".join([f"  {i+1}. {s['text']}" for i, s in enumerate(v.get('scenes', []))])
                + f"\n━━━━━━━━━━━━━━━━━━━━\n"
                f"⏸️ الإنتاج مجمّد — أرسل *ابدأ الإنتاج* للتفعيل"
            )
        return "⚠️ لم يتم العثور على ملف الفيديو الافتتاحي."

    def handle_message(self, message):
        text = message.get('text', '').strip()
        chat_id = message['chat']['id']

        status_triggers = ['📡 نبض مباشر', '📊 تقرير الحالة',
                           'ما الذي يحدث الآن', 'what is happening now',
                           '/status', '/start', '/pulse']
        video_triggers  = ['🎞️ الفيديو الافتتاحي', '/video']
        gen_triggers    = ['🎬 توليد فوري', '/gen']
        settings_triggers = ['⚙️ الإعدادات', '/settings']
        help_triggers   = ['❓ مساعدة', '/help']

        if any(t in text for t in status_triggers):
            self.send(self.build_status_report(), chat_id=chat_id)

        elif any(t in text for t in video_triggers):
            self.send(self.pilot_video_report(), chat_id=chat_id)

        elif any(t in text for t in gen_triggers):
            self.send(
                "🔒 *الإنتاج مجمّد*\n"
                "لن يتم توليد أي محتوى تلقائياً.\n"
                "أرسل *ابدأ الإنتاج* لتفعيل أول فيديو.",
                chat_id=chat_id
            )

        elif any(t in text for t in settings_triggers):
            self.send(
                "⚙️ *الإعدادات الحالية*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🧠 النموذج: gemini-1.5-flash\n"
                f"📡 التليجرام: متصل\n"
                f"💾 حفظ الحالة: تلقائي كل ساعة\n"
                f"🎬 الإنتاج: مجمّد ⏸️",
                chat_id=chat_id
            )

        elif any(t in text for t in help_triggers):
            self.send(
                "❓ *الأوامر المتاحة*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📡 *نبض مباشر* — تقرير الحالة الفوري\n"
                "📊 *تقرير الحالة* — نفس السابق\n"
                "🎞️ *الفيديو الافتتاحي* — مراجعة الفيديو الجاهز\n"
                "🎬 *توليد فوري* — (مجمّد الآن)\n"
                "⚙️ *الإعدادات* — عرض الإعدادات الحالية\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "لبدء الإنتاج أرسل: *ابدأ الإنتاج*",
                chat_id=chat_id
            )

        elif 'ابدأ الإنتاج' in text:
            self.send(
                "⚠️ *تأكيد مطلوب*\n"
                "هل أنت متأكد من بدء إنتاج الفيديو الافتتاحي؟\n"
                "أرسل: *تأكيد الإنتاج* للمتابعة.",
                chat_id=chat_id
            )

        else:
            self.send(
                "👋 اختر من الأزرار أدناه أو اكتب أمرك.",
                chat_id=chat_id
            )

    def polling_loop(self):
        print("[VULTIX] Telegram polling started.")
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

    def heartbeat_loop(self):
        self.send(
            "🚀 *VULTIX — تم التفعيل*\n"
            "النظام في وضع المراقبة.\n"
            "الإنتاج مجمّد حتى أمرك.\n\n"
            "اختر من الأزرار 👇"
        )
        while True:
            try:
                self.state['cycle'] = self.state.get('cycle', 0) + 1
                self.state['status'] = 'SOVEREIGN_ACTIVE'
                self.sync_state()
                time.sleep(HEARTBEAT_INTERVAL)
            except Exception as e:
                print(f"[Heartbeat Error] {e}")
                self.sync_state()
                time.sleep(60)

    def run(self):
        threading.Thread(target=self.polling_loop, daemon=True).start()
        self.heartbeat_loop()

if __name__ == '__main__':
    vultix = VultixSovereign()
    vultix.run()
