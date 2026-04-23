from core import ExamApp, ExamConfig


def main() -> None:
    config = ExamConfig(
        start_url="https://www.codechef.com",
        quit_password="admin123",
        # Navigate the student to this URL to end the session without a password.
        # e.g. your platform's "submission confirmed" page.
        quit_url="https://www.codechef.com/ide",
        window_title="Secure Exam Browser",
    )
    ExamApp(config).run()


if __name__ == "__main__":
    main()
