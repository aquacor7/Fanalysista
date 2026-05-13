"""
Download formations xlsx for every giornata in a (league, competition).

Usage:
    python download_all.py -l My League -c "Serie C"
    python download_all.py -l My League -c "Serie C" -t "My Team"
"""
import argparse

from cli import add_common_args, login_and_select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.add_argument(
        "--min-bytes", type=int, default=1024,
        help="Skip downloads smaller than this many bytes (default: 1024)",
    )
    args = parser.parse_args()

    client, _league, comp, out_dir = login_and_select(args)

    rounds = client.get_competition_rounds(comp.id)
    print(f"[rounds]     {len(rounds)} configured: {rounds[0]}..{rounds[-1]}")

    saved, skipped, failed = [], [], []
    for r in rounds:
        try:
            path = client.download_formations(comp.id, r, out_dir=out_dir)
        except Exception as e:
            print(f"  g{r:>2}: FAILED - {e}")
            failed.append(r)
            continue

        size = path.stat().st_size
        if size < args.min_bytes:
            path.unlink()
            print(f"  g{r:>2}: empty ({size} B), skipped")
            skipped.append(r)
        else:
            print(f"  g{r:>2}: {path.name}  ({size} B)")
            saved.append(r)

    print(f"\n[done] saved={len(saved)} skipped={len(skipped)} failed={len(failed)}")
    print(f"       out: {out_dir}/")


if __name__ == "__main__":
    main()
