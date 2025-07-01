import os
import json
import urllib.parse
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, QuickReply, QuickReplyButton,
    MessageAction, PostbackAction, FlexSendMessage
)
# 新增這個模組，用來解析 postback data
from urllib.parse import parse_qs

app = Flask(__name__)

# 從環境變數讀取金鑰
CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    print("錯誤：CHANNEL_ACCESS_TOKEN 或 CHANNEL_SECRET 環境變數未設定。")

# 初始化 Line Bot API
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 載入資料檔案
try:
    with open('急診醫院清單_台北新北基隆.json', 'r', encoding='utf-8') as f:
        hospital_data = json.load(f)
    print("成功載入急診醫院清單資料！")
except FileNotFoundError:
    print("錯誤：找不到 '急診醫院清單_台北新北基隆.json'。")
    hospital_data = []

# Webhook 路由
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("簽名錯誤，請檢查您的 Channel Secret 是否正確。")
        abort(400)
    return 'OK'

# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.lower().strip()

    # 主選單觸發指令
    if msg == '主選單':
        flex_message = FlexSendMessage(
            alt_text='請選擇服務',
            contents={
              "type": "bubble",
              "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                  {
                    "type": "text",
                    "text": "醫療資訊查詢服務",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#FFFFFF"
                  }
                ],
                "backgroundColor": "#0066cc",
                "paddingAll": "20px"
              },
              "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                  {
                    "type": "button",
                    "action": {
                      "type": "postback",
                      "label": "🌙 深夜/假日診所查詢",
                      "data": "action=select_city&type=clinic"
                    },
                    "style": "link",
                    "height": "sm"
                  },
                  {
                    "type": "separator",
                    "margin": "md"
                  },
                  {
                    "type": "button",
                    "action": {
                      "type": "postback",
                      "label": "💊 北北基特約藥局查詢",
                      "data": "action=select_city&type=pharmacy" # pharmacy 為藥局，可自行擴充
                    },
                    "style": "link",
                    "height": "sm"
                  }
                ],
                "spacing": "sm",
                "paddingAll": "12px"
              }
            }
        )
        line_bot_api.reply_message(event.reply_token, flex_message)
        return

    # 保留原本的文字查詢功能
    if '醫院' in msg and '查詢' in msg:
        area = msg.replace('查詢', '').replace('醫院', '').strip()
        clinics = [h for h in hospital_data if area in h.get('地區', '') or area in h.get('行政區', '')]
        
        if not clinics:
            reply_text = f"抱歉，找不到位於「{area}」的醫院資料。"
        else:
            # 只回覆前5筆文字資料
            reply_list = []
            for h in clinics[:5]:
                address = h.get('醫院地址', '')
                maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(address)}"
                reply_list.append(f"🏥 {h['醫院名稱']}\n📍 {address}\n📞 {h.get('醫院電話', '')}\n🗺️ 地圖: {maps_url}")
            
            reply_text = f"為您查詢到「{area}」的醫院如下：\n\n" + "\n\n".join(reply_list)
            if len(clinics) > 5:
                reply_text += f"\n\n...共找到 {len(clinics)} 筆，僅顯示前 5 筆。"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
    else:
        reply_text = "您好！請輸入「主選單」來開始互動，或使用「查詢 [地區] 醫院」來進行文字查詢。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))


# 處理 Postback 事件 (選單互動的核心)
@handler.add(PostbackEvent)
def handle_postback(event):
    # 解析 postback.data
    data = dict(parse_qs(event.postback.data))
    action = data.get('action')[0]
    
    # 根據 action 執行不同動作
    if action == 'select_city':
        # 找出所有不重複的縣市
        cities = sorted(list(set([item.get('縣市', '其他') for item in hospital_data])))
        
        # 建立 Quick Reply 按鈕
        quick_reply_buttons = []
        for city in cities:
            if city: # 確保城市名稱不是空的
                quick_reply_buttons.append(
                    QuickReplyButton(action=PostbackAction(label=city, data=f"action=select_district&city={city}"))
                )
            
        message = TextSendMessage(
            text='請選擇縣市：',
            quick_reply=QuickReply(items=quick_reply_buttons)
        )
        line_bot_api.reply_message(event.reply_token, message)

    elif action == 'select_district':
        city = data.get('city')[0]
        
        # 篩選出該縣市所有不重複的地區
        districts = sorted(list(set([item.get('地區', '其他') for item in hospital_data if item.get('縣市') == city])))
        
        quick_reply_buttons = []
        for district in districts:
            if district: # 確保地區名稱不是空的
                quick_reply_buttons.append(
                    QuickReplyButton(action=PostbackAction(label=district, data=f"action=show_clinics&city={city}&district={district}"))
                )
        
        message = TextSendMessage(
            text=f'您選擇了 {city}，請選擇地區：',
            quick_reply=QuickReply(items=quick_reply_buttons)
        )
        line_bot_api.reply_message(event.reply_token, message)
        
    elif action == 'show_clinics':
        city = data.get('city')[0]
        district = data.get('district')[0]
        
        # 篩選出最終的診所列表
        clinics = [h for h in hospital_data if h.get('縣市') == city and h.get('地區') == district]

        if not clinics:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"抱歉，在「{city}{district}」找不到資料。"))
            return

        # 準備輪播卡片的容器
        bubbles = []
        for h in clinics[:12]: # LINE 輪播最多顯示 12 張卡片
            address = h.get('醫院地址', '')
            encoded_address = urllib.parse.quote(address)
            maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
            
            # 製作一張卡片 (bubble)
            bubble = {
              "type": "bubble", "size": "kilo",
              "body": { "type": "box", "layout": "vertical", "contents": [
                  { "type": "text", "text": h.get('醫院名稱', '無名稱'), "weight": "bold", "size": "md", "wrap": True },
                  { "type": "box", "layout": "vertical", "margin": "lg", "spacing": "sm", "contents": [
                      { "type": "box", "layout": "baseline", "spacing": "sm", "contents": [
                          { "type": "text", "text": "📍", "color": "#aaaaaa", "size": "sm", "flex": 1 },
                          { "type": "text", "text": address, "wrap": True, "color": "#666666", "size": "sm", "flex": 5 }
                      ]},
                      { "type": "box", "layout": "baseline", "spacing": "sm", "contents": [
                          { "type": "text", "text": "📞", "color": "#aaaaaa", "size": "sm", "flex": 1 },
                          { "type": "text", "text": h.get('醫院電話', '無提供'), "wrap": True, "color": "#666666", "size": "sm", "flex": 5 }
                      ]}]
                  }]},
              "footer": { "type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                  { "type": "button", "style": "link", "height": "sm", "action": {
                      "type": "uri", "label": "🗺️ 開啟地圖", "uri": maps_url
                  }}], "flex": 0 }}
            bubbles.append(bubble)

        # 建立輪播訊息
        flex_message = FlexSendMessage(
            alt_text=f"{city}{district}的診所資訊",
            contents={"type": "carousel", "contents": bubbles}
        )
        
        line_bot_api.reply_message(event.reply_token, flex_message)

# 程式的進入點
if __name__ == "__main__":
    app.run()