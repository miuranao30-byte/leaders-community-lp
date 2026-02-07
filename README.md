# Twilio + Gemini AI 着信自動化システム

Twilioへの着信をSIP経由で複数端末に転送し、応答通知および通話終了後のAI自動要約（Gemini使用）を行うFastAPIアプリケーションです。

## セットアップ

1. **環境構築**
   Python 3.10+ が必要です。
   ```bash
   pip install -r requirements.txt
   ```

2. **環境変数設定**
   `.env` ファイルを編集し、以下のキーを設定してください。
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`: Twilioダッシュボードから取得
   - `TWILIO_SIP_DOMAIN`: Twilio SIPドメイン (例: `my-domain.sip.twilio.com`)
   - `GOOGLE_API_KEY`: Google AI Studioから取得 (Gemini API用)
   - `LINE_NOTIFY_TOKEN`: LINE Notifyマイページから発行
   - `BASE_URL`: アプリケーションの公開URL (ngrokやCloud RunのURLなど)

## 起動方法

```bash
uvicorn main:app --reload
```
サーバーが `http://localhost:8000` で起動します。

## 動作確認 (Manual Verification)

Twilio WebhookはパブリックなURLが必要ですが、ローカルでのロジック確認には以下のcurlコマンドが便利です。

### 1. 着信リクエスト (TwiML生成確認)
```bash
curl -X POST http://localhost:8000/voice
```
**期待される結果:**
`<Dial><Sip>...` を含むXMLが返されること。

### 2. 応答ステータス通知テスト
```bash
curl -X POST http://localhost:8000/status_callback \
     -d "CallStatus=answered" \
     -d "To=sip:mobile_a@my-domain.sip.twilio.com"
```
**期待される結果:**
LINEに「📞 携帯A が電話に出ました！」と通知が届くこと。

### 3. 通話終了＆要約テスト
※実際に録音ファイルがないとエラーになりますが、ログで動作フローを確認できます。
```bash
curl -X POST http://localhost:8000/gather_result \
     -d "RecordingUrl=http://example.com/recording"
```
**期待される結果:**
バックグラウンドタスクが開始され、ログに `Downloading recording...` などが表示されること（ダウンロード失敗エラーになるのが正常）。

## デプロイ
ReplitやCloud Runにデプロイし、TwilioのVoice Webhook URLに `https://YOUR-APP-FOO.com/voice` を設定してください。
