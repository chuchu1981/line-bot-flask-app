# 檔名: app.py

import os
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# 從「環境變數」讀取金鑰，這是部署到正式主機的標準做法
# 我們稍後會在 Render 的後台設定這些金鑰，而不是寫死在程式碼裡
CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')

# 檢查金鑰是否成功讀取，若在本機測試時未設定，程式會提示並結束
if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    print("錯誤：CHANNEL_ACCESS_TOKEN 或 CHANNEL_SECRET 環境變數未設定。")
    # 在正式環境中，若未設定，程式將無法啟動
    # exit() # 在本地運行時可以先註解掉這行，方便測試

# 初始化 Line Bot API
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 載入資料檔案 (我們假設檔案和 app.py 在同一個資料夾)
try:
    # 確保檔案路徑正確
    with open('急診醫院清單_台北新北基隆.json', 'r', encoding='utf-8') as f:
        hospital_data = json.load(f)
    print("成功載入急診醫院清單資料！")
    print(f"總共載入了 {len(hospital_data)} 筆資料。")
    print(f"前三筆資料內容： {hospital_data[:3]}")
except FileNotFoundError:
    print("錯誤：找不到 '急診醫院清單_台北新北基隆.json'。請確保檔案與 app.py 在同一個資料夾中。")
    hospital_data = [] # 如果找不到檔案，給一個空列表以避免程式崩潰

# Webhook 路由，這是 LINE 平台會來呼叫的網址
@app.route("/callback", methods=['POST'])
def callback():
    # 取得 LINE 發送過來的簽名
    signature = request.headers['X-Line-Signature']

    # 取得請求的內容
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # 驗證簽名是否正確
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("簽名錯誤，請檢查您的 Channel Secret 是否正確。")
        abort(400)

    return 'OK'

# 處理文字訊息的邏輯
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.lower().strip() # 將使用者訊息轉為小寫並移除前後空白

    # 關鍵字觸發邏輯
    if '醫院' in msg and '查詢' in msg:
        # 從訊息中提取地區名稱
        area = msg.replace('查詢', '').replace('醫院', '').strip()

        # 在資料中尋找符合地區的醫院
        reply_list = [
            f"🏥 {h['醫院名稱']}\n📍 地址: {h['醫院地址']}\n📞 電話: {h['醫院電話']}"
            for h in hospital_data if area in h.get('地區', '')
        ]

        if reply_list:
            # 如果找到醫院，格式化回覆訊息
            reply_text = f"為您查詢到「{area}」的醫院如下：\n\n" + "\n\n".join(reply_list)
        else:
            # 如果找不到
            reply_text = f"抱歉，找不到位於「{area}」的醫院資料。\n請確認地區名稱是否正確（例如：中山區、信義區...）。"
    else:
        # 如果不符合關鍵字，回傳預設訊息
        reply_text = "您好！這是一個醫院資訊查詢機器人。\n\n請試著輸入「查詢 [地區] 醫院」，例如：\n查詢 北投區 醫院"

    # 將準備好的訊息回覆給使用者
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# 程式的進入點 (讓 Render 能夠啟動)
if __name__ == "__main__":
    # Render 會自動處理 port，所以我們不需要指定
    app.run()