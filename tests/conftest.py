# 公共fixture
import pytest
import yaml
import os

@pytest.fixture(scope="session")
def load_data():
    """加载测试数据"""
    data_path = os.path.join(os.path.dirname(__file__), "data", "api_data.yaml")
    with open(data_path, encoding="utf-8") as f:
        return yaml.safe_load(f)
