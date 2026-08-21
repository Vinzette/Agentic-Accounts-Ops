"""CLI entry point: generate a briefing for one or more accounts."""

import argparse

from dotenv import load_dotenv

from graph import build_graph

ACCOUNTS = ["nimbus", "corner_beverages", "zephyr"]


def main() -> None:
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
        result = app.invoke({"account_name": account_name})

        print(result["markdown"])
        if (attempts := result.get("attempts", 1)) > 1:
            print(f"Regenerated {attempts - 1}x after failing validation.")
        print(f"Saved to {result['output_path']}\n")


if __name__ == "__main__":
    main()
