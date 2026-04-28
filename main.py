from core import ExamApp, ExamConfig, load_config

_FALLBACK_CONFIG = ExamConfig(
    start_url="https://example.com/",
    quit_url="https://www.iana.org/domains/example",
    quit_password="admin123",
    window_title="Secure Exam Browser (Demo)",
    duration_minutes=75,
)


def main() -> None:
    try:
        config = load_config()
    except FileNotFoundError:
        config = _FALLBACK_CONFIG
    ExamApp(config).run()


if __name__ == "__main__":
    main()
