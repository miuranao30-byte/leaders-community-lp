import os
import requests
import tempfile
from fastapi import FastAPI, BackgroundTasks, Form, Request, Response
from twilio.twiml.voice_response import VoiceResponse, Dial, Sip
from twilio.request_validator import RequestValidator
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configuration
TWILIO_SIP_DOMAIN = os.getenv("TWILIO_SIP_DOMAIN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN")
BASE_URL = os.getenv("BASE_URL")

# Initialize Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

app = FastAPI()

def send_line_notify(message: str):
    """Line Notify APIを使用してメッセージを送信する"""
    if not LINE_NOTIFY_TOKEN:
        print("LINE_NOTIFY_TOKEN is not set. Skipping notification.")
        return

    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
    data = {"message": message}
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
    except Exception as e:
        print(f"Error sending LINE notification: {e}")

def process_recording_and_summarize(recording_url: str):
    """
    録音ファイルをダウンロードし、Geminiで要約してLINE通知する処理
    (Background Task)
    """
    temp_file_path = None
    try:
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set.")

        send_line_notify("\n🎤 通話録音の解析を開始します...")

        # 1. Download the recording
        # TwilioのRecordingUrlはmp3/wavなどを返す。ここでは拡張子なしURLの場合もあるが、
        # 通常.mp3などを付与してリクエストするとその形式で取得可能。
        # デフォルトでTwilioはwavまたはmp3。とりあえずそのまま取得してGeminiに投げる。
        # (認証が必要な場合があるため、Twilio設定でPublic Access許可が必要か、認証ヘッダが必要)
        # ここでは簡易実装として直接GETする(Twilio設定依存)。
        
        # 安全のため .mp3 を付与して明示的にmp3を取得
        download_url = f"{recording_url}.mp3" 
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file_path = temp_file.name

        print(f"Downloaded recording to {temp_file_path}")

        # 2. Upload to Gemini
        print("Uploading to Gemini...")
        uploaded_file = genai.upload_file(temp_file_path, mime_type="audio/mp3")
        
        # 3. Generate content
        print("Generating summary...")
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = "この通話音声を分析し、『発信者』『用件』『ネクストアクション』を日本語で要約してください。"
        
        result = model.generate_content([uploaded_file, prompt])
        summary_text = result.text

        # 4. Notify result
        message = f"\n📝 通話要約結果:\n{summary_text}"
        send_line_notify(message)

        # 5. Cleanup Gemini file (Optional but recommended)
        try:
            uploaded_file.delete()
        except:
            pass

    except Exception as e:
        error_msg = f"\n❌ AI処理中にエラーが発生しました:\n{str(e)}"
        print(error_msg)
        send_line_notify(error_msg)
    finally:
        # Cleanup local file
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.post("/voice")
async def voice_handler(request: Request):
    """
    Twilio着信時のWebhook。
    SIPユーザーを一斉呼び出しする。
    """
    response = VoiceResponse()
    
    # Simultaneous dialing
    # record='true' で通話録音
    # action で通話終了後の処理を指定
    dial = Dial(record='true', action='/gather_result')
    
    # SIPユーザーリスト
    sip_users = ['mobile_a', 'mobile_b', 'emergency']
    
    if TWILIO_SIP_DOMAIN:
        for user in sip_users:
            sip_uri = f"sip:{user}@{TWILIO_SIP_DOMAIN}"
            # statusCallback で応答イベントを監視
            dial.sip(
                sip_uri, 
                statusCallback=f"{BASE_URL}/status_callback", 
                statusCallbackEvent='answered'
            )
    else:
        # For testing or error handling
        response.say("システムエラーです。SIPドメイン設定を確認してください。")
        return Response(content=str(response), media_type="application/xml")

    response.append(dial)
    
    return Response(content=str(response), media_type="application/xml")
    
# NOTE: returning raw XML response helper for FastAPI

@app.post("/status_callback")
async def status_callback(
    To: str = Form(...), 
    CallStatus: str = Form(...)
):
    """
    SIPコールのステータス変更を受け取る。
    誰が応答したか(answered)を通知する。
    """
    if CallStatus == 'answered':
        # To format: sip:mobile_a@domain.sip.twilio.com
        # Extract user part
        try:
            user_part = To.split(":")[1].split("@")[0]
            
            # User friendly mapping
            user_map = {
                "mobile_a": "携帯A",
                "mobile_b": "携帯B",
                "emergency": "緊急用携帯"
            }
            display_name = user_map.get(user_part, user_part)
            
            message = f"\n📞 {display_name} が電話に出ました！"
            send_line_notify(message)
            
        except Exception as e:
            print(f"Error parse status callback: {e}")

    return Response(content="OK", media_type="text/plain")


@app.post("/gather_result")
async def gather_result(
    background_tasks: BackgroundTasks,
    RecordingUrl: str = Form(None)
):
    """
    通話終了後の処理。
    録音があればバックグラウンドで解析する。
    """
    resp = VoiceResponse()
    resp.hangup()

    if RecordingUrl:
        # バックグラウンドでAI処理を実行して、レスポンスを即座に返す
        background_tasks.add_task(process_recording_and_summarize, RecordingUrl)
    else:
        print("No RecordingUrl found in request.")

    return Response(content=str(resp), media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
