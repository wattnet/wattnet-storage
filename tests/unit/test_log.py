import logging
from unittest.mock import patch

from wattnet.storage.utils.log import CustomFormatter, _get_level, get


class TestGetLevel:
    def test_debug(self):
        assert _get_level("debug") == logging.DEBUG

    def test_info(self):
        assert _get_level("info") == logging.INFO

    def test_warning(self):
        assert _get_level("warning") == logging.WARNING

    def test_error(self):
        assert _get_level("error") == logging.ERROR

    def test_critical(self):
        assert _get_level("critical") == logging.CRITICAL

    def test_uppercase_input(self):
        assert _get_level("DEBUG") == logging.DEBUG

    def test_mixed_case_input(self):
        assert _get_level("Warning") == logging.WARNING

    def test_invalid_string_returns_info(self):
        assert _get_level("not_a_level") == logging.INFO

    def test_empty_string_returns_info(self):
        assert _get_level("") == logging.INFO


class TestCustomFormatter:
    def test_format_returns_string(self):
        fmt = "%(levelname)s | %(message)s"
        formatter = CustomFormatter(fmt)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert isinstance(result, str)

    def test_format_contains_message(self):
        formatter = CustomFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        assert "hello world" in formatter.format(record)

    def test_format_contains_ansi_color(self):
        formatter = CustomFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="msg",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "\x1b[" in result

    def test_format_contains_reset(self):
        formatter = CustomFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="msg",
            args=(),
            exc_info=None,
        )
        assert "\x1b[0m" in formatter.format(record)

    def test_debug_and_error_have_different_colors(self):
        formatter = CustomFormatter("%(message)s")

        def make(level):
            return logging.LogRecord(
                name="t",
                level=level,
                pathname="",
                lineno=0,
                msg="x",
                args=(),
                exc_info=None,
            )

        debug_result = formatter.format(make(logging.DEBUG))
        error_result = formatter.format(make(logging.ERROR))
        assert debug_result != error_result

    def test_all_standard_levels_produce_colored_output(self):
        formatter = CustomFormatter("%(levelname)s")
        for level in (
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        ):
            record = logging.LogRecord(
                name="t",
                level=level,
                pathname="",
                lineno=0,
                msg="msg",
                args=(),
                exc_info=None,
            )
            result = formatter.format(record)
            assert "\x1b[" in result, f"No ANSI code for level {level}"


class TestGet:
    def test_returns_logger_instance(self):
        assert isinstance(get("test.logger"), logging.Logger)

    def test_logger_name_matches(self):
        logger = get("my.module.name")
        assert logger.name == "my.module.name"

    def test_console_handler_present_when_configured(self, tmp_path):
        from unittest.mock import MagicMock

        from wattnet.storage.utils import log as log_module

        mock_settings = MagicMock()
        mock_settings.log_level = "INFO"
        mock_settings.log_handlers = ["console"]
        mock_settings.log_file = tmp_path / "test.log"
        with patch.object(log_module, "settings", mock_settings):
            logger = log_module.get("test.console_only")
        handler_types = [type(h) for h in logger.handlers]
        assert logging.StreamHandler in handler_types

    def test_no_file_handler_when_only_console_configured(self, tmp_path):
        from unittest.mock import MagicMock

        from wattnet.storage.utils import log as log_module

        mock_settings = MagicMock()
        mock_settings.log_level = "INFO"
        mock_settings.log_handlers = ["console"]
        mock_settings.log_file = tmp_path / "test.log"
        with patch.object(log_module, "settings", mock_settings):
            logger = log_module.get("test.no_file_explicit")
        assert not any(isinstance(h, logging.FileHandler) for h in logger.handlers)

    def test_no_duplicate_handlers_on_repeated_calls(self, tmp_path):
        from unittest.mock import MagicMock

        from wattnet.storage.utils import log as log_module

        mock_settings = MagicMock()
        mock_settings.log_level = "INFO"
        mock_settings.log_handlers = ["console"]
        mock_settings.log_file = tmp_path / "test.log"
        name = "test.dedup.unique"
        with patch.object(log_module, "settings", mock_settings):
            log_module.get(name)
            log_module.get(name)
            logger = log_module.get(name)
        assert len(logger.handlers) == 1

    def test_logger_level_reflects_settings(self):
        from wattnet.storage.settings import settings

        expected = _get_level(settings.log_level)
        logger = get("test.level")
        assert logger.level == expected

    def test_file_handler_added_when_configured(self, tmp_path):
        log_file = tmp_path / "test.log"
        from unittest.mock import MagicMock

        from wattnet.storage.utils import log as log_module

        mock_settings = MagicMock()
        mock_settings.log_level = "INFO"
        mock_settings.log_handlers = ["console", "file"]
        mock_settings.log_file = log_file

        with patch.object(log_module, "settings", mock_settings):
            logger = log_module.get("test.file_handler")

        assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)

    def test_file_handler_creates_parent_dir(self, tmp_path):
        log_file = tmp_path / "subdir" / "nested.log"
        from unittest.mock import MagicMock

        from wattnet.storage.utils import log as log_module

        mock_settings = MagicMock()
        mock_settings.log_level = "INFO"
        mock_settings.log_handlers = ["file"]
        mock_settings.log_file = log_file

        with patch.object(log_module, "settings", mock_settings):
            log_module.get("test.dir_creation")

        assert log_file.parent.exists()
