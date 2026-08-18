import argparse

from dotenv import load_dotenv

from graph import build_graph

ACCOUNTS = ["nimbus", "corner_beverages", "zephyr"]


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Generate pre-call account briefing(s).")
    parser.add_argument(
        "--account",
        required=True,
        nargs="+",
        choices=ACCOUNTS,
        help="One or more accounts to generate a briefing for.",
    )
    args = parser.parse_args()

    app = build_graph()
    for account_name in args.account:
        app.invoke({"account_name": account_name})


if __name__ == "__main__":
    main()
