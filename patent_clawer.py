import webview
import json
import threading
import time
import requests
from bs4 import BeautifulSoup
from apiCall import GenAI

class PatentAnalyzerAPI:
    def __init__(self):
        self.patent_queue = []  # 專利號隊列
        self.responses = {}  # 存儲專利號與其回應
        self.current_patent = None
        self.lock = threading.Lock()
        self.api_key = None
        self.PROMPT_TEXT = None
        self.gpt = None
        self.load_config()

    def load_config(self):
        try:
            with open('config.json') as f:
                config = json.load(f)
                self.api_key = config.get('api_key')
                prompt_path = config.get('prompt_path')
                
            with open(prompt_path, 'r', encoding="utf-8") as f:
                self.PROMPT_TEXT = f.read()
            
            self.gpt = GenAI(self.api_key)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return f"Failed to load configuration: {e}"

    def enqueue_patent(self, patent_number):
        with self.lock:
            # 檢查專利號是否已存在於回應或隊列中
            if patent_number in self.responses:
                return {"status": "exists", "message": "該專利號已經有回應。"}
            if patent_number == self.current_patent or patent_number in self.patent_queue:
                return {"status": "in_queue", "message": "該專利號已經在處理或等待處理。"}
            
            self.patent_queue.append(patent_number)
            if len(self.patent_queue) == 1:  # 如果隊列只有一個項目，立刻處理
                threading.Thread(target=self.process_queue).start()

        return {"status": "added", "message": self.get_pending_patents()}

    def process_queue(self):
        while self.patent_queue:
            with self.lock:
                self.current_patent = self.patent_queue.pop(0)
            response = self.fetch_patent_data(self.current_patent)
            self.responses[self.current_patent] = response
            self.current_patent = None

            # 通知前端更新隊列和回應
            webview.windows[0].evaluate_js("loadResponses(); loadPendingPatents();")

    def fetch_patent_data(self, patent_number):
        """獲取給定專利號的專利數據。"""
        link = f'https://patents.google.com/patent/{patent_number}/'
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0'}
        try:
            response = requests.get(link, headers=headers, verify=False)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            return f"請求錯誤: {e}"

        bs = BeautifulSoup(response.content, 'html.parser')

        def extract_text(itemprop):
            section = bs.find('section', {'itemprop': itemprop})
            if section:
                span = section.find('span', class_='notranslate')
                if span:
                    [tag.extract() for tag in section.find_all('span', class_='notranslate')]
                return section.text.strip()
            return '未找到'

        data = {
            'Claims': extract_text('claims'),
            'Description': extract_text('description'),
            'Abstract': extract_text('abstract'),
            'Patent Office': bs.find('dd', {'itemprop': 'countryName'}).text if bs.find('dd', {'itemprop': 'countryName'}) else '未找到'
        }

        if not data['Abstract'] and not data['Description']:
            return "此專利號未找到有效內容。"

        query = self.PROMPT_TEXT + "此為專利內容:\n " + data['Abstract'] + data['Description'] + self.PROMPT_TEXT
        response = self.gpt.generate_content(query)
        return response.text

    def get_responses(self):
        return json.dumps(self.responses)

    def get_pending_patents(self):
        with self.lock:
            return json.dumps({
                "current": self.current_patent,
                "queue": self.patent_queue
            })

    def search_patent_response(self, patent_number):
        return self.responses.get(patent_number, "未找到該專利號的回應")

    def delete_patent_response(self, patent_number):
        if patent_number in self.responses:
            del self.responses[patent_number]
            return f"已刪除專利號 {patent_number} 的回應"
        return "未找到該專利號的回應"

def main():
    api = PatentAnalyzerAPI()
    webview.create_window('Patent Search Interface', './templates/index.html', js_api=api)
    webview.start()

if __name__ == "__main__":
    main()
