import os, json, time, datetime, requests
from google import genai

STATE_PATH = 'Vultix_Master_State.json'

class VultixSovereign:
    def __init__(self):
        self.fuel = {
            'GEMINI_API_KEY': os.environ.get('GEMINI_API_KEY'),
            'TELEGRAM_BOT_TOKEN': os.environ.get('TELEGRAM_BOT_TOKEN'),
            'OMAR_CHAT_ID': os.environ.get('OMAR_CHAT_ID')
        }
        self.state = self.load_state()
        self.init_brain()

    def load_state(self):
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, 'r') as f:
                return json.load(f)
        return {'status': 'DEPLOYED', 'cycle': 0}

    def sync_state(self):
        self.state['last_sync'] = datetime.datetime.now().isoformat()
        with open(STATE_PATH, 'w') as f:
            json.dump(self.state, f, indent=4, ensure_ascii=False)

    def init_brain(self):
        if self.fuel['GEMINI_API_KEY']:
            self.client = genai.Client(api_key=self.fuel['GEMINI_API_KEY'])
            self.model = 'gemini-1.5-flash'
            print(f"[VULTIX] Brain initialized with model: {self.model}")
        else:
            print("[WARNING] GEMINI_API_KEY not set.")
            self.client = None

    def send_signal(self, text):
        try:
            url = f"https://api.telegram.org/bot{self.fuel['TELEGRAM_BOT_TOKEN']}/sendMessage"
            requests.post(
                url,
                json={'chat_id': self.fuel['OMAR_CHAT_ID'], 'text': text, 'parse_mode': 'Markdown'},
                timeout=10
            )
            print(f"[Telegram] Signal sent: {text[:60]}...")
        except Exception as e:
            print(f"[Telegram Error] {e}")

    def run_eternal_loop(self):
        self.send_signal("🚀 *VULTIX ONLINE ON CLOUD*\nSystem has successfully migrated and is now independent.")
        while True:
            try:
                self.state['cycle'] += 1
                self.state['status'] = 'SOVEREIGN_ACTIVE'
                self.sync_state()
                print(f"[{datetime.datetime.now().isoformat()}] Cycle {self.state['cycle']} complete. State saved.")
                time.sleep(3600)
            except Exception as e:
                print(f"[Loop Error] {e}")
                self.send_signal(f"⚠️ Error in loop: {e}")
                time.sleep(60)

if __name__ == '__main__':
    vultix = VultixSovereign()
    vultix.run_eternal_loop()
