# 示例接口用例
import requests
import pytest

@pytest.mark.smoke
def test_get_user(load_data):
    """示例接口测试"""
    case = load_data["get_user"]
    resp = requests.request(method=case["method"], url=case["url"])

    assert resp.status_code == case["expected_status"], f"状态码错误: {resp.status_code}"
    assert resp.json()["name"] == case["expected_name"], f"用户名不匹配: {resp.json()['name']}"
