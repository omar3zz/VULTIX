import os, json, time, datetime, requests, threading

from google import genai

STATE_PATH = 'Vultix_Master_State.json'
POLL_INTERVAL = 2
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

    def send(self, text, chat_id=None, reply_markup=None):
        payload = {
            'chat_id': chat_id or self.chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        if reply_markup:
            payload['reply_markup'] = reply_markup
        return self.api('sendMessage', **payload)

    def main_keyboard(self):
        return {
            'inline_keyboard': [[
                {'text': '📡 Live Pulse', 'callback_data': 'live_pulse'},
                {'text': '🎬 Instant Gen', 'callback_data': 'instant_gen'}
            ]]
        }

    def build_status_report(self):
        s = self.state
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
            f"🎬 الإنتاج: *مجمّد* — بانتظار أمرك الشخصي"
        )

    def handle_callback(self, callback):
        query_id = callback['id']
        data = callback.get('data', '')
        chat_id = callback['message']['chat']['id']

        self.api('answerCallbackQuery', callback_query_id=query_id)

        if data == 'live_pulse':
            self.state = self.load_state()
            self.send(self.build_status_report(), chat_id=chat_id, reply_markup=self.main_keyboard())

        elif data == 'instant_gen':
            self.send(
                "🔒 *الإنتاج مجمّد*\n"
                "لن يتم توليد أي محتوى تلقائياً.\n"
                "أرسل أمر الإنتاج يدوياً لبدء التشغيل.",
                chat_id=chat_id,
                reply_markup=self.main_keyboard()
            )

    def handle_message(self, message):
        text = message.get('text', '').strip().lower()
        chat_id = message['chat']['id']

        status_triggers = [
            'ما الذي يحدث الآن', 'what is happening now',
            'ما يحدث', 'الحالة', 'status', '/status', '/start', '/pulse'
        ]

        if any(t in text for t in status_triggers):
            self.state = self.load_state()
            self.send(self.build_status_report(), chat_id=chat_id, reply_markup=self.main_keyboard())
        else:
            self.send(
                "👋 مرحباً! اختر من الأزرار أو اسأل: *ما الذي يحدث الآن؟*",
                chat_id=chat_id,
                reply_markup=self.main_keyboard()
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
                        if 'callback_query' in update:
                            self.handle_callback(update['callback_query'])
                        elif 'message' in update:
                            self.handle_message(update['message'])
            except Exception as e:
                print(f"[Polling Error] {e}")
                time.sleep(5)

    def heartbeat_loop(self):
        self.send(
            "🚀 *VULTIX — تم التفعيل*\n"
            "النظام يعمل في وضع المراقبة.\n"
            "الإنتاج مجمّد حتى أمرك الشخصي.\n\n"
            "اضغط على الأزرار للتفاعل 👇",
            reply_markup=self.main_keyboard()
        )
        while True:
            try:
                self.state['cycle'] = self.state.get('cycle', 0) + 1
                self.state['status'] = 'SOVEREIGN_ACTIVE'
                self.sync_state()
                print(f"[{datetime.datetime.now().isoformat()}] Heartbeat #{self.state['cycle']} saved.")
                time.sleep(HEARTBEAT_INTERVAL)
            except Exception as e:
                print(f"[Heartbeat Error] {e}")
                self.sync_state()
                time.sleep(60)

    def run(self):
        t_poll = threading.Thread(target=self.polling_loop, daemon=True)
        t_poll.start()
        self.heartbeat_loop()

if __name__ == '__main__':
    vultix = VultixSovereign()
    vultix.run()
