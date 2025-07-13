import asyncio
import websockets
import json
import uuid

MODE = 2
ROOM_ID = "1234-5678"
USER_ID = str(uuid.uuid4())
USER_NAME = "テストユーザ"

# WebSocketのエンドポイントURL
# chalice deploy後に表示されるURLを使ってください。
# 例: wss://xxxxxx.execute-api.ap-northeast-1.amazonaws.com/api
WEBSOCKET_URL = "wss://abtz3xytoi.execute-api.ap-northeast-1.amazonaws.com/api?roomId=1234-5678&mode=2"

async def connect_and_send():
    async with websockets.connect(WEBSOCKET_URL) as websocket:
        print(f"接続完了: {WEBSOCKET_URL}")

        # 送信メッセージ
        result_xml = """
        <item>
            <lv>11</lv><title>ILAYZA</title><difficulty>DPA</difficulty><dp_unofficial_lv>11.4</dp_unofficial_lv>
            <lamp>H-CLEAR</lamp><score>+110</score><opt>OFF / OFF</opt><bp>4</bp><bpi>??</bpi>
            <notes>1465</notes><score_cur>2657</score_cur><score_pre>2547</score_pre>
            <lamp_pre>EXH-CLEAR</lamp_pre><bp_pre>15</bp_pre><rank_pre>AA</rank_pre><rank>AAA</rank>
            <rankdiff>AAA+52</rankdiff><rankdiff0>AAA</rankdiff0><rankdiff1>+52</rankdiff1>
            <scorerate>90.68</scorerate>
        </item>
        """

        message = {
            "mode": MODE,
            "roomId": ROOM_ID,
            "userId": USER_ID,
            "name": USER_NAME,
            "result": result_xml.strip()
        }

        await websocket.send(json.dumps(message))
        print("メッセージ送信完了")

        # メッセージ受信（他ユーザから返ってくるものも受信）
        while True:
            response = await websocket.recv()
            print("受信:", response)

if __name__ == "__main__":
    asyncio.run(connect_and_send())