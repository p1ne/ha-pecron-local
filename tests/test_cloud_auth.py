import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from custom_components.pecron_local.cloud_auth import (
    cloud_login,
    fetch_auth_key,
    fetch_product_tsl,
    CloudAuthError,
)


async def test_login_returns_token_on_success():
    import base64, json
    jwt_payload = base64.b64encode(json.dumps({"uid": "123", "exp": 9999999999}).encode()).decode().rstrip("=")
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "code": 200,
        "data": {
            "accessToken": {
                "token": f"header.{jwt_payload}.sig"
            }
        }
    })
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession.post", return_value=mock_resp):
        result = await cloud_login(
            email="test@example.com",
            password="pass",
            region_key="na",
        )
    assert "token" in result


async def test_login_raises_on_bad_credentials():
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"code": 5031, "msg": "not registered"})
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession.post", return_value=mock_resp):
        with pytest.raises(CloudAuthError):
            await cloud_login("bad@test.com", "wrong", "na")


async def test_fetch_auth_key_returns_key():
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "code": 200,
        "data": {"authKey": "dGVzdGtleQ=="}
    })
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession.post", return_value=mock_resp):
        key = await fetch_auth_key(
            token="mytoken",
            region_key="na",
            product_key="p11uAG",
            device_key="AABBCCDDEEFF",
        )
    assert key == "dGVzdGtleQ=="


async def test_fetch_product_tsl_preserves_enum_labels():
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "code": 200,
        "data": {
            "properties": [
                {
                    "code": "ac_charging_power_ios",
                    "id": 89,
                    "dataType": "ENUM",
                    "name": "AC charging speed",
                    "subType": "RW",
                    "specs": [
                        {"dataType": "ENUM", "name": "20%", "value": "0"},
                        {"dataType": "ENUM", "name": "100%", "value": "4"},
                    ],
                }
            ]
        },
    })
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession.get", return_value=mock_resp):
        controls = await fetch_product_tsl(
            token="mytoken",
            region_key="na",
            product_key="p11uAG",
        )

    assert controls["ac_charging_power_ios"]["id"] == 89
    assert controls["ac_charging_power_ios"]["enum_labels"] == {0: "20%", 4: "100%"}
