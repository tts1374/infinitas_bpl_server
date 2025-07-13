import pytest
import os
import json
from moto import mock_dynamodb
import boto3
from unittest.mock import patch
from chalice.app import WebsocketDisconnectedError, BadRequestError
from app import register_user, broadcast_result, unregister_user, app

TABLE_NAME = "bpl_room_dev"

@pytest.fixture(scope='function')
def setup_dynamodb():
    os.environ['APP_AWS_REGION'] = 'ap-northeast-1'
    os.environ['TABLE_NAME'] = TABLE_NAME

    with mock_dynamodb():
        dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'connection_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'connection_id', 'AttributeType': 'S'},
                {'AttributeName': 'room_id', 'AttributeType': 'S'},
                {'AttributeName': 'mode', 'AttributeType': 'N'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'room_mode-index',
                    'KeySchema': [
                        {'AttributeName': 'room_id', 'KeyType': 'HASH'},
                        {'AttributeName': 'mode', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        table.meta.client.get_waiter('table_exists').wait(TableName=TABLE_NAME)
        yield

# 疑似 Websocket Event
class DummyEvent:
    def __init__(self, connection_id, params=None, body=None):
        self.connection_id = connection_id
        self.body = body
        self._params = params or {}

    def to_dict(self):
        return {'queryStringParameters': self._params}

# ---------- 正常系 ----------

@pytest.mark.usefixtures("setup_dynamodb")
def test_register_user():
    event = DummyEvent(
        connection_id="test-conn-1",
        params={"roomId": "1234-5678", "mode": "1"}
    )

    response = register_user(event)
    assert response['statusCode'] == 200

@pytest.mark.usefixtures("setup_dynamodb")
def test_register_user_over_capacity():
    for i in range(4):
        event = DummyEvent(
            connection_id=f"conn-{i}",
            params={"roomId": "1111-2222", "mode": "1"}
        )
        response = register_user(event)
        assert response['statusCode'] == 200

    event_over = DummyEvent(
        connection_id="conn-5",
        params={"roomId": "1111-2222", "mode": "1"}
    )
    response = register_user(event_over)
    assert response['statusCode'] == 500
    assert "定員オーバー" in response['body']

@pytest.mark.usefixtures("setup_dynamodb")
def test_broadcast_result():
    event = DummyEvent(
        connection_id="test-conn-2",
        params={"roomId": "3333-4444", "mode": "2"}
    )
    register_user(event)

    send_body = json.dumps({
        "roomId": "3333-4444",
        "mode": 2,
        "userId": "user123",
        "name": "テストユーザー",
        "result": "<result>test</result>"
    })
    event_msg = DummyEvent(
        connection_id="test-conn-2",
        body=send_body
    )

    with patch.object(app.websocket_api, 'send', return_value=None):
        response = broadcast_result(event_msg)
        assert response['statusCode'] == 200

@pytest.mark.usefixtures("setup_dynamodb")
def test_unregister_user():
    event = DummyEvent(
        connection_id="test-conn-3",
        params={"roomId": "5555-6666", "mode": "2"}
    )
    register_user(event)

    disconnect_event = DummyEvent(connection_id="test-conn-3")
    response = unregister_user(disconnect_event)
    assert response['statusCode'] == 200

# ---------- 異常系 ----------

@pytest.mark.usefixtures("setup_dynamodb")
def test_register_user_invalid_mode():
    event = DummyEvent(
        connection_id="test-conn-invalid-mode",
        params={"roomId": "1234-5678", "mode": "99"}
    )

    response = register_user(event)
    assert response['statusCode'] == 500
    assert "モードの形式が違います" in response['body']

@pytest.mark.usefixtures("setup_dynamodb")
def test_register_user_invalid_room_id():
    event = DummyEvent(
        connection_id="test-conn-invalid-room",
        params={"roomId": "abcd-efgh", "mode": "1"}
    )

    response = register_user(event)
    assert response['statusCode'] == 500
    assert "ルームIDの形式が違います" in response['body']

def test_register_user_dynamodb_error(monkeypatch):
    monkeypatch.setenv("APP_AWS_REGION", "invalid-region")
    monkeypatch.setenv("TABLE_NAME", "dummy_table")

    event = DummyEvent(
        connection_id="test-conn-dynamo-error",
        params={"roomId": "1234-5678", "mode": "1"}
    )

    response = register_user(event)
    assert response['statusCode'] == 500
    assert "ルームの接続に失敗しました" in response['body']

@pytest.mark.usefixtures("setup_dynamodb")
def test_broadcast_result_disconnected():
    event = DummyEvent(
        connection_id="test-conn-disconnect",
        params={"roomId": "9999-8888", "mode": "2"}
    )
    register_user(event)

    send_body = json.dumps({
        "roomId": "9999-8888",
        "mode": 2,
        "userId": "user999",
        "name": "切断テスト",
        "result": "<result>test</result>"
    })

    event_msg = DummyEvent(
        connection_id="test-conn-disconnect",
        body=send_body
    )

    with patch.object(app.websocket_api, 'send', side_effect=WebsocketDisconnectedError()):
        response = broadcast_result(event_msg)
        assert response['statusCode'] == 200

    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')
    table = dynamodb.Table(TABLE_NAME)

    result = table.get_item(Key={'connection_id': "test-conn-disconnect"})
    assert 'Item' not in result
