from core import ExamApp, load_config


def main() -> None:
    config = load_config()   # reads config.toml from the project root
    ExamApp(config).run()


if __name__ == "__main__":
    main()
