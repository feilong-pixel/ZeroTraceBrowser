# SPDX-License-Identifier: MIT

from __future__ import annotations

import core.context_modules.iphone_context as iphone_context


def test_iphone_devices_api_returns_detected_devices(api_client, monkeypatch):
    client, *_ = api_client

    monkeypatch.setattr(
        iphone_context,
        "detect_iphone_devices",
        lambda: {
            "supported": True,
            "devices": [
                {
                    "name": "Apple iPhone",
                    "device_id": "Apple iPhone",
                    "kind": "mtp",
                    "dcim_available": True,
                    "album_count_sample": 1,
                    "media_count_sample": 5,
                }
            ],
            "message": "ok",
        },
    )

    response = client.get("/api/iphone/devices")

    assert response.status_code == 200
    data = response.json()
    assert data["supported"] is True
    assert data["devices"][0]["name"] == "Apple iPhone"
    assert data["devices"][0]["dcim_available"] is True
