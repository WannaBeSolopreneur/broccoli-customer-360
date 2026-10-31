"""One chDB session per process, so the warehouse is built once per test run."""
import pytest

from c360 import config, er_report, generate, warehouse


@pytest.fixture(scope="session")
def wh():
    if not (config.RAW / "tenants.json").exists():
        generate.Gen().run()
    if warehouse._SESSION is None:
        warehouse.build()
    er_report.load_truth()
    return warehouse
