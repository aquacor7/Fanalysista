"""
Download the formations xlsx for one (league, competition, giornata).

Usage:
    python download_one.py -l My League -c "Serie C" -r 1
    python download_one.py -l My League -c "Serie C" -t "My Team" -r 1
"""
import argparse

from cli import add_common_args, login_and_select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.add_argument("-r", "--round", type=int, default=1, help="Giornata (default: 1)")
    args = parser.parse_args()

    client, _league, comp, out_dir = login_and_select(args)

    print(f"[download] giornata {args.round} -> {out_dir}/")
    path = client.download_formations(comp.id, args.round, out_dir=out_dir)
    print(f"           saved: {path.name}  ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
