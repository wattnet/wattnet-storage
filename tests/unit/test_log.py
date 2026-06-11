import logging

from wattnet.storage.utils.log import get


class TestGet:
    def test_returns_logger_instance(self):
        assert isinstance(get("test.logger"), logging.Logger)

    def test_logger_name_matches(self):
        logger = get("my.module.name")
        assert logger.name == "my.module.name"

    def test_library_root_has_null_handler(self):
        root = logging.getLogger("wattnet.storage")
        handler_types = [type(h) for h in root.handlers]
        assert logging.NullHandler in handler_types
